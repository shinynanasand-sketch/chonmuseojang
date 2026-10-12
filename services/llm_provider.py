import os
from abc import ABC, abstractmethod

GEMINI_MODEL = "gemini-3.5-flash-lite"
CLAUDE_MODEL = "claude-haiku-4-5"
OPENAI_MODEL = "gpt-4.1-mini"

_RECOMMENDATION_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "village_recommendations",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "recommendations": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "village_id": {"type": "string"},
                            "village_name": {"type": "string"},
                            "reason": {"type": "string"},
                        },
                        "required": ["village_id", "village_name", "reason"],
                    },
                }
            },
            "required": ["recommendations"],
        },
    },
}


class LLMUnavailable(Exception):
    """키가 없거나 HTTP로 바로 거절된 호출이다."""


_FAILOVER_STATUS = frozenset({401, 403, 408, 429, 500, 502, 503, 504})
_PROVIDER_KEYS = {
    "gemini": "GEMINI_API_KEY",
    "openai": "OPENAI_API_KEY",
    "claude": "CLAUDE_API_KEY",
}


def provider_has_key(name: str) -> bool:
    env_name = _PROVIDER_KEYS.get(name)
    if not env_name:
        return False
    return bool(os.getenv(env_name, "").strip())


def _raise_if_unavailable(response) -> None:
    import httpx

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in _FAILOVER_STATUS:
            raise LLMUnavailable(str(exc.response.status_code)) from exc
        raise


class LLMProvider(ABC):
    @abstractmethod
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        timeout: float = 30.0,
        json_mode: bool = False,
    ) -> str:
        pass


class GeminiProvider(LLMProvider):
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY", "")

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        timeout: float = 30.0,
        json_mode: bool = False,
    ) -> str:
        if not self.api_key:
            raise LLMUnavailable("missing")
        import httpx

        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{GEMINI_MODEL}:generateContent?key={self.api_key}"
        )
        payload = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"parts": [{"text": user_prompt}]}],
        }
        if json_mode:
            payload["generationConfig"] = {
                "responseMimeType": "application/json",
                "maxOutputTokens": 1024,
                "thinkingConfig": {"thinkingLevel": "minimal"},
            }
        with httpx.Client(timeout=timeout) as client:
            response = client.post(url, json=payload)
            _raise_if_unavailable(response)
            data = response.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]


class ClaudeProvider(LLMProvider):
    def __init__(self):
        self.api_key = os.getenv("CLAUDE_API_KEY", "")

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        timeout: float = 30.0,
        json_mode: bool = False,
    ) -> str:
        if not self.api_key:
            raise LLMUnavailable("missing")
        import httpx

        with httpx.Client(timeout=timeout) as client:
            response = client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": CLAUDE_MODEL,
                    "max_tokens": 512 if json_mode else 1024,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": user_prompt}],
                },
            )
            _raise_if_unavailable(response)
            return response.json()["content"][0]["text"]


class OpenAIProvider(LLMProvider):
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY", "")

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        timeout: float = 30.0,
        json_mode: bool = False,
    ) -> str:
        if not self.api_key:
            raise LLMUnavailable("missing")
        import httpx

        body = {
            "model": OPENAI_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        if json_mode:
            body["temperature"] = 0.2
            body["max_tokens"] = 1024
            body["response_format"] = _RECOMMENDATION_SCHEMA
        with httpx.Client(timeout=timeout) as client:
            response = client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=body,
            )
            _raise_if_unavailable(response)
            return response.json()["choices"][0]["message"]["content"]


def get_llm_provider(name: str | None = None) -> LLMProvider:
    provider_name = (name or os.getenv("LLM_PROVIDER", "gemini")).lower()
    mapping = {
        "gemini": GeminiProvider,
        "claude": ClaudeProvider,
        "openai": OpenAIProvider,
    }
    provider_class = mapping.get(provider_name, GeminiProvider)
    return provider_class()
