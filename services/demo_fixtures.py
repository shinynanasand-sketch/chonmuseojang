"""V001 시연 예약·후기. 기존 카카오 사용자 ID는 바꾸지 않는다."""

from services.demo_data import DEMO_VILLAGES
from services.supabase_client import (
    get_operator_by_village_id,
    get_village_by_id,
    insert_booking,
    insert_operator,
    insert_review,
    list_bookings,
    list_reviews,
    set_operator_login_id,
    upsert_villages,
)

VILLAGE_ID = "V001"
LOGIN_ID = "owner_v001"
GUEST_ID = "kakao_guest_demo"
GUEST_NAME = "시연 손님"
REVIEW_COMMENT = "시연 후기입니다"
_BOOKING_SPECS = (
    {"visit_date": "2026-12-01", "num_people": 2, "status": "pending"},
    {"visit_date": "2026-12-15", "num_people": 3, "status": "confirmed"},
)


def _same_day(value: object, day: str) -> bool:
    return str(value or "").startswith(day)


def _find_fixture_booking(visit_date: str) -> dict | None:
    for row in list_bookings(village_id=VILLAGE_ID):
        if row.get("customer_kakao_id") == GUEST_ID and _same_day(row.get("visit_date"), visit_date):
            return row
    return None


def _ensure_village() -> None:
    if get_village_by_id(VILLAGE_ID) is None:
        village = next(row for row in DEMO_VILLAGES if row["village_id"] == VILLAGE_ID)
        upsert_villages([village])


def _ensure_operator() -> None:
    operator = get_operator_by_village_id(VILLAGE_ID)
    if operator is None:
        insert_operator(
            {
                "village_id": VILLAGE_ID,
                "kakao_user_id": "kakao_owner_v001",
                "login_id": LOGIN_ID,
                "operator_name": "V001 운영자",
                "is_active": True,
            }
        )
        return
    if operator.get("login_id") != LOGIN_ID:
        set_operator_login_id(VILLAGE_ID, LOGIN_ID)


def _ensure_booking(spec: dict) -> dict:
    existing = _find_fixture_booking(spec["visit_date"])
    if existing:
        return existing
    return insert_booking(
        {
            "village_id": VILLAGE_ID,
            "customer_kakao_id": GUEST_ID,
            "customer_name": GUEST_NAME,
            "visit_date": spec["visit_date"],
            "num_people": spec["num_people"],
            "status": spec["status"],
        }
    )


def _ensure_review(booking_id: int) -> dict:
    for row in list_reviews(village_id=VILLAGE_ID):
        if row.get("booking_id") == booking_id and row.get("comment") == REVIEW_COMMENT:
            return row
    return insert_review(
        {
            "village_id": VILLAGE_ID,
            "booking_id": booking_id,
            "customer_kakao_id": GUEST_ID,
            "rating": 4,
            "comment": REVIEW_COMMENT,
            "sentiment": "긍정",
        }
    )


def load_demo_fixtures() -> dict:
    _ensure_village()
    _ensure_operator()
    pending = _ensure_booking(_BOOKING_SPECS[0])
    confirmed = _ensure_booking(_BOOKING_SPECS[1])
    review = _ensure_review(int(confirmed["booking_id"]))
    return {
        "login_id": LOGIN_ID,
        "pending_booking_id": pending["booking_id"],
        "confirmed_booking_id": confirmed["booking_id"],
        "review_id": review["review_id"],
    }
