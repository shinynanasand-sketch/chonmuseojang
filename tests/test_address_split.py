"""통합특별시 줄이 있으면 예전 행정명 줄은 저장하지 않고 캐시에서도 뺀다."""

import json
from pathlib import Path
from unittest.mock import patch

import services.supabase_client as store
from services.booking import create_booking
from services.public_data_sync import sync_village_data
from services.supabase_client import (
    get_operator_by_kakao_id,
    get_village_by_id,
    insert_operator,
    insert_review,
    list_bookings,
    list_reviews,
    list_villages,
    set_registration_code,
    upsert_villages,
)
from services.village_retirement import retire_split_villages, split_village_pairs

NEW_ID = "PDintegrated01"
OLD_ID = "PDjeonnam0001"
ALONE_ID = "PDjeonnam0002"
GWANGJU_ID = "PDgwangju0001"
FLOWER_ID = "PDflower00001"
KEPT_CODE = "SPLIT-KEEP-1"


def _row(village_id: str, name: str, sigungu: str, sido: str, address: str, program: str) -> dict:
    return {
        "village_id": village_id,
        "village_name": name,
        "sigungu": sigungu,
        "sido": sido,
        "address": address,
        "program_name": program,
    }


def test_split_ignores_demo_rows_and_villages_without_integrated_row():
    rows = [
        _row("V001", "예시 갯벌마을", "신안군", "전라남도", "전라남도 신안군", "갯벌"),
        _row(OLD_ID, "나눔마을", "순천시", "전라남도", "전라남도 순천시 옛길 1", "감자수확"),
        _row(NEW_ID, "나눔마을", "순천시", "전남광주통합특별시", "전남광주통합특별시 순천시 새길 1", "감자수확"),
        _row(GWANGJU_ID, "나눔마을", "순천시", "광주광역시", "광주광역시 순천시 옛길 2", "감자수확"),
        _row(ALONE_ID, "외딴마을", "구례군", "전라남도", "전라남도 구례군", "고구마수확"),
        _row("PDcity000001", "빛고을마을", "북구", "광주특별시", "광주특별시 북구", "농사체험"),
    ]
    pairs = {(old["village_id"], keep["village_id"]) for old, keep in split_village_pairs(rows)}
    assert pairs == {(OLD_ID, NEW_ID), (GWANGJU_ID, NEW_ID)}


@patch("services.public_data_sync.fetch_from_public_data_api")
def test_sync_keeps_integrated_row_and_lone_old_village(mock_fetch, tmp_path, monkeypatch):
    monkeypatch.setenv("VILLAGE_BACKUP_DIR", str(tmp_path))
    upsert_villages(
        [_row(OLD_ID, "나눔마을", "순천시", "전라남도", "전라남도 순천시 옛길 1", "감자수확")]
    )
    mock_fetch.return_value = [
        _row(OLD_ID, "나눔마을", "순천시", "전라남도", "전라남도 순천시 옛길 1", "감자수확"),
        _row(NEW_ID, "나눔마을", "순천시", "전남광주통합특별시", "전남광주통합특별시 순천시 새길 1", "감자수확"),
        _row(ALONE_ID, "외딴마을", "구례군", "전라남도", "전라남도 구례군", "고구마수확"),
    ]

    result = sync_village_data()

    ids = {row["village_id"] for row in list_villages()}
    assert result["retired_old_rows"] == 1
    assert OLD_ID not in ids
    assert NEW_ID in ids
    assert ALONE_ID in ids
    assert get_village_by_id(ALONE_ID)["address"].startswith("전라남도")


def test_retire_moves_operator_booking_and_named_reservation(test_client, tmp_path):
    store._operators[:] = [
        row
        for row in store._operators
        if row.get("village_id") not in {OLD_ID, NEW_ID}
        and not str(row.get("kakao_user_id") or "").startswith("split-")
    ]
    upsert_villages(
        [
            _row(OLD_ID, "나눔마을", "순천시", "전라남도", "전라남도 순천시 옛길 1", "감자수확"),
            _row(NEW_ID, "나눔마을", "순천시", "전남광주통합특별시", "전남광주통합특별시 순천시 새길 1", "감자수확"),
            _row(FLOWER_ID, "순천꽃마차마을", "순천시", "전라남도", "전라남도 순천시", "감자수확"),
        ]
    )
    set_registration_code(OLD_ID, KEPT_CODE)
    insert_operator(
        {
            "operator_id": 9301,
            "village_id": OLD_ID,
            "kakao_user_id": "split-manager",
            "login_id": "split-manager",
            "role": "village",
            "is_active": True,
        }
    )
    pending = create_booking(OLD_ID, "split-guest", "2026-11-04", 3, program_label="감자수확")
    insert_review(
        {
            "village_id": OLD_ID,
            "booking_id": pending["booking_id"],
            "customer_kakao_id": "split-guest",
            "rating": 5,
            "comment": "옛 후기",
        }
    )

    retired = retire_split_villages(tmp_path)
    assert len(retired) == 1
    assert get_village_by_id(OLD_ID) is None
    assert get_operator_by_kakao_id("split-manager")["village_id"] == NEW_ID
    assert list_bookings(village_id=NEW_ID)[0]["booking_id"] == pending["booking_id"]
    assert list_reviews(village_id=NEW_ID)[0]["comment"] == "옛 후기"
    assert get_village_by_id(NEW_ID)["registration_code"] == KEPT_CODE
    backup = json.loads(Path(retired[0]["backup"]).read_text(encoding="utf-8"))
    assert KEPT_CODE not in json.dumps(backup, ensure_ascii=False)
    assert "split-guest" not in json.dumps(backup, ensure_ascii=False)

    booked = test_client.post(
        "/kakao/booking",
        json={
            "intent": {"name": ""},
            "userRequest": {
                "utterance": "나눔마을 감자수확 2026-11-01 30명",
                "user": {"id": "split-tourist"},
            },
            "action": {"params": {}},
        },
    )
    assert booked.status_code == 200
    assert "접수" in booked.text
    labels = [row["program_label"] for row in list_bookings(village_id=NEW_ID)]
    assert labels.count("감자수확") == 2
    assert get_village_by_id(FLOWER_ID) is not None
