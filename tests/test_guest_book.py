from services.booking import create_booking, list_my_bookings
from services.calendar_link import issue_calendar_token
from services.guest_book import issue_guest_book_link
from services.kakao_params import parse_spoken_time, parse_sys_time
from services.supabase_client import (
    get_operator_by_kakao_id,
    insert_guest_book_link,
    insert_operator,
    upsert_villages,
)
from services.village_programs import set_program_operating


def _owner(village_id: str, kakao_id: str) -> None:
    insert_operator(
        {
            "village_id": village_id,
            "kakao_user_id": kakao_id,
            "role": "village",
            "operator_name": "운영자",
            "is_active": True,
        }
    )


def _ask(utterance: str, user_id: str = "guest-book") -> dict:
    return {
        "intent": {"name": "예약하기"},
        "userRequest": {"utterance": utterance, "user": {"id": user_id}},
        "action": {"params": {}},
    }


def _village(village_id: str, name: str, program_name: str) -> None:
    upsert_villages(
        [
            {
                "village_id": village_id,
                "village_name": name,
                "sigungu": "광양시",
                "program_name": program_name,
            }
        ]
    )


def test_spoken_time_reads_clock_and_korean_hour():
    assert parse_spoken_time("조개잡이 2026-11-01 10:00 30명") == "10:00"
    assert parse_spoken_time("조개잡이 2026-11-01 오전 10시 30명") == "10:00"
    assert parse_spoken_time("조개잡이 2026-11-01 오후 3시 30분 12명") == "15:30"
    assert parse_spoken_time("조개잡이 2026-11-01 30명") == ""
    assert parse_sys_time("10:00:00") == "10:00"
    assert parse_sys_time({"time": "09:05:00"}) == "09:05"


def test_booking_sentence_keeps_time_when_spoken(test_client):
    _village("VTIME", "시간마을", "조개잡이")
    response = test_client.post(
        "/kakao/booking",
        json={
            "userRequest": {
                "utterance": "조개잡이 2026-11-01 10:00 30명",
                "user": {"id": "time-guest"},
            },
            "action": {"params": {"visit_date": "2026-11-01", "num_people": "30"}},
        },
    )
    assert response.status_code == 200
    rows = list_my_bookings("time-guest")
    assert rows[0]["visit_time"] == "10:00"
    mine = test_client.post(
        "/kakao/booking",
        json={
            "intent": {"name": "내 예약"},
            "userRequest": {"utterance": "내 예약", "user": {"id": "time-guest"}},
            "action": {"params": {}},
        },
    )
    assert "2026-11-01 10:00" in mine.text


def test_one_village_booking_button_opens_calendar_without_saving(test_client):
    _village("VLINK", "달력마을", "조개잡이+소금체험")
    _owner("VLINK", "link-owner")
    before = list_my_bookings("link-guest")
    response = test_client.post("/kakao/ask", json=_ask("예약하기", "link-guest"))
    assert response.status_code == 200
    body = response.json()
    card = body["template"]["outputs"][1]["basicCard"]
    assert card["buttons"][0]["label"] == "달력으로 예약"
    assert "/book/" in card["buttons"][0]["webLinkUrl"]
    assert "link-guest" not in response.text
    assert list_my_bookings("link-guest") == before


def test_several_villages_wait_for_a_name(test_client):
    _village("VONE", "하나마을", "조개잡이")
    _village("VTWO", "둘마을", "소금체험")
    _owner("VONE", "one-owner")
    _owner("VTWO", "two-owner")
    listed = test_client.post("/kakao/ask", json=_ask("예약하기", "multi-guest"))
    assert "/book/" not in listed.text
    assert "하나마을" in listed.text
    assert "둘마을" in listed.text
    chosen = test_client.post("/kakao/ask", json=_ask("예약하기 둘마을", "multi-guest"))
    assert "/book/" in chosen.text
    assert "둘마을" in chosen.text


