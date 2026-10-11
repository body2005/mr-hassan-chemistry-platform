from __future__ import annotations

from datetime import datetime, timezone
import math
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import CurrentUser, require_roles
from app.core.database import get_db
from app.core.rate_limit import enforce_rate_limit
from app.models.course import Course, CourseModule, Lesson, Enrollment, EnrollmentStatus
from app.models.platform import (Assignment, AssignmentStatus, AssignmentSubmission, Quiz,
    QuizStatus, QuizAttempt, QuizAttemptAnswer, AttemptStatus)
from app.models.progress import LessonProgress
from app.models.user import User, UserRole

router = APIRouter()
Db = Annotated[Session, Depends(get_db)]


class AnalyticsSummary(BaseModel):
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    course_id: str | None = None
    students_count: int
    lessons_count: int
    quizzes_count: int
    assignments_count: int
    quiz_avg_score: float | None = None
    quiz_completion_rate: float | None = None
    assignment_submission_rate: float | None = None
    lesson_completion_rate: float | None = None
    mastery_distribution: dict[str, int] | None = None
    risk_students_count: int = 0
    top_quizzes: list[dict[str, Any]] = []
    assignments_on_time_rate: float | None = None
    metric_policy: str = "percent/latest-submitted-official/enrollment-pairs/v1"
    quiz_eligible_count: int = 0
    quiz_completed_count: int = 0
    quiz_scored_count: int = 0
    invalid_score_count: int = 0
    assignment_eligible_count: int = 0
    lesson_eligible_count: int = 0


