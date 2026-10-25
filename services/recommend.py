import json
import os
import re
import time

import httpx

from services.llm_provider import LLMUnavailable, get_llm_provider, provider_has_key
from services.supabase_client import list_program_status_map
from services.trust_score import calculate_trust_score
from services.village_programs import programs_for

WEB_LLM_TIMEOUT = 8.0
KAKAO_LLM_TIMEOUT = 2.0
_KAKAO_LLM_FLOOR = 1.0
_MIN_SPARE_SECONDS = 2.0
_CANDIDATE_LIMIT = 20
_RESULT_LIMIT = 5

_SYNONYM_GROUPS = (
    ("아이", "어린이", "가족"),
    ("갯벌", "조개"),
    ("농사", "농촌"),
    ("숙박", "민박"),
)
_STOPWORDS = frozenset({"있는", "갈만한", "추천", "해주세요", "싶은", "어디"})
_SCORE_FIELDS = (
    ("program_type", 4, "프로그램"),
    ("program_name", 4, "프로그램"),
    ("sigungu", 4, "지역"),
    ("village_name", 5, "마을 이름"),
    ("facilities", 3, "시설"),
    ("address", 1, "주소"),
)
_SYSTEM_PROMPT = (
    "당신은 광주·전남 농촌체험마을 추천 도우미입니다. "
    "제공된 마을 목록 안에서만 최대 5곳을 고르세요. "
    "목록에 없는 village_id는 만들지 마세요. "
    "reason은 그 줄의 시군구, 체험, 프로그램명, 시설, 등급, 신뢰도에 적힌 말만 쓰세요. "
    "reason은 40자 이내의 한 문장입니다. 체험이나 프로그램 전체를 옮기지 마세요. "
    "예약, 연락처, 대표자, 등록 코드는 넣지 마세요. "
    "JSON으로만 응답하세요. 배열이거나 recommendations 배열을 가진 객체이며, "
    "각 원소는 village_id, village_name, reason 필드를 가집니다."
)


def _clip(value: object, limit: int = 40) -> str:
    flat = " ".join(str(value or "").split())
    if len(flat) <= limit:
        return flat
    return flat[: limit - 1] + "…"


def _plain(value: object) -> str:
    opened = (
        str(value or "")
        .replace("(", " ")
        .replace(")", " ")
        .replace("（", " ")
        .replace("）", " ")
        .replace("+", " ")
    )
    return " ".join(opened.split())


def _search_terms(query: str) -> list[str]:
    tokens = [
        token
        for token in re.split(r"\s+", query)
        if len(token) >= 2 and token not in _STOPWORDS
    ]
    terms = set(tokens)
    for group in _SYNONYM_GROUPS:
        if any(word in query for word in group):
            terms.update(word for word in group if len(word) >= 2)
    return [term for term in terms if term not in _STOPWORDS]


def _field_parts(row: dict, field: str) -> list[str]:
    value = str(row.get(field) or "").strip()
    if not value:
        return []
    if field == "program_type":
        parts = [part.strip() for part in value.split("+") if part.strip()]
        return parts or [value]
    return [value]


def _term_hits(query: str, terms: list[str], value: str) -> bool:
    if value in query:
        return True
    return any(term in value for term in terms)


def _trust_value(row: dict) -> float:
    raw = row.get("trust_score")
    if raw is not None and raw != "":
        try:
            return float(raw)
        except (TypeError, ValueError):
            return 0.0
    return float(calculate_trust_score(row))


def _grade_rank(row: dict) -> int:
    return 1 if str(row.get("grade") or "").strip() == "으뜸촌" else 0


def _match_score(query: str, terms: list[str], row: dict) -> tuple[int, str]:
    score = 0
    reason = ""
    for field, weight, label in _SCORE_FIELDS:
        matched = ""
        for part in _field_parts(row, field):
            if _term_hits(query, terms, part):
                matched = part
                break
        if not matched:
            continue
        score += weight
        if not reason:
            reason = f"{label} '{matched}'이 질문과 맞습니다."
    return score, reason


_REASON_LIMIT = 80


