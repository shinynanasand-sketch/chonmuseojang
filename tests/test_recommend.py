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
