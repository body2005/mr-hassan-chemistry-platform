from functools import lru_cache
from typing import Literal, Optional
from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # General App Settings
    APP_NAME: str = "LMS AI Service"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: Literal["development", "staging", "production", "test"] = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    API_V1_PREFIX: str = "/api/v1"
    API_KEY: Optional[str] = None  # Optional only in development/test
    CORS_ORIGINS: str = "http://localhost:5173"
    REQUIRE_REDIS: bool = False

    # Admission Control & GPU Guard (8GB VRAM Constraint)
    MAX_CONCURRENT_INTERACTIVE_INFERENCES: int = 2  # Max simultaneous local LLM inferences (2-4 supported)
    SEMAPHORE_TIMEOUT_SECONDS: float = 60.0         # Max wait time to acquire GPU inference slot
    RATE_LIMIT_PER_MINUTE: int = 60                 # Per-client IP/Tenant interactive request rate limit

    # Deterministic Redis Request Cache TTLs (in seconds)
    REDIS_URL: str = "redis://localhost:6379/0"
    CACHE_ENABLED: bool = True
    TTL_QUIZ_CACHE: int = 86400        # 24 hours
    TTL_GRADING_CACHE: int = 172800    # 48 hours
    TTL_REPORT_CACHE: int = 86400      # 24 hours
    TTL_ANALYTICS_CACHE: int = 21600   # 6 hours

    # AI Provider Settings (Defaults strictly to local open-source Ollama)
    DEFAULT_PROVIDER: Literal["ollama", "local", "external", "mock"] = Field(
        default="ollama",
        validation_alias=AliasChoices("AI_PROVIDER", "DEFAULT_PROVIDER")
    )
    
    # Local Provider (Ollama / Qwen)
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen3:8b"
    OLLAMA_EMBED_MODEL: str = "qwen3:8b"
    OLLAMA_REQUEST_TIMEOUT: float = 180.0

    # External Provider (OpenAI / OpenAI-Compatible Cloud API - Optional)
    EXTERNAL_BASE_URL: str = "https://api.openai.com/v1"
    EXTERNAL_API_KEY: Optional[str] = None
    EXTERNAL_MODEL: str = "gpt-4o-mini"
    EXTERNAL_EMBED_MODEL: str = "text-embedding-3-small"
    EXTERNAL_REQUEST_TIMEOUT: float = 45.0

    # Vector Storage (PostgreSQL with pgvector)
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/lms_ai"
    VECTOR_SIMILARITY_THRESHOLD: float = 0.65  # Minimum cosine similarity score for grounded tutor retrieval
    TOP_K_CHUNKS: int = 4

    # Celery & Background Queues
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    @model_validator(mode="after")
    def validate_security_sensitive_settings(self):
        if self.ENVIRONMENT in {"staging", "production"}:
            if self.DEBUG:
                raise ValueError("DEBUG must be disabled in staging/production")
            if not self.API_KEY:
                raise ValueError("API_KEY is required in staging/production")
            origins = [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]
            if not origins or "*" in origins:
                raise ValueError("Explicit CORS_ORIGINS are required in staging/production")
            if not self.DATABASE_URL:
                raise ValueError("DATABASE_URL is required in staging/production")
            if self.REQUIRE_REDIS and not self.REDIS_URL:
                raise ValueError("REDIS_URL is required when REQUIRE_REDIS is enabled")
        return self

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache()
def get_settings() -> Settings:
    return Settings()
