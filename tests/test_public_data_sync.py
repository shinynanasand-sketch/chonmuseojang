from unittest.mock import patch

from services.public_data_sync import (
    _extract_items,
    normalize_public_data_row,
    sync_village_data,
)


def test_extract_standard_openapi_items():
    payload = {
        "header": {"resultCode": "00", "resultMsg": "NORMAL SERVICE."},
        "body": {
            "items": {
                "item": [
                    {
                        "exprnVilageNm": "태인농촌체험휴양마을",
                        "ctprvnNm": "전라남도",
                        "signguNm": "해남군",
                        "exprnSe": "전통 문화체험",
                        "exprnCn": "김치체험",
                        "rdnmadr": "전라남도 해남군 계곡면 비슬안길 187",
                        "latitude": "34.67906178",
                        "longitude": "126.6626818",
                    }
                ]
            },
            "numOfRows": 1,
            "pageNo": 1,
            "totalCount": 1,
        },
    }

    rows = _extract_items(payload)
    assert len(rows) == 1
    normalized = normalize_public_data_row(rows[0])
    assert normalized["village_name"] == "태인농촌체험휴양마을"
    assert normalized["sido"] == "전라남도"
    assert normalized["sigungu"] == "해남군"
    assert normalized["program_type"] == "전통 문화체험"
    assert normalized["program_name"] == "김치체험"
    assert normalized["address"].startswith("전라남도 해남군")
    assert normalized["latitude"] == 34.67906178
    assert normalized["village_id"].startswith("PD")


def test_village_id_stays_the_same_across_calls():
    raw = {
        "exprnVilageNm": "태인농촌체험휴양마을",
        "signguNm": "해남군",
        "rdnmadr": "전라남도 해남군 계곡면 비슬안길 187",
    }
    assert normalize_public_data_row(raw)["village_id"] == normalize_public_data_row(raw)["village_id"]


@patch("services.public_data_sync.upsert_to_supabase")
@patch("services.public_data_sync.fetch_from_public_data_api")
def test_sync_filters_before_saving(mock_fetch, mock_upsert):
    mock_fetch.return_value = [
        {"village_id": "V001", "sido": "전라남도", "sigungu": "신안군"},
        {"village_id": "V002", "sido": "강원특별자치도", "sigungu": "춘천시"},
    ]

    sync_village_data()

    saved_rows = mock_upsert.call_args[0][0]
    saved_ids = [row["village_id"] for row in saved_rows]
    assert "V001" in saved_ids
    assert "V002" not in saved_ids


@patch("services.public_data_sync.log_sync_result")
@patch("services.public_data_sync.upsert_to_supabase")
@patch("services.public_data_sync.fetch_from_public_data_api")
def test_sync_logs_result(mock_fetch, mock_upsert, mock_log):
    mock_fetch.return_value = [{"village_id": "V001", "sido": "전라남도", "sigungu": "신안군"}]

    sync_village_data()

    assert mock_log.called


@patch("services.public_data_sync.upsert_to_supabase")
@patch("services.public_data_sync.fetch_from_public_data_api")
def test_sync_sets_trust_score_when_missing(mock_fetch, mock_upsert):
    mock_fetch.return_value = [
        {"village_id": "PD001", "village_name": "태인마을", "sido": "전라남도", "sigungu": "해남군"}
    ]

    sync_village_data()

    saved = mock_upsert.call_args[0][0][0]
    assert saved["trust_score"] == 40


@patch("services.public_data_sync.fetch_from_public_data_api")
def test_sync_skips_demo_fallback_by_default(mock_fetch):
    mock_fetch.return_value = []

    result = sync_village_data()

    assert result["source"] == "public_data_village"
    assert result["total_filtered"] == 0


@patch("services.public_data_sync.fetch_from_public_data_api")
def test_sync_skips_demo_fallback_when_real_villages_exist(mock_fetch):
    from services.supabase_client import list_villages, upsert_villages

    upsert_villages(
        [{"village_id": "PD999", "village_name": "실마을", "sido": "전라남도", "sigungu": "담양군"}]
    )
    mock_fetch.return_value = []

    result = sync_village_data(use_demo_fallback=True)

    saved_ids = [row["village_id"] for row in list_villages()]
    assert result["source"] == "public_data_village"
    assert "V001" not in saved_ids
    assert "PD999" in saved_ids


def test_public_list_hides_demo_villages_when_real_data_exists():
    from services.supabase_client import list_public_villages, list_villages, upsert_villages

    upsert_villages(
        [
            {"village_id": "V001", "village_name": "예시 갯벌마을", "sido": "전라남도", "sigungu": "신안군"},
            {"village_id": "PD100", "village_name": "푸른바다마을", "sido": "전라남도", "sigungu": "완도군"},
        ]
    )

    public_ids = [row["village_id"] for row in list_public_villages()]
    stored_ids = [row["village_id"] for row in list_villages()]
    assert public_ids == ["PD100"]
    assert "V001" in stored_ids


@patch("services.public_data_sync.fetch_from_public_data_api")
def test_sync_handles_api_failure_without_crashing(mock_fetch):
    mock_fetch.side_effect = Exception("공공데이터 API 호출 실패")

    result = sync_village_data()
    assert result["status"] == "failure"
