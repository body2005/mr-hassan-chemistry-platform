from __future__ import annotations

import json
import os
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.dependencies import CurrentUser
from app.core.database import get_db
from app.core.rate_limit import enforce_rate_limit
from app.models.course import Course
from app.models.transcript import TranscriptionJob, TranscriptionJobStatus
from app.models.user import UserRole
from app.services.transcription_job_manager import TranscriptionJobManager

router = APIRouter(prefix="/transcription", tags=["transcription"])
Db = Annotated[Session, Depends(get_db)]


class CallbackPayload(BaseModel):
    status: str = "completed"
    video_id: str | None = None
    lesson_id: str | None = None
    course_id: str | None = None
    duration: float = 0.0
    full_text: str = ""
    language: str = "ar"
    segments: list[dict[str, Any]] = Field(default_factory=list)
    artifact_url: str | None = None
    error_code: str | None = None
    message: str | None = None


@router.get("/download/{token}")
def download_scoped_video(token: str, request: Request, db: Db) -> FileResponse:
    """
    Secure scoped media download endpoint for authorized remote compute workers.
    Validates token expiration and cryptographically verifies the download scope.
    """
    enforce_rate_limit(request, bucket="read", limit=60, window_seconds=60)
    filepath = TranscriptionJobManager.resolve_download_file(db, token)
    if not filepath or not os.path.isfile(filepath):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "EXPIRED_OR_INVALID_TOKEN", "message": "Download link is invalid or has expired."},
        )

    return FileResponse(
        filepath,
        media_type="application/octet-stream",
        filename=os.path.basename(filepath),
    )


@router.post("/jobs/{job_id}/callback")
async def job_callback(
    job_id: uuid.UUID,
    request: Request,
    db: Db,
    x_callback_auth: Annotated[str | None, Header(alias="X-Callback-Auth")] = None,
    x_signature_sha256: Annotated[str | None, Header(alias="X-Signature-SHA256")] = None,
    x_timestamp: Annotated[str | None, Header(alias="X-Timestamp")] = None,
) -> dict[str, Any]:
    """
    Secure callback endpoint invoked by the remote GPU worker upon transcription completion or failure.
    Authenticated via HMAC-SHA256 signature, scoped token, and timestamp replay protection.
    """
    auth_header = x_signature_sha256 or x_callback_auth
    body_bytes = await request.body()
    try:
        payload_data = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    result = await TranscriptionJobManager.process_callback(
        db=db,
        job_id=job_id,
        payload=payload_data,
        auth_header=auth_header,
        body_bytes=body_bytes,
        timestamp=x_timestamp,
    )

    if "error" in result:
        err_code = result["error"]
        if err_code == "UNAUTHORIZED":
            raise HTTPException(status_code=401, detail="Unauthorized callback signature")
        if err_code == "JOB_NOT_FOUND":
            raise HTTPException(status_code=404, detail="Job not found")
        if err_code in {"VIDEO_MISMATCH", "LESSON_MISMATCH"}:
            raise HTTPException(status_code=403, detail=result.get("message", "Isolation violation"))
        raise HTTPException(status_code=422, detail=result.get("message", "Processing error"))

    return result


@router.get("/jobs/{job_id}")
def get_job_status(job_id: uuid.UUID, db: Db, user: CurrentUser) -> dict[str, Any]:
    """Query the live progress, stage, and metadata of a transcription job."""
    job = db.get(TranscriptionJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Transcription job not found")
    course = db.get(Course, job.course_id)
    if not course or (user.role != UserRole.PLATFORM_ADMIN and course.institution_id != user.institution_id):
        raise HTTPException(status_code=404, detail="Transcription job not found")

    return {
        "job_id": str(job.id),
        "lesson_id": str(job.lesson_id),
        "course_id": str(job.course_id),
        "video_id": str(job.video_id),
        "status": str(job.status.value if hasattr(job.status, "value") else job.status),
        "provider": job.provider,
        "model_name": job.model_name,
        "progress_percent": job.progress_percent,
        "stage": job.current_stage,
        "duration_seconds": job.duration_seconds,
        "segment_count": job.segment_count,
        "chunk_count": job.chunk_count,
        "coverage_ratio": job.coverage_ratio,
        "error_code": job.error_code,
        "error_message": job.error_message,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }
