import time

import pytest

from services.auth import register_operator
from services.booking import create_booking, get_booking_by_id
from services.calendar_link import issue_calendar_token, issue_change_token
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


class _EventResponse:
    def __init__(self, payload):
        self.status_code = 200
        self._payload = payload

    def json(self):
        return self._payload


class _EventClient:
    def __init__(self, calls):
        self._calls = calls

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def post(self, url, headers=None, json=None):
        self._calls.append({"url": url, "json": json})
        return _EventResponse({"status": "SUCCESS"})


def _enable_event(monkeypatch):
    calls = []
    monkeypatch.setenv("KAKAO_REST_API_KEY", "test-rest-key")
    monkeypatch.setenv("KAKAO_BOT_ID", "bot-test")
    monkeypatch.setattr(
        "services.kakao_client.httpx.Client",
        lambda *args, **kwargs: _EventClient(calls),
    )
    return calls


def _change_token(link: str) -> str:
    return link.rstrip("/").rsplit("/", 1)[-1]


def _pending_booking():
    register_operator("book_owner_a", "예약달력마을 BA-001")
    saved = create_booking(
        "VBOOKA",
        "book_guest",
        "2026-11-03",
        30,
        program_label="달력예약체험",
        visit_time="10:00",
    )
    token = issue_calendar_token(get_operator_by_kakao_id("book_owner_a"))
    return saved, token


def test_customer_accepts_proposal_and_booking_stays_pending(test_client, booking_villages, monkeypatch):
    saved, token = _pending_booking()
    calls = _enable_event(monkeypatch)
    proposed = test_client.post(
        f"/api/calendar/{token}/bookings/{saved['booking_id']}/proposal",
        json={"visit_date": "2026-11-08", "visit_time": "14:00"},
    )
    assert proposed.status_code == 200
    body = proposed.json()
    assert body["status"] == "pending"
    assert body["visit_date"] == "2026-11-03"
    assert body["proposed_visit_date"] == "2026-11-08"
    assert body["proposed_visit_time"] == "14:00"
    assert "book_guest" not in proposed.text
    offered = next(item for item in calls if item["json"]["event"]["name"] == "booking_change_offered")
    assert offered["json"]["user"] == [{"type": "botUserKey", "id": "book_guest"}]
    assert "2026-11-08 14:00" in offered["json"]["event"]["data"]["message"]
    assert "바꿀 수 있습니다" in offered["json"]["event"]["data"]["message"]
    change_token = _change_token(offered["json"]["event"]["data"]["link"])
    assert "book_guest" not in change_token
    page = test_client.get(f"/change/{change_token}")
    assert page.status_code == 200
    assert 'data-mode="change"' in page.text
    snap = test_client.get(f"/api/change/{change_token}")
    assert snap.status_code == 200
    assert snap.json()["open"] is True
    assert snap.json()["focus_date"] == "2026-11-08"
    assert snap.json()["bookings"][0]["original_visit_date"] == "2026-11-03"
    assert "book_guest" not in snap.text
    mine = test_client.post(
        "/kakao/booking",
        json={
            "intent": {"name": "내 예약"},
            "userRequest": {"utterance": "내 예약", "user": {"id": "book_guest"}},
            "action": {"params": {}},
        },
    )
    assert "변경 제안 2026-11-08 14:00" in mine.text
    accepted = test_client.post(f"/api/change/{change_token}", json={"decision": "accept"})
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "pending"
    assert accepted.json()["visit_date"] == "2026-11-08"
    assert accepted.json()["visit_time"] == "14:00"
    assert accepted.json()["proposed_visit_date"] == ""
    row = get_booking_by_id(saved["booking_id"])
    assert row["status"] == "pending"
    assert str(row["visit_date"]).startswith("2026-11-08")
    assert str(row["visit_time"]).startswith("14:00")
    assert not row.get("proposed_visit_date")
    answered = next(item for item in calls if item["json"]["event"]["name"] == "booking_change_answered")
    assert answered["json"]["user"] == [{"type": "botUserKey", "id": "book_owner_a"}]
    assert "동의했습니다" in answered["json"]["event"]["data"]["message"]
    assert "book_guest" not in str(answered["json"]["user"])
    closed = test_client.get(f"/api/change/{change_token}")
    assert closed.json()["open"] is False
    again = test_client.post(f"/api/change/{change_token}", json={"decision": "accept"})
    assert again.status_code == 400


def test_customer_declines_proposal_and_keeps_original_slot(test_client, booking_villages, monkeypatch):
    saved, token = _pending_booking()
    calls = _enable_event(monkeypatch)
    proposed = test_client.post(
        f"/api/calendar/{token}/bookings/{saved['booking_id']}/proposal",
        json={"visit_date": "2026-11-08", "visit_time": "14:00"},
    )
    change_token = _change_token(proposed.json()["link"])
    declined = test_client.post(f"/api/change/{change_token}", json={"decision": "decline"})
    assert declined.status_code == 200
    assert declined.json()["status"] == "pending"
    assert declined.json()["visit_date"] == "2026-11-03"
    assert declined.json()["visit_time"] == "10:00"
    assert declined.json()["proposed_visit_date"] == ""
    row = get_booking_by_id(saved["booking_id"])
    assert row["status"] == "pending"
    assert str(row["visit_date"]).startswith("2026-11-03")
    answered = next(item for item in calls if item["json"]["event"]["name"] == "booking_change_answered")
    assert "거부했습니다" in answered["json"]["event"]["data"]["message"]
    assert answered["json"]["user"][0]["id"] == "book_owner_a"


