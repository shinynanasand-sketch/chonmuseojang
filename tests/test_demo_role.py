"""발표 모드 시연 역할. 저장된 사무장 등록은 그대로 둔다."""

from urllib.parse import urlparse

import pytest

from services.booking import create_booking, get_booking_by_id
from services.demo_data import DEMO_STAFF_NAME
from services.demo_role import reset_demo_roles, role_page_url, set_demo_persona
from services.program_groups import program_group_snapshot, save_program_groups
from services.supabase_client import get_operator_by_kakao_id, upsert_villages
from services.village_programs import program_key, program_labels, set_program_operating


@pytest.fixture(autouse=True)
def _clear_demo_roles():
    reset_demo_roles()
    yield
    reset_demo_roles()


def _ask(user_id: str, name: str, utterance: str) -> dict:
    return {
        "intent": {"name": name},
        "userRequest": {"utterance": utterance, "user": {"id": user_id}},
        "action": {"params": {}},
    }


def _labels(response) -> list[str]:
    replies = response.json()["template"].get("quickReplies") or []
    return [item["label"] for item in replies]


def test_flat_village_gains_two_demo_programs():
    labels = program_labels({"village_id": "V001", "program_type": "갯벌체험"})
    assert labels == ["갯벌체험", "소금체험", "조개잡이"]


def test_named_program_list_is_left_alone():
    labels = program_labels(
        {"village_id": "V001", "program_name": "자연생태체험+기타(영농체험+먹거리체험)"}
    )
    assert labels == ["자연생태체험", "기타(영농체험+먹거리체험)"]


def test_role_switch_changes_buttons_without_replacing_the_operator(test_client):
    owner = get_operator_by_kakao_id("kakao_owner_v001")
    assert owner["role"] == "village"
    assert set_demo_persona("kakao_owner_v001", "guest") is True
    guest = test_client.post(
        "/kakao/ask",
        json=_ask("kakao_owner_v001", "예약 현황 조회", "예약 현황 조회"),
    )
    assert _labels(guest)[:4] == ["마을 추천", "예약하기", "내 예약", "후기 보기"]
    assert "2026" not in guest.text

    assert set_demo_persona("kakao_owner_v001", "program") is True
    staff = test_client.post(
        "/kakao/ask",
        json=_ask("kakao_owner_v001", "체험 달력 조회", "체험 달력 조회"),
    )
    assert "예약 현황 조회" not in _labels(staff)
    assert "홍보 사진" not in _labels(staff)
    assert "달력 열기" in staff.text
    outputs = staff.json()["template"]["outputs"]
    link = ""
    for output in outputs:
        card = output.get("basicCard")
        if not card:
            continue
        for button in card["buttons"]:
            if button.get("label") == "달력 열기":
                link = button["webLinkUrl"]
    staff_row = get_operator_by_kakao_id("kakao_demo_staff_v001")
    assert staff_row is not None
    assert link.split("/calendar/")[1].split(".")[0] == str(staff_row["operator_id"])
    assert get_operator_by_kakao_id("kakao_owner_v001")["role"] == "village"

    assert set_demo_persona("kakao_owner_v001", "village") is True
    manager = test_client.post(
        "/kakao/ask",
        json=_ask("kakao_owner_v001", "예약 현황 조회", "예약 현황 조회"),
    )
    assert _labels(manager)[0] == "이전 주" or _labels(manager)[0] == "예약 현황 조회"


def _role_card(response) -> dict:
    for output in response.json()["template"]["outputs"]:
        card = output.get("basicCard") or {}
        if card.get("title") == "시연 역할":
            return card
    return {}


def test_chosen_manager_my_bookings_keeps_manager_buttons(test_client):
    assert set_demo_persona("kakao_owner_v001", "village") is True
    response = test_client.post(
        "/kakao/ask",
        json=_ask("kakao_owner_v001", "내 예약", "내 예약"),
    )
    assert "사무장으로 바꿨습니다. 예약 현황, 달력, 홍보 사진을 씁니다." in response.text
    assert "내 예약" not in response.text
    assert _labels(response)[:4] == ["예약 현황 조회", "체험 달력 조회", "체험 글 조회", "홍보 사진"]
    assert _role_card(response)["description"] == "지금 역할은 사무장입니다."


