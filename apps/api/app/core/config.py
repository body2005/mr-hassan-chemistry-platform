import os
from functools import lru_cache
import re
from dotenv import load_dotenv

load_dotenv()

from pydantic import AliasChoices, Field, SecretStr, model_validator
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


def is_deployment_environment(value: str) -> bool:
    # Unknown names fail closed; Settings separately rejects unsupported names.
    return value.strip().lower() not in {'development', 'test', 'testing'}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )

    app_name: str = "Learning Website"
    app_env: str = "development"
    api_v1_prefix: str = "/api/v1"
    secret_key: str = Field(default="development-only-change-me", min_length=16)
    # Public SPA/HttpOnly session contract: reject unsupported renaming.
    session_cookie_name: Literal['matgar_session'] = "matgar_session"
    csrf_cookie_name: Literal['matgar_csrf'] = "matgar_csrf"
    refresh_cookie_name: Literal['matgar_refresh'] = "matgar_refresh"
    session_issuer: str = "mr-hassan-chemistry-platform"
    session_ttl_seconds: int = Field(default=12 * 60 * 60, ge=300, le=60 * 60 * 24)
    refresh_ttl_seconds: int = Field(default=60 * 60 * 24 * 30, ge=60 * 60, le=60 * 60 * 24 * 365)
    password_reset_ttl_minutes: int = Field(default=30, ge=5, le=24 * 60)
    refresh_replay_grace_seconds: int = Field(default=30, ge=1, le=30)
    # Email is an optional product feature, including in production.
    email_enabled: bool = False
    email_provider: Literal['smtp', 'resend'] = 'smtp'
    email_from_email: str | None = None
    resend_api_key: SecretStr | None = None
    smtp_host: str | None = None
    smtp_port: int = Field(default=465, ge=1, le=65535)
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str | None = None
    smtp_tls_verify: bool = True
    default_institution_slug: str = "demo"
    database_url: str = "sqlite:///./learning_website.db"
    db_pool_size: int = Field(default=15, ge=1, le=50)
    db_max_overflow: int = Field(default=25, ge=0, le=100)
    db_pool_timeout_seconds: int = Field(default=30, ge=5, le=120)
    db_pool_recycle_seconds: int = Field(default=1800, ge=60, le=7200)
    redis_url: str = "redis://localhost:6379/0"
    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = Field(
        default="learning",
        validation_alias=AliasChoices("s3_access_key", "S3_ACCESS_KEY_ID", "S3_ACCESS_KEY"),
    )
    s3_secret_key: str = Field(
        default="learning-development",
        validation_alias=AliasChoices("s3_secret_key", "S3_SECRET_ACCESS_KEY", "S3_SECRET_KEY"),
    )
    s3_bucket: str = Field(
        default="learning-website",
        validation_alias=AliasChoices("s3_bucket", "S3_BUCKET_NAME", "S3_BUCKET"),
    )
    s3_region: str = "auto"
    frontend_origins: str = "http://localhost:5173"
    # Set to true ONLY when API and frontend are on different domains
    # (e.g. api.onrender.com + vercel app). Requires HTTPS on both.
    cookie_cross_site: bool = False
    tesseract_cmd: str | None = None
    max_file_size_mb: int = Field(default=500, ge=10, le=2048)
    max_batch_size_mb: int = Field(default=1000, ge=50, le=4096)
    max_request_size_mb: int = Field(default=1000, ge=50, le=4096)
    multipart_overhead_mb: int = Field(default=10, ge=1, le=100)
    max_concurrent_ingestions: int = Field(default=1, ge=1, le=8)
    redis_required: bool = False
    # Preparation only: no RLS policies are enabled by startup/migrations.
    rls_context_enabled: bool = False
    payment_instapay_account: str | None = None
    payment_vodafone_cash_number: str | None = None
    payment_bank_details: str | None = None
    storage_backend: str = "local"
    cookie_secure: bool | None = None
    # Knowledge Center ingestion was removed. Direct assessment extraction
    # does not dispatch Celery tasks; do not require a nonexistent consumer.
    ingestion_backend: Literal['disabled', 'celery'] = "disabled"
    allow_local_ingestion: bool = False
    payment_receipt_max_mb: int = Field(default=10, ge=1, le=25)
    trusted_proxies: str = "127.0.0.1,::1"
    rate_limit_login: int = Field(default=15, ge=1, le=1000)
    rate_limit_read: int = Field(default=600, ge=1, le=10000)
    rate_limit_upload: int = Field(default=60, ge=1, le=1000)
    rate_limit_quiz_extraction: int = Field(default=30, ge=1, le=1000)
    rate_limit_pdf_render: int = Field(default=240, ge=1, le=10000)
    rate_limit_heavy_query: int = Field(default=60, ge=1, le=1000)
    rate_limit_api_default: int = Field(default=600, ge=1, le=10000)
    rate_limit_window_seconds: int = Field(default=60, ge=1, le=3600)
    # Max simultaneous video playback sessions per (account, lesson) pair.
    video_max_concurrent_sessions: int = Field(default=2, ge=1, le=10)
    video_direct_upload_enabled: bool = False
    # Enable only after a separate FFmpeg video worker is running.
    video_processing_enabled: bool = False
    video_upload_public_endpoint: str | None = None
    video_drm_required: bool = False

    @model_validator(mode="after")
    def validate_video_upload_endpoint(self) -> "Settings":
        from urllib.parse import urlsplit
        if self.video_direct_upload_enabled:
            endpoint = urlsplit(self.video_upload_public_endpoint or "")
            if endpoint.scheme != "https" or not endpoint.netloc or endpoint.path not in {"", "/"} or endpoint.query or endpoint.fragment or endpoint.username:
                raise ValueError("Direct video uploads require an HTTPS origin without a path or credentials")
            if self.storage_backend.lower() not in {"s3", "r2", "minio"}:
                raise ValueError("Direct video uploads require object storage")
        return self

    @property
    def secure_cookies(self) -> bool:
        if self.cookie_secure is not None:
            return self.cookie_secure
        return self.deployment_environment

    @property
    def deployment_environment(self) -> bool:
        return is_deployment_environment(self.app_env)

    @model_validator(mode="after")
    def validate_production_secret(self) -> "Settings":
        self.app_env = self.app_env.strip().lower()
        if self.app_env not in {'development', 'test', 'testing', 'production', 'production_like', 'staging'}:
            raise ValueError('Unsupported APP_ENV; do not silently treat a deployment as development')
        if self.deployment_environment and (len(self.secret_key.strip()) < 32 or self.secret_key.strip().lower() in {
            'development-only-change-me', 'test-secret-key-that-is-long-enough',
            'change-me-before-production-please', 'your-secret-key-here-change-this-now',
            'local-docker-production-secret-key-at-least-32-chars-long'}):
            raise ValueError("SECRET_KEY must be replaced before production startup")
        if self.deployment_environment and not self.secure_cookies:
            raise ValueError('Secure cookies must remain enabled in deployment environments')
        if self.deployment_environment and os.getenv('DISABLE_RATE_LIMITING', '').lower() in {'1', 'true', 'yes'}:
            raise ValueError('Rate limiting cannot be disabled in deployment environments')
        if self.deployment_environment and (
            not self.cors_origins or any(not origin.startswith("https://") for origin in self.cors_origins)
        ):
            raise ValueError("FRONTEND_ORIGINS must use HTTPS in production")
        if self.deployment_environment and self.email_enabled and self.email_provider == 'resend' and (
            not self.resend_api_key or not self.resend_api_key.get_secret_value().strip()
            or not self.email_from_email or not self.email_from_email.strip()
        ):
            raise ValueError('RESEND_API_KEY and EMAIL_FROM_EMAIL are required when Resend delivery is enabled')
        if self.deployment_environment and self.email_enabled and self.email_provider == 'smtp' and not all(
            (self.smtp_host, self.smtp_user, self.smtp_password, self.smtp_from_email)
        ):
            raise ValueError("SMTP delivery must be configured before production startup")
        if self.deployment_environment and self.email_enabled and self.email_provider == 'smtp' and not self.smtp_tls_verify:
            raise ValueError("SMTP TLS certificate verification must remain enabled in production")
        if self.deployment_environment and not any(
            (self.payment_instapay_account, self.payment_vodafone_cash_number, self.payment_bank_details)
        ):
            raise ValueError("At least one payment destination must be configured before production startup")
        return self

    @property
    def cors_origins(self) -> list[str]:
        raw = (self.frontend_origins or "").strip()
        origins: list[str] = []
        if raw.startswith("[") and raw.endswith("]"):
            import json
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    origins = [str(item).strip() for item in parsed if str(item).strip()]
            except Exception:
                pass
        if not origins and raw:
            origins = [origin.strip() for origin in raw.split(",") if origin.strip()]

        if not self.deployment_environment:
            default_exact = [
                "https://mr-hassan-chemistry-platform.vercel.app",
                "https://mr-hassan-chemistry.vercel.app",
                "http://localhost:5173",
                "http://127.0.0.1:5173",
            ]
            for d in default_exact:
                if d not in origins:
                    origins.append(d)
        return origins

    @property
    def cors_origin_regex(self) -> str | None:
        """Allow only this project's Vercel previews, never an arbitrary origin."""
        configured = os.getenv("CORS_ORIGIN_REGEX", "").strip()
        if configured:
            # Validate configuration now so a malformed deployment variable
            # fails closed rather than silently widening CORS.
            re.compile(configured)
            return configured
        if self.deployment_environment:
            return None
        return r"^https://mr-hassan-chemistry-platform-[a-z0-9]+-body19\.vercel\.app$"

    @property
    def sqlalchemy_database_url(self) -> str:
        """Use psycopg v3 for provider URLs that omit a SQLAlchemy driver."""
        if self.database_url.startswith("postgres://"):
            return self.database_url.replace("postgres://", "postgresql+psycopg://", 1)
        if self.database_url.startswith("postgresql://"):
            return self.database_url.replace("postgresql://", "postgresql+psycopg://", 1)
        return self.database_url


@lru_cache
def get_settings() -> Settings:
    return Settings()


def get_tesseract_cmd() -> str | None:
    """Discovers and configures the Tesseract OCR executable path cleanly."""
    import os
    import shutil
    try:
        import pytesseract
    except ImportError:
        return None

    settings = get_settings()
    local_app_data = os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe")
    candidates = [
        settings.tesseract_cmd,
        os.getenv("TESSERACT_CMD"),
        shutil.which("tesseract"),
        local_app_data,
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        "/usr/bin/tesseract",
        "/usr/local/bin/tesseract",
    ]
    for c in candidates:
        if c:
            clean_path = os.path.expandvars(str(c))
            if os.path.exists(clean_path):
                pytesseract.pytesseract.tesseract_cmd = clean_path
                return clean_path
    return None
