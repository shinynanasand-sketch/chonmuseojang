"""카카오 질문 스킬. 관광객은 비교 추천, 운영자는 자기 마을만 답한다."""

from services.auth import get_operator_by_kakao_id
from services.kakao_client import (
    allow_external,
    build_error_skill_response,
    build_skill_response,
    seconds_remaining,
    time_budget_response,
)
from services.recommend import recommendation_lines, recommend_for_kakao
from services.supabase_client import get_village_by_id, list_recommend_villages
from services.tourapi import get_nearby_for_village

_MAX_TEXT = 1000
_NEARBY_MIN_SECONDS = 1.0


def _clip(text: str) -> str:
    flat = " ".join(str(text).split())
    if len(flat) <= _MAX_TEXT:
        return flat
    return flat[: _MAX_TEXT - 1] + "…"


def _nearby_timeout() -> float | None:
    """1초 이상 남았을 때만 주변 정보를 부른다. 제한 시간은 남은 예산이다."""
    remaining = seconds_remaining()
    if remaining is None or remaining < _NEARBY_MIN_SECONDS:
        return None
    return remaining


def _nearby_phrase(village_id: str, timeout: float) -> str:
    nearby = get_nearby_for_village(village_id, timeout=timeout)
    if nearby.get("status") == "unavailable":
        return "주변 정보는 지금 불러오지 못했습니다."
    attractions = [
        item.get("title")
        for item in (nearby.get("attractions") or [])
        if item.get("title")
    ][:3]
    restaurants = [
        item.get("title")
        for item in (nearby.get("restaurants") or [])
        if item.get("title")
    ][:2]
    parts = []
    if attractions:
        parts.append("주변 관광: " + ", ".join(attractions))
    if restaurants:
        parts.append("주변 음식: " + ", ".join(restaurants))
    if not parts:
        return "주변에 등록된 관광정보가 없습니다."
    return ". ".join(parts)


def _tourist_answer(utterance: str) -> dict:
    query = (utterance or "").strip()
    if not query:
        return build_error_skill_response("체험 종류나 시군 이름을 넣어 질문해 주세요.")
    if not allow_external():
        return time_budget_response()
    villages = list_recommend_villages()
    matches = recommend_for_kakao(query, villages, seconds_remaining())
    if not matches:
        return build_error_skill_response(
            "조건에 맞는 마을을 찾지 못했습니다. 체험 종류나 시군 이름을 넣어 주세요."
        )
    description = " / ".join(recommendation_lines(matches, villages))
    top_id = str(matches[0].get("village_id") or "")
    timeout = _nearby_timeout()
    if top_id and timeout is not None:
        description = f"{description}. {_nearby_phrase(top_id, timeout)}"
    return build_skill_response("추천", _clip(description))


def _operator_answer(operator: dict) -> dict:
    village_id = str(operator.get("village_id") or "")
    village = get_village_by_id(village_id) or {}
    name = village.get("village_name") or village_id or "우리 마을"
    sigungu = village.get("sigungu") or ""
    place = f"{name}({sigungu})" if sigungu else name
    timeout = _nearby_timeout() if village_id else None
    description = f"{place}. {_nearby_phrase(village_id, timeout)}" if timeout is not None else place
    return build_skill_response("우리 마을", _clip(description))


def answer_kakao_question(utterance: str, kakao_user_id: str) -> dict:
    if not allow_external():
        return time_budget_response()
    operator = get_operator_by_kakao_id(kakao_user_id) if kakao_user_id else None
    if operator:
        return _operator_answer(operator)
    return _tourist_answer(utterance)
