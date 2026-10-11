"""Exercise the actual migration with duplicate null keys on PostgreSQL."""
import importlib.util
from pathlib import Path
import uuid
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text
from .live_helpers import isolated, pg_engine


def test_ledger_migration_preserves_scores_and_scopes_report_uniqueness():
    isolated()
    root = pg_engine()
    schema = 'qa_ledger_migration_' + uuid.uuid4().hex
    scoped = None
    try:
        with root.begin() as db: db.execute(text(f'CREATE SCHEMA {schema}'))
        scoped = create_engine(root.url.update_query_dict({'options': f'-csearch_path={schema}'}))
        with scoped.begin() as db:
            db.execute(text('''CREATE TABLE grades (id uuid PRIMARY KEY, institution_id uuid NOT NULL,
                student_id uuid NOT NULL, course_id uuid, item_type varchar NOT NULL, item_id uuid,
                score float NOT NULL, is_current boolean NOT NULL, updated_at timestamptz NOT NULL)'''))
            db.execute(text('CREATE UNIQUE INDEX ix_grades_current ON grades(student_id,item_type,item_id)'))
            db.execute(text('''CREATE TABLE report_jobs (id uuid PRIMARY KEY, institution_id uuid NOT NULL,
                requested_by uuid NOT NULL, idempotency_key varchar,
                CONSTRAINT uq_legacy_report_key UNIQUE(idempotency_key))'''))
            inst, student, course = [uuid.uuid4() for _ in range(3)]
            for score in (90, 95):
                db.execute(text("""INSERT INTO grades VALUES (:id,:inst,:student,:course,'course',NULL,
                    :score,true, to_timestamp(:score))"""), dict(id=uuid.uuid4(), inst=inst, student=student, course=course, score=score))
            filename = Path('/srv/alembic/versions/e8a0c2d4f6b8_scoped_reports_current_grades.py')
            spec = importlib.util.spec_from_file_location('review_migration', filename)
            module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
            module.op = Operations(MigrationContext.configure(db))
            module.upgrade()
            assert db.execute(text('SELECT score FROM grades ORDER BY score')).scalars().all() == [90, 95]
            assert db.execute(text('SELECT score FROM grades WHERE is_current')).scalars().all() == [95]
            for _ in range(2):
                db.execute(text("INSERT INTO report_jobs VALUES (:id,:inst,:user,'same-key')"),
                           dict(id=uuid.uuid4(), inst=inst, user=uuid.uuid4()))
            assert db.execute(text('SELECT count(*) FROM report_jobs')).scalar() == 2
    finally:
        if scoped is not None: scoped.dispose()
        with root.begin() as db: db.execute(text(f'DROP SCHEMA {schema} CASCADE'))
        root.dispose()
