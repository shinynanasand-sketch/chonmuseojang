"""카카오 질문 스킬. 관광객은 비교 추천, 운영자는 자기 마을만 답한다."""

from services.auth import get_operator_by_kakao_id
from services.kakao_client import build_error_skill_response, build_skill_response
from services.recommend import keyword_recommendations
from services.supabase_client import get_village_by_id, list_public_villages
from services.tourapi import get_nearby_for_village

_MAX_TEXT = 1000


def _clip(text: str) -> str:
    flat = " ".join(str(text).split())
    if len(flat) <= _MAX_TEXT:
        return flat
    return flat[: _MAX_TEXT - 1] + "…"


def _nearby_phrase(village_id: str) -> str:
    nearby = get_nearby_for_village(village_id)
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
    villages = list_public_villages()
    matches = keyword_recommendations(query, villages)[:2]
    if not matches:
        return build_error_skill_response(
            "조건에 맞는 마을을 찾지 못했습니다. 체험 종류나 시군 이름을 넣어 주세요."
        )
    bits = []
    for item in matches:
        village = next(
            (row for row in villages if row.get("village_id") == item.get("village_id")),
            {},
        )
        name = item.get("village_name") or "이름 없음"
        sigungu = village.get("sigungu") or ""
        place = f"{name}({sigungu})" if sigungu else name
        reason = item.get("reason") or ""
        bits.append(f"{place}. {reason}".strip().rstrip("."))
    top_id = str(matches[0].get("village_id") or "")
    description = ". ".join(bits)
    if top_id:
        description = f"{description}. {_nearby_phrase(top_id)}"
    return build_skill_response("추천", _clip(description))


def _operator_answer(operator: dict) -> dict:
    village_id = str(operator.get("village_id") or "")
    village = get_village_by_id(village_id) or {}
    name = village.get("village_name") or village_id or "우리 마을"
    sigungu = village.get("sigungu") or ""
    place = f"{name}({sigungu})" if sigungu else name
    description = f"{place}. {_nearby_phrase(village_id)}" if village_id else place
    return build_skill_response("우리 마을", _clip(description))


def answer_kakao_question(utterance: str, kakao_user_id: str) -> dict:
    operator = get_operator_by_kakao_id(kakao_user_id) if kakao_user_id else None
    if operator:
        return _operator_answer(operator)
    return _tourist_answer(utterance)
