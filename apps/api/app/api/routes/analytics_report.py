from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import CurrentUser, require_roles
from app.core.database import get_db
from app.core.rate_limit import enforce_rate_limit
from app.models.course import Course, CourseModule, Lesson, Enrollment, EnrollmentStatus
from app.models.platform import Assignment, AssignmentSubmission, Quiz, QuizAttempt, QuizAttemptAnswer
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
        .join(CourseModule, Lesson.module_id == CourseModule.id)
        .join(Course, CourseModule.course_id == Course.id)
        .where(Course.id.in_(courses))
    ).scalar_one() or 0
    quizzes_count = db.scalar(select(func.count(Quiz.id)).where(Quiz.institution_id == user.institution_id, Quiz.course_id.in_(courses))) or 0
    assignments_count = db.scalar(select(func.count(Assignment.id)).where(Assignment.institution_id == user.institution_id, Assignment.course_id.in_(courses))) or 0

    # Practice (self-training) attempts are the student's private business:
    # teacher analytics only ever see official attempts.
    attempts = db.execute(
        select(QuizAttempt).join(Quiz, Quiz.id == QuizAttempt.quiz_id).where(
            QuizAttempt.institution_id == user.institution_id,
            Quiz.course_id.in_(courses), QuizAttempt.student_id.in_(students),
            QuizAttempt.is_practice.is_(False),
            ~select(QuizAttemptAnswer.id).where(QuizAttemptAnswer.attempt_id == QuizAttempt.id,
                                               QuizAttemptAnswer.graded_at.is_(None)).exists(),
        )
    ).scalars().all()
    if attempts:
        quiz_avg_score = round(sum(a.score or 0 for a in attempts) / len(attempts), 2)
        quiz_completion_rate = round(len(attempts) / max(students_count, 1), 2)
    else:
        quiz_avg_score = None
        quiz_completion_rate = None

    submissions = db.scalars(select(AssignmentSubmission).join(Assignment, Assignment.id == AssignmentSubmission.assignment_id)
        .where(AssignmentSubmission.institution_id == user.institution_id,
               Assignment.course_id.in_(courses), AssignmentSubmission.student_id.in_(students))).all()
    if submissions:
        assignment_submission_rate = round(len(submissions) / max(students_count, 1), 2)
    else:
        assignment_submission_rate = None

    progresses = db.execute(select(LessonProgress).join(Lesson, LessonProgress.lesson_id == Lesson.id).join(CourseModule, Lesson.module_id == CourseModule.id).join(Course, CourseModule.course_id == Course.id).where(Course.id.in_(courses), LessonProgress.student_id.in_(students), LessonProgress.institution_id == user.institution_id)).scalars().all()
    if progresses:
        completed_count = sum(1 for p in progresses if p.completed_at is not None or (p.completion_percent or 0) >= 90.0)
        lesson_completion_rate = round((completed_count / max(len(progresses), 1)) * 100, 2)
    else:
        lesson_completion_rate = None

    mastery_distribution = {"ممتاز": 0, "جيد جداً": 0, "جيد": 0, "مقبول": 0, "ضعيف": 0}
    for a in attempts:
        score = a.score or 0
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
    if attempts:
        top = sorted(attempts, key=lambda a: a.score or 0, reverse=True)[:5]
        top_quizzes = [{"quiz_id": str(a.quiz_id), "score": a.score, "submitted_at": a.submitted_at.isoformat() if a.submitted_at else None} for a in top]

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
    )
