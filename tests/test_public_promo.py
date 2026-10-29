"""관광객 마을 화면은 확인된 최신 홍보만 보여 준다."""

from urllib.parse import urlsplit

from config import presentation_enabled
from main import templates
from services.booking import create_booking
from services.presentation_board import _PRESENTATION_GUEST_ID
from services.supabase_client import insert_content, insert_operator, insert_review, upsert_villages

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
    _content("V001", "소개글", "페이지 소개", public=True, photo_url="https://example.test/content-photos/V001/a.png")
    _content("V001", "SNS홍보문구", "페이지 문구", public=True)

    page = test_client.get("/village/V001")
    assert page.status_code == 200
    assert "페이지 소개" in page.text
    assert "페이지 문구" in page.text
    assert "신안군" in page.text
    assert 'class="promo-photo"' in page.text
    css = test_client.get("/static/css/style.css").text
    rule = css.split(".promo-photo img", 1)[1].split("}", 1)[0]
    assert "height: auto" in rule


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


def test_home_exposes_naver_verification_and_public_sitemap(test_client):
    page = test_client.get("/")
    assert page.status_code == 200
    assert 'name="naver-site-verification"' in page.text
    assert "bf6009ea39af06737f3b4647a7e8a848b21a4bf0" in page.text

    sitemap = test_client.get("/sitemap.xml")
    assert sitemap.status_code == 200
    assert "https://chonmuseojang.vercel.app/villages" in sitemap.text
    assert "/operator" not in sitemap.text
    assert "/calendar/" not in sitemap.text

    robots = test_client.get("/robots.txt")
    assert robots.status_code == 200
    assert "Sitemap: https://chonmuseojang.vercel.app/sitemap.xml" in robots.text
    assert "Disallow: /operator" in robots.text
    assert "Disallow: /calendar/" in robots.text
    assert "Disallow: /book/" in robots.text
    assert "Disallow: /guide/dev" in robots.text


def test_home_links_to_village_page(test_client):
    page = test_client.get("/")
    assert page.status_code == 200
    assert "/village/" in page.text
    assert "마을 소개" in page.text
    assert "아직 카카오로 예약할 수 있는 마을이 없습니다." in page.text


def test_home_kakao_guide_lists_only_village_operators(test_client):
    upsert_villages(
        [
            {
                "village_id": "VK-HOME",
                "village_name": "돌담마을",
                "sigungu": "해남군",
                "program_type": "농사체험",
            },
            {
                "village_id": "VK-PROG",
                "village_name": "프로그램만마을",
                "sigungu": "강진군",
                "program_type": "요리체험",
            },
        ]
    )
    insert_operator(
        {
            "village_id": "VK-HOME",
            "kakao_user_id": "secret-kakao-home-id",
            "login_id": "secret-login-home",
            "operator_name": "숨은이름운영자",
            "registration_code": "SECRET-CODE-99",
            "role": "village",
            "is_active": True,
        }
    )
    insert_operator(
        {
            "village_id": "VK-PROG",
            "kakao_user_id": "secret-kakao-program-id",
            "login_id": "secret-login-program",
            "operator_name": "숨은체험담당",
            "registration_code": "SECRET-CODE-88",
            "role": "program",
            "program_key": "cook",
            "is_active": True,
        }
    )

    page = test_client.get("/")
    assert page.status_code == 200
    text = page.text
    assert "돌담마을" in text
    assert "해남군" in text
    assert "프로그램만마을" not in text
    assert "secret-kakao-home-id" not in text
    assert "secret-kakao-program-id" not in text
    assert "SECRET-CODE-99" not in text
    assert "SECRET-CODE-88" not in text
    assert "숨은이름운영자" not in text
    assert "달력이 열립니다" in text
    assert "내 예약" in text
    assert 'href="https://pf.kakao.com/_RgZaX"' in text
    assert "<title>https://pf.kakao.com/_RgZaX</title>" in text
    assert "<svg" in text


