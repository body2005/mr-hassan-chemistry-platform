"""Reset user activity while preserving accounts and learning content.

This intentionally keeps users, courses, modules, lessons, uploaded knowledge
sources, materials, video assets and transcripts.  It removes the records that
make an account look used: enrolments, viewing history, attempts, grades,
payments/entitlements, notifications, AI interactions, generated assessments
and teacher-created calendar entries.

Run a dry run first.  Destructive execution always requires both flags:

    python scripts/reset_account_activity.py --all-institutions --confirm
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import delete, func, inspect, select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import SessionLocal  # noqa: E402
from app.models.base import Base  # noqa: E402
# Import every model module so Base.metadata contains the mapped tables when the
# script runs directly (the application startup imports them implicitly).
import app.models.course  # noqa: E402,F401
import app.models.extended  # noqa: E402,F401
import app.models.knowledge_center  # noqa: E402,F401
import app.models.payment  # noqa: E402,F401
import app.models.platform  # noqa: E402,F401
import app.models.progress  # noqa: E402,F401
import app.models.transcript  # noqa: E402,F401
import app.models.user  # noqa: E402,F401


# Children must be removed before their parents.  Do not add learning-content
# tables here: users, courses, course_modules, lessons, knowledge_sources,
# knowledge_documents, lesson_assets, transcripts and transcription_jobs stay.
ACTIVITY_TABLES = (
    "notification_recipient_states",
    "notification_deliveries",
    "quiz_attempt_answers",
    "quiz_attempts",
    "assignment_submissions",
    "assignment_attempts",
    "certificates",
    "grades",
    "student_mastery",
    "interventions",
    "risk_assessments",
    "video_events",
    "lesson_progress",
    "knowledge_conversation_turns",
    "knowledge_query_events",
    "ai_refusal_logs",
    "ai_runs",
    "ai_jobs",
    "ai_invocations",
    "report_jobs",
    "idempotency_keys",
    "password_reset_tokens",
    "revoked_sessions",
    "student_entitlements",
    "payment_orders",
    "notifications",
    "calendar_events",
    "quiz_questions",
    "quizzes",
    "rubric_criteria",
    "rubrics",
    "question_versions",
    "questions",
    "question_banks",
    "assignments",
    "enrollments",
    "audit_logs",
)


def activity_counts(table_names: tuple[str, ...]) -> list[tuple[str, int]]:
    """Return counts only for tables present in the current migration head."""
    with SessionLocal() as db:
        present = set(inspect(db.get_bind()).get_table_names())
        result: list[tuple[str, int]] = []
        for name in table_names:
            table = Base.metadata.tables.get(name)
            if table is not None and name in present:
                result.append((name, db.scalar(select(func.count()).select_from(table)) or 0))
        return result


def reset_activity(table_names: tuple[str, ...]) -> dict[str, int]:
    """Delete only activity tables in one transaction and return row counts."""
    with SessionLocal() as db:
        present = set(inspect(db.get_bind()).get_table_names())
        deleted: dict[str, int] = {}
        try:
            for name in table_names:
                table = Base.metadata.tables.get(name)
                if table is None or name not in present:
                    continue
                deleted[name] = db.execute(delete(table)).rowcount or 0
            db.commit()
        except Exception:
            db.rollback()
            raise
        return deleted


def main() -> int:
    parser = argparse.ArgumentParser(description="Reset all account activity but preserve learning content.")
    parser.add_argument("--all-institutions", action="store_true", help="Required: applies to every account.")
    parser.add_argument("--confirm", action="store_true", help="Required: performs deletion instead of a dry run.")
    parser.add_argument(
        "--tables",
        nargs="+",
        choices=ACTIVITY_TABLES,
        help="Optional, explicit activity tables to reset. Defaults to all listed activity tables.",
    )
    args = parser.parse_args()

    if not args.all_institutions:
        parser.error("Pass --all-institutions; this reset has no implicit scope.")

    selected_tables = tuple(args.tables) if args.tables else ACTIVITY_TABLES
    counts = activity_counts(selected_tables)
    total = sum(count for _, count in counts)
    print(f"Activity rows found: {total}")
    for name, count in counts:
        if count:
            print(f"  {name}: {count}")

    if not args.confirm:
        print("Dry run only. Re-run with --all-institutions --confirm to delete these activity rows.")
        return 0

    deleted = reset_activity(selected_tables)
    print(f"Deleted activity rows: {sum(deleted.values())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
