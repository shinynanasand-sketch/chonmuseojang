from unittest.mock import patch

import pytest

from services.booking import create_booking


@pytest.fixture
def booking_for_approve():
    return create_booking("V001", "customer_test", "2026-09-20", 2)


def test_approve_updates_booking_status(test_client, booking_for_approve):
    payload = {
        "userRequest": {"utterance": "승인", "user": {"id": "owner_test"}},
        "action": {"params": {"booking_id": str(booking_for_approve["booking_id"]), "decision": "approve"}},
    }
    response = test_client.post("/kakao/approve", json=payload)
    assert response.status_code == 200
    assert "outputs" in response.json()["template"]


def test_reject_updates_booking_status(test_client, booking_for_approve):
    payload = {
        "userRequest": {"utterance": "거절", "user": {"id": "owner_test"}},
        "action": {"params": {"booking_id": str(booking_for_approve["booking_id"]), "decision": "reject"}},
    }
    response = test_client.post("/kakao/approve", json=payload)
    assert response.status_code == 200


@patch("services.kakao_client.send_kakao_notification_to_customer")
def test_approve_notifies_customer(mock_notify, test_client, booking_for_approve):
    payload = {
        "userRequest": {"utterance": "승인", "user": {"id": "owner_test"}},
        "action": {"params": {"booking_id": str(booking_for_approve["booking_id"]), "decision": "approve"}},
    }
    test_client.post("/kakao/approve", json=payload)
    assert mock_notify.called


def test_approve_with_nonexistent_booking_id_does_not_crash(test_client):
    payload = {
        "userRequest": {"utterance": "승인", "user": {"id": "owner_test"}},
        "action": {"params": {"booking_id": "999999", "decision": "approve"}},
    }
    response = test_client.post("/kakao/approve", json=payload)
    assert response.status_code == 200


@patch("services.auth.get_operator_by_kakao_id")
@patch("services.booking.get_booking_by_id")
def test_approve_rejects_cross_village_booking(mock_get_booking, mock_get_operator, test_client, sample_operator_a):
    mock_get_operator.return_value = sample_operator_a
    mock_get_booking.return_value = {"booking_id": 99, "village_id": "V002", "status": "pending"}

    payload = {
        "userRequest": {"utterance": "승인", "user": {"id": "kakao_owner_v001"}},
        "action": {"params": {"booking_id": "99", "decision": "approve"}},
    }
    response = test_client.post("/kakao/approve", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert "outputs" in body["template"]


@patch("services.auth.get_operator_by_kakao_id")
def test_approve_rejects_unregistered_operator(mock_get_operator, test_client):
    mock_get_operator.return_value = None
    payload = {
        "userRequest": {"utterance": "승인", "user": {"id": "unknown_kakao_user"}},
        "action": {"params": {"booking_id": "1", "decision": "approve"}},
    }
    response = test_client.post("/kakao/approve", json=payload)
    assert response.status_code == 200
