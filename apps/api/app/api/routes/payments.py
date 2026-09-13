from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import CurrentUser, require_roles
from app.core.config import get_settings
from app.core.database import get_db
from app.models.payment import (
    PaymentMethod,
    PaymentOrder,
    PaymentProductType,
    PaymentStatus,
    StudentEntitlement,
)
from app.models.course import Course, CourseModule, Lesson
from app.models.user import User, UserRole
from app.services import payment_service

router = APIRouter(prefix="/payments")
Db = Annotated[Session, Depends(get_db)]
Student = Annotated[User, Depends(require_roles(UserRole.STUDENT))]
Reviewer = Annotated[
    User,
    Depends(require_roles(UserRole.TEACHER, UserRole.INSTITUTION_ADMIN, UserRole.PLATFORM_ADMIN)),
]


class PaymentOrderCreate(BaseModel):
    product_type: PaymentProductType
    product_id: uuid.UUID | None = None
    payment_method: PaymentMethod
    payer_reference: str | None = Field(default=None, max_length=160)
    student_note: str | None = Field(default=None, max_length=4000)


class ReviewPaymentRequest(BaseModel):
    note: str | None = Field(default=None, max_length=4000)


class PriceUpdateRequest(BaseModel):
    price_egp: float = Field(ge=0, le=1_000_000)


def _order_response(order: PaymentOrder) -> dict[str, Any]:
    return {
        "id": str(order.id),
        "student_id": str(order.student_id),
        "student_name": order.student.display_name if order.student else None,
        "product_type": order.product_type.value,
        "product_id": str(order.product_id) if order.product_id else None,
        "product_name": order.product_name,
        "amount_egp": float(order.amount_egp),
        "payment_method": order.payment_method.value,
        "status": order.status.value,
        "payer_reference": order.payer_reference,
        "has_receipt": bool(order.receipt_path),
        "student_note": order.student_note,
        "review_note": order.review_note,
        "reviewed_at": order.reviewed_at.isoformat() if order.reviewed_at else None,
        "created_at": order.created_at.isoformat(),
    }


def _method_destination(method: PaymentMethod) -> str | None:
    settings = get_settings()
    return {
        PaymentMethod.INSTAPAY: settings.payment_instapay_account,
        PaymentMethod.VODAFONE_CASH: settings.payment_vodafone_cash_number,
        PaymentMethod.BANK_TRANSFER: settings.payment_bank_details,
    }[method]


@router.get("/config")
def payment_config(user: Student) -> dict[str, Any]:
    settings = get_settings()
    methods = [
        {
            "id": method.value,
            "label": label,
            "destination": destination,
            "enabled": bool(destination),
        }
        for method, label, destination in (
            (PaymentMethod.INSTAPAY, "InstaPay", settings.payment_instapay_account),
            (PaymentMethod.VODAFONE_CASH, "Vodafone Cash", settings.payment_vodafone_cash_number),
            (PaymentMethod.BANK_TRANSFER, "تحويل بنكي", settings.payment_bank_details),
        )
    ]
    return {
        "currency": "EGP",
        "ai_monthly_price_egp": settings.student_ai_monthly_price_egp,
        "ai_subscription_days": settings.student_ai_subscription_days,
        "ai_access_mode": settings.student_ai_access_mode,
        "methods": methods,
    }


@router.post("/orders", status_code=status.HTTP_201_CREATED)
def create_payment_order(payload: PaymentOrderCreate, user: Student, db: Db) -> dict[str, Any]:
    if not _method_destination(payload.payment_method):
        raise HTTPException(status_code=409, detail="Selected payment method is not configured")
    order = payment_service.create_order(
        db,
        user,
        payload.product_type,
        payload.product_id,
        payload.payment_method,
        payload.payer_reference,
        payload.student_note,
    )
    return _order_response(order)


