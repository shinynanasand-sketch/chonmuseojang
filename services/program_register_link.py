"""체험 담당 고르기 링크. 주소에는 카카오 사용자 ID를 넣지 않는다."""

import base64
import hashlib
import hmac
import os
import time

_TTL_SECONDS = 2 * 60 * 60
_PREFIX = b"program-register-v1"


def _secret() -> bytes:
    return os.getenv("CRON_SECRET", "").encode()


def _keystream(nonce: bytes, size: int) -> bytes:
    chunks: list[bytes] = []
    counter = 0
    filled = 0
    while filled < size:
        chunk = hmac.new(
            _secret(), _PREFIX + nonce + counter.to_bytes(2, "big"), hashlib.sha256
        ).digest()
        chunks.append(chunk)
        filled += len(chunk)
        counter += 1
    return b"".join(chunks)[:size]


def _encode_user(user_id: str, nonce: bytes) -> str:
    raw = user_id.encode()
    masked = bytes(left ^ right for left, right in zip(raw, _keystream(nonce, len(raw))))
    packed = nonce + len(raw).to_bytes(2, "big") + masked
    return base64.urlsafe_b64encode(packed).decode().rstrip("=")


def _decode_user(encoded: str) -> str | None:
    padding = "=" * (-len(encoded) % 4)
    try:
        packed = base64.urlsafe_b64decode(encoded + padding)
    except (ValueError, TypeError):
        return None
    if len(packed) < 8:
        return None
    nonce, length_bytes, masked = packed[:6], packed[6:8], packed[8:]
    length = int.from_bytes(length_bytes, "big")
    if length != len(masked) or length == 0 or length > 200:
        return None
    raw = bytes(left ^ right for left, right in zip(masked, _keystream(nonce, length)))
    try:
        return raw.decode()
    except UnicodeDecodeError:
        return None


def issue_program_register_token(user_id: str, village_id: str) -> str:
    expires = int(time.time()) + _TTL_SECONDS
    nonce = hashlib.sha256(f"{user_id}.{village_id}.{expires}".encode()).digest()[:6]
    user_part = _encode_user(user_id, nonce)
    payload = f"{village_id}.{expires}.{user_part}"
    signature = hmac.new(_secret(), payload.encode(), hashlib.sha256).hexdigest()[:20]
    return f"{payload}.{signature}"


def claims_from_program_register_token(token: str) -> dict | None:
    parts = (token or "").rsplit(".", 3)
    if len(parts) != 4:
        return None
    village_id, expires, user_part, signature = parts
    if not village_id or not user_part:
        return None
    payload = f"{village_id}.{expires}.{user_part}"
    expected = hmac.new(_secret(), payload.encode(), hashlib.sha256).hexdigest()[:20]
    if len(expected) != len(signature) or not hmac.compare_digest(expected, signature):
        return None
    try:
        if int(expires) < int(time.time()):
            return None
    except (TypeError, ValueError):
        return None
    user_id = _decode_user(user_part)
    if not user_id:
        return None
    return {"kakao_user_id": user_id, "village_id": village_id}


def program_register_url(user_id: str, village_id: str) -> str:
    base = os.getenv("PUBLIC_BASE_URL", "https://chonmuseojang.vercel.app").rstrip("/")
    return f"{base}/program/{issue_program_register_token(user_id, village_id)}"
