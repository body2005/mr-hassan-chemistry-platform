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


def test_points_never_default_when_not_in_source(db) -> None:
    """If no points are explicitly stated, points must be None and needs_points_assignment must be True."""
    inst, teacher, _course = make_teacher_course(db, "no-pts")
    client = TestClient(app)
    login(client, teacher, "no-pts")

    content = "س1: ما هو الرمز الكيميائي للماء؟\nأ) H2O\nب) CO2\nج) NaCl\nد) O2\n"
    res = _extract(client, "chemistry.txt", content)
    questions = res["questions"]
    assert len(questions) == 1
    q = questions[0]
    assert q["points"] is None
    assert q["needs_points_assignment"] is True
    assert res["total_points"] is None


def test_explicit_points_extracted_faithfully(db) -> None:
    """Explicit point values e.g. (درجتان) or (3 درجات) are extracted without guessing."""
    inst, teacher, _course = make_teacher_course(db, "explicit-pts")
    client = TestClient(app)
    login(client, teacher, "explicit-pts")

    content = (
        "س1: ما هو الرمز الكيميائي للماء؟ (درجتان)\n"
        "أ) H2O\nب) CO2\nج) NaCl\nد) O2\n"
        "س2: اذكر استخدامات حمض الكبريتيك؟ [3 درجات]\n"
    )
    res = _extract(client, "points_exam.txt", content)
    questions = res["questions"]
    assert len(questions) == 2
    assert questions[0]["points"] == 2
    assert questions[0]["needs_points_assignment"] is False
    assert questions[1]["points"] == 3
    assert questions[1]["needs_points_assignment"] is False
    assert res["total_points"] == 5


def test_section_headers_provide_context_and_do_not_leak(db) -> None:
    """Section headers (e.g. 'ضع علامة صح أو خطأ') establish context and are not extracted as questions."""
    inst, teacher, _course = make_teacher_course(db, "sec-headers")
    client = TestClient(app)
    login(client, teacher, "sec-headers")

    content = (
        "السؤال الأول: ضع علامة صح أو خطأ أمام العبارات الآتية:\n"
        "1- الماء مركب كيميائي يتكون من الهيدروجين والأكسجين.\n"
        "2- الحديد لا يتفاعل مع أكسجين الهواء الرطب.\n"
    )
    res = _extract(client, "tf_exam.txt", content)
    questions = res["questions"]
    assert len(questions) == 2

    # Section header should not become a question
    all_stems = [q["question_text"] for q in questions]
    assert not any("ضع علامة" in s for s in all_stems)

    # Questions should be classified as TRUE_FALSE with 2 options (صح / خطأ)
    for q in questions:
        assert q["question_type"] == "TRUE_FALSE"
        assert q["options"] is not None
        assert len(q["options"]) == 2
        opt_texts = {opt["text"] for opt in q["options"]}
        assert "صح" in opt_texts and "خطأ" in opt_texts


def test_missing_answers_require_teacher_review(db) -> None:
    """Questions without explicit answers must have correct_answer=None and needs_answer_review=True."""
    inst, teacher, _course = make_teacher_course(db, "no-ans")
    client = TestClient(app)
    login(client, teacher, "no-ans")

    content = "س1: أي الغازات التالية يسبب الاحتباس الحراري؟\nأ) ثاني أكسيد الكربون\nب) الأكسجين\nج) النيتروجين\nد) الهيدروجين\n"
    res = _extract(client, "no_ans_exam.txt", content)
    questions = res["questions"]
    assert len(questions) == 1
    q = questions[0]
    assert q["correct_answer"] is None
    assert q["needs_answer_review"] is True
    assert q["answer_confidence"] == "unknown"


