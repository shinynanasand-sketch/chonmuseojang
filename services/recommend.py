import json
import re

from services.llm_provider import get_llm_provider


def format_village_context(village_rows: list[dict]) -> str:
    lines = []
    for row in village_rows[:20]:
        lines.append(
            f"- {row.get('village_id')}: {row.get('village_name')} "
            f"({row.get('sigungu')}, {row.get('program_type', '')})"
        )
    return "\n".join(lines)


def select_candidates(user_query: str, village_rows: list[dict], limit: int = 20) -> list[dict]:
    """질문과 겹치는 마을을 먼저 고르고, 없으면 목록 앞부분을 쓴다."""
    query = (user_query or "").strip()
    tokens = [token for token in re.split(r"\s+", query) if len(token) >= 2]
    matched = [row for row in village_rows if _keyword_reason(query, tokens, row)]
    if matched:
        return matched[:limit]
    return list(village_rows[:limit])


def parse_recommendation_response(raw_response: str, village_rows: list[dict]) -> list[dict]:
    try:
        match = re.search(r"\[.*\]", raw_response, re.DOTALL)
        if match:
            parsed = json.loads(match.group())
            if isinstance(parsed, list):
                return parsed[:5]
    except (json.JSONDecodeError, TypeError):
        pass
    return []


def keyword_recommendations(user_query: str, village_rows: list[dict]) -> list[dict]:
    """LLM 없이 마을명·시군구·프로그램이 질문과 겹치는 곳을 고른다."""
    query = (user_query or "").strip()
    if not query:
        return []
    tokens = [token for token in re.split(r"\s+", query) if len(token) >= 2]
    matches: list[dict] = []
    for row in village_rows:
        reason = _keyword_reason(query, tokens, row)
        if not reason:
            continue
        matches.append(
            {
                "village_id": row.get("village_id"),
                "village_name": row.get("village_name"),
                "reason": reason,
            }
        )
    return matches[:5]


def _keyword_reason(query: str, tokens: list[str], row: dict) -> str:
    checks = (
        ("program_type", "프로그램"),
        ("sigungu", "지역"),
        ("village_name", "마을 이름"),
    )
    for field, label in checks:
        value = str(row.get(field) or "").strip()
        if not value:
            continue
        if value in query or any(token in value for token in tokens):
            return f"{label} '{value}'이 질문과 맞습니다."
    return ""


def recommend_villages(user_query: str, village_rows: list[dict]) -> list[dict]:
    if not village_rows:
        return []

    candidates = select_candidates(user_query, village_rows)
    allowed_ids = {row.get("village_id") for row in candidates}
    try:
        llm = get_llm_provider()
        system_prompt = (
            "당신은 광주·전남 농촌체험마을 추천 도우미입니다. "
            "제공된 마을 목록 중에서 사용자 질문에 가장 적합한 마을을 최대 5곳 골라 "
            "JSON 배열로 village_id, village_name, reason 필드를 포함해 응답하세요."
        )
        context = format_village_context(candidates)
        user_prompt = f"마을 목록:\n{context}\n\n사용자 질문: {user_query}"
        raw_response = llm.generate(system_prompt, user_prompt)
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
