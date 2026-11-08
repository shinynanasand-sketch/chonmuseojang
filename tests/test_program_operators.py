import pytest

from conftest import operator_headers
from services.auth import register_operator, register_operator_with_ids
from services.booking import create_booking, get_booking_by_id, list_bookings_for_operator
from services.program_share import (
    list_calendar,
    list_program_notes,
    save_calendar_entry,
    save_program_note,
)
from services.supabase_client import (
    delete_operator_by_kakao_id,
    get_operator_by_kakao_id,
    insert_operator,
    set_registration_code,
    upsert_villages,
)
from services.village_programs import program_key

_CREATED = (
    "share_owner",
    "shell_owner",
    "salt_owner",
    "other_owner",
    "extra_owner",
    "prog_web",
)


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
def share_villages():
    _put_village("VSHARE", "공유마을", "SH-001", "조개잡이+소금체험")
    _put_village("VOTHER", "다른마을", "OT-001", "농사체험")
    yield
    for user_id in _CREATED:
        delete_operator_by_kakao_id(user_id)


def _skill(name: str, user_id: str, utterance: str, params: dict | None = None) -> dict:
    return {
        "intent": {"name": name},
        "userRequest": {"utterance": utterance, "user": {"id": user_id}},
        "action": {"params": params or {}},
    }


def test_first_registration_is_village_operator(share_villages):
    result = register_operator("share_owner", "등록 공유마을 SH-001")
    assert result == {"ok": True, "village_id": "VSHARE"}
    row = get_operator_by_kakao_id("share_owner")
    assert row["role"] == "village"
    assert not row.get("program_key")


def test_second_user_takes_one_program(share_villages):
    register_operator("share_owner", "등록 공유마을 SH-001")
    result = register_operator("shell_owner", "등록 공유마을 SH-001 조개잡이")
    assert result["ok"] is True
    assert result["role"] == "program"
    row = get_operator_by_kakao_id("shell_owner")
    assert row["village_id"] == "VSHARE"
    assert row["program_key"] == program_key("조개잡이")


def test_program_name_before_village_operator_is_rejected(share_villages):
    result = register_operator("shell_owner", "등록 공유마을 SH-001 조개잡이")
    assert result == {"ok": False, "reason": "village_operator_required"}


def test_second_without_program_asks_for_a_choice(share_villages):
    register_operator("share_owner", "등록 공유마을 SH-001")
    result = register_operator("shell_owner", "등록 공유마을 SH-001")
    assert result == {"ok": False, "reason": "program_choice", "village_id": "VSHARE"}


def test_program_choice_link_registers_that_program(test_client, share_villages):
    register_operator("share_owner", "공유마을 SH-001")
    response = test_client.post(
        "/kakao/ask",
        json=_skill("운영자 등록", "prog_web", "공유마을 SH-001"),
    )
    assert response.status_code == 200
    body = response.json()
    assert "아래 링크에서 맡을 체험을 고르면" in response.text
    assert "체험 이름을 붙여" not in response.text
    button = body["template"]["outputs"][1]["basicCard"]["buttons"][0]
    assert button["label"] == "체험 고르기"
    token = button["webLinkUrl"].rstrip("/").split("/")[-1]
    assert "prog_web" not in token
    page = test_client.get(f"/program/{token}")
    assert page.status_code == 200
    assert "조개잡이" in page.text
    assert "소금체험" in page.text
    saved = test_client.post(f"/program/{token}", data={"program": "조개잡이"})
    assert "조개잡이 체험 담당으로 등록되었습니다." in saved.text
    row = get_operator_by_kakao_id("prog_web")
    assert row["role"] == "program"
    assert row["program_key"] == program_key("조개잡이")
    again = test_client.post(f"/program/{token}", data={"program": "소금체험"})
    assert "이 카카오 계정은 이미 등록되어 있습니다." in again.text


def test_program_choice_link_rejects_a_bad_token(test_client):
    page = test_client.get("/program/not-a-token")
    assert "이 링크는 쓸 수 없습니다." in page.text


def test_same_program_is_taken(share_villages):
    register_operator("share_owner", "등록 공유마을 SH-001")
    register_operator("shell_owner", "등록 공유마을 SH-001 조개잡이")
    result = register_operator("extra_owner", "공유마을 SH-001 조개잡이")
    assert result == {"ok": False, "reason": "program_taken"}


