"""Authenticated course cards expose names and locks, never assessment content."""
from sqlalchemy import select
from app.models.platform import Quiz, Assignment
from app.models.course import Lesson
from app.schemas import AssessmentCatalogSummary
from app.services.content_access import assessment_started


def assessment_catalog(db, user, courses, lessons, course_entitlements, lesson_entitlements):
    by_course = {course.id: course for course in courses}
    visible = {lesson.id: lesson for lesson in lessons}
    result = {course.id: [] for course in courses}
    if not courses:
        return result
    # Unit scopes include unavailable siblings too. Do not silently shrink a
    # mixed unit to its visible/free lessons and suggest that it is unlocked.
    unit_lessons = list(db.execute(select(Lesson.id, Lesson.course_id, Lesson.module_id)
        .where(Lesson.course_id.in_(by_course))))
    for kind, model in [('quiz', Quiz), ('assignment', Assignment)]:
        items = db.scalars(select(model).where(model.course_id.in_(by_course),
            model.institution_id == user.institution_id, model.status == 'published').order_by(model.created_at.desc()))
        for item in items:
            # Keep publication timing and unpublished lesson scopes sealed.
            if not assessment_started(item):
                continue
            required = set(item.lesson_ids) | {lesson.id for lesson in unit_lessons
                if lesson.course_id == item.course_id and lesson.module_id in item.module_ids}
            course_visible = {lesson.id for lesson in lessons if lesson.course_id == item.course_id}
            if not required or not required.issubset(course_visible):
                continue
            course = by_course[item.course_id]
            needs_purchase = course.id not in course_entitlements and any(
                lid not in lesson_entitlements and
                (float(course.price_egp or 0) > 0 or float(visible[lid].price_egp or 0) > 0)
                for lid in required)
            result[item.course_id].append(AssessmentCatalogSummary(id=item.id, kind=kind,
                title=item.title, lesson_ids=sorted(required, key=str), requires_purchase=needs_purchase))
    return result
