from unittest.mock import patch

import pytest

import json

from services.booking import create_booking, get_booking_by_id
from services.review import list_reviews_for_village
from services.supabase_client import insert_review, upsert_villages


@pytest.fixture
def booking_for_approve():
    return create_booking("V001", "customer_test", "2026-09-20", 2)


def test_approve_updates_booking_status(test_client, booking_for_approve):
    """예약승인 블록이면 예약 상태가 confirmed로 변경되어야 한다. decision은 없다"""
    payload = {
        "intent": {"name": "예약승인"},
        "userRequest": {"utterance": "7번 승인", "user": {"id": "owner_test"}},
        "action": {"params": {"booking_id": str(booking_for_approve["booking_id"])}},
    }
    response = test_client.post("/kakao/approve", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert "outputs" in body["template"]
    assert "context" not in body
    assert "승인" in response.text
    assert get_booking_by_id(booking_for_approve["booking_id"])["status"] == "confirmed"


def test_reject_updates_booking_status(test_client, booking_for_approve):
    """예약거절 블록이면 예약 상태가 rejected로 변경되어야 한다. decision은 없다"""
    payload = {
        "intent": {"name": "예약거절"},
        "userRequest": {"utterance": "7번 거절", "user": {"id": "owner_test"}},
        "action": {"params": {"booking_id": str(booking_for_approve["booking_id"])}},
    }
    response = test_client.post("/kakao/approve", json=payload)
    assert response.status_code == 200
    assert "context" not in response.json()
    assert "거절" in response.text
    assert get_booking_by_id(booking_for_approve["booking_id"])["status"] == "rejected"


@patch("services.kakao_client.send_kakao_notification_to_customer")
def test_approve_does_not_push_customer(mock_notify, test_client, booking_for_approve):
    payload = {
        "intent": {"name": "예약승인"},
        "userRequest": {"utterance": "7번 승인", "user": {"id": "owner_test"}},
        "action": {"params": {"booking_id": str(booking_for_approve["booking_id"])}},
    }
    test_client.post("/kakao/approve", json=payload)
    assert mock_notify.called is False


def test_approve_with_nonexistent_booking_id_does_not_crash(test_client, booking_for_approve):
    payload = {
        "intent": {"name": "예약승인"},
        "userRequest": {"utterance": "999999번 승인", "user": {"id": "owner_test"}},
        "action": {"params": {"booking_id": "999999"}},
    }
    response = test_client.post("/kakao/approve", json=payload)
    assert response.status_code == 200
    assert "예약을 찾을 수 없습니다" in response.text
    assert "context" not in response.json()
    assert get_booking_by_id(booking_for_approve["booking_id"])["status"] == "pending"


def test_reject_with_nonexistent_booking_id_leaves_pending(test_client, booking_for_approve):
    payload = {
        "intent": {"name": "예약거절"},
        "userRequest": {"utterance": "999999번 거절", "user": {"id": "owner_test"}},
        "action": {"params": {"booking_id": "999999"}},
    }
    response = test_client.post("/kakao/approve", json=payload)
    assert response.status_code == 200
    assert "예약을 찾을 수 없습니다" in response.text
    assert "context" not in response.json()
    assert get_booking_by_id(booking_for_approve["booking_id"])["status"] == "pending"


@patch("services.auth.get_operator_by_kakao_id")
@patch("services.booking.get_booking_by_id")
def test_approve_rejects_cross_village_booking(mock_get_booking, mock_get_operator, test_client, sample_operator_a):
    mock_get_operator.return_value = sample_operator_a
    mock_get_booking.return_value = {"booking_id": 99, "village_id": "V002", "status": "pending"}

    payload = {
        "intent": {"name": "예약승인"},
        "userRequest": {"utterance": "99번 승인", "user": {"id": "kakao_owner_v001"}},
        "action": {"params": {"booking_id": "99"}},
    }
    with patch("services.booking.update_booking_status") as mock_update:
        response = test_client.post("/kakao/approve", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert "outputs" in body["template"]
    assert "권한" in response.text
    assert "context" not in body
    assert mock_update.called is False


@patch("services.auth.get_operator_by_kakao_id")
def test_approve_rejects_unregistered_operator(mock_get_operator, test_client):
    mock_get_operator.return_value = None
    payload = {
        "intent": {"name": "예약승인"},
        "userRequest": {"utterance": "7번 승인", "user": {"id": "unknown_kakao_user"}},
        "action": {"params": {"booking_id": "7"}},
    }
    response = test_client.post("/kakao/approve", json=payload)
    assert response.status_code == 200
    assert "등록" in response.text
    assert "context" not in response.json()


@patch("services.booking.update_booking_status")
def test_approve_without_booking_id_returns_guidance_and_stops(mock_update, test_client):
    """booking_id가 없으면 승인 안내만 반환하고 상태를 바꾸지 않는다"""
    payload = {
        "intent": {"name": "예약승인"},
        "userRequest": {"utterance": "승인할게요", "user": {"id": "owner_test"}},
        "action": {
            "params": {},
            "detailParams": {"booking_id": {"origin": "7번"}},
        },
    }
    response = test_client.post("/kakao/approve", json=payload)
    assert response.status_code == 200
    assert "몇 번 예약을 승인하시겠어요? 예시: 7번 승인" in response.text
    assert "context" not in response.json()
    assert mock_update.called is False


def test_reject_without_booking_id_returns_guidance_and_stops(test_client, booking_for_approve):
    """booking_id가 없으면 거절 안내만 반환하고 상태를 바꾸지 않는다"""
    payload = {
        "intent": {"name": "예약거절"},
        "userRequest": {"utterance": "거절할게요", "user": {"id": "owner_test"}},
        "action": {
            "params": {},
            "detailParams": {"booking_id": {"origin": "7번"}},
        },
    }
    response = test_client.post("/kakao/approve", json=payload)
    assert response.status_code == 200
    assert "몇 번 예약을 거절하시겠어요? 예시: 7번 거절" in response.text
    assert "context" not in response.json()
    assert get_booking_by_id(booking_for_approve["booking_id"])["status"] == "pending"


def test_approve_other_village_booking_stays_pending(test_client, booking_for_approve):
    other = create_booking("V002", "customer_test", "2026-09-21", 1)
    payload = {
        "intent": {"name": "예약승인"},
        "userRequest": {"utterance": "승인", "user": {"id": "owner_test"}},
        "action": {"params": {"booking_id": str(other["booking_id"])}},
    }
    response = test_client.post("/kakao/approve", json=payload)
    assert response.status_code == 200
    assert "권한" in response.text
    assert "context" not in response.json()
    assert get_booking_by_id(other["booking_id"])["status"] == "pending"
    assert get_booking_by_id(booking_for_approve["booking_id"])["status"] == "pending"


def test_reject_other_village_booking_stays_pending(test_client, booking_for_approve):
    other = create_booking("V002", "customer_test", "2026-09-21", 1)
    payload = {
        "intent": {"name": "예약거절"},
        "userRequest": {"utterance": "거절", "user": {"id": "owner_test"}},
        "action": {"params": {"booking_id": str(other["booking_id"])}},
    }
    response = test_client.post("/kakao/approve", json=payload)
    assert response.status_code == 200
    assert "권한" in response.text
    assert "context" not in response.json()
    assert get_booking_by_id(other["booking_id"])["status"] == "pending"
    assert get_booking_by_id(booking_for_approve["booking_id"])["status"] == "pending"


def test_approve_reads_sys_number_json_not_origin(test_client, booking_for_approve):
    booking_id = booking_for_approve["booking_id"]
    payload = {
        "intent": {"name": "예약승인"},
        "userRequest": {"utterance": "7번 승인", "user": {"id": "owner_test"}},
        "action": {
            "params": {"booking_id": json.dumps({"amount": booking_id, "unit": "번"})},
            "detailParams": {"booking_id": {"origin": "99번"}},
        },
    }
    response = test_client.post("/kakao/approve", json=payload)
    assert response.status_code == 200
    assert "context" not in response.json()
    assert get_booking_by_id(booking_id)["status"] == "confirmed"


def test_recommend_success_uses_list_card(test_client):
    """마을 추천 성공 응답은 listCard다. 엔티티는 없다"""
    upsert_villages(
        [
            {
                "village_id": "V009",
                "village_name": "갯벌체험마을",
                "sigungu": "신안군",
                "program_type": "갯벌체험",
            }
        ]
    )
    payload = {
        "intent": {"name": "마을 추천"},
        "userRequest": {"utterance": "아이와 갈 갯벌", "user": {"id": "guest"}},
        "action": {"params": {}},
    }
    body = test_client.post("/kakao/ask", json=payload).json()
    assert "listCard" in body["template"]["outputs"][0]
    assert "context" not in body


def test_review_lookup_uses_village_id_and_list_card(test_client):
    """후기 조회는 village_id로 그 마을 후기를 listCard로 안내한다"""
    insert_review(
        {
            "village_id": "V001",
            "booking_id": 1,
            "customer_kakao_id": "guest",
            "comment": "아이들이 좋아했어요",
            "rating": 5,
        }
    )
    payload = {
        "intent": {"name": "후기 조회"},
        "userRequest": {"utterance": "예시 갯벌마을 후기", "user": {"id": "guest"}},
        "action": {"params": {"village_id": "V001"}},
    }
    body = test_client.post("/kakao/ask", json=payload).json()
    card = body["template"]["outputs"][0]["listCard"]
    assert card["items"][0]["title"] == "별점 5"
    assert "context" not in body


def test_review_lookup_on_review_route_does_not_save(test_client):
    payload = {
        "intent": {"name": "후기 조회"},
        "userRequest": {"utterance": "정말 즐거웠어요", "user": {"id": "guest"}},
        "action": {"params": {"village_id": "V001", "rating": "5"}},
    }
    response = test_client.post("/kakao/review", json=payload)
    assert response.status_code == 200
    assert list_reviews_for_village("V001") == []


def test_booking_status_uses_list_card(test_client):
    """예약 현황 성공 응답은 listCard다. start_date와 end_date는 없다"""
    create_booking("V001", "customer_test", "2026-11-01", 4)
    payload = {
        "intent": {"name": "예약 현황 조회"},
        "userRequest": {"utterance": "예약 현황", "user": {"id": "owner_test"}},
        "action": {"params": {}},
    }
    body = test_client.post("/kakao/booking", json=payload).json()
    assert "listCard" in body["template"]["outputs"][0]
    assert "start_date" not in payload["action"]["params"]
    assert "context" not in body


def test_operator_register_block_uses_representative_values(test_client):
    from services.supabase_client import detach_operators_for_village, set_registration_code

    detach_operators_for_village("V008")
    upsert_villages(
        [{"village_id": "V008", "village_name": "예시 갯벌마을", "sigungu": "신안군"}]
    )
    set_registration_code("V008", "GB-001")
    payload = {
        "intent": {"name": "운영자등록"},
        "userRequest": {"utterance": "예시 갯벌마을 GB-001", "user": {"id": "fresh_owner"}},
        "action": {
            "params": {"village_id": "V008", "registration_code": "GB-001"},
            "detailParams": {
                "village_id": {"origin": "예시 갯벌마을", "value": "V008"},
                "registration_code": {"origin": "GB-001", "value": "GB-001"},
            },
        },
    }
    response = test_client.post("/kakao/booking", json=payload)
    assert response.status_code == 200
    assert "등록 완료" in response.text
    assert "context" not in response.json()
