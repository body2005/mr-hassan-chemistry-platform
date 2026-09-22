from __future__ import annotations

import os
import secrets
import uuid
from datetime import datetime, timezone, timedelta
UTC = timezone.utc

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.course import Course, CourseModule, Enrollment, EnrollmentStatus
from app.models.platform import (
    Assignment,
    AssignmentAttempt,
    AssignmentAttemptStatus,
    AssignmentStatus,
    AssignmentSubmission,
    AttemptStatus,
    CalendarEvent,
    Certificate,
    DeliveryStatus,
    Notification,
    Question,
    Quiz,
    QuizAttempt,
    QuizAttemptAnswer,
    QuizQuestion,
    QuizStatus,
    SubmissionStatus,
)
from app.models.progress import LessonProgress
from app.models.user import User, UserRole
from app.schemas import (
    AssignmentCreateRequest,
    AssignmentSubmissionCreateRequest,
    CalendarEventCreateRequest,
    GradeSubmissionRequest,
    LessonCreateRequest,
    ModuleCreateRequest,
    NotificationBroadcastRequest,
    NotificationCreateRequest,
    QuestionCreateRequest,
    QuizAnswerInput,
    QuizAttemptSubmitRequest,
    QuizCreateRequest,
)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def course_for_user(db: Session, user: User, course_id: uuid.UUID) -> Course:
    query = select(Course).where(Course.id == course_id)
    if user.role != UserRole.PLATFORM_ADMIN:
        query = query.where(Course.institution_id == user.institution_id)
    course = db.scalar(query)
    if course is None:
        raise LookupError("Course not found")
    return course


def ensure_course_manager(user: User, course: Course) -> None:
    if user.role not in {
        UserRole.TEACHER,
        UserRole.INSTITUTION_ADMIN,
        UserRole.PLATFORM_ADMIN,
    }:
        raise PermissionError("Insufficient permissions")
    if user.role != UserRole.PLATFORM_ADMIN and course.institution_id != user.institution_id:
        raise PermissionError("You do not have access to this institution's courses")
    if user.role == UserRole.TEACHER and course.teacher_id != user.id:
        raise PermissionError("Teachers can manage only their own courses")


def add_module(
    db: Session, user: User, course_id: uuid.UUID, payload: ModuleCreateRequest
) -> CourseModule:
    course = course_for_user(db, user, course_id)
    ensure_course_manager(user, course)
    module = CourseModule(
        course_id=course.id, title=payload.title.strip(), position=payload.position
    )
    db.add(module)
    db.commit()
    db.refresh(module)
    return module


def add_lesson(db: Session, user: User, module_id: uuid.UUID, payload: LessonCreateRequest):
    module = db.scalar(
        select(CourseModule)
        .join(Course)
        .where(
            CourseModule.id == module_id,
            Course.institution_id == user.institution_id
            if user.role != UserRole.PLATFORM_ADMIN
            else CourseModule.id == module_id,
        )
    )
    if module is None:
        raise LookupError("Module not found")
    course = db.get(Course, module.course_id)
    if course is None:
        raise LookupError("Course not found")
    ensure_course_manager(user, course)
    from app.models.course import Lesson

    lesson = Lesson(
        module_id=module.id,
        title=payload.title.strip(),
        kind=payload.kind,
        position=payload.position,
        content=payload.content.strip() if payload.content else None,
        # Native videos are attached only through the protected upload
        # endpoint; the create payload can never plant a storage key.
        video_duration_seconds=payload.video_duration_seconds,
        price_egp=payload.price_egp,
    )
    db.add(lesson)
    db.commit()
    db.refresh(lesson)
    return lesson


