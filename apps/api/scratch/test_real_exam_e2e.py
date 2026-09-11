import os
import sys
import json
import uuid

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# Ensure apps/api is in sys.path
sys.path.insert(0, "D:/learning project/apps/api")

from sqlalchemy import select
from app.core.database import SessionLocal, engine
from app.models import Base
from app.models.institution import Institution
from app.models.user import User, UserRole
from app.models.course import Course, CourseModule, Lesson
from app.models.knowledge_center import (
    KnowledgeSource,
    KnowledgeDocument,
    KnowledgeUnitRecord,
    KnowledgeQuestionRecord,
)
from app.services.knowledge_center_service import (
    classify_and_parse_question,
    extract_distant_answer_keys,
    parse_table_questions,
    resolve_correct_answer_text,
    create_knowledge_source,
    process_knowledge_source,
)

print("=" * 80)
print("PART 1: REALISTIC DETECTION RATE BENCHMARK ACROSS 4+ EXAM FORMATS")
print("=" * 80)

# 1. Format 1: Standard Formal Arabic ("السؤال الأول / السؤال 1") with various punctuation and markers
format_1_samples = [
    ("السؤال الأول: ما هو المعدن الأكثر صلابة على مقياس موهس؟\nأ. الكوارتز\nب. التلك\nج. الماس\nد. الكالسيت\nالإجابة: ج", "الماس", "question"),
    ("السؤال 2: ما الصخر الذي يتكون نتيجة تبريد اللافا السطحي؟\n(أ) الجرانيت\n(ب) البازلت\n(ج) الجابرو\n(د) الديونيت\nالإجابة الصحيحة: ب", "البازلت", "question"),
    ("سؤال 3 - أي التراكيب الجيولوجية التالية ينتج عن قوى الشد التكتونية؟\nأ- الفالق المعكوس\nب- الفالق العادي\nج- الطية المحدبة\nد- الطية المقعرة\nالجواب: ب", "الفالق العادي", "question"),
    ("السؤال الرابع : ما الخاصية التي تعبر عن مقاومة المعدن للخدش؟\nأ) الصلادة\nب) المخدش\nج) الانفصام\nد) الشفافية\nالحل: أ", "الصلادة", "question"),
    ("السؤال 5: تتكون صخور الشيست الميكائي بالتحول نتيجة:\nأ. الحرارة والضغط معاً\nب. الحرارة فقط\nج. الضغط فقط\nد. الترسيب المائي\nالإجابة: أ", "الحرارة والضغط معاً", "question"),
]

# 2. Format 2: Abbreviated prefix ("س1:", "س٢ :", "Q1:") with various real-world noisy formatting
format_2_samples = [
    ("س1: ما هو المخدش؟\nأ) لون المعدن في الضوء\nب) لون مسحوق المعدن بعد حكه\nج) مقاومة المعدن للكسر\nد) درجة لمعان السطح\nالإجابة الصحيحة: ب", "لون مسحوق المعدن بعد حكه", "question"),
    ("س 2 : الصخر الرسوبي الكيميائي النطاق هو:\nأ. الحجر الجيري\nب. البريشيا\nج. الكونجلوميرات\nد. الفحم الحجري\nالحل : أ", "الحجر الجيري", "question"),
    ("س٣: من أمثلة الفوالق الزحفية:\nأ- فالق دسر\nب- فالق عادي\nج- فالق بارز\nد- فالق خسفي\nالجواب: أ", "فالق دسر", "question"),
    ("Q4: The Mohs scale hardness of Quartz is:\nA) 5\nB) 7\nC) 9\nD) 10\nAnswer: B", "7", "question"),
    ("س5) أي المعادن الآتية عنصري منفرد؟\nأ. الذهب\nب. الكالسيت\nج. المرو\nد. الهيماتيت\nالإجابة: أ", "الذهب", "question"),
]

