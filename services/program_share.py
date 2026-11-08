"""같은 마을 운영자가 나누는 체험 글과 체험 달력."""

from datetime import date, datetime, timezone

from services.supabase_client import (
    delete_calendar_entry_row,
    get_village_by_id,
    list_calendar_for_village,
    list_program_notes_for_village,
    upsert_calendar_entry,
    upsert_program_note,
)
from services.program_groups import assigned_program_keys
from services.village_programs import program_key, program_labels


def _role(operator: dict) -> str:
    return str(operator.get("role") or "village")


def _canonical_label(village_id: str, label: str) -> str:
    village = get_village_by_id(village_id) or {}
    normalized = " ".join(label.split())
    for item in program_labels(village):
        if " ".join(item.split()) == normalized:
            return item
    return ""


def _owned_labels(operator: dict) -> list[str]:
    village = get_village_by_id(str(operator.get("village_id") or "")) or {}
    keys = assigned_program_keys(operator)
    return [item for item in program_labels(village) if program_key(item) in keys]


def _split_owned_label(labels: list[str], body: str) -> tuple[str, str] | None:
    """여러 체험을 맡으면 본문 앞의 체험 이름으로 고른다."""
    for label in sorted(labels, key=len, reverse=True):
        if body == label or body.startswith(label + " "):
            return label, body[len(label) :].strip()
    return None


def save_program_note(operator: dict, body: str, label: str = "") -> dict:
    """체험 담당만 맡은 체험 글을 저장한다."""
    if not operator or not operator.get("village_id"):
        return {"ok": False, "reason": "forbidden"}
    if _role(operator) != "program":
        return {"ok": False, "reason": "read_only"}
    owned = _owned_labels(operator)
    if not owned:
        return {"ok": False, "reason": "program_not_found"}
    text = body.strip()
    if label:
        wanted = program_key(" ".join(label.split()))
        canonical = next((item for item in owned if program_key(item) == wanted), "")
        if not canonical:
            return {"ok": False, "reason": "forbidden"}
    elif len(owned) == 1:
        canonical = owned[0]
    else:
        chosen = _split_owned_label(owned, text)
        if not chosen:
            return {"ok": False, "reason": "which_program"}
        canonical, text = chosen
    if not text:
        return {"ok": False, "reason": "bad_format"}
    try:
        upsert_program_note(
            {
                "village_id": operator["village_id"],
                "program_key": program_key(canonical),
                "label": canonical,
                "body": text,
                "updated_by": operator.get("operator_id"),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        )
    except RuntimeError:
        return {"ok": False, "reason": "storage_unavailable"}
    return {"ok": True, "label": canonical, "body": text}


def list_program_notes(operator: dict) -> dict:
    """같은 마을 운영자와 체험 담당만 글을 읽는다."""
    if not operator or not operator.get("village_id"):
        return {"ok": False, "reason": "forbidden", "notes": []}
    notes = list_program_notes_for_village(str(operator["village_id"]))
    return {"ok": True, "notes": notes}


def save_calendar_entry(
    operator: dict,
    label: str,
    visit_date: str,
    group_name: str,
    num_people: int,
    note: str = "",
) -> dict:
    """마을 운영자만 체험 일정에 단체와 인원을 등록한다."""
    if not operator or not operator.get("village_id"):
        return {"ok": False, "reason": "forbidden"}
    if _role(operator) != "village":
        return {"ok": False, "reason": "forbidden"}
    canonical = _canonical_label(str(operator["village_id"]), label)
    if not canonical:
        return {"ok": False, "reason": "program_not_found"}
    group = " ".join(str(group_name or "").split())
    try:
        parsed = date.fromisoformat(visit_date)
        count = int(num_people)
    except (TypeError, ValueError):
        return {"ok": False, "reason": "bad_format"}
    if not group or count < 1:
        return {"ok": False, "reason": "bad_format"}
    try:
        upsert_calendar_entry(
            {
                "village_id": operator["village_id"],
                "program_key": program_key(canonical),
                "label": canonical,
                "visit_date": parsed.isoformat(),
                "group_name": group,
                "num_people": count,
                "note": note.strip(),
                "created_by": operator.get("operator_id"),
            }
        )
    except RuntimeError:
        return {"ok": False, "reason": "storage_unavailable"}
    return {
        "ok": True,
        "label": canonical,
        "visit_date": parsed.isoformat(),
        "group_name": group,
        "num_people": count,
    }


def delete_calendar_entry(operator: dict, label: str, visit_date: str, group_name: str) -> dict:
    """마을 운영자만 자기 마을의 체험·날짜·단체 한 건을 지운다."""
    if not operator or not operator.get("village_id"):
        return {"ok": False, "reason": "forbidden"}
    if _role(operator) != "village":
        return {"ok": False, "reason": "forbidden"}
    canonical = _canonical_label(str(operator["village_id"]), label)
    group = " ".join(str(group_name or "").split())
    try:
        parsed = date.fromisoformat(visit_date)
    except (TypeError, ValueError):
        return {"ok": False, "reason": "bad_format"}
    if not canonical or not group:
        return {"ok": False, "reason": "bad_format"}
    try:
        delete_calendar_entry_row(
            str(operator["village_id"]),
            program_key(canonical),
            parsed.isoformat(),
            group,
        )
    except RuntimeError:
        return {"ok": False, "reason": "storage_unavailable"}
    return {"ok": True, "village_id": operator["village_id"]}


def list_calendar(operator: dict) -> dict:
    """마을 운영자는 마을 전체를, 체험 담당은 자기 체험만 읽는다."""
    if not operator or not operator.get("village_id"):
        return {"ok": False, "reason": "forbidden", "entries": []}
    entries = list_calendar_for_village(str(operator["village_id"]))
    if _role(operator) == "program":
        keys = assigned_program_keys(operator)
        entries = [row for row in entries if row.get("program_key") in keys]
    return {"ok": True, "entries": entries}
