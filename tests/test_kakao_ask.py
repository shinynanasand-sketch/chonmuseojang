from unittest.mock import patch

VILLAGES = [
    {
        "village_id": "PD_MUD",
        "village_name": "무등마을",
        "sigungu": "북구",
        "program_type": "농사체험",
    },
    {
        "village_id": "PD_TIDAL",
        "village_name": "갯벌마을",
        "sigungu": "신안군",
        "program_type": "갯벌체험",
    },
]


def _skill_text(response) -> str:
    return response.json()["template"]["outputs"][0]["simpleText"]["text"]


def test_tourist_ask_recommends_and_adds_nearby(test_client):
    nearby = {
        "status": "success",
        "attractions": [{"title": "장보고대교"}],
        "restaurants": [{"title": "완도식당"}],
    }
    with (
        patch("services.kakao_ask.get_operator_by_kakao_id", return_value=None),
        patch("services.kakao_ask.list_public_villages", return_value=VILLAGES),
        patch("services.kakao_ask.get_nearby_for_village", return_value=nearby) as mock_nearby,
    ):
        response = test_client.post(
            "/kakao/ask",
            json={
                "userRequest": {"utterance": "아이와 갈만한 갯벌체험", "user": {"id": "tourist-1"}},
                "action": {"params": {}},
            },
        )

    assert response.status_code == 200
    text = _skill_text(response)
    assert "\n" not in text
    assert "갯벌마을" in text
    assert "장보고대교" in text
    assert "무등마을" not in text
    mock_nearby.assert_called_once_with("PD_TIDAL")


def test_operator_ask_stays_on_own_village(test_client):
    nearby = {
        "status": "success",
        "attractions": [{"title": "자은선착장"}],
        "restaurants": [],
    }
    with (
        patch(
            "services.kakao_ask.get_operator_by_kakao_id",
            return_value={"village_id": "V001", "kakao_user_id": "206405"},
        ),
        patch(
            "services.kakao_ask.get_village_by_id",
            return_value={"village_id": "V001", "village_name": "예시 갯벌마을", "sigungu": "신안군"},
        ),
        patch("services.kakao_ask.get_nearby_for_village", return_value=nearby) as mock_nearby,
        patch("services.kakao_ask.keyword_recommendations") as mock_recommend,
    ):
        response = test_client.post(
            "/kakao/ask",
            json={
                "userRequest": {
                    "utterance": "무등마을 추천해줘",
                    "user": {"id": "206405"},
                },
                "action": {"params": {}},
            },
        )

    assert response.status_code == 200
    text = _skill_text(response)
    assert "예시 갯벌마을" in text
    assert "자은선착장" in text
    assert "무등마을" not in text
    mock_nearby.assert_called_once_with("V001")
    mock_recommend.assert_not_called()


def test_empty_tourist_question_and_nearby_failure_stay_skill_json(test_client):
    empty = test_client.post(
        "/kakao/ask",
        json={"userRequest": {"utterance": "  ", "user": {"id": "tourist-2"}}, "action": {"params": {}}},
    )
    assert empty.status_code == 200
    assert "질문해 주세요" in _skill_text(empty)

    with (
        patch("services.kakao_ask.get_operator_by_kakao_id", return_value=None),
        patch("services.kakao_ask.list_public_villages", return_value=VILLAGES),
        patch(
            "services.kakao_ask.get_nearby_for_village",
            return_value={"status": "unavailable", "attractions": [], "restaurants": []},
        ),
    ):
        failed = test_client.post(
            "/kakao/ask",
            json={
                "userRequest": {"utterance": "갯벌체험", "user": {"id": "tourist-3"}},
                "action": {"params": {}},
            },
        )
    assert failed.status_code == 200
    text = _skill_text(failed)
    assert "갯벌마을" in text
    assert "불러오지 못했습니다" in text
    assert "\n" not in text


def test_long_recommendation_simpletext_stays_within_1000(test_client):
    long_name = "갯벌마을" * 80
    nearby = {
        "status": "success",
        "attractions": [{"title": "관광지" * 120}] * 3,
        "restaurants": [{"title": "음식점" * 120}] * 2,
    }
    villages = [
        {
            "village_id": "PD_LONG",
            "village_name": long_name,
            "sigungu": "신안군",
            "program_type": "갯벌체험",
        }
    ]
    with (
        patch("services.kakao_ask.get_operator_by_kakao_id", return_value=None),
        patch("services.kakao_ask.list_public_villages", return_value=villages),
        patch("services.kakao_ask.get_nearby_for_village", return_value=nearby),
    ):
        response = test_client.post(
            "/kakao/ask",
            json={
                "userRequest": {"utterance": "갯벌체험", "user": {"id": "tourist-long"}},
                "action": {"params": {}},
            },
        )

    assert response.status_code == 200
    text = _skill_text(response)
    assert text.startswith("추천.")
    assert "\n" not in text
    assert 1 <= len(text) <= 1000
