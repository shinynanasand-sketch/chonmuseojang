from unittest.mock import patch

from services.booking import create_booking


@patch("services.llm_provider.get_llm_provider")
def test_review_positive_sentiment_detected(mock_get_provider, test_client):
    mock_llm = mock_get_provider.return_value
    mock_llm.generate.return_value = "긍정"
    booking = create_booking("V001", "c1", "2026-09-20", 2)

    payload = {
        "userRequest": {"utterance": "정말 즐거웠어요! 최고였습니다", "user": {"id": "customer_test"}},
        "action": {"params": {"booking_id": str(booking["booking_id"]), "rating": "5"}},
    }
    response = test_client.post("/kakao/review", json=payload)
    assert response.status_code == 200


@patch("services.llm_provider.get_llm_provider")
def test_review_negative_sentiment_detected(mock_get_provider, test_client):
    mock_llm = mock_get_provider.return_value
    mock_llm.generate.return_value = "부정"

    payload = {
        "userRequest": {"utterance": "별로였고 다시는 안 갈 것 같아요", "user": {"id": "customer_test"}},
        "action": {"params": {"booking_id": "1", "rating": "1"}},
    }
    response = test_client.post("/kakao/review", json=payload)
    assert response.status_code == 200


def test_review_without_photo_still_saves(test_client):
    payload = {
        "userRequest": {"utterance": "좋았어요", "user": {"id": "customer_test"}},
        "action": {"params": {"booking_id": "1", "rating": "4"}},
    }
    response = test_client.post("/kakao/review", json=payload)
    assert response.status_code == 200


def test_review_triggers_trust_score_recalculation(test_client):
    with patch("services.trust_score.recalculate_for_village") as mock_recalc:
        payload = {
            "userRequest": {"utterance": "좋았어요", "user": {"id": "customer_test"}},
            "action": {"params": {"booking_id": "1", "rating": "5"}},
        }
        test_client.post("/kakao/review", json=payload)
        assert mock_recalc.called
