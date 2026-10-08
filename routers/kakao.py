from typing import Any

from fastapi import APIRouter

from models.kakao_schemas import KakaoSkillRequest
from services import auth, booking, kakao_client, review, trust_score
from services.kakao_ask import answer_kakao_question
from services.kakao_client import skill_http_response
from services.kakao_phase_a import handle_phase_a

router = APIRouter(prefix="/kakao", tags=["kakao"])

DEFAULT_VILLAGE_ID = "V001"


def _skill_json(body: dict):
    return skill_http_response(body)


def _phase_a(payload: KakaoSkillRequest):
    body = handle_phase_a(payload)
    if body is None:
        return None
    return _skill_json(body)


def _param_str(params: dict[str, Any], key: str) -> str:
    value = params.get(key)
    if value is None:
        return ""
    if isinstance(value, dict):
        nested = value.get("value") or value.get("origin") or ""
        return str(nested).strip()
    return str(value).strip()


def _parse_int(value: str) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


@router.post("/ping")
async def kakao_ping():
    """오픈빌더 연결 격리 테스트용 — 가이드 예제와 동일한 simpleText만 반환."""
    return _skill_json(
        {
            "version": "2.0",
            "template": {
                "outputs": [{"simpleText": {"text": "스킬 연결 OK"}}]
            },
        }
    )


@router.post("/ask")
async def kakao_ask(payload: KakaoSkillRequest):
    """관광객은 비교 추천, 운영자는 자기 마을과 주변정보만 답한다."""
    handled = _phase_a(payload)
    if handled is not None:
        return handled
    utterance = (payload.userRequest.utterance or "").strip() or _param_str(
        payload.action.params, "query"
    )
    user_id = str(payload.userRequest.user.get("id") or "")
    return _skill_json(answer_kakao_question(utterance, user_id))


_REGISTER_HINT = "운영자는 등록 [마을명] [코드]로 등록할 수 있습니다."


def _inquiry_response(utterance: str, user_id: str):
    if utterance.startswith("등록 "):
        result = auth.register_operator(user_id, utterance)
        if result.get("ok"):
            return kakao_client.build_skill_response(
                "등록 완료",
                f"{result['village_id']} 운영자로 등록되었습니다.",
            )
        return kakao_client.build_error_skill_response(_REGISTER_HINT)

    if utterance == "예약 현황":
        role = auth.resolve_kakao_role(user_id)
        if role["mode"] != "operator":
            return kakao_client.build_error_skill_response(_REGISTER_HINT)
        lines = booking.format_booking_lines(booking.list_bookings_for_operator(user_id))
        return kakao_client.build_skill_response("예약 현황", lines)

    if utterance == "내 예약":
        lines = booking.format_booking_lines(booking.list_my_bookings(user_id))
        return kakao_client.build_skill_response("내 예약", lines)

    return None


@router.post("/booking")
async def kakao_booking(payload: KakaoSkillRequest):
    handled = _phase_a(payload)
    if handled is not None:
        return handled
    params = payload.action.params
    utterance = (payload.userRequest.utterance or "").strip()
    user_id = str(payload.userRequest.user.get("id") or "")

    inquiry = _inquiry_response(utterance, user_id)
    if inquiry is not None:
        return _skill_json(inquiry)

    visit_date = _param_str(params, "visit_date")
    num_people_raw = _param_str(params, "num_people")

    if not visit_date or not num_people_raw:
        return _skill_json(
            kakao_client.build_error_skill_response("방문일과 인원수를 입력해 주세요.")
        )

    num_people = _parse_int(num_people_raw)
    if num_people is None or num_people < 1:
        return _skill_json(
            kakao_client.build_error_skill_response("인원수는 숫자로 입력해 주세요.")
        )

    village_id = _param_str(params, "village_id") or DEFAULT_VILLAGE_ID
    new_booking = booking.create_booking(
        village_id=village_id,
        customer_kakao_id=user_id,
        visit_date=visit_date,
        num_people=num_people,
    )
    return _skill_json(
        kakao_client.build_skill_response(
            "예약이 접수되었습니다",
            f"예약번호 {new_booking['booking_id']}번으로 접수되었습니다. 상태는 '내 예약'으로 확인할 수 있습니다.",
        )
    )


@router.post("/approve")
async def kakao_approve(payload: KakaoSkillRequest):
    handled = _phase_a(payload)
    if handled is not None:
        return handled
    params = payload.action.params
    booking_id = _param_str(params, "booking_id")
    decision = _param_str(params, "decision")
    kakao_user_id = str(payload.userRequest.user.get("id") or "")

    role = auth.resolve_kakao_role(kakao_user_id)
    if role["mode"] != "operator":
        return _skill_json(
            kakao_client.build_error_skill_response("등록된 운영자만 승인/거절할 수 있습니다.")
        )

    existing = booking.get_booking_by_id(booking_id) if booking_id else None
    if not existing:
        return _skill_json(kakao_client.build_error_skill_response("예약을 찾을 수 없습니다."))

    try:
        village_id = auth.scoped_village_id(kakao_user_id)
    except PermissionError:
        return _skill_json(
            kakao_client.build_error_skill_response("등록된 운영자만 승인/거절할 수 있습니다.")
        )

    if existing["village_id"] != village_id:
        return _skill_json(
            kakao_client.build_error_skill_response("자기 마을의 예약만 처리할 수 있습니다.")
        )

    if decision == "approve":
        booking.update_booking_status(booking_id, "confirmed")
        return _skill_json(
            kakao_client.build_skill_response("승인 완료", "예약이 승인되었습니다.")
        )
    if decision == "reject":
        booking.update_booking_status(booking_id, "rejected")
        return _skill_json(
            kakao_client.build_skill_response("거절 완료", "예약이 거절되었습니다.")
        )

    return _skill_json(
        kakao_client.build_error_skill_response("승인 또는 거절을 선택해 주세요.")
    )


@router.post("/review")
async def kakao_review(payload: KakaoSkillRequest):
    handled = _phase_a(payload)
    if handled is not None:
        return handled
    params = payload.action.params
    booking_id_raw = _param_str(params, "booking_id")
    rating_raw = _param_str(params, "rating")
    user_id = str(payload.userRequest.user.get("id") or "")
    comment = payload.userRequest.utterance

    booking_id = _parse_int(booking_id_raw) if booking_id_raw else 0
    if booking_id_raw and booking_id is None:
        return _skill_json(
            kakao_client.build_error_skill_response("예약번호는 숫자로 입력해 주세요.")
        )

    rating = _parse_int(rating_raw) if rating_raw else None
    if rating_raw and rating is None:
        return _skill_json(
            kakao_client.build_error_skill_response("별점은 숫자로 입력해 주세요.")
        )

    existing = booking.get_booking_by_id(booking_id) if booking_id else None
    village_id = existing["village_id"] if existing else DEFAULT_VILLAGE_ID

    sentiment = review.analyze_sentiment(comment)
    review.create_review(
        village_id=village_id,
        booking_id=booking_id or 0,
        customer_kakao_id=user_id,
        comment=comment,
        rating=rating,
        sentiment=sentiment,
    )
    trust_score.recalculate_for_village(village_id)
    return _skill_json(
        kakao_client.build_skill_response("후기 등록 완료", "소중한 후기 감사합니다!")
    )
