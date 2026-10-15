"""카카오 홍보 사진은 담당 마을 소개글·SNS 초안만 저장한다."""

from services.operator_assistant import PHOTO_LLM_TIMEOUT
from services.supabase_client import list_contents, list_reviews, upsert_villages

_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
_JPEG = b"\xff\xd8\xff" + b"\x00" * 16
_SECURE = "https://t1.kakaocdn.net/secure.jpg"
_MEDIA = "https://t1.kakaocdn.net/media.jpg"
_UTTERANCE = "https://t1.kakaocdn.net/utterance.jpg"
_DRAFT = "소개글: 가을 갯벌\nSNS홍보문구: 갯벌 체험 오세요"
_OPERATOR = "kakao_owner_v001"
_CALLBACK = "https://bot-api.kakao.com/v2/bots/x/callback"


def _seed_two_villages():
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


def _skill_body(response):
    return response.json()


def _skill_text(response) -> str:
    return _skill_body(response)["template"]["outputs"][0]["simpleText"]["text"]


def _assert_simple_text(response):
    body = _skill_body(response)
    outputs = body["template"]["outputs"]
    assert response.status_code == 200
    assert "context" not in body
    assert len(outputs) == 1
    assert "simpleText" in outputs[0]
    assert "listCard" not in outputs[0]
    assert "listCard" not in response.text


def _post(test_client, *, user, utterance="", params=None, user_params=None, callback="", headers=None):
    user_request = {
        "utterance": utterance,
        "user": {"id": user},
        "params": user_params or {},
    }
    if callback:
        user_request["callbackUrl"] = callback
    return test_client.post(
        "/kakao/ask",
        headers=headers,
        json={
            "intent": {"name": "홍보 사진"},
            "userRequest": user_request,
            "action": {"params": params or {}},
        },
    )


def _capture_callback(monkeypatch):
    sent = []

    def post(url, body):
        sent.append((url, body))

    monkeypatch.setattr("routers.kakao.kakao_client.post_skill_callback", post)
    return sent


def _callback_text(sent) -> str:
    return sent[0][1]["template"]["outputs"][0]["simpleText"]["text"]


class _Vision:
    def __init__(self, text: str, fail: bool = False):
        self.text = text
        self.fail = fail
        self.calls = []

    def generate_with_image(self, system_prompt, user_prompt, image, media_type, timeout=30.0):
        self.calls.append(
            {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "image": image,
                "media_type": media_type,
                "timeout": timeout,
            }
        )
        if self.fail:
            raise TimeoutError("slow")
        return self.text


class _Stream:
    def __init__(self, chunks, status=200, headers=None):
        self.status_code = status
        self.headers = headers or {}
        self._chunks = chunks

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def iter_bytes(self):
        yield from self._chunks


class _Client:
    opened = []
    script = None

    def __init__(self, timeout=None, follow_redirects=None):
        self.timeout = timeout
        self.follow_redirects = follow_redirects
        self.urls = []
        _Client.opened.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def stream(self, method, url):
        self.urls.append((method, url))
        if _Client.script:
            status, headers, chunks = _Client.script.pop(0)
            return _Stream(chunks, status=status, headers=headers)
        return _Stream(_Client.payload)


def _install_download(monkeypatch, payload):
    _Client.opened = []
    _Client.payload = [payload]
    _Client.script = None
    monkeypatch.setattr("services.operator_assistant.httpx.Client", _Client)


def _install_vision(monkeypatch, vision, stored):
    monkeypatch.setattr("services.operator_assistant.get_llm_provider", lambda name=None: vision)

    def store(village_id, data):
        stored.append((village_id, data))
        return f"https://example.test/content-photos/{village_id}/a.png"

    monkeypatch.setattr("services.operator_assistant.store_content_photo", store)


