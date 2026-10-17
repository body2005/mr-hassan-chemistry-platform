"""Explicit account management, separate from course/payment authorization."""
from app.core.config import get_settings
from app.models.user import User, UserRole


def manages_registered_students(actor: User) -> bool:
    return actor.role in {UserRole.INSTITUTION_ADMIN, UserRole.PLATFORM_ADMIN} or (
        actor.role == UserRole.TEACHER
        and actor.id in get_settings().registered_student_manager_ids
    )
