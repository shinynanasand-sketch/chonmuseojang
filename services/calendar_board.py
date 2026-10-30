"""토큰으로 여는 체험 달력. 마을 번호는 토큰의 운영자에게서만 읽는다."""

from datetime import date

from services.booking import (
    apply_booking_proposal,
    clear_booking_proposal,
    get_booking_by_id,
    list_bookings_for_village,
    save_booking_proposal,
    update_booking_status,
)
from services.kakao_client import (
    notify_booking_change_answered,
    notify_booking_change_offered,
    notify_booking_decided,
)
from services.calendar_link import (
    booking_from_change_token,
    change_page_url,
    operator_from_calendar_token,
)
from services.kakao_params import normalize_clock
from services.program_share import delete_calendar_entry, list_calendar, save_calendar_entry
from services.supabase_client import get_village_by_id
from services.guest_book import operating_names
from services.village_programs import program_key, program_labels

_STATUS_LABEL = {"pending": "대기", "confirmed": "승인", "rejected": "거절"}


def _public_entry(row: dict) -> dict:
    return {
        "label": row.get("label") or "",
        "visit_date": row.get("visit_date") or "",
        "group_name": row.get("group_name") or "",
        "num_people": row.get("num_people") or 0,
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


def _booking_view(row: dict) -> dict:
    status = str(row.get("status") or "pending")
    return {
        "booking_id": row.get("booking_id"),
        "label": row.get("program_label") or "체험 미정",
        "visit_date": str(row.get("visit_date") or "")[:10],
        "visit_time": str(row.get("visit_time") or "")[:5],
        "proposed_visit_date": str(row.get("proposed_visit_date") or "")[:10],
        "proposed_visit_time": str(row.get("proposed_visit_time") or "")[:5],
        "num_people": row.get("num_people") or 0,
        "status": status,
        "status_label": _STATUS_LABEL.get(status, status),
    }


def _proposal_matches(row: dict | None, claims: dict) -> bool:
    if not row or str(row.get("status") or "") != "pending":
        return False
    stored_date = str(row.get("proposed_visit_date") or "")[:10]
    stored_time = str(row.get("proposed_visit_time") or "")[:5]
    return (
        stored_date == claims["proposed_visit_date"]
        and stored_time == claims["proposed_visit_time"]
    )


def _bookings_for(operator: dict) -> list[dict]:
    rows = list_bookings_for_village(str(operator["village_id"]))
    if str(operator.get("role") or "village") == "program":
        key = str(operator.get("program_key") or "")
        rows = [row for row in rows if row.get("program_key") and row.get("program_key") == key]
    return [_booking_view(row) for row in rows]


def _first_program_key(village: dict) -> str:
    names = operating_names(village)
    if names:
        return program_key(names[0])
    labels = program_labels(village)
    if labels:
        return program_key(labels[0])
    return ""


def calendar_snapshot(token: str, view: str = "") -> dict | None:
    operator = operator_from_calendar_token(token)
    if not operator:
        return None
    village = get_village_by_id(str(operator["village_id"])) or {}
    labels = program_labels(village)
    names = operating_names(village)
    role = str(operator.get("role") or "village")
    program_view = view == "program" and role == "village"
    focus = str(operator.get("program_key") or "") if role == "program" else ""
    if program_view:
        focus = _first_program_key(village)
    if role == "program" or program_view:
        labels = [label for label in labels if program_key(label) == focus]
        names = [label for label in names if program_key(label) == focus]
    listed = list_calendar(operator)
    entries = [_public_entry(row) for row in listed.get("entries") or []]
    bookings = _bookings_for(operator)
    if program_view:
        entries = [row for row in entries if program_key(str(row.get("label") or "")) == focus]
        bookings = [row for row in bookings if program_key(str(row.get("label") or "")) == focus]
    return {
        "mode": "operator",
        "village_id": operator["village_id"],
        "village_name": village.get("village_name") or operator["village_id"],
        "can_write": role == "village" and not program_view,
        "programs": labels,
        "experience_names": names,
        "entries": entries,
        "bookings": bookings,
    }


def save_calendar_from_token(
    token: str, label: str, visit_date: str, group_name: str, num_people
) -> dict:
    operator = operator_from_calendar_token(token)
    if not operator:
        return {"ok": False, "reason": "not_found"}
    result = save_calendar_entry(operator, label, visit_date, group_name, num_people)
    if result.get("ok"):
        result["village_id"] = operator["village_id"]
    return result


def set_booking_status_from_token(token: str, booking_id, status: str) -> dict:
    operator = operator_from_calendar_token(token)
    if not operator:
        return {"ok": False, "reason": "not_found"}
    if str(operator.get("role") or "") != "village":
        return {"ok": False, "reason": "forbidden"}
    if status not in ("confirmed", "rejected"):
        return {"ok": False, "reason": "bad_format"}
    existing = get_booking_by_id(booking_id)
    if not existing or str(existing.get("village_id")) != str(operator["village_id"]):
        return {"ok": False, "reason": "forbidden"}
    saved = update_booking_status(existing["booking_id"], status)
    if not saved:
        return {"ok": False, "reason": "forbidden"}
    notify_booking_decided(existing, "approve" if status == "confirmed" else "reject")
    view = _booking_view(saved)
    view["ok"] = True
    return view


def propose_booking_from_token(token: str, booking_id, visit_date: str, visit_time: str) -> dict:
    """대기 예약에 다른 일시를 제안하고 고객에게 달력 링크를 보낸다."""
    operator = operator_from_calendar_token(token)
    if not operator:
        return {"ok": False, "reason": "not_found"}
    if str(operator.get("role") or "") != "village":
        return {"ok": False, "reason": "forbidden"}
    existing = get_booking_by_id(booking_id)
    if not existing or str(existing.get("village_id")) != str(operator["village_id"]):
        return {"ok": False, "reason": "forbidden"}
    if str(existing.get("status") or "") != "pending":
        return {"ok": False, "reason": "not_pending"}
    try:
        parsed = date.fromisoformat(str(visit_date or "").strip())
    except (TypeError, ValueError):
        return {"ok": False, "reason": "bad_slot"}
    clock = _clock(str(visit_time or ""))
    if not clock:
        return {"ok": False, "reason": "bad_slot"}
    saved = save_booking_proposal(existing["booking_id"], parsed.isoformat(), clock)
    if not saved:
        return {"ok": False, "reason": "forbidden"}
    link = change_page_url(int(saved["booking_id"]), parsed.isoformat(), clock)
    notify_booking_change_offered(saved, link)
    view = _booking_view(saved)
    view["ok"] = True
    view["link"] = link
    return view


def change_snapshot(token: str) -> dict | None:
    """고객이 제안 일시를 보고 승인하거나 거부한다. 다른 예약은 넣지 않는다."""
    claims = booking_from_change_token(token)
    if claims is None:
        return None
    row = get_booking_by_id(claims["booking_id"])
    open_offer = _proposal_matches(row, claims)
    village_name = ""
    if row:
        village = get_village_by_id(str(row.get("village_id") or "")) or {}
        village_name = village.get("village_name") or row.get("village_id") or ""
    bookings = []
    if open_offer and row:
        view = _booking_view(row)
        view["original_visit_date"] = view["visit_date"]
        view["original_visit_time"] = view["visit_time"]
        view["visit_date"] = claims["proposed_visit_date"]
        view["visit_time"] = claims["proposed_visit_time"]
        bookings.append(view)
    return {
        "mode": "change",
        "open": open_offer,
        "village_name": village_name,
        "can_write": False,
        "programs": [],
        "experience_names": [],
        "entries": [],
        "bookings": bookings,
        "focus_date": claims["proposed_visit_date"] if open_offer else "",
    }


def answer_booking_change(token: str, decision: str) -> dict:
    """고객의 변경 승인·거부. 승인해도 예약 상태는 대기다."""
    claims = booking_from_change_token(token)
    if claims is None:
        return {"ok": False, "reason": "not_found"}
    row = get_booking_by_id(claims["booking_id"])
    if not _proposal_matches(row, claims):
        return {"ok": False, "reason": "closed"}
    if decision == "accept":
        saved = apply_booking_proposal(row["booking_id"])
        if not saved:
            return {"ok": False, "reason": "closed"}
        notify_booking_change_answered(saved, True)
    elif decision == "decline":
        saved = clear_booking_proposal(row["booking_id"])
        if not saved:
            return {"ok": False, "reason": "closed"}
        notify_booking_change_answered(saved, False)
    else:
        return {"ok": False, "reason": "bad_decision"}
    view = _booking_view(saved)
    view["ok"] = True
    return view


def delete_calendar_from_token(token: str, label: str, visit_date: str, group_name: str) -> dict:
    operator = operator_from_calendar_token(token)
    if not operator:
        return {"ok": False, "reason": "not_found"}
    return delete_calendar_entry(operator, label, visit_date, group_name)
