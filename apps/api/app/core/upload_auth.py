"""Validate file-upload identity before parsing, spooling or acquiring leases.

Route dependencies still enforce resource ownership and repeat validation at
use time. This guard reuses the same revocation/role/family checks, never just
the presence or signature of a token. It does not read the ASGI body.
"""
import re

from fastapi import HTTPException, Request
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse

from app.api.dependencies import get_current_user
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.rate_limit import enforce_rate_limit
from app.models.user import UserRole


class UploadAuthenticationMiddleware:
    def __init__(self, app, classify):
        self.app = app
        self.classify = classify

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope['method'] != 'POST':
            return await self.app(scope, receive, send)
        prefix = get_settings().api_v1_prefix
        path = scope['path']
        manager = re.fullmatch(re.escape(prefix) + r'/lessons/[^/]+/(video|materials)/?', path)
        extraction = path.rstrip('/') == prefix + '/quiz/extract-from-file'
        student = re.fullmatch(re.escape(prefix) +
            r'/(assignments/[^/]+/submissions/file|payments/orders/[^/]+/receipt)/?', path)
        if not (manager or extraction or student):
            return await self.app(scope, receive, send)
        request = Request(scope)  # No receive callback: authentication cannot read body.
        def authenticate():
            # Keep the existing per-category limiter even on early denials.
            # Its request policy set prevents charging authenticated requests
            # twice when the ordinary security middleware executes later.
            category = self.classify(scope['method'], path)
            enforce_rate_limit(request, category=category)
            with SessionLocal() as db:
                user = get_current_user(request, db,
                    request.cookies.get(get_settings().session_cookie_name))
                allowed = ({UserRole.STUDENT} if student else
                    {UserRole.TEACHER, UserRole.INSTITUTION_ADMIN, UserRole.PLATFORM_ADMIN})
                if user.role not in allowed:
                    raise HTTPException(403, 'Insufficient permissions')
        try:
            await run_in_threadpool(authenticate)
        except HTTPException as exc:
            return await JSONResponse({'detail': exc.detail}, status_code=exc.status_code,
                                      headers=exc.headers)(scope, receive, send)
        except SQLAlchemyError:
            return await JSONResponse({'detail': 'Authentication service unavailable'},
                status_code=503, headers={'Retry-After': '1'})(scope, receive, send)
        return await self.app(scope, receive, send)
