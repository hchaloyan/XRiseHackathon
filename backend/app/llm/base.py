"""The single interface every model call goes through (CLAUDE.md rule 2).

Two implementations, selected by settings.llm_provider. Swapping providers
must stay a one-variable change, never a refactor.

Structured output is requested by passing a JSON schema, not by asking the
model politely (rule 3). Every array in every schema must carry explicit
minItems/maxItems - see spec 8.
"""

from abc import ABC, abstractmethod
from pathlib import Path

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
    def complete(self, prompt: str, schema: dict, timeout: int) -> dict | None:
        """Return parsed JSON matching `schema`, or None on failure.

        Never raises for model-side problems. Returning None is what lets
        callers degrade to computed-only responses instead of 5xx (spec 5).
        """

    @abstractmethod
    def prewarm(self) -> None:
        """Throwaway call that makes the model resident. Ignores its own result."""


_client: LLMClient | None = None


def get_client() -> LLMClient:
    """Provider is a one-variable change: settings.llm_provider."""
    global _client
    if _client is None:
        if settings.llm_provider == "hosted":
            from app.llm.hosted_client import HostedClient

            _client = HostedClient()
        else:
            from app.llm.ollama_client import OllamaClient

            _client = OllamaClient()
    return _client
