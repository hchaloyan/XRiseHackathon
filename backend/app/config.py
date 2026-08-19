"""Env-driven settings. Single source of truth for all tunables."""

from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Inference
    llm_provider: str = "ollama"  # "ollama" | "hosted"
    ollama_host: str = "http://localhost:11434"
    llm_model: str = "qwen2.5:7b-instruct"
    embed_model: str = "nomic-embed-text"
    keep_alive: str = "30m"  # holds the model in VRAM between requests

    # Hosted provider. Any OpenAI-compatible endpoint; defaults target Groq.
    # Used in two independent places:
    #   - as the whole-app fallback when llm_provider == "hosted"
    #   - as the general-knowledge answerer, below, whatever llm_provider is
    hosted_base_url: str = "https://api.groq.com/openai/v1"
    hosted_api_key: str = ""  # GROQ key goes in backend/.env, never in git
    # llama-3.3-70b-versatile was deprecated on Groq in June 2026. The 20B is
    # the fast option and this answer is three sentences; use gpt-oss-120b or
    # qwen/qwen3.6-27b if the answers read too thin.
    hosted_model: str = "openai/gpt-oss-20b"

    # Who answers a question the SOPs do not cover: "hosted", "ollama", or
    # "off" to keep the plain redirect. Hosted by default because this path is
    # user-facing latency, and a 7B local model spends 3s saying less.
    general_provider: str = "hosted"
    general_timeout: int = 15

    # Timeouts, seconds. On expiry, endpoints return computed fields only.
    insights_timeout: int = 30
    root_cause_timeout: int = 30
    search_timeout: int = 20

    # Knowledge base. Calibrate the similarity floor, do not guess.
    chroma_path: str = str(REPO_ROOT / "backend" / "chroma")
    sop_dir: str = str(REPO_ROOT / "data" / "sops")
    retrieval_top_k: int = 4
    # Chroma cosine DISTANCE ceiling; above this a chunk is "not really a match".
    # Set by `python calibrate_kb.py` over 17 realistic in-corpus phrasings and
    # 10 factory-data questions: answers 17/17, admits 1.
    #
    # The bands OVERLAP - there is no clean number. Real questions run to 0.306
    # while "how many parts did we scrap on the molding line today" sits at
    # 0.299, and SOP-006 does cover line-side scrap, so that one is a soft miss.
    # The failure that actually costs the demo is a data question answered with
    # a confident procedure, and those stay out: downtime 0.366, scrap rate
    # 0.396, OEE 0.477. Past ~0.36 they start getting in.
    #
    # Take the MIDDLE of the viable range, never its edge. An earlier 0.26 sat
    # a thousandth away from real questions it silently rejected.
    #
    # Not comparable across an embedding change: values from before the nomic
    # query/document prefixes sat on a different distribution.
    max_match_distance: float = 0.34

    data_dir: str = str(REPO_ROOT / "data" / "generated")

    @field_validator("ollama_host")
    @classmethod
    def _dialable(cls, value: str) -> str:
        """`OLLAMA_HOST` is a SERVER bind address by convention, not a client
        target, and pydantic binds that ambient var to this field ahead of any
        .env value. `0.0.0.0` means "listen on every interface" and is not
        connectable on Windows. Scheme and port are left to the Ollama SDK,
        which already fills both in.
        """
        return value.replace("0.0.0.0", "127.0.0.1")


settings = Settings()
