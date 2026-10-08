"""마을명·시군구당 등록 코드 하나. V001은 GB-001을 유지한다."""

import hashlib

V001_CODE = "GB-001"
_PREFERRED_SIDO = ("전남광주통합특별시", "광주특별시")


def plan_registration_codes(villages: list[dict]) -> list[tuple[str, str]]:
    """코드가 비어 있는 행만 (village_id, code)로 돌려준다."""
    groups: dict[tuple[str, str], list[dict]] = {}
    order: list[tuple[str, str]] = []
    for village in villages:
        name = str(village.get("village_name") or "").strip()
        if not name:
            continue
        key = (name, str(village.get("sigungu") or "").strip())
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(village)

    used = {
        str(village.get("registration_code") or "").strip()
        for village in villages
        if str(village.get("registration_code") or "").strip()
    }
    used.add(V001_CODE)
    planned: list[tuple[str, str]] = []
    for key in order:
        rows = groups[key]
        code = _group_code(rows, used)
        if code != V001_CODE:
            used.add(code)
        for row in rows:
            if str(row.get("registration_code") or "").strip():
                continue
            planned.append((str(row.get("village_id") or "").strip(), code))
    return planned


def _group_code(rows: list[dict], used: set[str]) -> str:
    if any(str(row.get("village_id") or "").strip() == "V001" for row in rows):
        return V001_CODE
    existing = [
        str(row.get("registration_code") or "").strip()
        for row in rows
        if str(row.get("registration_code") or "").strip()
    ]
    if existing:
        preferred = _preferred(rows)
        current = str(preferred.get("registration_code") or "").strip()
        return current or existing[0]
    code = _code_for(str(_preferred(rows).get("village_id") or ""), used)
    used.add(code)
    return code


def _code_for(village_id: str, used: set[str]) -> str:
    for salt in range(1000):
        material = hashlib.sha256(f"{village_id}:{salt}".encode()).digest()
        letters = "".join(chr(ord("A") + byte % 26) for byte in material[:2])
        number = int.from_bytes(material[2:4], "big") % 1000
        code = f"{letters}-{number:03d}"
        if code not in used:
            return code
    raise RuntimeError(f"registration code collision: {village_id}")


def _preferred(rows: list[dict]) -> dict:
    chosen = rows[0]
    for row in rows[1:]:
        if _sido_rank(row) < _sido_rank(chosen):
            chosen = row
    return chosen


def _sido_rank(village: dict) -> int:
    text = f"{village.get('sido') or ''} {village.get('address') or ''}"
    for index, name in enumerate(_PREFERRED_SIDO):
        if name in text:
            return index
    return len(_PREFERRED_SIDO)
