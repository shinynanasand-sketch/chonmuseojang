import pytest

from services.auth import register_operator
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


def test_second_without_program_is_rejected(share_villages):
    register_operator("share_owner", "등록 공유마을 SH-001")
    result = register_operator("shell_owner", "등록 공유마을 SH-001")
    assert result == {"ok": False, "reason": "already_registered"}


def test_same_program_is_taken(share_villages):
    register_operator("share_owner", "등록 공유마을 SH-001")
    register_operator("shell_owner", "등록 공유마을 SH-001 조개잡이")
    result = register_operator("extra_owner", "공유마을 SH-001 조개잡이")
    assert result == {"ok": False, "reason": "program_taken"}


def test_unknown_program_is_rejected(share_villages):
    register_operator("share_owner", "등록 공유마을 SH-001")
    result = register_operator("shell_owner", "등록 공유마을 SH-001 없는체험")
    assert result == {"ok": False, "reason": "program_not_found"}


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
    assert save_calendar_entry(owners["shell"], "조개잡이", "2026-11-01", "오전") == {
        "ok": False,
        "reason": "forbidden",
    }


def test_village_operator_calendar_is_shared_inside_village_only(share_villages):
    owners = _owners()
    assert save_calendar_entry(owners["village"], "조개잡이", "2026-11-01", "오전")["ok"] is True
    home = list_calendar(owners["salt"])["entries"]
    assert home[0]["label"] == "조개잡이"
    assert home[0]["visit_date"] == "2026-11-01"
    assert list_calendar(owners["other"])["entries"] == []


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
            headers={"Authorization": "Bearer prog_web"},
        )
        publish = test_client.post(
            "/api/operator/contents/publish",
            headers={"Authorization": "Bearer prog_web"},
            json={},
        )
        assert dashboard.status_code == 403
        assert publish.status_code == 403
    finally:
        delete_operator_by_kakao_id("prog_web")


def test_kakao_blocks_share_notes_and_calendar(test_client, share_villages):
    register_operator("share_owner", "등록 공유마을 SH-001")
    register_operator("shell_owner", "등록 공유마을 SH-001 조개잡이")
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

    calendar = test_client.post(
        "/kakao/ask",
        json=_skill(
            "체험 달력 등록",
            "share_owner",
            "조개잡이 2026-11-01 오전",
            {"program_label": "조개잡이", "visit_date": "2026-11-01", "note": "오전"},
        ),
    )
    assert "2026-11-01" in calendar.text

    seen = test_client.post(
        "/kakao/ask",
        json=_skill("체험 달력 조회", "shell_owner", "체험 달력 조회"),
    )
    assert "2026-11-01" in seen.text

    blocked = test_client.post(
        "/kakao/ask",
        json=_skill(
            "체험 달력 등록",
            "shell_owner",
            "조개잡이 2026-11-02",
            {"program_label": "조개잡이", "visit_date": "2026-11-02"},
        ),
    )
    assert "마을 운영자" in blocked.text

    tourist = test_client.post(
        "/kakao/ask",
        json=_skill("체험 달력 조회", "tourist-share", "체험 달력 조회"),
    )
    assert "운영자" in tourist.text
