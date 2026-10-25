import pytest

from services.auth import register_operator
from services.booking import create_booking, list_my_bookings
from services.supabase_client import (
    delete_operator_by_kakao_id,
    insert_operator,
    insert_review,
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
    assert _labels(response) == ["마을 추천", "예약하기", "내 예약", "후기 보기"]


def test_tourist_response_has_no_operator_buttons(test_client, quick_reply_village):
    response = test_client.post(
        "/kakao/ask",
        json=_ask("체험 달력 조회", "qr_tourist", "체험 달력 조회"),
    )
    assert response.status_code == 200
    assert _labels(response) == ["마을 추천", "예약하기", "내 예약", "후기 보기"]
    assert "예약 현황 조회" not in _labels(response)
    assert "체험 달력 조회" not in _labels(response)
    assert "홍보 사진" not in _labels(response)


def _text(response) -> str:
    return response.json()["template"]["outputs"][0]["simpleText"]["text"]


def test_village_button_asks_for_a_condition(test_client, mocker):
    mocked = mocker.patch("services.kakao_phase_a.recommend_for_kakao")
    response = test_client.post("/kakao/ask", json=_ask("마을 추천", "guest", "마을 추천"))
    assert "체험 종류나 시군 이름" in _text(response)
    assert _labels(response) == ["마을 추천", "예약하기", "내 예약", "후기 보기"]
    mocked.assert_not_called()


def test_booking_button_guides_without_saving(test_client):
    upsert_villages(
        [
            {"village_id": "V001", "village_name": "예시 무등마을", "sigungu": "북구"},
            {
                "village_id": "VK-REAL",
                "village_name": "도선국사체험마을영농조합법인",
                "sigungu": "광양시",
            },
        ]
    )
    insert_operator(
        {
            "village_id": "VK-REAL",
            "kakao_user_id": "real-op",
            "role": "village",
            "is_active": True,
        }
    )
    before = list_my_bookings("guest")
    for path in ("/kakao/ask", "/kakao/booking"):
        response = test_client.post(path, json=_ask("예약하기", "guest", "예약하기"))
        text = _text(response)
        assert "도선국사체험마을영농조합법인" in text
        assert "광양시" in text
        assert "예시" not in text
        assert "체험 이름 2026-11-01 30명" in text
        assert _labels(response) == ["마을 추천", "예약하기", "내 예약", "후기 보기"]
    assert list_my_bookings("guest") == before


def test_my_booking_button_lists_only_that_user(test_client):
    create_booking("V001", "guest", "2026-11-01", 30, program_label="조개잡이")
    create_booking("V001", "other", "2026-12-01", 4, program_label="숨은체험")
    response = test_client.post("/kakao/booking", json=_ask("내 예약", "guest", "내 예약"))
    text = _text(response)
    assert "2026-11-01" in text
    assert "30명" in text
    assert "2026-12-01" not in text


def test_review_button_asks_then_shows_that_village(test_client):
    upsert_villages(
        [{"village_id": "VK-REAL", "village_name": "도선국사체험마을영농조합법인", "sigungu": "광양시"}]
    )
    insert_review(
        {
            "village_id": "VK-REAL",
            "customer_kakao_id": "guest",
            "comment": "아이들이 좋아했어요",
            "rating": 5,
        }
    )
    ask = test_client.post("/kakao/ask", json=_ask("후기 보기", "guest", "후기 보기"))
    assert "어떤 마을 후기" in _text(ask)
    shown = test_client.post(
        "/kakao/ask",
        json=_ask("후기 보기", "guest", "후기 보기 도선국사체험마을영농조합법인"),
    )
    text = _text(shown)
    assert "별점 5" in text
    assert "아이들이 좋아했어요" in text
