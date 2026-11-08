"""도선국사마을은 화면 이름만 바꾸고 저장 원본은 법인명으로 둔다."""

from services.kakao_entity_export import build_village_name_rows
from services.supabase_client import (
    get_village_by_id,
    list_villages,
    list_villages_by_name,
    upsert_villages,
)

_VILLAGE_ID = "PDeac2fe424e02"
_OFFICIAL = "도선국사체험마을영농조합법인"
_REQUESTED = "도선국사마을"


def _store_doseon() -> None:
    upsert_villages(
        [
            {
                "village_id": _VILLAGE_ID,
                "village_name": _OFFICIAL,
                "sido": "전남광주통합특별시",
                "sigungu": "광양시",
                "program_type": "만들기체험",
                "program_name": "감수확",
            }
        ]
    )


def test_villages_menu_lists_requested_name_without_public_copy(test_client):
    _store_doseon()

    page = test_client.get("/villages")
    assert page.status_code == 200
    assert page.text.count(f'href="/village/{_VILLAGE_ID}"') == 1
    assert _REQUESTED in page.text
    assert "광양시" in page.text
    assert _OFFICIAL not in page.text


def test_villages_menu_lists_requested_name_once_when_copy_is_public(test_client):
    from services.supabase_client import insert_content

    _store_doseon()
    insert_content(
        {
            "village_id": _VILLAGE_ID,
            "content_type": "소개글",
            "body": "이미 쓴 도선국사 소개",
            "is_public": True,
        }
    )

    page = test_client.get("/villages")
    assert page.text.count(f'href="/village/{_VILLAGE_ID}"') == 1
    assert _REQUESTED in page.text
    detail = test_client.get(f"/village/{_VILLAGE_ID}")
    assert "이미 쓴 도선국사 소개" in detail.text


def test_public_surfaces_show_requested_name_and_keep_stored_name(test_client):
    _store_doseon()

    listed = test_client.get("/api/villages?sigungu=광양시").json()
    match = [row for row in listed["villages"] if row["village_id"] == _VILLAGE_ID]
    assert match[0]["village_name"] == _REQUESTED

    page = test_client.get(f"/village/{_VILLAGE_ID}")
    assert page.status_code == 200
    assert _REQUESTED in page.text

    stored = next(row for row in list_villages() if row["village_id"] == _VILLAGE_ID)
    assert stored["village_name"] == _OFFICIAL
    assert get_village_by_id(_VILLAGE_ID)["village_name"] == _REQUESTED

    by_new = list_villages_by_name(_REQUESTED)
    by_old = list_villages_by_name(_OFFICIAL)
    by_place = list_villages_by_name(_REQUESTED, sigungu="광양시")
    by_other = list_villages_by_name(_REQUESTED, sigungu="구례군")
    assert [row["village_id"] for row in by_new] == [_VILLAGE_ID]
    assert by_new[0]["village_name"] == _REQUESTED
    assert by_old[0]["village_id"] == _VILLAGE_ID
    assert by_old[0]["village_name"] == _REQUESTED
    assert [row["village_id"] for row in by_place] == [_VILLAGE_ID]
    assert by_other == []


def test_other_village_keeps_the_legal_name(test_client):
    upsert_villages(
        [
            {
                "village_id": "VK-REAL",
                "village_name": _OFFICIAL,
                "sigungu": "광양시",
            }
        ]
    )
    assert get_village_by_id("VK-REAL")["village_name"] == _OFFICIAL
    assert list_villages_by_name(_REQUESTED) == []


def test_entity_export_puts_requested_name_before_legal_name():
    rows, errors = build_village_name_rows(
        [
            {
                "village_id": _VILLAGE_ID,
                "village_name": _OFFICIAL,
                "sigungu": "광양시",
            }
        ]
    )
    assert errors == []
    assert rows == [[_VILLAGE_ID, _REQUESTED, _OFFICIAL]]


def test_name_request_page_records_what_was_applied(test_client):
    page = test_client.get("/guide/name-requests")
    assert page.status_code == 200
    text = page.text
    assert _REQUESTED in text
    assert _OFFICIAL in text
    assert "PDeac2fe424e02" in text
    assert "현장 변경 기록" in text
    assert "현장 요청" in text
    assert "적용함" in text
    assert "적용하지 않음" in text
    assert "천연염색(에코백)" in text
    assert "양파수확" in text
    assert "RH-616" not in text
    assert "/guide/name-requests" not in test_client.get("/sitemap.xml").text

    guide = test_client.get("/guide/use")
    assert 'href="/guide/name-requests"' in guide.text
    assert "현장 변경 기록" in guide.text