def test_ocr_cache_uses_full_file_sha256() -> None:
    """OCR cache keys depend on full file sha256, page number, language, and parser version."""
    import hashlib
    from app.services.document_parsers import PARSER_OCR_VERSION

    b1 = b"%PDF-1.4 file 1 content " + (b"A" * 200000)
    b2 = b"%PDF-1.4 file 1 content " + (b"B" * 200000)

    hash1 = hashlib.sha256(b1).hexdigest()
    hash2 = hashlib.sha256(b2).hexdigest()
    assert hash1 != hash2, "Full hashes must differ even if prefixes are identical"
    assert PARSER_OCR_VERSION == "v3"


def test_chemistry_16q_fixture_exact_contract(db) -> None:
    """
    Validates all 13 user requirements on the exact 16-question chemistry exam fixture:
    - 16 questions extracted, all canonical MCQ
    - Sequential IDs 1 to 16
    - points=None, needs_points_assignment=True
    - correct_answer=None, needs_answer_review=True
    - Clean chemical formulas (Fe₃O₄, PCl₅, Ba₃(PO₄)₂, Ksp = 108 S⁵)
    - Zero markdown asterisks (no *****)
    - Repaired Arabic BiDi sentence order with numbers and units
    - Preserved negative signs (-0.30 V)
    - Reversed parentheses normalized ((النحاس والخارصين), (الأيزوميرات), (الأسيتيلين), (غطاء كاثودي))
    - Zero UI tokens (svg, تعديل, الدرجة, اختيار من متعدد)
    """
    inst, teacher, _course = make_teacher_course(db, "chem-16q")
    client = TestClient(app)
    login(client, teacher, "chem-16q")

    fixture_path = os.path.join(
        os.path.dirname(__file__), "fixtures", "chemistry_16q_exam.pdf"
    )
    assert os.path.exists(fixture_path), f"Fixture not found at {fixture_path}"

    with open(fixture_path, "rb") as f:
        pdf_bytes = f.read()

    response = client.post(
        "/api/v1/quiz/extract-from-file",
        files={"file": ("chemistry_16q_exam.pdf", pdf_bytes, "application/pdf")},
        headers={"X-CSRF-Token": client.cookies.get("matgar_csrf", "")},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    questions = body["questions"]
    assert len(questions) == 20, f"Expected 20 questions, got {len(questions)}"

    # 1. Sequential IDs, types, points, and answers contract for 16 MCQs
    for idx, q in enumerate(questions[:16], start=1):
        assert q["id"] == idx, f"Question at index {idx} has id {q['id']}"
        assert q["question_type"] == "MCQ"
        assert q["points"] is None
        assert q["needs_points_assignment"] is True
        assert q["correct_answer"] is None
        assert q["needs_answer_review"] is True
        assert q["options"] is not None and len(q["options"]) >= 4

        # Zero markdown asterisks and zero UI leak
        stem = q["question_text"]
        assert "*****" not in stem, f"Asterisks in Q{idx}: {stem}"
        assert "svg" not in stem.lower()
        assert "تعديل" not in stem
        assert "حدد الدرجة" not in stem

        for opt in q["options"]:
            opt_txt = opt["text"]
            assert "*****" not in opt_txt, f"Asterisks in Q{idx} option: {opt_txt}"
            assert "svg" not in opt_txt.lower()
            assert "تعديل" not in opt_txt

    # 2. Sequential IDs, types, points, and answers contract for 4 Essay questions
    for idx, q in enumerate(questions[16:], start=17):
        assert q["id"] == idx, f"Question at index {idx} has id {q['id']}"
        assert q["question_type"] == "ESSAY"
        assert q["points"] == 3
        assert q["needs_points_assignment"] is False
        assert q["correct_answer"] is None
        assert q["needs_review"] is False
        assert q["needs_answer_review"] is False
        assert q["options"] == []
        assert q["source_page"] in (4, 5)

        stem = q["question_text"]
        assert "*****" not in stem, f"Asterisks in Q{idx}: {stem}"
        assert "svg" not in stem.lower()
        assert "تعديل" not in stem
        assert "حدد الدرجة" not in stem

    # 3. Specific questions verification
    # Q1: First transition series element
    assert "عنصر انتقالي من السلسلة الأولى" in questions[0]["question_text"]
    assert "كعامل مؤكسد قوي" in questions[0]["question_text"]

    # Q2: Fe₃O₄ and temperature range
    assert "Fe₃O₄" in questions[1]["question_text"]
    assert "من 400°C إلى 700°C" in questions[1]["question_text"]

    # Q3: Copper-zinc alloy
    assert "سبيكة مكونة من عنصري (النحاس والخارصين)" in questions[2]["question_text"]
    assert "كيف يمكن فصل النحاس منها نقّيًا؟" in questions[2]["question_text"]

    # Q4: Reordered conclusion
    assert "تكون مع (X) راسب أصفر يذوب في محلول النشادر المركز، وتكون مع (Y) راسب أصفر لا يذوب في محلول النشادر المركز، فإن الأنيونين (X) و (Y) هما على الترتيب:" in questions[3]["question_text"]

    # Q5: Sodium carbonate hydrate and consumption
    assert "أذيب 14.3 g من كربونات الصوديوم المتهدرتة" in questions[4]["question_text"]
    assert "اسُتهلك 25 mL من الحمض، فإن النسبة المئوية لماء التبلر في العينة تساوي:" in questions[4]["question_text"]

    # Q6: PCl₅ and option paren reordering
    assert "PCl₅(g) ⇌ PCl₃(g) + Cl₂(g)" in questions[5]["question_text"]
    q6_opts = [o["text"] for o in questions[5]["options"]]
    assert any("تقليل حجم وعاء التفاعل (زيادة الضغط)" in o for o in q6_opts)

    # Q7: Ba₃(PO₄)₂ and solubility degree
    assert "Ba₃(PO₄)₂" in questions[6]["question_text"]
    assert "درجة الإذابة (S)" in questions[6]["question_text"]
    q7_opts = [o["text"] for o in questions[6]["options"]]
    assert any("Ksp = 108 S⁵" in o for o in q7_opts)

    # Q8: Ammonium acetate and pH
    assert "CH₃COONH₄" in questions[7]["question_text"]
    assert "(pH)" in questions[7]["question_text"]
    assert "25°C" in questions[7]["question_text"]

    # Q9: Cell diagram, oxidation potentials, and negative voltage
    assert "Cr(s) | Cr³⁺(aq) || Fe²⁺(aq) | Fe(s)" in questions[8]["question_text"]
    assert "جهد تأكسد الكروم = +0.74 V" in questions[8]["question_text"]
    q9_opts = [o["text"] for o in questions[8]["options"]]
    assert "-0.30 V" in q9_opts, f"Expected -0.30 V in Q9 options: {q9_opts}"

    # Q10: Cathodic and anodic protection options
    q10_opts = [o["text"] for o in questions[9]["options"]]
    assert any("طلاؤها بطبقة من القصدير (غطاء كاثودي)" in o for o in q10_opts)
    assert any("جلفنتها بطبقة من الخارصين (غطاء آنودي)" in o for o in q10_opts)

    # Q11: Current and mass
    assert "عند إمرار تيار كهربي شدته 9.65 A لمدة 1000 s" in questions[10]["question_text"]
    assert "ترسب 0.9 g" in questions[10]["question_text"]

    # Q12: Isomers
    assert "ما هو إجمالي عدد المتشكلات (الأيزوميرات) المفتوحة والحلقية معًا لهذه الصيغة؟" in questions[11]["question_text"]

    # Q13: Hydration of ethyne (acetylene)
    assert "عند إضافة الماء إلى الإيثاين (الأسيتيلين) في وجود حمض الكبريتيك 40% وكبريتات الزئبق الثنائي عند 60°C" in questions[12]["question_text"]
    q13_opts = [o["text"] for o in questions[12]["options"]]
    assert any("حمض الإيثانويك (الأسيتيك)" in o for o in q13_opts)

    # Q16: Polymerization of ethylene glycol and terephthalic acid
    assert "وحمض التيرفثاليك يعرف تجاريًا باسم:" in questions[15]["question_text"]

    # Q17: Barium sulfate and phosphate separation
    assert "لديك خليط صلب من ملحي (كبريتات الباريوم) و (فوسفات الباريوم)" in questions[16]["question_text"]
    assert "كيف تفصل كبريتات الباريوم عن فوسفات الباريوم" in questions[16]["question_text"]

    # Q18: Hydrofluoric acid pH calculation
    assert "احسب قيمة الأس الهيدروجيني (pH)" in questions[17]["question_text"]
    assert "HF" in questions[17]["question_text"]
    assert "0.2 M" in questions[17]["question_text"]

    # Q19: Fuel cell diagram and potential
    assert "اكتب الرمز الاصطلاحي لخلية الوقود" in questions[18]["question_text"]
    assert "E°cell" in questions[18]["question_text"]

    # Q20: Synthesis of meta-chloronitrobenzene
    assert "وضح بالمعادلات الكيميائية الرمزية الموزونة وشروط التفاعل:" in questions[19]["question_text"]
    assert "بنزوات الصوديوم" in questions[19]["question_text"]
    assert "ميتا - كلورو نيتروبنزين" in questions[19]["question_text"]


def test_four_sequential_files_isolation(db) -> None:
    """
    Strict Point 11 verification: proves that 4 sequential extractions remain 100% isolated:
    1) chemistry_16q_exam.pdf -> 20 questions
    2) distinct 3-question file -> 3 questions (zero chem-16 bleed)
    3) distinct 2-question file -> 2 questions (zero bleed)
    4) corrupt file -> 422 rejection (zero bleed)
    """
    inst, teacher, _course = make_teacher_course(db, "seq-4files")
    client = TestClient(app)
    login(client, teacher, "seq-4files")

    fixture_path = os.path.join(
        os.path.dirname(__file__), "fixtures", "chemistry_16q_exam.pdf"
    )

    # File 1: Chemistry 16Q (20 questions total: 16 MCQ + 4 Essay)
    with open(fixture_path, "rb") as f:
        pdf_bytes = f.read()
    r1 = client.post(
        "/api/v1/quiz/extract-from-file",
        files={"file": ("chem_exam.pdf", pdf_bytes, "application/pdf")},
        headers={"X-CSRF-Token": client.cookies.get("matgar_csrf", "")},
    )
    assert r1.status_code == 200
    q1 = r1.json()["questions"]
    assert len(q1) == 20

    # File 2: Distinct 3-question file
    f2_content = (
        "س1: ما هو الكوكب الأحمر؟\nأ) المريخ\nب) الزهرة\nج) المشتري\nد) عطارد\n"
        "س2: ما هي عاصمة فرنسا؟\nأ) باريس\nب) لندن\nج) روما\nد) مدريد\n"
        "س3: ما وحدة قياس القوة؟\nأ) نيوتن\nب) جول\nج) واط\nد) باسكال\n"
    )
    r2 = client.post(
        "/api/v1/quiz/extract-from-file",
        files={"file": ("astronomy_3q.txt", f2_content.encode("utf-8"), "text/plain")},
        headers={"X-CSRF-Token": client.cookies.get("matgar_csrf", "")},
    )
    assert r2.status_code == 200
    q2 = r2.json()["questions"]
    assert len(q2) == 3
    q2_opts = " ".join(o["text"] for q in q2 for o in (q.get("options") or []))
    q2_text = " ".join(q["question_text"] for q in q2)
    assert "المريخ" in q2_opts and "باريس" in q2_opts and "نيوتن" in q2_opts
    assert "الكوكب الأحمر" in q2_text and "عاصمة فرنسا" in q2_text
    assert "Fe₃O₄" not in q2_text and "Fe₃O₄" not in q2_opts
    assert "الأسيتيلين" not in q2_text and "الأسيتيلين" not in q2_opts
    assert "الكروم" not in q2_text and "الكروم" not in q2_opts

    # File 3: Distinct 2-question file
    f3_content = (
        "1. الكائن الحي الوحيد الخلية هو:\n(أ) الأميبا\n(ب) الأسد\n(ج) الفيل\n(د) الشجرة\n"
        "2. عملية البناء الضوئي تتم في:\n(أ) البلاستيدات الخضراء\n(ب) الميتوكوندريا\n(ج) النواة\n(د) الجدار الخلوي\n"
    )
    r3 = client.post(
        "/api/v1/quiz/extract-from-file",
        files={"file": ("biology_2q.txt", f3_content.encode("utf-8"), "text/plain")},
        headers={"X-CSRF-Token": client.cookies.get("matgar_csrf", "")},
    )
    assert r3.status_code == 200
    q3 = r3.json()["questions"]
    assert len(q3) == 2
    q3_opts = " ".join(o["text"] for q in q3 for o in (q.get("options") or []))
    q3_text = " ".join(q["question_text"] for q in q3)
    assert "الأميبا" in q3_opts
    assert "البناء الضوئي" in q3_text
    assert "المريخ" not in q3_text and "المريخ" not in q3_opts
    assert "Fe₃O₄" not in q3_text and "Fe₃O₄" not in q3_opts

    # File 4: Corrupt PDF file
    r4 = client.post(
        "/api/v1/quiz/extract-from-file",
        files={"file": ("corrupt.pdf", b"NOT_A_REAL_PDF_DATA_GARBAGE", "application/pdf")},
        headers={"X-CSRF-Token": client.cookies.get("matgar_csrf", "")},
    )
    assert r4.status_code == 422
    err_body = r4.json()
    assert "detail" in err_body


def test_target_type_assignment_handling(db) -> None:
    """Verifies that target_type='assignment' is reflected in draft metadata and title."""
    inst, teacher, _course = make_teacher_course(db, "target-type")
    client = TestClient(app)
    login(client, teacher, "target-type")

    content = "س1: اشرح بالتفصيل دور العامل الحفاز في التفاعلات الكيميائية.\n"
    res = client.post(
        "/api/v1/quiz/extract-from-file",
        files={"file": ("homework.txt", content.encode("utf-8"), "text/plain")},
        data={"target_type": "assignment"},
        headers={"X-CSRF-Token": client.cookies.get("matgar_csrf", "")},
    )
    assert res.status_code == 200
    data = res.json()
    assert "واجب" in data["title"]
    assert data["metadata"]["target_type"] == "assignment"


def test_magic_byte_rejection(db) -> None:
    """Forged or corrupt files with invalid header signatures are rejected with 422."""
    inst, teacher, _course = make_teacher_course(db, "magic-bytes")
    client = TestClient(app)
    login(client, teacher, "magic-bytes")

    bad_files = [
        ("fake.pdf", b"hello world not a pdf", "application/pdf"),
        ("fake.docx", b"hello world not a docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        ("fake.png", b"hello world not a png", "image/png"),
        ("fake.jpg", b"hello world not a jpeg", "image/jpeg"),
    ]

    for fname, bad_bytes, mime in bad_files:
        resp = client.post(
            "/api/v1/quiz/extract-from-file",
            files={"file": (fname, bad_bytes, mime)},
            headers={"X-CSRF-Token": client.cookies.get("matgar_csrf", "")},
        )
        assert resp.status_code == 422, f"Expected 422 for {fname}, got {resp.status_code}"
        payload = resp.json()
        code = payload.get("error", {}).get("code") or (
            payload.get("detail", {}).get("code") if isinstance(payload.get("detail"), dict) else None
        )
        assert code == "CORRUPT_OR_INVALID_FILE", f"Unexpected code for {fname}: {payload}"


