"""Owner-scoped resumable upload control plane (S3 multipart, not wire tus)."""
import uuid
import re
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import CurrentUser
from app.core.config import get_settings
from app.core.database import get_db
from app.core.rate_limit import enforce_rate_limit
from app.models.course import Lesson
from app.models.user import UserRole
from app.services import platform_service, video_uploads as service

router = APIRouter()
Db = Annotated[Session, Depends(get_db)]


def bounded_quality_manifest(manifest: str) -> str:
    lines, pending = [], None
    for line in manifest.splitlines():
        if line.startswith("#EXT-X-STREAM-INF:"):
            pending = line
        elif pending is not None and line and not line.startswith("#"):
            resolution = re.search(r"RESOLUTION=\d+x(\d+)", pending)
            named = re.match(r"(\d+)p/", line)
            height = int(resolution.group(1)) if resolution else int(named.group(1)) if named else 0
            if height <= 1080:
                lines.extend([pending, line])
            pending = None
        else:
            lines.append(line)
    return "\n".join(lines) + "\n"


class CreateUpload(BaseModel):
    filename: str = Field(min_length=1, max_length=200)
    size_bytes: int = Field(gt=0)
    content_type: str = Field(max_length=80)
    fingerprint: str = Field(min_length=64, max_length=64)
    request_key: str = Field(min_length=8, max_length=64)


def manager(db, user, lesson_id):
    from app.api.routes.platform import _lesson_course
    lesson, course = _lesson_course(db, lesson_id)
    if user.role == UserRole.STUDENT:
        raise HTTPException(403, "Teacher upload access required")
    if user.role != UserRole.PLATFORM_ADMIN and course.institution_id != user.institution_id:
        raise HTTPException(404, "Lesson not found")
    try:
        platform_service.ensure_course_manager(user, course)
    except PermissionError as exc:
        raise HTTPException(403, "Course manager access required") from exc
    return lesson


@router.get("/video-upload-capabilities")
def capabilities(user: CurrentUser, response: Response) -> dict:
    response.headers["Cache-Control"] = "private, no-store"
    settings = get_settings()
    return {"direct_upload": settings.video_direct_upload_enabled,
            "processing_enabled": settings.video_processing_enabled,
            "protocol": "s3-multipart", "max_bytes": service.MAX_VIDEO_BYTES,
            "part_bytes": service.PART_BYTES, "drm_required": settings.video_drm_required}


@router.post("/lessons/{lesson_id}/video-uploads", status_code=201)
def create_upload(lesson_id: uuid.UUID, payload: CreateUpload, user: CurrentUser, db: Db, request: Request, response: Response):
    response.headers["Cache-Control"] = "private, no-store"
    enforce_rate_limit(request, bucket="video-upload-create", limit=5, window_seconds=60)
    lesson = manager(db, user, lesson_id)
    upload = service.create(db, user, lesson, payload)
    # Relock after the durable 'creating' intent commit, serialize storage init.
    upload = service.owned(db, upload.id, user, lock=True)
    service.initialize(db, upload)
    # initialize commits; refresh/relock before interpreting ListParts failure.
    upload = service.owned(db, upload.id, user, lock=True)
    return service.summary(upload, service.recover_parts(db, upload) if upload.status == "uploading" else [])


@router.post("/lessons/{lesson_id}/prepare-video", status_code=202)
def prepare_stored_video(lesson_id: uuid.UUID, user: CurrentUser, db: Db, request: Request, response: Response):
    response.headers["Cache-Control"] = "private, no-store"
    enforce_rate_limit(request, bucket="video-prepare", limit=5, window_seconds=60)
    lesson = manager(db, user, lesson_id)
    upload = service.enqueue_published_source(db, user, lesson)
    db.commit()
    return service.summary(upload)


@router.get("/video-uploads/{upload_id}")
def get_upload(upload_id: uuid.UUID, user: CurrentUser, db: Db, request: Request, response: Response):
    response.headers["Cache-Control"] = "private, no-store"
    enforce_rate_limit(request, bucket="video-upload-control", category="read")
    upload = service.owned(db, upload_id, user, lock=True)
    manager(db, user, upload.lesson_id)
    return service.summary(upload, service.recover_parts(db, upload) if upload.status == "uploading" else [])


@router.post("/video-uploads/{upload_id}/parts/{number}")
def sign_part(upload_id: uuid.UUID, number: int, user: CurrentUser, db: Db, request: Request, response: Response):
    response.headers["Cache-Control"] = "private, no-store"
    enforce_rate_limit(request, bucket="video-upload-control", category="read")
    upload = service.owned(db, upload_id, user)
    manager(db, user, upload.lesson_id)
    return service.sign_part(upload, number)


