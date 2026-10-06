"""Independent review regressions on real HTTP + PostgreSQL (no SQLite locks)."""
import uuid
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.security import hash_password
from app.models.course import Enrollment
from app.models.extended import Grade, ReportJob
from app.models.user import User, UserRole
from .live_helpers import BASE, clear_auth, lesson, pg_engine, session
from .test_audit_concurrency import overlap, assessment


@pytest.mark.parametrize('item_type', ['course', 'quiz'])
def test_concurrent_regrades_keep_history_and_one_current(item_type):
    clear_auth()
    engine = pg_engine()
    try:
        with session() as teacher:
            course, item = lesson(teacher)
            quiz_id, _ = assessment(teacher, course, item)
            with Session(engine) as db:
                owner = db.get(User, uuid.UUID(course['teacher_id']))
                student = User(institution_id=owner.institution_id, username='ledger-' + uuid.uuid4().hex,
                    email=uuid.uuid4().hex + '@qa.example.com', display_name='QA ledger student',
                    role=UserRole.STUDENT, password_hash=hash_password('synthetic-only-password'))
                db.add(student); db.flush()
                student_id = student.id
                db.add(Enrollment(course_id=uuid.UUID(course['id']), student_id=student_id)); db.commit()
            payload = dict(student_id=str(student_id), course_id=course['id'], item_type=item_type,
                           item_id=quiz_id if item_type == 'quiz' else None, max_score=100)
            responses = overlap(teacher, [('POST', '/grades', {**payload, 'score': score}) for score in (90, 95, 98)])
            try:
                assert [r.status_code for _, r in responses] == [201] * 3
                with Session(engine) as db:
                    rows = db.scalars(select(Grade).where(Grade.student_id == student_id)).all()
                    assert sorted(r.score for r in rows) == [90, 95, 98]
                    assert len([r for r in rows if r.is_current]) == 1
            finally:
                for client, _ in responses: client.close()
    finally: engine.dispose()


def test_concurrent_report_replays_and_payload_conflict():
    clear_auth(); engine = pg_engine()
    try:
        with session() as teacher:
            key = 'review-' + uuid.uuid4().hex
            payload = dict(report_kind='course', params={'review': key}, format='pdf', idempotency_key=key)
            responses = overlap(teacher, [('POST', '/reports/jobs', payload)] * 3)
            try:
                assert [r.status_code for _, r in responses] == [202] * 3
                assert len({r.json()['id'] for _, r in responses}) == 1
                with Session(engine) as db:
                    rows = db.scalars(select(ReportJob).where(ReportJob.idempotency_key == key)).all()
                    assert len(rows) == 1
                response = teacher.post(BASE + '/reports/jobs', json={**payload, 'format': 'xlsx'}, timeout=15)
                assert response.status_code == 409
            finally:
                for client, _ in responses: client.close()
    finally: engine.dispose()
