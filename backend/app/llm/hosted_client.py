"""Hosted OpenAI-compatible fallback. Unused unless LLM_PROVIDER=hosted.

This exists for one reason: if the local model is slow or incoherent at hour
six, switching providers must be a one-variable change.
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
from typing import Any

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

    def _payload(
        self, prompt: str, schema: dict[str, Any], max_tokens: int, mode: str
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "max_tokens": max_tokens,
        }
        if mode == "json_schema":
            # Structured output by schema, not by prompting.
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "response", "schema": schema, "strict": False},
            }
        else:
            # Not every hosted model accepts json_schema - Groq supports it on
            # some models and rejects it with a 400 on others. json_object is
            # universal, so the shape moves into the prompt for that case.
            payload["response_format"] = {"type": "json_object"}
            payload["messages"] = [
                {
                    "role": "user",
                    "content": (
                        f"{prompt}\n\nReturn JSON matching exactly this schema, "
                        f"with no extra keys:\n{json.dumps(schema)}"
                    ),
                }
            ]
        return payload

    def complete(
        self, prompt: str, schema: dict[str, Any], timeout: int = 30, max_tokens: int = 450
    ) -> dict[str, Any] | None:
        body = None
        for mode in ("json_schema", "json_object"):
            try:
                response = httpx.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=self._payload(prompt, schema, max_tokens, mode),
                    timeout=timeout,
                )
                # A 400 usually means this model will not take json_schema.
                # Retry once in the universal mode before giving up.
                if response.status_code == 400 and mode == "json_schema":
                    print("[llm] hosted rejected json_schema, retrying as json_object")
                    continue
                response.raise_for_status()
                body = response.json()
                break
            except Exception as exc:
                print(f"[llm] hosted call failed: {type(exc).__name__}: {exc}")
                return None

        if body is None:
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
