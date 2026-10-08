"""Phase A 여섯 블록. 응답에 context를 넣지 않는다."""

from models.kakao_schemas import KakaoSkillRequest
from services import booking, review
from services.auth import register_operator_with_ids, resolve_kakao_role
from services.kakao_client import (
    build_error_skill_response,
    build_list_card,
    build_skill_response,
)
from services.kakao_params import booking_id_from_params, representative
from services.recommend import keyword_recommendations
from services.supabase_client import list_public_villages

_BLOCKS = {
    "마을 추천": "recommend",
    "후기 조회": "reviews",
    "예약 현황 조회": "status",
    "예약승인": "approve",
    "예약거절": "reject",
    "운영자 등록": "register",
    "운영자등록": "register",
}

_APPROVE_GUIDE = "몇 번 예약을 승인하시겠어요? 예시: 7번 승인"
_REJECT_GUIDE = "몇 번 예약을 거절하시겠어요? 예시: 7번 거절"
_OPERATOR_ONLY = "등록된 운영자만 승인/거절할 수 있습니다."
_STATUS_HINT = "운영자는 등록 [마을명] [코드]로 등록할 수 있습니다."
_OTHER_VILLAGE = "이 예약을 처리할 권한이 없습니다."
_REGISTER_NEED = "마을명과 등록 코드를 한 문장으로 말해 주세요. 예시: 예시 갯벌마을 GB-001"
_STATUS_LABEL = {"pending": "대기", "confirmed": "승인", "rejected": "거절"}


def handle_phase_a(payload: KakaoSkillRequest) -> dict | None:
    """블록 이름 앞에서 운영자를 조회한다. 여섯 블록이 아니면 None."""
    user_id = str(payload.userRequest.user.get("id") or "")
    role = resolve_kakao_role(user_id)
    kind = _BLOCKS.get((payload.intent.name or "").strip())
    if kind is None:
        return None
    if kind == "recommend":
        return _recommend(payload.userRequest.utterance)
    if kind == "reviews":
        return _reviews(payload)
    if kind == "register":
        return _register(user_id, payload)
    if role["mode"] != "operator":
        hint = _STATUS_HINT if kind == "status" else _OPERATOR_ONLY
        return build_error_skill_response(hint)
    if kind == "status":
        return _status(str(role["village_id"]))
    return _decide(kind, str(role["village_id"]), payload)


def _recommend(utterance: str) -> dict:
    query = (utterance or "").strip()
    if not query:
        return build_error_skill_response("체험 종류나 시군 이름을 넣어 질문해 주세요.")
    villages = list_public_villages()
    matches = keyword_recommendations(query, villages)
    if not matches:
        return build_error_skill_response(
            "조건에 맞는 마을을 찾지 못했습니다. 조건을 조금 넓혀 주세요."
        )
    by_id = {row.get("village_id"): row for row in villages}
    items = []
    for item in matches:
        village = by_id.get(item.get("village_id"), {})
        place = str(village.get("sigungu") or village.get("address") or "")
        program = str(village.get("program_type") or "")
        reason = str(item.get("reason") or "")
        items.append(
            {
                "title": str(item.get("village_name") or "마을"),
                "description": " ".join(part for part in (place, program, reason) if part),
            }
        )
    return build_list_card("마을 추천", items)


def _reviews(payload: KakaoSkillRequest) -> dict:
    village_id = str(representative(payload.action.params, "village_id") or "").strip()
    if not village_id:
        return build_error_skill_response("어떤 마을 후기를 볼까요? 마을 이름을 말해 주세요.")
    rows = review.list_reviews_for_village(village_id)
    if not rows:
        return build_error_skill_response("등록된 후기가 없습니다.")
    items = [
        {
            "title": f"별점 {row.get('rating')}",
            "description": str(row.get("comment") or ""),
        }
        for row in rows
    ]
    return build_list_card("후기", items)


def _status(village_id: str) -> dict:
    rows = booking.list_bookings_for_village(village_id)
    if not rows:
        return build_error_skill_response("예약이 없습니다.")
    items = []
    for row in rows:
        label = _STATUS_LABEL.get(row.get("status"), row.get("status"))
        items.append(
            {
                "title": f"{row.get('booking_id')}번 {label}",
                "description": f"{row.get('visit_date')} {row.get('num_people')}명",
            }
        )
    return build_list_card("예약 현황", items)


def _register(user_id: str, payload: KakaoSkillRequest) -> dict:
    params = payload.action.params
    village_id = str(representative(params, "village_id") or "").strip()
    code = str(representative(params, "registration_code") or "").strip()
    if not village_id or not code:
        return build_error_skill_response(_REGISTER_NEED)
    result = register_operator_with_ids(user_id, village_id, code)
    if result.get("ok"):
        return build_skill_response(
            "등록 완료",
            f"{result['village_id']} 운영자로 등록되었습니다.",
        )
    return build_error_skill_response("등록 코드가 마을과 맞지 않습니다.")


def _decide(kind: str, village_id: str, payload: KakaoSkillRequest) -> dict:
    booking_id = booking_id_from_params(payload.action.params)
    if booking_id is None:
        guide = _APPROVE_GUIDE if kind == "approve" else _REJECT_GUIDE
        return build_error_skill_response(guide)
    existing = booking.get_booking_by_id(booking_id)
    if not existing:
        return build_error_skill_response("예약을 찾을 수 없습니다.")
    if existing.get("village_id") != village_id:
        return build_error_skill_response(_OTHER_VILLAGE)
    if kind == "approve":
        booking.update_booking_status(booking_id, "confirmed")
        return build_skill_response("승인 완료", "예약이 승인되었습니다.")
    booking.update_booking_status(booking_id, "rejected")
    return build_skill_response("거절 완료", "예약이 거절되었습니다.")
