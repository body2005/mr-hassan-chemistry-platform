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


def _video_playback_fields(lesson) -> tuple[bool, str | None]:
    """Playback info without ever serializing the private storage key.

    Teacher-entered external URLs stay as-is (they are public by nature);
    every locally-stored video is only reachable through the token-gated
    stream endpoint, so the client just gets that entry point.
    """
    key = lesson.video_asset_key
    if not key:
        return False, None
    if key.startswith("http://") or key.startswith("https://"):
        return True, key
    return True, f"/api/v1/lessons/{lesson.id}/video-token"


def _safe_course_responses(db: Session, user: User | None, courses: list) -> list[CourseResponse]:
    responses = [CourseResponse.model_validate(course) for course in courses]
    # Pair each serialized lesson with its ORM source so playback fields can be
    # derived from the private key without ever serializing the key itself.
    orm_lessons_by_id = {
        lesson.id: lesson
        for course in courses
        for module in getattr(course, "modules", [])
        for lesson in getattr(module, "lessons", [])
    }
    
    # Collect all lesson IDs across returned courses
    all_lesson_ids = [lesson.id for course in responses for module in course.modules for lesson in module.lessons]
    materials_by_lesson: dict[uuid.UUID, list[LessonMaterialSummary]] = {}
    if all_lesson_ids:
        from app.models.extended import LessonAsset
        from app.schemas import LessonMaterialSummary

        assets = db.scalars(
            select(LessonAsset).where(
                LessonAsset.lesson_id.in_(all_lesson_ids),
                LessonAsset.asset_kind.in_(["pdf", "document", "attachment"]),
            )
        ).all()
        for a in assets:
            ext = (a.filename or "").rsplit(".", 1)[-1].lower() if a.filename else "bin"
            materials_by_lesson.setdefault(a.lesson_id, []).append(
                LessonMaterialSummary(
                    id=a.id,
                    filename=a.filename or "material",
                    file_format=ext,
                    size_bytes=a.size_bytes or 0,
                    source_role="LESSON_MATERIAL",
                    download_url=f"/api/v1/lessons/{a.lesson_id}/materials/{a.id}/download",
                    created_at=a.created_at,
                )
            )

    if user and user.role != UserRole.STUDENT:
        for course in responses:
            for module in course.modules:
                for lesson in module.lessons:
                    lesson.materials = materials_by_lesson.get(lesson.id, [])
                    orm_lesson = orm_lessons_by_id.get(lesson.id)
                    if orm_lesson is not None:
                        lesson.has_video, lesson.video_url = _video_playback_fields(orm_lesson)
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
                    orm_lesson = orm_lessons_by_id.get(lesson.id)
                    if orm_lesson is not None:
                        lesson.has_video, lesson.video_url = _video_playback_fields(orm_lesson)
                else:
                    lesson.content = None
                    lesson.has_video = False
                    lesson.video_url = None
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
