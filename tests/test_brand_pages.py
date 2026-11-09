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
    assert 'href="/home"' in text
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
    assert 'href="/home#demo"' in text
    order = ["why", "direction", "response", "changes", "roles", "usage", "start"]
    positions = [text.index(f'id="{section}"') for section in order]
    assert positions == sorted(positions)
    assert "사무장이 없거나, 고령화로" in text
    assert "익숙한 카카오로 운영을 도울 수 있을까?" in text
    assert "검토한 방향을 이렇게 구현했다." in text
    assert "현장의 요청을 반영해 바꿨다." in text
    assert "구현한 대응과 실제 효과는 구분한다." in text
    assert "기존 권한과 진입 경로에 따라" in text
    roles = text[text.index('id="roles"'):text.index('id="usage"')]
    for href in (
        "/home",
        "/recommend",
        "/map",
        "/nearby",
        "/villages",
        "/operator",
        "/guide/use",
        "/home#demo-step-1",
        "/home#demo-step-4",
        "/home#demo-step-5",
    ):
        assert f'href="{href}"' in roles
    assert "체험 담당은 같은 마을 일정을 보고" in roles
    usage = text[text.index('id="usage"'):text.index('id="start"')]
    assert "체험을 찾는다" in usage
    assert "마을을 운영한다" in usage
    assert "예약하기" in usage
    assert "체험 달력 조회" in usage
    assert "홍보 사진" in usage
    assert 'href="/home#demo-step-1"' in usage
    assert 'href="/home#demo-step-4"' in usage
    assert "다음 · 어떤 방향을 검토했는가" in text
    assert "다음 · 무엇을 구현했는가" in text
    assert "다음 · 주요 변경" in text
    assert "다음 · 누가 사용하는가" in text
    changes = text[text.index('id="changes"'):text.index('id="roles"')]
    assert "현장의 요청을 반영해 바꿨다." in changes
    assert "마을에서 요청한 변경 가운데 적용한 것과 적용하지 않은 것을 건수로 보여 준다." in changes
    assert "주요 변경을 건수와 함께 본다." not in changes
    assert "전체 41건" in changes
    assert "적용 36건" in changes
    assert "적용하지 않음 5건" in changes
    assert 'href="/story/changes"' in changes
    assert 'href="/guide/name-requests"' in changes
    assert "감수확" not in changes
    assert "다음 · 어떻게 사용하는가" in text
    assert "다음 · 이용·시연 안내" in text
    assert 'href="/guide/register"' not in text
    assert 'href="/guide/dev"' not in text
    for token in _FORBIDDEN:
        assert token not in text


def test_story_hides_demo_link_when_presentation_is_off(test_client, monkeypatch):
    _presentation(monkeypatch, False)
    text = test_client.get("/story").text
    assert 'href="/home#demo"' not in text
    assert 'href="/home#demo-step-1"' not in text
    assert 'href="/home#demo-step-4"' not in text
    assert 'href="/home#demo-step-5"' not in text
    assert 'href="/operator"' in text
    assert 'href="/guide/use"' in text
    assert "실제 이용 과정은 시연에서." in text
    assert _KAKAO in text


def test_story_changes_summarizes_counts_and_major_changes(test_client):
    from services.change_summary import change_summary
    from services.field_changes import guide_rows

    rows = guide_rows()
    summary = change_summary()
    assert summary["total"] == len(rows) == 41
    assert summary["applied"] == sum(1 for row in rows if row["applied"]) == 36
    assert summary["not_applied"] == 5
    assert sum(group["count"] for group in summary["groups"]) == 41

    page = test_client.get("/story/changes")
    assert page.status_code == 200
    text = page.text
    assert "<title>주요 변경 - 체험마을 AI사무장</title>" in text
    assert "전체 41건 가운데 적용 36건, 적용하지 않음 5건이다." in text
    for label in (
        "마을명 · 6건",
        "체험 추가 · 3건",
        "가격 · 19건",
        "운영 중지 · 4건",
        "예약 현황 · 1건",
        "체험 달력 · 1건",
        "단체 이름 · 1건",
        "체험 묶음 · 3건",
        "시연 · 1건",
        "적용하지 않은 나머지 · 2건",
    ):
        assert label in text
    assert "화면 이름을 도선국사마을로 보여 주고" in text
    assert "가격표의 천연염색 세 가지를 목록 뒤에 붙인다." in text
    assert "프로그램 목록과 같은 체험을 한 줄로 보고" in text
    assert "담당 카드에서 이름을 찾아 더한다." in text
    assert "1인 금액을 체험객 화면에 보이고" in text
    assert "오픈빌더에 주 이동 버튼을 넣지 않았다." in text
    assert text.count('href="/guide/name-requests"') == len(summary["groups"])
    for sentence in (
        "카카오 채널 하나에서 체험객과 사무장을 나눈다.",
        "챗봇이 먼저 알림을 보내지 않는다.",
        "마을 추천에 한 줄 이유를 붙인다.",
        "사무장이 확인한 뒤에 마을 화면에 공개한다.",
        "지금 하지 않는 체험만 사무장이 중지한다.",
        "체험 달력은 단체와 인원이고, 승인은 사무장만 한다.",
        "한 담당이 여러 체험을 맡는다.",
        "사무장이 내 마을에서 체험을 묶어 옮긴다.",
        "발표에서 한 계정으로 체험객, 사무장, 체험 담당을 바꾼다.",
        "채널 QR을 보여 준다.",
        "전국 농촌여행 포털을 대신하지 않는다.",
        "광주·전남 마을의 예약과 홍보를 맡는다.",
    ):
        assert sentence in text
    assert "감수확" not in text
    assert "10,000원" not in text
    assert "천연염색(에코백)" not in text
    assert "FR-" not in text
    assert "v2." not in text
    assert 'href="/story#changes"' in text
    sitemap = test_client.get("/sitemap.xml").text
    assert "https://chonmuseojang.vercel.app/story/changes" in sitemap
    assert "/guide/name-requests" not in sitemap
    for token in _FORBIDDEN:
        assert token not in text


def test_root_opens_brand_page(test_client):
    redirect = test_client.get("/", follow_redirects=False)
    assert redirect.status_code == 302
    assert redirect.headers["location"] == "/brand"
    page = test_client.get("/")
    assert page.status_code == 200
    assert "익숙한 카카오에서" in page.text


def test_home_stays_on_its_own_stylesheet(test_client, monkeypatch):
    _presentation(monkeypatch, True)
    home = test_client.get("/home")
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
    assert 'href="/find"' in home.text
    assert 'id="village-finder"' not in home.text
    assert 'id="sigungu-filter"' not in home.text
    assert "<h2>체험객</h2>" in home.text
    assert "<h2>사무장</h2>" in home.text
    find = test_client.get("/find")
    assert find.status_code == 200
    assert 'id="village-finder"' in find.text
    assert 'id="sigungu-filter"' in find.text
    assert "광주·전남 농촌체험마을" in find.text
    sitemap = test_client.get("/sitemap.xml").text
    assert "https://chonmuseojang.vercel.app/home" in sitemap
    assert "https://chonmuseojang.vercel.app/find" in sitemap
    assert "https://chonmuseojang.vercel.app/brand" in sitemap
    assert "https://chonmuseojang.vercel.app/story" in sitemap
    assert "/operator" not in sitemap
    assert "/calendar/" not in sitemap
