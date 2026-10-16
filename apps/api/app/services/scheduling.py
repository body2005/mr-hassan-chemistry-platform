"""Reject newly selected past times without changing historical schedules."""

from datetime import UTC, datetime

from fastapi import HTTPException


def require_upcoming_time(value, *, existing=None):
    if value is None:
        return  # No timestamp means immediate publication, not a past schedule.
    # Request schemas reject naive user input; SQLite/legacy stored rows can
    # still return naive UTC values, as in the existing scheduling services.
    value = (
        value.replace(tzinfo=UTC)
        if value.tzinfo is None
        else value.astimezone(UTC)
    )
    if existing is not None:
        existing = (
            existing.replace(tzinfo=UTC)
            if existing.tzinfo is None
            else existing.astimezone(UTC)
        )
        if value == existing:
            return
    # Forms select minutes: selecting the current minute remains valid while
    # seconds elapse in a confirmation dialog. Earlier minutes are rejected.
    if value < datetime.now(UTC).replace(second=0, microsecond=0):
        raise HTTPException(
            422, "لا يمكن اختيار موعد جدولة في الماضي؛ اختر الوقت الحالي أو موعدًا لاحقًا."
        )
