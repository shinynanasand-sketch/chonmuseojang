"""체험객 달력 링크. 운영자 달력 토큰과 주소를 섞지 않는다."""

import os
import secrets
from datetime import date, datetime, timedelta, timezone

from services.booking import create_booking
from services.kakao_params import normalize_clock
from services.supabase_client import (
    get_guest_book_link,
    get_village_by_id,
    insert_guest_book_link,
    list_guest_book_links,
)
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


def _status_url(token: str) -> str:
    base = os.getenv("PUBLIC_BASE_URL", "https://chonmuseojang.vercel.app").rstrip("/")
    return f"{base}/book/{token}"


def issue_guest_book_link(kakao_user_id: str, village_id: str) -> str:
    """그 손님과 마을의 유효한 주소가 있으면 다시 쓰고, 없으면 14일짜리 토큰을 만든다."""
    for row in list_guest_book_links(kakao_user_id, village_id):
        if row.get("token") and not _expired(row.get("expires_at")):
            return _status_url(str(row["token"]))
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
    return _status_url(token)


def guest_from_token(token: str) -> dict | None:
    row = get_guest_book_link(token)
    if not row or _expired(row.get("expires_at")):
        return None
    if not row.get("village_id") or not row.get("customer_kakao_id"):
        return None
    return row


def operating_names(village: dict) -> list[str]:
    return [item["label"] for item in programs_for(village) if item.get("is_operating")]


def bookable_names(village: dict) -> list[str]:
    """체험객이 고를 수 있는 체험. 가격표가 있는 마을은 1인 금액이 있는 운영 중 체험만."""
    names = operating_names(village)
    from services.field_changes import has_price_table, price_of

    village_id = str(village.get("village_id") or "")
    if not has_price_table(village_id):
        return names
    return [name for name in names if price_of(village_id, name) is not None]


def _own_bookings(customer_kakao_id: str) -> list[dict]:
    """그 손님의 예약만. 마을 이름과 상태를 넣고 카카오 사용자 ID는 빼 둔다."""
    from services.booking import list_bookings
    from services.calendar_board import _booking_view

    rows = list_bookings(customer_kakao_id=customer_kakao_id)
    views = []
    for row in rows:
        view = _booking_view(row)
        village = get_village_by_id(str(row.get("village_id") or "")) or {}
        view["village_name"] = village.get("village_name") or row.get("village_id")
        views.append(view)
    return views


def guest_snapshot(token: str) -> dict | None:
    """체험 목록과 그 링크 사용자의 예약. 다른 사람의 예약과 카카오 사용자 ID는 넣지 않는다."""
    link = guest_from_token(token)
    if not link:
        return None
    village = get_village_by_id(str(link["village_id"]))
    if not village:
        return None
    names = bookable_names(village)
    from services.field_changes import has_price_table, price_of

    village_id = str(village.get("village_id") or "")
    snapshot = {
        "mode": "guest",
        "village_id": village.get("village_id"),
        "village_name": village.get("village_name") or village.get("village_id"),
        "can_write": False,
        "can_book": True,
        "programs": names,
        "experience_names": names,
        "entries": [],
        "bookings": _own_bookings(str(link["customer_kakao_id"])),
    }
    if has_price_table(village_id):
        snapshot["prices"] = {name: price_of(village_id, name) for name in names}
    return snapshot


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


def save_guest_booking(
    token: str, label: str, visit_date: str, visit_time: str, num_people, group_name: str = ""
) -> dict:
    """대기 예약만 만든다. 단체 이름은 예약에 두고, 운영자 단체 일정 표는 바꾸지 않는다."""
    link = guest_from_token(token)
    if not link:
        return {"ok": False, "reason": "not_found"}
    village = get_village_by_id(str(link["village_id"]))
    if not village:
        return {"ok": False, "reason": "not_found"}
    from services.demo_data import DEMO_VILLAGE_ID
    from services.demo_role import persona_of

    if str(village.get("village_id") or "") == DEMO_VILLAGE_ID and not persona_of(
        str(link.get("customer_kakao_id") or "")
    ):
        return {"ok": False, "reason": "demo_closed"}
    try:
        parsed = date.fromisoformat(visit_date)
        count = int(num_people)
    except (TypeError, ValueError):
        return {"ok": False, "reason": "bad_format"}
    clock = _clock(visit_time)
    group = " ".join(str(group_name or "").split())
    if count < 1 or not clock:
        return {"ok": False, "reason": "bad_format"}
    if not group:
        return {"ok": False, "reason": "group_missing"}
    wanted = program_key(label)
    canonical = next(
        (name for name in bookable_names(village) if program_key(name) == wanted),
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
        group_name=group,
    )
    if not saved.get("booking_id"):
        return {"ok": False, "reason": "not_saved"}
    from services.demo_role import mark_guest_demo

    mark_guest_demo(str(link["customer_kakao_id"]), saved.get("booking_id"))
    if not saved.get("already_open"):
        from services.kakao_client import notify_booking_received

        notify_booking_received(saved)
    from services.booking import _STATUS_LABEL
    from services.field_changes import line_total

    payload = {
        "ok": True,
        "booking_id": saved.get("booking_id"),
        "label": canonical,
        "visit_date": str(saved.get("visit_date") or parsed.isoformat())[:10],
        "visit_time": str(saved.get("visit_time") or clock)[:5],
        "num_people": saved.get("num_people"),
        "group_name": saved.get("group_name") or group,
        "group_updated": bool(saved.get("group_updated")),
        "status": saved.get("status"),
        "status_label": _STATUS_LABEL.get(saved.get("status"), "대기"),
        "already_open": bool(saved.get("already_open")),
        "headcount_updated": bool(saved.get("headcount_updated")),
    }
    amount = line_total(village.get("village_id"), canonical, saved.get("num_people"))
    if amount is not None:
        payload["total"] = amount
    return payload
