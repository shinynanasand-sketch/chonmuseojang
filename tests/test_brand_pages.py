"""소개 화면은 기존 홈과 분리되고, 목업 도구는 포함하지 않는다."""

from main import templates

_KAKAO = 'href="https://pf.kakao.com/_RgZaX"'
_FORBIDDEN = (
    "character-file",
    "asset-picker",
    "preview-bar",
    "character-placeholder",
    "route-placeholder",
    "디자인 참고용",
    "브랜드 목업",
    "/static/css/style.css",
)


def _presentation(monkeypatch, enabled: bool) -> None:
    monkeypatch.setitem(templates.env.globals, "presentation_mode", enabled)


def test_brand_page_keeps_copy_image_and_channel(test_client):
    page = test_client.get("/brand")
    assert page.status_code == 200
    text = page.text
    assert "<title>체험마을 AI사무장</title>" in text
    assert "익숙한 카카오에서" in text
    assert "왜 만들었는지 알아보기" in text
    assert 'href="/story"' in text
    assert 'href="/"' in text
    assert _KAKAO in text
    assert 'target="_blank"' in text
    assert 'rel="noopener noreferrer"' in text
    assert 'src="/static/ai-samujang.webp"' in text
    assert "태블릿을 들고 농촌 체험마을에서 안내하는 AI사무장 로봇" in text
    assert "/static/css/brand.css" in text
    assert 'aria-label="체험객"' not in text
    for token in _FORBIDDEN:
        assert token not in text


def test_story_page_keeps_section_order_and_demo_link(test_client, monkeypatch):
    _presentation(monkeypatch, True)
    page = test_client.get("/story")
    assert page.status_code == 200
    text = page.text
    assert "<title>서비스 이야기·이용 안내 - 체험마을 AI사무장</title>" in text
    assert 'href="/brand"' in text
    assert _KAKAO in text
    assert 'href="/#demo"' in text
    order = ["why", "direction", "response", "roles", "usage", "start"]
    positions = [text.index(f'id="{section}"') for section in order]
    assert positions == sorted(positions)
    assert "사무장이 없거나, 고령화로" in text
    assert "익숙한 카카오로 운영을 도울 수 있을까?" in text
    assert "검토한 방향을 이렇게 구현했다." in text
    assert "구현한 대응과 실제 효과는 구분한다." in text
    assert "기존 권한과 진입 경로에 따라" in text
    roles = text[text.index('id="roles"'):text.index('id="usage"')]
    for href in (
        "/",
        "/recommend",
        "/map",
        "/nearby",
        "/villages",
        "/operator",
        "/guide/use",
        "/#demo-step-1",
        "/#demo-step-4",
        "/#demo-step-5",
    ):
        assert f'href="{href}"' in roles
    assert "체험 담당은 같은 마을 일정을 보고" in roles
    assert 'href="/guide/register"' not in text
    assert 'href="/guide/dev"' not in text
    for token in _FORBIDDEN:
        assert token not in text


def test_story_hides_demo_link_when_presentation_is_off(test_client, monkeypatch):
    _presentation(monkeypatch, False)
    text = test_client.get("/story").text
    assert 'href="/#demo"' not in text
    assert 'href="/#demo-step-1"' not in text
    assert 'href="/#demo-step-4"' not in text
    assert 'href="/#demo-step-5"' not in text
    assert 'href="/operator"' in text
    assert 'href="/guide/use"' in text
    assert "실제 이용 과정은 시연에서." in text
    assert _KAKAO in text


def test_home_stays_on_its_own_stylesheet(test_client, monkeypatch):
    _presentation(monkeypatch, True)
    home = test_client.get("/")
    assert home.status_code == 200
    assert "/static/css/style.css" in home.text
    assert "/static/css/brand.css" not in home.text
    assert 'id="demo"' in home.text
    assert 'id="demo-step-1"' in home.text
    assert 'id="demo-step-4"' in home.text
    assert 'id="demo-step-5"' in home.text
    step1 = home.text[home.text.index('data-demo-panel="1"'):home.text.index('data-demo-panel="2"')]
    assert step1.index("달력으로 예약") < step1.index("카카오에 넣는 문장")
    assert 'aria-label="체험객"' in home.text
    assert 'href="/operator"' in home.text
    assert 'href="/guide/use"' in home.text
    assert 'href="/brand"' in home.text
    assert 'href="/story"' in home.text
    sitemap = test_client.get("/sitemap.xml").text
    assert "https://chonmuseojang.vercel.app/brand" in sitemap
    assert "https://chonmuseojang.vercel.app/story" in sitemap
    assert "/operator" not in sitemap
    assert "/calendar/" not in sitemap