def _has_batchim(word: str) -> bool:
    if not word:
        return False
    code = ord(word[-1])
    if 0xAC00 <= code <= 0xD7A3:
        return (code - 0xAC00) % 28 != 0
    return False


def _concept(word: str) -> str:
    for group in _SYNONYM_GROUPS:
        if word in group:
            return group[0]
    return word


def _reason_word(query: str, terms: list[str], value: str) -> str:
    hitting = [term for term in terms if term and term in value]
    if value and value in query and value not in hitting:
        hitting.append(value)
    if not hitting:
        return ""
    group_words = {word for group in _SYNONYM_GROUPS for word in group}
    reduced = [
        term
        for term in hitting
        if not any(
            other != term and other in term and other in group_words and other in hitting
            for other in hitting
        )
    ]
    reduced.sort(key=lambda term: (0 if term in query else 1, len(term), term))
    return reduced[0]


def specific_reason(user_query: str, row: dict) -> str:
    """질문과 맞은 말, 프로그램명, 맞은 시설로 80자 이내 한 줄을 만든다."""
    query = (user_query or "").strip()
    terms = _search_terms(query)
    words: list[str] = []
    used: set[str] = set()
    matched_facility = ""
    any_match = False
    for field, _weight, _label in _SCORE_FIELDS:
        matched_part = ""
        for part in _field_parts(row, field):
            if _term_hits(query, terms, part):
                matched_part = part
                break
        if not matched_part:
            continue
        any_match = True
        word = _reason_word(query, terms, matched_part)
        concept = _concept(word) if word else ""
        if word and concept not in used and len(words) < 2:
            words.append(word)
            used.add(concept)
        if field == "facilities":
            matched_facility = matched_part
    program = str(row.get("program_name") or "").strip() or _primary_program(row)
    facility = matched_facility if any_match else str(row.get("facilities") or "").strip()
    detail = ", ".join(bit for bit in (_clip(program, 40), _clip(facility, 40)) if bit)
    if words:
        particle = "과" if _has_batchim(words[-1]) else "와"
        head = f"{'·'.join(words)}{particle} 맞습니다."
        sentence = f"{head} {detail}".strip() if detail else head
    else:
        sentence = detail
    if sentence and not sentence.endswith("."):
        sentence += "."
    return _clip(sentence, _REASON_LIMIT)


def _apply_specific_reasons(
    user_query: str, matches: list[dict], village_rows: list[dict]
) -> list[dict]:
    by_id = {row.get("village_id"): row for row in village_rows}
    applied = []
    for item in matches:
        row = by_id.get(item.get("village_id"), {})
        applied.append({**item, "reason": specific_reason(user_query, row)})
    return applied


def _quality_key(row: dict, index: int) -> tuple:
    return (-_trust_value(row), -_grade_rank(row), index)


def _primary_program(row: dict) -> str:
    parts = _field_parts(row, "program_type")
    return parts[0] if parts else ""


def _diverse_candidates(village_rows: list[dict], limit: int) -> list[dict]:
    """점수가 없을 때는 체험유형이 겹치지 않게 신뢰도가 높은 마을만 고른다."""
    best: dict[str, tuple[int, dict]] = {}
    for index, row in enumerate(village_rows):
        key = _primary_program(row)
        current = best.get(key)
        if current is None or _quality_key(row, index) < _quality_key(current[1], current[0]):
            best[key] = (index, row)
    ordered = sorted(best.values(), key=lambda pair: _quality_key(pair[1], pair[0]))
    return [row for _, row in ordered[:limit]]


def format_village_context(village_rows: list[dict]) -> str:
    lines = []
    for row in village_rows[:_CANDIDATE_LIMIT]:
        bits = [
            f"- {row.get('village_id')}: {_clip(row.get('village_name'))}",
            f"시군구 {_clip(row.get('sigungu'), 20)}",
            f"체험 {_clip(row.get('program_type'))}",
            f"프로그램명 {_clip(row.get('program_name'))}",
            f"시설 {_clip(row.get('facilities'))}",
            f"등급 {_clip(row.get('grade'), 20)}",
            f"신뢰도 {_trust_value(row):.0f}",
        ]
        address = _clip(row.get("address"))
        if address:
            bits.append(f"주소 {address}")
        lines.append(", ".join(bits))
    return "\n".join(lines)


