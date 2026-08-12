"""Ollama client. Default provider. Uses the `format` param for structured output.

Contract notes (CLAUDE.md rules 2 and 3):
  - `complete()` never raises for model-side problems. It returns None so the
    caller can degrade to computed-only fields instead of returning a 5xx.
  - Shape is enforced by passing the JSON schema to Ollama's `format`, not by
    asking the model nicely. A 7B model drifts by the third call otherwise.
"""

from __future__ import annotations

import json
from typing import Any

from ollama import Client as OllamaSDK

from app.config import settings
from app.llm.base import LLMClient

# One SDK client per timeout value. The SDK forwards kwargs to httpx, and
# httpx fixes its timeout at construction, so we cache instead of rebuilding.
_clients: dict[int, OllamaSDK] = {}


def _client(timeout: int) -> OllamaSDK:
    if timeout not in _clients:
        _clients[timeout] = OllamaSDK(host=settings.ollama_host, timeout=timeout)
    return _clients[timeout]


class OllamaClient(LLMClient):
    def __init__(self, model: str | None = None) -> None:
        self.model = model or settings.llm_model

    def complete(
        self, prompt: str, schema: dict[str, Any], timeout: int = 30, max_tokens: int = 450
    ) -> dict[str, Any] | None:
        try:
            response = _client(timeout).chat(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                format=schema,
                keep_alive=settings.keep_alive,
                options={
                    "temperature": 0.2,  # narrative, not creativity
                    # Generation time is roughly linear in tokens produced.
                    # The schema caps array lengths; this caps the total.
                    "num_predict": max_tokens,
                    # Nothing here benefits from sampling breadth, and a
                    # narrower candidate set decodes slightly faster.
                    "top_k": 20,
                },
            )
        except Exception as exc:  # network down, model missing, timeout
            print(f"[llm] call failed: {type(exc).__name__}: {exc}")
            return None

        raw = (response.get("message") or {}).get("content", "").strip()
        if not raw:
            print("[llm] empty response")
            return None

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            print(f"[llm] non-JSON response despite schema: {raw[:200]}")
            return None

        if not isinstance(parsed, dict):
            print(f"[llm] expected object, got {type(parsed).__name__}")
            return None

        return parsed

    def prewarm(self) -> None:
        """Make the model VRAM-resident so the first real request isn't cold."""
        try:
            _client(120).chat(
                model=self.model,
                messages=[{"role": "user", "content": "ok"}],
                keep_alive=settings.keep_alive,
                options={"num_predict": 1},
            )
            print(f"[llm] prewarmed {self.model}")
        except Exception as exc:
            print(f"[llm] prewarm failed (non-fatal): {type(exc).__name__}: {exc}")
