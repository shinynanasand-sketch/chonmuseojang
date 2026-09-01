import pytest
from fastapi.testclient import TestClient

from main import app
from services import booking as booking_service


@pytest.fixture(autouse=True)
def reset_stores():
    booking_service.reset_bookings()
    yield
    booking_service.reset_bookings()


@pytest.fixture
def sample_raw_village_rows_old_names():
    return [
        {"village_id": "V001", "village_name": "예시 갯벌마을", "sido": "전라남도", "sigungu": "신안군"},
        {"village_id": "V002", "village_name": "예시 무등마을", "sido": "광주광역시", "sigungu": "북구"},
        {"village_id": "V003", "village_name": "예시 강원마을", "sido": "강원특별자치도", "sigungu": "춘천시"},
    ]


@pytest.fixture
def sample_raw_village_rows_new_name():
    return [
        {"village_id": "V004", "village_name": "예시 여수마을", "sido": "전남광주통합특별시", "sigungu": "여수시"},
        {"village_id": "V005", "village_name": "예시 제주마을", "sido": "제주특별자치도", "sigungu": "제주시"},
    ]


@pytest.fixture
def sample_village_for_trust_score():
    return {
        "village_id": "V001",
        "grade": "으뜸촌",
        "synced_days_ago": 5,
        "average_rating": 4.5,
    }


@pytest.fixture
def test_client():
    return TestClient(app)


@pytest.fixture
def sample_kakao_booking_payload():
    return {
        "userRequest": {
            "utterance": "9월 20일 3명 예약할게요",
            "user": {"id": "kakao_user_id_test123"},
        },
        "action": {
            "name": "booking_action",
            "params": {"visit_date": "2026-09-20", "num_people": "3"},
        },
    }


@pytest.fixture
def sample_operator_a():
    return {
        "operator_id": 1,
        "village_id": "V001",
        "kakao_user_id": "kakao_owner_v001",
        "login_id": "owner_v001",
        "is_active": True,
    }


@pytest.fixture
def sample_operator_b():
    return {
        "operator_id": 2,
        "village_id": "V002",
        "kakao_user_id": "kakao_owner_v002",
        "login_id": "owner_v002",
        "is_active": True,
    }
