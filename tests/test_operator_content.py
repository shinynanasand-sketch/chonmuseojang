"""FR-11: 홍보문구는 담당 마을만 프롬프트에 넣고 contents에 저장한다."""

import ast
from pathlib import Path

from services.operator_assistant import save_operator_contents
from services.supabase_client import insert_content, upsert_villages

_AUTH = {"Authorization": "Bearer owner_v001"}


def test_pillow_import_stays_inside_photo_processing():
    source = (
        Path(__file__).resolve().parents[1] / "services" / "operator_assistant.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == "PIL":
            raise AssertionError("Pillow는 사진 처리 함수 안에서만 불러온다.")
    fit = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "_fit_photo")
    imported = [
        child
        for child in ast.walk(fit)
        if isinstance(child, ast.ImportFrom) and child.module == "PIL"
    ]
    assert imported


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
    assert 'className = "promo-photo"' in html


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


def test_operator_can_edit_and_delete_own_copy(test_client):
    saved = insert_content(
        {"village_id": "V001", "content_type": "소개글", "body": "옛 소개", "is_public": True}
    )
    edited = test_client.patch(
        f"/api/operator/contents/{saved['content_id']}",
        headers=_AUTH,
        json={"body": "고친 소개"},
    )
    assert edited.status_code == 200
    assert edited.json()["content"]["body"] == "고친 소개"
    assert edited.json()["content"]["is_public"] is True

    removed = test_client.delete(
        f"/api/operator/contents/{saved['content_id']}",
        headers=_AUTH,
    )
    assert removed.status_code == 200
    listed = test_client.get("/api/operator/contents", headers=_AUTH)
    assert listed.json()["contents"] == []


def test_edit_other_village_content_is_forbidden(test_client):
    saved = insert_content(
        {"village_id": "V002", "content_type": "소개글", "body": "무등 소개"}
    )
    response = test_client.patch(
        f"/api/operator/contents/{saved['content_id']}",
        headers=_AUTH,
        json={"body": "침입"},
    )
    assert response.status_code == 403
    kept = test_client.get(
        "/api/operator/contents",
        headers={"Authorization": "Bearer owner_v002"},
    )
    assert kept.json()["contents"][0]["body"] == "무등 소개"


def test_empty_and_long_edits_are_rejected(test_client):
    saved = insert_content(
        {"village_id": "V001", "content_type": "소개글", "body": "옛 소개"}
    )
    empty = test_client.patch(
        f"/api/operator/contents/{saved['content_id']}",
        headers=_AUTH,
        json={"body": "   "},
    )
    assert empty.status_code == 400
    too_long = test_client.patch(
        f"/api/operator/contents/{saved['content_id']}",
        headers=_AUTH,
        json={"body": "가" * 401},
    )
    assert too_long.status_code == 400
    listed = test_client.get("/api/operator/contents", headers=_AUTH)
    assert listed.json()["contents"][0]["body"] == "옛 소개"


def test_content_edit_requires_login(test_client):
    saved = insert_content(
        {"village_id": "V001", "content_type": "소개글", "body": "옛 소개"}
    )
    response = test_client.patch(
        f"/api/operator/contents/{saved['content_id']}",
        json={"body": "고친 소개"},
    )
    assert response.status_code == 401


def test_delete_text_keeps_shared_photo_on_the_other_row(test_client):
    photo = "https://example.test/storage/v1/object/public/content-photos/V001/a.png"
    intro = insert_content(
        {
            "village_id": "V001",
            "content_type": "소개글",
            "body": "소개",
            "photo_url": photo,
        }
    )
    insert_content(
        {
            "village_id": "V001",
            "content_type": "SNS홍보문구",
            "body": "문구",
            "photo_url": photo,
        }
    )
    response = test_client.delete(
        f"/api/operator/contents/{intro['content_id']}",
        headers=_AUTH,
    )
    assert response.status_code == 200
    rows = test_client.get("/api/operator/contents", headers=_AUTH).json()["contents"]
    assert len(rows) == 1
    assert rows[0]["body"] == "문구"
    assert rows[0]["photo_url"] == photo


def test_delete_photo_clears_the_same_url_in_this_village_only(test_client):
    photo = "https://example.test/storage/v1/object/public/content-photos/V001/a.png"
    intro = insert_content(
        {
            "village_id": "V001",
            "content_type": "소개글",
            "body": "소개",
            "photo_url": photo,
        }
    )
    insert_content(
        {
            "village_id": "V001",
            "content_type": "SNS홍보문구",
            "body": "문구",
            "photo_url": photo,
        }
    )
    insert_content(
        {
            "village_id": "V002",
            "content_type": "소개글",
            "body": "다른 마을",
            "photo_url": photo,
        }
    )
    response = test_client.delete(
        f"/api/operator/contents/{intro['content_id']}/photo",
        headers=_AUTH,
    )
    assert response.status_code == 200
    own = test_client.get("/api/operator/contents", headers=_AUTH).json()["contents"]
    assert [row["photo_url"] for row in own] == ["", ""]
    assert [row["body"] for row in own] == ["소개", "문구"]
    other = test_client.get(
        "/api/operator/contents",
        headers={"Authorization": "Bearer owner_v002"},
    ).json()["contents"]
    assert other[0]["photo_url"] == photo


def test_photo_delete_removes_only_this_village_object(monkeypatch):
    from services.operator_assistant import remove_stored_content_photo

    removed = []

    class Bucket:
        def remove(self, paths):
            removed.extend(paths)

    class Storage:
        def from_(self, name):
            assert name == "content-photos"
            return Bucket()

    class Client:
        storage = Storage()

    monkeypatch.setattr("services.operator_assistant.get_supabase_client", lambda: Client())
    remove_stored_content_photo(
        "V001",
        "https://example.test/storage/v1/object/public/content-photos/V001/a.png",
    )
    remove_stored_content_photo(
        "V001",
        "https://example.test/storage/v1/object/public/content-photos/V002/a.png",
    )
    remove_stored_content_photo("V001", "https://example.test/other/a.png")
    remove_stored_content_photo(
        "V001",
        "https://example.test/storage/v1/object/public/content-photos/V001/../V002/a.png",
    )
    assert removed == ["V001/a.png"]


def test_missing_photo_file_does_not_fail_delete(monkeypatch):
    from services.operator_assistant import remove_stored_content_photo

    class Bucket:
        def remove(self, paths):
            raise RuntimeError("Object not found")

    class Storage:
        def from_(self, name):
            return Bucket()

    class Client:
        storage = Storage()

    monkeypatch.setattr("services.operator_assistant.get_supabase_client", lambda: Client())
    remove_stored_content_photo(
        "V001",
        "https://example.test/storage/v1/object/public/content-photos/V001/a.png",
    )
