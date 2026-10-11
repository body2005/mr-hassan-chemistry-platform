"""Binary byte limits; multipart envelope is NOT included in the file budget."""
import shutil
import tempfile

from fastapi import HTTPException

MAX_VIDEO_BYTES = 5 * 1024**3  # 5 GiB = 5,368,709,120 bytes
MAX_MATERIAL_BYTES = 1024**3  # 1 GiB = 1,073,741,824 bytes
MULTIPART_HEADROOM = 1024**2


def ensure_staging_capacity(size: int, directory: str | None = None) -> None:
    # Starlette's rolled multipart upload and application staging can coexist.
    free = shutil.disk_usage(directory or tempfile.gettempdir()).free
    if free < size + 256 * 1024**2:
        raise HTTPException(507, "Insufficient temporary storage for this upload")


class UploadBudgetMiddleware:
    """Reject known oversized payloads before multipart parsing allocates disk."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        limit = None
        if scope["type"] == "http" and scope["method"] == "POST":
            from app.core.config import get_settings
            path = scope["path"]
            if path.endswith("/video") and "/lessons/" in path:
                limit = MAX_VIDEO_BYTES
            elif path.endswith("/materials") and "/lessons/" in path:
                limit = MAX_MATERIAL_BYTES
            elif path.endswith("/submissions/file") and "/assignments/" in path:
                limit = MAX_MATERIAL_BYTES
            elif path.endswith("/receipt") and "/payments/orders/" in path:
                limit = get_settings().payment_receipt_max_mb * 1024**2
            elif path.rstrip("/").endswith("/quiz/extract-from-file"):
                limit = get_settings().max_request_size_mb * 1024**2
        if limit is not None:
            headers = dict(scope.get("headers", []))
            try:
                size = int(headers.get(b"content-length", b"0"))
                if size < 0 or size > limit + MULTIPART_HEADROOM:
                    raise HTTPException(413, "Upload exceeds the allowed byte limit")
                ensure_staging_capacity((size or limit + MULTIPART_HEADROOM) * 2)
            except (HTTPException, ValueError) as exc:
                from fastapi.responses import JSONResponse
                response = JSONResponse({"detail": str(getattr(exc, "detail", "Invalid Content-Length"))},
                                         status_code=getattr(exc, "status_code", 400))
                return await response(scope, receive, send)
            from app.core.leases import ResourceLease
            # Bounds multipart spool + staging + S3 transfer work across workers.
            lease = ResourceLease([("upload:global", 2)], global_index=1)
            try:
                await lease.acquire()
            except HTTPException as exc:
                from fastapi.responses import JSONResponse
                return await JSONResponse({"detail": exc.detail}, status_code=exc.status_code,
                                          headers=exc.headers)(scope, receive, send)
            consumed = 0
            async def bounded_receive():
                nonlocal consumed
                message = await receive()
                if message["type"] == "http.request":
                    consumed += len(message.get("body", b""))
                    if consumed > limit + MULTIPART_HEADROOM:
                        # Starlette closes its rolled multipart temporary files
                        # when this HTTPException interrupts parsing.
                        raise HTTPException(413, "Upload exceeds the allowed byte limit")
                return message
            try:
                return await lease.run(self.app, scope, bounded_receive, send)
            finally:
                await lease.release()
        return await self.app(scope, receive, send)
