import pytest

from services.auth import register_operator
from services.supabase_client import (
    delete_operator_by_kakao_id,
    set_registration_code,
    upsert_villages,
)

_CREATED = ("qr_owner", "qr_program", "qr_tourist")


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
def quick_reply_village():
    _put_village("VQUICK", "버튼마을", "QR-001", "조개잡이")
    yield
    for user_id in _CREATED:
        delete_operator_by_kakao_id(user_id)


def _ask(name: str, user_id: str, utterance: str) -> dict:
    return {
        "intent": {"name": name},
        "userRequest": {"utterance": utterance, "user": {"id": user_id}},
        "action": {"params": {}},
    }


def _labels(response) -> list[str]:
    replies = response.json()["template"].get("quickReplies") or []
    return [item["label"] for item in replies]


def test_village_operator_gets_lookup_buttons(test_client, quick_reply_village):
    register_operator("qr_owner", "버튼마을 QR-001")
    response = test_client.post(
        "/kakao/ask",
        json=_ask("체험 달력 조회", "qr_owner", "체험 달력 조회"),
    )
    body = response.json()
    replies = body["template"]["quickReplies"]
    assert _labels(response) == [
        "예약 현황 조회",
        "체험 달력 조회",
        "체험 글 조회",
        "홍보 사진",
        "등록 안내",
        "사용 안내",
    ]
    assert "체험 글 저장" not in response.text
    assert all(item["action"] == "message" for item in replies)
    assert all(item["messageText"] == item["label"] for item in replies)
    assert "simpleText" in body["template"]["outputs"][0]


def test_program_operator_buttons_skip_booking_status(test_client, quick_reply_village):
    register_operator("qr_owner", "버튼마을 QR-001")
    register_operator("qr_program", "버튼마을 QR-001 조개잡이")
    response = test_client.post(
        "/kakao/ask",
        json=_ask("체험 글 조회", "qr_program", "체험 글 조회"),
    )
    assert _labels(response) == ["체험 달력 조회", "체험 글 조회", "체험 글 저장", "등록 안내", "사용 안내"]
    assert "예약 현황 조회" not in response.text
    assert "홍보 사진" not in response.text


def test_registration_success_shows_that_role_buttons(test_client, quick_reply_village):
    owner = test_client.post(
        "/kakao/ask",
        json=_ask("운영자 등록", "qr_owner", "버튼마을 QR-001"),
    )
    assert "등록 완료" in owner.text
    assert _labels(owner) == [
        "예약 현황 조회",
        "체험 달력 조회",
        "체험 글 조회",
        "홍보 사진",
        "등록 안내",
        "사용 안내",
    ]

    program = test_client.post(
        "/kakao/ask",
        json=_ask("운영자 등록", "qr_program", "버튼마을 QR-001 조개잡이"),
    )
    assert "체험 담당" in program.text
    assert _labels(program) == ["체험 달력 조회", "체험 글 조회", "체험 글 저장", "등록 안내", "사용 안내"]


def test_same_program_again_is_refused(test_client, quick_reply_village):
    register_operator("qr_owner", "버튼마을 QR-001")
    register_operator("qr_program", "버튼마을 QR-001 조개잡이")
    response = test_client.post(
        "/kakao/ask",
        json=_ask("운영자 등록", "qr_tourist", "버튼마을 QR-001 조개잡이"),
    )
    assert "이미 담당자" in response.text
    assert "quickReplies" not in response.json()["template"]


def test_tourist_response_has_no_operator_buttons(test_client, quick_reply_village):
    response = test_client.post(
        "/kakao/ask",
        json=_ask("체험 달력 조회", "qr_tourist", "체험 달력 조회"),
    )
    assert response.status_code == 200
    assert "quickReplies" not in response.json()["template"]
    assert "예약 현황 조회" not in response.text
    assert "체험 달력 조회" not in response.json()["template"].get("quickReplies", [])
