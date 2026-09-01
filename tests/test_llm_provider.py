import os

from services.llm_provider import ClaudeProvider, GeminiProvider, OpenAIProvider, get_llm_provider


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
