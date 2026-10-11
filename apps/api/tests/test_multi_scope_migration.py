import importlib.util
from pathlib import Path
from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text


def test_scope_migration_backfills_legacy_links_and_has_one_head():
    directory = ScriptDirectory.from_config(Config('alembic.ini'))
    assert len(directory.get_heads()) == 1
    assert 'f6b8d0e2a4c6' in {revision.revision for revision in directory.walk_revisions()}
    path = Path('alembic/versions/f6b8d0e2a4c6_multi_assessment_scope.py')
    spec = importlib.util.spec_from_file_location('multi_scope_migration', path)
    migration = importlib.util.module_from_spec(spec); spec.loader.exec_module(migration)
    engine = create_engine('sqlite://')
    with engine.begin() as connection:
        for table in ('lessons', 'course_modules'):
            connection.execute(text(f'CREATE TABLE {table} (id UUID PRIMARY KEY)'))
        for table in ('quizzes', 'assignments'):
            connection.execute(text(f'CREATE TABLE {table} (id UUID PRIMARY KEY, lesson_id UUID, module_id UUID)'))
            connection.execute(text(f"INSERT INTO {table} VALUES ('assessment','lesson','module')"))
            connection.execute(text(f"INSERT INTO {table} VALUES ('unit-only',NULL,'module')"))
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        for kind in ('quiz', 'assignment'):
            for scope in ('lesson', 'module'):
                expected = [('assessment', 'lesson')] if scope == 'lesson' else [('unit-only', 'module')]
                assert connection.execute(text(f'SELECT assessment_id, {scope}_id FROM {kind}_{scope}_links')).all() == expected
        migration.downgrade()
        assert connection.execute(text('SELECT count(*) FROM quizzes')).scalar() == 2
    engine.dispose()
