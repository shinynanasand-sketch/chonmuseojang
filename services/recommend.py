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


def recommend_villages(user_query: str, village_rows: list[dict]) -> list[dict]:
    if not village_rows:
        return []

    try:
        llm = get_llm_provider()
        system_prompt = (
            "당신은 광주·전남 농촌체험마을 추천 도우미입니다. "
            "제공된 마을 목록 중에서 사용자 질문에 가장 적합한 마을을 최대 5곳 골라 "
            "JSON 배열로 village_id, village_name, reason 필드를 포함해 응답하세요."
        )
        context = format_village_context(village_rows)
        user_prompt = f"마을 목록:\n{context}\n\n사용자 질문: {user_query}"
        raw_response = llm.generate(system_prompt, user_prompt)
        return parse_recommendation_response(raw_response, village_rows)
    except Exception:
        return []
