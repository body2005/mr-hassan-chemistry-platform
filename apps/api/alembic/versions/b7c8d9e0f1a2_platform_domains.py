"""platform domains, auditability, assessment and certificates

Revision ID: b7c8d9e0f1a2
Revises: a4b5c6d7e8f9
Create Date: 2026-08-25 18:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7c8d9e0f1a2"
down_revision: str | None = "a4b5c6d7e8f9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> tuple[sa.Column, sa.Column]:
    return (
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
    )


def upgrade() -> None:
    op.create_table(
        "audit_logs",
        sa.Column("institution_id", sa.Uuid(), nullable=True),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("resource_type", sa.String(80), nullable=False),
        sa.Column("resource_id", sa.String(128), nullable=True),
        sa.Column("before_json", sa.JSON(), nullable=True),
        sa.Column("after_json", sa.JSON(), nullable=True),
        sa.Column("request_id", sa.String(64), nullable=True),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.String(512), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_audit_logs"),
    )
    op.create_index("ix_audit_logs_institution_id", "audit_logs", ["institution_id"])
    op.create_index("ix_audit_logs_actor_id", "audit_logs", ["actor_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_request_id", "audit_logs", ["request_id"])

    op.create_table(
        "revoked_sessions",
        sa.Column("jti", sa.String(64), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_revoked_sessions"),
        sa.UniqueConstraint("jti", name="uq_revoked_sessions_jti"),
    )
    op.create_index("ix_revoked_sessions_jti", "revoked_sessions", ["jti"])
    op.create_index("ix_revoked_sessions_user_id", "revoked_sessions", ["user_id"])
    op.create_index("ix_revoked_sessions_expires_at", "revoked_sessions", ["expires_at"])

    op.create_table(
        "notifications",
        sa.Column("institution_id", sa.Uuid(), nullable=False),
        sa.Column("recipient_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("action_url", sa.String(512), nullable=True),
        sa.Column("dedup_key", sa.String(160), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivery_status", sa.String(20), nullable=False),
        sa.Column("delivery_attempts", sa.Integer(), nullable=False),
        *_timestamps(),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recipient_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_notifications"),
        sa.UniqueConstraint("institution_id", "recipient_id", "dedup_key", name="uq_notifications_dedup"),
    )
    op.create_index("ix_notifications_institution_id", "notifications", ["institution_id"])
    op.create_index("ix_notifications_recipient_id", "notifications", ["recipient_id"])
    op.create_index("ix_notifications_scheduled_for", "notifications", ["scheduled_for"])

    op.create_table(
        "calendar_events",
        sa.Column("institution_id", sa.Uuid(), nullable=False),
        sa.Column("creator_id", sa.Uuid(), nullable=False),
        sa.Column("course_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_published", sa.Boolean(), nullable=False),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["creator_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_calendar_events"),
    )
    op.create_index("ix_calendar_events_institution_id", "calendar_events", ["institution_id"])
    op.create_index("ix_calendar_events_creator_id", "calendar_events", ["creator_id"])
    op.create_index("ix_calendar_events_course_id", "calendar_events", ["course_id"])
    op.create_index("ix_calendar_events_starts_at", "calendar_events", ["starts_at"])

    op.create_table(
        "questions",
        sa.Column("institution_id", sa.Uuid(), nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=False),
        sa.Column("course_id", sa.Uuid(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("question_type", sa.String(40), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("options", sa.JSON(), nullable=True),
        sa.Column("correct_answer", sa.JSON(), nullable=True),
        sa.Column("points", sa.Float(), nullable=False),
        sa.Column("learning_objective", sa.String(200), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        *_timestamps(),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_questions"),
    )
    op.create_index("ix_questions_institution_id", "questions", ["institution_id"])
    op.create_index("ix_questions_author_id", "questions", ["author_id"])
    op.create_index("ix_questions_course_id", "questions", ["course_id"])

    op.create_table(
        "quizzes",
        sa.Column("institution_id", sa.Uuid(), nullable=False),
        sa.Column("course_id", sa.Uuid(), nullable=False),
        sa.Column("creator_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("randomize_questions", sa.Boolean(), nullable=False),
        sa.Column("attempts_allowed", sa.Integer(), nullable=False),
        *_timestamps(),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["creator_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_quizzes"),
    )
    op.create_index("ix_quizzes_institution_id", "quizzes", ["institution_id"])
    op.create_index("ix_quizzes_course_id", "quizzes", ["course_id"])
    op.create_index("ix_quizzes_creator_id", "quizzes", ["creator_id"])

    op.create_table(
        "quiz_questions",
        sa.Column("quiz_id", sa.Uuid(), nullable=False),
        sa.Column("question_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("points", sa.Float(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["quiz_id"], ["quizzes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_quiz_questions"),
        sa.UniqueConstraint("quiz_id", "question_id", name="uq_quiz_questions_question"),
    )
    op.create_index("ix_quiz_questions_quiz_id", "quiz_questions", ["quiz_id"])
    op.create_index("ix_quiz_questions_question_id", "quiz_questions", ["question_id"])

    op.create_table(
        "quiz_attempts",
        sa.Column("institution_id", sa.Uuid(), nullable=False),
        sa.Column("quiz_id", sa.Uuid(), nullable=False),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("total_points", sa.Float(), nullable=True),
        sa.Column("submission_key", sa.String(100), nullable=True),
        *_timestamps(),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["quiz_id"], ["quizzes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_quiz_attempts"),
        sa.UniqueConstraint("quiz_id", "student_id", "attempt_number", name="uq_quiz_attempt_number"),
        sa.UniqueConstraint("submission_key", name="uq_quiz_attempts_submission_key"),
    )
    op.create_index("ix_quiz_attempts_institution_id", "quiz_attempts", ["institution_id"])
    op.create_index("ix_quiz_attempts_quiz_id", "quiz_attempts", ["quiz_id"])
    op.create_index("ix_quiz_attempts_student_id", "quiz_attempts", ["student_id"])

    op.create_table(
        "quiz_attempt_answers",
        sa.Column("attempt_id", sa.Uuid(), nullable=False),
        sa.Column("question_id", sa.Uuid(), nullable=False),
        sa.Column("answer", sa.JSON(), nullable=True),
        sa.Column("awarded_points", sa.Float(), nullable=False),
        sa.Column("graded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("graded_by", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["attempt_id"], ["quiz_attempts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["graded_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_quiz_attempt_answers"),
        sa.UniqueConstraint("attempt_id", "question_id", name="uq_attempt_answers_question"),
    )
    op.create_index("ix_quiz_attempt_answers_attempt_id", "quiz_attempt_answers", ["attempt_id"])
    op.create_index("ix_quiz_attempt_answers_question_id", "quiz_attempt_answers", ["question_id"])

    op.create_table(
        "assignments",
        sa.Column("institution_id", sa.Uuid(), nullable=False),
        sa.Column("course_id", sa.Uuid(), nullable=False),
        sa.Column("creator_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("max_score", sa.Float(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        *_timestamps(),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["creator_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_assignments"),
    )
    op.create_index("ix_assignments_institution_id", "assignments", ["institution_id"])
    op.create_index("ix_assignments_course_id", "assignments", ["course_id"])
    op.create_index("ix_assignments_creator_id", "assignments", ["creator_id"])

    op.create_table(
        "assignment_submissions",
        sa.Column("institution_id", sa.Uuid(), nullable=False),
        sa.Column("assignment_id", sa.Uuid(), nullable=False),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("answer_text", sa.Text(), nullable=False),
        sa.Column("object_key", sa.String(512), nullable=True),
        sa.Column("idempotency_key", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("ai_score", sa.Float(), nullable=True),
        sa.Column("final_score", sa.Float(), nullable=True),
        sa.Column("ai_feedback", sa.Text(), nullable=True),
        sa.Column("teacher_feedback", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("graded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("graded_by", sa.Uuid(), nullable=True),
        *_timestamps(),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assignment_id"], ["assignments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["graded_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_assignment_submissions"),
        sa.UniqueConstraint("assignment_id", "student_id", "version", name="uq_assignment_submission_version"),
        sa.UniqueConstraint("assignment_id", "student_id", "idempotency_key", name="uq_assignment_submission_idempotency"),
    )
    op.create_index("ix_assignment_submissions_institution_id", "assignment_submissions", ["institution_id"])
    op.create_index("ix_assignment_submissions_assignment_id", "assignment_submissions", ["assignment_id"])
    op.create_index("ix_assignment_submissions_student_id", "assignment_submissions", ["student_id"])

    op.create_table(
        "certificates",
        sa.Column("institution_id", sa.Uuid(), nullable=False),
        sa.Column("course_id", sa.Uuid(), nullable=False),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("enrollment_id", sa.Uuid(), nullable=False),
        sa.Column("verification_token", sa.String(96), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["enrollment_id"], ["enrollments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_certificates"),
        sa.UniqueConstraint("course_id", "student_id", name="uq_certificate_course_student"),
        sa.UniqueConstraint("verification_token", name="uq_certificates_verification_token"),
    )
    op.create_index("ix_certificates_institution_id", "certificates", ["institution_id"])
    op.create_index("ix_certificates_course_id", "certificates", ["course_id"])
    op.create_index("ix_certificates_student_id", "certificates", ["student_id"])
    op.create_index("ix_certificates_verification_token", "certificates", ["verification_token"])

    op.create_table(
        "ai_invocations",
        sa.Column("institution_id", sa.Uuid(), nullable=True),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("task", sa.String(60), nullable=False),
        sa.Column("provider", sa.String(60), nullable=False),
        sa.Column("model", sa.String(120), nullable=False),
        sa.Column("prompt_version", sa.String(40), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("estimated_cost", sa.Float(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("error_code", sa.String(80), nullable=True),
        sa.Column("output_json", sa.JSON(), nullable=True),
        sa.Column("approved_by", sa.Uuid(), nullable=True),
        *_timestamps(),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_ai_invocations"),
    )
    op.create_index("ix_ai_invocations_institution_id", "ai_invocations", ["institution_id"])
    op.create_index("ix_ai_invocations_actor_id", "ai_invocations", ["actor_id"])
    op.create_index("ix_ai_invocations_task", "ai_invocations", ["task"])


def downgrade() -> None:
    for index_name, table_name in (
        ("ix_ai_invocations_task", "ai_invocations"),
        ("ix_ai_invocations_actor_id", "ai_invocations"),
        ("ix_ai_invocations_institution_id", "ai_invocations"),
    ):
        op.drop_index(index_name, table_name=table_name)
    op.drop_table("ai_invocations")
    for index_name, table_name in (
        ("ix_certificates_verification_token", "certificates"),
        ("ix_certificates_student_id", "certificates"),
        ("ix_certificates_course_id", "certificates"),
        ("ix_certificates_institution_id", "certificates"),
    ):
        op.drop_index(index_name, table_name=table_name)
    op.drop_table("certificates")
    for index_name, table_name in (
        ("ix_assignment_submissions_student_id", "assignment_submissions"),
        ("ix_assignment_submissions_assignment_id", "assignment_submissions"),
        ("ix_assignment_submissions_institution_id", "assignment_submissions"),
    ):
        op.drop_index(index_name, table_name=table_name)
    op.drop_table("assignment_submissions")
    for index_name, table_name in (
        ("ix_assignments_creator_id", "assignments"),
        ("ix_assignments_course_id", "assignments"),
        ("ix_assignments_institution_id", "assignments"),
    ):
        op.drop_index(index_name, table_name=table_name)
    op.drop_table("assignments")
    for index_name, table_name in (
        ("ix_quiz_attempt_answers_question_id", "quiz_attempt_answers"),
        ("ix_quiz_attempt_answers_attempt_id", "quiz_attempt_answers"),
    ):
        op.drop_index(index_name, table_name=table_name)
    op.drop_table("quiz_attempt_answers")
    for index_name, table_name in (
        ("ix_quiz_attempts_student_id", "quiz_attempts"),
        ("ix_quiz_attempts_quiz_id", "quiz_attempts"),
        ("ix_quiz_attempts_institution_id", "quiz_attempts"),
    ):
        op.drop_index(index_name, table_name=table_name)
    op.drop_table("quiz_attempts")
    for index_name, table_name in (
        ("ix_quiz_questions_question_id", "quiz_questions"),
        ("ix_quiz_questions_quiz_id", "quiz_questions"),
    ):
        op.drop_index(index_name, table_name=table_name)
    op.drop_table("quiz_questions")
    for index_name, table_name in (
        ("ix_quizzes_creator_id", "quizzes"),
        ("ix_quizzes_course_id", "quizzes"),
        ("ix_quizzes_institution_id", "quizzes"),
    ):
        op.drop_index(index_name, table_name=table_name)
    op.drop_table("quizzes")
    for index_name, table_name in (
        ("ix_questions_course_id", "questions"),
        ("ix_questions_author_id", "questions"),
        ("ix_questions_institution_id", "questions"),
    ):
        op.drop_index(index_name, table_name=table_name)
    op.drop_table("questions")
    for index_name, table_name in (
        ("ix_calendar_events_starts_at", "calendar_events"),
        ("ix_calendar_events_course_id", "calendar_events"),
        ("ix_calendar_events_creator_id", "calendar_events"),
        ("ix_calendar_events_institution_id", "calendar_events"),
    ):
        op.drop_index(index_name, table_name=table_name)
    op.drop_table("calendar_events")
    for index_name, table_name in (
        ("ix_notifications_scheduled_for", "notifications"),
        ("ix_notifications_recipient_id", "notifications"),
        ("ix_notifications_institution_id", "notifications"),
    ):
        op.drop_index(index_name, table_name=table_name)
    op.drop_table("notifications")
    for index_name, table_name in (
        ("ix_revoked_sessions_expires_at", "revoked_sessions"),
        ("ix_revoked_sessions_user_id", "revoked_sessions"),
        ("ix_revoked_sessions_jti", "revoked_sessions"),
    ):
        op.drop_index(index_name, table_name=table_name)
    op.drop_table("revoked_sessions")
    for index_name, table_name in (
        ("ix_audit_logs_request_id", "audit_logs"),
        ("ix_audit_logs_action", "audit_logs"),
        ("ix_audit_logs_actor_id", "audit_logs"),
        ("ix_audit_logs_institution_id", "audit_logs"),
    ):
        op.drop_index(index_name, table_name=table_name)
    op.drop_table("audit_logs")
