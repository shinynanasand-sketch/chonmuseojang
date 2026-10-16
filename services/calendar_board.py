"""토큰으로 여는 체험 달력. 마을 번호는 토큰의 운영자에게서만 읽는다."""

from services.calendar_link import operator_from_calendar_token
from services.program_share import delete_calendar_entry, list_calendar, save_calendar_entry
from services.supabase_client import get_village_by_id
from services.village_programs import program_key, program_labels


def _public_entry(row: dict) -> dict:
    return {
        "label": row.get("label") or "",
        "visit_date": row.get("visit_date") or "",
        "group_name": row.get("group_name") or "",
        "num_people": row.get("num_people") or 0,
    }


def calendar_snapshot(token: str) -> dict | None:
    operator = operator_from_calendar_token(token)
    if not operator:
        return None
    village = get_village_by_id(str(operator["village_id"])) or {}
    labels = program_labels(village)
    role = str(operator.get("role") or "village")
    if role == "program":
        key = str(operator.get("program_key") or "")
        labels = [label for label in labels if program_key(label) == key]
    listed = list_calendar(operator)
    return {
        "village_id": operator["village_id"],
        "village_name": village.get("village_name") or operator["village_id"],
        "can_write": role == "village",
        "programs": labels,
        "entries": [_public_entry(row) for row in listed.get("entries") or []],
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


def delete_calendar_from_token(token: str, label: str, visit_date: str, group_name: str) -> dict:
    operator = operator_from_calendar_token(token)
    if not operator:
        return {"ok": False, "reason": "not_found"}
    return delete_calendar_entry(operator, label, visit_date, group_name)
