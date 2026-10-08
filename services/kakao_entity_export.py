"""villages_cache 행을 오픈빌더 엔티티 CSV 행으로 바꾼다."""

import csv
import re
from pathlib import Path

_ALIAS_SPLIT = re.compile(r"[,、|;]+")
_TRAILING_PAREN = re.compile(r"^(.+?)[（(]([^()（）]+)[）)]$")
_PREFERRED_SIDO = ("전남광주통합특별시", "광주특별시")


class EntityExportError(Exception):
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("\n".join(errors))


def expand_synonyms(row: dict) -> list[str]:
    parts = _without_parens(str(row.get("village_name") or ""))
    for token in _alias_tokens(row.get("alias")):
        parts.extend(_without_parens(token))
    return [cleaned for part in parts if (cleaned := _one_space(part))]


def build_village_name_rows(villages: list[dict]) -> tuple[list[list[str]], list[str]]:
    rows: list[list[str]] = []
    errors: list[str] = []
    for village in villages:
        village_id = str(village.get("village_id") or "").strip()
        if not str(village.get("village_name") or "").strip():
            errors.append(f"마을명이 비어 있음: {village_id}")
            continue
        rows.append([village_id, *expand_synonyms(village)])
    return rows, errors


def build_registration_code_rows(villages: list[dict]) -> list[list[str]]:
    rows: list[list[str]] = []
    for village in villages:
        code = str(village.get("registration_code") or "").strip()
        if code:
            rows.append([code])
    return rows


def validate_entries(rows: list[list[str]]) -> list[str]:
    errors: list[str] = []
    seen_representatives: set[str] = set()
    synonym_owner: dict[str, str] = {}
    for row in rows:
        representative = row[0]
        if representative in seen_representatives:
            errors.append(f"대표값 중복: {representative}")
        seen_representatives.add(representative)
        seen_in_row: set[str] = set()
        for synonym in row[1:]:
            if synonym in seen_in_row:
                errors.append(f"같은 대표값 안 동의어 중복: {representative} '{synonym}'")
            else:
                seen_in_row.add(synonym)
            owner = synonym_owner.get(synonym)
            if owner is None:
                synonym_owner[synonym] = representative
            elif owner != representative:
                errors.append(
                    f"서로 다른 대표값의 동의어 겹침: '{synonym}' ({owner}, {representative})"
                )
    return errors


def export_entity_csvs(villages: list[dict], out_dir: Path) -> None:
    villages = _collapse_same_place(villages)
    villages = _qualify_shared_names(villages)
    village_rows, errors = build_village_name_rows(villages)
    errors.extend(validate_entries(village_rows))
    code_rows = build_registration_code_rows(villages)
    errors.extend(validate_entries(code_rows))
    if errors:
        raise EntityExportError(errors)
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_entity_csv(out_dir / "village_name.csv", village_rows)
    _write_entity_csv(out_dir / "registration_code.csv", code_rows)


def _collapse_same_place(villages: list[dict]) -> list[dict]:
    """같은 마을명·시군구는 행정구역 명칭만 다른 중복이므로 한 행만 남긴다."""
    chosen: dict[tuple[str, str], dict] = {}
    order: list[tuple[str, str]] = []
    for village in villages:
        key = (
            str(village.get("village_name") or "").strip(),
            str(village.get("sigungu") or "").strip(),
        )
        if key not in chosen:
            chosen[key] = village
            order.append(key)
            continue
        chosen[key] = _prefer_village(chosen[key], village)
    return [chosen[key] for key in order]


def _qualify_shared_names(villages: list[dict]) -> list[dict]:
    """시군이 다른데 마을명이 같으면 동의어에 시군구를 붙인다."""
    counts: dict[str, int] = {}
    for village in villages:
        name = str(village.get("village_name") or "").strip()
        counts[name] = counts.get(name, 0) + 1
    qualified: list[dict] = []
    for village in villages:
        name = str(village.get("village_name") or "").strip()
        if counts.get(name, 0) < 2:
            qualified.append(village)
            continue
        sigungu = str(village.get("sigungu") or "").strip()
        copy = dict(village)
        copy["village_name"] = f"{sigungu} {name}".strip()
        qualified.append(copy)
    return qualified


def _prefer_village(current: dict, candidate: dict) -> dict:
    chosen, other = current, candidate
    if _sido_rank(candidate) < _sido_rank(current):
        chosen, other = candidate, current
    code = str(other.get("registration_code") or "").strip()
    if code and not str(chosen.get("registration_code") or "").strip():
        chosen = dict(chosen)
        chosen["registration_code"] = code
    return chosen


def _sido_rank(village: dict) -> int:
    text = f"{village.get('sido') or ''} {village.get('address') or ''}"
    for index, name in enumerate(_PREFERRED_SIDO):
        if name in text:
            return index
    return len(_PREFERRED_SIDO)


def _without_parens(text: str) -> list[str]:
    stripped = text.strip()
    match = _TRAILING_PAREN.fullmatch(stripped)
    if match:
        return [part.strip() for part in match.groups() if part.strip()]
    if any(mark in stripped for mark in "()（）"):
        joined = re.sub(r"[()（）]", "", stripped).strip()
        return [joined] if joined else []
    return [stripped] if stripped else []


def _one_space(text: str) -> str:
    collapsed = re.sub(r"\s+", " ", text.strip())
    if collapsed.count(" ") <= 1:
        return collapsed
    first, rest = collapsed.split(" ", 1)
    return f"{first} {rest.replace(' ', '')}"


def _alias_tokens(alias) -> list[str]:
    if alias is None:
        return []
    if isinstance(alias, list):
        parts = [str(item) for item in alias]
    else:
        parts = _ALIAS_SPLIT.split(str(alias))
    return [part.strip() for part in parts if part.strip()]


def _write_entity_csv(path: Path, rows: list[list[str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        csv.writer(handle, lineterminator="\n").writerows(rows)