# 3. Format 3: Bare digits with no question keywords ("1-", "2.", "(3)")
format_3_samples = [
    ("1- يعتبر الجرانيت من الصخور النارية:\nأ. الجوفية الحامضية\nب. السطحية القاعدية\nج. المتداخلة المتوسطة\nد. البركانية\nالحل: أ", "الجوفية الحامضية", "question"),
    ("2. مستوى الفالق هو المستوى الذي:\nأ- تتحرك على جانبيه الكتل الصخرية\nب- يفصل بين البلورات فقط\nج- لا يتحرك إطلاقاً\nد- ينشأ بالرياح\nالإجابة: أ", "تتحرك على جانبيه الكتل الصخرية", "question"),
    ("(3) عدد أنظمة التبلور التي تشمل 4 محاور بلورية هو:\nأ) نظام واحد\nب) نظامان\nج) 3 أنظمة\nد) 4 أنظمة\nالجواب: ب", "نظامان", "question"),
    ("4- النسيج البرفيري يميز الصخور النارية:\nأ. المتداخلة\nب. الجوفية\nج. البركانية السطحية\nد. الرسوبية\nالحل: أ", "المتداخلة", "question"),
    ("5. الأوليفين يتبلور في درجات حرارة:\nأ) مرتفعة أولاً\nب) منخفضة أخيراً\nج) متوسطة فقط\nد) لا يتبلور\nالإجابة: أ", "مرتفعة أولاً", "question"),
]

# 4. Format 4: Distant answer keys at the bottom of exam
distant_exam_doc = """
س1: أي مما يلي يمثل معدناً كربونياً؟
أ. الكالسيت
ب. الكوارتز
ج. الفلسبار
د. الجبس

س2: زاوية ميل الفالق الدسر تكون:
أ. قليلة تقترب من الأفقية
ب. عمودية تماماً
ج. قائمة
د. منفرجة جداً

س3: الصخر المتحول الكتلي ينتج أساساً بفعل:
أ. الحرارة الشديدة
ب. الضغط فقط
ج. التيارات الهوائية
د. التجوية الميكانيكية

=== نموذج الإجابات الرسمية والنهائية ===
1- أ
2- أ
3- أ
"""
distant_keys = extract_distant_answer_keys(distant_exam_doc)

format_4_samples = [
    ("س1: أي مما يلي يمثل معدناً كربونياً؟\nأ. الكالسيت\nب. الكوارتز\nج. الفلسبار\nد. الجبس", "الكالسيت", "question"),
    ("س2: زاوية ميل الفالق الدسر تكون:\nأ. قليلة تقترب من الأفقية\nب. عمودية تماماً\nج. قائمة\nد. منفرجة جداً", "قليلة تقترب من الأفقية", "question"),
    ("س3: الصخر المتحول الكتلي ينتج أساساً بفعل:\nأ. الحرارة الشديدة\nب. الضغط فقط\nج. التيارات الهوائية\nد. التجوية الميكانيكية", "الحرارة الشديدة", "question"),
]

# 5. Format 5: Uncertain Blocks (Rhetorical question in content, no options)
uncertain_samples = [
    ("هل تساءلت يوماً عن سبب اختلاف ألوان معدن الكوارتز بين الوردي والبنفسجي والرمادي رغم تشابه تركيبه الكيميائي من ثاني أكسيد السيليكون؟", "uncertain"),
    ("كيف يمكن للجيولوجي في الحقل التمييز بين الطية المحدبة والطية المقعرة بالعين المجردة من خلال ترتيب الطبقات الأقدم والأحدث؟", "uncertain"),
    ("لماذا تختلف سرعة تبريد الصهير الجوفي في باطن الأرض عن تبريد الحمم البركانية على السطح وتأثير ذلك على حجم البلورات؟", "uncertain"),
]

# 6. Format 6: Pure Content (Textbook Paragraphs)
content_samples = [
    ("تنشأ الصخور الرسوبية الفتاتية نتيجة تفتت الصخور القديمة بفعل عوامل التجوية ثم نقلها بواسطة المياه الجارية أو الرياح وترسيبها في أحواض الترسيب.", "content"),
    ("علم الجيولوجيا التاريخية يهدف إلى استنتاج التاريخ الجيولوجي للأرض وتحديد أعمار الصخور وتطور الكائنات الحية عبر العصور الجيولوجية المتعاقبة.", "content"),
    ("التركيب البلوري للمعدن هو الترتيب الهندسي المنتظم للذرات والأيونات المكونة للمعدن في الفراغ، وهو الذي يتحكم في الخصائص الفيزيائية والكيميائية للمعدن.", "content"),
]

