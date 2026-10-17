"""A mixed free/paid scope opens only when every paid lesson is owned."""
from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models.course import Lesson, Enrollment
from app.models.platform import Quiz, Assignment, QuizLessonLink, AssignmentLessonLink, Question, QuizQuestion
from app.models.payment import EntitlementType
from tests.test_course_metadata_authorization import domain
from tests.test_course_purchase_scope import grant
from tests.test_security_and_tenancy import login, csrf_headers


def add_question(db, inst, teacher, quiz):
    question = Question(institution_id=inst.id, author_id=teacher.id, prompt='PRIVATE EXAM QUESTION',
        question_type='mcq', options=['A', 'B'], correct_answer='A')
    db.add(question); db.flush()
    db.add(QuizQuestion(quiz_id=quiz.id, question_id=question.id, position=1, points=1))


@pytest.mark.parametrize('scope', ['lessons', 'unit'])
@pytest.mark.parametrize('purchase', ['none', 'one', 'all', 'expired', 'revoked', 'future', 'other_student'])
def test_mixed_quiz_and_homework_require_every_paid_lesson(db, scope, purchase):
    inst, teacher, student, other, course, free, paid, *_ = domain(db)
    second = Lesson(course_id=course.id, module_id=paid.module_id, title='Second paid lesson',
        kind='article', content='Private second lesson', price_egp=75, position=3)
    db.add(second); db.flush()
    args = {'module_id': paid.module_id} if scope == 'unit' else {'lesson_id': free.id}
    quiz = Quiz(institution_id=inst.id, course_id=course.id, creator_id=teacher.id,
        title='Mixed exam', status='published', **args)
    assignment = Assignment(institution_id=inst.id, course_id=course.id, creator_id=teacher.id,
        title='Mixed homework', prompt='PRIVATE QUESTIONS', status='published', **args)
    db.add_all([quiz, assignment]); db.flush()
    add_question(db, inst, teacher, quiz)
    if scope == 'lessons':
        for lesson in (paid, second):
            db.add(QuizLessonLink(assessment_id=quiz.id, lesson_id=lesson.id))
            db.add(AssignmentLessonLink(assessment_id=assignment.id, lesson_id=lesson.id))
    db.add(Enrollment(course_id=course.id, student_id=student.id)); db.commit()
    if purchase != 'none':
        grant(db, inst, student, paid.id)
    if purchase not in {'none', 'one'}:
        now = datetime.now(timezone.utc)
        changes = {'expired': {'expires_at': now-timedelta(seconds=1)},
            'revoked': {'revoked_at': now}, 'future': {'starts_at': now+timedelta(hours=1)}}.get(purchase, {})
        grant(db, inst, other if purchase == 'other_student' else student, second.id, **changes)
    client = login(TestClient(app), student, inst.slug)
    listing = client.get('/api/v1/courses').json()['items'][0]['catalog_assessments']
    cards = [row for row in listing if row['id'] in {str(quiz.id), str(assignment.id)}]
    assert len(cards) == 2
    assert all(set(row) == {'id', 'kind', 'title', 'lesson_ids', 'requires_purchase'} for row in cards)
    assert all(row['requires_purchase'] is (purchase != 'all') for row in cards)
    private = client.get(f'/api/v1/courses/{course.id}/assessments').json()
    assert any(row['id'] == str(free.id) and row['accessible'] for row in private['lessons'])
    for model, item, key in [('quizzes', quiz, 'quizzes'), ('assignments', assignment, 'assignments')]:
        assert (str(item.id) in {row['id'] for row in private.get(key, [])}) is (purchase == 'all')
        assert client.get(f'/api/v1/{model}/{item.id}/solve').status_code == (200 if purchase == 'all' else 403)
        if purchase != 'all':
            assert client.post(f'/api/v1/{model}/{item.id}/attempts', headers=csrf_headers(client)).status_code == 403
    if purchase != 'all':
        assert client.get(f'/api/v1/quizzes/{quiz.id}/result').status_code == 403


def test_preview_hides_future_drafts_and_private_content_but_allows_free_only_activity(db):
    inst, teacher, student, _, course, free, paid, free_quiz, paid_quiz, assignment = domain(db)
    add_question(db, inst, teacher, free_quiz)
    db.add(Enrollment(course_id=course.id, student_id=student.id)); db.commit()
    client = login(TestClient(app), student, inst.slug)
    sale = client.get('/api/v1/courses').json()['items'][0]
    previews = sale['catalog_assessments']
    assert str(paid_quiz.id) not in {row['id'] for row in previews}  # Future start remains sealed.
    assert any(row['id'] == str(assignment.id) and row['requires_purchase'] for row in previews)
    allowed = client.get(f'/api/v1/courses/{course.id}/assessments')
    assert allowed.status_code == 200
    assert [row['id'] for row in allowed.json()['quizzes']] == [str(free_quiz.id)]
    assert allowed.json()['assignments'] == []
    assert client.get(f'/api/v1/quizzes/{free_quiz.id}/solve').status_code == 200
    assert client.get(f'/api/v1/assignments/{assignment.id}/solve').status_code == 403
    assert 'catalog_assessments' not in TestClient(app).get('/api/v1/courses').json()['items'][0]


def test_unit_preview_does_not_drop_a_hidden_paid_sibling_from_its_scope(db):
    inst, teacher, student, _, course, free, paid, *_ = domain(db)
    paid.publication_status = 'draft'
    quiz = Quiz(institution_id=inst.id, course_id=course.id, creator_id=teacher.id,
        module_id=free.module_id, title='Hidden scope exam', status='published')
    db.add(quiz); db.commit()
    client = login(TestClient(app), student, inst.slug)
    catalog = client.get('/api/v1/courses').json()['items'][0]['catalog_assessments']
    assert str(quiz.id) not in {item['id'] for item in catalog}
    assert client.get(f'/api/v1/quizzes/{quiz.id}/solve').status_code == 403
