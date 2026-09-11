from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone
UTC = timezone.utc

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models.course import Course, CourseModule, CourseStatus, Enrollment, EnrollmentStatus
from app.models.user import User, UserRole
from app.schemas import CourseCreateRequest


def _course_query_for_user(db: Session, user: User | None):
    query = select(Course)
    if user is None:
        return query.where(Course.status == CourseStatus.PUBLISHED)
    if user.role != UserRole.PLATFORM_ADMIN:
        query = query.where(Course.institution_id == user.institution_id)
    if user.role == UserRole.STUDENT:
        query = query.where(Course.status == CourseStatus.PUBLISHED)
    return query


def list_courses(
    db: Session,
    user: User | None,
    page: int,
    page_size: int,
    search: str | None,
    sort: str,
) -> tuple[list[Course], int]:
    query = _course_query_for_user(db, user)
    count_query = select(func.count()).select_from(query.subquery())
    if search:
        term = f"%{search.strip()}%"
        query = query.where(or_(Course.title.ilike(term), Course.code.ilike(term)))
        count_query = select(func.count()).select_from(query.subquery())

    total = db.scalar(count_query) or 0
    ordering = Course.title.asc() if sort == "title" else Course.created_at.desc()
    query = (
        query.options(selectinload(Course.modules).selectinload(CourseModule.lessons))
        .order_by(ordering)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(db.scalars(query).unique().all()), total


def get_course(db: Session, user: User | None, course_id: uuid.UUID) -> Course | None:
    query = _course_query_for_user(db, user).where(Course.id == course_id)
    return (
        db.scalars(query.options(selectinload(Course.modules).selectinload(CourseModule.lessons)))
        .unique()
        .first()
    )


def create_course(db: Session, user: User, payload: CourseCreateRequest) -> Course:
    if user.role == UserRole.TEACHER:
        teacher_id = user.id
    else:
        teacher_id = payload.teacher_id or user.id
        teacher = db.scalar(
            select(User).where(
                User.id == teacher_id,
                User.institution_id == user.institution_id,
                User.role == UserRole.TEACHER,
                User.is_active.is_(True),
            )
        )
        if teacher is None:
            raise ValueError("A course must be assigned to an active teacher in this institution")

    course = Course(
        institution_id=user.institution_id,
        teacher_id=teacher_id,
        code=payload.code.strip().upper(),
        title=payload.title.strip(),
        description=payload.description.strip() if payload.description else None,
        status=CourseStatus.DRAFT,
    )
    db.add(course)
    db.commit()
    db.refresh(course)
    return course


def publish_course(db: Session, user: User, course_id: uuid.UUID) -> Course:
    query = select(Course).where(Course.id == course_id)
    if user.role != UserRole.PLATFORM_ADMIN:
        query = query.where(Course.institution_id == user.institution_id)
    course = db.scalar(query)
    if course is None:
        raise LookupError("Course not found")
    if user.role == UserRole.TEACHER and course.teacher_id != user.id:
        raise PermissionError("You do not own this course")
    course.status = CourseStatus.PUBLISHED
    course.published_at = datetime.now(UTC)
    db.commit()
    db.refresh(course)
    return course


def enroll(db: Session, user: User, course_id: uuid.UUID) -> Enrollment:
    course = db.scalar(
        select(Course).where(
            Course.id == course_id,
            Course.institution_id == user.institution_id,
            Course.status == CourseStatus.PUBLISHED,
        )
    )
    if course is None:
        raise LookupError("Published course not found")

    existing = db.scalar(
        select(Enrollment).where(
            Enrollment.course_id == course_id,
            Enrollment.student_id == user.id,
        )
    )
    if existing:
        return existing

    enrollment = Enrollment(course_id=course_id, student_id=user.id, status=EnrollmentStatus.ACTIVE)
    db.add(enrollment)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(
            select(Enrollment).where(
                Enrollment.course_id == course_id,
                Enrollment.student_id == user.id,
            )
        )
        if existing is None:
            raise
        return existing
    db.refresh(enrollment)
    return enrollment


def list_my_enrollments(db: Session, user: User) -> list[Enrollment]:
    return list(
        db.scalars(
            select(Enrollment)
            .where(Enrollment.student_id == user.id)
            .order_by(Enrollment.enrolled_at.desc())
        ).all()
    )


def page_count(total: int, page_size: int) -> int:
    return math.ceil(total / page_size) if total else 0
