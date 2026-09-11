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
        return [origin.strip() for origin in self.frontend_origins.split(",") if origin.strip()]


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


