import uuid,secrets,hashlib
from datetime import datetime,timedelta,timezone
from sqlalchemy import select,func
from app import models
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.core.storage import get_storage_provider
from app.models.institution import Institution
from app.models.user import User,UserRole
from app.models.course import Course,CourseModule,Lesson,CourseStatus,LessonKind,Enrollment,EnrollmentStatus
from app.models.platform import RefreshSession,Notification,CalendarEvent

def identity(label):return uuid.uuid5(uuid.NAMESPACE_DNS,'chemistry-reliability-staging-'+label)
if get_settings().app_env!='staging' or '@postgres:5432/staging' not in get_settings().database_url:
    raise RuntimeError('Only an isolated staging database can be seeded')
now=datetime.now(timezone.utc)
with SessionLocal() as db:
    if db.scalar(select(Institution.id)):
        raise RuntimeError('Only seed an empty isolated database')
    institution=Institution(id=identity('institution'),slug='reliability-staging',name='Isolated Staging')
    db.add(institution);db.flush()
    password=hash_password(secrets.token_hex(32))
    users=[]
    for i in range(512):
        role=UserRole.STUDENT if i<511 else UserRole.TEACHER
        user=User(id=identity('user-'+str(i)),institution_id=institution.id,username='stage-'+str(i),
            email=f'stage-{i}@example.com',display_name='Synthetic Student',role=role,
            grade_level='SECONDARY_1' if role==UserRole.STUDENT else None,password_hash=password)
        db.add(user);users.append(user)
    db.flush()
    for i,user in enumerate(users):
        db.add(RefreshSession(user_id=user.id,family_id=identity('family-'+str(i)),jti=uuid.uuid4().hex,
            token_hash=hashlib.sha256(secrets.token_bytes(32)).hexdigest(),expires_at=now+timedelta(hours=6)))
    for n in range(3):
        course=Course(id=identity('course-'+str(n)),institution_id=institution.id,teacher_id=users[-1].id,
            code='STAGE-'+str(n),title='Synthetic course '+str(n),status=CourseStatus.PUBLISHED,
            grade_level='SECONDARY_1',price_egp=0,published_at=now)
        db.add(course);db.flush()
        module=CourseModule(course_id=course.id,title='Unit',position=1);db.add(module);db.flush()
        for j in range(10):
            db.add(Lesson(course_id=course.id,module_id=module.id,title='Synthetic lesson '+str(j),
                kind=LessonKind.ARTICLE,content='Synthetic private lesson body',position=j+1,price_egp=50,publication_status='published',
                publish_at=now-timedelta(hours=1),announce_to_students=False))
        for user in users[:500]:db.add(Enrollment(course_id=course.id,student_id=user.id,status=EnrollmentStatus.ACTIVE))
        for j in range(4):
            db.add(CalendarEvent(institution_id=institution.id,creator_id=users[-1].id,course_id=course.id,
                title='Synthetic scheduled activity',event_type='live',starts_at=now+timedelta(days=j+1),is_published=True))
    for user in users[:500]:
        for j in range(10):db.add(Notification(institution_id=institution.id,recipient_id=user.id,
            kind='announcement',title='Synthetic notice '+str(j),message='Staging only'))
    db.commit()
provider=get_storage_provider();client=provider._get_client()
if provider.bucket_name not in [b['Name'] for b in client.list_buckets()['Buckets']]:
    client.create_bucket(Bucket=provider.bucket_name)
print('Seeded staging only:512 users,3 courses,30 visible paid text lessons,12 events,5000 notices; no real data')