def test_home_kakao_guide_omits_demo_villages(test_client):
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
            "kakao_user_id": "real-home-op",
            "role": "village",
            "is_active": True,
        }
    )
    page = test_client.get("/")
    assert page.status_code == 200
    assert "도선국사체험마을영농조합법인" in page.text
    assert "광양시" in page.text
    assert "예시 무등마을" not in page.text


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


def test_edited_public_copy_shows_on_village_page(test_client):
    _seed_village()
    intro = _content("V001", "소개글", "옛 소개", public=True)
    _content("V001", "SNS홍보문구", "페이지 문구", public=True)
    edited = test_client.patch(
        f"/api/operator/contents/{intro['content_id']}",
        headers=_AUTH,
        json={"body": "고친 소개"},
    )
    assert edited.status_code == 200
    page = test_client.get("/village/V001")
    assert page.status_code == 200
    assert "고친 소개" in page.text
    assert "옛 소개" not in page.text
    assert "페이지 문구" in page.text


def test_deleting_public_intro_falls_back_to_the_older_copy(test_client):
    _seed_village()
    _content("V001", "소개글", "옛 소개", public=True)
    newer = _content("V001", "소개글", "새 소개", public=True)
    _content("V001", "SNS홍보문구", "페이지 문구", public=True)
    removed = test_client.delete(
        f"/api/operator/contents/{newer['content_id']}",
        headers=_AUTH,
    )
    assert removed.status_code == 200
    page = test_client.get("/village/V001")
    assert "새 소개" not in page.text
    assert "옛 소개" in page.text
    assert "페이지 문구" in page.text


def test_deleting_shared_photo_hides_it_on_the_village_page(test_client):
    _seed_village()
    photo = "https://example.test/storage/v1/object/public/content-photos/V001/a.png"
    intro = _content("V001", "소개글", "페이지 소개", public=True, photo_url=photo)
    _content("V001", "SNS홍보문구", "페이지 문구", public=True, photo_url=photo)
    removed = test_client.delete(
        f"/api/operator/contents/{intro['content_id']}/photo",
        headers=_AUTH,
    )
    assert removed.status_code == 200
    page = test_client.get("/village/V001")
    assert page.status_code == 200
    assert "페이지 소개" in page.text
    assert "페이지 문구" in page.text
    assert 'class="promo-photo"' not in page.text
    promo = test_client.get("/api/villages/V001/promo").json()
    assert promo["photo_url"] == ""
    assert promo["intro"] == "페이지 소개"


def _presentation(monkeypatch, enabled: bool) -> None:
    monkeypatch.setitem(templates.env.globals, "presentation_mode", enabled)


def test_presentation_flag_is_off_only_for_zero():
    assert presentation_enabled("0") is False
    assert presentation_enabled(" 0 ") is False
    assert presentation_enabled("1") is True
    assert presentation_enabled("") is True
    assert presentation_enabled("false") is True


def _assert_role_menus(text: str) -> None:
    assert 'aria-label="체험객"' in text
    assert 'aria-label="사무장"' in text
    assert 'href="/recommend"' in text
    assert 'href="/map"' in text
    assert 'href="/nearby"' in text
    assert 'href="/villages"' in text
    assert 'href="/operator"' in text
    assert 'href="/guide/use"' in text
    assert 'href="/guide/register"' not in text
    assert 'href="/guide/dev"' not in text
    assert 'href="/dashboard"' not in text