@router.post("/video-uploads/{upload_id}/complete", status_code=202)
def complete_upload(upload_id: uuid.UUID, user: CurrentUser, db: Db, request: Request, response: Response):
    response.headers["Cache-Control"] = "private, no-store"
    enforce_rate_limit(request, bucket="video-upload-control", category="read")
    upload = service.owned(db, upload_id, user, lock=True)
    manager(db, user, upload.lesson_id)
    # A session-level advisory lock survives the recovery commit inside complete.
    # On a crash PostgreSQL releases it. SQLite is used only in serial unit tests.
    if db.bind.dialect.name == "postgresql":
        from sqlalchemy import text
        with db.bind.connect().execution_options(isolation_level="AUTOCOMMIT") as guard:
            key = int.from_bytes(upload.id.bytes[:8], "big", signed=True)
            if not guard.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": key}):
                raise HTTPException(409, "Completion is already running; check upload status")
            try:
                service.complete(db, upload)
            finally:
                guard.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": key})
    else:
        service.complete(db, upload)
    return service.summary(upload)


@router.delete("/video-uploads/{upload_id}", status_code=204)
def abort_upload(upload_id: uuid.UUID, user: CurrentUser, db: Db, request: Request):
    enforce_rate_limit(request, bucket="video-upload-control", category="read")
    upload = service.owned(db, upload_id, user, lock=True)
    manager(db, user, upload.lesson_id)
    if db.bind.dialect.name == "postgresql":
        from sqlalchemy import text
        with db.bind.connect().execution_options(isolation_level="AUTOCOMMIT") as guard:
            key = int.from_bytes(upload.id.bytes[:8], "big", signed=True)
            if not guard.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": key}):
                raise HTTPException(409, "Video processing or completion has already started")
            try:
                service.abort(db, upload)
            finally:
                guard.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": key})
    else:
        service.abort(db, upload)


@router.post('/video-uploads/{upload_id}/retry', status_code=202)
def retry_upload(upload_id: uuid.UUID, user: CurrentUser, db: Db, request: Request, response: Response):
    response.headers['Cache-Control'] = 'private, no-store'
    enforce_rate_limit(request, bucket='video-upload-retry', category='upload', limit=5, window_seconds=300)
    upload = service.owned(db, upload_id, user, lock=True)
    manager(db, user, upload.lesson_id)
    service.retry_processing(db, upload)
    return service.summary(upload)


def authorized_drm_asset(lesson_id, upload_id, request, db, token):
    from app.api.routes.platform import _authorize_video_stream
    from app.services.video_drm import current_asset
    lesson = _authorize_video_stream(lesson_id, request, db, token)
    asset = current_asset(db, lesson)
    if not lesson.video_drm_protected or not asset or asset.id != upload_id or not asset.drm:
        raise HTTPException(404, 'Encrypted video generation not found')
    return lesson, asset


@router.get('/lessons/{lesson_id}/hls/{upload_id}/drm/certificate')
def drm_certificate(lesson_id: uuid.UUID, upload_id: uuid.UUID, request: Request, db: Db, token: str | None = None):
    from app.services.video_drm import fairplay_certificate
    authorized_drm_asset(lesson_id, upload_id, request, db, token)
    return Response(fairplay_certificate(), media_type='application/octet-stream',
        headers={'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff'})


@router.post('/lessons/{lesson_id}/hls/{upload_id}/drm/license/{system}')
async def drm_license(lesson_id: uuid.UUID, upload_id: uuid.UUID, system: str, request: Request, db: Db, token: str | None = None):
    import httpx
    from app.services.video_drm import LICENSE_ENDPOINTS, license_message
    from app.core.security import decode_video_token
    if system not in LICENSE_ENDPOINTS:
        raise HTTPException(404, 'DRM system not supported')
    enforce_rate_limit(request, bucket='drm-license', limit=12, window_seconds=60)
    lesson, asset = authorized_drm_asset(lesson_id, upload_id, request, db, token)
    claims = decode_video_token(token) or {}
    subject = claims.get('sub')
    # _authorize_video_stream has already checked subject, active cookie/family,
    # revocation, institution, schedule and current entitlement. Never accept a
    # client key ID or provider URL in place of this exact generation.
    entitlement = license_message(asset, lesson, str(subject), is_student=claims.get('role') == 'student')
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 256 * 1024:
            raise HTTPException(413, 'DRM challenge is too large')
    if not body:
        raise HTTPException(422, 'DRM challenge is required')
    db.close()
    result = bytearray()
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=False, trust_env=False) as client:
            async with client.stream('POST', LICENSE_ENDPOINTS[system], content=bytes(body),
                    headers={'Content-Type': 'application/octet-stream', 'X-AxDRM-Message': entitlement}) as upstream:
                if upstream.status_code != 200:
                    raise HTTPException(503 if upstream.status_code >= 500 or upstream.status_code == 429 else 403, 'DRM license could not be issued')
                async for chunk in upstream.aiter_bytes():
                    result.extend(chunk)
                    if len(result) > 2 * 1024 * 1024:
                        raise HTTPException(502, 'DRM license response is invalid')
    except httpx.HTTPError:
        # No provider exceptions/bodies/headers: they can contain entitlements.
        raise HTTPException(503, 'DRM license service is temporarily unavailable') from None
    if not result:
        raise HTTPException(502, 'DRM license response is invalid')
    # Re-check revocation/generation changes during the external request.
    db.expire_all()
    authorized_drm_asset(lesson_id, upload_id, request, db, token)
    return Response(bytes(result), media_type='application/octet-stream', headers={
        'Cache-Control': 'private, no-store', 'Referrer-Policy': 'no-referrer',
        'X-Content-Type-Options': 'nosniff', 'Cross-Origin-Resource-Policy': 'same-origin'})


