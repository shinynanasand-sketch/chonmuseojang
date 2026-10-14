"""FR-11: 홍보문구는 담당 마을만 프롬프트에 넣고 contents에 저장한다."""

from services.operator_assistant import save_operator_contents
from services.supabase_client import insert_content, upsert_villages

_AUTH = {"Authorization": "Bearer owner_v001"}


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


class _FakeLLM:
    def __init__(self, text: str):
        self.text = text
        self.prompts: list[str] = []

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        self.prompts.append(f"{system_prompt}\n{user_prompt}")
        return self.text


def test_promo_draft_uses_openai(monkeypatch):
    _seed_two_villages()
    llm = _FakeLLM("소개글: 가을 갯벌\nSNS홍보문구: 갯벌 체험 오세요")
    names = []

    def get(name=None):
        names.append(name)
        return llm

    monkeypatch.setattr("services.operator_assistant.get_llm_provider", get)
    result = save_operator_contents(
        {"operator_id": 1, "village_id": "V001"},
        "가을에 조개를 잡아요",
    )

    assert result["saved"] is True
    assert names == ["openai"]


def test_prompt_contains_only_the_operator_village(monkeypatch):
    _seed_two_villages()
    llm = _FakeLLM("소개글: 가을 갯벌\nSNS홍보문구: 갯벌 체험 오세요")
    monkeypatch.setattr("services.operator_assistant.get_llm_provider", lambda name=None: llm)

    result = save_operator_contents(
        {"operator_id": 1, "village_id": "V001"},
        "가을에 조개를 잡아요",
    )

    assert result["saved"] is True
    assert llm.prompts
    prompt = "\n".join(llm.prompts)
    assert "갯벌마을" in prompt
    assert "무등마을" not in prompt
    assert "농사체험" not in prompt


def test_saved_contents_stay_on_operator_village(test_client, monkeypatch):
    _seed_two_villages()
    llm = _FakeLLM("소개글: 가을 갯벌\nSNS홍보문구: 갯벌 체험 오세요")
    monkeypatch.setattr("services.operator_assistant.get_llm_provider", lambda name=None: llm)
    insert_content(
        {
            "village_id": "V002",
            "operator_id": 2,
            "content_type": "소개글",
            "body": "무등 비밀",
        }
    )

    created = test_client.post(
        "/api/operator/contents",
        headers=_AUTH,
        json={"description": "가을에 조개를 잡아요"},
    )
    assert created.status_code == 200
    assert created.json()["saved"] is True

    listed = test_client.get("/api/operator/contents", headers=_AUTH)
    assert listed.status_code == 200
    rows = listed.json()["contents"]
    assert rows
    assert {row["village_id"] for row in rows} == {"V001"}
    assert {row["content_type"] for row in rows} == {"소개글", "SNS홍보문구"}
    assert "무등 비밀" not in listed.text


def test_other_village_id_in_body_is_forbidden(test_client):
    response = test_client.post(
        "/api/operator/contents",
        headers=_AUTH,
        json={"description": "가을에 조개를 잡아요", "village_id": "V002"},
    )
    assert response.status_code == 403


def test_blank_description_is_rejected(test_client):
    response = test_client.post(
        "/api/operator/contents",
        headers=_AUTH,
        json={"description": "  "},
    )
    assert response.status_code == 400
    listed = test_client.get("/api/operator/contents", headers=_AUTH)
    assert listed.status_code == 200
    assert listed.json()["contents"] == []


def test_empty_llm_text_does_not_save(test_client, monkeypatch):
    _seed_two_villages()
    monkeypatch.setattr(
        "services.operator_assistant.get_llm_provider",
        lambda name=None: _FakeLLM(""),
    )
    response = test_client.post(
        "/api/operator/contents",
        headers=_AUTH,
        json={"description": "가을에 조개를 잡아요"},
    )
    assert response.status_code == 200
    assert response.json()["saved"] is False
    listed = test_client.get("/api/operator/contents", headers=_AUTH)
    assert listed.json()["contents"] == []


def test_operator_page_has_description_field(test_client):
    html = test_client.get("/operator").text
    assert 'name="description"' in html
    assert 'name="photo"' in html
    assert 'type="file"' in html
    assert "홍보문구를 만들고 있습니다" in html


def test_prompt_asks_for_a_longer_intro(monkeypatch):
    _seed_two_villages()
    llm = _FakeLLM("소개글: 가을 갯벌\nSNS홍보문구: 갯벌 체험 오세요")
    monkeypatch.setattr("services.operator_assistant.get_llm_provider", lambda name=None: llm)

    save_operator_contents(
        {"operator_id": 1, "village_id": "V001"},
        "가을에 조개를 잡아요",
    )

    prompt = "\n".join(llm.prompts)
    assert "4문장" in prompt
    assert "400" in prompt
    assert "120" in prompt
    assert "가격" in prompt
    assert "전화번호" in prompt
    assert "두 줄로만" not in prompt


def test_text_without_photo_leaves_photo_url_empty(test_client, monkeypatch):
    _seed_two_villages()
    monkeypatch.setattr(
        "services.operator_assistant.get_llm_provider",
        lambda name=None: _FakeLLM("소개글: 가을 갯벌\nSNS홍보문구: 갯벌 체험 오세요"),
    )

    created = test_client.post(
        "/api/operator/contents",
        headers=_AUTH,
        json={"description": "가을에 조개를 잡아요"},
    )
    assert created.status_code == 200
    rows = test_client.get("/api/operator/contents", headers=_AUTH).json()["contents"]
    assert rows
    assert all(not row.get("photo_url") for row in rows)