@router.post("/orders/{order_id}/receipt")
async def upload_payment_receipt(
    order_id: uuid.UUID,
    user: Student,
    db: Db,
    payer_reference: str | None = Form(default=None),
    receipt: UploadFile = File(...),
) -> dict[str, Any]:
    order = db.scalar(
        select(PaymentOrder).where(
            PaymentOrder.id == order_id,
            PaymentOrder.student_id == user.id,
            PaymentOrder.institution_id == user.institution_id,
        )
    )
    if not order:
        raise HTTPException(status_code=404, detail="Payment order not found")
    if order.status in {PaymentStatus.PAID, PaymentStatus.REJECTED, PaymentStatus.CANCELLED}:
        raise HTTPException(status_code=409, detail="This payment order is already closed")

    extension = os.path.splitext(receipt.filename or "")[1].lower()
    allowed = {".jpg", ".jpeg", ".png", ".webp", ".pdf"}
    if extension not in allowed:
        raise HTTPException(status_code=422, detail="Receipt must be JPG, PNG, WEBP, or PDF")
    allowed_mime = {"image/jpeg", "image/png", "image/webp", "application/pdf"}
    if receipt.content_type and receipt.content_type not in allowed_mime:
        raise HTTPException(status_code=422, detail="Unsupported receipt content type")

    storage_root = os.getenv("STORAGE_DIR", "storage")
    receipt_dir = os.path.join(storage_root, "payment_receipts")
    os.makedirs(receipt_dir, exist_ok=True)
    destination = os.path.join(receipt_dir, f"{uuid.uuid4().hex}{extension}")
    max_bytes = get_settings().payment_receipt_max_mb * 1024 * 1024
    written = 0
    try:
        with open(destination, "wb") as output:
            while chunk := await receipt.read(1024 * 1024):
                written += len(chunk)
                if written > max_bytes:
                    raise HTTPException(status_code=413, detail="Payment receipt is too large")
                output.write(chunk)
    except Exception:
        if os.path.exists(destination):
            os.remove(destination)
        raise
    if written == 0:
        os.remove(destination)
        raise HTTPException(status_code=422, detail="Payment receipt is empty")

    previous_path = order.receipt_path
    order.receipt_path = destination
    order.payer_reference = (payer_reference or order.payer_reference or "").strip()[:160] or None
    order.status = PaymentStatus.UNDER_REVIEW
    db.commit()
    db.refresh(order)
    if previous_path and previous_path != destination and os.path.exists(previous_path):
        try:
            os.remove(previous_path)
        except OSError:
            pass
    return _order_response(order)


@router.get("/me/orders")
def my_payment_orders(user: Student, db: Db) -> list[dict[str, Any]]:
    orders = db.scalars(
        select(PaymentOrder)
        .where(
            PaymentOrder.student_id == user.id,
            PaymentOrder.institution_id == user.institution_id,
        )
        .order_by(PaymentOrder.created_at.desc())
    ).all()
    return [_order_response(order) for order in orders]


@router.get("/me/entitlements")
def my_entitlements(user: Student, db: Db) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(StudentEntitlement)
        .where(
            StudentEntitlement.student_id == user.id,
            StudentEntitlement.institution_id == user.institution_id,
            StudentEntitlement.revoked_at.is_(None),
        )
        .order_by(StudentEntitlement.created_at.desc())
    ).all()
    now = datetime.now(timezone.utc)
    return [
        {
            "id": str(row.id),
            "entitlement_type": row.entitlement_type.value,
            "resource_id": str(row.resource_id) if row.resource_id else None,
            "starts_at": row.starts_at.isoformat(),
            "expires_at": row.expires_at.isoformat() if row.expires_at else None,
            "active": payment_service.is_entitlement_active(row, now),
        }
        for row in rows
    ]


@router.get("/me/ai-access")
def my_ai_access(
    user: Student,
    db: Db,
    lesson_id: uuid.UUID | None = Query(default=None),
) -> dict[str, Any]:
    subscribed = payment_service.has_global_ai_entitlement(db, user)
    allowed = subscribed
    if lesson_id:
        allowed = payment_service.student_can_use_ai_for_lesson(db, user, lesson_id)
    return {
        "allowed": allowed,
        "global_subscription": subscribed,
        "lesson_id": str(lesson_id) if lesson_id else None,
        "mode": get_settings().student_ai_access_mode,
    }


