"""Unified API error standard.

Every error leaving the API has the shape:
    {"error": {"code": "...", "message": "..."}, "request_id": "..."}
"""
from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

_VALIDATION_STATUS = getattr(
    status, "HTTP_422_UNPROCESSABLE_CONTENT", 422
)


class ApiError(Exception):
    """Domain-level error carrying a stable machine code."""

    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


_STATUS_TO_CODE = {
    status.HTTP_400_BAD_REQUEST: "BAD_REQUEST",
    status.HTTP_401_UNAUTHORIZED: "UNAUTHENTICATED",
    status.HTTP_403_FORBIDDEN: "FORBIDDEN",
    status.HTTP_404_NOT_FOUND: "NOT_FOUND",
    status.HTTP_409_CONFLICT: "CONFLICT",
    status.HTTP_429_TOO_MANY_REQUESTS: "RATE_LIMITED",
}

try:  # Starlette >= 0.41 renamed the constant
    _STATUS_TO_CODE[status.HTTP_422_UNPROCESSABLE_CONTENT] = "VALIDATION_ERROR"
except AttributeError:
    pass


def _error_payload(request: Request, code: str, message: str) -> dict:
    request_id = getattr(getattr(request, "state", None), "request_id", None)
    return {"error": {"code": code, "message": message}, "request_id": request_id}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_payload(request, exc.code, exc.message),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        # Rate limiter attaches structured detail dicts; pass codes through.
        if isinstance(exc.detail, dict) and "code" in exc.detail:
            content = _error_payload(request, exc.detail["code"], exc.detail.get("message", ""))
        else:
            code = _STATUS_TO_CODE.get(exc.status_code, "ERROR")
            content = _error_payload(request, code, str(exc.detail))
        response = JSONResponse(status_code=exc.status_code, content=content)
        if exc.headers:
            response.headers.update(exc.headers)
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {}
        loc = ".".join(str(part) for part in first.get("loc", []) if part != "body")
        message = f"Invalid value for '{loc}'" if loc else "Invalid request payload"
        return JSONResponse(
            status_code=_VALIDATION_STATUS,
            content=_error_payload(request, "VALIDATION_ERROR", message),
        )
