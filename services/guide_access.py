"""등록 안내의 비밀번호. 쿠키에는 비밀번호를 넣지 않는다."""

import hashlib
import hmac
import os
import time

from services.supabase_client import list_villages
from services.village_programs import program_labels

_TTL_SECONDS = 12 * 60 * 60


def guide_password() -> str:
    return os.getenv("GUIDE_PASSWORD", "")


def password_matches(given: str) -> bool:
    expected = guide_password()
    if not expected or not given or len(expected) != len(given):
        return False
    return hmac.compare_digest(expected, given)


def _secret() -> str:
    return os.getenv("CRON_SECRET", "")


def issue_unlock_cookie() -> str:
    expires = int(time.time()) + _TTL_SECONDS
    payload = f"guide.{expires}"
    signature = hmac.new(_secret().encode(), payload.encode(), hashlib.sha256).hexdigest()[:20]
    return f"{payload}.{signature}"


def unlock_cookie_ok(value: str) -> bool:
    parts = (value or "").split(".")
    if len(parts) != 3 or parts[0] != "guide":
        return False
    payload = f"{parts[0]}.{parts[1]}"
    expected = hmac.new(_secret().encode(), payload.encode(), hashlib.sha256).hexdigest()[:20]
    if len(expected) != len(parts[2]) or not hmac.compare_digest(expected, parts[2]):
        return False
    try:
        return int(parts[1]) >= int(time.time())
    except ValueError:
        return False


def codes_open(cookie: str, posted: str | None) -> tuple[bool, str]:
    """비밀번호가 없거나 틀리면 코드를 열지 않는다."""
    if not guide_password():
        return False, "관리자가 비밀번호를 아직 정하지 않았습니다."
    if posted:
        if password_matches(posted):
            return True, ""
        return False, "비밀번호가 맞지 않습니다."
    if unlock_cookie_ok(cookie):
        return True, ""
    return False, ""


def guide_rows(show_codes: bool) -> list[dict]:
    rows = []
    for village in list_villages():
        name = str(village.get("village_name") or "").strip()
        if not name:
            continue
        labels = program_labels(village)
        rows.append(
            {
                "village_name": name,
                "sigungu": str(village.get("sigungu") or ""),
                "programs": ", ".join(labels) if labels else "없음",
                "code": str(village.get("registration_code") or "") if show_codes else "",
            }
        )
    rows.sort(key=lambda row: (row["sigungu"], row["village_name"]))
    return rows


def guide_page_url(path: str) -> str:
    base = os.getenv("PUBLIC_BASE_URL", "https://chonmuseojang.vercel.app").rstrip("/")
    return f"{base}{path}"
