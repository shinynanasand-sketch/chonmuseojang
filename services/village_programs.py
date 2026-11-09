"""공공데이터 프로그램 글을 항목으로 나누고 운영 여부를 붙인다."""

import hashlib

from services.supabase_client import get_village_by_id, list_program_status, save_program_status


def program_key(label: str) -> str:
    normalized = " ".join(label.split())
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
    return digest


def split_program_text(value: str) -> list[str]:
    """괄호 밖의 +와 줄바꿈만 항목 경계로 쓴다."""
    text = (value or "").replace("\r\n", "\n").replace("\r", "\n")
    parts: list[str] = []
    buf: list[str] = []
    depth = 0
    for char in text:
        if char == "(":
            depth += 1
            buf.append(char)
        elif char == ")" and depth:
            depth -= 1
            buf.append(char)
        elif depth == 0 and char in "+\n":
            piece = "".join(buf).strip()
            if piece:
                parts.append(piece)
            buf = []
        else:
            buf.append(char)
    tail = "".join(buf).strip()
    if tail:
        parts.append(tail)
    return parts


def program_labels(village: dict) -> list[str]:
    name = str(village.get("program_name") or "").strip()
    source = name or str(village.get("program_type") or "").strip()
    labels = split_program_text(source)
    from services.demo_data import demo_extra_labels

    for extra in demo_extra_labels(village):
        if extra not in labels:
            labels.append(extra)
    from services.field_changes import extra_labels

    for extra in extra_labels(str(village.get("village_id") or "")):
        if extra not in labels:
            labels.append(extra)
    return labels


def programs_for(village: dict, saved_rows: list[dict] | None = None) -> list[dict]:
    labels = program_labels(village)
    village_id = str(village.get("village_id") or "")
    if saved_rows is None:
        saved_rows = list_program_status(village_id)
    saved = {row.get("program_key"): row for row in saved_rows}
    from services.field_changes import status_is_before_record, stop_labels

    stopped = stop_labels(village_id)
    items = []
    to_stop: list[str] = []
    for label in labels:
        row = saved.get(program_key(label))
        if row is None:
            operating = label not in stopped
            if label in stopped:
                to_stop.append(label)
        else:
            operating = bool(row.get("is_operating"))
            if label in stopped and operating and status_is_before_record(row.get("updated_at")):
                operating = False
                to_stop.append(label)
        items.append({"label": label, "is_operating": operating})
    for label in to_stop:
        try:
            save_program_status(village_id, program_key(label), label, False)
        except RuntimeError:
            break
    return items


class UnknownProgram(Exception):
    pass


def set_program_operating(village_id: str, label: str, is_operating: bool) -> list[dict]:
    village = get_village_by_id(village_id)
    if village is None:
        raise UnknownProgram("마을을 찾지 못했습니다.")
    labels = program_labels(village)
    key = program_key(label)
    canonical = next((item for item in labels if program_key(item) == key), "")
    if not canonical:
        raise UnknownProgram("이 마을 프로그램이 아닙니다.")
    save_program_status(village_id, key, canonical, is_operating)
    return programs_for(village)
