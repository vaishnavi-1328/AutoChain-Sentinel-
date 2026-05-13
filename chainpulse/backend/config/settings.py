"""Pydantic Settings — all env vars per BACKEND_PROMPT module 8 (Redis Streams sub for Kafka)."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project .env lives at chainpulse/.env regardless of CWD.
_ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # PostgreSQL
    database_url: str = Field(
        default="postgresql+asyncpg://user:pass@localhost:5432/chainpulse",
        alias="DATABASE_URL",
    )

    # Neo4j
    neo4j_uri: str = Field(default="bolt://localhost:7687", alias="NEO4J_URI")
    neo4j_user: str = Field(default="neo4j", alias="NEO4J_USER")
    neo4j_password: str = Field(default="your_password", alias="NEO4J_PASSWORD")

    # Redis (Upstash) — used for stream queue, pub/sub, bloom filter, TTL cache
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    # Streams (Kafka replacement)
    stream_raw: str = Field(default="stream:raw.news", alias="STREAM_RAW")
    stream_processed: str = Field(default="stream:processed.events", alias="STREAM_PROCESSED")
    stream_group: str = Field(default="chainpulse-nlp", alias="STREAM_GROUP")

    # LLM (Groq)
    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")
    groq_model: str = Field(default="llama-3.1-8b-instant", alias="GROQ_MODEL")

    # News APIs
    guardian_api_key: str = Field(default="", alias="GUARDIAN_API_KEY")
    gnews_api_key: str = Field(default="", alias="GNEWS_API_KEY")
    newsapi_key: str = Field(default="", alias="NEWSAPI_KEY")
    geonames_username: str = Field(default="", alias="GEONAMES_USERNAME")

    # Auth
    jwt_secret: str = Field(
        default="change-me-in-prod-min-32-chars-please-1234",
        alias="JWT_SECRET",
    )
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    jwt_expiry_hours: int = Field(default=24, alias="JWT_EXPIRY_HOURS")

    # ML
    model_dir: str = Field(default="./backend/ml", alias="MODEL_DIR")

    # App
    app_env: str = Field(default="development", alias="APP_ENV")
    cors_origins: str = Field(
        default="http://localhost:3000,http://localhost:5173",
        alias="CORS_ORIGINS",
    )
    allow_seed: bool = Field(default=False, alias="ALLOW_SEED")

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
