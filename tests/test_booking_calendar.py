import pytest

from services.auth import register_operator
from services.booking import create_booking
from services.calendar_link import issue_calendar_token
from services.supabase_client import (
    delete_bookings_for_village,
    delete_operator_by_kakao_id,
    get_operator_by_kakao_id,
    set_registration_code,
    upsert_villages,
)

_USERS = ("book_owner_a", "book_owner_b", "book_owner_d", "book_program_a", "book_guest")


def _put_village(village_id: str, name: str, code: str, program_name: str) -> None:
    row = {
        "village_id": village_id,
        "village_name": name,
        "sigungu": "신안군",
        "program_name": program_name,
        "registration_code": code,
    }
    upsert_villages([row])
    set_registration_code(village_id, code, row)


@pytest.fixture
def booking_villages():
    _put_village("VBOOKA", "예약달력마을", "BA-001", "달력예약체험")
    _put_village("VBOOKB", "다른예약마을", "BB-001", "소금체험")
    _put_village("VBOOKC", "같은이름하나", "BC-001", "같은예약체험")
    _put_village("VBOOKD", "같은이름둘", "BD-001", "같은예약체험")
    yield
    for village_id in ("VBOOKA", "VBOOKB", "VBOOKC", "VBOOKD"):
        delete_bookings_for_village(village_id)
    for user_id in _USERS:
        delete_operator_by_kakao_id(user_id)


def _book(utterance: str, village_id: str = "VBOOKB") -> dict:
    return {
        "userRequest": {"utterance": utterance, "user": {"id": "book_guest"}},
        "action": {
            "params": {
                "visit_date": "2026-11-03",
                "num_people": "30",
                "village_id": village_id,
            }
        },
    }


def test_named_program_booking_is_pending_on_that_calendar(test_client, booking_villages):
    register_operator("book_owner_a", "예약달력마을 BA-001")
    response = test_client.post(
        "/kakao/booking",
        json=_book("달력예약체험 2026-11-03 30명", village_id="VBOOKB"),
    )
    assert response.status_code == 200
    assert "대기" in response.text
    assert "번" in response.text

    token = issue_calendar_token(get_operator_by_kakao_id("book_owner_a"))
    bookings = test_client.get(f"/api/calendar/{token}").json()["bookings"]
    matched = [row for row in bookings if row["visit_date"] == "2026-11-03" and row["label"] == "달력예약체험"]
    assert len(matched) == 1
    assert matched[0]["status"] == "pending"
    assert matched[0]["num_people"] == 30
    assert "book_guest" not in response.text

    register_operator("book_owner_b", "다른예약마을 BB-001")
    other = issue_calendar_token(get_operator_by_kakao_id("book_owner_b"))
    hidden = test_client.get(f"/api/calendar/{other}").json()["bookings"]
    assert all(row["label"] != "달력예약체험" for row in hidden)


def test_program_operator_sees_booking_but_cannot_approve(test_client, booking_villages):
    register_operator("book_owner_a", "예약달력마을 BA-001")
    register_operator("book_program_a", "예약달력마을 BA-001 달력예약체험")
    test_client.post("/kakao/booking", json=_book("달력예약체험 2026-11-03 30명"))
    token = issue_calendar_token(get_operator_by_kakao_id("book_program_a"))
    body = test_client.get(f"/api/calendar/{token}").json()
    matched = [row for row in body["bookings"] if row["label"] == "달력예약체험"]
    assert matched
    assert body["can_write"] is False
    decided = test_client.post(
        f"/api/calendar/{token}/bookings/{matched[0]['booking_id']}",
        json={"status": "confirmed", "village_id": "VBOOKB"},
    )
    assert decided.status_code == 403
    again = test_client.get(f"/api/calendar/{token}").json()["bookings"]
    assert next(row for row in again if row["booking_id"] == matched[0]["booking_id"])["status"] == "pending"


