"""도선국사마을 가격표는 화면 목록에만 붙이고, 금액 없는 체험은 중지로 저장한다."""

from services.booking import booking_summary, list_my_bookings
from services.calendar_link import issue_calendar_token
from services.field_changes import guide_rows, price_of, won
from services.guest_book import issue_guest_book_link
from services import supabase_client
from services.supabase_client import (
    get_operator_by_kakao_id,
    insert_operator,
    save_program_status,
    upsert_villages,
)
from services.village_programs import program_key, program_labels, programs_for, set_program_operating

_VILLAGE_ID = "PDeac2fe424e02"
_PUBLIC = "감자수확+양파수확+전통손두부만들기"


def _store() -> dict:
    village = {
        "village_id": _VILLAGE_ID,
        "village_name": "도선국사체험마을영농조합법인",
        "sigungu": "광양시",
        "program_name": _PUBLIC,
    }
    upsert_villages([village])
    return village


def _owner() -> None:
    insert_operator(
        {
            "village_id": _VILLAGE_ID,
            "kakao_user_id": "doseon-owner",
            "role": "village",
            "operator_name": "사무장",
            "is_active": True,
        }
    )


def test_extra_programs_follow_public_names_without_replacing_them():
    labels = program_labels({"village_id": _VILLAGE_ID, "program_name": _PUBLIC})
    assert labels[:3] == ["감자수확", "양파수확", "전통손두부만들기"]
    assert labels[-3:] == [
        "천연염색(에코백)",
        "천연염색(크로스백)",
        "천연염색(삼각스카프-일반)",
    ]
    again = program_labels(
        {"village_id": _VILLAGE_ID, "program_name": _PUBLIC + "+천연염색(에코백)"}
    )
    assert again.count("천연염색(에코백)") == 1
    assert program_labels({"village_id": "VOTHER", "program_name": "조개잡이"}) == ["조개잡이"]
    assert price_of("VOTHER", "감자수확") is None


def test_unpriced_programs_start_stopped_and_can_be_reopened(test_client):
    village = _store()
    flags = {item["label"]: item["is_operating"] for item in programs_for(village)}
    assert flags["양파수확"] is False
    assert flags["감자수확"] is True
    assert flags["천연염색(에코백)"] is True
    stored = [row for row in supabase_client._program_status if row["label"] == "양파수확"]
    assert stored[0]["is_operating"] is False

    save_program_status(_VILLAGE_ID, program_key("양파수확"), "양파수확", True)
    stale = next(row for row in supabase_client._program_status if row["label"] == "양파수확")
    stale["updated_at"] = "2026-11-01T00:00:00+00:00"
    flags = {item["label"]: item["is_operating"] for item in programs_for(village)}
    assert flags["양파수확"] is False
    assert next(row for row in supabase_client._program_status if row["label"] == "양파수확")["is_operating"] is False

    set_program_operating(_VILLAGE_ID, "양파수확", True)
    flags = {item["label"]: item["is_operating"] for item in programs_for(village)}
    assert flags["양파수확"] is True


