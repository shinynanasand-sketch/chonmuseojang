from unittest.mock import patch

from services.public_data_sync import sync_village_data


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


@patch("services.public_data_sync.fetch_from_public_data_api")
def test_sync_handles_api_failure_without_crashing(mock_fetch):
    mock_fetch.side_effect = Exception("공공데이터 API 호출 실패")

    result = sync_village_data()
    assert result["status"] == "failure"
