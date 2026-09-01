from unittest.mock import patch

import pytest

from services.booking import create_booking


@pytest.fixture
def seeded_booking():
    return create_booking("V001", "customer_test", "2026-09-20", 2)


def test_booking_endpoint_returns_valid_kakao_format(test_client, sample_kakao_booking_payload):
    response = test_client.post("/kakao/booking", json=sample_kakao_booking_payload)

    assert response.status_code == 200
    body = response.json()
    assert body["version"] == "2.0"
    assert "outputs" in body["template"]


def test_booking_endpoint_responds_within_time_limit(test_client, sample_kakao_booking_payload):
    import time

    start = time.time()
    test_client.post("/kakao/booking", json=sample_kakao_booking_payload)
    elapsed = time.time() - start
    assert elapsed < 5.0


def test_booking_missing_required_fields_does_not_crash(test_client):
    incomplete_payload = {
        "userRequest": {"utterance": "예약할게요", "user": {"id": "test"}},
        "action": {"params": {}},
    }
    response = test_client.post("/kakao/booking", json=incomplete_payload)
    assert response.status_code == 200


@patch("services.kakao_client.send_kakao_notification_to_owner")
def test_booking_triggers_owner_notification(mock_notify, test_client, sample_kakao_booking_payload):
    test_client.post("/kakao/booking", json=sample_kakao_booking_payload)
    assert mock_notify.called
