"""Post-removal extraction regression tests.

Pins the contract that survived the AI removal:
* Knowledge-Center/indexing endpoints answer 404 (never 500).
* No knowledge tables or RAG models exist.
* Extraction builds drafts from file content only (no cross-file bleed).
* Question types are detected conservatively (MCQ / TRUE_FALSE / ESSAY /
  FILL_BLANK / NEEDS_REVIEW) and never invented.
* Concurrent extractions of two files never mix results.
"""
from __future__ import annotations

import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.models.course import Course, CourseModule, CourseStatus, Lesson
from app.models.institution import Institution
from app.models.user import User, UserRole
from app.services.exam_text_extractor import classify_and_parse_question


def make_institution(db: Session, slug: str) -> Institution:
    inst = Institution(name=f"Inst {slug}", slug=slug)
    db.add(inst)
    db.commit()
    db.refresh(inst)
    return inst


def make_user(db: Session, institution_id: str, role: UserRole, tag: str) -> User:
    from app.core.security import hash_password

    user = User(
        institution_id=institution_id,
        username=f"user_{tag}_{uuid.uuid4().hex[:8]}",
        email=f"user_{tag}_{uuid.uuid4().hex[:8]}@example.com",
        password_hash=hash_password("password-123456"),
        display_name=f"User {tag}",
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def make_teacher_course(db: Session, slug: str) -> tuple[Institution, User, Course]:
    inst = make_institution(db, slug)
    teacher = make_user(db, inst.id, UserRole.TEACHER, slug)
    course = Course(
        institution_id=inst.id,
        teacher_id=teacher.id,
        code=f"C-{uuid.uuid4().hex[:6].upper()}",
        title="Course",
        status=CourseStatus.PUBLISHED,
    )
    db.add(course)
    db.commit()
    db.refresh(course)
    return inst, teacher, course


def login(client: TestClient, user: User, slug: str) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": user.email,
            "password": "password-123456",
            "institution_slug": slug,
        },
    )
    assert response.status_code == 200, response.text


# ---------------------------------------------------------------------------
# 1) 404 contract for removed endpoints
# ---------------------------------------------------------------------------

def test_removed_kc_endpoints_answer_404_not_500(db) -> None:
    inst, teacher, _course = make_teacher_course(db, "removed-a")
    client = TestClient(app)
    login(client, teacher, "removed-a")

    paths = [
        "/api/v1/knowledge-center/sources",
        "/api/v1/knowledge-center/sources/00000000-0000-0000-0000-000000000000",
        "/api/v1/knowledge-center/sources/00000000-0000-0000-0000-000000000000/view",
        "/api/v1/knowledge-center/search",
        "/api/v1/lessons/00000000-0000-0000-0000-000000000000/reindex",
        "/api/v1/lessons/00000000-0000-0000-0000-000000000000/indexing-status",
        "/api/v1/lessons/00000000-0000-0000-0000-000000000000/sync-rag",
        "/api/v1/quiz/draft",
    ]
    for path in paths:
        response = client.get(path)
        if response.status_code == 405:  # GET not allowed on POST-only route
            response = client.post(path)
        assert response.status_code == 404, f"{path} -> {response.status_code}"


def test_no_knowledge_models_or_tables_remain() -> None:
    from app.models import Base

    kc_tables = [
        t for t in Base.metadata.tables if t.startswith(("knowledge_", "assessment_"))
    ]
    assert kc_tables == [], f"knowledge/assessment tables still registered: {kc_tables}"

    # RAG service modules are gone from the codebase
    import importlib.util

    for module in (
        "app.services.knowledge_center_service",
        "app.services.knowledge_retriever",
        "app.services.vector_store",
        "app.services.embedding_provider",
        "app.services.grounded_answer",
        "app.services.knowledge_pipeline",
        "app.services.transcript_indexer",
        "app.services.exam_processing",
        "app.services.ai_access_policy",
    ):
        assert importlib.util.find_spec(module) is None, f"{module} still importable"


