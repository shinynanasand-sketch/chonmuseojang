"""사무장이 체험 담당에게 체험을 나누어 붙인다.

체험 하나는 담당 한 명만 맡는다. 권한은 operators.program_key가 아니라 배정 표를 본다.
"""

from datetime import datetime, timezone

from services.supabase_client import (
    _stored_village,
    get_village_by_id,
    list_operator_programs,
    list_operators_for_village,
    replace_operator_programs,
)
from services.village_programs import program_key, programs_for


class GroupRejected(Exception):
    def __init__(self, message: str):
        self.message = message


def _operator_id(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def assigned_program_keys(operator: dict) -> set[str]:
    """체험 담당이 맡은 체험 키. 마을 운영자는 비어 있다."""
    if str(operator.get("role") or "village") != "program":
        return set()
    operator_id = _operator_id(operator.get("operator_id"))
    village_id = str(operator.get("village_id") or "")
    if operator_id is None or not village_id:
        return set()
    keys = set()
    for row in list_operator_programs(village_id):
        if _operator_id(row.get("operator_id")) == operator_id:
            key = str(row.get("program_key") or "")
            if key:
                keys.add(key)
    return keys


def _program_operators(village_id: str) -> list[dict]:
    return [
        operator
        for operator in list_operators_for_village(village_id)
        if operator.get("role") == "program" and operator.get("is_active", True)
    ]


def choice_label(operator_name: str, village_name: str) -> str:
    """선택 상자용 이름. 마을 저장 이름이 앞에 있을 때만 뺀다."""
    name = " ".join(str(operator_name or "").split())
    prefix = " ".join(str(village_name or "").split())
    if prefix and name.startswith(prefix + " "):
        short = name[len(prefix) :].strip()
        if short:
            return short
    return name or "담당"


def _stored_name(village_id: str) -> str:
    row = _stored_village(village_id) or {}
    return str(row.get("village_name") or "").strip()


def program_group_snapshot(village_id: str) -> dict:
    """현재 체험 목록과 담당 배정. 목록에서 빠진 체험은 stale에 둔다."""
    village = get_village_by_id(village_id) or {}
    current = programs_for(village)
    if any(item["label"] == "소금체험" for item in current):
        from services.demo_role import ensure_demo_staff

        ensure_demo_staff()
    labels = {program_key(item["label"]): item for item in current}
    operators = _program_operators(village_id)
    operator_ids = {_operator_id(operator.get("operator_id")) for operator in operators}
    assigned: dict[str, int] = {}
    stale = []
    for row in list_operator_programs(village_id):
        key = str(row.get("program_key") or "")
        operator_id = _operator_id(row.get("operator_id"))
        if key in labels and operator_id in operator_ids:
            assigned[key] = operator_id
            continue
        if key not in labels:
            stale.append(
                {
                    "program_key": key,
                    "label": row.get("label") or key,
                    "operator_id": operator_id,
                }
            )
    programs = []
    for item in current:
        key = program_key(item["label"])
        programs.append(
            {
                "label": item["label"],
                "program_key": key,
                "is_operating": item["is_operating"],
                "operator_id": assigned.get(key),
            }
        )
    unassigned = sum(1 for row in programs if row["operator_id"] is None)
    assigned_count = len(programs) - unassigned
    stored_name = _stored_name(village_id)
    return {
        "programs": programs,
        "operators": [
            {
                "operator_id": _operator_id(operator.get("operator_id")),
                "operator_name": operator.get("operator_name") or "",
                "option_label": choice_label(operator.get("operator_name") or "", stored_name),
            }
            for operator in operators
        ],
        "counts": {
            "programs": len(programs),
            "operators": len(operators),
            "unassigned": unassigned,
        },
        "stale": stale,
        "changed": bool(stale) or (unassigned > 0 and assigned_count > 0),
    }


def save_program_groups(village_id: str, assignments: list[dict]) -> dict:
    """현재 체험만 다시 배정한다. 빠지거나 비운 체험은 담당이 없다."""
    snapshot = program_group_snapshot(village_id)
    valid = {row["program_key"]: row["label"] for row in snapshot["programs"]}
    operator_ids = {row["operator_id"] for row in snapshot["operators"]}
    seen: set[str] = set()
    rows = []
    now = datetime.now(timezone.utc).isoformat()
    for item in assignments:
        key = str(item.get("program_key") or "").strip()
        if key not in valid:
            raise GroupRejected("없는 체험입니다.")
        if key in seen:
            raise GroupRejected("한 체험을 두 명에게 줄 수 없습니다.")
        seen.add(key)
        operator_id = item.get("operator_id")
        if operator_id in (None, ""):
            continue
        operator_id = _operator_id(operator_id)
        if operator_id not in operator_ids:
            raise GroupRejected("이 마을 체험 담당만 묶을 수 있습니다.")
        rows.append(
            {
                "village_id": village_id,
                "program_key": key,
                "label": valid[key],
                "operator_id": operator_id,
                "updated_at": now,
            }
        )
    replace_operator_programs(village_id, rows)
    return program_group_snapshot(village_id)
