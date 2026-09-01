"""카카오 이벤트 API 및 스킬 응답 포맷."""

import logging
import os

import httpx

logger = logging.getLogger(__name__)


def build_skill_response(title: str, description: str) -> dict:
    return {
        "version": "2.0",
        "template": {
            "outputs": [
                {
                    "basicCard": {
                        "title": title,
                        "description": description,
                    }
                }
            ]
        },
    }


def build_error_skill_response(message: str) -> dict:
    return build_skill_response("안내", message)


def _send_kakao_event_message(receiver_id: str, text: str) -> bool:
    """카카오 이벤트 API로 사용자에게 메시지를 발송한다 (FR-10)."""
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
    """대표자에게 이벤트 API 알림. operators.kakao_user_id를 수신자로 사용."""
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
    """여행객에게 결과 알림."""
    if customer_kakao_id:
        _send_kakao_event_message(customer_kakao_id, message)
    else:
        logger.info("고객 알림(로컬): %s", message)