def delete_lesson(db: Session, user: User, module_id: uuid.UUID, lesson_id: uuid.UUID) -> None:
    from app.models.course import Lesson
    from app.models.transcript import Transcript, TranscriptSegment, TranscriptionJob
    from app.models.progress import LessonProgress, VideoEvent
    from app.models.extended import LessonAsset

    lesson = db.scalar(select(Lesson).where(Lesson.id == lesson_id, Lesson.module_id == module_id))
    if lesson is None:
        raise LookupError("Lesson not found")
    module = db.get(CourseModule, module_id)
    if module is None:
        raise LookupError("Module not found")
    course = db.get(Course, module.course_id)
    if course is None:
        raise LookupError("Course not found")
    ensure_course_manager(user, course)

    # 1. Clean up associated video file if stored locally
    if lesson.video_asset_key and lesson.video_asset_key.startswith("/static/uploads/"):
        filename = os.path.basename(lesson.video_asset_key)
        upload_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "uploads")
        filepath = os.path.join(upload_dir, filename)
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception:
                pass

    # 2. Clean up all child relational entities
    db.query(TranscriptSegment).filter(TranscriptSegment.lesson_id == lesson_id).delete()
    db.query(Transcript).filter(Transcript.lesson_id == lesson_id).delete()
    db.query(TranscriptionJob).filter(TranscriptionJob.lesson_id == lesson_id).delete()
    db.query(LessonProgress).filter(LessonProgress.lesson_id == lesson_id).delete()
    db.query(LessonAsset).filter(LessonAsset.lesson_id == lesson_id).delete()
    db.query(VideoEvent).filter(VideoEvent.lesson_id == lesson_id).delete()

    # 3. Delete the lesson record
    db.delete(lesson)
    db.commit()


def _enrolled(db: Session, user: User, course_id: uuid.UUID) -> bool:
    return (
        db.scalar(
            select(Enrollment.id).where(
                Enrollment.course_id == course_id,
                Enrollment.student_id == user.id,
                Enrollment.status.in_([EnrollmentStatus.ACTIVE, EnrollmentStatus.COMPLETED]),
            )
        )
        is not None
    )


def create_question(db: Session, user: User, payload: QuestionCreateRequest) -> Question:
    if user.role == UserRole.TEACHER and payload.course_id:
        course = course_for_user(db, user, payload.course_id)
        ensure_course_manager(user, course)
    question = Question(
        institution_id=user.institution_id,
        author_id=user.id,
        course_id=payload.course_id,
        question_type=payload.question_type.strip().lower(),
        prompt=payload.prompt.strip(),
        options=payload.options,
        correct_answer=payload.correct_answer,
        points=payload.points,
        learning_objective=payload.learning_objective,
    )
    db.add(question)
    db.commit()
    db.refresh(question)
    return question


def create_quiz(db: Session, user: User, payload: QuizCreateRequest) -> Quiz:
    course = course_for_user(db, user, payload.course_id)
    ensure_course_manager(user, course)
    quiz = Quiz(
        institution_id=course.institution_id,
        course_id=course.id,
        creator_id=user.id,
        title=payload.title.strip(),
        duration_seconds=payload.duration_seconds,
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
        randomize_questions=payload.randomize_questions,
        attempts_allowed=payload.attempts_allowed,
    )
    db.add(quiz)
    db.flush()
    if payload.question_ids:
        questions = list(
            db.scalars(
                select(Question).where(
                    Question.id.in_(payload.question_ids),
                    Question.institution_id == course.institution_id,
                    Question.is_active.is_(True),
                )
            ).all()
        )
        if len(questions) != len(set(payload.question_ids)):
            db.rollback()
            raise ValueError("One or more questions are unavailable")
        for position, question in enumerate(questions, start=1):
            db.add(
                QuizQuestion(
                    quiz_id=quiz.id,
                    question_id=question.id,
                    position=position,
                    points=question.points,
                )
            )
    db.commit()
    db.refresh(quiz)
    return quiz


def publish_quiz(db: Session, user: User, quiz_id: uuid.UUID) -> Quiz:
    quiz = db.scalar(
        select(Quiz).where(Quiz.id == quiz_id, Quiz.institution_id == user.institution_id)
    )
    if quiz is None:
        raise LookupError("Quiz not found")
    course = db.get(Course, quiz.course_id)
    if course is None:
        raise LookupError("Course not found")
    ensure_course_manager(user, course)
    quiz.status = QuizStatus.PUBLISHED
    quiz.published_at = datetime.now(UTC)
    db.commit()
    db.refresh(quiz)
    return quiz