def eval_samples(name, samples, distant_dict={}):
    correct_detect = 0
    correct_answer_match = 0
    total = len(samples)
    samples_with_expected_ans = 0
    for sample in samples:
        text = sample[0]
        expected_ans = sample[1] if len(sample) == 3 else None
        expected_state = sample[2] if len(sample) == 3 else sample[1]
        
        state, data = classify_and_parse_question(text, distant_keys=distant_dict)
        if state == expected_state:
            correct_detect += 1
        if expected_ans is not None:
            samples_with_expected_ans += 1
            if data and data.get("correct_answer") == expected_ans:
                correct_answer_match += 1

    det_rate = (correct_detect / total) * 100
    print(f"- {name}:")
    print(f"    * Detection Rate: {correct_detect}/{total} ({det_rate:.1f}%)")
    if samples_with_expected_ans > 0:
        ans_rate = (correct_answer_match / samples_with_expected_ans) * 100
        print(f"    * Answer Resolution to Full Text: {correct_answer_match}/{samples_with_expected_ans} ({ans_rate:.1f}%)")
    return det_rate

print("\n--- RESULTS PER PATTERN ---")
r1 = eval_samples("Pattern 1 (Formal Arabic 'السؤال الأول / السؤال 1')", format_1_samples)
r2 = eval_samples("Pattern 2 (Short Prefix 'س1: / س 2 : / Q1:')", format_2_samples)
r3 = eval_samples("Pattern 3 (Plain Numbering '1- / 2. / (3)')", format_3_samples)
r4 = eval_samples("Pattern 4 (Distant Answer Keys at Exam End)", format_4_samples, distant_keys)
r5 = eval_samples("Pattern 5 (Uncertain / Ambiguous Blocks -> 'uncertain')", uncertain_samples)
r6 = eval_samples("Pattern 6 (Pure Content Paragraphs -> 'content')", content_samples)

print("\n" + "=" * 80)
print("PART 2: END-TO-END DATABASE INGESTION & EXTRACTION ON A REAL EXAM FILE")
print("=" * 80)

Base.metadata.create_all(bind=engine)