@router.get("/reports/summary", response_model=AnalyticsSummary)
async def get_analytics_summary(
    user: CurrentUser,
    request: Request,
    db: Db,
) -> AnalyticsSummary:
    enforce_rate_limit(request, bucket="default", limit=10, window_seconds=60)
    if user.role == UserRole.STUDENT:
        raise HTTPException(403, "Institution reports are restricted to managers")
    # Platform admins remain scoped to their current institution; this does
    # not introduce a cross-tenant reporting policy.
    courses = select(Course.id).where(Course.institution_id == user.institution_id)
    if user.role == UserRole.TEACHER:
        courses = courses.where(Course.teacher_id == user.id)
    students = select(User.id).where(User.institution_id == user.institution_id,
        User.role == UserRole.STUDENT, User.deleted_at.is_(None))
    if user.role == UserRole.TEACHER:
        students = students.where(User.id.in_(select(Enrollment.student_id).where(
            Enrollment.course_id.in_(courses), Enrollment.status.in_(
                [EnrollmentStatus.ACTIVE, EnrollmentStatus.COMPLETED]))))
    students_count = db.scalar(select(func.count()).select_from(students.subquery())) or 0

    lessons_count = db.execute(
        select(func.count(Lesson.id))
        .select_from(Lesson)
        .join(Course, Lesson.course_id == Course.id)
        .where(Course.id.in_(courses))
    ).scalar_one() or 0
    quizzes_count = db.scalar(select(func.count(Quiz.id)).where(Quiz.institution_id == user.institution_id, Quiz.course_id.in_(courses))) or 0
    assignments_count = db.scalar(select(func.count(Assignment.id)).where(Assignment.institution_id == user.institution_id, Assignment.course_id.in_(courses))) or 0

    # Denominators are eligible student/content pairs, not all students times
    # all content, and not the count of retries or existing progress rows.
    enrollment_filter = (Enrollment.status.in_([EnrollmentStatus.ACTIVE, EnrollmentStatus.COMPLETED]),
                         Enrollment.student_id.in_(students), Enrollment.course_id.in_(courses))
    quiz_filter = (Quiz.institution_id == user.institution_id,
                   Quiz.status.in_([QuizStatus.PUBLISHED, QuizStatus.CLOSED]))
    assignment_filter = (Assignment.institution_id == user.institution_id,
                         Assignment.status.in_([AssignmentStatus.PUBLISHED, AssignmentStatus.CLOSED]))
    quiz_eligible_count = db.scalar(select(func.count()).select_from(Enrollment).join(
        Quiz, Quiz.course_id == Enrollment.course_id).where(*enrollment_filter, *quiz_filter)) or 0
    assignment_eligible_count = db.scalar(select(func.count()).select_from(Enrollment).join(
        Assignment, Assignment.course_id == Enrollment.course_id).where(*enrollment_filter, *assignment_filter)) or 0
    lesson_eligible_count = db.scalar(select(func.count()).select_from(Enrollment).join(
        Lesson, Lesson.course_id == Enrollment.course_id).where(*enrollment_filter)) or 0
    pending = select(QuizAttemptAnswer.id).where(QuizAttemptAnswer.attempt_id == QuizAttempt.id,
        QuizAttemptAnswer.graded_at.is_(None)).exists()
    rows = db.execute(
        select(QuizAttempt, pending.label("pending")).join(Quiz, Quiz.id == QuizAttempt.quiz_id).join(
            Enrollment, (Enrollment.course_id == Quiz.course_id) &
                        (Enrollment.student_id == QuizAttempt.student_id)).where(
            QuizAttempt.institution_id == user.institution_id,
            *enrollment_filter, *quiz_filter,
            QuizAttempt.is_practice.is_(False),
            QuizAttempt.status == AttemptStatus.SUBMITTED,
            QuizAttempt.submitted_at.is_not(None),
        ).order_by(QuizAttempt.attempt_number.desc(), QuizAttempt.submitted_at.desc(), QuizAttempt.id)
    ).all()
    latest = {}
    for attempt, is_pending in rows:
        latest.setdefault((attempt.student_id, attempt.quiz_id), (attempt, is_pending))
    attempts = [attempt for attempt, is_pending in latest.values() if not is_pending]
    scored = []
    invalid_score_count = 0
    for attempt in attempts:
        score, total = attempt.score, attempt.total_points
        if (score is None or total is None or not math.isfinite(score) or not math.isfinite(total)
                or total <= 0 or not 0 <= score <= total):
            invalid_score_count += 1
            continue
        scored.append((attempt, score / total * 100))
    quiz_avg_score = round(sum(percent for _, percent in scored) / len(scored), 2) if scored else None
    quiz_completion_rate = round(len(attempts) / quiz_eligible_count * 100, 2) if quiz_eligible_count else None

    submissions = db.scalars(select(AssignmentSubmission).join(Assignment, Assignment.id == AssignmentSubmission.assignment_id)
        .join(Enrollment, (Enrollment.course_id == Assignment.course_id) &
                         (Enrollment.student_id == AssignmentSubmission.student_id))
        .where(AssignmentSubmission.institution_id == user.institution_id,
               *enrollment_filter, *assignment_filter,
               AssignmentSubmission.submitted_at.is_not(None))).all()
    submitted_pairs = {(row.student_id, row.assignment_id) for row in submissions}
    assignment_submission_rate = (round(len(submitted_pairs) / assignment_eligible_count * 100, 2)
                                  if assignment_eligible_count else None)

    progresses = db.execute(select(LessonProgress).join(Lesson, LessonProgress.lesson_id == Lesson.id)
        .join(Enrollment,
            (Enrollment.course_id == Lesson.course_id) &
            (Enrollment.student_id == LessonProgress.student_id))
        .where(*enrollment_filter, LessonProgress.institution_id == user.institution_id)).scalars().all()
    completed_pairs = {(row.student_id, row.lesson_id) for row in progresses
                       if row.completed_at is not None or (row.completion_percent or 0) >= 90}
    lesson_completion_rate = (round(len(completed_pairs) / lesson_eligible_count * 100, 2)
                              if lesson_eligible_count else None)

    mastery_distribution = {"ممتاز": 0, "جيد جداً": 0, "جيد": 0, "مقبول": 0, "ضعيف": 0}
    for _, score in scored:
        if score >= 90:
            mastery_distribution["ممتاز"] += 1
        elif score >= 80:
            mastery_distribution["جيد جداً"] += 1
        elif score >= 70:
            mastery_distribution["جيد"] += 1
        elif score >= 60:
            mastery_distribution["مقبول"] += 1
        else:
            mastery_distribution["ضعيف"] += 1

    top_quizzes = []
    if scored:
        top = sorted(scored, key=lambda item: (-item[1], str(item[0].id)))[:5]
        top_quizzes = [{"quiz_id": str(a.quiz_id), "score": round(percent, 2),
            "raw_score": a.score, "total_points": a.total_points, "submitted_at": a.submitted_at.isoformat()}
            for a, percent in top]

    return AnalyticsSummary(
        course_id=None,
        students_count=students_count,
        lessons_count=lessons_count,
        quizzes_count=quizzes_count,
        assignments_count=assignments_count,
        quiz_avg_score=quiz_avg_score,
        quiz_completion_rate=quiz_completion_rate,
        assignment_submission_rate=assignment_submission_rate,
        lesson_completion_rate=lesson_completion_rate,
        mastery_distribution=mastery_distribution,
        risk_students_count=0,
        top_quizzes=top_quizzes,
        assignments_on_time_rate=None,
        quiz_eligible_count=quiz_eligible_count,
        quiz_completed_count=len(attempts),
        quiz_scored_count=len(scored),
        invalid_score_count=invalid_score_count,
        assignment_eligible_count=assignment_eligible_count,
        lesson_eligible_count=lesson_eligible_count,
    )
