"""Hosted OpenAI-compatible fallback. Unused unless LLM_PROVIDER=hosted.

This exists for one reason: if the local model is slow or incoherent at hour
six, switching providers must be a one-variable change (CLAUDE.md rule 2).
Same contract as OllamaClient - returns None on any failure, never raises.

Works against any OpenAI-compatible /chat/completions endpoint (OpenAI,
Groq, Together, a teammate's vLLM server). Set in backend/.env:

    LLM_PROVIDER=hosted
    HOSTED_BASE_URL=https://api.openai.com/v1
    HOSTED_API_KEY=sk-...
    HOSTED_MODEL=gpt-4o-mini
"""

from __future__ import annotations

import json

import httpx

from app.config import settings
from app.llm.base import LLMClient


class HostedClient(LLMClient):
    def __init__(self) -> None:
        self.base_url = settings.hosted_base_url.rstrip("/")
        self.api_key = settings.hosted_api_key
        self.model = settings.hosted_model

        if not (self.base_url and self.api_key and self.model):
            print(
                "[llm] WARNING: LLM_PROVIDER=hosted but HOSTED_BASE_URL / "
                "HOSTED_API_KEY / HOSTED_MODEL are not all set. Calls will fail "
                "and endpoints will degrade to computed-only."
            )

    def complete(
        self, prompt: str, schema: dict, timeout: int = 30, max_tokens: int = 450
    ) -> dict | None:
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "max_tokens": max_tokens,
            # Structured output by schema, not by prompting (rule 3).
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "response",
                    "schema": schema,
                    "strict": False,
                },
            },
        }

        try:
            response = httpx.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=timeout,
            )
            response.raise_for_status()
            body = response.json()
        except Exception as exc:
            print(f"[llm] hosted call failed: {type(exc).__name__}: {exc}")
            return None

        try:
            raw = body["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, AttributeError):
            print(f"[llm] unexpected hosted response shape: {str(body)[:200]}")
            return None

        if not raw:
            print("[llm] empty hosted response")
            return None

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            print(f"[llm] non-JSON hosted response: {raw[:200]}")
            return None

        if not isinstance(parsed, dict):
            print(f"[llm] expected object, got {type(parsed).__name__}")
            return None

        return parsed

    def prewarm(self) -> None:
        """No-op. Hosted endpoints have no cold model to make resident."""
        return