def test_unknown_program_is_rejected(share_villages):
    register_operator("share_owner", "등록 공유마을 SH-001")
    result = register_operator("shell_owner", "등록 공유마을 SH-001 없는체험")
    assert result == {"ok": False, "reason": "program_not_found"}


def test_whole_sentence_in_program_label_registers_that_program(test_client, share_villages):
    register_operator("share_owner", "공유마을 SH-001")
    utterance = "공유마을 SH-001 조개잡이"
    response = test_client.post(
        "/kakao/ask",
        json={
            "intent": {"name": "운영자 등록"},
            "userRequest": {"utterance": utterance, "user": {"id": "shell_owner"}},
            "action": {
                "params": {
                    "village_id": "VSHARE",
                    "registration_code": "SH-001",
                    "program_label": utterance,
                }
            },
        },
    )
    assert response.status_code == 200
    assert "VSHARE 체험 담당으로 등록되었습니다." in response.text
    row = get_operator_by_kakao_id("shell_owner")
    assert row["role"] == "program"
    assert row["program_key"] == program_key("조개잡이")


def test_parenthesis_program_matches_the_code_tail(share_villages):
    _put_village(
        "VDYE",
        "염색마을",
        "DY-001",
        "천연염색(인견이불)+천연염색(사각스카프감+쪽염색)",
    )
    register_operator("share_owner", "염색마을 DY-001")
    utterance = "염색마을 DY-001 천연염색(사각스카프감+쪽염색)"
    result = register_operator_with_ids("shell_owner", "VDYE", "DY-001", utterance, utterance)
    assert result["ok"] is True
    assert result["role"] == "program"
    assert get_operator_by_kakao_id("shell_owner")["program_key"] == program_key(
        "천연염색(사각스카프감+쪽염색)"
    )
    plain = register_operator_with_ids(
        "salt_owner",
        "VDYE",
        "DY-001",
        "천연염색 인견이불",
        "염색마을 DY-001 천연염색 인견이불",
    )
    assert plain["role"] == "program"
    assert get_operator_by_kakao_id("salt_owner")["program_key"] == program_key("천연염색(인견이불)")
    delete_operator_by_kakao_id("shell_owner")
    delete_operator_by_kakao_id("salt_owner")
    delete_operator_by_kakao_id("share_owner")


def test_village_sentence_stays_village_operator_when_name_contains_program():
    _put_village("VSHELL", "조개잡이마을", "JS-001", "조개잡이")
    utterance = "조개잡이마을 JS-001"
    result = register_operator_with_ids("extra_owner", "VSHELL", "JS-001", utterance, utterance)
    assert result == {"ok": True, "village_id": "VSHELL"}
    assert get_operator_by_kakao_id("extra_owner")["role"] == "village"
    delete_operator_by_kakao_id("extra_owner")


def _owners() -> dict:
    register_operator("share_owner", "등록 공유마을 SH-001")
    register_operator("shell_owner", "등록 공유마을 SH-001 조개잡이")
    register_operator("salt_owner", "등록 공유마을 SH-001 소금체험")
    register_operator("other_owner", "등록 다른마을 OT-001")
    return {
        "village": get_operator_by_kakao_id("share_owner"),
        "shell": get_operator_by_kakao_id("shell_owner"),
        "salt": get_operator_by_kakao_id("salt_owner"),
        "other": get_operator_by_kakao_id("other_owner"),
    }


def test_program_operator_cannot_edit_other_note(share_villages):
    owners = _owners()
    assert save_program_note(owners["shell"], "아이들이 조개를 잡습니다.")["ok"] is True
    assert save_program_note(owners["salt"], "다른 글", label="조개잡이") == {
        "ok": False,
        "reason": "forbidden",
    }
    notes = list_program_notes(owners["shell"])["notes"]
    assert [row["body"] for row in notes] == ["아이들이 조개를 잡습니다."]


