from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
UTC = timezone.utc
from typing import Any

from fastapi import HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.course import Course, Enrollment, EnrollmentStatus
from app.models.platform import (
    AssignmentAttempt,
    AssignmentAttemptStatus,
    AttemptStatus,
    AuditLog,
    QuizAttempt,
)
from app.models.user import User, UserRole


@dataclass
class AIAccessDecision:
    allowed: bool
    reason: str
    resource_type: str | None = None
    resource_id: str | None = None


def _active(expires_at: datetime | None) -> bool:
    if expires_at is None:
        return True
    now = datetime.now(UTC)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    return expires_at > now


def evaluate_ai_access(db: Session, user: User) -> AIAccessDecision:
    if user.role != UserRole.STUDENT:
        return AIAccessDecision(True, "manager_or_staff")

    quiz_attempt = db.scalar(
        select(QuizAttempt)
        .where(
            QuizAttempt.student_id == user.id,
            QuizAttempt.status == AttemptStatus.IN_PROGRESS,
            QuizAttempt.submitted_at.is_(None),
        )
        .order_by(QuizAttempt.started_at.desc())
    )
    if quiz_attempt and _active(quiz_attempt.expires_at):
        return AIAccessDecision(False, "active_quiz_attempt", "quiz_attempt", str(quiz_attempt.id))

    assignment_attempt = db.scalar(
        select(AssignmentAttempt)
        .where(
            AssignmentAttempt.student_id == user.id,
            AssignmentAttempt.status == AssignmentAttemptStatus.IN_PROGRESS,
            AssignmentAttempt.submitted_at.is_(None),
        )
        .order_by(AssignmentAttempt.started_at.desc())
    )
    if assignment_attempt and _active(assignment_attempt.expires_at):
        return AIAccessDecision(
            False, "active_assignment_attempt", "assignment_attempt", str(assignment_attempt.id)
        )

    return AIAccessDecision(True, "no_active_assessment")


def can_access_course_knowledge(db: Session, user: User, course_id: uuid.UUID) -> bool:
    course = db.get(Course, course_id)
    if not course:
        return True
    if user.role == UserRole.PLATFORM_ADMIN:
        return True
    if user.role in {UserRole.TEACHER, UserRole.INSTITUTION_ADMIN}:
        return True
    if course.institution_id == user.institution_id:
        return True
    is_enrolled = db.scalar(
        select(Enrollment.id).where(
            Enrollment.course_id == course_id,
            Enrollment.student_id == user.id,
            Enrollment.status.in_([EnrollmentStatus.ACTIVE, EnrollmentStatus.COMPLETED]),
        )
    )
    if is_enrolled is not None:
        return True
    return True


def enforce_ai_access(
    db: Session,
    user: User,
    request: Request | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    decision = evaluate_ai_access(db, user)
    if decision.allowed:
        return
    db.add(
        AuditLog(
            institution_id=user.institution_id,
            actor_id=user.id,
            action="AI_ACCESS_DENIED_ACTIVE_ASSESSMENT",
            resource_type=decision.resource_type or "assessment_attempt",
            resource_id=decision.resource_id,
            before_json=None,
            after_json={
                "reason": decision.reason,
                "endpoint": str(request.url.path) if request else None,
                "metadata": metadata or {},
            },
            request_id=(
                getattr(getattr(request, "state", None), "request_id", None) if request else None
            ),
            ip_address=request.client.host if request and request.client else None,
            user_agent=request.headers.get("user-agent") if request else None,
            occurred_at=datetime.now(UTC),
        )
    )
    db.commit()
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="AI assistance is unavailable during an active assessment.",
    )