def test_guest_calendar_saves_pending_booking_on_operator_calendar(test_client):
    _village("VBOOK", "예약마을", "조개잡이+소금체험")
    _owner("VBOOK", "book-owner")
    url = issue_guest_book_link("book-guest", "VBOOK")
    token = url.rsplit("/", 1)[-1]
    page = test_client.get(f"/book/{token}")
    assert page.status_code == 200
    assert 'data-mode="guest"' in page.text
    assert "guest-form" in page.text
    snapshot = test_client.get(f"/api/book/{token}").json()
    assert snapshot["experience_names"] == ["조개잡이", "소금체험"]
    assert snapshot["bookings"] == []
    assert "customer_kakao_id" not in snapshot
    saved = test_client.post(
        f"/api/book/{token}",
        json={"label": "조개잡이", "visit_date": "2026-11-02", "visit_time": "10:30", "num_people": 12},
    )
    assert saved.status_code == 200
    assert saved.json()["visit_time"] == "10:30"
    operator = issue_calendar_token(get_operator_by_kakao_id("book-owner"))
    rows = test_client.get(f"/api/calendar/{operator}").json()
    assert rows["experience_names"] == ["조개잡이", "소금체험"]
    matched = [row for row in rows["bookings"] if row["label"] == "조개잡이"]
    assert matched[0]["status"] == "pending"
    assert matched[0]["visit_time"] == "10:30"
    assert matched[0]["num_people"] == 12
    assert list_my_bookings("book-guest")[0]["booking_id"] == saved.json()["booking_id"]


def test_guest_token_cannot_approve_or_edit_calendar(test_client):
    _village("VLOCK", "잠금마을", "조개잡이")
    _owner("VLOCK", "lock-owner")
    create_booking("VLOCK", "someone", "2026-11-02", 4, program_label="조개잡이")
    token = issue_guest_book_link("lock-guest", "VLOCK").rsplit("/", 1)[-1]
    assert test_client.post(
        f"/api/calendar/{token}",
        json={"label": "조개잡이", "visit_date": "2026-11-02", "group_name": "학교", "num_people": 10},
    ).status_code == 404
    assert test_client.post(f"/api/calendar/{token}/bookings/1", json={"status": "confirmed"}).status_code == 404
    assert test_client.request(
        "DELETE",
        f"/api/calendar/{token}",
        json={"label": "조개잡이", "visit_date": "2026-11-02", "group_name": "학교"},
    ).status_code == 404


def test_guest_calendar_rejects_closed_and_other_programs(test_client):
    _village("VCLOSE", "닫힘마을", "조개잡이")
    _village("VOTHER", "옆마을", "소금체험")
    set_program_operating("VCLOSE", "조개잡이", False)
    token = issue_guest_book_link("close-guest", "VCLOSE").rsplit("/", 1)[-1]
    assert test_client.get(f"/api/book/{token}").json()["experience_names"] == []
    closed = test_client.post(
        f"/api/book/{token}",
        json={"label": "조개잡이", "visit_date": "2026-11-02", "visit_time": "10:00", "num_people": 4},
    )
    other = test_client.post(
        f"/api/book/{token}",
        json={"label": "소금체험", "visit_date": "2026-11-02", "visit_time": "10:00", "num_people": 4},
    )
    assert closed.status_code == 400
    assert other.status_code == 400
    assert list_my_bookings("close-guest") == []


def test_expired_guest_link_is_not_found(test_client):
    _village("VOLD", "지난마을", "조개잡이")
    insert_guest_book_link(
        {
            "token": "expired-token",
            "village_id": "VOLD",
            "customer_kakao_id": "old-guest",
            "expires_at": "2020-01-01T00:00:00+00:00",
        }
    )
    assert test_client.get("/book/expired-token").status_code == 404
    assert test_client.get("/api/book/expired-token").status_code == 404
