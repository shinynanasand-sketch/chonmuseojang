import json
import re

from services.llm_provider import get_llm_provider
from services.trust_score import calculate_trust_score

WEB_LLM_TIMEOUT = 8.0
KAKAO_LLM_TIMEOUT = 3.5
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


def parse_recommendation_response(raw_response: str, village_rows: list[dict]) -> list[dict]:
    text = (raw_response or "").strip()
    if not text:
        return []
    fenced = re.sub(r"^```(?:json)?\s*", "", text)
    fenced = re.sub(r"\s*```$", "", fenced).strip()
    parsed = None
    for candidate in (text, fenced):
        try:
            parsed = json.loads(candidate)
            break
        except json.JSONDecodeError:
            parsed = None
    if parsed is None:
        match = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
        if not match:
            return []
        try:
            parsed = json.loads(match.group(1))
        except json.JSONDecodeError:
            return []
    items = [item for item in _recommendation_items(parsed) if isinstance(item, dict)]
    return items[:_RESULT_LIMIT]


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


def recommend_villages(
    user_query: str,
    village_rows: list[dict],
    timeout: float = WEB_LLM_TIMEOUT,
) -> list[dict]:
    if not village_rows or not (user_query or "").strip():
        return []

    candidates = select_candidates(user_query, village_rows)
    allowed_ids = {row.get("village_id") for row in candidates}
    try:
        llm = get_llm_provider()
        context = format_village_context(candidates)
        user_prompt = f"마을 목록:\n{context}\n\n사용자 질문: {user_query}"
        raw_response = llm.generate(
            _SYSTEM_PROMPT,
            user_prompt,
            timeout=timeout,
            json_mode=True,
        )
        parsed = [
            item
            for item in parse_recommendation_response(raw_response, candidates)
            if item.get("village_id") in allowed_ids
        ]
        if parsed:
            return parsed
    except Exception:
        pass
    return keyword_recommendations(user_query, candidates)


def recommendation_lines(matches: list[dict], villages: list[dict], limit: int = _RESULT_LIMIT) -> list[str]:
    """카카오 simpleText용. 마을명 시군구. 한 줄 이유."""
    by_id = {row.get("village_id"): row for row in villages}
    lines = []
    seen_names: set[str] = set()
    for item in matches:
        name = str(item.get("village_name") or "마을")
        if name in seen_names:
            continue
        seen_names.add(name)
        village = by_id.get(item.get("village_id"), {})
        place = _plain(village.get("sigungu"))
        label = " ".join(part for part in (_plain(name), place) if part)
        reason = _plain(item.get("reason"))
        lines.append(f"{label}. {reason}" if reason else label)
        if len(lines) >= limit:
            break
    return lines
