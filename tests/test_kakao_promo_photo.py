"""카카오 홍보 사진은 담당 마을 소개글·SNS 초안만 저장한다."""

import httpx

from services.recommend import KAKAO_LLM_TIMEOUT
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


def _capture_schedule(monkeypatch):
    scheduled = []

    def schedule(base_url, body):
        scheduled.append((base_url, body))

    monkeypatch.setattr("routers.kakao.schedule_photo_draft", schedule)
    return scheduled


def _capture_callback(monkeypatch):
    sent = []

    def post(url, body):
        sent.append((url, body))

    monkeypatch.setattr("routers.kakao.kakao_client.post_skill_callback", post)
    return sent


def _callback_text(sent) -> str:
    return sent[0][1]["template"]["outputs"][0]["simpleText"]["text"]


def _run_scheduled(test_client, scheduled):
    return test_client.post("/kakao/photo-draft", json=scheduled[0][1])


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
    scheduled = _capture_schedule(monkeypatch)
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
    assert list_contents(village_id="V001") == []
    assert _Client.opened == []
    assert scheduled[0][1]["userRequest"]["callbackUrl"] == _CALLBACK

    job = _run_scheduled(test_client, scheduled)
    assert job.status_code == 200
    assert sent[0][0] == _CALLBACK
    text = _callback_text(sent)
    assert "simpleText" in sent[0][1]["template"]["outputs"][0]
    assert "listCard" not in sent[0][1]["template"]["outputs"][0]
    assert "context" not in sent[0][1]
    assert "가을 갯벌" in text
    assert "갯벌 체험 오세요" in text
    assert "웹에서 관광객에게 공개를 누르면 마을 화면에 나갑니다." in text
    assert _Client.opened[0].urls == [("GET", _SECURE)]
    assert _Client.opened[0].timeout == 4.0
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
    assert vision.calls[0]["timeout"] == KAKAO_LLM_TIMEOUT
    assert "kakaocdn" not in text


def test_kakao_redirect_is_followed_and_saved(test_client, monkeypatch):
    _seed_two_villages()
    vision = _Vision(_DRAFT)
    stored = []
    scheduled = _capture_schedule(monkeypatch)
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
    _run_scheduled(test_client, scheduled)
    assert _Client.opened[0].timeout == 4.0
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
    scheduled = _capture_schedule(monkeypatch)
    sent = _capture_callback(monkeypatch)
    _install_download(monkeypatch, _PNG)
    _install_vision(monkeypatch, vision, stored)
    start = "https://t1.kakaocdn.net/start.jpg"
    _Client.script = [
        (302, {"location": "https://169.254.169.254/latest/meta-data"}, []),
    ]

    response = _post(test_client, user=_OPERATOR, utterance=start, callback=_CALLBACK)

    assert response.json()["useCallback"] is True
    _run_scheduled(test_client, scheduled)
    assert _Client.opened[0].urls == [("GET", start)]
    assert "사진을 한 장 올려 주세요." in _callback_text(sent)
    assert stored == []
    assert vision.calls == []
    assert list_contents(village_id="V001") == []


def test_media_url_and_utterance_are_used_in_order(test_client, monkeypatch):
    _seed_two_villages()
    vision = _Vision(_DRAFT)
    scheduled = _capture_schedule(monkeypatch)
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
    _run_scheduled(test_client, scheduled)
    assert _Client.opened[-1].urls == [("GET", _MEDIA)]

    spoken = _post(test_client, user=_OPERATOR, utterance=_UTTERANCE, callback=_CALLBACK)
    assert spoken.json()["useCallback"] is True
    _run_scheduled(test_client, scheduled[-1:])
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


def test_guest_photo_gets_register_hint_without_save(test_client, monkeypatch):
    _seed_two_villages()
    scheduled = _capture_schedule(monkeypatch)
    _install_download(monkeypatch, _PNG)
    response = _post(test_client, user="tourist-photo", utterance=_UTTERANCE, callback=_CALLBACK)
    _assert_simple_text(response)
    assert "useCallback" not in response.json()
    assert "등록" in _skill_text(response)
    assert scheduled == []
    assert _Client.opened == []
    assert list_contents(village_id="V001") == []
    assert list_reviews(village_id="V001") == []


def test_missing_photo_guides_without_save(test_client, monkeypatch):
    _seed_two_villages()
    vision = _Vision(_DRAFT)
    scheduled = _capture_schedule(monkeypatch)
    monkeypatch.setattr("services.operator_assistant.get_llm_provider", lambda name=None: vision)
    response = _post(test_client, user=_OPERATOR, utterance="사진 올릴게요", callback=_CALLBACK)
    _assert_simple_text(response)
    assert "useCallback" not in response.json()
    assert "사진을 한 장 올려 주세요." in _skill_text(response)
    assert scheduled == []
    assert vision.calls == []
    assert list_contents(village_id="V001") == []


def test_photo_without_callback_returns_guide_without_download(test_client, monkeypatch):
    _seed_two_villages()
    scheduled = _capture_schedule(monkeypatch)
    _install_download(monkeypatch, _PNG)
    response = _post(test_client, user=_OPERATOR, utterance=_UTTERANCE)
    _assert_simple_text(response)
    assert "useCallback" not in response.json()
    assert "홍보문구를 만들지 못했습니다." in _skill_text(response)
    assert scheduled == []
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