def start_quiz(db: Session, user: User, quiz_id: uuid.UUID) -> QuizAttempt:
    quiz = db.scalar(
        select(Quiz).where(
            Quiz.id == quiz_id,
            Quiz.institution_id == user.institution_id,
            Quiz.status == QuizStatus.PUBLISHED,
        )
    )
    if quiz is None or not _enrolled(db, user, quiz.course_id):
        raise LookupError("Quiz not found")
    now = datetime.now(UTC)
    if _as_utc(quiz.starts_at) and _as_utc(quiz.starts_at) > now:
        raise PermissionError("Quiz is not open yet")
    if _as_utc(quiz.ends_at) and _as_utc(quiz.ends_at) <= now:
        raise PermissionError("Quiz is closed")
    active = db.scalar(
        select(QuizAttempt).where(
            QuizAttempt.quiz_id == quiz.id,
            QuizAttempt.student_id == user.id,
            QuizAttempt.status == AttemptStatus.IN_PROGRESS,
        )
    )
    if active:
        if _as_utc(active.expires_at) and _as_utc(active.expires_at) <= now:
            active.status = AttemptStatus.EXPIRED
            db.commit()
        else:
            return active
    attempt_number = (
        db.scalar(
            select(func.max(QuizAttempt.attempt_number)).where(
                QuizAttempt.quiz_id == quiz.id, QuizAttempt.student_id == user.id
            )
        )
        or 0
    ) + 1
    if attempt_number > quiz.attempts_allowed:
        raise PermissionError("Attempt limit reached")
    expires_at = now + timedelta(seconds=quiz.duration_seconds) if quiz.duration_seconds else None
    attempt = QuizAttempt(
        institution_id=user.institution_id,
        quiz_id=quiz.id,
        student_id=user.id,
        attempt_number=attempt_number,
        started_at=now,
        expires_at=expires_at,
        total_points=db.scalar(
            select(func.sum(QuizQuestion.points)).where(QuizQuestion.quiz_id == quiz.id)
        )
        or 0,
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return attempt


def _answers_equal(answer: object, correct: object) -> bool:
    if isinstance(answer, str) and isinstance(correct, str):
        return answer.strip().casefold() == correct.strip().casefold()
    return answer == correct


def submit_quiz(
    db: Session, user: User, attempt_id: uuid.UUID, payload: QuizAttemptSubmitRequest
) -> QuizAttempt:
    attempt = db.scalar(
        select(QuizAttempt).where(
            QuizAttempt.id == attempt_id,
            QuizAttempt.student_id == user.id,
            QuizAttempt.institution_id == user.institution_id,
        )
    )
    if attempt is None:
        raise LookupError("Attempt not found")
    if attempt.status != AttemptStatus.IN_PROGRESS:
        return attempt
    now = datetime.now(UTC)
    if _as_utc(attempt.expires_at) and _as_utc(attempt.expires_at) <= now:
        attempt.status = AttemptStatus.EXPIRED
        db.commit()
        raise PermissionError("Attempt has expired")
    quiz_questions = list(
        db.scalars(select(QuizQuestion).where(QuizQuestion.quiz_id == attempt.quiz_id)).all()
    )
    allowed = {item.question_id: item.points for item in quiz_questions}
    answers_by_question: dict[uuid.UUID, QuizAnswerInput] = {}
    for answer in payload.answers:
        if answer.question_id not in allowed:
            raise ValueError("Answer contains a question outside this quiz")
        if answer.question_id in answers_by_question:
            raise ValueError("Duplicate question answer")
        answers_by_question[answer.question_id] = answer
    score = 0.0
    for question_id, points in allowed.items():
        input_answer = answers_by_question.get(question_id)
        question = db.get(Question, question_id)
        if question is None:
            continue
        awarded = (
            points
            if input_answer and _answers_equal(input_answer.answer, question.correct_answer)
            else 0.0
        )
        if question.question_type not in {"essay", "short_answer"}:
            score += awarded
        db.add(
            QuizAttemptAnswer(
                attempt_id=attempt.id,
                question_id=question_id,
                answer=input_answer.answer if input_answer else None,
                awarded_points=awarded,
                graded_at=now if question.question_type not in {"essay", "short_answer"} else None,
            )
        )
    attempt.submission_key = payload.submission_key
    attempt.status = AttemptStatus.SUBMITTED
    attempt.submitted_at = now
    attempt.score = score
    db.commit()
    db.refresh(attempt)
    return attempt


def create_assignment(db: Session, user: User, payload: AssignmentCreateRequest) -> Assignment:
    course = course_for_user(db, user, payload.course_id)
    ensure_course_manager(user, course)
    assignment = Assignment(
        institution_id=course.institution_id,
        course_id=course.id,
        creator_id=user.id,
        title=payload.title.strip(),
        prompt=payload.prompt.strip(),
        due_at=payload.due_at,
        max_score=payload.max_score,
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return assignment


def publish_assignment(db: Session, user: User, assignment_id: uuid.UUID) -> Assignment:
    assignment = db.scalar(
        select(Assignment).where(
            Assignment.id == assignment_id, Assignment.institution_id == user.institution_id
        )
    )
    if assignment is None:
        raise LookupError("Assignment not found")
    course = db.get(Course, assignment.course_id)
    if course is None:
        raise LookupError("Course not found")
    ensure_course_manager(user, course)
    assignment.status = AssignmentStatus.PUBLISHED
    db.commit()
    db.refresh(assignment)
    return assignment


def start_assignment(db: Session, user: User, assignment_id: uuid.UUID) -> AssignmentAttempt:
    assignment = db.scalar(
        select(Assignment).where(
            Assignment.id == assignment_id,
            Assignment.institution_id == user.institution_id,
            Assignment.status == AssignmentStatus.PUBLISHED,
        )
    )
    if assignment is None or not _enrolled(db, user, assignment.course_id):
        raise LookupError("Assignment not found")
    now = datetime.now(UTC)
    if _as_utc(assignment.due_at) and _as_utc(assignment.due_at) <= now:
        raise PermissionError("Assignment is closed")
    active = db.scalar(
        select(AssignmentAttempt).where(
            AssignmentAttempt.assignment_id == assignment.id,
            AssignmentAttempt.student_id == user.id,
            AssignmentAttempt.status == AssignmentAttemptStatus.IN_PROGRESS,
        )
    )
    if active:
        if _as_utc(active.expires_at) and _as_utc(active.expires_at) <= now:
            active.status = AssignmentAttemptStatus.EXPIRED
            db.commit()
        else:
            return active
    attempt_number = (
        db.scalar(
            select(func.max(AssignmentAttempt.attempt_number)).where(
                AssignmentAttempt.assignment_id == assignment.id,
                AssignmentAttempt.student_id == user.id,
            )
        )
        or 0
    ) + 1
    attempt = AssignmentAttempt(
        institution_id=user.institution_id,
        assignment_id=assignment.id,
        student_id=user.id,
        attempt_number=attempt_number,
        started_at=now,
        expires_at=assignment.due_at,
        status=AssignmentAttemptStatus.IN_PROGRESS,
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return attempt


def submit_assignment(
    db: Session, user: User, assignment_id: uuid.UUID, payload: AssignmentSubmissionCreateRequest
) -> AssignmentSubmission:
    assignment = db.scalar(
        select(Assignment).where(
            Assignment.id == assignment_id,
            Assignment.institution_id == user.institution_id,
            Assignment.status == AssignmentStatus.PUBLISHED,
        )
    )
    if assignment is None or not _enrolled(db, user, assignment.course_id):
        raise LookupError("Assignment not found")
    now = datetime.now(UTC)
    active_attempt = db.scalar(
        select(AssignmentAttempt).where(
            AssignmentAttempt.assignment_id == assignment.id,
            AssignmentAttempt.student_id == user.id,
            AssignmentAttempt.status == AssignmentAttemptStatus.IN_PROGRESS,
        )
    )
    if active_attempt and _as_utc(active_attempt.expires_at) and _as_utc(active_attempt.expires_at) <= now:
        active_attempt.status = AssignmentAttemptStatus.EXPIRED
        db.commit()
        raise PermissionError("Assignment attempt has expired")
    existing = db.scalar(
        select(AssignmentSubmission).where(
            AssignmentSubmission.assignment_id == assignment.id,
            AssignmentSubmission.student_id == user.id,
            AssignmentSubmission.idempotency_key == payload.idempotency_key,
        )
    )
    if existing:
        return existing
    version = (
        db.scalar(
            select(func.max(AssignmentSubmission.version)).where(
                AssignmentSubmission.assignment_id == assignment.id,
                AssignmentSubmission.student_id == user.id,
            )
        )
        or 0
    ) + 1
    submission = AssignmentSubmission(
        institution_id=user.institution_id,
        assignment_id=assignment.id,
        student_id=user.id,
        version=version,
        answer_text=payload.answer_text,
        object_key=payload.object_key,
        idempotency_key=payload.idempotency_key,
        submitted_at=now,
    )
    if active_attempt:
        active_attempt.status = AssignmentAttemptStatus.SUBMITTED
        active_attempt.submitted_at = now
    db.add(submission)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(
            select(AssignmentSubmission).where(
                AssignmentSubmission.assignment_id == assignment.id,
                AssignmentSubmission.student_id == user.id,
                AssignmentSubmission.idempotency_key == payload.idempotency_key,
            )
        )
        if existing is None:
            raise
        return existing
    db.refresh(submission)
    return submission


def grade_submission(
    db: Session, user: User, submission_id: uuid.UUID, payload: GradeSubmissionRequest
) -> AssignmentSubmission:
    submission = db.get(AssignmentSubmission, submission_id)
    if submission is None or submission.institution_id != user.institution_id:
        raise LookupError("Submission not found")
    assignment = db.get(Assignment, submission.assignment_id)
    if assignment is None:
        raise LookupError("Assignment not found")
    course = db.get(Course, assignment.course_id)
    if course is None:
        raise LookupError("Course not found")
    ensure_course_manager(user, course)
    if payload.final_score > assignment.max_score:
        raise ValueError("Score cannot exceed assignment maximum")
    now = datetime.now(UTC)
    submission.final_score = payload.final_score
    submission.teacher_feedback = payload.teacher_feedback
    submission.graded_by = user.id
    submission.graded_at = now
    submission.status = SubmissionStatus.APPROVED if payload.approve else SubmissionStatus.GRADED
    if payload.approve:
        submission.approved_at = now
    db.commit()
    db.refresh(submission)
    return submission


def create_notification(
    db: Session, user: User, payload: NotificationCreateRequest
) -> Notification:
    recipient = db.scalar(
        select(User).where(
            User.id == payload.recipient_id,
            User.institution_id == user.institution_id,
            User.is_active.is_(True),
        )
    )
    if recipient is None:
        raise LookupError("Recipient not found")
    if payload.dedup_key:
        existing = db.scalar(
            select(Notification).where(
                Notification.institution_id == user.institution_id,
                Notification.recipient_id == recipient.id,
                Notification.dedup_key == payload.dedup_key,
            )
        )
        if existing:
            return existing
    notification = Notification(
        institution_id=user.institution_id,
        recipient_id=recipient.id,
        kind=payload.kind,
        title=payload.title.strip(),
        message=payload.message.strip(),
        action_url=payload.action_url,
        dedup_key=payload.dedup_key,
        scheduled_for=payload.scheduled_for,
        delivery_status=DeliveryStatus.PENDING,
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification


def broadcast_notification(
    db: Session, user: User, payload: NotificationBroadcastRequest
) -> list[Notification]:
    if user.role not in {
        UserRole.TEACHER,
        UserRole.INSTITUTION_ADMIN,
        UserRole.PLATFORM_ADMIN,
    }:
        raise PermissionError("Insufficient permissions")
    query = select(User).where(
        User.institution_id == user.institution_id,
        User.role == UserRole.STUDENT,
        User.is_active.is_(True),
        User.deleted_at.is_(None),
    )
    recipients = list(db.scalars(query).all())
    notifications: list[Notification] = []
    new_notifications: list[Notification] = []
    for recipient in recipients:
        dedup_key = f"{payload.dedup_key}:{recipient.id}" if payload.dedup_key else None
        existing = None
        if dedup_key:
            existing = db.scalar(
                select(Notification).where(
                    Notification.institution_id == user.institution_id,
                    Notification.recipient_id == recipient.id,
                    Notification.dedup_key == dedup_key,
                )
            )
        if existing:
            notifications.append(existing)
            continue
        notification = Notification(
            institution_id=user.institution_id,
            recipient_id=recipient.id,
            kind=payload.kind,
            title=payload.title.strip(),
            message=payload.message.strip(),
            action_url=payload.action_url,
            dedup_key=dedup_key,
            scheduled_for=payload.scheduled_for,
            delivery_status=DeliveryStatus.PENDING,
        )
        notifications.append(notification)
        new_notifications.append(notification)
    db.add_all(new_notifications)
    db.commit()
    for item in new_notifications:
        db.refresh(item)
    return notifications


def create_calendar_event(
    db: Session, user: User, payload: CalendarEventCreateRequest
) -> CalendarEvent:
    if payload.course_id:
        course = course_for_user(db, user, payload.course_id)
        ensure_course_manager(user, course)
    event = CalendarEvent(
        institution_id=user.institution_id,
        creator_id=user.id,
        course_id=payload.course_id,
        title=payload.title.strip(),
        description=payload.description,
        event_type=payload.event_type,
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
        is_published=payload.is_published,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def issue_certificate(db: Session, user: User, course_id: uuid.UUID) -> Certificate:
    course = course_for_user(db, user, course_id)
    if user.role == UserRole.STUDENT:
        student_id = user.id
        if not _enrolled(db, user, course.id):
            raise LookupError("Enrollment not found")
    else:
        raise PermissionError("Only students can issue their certificate")
    enrollment = db.scalar(
        select(Enrollment).where(
            Enrollment.course_id == course.id, Enrollment.student_id == student_id
        )
    )
    if enrollment is None:
        raise LookupError("Enrollment not found")
    if enrollment.status != EnrollmentStatus.COMPLETED and enrollment.progress_percent < 100:
        raise PermissionError("Complete all course lessons before issuing a certificate")
    existing = db.scalar(
        select(Certificate).where(
            Certificate.course_id == course.id, Certificate.student_id == student_id
        )
    )
    if existing:
        return existing
    certificate = Certificate(
        institution_id=user.institution_id,
        course_id=course.id,
        student_id=student_id,
        enrollment_id=enrollment.id,
        verification_token=secrets.token_urlsafe(48),
        score=enrollment.progress_percent,
        issued_at=datetime.now(UTC),
    )
    db.add(certificate)
    db.commit()
    db.refresh(certificate)
    return certificate


def course_analytics(db: Session, user: User, course_id: uuid.UUID) -> dict[str, object]:
    course = course_for_user(db, user, course_id)
    ensure_course_manager(user, course)
    enrolled_students = (
        db.scalar(select(func.count(Enrollment.id)).where(Enrollment.course_id == course.id)) or 0
    )
    progress_rows = list(
        db.execute(
            select(LessonProgress.completion_percent).join(
                Enrollment,
                (Enrollment.student_id == LessonProgress.student_id)
                & (Enrollment.course_id == course.id),
            )
        )
        .scalars()
        .all()
    )
    average = round(sum(progress_rows) / len(progress_rows), 2) if progress_rows else 0.0
    risk_score = max(0.0, min(1.0, 1 - average / 100))
    return {
        "course_id": course.id,
        "enrolled_students": enrolled_students,
        "completed_lessons": sum(1 for value in progress_rows if value >= 100),
        "average_completion_percent": average,
        "assignment_average_score": None,
        "quiz_average_score": None,
        "risk": {
            "score": round(risk_score, 3),
            "explanation": (
                "Based on server-side lesson completion; add assessment signals when available."
            ),
        },
    }