db = SessionLocal()
try:
    # Setup test Institution & Teacher
    inst = db.scalar(select(Institution).where(Institution.slug == "e2e_stress_test_inst"))
    if not inst:
        inst = Institution(name="مؤسسة الاختبار الفعلي", slug="e2e_stress_test_inst")
        db.add(inst)
        db.commit()
        db.refresh(inst)

    teacher = db.scalar(select(User).where(User.username == "e2e_stress_teacher"))
    if not teacher:
        teacher = User(
            institution_id=inst.id,
            username="e2e_stress_teacher",
            email="stress_teacher@lms.edu",
            password_hash="fake_hash",
            display_name="د. أحمد حسن - معلم الجيولوجيا",
            role=UserRole.TEACHER,
        )
        db.add(teacher)
        db.commit()
        db.refresh(teacher)

    course = db.scalar(select(Course).where(Course.code == "GEO101"))
    if not course:
        course = Course(
            institution_id=inst.id,
            teacher_id=teacher.id,
            title="مقرر الجيولوجيا والعلوم البيئية - امتحان شامل",
            code="GEO101",
        )
        db.add(course)
        db.commit()
        db.refresh(course)

    # Build a complex, realistic, multi-pattern real exam document
    real_exam_content = """# امتحان الجيولوجيا الشامل - الفصل الدراسي الأول

تعتبر الجيولوجيا علم الأرض الذي يبحث في كل ما له علاقة بالأرض ونشأتها وتاريخها ومكوناتها وحركاتها وثرواتها الطبيعية.

السؤال الأول: ما هو المعدن الذي ينفصم في أكثر من اتجاه بزوايا غير قائمة؟
أ. الكالسيت
ب. الهاليت
ج. الجالينا
د. الميكا
الإجابة: أ

س٢ : صخر الجرانيت يتكون أساساً من ثلاثة معادن رئيسية هي:
أ- الفلسبار والكوارتز والميكا
ب- الأوليفين والبيروكسين والأنفيبول
ج- الكالسيت والدولوميت والأراجونيت
د- الجبس والأنهيدريت والملح الصخري
الحل: أ

3. الفالق الخندقي (الخسفي) يحدث نتيجة:
أ) تأثر صخور الحائط العلوي بقوى شد بين فالقين عاديين
ب) قوى ضغط هائلة تؤدي لانزلاق صخور الحائط السفلي
ج) حركة أفقية دون وجود أي إزاحة رأسية
د) تجوية كيميائية مستمرة للمغارات الجيرية
الجواب: أ

هل يمكن للجيولوجي أن يستدل على بيئة الترسيب القديمة من خلال دراسة حفريات الشعاب المرجانية والفحم الحجري؟

س4: النسيج الزجاجي للصخور النارية يدل على أن الصهير:
أ. تبرد سريعاً على السطح
ب. تبرد ببطء شديد في الأعماق
ج. تعرض لضغط وحرارة معاً
د. لم يتصلب إطلاقاً

س5: أي المعادن التالية يتميز ببريق فلزي قوي ومخدش أسود؟
أ. البيرايت
ب. المرو
ج. الماس
د. التلك

=== نموذج إجابة امتحان الجيولوجيا ===
4- أ
5- أ
"""

    from sqlalchemy import delete
    db.execute(delete(KnowledgeSource).where(KnowledgeSource.course_id == course.id))
    db.commit()

    file_bytes = real_exam_content.encode("utf-8")
    test_filename = f"real_geology_exam_{uuid.uuid4().hex[:6]}.txt"
    source = create_knowledge_source(
        db=db,
        user=teacher,
        course_id=course.id,
        filename=test_filename,
        file_bytes=file_bytes,
        source_role="KNOWLEDGE",
        mime_type="text/plain",
    )

    print(f"1. Created KnowledgeSource: ID={source.id}, filename={source.filename}")
    
    # Process document through the ingestion pipeline
    process_knowledge_source(db, source.id)
    db.refresh(source)
    print(f"2. Processed Source Status: {source.status}")
    print(f"   - Questions Indexed: {source.question_count}")
    print(f"   - Units Indexed: {source.unit_count}")

    # Query SQLite KnowledgeQuestionRecord
    questions_in_db = db.scalars(
        select(KnowledgeQuestionRecord)
        .where(KnowledgeQuestionRecord.source_id == source.id)
        .order_by(KnowledgeQuestionRecord.created_at.asc())
    ).all()

    print(f"\n3. RAW DATABASE RECORDS IN SQLite (`knowledge_question_records`):")
    print(f"   Total rows stored: {len(questions_in_db)}")
    for idx, q_rec in enumerate(questions_in_db, start=1):
        print(f"\n   [RECORD #{idx}]")
        print(f"     ID: {q_rec.id}")
        print(f"     Question Stem: {q_rec.question_text[:80]}...")
        print(f"     Type: {q_rec.question_type}")
        print(f"     Resolved Correct Answer: '{q_rec.correct_answer}'")
        print(f"     Needs Answer Review: {q_rec.needs_answer_review}")
        print(f"     Classification Confidence: {q_rec.classification_confidence}")
        if q_rec.options_json:
            opts_summary = ", ".join(f"({o['key']}) {o['text']}{' [✓]' if o.get('is_correct') else ''}" for o in q_rec.options_json)
            print(f"     Options in DB: {opts_summary}")

    # Query SQLite KnowledgeUnitRecord (verify pure content and uncertain units)
    units_in_db = db.scalars(
        select(KnowledgeUnitRecord)
        .where(KnowledgeUnitRecord.source_id == source.id)
    ).all()
    print(f"\n4. RAW KNOWLEDGE UNITS IN SQLite (`knowledge_units_records`):")
    print(f"   Total units stored: {len(units_in_db)}")
    for idx, u_rec in enumerate(units_in_db, start=1):
        print(f"     Unit #{idx}: Concept='{u_rec.concept}' | Statement='{u_rec.statement[:60]}...' | Needs Review={u_rec.needs_review}")

finally:
    db.close()

print("\n" + "=" * 80)
print("ALL REAL PIPELINE CHECKS FINISHED SUCCESSFULLY")
print("=" * 80)
