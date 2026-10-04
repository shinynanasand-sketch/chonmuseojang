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


def test_prompt_contains_only_the_operator_village(monkeypatch):
    _seed_two_villages()
    llm = _FakeLLM("소개글: 가을 갯벌\nSNS홍보문구: 갯벌 체험 오세요")
    monkeypatch.setattr("services.operator_assistant.get_llm_provider", lambda: llm)

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
    monkeypatch.setattr("services.operator_assistant.get_llm_provider", lambda: llm)
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
        lambda: _FakeLLM(""),
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
