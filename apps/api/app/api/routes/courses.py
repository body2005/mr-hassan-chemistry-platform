from __future__ import annotations

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import CurrentUser, OptionalUser, require_roles
from app.core.database import get_db
from app.models.user import User, UserRole
from app.schemas import (
    CourseCreateRequest,
    CourseResponse,
    EnrollmentResponse,
    PageInfo,
    PageResponse,
)
from app.services import course_service

router = APIRouter(prefix="/courses")
Db = Annotated[Session, Depends(get_db)]
CourseManager = Annotated[
    User,
    Depends(require_roles(UserRole.TEACHER, UserRole.INSTITUTION_ADMIN, UserRole.PLATFORM_ADMIN)),
]
Student = Annotated[User, Depends(require_roles(UserRole.STUDENT))]


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
        items=[CourseResponse.model_validate(course) for course in courses],
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
    return CourseResponse.model_validate(course)


@router.get("/{course_id}", response_model=CourseResponse)
def get_course(course_id: uuid.UUID, user: OptionalUser, db: Db) -> CourseResponse:
    course = course_service.get_course(db, user, course_id)
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    return CourseResponse.model_validate(course)


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
    return EnrollmentResponse.model_validate(enrollment)


@router.get("/me/enrollments", response_model=list[EnrollmentResponse])
def my_enrollments(user: Student, db: Db) -> list[EnrollmentResponse]:
    return [
        EnrollmentResponse.model_validate(item)
        for item in course_service.list_my_enrollments(db, user)
    ]
