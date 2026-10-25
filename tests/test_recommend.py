from unittest.mock import MagicMock, patch

import httpx
import pytest

from services.llm_provider import LLMUnavailable
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
    assert result[0]["reason"] == "갯벌과 맞습니다. 갯벌체험."


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


_SCENARIO_ROWS = [
    {
        "village_id": "PD_TIDAL",
        "village_name": "증도갯벌마을",
        "sigungu": "신안군",
        "program_type": "갯벌체험",
        "program_name": "조개잡이",
        "facilities": "가족 체험장",
        "grade": "으뜸촌",
        "trust_score": 80,
        "representative_name": "홍길동",
        "phone": "061-000-0000",
        "registration_code": "GB-009",
    },
    {
        "village_id": "PD_BAMBOO",
        "village_name": "죽녹원마을",
        "sigungu": "담양군",
        "program_type": "대나무",
        "program_name": "대나무 공예",
        "facilities": "체험장",
        "trust_score": 70,
    },
    {
        "village_id": "PD_FARM",
        "village_name": "들녘마을",
        "sigungu": "곡성군",
        "program_type": "농사체험",
        "program_name": "모내기",
        "facilities": "민박",
        "trust_score": 60,
    },
    {
        "village_id": "PD_INDOOR",
        "village_name": "실내공예마을",
        "sigungu": "목포시",
        "program_type": "만들기체험",
        "program_name": "도자기",
        "facilities": "실내 체험장",
        "trust_score": 50,
    },
    {
        "village_id": "PD_OTHER",
        "village_name": "산골마을",
        "sigungu": "구례군",
        "program_type": "산악",
        "program_name": "등산",
        "facilities": "주차장",
        "trust_score": 90,
    },
]


@pytest.mark.parametrize(
    ("query", "expected_id", "absent_id"),
    [
        ("아이와 갈만한 갯벌", "PD_TIDAL", "PD_OTHER"),
        ("담양 대나무", "PD_BAMBOO", "PD_OTHER"),
        ("신안 가족", "PD_TIDAL", "PD_OTHER"),
        ("숙박 있는 농촌", "PD_FARM", "PD_OTHER"),
        ("실내 체험", "PD_INDOOR", "PD_OTHER"),
    ],
)
@patch("services.recommend.get_llm_provider")
def test_recommend_natural_language_queries_keep_matching_candidates(
    mock_get_provider, query, expected_id, absent_id
):
    mock_llm = mock_get_provider.return_value
    mock_llm.generate.return_value = (
        f'[{{"village_id": "{expected_id}", "village_name": "맞춤", "reason": "체험이 맞습니다"}}]'
    )

    result = recommend_villages(query, _SCENARIO_ROWS)

    prompt = mock_llm.generate.call_args[0][1]
    assert mock_llm.generate.call_args.kwargs["timeout"] == 8
    assert mock_llm.generate.call_args.kwargs["json_mode"] is True
    assert expected_id in prompt
    assert absent_id not in prompt
    assert "프로그램명" in prompt
    assert "시설" in prompt
    assert "등급" in prompt
    assert "신뢰도" in prompt
    assert "홍길동" not in prompt
    assert "061-000-0000" not in prompt
    assert "GB-009" not in prompt
    assert result[0]["village_id"] == expected_id


@patch("services.recommend.get_llm_provider")
def test_zero_score_query_does_not_send_the_first_slice(mock_get_provider):
    mock_llm = mock_get_provider.return_value
    mock_llm.generate.return_value = "[]"
    sample_rows = [
        {
            "village_id": f"P{i:03d}",
            "village_name": f"마을{i}",
            "sigungu": "목포시",
            "program_type": "민박",
        }
        for i in range(25)
    ]

    recommend_villages("힐링 여행", sample_rows)

    prompt = mock_llm.generate.call_args[0][1]
    present = [row["village_id"] for row in sample_rows if row["village_id"] in prompt]
    assert len(present) == 1


@patch("services.recommend.get_llm_provider")
def test_recommend_accepts_recommendations_object(mock_get_provider):
    mock_llm = mock_get_provider.return_value
    mock_llm.generate.return_value = (
        '{"recommendations":[{"village_id":"V001","village_name":"예시 갯벌마을","reason":"갯벌체험"}]}'
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

    assert result[0]["village_id"] == "V001"


_ROW = {
    "village_id": "V001",
    "village_name": "예시 갯벌마을",
    "sigungu": "신안군",
    "program_type": "갯벌체험",
}
_LLM_JSON = (
    '[{"village_id": "V001", "village_name": "예시 갯벌마을", "reason": "신안군 갯벌체험"}]'
)


def _providers(mock_get, primary, spare):
    def choose(name=None):
        if name == "openai":
            return spare
        return primary

    mock_get.side_effect = choose


def _enable_both(monkeypatch, provider="gemini"):
    monkeypatch.setenv("LLM_PROVIDER", provider)
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-key")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")


