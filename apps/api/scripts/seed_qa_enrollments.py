"""Idempotent large-catalog fixture, ONLY for the explicit local QA project.

Creates synthetic course/enrollment rows, not images, files, real accounts or
mail. Backdated course metadata keeps the new journey's own course selectable.
"""
from datetime import datetime, timedelta, timezone
import json
import os
import uuid

from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.models.course import Course, CourseStatus, Enrollment, EnrollmentStatus
from app.models.institution import Institution
from app.models.user import User, UserRole


def seed(db):
    inst = db.scalar(select(Institution).where(Institution.slug == 'demo'))
    assert inst is not None, 'Seed the isolated demo institution first'
    users = list(db.scalars(select(User).where(User.institution_id == inst.id,
        User.email.in_(['teacher@demo.com', 'student03@demo.com']))))
    teacher = next((user for user in users if user.email == 'teacher@demo.com' and user.role == UserRole.TEACHER), None)
    student = next((user for user in users if user.email == 'student03@demo.com' and user.role == UserRole.STUDENT), None)
    assert teacher and student, 'Expected synthetic demo identities only'
    count = db.scalar(select(func.count(Course.id)).join(Enrollment, Enrollment.course_id == Course.id)
        .where(Course.institution_id == inst.id, Course.status == CourseStatus.PUBLISHED,
               Enrollment.student_id == student.id,
               Enrollment.status.in_([EnrollmentStatus.ACTIVE, EnrollmentStatus.COMPLETED]))) or 0
    created = max(0, 152 - count)
    past = datetime.now(timezone.utc) - timedelta(days=1)
    for _ in range(created):
        course_id = uuid.uuid4()
        db.add(Course(id=course_id, institution_id=inst.id, teacher_id=teacher.id,
            code='QAH-' + uuid.uuid4().hex[:24], title='Synthetic large catalog QA',
            status=CourseStatus.PUBLISHED, grade_level='SECONDARY_1', price_egp=0,
            published_at=past, created_at=past))
        db.add(Enrollment(course_id=course_id, student_id=student.id, status=EnrollmentStatus.ACTIVE))
    db.commit()
    return {'created': created, 'published_active_enrollments': count + created, 'minimum': 152}


def main():
    if os.getenv('QA_ISOLATED') != 'true' or os.getenv('QA_PROJECT') != 'chemistryaudit2':
        raise RuntimeError('Large-catalog fixtures require the explicit local chemistryaudit2 project')
    with SessionLocal() as db:
        result = seed(db)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
