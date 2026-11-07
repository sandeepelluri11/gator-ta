from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

API_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = API_ROOT.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GATOR_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://gator:gator@localhost:5432/gator"
    redis_url: str = "redis://localhost:6379/0"

    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    chat_model: str = "gpt-4o-mini"
    judge_model: str = "gpt-4o"
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536

    course_id: str = "CIS6930"
    syllabus_path: Path = REPO_ROOT / "data/sample/syllabus.yaml"

    top_k: int = 6
    candidate_k: int = 20
    chunk_tokens: int = 350
    chunk_overlap_tokens: int = 50
    max_tool_rounds: int = 3
    history_turns: int = 8
    session_ttl_seconds: int = 60 * 60 * 6

    cors_origins: list[str] = ["http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
