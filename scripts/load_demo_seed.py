"""시연용 마을·운영자 시드 데이터를 Supabase 또는 인메모리에 로드한다."""

import _bootstrap  # noqa: F401

from services.demo_data import DEMO_OPERATORS, DEMO_VILLAGES
from services.public_data_sync import log_sync_result
from services.supabase_client import get_supabase_client, upsert_villages


def load_demo_seed() -> dict:
    upsert_villages(DEMO_VILLAGES)

    client = get_supabase_client()
    if client:
        for op in DEMO_OPERATORS:
            client.table("operators").upsert(op, on_conflict="village_id").execute()

    log_sync_result(
        source="demo_seed",
        total_fetched=len(DEMO_VILLAGES),
        total_filtered=len(DEMO_VILLAGES),
        status="success",
        message="시연용 시드 데이터 로드",
    )
    return {"status": "success", "villages_loaded": len(DEMO_VILLAGES)}


if __name__ == "__main__":
    result = load_demo_seed()
    print(result)
