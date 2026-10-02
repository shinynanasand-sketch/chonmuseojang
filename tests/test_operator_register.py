import pytest

from services.auth import register_operator
from services.supabase_client import (
    delete_operator_by_kakao_id,
    detach_operators_for_village,
    list_villages,
    restore_operators,
    set_registration_code,
    upsert_villages,
)


@pytest.fixture
def sample_village_with_registration_code():
    village = {
        "village_id": "V001",
        "village_name": "예시 갯벌마을",
        "registration_code": "GB-001",
    }
    detached = detach_operators_for_village(village["village_id"])
    upsert_villages([village])
    set_registration_code(village["village_id"], village["registration_code"], village)
    yield village
    delete_operator_by_kakao_id("new_owner_kakao")
    restore_operators(detached)


def test_register_operator_with_valid_code_inserts_row(sample_village_with_registration_code):
    utterance = "등록 예시 갯벌마을 GB-001"
    result = register_operator("new_owner_kakao", utterance)
    assert result["ok"] is True
    assert result["village_id"] == sample_village_with_registration_code["village_id"]


def test_register_operator_rejects_wrong_code(sample_village_with_registration_code):
    result = register_operator("new_owner_kakao", "등록 예시 갯벌마을 WRONG")
    assert result == {"ok": False, "reason": "code_mismatch"}


def test_sync_keeps_existing_registration_code(sample_village_with_registration_code):
    upsert_villages(
        [{"village_id": "V001", "village_name": "예시 갯벌마을", "sigungu": "신안군"}]
    )
    rows = [row for row in list_villages() if row["village_id"] == "V001"]
    assert rows[0]["registration_code"] == "GB-001"
