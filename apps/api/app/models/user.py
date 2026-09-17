import uuid
from datetime import datetime
try:
    from enum import StrEnum
except ImportError:
    from enum import Enum
    class StrEnum(str, Enum):
        pass


from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, enum_values


class UserRole(StrEnum):
    STUDENT = "student"
    TEACHER = "teacher"
    INSTITUTION_ADMIN = "institution_admin"
    PLATFORM_ADMIN = "platform_admin"


class GradeLevel(StrEnum):
    SECONDARY_1 = "SECONDARY_1"
    SECONDARY_2 = "SECONDARY_2"
    SECONDARY_3 = "SECONDARY_3"


class Gender(StrEnum):
    MALE = "MALE"
    FEMALE = "FEMALE"


class Religion(StrEnum):
    MUSLIM = "MUSLIM"
    CHRISTIAN = "CHRISTIAN"
    OTHER = "OTHER"
    PREFER_NOT_TO_SAY = "PREFER_NOT_TO_SAY"


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("institution_id", "username", name="uq_users_institution_username"),
        UniqueConstraint("institution_id", "email", name="uq_users_institution_email"),
        UniqueConstraint("institution_id", "national_id", name="uq_users_institution_national_id"),
    )

    institution_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("institutions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    username: Mapped[str] = mapped_column(String(80), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role", native_enum=False, values_callable=enum_values),
        index=True,
        nullable=False,
    )
    grade_level: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    student_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    guardian_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    national_id: Mapped[str | None] = mapped_column(String(14), nullable=True)
    governorate: Mapped[str | None] = mapped_column(String(40), nullable=True)
    school_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    gender: Mapped[Gender | None] = mapped_column(
        Enum(Gender, name="user_gender", native_enum=False, values_callable=enum_values), nullable=True
    )
    religion: Mapped[Religion | None] = mapped_column(
        Enum(Religion, name="user_religion", native_enum=False, values_callable=enum_values), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    institution = relationship("Institution", back_populates="users")
    taught_courses = relationship("Course", back_populates="teacher")
    enrollments = relationship("Enrollment", back_populates="student")
    password_reset_tokens = relationship(
        "PasswordResetToken", back_populates="user", cascade="all, delete-orphan"
    )


class PasswordResetToken(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "password_reset_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user = relationship("User", back_populates="password_reset_tokens")
