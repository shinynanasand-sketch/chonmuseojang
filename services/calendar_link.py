"""체험 달력 링크. 주소에는 카카오 사용자 ID를 넣지 않는다."""

import hashlib
import hmac
import os
import time
from datetime import date

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


def issue_change_token(booking_id: int, visit_date: str, visit_time: str) -> str:
    """제안 일시가 바뀌면 이전 토큰은 맞지 않는다. 카카오 사용자 ID는 넣지 않는다."""
    expires = int(time.time()) + _TTL_SECONDS
    clock = f"{visit_time[:2]}{visit_time[3:5]}"
    payload = f"{int(booking_id)}.{visit_date}.{clock}.{expires}"
    signature = hmac.new(_secret().encode(), payload.encode(), hashlib.sha256).hexdigest()[:20]
    return f"{payload}.{signature}"


def booking_from_change_token(token: str) -> dict | None:
    parts = (token or "").split(".")
    if len(parts) != 5:
        return None
    booking_id, visit_date, clock, expires, signature = parts
    if len(clock) != 4 or not clock.isdigit():
        return None
    payload = f"{booking_id}.{visit_date}.{clock}.{expires}"
    expected = hmac.new(_secret().encode(), payload.encode(), hashlib.sha256).hexdigest()[:20]
    if len(expected) != len(signature) or not hmac.compare_digest(expected, signature):
        return None
    try:
        if int(expires) < int(time.time()):
            return None
        parsed_id = int(booking_id)
        date.fromisoformat(visit_date)
    except (TypeError, ValueError):
        return None
    return {
        "booking_id": parsed_id,
        "proposed_visit_date": visit_date,
        "proposed_visit_time": f"{clock[:2]}:{clock[2:]}",
    }


def change_page_url(booking_id: int, visit_date: str, visit_time: str) -> str:
    base = os.getenv("PUBLIC_BASE_URL", "https://chonmuseojang.vercel.app").rstrip("/")
    return f"{base}/change/{issue_change_token(booking_id, visit_date, visit_time)}"


def calendar_page_url(operator: dict) -> str:
    base = os.getenv("PUBLIC_BASE_URL", "https://chonmuseojang.vercel.app").rstrip("/")
    return f"{base}/calendar/{issue_calendar_token(operator)}"


def attach_calendar_card(
    body: dict,
    operator: dict,
    *,
    title: str = "체험 달력",
    description: str = "날짜를 눌러 일정을 확인합니다.",
    label: str = "달력 열기",
) -> dict:
    """답장 아래에 운영자 달력 버튼을 붙인다. 주소에는 카카오 사용자 ID가 없다."""
    from config import KAKAO_CARD_IMAGE_URL

    outputs = body.setdefault("template", {}).setdefault("outputs", [])
    outputs.append(
        {
            "basicCard": {
                "title": title,
                "description": description,
                "thumbnail": {"imageUrl": KAKAO_CARD_IMAGE_URL},
                "buttons": [
                    {
                        "action": "webLink",
                        "label": label,
                        "webLinkUrl": calendar_page_url(operator),
                    }
                ],
            }
        }
    )
    return body


def attach_approval_calendar(body: dict, operator: dict) -> dict:
    """예약 현황 아래에 날짜에서 승인하는 달력을 연다."""
    return attach_calendar_card(
        body,
        operator,
        title="예약 달력",
        description="대기인 날짜를 눌러 승인하거나 거절합니다.",
        label="달력에서 승인",
    )
