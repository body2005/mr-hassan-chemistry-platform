from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.course import Course, CourseModule, CourseStatus, Enrollment, EnrollmentStatus, Lesson
from app.models.payment import (
    EntitlementType,
    PaymentMethod,
    PaymentOrder,
    PaymentProductType,
    PaymentStatus,
    StudentEntitlement,
)
from app.models.user import User, UserRole

UTC = timezone.utc


def _now() -> datetime:
    return datetime.now(UTC)


def is_entitlement_active(entitlement: StudentEntitlement, now: datetime | None = None) -> bool:
    current = now or _now()
    expires_at = entitlement.expires_at
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    starts_at = entitlement.starts_at
    if starts_at.tzinfo is None:
        starts_at = starts_at.replace(tzinfo=UTC)
    return entitlement.revoked_at is None and starts_at <= current and (
        expires_at is None or expires_at > current
    )


def get_active_entitlement(
    db: Session,
    student: User,
    entitlement_type: EntitlementType,
    resource_id: uuid.UUID | None = None,
) -> StudentEntitlement | None:
    rows = db.scalars(
        select(StudentEntitlement).where(
            StudentEntitlement.institution_id == student.institution_id,
            StudentEntitlement.student_id == student.id,
            StudentEntitlement.entitlement_type == entitlement_type,
            StudentEntitlement.resource_id == resource_id,
            StudentEntitlement.revoked_at.is_(None),
        )
    ).all()
    return next((row for row in rows if is_entitlement_active(row)), None)


def has_course_entitlement(db: Session, student: User, course_id: uuid.UUID) -> bool:
    return get_active_entitlement(db, student, EntitlementType.COURSE, course_id) is not None


def has_lesson_entitlement(db: Session, student: User, lesson_id: uuid.UUID) -> bool:
    return get_active_entitlement(db, student, EntitlementType.LESSON, lesson_id) is not None


def has_global_ai_entitlement(db: Session, student: User) -> bool:
    return get_active_entitlement(db, student, EntitlementType.AI_GLOBAL, None) is not None


def _lesson_and_course(db: Session, lesson_id: uuid.UUID) -> tuple[Lesson | None, Course | None]:
    row = db.execute(
        select(Lesson, Course)
        .join(CourseModule, Lesson.module_id == CourseModule.id)
        .join(Course, CourseModule.course_id == Course.id)
        .where(Lesson.id == lesson_id)
    ).first()
    return (row[0], row[1]) if row else (None, None)


def can_access_course_content(db: Session, user: User, course_id: uuid.UUID) -> bool:
    course = db.get(Course, course_id)
    if not course:
        return False
    if user.role == UserRole.PLATFORM_ADMIN:
        return True
    if course.institution_id != user.institution_id:
        return False
    if user.role in {UserRole.TEACHER, UserRole.INSTITUTION_ADMIN}:
        return user.role == UserRole.INSTITUTION_ADMIN or course.teacher_id == user.id
    enrollment = db.scalar(
        select(Enrollment.id).where(
            Enrollment.course_id == course_id,
            Enrollment.student_id == user.id,
            Enrollment.status.in_([EnrollmentStatus.ACTIVE, EnrollmentStatus.COMPLETED]),
        )
    )
    if enrollment is None:
        return False
    return float(course.price_egp or 0) == 0 or has_course_entitlement(db, user, course_id)


def can_access_lesson_content(db: Session, user: User, lesson_id: uuid.UUID) -> bool:
    lesson, course = _lesson_and_course(db, lesson_id)
    if not lesson or not course:
        return False
    if user.role == UserRole.PLATFORM_ADMIN:
        return True
    if course.institution_id != user.institution_id:
        return False
    if user.role in {UserRole.TEACHER, UserRole.INSTITUTION_ADMIN}:
        return user.role == UserRole.INSTITUTION_ADMIN or course.teacher_id == user.id
    enrollment = db.scalar(
        select(Enrollment.id).where(
            Enrollment.course_id == course.id,
            Enrollment.student_id == user.id,
            Enrollment.status.in_([EnrollmentStatus.ACTIVE, EnrollmentStatus.COMPLETED]),
        )
    )
    if enrollment is None:
        return False
    if has_course_entitlement(db, user, course.id):
        return True
    if has_lesson_entitlement(db, user, lesson.id):
        return True
    return float(course.price_egp or 0) == 0 and float(lesson.price_egp or 0) == 0


def student_can_use_ai_for_lesson(db: Session, student: User, lesson_id: uuid.UUID) -> bool:
    if not can_access_lesson_content(db, student, lesson_id):
        return False
    settings = get_settings()
    mode = settings.student_ai_access_mode
    if mode == "open":
        return True
    if mode == "subscription_only":
        return has_global_ai_entitlement(db, student)
    if mode == "included_with_content":
        return True
    lesson, course = _lesson_and_course(db, lesson_id)
    if not lesson or not course:
        return False
    return (
        has_global_ai_entitlement(db, student)
        or has_course_entitlement(db, student, course.id)
        or has_lesson_entitlement(db, student, lesson.id)
    )