def select_candidates(user_query: str, village_rows: list[dict], limit: int = _CANDIDATE_LIMIT) -> list[dict]:
    """질문과 겹치는 마을을 점수순으로 고르고, 없으면 체험유형이 다른 마을만 고른다."""
    query = (user_query or "").strip()
    if not query or not village_rows:
        return []
    terms = _search_terms(query)
    scored = []
    for index, row in enumerate(village_rows):
        score, _reason = _match_score(query, terms, row)
        if score:
            scored.append((index, row, score))
    if not scored:
        return _diverse_candidates(village_rows, limit)
    scored.sort(key=lambda item: (-item[2],) + _quality_key(item[1], item[0]))
    return [row for _index, row, _score in scored[:limit]]


def _recommendation_items(parsed: object) -> list:
    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, dict):
        for key in ("recommendations", "results", "villages"):
            value = parsed.get(key)
            if isinstance(value, list):
                return value
    return []


def _now() -> float:
    return time.monotonic()


def _load_recommendation_json(raw_response: str):
    text = (raw_response or "").strip()
    if not text:
        return None
    fenced = re.sub(r"^```(?:json)?\s*", "", text)
    fenced = re.sub(r"\s*```$", "", fenced).strip()
    for candidate in (text, fenced):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    match = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


def _is_recommendation_document(parsed: object) -> bool:
    if isinstance(parsed, list):
        return True
    if isinstance(parsed, dict):
        return any(isinstance(parsed.get(key), list) for key in ("recommendations", "results", "villages"))
    return False


def parse_recommendation_response(raw_response: str, village_rows: list[dict]) -> list[dict]:
    parsed = _load_recommendation_json(raw_response)
    if not _is_recommendation_document(parsed):
        return []
    items = [item for item in _recommendation_items(parsed) if isinstance(item, dict)]
    return items[:_RESULT_LIMIT]


def _recommendation_outcome(raw_response: str, village_rows: list[dict]) -> tuple[str, list[dict]]:
    parsed = _load_recommendation_json(raw_response)
    if not _is_recommendation_document(parsed):
        return "invalid", []
    allowed_ids = {row.get("village_id") for row in village_rows}
    items = [item for item in _recommendation_items(parsed) if isinstance(item, dict)]
    kept = [item for item in items[:_RESULT_LIMIT] if item.get("village_id") in allowed_ids]
    if kept:
        return "ok", kept
    if items:
        return "rejected", []
    return "empty", []


def _recommend_provider_names() -> list[str]:
    primary = os.getenv("LLM_PROVIDER", "gemini").lower()
    if primary == "openai":
        return ["openai", "gemini"]
    if primary == "claude":
        return ["claude"]
    return ["gemini", "openai"]


def _providers_to_call() -> list[str]:
    names = _recommend_provider_names()
    ready = [name for name in names if provider_has_key(name)]
    if ready:
        return ready
    return names[:1]


def keyword_recommendations(user_query: str, village_rows: list[dict]) -> list[dict]:
    """LLM 없이 마을명·시군구·프로그램·시설·주소가 질문과 겹치는 곳을 고른다."""
    query = (user_query or "").strip()
    if not query:
        return []
    terms = _search_terms(query)
    scored = []
    for index, row in enumerate(village_rows):
        score, reason = _match_score(query, terms, row)
        if not score:
            continue
        scored.append((index, row, score, reason))
    scored.sort(key=lambda item: (-item[2],) + _quality_key(item[1], item[0]))
    matches = []
    for _index, row, _score, reason in scored[:_RESULT_LIMIT]:
        matches.append(
            {
                "village_id": row.get("village_id"),
                "village_name": row.get("village_name"),
                "reason": reason,
            }
        )
    return matches


