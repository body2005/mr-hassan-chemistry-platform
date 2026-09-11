from __future__ import annotations

from datetime import datetime, timezone
UTC = timezone.utc
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import CurrentUser
from app.core.database import get_db
from app.models.course import Course, CourseModule, Enrollment, EnrollmentStatus, Lesson
from app.models.progress import LessonProgress, VideoEvent
from app.models.progress import VideoEventType as ModelVideoEventType
from app.models.user import UserRole
from app.schemas import VideoTelemetryBatch, VideoTelemetryResponse

router = APIRouter(prefix="/telemetry")
Db = Annotated[Session, Depends(get_db)]


@router.post(
    "/video-events",
    response_model=VideoTelemetryResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def ingest_video_events(
    payload: VideoTelemetryBatch, user: CurrentUser, db: Db
) -> VideoTelemetryResponse:
    if user.role != UserRole.STUDENT:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Student telemetry only")

    accepted = 0
    duplicates = 0
    seen_client_ids: set[str] = set()
    for event in payload.events:
        if event.client_event_id in seen_client_ids:
            duplicates += 1
            continue
        seen_client_ids.add(event.client_event_id)

        lesson_access = db.scalar(
            select(Lesson.id)
            .join(CourseModule, Lesson.module_id == CourseModule.id)
            .join(Course, CourseModule.course_id == Course.id)
            .join(Enrollment, Enrollment.course_id == Course.id)
            .where(
                Lesson.id == event.lesson_id,
                Course.institution_id == user.institution_id,
                Enrollment.student_id == user.id,
                Enrollment.status.in_([EnrollmentStatus.ACTIVE, EnrollmentStatus.COMPLETED]),
            )
        )
        if lesson_access is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")

        already_recorded = db.scalar(
            select(VideoEvent.id).where(
                VideoEvent.student_id == user.id,
                VideoEvent.client_event_id == event.client_event_id,
            )
        )
        if already_recorded:
            duplicates += 1
            continue

        occurred_at = event.occurred_at or datetime.now(UTC)
        video_event = VideoEvent(
            institution_id=user.institution_id,
            student_id=user.id,
            lesson_id=event.lesson_id,
            client_event_id=event.client_event_id,
            event_type=ModelVideoEventType(event.event_type.value),
            position_seconds=event.position_seconds,
            watched_delta_seconds=event.watched_delta_seconds,
            duration_seconds=event.duration_seconds,
            occurred_at=occurred_at,
        )
        db.add(video_event)
        progress = db.scalar(
            select(LessonProgress).where(
                LessonProgress.student_id == user.id,
                LessonProgress.lesson_id == event.lesson_id,
            )
        )
        if progress is None:
            progress = LessonProgress(
                institution_id=user.institution_id,
                student_id=user.id,
                lesson_id=event.lesson_id,
            )
            db.add(progress)

        progress.last_position_seconds = event.position_seconds
        progress.watched_duration_seconds = (
            progress.watched_duration_seconds or 0
        ) + event.watched_delta_seconds
        if event.duration_seconds:
            progress.completion_percent = min(
                100.0,
                max(
                    progress.completion_percent or 0,
                    (event.position_seconds / event.duration_seconds) * 100,
                ),
            )
        if event.event_type.value == "ended":
            progress.completion_percent = 100.0
        progress.last_event_at = occurred_at
        if progress.completion_percent >= 100:
            progress.completed_at = occurred_at
        accepted += 1

    db.commit()
    return VideoTelemetryResponse(accepted=accepted, duplicates=duplicates)
