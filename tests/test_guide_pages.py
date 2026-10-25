import pytest

from services.supabase_client import set_registration_code, upsert_villages

_PASSWORD = "guide-test-secret"
_CODE = "GX-8841"


def _put_village() -> None:
    row = {
        "village_id": "VGUIDE",
        "village_name": "안내코드마을",
        "sigungu": "신안군",
        "program_name": "안내체험",
        "registration_code": _CODE,
    }
    upsert_villages([row])
    set_registration_code("VGUIDE", _CODE, row)


@pytest.fixture
def guide_password(monkeypatch):
    monkeypatch.setenv("GUIDE_PASSWORD", _PASSWORD)


def test_register_page_hides_code_until_password(test_client, guide_password):
    _put_village()
    locked = test_client.get("/guide/register")
    assert locked.status_code == 200
    assert "안내코드마을" in locked.text
    assert "안내체험" in locked.text
    assert _CODE not in locked.text

    wrong = test_client.post("/guide/register", data={"password": "nope"})
    assert "비밀번호가 맞지 않습니다." in wrong.text
    assert _CODE not in wrong.text

    opened = test_client.post("/guide/register", data={"password": _PASSWORD})
    assert _CODE in opened.text
    assert "안내체험" in opened.text

    again = test_client.get("/guide/register")
    assert _CODE in again.text


def test_register_page_hides_rows_until_village_search(test_client, guide_password):
    _put_village()
    page = test_client.get("/guide/register")
    assert "마을 이름을 두 글자 이상 입력하면 후보가 나옵니다. 하나를 누르면 등록 문장이 아래에 나옵니다." in page.text
    assert 'id="village-search"' in page.text
    assert 'data-min-length="2"' in page.text
    assert "guide-register.js" in page.text
    assert 'data-village="안내코드마을"' in page.text
    assert 'data-program="안내체험"' in page.text
    assert 'id="village-picks"' in page.text
    assert 'id="registration-lines"' in page.text
    assert "등록 문장은 비밀번호를 맞춘 뒤에 나옵니다." in page.text
    assert "복사한 문장을 카카오톡 대화에 붙여 넣습니다." in page.text
    assert "맞는 마을이 없습니다." in page.text
    assert "guide-table" not in page.text
    assert _CODE not in page.text


def test_register_page_without_password_stays_closed(test_client, monkeypatch):
    monkeypatch.setenv("GUIDE_PASSWORD", "")
    _put_village()
    page = test_client.get("/guide/register")
    assert "관리자가 비밀번호를 아직 정하지 않았습니다." in page.text
    assert _CODE not in page.text
    posted = test_client.post("/guide/register", data={"password": _PASSWORD})
    assert _CODE not in posted.text


def test_use_page_explains_operator_buttons(test_client):
    page = test_client.get("/guide/use")
    assert page.status_code == 200
    assert "달력 열기" in page.text
    assert "예약 현황 조회" in page.text
    assert "체험 글 저장" in page.text
    assert "비밀번호" not in page.text


def test_operator_guide_buttons_open_cards(test_client, guide_password):
    from services.auth import register_operator

    _put_village()
    register_operator("guide_owner", "안내코드마을 GX-8841")
    response = test_client.post(
        "/kakao/ask",
        json={
            "intent": {"name": "등록 안내"},
            "userRequest": {"utterance": "등록 안내", "user": {"id": "guide_owner"}},
            "action": {"params": {}},
        },
    )
    body = response.json()
    labels = [item["label"] for item in body["template"]["quickReplies"]]
    assert labels[:4] == ["예약 현황 조회", "체험 달력 조회", "체험 글 조회", "홍보 사진"]
    assert labels[-2:] == ["등록 안내", "사용 안내"]
    buttons = body["template"]["outputs"][1]["basicCard"]["buttons"]
    assert [item["label"] for item in buttons] == ["등록 안내 열기", "사용 안내 열기"]
    assert "/guide/register" in buttons[0]["webLinkUrl"]
    assert "/guide/use" in buttons[1]["webLinkUrl"]
    assert body["template"]["outputs"][1]["basicCard"]["thumbnail"]["imageUrl"] == (
        "https://chonmuseojang.vercel.app/static/kakao-card.png"
    )
    assert "guide_owner" not in response.text


def test_tourist_reply_has_no_guide_buttons(test_client):
    response = test_client.post(
        "/kakao/ask",
        json={
            "intent": {"name": "체험 달력 조회"},
            "userRequest": {"utterance": "체험 달력 조회", "user": {"id": "guide_guest"}},
            "action": {"params": {}},
        },
    )
    labels = [item["label"] for item in response.json()["template"]["quickReplies"]]
    assert labels == ["마을 추천", "예약하기", "내 예약", "후기 보기"]
    assert "등록 안내" not in labels
    assert "등록 안내 열기" not in response.text


def test_failed_registration_includes_register_card(test_client):
    response = test_client.post(
        "/kakao/ask",
        json={
            "intent": {"name": "운영자 등록"},
            "userRequest": {"utterance": "없는마을 ZZ-000", "user": {"id": "guide_guest"}},
            "action": {"params": {}},
        },
    )
    labels = [item["label"] for item in response.json()["template"]["quickReplies"]]
    assert labels == ["마을 추천", "예약하기", "내 예약", "후기 보기"]
    text = response.text
    assert "등록 안내 열기" in text
    assert "/guide/register" in text
