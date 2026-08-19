"""The single interface every model call goes through.

Two implementations, selected by settings.llm_provider. Swapping providers
must stay a one-variable change, never a refactor.

Structured output is requested by passing a JSON schema, not by asking the
model politely. Every array in every schema must carry explicit
minItems/maxItems.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from app.config import settings

PROMPT_DIR = Path(__file__).resolve().parents[1] / "prompts"


def render_prompt(template_name: str, **values: str) -> str:
    """Load a prompt file and substitute {placeholders}.

    str.replace, not str.format - prompt and evidence text contain braces
    (JSON examples, dict literals) and format() would raise KeyError on them.
    """
    text = (PROMPT_DIR / template_name).read_text(encoding="utf-8")
    for key, value in values.items():
        text = text.replace("{" + key + "}", value)
    return text


class LLMClient(ABC):
    @abstractmethod
    def complete(
        self, prompt: str, schema: dict[str, Any], timeout: int, max_tokens: int = 450
    ) -> dict[str, Any] | None:
        """Return parsed JSON matching `schema`, or None on failure.

        Never raises for model-side problems. Returning None is what lets
        callers degrade to computed-only responses instead of 5xx.
        """

    @abstractmethod
    def prewarm(self) -> None:
        """Throwaway call that makes the model resident. Ignores its own result."""


_clients: dict[str, LLMClient] = {}


def get_client(provider: str | None = None) -> LLMClient:
    """Provider is a one-variable change: settings.llm_provider.

    `provider` overrides that for a single call site. Only the general-answer
    path uses it, so the plant-data endpoints keep running on whatever
    llm_provider says even when a hosted key is present - no figure computed
    from this factory's data should depend on someone else's uptime.
    """
    name = provider or settings.llm_provider
    if name not in _clients:
        if name == "hosted":
            from app.llm.hosted_client import HostedClient

            _clients[name] = HostedClient()
        else:
            from app.llm.ollama_client import OllamaClient

            _clients[name] = OllamaClient()
    return _clients[name]
