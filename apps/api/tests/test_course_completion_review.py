"""Course progress is the current student's real submissions, not starts."""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.course import Enrollment
from app.models.platform import (Assignment, AssignmentStatus, AssignmentSubmission,
    AttemptStatus, Quiz, QuizAttempt, QuizStatus)
from app.models.user import UserRole
from test_security_and_tenancy import make_institution, make_user, make_course, login


def domain(db):
    inst = make_institution(db, 'completion')
    teacher = make_user(db, inst.id, UserRole.TEACHER, 'owner')
    student = make_user(db, inst.id, UserRole.STUDENT, 'student')
    other = make_user(db, inst.id, UserRole.STUDENT, 'other')
    course = make_course(db, inst, teacher)
    db.add(Enrollment(course_id=course.id, student_id=student.id))
    db.commit()
    return inst, teacher, student, other, course


@pytest.mark.parametrize('state,practice,expected', [
    (AttemptStatus.IN_PROGRESS, False, False),
    (AttemptStatus.EXPIRED, False, False),
    (AttemptStatus.SUBMITTED, True, False),
    (AttemptStatus.SUBMITTED, False, True),
])
def test_quiz_completion_requires_own_official_submission(db, state, practice, expected):
    inst, teacher, student, other, course = domain(db)
    quiz = Quiz(institution_id=inst.id, course_id=course.id, creator_id=teacher.id,
                title='Completion quiz', status=QuizStatus.PUBLISHED)
    db.add(quiz); db.flush()
    now = datetime.now(timezone.utc)
    db.add_all([
        QuizAttempt(institution_id=inst.id, quiz_id=quiz.id, student_id=student.id,
            attempt_number=1, started_at=now, status=state, is_practice=practice,
            submitted_at=now if state == AttemptStatus.SUBMITTED else None),
        QuizAttempt(institution_id=inst.id, quiz_id=quiz.id, student_id=other.id,
            attempt_number=1, started_at=now, status=AttemptStatus.SUBMITTED, submitted_at=now),
    ])
    db.commit()
    client = login(TestClient(app), student, inst.slug)
    response = client.get(f'/api/v1/courses/{course.id}/assessments')
    assert response.status_code == 200
    assert response.json()['quizzes'][0].get('completed') is expected
    # Consumed-attempt policy is separate and must not be weakened.
    assert response.json()['quizzes'][0]['attempts_used'] == (0 if practice else 1)


def test_assignment_completion_is_own_submission_and_never_another_course(db):
    inst, teacher, student, other, course = domain(db)
    foreign_course = make_course(db, inst, teacher)
    assignments = [Assignment(institution_id=inst.id, course_id=course.id, creator_id=teacher.id,
        title=f'Completion homework{index}', prompt='Explain', status=AssignmentStatus.PUBLISHED) for index in range(2)]
    unrelated = Assignment(institution_id=inst.id, course_id=foreign_course.id, creator_id=teacher.id,
        title='Unrelated', prompt='Explain', status=AssignmentStatus.PUBLISHED)
    db.add_all([*assignments, unrelated]); db.flush()
    now = datetime.now(timezone.utc)
    for assignment, learner, version in [(assignments[0], student, 1), (assignments[0], student, 2),
                                          (assignments[1], other, 1), (unrelated, student, 1)]:
        db.add(AssignmentSubmission(institution_id=inst.id, assignment_id=assignment.id,
            student_id=learner.id, version=version, answer_text='Local synthetic solution',
            idempotency_key=f'{assignment.id}-{learner.id}-{version}', submitted_at=now))
    db.commit()
    client = login(TestClient(app), student, inst.slug)
    response = client.get(f'/api/v1/courses/{course.id}/assessments')
    assert response.status_code == 200
    result = {item['id']: item.get('completed') for item in response.json()['assignments']}
    assert result == {str(assignments[0].id): True, str(assignments[1].id): False}
