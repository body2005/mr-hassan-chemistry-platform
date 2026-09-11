from __future__ import annotations

import uuid
from datetime import datetime
try:
    from enum import StrEnum
except ImportError:
    from enum import Enum
    class StrEnum(str, Enum):
        pass

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.course import CourseStatus, EnrollmentStatus, LessonKind, IndexingStatus
from app.models.platform import (
    AssignmentStatus,
    AttemptStatus,
    DeliveryStatus,
    QuizStatus,
    SubmissionStatus,
)
from app.models.user import UserRole


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    institution_id: uuid.UUID
    username: str
    email: EmailStr
    display_name: str
    role: UserRole
    is_active: bool
    created_at: datetime


class RegisterRequest(BaseModel):
    display_name: str = Field(min_length=2, max_length=160)
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    username: str | None = Field(default=None, min_length=3, max_length=80)
    institution_slug: str = Field(
        default="demo", min_length=2, max_length=80, pattern=r"^[a-z0-9-]+$"
    )

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
    user: UserResponse
    expires_in: int
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


class ModuleCreateRequest(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    position: int = Field(ge=1, le=10_000)


class LessonCreateRequest(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    kind: LessonKind
    position: int = Field(ge=1, le=10_000)
    content: str | None = Field(default=None, max_length=100_000)
    video_asset_key: str | None = Field(default=None, max_length=512)
    video_duration_seconds: int | None = Field(default=None, ge=1, le=24 * 60 * 60)


class LessonResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    kind: LessonKind
    position: int
    content: str | None
    video_asset_key: str | None
    video_duration_seconds: int | None
    indexing_status: IndexingStatus = IndexingStatus.NOT_INDEXED
    indexing_error: str | None = None
    indexed_chunks_count: int = 0
    rag_synced: bool = False


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
    title: str = Field(min_length=2, max_length=200)
    duration_seconds: int | None = Field(default=None, ge=30, le=24 * 60 * 60)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    randomize_questions: bool = False
    attempts_allowed: int = Field(default=1, ge=1, le=10)
    question_ids: list[uuid.UUID] = Field(default_factory=list, max_length=200)


class QuizResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    course_id: uuid.UUID
    title: str
    status: QuizStatus
    version: int
    duration_seconds: int | None
    starts_at: datetime | None
    ends_at: datetime | None
    published_at: datetime | None
    randomize_questions: bool
    attempts_allowed: int
    created_at: datetime


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
    title: str = Field(min_length=2, max_length=200)
    prompt: str = Field(min_length=2, max_length=20_000)
    due_at: datetime | None = None
    max_score: float = Field(default=100.0, gt=0, le=100_000)


class AssignmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    course_id: uuid.UUID
    title: str
    prompt: str
    due_at: datetime | None
    max_score: float
    status: AssignmentStatus
    created_at: datetime


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


class AIInvocationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    task: str
    provider: str
    model: str
    prompt_version: str
    status: str
    latency_ms: int | None
    input_tokens: int | None
    output_tokens: int | None
    estimated_cost: float | None
    error_code: str | None
    output_json: dict | list | None
    created_at: datetime


class AIInvocationRequest(BaseModel):
    task: str = Field(min_length=2, max_length=60)
    prompt: str = Field(min_length=1, max_length=100_000)
    provider: str = Field(default="ollama", min_length=2, max_length=60)
    model: str | None = Field(default=None, max_length=120)
    prompt_version: str = Field(default="v1", min_length=1, max_length=40)


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
