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


def test_register_operator_without_prefix_inserts_row(sample_village_with_registration_code):
    result = register_operator("new_owner_kakao", "예시 갯벌마을 GB-001")
    assert result["ok"] is True
    assert result["village_id"] == sample_village_with_registration_code["village_id"]


def test_register_operator_rejects_wrong_code(sample_village_with_registration_code):
    result = register_operator("new_owner_kakao", "등록 예시 갯벌마을 WRONG")
    assert result == {"ok": False, "reason": "code_mismatch"}


def test_same_code_on_sido_copies_registers_one_village():
    upsert_villages(
        [
            {
                "village_id": "OLD",
                "village_name": "소포마을",
                "sigungu": "진도군",
                "address": "전라남도 진도군",
            },
            {
                "village_id": "NEW",
                "village_name": "소포마을",
                "sigungu": "진도군",
                "address": "전남광주통합특별시 진도군",
            },
        ]
    )
    set_registration_code("OLD", "SP-010")
    set_registration_code("NEW", "SP-010")
    result = register_operator("sopo_owner", "등록 소포마을 SP-010")
    assert result == {"ok": True, "village_id": "NEW"}
    delete_operator_by_kakao_id("sopo_owner")


def test_same_name_in_two_sigungu_needs_sigungu_in_utterance():
    upsert_villages(
        [
            {"village_id": "DAM", "village_name": "학동마을", "sigungu": "담양군"},
            {"village_id": "GO", "village_name": "학동마을", "sigungu": "고흥군"},
        ]
    )
    set_registration_code("DAM", "DM-011")
    set_registration_code("GO", "GH-012")
    assert register_operator("owner_short", "등록 학동마을 DM-011") == {
        "ok": False,
        "reason": "village_not_found",
    }
    result = register_operator("owner_dam", "등록 담양군 학동마을 DM-011")
    assert result == {"ok": True, "village_id": "DAM"}
    assert register_operator("owner_bad", "등록 담양군 학동마을 GH-012") == {
        "ok": False,
        "reason": "code_mismatch",
    }
    delete_operator_by_kakao_id("owner_dam")


def test_sync_keeps_existing_registration_code(sample_village_with_registration_code):
    upsert_villages(
        [{"village_id": "V001", "village_name": "예시 갯벌마을", "sigungu": "신안군"}]
    )
    rows = [row for row in list_villages() if row["village_id"] == "V001"]
    assert rows[0]["registration_code"] == "GB-001"
