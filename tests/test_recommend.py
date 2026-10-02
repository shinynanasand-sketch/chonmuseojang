from unittest.mock import patch

from services.recommend import recommend_villages


@patch("services.recommend.get_llm_provider")
def test_recommend_returns_list_of_dicts(mock_get_provider):
    mock_llm = mock_get_provider.return_value
    mock_llm.generate.return_value = (
        '[{"village_id": "V001", "village_name": "예시 갯벌마을", "reason": "가족 단위로 즐기기 좋습니다"}]'
    )
    sample_rows = [{"village_id": "V001", "village_name": "예시 갯벌마을", "program_type": "갯벌체험"}]

    result = recommend_villages("아이와 갈만한 갯벌체험", sample_rows)

    assert isinstance(result, list)
    assert all(isinstance(item, dict) for item in result)


@patch("services.recommend.get_llm_provider")
def test_recommend_result_count_within_limit(mock_get_provider):
    mock_llm = mock_get_provider.return_value
    mock_llm.generate.return_value = "[]"
    sample_rows = [{"village_id": f"V{i}", "village_name": f"마을{i}"} for i in range(10)]

    result = recommend_villages("아무 조건", sample_rows)

    assert len(result) <= 5


@patch("services.recommend.get_llm_provider")
def test_recommend_handles_llm_failure_gracefully(mock_get_provider):
    mock_llm = mock_get_provider.return_value
    mock_llm.generate.side_effect = Exception("LLM 호출 실패")
    sample_rows = [{"village_id": "V001", "village_name": "예시마을"}]

    result = recommend_villages("질문", sample_rows)

    assert result == [] or isinstance(result, list)


def test_recommend_with_empty_village_data_returns_empty():
    result = recommend_villages("아무 질문", [])
    assert result == []


@patch("services.recommend.get_llm_provider")
def test_recommend_uses_keyword_match_when_llm_fails(mock_get_provider):
    mock_llm = mock_get_provider.return_value
    mock_llm.generate.side_effect = Exception("LLM 호출 실패")
    sample_rows = [
        {
            "village_id": "V001",
            "village_name": "예시 갯벌마을",
            "sigungu": "신안군",
            "program_type": "갯벌체험",
        },
        {
            "village_id": "V002",
            "village_name": "예시 무등마을",
            "sigungu": "북구",
            "program_type": "농사체험",
        },
    ]

    result = recommend_villages("아이와 갈만한 갯벌체험", sample_rows)

    assert len(result) == 1
    assert result[0]["village_id"] == "V001"
    assert "갯벌체험" in result[0]["reason"]


@patch("services.recommend.get_llm_provider")
def test_recommend_sends_keyword_matches_beyond_first_slice(mock_get_provider):
    mock_llm = mock_get_provider.return_value
    mock_llm.generate.return_value = (
        '[{"village_id": "PD_DAMYANG", "village_name": "담양죽녹원마을", "reason": "담양 대나무 체험"}]'
    )
    sample_rows = [
        {"village_id": f"P{i:03d}", "village_name": f"마을{i}", "sigungu": "목포시", "program_type": "민박"}
        for i in range(25)
    ]
    sample_rows.append(
        {
            "village_id": "PD_DAMYANG",
            "village_name": "담양죽녹원마을",
            "sigungu": "담양군",
            "program_type": "대나무",
        }
    )

    result = recommend_villages("담양 대나무", sample_rows)

    prompt = mock_llm.generate.call_args[0][1]
    assert "PD_DAMYANG" in prompt
    assert "P000" not in prompt
    assert result[0]["village_id"] == "PD_DAMYANG"


@patch("services.recommend.get_llm_provider")
def test_recommend_drops_village_ids_outside_candidates(mock_get_provider):
    mock_llm = mock_get_provider.return_value
    mock_llm.generate.return_value = (
        '[{"village_id": "UNKNOWN", "village_name": "없는마을", "reason": "없음"}]'
    )
    sample_rows = [
        {
            "village_id": "V001",
            "village_name": "예시 갯벌마을",
            "sigungu": "신안군",
            "program_type": "갯벌체험",
        }
    ]

    result = recommend_villages("갯벌체험", sample_rows)

    assert result
    assert all(item["village_id"] != "UNKNOWN" for item in result)
    assert result[0]["village_id"] == "V001"
