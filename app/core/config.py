"""Application configuration, loaded entirely from environment variables."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class SearchWeights(BaseSettings):
    """Weights for the hybrid search ranking formula. Must sum to ~1.0."""

    semantic: float = Field(default=0.55)
    lexical: float = Field(default=0.25)
    metadata: float = Field(default=0.10)
    recency: float = Field(default=0.10)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )

    # --- App ---
    env: str = Field(default="dev", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    default_locale: str = Field(default="ru", alias="DEFAULT_LOCALE")

    # --- Telegram ---
    telegram_bot_token: str = Field(default="", alias="TELEGRAM_BOT_TOKEN")
    telegram_admin_ids: str = Field(default="", alias="TELEGRAM_ADMIN_IDS")

    # --- Database ---
    database_url: str = Field(
        default="postgresql+asyncpg://savebot:savebot@localhost:5432/savebot",
        alias="DATABASE_URL",
    )

    # --- Redis ---
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    # --- AI providers (abstraction: see app/services/ai) ---
    ai_provider: str = Field(default="openai", alias="AI_PROVIDER")
    ai_api_key: str = Field(default="", alias="AI_API_KEY")
    ai_model: str = Field(default="gpt-4o-mini", alias="AI_MODEL")
    ai_base_url: str | None = Field(default=None, alias="AI_BASE_URL")

    embedding_provider: str = Field(default="openai", alias="EMBEDDING_PROVIDER")
    embedding_model: str = Field(default="text-embedding-3-small", alias="EMBEDDING_MODEL")
    embedding_dimensions: int = Field(default=1536, alias="EMBEDDING_DIMENSIONS")

    vision_provider: str = Field(default="openai", alias="VISION_PROVIDER")
    vision_model: str = Field(default="gpt-4o-mini", alias="VISION_MODEL")

    ai_request_timeout_seconds: float = Field(default=30.0, alias="AI_REQUEST_TIMEOUT_SECONDS")

    # --- Object storage (S3-compatible) ---
    s3_endpoint: str = Field(default="http://localhost:9000", alias="S3_ENDPOINT")
    s3_bucket: str = Field(default="savebot", alias="S3_BUCKET")
    s3_access_key: str = Field(default="", alias="S3_ACCESS_KEY")
    s3_secret_key: str = Field(default="", alias="S3_SECRET_KEY")
    s3_region: str = Field(default="us-east-1", alias="S3_REGION")

    # --- Observability ---
    sentry_dsn: str | None = Field(default=None, alias="SENTRY_DSN")

    # --- Outbound proxy (for VPS networks where Telegram/OpenAI/social platforms
    # aren't directly reachable) ---
    proxy_url: str | None = Field(default=None, alias="PROXY_URL")

    # --- Search ranking ---
    search_weight_semantic: float = Field(default=0.55, alias="SEARCH_WEIGHT_SEMANTIC")
    search_weight_lexical: float = Field(default=0.25, alias="SEARCH_WEIGHT_LEXICAL")
    search_weight_metadata: float = Field(default=0.10, alias="SEARCH_WEIGHT_METADATA")
    search_weight_recency: float = Field(default=0.10, alias="SEARCH_WEIGHT_RECENCY")
    search_result_limit: int = Field(default=20, alias="SEARCH_RESULT_LIMIT")
    search_min_score: float = Field(default=0.15, alias="SEARCH_MIN_SCORE")

    # --- Security / extraction limits ---
    http_timeout_seconds: float = Field(default=15.0, alias="HTTP_TIMEOUT_SECONDS")
    http_max_response_bytes: int = Field(default=8 * 1024 * 1024, alias="HTTP_MAX_RESPONSE_BYTES")
    http_max_redirects: int = Field(default=5, alias="HTTP_MAX_REDIRECTS")
    image_max_bytes: int = Field(default=15 * 1024 * 1024, alias="IMAGE_MAX_BYTES")

    # --- Rate limiting ---
    rate_limit_user_per_minute: int = Field(default=20, alias="RATE_LIMIT_USER_PER_MINUTE")
    rate_limit_extraction_per_minute: int = Field(default=10, alias="RATE_LIMIT_EXTRACTION_PER_MINUTE")
    rate_limit_ai_per_minute: int = Field(default=15, alias="RATE_LIMIT_AI_PER_MINUTE")
    rate_limit_max_concurrent_jobs_per_user: int = Field(
        default=3, alias="RATE_LIMIT_MAX_CONCURRENT_JOBS_PER_USER"
    )

    # --- Admin API ---
    admin_api_token: str = Field(default="", alias="ADMIN_API_TOKEN")

    @field_validator("telegram_admin_ids")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()

    @property
    def admin_ids(self) -> set[int]:
        if not self.telegram_admin_ids:
            return set()
        return {int(x) for x in self.telegram_admin_ids.split(",") if x.strip()}

    @property
    def search_weights(self) -> SearchWeights:
        return SearchWeights(
            semantic=self.search_weight_semantic,
            lexical=self.search_weight_lexical,
            metadata=self.search_weight_metadata,
            recency=self.search_weight_recency,
        )

    @property
    def is_dev(self) -> bool:
        return self.env == "dev"


@lru_cache
def get_settings() -> Settings:
    return Settings()
