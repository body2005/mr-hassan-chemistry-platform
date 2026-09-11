import time
import uuid
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from app.core.telemetry import telemetry
from app.core.logging import logger


class TelemetryMiddleware(BaseHTTPMiddleware):
    """
    Middleware that captures request duration, status codes, assigns correlation IDs,
    and updates the service telemetry store.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Correlation ID
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id

        # Determine domain from path
        path = request.url.path
        domain = "other"
        for candidate in ["quiz", "grading", "tutor", "analytics", "risk", "reports", "system"]:
            if f"/{candidate}" in path:
                domain = candidate
                break

        start_time = time.perf_counter()
        status_code = 500
        
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception as exc:
            telemetry.record_error(exc.__class__.__name__, domain)
            logger.error(f"Unhandled exception on {request.method} {path}: {str(exc)}", exc_info=True)
            raise
        finally:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            
            # Check if cache hit was flagged on request state
            is_cached = getattr(request.state, "cache_hit", False)
            
            telemetry.record_request(
                domain=domain,
                endpoint=f"{request.method}:{path}",
                status_code=status_code,
                duration_ms=duration_ms,
                cached=is_cached
            )

            # If response exists, attach headers
            if 'response' in locals() and response is not None:
                response.headers["X-Request-ID"] = request_id
                response.headers["X-Process-Time-Ms"] = f"{duration_ms:.2f}"