def recommend_for_kakao(
    user_query: str, village_rows: list[dict], remaining: float | None
) -> list[dict]:
    """남은 시간이 1초 미만이면 LLM을 호출하지 않고 키워드 추천을 반환한다."""
    if not village_rows or not (user_query or "").strip():
        return []
    if remaining is not None and remaining < _KAKAO_LLM_FLOOR:
        candidates = select_candidates(user_query, village_rows)
        return _apply_specific_reasons(
            user_query, keyword_recommendations(user_query, candidates), candidates
        )
    timeout = KAKAO_LLM_TIMEOUT if remaining is None else min(KAKAO_LLM_TIMEOUT, remaining)
    return recommend_villages(user_query, village_rows, timeout=timeout)


def recommend_villages(
    user_query: str,
    village_rows: list[dict],
    timeout: float = WEB_LLM_TIMEOUT,
) -> list[dict]:
    if not village_rows or not (user_query or "").strip():
        return []

    candidates = select_candidates(user_query, village_rows)
    context = format_village_context(candidates)
    user_prompt = f"마을 목록:\n{context}\n\n사용자 질문: {user_query}"
    deadline = _now() + timeout
    for index, name in enumerate(_providers_to_call()):
        remaining = deadline - _now()
        if index > 0 and remaining < _MIN_SPARE_SECONDS:
            break
        call_timeout = timeout if index == 0 else remaining
        try:
            llm = get_llm_provider(name)
            raw_response = llm.generate(
                _SYSTEM_PROMPT,
                user_prompt,
                timeout=call_timeout,
                json_mode=True,
            )
        except httpx.TimeoutException:
            break
        except LLMUnavailable:
            continue
        except Exception:
            break
        kind, parsed = _recommendation_outcome(raw_response, candidates)
        if kind == "ok":
            return _apply_specific_reasons(user_query, parsed, candidates)
        if kind == "invalid":
            continue
        break
    return _apply_specific_reasons(
        user_query, keyword_recommendations(user_query, candidates), candidates
    )


def _mark_stopped_programs(reason: str, programs: list[dict]) -> str:
    """이유에 들어 있는 꺼진 항목만 운영하지 않는다고 바꾼다."""
    stopped = [
        str(item.get("label") or "")
        for item in programs
        if item.get("label") and not item.get("is_operating") and str(item["label"]) in reason
    ]
    if not stopped:
        return reason
    stopped.sort(key=len, reverse=True)
    pattern = "|".join(re.escape(label) for label in stopped)

    def replace(match: re.Match) -> str:
        label = match.group(0)
        particle = "은" if _has_batchim(label) else "는"
        return f"{label}{particle} 지금은 운영하지 않음"

    return re.sub(pattern, replace, reason)


def _program_status(village_ids: list[str]) -> dict[str, list[dict]]:
    """예산이 거의 없으면 운영 여부 조회를 건너뛴다."""
    from services.kakao_client import allow_external

    if not allow_external():
        return {}
    return list_program_status_map(village_ids)


def recommendation_lines(matches: list[dict], villages: list[dict], limit: int = _RESULT_LIMIT) -> list[str]:
    """카카오 simpleText용. 마을명 시군구. 한 줄 이유."""
    by_id = {row.get("village_id"): row for row in villages}
    chosen = []
    seen_names: set[str] = set()
    for item in matches:
        name = str(item.get("village_name") or "마을")
        if name in seen_names:
            continue
        seen_names.add(name)
        chosen.append(item)
        if len(chosen) >= limit:
            break
    status_map = _program_status([str(item.get("village_id") or "") for item in chosen])
    lines = []
    for item in chosen:
        village = by_id.get(item.get("village_id"), {})
        village_id = str(village.get("village_id") or item.get("village_id") or "")
        place = _plain(village.get("sigungu"))
        name = str(item.get("village_name") or "마을")
        label = " ".join(part for part in (_plain(name), place) if part)
        programs = programs_for(village, status_map.get(village_id, []))
        reason = _plain(_mark_stopped_programs(str(item.get("reason") or ""), programs))
        lines.append(f"{label}. {reason}" if reason else label)
    return lines