@patch("services.recommend.get_llm_provider")
def test_recommend_uses_openai_after_gemini_503(mock_get, monkeypatch):
    _enable_both(monkeypatch)
    clock = {"t": 0.0}
    monkeypatch.setattr("services.recommend._now", lambda: clock["t"])
    gemini = MagicMock()
    openai = MagicMock()
    openai.generate.return_value = _LLM_JSON

    def fail(*_args, **_kwargs):
        clock["t"] = 3.0
        raise LLMUnavailable("503")

    gemini.generate.side_effect = fail
    _providers(mock_get, gemini, openai)

    result = recommend_villages("갯벌체험", [_ROW])

    assert result[0]["reason"] == "갯벌과 맞습니다. 갯벌체험."
    openai.generate.assert_called_once()
    assert openai.generate.call_args.kwargs["timeout"] == 5.0


@patch("services.recommend.get_llm_provider")
def test_recommend_does_not_call_openai_when_gemini_succeeds(mock_get, monkeypatch):
    _enable_both(monkeypatch)
    gemini = MagicMock()
    openai = MagicMock()
    gemini.generate.return_value = _LLM_JSON
    _providers(mock_get, gemini, openai)

    result = recommend_villages("갯벌체험", [_ROW])

    assert result[0]["reason"] == "갯벌과 맞습니다. 갯벌체험."
    openai.generate.assert_not_called()


@patch("services.recommend.get_llm_provider")
def test_recommend_timeout_skips_second_provider(mock_get, monkeypatch):
    _enable_both(monkeypatch)
    gemini = MagicMock()
    openai = MagicMock()
    gemini.generate.side_effect = httpx.TimeoutException("시간 초과")
    _providers(mock_get, gemini, openai)

    result = recommend_villages("갯벌체험", [_ROW])

    openai.generate.assert_not_called()
    assert result[0]["village_id"] == "V001"
    assert result[0]["reason"] == "갯벌과 맞습니다. 갯벌체험."


