"""Idempotent demo seed for client previews.

Creates: demo institution, teacher + student accounts, a published course with
module/lesson, an MCQ quiz, an enrollment, a calendar event and a notification.

Usage:
    python scripts/seed_demo.py            # prints the demo credentials

Safe to run repeatedly: every step checks for existing rows first.
NEVER use these credentials in production.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import SessionLocal  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.models.course import (  # noqa: E402
    Course,
    CourseModule,
    Enrollment,
    EnrollmentStatus,
    Lesson,
    LessonKind,
)
from app.models.institution import Institution  # noqa: E402
from app.models.platform import (  # noqa: E402
    CalendarEvent,
    Notification,
    Question,
    Quiz,
    QuizQuestion,
    QuizStatus,
)
from app.models.user import User, UserRole  # noqa: E402

DEMO_SLUG = "demo"
TEACHER_EMAIL = "teacher@demo.com"
STUDENT_EMAIL = "student@demo.com"
DEMO_PASSWORD = "Demo-Pass-2026!"


def get_or_create_institution(db) -> Institution:
    institution = db.query(Institution).filter(Institution.slug == DEMO_SLUG).one_or_none()
    if institution is None:
        institution = Institution(name="مدرسة تجريبية", slug=DEMO_SLUG)
        db.add(institution)
        db.flush()
    return institution


def get_or_create_user(db, institution, email, name, role) -> User:
    user = db.query(User).filter(User.email == email).one_or_none()
    if user is None:
        user = User(
            institution_id=institution.id,
            username=email.split("@")[0],
            email=email,
            display_name=name,
            password_hash=hash_password(DEMO_PASSWORD),
            role=role,
        )
        db.add(user)
        db.flush()
    return user


def seed() -> None:
    db = SessionLocal()
    try:
        institution = get_or_create_institution(db)
        teacher = get_or_create_user(
            db, institution, TEACHER_EMAIL, "حسن شعبان", UserRole.TEACHER
        )
        student = get_or_create_user(
            db, institution, STUDENT_EMAIL, "طالب تجريبي", UserRole.STUDENT
        )

        course = (
            db.query(Course)
            .filter(Course.institution_id == institution.id, Course.code == "CHEM-101")
            .one_or_none()
        )
        if course is None:
            course = Course(
                institution_id=institution.id,
                teacher_id=teacher.id,
                code="CHEM-101",
                title="الكيمياء — الصف الأول الثانوي",
                description="المقرر الشامل لمادة الكيمياء للصف الأول الثانوي مع مستر حسن شعبان.",
                status="published",
            )
            db.add(course)
            db.flush()

        module = (
            db.query(CourseModule)
            .filter(CourseModule.course_id == course.id, CourseModule.title == "الوحدة الأولى: الكيمياء مركز العلوم")
            .one_or_none()
        )
        if module is None:
            module = CourseModule(course_id=course.id, title="الوحدة الأولى: الكيمياء مركز العلوم", position=1)
            db.add(module)
            db.flush()

        lesson = (
            db.query(Lesson)
            .filter(Lesson.module_id == module.id, Lesson.title == "القياس في الكيمياء وأدوات المعمل")
            .one_or_none()
        )
        if lesson is None:
            lesson = Lesson(
                module_id=module.id,
                title="القياس في الكيمياء وأدوات المعمل",
                kind=LessonKind.ARTICLE,
                position=1,
                content=(
                    "الكيمياء هي مركز العلوم. في هذا الدرس نتعرف على أدوات القياس المعملية "
                    "كالميزان الحساس والمخبار المدرج والسحاحة والماصة وأهمية القياس الدقيق في التجارب الكيميائية."
                ),
            )
            db.add(lesson)

        quiz = db.query(Quiz).filter(Quiz.course_id == course.id, Quiz.title == "اختبار الكيمياء — الوحدة الأولى").one_or_none()
        if quiz is None:
            quiz = Quiz(
                institution_id=institution.id,
                course_id=course.id,
                creator_id=teacher.id,
                title="اختبار الكيمياء — الوحدة الأولى",
                status=QuizStatus.PUBLISHED,
                duration_seconds=600,
                attempts_allowed=2,
            )
            db.add(quiz)
            db.flush()

            q1_text = "ما هو العلم الذي يهتم بدراسة تركيب المادة وخواصها والتغيرات التي تطرأ عليها؟"
            if db.query(Question).filter(Question.prompt == q1_text).one_or_none() is None:
                q1 = Question(
                    institution_id=institution.id,
                    author_id=teacher.id,
                    course_id=course.id,
                    version=1,
                    question_type="mcq",
                    prompt=q1_text,
                    options=["الكيمياء", "الفيزياء", "الفلك", "الجيولوجيا"],
                    correct_answer="الكيمياء",
                    points=5,
                    learning_objective="units",
                )
                q2_text = "تُستخدم الماصة والسحاحة في معمل الكيمياء لإجراء عملية..."
                q2 = Question(
                    institution_id=institution.id,
                    author_id=teacher.id,
                    course_id=course.id,
                    version=1,
                    question_type="mcq",
                    prompt=q2_text,
                    options=["المعايرة", "الترشيح", "التبخير", "التسامي"],
                    correct_answer="المعايرة",
                    points=5,
                    learning_objective="units",
                )
                db.add_all([q1, q2])
                db.flush()
                db.add_all(
                    [
                        QuizQuestion(quiz_id=quiz.id, question_id=q1.id, position=1, points=5),
                        QuizQuestion(quiz_id=quiz.id, question_id=q2.id, position=2, points=5),
                    ]
                )

        enrollment = (
            db.query(Enrollment)
            .filter(Enrollment.course_id == course.id, Enrollment.student_id == student.id)
            .one_or_none()
        )
        if enrollment is None:
            db.add(
                Enrollment(
                    course_id=course.id,
                    student_id=student.id,
                    status=EnrollmentStatus.ACTIVE,
                )
            )

        event = (
            db.query(CalendarEvent)
            .filter(CalendarEvent.course_id == course.id, CalendarEvent.title == "بث مباشر: مراجعة الحركة")
            .one_or_none()
        )
        if event is None:
            db.add(
                CalendarEvent(
                    institution_id=institution.id,
                    creator_id=teacher.id,
                    course_id=course.id,
                    title="بث مباشر: مراجعة الحركة",
                    description="مراجعة شاملة قبل اختبار الوحدة.",
                    event_type="live",
                    starts_at=datetime.now(timezone.utc) + timedelta(days=2),
                    ends_at=datetime.now(timezone.utc) + timedelta(days=2, hours=1),
                )
            )

        notification = (
            db.query(Notification)
            .filter(Notification.recipient_id == student.id, Notification.dedup_key == "seed:welcome")
            .one_or_none()
        )
        if notification is None:
            db.add(
                Notification(
                    institution_id=institution.id,
                    recipient_id=student.id,
                    kind="announcement",
                    title="مرحبًا بك في المنصة 👋",
                    message="تم تسجيلك في مقرر الجيولوجيا. ابدأ من الوحدة الأولى الآن.",
                    dedup_key="seed:welcome",
                )
            )

        db.commit()
        print("Seed OK.")
        print(f"Institution : {DEMO_SLUG}")
        print(f"Teacher      : {TEACHER_EMAIL} / {DEMO_PASSWORD}")
        print(f"Student      : {STUDENT_EMAIL} / {DEMO_PASSWORD}")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
