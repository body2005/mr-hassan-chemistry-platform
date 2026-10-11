"""Cookie-authenticated read isolation with actual PostgreSQL mastery SQL."""
from datetime import datetime, timezone
import uuid
import pytest
from sqlalchemy.orm import Session
from app.core.security import hash_password
from app.models.course import Course, CourseStatus, Enrollment
from app.models.extended import Grade, LearningObjective
from app.models.platform import Question, Quiz, QuizQuestion, QuizStatus, QuizAttempt, QuizAttemptAnswer, AttemptStatus
from app.models.user import User, UserRole
from .live_helpers import BASE, clear_auth, pg_engine, session


@pytest.mark.parametrize('global_fallback', [False, True])
def test_teacher_reads_only_owned_course_evidence_for_shared_student(global_fallback):
    clear_auth(); engine = pg_engine()
    password = 'Qa-review-cookie-only-2026!'
    try:
        with session() as bootstrap:
            institution = uuid.UUID(bootstrap.get(BASE + '/auth/me', timeout=15).json()['institution_id'])
        with Session(engine) as db:
            objective_code = 'shared-' + uuid.uuid4().hex[:12]
            users = []
            for role in (UserRole.TEACHER, UserRole.TEACHER, UserRole.TEACHER, UserRole.STUDENT):
                key = uuid.uuid4().hex
                user = User(institution_id=institution, username='scope-' + key, email=key+'@qa.example.com',
                    role=role, display_name='QA cookie read scope', password_hash=hash_password(password))
                db.add(user); users.append(user)
            db.flush()
            owner, colleague, stranger, student = users
            courses = []
            for teacher, score in ((owner, 1), (colleague, 0)):
                c = Course(institution_id=institution, teacher_id=teacher.id, code='QA-SCOPE-'+uuid.uuid4().hex[:12],
                    title='Synthetic read isolation', status=CourseStatus.PUBLISHED)
                db.add(c); db.flush(); courses.append(c)
                db.add(Enrollment(course_id=c.id, student_id=student.id))
                db.add(Grade(institution_id=institution, course_id=c.id, student_id=student.id,
                    item_type='course', score=score, max_score=1, graded_by=teacher.id))
                db.add(LearningObjective(institution_id=institution,
                    course_id=None if global_fallback and teacher == colleague else c.id,
                    code=objective_code, title=c.code))
                q = Question(institution_id=institution, course_id=c.id, author_id=teacher.id,
                    prompt='Explain conservation of mass', question_type='essay', points=1, learning_objective=objective_code)
                quiz = Quiz(institution_id=institution, course_id=c.id, creator_id=teacher.id, title='QA evidence', status=QuizStatus.PUBLISHED)
                db.add_all([q, quiz]); db.flush()
                from app.services.quiz_snapshot import capture_questions
                link = QuizQuestion(quiz_id=quiz.id, question_id=q.id, points=1, position=1)
                db.add(link); db.flush()
                snapshot = capture_questions(db, quiz, [(link, q)])[0]
                attempt = QuizAttempt(institution_id=institution, quiz_id=quiz.id, student_id=student.id,
                    attempt_number=1, status=AttemptStatus.SUBMITTED, started_at=datetime.now(timezone.utc),
                    submitted_at=datetime.now(timezone.utc), total_points=1, question_snapshot=[snapshot],
                    results_approved_at=datetime.now(timezone.utc), results_approved_by=teacher.id)
                db.add(attempt); db.flush()
                db.add(QuizAttemptAnswer(attempt_id=attempt.id, question_id=q.id, answer='Synthetic',
                    awarded_points=score, graded_at=datetime.now(timezone.utc), question_snapshot=snapshot))
            db.commit()
            ids = [str(c.id) for c in courses]; codes = [c.code for c in courses]
            emails = [u.email for u in users]; student_id = str(student.id)
        for index in (0, 1):
            with session(emails[index], password) as teacher:
                grades = teacher.get(f'{BASE}/grades/students/{student_id}', timeout=15)
                assert grades.status_code == 200
                assert [g['course_id'] for g in grades.json()] == [ids[index]]
                mastery = teacher.get(f'{BASE}/analytics/students/{student_id}/mastery', timeout=15)
                assert mastery.status_code == 200
                assert [(m['title'], m['mastery'], m['evidence_count']) for m in mastery.json()['items']] == [(codes[index], 1-index, 1)]
        with session(emails[2], password) as teacher:
            for path in (f'grades/students/{student_id}', f'analytics/students/{student_id}/mastery'):
                assert teacher.get(BASE+'/'+path, timeout=15).status_code == 404
        with session(emails[3], password) as learner:
            assert len(learner.get(f'{BASE}/grades/students/{student_id}', timeout=15).json()) == 2
            mastery = learner.get(f'{BASE}/analytics/students/{student_id}/mastery', timeout=15)
            assert mastery.status_code == 200
            assert sorted((m['title'], m['mastery'], m['evidence_count']) for m in mastery.json()['items']) == sorted([
                (codes[0], 1, 1), (codes[1], 0, 1)])
    finally:
        engine.dispose()