@patch("services.recommend.get_llm_provider")
def test_recommend_skips_gemini_when_key_is_missing(mock_get, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    openai = MagicMock()
    openai.generate.return_value = _LLM_JSON
    mock_get.return_value = openai

    result = recommend_villages("갯벌체험", [_ROW])

    mock_get.assert_called_once_with("openai")
    assert result[0]["reason"] == "갯벌과 맞습니다. 갯벌체험."


@patch("services.recommend.get_llm_provider")
def test_recommend_uses_keywords_when_both_providers_fail(mock_get, monkeypatch):
    _enable_both(monkeypatch)
    gemini = MagicMock()
    openai = MagicMock()
    gemini.generate.side_effect = LLMUnavailable("503")
    openai.generate.side_effect = LLMUnavailable("503")
    _providers(mock_get, gemini, openai)

    result = recommend_villages("갯벌체험", [_ROW])

    assert result[0]["village_id"] == "V001"
    assert result[0]["reason"] == "갯벌과 맞습니다. 갯벌체험."


@patch("services.recommend.get_llm_provider")
def test_recommend_empty_json_skips_second_provider(mock_get, monkeypatch):
    _enable_both(monkeypatch)
    gemini = MagicMock()
    openai = MagicMock()
    gemini.generate.return_value = "[]"
    _providers(mock_get, gemini, openai)

    result = recommend_villages("갯벌체험", [_ROW])

    openai.generate.assert_not_called()
    assert result[0]["reason"] == "갯벌과 맞습니다. 갯벌체험."


@patch("services.recommend.get_llm_provider")
def test_recommend_tries_openai_when_gemini_json_is_truncated(mock_get, monkeypatch):
    _enable_both(monkeypatch)
    gemini = MagicMock()
    openai = MagicMock()
    gemini.generate.return_value = '{"recommendations":[{"village_id":"V001"'
    openai.generate.return_value = _LLM_JSON
    _providers(mock_get, gemini, openai)

    result = recommend_villages("갯벌체험", [_ROW])

    assert result[0]["reason"] == "갯벌과 맞습니다. 갯벌체험."
    openai.generate.assert_called_once()


@patch("services.recommend.get_llm_provider")
def test_recommend_skips_second_provider_when_time_left_is_short(mock_get, monkeypatch):
    _enable_both(monkeypatch)
    clock = {"t": 0.0}
    monkeypatch.setattr("services.recommend._now", lambda: clock["t"])
    gemini = MagicMock()
    openai = MagicMock()

    def fail(*_args, **_kwargs):
        clock["t"] = 6.5
        raise LLMUnavailable("503")

    gemini.generate.side_effect = fail
    _providers(mock_get, gemini, openai)

    result = recommend_villages("갯벌체험", [_ROW])

    openai.generate.assert_not_called()
    assert result[0]["reason"] == "갯벌과 맞습니다. 갯벌체험."


@patch("services.recommend.get_llm_provider")
def test_openai_primary_falls_back_to_gemini(mock_get, monkeypatch):
    _enable_both(monkeypatch, provider="openai")
    gemini = MagicMock()
    openai = MagicMock()
    openai.generate.side_effect = LLMUnavailable("401")
    gemini.generate.return_value = _LLM_JSON

    def choose(name=None):
        if name == "gemini":
            return gemini
        return openai

    mock_get.side_effect = choose

    result = recommend_villages("갯벌체험", [_ROW])

    assert result[0]["reason"] == "갯벌과 맞습니다. 갯벌체험."
    assert [call.args[0] for call in mock_get.call_args_list] == ["openai", "gemini"]


@patch("services.recommend.get_llm_provider")
def test_claude_recommend_does_not_call_other_providers(mock_get, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "claude")
    monkeypatch.setenv("CLAUDE_API_KEY", "claude-key")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-key")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    claude = MagicMock()
    claude.generate.return_value = _LLM_JSON
    mock_get.return_value = claude

    result = recommend_villages("갯벌체험", [_ROW])

    mock_get.assert_called_once_with("claude")
    assert result[0]["reason"] == "갯벌과 맞습니다. 갯벌체험."


@patch("services.recommend.get_llm_provider")
def test_specific_reason_names_matched_words_and_program(mock_get_provider):
    mock_get_provider.return_value.generate.return_value = (
        '[{"village_id": "PD_TIDAL", "village_name": "증도갯벌마을", "reason": "모델 문장"}]'
    )
    row = {
        "village_id": "PD_TIDAL",
        "village_name": "증도갯벌마을",
        "sigungu": "신안군",
        "program_type": "갯벌체험",
        "program_name": "조개잡이",
        "facilities": "가족 체험장",
        "representative_name": "홍길동",
        "phone": "061-000-0000",
        "registration_code": "GB-009",
    }

    result = recommend_villages("아이와 갈만한 갯벌체험", [row])

    assert result[0]["reason"] == "갯벌·가족과 맞습니다. 조개잡이, 가족 체험장."
    assert "홍길동" not in result[0]["reason"]
    assert "061-000-0000" not in result[0]["reason"]
    assert "GB-009" not in result[0]["reason"]
    assert len(result[0]["reason"]) <= 80


@patch("services.recommend.get_llm_provider")
def test_specific_reason_does_not_invent_a_match(mock_get_provider):
    mock_get_provider.return_value.generate.return_value = (
        '[{"village_id": "PD_BAMBOO", "village_name": "죽녹원마을", "reason": "힐링에 좋습니다"}]'
    )
    row = {
        "village_id": "PD_BAMBOO",
        "village_name": "죽녹원마을",
        "sigungu": "담양군",
        "program_type": "대나무",
        "program_name": "대나무 공예",
        "facilities": "체험장",
    }

    result = recommend_villages("힐링 여행", [row])

    assert result[0]["reason"] == "대나무 공예, 체험장."
    assert "맞습니다" not in result[0]["reason"]


@patch("services.recommend.get_llm_provider")
def test_kakao_recommend_skips_llm_when_under_one_second(mock_get):
    from services.recommend import recommend_for_kakao

    result = recommend_for_kakao("갯벌체험", [_ROW], 0.5)

    mock_get.assert_not_called()
    assert result[0]["village_id"] == "V001"


@patch("services.recommend.get_llm_provider")
def test_kakao_recommend_caps_timeout_at_two_seconds(mock_get):
    from services.recommend import recommend_for_kakao

    mock_get.return_value.generate.return_value = _LLM_JSON
    recommend_for_kakao("갯벌체험", [_ROW], 3.0)
    assert mock_get.return_value.generate.call_args.kwargs["timeout"] == 2.0

    recommend_for_kakao("갯벌체험", [_ROW], 1.4)
    assert mock_get.return_value.generate.call_args.kwargs["timeout"] == 1.4