def resolve_product(
    db: Session,
    student: User,
    product_type: PaymentProductType,
    product_id: uuid.UUID | None,
) -> tuple[str, float]:
    if product_type == PaymentProductType.AI_SUBSCRIPTION:
        if product_id is not None:
            raise HTTPException(status_code=422, detail="AI subscription does not accept product_id")
        return "اشتراك المساعد الذكي لمدة 30 يومًا", float(get_settings().student_ai_monthly_price_egp)

    if product_id is None:
        raise HTTPException(status_code=422, detail="product_id is required")
    if product_type == PaymentProductType.COURSE:
        course = db.scalar(
            select(Course).where(
                Course.id == product_id,
                Course.institution_id == student.institution_id,
                Course.status == CourseStatus.PUBLISHED,
            )
        )
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")
        return course.title, float(course.price_egp or 0)

    lesson, course = _lesson_and_course(db, product_id)
    if not lesson or not course or course.institution_id != student.institution_id:
        raise HTTPException(status_code=404, detail="Lesson not found")
    if course.status != CourseStatus.PUBLISHED:
        raise HTTPException(status_code=404, detail="Lesson not found")
    return lesson.title, float(lesson.price_egp or 0)


def create_order(
    db: Session,
    student: User,
    product_type: PaymentProductType,
    product_id: uuid.UUID | None,
    payment_method: PaymentMethod,
    payer_reference: str | None,
    student_note: str | None,
) -> PaymentOrder:
    product_name, amount = resolve_product(db, student, product_type, product_id)
    if amount <= 0:
        raise HTTPException(status_code=409, detail="This item is free and does not require payment")
    existing = db.scalar(
        select(PaymentOrder)
        .where(
            PaymentOrder.student_id == student.id,
            PaymentOrder.product_type == product_type,
            PaymentOrder.product_id == product_id,
            PaymentOrder.status.in_([PaymentStatus.PENDING, PaymentStatus.UNDER_REVIEW]),
        )
        .order_by(PaymentOrder.created_at.desc())
    )
    if existing:
        return existing
    order = PaymentOrder(
        institution_id=student.institution_id,
        student_id=student.id,
        product_type=product_type,
        product_id=product_id,
        product_name=product_name,
        amount_egp=amount,
        payment_method=payment_method,
        payer_reference=(payer_reference or "").strip()[:160] or None,
        student_note=(student_note or "").strip()[:4000] or None,
        status=PaymentStatus.PENDING,
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


def can_review_order(db: Session, reviewer: User, order: PaymentOrder) -> bool:
    if reviewer.role == UserRole.PLATFORM_ADMIN:
        return True
    if reviewer.institution_id != order.institution_id:
        return False
    if reviewer.role == UserRole.INSTITUTION_ADMIN:
        return True
    if reviewer.role != UserRole.TEACHER:
        return False
    if order.product_type == PaymentProductType.AI_SUBSCRIPTION:
        return True
    if order.product_type == PaymentProductType.COURSE:
        course = db.get(Course, order.product_id)
        return bool(course and course.teacher_id == reviewer.id)
    _, course = _lesson_and_course(db, order.product_id) if order.product_id else (None, None)
    return bool(course and course.teacher_id == reviewer.id)


def approve_order(db: Session, reviewer: User, order: PaymentOrder, note: str | None) -> PaymentOrder:
    if not can_review_order(db, reviewer, order):
        raise HTTPException(status_code=404, detail="Payment order not found")
    if order.status == PaymentStatus.PAID:
        return order
    if order.status in {PaymentStatus.REJECTED, PaymentStatus.CANCELLED}:
        raise HTTPException(status_code=409, detail="Closed payment orders cannot be approved")

    now = _now()
    if order.product_type == PaymentProductType.COURSE:
        entitlement_type = EntitlementType.COURSE
        resource_id = order.product_id
        expires_at = None
    elif order.product_type == PaymentProductType.LESSON:
        entitlement_type = EntitlementType.LESSON
        resource_id = order.product_id
        expires_at = None
    else:
        entitlement_type = EntitlementType.AI_GLOBAL
        resource_id = None
        current = get_active_entitlement(db, order.student, EntitlementType.AI_GLOBAL, None)
        current_expiry = current.expires_at if current else None
        if current_expiry and current_expiry.tzinfo is None:
            current_expiry = current_expiry.replace(tzinfo=UTC)
        start_from = max(now, current_expiry) if current_expiry else now
        expires_at = start_from + timedelta(days=get_settings().student_ai_subscription_days)

    entitlement = get_active_entitlement(db, order.student, entitlement_type, resource_id)
    if entitlement:
        if expires_at:
            entitlement.expires_at = expires_at
        entitlement.source_order_id = order.id
    else:
        db.add(
            StudentEntitlement(
                institution_id=order.institution_id,
                student_id=order.student_id,
                entitlement_type=entitlement_type,
                resource_id=resource_id,
                source_order_id=order.id,
                starts_at=now,
                expires_at=expires_at,
            )
        )

    if order.product_type in {PaymentProductType.COURSE, PaymentProductType.LESSON}:
        course_id = order.product_id
        if order.product_type == PaymentProductType.LESSON and order.product_id:
            _, lesson_course = _lesson_and_course(db, order.product_id)
            course_id = lesson_course.id if lesson_course else None
        if course_id:
            enrollment = db.scalar(
                select(Enrollment).where(
                    Enrollment.course_id == course_id,
                    Enrollment.student_id == order.student_id,
                )
            )
            if enrollment:
                enrollment.status = EnrollmentStatus.ACTIVE
            else:
                db.add(
                    Enrollment(
                        course_id=course_id,
                        student_id=order.student_id,
                        status=EnrollmentStatus.ACTIVE,
                    )
                )

    order.status = PaymentStatus.PAID
    order.reviewed_by = reviewer.id
    order.reviewed_at = now
    order.review_note = (note or "").strip()[:4000] or None
    db.commit()
    db.refresh(order)
    return order
