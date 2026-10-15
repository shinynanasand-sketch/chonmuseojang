"""관광객 마을 화면은 확인된 최신 홍보만 보여 준다."""

from services.supabase_client import insert_content, insert_review, upsert_villages

_AUTH = {"Authorization": "Bearer owner_v001"}


def _seed_village():
    upsert_villages(
        [
            {
                "village_id": "V001",
                "village_name": "갯벌마을",
                "sigungu": "신안군",
                "program_type": "갯벌체험",
            },
            {
                "village_id": "V002",
                "village_name": "무등마을",
                "sigungu": "북구",
                "program_type": "농사체험",
            },
        ]
    )


def _content(village_id, content_type, body, *, public=False, photo_url=""):
    row = {
        "village_id": village_id,
        "operator_id": 1 if village_id == "V001" else 2,
        "content_type": content_type,
        "body": body,
        "is_public": public,
    }
    if photo_url:
        row["photo_url"] = photo_url
    return insert_content(row)


def test_publish_shows_only_the_latest_pair(test_client):
    _seed_village()
    _content("V001", "소개글", "옛 소개", public=True)
    _content("V001", "SNS홍보문구", "옛 문구", public=True)
    _content("V001", "소개글", "새 소개")
    _content(
        "V001",
        "SNS홍보문구",
        "새 문구",
        photo_url="https://example.test/content-photos/V001/a.png",
    )
    insert_review(
        {
            "village_id": "V001",
            "booking_id": 1,
            "customer_kakao_id": "guest",
            "comment": "비밀 후기",
            "rating": 5,
        }
    )
    _content("V002", "소개글", "무등 소개", public=True)

    published = test_client.post("/api/operator/contents/publish", headers=_AUTH)
    assert published.status_code == 200
    assert published.json()["published"] is True

    response = test_client.get("/api/villages/V001/promo")
    assert response.status_code == 200
    body = response.json()
    assert body["intro"] == "새 소개"
    assert body["sns"] == "새 문구"
    assert body["photo_url"] == "https://example.test/content-photos/V001/a.png"
    assert body["sigungu"] == "신안군"
    assert body["program_type"] == "갯벌체험"
    text = response.text
    assert "옛 소개" not in text
    assert "옛 문구" not in text
    assert "비밀 후기" not in text
    assert "무등 소개" not in text
    assert "guest" not in text


def test_draft_is_hidden_and_place_remains(test_client):
    _seed_village()
    _content("V001", "소개글", "아직 초안")
    _content("V001", "SNS홍보문구", "아직 문구")

    response = test_client.get("/api/villages/V001/promo")
    assert response.status_code == 200
    body = response.json()
    assert body["intro"] == ""
    assert body["sns"] == ""
    assert body["photo_url"] == ""
    assert body["village_name"] == "갯벌마을"
    assert body["sigungu"] == "신안군"
    assert body["program_type"] == "갯벌체험"
    assert "아직 초안" not in response.text


def test_publish_other_village_is_forbidden(test_client):
    _seed_village()
    _content("V001", "소개글", "갯벌 소개", public=True)
    response = test_client.post(
        "/api/operator/contents/publish",
        headers=_AUTH,
        json={"village_id": "V002"},
    )
    assert response.status_code == 403
    kept = test_client.get("/api/villages/V001/promo").json()
    assert kept["intro"] == "갯벌 소개"


def test_village_page_shows_published_copy(test_client):
    _seed_village()
    _content("V001", "소개글", "페이지 소개", public=True)
    _content("V001", "SNS홍보문구", "페이지 문구", public=True)

    page = test_client.get("/village/V001")
    assert page.status_code == 200
    assert "페이지 소개" in page.text
    assert "페이지 문구" in page.text
    assert "신안군" in page.text


def test_village_page_without_promo_shows_place(test_client):
    _seed_village()
    page = test_client.get("/village/V001")
    assert page.status_code == 200
    assert "갯벌마을" in page.text
    assert "신안군" in page.text
    assert "갯벌체험" in page.text


def test_recommend_and_map_link_to_village_page(test_client):
    recommend = test_client.get("/static/js/recommend.js").text
    village_map = test_client.get("/static/js/map.js").text
    assert "/village/" in recommend
    assert "/village/" in village_map


def test_home_links_to_village_page(test_client):
    page = test_client.get("/")
    assert page.status_code == 200
    assert "/village/" in page.text
    assert "마을 소개" in page.text


def test_operator_page_has_publish_button(test_client):
    html = test_client.get("/operator").text
    assert "관광객에게 공개" in html


def test_published_menu_lists_demo_village_and_skips_drafts(test_client):
    upsert_villages(
        [
            {
                "village_id": "V001",
                "village_name": "예시 갯벌마을",
                "sigungu": "신안군",
                "program_type": "갯벌체험",
            },
            {
                "village_id": "V003",
                "village_name": "진도 농촌마을",
                "sigungu": "진도군",
                "program_type": "농사체험",
            },
        ]
    )
    _content("V001", "소개글", "공개 소개", public=True)
    _content("V001", "SNS홍보문구", "공개 문구", public=True)
    _content("V003", "소개글", "비공개 소개")
    insert_review(
        {
            "village_id": "V001",
            "booking_id": 1,
            "customer_kakao_id": "guest",
            "comment": "비밀 후기",
            "rating": 5,
        }
    )

    page = test_client.get("/villages")
    assert page.status_code == 200
    assert 'href="/village/V001"' in page.text
    assert "예시 갯벌마을" in page.text
    assert "신안군" in page.text
    assert "진도 농촌마을" not in page.text
    assert "비공개 소개" not in page.text
    assert "비밀 후기" not in page.text
    assert 'href="/villages"' in page.text
    assert 'href="/operator"' in page.text


def test_published_menu_is_empty_without_public_copy(test_client):
    _seed_village()
    _content("V001", "소개글", "아직 초안")
    page = test_client.get("/villages")
    assert page.status_code == 200
    assert "공개된 마을 소개가 없습니다." in page.text
    assert "갯벌마을" not in page.text
    assert "아직 초안" not in page.text
