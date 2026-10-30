"""관광객 홈의 카카오 예약 안내. 운영자 식별자는 내보내지 않는다."""

import time

import segno

from config import KAKAO_CHANNEL_URL
from services.demo_data import is_demo_village
from services.supabase_client import (
    get_supabase_client,
    list_village_operator_ids,
    list_villages_by_ids,
)

_VILLAGE_TTL = 60.0
_village_cache: tuple[float, list[dict]] | None = None


def list_kakao_booking_villages() -> list[dict]:
    """마을 운영자가 있는 마을의 이름과 시군구만. 시연 마을은 빼 둔다."""
    global _village_cache
    now = time.monotonic()
    live = get_supabase_client() is not None
    if live and _village_cache is not None and now - _village_cache[0] < _VILLAGE_TTL:
        return _village_cache[1]
    rows = _load_kakao_booking_villages()
    if live:
        _village_cache = (now, rows)
    return rows


def _load_kakao_booking_villages() -> list[dict]:
    ids = list_village_operator_ids()
    by_id = {str(row.get("village_id") or ""): row for row in list_villages_by_ids(ids)}
    rows = []
    for village_id in ids:
        village = by_id.get(village_id)
        if not village or is_demo_village(village):
            continue
        rows.append(
            {
                "village_id": village_id,
                "village_name": village.get("village_name") or village_id,
                "sigungu": village.get("sigungu") or "",
                "program_name": village.get("program_name") or "",
                "program_type": village.get("program_type") or "",
            }
        )
    rows.sort(key=lambda row: (row["sigungu"], row["village_name"]))
    return rows


def channel_qr_svg() -> str:
    qr = segno.make(KAKAO_CHANNEL_URL, error="m")
    return qr.svg_inline(title=KAKAO_CHANNEL_URL)


def home_kakao_guide() -> dict:
    return {
        "villages": list_kakao_booking_villages(),
        "channel_url": KAKAO_CHANNEL_URL,
        "qr_svg": channel_qr_svg(),
    }