def test_village_operator_reads_notes_but_does_not_write(share_villages):
    owners = _owners()
    save_program_note(owners["shell"], "조개 안내")
    assert save_program_note(owners["village"], "운영자가 고침") == {
        "ok": False,
        "reason": "read_only",
    }
    bodies = {row["label"]: row["body"] for row in list_program_notes(owners["village"])["notes"]}
    assert bodies == {"조개잡이": "조개 안내"}


def test_program_operator_cannot_write_calendar(share_villages):
    owners = _owners()
    assert save_calendar_entry(owners["shell"], "조개잡이", "2026-11-01", "광주소등학교", 30) == {
        "ok": False,
        "reason": "forbidden",
    }


def test_calendar_groups_belong_to_one_program(share_villages):
    owners = _owners()
    assert save_calendar_entry(owners["village"], "조개잡이", "2026-11-01", "광주소등학교", 30)["ok"] is True
    assert save_calendar_entry(owners["village"], "조개잡이", "2026-11-01", "무안유치원", 20)["ok"] is True
    shell = list_calendar(owners["shell"])["entries"]
    assert [(row["group_name"], row["num_people"]) for row in shell] == [
        ("광주소등학교", 30),
        ("무안유치원", 20),
    ]
    assert list_calendar(owners["salt"])["entries"] == []
    assert list_calendar(owners["other"])["entries"] == []
    village = list_calendar(owners["village"])["entries"]
    assert len(village) == 2


def test_same_group_on_same_day_updates_headcount(share_villages):
    owners = _owners()
    save_calendar_entry(owners["village"], "조개잡이", "2026-11-01", "광주소등학교", 30)
    save_calendar_entry(owners["village"], "조개잡이", "2026-11-01", "광주소등학교", 40)
    rows = list_calendar(owners["shell"])["entries"]
    assert len(rows) == 1
    assert rows[0]["num_people"] == 40


def test_other_village_notes_stay_hidden(share_villages):
    owners = _owners()
    save_program_note(owners["shell"], "공유 마을 글")
    registered = register_operator("extra_owner", "등록 다른마을 OT-001 농사체험")
    assert registered["role"] == "program"
    other_program = get_operator_by_kakao_id("extra_owner")
    save_program_note(other_program, "다른 마을 글")
    home = {row["label"] for row in list_program_notes(owners["shell"])["notes"]}
    away = {row["label"] for row in list_program_notes(other_program)["notes"]}
    assert home == {"조개잡이"}
    assert away == {"농사체험"}


def test_program_operator_cannot_approve_booking(test_client, share_villages):
    register_operator("share_owner", "등록 공유마을 SH-001")
    register_operator("shell_owner", "등록 공유마을 SH-001 조개잡이")
    pending = create_booking("VSHARE", "guest", "2026-11-02", 2)
    response = test_client.post(
        "/kakao/approve",
        json=_skill("예약승인", "shell_owner", "1번 승인", {"booking_id": str(pending["booking_id"])}),
    )
    assert response.status_code == 200
    assert "마을 운영자" in response.text
    assert get_booking_by_id(pending["booking_id"])["status"] == "pending"


def test_list_bookings_rejects_program_operator(share_villages):
    register_operator("share_owner", "등록 공유마을 SH-001")
    register_operator("shell_owner", "등록 공유마을 SH-001 조개잡이")
    with pytest.raises(PermissionError):
        list_bookings_for_operator("shell_owner")


def test_program_operator_web_routes_are_forbidden(test_client):
    insert_operator(
        {
            "kakao_user_id": "prog_web",
            "village_id": "V001",
            "login_id": "prog_web",
            "operator_name": "체험 담당",
            "role": "program",
            "program_key": "abc",
            "is_active": True,
            "registered_at": "2026-10-17T00:00:00+00:00",
        }
    )
    try:
        dashboard = test_client.get(
            "/api/operator/dashboard",
            headers=operator_headers("prog_web"),
        )
        publish = test_client.post(
            "/api/operator/contents/publish",
            headers=operator_headers("prog_web"),
            json={},
        )
        assert dashboard.status_code == 403
        assert publish.status_code == 403
    finally:
        delete_operator_by_kakao_id("prog_web")


