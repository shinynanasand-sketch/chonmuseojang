"""Phase A 여섯 블록. 응답에 context를 넣지 않는다."""

from urllib.parse import urlparse

from models.kakao_schemas import KakaoSkillRequest
from services import booking, review
from services.auth import get_operator_by_kakao_id, register_operator_with_ids, resolve_kakao_role
from services.kakao_client import build_error_skill_response, build_skill_response
from services.kakao_params import booking_id_from_params, kakao_photo_url, representative
from services.operator_assistant import (
    PhotoRejected,
    _kakao_photo_host,
    download_kakao_photo,
    save_operator_photo_draft,
)
from services.recommend import KAKAO_LLM_TIMEOUT, recommendation_lines, recommend_villages
from services.supabase_client import list_public_villages

_BLOCKS = {
    "마을 추천": "recommend",
    "후기 조회": "reviews",
    "예약 현황 조회": "status",
    "예약승인": "approve",
    "예약거절": "reject",
    "운영자 등록": "register",
    "운영자등록": "register",
    "홍보 사진": "promo_photo",
}

_APPROVE_GUIDE = "몇 번 예약을 승인하시겠어요? 예시: 7번 승인"
_REJECT_GUIDE = "몇 번 예약을 거절하시겠어요? 예시: 7번 거절"
_OPERATOR_ONLY = "등록된 운영자만 승인/거절할 수 있습니다."
_STATUS_HINT = "운영자는 등록 [마을명] [코드]로 등록할 수 있습니다."
_OTHER_VILLAGE = "이 예약을 처리할 권한이 없습니다."
_REGISTER_NEED = "마을명과 등록 코드를 한 문장으로 말해 주세요. 예시: 예시 갯벌마을 GB-001"
_PHOTO_GUIDE = "사진을 한 장 올려 주세요."
_PHOTO_FAILED = "홍보문구를 만들지 못했습니다."
_PHOTO_PUBLISH = "웹에서 관광객에게 공개를 누르면 마을 화면에 나갑니다."
_STATUS_LABEL = {"pending": "대기", "confirmed": "승인", "rejected": "거절"}


def _skill_lines(title: str, lines: list[str], total: int) -> dict:
    shown = [line for line in lines if line][:5]
    heading = "최근 5건" if total > 5 else title
    return build_skill_response(heading, " / ".join(shown))


def _https_host(url: str, allowed) -> bool:
    parsed = urlparse(url or "")
    return parsed.scheme == "https" and allowed(parsed.hostname or "")


def _kakao_callback_host(host: str) -> bool:
    name = (host or "").lower().rstrip(".")
    return name == "kakao.com" or name.endswith(".kakao.com")


def promo_photo_should_defer(payload: KakaoSkillRequest) -> bool:
    """운영자의 카카오 사진과 콜백 주소가 있을 때만 별도 실행으로 넘긴다."""
    if (payload.intent.name or "").strip() != "홍보 사진":
        return False
    user_id = str(payload.userRequest.user.get("id") or "")
    if resolve_kakao_role(user_id)["mode"] != "operator":
        return False
    if not _https_host(kakao_photo_url(payload), _kakao_photo_host):
        return False
    return _https_host(payload.userRequest.callbackUrl, _kakao_callback_host)


def finish_promo_photo(payload: KakaoSkillRequest) -> dict:
    user_id = str(payload.userRequest.user.get("id") or "")
    return _promo_photo(user_id, resolve_kakao_role(user_id), payload)


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
    if kind == "promo_photo":
        return _promo_photo(user_id, role, payload)
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
    matches = recommend_villages(query, villages, timeout=KAKAO_LLM_TIMEOUT)
    if not matches:
        return build_error_skill_response(
            "조건에 맞는 마을을 찾지 못했습니다. 조건을 조금 넓혀 주세요."
        )
    items = recommendation_lines(matches, villages)
    return _skill_lines("마을 추천", items, len(items))


def _reviews(payload: KakaoSkillRequest) -> dict:
    village_id = str(representative(payload.action.params, "village_id") or "").strip()
    if not village_id:
        return build_error_skill_response("어떤 마을 후기를 볼까요? 마을 이름을 말해 주세요.")
    rows = review.list_reviews_for_village(village_id)
    if not rows:
        return build_error_skill_response("등록된 후기가 없습니다.")
    lines = [
        " ".join(part for part in (f"별점 {row.get('rating')}", str(row.get("comment") or "").strip()) if part)
        for row in rows
    ]
    return _skill_lines("후기", lines, len(rows))


def _status(village_id: str) -> dict:
    rows = booking.list_bookings_for_village(village_id)
    if not rows:
        return build_error_skill_response("예약이 없습니다.")
    lines = []
    for row in rows:
        label = _STATUS_LABEL.get(row.get("status"), row.get("status"))
        lines.append(f"{row.get('booking_id')}번 {label} {row.get('visit_date')} {row.get('num_people')}명")
    return _skill_lines("예약 현황", lines, len(rows))


def _promo_photo(user_id: str, role: dict, payload: KakaoSkillRequest) -> dict:
    if role["mode"] != "operator":
        return build_error_skill_response(_STATUS_HINT)
    url = kakao_photo_url(payload)
    if not url:
        return build_error_skill_response(_PHOTO_GUIDE)
    if not _https_host(url, _kakao_photo_host):
        return build_error_skill_response(_PHOTO_GUIDE)
    if not _https_host(payload.userRequest.callbackUrl, _kakao_callback_host):
        return build_error_skill_response(_PHOTO_FAILED)
    try:
        photo = download_kakao_photo(url)
    except PhotoRejected as exc:
        return build_error_skill_response(exc.message)
    operator = get_operator_by_kakao_id(user_id)
    if not operator:
        return build_error_skill_response(_STATUS_HINT)
    result = save_operator_photo_draft(operator, photo)
    if not result.get("saved"):
        return build_error_skill_response(str(result.get("message") or _PHOTO_FAILED))
    bodies = {row.get("content_type"): row.get("body") for row in result.get("contents") or []}
    description = f"{bodies.get('소개글', '')} {bodies.get('SNS홍보문구', '')} {_PHOTO_PUBLISH}"
    return build_skill_response("홍보문구", description)


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
