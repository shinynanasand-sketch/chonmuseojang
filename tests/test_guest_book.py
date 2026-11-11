from unittest.mock import patch

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
        json={
            "label": "조개잡이",
            "visit_date": "2026-11-02",
            "visit_time": "10:30",
            "num_people": 12,
            "group_name": "  광주  초등학교  ",
        },
    )
    assert saved.status_code == 200
    assert saved.json()["visit_time"] == "10:30"
    assert saved.json()["group_name"] == "광주 초등학교"
    blank = test_client.post(
        f"/api/book/{token}",
        json={"label": "소금체험", "visit_date": "2026-11-02", "visit_time": "11:00", "num_people": 4, "group_name": "  "},
    )
    assert blank.status_code == 400
    assert blank.json()["detail"] == "단체 이름이 없으면 없음을 입력해 주세요."
    operator = issue_calendar_token(get_operator_by_kakao_id("book-owner"))
    rows = test_client.get(f"/api/calendar/{operator}").json()
    assert rows["experience_names"] == ["조개잡이", "소금체험"]
    matched = [row for row in rows["bookings"] if row["label"] == "조개잡이"]
    assert matched[0]["status"] == "pending"
    assert matched[0]["visit_time"] == "10:30"
    assert matched[0]["num_people"] == 12
    assert matched[0]["group_name"] == "광주 초등학교"
    status = test_client.post(
        "/kakao/ask",
        json={
            "userRequest": {"utterance": "예약 현황 2026-11-02", "user": {"id": "book-owner"}},
            "action": {"params": {}},
        },
    )
    assert "광주 초등학교 12명" in status.text
    assert list_my_bookings("book-guest")[0]["booking_id"] == saved.json()["booking_id"]
    create_booking(
        "VBOOK",
        "other-guest",
        "2026-11-03",
        4,
        program_label="소금체험",
        visit_time="09:00",
    )
    again = test_client.get(f"/api/book/{token}").json()
    assert len(again["bookings"]) == 1
    own = again["bookings"][0]
    assert own["booking_id"] == saved.json()["booking_id"]
    assert own["status"] == "pending"
    assert own["status_label"] == "대기"
    assert own["visit_time"] == "10:30"
    assert own["label"] == "조개잡이"
    assert own["group_name"] == "광주 초등학교"
    assert "customer_kakao_id" not in own
    assert "other-guest" not in test_client.get(f"/api/book/{token}").text


def test_guest_booking_rereads_a_hidden_number(test_client, monkeypatch):
    from services.supabase_client import insert_booking

    _village("VHIDE", "숨은번호마을", "조개잡이")
    _owner("VHIDE", "hide-owner")
    token = issue_guest_book_link("hide-guest", "VHIDE").rsplit("/", 1)[-1]

    def hide_number(row):
        saved = dict(insert_booking(row))
        saved.pop("booking_id", None)
        return saved

    monkeypatch.setattr("services.booking.insert_booking", hide_number)
    saved = test_client.post(
        f"/api/book/{token}",
        json={
            "label": "조개잡이",
            "visit_date": "2026-11-12",
            "visit_time": "10:00",
            "num_people": 4,
            "group_name": "없음",
        },
    )
    assert saved.status_code == 200
    assert isinstance(saved.json()["booking_id"], int)
    assert list_my_bookings("hide-guest")[0]["booking_id"] == saved.json()["booking_id"]


def test_guest_booking_does_not_confirm_without_a_number(test_client, monkeypatch):
    _village("VNONEID", "번호없음마을", "조개잡이")
    _owner("VNONEID", "noneid-owner")
    token = issue_guest_book_link("noneid-guest", "VNONEID").rsplit("/", 1)[-1]
    monkeypatch.setattr("services.booking.insert_booking", lambda row: dict(row))
    saved = test_client.post(
        f"/api/book/{token}",
        json={
            "label": "조개잡이",
            "visit_date": "2026-11-12",
            "visit_time": "10:00",
            "num_people": 4,
            "group_name": "없음",
        },
    )
    assert saved.status_code == 400
    assert saved.json()["detail"] == "예약을 접수하지 못했습니다. 다시 눌러 주세요."
    assert list_my_bookings("noneid-guest") == []


def test_guest_can_book_with_no_group_name(test_client):
    _village("VNONE", "없음마을", "조개잡이")
    _owner("VNONE", "none-owner")
    url = issue_guest_book_link("none-guest", "VNONE")
    token = url.rsplit("/", 1)[-1]
    page = test_client.get(f"/book/{token}")
    assert "단체 이름이 없으면 없음을 입력합니다." in page.text
    assert 'placeholder="없으면 없음"' in page.text
    saved = test_client.post(
        f"/api/book/{token}",
        json={
            "label": "조개잡이",
            "visit_date": "2026-11-12",
            "visit_time": "10:30",
            "num_people": 24,
            "group_name": "없음",
        },
    )
    assert saved.status_code == 200
    assert saved.json()["group_name"] == "없음"
    operator = issue_calendar_token(get_operator_by_kakao_id("none-owner"))
    rows = test_client.get(f"/api/calendar/{operator}").json()["bookings"]
    assert rows[0]["group_name"] == "없음"
    status = test_client.post(
        "/kakao/ask",
        json={
            "userRequest": {"utterance": "예약 현황 2026-11-12", "user": {"id": "none-owner"}},
            "action": {"params": {}},
        },
    )
    assert "없음 24명" in status.text


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


