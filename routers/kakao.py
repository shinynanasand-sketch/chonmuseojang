from fastapi import APIRouter

from models.kakao_schemas import KakaoSkillRequest
from services import auth, booking, kakao_client, review, trust_score
from services.auth import scoped_village_id

router = APIRouter(prefix="/kakao", tags=["kakao"])

DEFAULT_VILLAGE_ID = "V001"


@router.post("/booking")
async def kakao_booking(payload: KakaoSkillRequest):
    params = payload.action.params
    visit_date = params.get("visit_date")
    num_people = params.get("num_people")
    user_id = payload.userRequest.user.get("id", "")

    if not visit_date or not num_people:
        return kakao_client.build_error_skill_response("방문일과 인원수를 입력해 주세요.")

    new_booking = booking.create_booking(
        village_id=DEFAULT_VILLAGE_ID,
        customer_kakao_id=user_id,
        visit_date=str(visit_date),
        num_people=int(num_people),
    )
    kakao_client.send_kakao_notification_to_owner(
        DEFAULT_VILLAGE_ID, f"새 예약: {new_booking['booking_id']}"
    )
    return kakao_client.build_skill_response(
        "예약이 접수되었습니다",
        f"예약번호 {new_booking['booking_id']}번으로 접수되었습니다. 마을에서 확인 후 알려드릴게요.",
    )


@router.post("/approve")
async def kakao_approve(payload: KakaoSkillRequest):
    params = payload.action.params
    booking_id = params.get("booking_id")
    decision = params.get("decision", "")
    kakao_user_id = payload.userRequest.user.get("id", "")

    operator = auth.get_operator_by_kakao_id(kakao_user_id)
    if not operator:
        return kakao_client.build_error_skill_response("등록된 운영자만 승인/거절할 수 있습니다.")

    existing = booking.get_booking_by_id(booking_id) if booking_id else None
    if not existing:
        return kakao_client.build_error_skill_response("예약을 찾을 수 없습니다.")

    if existing["village_id"] != scoped_village_id(operator):
        return kakao_client.build_error_skill_response("자기 마을의 예약만 처리할 수 있습니다.")

    if decision == "approve":
        booking.update_booking_status(booking_id, "confirmed")
        kakao_client.send_kakao_notification_to_customer(
            existing["customer_kakao_id"], "예약이 승인되었습니다."
        )
        return kakao_client.build_skill_response("승인 완료", "예약이 승인되었습니다.")
    if decision == "reject":
        booking.update_booking_status(booking_id, "rejected")
        kakao_client.send_kakao_notification_to_customer(
            existing["customer_kakao_id"], "예약이 거절되었습니다."
        )
        return kakao_client.build_skill_response("거절 완료", "예약이 거절되었습니다.")

    return kakao_client.build_error_skill_response("승인 또는 거절을 선택해 주세요.")


@router.post("/review")
async def kakao_review(payload: KakaoSkillRequest):
    params = payload.action.params
    booking_id = params.get("booking_id")
    rating = params.get("rating")
    user_id = payload.userRequest.user.get("id", "")
    comment = payload.userRequest.utterance

    existing = booking.get_booking_by_id(booking_id) if booking_id else None
    village_id = existing["village_id"] if existing else DEFAULT_VILLAGE_ID

    sentiment = review.analyze_sentiment(comment)
    review.create_review(
        village_id=village_id,
        booking_id=booking_id or 0,
        customer_kakao_id=user_id,
        comment=comment,
        rating=int(rating) if rating else None,
        sentiment=sentiment,
    )
    trust_score.recalculate_for_village(village_id)
    return kakao_client.build_skill_response("후기 등록 완료", "소중한 후기 감사합니다!")