@router.get("/lessons/{lesson_id}/hls/{upload_id}/{name:path}")
def hls(lesson_id: uuid.UUID, upload_id: uuid.UUID, name: str, request: Request, db: Db, token: str | None = None):
    import posixpath
    from urllib.parse import quote
    from fastapi.responses import StreamingResponse
    from app.api.routes.platform import _authorize_video_stream, _parse_byte_range
    from app.models.video_upload import VideoUpload
    from app.core.storage import get_storage_provider
    lesson = _authorize_video_stream(lesson_id, request, db, token)
    upload = db.get(VideoUpload, upload_id)
    if upload is None or upload.lesson_id != lesson_id or upload.status != "ready" or not upload.manifest_key:
        raise HTTPException(404, "Video generation not found")
    if not lesson.video_asset_key or not lesson.video_asset_key.endswith(f"/{upload.manifest_key}"):
        raise HTTPException(404, "Video generation is no longer current")
    if lesson.video_drm_protected and (not upload.drm or upload.drm.get('scheme') != 'cbcs'
            or not name.endswith(('.m3u8', '.mp4', '.m4s'))):
        raise HTTPException(403, 'Clear playback is forbidden for this video')
    if name.startswith("/") or ".." in name.split("/") or "\\" in name:
        raise HTTPException(404, "Video part not found")
    rendition = re.match(r"(\d+)p/", name)
    if rendition and int(rendition.group(1)) > 1080:
        raise HTTPException(404, "Video part not found")
    prefix = posixpath.dirname(upload.manifest_key)
    key = f"{prefix}/{name}"
    if key not in upload.outputs:
        raise HTTPException(404, "Video part not found")
    db.close()
    provider = get_storage_provider()
    headers = {"Cache-Control": "private, no-store", "Referrer-Policy": "no-referrer",
        "X-Content-Type-Options": "nosniff", "Cross-Origin-Resource-Policy": "same-origin"}
    try:
        size = provider.get_size(key)
        if name.endswith(".m3u8"):
            if size > 1024 * 1024:
                raise HTTPException(503, "Video manifest unavailable")
            manifest = b"".join(provider.open_stream(key, length=size)).decode("utf-8")
            if name == "master.m3u8":
                manifest = bounded_quality_manifest(manifest)
            lines = []
            def admitted_uri(uri):
                target = posixpath.normpath(posixpath.join(posixpath.dirname(name), uri))
                if f'{prefix}/{target}' not in upload.outputs:
                    raise HTTPException(503, 'Video manifest unavailable')
                return f'/api/v1/lessons/{lesson_id}/hls/{upload_id}/{quote(target)}?token={quote(token or "")}'
            for line in manifest.splitlines():
                if line and not line.startswith("#"):
                    line = admitted_uri(line)
                elif 'URI="' in line:
                    def rewrite_attribute(match):
                        uri = match.group(1)
                        # DRM signaling contains public KIDs/PSSH, never keys.
                        # MAP/MEDIA references must always traverse admission.
                        if upload.drm and line.startswith(('#EXT-X-KEY:', '#EXT-X-SESSION-KEY:')) and uri.startswith(('skd://', 'data:')):
                            return match.group(0)
                        return f'URI="{admitted_uri(uri)}"'
                    line = re.sub(r'URI="([^"]+)"', rewrite_attribute, line)
                lines.append(line)
            return Response("\n".join(lines) + "\n", media_type="application/vnd.apple.mpegurl", headers=headers)
        byte_range = _parse_byte_range(request.headers.get("range"), size)
        start, end = byte_range if byte_range else (0, size - 1)
        length = end - start + 1
        headers["Content-Length"] = str(length)
        headers["Accept-Ranges"] = "bytes"
        if byte_range:
            headers["Content-Range"] = f"bytes {start}-{end}/{size}"
        return StreamingResponse(provider.open_stream(key, start=start, length=length), status_code=206 if byte_range else 200,
            media_type=('audio/mp4' if name.startswith('audio/') else 'video/mp4' if name.endswith(('.mp4', '.m4s')) else 'video/mp2t'), headers=headers)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(503, "Video storage temporarily unavailable") from exc
