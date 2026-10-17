"""체험 달력 링크. 주소에는 카카오 사용자 ID를 넣지 않는다."""

import hashlib
import hmac
import os
import time

from services.supabase_client import get_operator_by_id

_TTL_SECONDS = 14 * 24 * 60 * 60


def _secret() -> str:
    return os.getenv("CRON_SECRET", "")


def issue_calendar_token(operator: dict) -> str:
    operator_id = int(operator["operator_id"])
    expires = int(time.time()) + _TTL_SECONDS
    payload = f"{operator_id}.{expires}"
    signature = hmac.new(_secret().encode(), payload.encode(), hashlib.sha256).hexdigest()[:20]
    return f"{payload}.{signature}"


def operator_from_calendar_token(token: str) -> dict | None:
    parts = (token or "").split(".")
    if len(parts) != 3:
        return None
    operator_id, expires, signature = parts
    payload = f"{operator_id}.{expires}"
    expected = hmac.new(_secret().encode(), payload.encode(), hashlib.sha256).hexdigest()[:20]
    if not hmac.compare_digest(expected, signature):
        return None
    try:
        if int(expires) < int(time.time()):
            return None
        found = get_operator_by_id(int(operator_id))
    except (TypeError, ValueError):
        return None
    return found


def calendar_page_url(operator: dict) -> str:
    base = os.getenv("PUBLIC_BASE_URL", "https://chonmuseojang.vercel.app").rstrip("/")
    return f"{base}/calendar/{issue_calendar_token(operator)}"


def attach_calendar_card(body: dict, operator: dict) -> dict:
    """조회 답장 아래에 달력 열기 버튼을 붙인다."""
    from config import KAKAO_CARD_IMAGE_URL

    outputs = body.setdefault("template", {}).setdefault("outputs", [])
    outputs.append(
        {
            "basicCard": {
                "title": "체험 달력",
                "description": "날짜를 눌러 일정을 확인합니다.",
                "thumbnail": {"imageUrl": KAKAO_CARD_IMAGE_URL},
                "buttons": [
                    {
                        "action": "webLink",
                        "label": "달력 열기",
                        "webLinkUrl": calendar_page_url(operator),
                    }
                ],
            }
        }
    )
    return body