def test_village_operator_approves_only_that_booking(test_client, booking_villages, monkeypatch):
    register_operator("book_owner_a", "예약달력마을 BA-001")
    register_operator("book_owner_b", "다른예약마을 BB-001")
    test_client.post("/kakao/booking", json=_book("달력예약체험 2026-11-03 30명"))
    test_client.post(
        "/kakao/booking",
        json={
            "userRequest": {"utterance": "달력예약체험 2026-11-04 12명", "user": {"id": "book_guest"}},
            "action": {"params": {"visit_date": "2026-11-04", "num_people": "12"}},
        },
    )
    other = create_booking("VBOOKB", "book_guest", "2026-11-05", 4)
    told = []
    monkeypatch.setattr(
        "services.calendar_board.notify_booking_decided",
        lambda booking, decision: told.append((booking.get("customer_kakao_id"), decision)),
    )
    token = issue_calendar_token(get_operator_by_kakao_id("book_owner_a"))
    rows = test_client.get(f"/api/calendar/{token}").json()["bookings"]
    target = next(row for row in rows if row["visit_date"] == "2026-11-03")
    kept = next(row for row in rows if row["visit_date"] == "2026-11-04")
    approved = test_client.post(
        f"/api/calendar/{token}/bookings/{target['booking_id']}",
        json={"status": "confirmed"},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "confirmed"
    assert told == [("book_guest", "approve")]
    after = test_client.get(f"/api/calendar/{token}").json()["bookings"]
    assert next(row for row in after if row["booking_id"] == target["booking_id"])["status"] == "confirmed"
    assert next(row for row in after if row["booking_id"] == kept["booking_id"])["status"] == "pending"
    denied = test_client.post(
        f"/api/calendar/{token}/bookings/{other['booking_id']}",
        json={"status": "rejected"},
    )
    assert denied.status_code == 403


def test_same_program_name_needs_a_village_name(test_client, booking_villages):
    response = test_client.post(
        "/kakao/booking",
        json=_book("같은예약체험 2026-12-01 8명"),
    )
    assert "마을 이름" in response.text
    named = test_client.post(
        "/kakao/booking",
        json={
            "userRequest": {
                "utterance": "같은이름둘 같은예약체험 2026-12-01 8명",
                "user": {"id": "book_guest"},
            },
            "action": {"params": {"visit_date": "2026-12-01", "num_people": "8", "village_id": "VBOOKC"}},
        },
    )
    assert "대기" in named.text
    register_operator("book_owner_d", "같은이름둘 BD-001")
    token = issue_calendar_token(get_operator_by_kakao_id("book_owner_d"))
    rows = test_client.get(f"/api/calendar/{token}").json()["bookings"]
    assert any(row["visit_date"] == "2026-12-01" and row["label"] == "같은예약체험" for row in rows)


def test_missing_program_name_does_not_save(test_client, booking_villages):
    response = test_client.post("/kakao/booking", json=_book("2026-11-03 30명"))
    assert "체험 이름" in response.text
    register_operator("book_owner_a", "예약달력마을 BA-001")
    token = issue_calendar_token(get_operator_by_kakao_id("book_owner_a"))
    rows = test_client.get(f"/api/calendar/{token}").json()["bookings"]
    assert all(row["visit_date"] != "2026-11-03" for row in rows)


def test_old_booking_without_program_shows_only_for_village_operator(test_client, booking_villages):
    register_operator("book_owner_a", "예약달력마을 BA-001")
    register_operator("book_program_a", "예약달력마을 BA-001 달력예약체험")
    create_booking("VBOOKA", "book_guest", "2026-11-09", 5)
    owner = issue_calendar_token(get_operator_by_kakao_id("book_owner_a"))
    program = issue_calendar_token(get_operator_by_kakao_id("book_program_a"))
    owner_rows = test_client.get(f"/api/calendar/{owner}").json()["bookings"]
    program_rows = test_client.get(f"/api/calendar/{program}").json()["bookings"]
    assert any(row["label"] == "체험 미정" and row["visit_date"] == "2026-11-09" for row in owner_rows)
    assert all(row["visit_date"] != "2026-11-09" for row in program_rows)
