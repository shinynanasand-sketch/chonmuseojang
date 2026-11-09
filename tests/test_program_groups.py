import pytest

from conftest import operator_headers
from services.auth import register_operator
from services.booking import bookings_for_operator_view, create_booking
from services.calendar_link import issue_calendar_token
from services.program_share import list_calendar, save_calendar_entry, save_program_note
from services.supabase_client import (
    delete_operator_by_kakao_id,
    get_operator_by_kakao_id,
    get_program_operator,
    insert_operator,
    list_operator_programs,
    set_operator_login_id,
    set_registration_code,
    upsert_villages,
)
from services.village_programs import program_key


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


def _skill(name: str, user_id: str, utterance: str) -> dict:
    return {
        "intent": {"name": name},
        "userRequest": {"utterance": utterance, "user": {"id": user_id}},
        "action": {"params": {}},
    }


def _office(test_client):
    _put_village("VSHARE", "공유마을", "SH-001", "조개잡이+소금체험")
    _put_village("VOTHER", "다른마을", "OT-001", "농사체험")
    register_operator("share_owner", "등록 공유마을 SH-001")
    register_operator("shell_owner", "등록 공유마을 SH-001 조개잡이")
    register_operator("salt_owner", "등록 공유마을 SH-001 소금체험")
    set_operator_login_id("VSHARE", "share_web")
    return operator_headers("share_web")


@pytest.fixture
def office(test_client):
    headers = _office(test_client)
    yield headers
    for user_id in ("share_owner", "shell_owner", "salt_owner", "other_owner"):
        delete_operator_by_kakao_id(user_id)


def test_office_gives_both_programs_to_one_operator(test_client, office):
    headers = office
    shell = get_operator_by_kakao_id("shell_owner")
    salt = get_operator_by_kakao_id("salt_owner")
    shell_key = program_key("조개잡이")
    salt_key = program_key("소금체험")
    saved = test_client.post(
        "/api/operator/program-groups",
        headers=headers,
        json={
            "assignments": [
                {"program_key": shell_key, "operator_id": shell["operator_id"]},
                {"program_key": salt_key, "operator_id": shell["operator_id"]},
            ]
        },
    )
    assert saved.status_code == 200
    body = saved.json()
    assert body["counts"] == {"programs": 2, "operators": 2, "unassigned": 0}
    assert body["changed"] is False
    assert body["stale"] == []
    assert get_program_operator("VSHARE", salt_key)["operator_id"] == shell["operator_id"]

    create_booking("VSHARE", "guest-shell", "2026-11-03", 4, program_label="조개잡이", visit_time="10:00")
    create_booking("VSHARE", "guest-salt", "2026-11-04", 2, program_label="소금체험", visit_time="11:00")
    shell = get_operator_by_kakao_id("shell_owner")
    salt = get_operator_by_kakao_id("salt_owner")
    assert {row["program_label"] for row in bookings_for_operator_view(shell)} == {"조개잡이", "소금체험"}
    assert bookings_for_operator_view(salt) == []

    assert save_calendar_entry(get_operator_by_kakao_id("share_owner"), "조개잡이", "2026-11-01", "광주소등학교", 30)["ok"]
    assert save_calendar_entry(get_operator_by_kakao_id("share_owner"), "소금체험", "2026-11-02", "무안유치원", 12)["ok"]
    assert {row["label"] for row in list_calendar(shell)["entries"]} == {"조개잡이", "소금체험"}
    assert list_calendar(salt)["entries"] == []

    snapshot = test_client.get(f"/api/calendar/{issue_calendar_token(shell)}").json()
    assert set(snapshot["programs"]) == {"조개잡이", "소금체험"}
    assert {row["label"] for row in snapshot["bookings"]} == {"조개잡이", "소금체험"}