def test_guest_sees_unit_price_and_operator_sees_booking_total(test_client):
    _store()
    _owner()
    url = issue_guest_book_link("price-guest", _VILLAGE_ID)
    token = url.rsplit("/", 1)[-1]
    snapshot = test_client.get(f"/api/book/{token}").json()
    assert "양파수확" not in snapshot["experience_names"]
    assert "천연염색(에코백)" in snapshot["experience_names"]
    assert snapshot["prices"]["감자수확"] == 10000
    assert snapshot["prices"]["천연염색(에코백)"] == 18000
    assert "양파수확" not in snapshot["prices"]

    saved = test_client.post(
        f"/api/book/{token}",
        json={
            "label": "천연염색(에코백)",
            "visit_date": "2026-11-20",
            "visit_time": "10:00",
            "num_people": 2,
            "group_name": "염색반",
        },
    )
    assert saved.status_code == 200
    assert saved.json()["total"] == 36000
    closed = test_client.post(
        f"/api/book/{token}",
        json={"label": "양파수확", "visit_date": "2026-11-20", "visit_time": "11:00", "num_people": 2},
    )
    assert closed.status_code == 400

    own = test_client.get(f"/api/book/{token}").json()["bookings"][0]
    assert own["total"] == 36000
    assert "price" not in own

    operator = issue_calendar_token(get_operator_by_kakao_id("doseon-owner"))
    board = test_client.get(f"/api/calendar/{operator}").json()
    assert "prices" not in board
    assert "18,000" not in " ".join(board["programs"])
    assert "양파수확" not in board["experience_names"]
    matched = [row for row in board["bookings"] if row["label"] == "천연염색(에코백)"]
    assert matched[0]["total"] == 36000
    assert "price" not in matched[0]
    summary = booking_summary(
        {
            "booking_id": matched[0]["booking_id"],
            "status": "pending",
            "visit_date": "2026-11-20",
            "visit_time": "10:00",
            "num_people": 2,
            "village_id": _VILLAGE_ID,
            "program_label": "천연염색(에코백)",
        }
    )
    assert summary == f"{matched[0]['booking_id']}번 대기 2026-11-20 10:00 2명 {won(36000)}"
    plain = booking_summary(
        {
            "booking_id": 1,
            "status": "pending",
            "visit_date": "2026-12-01",
            "visit_time": "10:00",
            "num_people": 4,
            "village_id": "VK-BOARD",
            "program_label": "조개잡이",
        }
    )
    assert plain == "1번 대기 2026-12-01 10:00 4명"


def test_sentence_booking_rejects_stopped_program_and_states_total(test_client):
    _store()
    refused = test_client.post(
        "/kakao/ask",
        json={
            "userRequest": {
                "utterance": "양파수확 2026-11-08 10:00 4명",
                "user": {"id": "sentence-guest"},
            },
            "action": {"params": {}},
        },
    )
    assert "예약할 수 없습니다" in refused.text
    assert list_my_bookings("sentence-guest") == []
    accepted = test_client.post(
        "/kakao/ask",
        json={
            "userRequest": {
                "utterance": "감자수확 2026-11-08 10:00 4명",
                "user": {"id": "sentence-guest"},
            },
            "action": {"params": {}},
        },
    )
    assert "4명 40,000원" in accepted.text
    assert list_my_bookings("sentence-guest")[0]["program_label"] == "감자수확"


def test_guide_table_lists_each_price_and_stop():
    rows = guide_rows()
    prices = [row for row in rows if row["kind"] == "가격"]
    stops = [row for row in rows if row["kind"] == "운영 중지"]
    added = [row for row in rows if row["kind"] == "체험 추가"]
    assert len(prices) == 19
    assert len(stops) == 4
    assert len(added) == 3
    assert all(row["applied"] for row in prices + stops + added)
    assert any(row["kind"] == "공공데이터" and row["applied"] is False for row in rows)
    assert any(row["kind"] == "마을명" and row["applied"] is False for row in rows)
    screens = [row for row in rows if row["village"] == "카카오 사무장"]
    assert [row["kind"] for row in screens] == ["예약 현황", "체험 달력", "오픈빌더"]
    assert screens[0]["applied"] is True
    assert screens[1]["applied"] is True
    assert "일요일부터 토요일" in screens[0]["result"]
    assert "이번 주" in screens[0]["result"]
    assert "이번 주" in screens[2]["result"]
    assert "열린 달만" in screens[1]["result"]
    assert screens[2]["applied"] is False
    calendar_rows = [row for row in rows if row["village"] == "체험 달력"]
    assert [row["kind"] for row in calendar_rows] == ["단체 이름"]
    assert calendar_rows[0]["applied"] is True
    assert "없음을 입력합니다" in calendar_rows[0]["request"]
    assert "없음도 예약으로 남습니다" in calendar_rows[0]["result"]
    assert any("인절미떡메치기" in row["result"] and "15,000원" in row["request"] for row in prices)
