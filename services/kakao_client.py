"""카카오 스킬 응답 포맷. 이벤트 API는 예약 접수·승인·거절 뒤에만 호출한다."""

import contextvars
import json
import logging
import os
import re
import time
from urllib.parse import urlparse

import httpx
from starlette.responses import Response

logger = logging.getLogger(__name__)

_SKILL_TEXT_LIMIT = 1000
_reply_user_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "kakao_reply_user_id", default=""
)
_SKILL_BUDGET_SECONDS = 4.0
_MIN_EXTERNAL_SECONDS = 0.4
_skill_deadline: contextvars.ContextVar[float | None] = contextvars.ContextVar(
    "kakao_skill_deadline", default=None
)
_VILLAGE_REPLIES = ("예약 현황 조회", "체험 달력 조회", "체험 글 조회", "홍보 사진")
_PROGRAM_REPLIES = ("체험 달력 조회", "체험 글 조회", "체험 글 저장")
_GUIDE_REPLIES = ("등록 안내", "사용 안내")
_TOURIST_REPLIES = ("마을 추천", "예약하기", "내 예약", "후기 보기")


def bind_reply_user(user_id: str):
    """이 요청의 스킬 응답에 넣을 바로연결 대상을 정한다."""
    return _reply_user_id.set(user_id or "")


def reset_reply_user(token) -> None:
    _reply_user_id.reset(token)


def bind_skill_deadline():
    """카카오 5초 제한 안에 200을 돌려주기 위한 요청 예산."""
    return _skill_deadline.set(time.monotonic() + _SKILL_BUDGET_SECONDS)


def reset_skill_deadline(token) -> None:
    _skill_deadline.reset(token)


def seconds_remaining() -> float | None:
    """스킬 예산이 없으면 None. 있으면 남은 초."""
    deadline = _skill_deadline.get()
    if deadline is None:
        return None
    return deadline - time.monotonic()


def allow_external(minimum: float = _MIN_EXTERNAL_SECONDS) -> bool:
    """예산이 없거나 최소 시간 이상 남았을 때만 외부 호출을 시작한다."""
    remaining = seconds_remaining()
    if remaining is None:
        return True
    return remaining >= minimum


def time_budget_response() -> dict:
    return build_error_skill_response("잠시 후 다시 시도해 주세요.")


def _reply_labels(operator: dict | None) -> tuple[str, ...]:
    """운영자는 자기 역할 버튼, 관광객은 마을 추천·예약·내 예약·후기 보기."""
    if not operator:
        return _TOURIST_REPLIES
    role = str(operator.get("role") or "village")
    if role == "village":
        return (*_VILLAGE_REPLIES, *_GUIDE_REPLIES)
    if role == "program":
        return (*_PROGRAM_REPLIES, *_GUIDE_REPLIES)
    return ()


def _quick_replies(user_id: str) -> list[dict]:
    """등록된 발화를 버튼으로 보낸다. 관광객에게는 운영자 버튼을 넣지 않는다."""
    if not user_id or not allow_external():
        return []
    from services.supabase_client import get_operator_by_kakao_id

    labels = _reply_labels(get_operator_by_kakao_id(user_id))
    return [
        {"label": label, "action": "message", "messageText": label}
        for label in labels
    ]


def build_skill_response(title: str, description: str) -> dict:
    """카카오 스킬 응답 (simpleText). 제목을 붙인 뒤 1000자·한 줄로 자른다."""
    text = f"{title}. {description}".strip() if description else title
    text = " ".join(text.split())
    if len(text) > _SKILL_TEXT_LIMIT:
        text = text[: _SKILL_TEXT_LIMIT - 1] + "…"
    template: dict = {
        "outputs": [
            {
                "simpleText": {
                    "text": text,
                }
            }
        ]
    }
    replies = _quick_replies(_reply_user_id.get())
    if replies:
        template["quickReplies"] = replies
    return {
        "version": "2.0",
        "template": template,
    }


def build_error_skill_response(message: str) -> dict:
    return build_skill_response("안내", message)


