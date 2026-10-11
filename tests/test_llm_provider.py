from unittest.mock import MagicMock, patch

from services.llm_provider import (
    CLAUDE_MODEL,
    GEMINI_MODEL,
    OPENAI_MODEL,
    ClaudeProvider,
    GeminiProvider,
    OpenAIProvider,
    get_llm_provider,
)


def test_default_provider_is_gemini(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    provider = get_llm_provider()
    assert isinstance(provider, GeminiProvider)


def test_provider_switches_to_claude(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "claude")
    provider = get_llm_provider()
    assert isinstance(provider, ClaudeProvider)


def test_provider_switches_to_openai(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    provider = get_llm_provider()
    assert isinstance(provider, OpenAIProvider)


def test_invalid_provider_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "존재하지않는제공자")
    provider = get_llm_provider()
    assert isinstance(provider, GeminiProvider)


def test_all_providers_implement_generate_method():
    for provider_class in [GeminiProvider, ClaudeProvider, OpenAIProvider]:
        assert hasattr(provider_class, "generate")


def _http_client(payload):
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = payload
    post = MagicMock(return_value=response)
    client = MagicMock()
    client.__enter__.return_value.post = post
    return client, post


def test_gemini_recommend_uses_flash_json_and_timeout(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    client, post = _http_client(
        {"candidates": [{"content": {"parts": [{"text": "[]"}]}}]}
    )
    with patch("httpx.Client", return_value=client) as client_cls:
        text = GeminiProvider().generate("시스템", "사용자", timeout=3.5, json_mode=True)

    assert text == "[]"
    assert client_cls.call_args.kwargs["timeout"] == 3.5
    assert GEMINI_MODEL in post.call_args.args[0]
    body = post.call_args.kwargs["json"]
    assert body["systemInstruction"]["parts"][0]["text"] == "시스템"
    assert body["generationConfig"]["responseMimeType"] == "application/json"
    assert body["generationConfig"]["maxOutputTokens"] == 1024
    assert body["generationConfig"]["thinkingConfig"]["thinkingLevel"] == "minimal"
    assert "temperature" not in body["generationConfig"]
    assert "thinkingBudget" not in body["generationConfig"]["thinkingConfig"]


def test_gemini_prose_call_omits_json_mime(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    client, post = _http_client(
        {"candidates": [{"content": {"parts": [{"text": "소개글"}]}}]}
    )
    with patch("httpx.Client", return_value=client) as client_cls:
        GeminiProvider().generate("시스템", "사용자")

    assert client_cls.call_args.kwargs["timeout"] == 30.0
    assert "generationConfig" not in post.call_args.kwargs["json"]


def test_openai_recommend_uses_mini_json_schema(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    client, post = _http_client({"choices": [{"message": {"content": "{\"recommendations\":[]}"}}]})
    with patch("httpx.Client", return_value=client):
        OpenAIProvider().generate("시스템", "사용자", timeout=3.5, json_mode=True)

    body = post.call_args.kwargs["json"]
    assert body["model"] == OPENAI_MODEL
    assert body["response_format"]["type"] == "json_schema"
    assert body["response_format"]["json_schema"]["strict"] is True


def test_openai_prose_call_omits_json_schema(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    client, post = _http_client({"choices": [{"message": {"content": "소개글"}}]})
    with patch("httpx.Client", return_value=client):
        OpenAIProvider().generate("시스템", "사용자")

    assert "response_format" not in post.call_args.kwargs["json"]


def test_claude_uses_haiku(monkeypatch):
    monkeypatch.setenv("CLAUDE_API_KEY", "test-key")
    client, post = _http_client({"content": [{"text": "소개글"}]})
    with patch("httpx.Client", return_value=client) as client_cls:
        ClaudeProvider().generate("시스템", "사용자", timeout=8)

    assert client_cls.call_args.kwargs["timeout"] == 8
    assert post.call_args.kwargs["json"]["model"] == CLAUDE_MODEL
