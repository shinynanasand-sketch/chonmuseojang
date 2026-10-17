"""관광객 홈의 카카오 예약 안내. 운영자 식별자는 내보내지 않는다."""

import segno

from config import KAKAO_CHANNEL_URL
from services.supabase_client import get_village_by_id, list_village_operator_ids


def list_kakao_booking_villages() -> list[dict]:
    """마을 운영자가 있는 마을의 이름과 시군구만."""
    rows = []
    for village_id in list_village_operator_ids():
        village = get_village_by_id(village_id)
        if not village:
            continue
        rows.append(
            {
                "village_id": village_id,
                "village_name": village.get("village_name") or village_id,
                "sigungu": village.get("sigungu") or "",
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
