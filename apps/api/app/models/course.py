import uuid
from datetime import datetime
try:
    from enum import StrEnum
except ImportError:  # Python 3.10: enum.StrEnum arrived in 3.11
    from enum import Enum

    class StrEnum(str, Enum):
        def __str__(self) -> str:
            return str(self.value)


from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, enum_values


class CourseStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class EnrollmentStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    WITHDRAWN = "withdrawn"


class LessonKind(StrEnum):
    VIDEO = "video"
    ARTICLE = "article"
    LIVE = "live"


class MaterializationStatus(StrEnum):
    NOT_INDEXED = "not_indexed"
    IN_PROGRESS = "in_progress"
    INDEXED = "indexed"
    FAILED = "failed"


class Course(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "courses"
    __table_args__ = (
        UniqueConstraint("institution_id", "code", name="uq_courses_institution_code"),
    )

    institution_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("institutions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    teacher_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[CourseStatus] = mapped_column(
        Enum(
            CourseStatus,
            name="course_status",
            native_enum=False,
            values_callable=enum_values,
        ),
        default=CourseStatus.DRAFT,
        nullable=False,
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    price_egp: Mapped[float] = mapped_column(Numeric(10, 2), default=0, nullable=False)
    grade_level: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)

    institution = relationship("Institution", back_populates="courses")
    teacher = relationship("User", back_populates="taught_courses")
    modules = relationship(
        "CourseModule", back_populates="course", order_by="CourseModule.position"
    )
    enrollments = relationship("Enrollment", back_populates="course")


class CourseModule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "course_modules"
    __table_args__ = (
        UniqueConstraint("course_id", "position", name="uq_course_modules_course_position"),
    )

    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    course = relationship("Course", back_populates="modules")
    lessons = relationship("Lesson", back_populates="module", order_by="Lesson.position")


class Lesson(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "lessons"
    __table_args__ = (UniqueConstraint("module_id", "position", name="uq_lessons_module_position"),)

    module_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("course_modules.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    kind: Mapped[LessonKind] = mapped_column(
        Enum(LessonKind, name="lesson_kind", native_enum=False, values_callable=enum_values),
        nullable=False,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str | None] = mapped_column(Text)
    video_asset_key: Mapped[str | None] = mapped_column(String(512))
    video_duration_seconds: Mapped[int | None] = mapped_column(Integer)
    materialization_status: Mapped[MaterializationStatus] = mapped_column(
        Enum(MaterializationStatus, name="materialization_status", native_enum=False, values_callable=enum_values),
        default=MaterializationStatus.NOT_INDEXED,
        nullable=False,
    )
    materialization_error: Mapped[str | None] = mapped_column(Text)
    transcript_text: Mapped[str | None] = mapped_column(Text)
    price_egp: Mapped[float] = mapped_column(Numeric(10, 2), default=0, nullable=False)

    module = relationship("CourseModule", back_populates="lessons")


class Enrollment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "enrollments"
    __table_args__ = (
        UniqueConstraint("course_id", "student_id", name="uq_enrollments_course_student"),
    )

    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), index=True, nullable=False
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    status: Mapped[EnrollmentStatus] = mapped_column(
        Enum(
            EnrollmentStatus,
            name="enrollment_status",
            native_enum=False,
            values_callable=enum_values,
        ),
        default=EnrollmentStatus.ACTIVE,
        nullable=False,
    )
    progress_percent: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    enrolled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now().astimezone(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    course = relationship("Course", back_populates="enrollments")
    student = relationship("User", back_populates="enrollments")
