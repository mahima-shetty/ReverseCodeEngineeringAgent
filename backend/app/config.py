from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env", override=True)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", env_file=str(BACKEND_DIR / ".env"))

    cors_allow_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )
    blueverse_url: str = "https://blueverse-foundry.ltimindtree.com/chatservice/chat"
    blueverse_space_name: str = ""
    blueverse_flow_id: str = ""
    blueverse_bearer_token: str = ""
    groq_url: str = "https://api.groq.com/openai/v1/chat/completions"
    groq_model: str = "meta-llama/llama-4-scout-17b-16e-instruct"
    groq_api_key: str = ""
    openai_url: str = "https://api.openai.com/v1/chat/completions"
    openai_model: str = "gpt-4o-mini"
    openai_api_key: str = ""
    provider_order: list[str] = Field(default_factory=lambda: ["groq", "openai", "heuristic"])
    provider_timeout_seconds: float = 60.0
    provider_validation_retries: int = 1
    enable_external_oracle_links: bool = False
    max_retrieval_hits: int = 8
    lexical_top_k: int = 20
    top_reranked_hits: int = 5
    local_embedding_model: str = "BAAI/bge-base-en-v1.5"
    local_reranker_model: str = "BAAI/bge-reranker-base"
    backend_dir: Path = BACKEND_DIR
    fixtures_dir: Path = BACKEND_DIR / "fixtures"
    evidence_dir: Path = BACKEND_DIR / "evidence"
    logs_dir: Path = BACKEND_DIR / "logs"
    source_registry_file: Path = BACKEND_DIR / "oracle_rag_sources.json"
    oracle_cache_file: Path = BACKEND_DIR / "oracle_docs_cache.json"
    benchmark_fixture_file: Path = BACKEND_DIR / "fixtures" / "benchmark_cases.json"
    llm_usage_log: Path = BACKEND_DIR / "logs" / "llm_usage.jsonl"
    latest_run_usage_log: Path = BACKEND_DIR / "logs" / "latest_run_usage.jsonl"
    llm_requests_dir: Path = BACKEND_DIR / "logs" / "llm_requests"
    llm_outputs_dir: Path = BACKEND_DIR / "logs" / "llm_outputs"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
