"""예전 마을 줄을 지금 줄로 모은 뒤, 예전 줄만 지운다."""

from __future__ import annotations

import json
from pathlib import Path

import services.supabase_client as store
from services.supabase_client import get_supabase_client

OLD_VILLAGE_ID = "PDaf579aadaa4d"
NEW_VILLAGE_ID = "PDeac2fe424e02"
INTEGRATED_SIDO = "전남광주통합특별시"
OLD_ADMIN_NAMES = ("전라남도", "광주광역시", "광주특별시")
_HIDDEN = {
    "kakao_user_id",
    "customer_kakao_id",
    "login_id",
    "password_hash",
    "registration_code",
}
_CHILD_TABLES = (
    "village_program_status",
    "program_notes",
    "experience_calendar",
    "contents",
)


def _public_row(row: dict) -> dict:
    return {key: value for key, value in row.items() if key not in _HIDDEN}


def _rows(table: str, village_id: str) -> list[dict]:
    client = get_supabase_client()
    if client:
        result = client.table(table).select("*").eq("village_id", village_id).execute()
        return result.data or []
    source = {
        "operators": store._operators,
        "bookings": store._bookings,
        "reviews": store._reviews,
        "contents": store._contents,
        "village_program_status": store._program_status,
        "program_notes": store._program_notes,
        "experience_calendar": store._calendar,
        "villages_cache": store._villages_cache,
    }[table]
    return [dict(row) for row in source if row.get("village_id") == village_id]


def _update_village(table: str, old_id: str, new_id: str) -> int:
    client = get_supabase_client()
    if client:
        result = (
            client.table(table).update({"village_id": new_id}).eq("village_id", old_id).execute()
        )
        return len(result.data or [])
    count = 0
    for row in _memory_table(table):
        if row.get("village_id") == old_id:
            row["village_id"] = new_id
            count += 1
    return count


def _delete_village_rows(table: str, village_id: str) -> None:
    client = get_supabase_client()
    if client:
        client.table(table).delete().eq("village_id", village_id).execute()
        return
    source = _memory_table(table)
    source[:] = [row for row in source if row.get("village_id") != village_id]


def _memory_table(table: str) -> list[dict]:
    return {
        "operators": store._operators,
        "bookings": store._bookings,
        "reviews": store._reviews,
        "contents": store._contents,
        "village_program_status": store._program_status,
        "program_notes": store._program_notes,
        "experience_calendar": store._calendar,
        "villages_cache": store._villages_cache,
    }[table]


def _clear_operator_links(operator_id: int) -> None:
    client = get_supabase_client()
    if client:
        client.table("contents").update({"operator_id": None}).eq("operator_id", operator_id).execute()
        client.table("program_notes").update({"updated_by": None}).eq("updated_by", operator_id).execute()
        client.table("experience_calendar").update({"created_by": None}).eq(
            "created_by", operator_id
        ).execute()
        return
    for row in store._contents:
        if row.get("operator_id") == operator_id:
            row["operator_id"] = None
    for row in store._program_notes:
        if row.get("updated_by") == operator_id:
            row["updated_by"] = None
    for row in store._calendar:
        if row.get("created_by") == operator_id:
            row["created_by"] = None


def _delete_operator(operator_id: int) -> None:
    _clear_operator_links(operator_id)
    client = get_supabase_client()
    if client:
        client.table("operators").delete().eq("operator_id", operator_id).execute()
        return
    store._operators[:] = [
        row for row in store._operators if row.get("operator_id") != operator_id
    ]


def _place_text(row: dict) -> str:
    return f"{row.get('sido') or ''} {row.get('address') or ''}"


def _group_key(row: dict) -> tuple[str, str] | None:
    name = str(row.get("village_name") or "").strip()
    if not name:
        return None
    return (name, str(row.get("sigungu") or "").strip())


def _is_integrated(row: dict) -> bool:
    return INTEGRATED_SIDO in _place_text(row)


def _is_old_admin(row: dict) -> bool:
    text = _place_text(row)
    if INTEGRATED_SIDO in text:
        return False
    return any(name in text for name in OLD_ADMIN_NAMES)


def split_village_pairs(rows: list[dict]) -> list[tuple[dict, dict]]:
    """통합특별시 줄이 있는 묶음의 예전 행정명 줄만 (예전 줄, 통합 줄)로 돌려준다."""
    from services.demo_data import is_demo_village

    groups: dict[tuple[str, str], list[dict]] = {}
    for row in rows:
        if is_demo_village(row):
            continue
        key = _group_key(row)
        if key is None:
            continue
        groups.setdefault(key, []).append(row)
    pairs: list[tuple[dict, dict]] = []
    for group in groups.values():
        keepers = [row for row in group if _is_integrated(row)]
        if not keepers:
            continue
        keep = keepers[0]
        keep_id = str(keep.get("village_id") or "")
        for row in group:
            if str(row.get("village_id") or "") == keep_id:
                continue
            if _is_old_admin(row):
                pairs.append((row, keep))
    return pairs