def test_home_shows_demo_tracks_when_presentation_is_on(test_client, monkeypatch):
    _presentation(monkeypatch, True)
    text = test_client.get("/").text
    _assert_role_menus(text)
    assert 'id="demo"' in text
    assert 'href="/#demo"' in text
    assert "시연 순서" in text
    assert "카카오에서 하고, 웹에서 확인합니다." in text
    assert "카카오에 넣는 문장" in text
    assert "카카오 답변" in text
    assert "예약번호와 대기로 접수됩니다." in text
    assert "사진을 한 장 올려 주세요." in text
    assert "달력에서 승인" in text
    assert "대기인 날짜를 눌러 승인하거나 거절합니다." in text
    assert 'id="demo-calendar"' in text
    assert 'id="demo-book-frame"' in text
    assert 'id="demo-approve-frame"' in text
    assert "<iframe" not in text
    assert "/book/" not in text
    assert "/calendar/" not in text
    assert 'class="kakao-ask"' in text
    assert "체험객 예약" in text
    for number in ("1", "2", "3", "4"):
        assert f'class="demo-num">{number}' in text
    assert text.index("시연 순서") < text.index("체험객</h2>")
    assert "사무장 관리" in text
    assert "카카오 홍보 사진" in text
    assert "카카오 관리" in text
    assert 'href="/operator#status"' in text
    assert 'href="/operator#bookings"' in text
    assert 'href="/operator#reviews"' in text
    assert 'href="/operator#programs"' in text
    assert 'href="/operator#promo"' in text
    for utterance in ("홍보 사진", "예약 현황", "7번 승인", "7번 거절", "체험 달력 조회", "체험 글 조회"):
        assert f'data-copy="{utterance}"' in text
    assert "아직 카카오로 예약할 수 있는 마을이 없습니다." in text
    assert "달력이 열립니다" in text
    assert "owner_v001" not in text
    assert "kakao_owner" not in text
    assert "GB-001" not in text
    operator = test_client.get("/operator").text
    assert 'id="status"' in operator
    assert 'id="bookings"' in operator
    assert 'id="reviews"' in operator
    assert 'id="promo"' in operator
    assert 'id="programs"' in operator
    assert "소개글과 SNS 초안" in operator
    assert "관광객에게 공개" in operator


def test_home_hides_demo_tracks_when_presentation_is_off(test_client, monkeypatch):
    _presentation(monkeypatch, False)
    text = test_client.get("/").text
    _assert_role_menus(text)
    assert 'id="demo"' not in text
    assert 'href="/#demo"' not in text
    assert "시연 순서" not in text
    assert "체험객 예약" not in text
    assert "demo-num" not in text
    assert "7번 승인" not in text
    assert "data-copy=" not in text
    assert "카카오에 넣는 문장" not in text
    assert "카카오 답변" not in text
    assert "예약번호와 대기로 접수됩니다." not in text
    assert "달력에서 체험, 날짜, 시간을 고릅니다." not in text
    assert "달력에서 승인" not in text
    assert 'id="demo-calendar"' not in text
    assert 'id="demo-book-frame"' not in text
    assert 'id="demo-approve-frame"' not in text
    assert "/book/" not in text
    assert "/calendar/" not in text
    assert "아직 카카오로 예약할 수 있는 마을이 없습니다." in text
    assert "달력이 열립니다" in text
    assert "내 예약" in text
    operator = test_client.get("/operator").text
    assert 'id="promo"' in operator
    assert "소개글과 SNS 초안" not in operator
    assert "관광객에게 공개" in operator


def test_presentation_board_uses_the_connected_village(test_client, monkeypatch):
    upsert_villages(
        [
            {
                "village_id": "VK-BOARD",
                "village_name": "돌담시연마을",
                "sigungu": "해남군",
                "program_name": "조개잡이",
            }
        ]
    )
    insert_operator(
        {
            "village_id": "VK-BOARD",
            "kakao_user_id": "secret-board-owner",
            "login_id": "secret-board-login",
            "operator_name": "숨은사무장",
            "registration_code": "SECRET-BOARD",
            "role": "village",
            "is_active": True,
        }
    )
    create_booking(
        "VK-BOARD",
        "secret-board-guest",
        "2026-12-01",
        4,
        customer_name="숨은손님",
        visit_time="10:00",
    )
    _content("VK-BOARD", "소개글", "비밀 소개 초안", photo_url="https://example.test/board.jpg")

    _presentation(monkeypatch, True)
    text = test_client.get("/").text
    assert 'data-copy="예약하기 돌담시연마을"' in text
    assert "돌담시연마을 해남군. 달력에서 체험, 날짜, 시간을 고릅니다." in text
    assert "달력으로 예약" in text
    assert "예약번호와 대기로 접수됩니다." in text
    assert 'class="kakao-ask"' in text
    assert 'class="kakao-reply"' in text
    assert 'data-copy="조개잡이 2026-11-01 10:00 30명"' in text
    assert 'data-copy="조개잡이 2026-11-01 광주소등학교 30명"' in text
    assert 'data-copy="1번 승인"' in text
    assert 'data-copy="1번 거절"' in text
    assert "1번 대기 2026-12-01 10:00 4명" in text
    assert "비밀 소개 초안" in text
    assert "초안" in text
    assert "https://example.test/board.jpg" in text
    assert 'href="/village/VK-BOARD"' not in text
    assert "번호 7은 예시입니다." not in text
    for secret in (
        "secret-board-owner",
        "secret-board-guest",
        "secret-board-login",
        "숨은손님",
        "숨은사무장",
        "SECRET-BOARD",
    ):
        assert secret not in text

    _presentation(monkeypatch, False)
    hidden = test_client.get("/").text
    assert 'data-copy="예약하기 돌담시연마을"' not in hidden
    assert "달력에서 체험, 날짜, 시간을 고릅니다." not in hidden
    assert "카카오에 넣는 문장" not in hidden
    assert "1번 대기 2026-12-01 10:00 4명" not in hidden
    assert "비밀 소개 초안" not in hidden
    assert "secret-board-guest" not in hidden


