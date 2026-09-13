from functools import lru_cache
from dotenv import load_dotenv

load_dotenv()

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Learning Website"
    app_env: str = "development"
    api_v1_prefix: str = "/api/v1"
    secret_key: str = Field(default="development-only-change-me", min_length=16)
    gemini_api_key: str | None = None
    groq_api_key: str | None = None
    groq_model: str = "qwen/qwen3.6-27b"
    qa_model: str = "gemini-2.5-flash"
    session_cookie_name: str = "matgar_session"
    csrf_cookie_name: str = "matgar_csrf"
    session_ttl_seconds: int = Field(default=60 * 60 * 24 * 30, ge=300, le=60 * 60 * 24 * 365)
    password_reset_ttl_minutes: int = Field(default=30, ge=5, le=24 * 60)
    default_institution_slug: str = "demo"
    database_url: str = "sqlite:///./learning_website.db"
    db_pool_size: int = Field(default=5, ge=1, le=50)
    db_max_overflow: int = Field(default=10, ge=0, le=100)
    db_pool_timeout_seconds: int = Field(default=30, ge=5, le=120)
    db_pool_recycle_seconds: int = Field(default=1800, ge=60, le=7200)
    redis_url: str = "redis://localhost:6379/0"
    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = "learning"
    s3_secret_key: str = "learning-development"
    s3_bucket: str = "learning-website"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"
    frontend_origins: str = "http://localhost:5173"
    kaggle_asr_url: str | None = None
    remote_callback_base_url: str | None = None
    transcription_provider: str = "auto"
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
    student_ai_access_mode: str = Field(
        default="paid_content_or_subscription",
        pattern=r"^(open|subscription_only|included_with_content|paid_content_or_subscription)$",
    )
    student_ai_monthly_price_egp: float = Field(default=99, ge=1, le=1_000_000)
    student_ai_subscription_days: int = Field(default=30, ge=1, le=366)
    payment_instapay_account: str | None = None
    payment_vodafone_cash_number: str | None = None
    payment_bank_details: str | None = None
    payment_receipt_max_mb: int = Field(default=10, ge=1, le=25)

    @property
    def secure_cookies(self) -> bool:
        return self.app_env.lower() == "production"

    @model_validator(mode="after")
    def validate_production_secret(self) -> "Settings":
        if self.secure_cookies and self.secret_key == "development-only-change-me":
            raise ValueError("SECRET_KEY must be replaced before production startup")
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
