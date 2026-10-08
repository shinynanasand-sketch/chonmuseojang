from services.registration_codes import plan_registration_codes
from services.supabase_client import list_villages, set_registration_code, upsert_villages


def test_v001_keeps_gb001_and_same_place_shares_it():
    upsert_villages(
        [
            {
                "village_id": "V001",
                "village_name": "예시 갯벌마을",
                "sigungu": "신안군",
                "address": "전남광주통합특별시 신안군",
            },
            {
                "village_id": "OLD",
                "village_name": "예시 갯벌마을",
                "sigungu": "신안군",
                "address": "전라남도 신안군",
            },
        ]
    )
    planned = dict(plan_registration_codes(list_villages()))
    assert planned["V001"] == "GB-001"
    assert planned["OLD"] == "GB-001"


def test_existing_code_is_not_replaced_and_is_shared():
    upsert_villages(
        [
            {
                "village_id": "KEEP",
                "village_name": "가마을",
                "sigungu": "담양군",
                "registration_code": "ZZ-999",
            },
            {"village_id": "EMPTY", "village_name": "가마을", "sigungu": "담양군"},
        ]
    )
    set_registration_code("KEEP", "ZZ-999")
    planned = dict(plan_registration_codes(list_villages()))
    assert "KEEP" not in planned
    assert planned["EMPTY"] == "ZZ-999"


def test_different_places_get_different_letter_codes():
    upsert_villages(
        [
            {"village_id": "P1", "village_name": "가마을", "sigungu": "담양군"},
            {"village_id": "P2", "village_name": "나마을", "sigungu": "고흥군"},
            {"village_id": "D1", "village_name": "학동마을", "sigungu": "담양군"},
            {"village_id": "G1", "village_name": "학동마을", "sigungu": "고흥군"},
        ]
    )
    planned = dict(plan_registration_codes(list_villages()))
    codes = [planned["P1"], planned["P2"], planned["D1"], planned["G1"]]
    assert len(set(codes)) == 4
    assert planned["D1"] != planned["G1"]
    for code in codes:
        assert len(code) == 6 and code[2] == "-"
        assert code[:2].isalpha() and code[:2].isupper()
        assert code[3:].isdigit()
        assert code != "GB-001"
