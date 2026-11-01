"""운영자 웹 세션. 로그인에 성공한 뒤에만 발급한다."""

import hashlib
import hmac
import secrets
import time

from config import CRON_SECRET

_PROCESS_SECRET = secrets.token_hex(32)
_TTL_SECONDS = 12 * 60 * 60


def _secret() -> bytes:
    return (CRON_SECRET or _PROCESS_SECRET).encode()


def issue_operator_session(operator: dict, now: float | None = None) -> str:
    expiry = int(now if now is not None else time.time()) + _TTL_SECONDS
    payload = f"{int(operator['operator_id'])}.{expiry}"
    signature = hmac.new(_secret(), payload.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{payload}.{signature}"


def operator_id_from_session(token: str, now: float | None = None) -> int | None:
    parts = (token or "").split(".")
    if len(parts) != 3:
        return None
    operator_id, expiry, signature = parts
    if not operator_id.isdigit() or not expiry.isdigit():
        return None
    payload = f"{operator_id}.{expiry}"
    expected = hmac.new(_secret(), payload.encode(), hashlib.sha256).hexdigest()[:32]
    if not hmac.compare_digest(signature, expected):
        return None
    if int(expiry) < int(now if now is not None else time.time()):
        return None
    return int(operator_id)
