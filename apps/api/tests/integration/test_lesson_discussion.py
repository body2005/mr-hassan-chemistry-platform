"""Actual HTTPS/cookie/CSRF/PG entitlement and persisted discussion boundary."""
from datetime import datetime, timezone
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.course import Course, CourseModule, CourseStatus, Enrollment, Lesson, LessonKind
from app.models.payment import EntitlementType, StudentEntitlement
from app.models.platform import LessonComment
from app.models.user import User, UserRole
from .live_helpers import BASE, clear_auth, pg_engine, session


def test_real_discussion_entitlement_revocation_and_saved_reply_ids():
    clear_auth()
    engine = pg_engine()
    password = 'Qa-synthetic-discussion-2026!'
    try:
        with session() as bootstrap:
            me = bootstrap.get(BASE + '/auth/me', timeout=15)
            assert me.status_code == 200
            institution = uuid.UUID(me.json()['institution_id'])
        with Session(engine) as db:
            users = []
            for role in (UserRole.TEACHER, UserRole.TEACHER, UserRole.STUDENT):
                key = uuid.uuid4().hex
                user = User(institution_id=institution, username='discussion-' + key,
                            email=key + '@qa.example.com', role=role, display_name='Synthetic discussion',
                            password_hash=hash_password(password))
                db.add(user)
                users.append(user)
            db.flush()
            owner, stranger, learner = users
            course = Course(institution_id=institution, teacher_id=owner.id,
                            code='QA-DISC-' + uuid.uuid4().hex[:12], title='Synthetic private discussion',
                            status=CourseStatus.PUBLISHED)
            db.add(course)
            db.flush()
            module = CourseModule(course_id=course.id, title='Discussion', position=1)
            db.add(module)
            db.flush()
            lesson = Lesson(module_id=module.id, title='Private paid lesson', kind=LessonKind.VIDEO,
                            position=1, price_egp=25)
            db.add(lesson)
            db.flush()
            db.add(Enrollment(course_id=course.id, student_id=learner.id))
            db.commit()
            emails = [user.email for user in users]
            lesson_id, learner_id = lesson.id, learner.id
        path = f'{BASE}/lessons/{lesson_id}/comments'
        with session(emails[0], password) as teacher:
            saved = teacher.post(path, json={'body': 'Persisted private question'}, timeout=15)
            assert saved.status_code == 201
            parent_id = saved.json()['id']
            uuid.UUID(parent_id)
            for body in (123, ['text']):
                assert teacher.post(path, json={'body': body}, timeout=15).status_code == 422
            assert teacher.post(path, json={'body': 'Valid', 'parent_id': 'invalid-uuid'}, timeout=15).status_code == 422
            # Cookie-authenticated unsafe request STILL requires real CSRF.
            headers = dict(teacher.headers)
            teacher.headers.pop('X-CSRF-Token')
            try:
                assert teacher.post(path, json={'body': 'Missing CSRF'}, timeout=15).status_code == 403
            finally:
                teacher.headers.update(headers)
        with session(emails[1], password) as colleague:
            assert colleague.get(path, timeout=15).status_code == 403
            assert colleague.post(path, json={'body': 'Unauthorized'}, timeout=15).status_code == 403
        with session(emails[2], password) as student:
            assert student.get(path, timeout=15).status_code == 403
            assert student.post(path, json={'body': 'Unpaid'}, timeout=15).status_code == 403
            with Session(engine) as db:
                entitlement = StudentEntitlement(institution_id=institution, student_id=learner_id,
                                                entitlement_type=EntitlementType.LESSON,
                                                resource_id=lesson_id, starts_at=datetime.now(timezone.utc))
                db.add(entitlement)
                db.commit()
                entitlement_id = entitlement.id
            reply = student.post(path, json={'body': 'Persisted authorized reply', 'parent_id': parent_id}, timeout=15)
            assert reply.status_code == 201
            reply_id = reply.json()['id']
            tree = student.get(path, timeout=15)
            assert tree.status_code == 200
            assert tree.json()['comments'][0]['id'] == parent_id
            assert tree.json()['comments'][0]['replies'][0]['id'] == reply_id
            assert student.post(path, json={'body': 'Invisible grandchild', 'parent_id': reply_id}, timeout=15).status_code == 422
            with Session(engine) as db:
                db.get(StudentEntitlement, entitlement_id).revoked_at = datetime.now(timezone.utc)
                db.commit()
            assert student.get(path, timeout=15).status_code == 403
            assert student.post(path, json={'body': 'Revoked'}, timeout=15).status_code == 403
        with Session(engine) as db:
            assert db.scalar(select(func.count(LessonComment.id)).where(LessonComment.lesson_id == lesson_id)) == 2
            assert db.get(LessonComment, uuid.UUID(reply_id)).parent_id == uuid.UUID(parent_id)
    finally:
        engine.dispose()
