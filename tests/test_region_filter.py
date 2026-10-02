from services.public_data_sync import filter_gwangju_jeonnam


def test_filter_includes_old_name_jeonnam(sample_raw_village_rows_old_names):
    result = filter_gwangju_jeonnam(sample_raw_village_rows_old_names)
    village_ids = [row["village_id"] for row in result]
    assert "V001" in village_ids


def test_filter_includes_old_name_gwangju(sample_raw_village_rows_old_names):
    result = filter_gwangju_jeonnam(sample_raw_village_rows_old_names)
    village_ids = [row["village_id"] for row in result]
    assert "V002" in village_ids


def test_filter_excludes_other_region(sample_raw_village_rows_old_names):
    result = filter_gwangju_jeonnam(sample_raw_village_rows_old_names)
    village_ids = [row["village_id"] for row in result]
    assert "V003" not in village_ids


def test_filter_includes_new_integrated_name(sample_raw_village_rows_new_name):
    result = filter_gwangju_jeonnam(sample_raw_village_rows_new_name)
    village_ids = [row["village_id"] for row in result]
    assert "V004" in village_ids


def test_filter_excludes_jeju_even_with_similar_words(sample_raw_village_rows_new_name):
    result = filter_gwangju_jeonnam(sample_raw_village_rows_new_name)
    village_ids = [row["village_id"] for row in result]
    assert "V005" not in village_ids


def test_filter_excludes_other_city_with_same_district_name():
    rows = [
        {"village_id": "PD_DAEJEON", "sido": "대전광역시", "sigungu": "동구"},
        {"village_id": "PD_GWANGJU", "sido": "광주광역시", "sigungu": "동구"},
    ]
    village_ids = [row["village_id"] for row in filter_gwangju_jeonnam(rows)]
    assert "PD_DAEJEON" not in village_ids
    assert "PD_GWANGJU" in village_ids


def test_filter_returns_empty_list_for_empty_input():
    result = filter_gwangju_jeonnam([])
    assert result == []


def test_filter_handles_missing_fields_gracefully():
    rows = [{"village_id": "V999", "village_name": "필드누락마을"}]
    result = filter_gwangju_jeonnam(rows)
    assert isinstance(result, list)
