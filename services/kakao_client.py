"""카카오 스킬 응답 포맷. 이벤트 API 함수는 다음 단계용이며 이번 단계 경로에서 호출하지 않는다."""

import json
import logging
import os

import httpx
from starlette.responses import Response

logger = logging.getLogger(__name__)

_SKILL_TEXT_LIMIT = 1000


def build_skill_response(title: str, description: str) -> dict:
    """카카오 스킬 응답 (simpleText). 제목을 붙인 뒤 1000자·한 줄로 자른다."""
    text = f"{title}. {description}".strip() if description else title
    text = " ".join(text.split())
    if len(text) > _SKILL_TEXT_LIMIT:
        text = text[: _SKILL_TEXT_LIMIT - 1] + "…"
    return {
        "version": "2.0",
        "template": {
            "outputs": [
                {
                    "simpleText": {
                        "text": text,
                    }
                }
            ]
        },
    }


def build_error_skill_response(message: str) -> dict:
    return build_skill_response("안내", message)


def build_list_card(header: str, items: list[dict]) -> dict:
    """성공 목록. 5건을 넘으면 앞 5건만 넣고 헤더에 최근 5건이라고 적는다."""
    shown = items[:5]
    title = "최근 5건" if len(items) > 5 else header
    return {
        "version": "2.0",
        "template": {
            "outputs": [
                {
                    "listCard": {
                        "header": {"title": title},
                        "items": [
                            {
                                "title": str(item.get("title") or ""),
                                "description": str(item.get("description") or ""),
                            }
                            for item in shown
                        ],
                    }
                }
            ]
        },
    }


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
