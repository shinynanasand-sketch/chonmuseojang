"""개발 화면의 비밀번호와 테스트 기록 삭제. 마을과 등록 코드는 남긴다."""

import hashlib
import hmac
import os
import time

from services.supabase_client import (
    delete_bookings_for_village,
    delete_calendar_for_village,
    delete_contents_for_village,
    delete_operators_for_village,
    delete_program_notes_for_village,
    delete_reviews_for_village,
    get_village_by_id,
    list_villages,
)

_TTL_SECONDS = 12 * 60 * 60
_CLEARS = {
    "operators": ("마을 운영자와 체험 담당을 지웠습니다.", delete_operators_for_village),
    "bookings": ("예약을 지웠습니다.", delete_bookings_for_village),
    "reviews": ("후기를 지웠습니다.", delete_reviews_for_village),
    "calendar": ("체험 달력을 지웠습니다.", delete_calendar_for_village),
    "notes": ("체험 글을 지웠습니다.", delete_program_notes_for_village),
    "contents": ("소개글·SNS를 지웠습니다.", delete_contents_for_village),
}


def dev_password() -> str:
    return os.getenv("DEV_ADMIN_PASSWORD", "")


def password_matches(given: str) -> bool:
    expected = dev_password()
    if not expected or not given or len(expected) != len(given):
        return False
    return hmac.compare_digest(expected, given)


def _secret() -> str:
    return os.getenv("CRON_SECRET", "")


def issue_dev_cookie() -> str:
    expires = int(time.time()) + _TTL_SECONDS
    payload = f"devadmin.{expires}"
    signature = hmac.new(_secret().encode(), payload.encode(), hashlib.sha256).hexdigest()[:20]
    return f"{payload}.{signature}"


def dev_cookie_ok(value: str) -> bool:
    parts = (value or "").split(".")
    if len(parts) != 3 or parts[0] != "devadmin":
        return False
    payload = f"{parts[0]}.{parts[1]}"
    expected = hmac.new(_secret().encode(), payload.encode(), hashlib.sha256).hexdigest()[:20]
    if len(expected) != len(parts[2]) or not hmac.compare_digest(expected, parts[2]):
        return False
    try:
        return int(parts[1]) >= int(time.time())
    except ValueError:
        return False


def dev_open(cookie: str, posted: str | None) -> tuple[bool, str]:
    if not dev_password():
        return False, "관리자가 비밀번호를 아직 정하지 않았습니다."
    if posted:
        if password_matches(posted):
            return True, ""
        return False, "비밀번호가 맞지 않습니다."
    if dev_cookie_ok(cookie):
        return True, ""
    return False, ""


def village_choices() -> list[dict]:
    rows = []
    for village in list_villages():
        name = str(village.get("village_name") or "").strip()
        village_id = str(village.get("village_id") or "").strip()
        if not name or not village_id:
            continue
        rows.append(
            {
                "village_id": village_id,
                "village_name": name,
                "sigungu": str(village.get("sigungu") or ""),
            }
        )
    rows.sort(key=lambda row: (row["sigungu"], row["village_name"]))
    return rows


def clear_village_records(village_id: str, kind: str) -> str:
    if get_village_by_id(village_id) is None:
        return "마을을 찾을 수 없습니다."
    chosen = _CLEARS.get(kind)
    if chosen is None:
        return "지울 항목이 없습니다."
    message, action = chosen
    action(village_id)
    return message
