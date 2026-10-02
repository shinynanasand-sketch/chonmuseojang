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
    assert "simpleText" in body["template"]["outputs"][0]
    text = body["template"]["outputs"][0]["simpleText"]["text"]
    assert text
    assert "\n" not in text


def test_booking_endpoint_responds_within_time_limit(test_client, sample_kakao_booking_payload):
    import time

    start = time.time()
    test_client.post("/kakao/booking", json=sample_kakao_booking_payload)
    elapsed = time.time() - start
    assert elapsed < 5.0


def test_unregistered_status_utterance_prompts_registration(test_client):
    payload = {
        "userRequest": {"utterance": "예약 현황", "user": {"id": "unknown_kakao_user"}},
        "action": {"params": {}},
    }
    response = test_client.post("/kakao/booking", json=payload)
    assert response.status_code == 200
    assert "등록" in response.text


def test_tourist_my_booking_does_not_prompt_registration(test_client):
    payload = {
        "userRequest": {"utterance": "내 예약", "user": {"id": "customer_flow_test"}},
        "action": {"params": {}},
    }
    response = test_client.post("/kakao/booking", json=payload)
    assert response.status_code == 200
    assert "등록 [" not in response.text


def test_booking_missing_required_fields_does_not_crash(test_client):
    incomplete_payload = {
        "userRequest": {"utterance": "예약할게요", "user": {"id": "test"}},
        "action": {"params": {}},
    }
    response = test_client.post("/kakao/booking", json=incomplete_payload)
    assert response.status_code == 200


@patch("services.kakao_client.send_kakao_notification_to_owner")
def test_booking_does_not_push_owner_notification(mock_notify, test_client, sample_kakao_booking_payload):
    response = test_client.post("/kakao/booking", json=sample_kakao_booking_payload)
    assert mock_notify.called is False
    text = response.json()["template"]["outputs"][0]["simpleText"]["text"]
    assert "알려드릴게요" not in text
    assert "내 예약" in text


def test_booking_accepts_full_kakao_payload(test_client):
    """오픈빌더가 보내는 실 payload(null/extra 필드)도 200 + simpleText."""
    payload = {
        "intent": {"id": "intent1", "name": "예약"},
        "userRequest": {
            "timezone": "Asia/Seoul",
            "params": {"ignoreMe": "true"},
            "block": {"id": "block1", "name": "예약"},
            "utterance": "예약",
            "lang": None,
            "user": {"id": "kakao_user_full", "type": "botUserKey"},
        },
        "bot": {"id": "bot1", "name": "체험마을AI사무장"},
        "action": {
            "name": "예약",
            "clientExtra": None,
            "params": {"visit_date": "2026-09-30", "num_people": "2"},
            "detailParams": {
                "visit_date": {"origin": "9월 30일", "value": "2026-09-30"},
                "num_people": {"origin": "2명", "value": "2"},
            },
        },
    }
    response = test_client.post("/kakao/booking", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["version"] == "2.0"
    assert "simpleText" in body["template"]["outputs"][0]
    assert body["template"]["outputs"][0]["simpleText"]["text"]


def test_booking_null_user_request_still_skill_format(test_client):
    response = test_client.post(
        "/kakao/booking",
        json={"userRequest": None, "action": None},
    )
    assert response.status_code == 200
    body = response.json()
    assert "simpleText" in body["template"]["outputs"][0]


def test_booking_empty_body_still_skill_format(test_client):
    response = test_client.post("/kakao/booking", json={})
    assert response.status_code == 200
    body = response.json()
    assert body["version"] == "2.0"
    assert "simpleText" in body["template"]["outputs"][0]


def test_booking_invalid_num_people_returns_skill_error(test_client):
    payload = {
        "userRequest": {"utterance": "예약", "user": {"id": "t"}},
        "action": {"params": {"visit_date": "2026-09-30", "num_people": "두명"}},
    }
    response = test_client.post("/kakao/booking", json=payload)
    assert response.status_code == 200
    text = response.json()["template"]["outputs"][0]["simpleText"]["text"]
    assert "인원수" in text
    assert "\n" not in text


def test_ping_returns_docs_simple_text(test_client):
    response = test_client.post("/kakao/ping", json={})
    assert response.status_code == 200
    assert "charset=utf-8" in response.headers.get("content-type", "")
    body = response.json()
    assert body == {
        "version": "2.0",
        "template": {"outputs": [{"simpleText": {"text": "스킬 연결 OK"}}]},
    }


def test_booking_openbuilder_exact_payload_numeric_num_people(test_client):
    """오픈빌더 스킬 테스트에서 복사한 실 payload (num_people은 number)."""
    payload = {
        "intent": {"id": "9kap24yhdblpya9n0qe4lbrg", "name": "블록 이름"},
        "userRequest": {
            "timezone": "Asia/Seoul",
            "params": {"ignoreMe": "true"},
            "block": {"id": "9kap24yhdblpya9n0qe4lbrg", "name": "블록 이름"},
            "utterance": "발화 내용",
            "lang": None,
            "user": {"id": "536285", "type": "accountId", "properties": {}},
        },
        "bot": {"id": "6aad4321707aa28d466ccfaf", "name": "봇 이름"},
        "action": {
            "name": "3uq4ole7qy",
            "clientExtra": None,
            "params": {"visit_date": "2026-09-30", "num_people": 2},
            "id": "9aea15uifaop2fmeu8aljjpq",
            "detailParams": {
                "visit_date": {
                    "origin": "2026-09-30",
                    "value": "2026-09-30",
                    "groupName": "",
                },
                "num_people": {"origin": 2, "value": 2, "groupName": ""},
            },
        },
    }
    response = test_client.post("/kakao/booking", json=payload)
    assert response.status_code == 200
    text = response.json()["template"]["outputs"][0]["simpleText"]["text"]
    assert "예약" in text
    assert "\n" not in text
