import secrets
from fastapi import Header, HTTPException, Security, status
from app.config import get_settings


async def verify_api_key(
    x_api_key: str = Header(None, alias="X-API-Key")
) -> bool:
    """
    Validates the X-API-Key header against configured settings.
    If API_KEY is not configured (e.g. in local dev/testing), requests are allowed.
    """
    settings = get_settings()
    if not settings.API_KEY:
        if settings.ENVIRONMENT in {"development", "test"}:
            return True
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service authentication is not configured",
        )

    if not x_api_key or not secrets.compare_digest(x_api_key, settings.API_KEY):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-API-Key header",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return True
