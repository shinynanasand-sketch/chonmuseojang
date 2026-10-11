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
            return "[]"
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
            response.raise_for_status()
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
            return "[]"
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
            response.raise_for_status()
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
            return "[]"
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
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]


def get_llm_provider() -> LLMProvider:
    provider_name = os.getenv("LLM_PROVIDER", "gemini").lower()
    mapping = {
        "gemini": GeminiProvider,
        "claude": ClaudeProvider,
        "openai": OpenAIProvider,
    }
    provider_class = mapping.get(provider_name, GeminiProvider)
    return provider_class()
