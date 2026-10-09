import pytest
from sqlalchemy import func, select

from app.models.course import Course, Enrollment
from app.models.user import UserRole
from scripts import seed_qa_enrollments
from test_security_and_tenancy import make_institution, make_user


def test_large_catalog_fixture_is_idempotent_and_keeps_original_accounts(db):
    inst = make_institution(db, 'demo')
    teacher = make_user(db, inst.id, UserRole.TEACHER, 'teacher')
    student = make_user(db, inst.id, UserRole.STUDENT, 'student03')
    teacher.email = 'teacher@demo.com'
    student.email = 'student03@demo.com'
    db.commit()
    first = seed_qa_enrollments.seed(db)
    assert first == {'created': 152, 'published_active_enrollments': 152, 'minimum': 152}
    assert seed_qa_enrollments.seed(db)['created'] == 0
    assert db.scalar(select(func.count(Course.id))) == 152
    assert db.scalar(select(func.count(Enrollment.id))) == 152
    assert student.email == 'student03@demo.com' and teacher.email == 'teacher@demo.com'


@pytest.mark.parametrize('project,enabled', [('chemistryprodlocal', 'true'), ('external', 'true'), ('chemistryaudit2', 'false')])
def test_large_catalog_fixture_refuses_noncurrent_or_nonisolated_projects(monkeypatch, project, enabled):
    monkeypatch.setenv('QA_PROJECT', project)
    monkeypatch.setenv('QA_ISOLATED', enabled)
    monkeypatch.setattr(seed_qa_enrollments, 'SessionLocal', lambda: pytest.fail('Must reject before opening a database'))
    with pytest.raises(RuntimeError, match='explicit local chemistryaudit2'):
        seed_qa_enrollments.main()
