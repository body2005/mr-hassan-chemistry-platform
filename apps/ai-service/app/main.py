from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.config import get_settings
from app.core.exceptions import (
    AdmissionLimitExceededException,
    AIServiceException,
    ModelInferenceException,
    ProviderUnavailableException,
    RateLimitExceededException,
    SchemaValidationException,
    UnsupportedGradingTypeException,
)
from app.core.logging import logger, setup_logging
from app.core.middleware import TelemetryMiddleware
from app.providers.factory import get_ai_provider


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    setup_logging(settings.LOG_LEVEL)
    
    # Resolve and log the active provider and model explicitly at startup
    provider = get_ai_provider()
    active_model = settings.OLLAMA_MODEL if settings.DEFAULT_PROVIDER in ["ollama", "local"] else settings.EXTERNAL_MODEL
    
    logger.info("=" * 70)
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION} [Environment: {settings.ENVIRONMENT}]")
    logger.info(f"ACTIVE AI PROVIDER : {provider.__class__.__name__} (Key: {settings.DEFAULT_PROVIDER})")
    logger.info(f"ACTIVE LOCAL MODEL  : {active_model}")
    logger.info(f"ADMISSION LIMIT     : Max {settings.MAX_CONCURRENT_INTERACTIVE_INFERENCES} concurrent GPU inferences")
    logger.info("=" * 70)
    
    yield
    logger.info(f"Shutting down {settings.APP_NAME}...")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="Dedicated AI and predictive intelligence service for LMS backend.",
        lifespan=lifespan
    )

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "X-API-Key", "X-Cache-Bypass", "X-Request-ID"],
    )

    # Telemetry and process time tracking middleware
    app.add_middleware(TelemetryMiddleware)

    # Register Exception Handlers
    @app.exception_handler(AdmissionLimitExceededException)
    async def admission_limit_handler(request: Request, exc: AdmissionLimitExceededException):
        headers = {"Retry-After": str(exc.retry_after)}
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": "GPU_CAPACITY_SATURATED",
                "message": exc.message,
                "details": exc.details
            },
            headers=headers
        )

    @app.exception_handler(RateLimitExceededException)
    async def rate_limit_handler(request: Request, exc: RateLimitExceededException):
        headers = {"Retry-After": str(exc.retry_after)}
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": "RATE_LIMIT_EXCEEDED",
                "message": exc.message,
                "details": exc.details
            },
            headers=headers
        )

    @app.exception_handler(ProviderUnavailableException)
    async def provider_unavailable_handler(request: Request, exc: ProviderUnavailableException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": "AI_PROVIDER_UNAVAILABLE",
                "message": exc.message,
                "details": exc.details
            }
        )

    @app.exception_handler(SchemaValidationException)
    async def schema_validation_handler(request: Request, exc: SchemaValidationException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": "OUTPUT_SCHEMA_VALIDATION_ERROR",
                "message": exc.message,
                "details": exc.details
            }
        )

    @app.exception_handler(UnsupportedGradingTypeException)
    async def unsupported_grading_handler(request: Request, exc: UnsupportedGradingTypeException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": "UNSUPPORTED_OBJECTIVE_GRADING_TYPE",
                "message": exc.message,
                "details": exc.details
            }
        )

    @app.exception_handler(AIServiceException)
    async def ai_service_exception_handler(request: Request, exc: AIServiceException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": "AI_SERVICE_ERROR",
                "message": exc.message,
                "details": exc.details
            }
        )

    # Mount API v1 router
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    return app


app = create_app()
