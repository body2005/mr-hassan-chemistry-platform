"""Two isolated PostgreSQL schemas: fresh head and upgrade from review head."""
import os
import uuid
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text


def main():
    config = Config("alembic.ini")
    heads = ScriptDirectory.from_config(config).get_heads()
    assert len(heads) == 1, f"Expected one migration head, found {len(heads)}"
    engine = create_engine(os.environ["DATABASE_URL"])
    for start in (None, "e8a0c2d4f6b8"):
        schema = "qa_ci_migration_" + uuid.uuid4().hex
        with engine.begin() as db:
            db.execute(text(f"CREATE SCHEMA {schema}"))
        try:
            url = engine.url.update_query_dict({"options": f"-csearch_path={schema}"}).render_as_string(hide_password=False)
            previous = os.environ["DATABASE_URL"]
            os.environ["DATABASE_URL"] = url
            from app.core.config import get_settings
            get_settings.cache_clear()
            if start:
                command.upgrade(config, start)
            command.upgrade(config, "head")
            scoped = create_engine(url)
            try:
                with scoped.connect() as db:
                    assert db.scalar(text("SELECT version_num FROM alembic_version")) == heads[0]
                    assert db.scalar(text("SELECT COUNT(*) FROM reset_mail_outbox")) == 0
                    assert db.scalar(text("SELECT COUNT(*) FROM reset_request_outbox")) == 0
            finally:
                scoped.dispose()
            print(f"Migration gate passed: {'fresh' if start is None else 'previous head'} -> {heads[0]}")
        finally:
            os.environ["DATABASE_URL"] = previous
            get_settings.cache_clear()
            with engine.begin() as db:
                db.execute(text(f"DROP SCHEMA {schema} CASCADE"))
    engine.dispose()


if __name__ == "__main__":
    main()
