import sys, os
sys.path.insert(0, r'D:\learning project\apps\api')
sys.stdout.reconfigure(encoding='utf-8')

from app.core.database import SessionLocal
from app.models.institution import Institution
from app.models.user import User, UserRole
from app.models.course import Course, CourseStatus
from app.models.knowledge_center import SourceRole, SourceStatus, KnowledgeUnitRecord, KnowledgeSource
from app.services.knowledge_center_service import create_knowledge_source, process_knowledge_source
from app.services.knowledge_retriever import check_grounding_and_answer, retrieve_lesson_knowledge
from app.services.quiz_engine import generate_quiz
from app.services.educational_normalizer import KnowledgeUnit

from app.models.base import Base

db = SessionLocal()
Base.metadata.create_all(bind=db.get_bind())

# Setup test models
inst = db.query(Institution).filter(Institution.slug == "demo_inst_kc").first()
if not inst:
    inst = Institution(name="مؤسسة مركز المعرفة الذكية", slug="demo_inst_kc")
    db.add(inst)
    db.commit()

teacher = db.query(User).filter(User.username == "demo_teacher_kc").first()
if not teacher:
    teacher = User(
        institution_id=inst.id,
        username="demo_teacher_kc",
        email="teacher_demo_kc@lms.edu",
        password_hash="hash",
        display_name="أ.د. حسن شعبان",
        role=UserRole.TEACHER,
    )
    db.add(teacher)
    db.commit()

course = db.query(Course).filter(Course.code == "GEO_KC_101").first()
if not course:
    course = Course(
        institution_id=inst.id,
        teacher_id=teacher.id,
        code="GEO_KC_101",
        title="مقرر الجيولوجيا والتركيبات الصخرية",
        grade_level="SECONDARY_1",
        status=CourseStatus.PUBLISHED,
    )
    db.add(course)
    db.commit()

# Ingest test document
doc_text = """# Chapter 1: Geology and Earth Structure
علم الجيولوجيا هو العلم الذي يختص بدراسة كوكب الأرض وحركتها ومكوناتها وتاريخها.
ينقسم كوكب الأرض إلى ثلاثة أجزاء رئيسية: القشرة الأرضية، الوشاح، واللب الداخلي والخارجي.
القشرة القارية تتكون من صخور الجرانيت الخفيفة المسماة السيال وسمكها يصل إلى 60 كيلومتر.
القشرة المحيطية تتكون من صخور البازلت الثقيلة المسماة السيما وسمكها من 8 إلى 12 كيلومتر تحت المحيطات.
علم الجيوفيزياء يستخدم الأجهزة الفيزيائية لاستكشاف الثروات البترولية والمياه الجوفية في باطن الأرض."""

source = create_knowledge_source(
    db=db,
    user=teacher,
    course_id=course.id,
    filename="geology_chapter_1.txt",
    file_bytes=doc_text.encode("utf-8"),
    source_role=SourceRole.KNOWLEDGE,
)

process_knowledge_source(db, source.id)

print("=" * 70)
print("VERIFICATION REPORT — AI TEACHING KNOWLEDGE CENTER")
print("=" * 70)
print(f"Source status:          {source.status}")
print(f"Knowledge units count:  {source.unit_count}")
print(f"Document format:        {source.file_format}")

# Test 1: Grounded Q&A with Citations
ans, is_g, is_ref, cits = check_grounding_and_answer(db, teacher, course.id, "ما الفرق بين القشرة القارية والقشرة المحيطية؟")
print("\n[TEST 1: GROUNDED Q&A WITH CITATION]")
print(f"Is Grounded:  {is_g}")
print(f"Is Refusal:   {is_ref}")
print(f"Citations:    {[c['citation'] for c in cits]}")
print(f"Answer:\n{ans[:250]}...")

# Test 2: Out-of-scope Refusal Contract
ans_ref, is_g_ref, is_ref_ref, _ = check_grounding_and_answer(db, teacher, course.id, "ما هي خوارزميات الذكاء الاصطناعي وبايثون؟")
print("\n[TEST 2: OUT-OF-SCOPE REFUSAL]")
print(f"Is Grounded:  {is_g_ref}")
print(f"Is Refusal:   {is_ref_ref}")
print(f"Refusal Response:\n{ans_ref}")

# Test 3: Quiz Generation from Knowledge Center Units
db_units = db.query(KnowledgeUnitRecord).filter(KnowledgeUnitRecord.source_id == source.id).all()
kus = [
    KnowledgeUnit(
        id=str(u.id),
        lesson_id="demo_l1",
        concept=u.concept,
        statement=u.statement,
        raw_text=u.details or u.statement,
        start_time=0.0,
        end_time=30.0,
        category=u.knowledge_type,
    )
    for u in db_units
]

questions, meta = generate_quiz(kus, [{"id": "multiple_choice", "count": 2}, {"id": "true_false", "count": 1}], 3)
print("\n[TEST 3: QUIZ ENGINE INTEGRATION]")
print(f"Requested: {meta['requested_count']} | Generated: {meta['generated_count']} | Distinct Concepts: {meta['distinct_concepts']}")
for i, q in enumerate(questions):
    print(f"  Q{i+1} [{q['question_type']}]: {q['question_text'][:80]}")

db.close()
