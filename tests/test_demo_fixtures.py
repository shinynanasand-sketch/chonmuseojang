"""V001 시연 목업은 카카오 ID를 유지하고 예약·후기를 중복 삽입하지 않는다."""

from services.demo_fixtures import load_demo_fixtures
from services.supabase_client import get_operator_by_village_id, list_bookings, list_reviews


def test_demo_fixtures_keep_kakao_id_and_do_not_duplicate():
    operator = get_operator_by_village_id("V001")
    original_kakao = operator["kakao_user_id"]
    original_login = operator["login_id"]
    operator["kakao_user_id"] = "206405"
    operator["login_id"] = None
    try:
        first = load_demo_fixtures()
        second = load_demo_fixtures()
        saved = get_operator_by_village_id("V001")
        assert saved["kakao_user_id"] == "206405"
        assert saved["login_id"] == "owner_v001"
        assert first["pending_booking_id"] == second["pending_booking_id"]
        assert first["confirmed_booking_id"] == second["confirmed_booking_id"]
        assert first["review_id"] == second["review_id"]

        bookings = list_bookings(village_id="V001")
        assert len([row for row in bookings if row.get("customer_kakao_id") == "kakao_guest_demo"]) == 2
        pending = next(row for row in bookings if row["booking_id"] == first["pending_booking_id"])
        confirmed = next(row for row in bookings if row["booking_id"] == first["confirmed_booking_id"])
        assert pending["status"] == "pending"
        assert str(pending["visit_date"]).startswith("2026-12-01")
        assert pending["num_people"] == 2
        assert pending["customer_name"] == "시연 손님"
        assert confirmed["status"] == "confirmed"
        assert str(confirmed["visit_date"]).startswith("2026-12-15")
        assert confirmed["num_people"] == 3

        reviews = list_reviews(village_id="V001")
        assert len(reviews) == 1
        assert reviews[0]["review_id"] == first["review_id"]
        assert reviews[0]["booking_id"] == first["confirmed_booking_id"]
        assert reviews[0]["rating"] == 4
        assert reviews[0]["comment"] == "시연 후기입니다"
    finally:
        operator["kakao_user_id"] = original_kakao
        operator["login_id"] = original_login
