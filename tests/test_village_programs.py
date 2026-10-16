"""마을 프로그램 글은 항목으로 나누고, 운영 여부는 담당 마을만 바로 바꾼다."""

from services.recommend import recommendation_lines
from services.supabase_client import upsert_villages
from services.village_programs import program_labels, set_program_operating

_AUTH = {"Authorization": "Bearer owner_v001"}
_NESTED = "자연생태체험+기타(영농체험+먹거리체험)"


def _seed():
    upsert_villages(
        [
            {
                "village_id": "V001",
                "village_name": "갯벌마을",
                "sigungu": "신안군",
                "program_type": "갯벌체험",
                "program_name": _NESTED,
            },
            {
                "village_id": "V002",
                "village_name": "무등마을",
                "sigungu": "북구",
                "program_type": "농사체험",
                "program_name": "모내기",
            },
        ]
    )


def test_plus_inside_parentheses_stays_one_item():
    labels = program_labels({"program_name": _NESTED, "program_type": "갯벌체험"})
    assert labels == ["자연생태체험", "기타(영농체험+먹거리체험)"]


def test_empty_program_name_uses_program_type():
    labels = program_labels(
        {"program_name": "", "program_type": "농사체험+음식체험"}
    )
    assert labels == ["농사체험", "음식체험"]


def test_programs_default_to_operating(test_client):
    _seed()
    body = test_client.get("/api/villages/V001/promo").json()
    assert [item["label"] for item in body["programs"]] == [
        "자연생태체험",
        "기타(영농체험+먹거리체험)",
    ]
    assert all(item["is_operating"] for item in body["programs"])


def test_operator_stop_shows_on_promo_immediately(test_client):
    _seed()
    stopped = test_client.post(
        "/api/operator/programs/status",
        headers=_AUTH,
        json={"label": "기타(영농체험+먹거리체험)", "is_operating": False},
    )
    assert stopped.status_code == 200
    body = test_client.get("/api/villages/V001/promo").json()
    flags = {item["label"]: item["is_operating"] for item in body["programs"]}
    assert flags["자연생태체험"] is True
    assert flags["기타(영농체험+먹거리체험)"] is False
    page = test_client.get("/village/V001")
    assert page.status_code == 200
    assert "기타(영농체험+먹거리체험)" in page.text
    assert "지금은 운영하지 않음" in page.text


def test_other_village_program_status_is_forbidden(test_client):
    _seed()
    response = test_client.post(
        "/api/operator/programs/status",
        headers=_AUTH,
        json={"label": "모내기", "is_operating": False, "village_id": "V002"},
    )
    assert response.status_code == 403
    other = test_client.get("/api/villages/V002/promo").json()
    assert other["programs"][0]["label"] == "모내기"
    assert other["programs"][0]["is_operating"] is True


def test_sync_keeps_stopped_program(test_client):
    _seed()
    test_client.post(
        "/api/operator/programs/status",
        headers=_AUTH,
        json={"label": "자연생태체험", "is_operating": False},
    )
    upsert_villages(
        [
            {
                "village_id": "V001",
                "village_name": "갯벌마을",
                "sigungu": "신안군",
                "program_type": "갯벌체험",
                "program_name": _NESTED,
                "address": "전남 신안군",
            }
        ]
    )
    body = test_client.get("/api/villages/V001/promo").json()
    flags = {item["label"]: item["is_operating"] for item in body["programs"]}
    assert flags["자연생태체험"] is False


def test_home_lists_operating_programs(test_client):
    _seed()
    test_client.post(
        "/api/operator/programs/status",
        headers=_AUTH,
        json={"label": "자연생태체험", "is_operating": False},
    )
    villages = test_client.get("/api/villages").json()["villages"]
    village = next(item for item in villages if item["village_id"] == "V001")
    operating = [item["label"] for item in village["programs"] if item["is_operating"]]
    assert operating == ["기타(영농체험+먹거리체험)"]
    assert "is_operating" in test_client.get("/").text


def test_operator_page_can_toggle_programs(test_client):
    html = test_client.get("/operator").text
    assert 'id="program-list"' in html
    assert "중지" in html


def test_kakao_reason_marks_stopped_program_only_for_that_village(test_client):
    _seed()
    set_program_operating("V001", "자연생태체험", False)
    set_program_operating("V002", "모내기", False)
    villages = [
        {
            "village_id": "V001",
            "village_name": "갯벌마을",
            "sigungu": "신안군",
            "program_type": "갯벌체험",
            "program_name": _NESTED,
        },
        {
            "village_id": "V002",
            "village_name": "무등마을",
            "sigungu": "북구",
            "program_type": "농사체험",
            "program_name": "모내기",
        },
    ]
    matches = [
        {
            "village_id": "V001",
            "village_name": "갯벌마을",
            "reason": "갯벌과 맞습니다. 자연생태체험, 기타(영농체험+먹거리체험).",
        }
    ]
    text = recommendation_lines(matches, villages)[0]
    assert "자연생태체험은 지금은 운영하지 않음" in text
    assert "먹거리체험" in text
    assert text.count("지금은 운영하지 않음") == 1
    assert "모내기" not in text