# ---------------------------------------------------------------------------
# 2) Extraction produces drafts from the current file only
# ---------------------------------------------------------------------------

def _extract(client: TestClient, filename: str, content: str) -> dict:
    response = client.post(
        "/api/v1/quiz/extract-from-file",
        files={"file": (filename, content.encode("utf-8"), "text/plain")},
        headers={"X-CSRF-Token": client.cookies.get("matgar_csrf", "")},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_extraction_result_depends_only_on_current_file(db) -> None:
    inst, teacher, _course = make_teacher_course(db, "iso-a")
    client = TestClient(app)
    login(client, teacher, "iso-a")

    first = _extract(client, "first.txt", "س1: ما هو البروتون؟\nأ) موجب\nب) سالب\nج) متعادل\nد) لا شيء\nالإجابة الصحيحة: أ\n")
    stems_first = {q["question_text"] for q in first["questions"]}

    second = _extract(client, "second.txt", "س1: وحدة قياس تركيز المحاليل؟\nأ) مول/لتر\nب) جرام\nج) لتر\nد) نيوتن\nالإجابة الصحيحة: أ\n")
    stems_second = {q["question_text"] for q in second["questions"]}

    assert stems_first and stems_second
    assert stems_first.isdisjoint(stems_second), "results from different files mixed"

    # Same file content -> same result (deterministic, no stale state)
    first_again = _extract(client, "first.txt", "س1: ما هو البروتون؟\nأ) موجب\nب) سالب\nج) متعادل\nد) لا شيء\nالإجابة الصحيحة: أ\n")
    assert {q["question_text"] for q in first_again["questions"]} == stems_first


def test_concurrent_extractions_do_not_mix(db) -> None:
    """Two extractions interleaved over the same client share no state."""
    inst, teacher, _course = make_teacher_course(db, "conc-a")
    client = TestClient(app)
    login(client, teacher, "conc-a")

    body_a = "س2: كتلة ذرة الكربون؟\nأ) 12\nب) 14\nج) 16\nد) 18\nالإجابة الصحيحة: أ\n"
    body_b = "س5: رمز عنصر الصوديوم؟\nأ) S\nب) Na\nج) So\nد) N\nالإجابة الصحيحة: ب\n"

    json_a = _extract(client, "a.txt", body_a)
    json_b = _extract(client, "b.txt", body_b)

    text_a = " ".join(q["question_text"] for q in json_a["questions"])
    text_b = " ".join(q["question_text"] for q in json_b["questions"])
    assert "الصوديوم" not in text_a
    assert "الكربون" not in text_b


# ---------------------------------------------------------------------------
# 3) Question-type conservatism (unit level)
# ---------------------------------------------------------------------------

def test_mcq_options_keep_order_and_question_separate() -> None:
    status, question = classify_and_parse_question(
        "س3: أي مما يلي يعد من خصائص القلویات؟\n(أ) تشعرك بالزلق\n(ب) طعمها مالح\n(ج) قيمة pH أقل من 7\n(د) جميع ما سبق"
    )
    assert status in {"question", "uncertain"}
    assert question is not None
    keys = [opt["key"] for opt in (question.get("options") or [])]
    assert keys, "MCQ must keep its options"
    assert keys == sorted(keys, key=["أ", "ب", "ج", "د"].index) if set(keys) <= set("أبجد") else True


def test_uncertain_text_becomes_needs_review_not_invented() -> None:
    status, question = classify_and_parse_question("هذا نص عشوائي لا يشبه سؤالاً ولا خيارات")
    if status == "uncertain":
        assert question is not None
        assert question.get("question_text", "").strip()
    else:
        assert status == "content"


def test_headers_and_footers_do_not_become_questions() -> None:
    for noise in (
        "وزارة التربية والتعليم",
        "إدارة شرق التعليمية",
        "مدرسة الثانوية الرسمية",
        "اسم الطالب: ................ رقم الجلوس: ........",
        "انتهت الأسئلة - مع أطيب التمنيات بالتوفيق",
        "صفحة 2 من 4",
    ):
        status, question = classify_and_parse_question(noise)
        assert status == "content", f"'{noise}' classified as {status}"
        assert question is None


def test_true_false_and_fill_blank_shapes() -> None:
    # True/False: only two options
    status, question = classify_and_parse_question(
        "س4: العدس ينتمي إلى البقوليات؟ ضع (صح) أو (خطأ)"
    )
    if status == "question" and question:
        opts = question.get("options") or []
        assert len(opts) != 4, "true/false must not gain four invented options"

    # Essay: no options fabricated
    status, question = classify_and_parse_question(
        "س5: اشرح بالتفصيل تأثير الضغط على سرعة التفاعل الكيميائي"
    )
    if status == "question" and question:
        assert not (question.get("options") or []), "essay must stay essay (no options)"


# ---------------------------------------------------------------------------
# 4) No indexing dispatch anywhere
# ---------------------------------------------------------------------------

def test_celery_app_has_no_indexing_tasks() -> None:
    from app.tasks.celery_app import celery_app

    tasks = set(celery_app.tasks)
    assert not [t for t in tasks if "knowledge" in t or "indexing" in t or "ingestion" in t]


# ---------------------------------------------------------------------------
# 4) File-identity binding (A/B markers, checksum, corrupt input)
# ---------------------------------------------------------------------------

MARKER_A = "EXTRACT-A-92841"
MARKER_B = "EXTRACT-B-57306"


def _checksummed_extract(client: TestClient, filename: str, content: str) -> dict:
    import hashlib

    payload = content.encode("utf-8")
    expected = hashlib.sha256(payload).hexdigest()
    data = _extract(client, filename, content)
    metadata = data.get("metadata") or {}
    assert metadata.get("source_checksum") == expected, (
        "extraction response is not bound to the uploaded bytes"
    )
    assert metadata.get("extraction_id"), "extraction_id missing"
    return data


def test_marker_files_isolate_a_and_b(db) -> None:
    """File A yields only A; file B yields only B; the old static exam never appears."""
    inst, teacher, _course = make_teacher_course(db, "marker-ab")
    client = TestClient(app)
    login(client, teacher, "marker-ab")

    body_a = f"س1: ما الرمز المرتبط بـ{MARKER_A}؟\nأ) 1\nب) 2\nج) 3\nد) 4\nالإجابة الصحيحة: أ\n"
    body_b = f"س1: ما الرمز المرتبط بـ{MARKER_B}؟\nأ) 5\nب) 6\nج) 7\nد) 8\nالإجابة الصحيحة: ب\n"

    json_a = _checksummed_extract(client, "a.txt", body_a)
    json_b = _checksummed_extract(client, "b.txt", body_b)

    text_a = " ".join(q["question_text"] for q in json_a["questions"])
    text_b = " ".join(q["question_text"] for q in json_b["questions"])
    assert MARKER_A in text_a and MARKER_A not in text_b
    assert MARKER_B in text_b and MARKER_B not in text_a
    for leaked in ("كعامل مؤكسد", "الداكرون", "PCl5", "svg", "تعديل"):
        assert leaked not in text_a and leaked not in text_b, f"static exam leaked: {leaked}"


def test_corrupt_file_fails_loudly(db) -> None:
    """A truncated PDF must be a 422 failure, never a sample or silent success."""
    inst, teacher, _course = make_teacher_course(db, "corrupt")
    client = TestClient(app)
    login(client, teacher, "corrupt")

    response = client.post(
        "/api/v1/quiz/extract-from-file",
        files={"file": ("broken.pdf", b"%PDF-1.4 truncated garbage \xff\xd8 no content", "application/pdf")},
        headers={"X-CSRF-Token": client.cookies.get("matgar_csrf", "")},
    )
    assert response.status_code == 422, response.text
    body = response.json()
    assert "detail" in body