def test_oversize_and_non_image_are_rejected(test_client, monkeypatch):
    _seed_two_villages()
    vision = _Vision(_DRAFT)
    stored = []
    scheduled = _capture_schedule(monkeypatch)
    sent = _capture_callback(monkeypatch)
    _install_vision(monkeypatch, vision, stored)
    _install_download(monkeypatch, _JPEG + b"a" * (2 * 1024 * 1024))
    huge = _post(test_client, user=_OPERATOR, utterance=_UTTERANCE, callback=_CALLBACK)
    assert huge.json()["useCallback"] is True
    _run_scheduled(test_client, scheduled)
    assert "2MB" in _callback_text(sent)

    _install_download(monkeypatch, b"hello")
    wrong = _post(test_client, user=_OPERATOR, utterance=_UTTERANCE, callback=_CALLBACK)
    assert wrong.json()["useCallback"] is True
    _run_scheduled(test_client, scheduled[-1:])
    assert "jpeg, png, webp" in _callback_text(sent[-1:])
    assert stored == []
    assert vision.calls == []
    assert list_contents(village_id="V001") == []


def _forwarded(proto):
    return {"x-forwarded-proto": proto, "x-forwarded-host": "chonmuseojang.vercel.app"}


def _assert_draft_timeout(timeout):
    assert timeout.connect == 2.0
    assert timeout.write == 2.0
    assert timeout.read == 1.0


def test_forwarded_https_posts_before_callback_ack(test_client, monkeypatch):
    calls = []

    def post(url, json=None, timeout=None, follow_redirects=True):
        calls.append(
            {
                "url": url,
                "json": json,
                "timeout": timeout,
                "follow_redirects": follow_redirects,
            }
        )
        return httpx.Response(200)

    monkeypatch.setattr("routers.kakao.httpx.post", post)
    response = _post(
        test_client,
        user=_OPERATOR,
        utterance=_UTTERANCE,
        callback=_CALLBACK,
        headers=_forwarded("https"),
    )

    assert len(calls) == 1
    assert response.json() == {"version": "2.0", "useCallback": True}
    assert calls[0]["url"] == "https://chonmuseojang.vercel.app/kakao/photo-draft"
    assert calls[0]["json"]["userRequest"]["callbackUrl"] == _CALLBACK
    assert calls[0]["follow_redirects"] is False
    _assert_draft_timeout(calls[0]["timeout"])


def test_read_timeout_still_returns_callback_ack(test_client, monkeypatch):
    calls = []

    def post(url, json=None, timeout=None, follow_redirects=True):
        calls.append(url)
        _assert_draft_timeout(timeout)
        raise httpx.ReadTimeout("sent")

    monkeypatch.setattr("routers.kakao.httpx.post", post)
    response = _post(
        test_client,
        user=_OPERATOR,
        utterance=_UTTERANCE,
        callback=_CALLBACK,
        headers=_forwarded("https"),
    )

    assert calls == ["https://chonmuseojang.vercel.app/kakao/photo-draft"]
    assert response.json() == {"version": "2.0", "useCallback": True}


def test_http_308_retries_https_with_the_same_body(test_client, monkeypatch):
    calls = []

    def post(url, json=None, timeout=None, follow_redirects=True):
        calls.append({"url": url, "json": json, "follow_redirects": follow_redirects, "timeout": timeout})
        if len(calls) == 1:
            return httpx.Response(
                308,
                headers={"location": "https://chonmuseojang.vercel.app/kakao/photo-draft"},
            )
        return httpx.Response(200)

    monkeypatch.setattr("routers.kakao.httpx.post", post)
    response = _post(
        test_client,
        user=_OPERATOR,
        utterance=_UTTERANCE,
        callback=_CALLBACK,
        headers=_forwarded("http"),
    )

    assert len(calls) == 2
    assert response.json() == {"version": "2.0", "useCallback": True}
    assert [item["url"] for item in calls] == [
        "http://chonmuseojang.vercel.app/kakao/photo-draft",
        "https://chonmuseojang.vercel.app/kakao/photo-draft",
    ]
    assert calls[0]["json"] == calls[1]["json"]
    assert calls[0]["json"]["userRequest"]["callbackUrl"] == _CALLBACK
    assert all(item["follow_redirects"] is False for item in calls)
    assert all(item["timeout"].read == 1.0 for item in calls)


def test_llm_failure_does_not_save(test_client, monkeypatch):
    _seed_two_villages()
    vision = _Vision("", fail=True)
    stored = []
    scheduled = _capture_schedule(monkeypatch)
    sent = _capture_callback(monkeypatch)
    _install_download(monkeypatch, _PNG)
    _install_vision(monkeypatch, vision, stored)
    response = _post(test_client, user=_OPERATOR, utterance=_UTTERANCE, callback=_CALLBACK)
    assert response.json()["useCallback"] is True
    _run_scheduled(test_client, scheduled)
    assert "홍보문구를 만들지 못했습니다." in _callback_text(sent)
    assert stored == []
    assert list_contents(village_id="V001") == []
    assert list_reviews(village_id="V001") == []
