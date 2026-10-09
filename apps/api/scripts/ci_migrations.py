"""Two isolated PostgreSQL schemas: fresh head and upgrade from review head."""
import os
import uuid
from datetime import datetime, timezone
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import MetaData, Table, create_engine, select, text


def seed_legacy_evidence(engine):
    """Known synthetic rows under the pre-snapshot schema, not current ORM."""
    metadata = MetaData()
    names = ("institutions", "users", "courses", "questions", "quizzes", "quiz_questions",
             "quiz_attempts", "quiz_attempt_answers")
    tables = {name: Table(name, metadata, autoload_with=engine) for name in names}
    inst, teacher, student, course, question, quiz, link, attempt, answer = [uuid.uuid4() for _ in range(9)]
    now = datetime.now(timezone.utc)
    seeds = [
        ("institutions", dict(id=inst, name="QA legacy migration", slug="qa-legacy")),
        ("users", dict(id=teacher, institution_id=inst, username="teacher", email="teacher@qa.example.test",
            display_name="Synthetic teacher", password_hash="not-a-login-hash", role="teacher", is_active=True)),
        ("users", dict(id=student, institution_id=inst, username="student", email="student@qa.example.test",
            display_name="Synthetic student", password_hash="not-a-login-hash", role="student", is_active=True)),
        ("courses", dict(id=course, institution_id=inst, teacher_id=teacher, code="QA-LEGACY", title="Chemistry",
            status="published", price_egp=0)),
        ("questions", dict(id=question, institution_id=inst, author_id=teacher, course_id=course, version=1,
            question_type="essay", prompt="Original unknown historical prompt", points=1,
            learning_objective="CHEM", is_active=True)),
        ("quizzes", dict(id=quiz, institution_id=inst, course_id=course, creator_id=teacher, title="Legacy exam",
            status="published", version=1, randomize_questions=False, attempts_allowed=1, allow_practice_attempts=True)),
        ("quiz_questions", dict(id=link, quiz_id=quiz, question_id=question, position=1, points=10)),
        ("quiz_attempts", dict(id=attempt, institution_id=inst, quiz_id=quiz, student_id=student, attempt_number=1,
            started_at=now, submitted_at=now, status="submitted", score=5, total_points=10, is_practice=False)),
        ("quiz_attempt_answers", dict(id=answer, attempt_id=attempt, question_id=question, answer="Synthetic legacy answer",
            awarded_points=5, graded_at=now)),
    ]
    saved = []
    with engine.begin() as db:
        for name, values in seeds:
            table = tables[name]
            db.execute(table.insert().values(**values))
            before = dict(db.execute(select(table).where(table.c.id == values["id"])).mappings().one())
            saved.append((name, values["id"], before))
    return saved


def assert_legacy_preserved(engine, saved):
    metadata = MetaData()
    with engine.connect() as db:
        for name, row_id, before in saved:
            table = Table(name, metadata, autoload_with=engine, extend_existing=True)
            after = dict(db.execute(select(table).where(table.c.id == row_id)).mappings().one())
            if name in {"quiz_questions", "quiz_attempts", "quiz_attempt_answers"}:
                assert after.pop("question_snapshot") is None, "Migration invented legacy question evidence"
            assert after == before, f"Migration modified synthetic historical row in {name}"


def main():
    config = Config("alembic.ini")
    heads = ScriptDirectory.from_config(config).get_heads()
    assert len(heads) == 1, f"Expected one migration head, found {len(heads)}"
    engine = create_engine(os.environ["DATABASE_URL"])
    for start in (None, "e8a0c2d4f6b8", "f3e5a7c9b1d3"):
        schema = "qa_ci_migration_" + uuid.uuid4().hex
        with engine.begin() as db:
            db.execute(text(f"CREATE SCHEMA {schema}"))
        try:
            url = engine.url.update_query_dict({"options": f"-csearch_path={schema}"}).render_as_string(hide_password=False)
            previous = os.environ["DATABASE_URL"]
            os.environ["DATABASE_URL"] = url
            from app.core.config import get_settings
            get_settings.cache_clear()
            scoped = create_engine(url)
            try:
                if start:
                    command.upgrade(config, start)
                legacy = seed_legacy_evidence(scoped) if start == "f3e5a7c9b1d3" else None
                command.upgrade(config, "head")
                if legacy:
                    assert_legacy_preserved(scoped, legacy)
                with scoped.connect() as db:
                    assert db.scalar(text("SELECT version_num FROM alembic_version")) == heads[0]
                    assert db.scalar(text("SELECT COUNT(*) FROM reset_mail_outbox")) == 0
                    assert db.scalar(text("SELECT COUNT(*) FROM reset_request_outbox")) == 0
            finally:
                scoped.dispose()
            print(f"Migration gate passed: {start or 'fresh'} -> {heads[0]}; historical rows preserved: {len(legacy or [])}")
        finally:
            os.environ["DATABASE_URL"] = previous
            get_settings.cache_clear()
            with engine.begin() as db:
                db.execute(text(f"DROP SCHEMA {schema} CASCADE"))
    engine.dispose()


if __name__ == "__main__":
    main()