def test_new_proposal_closes_the_previous_link(test_client, booking_villages, monkeypatch):
    saved, token = _pending_booking()
    _enable_event(monkeypatch)
    first = test_client.post(
        f"/api/calendar/{token}/bookings/{saved['booking_id']}/proposal",
        json={"visit_date": "2026-11-08", "visit_time": "14:00"},
    )
    first_token = _change_token(first.json()["link"])
    second = test_client.post(
        f"/api/calendar/{token}/bookings/{saved['booking_id']}/proposal",
        json={"visit_date": "2026-11-09", "visit_time": "15:30"},
    )
    assert second.status_code == 200
    assert test_client.get(f"/api/change/{first_token}").json()["open"] is False
    assert test_client.post(f"/api/change/{first_token}", json={"decision": "accept"}).status_code == 400
    second_token = _change_token(second.json()["link"])
    assert test_client.get(f"/api/change/{second_token}").json()["open"] is True
    assert get_booking_by_id(saved["booking_id"])["status"] == "pending"
    assert str(get_booking_by_id(saved["booking_id"])["visit_date"]).startswith("2026-11-03")


def test_expired_change_link_is_rejected(test_client, monkeypatch):
    token = issue_change_token(1, "2026-11-08", "14:00")
    later = time.time() + 20 * 24 * 3600
    monkeypatch.setattr("services.calendar_link.time.time", lambda: later)
    assert test_client.get(f"/api/change/{token}").status_code == 404
    assert test_client.get(f"/change/{token}").status_code == 404


def test_other_village_and_program_operator_cannot_propose(test_client, booking_villages):
    saved, _token = _pending_booking()
    register_operator("book_owner_b", "다른예약마을 BB-001")
    register_operator("book_program_a", "예약달력마을 BA-001 달력예약체험")
    other = issue_calendar_token(get_operator_by_kakao_id("book_owner_b"))
    program = issue_calendar_token(get_operator_by_kakao_id("book_program_a"))
    denied = test_client.post(
        f"/api/calendar/{other}/bookings/{saved['booking_id']}/proposal",
        json={"visit_date": "2026-11-08", "visit_time": "14:00"},
    )
    assert denied.status_code == 403
    staff = test_client.post(
        f"/api/calendar/{program}/bookings/{saved['booking_id']}/proposal",
        json={"visit_date": "2026-11-08", "visit_time": "14:00"},
    )
    assert staff.status_code == 403
    assert not get_booking_by_id(saved["booking_id"]).get("proposed_visit_date")


def test_reject_clears_proposal_and_sends_apology(test_client, booking_villages, monkeypatch):
    saved, token = _pending_booking()
    calls = _enable_event(monkeypatch)
    test_client.post(
        f"/api/calendar/{token}/bookings/{saved['booking_id']}/proposal",
        json={"visit_date": "2026-11-08", "visit_time": "14:00"},
    )
    rejected = test_client.post(
        f"/api/calendar/{token}/bookings/{saved['booking_id']}",
        json={"status": "rejected"},
    )
    assert rejected.status_code == 200
    row = get_booking_by_id(saved["booking_id"])
    assert row["status"] == "rejected"
    assert not row.get("proposed_visit_date")
    decided = next(item for item in calls if item["json"]["event"]["name"] == "booking_decided")
    assert decided["json"]["event"]["data"]["decision"] == "거절"
    assert "2026-11-03 10:00" in decided["json"]["event"]["data"]["message"]
    assert "불편을 드려 죄송합니다" in decided["json"]["event"]["data"]["message"]
    assert decided["json"]["user"][0]["id"] == "book_guest"


def test_proposal_needs_a_pending_booking_and_a_time(test_client, booking_villages):
    saved, token = _pending_booking()
    missing = test_client.post(
        f"/api/calendar/{token}/bookings/{saved['booking_id']}/proposal",
        json={"visit_date": "2026-11-08", "visit_time": ""},
    )
    assert missing.status_code == 400
    confirmed = test_client.post(
        f"/api/calendar/{token}/bookings/{saved['booking_id']}",
        json={"status": "confirmed"},
    )
    assert confirmed.status_code == 200
    late = test_client.post(
        f"/api/calendar/{token}/bookings/{saved['booking_id']}/proposal",
        json={"visit_date": "2026-11-08", "visit_time": "14:00"},
    )
    assert late.status_code == 400
    assert get_booking_by_id(saved["booking_id"])["status"] == "confirmed"


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
