"""체험객 달력 링크. 운영자 달력 토큰과 주소를 섞지 않는다."""

import os
import secrets
from datetime import date, datetime, timedelta, timezone

from services.booking import create_booking
from services.kakao_params import normalize_clock
from services.supabase_client import get_guest_book_link, get_village_by_id, insert_guest_book_link
from services.village_programs import program_key, programs_for

_TTL = timedelta(days=14)


def _expired(value) -> bool:
    text = str(value or "").strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        return True
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment <= datetime.now(timezone.utc)


def issue_guest_book_link(kakao_user_id: str, village_id: str) -> str:
    """무작위 토큰으로 14일짜리 예약 주소를 만든다."""
    token = secrets.token_urlsafe(24)
    expires = datetime.now(timezone.utc) + _TTL
    insert_guest_book_link(
        {
            "token": token,
            "village_id": village_id,
            "customer_kakao_id": kakao_user_id,
            "expires_at": expires.isoformat(),
        }
    )
    base = os.getenv("PUBLIC_BASE_URL", "https://chonmuseojang.vercel.app").rstrip("/")
    return f"{base}/book/{token}"


def guest_from_token(token: str) -> dict | None:
    row = get_guest_book_link(token)
    if not row or _expired(row.get("expires_at")):
        return None
    if not row.get("village_id") or not row.get("customer_kakao_id"):
        return None
    return row


def operating_names(village: dict) -> list[str]:
    return [item["label"] for item in programs_for(village) if item.get("is_operating")]


def guest_snapshot(token: str) -> dict | None:
    """체험 목록만. 다른 사람의 예약과 카카오 사용자 ID는 넣지 않는다."""
    link = guest_from_token(token)
    if not link:
        return None
    village = get_village_by_id(str(link["village_id"]))
    if not village:
        return None
    names = operating_names(village)
    return {
        "mode": "guest",
        "village_id": village.get("village_id"),
        "village_name": village.get("village_name") or village.get("village_id"),
        "can_write": False,
        "can_book": True,
        "programs": names,
        "experience_names": names,
        "entries": [],
        "bookings": [],
    }


def _clock(value: str) -> str:
    text = (value or "").strip()
    parts = text.split(":")
    if len(parts) < 2:
        return ""
    try:
        hour = int(parts[0])
        minute = int(parts[1])
    except ValueError:
        return ""
    return normalize_clock(hour, minute)


def save_guest_booking(token: str, label: str, visit_date: str, visit_time: str, num_people) -> dict:
    """대기 예약만 만든다. 승인이나 단체 일정은 바꾸지 않는다."""
    link = guest_from_token(token)
    if not link:
        return {"ok": False, "reason": "not_found"}
    village = get_village_by_id(str(link["village_id"]))
    if not village:
        return {"ok": False, "reason": "not_found"}
    try:
        parsed = date.fromisoformat(visit_date)
        count = int(num_people)
    except (TypeError, ValueError):
        return {"ok": False, "reason": "bad_format"}
    clock = _clock(visit_time)
    if count < 1 or not clock:
        return {"ok": False, "reason": "bad_format"}
    wanted = program_key(label)
    canonical = next(
        (name for name in operating_names(village) if program_key(name) == wanted),
        "",
    )
    if not canonical:
        return {"ok": False, "reason": "program_not_found"}
    saved = create_booking(
        village_id=str(village["village_id"]),
        customer_kakao_id=str(link["customer_kakao_id"]),
        visit_date=parsed.isoformat(),
        num_people=count,
        program_label=canonical,
        visit_time=clock,
    )
    from services.kakao_client import notify_booking_received

    notify_booking_received(saved)
    return {
        "ok": True,
        "booking_id": saved.get("booking_id"),
        "label": canonical,
        "visit_date": parsed.isoformat(),
        "visit_time": clock,
        "num_people": count,
    }