def test_presentation_calendar_url_needs_the_demo_password(test_client, monkeypatch):
    upsert_villages(
        [
            {
                "village_id": "VK-BOARD",
                "village_name": "돌담시연마을",
                "sigungu": "해남군",
                "program_name": "조개잡이",
            }
        ]
    )
    insert_operator(
        {
            "village_id": "VK-BOARD",
            "kakao_user_id": "secret-board-owner",
            "login_id": "secret-board-login",
            "operator_name": "숨은사무장",
            "registration_code": "SECRET-BOARD",
            "role": "village",
            "is_active": True,
        }
    )
    monkeypatch.setenv("PRESENTATION_CALENDAR_PASSWORD", "demo-pass")
    _presentation(monkeypatch, True)
    page = test_client.get("/").text
    assert 'id="demo-calendar"' in page
    assert 'id="demo-book-frame"' in page
    assert 'id="demo-approve-frame"' in page
    assert "<iframe" not in page
    assert "/book/" not in page
    assert "/calendar/" not in page
    assert "demo-pass" not in page
    assert _PRESENTATION_GUEST_ID not in page

    wrong = test_client.post("/api/presentation/calendar", json={"password": "nope"})
    assert wrong.status_code == 404
    assert "/book/" not in wrong.text
    assert "/calendar/" not in wrong.text
    assert "secret-board-owner" not in wrong.text
    assert _PRESENTATION_GUEST_ID not in wrong.text

    opened = test_client.post("/api/presentation/calendar", json={"password": "demo-pass"})
    assert opened.status_code == 200
    body = opened.json()
    assert set(body) == {"book_url", "calendar_url"}
    assert "/book/" in body["book_url"]
    assert "/calendar/" in body["calendar_url"]
    assert "embed=1" in body["book_url"]
    assert "embed=1" in body["calendar_url"]
    for secret in ("secret-board-owner", "secret-board-login", _PRESENTATION_GUEST_ID, "demo-pass"):
        assert secret not in opened.text

    def app_path(url: str) -> str:
        parts = urlsplit(url)
        query = f"?{parts.query}" if parts.query else ""
        return f"{parts.path}{query}"

    book_page = test_client.get(app_path(body["book_url"]))
    approve_page = test_client.get(app_path(body["calendar_url"]))
    plain_page = test_client.get(urlsplit(body["calendar_url"]).path)
    assert book_page.status_code == 200
    assert approve_page.status_code == 200
    assert plain_page.status_code == 200
    assert 'class="role-nav"' not in book_page.text
    assert 'class="role-nav"' not in approve_page.text
    assert 'class="role-nav"' in plain_page.text
    assert _PRESENTATION_GUEST_ID not in book_page.text

    _presentation(monkeypatch, False)
    hidden = test_client.post("/api/presentation/calendar", json={"password": "demo-pass"})
    assert hidden.status_code == 404
    assert "/book/" not in hidden.text
    assert "/calendar/" not in hidden.text
    assert 'id="demo-calendar"' not in test_client.get("/").text
