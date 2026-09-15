from __future__ import annotations

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import CurrentUser, OptionalUser, require_roles
from app.core.database import get_db
from app.models.user import User, UserRole
from app.models.course import Enrollment, EnrollmentStatus
from app.models.payment import EntitlementType, StudentEntitlement
from app.schemas import (
    CourseCreateRequest,
    CourseResponse,
    EnrollmentResponse,
    PageInfo,
    PageResponse,
)
from app.services import course_service
from app.services.payment_service import is_entitlement_active

router = APIRouter(prefix="/courses")
Db = Annotated[Session, Depends(get_db)]
CourseManager = Annotated[
    User,
    Depends(require_roles(UserRole.TEACHER, UserRole.INSTITUTION_ADMIN, UserRole.PLATFORM_ADMIN)),
]
Student = Annotated[User, Depends(require_roles(UserRole.STUDENT))]


def _safe_course_responses(db: Session, user: User | None, courses: list) -> list[CourseResponse]:
    responses = [CourseResponse.model_validate(course) for course in courses]
    
    # Collect all lesson IDs across returned courses
    all_lesson_ids = [lesson.id for course in responses for module in course.modules for lesson in module.lessons]
    materials_by_lesson: dict[uuid.UUID, list[LessonMaterialSummary]] = {}
    if all_lesson_ids:
        from app.models.knowledge_center import KnowledgeSource, SourceStatus, SourceRole
        from app.schemas import LessonMaterialSummary
        sources = db.scalars(
            select(KnowledgeSource).where(
                KnowledgeSource.lesson_id.in_(all_lesson_ids),
                KnowledgeSource.status != SourceStatus.DELETING,
                KnowledgeSource.source_role == SourceRole.LESSON_MATERIAL,
                KnowledgeSource.is_current == True,
            )
        ).all()
        for s in sources:
            if not s.lesson_id:
                continue
            materials_by_lesson.setdefault(s.lesson_id, []).append(
                LessonMaterialSummary(
                    id=s.id,
                    filename=s.filename,
                    file_format=s.file_format,
                    size_bytes=s.size_bytes,
                    source_role=s.source_role,
                    download_url=f"/api/v1/knowledge-center/sources/{s.id}/download",
                    created_at=s.created_at,
                )
            )

    if user and user.role != UserRole.STUDENT:
        for course in responses:
            for module in course.modules:
                for lesson in module.lessons:
                    lesson.materials = materials_by_lesson.get(lesson.id, [])
        return responses

    enrolled_course_ids: set[uuid.UUID] = set()
    course_entitlements: set[uuid.UUID] = set()
    lesson_entitlements: set[uuid.UUID] = set()
    if user:
        enrolled_course_ids = set(
            db.scalars(
                select(Enrollment.course_id).where(
                    Enrollment.student_id == user.id,
                    Enrollment.status.in_([EnrollmentStatus.ACTIVE, EnrollmentStatus.COMPLETED]),
                )
            ).all()
        )
        entitlements = db.scalars(
            select(StudentEntitlement).where(
                StudentEntitlement.student_id == user.id,
                StudentEntitlement.institution_id == user.institution_id,
                StudentEntitlement.revoked_at.is_(None),
            )
        ).all()
        for entitlement in entitlements:
            if not entitlement.resource_id or not is_entitlement_active(entitlement):
                continue
            if entitlement.entitlement_type == EntitlementType.COURSE:
                course_entitlements.add(entitlement.resource_id)
            elif entitlement.entitlement_type == EntitlementType.LESSON:
                lesson_entitlements.add(entitlement.resource_id)

    for course in responses:
        is_enrolled = course.id in enrolled_course_ids
        course_is_free = float(course.price_egp or 0) == 0
        has_course_entitlement = course.id in course_entitlements
        for module in course.modules:
            for lesson in module.lessons:
                has_lesson_access = is_enrolled and (
                    has_course_entitlement
                    or lesson.id in lesson_entitlements
                    or (course_is_free and float(lesson.price_egp or 0) == 0)
                )
                if has_lesson_access:
                    lesson.materials = materials_by_lesson.get(lesson.id, [])
                else:
                    lesson.content = None
                    lesson.video_asset_key = None
                    lesson.materials = []
    return responses


@router.get("", response_model=PageResponse[CourseResponse])
def list_courses(
    user: OptionalUser,
    db: Db,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None, max_length=100),
    sort: Literal["created_at", "title"] = "created_at",
) -> PageResponse[CourseResponse]:
    courses, total = course_service.list_courses(db, user, page, page_size, search, sort)
    return PageResponse(
        items=_safe_course_responses(db, user, courses),
        pagination=PageInfo(
            page=page,
            page_size=page_size,
            total=total,
            pages=course_service.page_count(total, page_size),
        ),
    )


@router.post("", response_model=CourseResponse, status_code=status.HTTP_201_CREATED)
def create_course(payload: CourseCreateRequest, user: CourseManager, db: Db) -> CourseResponse:
    try:
        course = course_service.create_course(db, user, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _safe_course_responses(db, user, [course])[0]


@router.get("/{course_id}", response_model=CourseResponse)
def get_course(course_id: uuid.UUID, user: OptionalUser, db: Db) -> CourseResponse:
    course = course_service.get_course(db, user, course_id)
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    return _safe_course_responses(db, user, [course])[0]


@router.post("/{course_id}/publish", response_model=CourseResponse)
def publish_course(course_id: uuid.UUID, user: CourseManager, db: Db) -> CourseResponse:
    try:
        course = course_service.publish_course(db, user, course_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return CourseResponse.model_validate(course)


@router.post("/{course_id}/enroll", response_model=EnrollmentResponse)
def enroll(course_id: uuid.UUID, user: Student, db: Db) -> EnrollmentResponse:
    try:
        enrollment = course_service.enroll(db, user, course_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=str(exc)) from exc
    return EnrollmentResponse.model_validate(enrollment)


@router.get("/me/enrollments", response_model=list[EnrollmentResponse])
def my_enrollments(user: Student, db: Db) -> list[EnrollmentResponse]:
    return [
        EnrollmentResponse.model_validate(item)
        for item in course_service.list_my_enrollments(db, user)
    ]
