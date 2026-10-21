"""Calendar publication uses one persisted, server-enforced visibility time."""
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi.testclient import TestClient

from app.main import app
from app.models.platform import CalendarEvent
from app.models.user import UserRole
from tests.test_calendar_capacity import payload, post, setup
from tests.test_security_and_tenancy import make_user, login


def test_scheduled_calendar_is_hidden_until_due_before_paging_and_survives_reload(db):
    institution, teacher = setup(db)
    learner = make_user(db, institution.id, UserRole.STUDENT, 'publication-student')
    future = datetime.now(UTC) + timedelta(days=1)
    with TestClient(app) as client:
        login(client, teacher, institution.slug)
        response = post(client, payload(0, publish_at=future.isoformat()))
        assert response.status_code == 201, response.text
        scheduled_id = response.json()['id']
        assert response.json()['publish_at'] is not None
        assert post(client, payload(1)).status_code == 201
        assert post(client, payload(2, is_published=False)).status_code == 201
        assert len(client.get('/api/v1/calendar').json()) == 3
    with TestClient(app) as client:
        login(client, learner, institution.slug)
        rows = client.get('/api/v1/calendar?limit=1&offset=0').json()
        assert len(rows) == 1 and rows[0]['title'] == 'Independent event 1'
        assert client.get('/api/v1/calendar?limit=1&offset=1').json() == []
        # Simulate the publication instant passing without changing the event time.
        event = db.get(CalendarEvent, UUID(scheduled_id))
        event.publish_at = datetime.now(UTC) - timedelta(minutes=1)
        db.commit()
        rows = client.get('/api/v1/calendar').json()
        assert len(rows) == 2
        assert any(row['id'] == scheduled_id for row in rows)


def test_edit_can_switch_between_scheduled_immediate_and_private(db):
    institution, teacher = setup(db)
    learner = make_user(db, institution.id, UserRole.STUDENT, 'publication-edit-student')
    with TestClient(app) as client:
        login(client, teacher, institution.slug)
        body = payload(0, publish_at=(datetime.now(UTC) + timedelta(days=1)).isoformat())
        event = post(client, body).json()
        headers = {'X-CSRF-Token': client.cookies.get('matgar_csrf')}
        for published in (True, False):
            body.update(publish_at=None, is_published=published)
            response = client.put(f"/api/v1/calendar/{event['id']}", json=body, headers=headers)
            assert response.status_code == 200, response.text
            assert response.json()['publish_at'] is None
            with TestClient(app) as student_client:
                login(student_client, learner, institution.slug)
                assert len(student_client.get('/api/v1/calendar').json()) == int(published)


def test_invalid_or_past_calendar_publication_is_rejected_without_saving(db):
    institution, teacher = setup(db)
    with TestClient(app) as client:
        login(client, teacher, institution.slug)
        for timestamp in ('2035-05-13T10:00:00', (datetime.now(UTC) - timedelta(days=1)).isoformat()):
            response = post(client, payload(0, publish_at=timestamp))
            assert response.status_code == 422, response.text
        assert client.get('/api/v1/calendar').json() == []


def test_publication_migration_preserves_legacy_manual_schedules_and_reverses():
    import importlib.util
    import json
    from pathlib import Path
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    import sqlalchemy as sa

    spec = importlib.util.spec_from_file_location('calendar_migration', Path(__file__).resolve().parents[1]
        / 'alembic/versions/g9d1e3f5a7b9_calendar_publication.py')
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = sa.create_engine('sqlite:///:memory:')
    with engine.begin() as connection:
        metadata = sa.MetaData()
        table = sa.Table('calendar_events', metadata, sa.Column('id', sa.Uuid(), primary_key=True),
            sa.Column('description', sa.Text()), sa.Column('request_key', sa.String()))
        metadata.create_all(connection)
        for ordinal, (key, description) in enumerate([
            ('evt_manual', json.dumps({'publishStartDate': '2035-05-13', 'publishStartTime': '٠٦:٣٠ م'})),
            ('evt_assessment_quiz_x', json.dumps({'publishStartDate': '2035-05-13', 'publishStartTime': '18:30'})),
            ('lesson-release:x', 'موعد إتاحة الدرس'), (None, 'legacy plain text'),
        ], start=1):
            connection.execute(table.insert().values(id=UUID(int=ordinal), request_key=key, description=description))
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            reflected = sa.Table('calendar_events', sa.MetaData(), autoload_with=connection)
            rows = connection.execute(sa.select(reflected).order_by(reflected.c.id)).all()
            assert rows[0].publish_at == datetime(2035, 5, 13, 15, 30)
            assert all(row.publish_at is None for row in rows[1:])
            migration.downgrade()
            assert 'publish_at' not in {column['name'] for column in sa.inspect(connection).get_columns('calendar_events')}
    engine.dispose()
