from services.auth import register_operator
from services.booking import create_booking
from services.supabase_client import (
    get_village_by_id,
    get_village_operator,
    insert_content,
    list_calendar_for_village,
    insert_review,
    list_bookings,
    list_contents,
    list_program_notes_for_village,
    list_reviews,
    set_registration_code,
    upsert_program_note,
    upsert_villages,
)
from services.supabase_client import upsert_calendar_entry

_PASSWORD = "dev-admin-secret"
_CODE = "DX-1001"
_OWNER = "dev-owner-marker"
_GUEST = "dev-guest-marker"


def _put_village() -> None:
    row = {
        "village_id": "VDEV",
        "village_name": "개발초기마을",
        "sigungu": "신안군",
        "program_name": "개발체험",
        "registration_code": _CODE,
    }
    other = {
        "village_id": "VOTHER",
        "village_name": "다른개발마을",
        "sigungu": "담양군",
        "program_name": "다른체험",
        "registration_code": "DX-2002",
    }
    upsert_villages([row, other])
    set_registration_code("VDEV", _CODE, row)
    set_registration_code("VOTHER", "DX-2002", other)
    register_operator(_OWNER, "개발초기마을 DX-1001")
    register_operator("other-owner-marker", "다른개발마을 DX-2002")
    create_booking("VDEV", _GUEST, "2026-11-02", 2)
    insert_review(
        {
            "village_id": "VDEV",
            "customer_kakao_id": _GUEST,
            "rating": 5,
            "body": "개발후기",
        }
    )
    insert_content(
        {
            "village_id": "VDEV",
            "content_type": "소개글",
            "body": "개발소개",
            "is_public": False,
        }
    )
    upsert_program_note(
        {
            "village_id": "VDEV",
            "program_key": "dev-note",
            "label": "개발체험",
            "body": "개발글",
        }
    )
    upsert_calendar_entry(
        {
            "village_id": "VDEV",
            "program_key": "dev-note",
            "label": "개발체험",
            "visit_date": "2026-11-02",
            "group_name": "개발단체",
            "num_people": 2,
        }
    )


def test_dev_page_hides_records_until_password(test_client, monkeypatch):
    monkeypatch.setenv("DEV_ADMIN_PASSWORD", _PASSWORD)
    _put_village()
    locked = test_client.get("/guide/dev")
    assert locked.status_code == 200
    assert "이 화면은 테스트용입니다." in locked.text
    assert "개발초기마을" not in locked.text
    assert _OWNER not in locked.text
    assert _GUEST not in locked.text
    assert _CODE not in locked.text

    wrong = test_client.post("/guide/dev", data={"password": "nope"})
    assert "비밀번호가 맞지 않습니다." in wrong.text
    assert get_village_operator("VDEV") is not None

    blocked = test_client.post(
        "/guide/dev/reset",
        data={"village_id": "VDEV", "kind": "operators"},
    )
    assert blocked.status_code == 403
    assert get_village_operator("VDEV") is not None

    opened = test_client.post("/guide/dev", data={"password": _PASSWORD})
    assert "개발초기마을" in opened.text
    assert _OWNER not in opened.text
    assert "마을 운영자와 체험 담당 지우기" in opened.text
    assert "예약 지우기" in opened.text
    assert "후기 지우기" in opened.text
    assert "체험 달력 지우기" in opened.text
    assert "체험 글 지우기" in opened.text
    assert "소개글·SNS 지우기" in opened.text

    cleared_owner = test_client.post(
        "/guide/dev/reset",
        data={"village_id": "VDEV", "kind": "operators"},
    )
    assert cleared_owner.status_code == 200
    assert get_village_operator("VDEV") is None
    assert get_village_operator("VOTHER") is not None
    assert get_village_by_id("VDEV")["registration_code"] == _CODE

    cleared_booking = test_client.post(
        "/guide/dev/reset",
        data={"village_id": "VDEV", "kind": "bookings"},
    )
    assert cleared_booking.status_code == 200
    assert list_bookings(village_id="VDEV") == []
    assert get_village_by_id("VDEV")["registration_code"] == _CODE

    test_client.post("/guide/dev/reset", data={"village_id": "VDEV", "kind": "reviews"})
    test_client.post("/guide/dev/reset", data={"village_id": "VDEV", "kind": "calendar"})
    test_client.post("/guide/dev/reset", data={"village_id": "VDEV", "kind": "notes"})
    test_client.post("/guide/dev/reset", data={"village_id": "VDEV", "kind": "contents"})
    assert list_reviews(village_id="VDEV") == []
    assert list_program_notes_for_village("VDEV") == []
    assert list_contents(village_id="VDEV") == []
    assert list_calendar_for_village("VDEV") == []


def test_clearing_operators_keeps_linked_records(test_client, monkeypatch):
    monkeypatch.setenv("DEV_ADMIN_PASSWORD", _PASSWORD)
    _put_village()
    owner = get_village_operator("VDEV")
    operator_id = owner["operator_id"]
    insert_content(
        {
            "village_id": "VDEV",
            "operator_id": operator_id,
            "content_type": "소개글",
            "body": "연결된소개",
            "is_public": False,
        }
    )
    upsert_program_note(
        {
            "village_id": "VDEV",
            "program_key": "dev-note",
            "label": "개발체험",
            "body": "연결된글",
            "updated_by": operator_id,
        }
    )
    upsert_calendar_entry(
        {
            "village_id": "VDEV",
            "program_key": "dev-note",
            "label": "개발체험",
            "visit_date": "2026-11-02",
            "group_name": "개발단체",
            "num_people": 2,
            "created_by": operator_id,
        }
    )

    test_client.post("/guide/dev", data={"password": _PASSWORD})
    cleared = test_client.post(
        "/guide/dev/reset",
        data={"village_id": "VDEV", "kind": "operators"},
    )

    assert cleared.status_code == 200
    assert "마을 운영자와 체험 담당을 지웠습니다." in cleared.text
    assert get_village_operator("VDEV") is None
    assert get_village_by_id("VDEV")["registration_code"] == _CODE
    contents = list_contents(village_id="VDEV")
    assert any(row.get("body") == "연결된소개" for row in contents)
    assert all(row.get("operator_id") is None for row in contents)
    notes = list_program_notes_for_village("VDEV")
    assert notes[0]["body"] == "연결된글"
    assert notes[0]["updated_by"] is None
    calendar = list_calendar_for_village("VDEV")
    assert calendar[0]["group_name"] == "개발단체"
    assert calendar[0]["created_by"] is None