_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


def test_photo_url_uses_the_operator_village(test_client, monkeypatch):
    _seed_two_villages()
    monkeypatch.setattr(
        "services.operator_assistant.get_llm_provider",
        lambda name=None: _FakeLLM("소개글: 가을 갯벌\nSNS홍보문구: 갯벌 체험 오세요"),
    )
    seen = {}

    def store(village_id, data):
        seen["village_id"] = village_id
        seen["size"] = len(data)
        return f"https://example.test/content-photos/{village_id}/a.png"

    monkeypatch.setattr("services.operator_assistant.store_content_photo", store)
    created = test_client.post(
        "/api/operator/contents",
        headers=_AUTH,
        data={"description": "가을에 조개를 잡아요"},
        files={"photo": ("mud.png", _PNG, "image/png")},
    )
    assert created.status_code == 200
    assert created.json()["saved"] is True
    assert seen == {"village_id": "V001", "size": len(_PNG)}
    rows = test_client.get("/api/operator/contents", headers=_AUTH).json()["contents"]
    assert {row["photo_url"] for row in rows} == {"https://example.test/content-photos/V001/a.png"}
    assert {row["village_id"] for row in rows} == {"V001"}


def test_other_village_id_in_form_is_forbidden(test_client, monkeypatch):
    _seed_two_villages()
    monkeypatch.setattr(
        "services.operator_assistant.get_llm_provider",
        lambda name=None: _FakeLLM("소개글: 가을 갯벌\nSNS홍보문구: 갯벌 체험 오세요"),
    )
    response = test_client.post(
        "/api/operator/contents",
        headers=_AUTH,
        data={"description": "가을에 조개를 잡아요", "village_id": "V002"},
        files={"photo": ("mud.png", _PNG, "image/png")},
    )
    assert response.status_code == 403
    listed = test_client.get("/api/operator/contents", headers=_AUTH)
    assert listed.json()["contents"] == []


def test_non_image_is_rejected(test_client, monkeypatch):
    _seed_two_villages()
    monkeypatch.setattr(
        "services.operator_assistant.get_llm_provider",
        lambda name=None: _FakeLLM("소개글: 가을 갯벌\nSNS홍보문구: 갯벌 체험 오세요"),
    )
    response = test_client.post(
        "/api/operator/contents",
        headers=_AUTH,
        data={"description": "가을에 조개를 잡아요"},
        files={"photo": ("note.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 400
    assert test_client.get("/api/operator/contents", headers=_AUTH).json()["contents"] == []


def test_photo_over_two_megabytes_is_rejected(test_client, monkeypatch):
    _seed_two_villages()
    monkeypatch.setattr(
        "services.operator_assistant.get_llm_provider",
        lambda name=None: _FakeLLM("소개글: 가을 갯벌\nSNS홍보문구: 갯벌 체험 오세요"),
    )
    called = {"store": False}

    def store(_village_id, _data):
        called["store"] = True
        return "https://example.test/content-photos/V001/a.jpg"

    monkeypatch.setattr("services.operator_assistant.store_content_photo", store)
    blob = b"\xff\xd8\xff" + b"\x00" * (2 * 1024 * 1024)
    response = test_client.post(
        "/api/operator/contents",
        headers=_AUTH,
        data={"description": "가을에 조개를 잡아요"},
        files={"photo": ("big.jpg", blob, "image/jpeg")},
    )
    assert response.status_code == 400
    assert called["store"] is False
    assert test_client.get("/api/operator/contents", headers=_AUTH).json()["contents"] == []


def test_photo_upload_failure_does_not_save_text(test_client, monkeypatch):
    _seed_two_villages()
    monkeypatch.setattr(
        "services.operator_assistant.get_llm_provider",
        lambda name=None: _FakeLLM("소개글: 가을 갯벌\nSNS홍보문구: 갯벌 체험 오세요"),
    )

    def store(_village_id, _data):
        raise RuntimeError("upload")

    monkeypatch.setattr("services.operator_assistant.store_content_photo", store)
    response = test_client.post(
        "/api/operator/contents",
        headers=_AUTH,
        data={"description": "가을에 조개를 잡아요"},
        files={"photo": ("mud.png", _PNG, "image/png")},
    )
    assert response.status_code == 200
    assert response.json()["saved"] is False
    assert test_client.get("/api/operator/contents", headers=_AUTH).json()["contents"] == []


def test_long_draft_is_clipped(monkeypatch):
    _seed_two_villages()
    intro = "가을에 조개를 잡습니다. " * 30
    sns = "조개 잡으러 오세요. " * 20
    monkeypatch.setattr(
        "services.operator_assistant.get_llm_provider",
        lambda name=None: _FakeLLM(f"소개글: {intro}\nSNS홍보문구: {sns}"),
    )

    result = save_operator_contents(
        {"operator_id": 1, "village_id": "V001"},
        "가을에 조개를 잡아요",
    )

    bodies = {row["content_type"]: row["body"] for row in result["contents"]}
    assert len(bodies["소개글"]) <= 400
    assert len(bodies["SNS홍보문구"]) <= 120
    assert "조개" in bodies["소개글"]
