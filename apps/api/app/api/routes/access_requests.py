from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import CurrentUser, require_roles
from app.core.database import get_db
from app.core.events import event_broker
from app.models.course import Course, CourseModule, CourseStatus, Enrollment, EnrollmentStatus, Lesson
from app.models.payment import (
    EntitlementType,
    PaymentMethod,
    PaymentOrder,
    PaymentProductType,
    PaymentStatus,
    StudentEntitlement,
)
from app.models.platform import Notification
from app.models.user import User, UserRole
from app.schemas import (
    LessonAccessRequestCreate,
    LessonAccessRequestResponse,
    LessonAccessReviewRequest,
    NotificationResponse,
)
from app.services import payment_service

logger = logging.getLogger(__name__)
UTC = timezone.utc

router = APIRouter(prefix="/lessons", tags=["lesson_access"])

Db = Annotated[Session, Depends(get_db)]
Student = Annotated[User, Depends(require_roles(UserRole.STUDENT))]
Reviewer = Annotated[
    User,
    Depends(require_roles(UserRole.TEACHER, UserRole.INSTITUTION_ADMIN, UserRole.PLATFORM_ADMIN)),
]


def _lesson_and_course(db: Session, lesson_id: uuid.UUID) -> tuple[Lesson, Course]:
    row = db.execute(
        select(Lesson, Course)
        .join(CourseModule, Lesson.module_id == CourseModule.id)
        .join(Course, CourseModule.course_id == Course.id)
        .where(Lesson.id == lesson_id)
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Lesson not found")
    return row[0], row[1]


def _build_response(order: PaymentOrder, lesson: Lesson, course: Course, student: User) -> LessonAccessRequestResponse:
    display_status = (
        "approved"
        if order.status == PaymentStatus.PAID
        else "rejected"
        if order.status in {PaymentStatus.REJECTED, PaymentStatus.CANCELLED}
        else "pending"
    )
    return LessonAccessRequestResponse(
        id=order.id,
        student_id=student.id,
        student_name=student.display_name,
        student_phone=student.student_phone,
        lesson_id=lesson.id,
        lesson_title=lesson.title,
        course_id=course.id,
        course_title=course.title,
        status=display_status,
        student_note=order.student_note,
        reviewer_note=order.review_note,
        created_at=order.created_at,
        reviewed_at=order.reviewed_at,
    )


@router.post("/{lesson_id}/access-requests", response_model=LessonAccessRequestResponse, status_code=status.HTTP_201_CREATED)
def request_lesson_access(
    lesson_id: uuid.UUID,
    payload: LessonAccessRequestCreate,
    user: Student,
    db: Db,
) -> LessonAccessRequestResponse:
    lesson, course = _lesson_and_course(db, lesson_id)
    if course.institution_id != user.institution_id:
        raise HTTPException(status_code=404, detail="Lesson not found")

    # If already entitled, return existing access state
    if payment_service.has_lesson_entitlement(db, user, lesson.id) or payment_service.has_course_entitlement(db, user, course.id):
        existing_order = db.scalar(
            select(PaymentOrder)
            .where(
                PaymentOrder.student_id == user.id,
                PaymentOrder.product_type == PaymentProductType.LESSON,
                PaymentOrder.product_id == lesson.id,
            )
            .order_by(PaymentOrder.created_at.desc())
        )
        if existing_order:
            return _build_response(existing_order, lesson, course, user)

    # Check for an existing pending request
    pending = db.scalar(
        select(PaymentOrder)
        .where(
            PaymentOrder.student_id == user.id,
            PaymentOrder.product_type == PaymentProductType.LESSON,
            PaymentOrder.product_id == lesson.id,
            PaymentOrder.status.in_([PaymentStatus.PENDING, PaymentStatus.UNDER_REVIEW]),
        )
        .order_by(PaymentOrder.created_at.desc())
    )
    if pending:
        return _build_response(pending, lesson, course, user)

    # Create new access request order
    order = PaymentOrder(
        institution_id=user.institution_id,
        student_id=user.id,
        product_type=PaymentProductType.LESSON,
        product_id=lesson.id,
        product_name=lesson.title,
        amount_egp=float(lesson.price_egp or 0),
        payment_method=PaymentMethod.INSTAPAY,
        payer_reference=None,
        student_note=(payload.student_note or "").strip()[:4000] or None,
        status=PaymentStatus.PENDING,
    )
    db.add(order)
    db.flush()

    # Identify teacher(s) to notify
    teacher_ids: list[uuid.UUID] = []
    if course.teacher_id:
        teacher_ids.append(course.teacher_id)
    admin_users = db.scalars(
        select(User).where(
            User.institution_id == user.institution_id,
            User.role.in_([UserRole.TEACHER, UserRole.INSTITUTION_ADMIN]),
        )
    ).all()
    for a in admin_users:
        if a.id not in teacher_ids and (a.role == UserRole.INSTITUTION_ADMIN or a.id == course.teacher_id):
            teacher_ids.append(a.id)

    # Create persistent in-app notifications
    action_url = f"/lessons/access-requests/{order.id}"
    notifications_created: list[Notification] = []
    for tid in teacher_ids:
        notif = Notification(
            institution_id=user.institution_id,
            recipient_id=tid,
            kind="lesson_access",
            title=f"طلب إتاحة درس: {lesson.title}",
            message=f"طلب الطالب {user.display_name} إتاحة درس '{lesson.title}' في كورس '{course.title}'. اضغط للاطلاع والاعتماد.",
            action_url=action_url,
        )
        db.add(notif)
        notifications_created.append(notif)

    db.commit()
    db.refresh(order)
    for n in notifications_created:
        db.refresh(n)

    # Publish real-time events to teachers
    resp = _build_response(order, lesson, course, user)
    event_data = resp.model_dump(mode="json")

    event_broker.publish_event(
        institution_id=user.institution_id,
        event_type="lesson_access_requested",
        data=event_data,
        target_user_ids=teacher_ids,
        target_roles=["teacher", "institution_admin", "platform_admin"],
    )

    for n in notifications_created:
        event_broker.publish_event(
            institution_id=user.institution_id,
            event_type="notification_created",
            data=NotificationResponse.model_validate(n).model_dump(mode="json"),
            target_user_ids=[n.recipient_id],
        )

    return resp


@router.get("/access-requests/{request_id}", response_model=LessonAccessRequestResponse)
def get_lesson_access_request(
    request_id: uuid.UUID,
    user: CurrentUser,
    db: Db,
) -> LessonAccessRequestResponse:
    order = db.get(PaymentOrder, request_id)
    if not order or order.product_type != PaymentProductType.LESSON or not order.product_id:
        raise HTTPException(status_code=404, detail="Lesson access request not found")

    if user.role == UserRole.STUDENT and order.student_id != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    lesson, course = _lesson_and_course(db, order.product_id)
    student = db.get(User, order.student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    return _build_response(order, lesson, course, student)


@router.post("/access-requests/{request_id}/approve", response_model=LessonAccessRequestResponse)
def approve_lesson_access_request(
    request_id: uuid.UUID,
    payload: LessonAccessReviewRequest,
    user: Reviewer,
    db: Db,
) -> LessonAccessRequestResponse:
    order = db.get(PaymentOrder, request_id)
    if not order or order.product_type != PaymentProductType.LESSON or not order.product_id:
        raise HTTPException(status_code=404, detail="Lesson access request not found")

    lesson, course = _lesson_and_course(db, order.product_id)
    if not payment_service.can_review_order(db, user, order):
        raise HTTPException(status_code=403, detail="You do not have permission to approve access for this course")

    student = db.get(User, order.student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    # If already approved, return current state
    if order.status == PaymentStatus.PAID:
        return _build_response(order, lesson, course, student)

    # Approve and grant access
    approved_order = payment_service.approve_order(db, user, order, payload.note)

    # Create persistent notification for the student
    student_notif = Notification(
        institution_id=order.institution_id,
        recipient_id=order.student_id,
        kind="system",
        title=f"تمت إتاحة درس: {lesson.title}",
        message=f"وافق المعلم على طلبك لإتاحة درس '{lesson.title}'. يمكنك الآن مشاهدة الدرس والمحتويات كاملة.",
        action_url="#mycourses",
    )
    db.add(student_notif)
    db.commit()
    db.refresh(approved_order)
    db.refresh(student_notif)

    resp = _build_response(approved_order, lesson, course, student)

    # Real-time event 1: Instant unlock for the student
    event_broker.publish_event(
        institution_id=order.institution_id,
        event_type="lesson_access_approved",
        data={
            "request_id": str(approved_order.id),
            "lesson_id": str(lesson.id),
            "course_id": str(course.id),
            "student_id": str(order.student_id),
            "status": "approved",
        },
        target_user_ids=[order.student_id],
    )

    # Real-time event 2: Notification delivery
    event_broker.publish_event(
        institution_id=order.institution_id,
        event_type="notification_created",
        data=NotificationResponse.model_validate(student_notif).model_dump(mode="json"),
        target_user_ids=[order.student_id],
    )

    # Real-time event 3: Notify reviewing teachers so their UI updates
    event_broker.publish_event(
        institution_id=order.institution_id,
        event_type="lesson_access_updated",
        data=resp.model_dump(mode="json"),
        target_roles=["teacher", "institution_admin"],
    )

    return resp


@router.post("/access-requests/{request_id}/reject", response_model=LessonAccessRequestResponse)
def reject_lesson_access_request(
    request_id: uuid.UUID,
    payload: LessonAccessReviewRequest,
    user: Reviewer,
    db: Db,
) -> LessonAccessRequestResponse:
    order = db.get(PaymentOrder, request_id)
    if not order or order.product_type != PaymentProductType.LESSON or not order.product_id:
        raise HTTPException(status_code=404, detail="Lesson access request not found")

    lesson, course = _lesson_and_course(db, order.product_id)
    if not payment_service.can_review_order(db, user, order):
        raise HTTPException(status_code=403, detail="You do not have permission to reject access for this course")

    if order.status == PaymentStatus.PAID:
        raise HTTPException(status_code=409, detail="Already approved requests cannot be rejected")

    student = db.get(User, order.student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    order.status = PaymentStatus.REJECTED
    order.reviewed_by = user.id
    order.reviewed_at = datetime.now(UTC)
    order.review_note = (payload.note or "").strip()[:4000] or None

    student_notif = Notification(
        institution_id=order.institution_id,
        recipient_id=order.student_id,
        kind="warning",
        title=f"رفض طلب إتاحة: {lesson.title}",
        message=f"تم رفض طلب إتاحة درس '{lesson.title}'." + (f" السبب: {payload.note}" if payload.note else ""),
        action_url="#mycourses",
    )
    db.add(student_notif)
    db.commit()
    db.refresh(order)
    db.refresh(student_notif)

    resp = _build_response(order, lesson, course, student)

    # Real-time events
    event_broker.publish_event(
        institution_id=order.institution_id,
        event_type="lesson_access_rejected",
        data={
            "request_id": str(order.id),
            "lesson_id": str(lesson.id),
            "student_id": str(order.student_id),
            "status": "rejected",
        },
        target_user_ids=[order.student_id],
    )

    event_broker.publish_event(
        institution_id=order.institution_id,
        event_type="notification_created",
        data=NotificationResponse.model_validate(student_notif).model_dump(mode="json"),
        target_user_ids=[order.student_id],
    )

    event_broker.publish_event(
        institution_id=order.institution_id,
        event_type="lesson_access_updated",
        data=resp.model_dump(mode="json"),
        target_roles=["teacher", "institution_admin"],
    )

    return resp


@router.get("/me/access-requests", response_model=list[LessonAccessRequestResponse])
def my_lesson_access_requests(
    user: Student,
    db: Db,
) -> list[LessonAccessRequestResponse]:
    orders = db.scalars(
        select(PaymentOrder)
        .where(
            PaymentOrder.student_id == user.id,
            PaymentOrder.institution_id == user.institution_id,
            PaymentOrder.product_type == PaymentProductType.LESSON,
        )
        .order_by(PaymentOrder.created_at.desc())
    ).all()

    results: list[LessonAccessRequestResponse] = []
    for order in orders:
        if not order.product_id:
            continue
        try:
            lesson, course = _lesson_and_course(db, order.product_id)
            results.append(_build_response(order, lesson, course, user))
        except HTTPException:
            continue
    return results