def attach_guide_card(body: dict) -> dict:
    """등록·사용 안내 웹을 여는 카드. 바로연결은 웹 주소를 열지 못한다."""
    from config import KAKAO_CARD_IMAGE_URL
    from services.guide_access import guide_page_url

    outputs = body.setdefault("template", {}).setdefault("outputs", [])
    outputs.append(
        {
            "basicCard": {
                "title": "안내",
                "description": "등록 문장과 사용 방법을 웹에서 봅니다.",
                "thumbnail": {"imageUrl": KAKAO_CARD_IMAGE_URL},
                "buttons": [
                    {
                        "action": "webLink",
                        "label": "등록 안내 열기",
                        "webLinkUrl": guide_page_url("/guide/register"),
                    },
                    {
                        "action": "webLink",
                        "label": "사용 안내 열기",
                        "webLinkUrl": guide_page_url("/guide/use"),
                    },
                ],
            }
        }
    )
    return body


def guide_skill_response(utterance: str) -> dict:
    if utterance == "사용 안내":
        text = "버튼, 달력, 예약 방법은 사용 안내에서 확인합니다."
    else:
        text = "마을 이름, 등록 코드, 체험 이름은 등록 안내에서 확인합니다."
    return attach_guide_card(build_skill_response("안내", text))


def _clip_chars(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit]


_KAKAO_KEEP = re.compile(r"[^0-9가-힣\-\s]")


def _kakao_plain(text: str) -> str:
    """괄호는 공백으로 열고, +와 그 밖 기호는 빼서 한글·숫자·하이픈만 남긴다."""
    opened = (
        text.replace("(", " ")
        .replace(")", " ")
        .replace("（", " ")
        .replace("）", " ")
        .replace("+", "")
    )
    return " ".join(_KAKAO_KEEP.sub("", opened).split())


def build_list_card(header: str, items: list[dict]) -> dict:
    """성공 목록. 리스트형 말풍선 글자 수에 맞춘다."""
    shown = items[:5]
    title = "최근 5건" if len(items) > 5 else header
    card_items = []
    for item in shown:
        description = _clip_chars(_kakao_plain(str(item.get("description") or "")), 14)
        item_title = _kakao_plain(str(item.get("title") or "")) or "마을"
        if description:
            card_items.append(
                {
                    "title": _clip_chars(item_title, 30),
                    "description": description,
                }
            )
        else:
            card_items.append({"title": _clip_chars(item_title, 35)})
    return {
        "version": "2.0",
        "template": {
            "outputs": [
                {
                    "listCard": {
                        "header": {"title": _clip_chars(title, 15)},
                        "items": card_items,
                    }
                }
            ]
        },
    }


def post_skill_callback(url: str, body: dict) -> None:
    """스킬 콜백 주소로 최종 simpleText를 보낸다. 이벤트 API는 쓰지 않는다."""
    parsed = urlparse(url or "")
    host = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme != "https" or not (host == "kakao.com" or host.endswith(".kakao.com")):
        return
    try:
        with httpx.Client(timeout=5.0) as client:
            client.post(url, json=body)
    except Exception as exc:
        logger.warning("카카오 스킬 콜백 실패: %s", exc)


def skill_http_response(body: dict) -> Response:
    """오픈빌더가 파싱하기 쉬운 UTF-8 JSON 원문 응답."""
    return Response(
        content=json.dumps(body, ensure_ascii=False),
        media_type="application/json; charset=utf-8",
        status_code=200,
    )


_EVENT_TIMEOUT = 2.0


def event_talk_url(bot_id: str) -> str:
    return f"https://bot-api.kakao.com/v2/bots/{bot_id}/talk"