def test_same_program_cannot_be_given_twice(test_client, office):
    headers = office
    shell = get_operator_by_kakao_id("shell_owner")
    salt = get_operator_by_kakao_id("salt_owner")
    key = program_key("조개잡이")
    response = test_client.post(
        "/api/operator/program-groups",
        headers=headers,
        json={
            "assignments": [
                {"program_key": key, "operator_id": shell["operator_id"]},
                {"program_key": key, "operator_id": salt["operator_id"]},
            ]
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "한 체험을 두 명에게 줄 수 없습니다."


def test_other_village_operator_is_rejected(test_client, office):
    headers = office
    other = insert_operator(
        {
            "kakao_user_id": "other_owner",
            "village_id": "VOTHER",
            "role": "program",
            "program_key": program_key("농사체험"),
            "operator_name": "다른 마을 담당",
            "is_active": True,
        }
    )
    response = test_client.post(
        "/api/operator/program-groups",
        headers=headers,
        json={
            "assignments": [
                {"program_key": program_key("조개잡이"), "operator_id": other["operator_id"]},
            ]
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "이 마을 체험 담당만 묶을 수 있습니다."


def test_unknown_program_is_rejected(test_client, office):
    headers = office
    shell = get_operator_by_kakao_id("shell_owner")
    response = test_client.post(
        "/api/operator/program-groups",
        headers=headers,
        json={"assignments": [{"program_key": "없는체험", "operator_id": shell["operator_id"]}]},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "없는 체험입니다."


def test_program_operator_cannot_save_groups(test_client, office):
    shell = get_operator_by_kakao_id("shell_owner")
    shell["login_id"] = "shell_web"
    response = test_client.post(
        "/api/operator/program-groups",
        headers=operator_headers("shell_web"),
        json={"assignments": []},
    )
    assert response.status_code == 403


def test_changed_programs_return_to_the_unassigned_pool(test_client, office):
    headers = office
    shell = get_operator_by_kakao_id("shell_owner")
    shell_key = program_key("조개잡이")
    salt_key = program_key("소금체험")
    test_client.post(
        "/api/operator/program-groups",
        headers=headers,
        json={
            "assignments": [
                {"program_key": shell_key, "operator_id": shell["operator_id"]},
                {"program_key": salt_key, "operator_id": shell["operator_id"]},
            ]
        },
    )
    _put_village("VSHARE", "공유마을", "SH-001", "조개잡이+소금체험+밤줍기")
    opened = test_client.get("/api/operator/program-groups", headers=headers).json()
    assert opened["changed"] is True
    assert opened["counts"]["programs"] == 3
    assert opened["counts"]["unassigned"] == 1
    fresh = next(row for row in opened["programs"] if row["label"] == "밤줍기")
    assert fresh["operator_id"] is None

    _put_village("VSHARE", "공유마을", "SH-001", "조개잡이+밤줍기")
    stale = test_client.get("/api/operator/program-groups", headers=headers).json()
    assert [row["label"] for row in stale["stale"]] == ["소금체험"]
    saved = test_client.post(
        "/api/operator/program-groups",
        headers=headers,
        json={
            "assignments": [
                {"program_key": shell_key, "operator_id": shell["operator_id"]},
                {"program_key": program_key("밤줍기"), "operator_id": shell["operator_id"]},
            ]
        },
    )
    assert saved.status_code == 200
    body = saved.json()
    assert body["stale"] == []
    assert body["counts"]["unassigned"] == 0
    assert [row["program_key"] for row in list_operator_programs("VSHARE")] == [
        shell_key,
        program_key("밤줍기"),
    ]


def test_note_names_the_program_when_one_person_has_several(test_client, office):
    headers = office
    shell = get_operator_by_kakao_id("shell_owner")
    test_client.post(
        "/api/operator/program-groups",
        headers=headers,
        json={
            "assignments": [
                {"program_key": program_key("조개잡이"), "operator_id": shell["operator_id"]},
                {"program_key": program_key("소금체험"), "operator_id": shell["operator_id"]},
            ]
        },
    )
    shell = get_operator_by_kakao_id("shell_owner")
    assert save_program_note(shell, "그냥 글") == {"ok": False, "reason": "which_program"}
    assert save_program_note(shell, "소금체험 소금 안내") == {
        "ok": True,
        "label": "소금체험",
        "body": "소금 안내",
    }
    asked = test_client.post(
        "/kakao/ask",
        json=_skill("체험 글 저장", "shell_owner", "체험 글 저장 그냥 글"),
    )
    assert "어느 체험인지 체험 이름을 앞에 말해 주세요." in asked.text


def test_operator_page_offers_the_group_board(test_client):
    page = test_client.get("/operator").text
    assert "<h2>체험 담당</h2>" in page
    assert "아직 담당 없음" in page
    assert "체험 추가" in page
    assert "빼기" in page
    assert "체험 찾기" in page
    assert "담당 없음" not in page.split("아직 담당 없음", 1)[-1]
    assert "option_label" not in page
    assert "비어 있는 체험으로 카카오에서 담당을 등록한 뒤 여기서 옮기세요." in page
    assert "체험 목록이 바뀌었습니다. 담당을 다시 묶고 저장하세요." in page
    css = test_client.get("/static/css/style.css").text
    assert ".group-board { display: grid; grid-template-columns: minmax(0, 1fr);" in css
    assert ".group-add label" in css
    assert ".group-row select" not in css


def test_group_board_lists_every_program_in_one_village(test_client):
    village_id = "PDeac2fe424e02"
    stored = "도선국사체험마을영농조합법인"
    program_name = (
        "감수확+전통손두부만들기+천연염색(손수건)"
        "+천연염색(사각스카프감+쪽염색)+감자수확"
    )
    _put_village(village_id, stored, "DS-001", program_name)
    assert register_operator("doseon_owner", f"등록 {stored} DS-001")["ok"] is True
    insert_operator(
        {
            "kakao_user_id": "tofu_owner",
            "village_id": village_id,
            "role": "program",
            "program_key": program_key("전통손두부만들기"),
            "operator_name": f"{stored} 전통손두부만들기 담당",
            "is_active": True,
        }
    )
    insert_operator(
        {
            "kakao_user_id": "dye_owner",
            "village_id": village_id,
            "role": "program",
            "program_key": program_key("천연염색(손수건)"),
            "operator_name": "손수건 담당",
            "is_active": True,
        }
    )
    set_operator_login_id(village_id, "doseon_web")
    try:
        opened = test_client.get(
            "/api/operator/program-groups",
            headers=operator_headers("doseon_web"),
        )
        assert opened.status_code == 200
        body = opened.json()
        labels = [row["label"] for row in body["programs"]]
        assert labels == [
            "감수확",
            "전통손두부만들기",
            "천연염색(손수건)",
            "천연염색(사각스카프감+쪽염색)",
            "감자수확",
            "천연염색(에코백)",
            "천연염색(크로스백)",
            "천연염색(삼각스카프-일반)",
        ]
        unassigned = [row["label"] for row in body["programs"] if row["operator_id"] is None]
        assert "감자수확" in unassigned
        assert "천연염색(에코백)" in unassigned
        assert "전통손두부만들기" not in unassigned
        assert body["counts"]["programs"] == len(labels)
        assert body["counts"]["unassigned"] == len(unassigned)
        by_name = {row["operator_name"]: row["option_label"] for row in body["operators"]}
        assert by_name[f"{stored} 전통손두부만들기 담당"] == "전통손두부만들기 담당"
        assert by_name["손수건 담당"] == "손수건 담당"
    finally:
        for user_id in ("doseon_owner", "tofu_owner", "dye_owner"):
            delete_operator_by_kakao_id(user_id)