def drop_old_address_rows(rows: list[dict]) -> list[dict]:
    """같은 수신 묶음에 통합특별시 줄이 있으면 예전 행정명 줄은 뺀다."""
    old_ids = {str(old.get("village_id") or "") for old, _keep in split_village_pairs(rows)}
    return [row for row in rows if str(row.get("village_id") or "") not in old_ids]


def read_operator_link(old_id: str = OLD_VILLAGE_ID, new_id: str = NEW_VILLAGE_ID) -> dict:
    """마을 번호, 역할, 활성 여부와 예약·후기 건수만 돌려준다."""
    operators = []
    for village_id in (old_id, new_id):
        for row in _rows("operators", village_id):
            operators.append(
                {
                    "operator_id": row.get("operator_id"),
                    "village_id": row.get("village_id"),
                    "role": row.get("role"),
                    "is_active": row.get("is_active"),
                    "program_key": row.get("program_key"),
                }
            )
    return {
        "operators": operators,
        "booking_counts": {old_id: len(_rows("bookings", old_id)), new_id: len(_rows("bookings", new_id))},
        "review_counts": {old_id: len(_rows("reviews", old_id)), new_id: len(_rows("reviews", new_id))},
    }


def backup_old_village(folder: Path, old_id: str = OLD_VILLAGE_ID) -> Path:
    payload = {
        "village": [_public_row(row) for row in _rows("villages_cache", old_id)],
        "program_status": _rows("village_program_status", old_id),
        "notes": [_public_row(row) for row in _rows("program_notes", old_id)],
        "calendar": [_public_row(row) for row in _rows("experience_calendar", old_id)],
        "contents": [_public_row(row) for row in _rows("contents", old_id)],
    }
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{old_id}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _village_operators(village_id: str) -> list[dict]:
    return [
        row
        for row in _rows("operators", village_id)
        if row.get("role") == "village" and row.get("is_active", True)
    ]


def _set_operator_village(operator_id: int, village_id: str) -> None:
    client = get_supabase_client()
    if client:
        client.table("operators").update({"village_id": village_id}).eq(
            "operator_id", operator_id
        ).execute()
        return
    for row in store._operators:
        if row.get("operator_id") == operator_id:
            row["village_id"] = village_id


def move_links_to_new(old_id: str = OLD_VILLAGE_ID, new_id: str = NEW_VILLAGE_ID) -> dict:
    """옛 번호의 사무장, 예약, 후기를 지금 번호로 옮긴다."""
    old_rows = _rows("operators", old_id)
    old_active = [
        row for row in old_rows if row.get("role") == "village" and row.get("is_active", True)
    ]
    new_active = _village_operators(new_id)
    keep_id = int(old_active[0]["operator_id"]) if old_active and not new_active else None
    retired_operator = bool(old_active and new_active)
    for row in old_rows:
        operator_id = int(row["operator_id"])
        if keep_id is not None and operator_id == keep_id:
            _set_operator_village(operator_id, new_id)
            continue
        _delete_operator(operator_id)
    bookings = _update_village("bookings", old_id, new_id)
    reviews = _update_village("reviews", old_id, new_id)
    return {
        "moved_operator": keep_id is not None,
        "retired_duplicate_operator": retired_operator,
        "bookings": bookings,
        "reviews": reviews,
    }


def delete_old_village(old_id: str = OLD_VILLAGE_ID) -> None:
    for row in list(_rows("operators", old_id)):
        _delete_operator(int(row["operator_id"]))
    for table in _CHILD_TABLES:
        _delete_village_rows(table, old_id)
    _delete_village_rows("villages_cache", old_id)


def _copy_registration_code_if_empty(old_id: str, new_id: str) -> None:
    old_rows = _rows("villages_cache", old_id)
    new_rows = _rows("villages_cache", new_id)
    old_code = str((old_rows[0].get("registration_code") if old_rows else "") or "").strip()
    new_code = str((new_rows[0].get("registration_code") if new_rows else "") or "").strip()
    if not old_code or new_code:
        return
    from services.supabase_client import set_registration_code

    set_registration_code(new_id, old_code)


def retire_old_village(
    folder: Path,
    old_id: str = OLD_VILLAGE_ID,
    new_id: str = NEW_VILLAGE_ID,
) -> dict:
    before = read_operator_link(old_id, new_id)
    path = backup_old_village(folder, old_id)
    _copy_registration_code_if_empty(old_id, new_id)
    move = move_links_to_new(old_id, new_id)
    delete_old_village(old_id)
    after = read_operator_link(old_id, new_id)
    return {"before": before, "backup": str(path), "move": move, "after": after}


def retire_split_villages(folder: Path) -> list[dict]:
    """캐시에 남은 예전 행정명 줄을 통합특별시 줄로 모은 뒤 지운다."""
    from services.supabase_client import list_villages

    pairs = split_village_pairs(list_villages())
    return [
        retire_old_village(folder, str(old.get("village_id") or ""), str(keep.get("village_id") or ""))
        for old, keep in pairs
    ]