def test_chosen_guest_status_names_the_current_role(test_client):
    assert set_demo_persona("kakao_owner_v001", "guest") is True
    response = test_client.post(
        "/kakao/ask",
        json=_ask("kakao_owner_v001", "예약 현황 조회", "예약 현황 조회"),
    )
    assert "지금은 체험객입니다. 예약하기와 내 예약을 씁니다." in response.text
    assert "운영자는 등록" not in response.text
    assert _labels(response)[:4] == ["마을 추천", "예약하기", "내 예약", "후기 보기"]
    assert _role_card(response)["description"] == "지금 역할은 체험객입니다."


def test_demo_staff_can_take_several_programs_and_one_can_stop():
    upsert_villages(
        [
            {
                "village_id": "V001",
                "village_name": "예시 갯벌마을",
                "sigungu": "신안군",
                "program_type": "갯벌체험",
            }
        ]
    )
    snapshot = program_group_snapshot("V001")
    assert [row["label"] for row in snapshot["programs"]] == ["갯벌체험", "소금체험", "조개잡이"]
    staff = next(row for row in snapshot["operators"] if row["operator_name"] == DEMO_STAFF_NAME)
    save_program_groups(
        "V001",
        [
            {"program_key": program_key("소금체험"), "operator_id": staff["operator_id"]},
            {"program_key": program_key("조개잡이"), "operator_id": staff["operator_id"]},
        ],
    )
    saved = program_group_snapshot("V001")
    taken = [row["label"] for row in saved["programs"] if row["operator_id"] == staff["operator_id"]]
    assert taken == ["소금체험", "조개잡이"]
    set_program_operating("V001", "조개잡이", False)
    flags = {row["label"]: row["is_operating"] for row in program_group_snapshot("V001")["programs"]}
    assert flags["갯벌체험"] is True
    assert flags["조개잡이"] is False


def test_limited_manager_cannot_decide_another_booking(test_client):
    booking = create_booking("V001", "customer_test", "2026-11-12", 2)
    assert set_demo_persona("judge_guest", "village") is True
    response = test_client.post(
        "/kakao/approve",
        json={
            "intent": {"name": "예약승인"},
            "userRequest": {
                "utterance": f"{booking['booking_id']}번 승인",
                "user": {"id": "judge_guest"},
            },
            "action": {"params": {"booking_id": str(booking["booking_id"])}},
        },
    )
    assert "직접 만든 예약만" in response.text
    assert get_booking_by_id(booking["booking_id"])["status"] == "pending"


def test_judge_guest_booking_stays_off_the_manager_list():
    from services.booking import list_bookings_for_operator
    from services.demo_role import mark_guest_demo

    set_demo_persona("judge_guest", "guest")
    own = create_booking("V001", "judge_guest", "2026-11-20", 3, program_label="갯벌체험")
    mark_guest_demo("judge_guest", own["booking_id"])
    kept = create_booking("V001", "kakao_owner_v001", "2026-11-21", 2, program_label="갯벌체험")
    shown = {row["booking_id"] for row in list_bookings_for_operator("kakao_owner_v001")}
    assert own["booking_id"] not in shown
    assert kept["booking_id"] in shown


def test_role_page_sets_persona_and_hides_the_account(test_client):
    url = role_page_url("kakao_owner_v001")
    path = urlparse(url).path
    assert "kakao_owner_v001" not in path
    page = test_client.get(path)
    assert page.status_code == 200
    assert "체험객" in page.text
    assert "사무장" in page.text
    assert "체험 담당" in page.text
    chosen = test_client.post(path, data={"persona": "guest"})
    assert chosen.status_code == 200
    assert "체험객으로 바꿨습니다" in chosen.text
    assert "kakao_owner_v001" not in chosen.text


def test_presentation_off_keeps_the_stored_role(monkeypatch):
    monkeypatch.setenv("PRESENTATION_MODE", "0")
    assert set_demo_persona("kakao_owner_v001", "guest") is True
    from services.auth import resolve_kakao_role

    role = resolve_kakao_role("kakao_owner_v001")
    assert role["mode"] == "operator"
    assert role["role"] == "village"


def test_other_village_cannot_switch_to_demo_staff():
    from services.supabase_client import insert_operator

    insert_operator(
        {
            "village_id": "V002",
            "kakao_user_id": "other_owner",
            "operator_name": "다른 마을",
            "role": "village",
            "is_active": True,
        }
    )
    assert set_demo_persona("other_owner", "program") is False
    from services.supabase_client import delete_operator_by_kakao_id

    delete_operator_by_kakao_id("other_owner")
