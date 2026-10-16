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
    return split_program_text(source)


def programs_for(village: dict, saved_rows: list[dict] | None = None) -> list[dict]:
    labels = program_labels(village)
    if saved_rows is None:
        saved_rows = list_program_status(str(village.get("village_id") or ""))
    saved = {row.get("program_key"): row for row in saved_rows}
    items = []
    for label in labels:
        row = saved.get(program_key(label))
        operating = True if row is None else bool(row.get("is_operating"))
        items.append({"label": label, "is_operating": operating})
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
