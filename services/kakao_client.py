"""카카오 스킬 응답 포맷. 이벤트 API 함수는 다음 단계용이며 이번 단계 경로에서 호출하지 않는다."""

import contextvars
import json
import logging
import os
import re
from urllib.parse import urlparse

import httpx
from starlette.responses import Response

logger = logging.getLogger(__name__)

_SKILL_TEXT_LIMIT = 1000
_reply_user_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "kakao_reply_user_id", default=""
)
_VILLAGE_REPLIES = ("예약 현황 조회", "체험 달력 조회", "체험 글 조회", "홍보 사진")
_PROGRAM_REPLIES = ("체험 달력 조회", "체험 글 조회", "체험 글 저장")


def bind_reply_user(user_id: str):
    """이 요청의 스킬 응답에 넣을 바로연결 대상을 정한다."""
    return _reply_user_id.set(user_id or "")


def reset_reply_user(token) -> None:
    _reply_user_id.reset(token)


def _quick_replies(user_id: str) -> list[dict]:
    """등록된 발화를 버튼으로 보낸다. 관광객에게는 운영자 버튼을 넣지 않는다."""
    if not user_id:
        return []
    from services.supabase_client import get_operator_by_kakao_id

    operator = get_operator_by_kakao_id(user_id)
    if not operator:
        return []
    role = str(operator.get("role") or "village")
    if role == "village":
        labels = _VILLAGE_REPLIES
    elif role == "program":
        labels = _PROGRAM_REPLIES
    else:
        return []
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


def _send_kakao_event_message(receiver_id: str, text: str) -> bool:
    """다음 단계의 이벤트 API 발송. 이번 단계 라우터에서는 호출하지 않는다."""
    admin_key = os.getenv("KAKAO_ADMIN_KEY", "")
    event_url = os.getenv(
        "KAKAO_EVENT_API_URL",
        "https://kapi.kakao.com/v1/api/talk/friends/message/default/send",
    )
    if not admin_key:
        logger.info("KAKAO_ADMIN_KEY 미설정 — 이벤트 메시지 스킵: %s", text[:50])
        return False

    headers = {
        "Authorization": f"KakaoAK {admin_key}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    payload = {
        "receiver_uuids": f'["{receiver_id}"]',
        "template_object": (
            '{"object_type":"text","text":"'
            + text.replace('"', '\\"')
            + '","link":{"web_url":"https://developers.kakao.com"}}'
        ),
    }
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.post(event_url, headers=headers, data=payload)
            response.raise_for_status()
        return True
    except Exception as exc:
        logger.warning("카카오 이벤트 API 발송 실패: %s", exc)
        return False


def send_kakao_notification_to_owner(village_id: str, message: str) -> None:
    """다음 단계용 운영자 선톡. 이번 단계에서는 호출하지 않는다."""
    from services.supabase_client import get_supabase_client

    client = get_supabase_client()
    if client:
        result = (
            client.table("operators")
            .select("kakao_user_id")
            .eq("village_id", village_id)
            .eq("is_active", True)
            .limit(1)
            .execute()
        )
        if result.data and result.data[0].get("kakao_user_id"):
            _send_kakao_event_message(result.data[0]["kakao_user_id"], message)
            return
    logger.info("운영자 알림(로컬): village=%s msg=%s", village_id, message)


def send_kakao_notification_to_customer(customer_kakao_id: str, message: str) -> None:
    """다음 단계용 관광객 선톡. 이번 단계에서는 호출하지 않는다."""
    if customer_kakao_id:
        _send_kakao_event_message(customer_kakao_id, message)
    else:
        logger.info("고객 알림(로컬): %s", message)
