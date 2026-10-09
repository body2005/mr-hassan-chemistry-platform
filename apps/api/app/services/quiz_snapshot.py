"""Server-only frozen content, version, rubric and objective.

These documents include answer keys: never return them directly to a student.
Legacy NULL attempts cannot be reconstructed from the current bank. Only NEW
attempts on legacy exams capture current content, with explicit provenance.
"""
from __future__ import annotations

import copy
from datetime import datetime, timezone
from types import SimpleNamespace
import uuid

from sqlalchemy import or_, select
from app.core.question_policy import validate_question_content
from app.models.extended import LearningObjective
from app.models.platform import Question, QuizQuestion


def capture_questions(db, quiz, rows, *, origin="publication") -> list[dict]:
    codes = {q.learning_objective for _, q in rows if q.learning_objective}
    objectives = db.scalars(select(LearningObjective).where(
        LearningObjective.institution_id == quiz.institution_id,
        LearningObjective.code.in_(codes),
        or_(LearningObjective.course_id == quiz.course_id, LearningObjective.course_id.is_(None)),
    )).all() if codes else []
    by_code = {}
    for objective in objectives:
        if objective.code not in by_code or objective.course_id == quiz.course_id:
            by_code[objective.code] = objective
    captured = []
    for link, question in rows:
        if link.question_snapshot is not None:
            captured.append(copy.deepcopy(link.question_snapshot))
            continue
        if question.institution_id != quiz.institution_id or question.course_id not in (None, quiz.course_id):
            raise ValueError("Quiz contains an unavailable question")
        validate_question_content(question, link.points)
        objective = by_code.get(question.learning_objective)
        captured.append(dict(
            question_id=str(question.id), question_version=question.version,
            question_type=question.question_type.strip().lower(), prompt=question.prompt.strip(),
            options=copy.deepcopy(question.options), correct_answer=copy.deepcopy(question.correct_answer),
            points=float(link.points), learning_objective=question.learning_objective,
            objective_id=str(objective.id) if objective else None,
            objective_title=objective.title if objective else None,
            course_id=str(quiz.course_id), origin=origin,
            captured_at=datetime.now(timezone.utc).isoformat(),
        ))
    return captured


def freeze_exam(db, quiz, *, origin="publication") -> list[dict]:
    rows = db.execute(select(QuizQuestion, Question).join(Question, Question.id == QuizQuestion.question_id)
        .where(QuizQuestion.quiz_id == quiz.id).order_by(QuizQuestion.position)
        .with_for_update(of=QuizQuestion)).all()
    if not rows:
        raise ValueError("A quiz must contain at least one valid question")
    captured = capture_questions(db, quiz, rows, origin=origin)
    for (link, _), snapshot in zip(rows, captured):
        if link.question_snapshot is None:
            link.question_snapshot = copy.deepcopy(snapshot)
    return captured


def question_rows(db, quiz, attempt=None):
    """Read view for explicit, field-whitelisted solve/result builders."""
    if attempt is not None:
        snapshots = attempt.question_snapshot
        if snapshots is None:
            return []  # Do not reinterpret historical question details.
    else:
        rows = db.execute(select(QuizQuestion, Question).join(Question, Question.id == QuizQuestion.question_id)
            .where(QuizQuestion.quiz_id == quiz.id).order_by(QuizQuestion.position)).all()
        snapshots = capture_questions(db, quiz, rows, origin="current-preview")
    result = []
    for item in snapshots:
        question = SimpleNamespace(**copy.deepcopy(item))
        question.id = uuid.UUID(item["question_id"])
        question.version = item["question_version"]
        result.append((SimpleNamespace(points=item["points"]), question))
    return result
