from __future__ import annotations

import uuid
from datetime import datetime
try:
    from enum import StrEnum
except ImportError:
    from enum import Enum
    class StrEnum(str, Enum):
        pass

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.models.course import CourseStatus, EnrollmentStatus, LessonKind, MaterializationStatus
from app.models.platform import (
    AssignmentStatus,
    AttemptStatus,
    DeliveryStatus,
    QuizStatus,
    SubmissionStatus,
)
from app.models.user import Gender, GradeLevel, Religion, UserRole

GOVERNORATE_CODES = frozenset({
    "ALEXANDRIA", "ASWAN", "ASIUT", "BEHEIRA", "BENI_SUEF", "CAIRO", "DAKAHLIA",
    "DAMIETTA", "FAYOUM", "GHARBIA", "GIZA", "ISMAILIA", "KAFR_EL_SHEIKH", "LUXOR",
    "MATROUH", "MINYA", "MONUFIA", "NEW_VALLEY", "NORTH_SINAI", "PORT_SAID",
    "QALYUBIA", "QENA", "RED_SEA", "SHARQIA", "SOHAG", "SOUTH_SINAI", "SUEZ",
})


def _normalize_digits(value: str) -> str:
    return value.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))


def _normalize_phone(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    normalized = _normalize_digits(value).replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if not normalized.isdigit() or len(normalized) > 20:
        raise ValueError("Phone number must contain at most 20 digits")
    return normalized


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    institution_id: uuid.UUID
    username: str
    email: EmailStr
    display_name: str
    role: UserRole
    grade_level: GradeLevel | None = None
    governorate: str | None = None
    school_name: str | None = None
    gender: Gender | None = None
    student_phone: str | None = None
    guardian_phone: str | None = None
    national_id: str | None = None
    religion: Religion | None = None
    is_active: bool
    created_at: datetime


class PrivateUserResponse(UserResponse):
    """Returned to the authenticated account owner and administrators during auth flows."""
    pass


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str = Field(min_length=2, max_length=160)
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    username: str | None = Field(default=None, min_length=3, max_length=80)
    institution_slug: str = Field(
        default="demo", min_length=2, max_length=80, pattern=r"^[a-z0-9-]+$"
    )
    grade_level: GradeLevel
    student_phone: str | None = None
    guardian_phone: str | None = None
    national_id: str | None = None
    governorate: str = Field(min_length=1, max_length=40)
    school_name: str = Field(min_length=2, max_length=200)
    gender: Gender
    religion: Religion | None = None

    @field_validator("display_name", "school_name", mode="before")
    @classmethod
    def trim_required_text(cls, value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("Value must be text")
        normalized = value.strip()
        if not normalized:
            raise ValueError("Value is required")
        return normalized

    @field_validator("student_phone", "guardian_phone", mode="before")
    @classmethod
    def validate_phone(cls, value: object) -> str | None:
        return _normalize_phone(value if isinstance(value, str) else None)

    @field_validator("national_id", mode="before")
    @classmethod
    def validate_national_id(cls, value: object) -> str | None:
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        if not isinstance(value, str):
            raise ValueError("National ID must be text")
        normalized = _normalize_digits(value.strip())
        if not normalized.isdigit() or len(normalized) != 14:
            raise ValueError("National ID must contain exactly 14 digits")
        return normalized

    @field_validator("governorate")
    @classmethod
    def validate_governorate(cls, value: str) -> str:
        if value not in GOVERNORATE_CODES:
            raise ValueError("Governorate is not supported")
        return value

    @field_validator("password")
    @classmethod
    def password_has_basic_strength(cls, value: str) -> str:
        if value.lower() in {"password123", "1234567890", "qwerty1234"}:
            raise ValueError("Choose a less predictable password")
        return value


class LoginRequest(BaseModel):
    email: str = Field(min_length=1, max_length=160)
    password: str = Field(min_length=1, max_length=128)
    institution_slug: str = Field(
        default="demo", min_length=2, max_length=80, pattern=r"^[a-z0-9-]+$"
    )


class AuthResponse(BaseModel):
    user: PrivateUserResponse
    expires_in: int
    expires_at: datetime
    token: str | None = None


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=10, max_length=128)


class PasswordResetRequest(BaseModel):
    email: EmailStr
    institution_slug: str = Field(
        default="demo", min_length=2, max_length=80, pattern=r"^[a-z0-9-]+$"
    )


class PasswordResetConfirm(BaseModel):
    token: str = Field(min_length=20, max_length=256)
    new_password: str = Field(min_length=10, max_length=128)


class CourseCreateRequest(BaseModel):
    code: str = Field(min_length=2, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")
    title: str = Field(min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=10_000)
    status: CourseStatus = CourseStatus.DRAFT
    teacher_id: uuid.UUID | None = None
    price_egp: float = Field(default=0, ge=0, le=1_000_000)


class ModuleCreateRequest(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    position: int = Field(ge=1, le=10_000)


class LessonCreateRequest(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    kind: LessonKind
    position: int = Field(ge=1, le=10_000)
    content: str | None = Field(default=None, max_length=100_000)
    # Deliberately no video_asset_key: native videos are attached only via the
    # authorization-checked upload endpoint, never through lesson creation.
    # Public embed URLs (YouTube/Drive) entered by the teacher are accepted
    # through this dedicated, scheme-validated field instead.
    external_video_url: str | None = Field(default=None, max_length=2048)
    video_duration_seconds: int | None = Field(default=None, ge=1, le=24 * 60 * 60)
    price_egp: float = Field(default=0, ge=0, le=1_000_000)

    @field_validator("external_video_url")
    @classmethod
    def _validate_external_video_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        if not trimmed:
            return None
        if not (trimmed.startswith("https://") or trimmed.startswith("http://")):
            raise ValueError("external_video_url must be an http(s) URL")
        return trimmed


class LessonMaterialSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    file_format: str
    size_bytes: int
    source_role: str
    download_url: str
    created_at: datetime


class LessonResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    kind: LessonKind
    position: int
    content: str | None
    # The raw storage key is never serialized: it is a private-path secret and
    # clients only need the boolean plus the token-gated stream URL.
    has_video: bool = False
    video_url: str | None = None
    video_duration_seconds: int | None
    materialization_status: MaterializationStatus = MaterializationStatus.NOT_INDEXED
    materialization_error: str | None = None
    price_egp: float = 0
    materials: list[LessonMaterialSummary] = []


class ModuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    position: int
    lessons: list[LessonResponse] = []


class CourseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    institution_id: uuid.UUID
    teacher_id: uuid.UUID
    code: str
    title: str
    description: str | None
    status: CourseStatus
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime
    price_egp: float = 0
    modules: list[ModuleResponse] = []


class EnrollmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    course_id: uuid.UUID
    student_id: uuid.UUID
    status: EnrollmentStatus
    progress_percent: float
    enrolled_at: datetime
    completed_at: datetime | None


class PageInfo(BaseModel):
    page: int
    page_size: int
    total: int
    pages: int


T = TypeVar("T")


class PageResponse(BaseModel, Generic[T]):
    items: list[T]
    pagination: PageInfo


class ReadinessResponse(BaseModel):
    status: str
    service: str
    environment: str
    dependencies: dict[str, str]


class VideoEventType(StrEnum):
    PLAY = "play"
    PAUSE = "pause"
    SEEK = "seek"
    RESUME = "resume"
    ENDED = "ended"
    VISIBILITY_CHANGE = "visibilitychange"
    PAGEHIDE = "pagehide"


class VideoEventInput(BaseModel):
    client_event_id: str = Field(min_length=8, max_length=64)
    lesson_id: uuid.UUID
    event_type: VideoEventType
    position_seconds: float = Field(default=0, ge=0)
    watched_delta_seconds: float = Field(default=0, ge=0, le=3600)
    duration_seconds: float | None = Field(default=None, ge=0, le=24 * 60 * 60)
    occurred_at: datetime | None = None


class VideoTelemetryBatch(BaseModel):
    events: list[VideoEventInput] = Field(min_length=1, max_length=100)


class VideoTelemetryResponse(BaseModel):
    accepted: int
    duplicates: int


class LessonProgressResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    lesson_id: uuid.UUID
    last_position_seconds: float
    watched_duration_seconds: float
    completion_percent: float
    last_event_at: datetime | None
    completed_at: datetime | None


class AnalyticsResponse(BaseModel):
    course_id: uuid.UUID
    enrolled_students: int
    completed_lessons: int
    average_completion_percent: float
    assignment_average_score: float | None
    quiz_average_score: float | None
    risk: dict[str, object]


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: str
    title: str
    message: str
    action_url: str | None
    read_at: datetime | None
    scheduled_for: datetime | None
    delivered_at: datetime | None
    delivery_status: DeliveryStatus
    created_at: datetime


class NotificationCreateRequest(BaseModel):
    recipient_id: uuid.UUID
    kind: str = Field(min_length=2, max_length=40)
    title: str = Field(min_length=2, max_length=200)
    message: str = Field(min_length=1, max_length=10_000)
    action_url: str | None = Field(default=None, max_length=512)
    dedup_key: str | None = Field(default=None, max_length=160)
    scheduled_for: datetime | None = None


class NotificationBroadcastRequest(BaseModel):
    kind: str = Field(min_length=2, max_length=40)
    title: str = Field(min_length=2, max_length=200)
    message: str = Field(min_length=1, max_length=10_000)
    action_url: str | None = Field(default=None, max_length=512)
    dedup_key: str | None = Field(default=None, max_length=160)
    scheduled_for: datetime | None = None


class CalendarEventCreateRequest(BaseModel):
    course_id: uuid.UUID | None = None
    title: str = Field(min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=10_000)
    event_type: str = Field(min_length=2, max_length=40)
    starts_at: datetime
    ends_at: datetime | None = None
    is_published: bool = True


class CalendarEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    course_id: uuid.UUID | None
    title: str
    description: str | None
    event_type: str
    starts_at: datetime
    ends_at: datetime | None
    is_published: bool
    cancelled_at: datetime | None
    created_at: datetime


class QuestionCreateRequest(BaseModel):
    course_id: uuid.UUID | None = None
    question_type: str = Field(min_length=2, max_length=40)
    prompt: str = Field(min_length=2, max_length=10_000)
    options: list | None = None
    correct_answer: object | None = None
    points: float = Field(default=1.0, gt=0, le=1000)
    learning_objective: str | None = Field(default=None, max_length=200)


class QuestionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    course_id: uuid.UUID | None
    version: int
    question_type: str
    prompt: str
    options: list | None
    points: float
    learning_objective: str | None
    is_active: bool
    created_at: datetime


class QuizCreateRequest(BaseModel):
    course_id: uuid.UUID
    title: str = Field(default="", max_length=200)
    quiz_title: str | None = Field(default=None, max_length=200)
    duration_seconds: int | None = Field(default=None, ge=30, le=24 * 60 * 60)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    randomize_questions: bool = False
    attempts_allowed: int = Field(default=1, ge=1, le=10)
    question_ids: list[uuid.UUID] = Field(default_factory=list, max_length=200)
    # Attach the quiz to a unit and optionally to the exact lesson it covers.
    module_id: uuid.UUID | None = None
    lesson_id: uuid.UUID | None = None

    @model_validator(mode="before")
    @classmethod
    def resolve_title(cls, data: Any) -> Any:
        if isinstance(data, dict):
            t = (data.get("title") or data.get("quiz_title") or "").strip()
            if not t:
                raise ValueError("اسم الاختبار (quiz_title) إجباري ولا يمكن تركه فارغاً")
            if len(t) < 2:
                raise ValueError("اسم الاختبار يجب أن يحتوي على حرفين على الأقل")
            data["title"] = t
            data["quiz_title"] = t
        return data


class QuizResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    course_id: uuid.UUID
    title: str
    quiz_title: str | None = None
    status: QuizStatus
    version: int
    duration_seconds: int | None
    starts_at: datetime | None
    ends_at: datetime | None
    published_at: datetime | None
    module_id: uuid.UUID | None = None
    lesson_id: uuid.UUID | None = None
    randomize_questions: bool
    attempts_allowed: int
    created_at: datetime

    @model_validator(mode="after")
    def populate_quiz_title(self) -> "QuizResponse":
        if not self.quiz_title:
            self.quiz_title = self.title
        return self


class QuizAttemptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    quiz_id: uuid.UUID
    student_id: uuid.UUID
    attempt_number: int
    started_at: datetime
    expires_at: datetime | None
    submitted_at: datetime | None
    status: AttemptStatus
    score: float | None
    total_points: float | None
    is_practice: bool = False


class AssignmentAttemptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    assignment_id: uuid.UUID
    student_id: uuid.UUID
    attempt_number: int
    started_at: datetime
    expires_at: datetime | None
    submitted_at: datetime | None
    status: str


class QuizAnswerInput(BaseModel):
    question_id: uuid.UUID
    answer: object | None = None


class QuizAttemptSubmitRequest(BaseModel):
    submission_key: str = Field(min_length=8, max_length=100)
    answers: list[QuizAnswerInput] = Field(max_length=200)


class AssignmentCreateRequest(BaseModel):
    course_id: uuid.UUID
    title: str = Field(default="", max_length=200)
    assignment_title: str | None = Field(default=None, max_length=200)
    prompt: str = Field(min_length=2, max_length=20_000)
    due_at: datetime | None = None
    # Attach the assignment to a unit and optionally to one lesson.
    module_id: uuid.UUID | None = None
    lesson_id: uuid.UUID | None = None
    max_score: float = Field(default=100.0, gt=0, le=100_000)

    @model_validator(mode="before")
    @classmethod
    def resolve_title(cls, data: Any) -> Any:
        if isinstance(data, dict):
            t = (data.get("title") or data.get("assignment_title") or "").strip()
            if not t:
                raise ValueError("اسم الواجب (assignment_title) إجباري ولا يمكن تركه فارغاً")
            if len(t) < 2:
                raise ValueError("اسم الواجب يجب أن يحتوي على حرفين على الأقل")
            data["title"] = t
            data["assignment_title"] = t
        return data


class AssignmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    course_id: uuid.UUID
    title: str
    assignment_title: str | None = None
    prompt: str
    due_at: datetime | None
    max_score: float
    status: AssignmentStatus
    created_at: datetime
    module_id: uuid.UUID | None = None
    lesson_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def populate_assignment_title(self) -> "AssignmentResponse":
        if not self.assignment_title:
            self.assignment_title = self.title
        return self


class AssignmentSubmissionCreateRequest(BaseModel):
    answer_text: str = Field(min_length=1, max_length=100_000)
    object_key: str | None = Field(default=None, max_length=512)
    idempotency_key: str = Field(min_length=8, max_length=100)


class AssignmentSubmissionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    assignment_id: uuid.UUID
    student_id: uuid.UUID
    version: int
    answer_text: str
    object_key: str | None
    status: SubmissionStatus
    ai_score: float | None
    final_score: float | None
    ai_feedback: str | None
    teacher_feedback: str | None
    submitted_at: datetime
    graded_at: datetime | None
    approved_at: datetime | None
    assignment_title: str | None = None
    assignment_prompt: str | None = None
    max_score: float | None = None
    course_title: str | None = None
    student_name: str | None = None


class GradeSubmissionRequest(BaseModel):
    final_score: float = Field(ge=0, le=100_000)
    teacher_feedback: str | None = Field(default=None, max_length=20_000)
    approve: bool = False


class CertificateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    course_id: uuid.UUID
    student_id: uuid.UUID
    verification_token: str
    score: float | None
    issued_at: datetime
    revoked_at: datetime | None


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    actor_id: uuid.UUID | None
    action: str
    resource_type: str
    resource_id: str | None
    before_json: dict | None
    after_json: dict | None
    request_id: str | None
    occurred_at: datetime


class LessonAccessRequestCreate(BaseModel):
    student_note: str | None = Field(default=None, max_length=2000)


class LessonAccessReviewRequest(BaseModel):
    note: str | None = Field(default=None, max_length=2000)


class LessonAccessRequestResponse(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    student_name: str
    student_phone: str | None = None
    lesson_id: uuid.UUID
    lesson_title: str
    course_id: uuid.UUID
    course_title: str
    status: str
    student_note: str | None = None
    reviewer_note: str | None = None
    created_at: datetime
    reviewed_at: datetime | None = None


class BootstrapResponse(BaseModel):
    authenticated: bool
    user: PrivateUserResponse | None = None
    unread_notifications_count: int = 0
    notifications: list[NotificationResponse] = Field(default_factory=list)
    courses: list[CourseResponse] = Field(default_factory=list)
    enrolled_course_ids: list[str] = Field(default_factory=list)
    entitlements: list[dict[str, Any]] = Field(default_factory=list)
    settings: dict[str, Any] = Field(default_factory=dict)