def _ask_sentence(utterance: str, user_id: str) -> dict:
    return {
        "userRequest": {"utterance": utterance, "user": {"id": user_id}},
        "action": {"params": {}},
    }


def test_ask_sentence_creates_pending_booking(test_client):
    _village("VASK", "문장마을", "조개잡이")
    response = test_client.post(
        "/kakao/ask",
        json=_ask_sentence("조개잡이 2026-11-01 10:00 30명", "ask-guest"),
    )
    assert response.status_code == 200
    assert "예약이 접수되었습니다" in response.text
    assert "대기로 접수" in response.text
    assert "/book/" in response.text
    rows = list_my_bookings("ask-guest")
    assert rows[0]["status"] == "pending"
    assert rows[0]["visit_time"] == "10:00"
    assert rows[0]["num_people"] == 30
    assert rows[0]["program_label"] == "조개잡이"


def test_repeat_sentence_keeps_one_booking_and_can_change_headcount(test_client):
    _village("VONCE", "한번마을", "조개잡이")
    first = test_client.post(
        "/kakao/ask",
        json=_ask_sentence("조개잡이 2026-11-01 10:00 30명", "once-guest"),
    )
    second = test_client.post(
        "/kakao/ask",
        json=_ask_sentence("조개잡이 2026-11-01 10:00 30명", "once-guest"),
    )
    changed = test_client.post(
        "/kakao/ask",
        json=_ask_sentence("조개잡이 2026-11-01 10:00 40명", "once-guest"),
    )
    assert "이미 접수된 예약" in second.text
    assert "인원을 40명으로 고쳤습니다" in changed.text
    rows = list_my_bookings("once-guest")
    assert len(rows) == 1
    assert rows[0]["num_people"] == 40
    assert f"예약번호 {rows[0]['booking_id']}번" in first.text


def test_rejected_booking_allows_a_new_row(test_client):
    from services.booking import update_booking_status

    _village("VAGAIN", "다시마을", "조개잡이")
    test_client.post(
        "/kakao/ask",
        json=_ask_sentence("조개잡이 2026-11-03 10:00 12명", "again-guest"),
    )
    first = list_my_bookings("again-guest")[0]
    update_booking_status(first["booking_id"], "rejected")
    response = test_client.post(
        "/kakao/ask",
        json=_ask_sentence("조개잡이 2026-11-03 10:00 12명", "again-guest"),
    )
    assert "예약이 접수되었습니다" in response.text
    rows = list_my_bookings("again-guest")
    assert len(rows) == 2
    assert {row["status"] for row in rows} == {"rejected", "pending"}


def test_ask_question_stays_a_recommendation(test_client):
    _village("VREC", "갯벌마을", "소금체험")
    with (
        patch(
            "services.kakao_ask.recommend_for_kakao",
            return_value=[{"village_id": "VREC", "village_name": "갯벌마을", "reason": "갯벌"}],
        ),
        patch(
            "services.kakao_ask.get_nearby_for_village",
            return_value={"status": "unavailable", "attractions": [], "restaurants": []},
        ),
    ):
        response = test_client.post(
            "/kakao/ask",
            json=_ask_sentence("아이와 갈 갯벌", "ask-question"),
        )
    assert response.status_code == 200
    assert "추천" in response.text
    assert "갯벌마을" in response.text
    assert "예약이 접수" not in response.text
    assert list_my_bookings("ask-question") == []


def test_ask_same_program_in_two_villages_asks_for_a_name(test_client):
    _village("VA", "가마을", "조개잡이")
    _village("VB", "나마을", "조개잡이")
    response = test_client.post(
        "/kakao/ask",
        json=_ask_sentence("조개잡이 2026-11-01 10:00 30명", "amb-guest"),
    )
    assert "여러 마을" in response.text
    assert list_my_bookings("amb-guest") == []


def test_operator_ask_does_not_take_a_guest_booking(test_client):
    _village("VOP", "운영마을", "조개잡이")
    _owner("VOP", "op-kakao")
    with patch(
        "services.kakao_ask.get_nearby_for_village",
        return_value={"status": "unavailable", "attractions": [], "restaurants": []},
    ):
        response = test_client.post(
            "/kakao/ask",
            json=_ask_sentence("조개잡이 2026-11-01 10:00 30명", "op-kakao"),
        )
    assert "운영마을" in response.text
    assert "예약이 접수" not in response.text
    assert list_my_bookings("op-kakao") == []
