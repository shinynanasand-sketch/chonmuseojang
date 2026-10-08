"""카카오 @sys.number, @sys.date와 대표값·원문 구분."""

import json
import re
from typing import Any

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def parse_sys_number(value: Any) -> int | None:
    """숫자, 숫자 문자열, amount/value JSON을 정수로 읽는다. 실패하면 None."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if value.is_integer() else None
    if isinstance(value, dict):
        return _number_from_mapping(value)
    text = str(value).strip()
    if not text:
        return None
    if text.isdigit():
        return int(text)
    if not text.startswith("{"):
        return None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    if isinstance(parsed, dict):
        return _number_from_mapping(parsed)
    return None


def parse_sys_date(value: Any) -> str | None:
    """YYYY-MM-DD 또는 JSON의 date/value만 날짜 문자열로 돌린다."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, dict):
        return _date_from_mapping(value)
    text = str(value).strip()
    if _DATE.match(text):
        return text
    if not text.startswith("{"):
        return None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    if isinstance(parsed, dict):
        return _date_from_mapping(parsed)
    return None


def representative(params: dict[str, Any] | None, key: str) -> Any:
    """action.params의 대표값. 원문은 읽지 않는다."""
    if not isinstance(params, dict):
        return None
    return params.get(key)


def param_origin(detail_params: dict[str, Any] | None, key: str) -> str:
    """detailParams.origin. 사람이 말한 원문이다."""
    if not isinstance(detail_params, dict):
        return ""
    raw = detail_params.get(key)
    if not isinstance(raw, dict):
        return ""
    return str(raw.get("origin") or "").strip()


def booking_id_from_params(params: dict[str, Any] | None) -> int | None:
    """예약번호는 대표값만 숫자로 파싱한다."""
    return parse_sys_number(representative(params, "booking_id"))


def _number_from_mapping(data: dict) -> int | None:
    for key in ("amount", "value"):
        if key not in data:
            continue
        parsed = parse_sys_number(data[key])
        if parsed is not None:
            return parsed
    return None


def _date_from_mapping(data: dict) -> str | None:
    for key in ("date", "value"):
        if key not in data:
            continue
        parsed = parse_sys_date(data[key])
        if parsed:
            return parsed
    return None