def test_kakao_blocks_share_notes_and_calendar(test_client, share_villages):
    register_operator("share_owner", "등록 공유마을 SH-001")
    register_operator("shell_owner", "등록 공유마을 SH-001 조개잡이")
    register_operator("salt_owner", "등록 공유마을 SH-001 소금체험")
    saved = test_client.post(
        "/kakao/ask",
        json=_skill("체험 글 저장", "shell_owner", "체험 글 아이들이 조개를 잡습니다"),
    )
    assert saved.status_code == 200
    assert "저장" in saved.text
    assert "context" not in saved.json()

    denied = test_client.post(
        "/kakao/ask",
        json=_skill("체험 글 저장", "share_owner", "체험 글 운영자 수정"),
    )
    assert "체험 담당" in denied.text

    listed = test_client.post(
        "/kakao/ask",
        json=_skill("체험 글 조회", "share_owner", "체험 글 조회"),
    )
    assert "조개잡이" in listed.text
    assert "아이들이 조개를 잡습니다" in listed.text

    missing = test_client.post(
        "/kakao/ask",
        json=_skill(
            "체험 달력 등록",
            "share_owner",
            "조개잡이 2026-11-01 오전",
            {"program_label": "조개잡이", "visit_date": "2026-11-01", "note": "오전"},
        ),
    )
    assert "체험객" in missing.text
    assert list_calendar(get_operator_by_kakao_id("share_owner"))["entries"] == []

    calendar = test_client.post(
        "/kakao/ask",
        json=_skill(
            "체험 달력 등록",
            "share_owner",
            "조개잡이 2026-11-01 광주소등학교 30명",
            {"program_label": "조개잡이", "visit_date": "2026-11-01"},
        ),
    )
    assert "체험객이 예약 달력에 입력합니다" in calendar.text
    assert list_calendar(get_operator_by_kakao_id("share_owner"))["entries"] == []

    seen = test_client.post(
        "/kakao/ask",
        json=_skill("체험 달력 조회", "shell_owner", "체험 달력 조회"),
    )
    assert "대기 0건 승인 0건 거절 0건" in seen.text
    assert "달력 열기" in seen.text
    assert "광주소등학교" not in seen.text

    hidden = test_client.post(
        "/kakao/ask",
        json=_skill("체험 달력 조회", "salt_owner", "체험 달력 조회"),
    )
    assert "광주소등학교" not in hidden.text

    blocked = test_client.post(
        "/kakao/ask",
        json=_skill(
            "체험 달력 등록",
            "shell_owner",
            "조개잡이 2026-11-02 무안유치원 20명",
            {"program_label": "조개잡이", "visit_date": "2026-11-02"},
        ),
    )
    assert "체험객이 예약 달력에 입력합니다" in blocked.text

    tourist = test_client.post(
        "/kakao/ask",
        json=_skill("체험 달력 조회", "tourist-share", "체험 달력 조회"),
    )
    assert "운영자" in tourist.text


def test_calendar_lookup_counts_only_own_program(test_client, share_villages, monkeypatch):
    from datetime import date

    monkeypatch.setattr("services.booking.seoul_today", lambda: date(2026, 11, 8))
    register_operator("share_owner", "등록 공유마을 SH-001")
    register_operator("shell_owner", "등록 공유마을 SH-001 조개잡이")
    register_operator("salt_owner", "등록 공유마을 SH-001 소금체험")
    create_booking("VSHARE", "guest-shell", "2026-11-03", 4, program_label="조개잡이", visit_time="10:00")
    create_booking("VSHARE", "guest-salt", "2026-11-04", 2, program_label="소금체험", visit_time="11:00")
    create_booking("VSHARE", "guest-later", "2026-12-01", 8, program_label="조개잡이", visit_time="09:00")
    shell = test_client.post("/kakao/ask", json=_skill("체험 달력 조회", "shell_owner", "체험 달력 조회"))
    salt = test_client.post("/kakao/ask", json=_skill("체험 달력 조회", "salt_owner", "체험 달력 조회"))
    assert "2026년 11월 예약 대기 1건 승인 0건 거절 0건" in shell.text
    assert "2026년 11월 예약 대기 1건 승인 0건 거절 0건" in salt.text
    village = test_client.post("/kakao/ask", json=_skill("체험 달력 조회", "share_owner", "체험 달력 조회"))
    assert "2026년 11월 예약 대기 2건 승인 0건 거절 0건" in village.text
