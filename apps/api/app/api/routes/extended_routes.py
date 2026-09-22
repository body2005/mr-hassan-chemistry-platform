"""Extended API surface: chapters, lesson assets, question versioning, grades,
report jobs and mastery analytics."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Header, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import CurrentUser, require_roles
from app.core.database import get_db
from app.core.errors import ApiError
from app.models.extended import (
    Chapter,
    Grade,
    LessonAsset,
    QuestionBank,
    QuestionVersion,
    ReportJob,
)
from app.models.platform import Question
from app.models.user import User, UserRole
from app.services import extended_service

router = APIRouter()
Db = Annotated[Session, Depends(get_db)]
Manager = Annotated[
    User,
    Depends(require_roles(UserRole.TEACHER, UserRole.INSTITUTION_ADMIN, UserRole.PLATFORM_ADMIN)),
]


def _translate(exc: Exception) -> HTTPException:
    if isinstance(exc, LookupError):
        raise ApiError("NOT_FOUND", str(exc), status_code=404)
    if isinstance(exc, PermissionError):
        raise ApiError("FORBIDDEN", str(exc), status_code=403)
    if isinstance(exc, ValueError) and str(exc) == "IDEMPOTENCY_KEY_REUSED":
        raise ApiError("IDEMPOTENCY_KEY_REUSED", "Key was already used with a different payload", 409)
    raise ApiError("BAD_REQUEST", str(exc), status_code=400)


# ---------------------------------------------------------------------------
# Schemas (extended)
# ---------------------------------------------------------------------------

class ChapterCreateRequest(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    position: int | None = Field(default=None, ge=1, le=10_000)


class ChapterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    module_id: uuid.UUID
    title: str
    position: int


class LessonAssetCreateRequest(BaseModel):
    asset_kind: str = Field(min_length=2, max_length=40)
    object_key: str | None = Field(default=None, max_length=512)
    external_url: str | None = Field(default=None, max_length=1024)
    filename: str | None = Field(default=None, max_length=255)
    mime_type: str | None = Field(default=None, max_length=120)
    size_bytes: int | None = Field(default=None, ge=0)
    duration_seconds: int | None = Field(default=None, ge=0)


class LessonAssetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    lesson_id: uuid.UUID
    asset_kind: str
    object_key: str | None
    external_url: str | None
    filename: str | None
    mime_type: str | None
    size_bytes: int | None
    duration_seconds: int | None


class QuestionExtCreateRequest(BaseModel):
    course_id: uuid.UUID | None = None
    bank_id: uuid.UUID | None = None
    question_type: str = Field(min_length=2, max_length=40)
    prompt: str = Field(min_length=2, max_length=10_000)
    options: list | None = None
    correct_answer: object | None = None
    points: float = Field(default=1.0, gt=0, le=1000)
    learning_objective: str | None = Field(default=None, max_length=200)
    difficulty: str | None = Field(default=None, max_length=20)
    topic: str | None = Field(default=None, max_length=200)
    explanation: str | None = Field(default=None, max_length=10_000)
    source: str = Field(default="manual", max_length=40)
    ai_generated: bool = False


class QuestionUpdateRequest(BaseModel):
    prompt: str | None = None
    options: list | None = None
    correct_answer: object | None = None
    points: float | None = None
    question_type: str | None = None
    difficulty: str | None = None
    topic: str | None = None
    explanation: str | None = None


class QuestionVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    question_id: uuid.UUID
    version: int
    question_type: str
    prompt: str
    options: list | None
    correct_answer: object | None
    points: float
    explanation: str | None
    difficulty: str | None
    topic: str | None
    source: str | None
    ai_generated: bool


class GradeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    student_id: uuid.UUID
    course_id: uuid.UUID | None
    item_type: str
    item_id: uuid.UUID | None
    score: float
    max_score: float
    feedback: str | None
    graded_by: uuid.UUID | None
    is_current: bool
    updated_at: datetime


class GradeWriteRequest(BaseModel):
    student_id: uuid.UUID
    course_id: uuid.UUID | None = None
    item_type: str = Field(min_length=2, max_length=40)
    item_id: uuid.UUID | None = None
    score: float = Field(ge=0, le=100_000)
    max_score: float = Field(gt=0, le=100_000)
    feedback: str | None = Field(default=None, max_length=20_000)


class AIJobCreateRequest(BaseModel):
    task: str = Field(min_length=2, max_length=60)
    payload: dict = Field(default_factory=dict)
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=100)


class AIJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    task: str
    status: str
    payload_json: dict | list | None
    result_json: dict | list | None
    error_code: str | None
    error_message: str | None
    attempts: int
    created_at: datetime
    finished_at: datetime | None


class AIRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    task: str
    provider: str
    model: str
    prompt_version: str
    status: str
    latency_ms: int | None
    input_tokens: int | None
    output_tokens: int | None
    estimated_cost: float | None
    created_at: datetime


class ReportJobCreateRequest(BaseModel):
    report_kind: str = Field(min_length=2, max_length=60)
    params: dict = Field(default_factory=dict)
    format: str = Field(default="xlsx", max_length=10)
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=100)


class ReportJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    report_kind: str
    status: str
    format: str
    object_key: str | None
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None


# ---------------------------------------------------------------------------
# Chapters & assets
# ---------------------------------------------------------------------------

@router.post("/modules/{module_id}/chapters", response_model=ChapterResponse, status_code=201)
def create_chapter(module_id: uuid.UUID, payload: ChapterCreateRequest, db: Db, user: Manager):
    try:
        chapter = extended_service.create_chapter(db, user, module_id, payload.title, payload.position)
    except Exception as exc:
        _translate(exc)
    return chapter


@router.post("/lessons/{lesson_id}/assets", response_model=LessonAssetResponse, status_code=201)
def create_asset(lesson_id: uuid.UUID, payload: LessonAssetCreateRequest, db: Db, user: Manager):
    try:
        asset = extended_service.create_lesson_asset(
            db, user, lesson_id,
            asset_kind=payload.asset_kind,
            object_key=payload.object_key,
            external_url=payload.external_url,
            filename=payload.filename,
            mime_type=payload.mime_type,
            size_bytes=payload.size_bytes,
            duration_seconds=payload.duration_seconds,
        )
    except Exception as exc:
        _translate(exc)
    return asset


@router.get("/lessons/{lesson_id}/assets", response_model=list[LessonAssetResponse])
def list_assets(lesson_id: uuid.UUID, db: Db, user: CurrentUser):
    try:
        return extended_service.list_lesson_assets(db, user, lesson_id)
    except Exception as exc:
        _translate(exc)


# ---------------------------------------------------------------------------
# Question versioning
# ---------------------------------------------------------------------------

@router.post("/questions/versioned", response_model=QuestionVersionResponse, status_code=201)
def create_question_versioned(payload: QuestionExtCreateRequest, db: Db, user: Manager):
    try:
        return extended_service.create_question_versioned(
            db, user,
            course_id=payload.course_id,
            bank_id=payload.bank_id,
            question_type=payload.question_type,
            prompt=payload.prompt,
            options=payload.options,
            correct_answer=payload.correct_answer,
            points=payload.points,
            learning_objective=payload.learning_objective,
            difficulty=payload.difficulty,
            topic=payload.topic,
            source=payload.source,
            ai_generated=payload.ai_generated,
            explanation=payload.explanation,
        )
    except Exception as exc:
        _translate(exc)


@router.post("/questions/{question_id}/versions", response_model=QuestionVersionResponse, status_code=201)
def update_question(question_id: uuid.UUID, payload: QuestionUpdateRequest, db: Db, user: Manager):
    changes = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not changes:
        raise ApiError("BAD_REQUEST", "No fields to update", 400)
    try:
        return extended_service.update_question_versioned(db, user, question_id, **changes)
    except Exception as exc:
        _translate(exc)


@router.get("/questions/{question_id}/versions", response_model=list[QuestionVersionResponse])
def question_versions(question_id: uuid.UUID, db: Db, user: CurrentUser):
    try:
        return extended_service.list_question_versions(db, user, question_id)
    except Exception as exc:
        _translate(exc)


# ---------------------------------------------------------------------------
# Grades
# ---------------------------------------------------------------------------

@router.post("/grades", response_model=GradeResponse, status_code=201)
def write_grade(payload: GradeWriteRequest, db: Db, user: Manager):
    try:
        grade = extended_service.record_grade(
            db, user,
            student_id=payload.student_id,
            course_id=payload.course_id,
            item_type=payload.item_type,
            item_id=payload.item_id,
            score=payload.score,
            max_score=payload.max_score,
            feedback=payload.feedback,
        )
    except Exception as exc:
        _translate(exc)
    return grade


@router.get("/grades/students/{student_id}", response_model=list[GradeResponse])
def read_student_grades(student_id: uuid.UUID, db: Db, user: CurrentUser):
    try:
        return extended_service.student_grades(db, user, student_id)
    except Exception as exc:
        _translate(exc)


# ---------------------------------------------------------------------------
# Report jobs
# ---------------------------------------------------------------------------

@router.post("/reports/jobs", response_model=ReportJobResponse, status_code=202)
def create_report_job(payload: ReportJobCreateRequest, db: Db, user: CurrentUser):
    try:
        job = extended_service.create_report_job(
            db, user,
            report_kind=payload.report_kind,
            params=payload.params,
            fmt=payload.format,
            idempotency_key=payload.idempotency_key,
        )
    except Exception as exc:
        _translate(exc)
    return job


@router.get("/reports/jobs/{job_id}", response_model=ReportJobResponse)
def read_report_job(job_id: uuid.UUID, db: Db, user: CurrentUser):
    try:
        return extended_service.get_report_job(db, user, job_id)
    except Exception as exc:
        _translate(exc)


# ---------------------------------------------------------------------------
# Mastery analytics
# ---------------------------------------------------------------------------

@router.get("/analytics/students/{student_id}/mastery")
def student_mastery(student_id: uuid.UUID, db: Db, user: CurrentUser):
    try:
        return {"items": extended_service.compute_student_mastery(db, user, student_id)}
    except Exception as exc:
        _translate(exc)