def test_operator_photo_saves_own_village_draft(test_client, monkeypatch):
    _seed_two_villages()
    vision = _Vision(_DRAFT)
    stored = []
    sent = _capture_callback(monkeypatch)
    _install_download(monkeypatch, _PNG)
    _install_vision(monkeypatch, vision, stored)

    response = _post(
        test_client,
        user=_OPERATOR,
        utterance=_UTTERANCE,
        callback=_CALLBACK,
        params={"village_id": "V002", "secureimage": '{"secureUrls":["%s","https://t1.kakaocdn.net/second.jpg"]}' % _SECURE},
        user_params={"media": {"type": "image", "url": _MEDIA}},
    )

    assert response.status_code == 200
    assert response.json() == {"version": "2.0", "useCallback": True}
    assert "template" not in response.json()
    assert "context" not in response.text
    assert sent[0][0] == _CALLBACK
    text = _callback_text(sent)
    assert "simpleText" in sent[0][1]["template"]["outputs"][0]
    assert "listCard" not in sent[0][1]["template"]["outputs"][0]
    assert "context" not in sent[0][1]
    assert "가을 갯벌" in text
    assert "갯벌 체험 오세요" in text
    assert "웹에서 관광객에게 공개를 누르면 마을 화면에 나갑니다." in text
    assert _Client.opened[0].urls == [("GET", _SECURE)]
    assert _Client.opened[0].timeout == 10.0
    assert _Client.opened[0].follow_redirects is False
    assert stored == [("V001", _PNG)]
    rows = list_contents(village_id="V001")
    assert {row["content_type"] for row in rows} == {"소개글", "SNS홍보문구"}
    assert {row["village_id"] for row in rows} == {"V001"}
    assert {row["photo_url"] for row in rows} == {"https://example.test/content-photos/V001/a.png"}
    assert all(row.get("is_public") is False for row in rows)
    assert list_contents(village_id="V002") == []
    assert list_reviews(village_id="V001") == []
    assert list_reviews(village_id="V002") == []
    prompt = vision.calls[0]["system_prompt"] + vision.calls[0]["user_prompt"]
    assert "갯벌마을" in prompt
    assert "무등마을" not in prompt
    assert "가격" in prompt
    assert "전화번호" in prompt
    assert vision.calls[0]["image"] == _PNG
    assert vision.calls[0]["media_type"] == "image/png"
    assert vision.calls[0]["timeout"] == PHOTO_LLM_TIMEOUT
    assert PHOTO_LLM_TIMEOUT == 15.0
    assert "kakaocdn" not in text


def test_kakao_redirect_is_followed_and_saved(test_client, monkeypatch):
    _seed_two_villages()
    vision = _Vision(_DRAFT)
    stored = []
    sent = _capture_callback(monkeypatch)
    _install_download(monkeypatch, _PNG)
    _install_vision(monkeypatch, vision, stored)
    landed = "https://t1.kakaocdn.net/landed.jpg"
    _Client.script = [
        (302, {"location": landed}, []),
        (200, {}, [_PNG]),
    ]
    start = "https://t1.kakaocdn.net/start.jpg"

    response = _post(test_client, user=_OPERATOR, utterance=start, callback=_CALLBACK)

    assert response.json() == {"version": "2.0", "useCallback": True}
    assert "template" not in response.json()
    assert _Client.opened[0].timeout == 10.0
    assert _Client.opened[0].follow_redirects is False
    assert _Client.opened[0].urls == [("GET", start), ("GET", landed)]
    assert stored == [("V001", _PNG)]
    rows = list_contents(village_id="V001")
    assert {row["content_type"] for row in rows} == {"소개글", "SNS홍보문구"}
    assert all(row.get("is_public") is False for row in rows)
    assert "가을 갯벌" in _callback_text(sent)


def test_redirect_off_kakao_is_not_saved(test_client, monkeypatch):
    _seed_two_villages()
    vision = _Vision(_DRAFT)
    stored = []
    sent = _capture_callback(monkeypatch)
    _install_download(monkeypatch, _PNG)
    _install_vision(monkeypatch, vision, stored)
    start = "https://t1.kakaocdn.net/start.jpg"
    _Client.script = [
        (302, {"location": "https://169.254.169.254/latest/meta-data"}, []),
    ]

    response = _post(test_client, user=_OPERATOR, utterance=start, callback=_CALLBACK)

    assert response.json()["useCallback"] is True
    assert "template" not in response.json()
    assert _Client.opened[0].urls == [("GET", start)]
    assert "사진을 한 장 올려 주세요." in _callback_text(sent)
    assert stored == []
    assert vision.calls == []
    assert list_contents(village_id="V001") == []


def test_media_url_and_utterance_are_used_in_order(test_client, monkeypatch):
    _seed_two_villages()
    vision = _Vision(_DRAFT)
    _capture_callback(monkeypatch)
    _install_download(monkeypatch, _PNG)
    _install_vision(monkeypatch, vision, [])
    media = _post(
        test_client,
        user=_OPERATOR,
        utterance=_UTTERANCE,
        callback=_CALLBACK,
        user_params={"media": {"type": "image", "url": _MEDIA}},
    )
    assert media.json()["useCallback"] is True
    assert _Client.opened[-1].urls == [("GET", _MEDIA)]

    spoken = _post(test_client, user=_OPERATOR, utterance=_UTTERANCE, callback=_CALLBACK)
    assert spoken.json()["useCallback"] is True
    assert _Client.opened[-1].urls == [("GET", _UTTERANCE)]


def test_secure_urls_list_string_uses_the_first_https_address():
    from models.kakao_schemas import KakaoSkillRequest
    from services.kakao_params import kakao_photo_url

    payload = KakaoSkillRequest.model_validate(
        {
            "intent": {"name": "홍보 사진"},
            "action": {
                "params": {
                    "secureimage": '{"secureUrls":"List(https://t1.kakaocdn.net/1.jpg, https://t1.kakaocdn.net/2.jpg)"}'
                }
            },
        }
    )
    assert kakao_photo_url(payload) == "https://t1.kakaocdn.net/1.jpg"


_PLUGIN_HTTP = (
    "http://secure.kakaocdn.net/dna/O5UOr/K6auLPnoAf/XXX/img.jpg"
    "?credential=abc&signature=d%3D"
)


def _plugin_body(url: str) -> str:
    return (
        '{"privacyAgreement":"Y","imageQuantity":"1","secureUrls":"List(%s)"}' % url
    )


def test_secureimage_plugin_http_list_is_the_photo_url():
    from models.kakao_schemas import KakaoSkillRequest
    from services.kakao_params import kakao_photo_url

    raw = _plugin_body(_PLUGIN_HTTP)
    payload = KakaoSkillRequest.model_validate(
        {
            "intent": {"name": "홍보 사진"},
            "action": {
                "params": {"secureimage": raw},
                "detailParams": {
                    "secureimage": {
                        "origin": "List(%s)" % _PLUGIN_HTTP,
                        "value": raw,
                        "groupName": "",
                    }
                },
            },
        }
    )
    assert kakao_photo_url(payload) == _PLUGIN_HTTP


def test_plugin_http_photo_is_downloaded_for_operator(test_client, monkeypatch):
    _seed_two_villages()
    vision = _Vision(_DRAFT)
    stored = []
    sent = _capture_callback(monkeypatch)
    _install_download(monkeypatch, _PNG)
    _install_vision(monkeypatch, vision, stored)

    response = _post(
        test_client,
        user=_OPERATOR,
        utterance="사진을 보냈습니다",
        callback=_CALLBACK,
        params={"secureimage": _plugin_body(_PLUGIN_HTTP)},
    )

    assert response.json() == {"version": "2.0", "useCallback": True}
    assert _Client.opened[0].urls[0] == ("GET", _PLUGIN_HTTP)
    assert stored == [("V001", _PNG)]
    assert "가을 갯벌" in _callback_text(sent)
    assert list_contents(village_id="V002") == []


def test_plugin_http_off_kakao_is_not_downloaded(test_client, monkeypatch):
    _seed_two_villages()
    _install_download(monkeypatch, _PNG)
    response = _post(
        test_client,
        user=_OPERATOR,
        utterance="사진을 보냈습니다",
        callback=_CALLBACK,
        params={"secureimage": _plugin_body("http://169.254.169.254/latest/meta-data")},
    )
    _assert_simple_text(response)
    assert "사진을 한 장 올려 주세요." in _skill_text(response)
    assert _Client.opened == []
    assert list_contents(village_id="V001") == []


def test_guest_photo_gets_register_hint_without_save(test_client, monkeypatch):
    _seed_two_villages()
    _install_download(monkeypatch, _PNG)
    response = _post(test_client, user="tourist-photo", utterance=_UTTERANCE, callback=_CALLBACK)
    _assert_simple_text(response)
    assert "useCallback" not in response.json()
    assert "등록" in _skill_text(response)
    assert _Client.opened == []
    assert list_contents(village_id="V001") == []
    assert list_reviews(village_id="V001") == []


