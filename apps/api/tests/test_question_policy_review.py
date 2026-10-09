"""Complete-question validation must precede writes, including partial versions."""
import copy
import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.extended import QuestionVersion
from app.models.platform import Question
from app.models.user import UserRole
from app.services import extended_service
from tests.test_security_and_tenancy import make_institution, make_user, login, csrf_headers


VALID = dict(question_type="mcq", prompt="Which option is correct?",
             options=[{"key": "A", "text": "First"}, {"key": "B", "text": "Second"}],
             correct_answer="B", points=10)
INVALID = [
    {"points": 0}, {"points": -1}, {"points": 1001},
    {"question_type": "unknown"}, {"question_type": None}, {"prompt": "  "},
    {"options": []}, {"options": ["Only one"]},
    {"options": [str(i) for i in range(27)]},
    {"options": [{"key": "A", "text": "One"}, {"key": "a", "text": "Two"}]},
    {"options": [{"key": "[", "text": "One"}, {"key": "B", "text": "Two"}]},
    {"options": [{"key": "AB", "text": "One"}, {"key": "B", "text": "Two"}]},
    {"options": ["", "Second"]}, {"correct_answer": "Z"}, {"correct_answer": None},
]


def domain(db):
    institution = make_institution(db, "question-policy")
    teacher = make_user(db, institution.id, UserRole.TEACHER, "owner")
    client = TestClient(app, raise_server_exceptions=False)
    login(client, teacher, institution.slug)
    return teacher, client


@pytest.mark.parametrize("changes", INVALID)
def test_invalid_partial_version_never_mutates_question_or_history(db, changes):
    teacher, client = domain(db)
    created = client.post("/api/v1/questions/versioned", json=VALID, headers=csrf_headers(client))
    assert created.status_code == 201, created.text
    row = db.get(Question, uuid.UUID(created.json()["question_id"]))
    before = {key: copy.deepcopy(getattr(row, key)) for key in VALID}
    response = client.post(f"/api/v1/questions/{row.id}/versions", json=changes,
                           headers=csrf_headers(client))
    assert response.status_code in {400, 422}, response.text
    db.expire_all()
    assert row.version == 1
    assert {key: getattr(row, key) for key in VALID} == before
    assert db.query(QuestionVersion).filter_by(question_id=row.id).count() == 1


@pytest.mark.parametrize("path", ["/api/v1/questions", "/api/v1/questions/versioned"])
@pytest.mark.parametrize("changes", [INVALID[0], INVALID[8], INVALID[9], INVALID[13]])
def test_both_create_paths_validate_complete_content_without_insert(db, path, changes):
    _, client = domain(db)
    response = client.post(path, json={**VALID, **changes}, headers=csrf_headers(client))
    assert response.status_code in {400, 422}, response.text
    assert db.query(Question).count() == 0
    assert db.query(QuestionVersion).count() == 0


def test_full_version_and_metadata_only_revision_keep_history(db):
    _, client = domain(db)
    created = client.post("/api/v1/questions/versioned", json=VALID, headers=csrf_headers(client))
    path = f'/api/v1/questions/{created.json()["question_id"]}/versions'
    full = client.post(path, json={**VALID, "points": 20}, headers=csrf_headers(client))
    assert full.status_code == 201, full.text
    metadata = client.post(path, json={"explanation": "Updated explanation"}, headers=csrf_headers(client))
    assert metadata.status_code == 201, metadata.text
    cleared = client.post(path, json={"explanation": None}, headers=csrf_headers(client))
    assert cleared.status_code == 201, cleared.text
    versions = client.get(path).json()
    assert [row["version"] for row in versions] == [1, 2, 3, 4]
    assert versions[0]["points"] == 10
    assert versions[2]["explanation"] == "Updated explanation"
    assert versions[3]["explanation"] is None


def test_unversioned_question_can_gain_a_valid_revision(db):
    teacher, _ = domain(db)
    question = Question(institution_id=teacher.institution_id, author_id=teacher.id, **VALID)
    db.add(question); db.commit()
    version = extended_service.update_question_versioned(db, teacher, question.id, points=20)
    assert version.version == 2 and version.points == 20
    assert question.points == 20 and question.version == 2
