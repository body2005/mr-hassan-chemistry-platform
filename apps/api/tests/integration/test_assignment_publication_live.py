"""Real PostgreSQL regression for blank and historically invalid homework."""
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.platform import Assignment, AssignmentStatus
from .live_helpers import BASE, clear_auth, lesson, pg_engine, session
from .test_audit_concurrency import overlap


def test_blank_homework_rejected_and_concurrent_legacy_publish_is_atomic():
    clear_auth()  # Read-only wait for real auth limits; never clears counters.
    engine = pg_engine()
    try:
        with session() as teacher:
            course, item = lesson(teacher)
            title = 'QA assignment content ' + uuid.uuid4().hex
            payload = {'course_id': course['id'], 'lesson_id': item['id'],
                       'title': title, 'prompt': '  ', 'max_score': 5}
            rejected = teacher.post(BASE + '/assignments', json=payload, timeout=15)
            assert rejected.status_code == 422
            with Session(engine) as db:
                assert db.scalar(select(func.count()).select_from(Assignment).where(
                    Assignment.course_id == uuid.UUID(course['id']),
                    Assignment.title == title)) == 0

            payload['prompt'] = '  اشرح قانون حفظ الكتلة  '
            created = teacher.post(BASE + '/assignments', json=payload, timeout=15)
            assert created.status_code == 201
            assignment_id = uuid.UUID(created.json()['id'])
            assert created.json()['prompt'] == payload['prompt'].strip()
            # Corrupt ONLY this test's new synthetic row to reproduce a
            # historical draft. No existing user content is modified.
            with Session(engine) as db:
                row = db.get(Assignment, assignment_id)
                assert row.course_id == uuid.UUID(course['id']) and row.title == title
                assert row.status == AssignmentStatus.DRAFT
                row.prompt = '  '
                db.commit()

            responses = overlap(teacher, [
                ('POST', f'/assignments/{assignment_id}/publish', None),
            ] * 2)
            try:
                assert [response.status_code for _, response in responses] == [400, 400]
                with Session(engine) as db:
                    row = db.get(Assignment, assignment_id)
                    assert row.status == AssignmentStatus.DRAFT
                    assert row.prompt == '  '
                    row.prompt = payload['prompt'].strip()
                    db.commit()
                published = teacher.post(
                    f'{BASE}/assignments/{assignment_id}/publish', timeout=15)
                assert published.status_code == 200
                assert published.json()['prompt'] == payload['prompt'].strip()
                with Session(engine) as db:
                    assert db.get(Assignment, assignment_id).status == AssignmentStatus.PUBLISHED
            finally:
                for client, _ in responses:
                    client.close()
    finally:
        engine.dispose()
