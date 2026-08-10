"""Env-driven settings. Single source of truth for all tunables."""

from pathlib import Path

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

    # Hosted fallback (unused while llm_provider == "ollama")
    hosted_base_url: str = ""
    hosted_api_key: str = ""
    hosted_model: str = ""

    # Timeouts, seconds. On expiry, endpoints return computed fields only.
    insights_timeout: int = 30
    root_cause_timeout: int = 30
    search_timeout: int = 20

    # Knowledge base. See spec 7.1 - calibrate, do not guess.
    chroma_path: str = str(REPO_ROOT / "backend" / "chroma")
    sop_dir: str = str(REPO_ROOT / "data" / "sops")
    retrieval_top_k: int = 4
    # Chroma cosine DISTANCE ceiling; above this a chunk is "not really a match".
    # Placeholder until calibrated against the two fixed query sets.
    max_match_distance: float = 0.31

    data_dir: str = str(REPO_ROOT / "data" / "generated")


settings = Settings()
