import os
from abc import ABC, abstractmethod


class LLMProvider(ABC):
    @abstractmethod
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        pass


class GeminiProvider(LLMProvider):
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY", "")

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        if not self.api_key:
            return "[]"
        import httpx

        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"gemini-1.5-flash:generateContent?key={self.api_key}"
        )
        payload = {
            "contents": [{"parts": [{"text": f"{system_prompt}\n\n{user_prompt}"}]}]
        }
        with httpx.Client(timeout=30.0) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]


class ClaudeProvider(LLMProvider):
    def __init__(self):
        self.api_key = os.getenv("CLAUDE_API_KEY", "")

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        if not self.api_key:
            return "[]"
        import httpx

        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-3-5-sonnet-20241022",
                    "max_tokens": 1024,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": user_prompt}],
                },
            )
            response.raise_for_status()
            return response.json()["content"][0]["text"]


class OpenAIProvider(LLMProvider):
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY", "")

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        if not self.api_key:
            return "[]"
        import httpx

        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                },
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
