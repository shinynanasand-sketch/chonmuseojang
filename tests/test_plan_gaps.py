"""예약 한 건, 후기 한 건, 신뢰도 저장, 운영자 비밀번호, 개인정보 안내."""

from services.booking import create_booking, update_booking_status
from services.review import register_booking_review
from services.supabase_client import (
    get_operator_by_login_id,
    get_review_for_booking,
    get_village_by_id,
    update_operator_password,
    upsert_villages,
)


def test_approval_changes_only_a_pending_booking():
    saved = create_booking("V001", "status-guest", "2026-11-04", 2)
    confirmed = update_booking_status(saved["booking_id"], "confirmed")
    again = update_booking_status(saved["booking_id"], "rejected")
    assert confirmed["unchanged"] is False
    assert confirmed["status"] == "confirmed"
    assert again["unchanged"] is True
    assert again["status"] == "confirmed"


def test_review_is_once_and_only_for_the_guest():
    upsert_villages(
        [{"village_id": "VREV", "village_name": "후기마을", "sido": "전라남도", "sigungu": "신안군"}]
    )
    booking = create_booking("VREV", "review-guest", "2026-11-05", 3)
    saved = register_booking_review(booking["booking_id"], "review-guest", "좋았다", rating=5)
    other = register_booking_review(booking["booking_id"], "other-guest", "별로", rating=1)
    duplicate = register_booking_review(booking["booking_id"], "review-guest", "또 씀", rating=4)
    assert saved["ok"] is True
    assert other["ok"] is False
    assert "이 예약의 후기만" in other["text"]
    assert duplicate.get("duplicate") is True
    village = get_village_by_id("VREV")
    assert village["average_rating"] == 5
    assert village["trust_score"] == 60


def test_unclear_sentiment_is_not_stored_as_positive():
    booking = create_booking("V001", "tone-guest", "2026-11-06", 2)
    saved = register_booking_review(booking["booking_id"], "tone-guest", "그냥 갔어요", rating=3)
    assert saved["ok"] is True
    assert get_review_for_booking(booking["booking_id"]).get("sentiment") is None


def test_operator_login_uses_password_not_login_id(test_client):
    from services.operator_password import hash_password

    operator = get_operator_by_login_id("owner_v001")
    update_operator_password(int(operator["operator_id"]), hash_password("correct-pass"))
    wrong = test_client.post(
        "/api/operator/login",
        json={"login_id": "owner_v001", "password": "wrong-pass"},
    )
    raw = test_client.get(
        "/api/operator/dashboard",
        headers={"Authorization": "Bearer owner_v001"},
    )
    good = test_client.post(
        "/api/operator/login",
        json={"login_id": "owner_v001", "password": "correct-pass"},
    )
    assert wrong.status_code == 401
    assert raw.status_code == 401
    assert good.status_code == 200
    dashboard = test_client.get(
        "/api/operator/dashboard",
        headers={"Authorization": f"Bearer {good.json()['token']}"},
    )
    assert dashboard.status_code == 200


def test_privacy_page_explains_kakao_id_storage(test_client):
    page = test_client.get("/privacy")
    assert page.status_code == 200
    assert "카카오 사용자 ID" in page.text
    assert "https://pf.kakao.com/_RgZaX" in page.text
    assert "customer_kakao_id" not in page.text
    assert 'href="/privacy"' in test_client.get("/").text