def test_missing_photo_guides_without_save(test_client, monkeypatch):
    _seed_two_villages()
    vision = _Vision(_DRAFT)
    monkeypatch.setattr("services.operator_assistant.get_llm_provider", lambda name=None: vision)
    response = _post(test_client, user=_OPERATOR, utterance="사진 올릴게요", callback=_CALLBACK)
    _assert_simple_text(response)
    assert "useCallback" not in response.json()
    assert "사진을 한 장 올려 주세요." in _skill_text(response)
    assert vision.calls == []
    assert list_contents(village_id="V001") == []


def test_photo_without_callback_returns_guide_without_download(test_client, monkeypatch):
    _seed_two_villages()
    _install_download(monkeypatch, _PNG)
    response = _post(test_client, user=_OPERATOR, utterance=_UTTERANCE)
    _assert_simple_text(response)
    assert "useCallback" not in response.json()
    assert "홍보문구를 만들지 못했습니다." in _skill_text(response)
    assert _Client.opened == []
    assert list_contents(village_id="V001") == []


def test_non_kakao_host_is_not_downloaded(test_client, monkeypatch):
    _seed_two_villages()
    _install_download(monkeypatch, _PNG)
    response = _post(test_client, user=_OPERATOR, utterance="https://169.254.169.254/latest/meta-data")
    _assert_simple_text(response)
    assert "사진을 한 장 올려 주세요." in _skill_text(response)
    assert _Client.opened == []
    assert list_contents(village_id="V001") == []


def _large_jpeg() -> bytes:
    import io
    import os

    from PIL import Image

    side = 1800
    image = Image.frombytes("RGB", (side, side), os.urandom(side * side * 3))
    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=95)
    return buf.getvalue()


def test_large_jpeg_is_shrunk_before_save(test_client, monkeypatch):
    _seed_two_villages()
    photo = _large_jpeg()
    assert 2 * 1024 * 1024 < len(photo) < 8 * 1024 * 1024
    vision = _Vision(_DRAFT)
    stored = []
    sent = _capture_callback(monkeypatch)
    _install_download(monkeypatch, photo)
    _install_vision(monkeypatch, vision, stored)

    response = _post(test_client, user=_OPERATOR, utterance=_UTTERANCE, callback=_CALLBACK)

    assert response.json()["useCallback"] is True
    assert stored[0][0] == "V001"
    saved = stored[0][1]
    assert saved.startswith(b"\xff\xd8\xff")
    assert len(saved) <= 2 * 1024 * 1024
    assert vision.calls[0]["image"] == saved
    assert vision.calls[0]["media_type"] == "image/jpeg"
    assert "가을 갯벌" in _callback_text(sent)
    rows = list_contents(village_id="V001")
    assert {row["content_type"] for row in rows} == {"소개글", "SNS홍보문구"}
    assert list_contents(village_id="V002") == []
    assert list_reviews(village_id="V001") == []


def test_oversize_and_non_image_are_rejected(test_client, monkeypatch):
    _seed_two_villages()
    vision = _Vision(_DRAFT)
    stored = []
    sent = _capture_callback(monkeypatch)
    _install_vision(monkeypatch, vision, stored)
    _install_download(monkeypatch, _JPEG + b"a" * (8 * 1024 * 1024))
    huge = _post(test_client, user=_OPERATOR, utterance=_UTTERANCE, callback=_CALLBACK)
    assert huge.json()["useCallback"] is True
    assert "8MB" in _callback_text(sent)

    _install_download(monkeypatch, b"hello")
    wrong = _post(test_client, user=_OPERATOR, utterance=_UTTERANCE, callback=_CALLBACK)
    assert wrong.json()["useCallback"] is True
    assert "jpeg, png, webp" in _callback_text(sent[-1:])
    assert stored == []
    assert vision.calls == []
    assert list_contents(village_id="V001") == []


def test_llm_failure_does_not_save(test_client, monkeypatch):
    _seed_two_villages()
    vision = _Vision("", fail=True)
    stored = []
    sent = _capture_callback(monkeypatch)
    _install_download(monkeypatch, _PNG)
    _install_vision(monkeypatch, vision, stored)
    response = _post(test_client, user=_OPERATOR, utterance=_UTTERANCE, callback=_CALLBACK)
    assert response.json()["useCallback"] is True
    assert "template" not in response.json()
    assert "홍보문구를 만들지 못했습니다." in _callback_text(sent)
    assert stored == []
    assert list_contents(village_id="V001") == []
    assert list_reviews(village_id="V001") == []
