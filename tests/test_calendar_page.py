import pytest

from services.auth import register_operator
from services.calendar_link import issue_calendar_token
from services.program_share import save_calendar_entry
from services.supabase_client import (
    delete_calendar_for_village,
    delete_operator_by_kakao_id,
    get_operator_by_kakao_id,
    set_registration_code,
    upsert_villages,
)

_USERS = ("cal_owner_a", "cal_owner_b", "cal_program_a", "cal_tourist")


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
def calendar_villages():
    _put_village("VCALA", "달력마을", "CA-001", "조개잡이")
    _put_village("VCALB", "다른달력", "CB-001", "소금체험")
    yield
    for village_id in ("VCALA", "VCALB"):
        delete_calendar_for_village(village_id)
    for user_id in _USERS:
        delete_operator_by_kakao_id(user_id)


def _ask(name: str, user_id: str) -> dict:
    return {
        "intent": {"name": name},
        "userRequest": {"utterance": name, "user": {"id": user_id}},
        "action": {"params": {}},
    }


def test_other_village_token_hides_entries(test_client, calendar_villages):
    register_operator("cal_owner_a", "달력마을 CA-001")
    register_operator("cal_owner_b", "다른달력 CB-001")
    owner_a = get_operator_by_kakao_id("cal_owner_a")
    save_calendar_entry(owner_a, "조개잡이", "2026-11-01", "광주소등학교", 30)
    token_b = issue_calendar_token(get_operator_by_kakao_id("cal_owner_b"))

    seen = test_client.get(f"/api/calendar/{token_b}")
    assert seen.status_code == 200
    assert "광주소등학교" not in seen.text
    assert seen.json()["village_id"] == "VCALB"

    posted = test_client.post(
        f"/api/calendar/{token_b}",
        json={
            "village_id": "VCALA",
            "label": "조개잡이",
            "visit_date": "2026-11-01",
            "group_name": "광주소등학교",
            "num_people": 30,
        },
    )
    assert posted.status_code == 400
    again = test_client.get(f"/api/calendar/{token_b}")
    assert "광주소등학교" not in again.text


def test_program_operator_cannot_save_or_delete(test_client, calendar_villages):
    register_operator("cal_owner_a", "달력마을 CA-001")
    register_operator("cal_program_a", "달력마을 CA-001 조개잡이")
    owner = get_operator_by_kakao_id("cal_owner_a")
    save_calendar_entry(owner, "조개잡이", "2026-11-01", "광주소등학교", 30)
    token = issue_calendar_token(get_operator_by_kakao_id("cal_program_a"))

    viewed = test_client.get(f"/api/calendar/{token}")
    assert viewed.status_code == 200
    assert viewed.json()["can_write"] is False
    assert "광주소등학교" in viewed.text

    saved = test_client.post(
        f"/api/calendar/{token}",
        json={
            "label": "조개잡이",
            "visit_date": "2026-11-02",
            "group_name": "무안유치원",
            "num_people": 20,
        },
    )
    assert saved.status_code == 403

    removed = test_client.request(
        "DELETE",
        f"/api/calendar/{token}",
        json={"label": "조개잡이", "visit_date": "2026-11-01", "group_name": "광주소등학교"},
    )
    assert removed.status_code == 403
    assert "광주소등학교" in test_client.get(f"/api/calendar/{token}").text


def test_village_operator_saves_and_deletes(test_client, calendar_villages):
    register_operator("cal_owner_a", "달력마을 CA-001")
    token = issue_calendar_token(get_operator_by_kakao_id("cal_owner_a"))
    body = {
        "village_id": "VCALB",
        "label": "조개잡이",
        "visit_date": "2026-11-01",
        "group_name": "광주소등학교",
        "num_people": 30,
    }
    saved = test_client.post(f"/api/calendar/{token}", json=body)
    assert saved.status_code == 200
    assert saved.json()["village_id"] == "VCALA"
    updated = test_client.post(f"/api/calendar/{token}", json={**body, "num_people": 40})
    assert updated.status_code == 200
    other = test_client.post(
        f"/api/calendar/{token}",
        json={**body, "group_name": "무안유치원", "num_people": 20},
    )
    assert other.status_code == 200
    listed = test_client.get(f"/api/calendar/{token}").json()["entries"]
    assert len(listed) == 2
    assert any(row["num_people"] == 40 and row["group_name"] == "광주소등학교" for row in listed)

    removed = test_client.request(
        "DELETE",
        f"/api/calendar/{token}",
        json={"label": "조개잡이", "visit_date": "2026-11-01", "group_name": "광주소등학교"},
    )
    assert removed.status_code == 200
    left = test_client.get(f"/api/calendar/{token}").json()["entries"]
    assert len(left) == 1
    assert left[0]["group_name"] == "무안유치원"


def test_calendar_lookup_has_open_button_for_operators_only(test_client, calendar_villages):
    register_operator("cal_owner_a", "달력마을 CA-001")
    owner = test_client.post("/kakao/ask", json=_ask("체험 달력 조회", "cal_owner_a"))
    card = next(item["basicCard"] for item in owner.json()["template"]["outputs"] if "basicCard" in item)
    button = card["buttons"][0]
    assert button["label"] == "달력 열기"
    assert button["action"] == "webLink"
    assert "/calendar/" in button["webLinkUrl"]
    assert "cal_owner_a" not in button["webLinkUrl"]
    path = button["webLinkUrl"].split(".app", 1)[-1]
    page = test_client.get(path)
    assert page.status_code == 200
    assert "달력" in page.text

    tourist = test_client.post("/kakao/ask", json=_ask("체험 달력 조회", "cal_tourist"))
    assert "달력 열기" not in tourist.text
    assert test_client.get("/calendar/not-a-token").status_code == 404
