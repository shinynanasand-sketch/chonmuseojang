"""카카오 @sys.number, @sys.date와 대표값·원문 구분."""

import json
import re
from typing import Any

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_CLOCK = re.compile(r"(?<!\d)(\d{1,2}):(\d{2})(?::\d{2})?(?!\d)")
_KO_TIME = re.compile(r"(오전|오후)?\s*(\d{1,2})\s*시(?:\s*(\d{1,2})\s*분)?")


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


def normalize_clock(hour: int, minute: int, ampm: str = "") -> str:
    """시·분을 HH:MM로 맞춘다. 범위 밖이면 빈 문자열."""
    if minute < 0 or minute > 59 or hour < 0:
        return ""
    if ampm == "오전":
        if hour == 12:
            hour = 0
        elif hour > 12:
            return ""
    elif ampm == "오후":
        if hour == 12:
            pass
        elif 1 <= hour <= 11:
            hour += 12
        else:
            return ""
    elif hour > 23:
        return ""
    return f"{hour:02d}:{minute:02d}"


def parse_spoken_time(text: str) -> str:
    """문장에서 처음 나오는 시각. 10:00, 10시, 10시 30분, 오전 10시를 받는다."""
    found: list[tuple[int, str]] = []
    for match in _CLOCK.finditer(text or ""):
        clock = normalize_clock(int(match.group(1)), int(match.group(2)))
        if clock:
            found.append((match.start(), clock))
    for match in _KO_TIME.finditer(text or ""):
        clock = normalize_clock(int(match.group(2)), int(match.group(3) or 0), match.group(1) or "")
        if clock:
            found.append((match.start(), clock))
    if not found:
        return ""
    found.sort()
    return found[0][1]


def parse_sys_time(value: Any) -> str:
    """HH:MM, HH:MM:SS, 한국어 시각, JSON의 time/value를 HH:MM로 돌린다."""
    if value is None or isinstance(value, bool):
        return ""
    if isinstance(value, dict):
        return _time_from_mapping(value)
    text = str(value).strip()
    if not text:
        return ""
    if text[:1] in "{[":
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return ""
        if isinstance(parsed, dict):
            return _time_from_mapping(parsed)
        return ""
    return parse_spoken_time(text)


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


def kakao_photo_url(payload) -> str:
    """홍보 사진 주소 하나. secureUrls, media.url, https 발화 순이다."""
    for source in (payload.action.params, payload.action.detailParams):
        urls = _secure_urls_in(source)
        if urls:
            return urls[0]
    media = payload.userRequest.params.get("media")
    if isinstance(media, dict):
        url = str(media.get("url") or "").strip()
        if url.startswith("https://") and " " not in url:
            return url
    utterance = (payload.userRequest.utterance or "").strip()
    if utterance.startswith("https://") and " " not in utterance:
        return utterance
    return ""


def _secure_urls_in(value: Any) -> list[str]:
    found: list[str] = []
    _collect_secure_urls(value, found)
    return found


def _collect_secure_urls(value: Any, found: list[str]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "secureUrls":
                found.extend(_urls_from_secure_field(item))
            else:
                _collect_secure_urls(item, found)
        return
    if isinstance(value, list):
        for item in value:
            _collect_secure_urls(item, found)
        return
    if not isinstance(value, str):
        return
    text = value.strip()
    if text[:1] not in "{[":
        return
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return
    _collect_secure_urls(parsed, found)


def _http_url(text: str) -> bool:
    """이미지 플러그인 secureUrls는 http, 그 외 카카오 주소는 https다."""
    stripped = text.strip()
    return (stripped.startswith("https://") or stripped.startswith("http://")) and " " not in stripped


def _urls_from_secure_field(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if _http_url(str(item))]
    if isinstance(value, dict):
        for key in ("url", "value"):
            if key in value:
                return _urls_from_secure_field(value[key])
        return []
    text = str(value or "").strip()
    if text.startswith("List(") and text.endswith(")"):
        inner = text[len("List(") : -1]
        return [part.strip() for part in inner.split(",") if _http_url(part)]
    if _http_url(text):
        return [text]
    if text[:1] in "{[":
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return []
        return _urls_from_secure_field(parsed)
    return []


def _number_from_mapping(data: dict) -> int | None:
    for key in ("amount", "value"):
        if key not in data:
            continue
        parsed = parse_sys_number(data[key])
        if parsed is not None:
            return parsed
    return None


def _time_from_mapping(data: dict) -> str:
    for key in ("time", "value"):
        if key not in data:
            continue
        parsed = parse_sys_time(data[key])
        if parsed:
            return parsed
    return ""


def _date_from_mapping(data: dict) -> str | None:
    for key in ("date", "value"):
        if key not in data:
            continue
        parsed = parse_sys_date(data[key])
        if parsed:
            return parsed
    return None
