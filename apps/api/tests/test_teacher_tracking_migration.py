"""Exercise the additive migration against a new disposable database only."""

import importlib.util
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text

from app.models import Base


def test_tracking_migration_preserves_existing_rows_and_declares_data_retention():
    path = Path(__file__).parents[1] / "alembic/versions/g7b9c1d3e5f7_teacher_tracking.py"
    spec = importlib.util.spec_from_file_location("tracking_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite:///:memory:")
    old_tables = [
        table
        for table in Base.metadata.sorted_tables
        if not table.name.startswith("teacher_tracking_")
    ]
    with engine.begin() as connection:
        connection.execute(text("PRAGMA foreign_keys=ON"))
        Base.metadata.create_all(connection, tables=old_tables)
        connection.execute(
            text("INSERT INTO institutions (id, name, slug) VALUES (:id, 'Keep', 'keep')"),
            {"id": "a" * 32},
        )
        before = set(inspect(connection).get_table_names())
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
        assert set(inspect(connection).get_table_names()) == before | {
            "teacher_tracking_columns",
            "teacher_tracking_values",
        }
        assert connection.scalar(text("SELECT name FROM institutions WHERE slug='keep'")) == "Keep"
        scope_fks = inspect(connection).get_foreign_keys("teacher_tracking_values")
        assert any(
            fk["constrained_columns"] == ["column_id", "institution_id", "teacher_id"]
            for fk in scope_fks
        )
        with (
            Operations.context(MigrationContext.configure(connection)),
            pytest.raises(RuntimeError, match="rollback application code only"),
        ):
            migration.downgrade()
        assert "teacher_tracking_values" in inspect(connection).get_table_names()
    engine.dispose()