def send_kakao_event(event_name: str, user_id: str, data: dict) -> bool:
    """챗봇 이벤트 API. 키가 없거나 카카오가 거절하면 False. 예외는 올리지 않는다."""
    rest_key = os.getenv("KAKAO_REST_API_KEY", "").strip()
    bot_id = os.getenv("KAKAO_BOT_ID", "").strip()
    if not rest_key or not bot_id or not user_id:
        logger.info("카카오 이벤트 API 생략: %s", event_name)
        return False
    body = {
        "event": {
            "name": event_name,
            "data": {key: "" if value is None else str(value) for key, value in data.items()},
        },
        "user": [{"type": "botUserKey", "id": user_id}],
    }
    try:
        with httpx.Client(timeout=_EVENT_TIMEOUT) as client:
            response = client.post(
                event_talk_url(bot_id),
                headers={
                    "Authorization": f"KakaoAK {rest_key}",
                    "Content-Type": "application/json",
                },
                json=body,
            )
        try:
            payload = response.json()
        except Exception:
            payload = {}
        status = str(payload.get("status") or "")
        if response.status_code >= 400 or status in {"FAIL", "ERROR"}:
            logger.info("카카오 이벤트 API 거절: %s %s", event_name, payload.get("message") or status or response.status_code)
            return False
        return status == "SUCCESS"
    except Exception as exc:
        logger.warning("카카오 이벤트 API 발송 실패: %s", exc)
        return False


def notify_booking_received(booking: dict) -> None:
    """예약 접수 선톡. 그 마을의 마을 운영자에게만 보낸다."""
    from services.supabase_client import get_village_operator

    operator = get_village_operator(str(booking.get("village_id") or ""))
    if not operator or not operator.get("is_active", True):
        return
    send_kakao_event(
        "booking_received",
        str(operator.get("kakao_user_id") or ""),
        {
            "booking_id": booking.get("booking_id"),
            "visit_date": booking.get("visit_date") or "",
        },
    )


def _slot(booking: dict, date_key: str = "visit_date", time_key: str = "visit_time") -> str:
    day = str(booking.get(date_key) or "")[:10]
    clock = str(booking.get(time_key) or "").strip()[:5]
    return f"{day} {clock}".strip()


def booking_decision_message(booking: dict, decision: str) -> str:
    """승인·거절 말풍선. 거절은 원래 방문 일시와 사과를 넣는다."""
    booking_id = booking.get("booking_id")
    if decision == "approve":
        return f"예약 {booking_id}번이 승인되었습니다."
    when = _slot(booking)
    return f"예약 {booking_id}번 {when}은 진행이 어렵습니다. 불편을 드려 죄송합니다."


def booking_offer_message(booking: dict) -> str:
    when = _slot(booking, "proposed_visit_date", "proposed_visit_time")
    return (
        f"예약 {booking.get('booking_id')}번을 {when}으로 바꿀 수 있습니다. "
        "달력에서 변경을 승인하거나 거부해 주세요."
    )


def booking_answer_message(booking: dict, accepted: bool) -> str:
    booking_id = booking.get("booking_id")
    if accepted:
        when = _slot(booking)
        return f"예약 {booking_id}번 고객이 {when} 변경에 동의했습니다. 달력에서 승인해 주세요."
    return f"예약 {booking_id}번 고객이 일정 변경을 거부했습니다. 다른 시간을 제안하거나 거절할 수 있습니다."


def notify_booking_decided(booking: dict, decision: str) -> None:
    """승인·거절 선톡. 그 예약을 한 관광객에게만 보낸다."""
    label = "승인" if decision == "approve" else "거절"
    send_kakao_event(
        "booking_decided",
        str(booking.get("customer_kakao_id") or ""),
        {
            "booking_id": booking.get("booking_id"),
            "decision": label,
            "message": booking_decision_message(booking, decision),
        },
    )


def notify_booking_change_offered(booking: dict, link: str) -> None:
    """일정 변경 제안 선톡. 그 예약을 한 관광객에게만 보낸다."""
    send_kakao_event(
        "booking_change_offered",
        str(booking.get("customer_kakao_id") or ""),
        {
            "booking_id": booking.get("booking_id"),
            "message": booking_offer_message(booking),
            "link": link,
        },
    )


def notify_booking_change_answered(booking: dict, accepted: bool) -> None:
    """고객의 변경 답. 그 마을 운영자에게만 보낸다."""
    from services.supabase_client import get_village_operator

    operator = get_village_operator(str(booking.get("village_id") or ""))
    if not operator or not operator.get("is_active", True):
        return
    send_kakao_event(
        "booking_change_answered",
        str(operator.get("kakao_user_id") or ""),
        {
            "booking_id": booking.get("booking_id"),
            "message": booking_answer_message(booking, accepted),
        },
    )
