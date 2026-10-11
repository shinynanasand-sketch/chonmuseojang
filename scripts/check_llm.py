"""현재 LLM 키가 생성 호출을 통과하는지 HTTP 상태와 reason만 출력한다."""

import os
import sys
from pathlib import Path

import _bootstrap  # noqa: F401

import httpx
from dotenv import load_dotenv

from services.llm_provider import (
    CLAUDE_MODEL,
    GEMINI_MODEL,
    OPENAI_MODEL,
    _RECOMMENDATION_SCHEMA,
)

_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(_ROOT / ".env")
load_dotenv(_ROOT / ".env.local", override=False)

_TIMEOUT = 20.0


def _safe_reason(response: httpx.Response) -> str:
    """응답 본문에서 상태 코드용 이유만 고른다. 메시지와 키는 넣지 않는다."""
    if response.status_code == 200:
        return "ok"
    try:
        body = response.json()
    except ValueError:
        return "unreadable"
    error = body.get("error") if isinstance(body, dict) else None
    if not isinstance(error, dict):
        return "unreadable"
    status = str(error.get("status") or error.get("type") or "")
    reason = ""
    details = error.get("details")
    if isinstance(details, list):
        for item in details:
            if isinstance(item, dict) and item.get("reason"):
                reason = str(item["reason"])
                break
    if not reason and error.get("code"):
        reason = str(error["code"])
    parts = [part for part in (status, reason) if part]
    return " ".join(parts) if parts else "unreadable"


def _post(url: str, **kwargs) -> tuple[int, str]:
    try:
        response = httpx.post(url, timeout=_TIMEOUT, **kwargs)
    except httpx.TimeoutException:
        return 0, "timeout"
    except httpx.RequestError:
        return 0, "request_error"
    return response.status_code, _safe_reason(response)


def probe(provider: str) -> tuple[str, int, str]:
    name = (provider or "gemini").lower()
    if name == "openai":
        key = os.getenv("OPENAI_API_KEY", "")
        model = OPENAI_MODEL
        if not key:
            return model, 0, "missing"
        status, reason = _post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": "JSON으로만 응답하세요."},
                    {"role": "user", "content": "ping"},
                ],
                "temperature": 0.2,
                "max_tokens": 64,
                "response_format": _RECOMMENDATION_SCHEMA,
            },
        )
        return model, status, reason
    if name == "claude":
        key = os.getenv("CLAUDE_API_KEY", "")
        model = CLAUDE_MODEL
        if not key:
            return model, 0, "missing"
        status, reason = _post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": model,
                "max_tokens": 64,
                "system": "한 단어로만 답하세요.",
                "messages": [{"role": "user", "content": "ping"}],
            },
        )
        return model, status, reason
    key = os.getenv("GEMINI_API_KEY", "")
    model = GEMINI_MODEL
    if not key:
        return model, 0, "missing"
    status, reason = _post(
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent",
        params={"key": key},
        json={
            "systemInstruction": {"parts": [{"text": "JSON으로만 응답하세요."}]},
            "contents": [{"parts": [{"text": "ping"}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "maxOutputTokens": 64,
                "thinkingConfig": {"thinkingLevel": "minimal"},
            },
        },
    )
    return model, status, reason


def main() -> int:
    provider = os.getenv("LLM_PROVIDER", "gemini")
    model, status, reason = probe(provider)
    print(f"provider={provider}")
    print(f"model={model}")
    print(f"http={status}")
    print(f"reason={reason}")
    return 0 if status == 200 else 1


if __name__ == "__main__":
    sys.exit(main())