@router.get("/orders")
def list_payment_orders(
    user: Reviewer,
    db: Db,
    order_status: PaymentStatus | None = Query(default=None, alias="status"),
) -> list[dict[str, Any]]:
    stmt = select(PaymentOrder)
    if user.role != UserRole.PLATFORM_ADMIN:
        stmt = stmt.where(PaymentOrder.institution_id == user.institution_id)
    if order_status:
        stmt = stmt.where(PaymentOrder.status == order_status)
    orders = db.scalars(stmt.order_by(PaymentOrder.created_at.desc()).limit(500)).all()
    return [_order_response(order) for order in orders if payment_service.can_review_order(db, user, order)]


@router.post("/orders/{order_id}/approve")
def approve_payment_order(
    order_id: uuid.UUID,
    payload: ReviewPaymentRequest,
    user: Reviewer,
    db: Db,
) -> dict[str, Any]:
    order = db.get(PaymentOrder, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Payment order not found")
    return _order_response(payment_service.approve_order(db, user, order, payload.note))


@router.post("/orders/{order_id}/reject")
def reject_payment_order(
    order_id: uuid.UUID,
    payload: ReviewPaymentRequest,
    user: Reviewer,
    db: Db,
) -> dict[str, Any]:
    order = db.get(PaymentOrder, order_id)
    if not order or not payment_service.can_review_order(db, user, order):
        raise HTTPException(status_code=404, detail="Payment order not found")
    if order.status == PaymentStatus.PAID:
        raise HTTPException(status_code=409, detail="Paid orders cannot be rejected")
    order.status = PaymentStatus.REJECTED
    order.reviewed_by = user.id
    order.reviewed_at = datetime.now(timezone.utc)
    order.review_note = (payload.note or "").strip()[:4000] or None
    db.commit()
    db.refresh(order)
    return _order_response(order)


@router.get("/orders/{order_id}/receipt", response_class=FileResponse)
def view_payment_receipt(order_id: uuid.UUID, user: CurrentUser, db: Db) -> FileResponse:
    order = db.get(PaymentOrder, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Payment order not found")
    can_view = order.student_id == user.id or payment_service.can_review_order(db, user, order)
    if not can_view:
        raise HTTPException(status_code=404, detail="Payment order not found")
    if not order.receipt_path:
        raise HTTPException(status_code=404, detail="Payment receipt not found")

    receipt_path = os.path.realpath(order.receipt_path)
    receipt_root = os.path.realpath(os.path.join(os.getenv("STORAGE_DIR", "storage"), "payment_receipts"))
    if os.path.commonpath([receipt_path, receipt_root]) != receipt_root or not os.path.isfile(receipt_path):
        raise HTTPException(status_code=404, detail="Payment receipt not found")
    return FileResponse(receipt_path, filename=f"receipt-{order.id}{os.path.splitext(receipt_path)[1]}")


@router.patch("/pricing/courses/{course_id}")
def update_course_price(
    course_id: uuid.UUID,
    payload: PriceUpdateRequest,
    user: Reviewer,
    db: Db,
) -> dict[str, Any]:
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    try:
        from app.services.platform_service import ensure_course_manager

        ensure_course_manager(user, course)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    course.price_egp = payload.price_egp
    db.commit()
    return {"id": str(course.id), "price_egp": float(course.price_egp or 0)}


@router.patch("/pricing/lessons/{lesson_id}")
def update_lesson_price(
    lesson_id: uuid.UUID,
    payload: PriceUpdateRequest,
    user: Reviewer,
    db: Db,
) -> dict[str, Any]:
    row = db.execute(
        select(Lesson, Course)
        .join(CourseModule, Lesson.module_id == CourseModule.id)
        .join(Course, CourseModule.course_id == Course.id)
        .where(Lesson.id == lesson_id)
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Lesson not found")
    lesson, course = row
    try:
        from app.services.platform_service import ensure_course_manager

        ensure_course_manager(user, course)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    lesson.price_egp = payload.price_egp
    db.commit()
    return {"id": str(lesson.id), "price_egp": float(lesson.price_egp or 0)}
