"""Seven targeted real HTTPS/PostgreSQL checks, not the historical full suite.

Run in the Docker-enabled QA runner (not pytest under apps/api/conftest.py).
Requires QA_ISOLATED=true, QA_CANDIDATE_IMAGE (immutable ID), QA_REPOSITORY,
QA_HOST_SECRETS (host directory containing the local QA cert.pem/key.pem).
The disposable runner must use bridge mode, not Docker's exclusive none mode;
the application fixtures themselves are attached ONLY to the internal network.
Creates only UUID-named disposable fixtures on a new INTERNAL network, with
no published ports, no shared application data and no external SMTP delivery.
"""
import http.client
import io
import json
import os
from pathlib import Path
import secrets
import ssl
import tarfile
import time
import unittest
import uuid

import docker
import requests
import yaml


PG_IMAGE = 'pgvector/pgvector:pg16@sha256:ccc6e83d6e35e931dc7c5def2022729d5a6c370318d099181995567ff1fb4d6b'
REDIS_IMAGE = 'redis:7-alpine@sha256:ff02b58f971e7d7d156a1267e283fcbbeee91773b6aa36c49dac28ecfe28eadf'
MAIL_IMAGE = 'axllent/mailpit:v1.31.1@sha256:98b916bd3c8d61f7633a52d3ea2f58d00620cb01ca57ab59edde68c347a95365'
PASSWORD = 'synthetic-seven-password-123456'
SEED = r'''
import json, uuid
from datetime import datetime, timezone
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.institution import Institution
from app.models.user import User, UserRole
from app.models.course import Course, CourseStatus, CourseModule, Lesson, LessonKind, Enrollment
from app.models.platform import Question, Quiz, QuizStatus, QuizQuestion, QuizAttempt, AttemptStatus, QuizAttemptAnswer
from app.models.progress import LessonProgress
with SessionLocal() as db:
    inst = Institution(name='Seven isolated regressions', slug='seven-' + uuid.uuid4().hex[:10])
    db.add(inst); db.flush()
    users = {}
    for name in ['teacher', 'student', 'practice', 'essay']:
        row = User(institution_id=inst.id, username=name + uuid.uuid4().hex[:8],
            email=name + uuid.uuid4().hex[:8] + '@example.com', display_name=name,
            password_hash=hash_password('synthetic-seven-password-123456'),
            role=UserRole.TEACHER if name == 'teacher' else UserRole.STUDENT)
        db.add(row); db.flush(); users[name] = row
    courses, lessons = [], []
    for suffix in ['A', 'B']:
        course = Course(institution_id=inst.id, teacher_id=users['teacher'].id,
            title='Course ' + suffix, code=uuid.uuid4().hex[:8], status=CourseStatus.PUBLISHED)
        db.add(course); db.flush(); courses.append(course)
        module = CourseModule(course_id=course.id, title='Unit', position=1)
        db.add(module); db.flush()
        lesson = Lesson(module_id=module.id, title='Free', kind=LessonKind.VIDEO, position=1)
        db.add(lesson); db.flush(); lessons.append(lesson)
        for name in ['student', 'practice', 'essay']:
            db.add(Enrollment(course_id=course.id, student_id=users[name].id))
    paid = Lesson(module_id=lessons[0].module_id, title='Paid', kind=LessonKind.VIDEO, position=2, price_egp=50)
    db.add(paid); db.flush()
    db.add(LessonProgress(institution_id=inst.id, student_id=users['student'].id,
        lesson_id=lessons[0].id, completion_percent=100))
    quizzes, questions, snapshots = [], [], []
    for kind in ['mcq', 'essay']:
        q = Question(institution_id=inst.id, author_id=users['teacher'].id,
            course_id=courses[0].id, prompt='اختر الغاز الصحيح', question_type=kind,
            correct_answer='أ', options=['الهيدروجين', 'الأكسجين'], points=10)
        quiz = Quiz(institution_id=inst.id, course_id=courses[0].id, creator_id=users['teacher'].id,
            title='Frozen ' + kind, status=QuizStatus.PUBLISHED)
        db.add_all([q, quiz]); db.flush()
        snapshot = dict(question_id=str(q.id), question_version=1, question_type=kind,
            prompt=q.prompt, options=q.options, correct_answer=q.correct_answer, points=10,
            learning_objective=None, course_id=str(courses[0].id), origin='synthetic-frozen')
        db.add(QuizQuestion(quiz_id=quiz.id, question_id=q.id, position=1, points=10, question_snapshot=snapshot))
        quizzes.append(quiz); questions.append(q); snapshots.append(snapshot)
    for practice, score, number in [(False, 0, 1), (True, 10, 2)]:
        db.add(QuizAttempt(institution_id=inst.id, quiz_id=quizzes[0].id,
            student_id=users['practice'].id, attempt_number=number, status=AttemptStatus.SUBMITTED,
            score=score, total_points=10, is_practice=practice, started_at=datetime.now(timezone.utc),
            submitted_at=datetime.now(timezone.utc), question_snapshot=[snapshots[0]]))
    attempt = QuizAttempt(institution_id=inst.id, quiz_id=quizzes[1].id,
        student_id=users['essay'].id, attempt_number=1, status=AttemptStatus.SUBMITTED,
        score=0, total_points=10, started_at=datetime.now(timezone.utc),
        submitted_at=datetime.now(timezone.utc), question_snapshot=[snapshots[1]])
    db.add(attempt); db.flush()
    db.add(QuizAttemptAnswer(attempt_id=attempt.id, question_id=questions[1].id,
        answer='Student explanation', question_snapshot=snapshots[1], awarded_points=0, graded_at=None))
    questions[1].question_type = 'mcq'
    db.commit()
    print(json.dumps(dict(slug=inst.slug, users={k: dict(id=str(v.id), email=v.email) for k,v in users.items()},
        courses=[str(c.id) for c in courses], lessons=[str(l.id) for l in lessons], paid=str(paid.id),
        quizzes=[str(q.id) for q in quizzes], questions=[str(q.id) for q in questions], attempt=str(attempt.id))))
'''


class SevenLiveRegressions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.getenv('QA_ISOLATED') != 'true':
            raise RuntimeError('Explicit isolated runner required; no implicit skips')
        cls.client = docker.from_env()
        cls.containers, cls.network, cls.runner_connected = [], None, False
        cls.addClassCleanup(cls.cleanup)
        cls.prefix = 'qa-seven-' + uuid.uuid4().hex[:12]
        cls.network = cls.client.networks.create(cls.prefix, internal=True)
        cls.network.connect(os.environ['HOSTNAME'])
        cls.runner_connected = True
        cls.image = cls.client.images.get(os.environ['QA_CANDIDATE_IMAGE']).id
        cls.cert = os.environ['QA_CA_FILE']
        host_secrets = os.environ['QA_HOST_SECRETS'].replace('\\', '/')
        tls = {host_secrets + '/cert.pem': {'bind': '/qa-tls/cert.pem', 'mode': 'ro'},
               host_secrets + '/key.pem': {'bind': '/qa-tls/key.pem', 'mode': 'ro'}}
        cls.pg = cls.start(PG_IMAGE, 'db', environment={'POSTGRES_USER': 'seven',
            'POSTGRES_DB': 'seven', 'POSTGRES_PASSWORD': secrets.token_hex(24)},
            mem_limit='384m', tmpfs={'/var/lib/postgresql/data': 'rw,size=256m'})
        cls.start(REDIS_IMAGE, 'cache', command=['redis-server', '--save', '', '--appendonly', 'no'], mem_limit='128m')
        cls.start(MAIL_IMAGE, 'mailpit', environment={'MP_SMTP_TLS_CERT': '/qa-tls/cert.pem',
            'MP_SMTP_TLS_KEY': '/qa-tls/key.pem', 'MP_SMTP_REQUIRE_TLS': 'true',
            'MP_SMTP_AUTH_ACCEPT_ANY': 'true', 'MP_SMTP_DISABLE_RDNS': 'true'}, volumes=tls, mem_limit='128m')
        for _ in range(100):
            if cls.pg.exec_run(['pg_isready', '-U', 'seven', '-d', 'seven']).exit_code == 0:
                break
            time.sleep(0.2)
        else:
            raise RuntimeError('Isolated PostgreSQL did not become ready')
        # Read the real production template's default, not a test-only true override.
        template = yaml.safe_load((Path(os.environ['QA_REPOSITORY']) / 'infra/docker-compose.yml').read_text())
        flag = template['x-api-env']['EMAIL_ENABLED']
        if flag != '${EMAIL_ENABLED:-true}':
            raise AssertionError('Production SMTP feature default is not enabled')
        db_password = next(v.split('=', 1)[1] for v in cls.pg.attrs['Config']['Env'] if v.startswith('POSTGRES_PASSWORD='))
        env = dict(APP_ENV='production', SECRET_KEY=secrets.token_hex(32),
            DATABASE_URL=f'postgresql+psycopg://seven:{db_password}@db:5432/seven',
            REDIS_URL='redis://cache:6379/0', REDIS_REQUIRED='true',
            EMAIL_ENABLED=flag.removeprefix('${EMAIL_ENABLED:-').removesuffix('}'),
            SMTP_HOST='mailpit', SMTP_PORT='1025', SMTP_USER='synthetic-mailer',
            SMTP_PASSWORD=secrets.token_hex(24), SMTP_FROM_EMAIL='qa@example.com',
            SMTP_TLS_VERIFY='true', SSL_CERT_FILE='/qa-tls/cert.pem',
            FRONTEND_ORIGINS='https://proxy:8000', COOKIE_SECURE='true',
            PAYMENT_BANK_DETAILS='Synthetic destination only', STORAGE_BACKEND='local',
            STORAGE_DIR='/tmp/seven-storage', INGESTION_BACKEND='celery', ALLOW_LOCAL_INGESTION='false')
        cls.api = cls.start(cls.image, 'proxy', entrypoint='/bin/sh',
            command=['-ec', 'alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 '
                '--ssl-certfile /qa-tls/cert.pem --ssl-keyfile /tmp/qa-key.pem'],
            environment=env, volumes={host_secrets + '/cert.pem': tls[host_secrets + '/cert.pem']},
            secure_key=True, mem_limit='768m', cap_drop=['ALL'], security_opt=['no-new-privileges'])
        cls.base = 'https://proxy:8000/api/v1'
        for _ in range(120):
            try:
                if requests.get(cls.base + '/health', verify=cls.cert, timeout=2).status_code == 200:
                    break
            except requests.RequestException:
                pass
            cls.api.reload()
            if cls.api.status == 'exited':
                raise RuntimeError('Candidate exited before readiness: ' + cls.api.logs(tail=30).decode())
            time.sleep(0.25)
        else:
            raise RuntimeError('Candidate HTTPS API did not become ready')
        cls.data = cls.execute(SEED)
        cls.pg_version = cls.pg.exec_run(['postgres', '--version']).output.decode().strip()
        print(json.dumps({'candidate_image': cls.image, 'postgres': cls.pg_version,
                          'network': cls.prefix, 'published_ports': [], 'email_default': True}))

    @classmethod
    def start(cls, image, alias, secure_key=False, **kwargs):
        container = cls.client.containers.create(image, name=cls.prefix + '-' + alias,
            network=cls.network.name, **kwargs)
        cls.containers.append(container)
        if secure_key:
            # Do not chmod the host's key or run the application as root.
            # Copy only the LOCAL QA key into this disposable fixture, owned
            # by the production API UID, then remove it with the fixture.
            data = Path(cls.cert).with_name('key.pem').read_bytes()
            archive = io.BytesIO()
            with tarfile.open(fileobj=archive, mode='w') as tar:
                info = tarfile.TarInfo('qa-key.pem')
                info.size, info.mode, info.uid, info.gid = len(data), 0o400, 10001, 10001
                tar.addfile(info, io.BytesIO(data))
            container.put_archive('/tmp', archive.getvalue())
        cls.network.disconnect(container)
        cls.network.connect(container, aliases=[alias])
        container.start()
        return container

    @classmethod
    def execute(cls, source):
        result = cls.api.exec_run(['python', '-c', source])
        if result.exit_code:
            raise AssertionError(result.output.decode())
        return json.loads(result.output)

    @classmethod
    def cleanup(cls):
        for container in reversed(cls.containers):
            container.remove(force=True, v=True)  # Only fixtures created by this run.
        if cls.network is not None:
            if cls.runner_connected:
                cls.network.disconnect(os.environ['HOSTNAME'])
            cls.network.remove()
        cls.client.close()

    def login(self, role):
        client = requests.Session()
        self.addCleanup(client.close)
        client.verify = self.cert
        client.headers['Origin'] = 'https://proxy:8000'
        response = client.post(self.base + '/auth/login', timeout=10, json=dict(
            email=self.data['users'][role]['email'], password=PASSWORD, institution_slug=self.data['slug']))
        self.assertEqual(response.status_code, 200, response.text)
        client.headers['X-CSRF-Token'] = client.cookies['matgar_csrf']
        return client

    def test_1_correct_arabic_key_equals_option_text(self):
        client = self.login('student')
        quiz, question = self.data['quizzes'][0], self.data['questions'][0]
        response = client.get(self.base + f'/quizzes/{quiz}/solve', timeout=10)
        self.assertEqual(response.status_code, 200, response.text)
        attempt = response.json()['attempt']['id']
        response = client.post(self.base + f'/quiz-attempts/{attempt}/submit', timeout=10,
            json={'submission_key': uuid.uuid4().hex, 'answers': [{'question_id': question, 'answer': 'الهيدروجين'}]})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['score'], 10)
        response = client.get(self.base + f'/quizzes/{quiz}/result', timeout=10)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['questions'][0]['student_answer_letter'], 0)
        self.assertEqual(response.json()['questions'][0]['correct_answer_letter'], 0)

    def student_row(self, client, name):
        response = client.get(self.base + '/users', timeout=10)
        self.assertEqual(response.status_code, 200, response.text)
        return next(row for row in response.json() if row['id'] == self.data['users'][name]['id'])

    def test_2_practice_not_in_official_average(self):
        row = self.student_row(self.login('teacher'), 'practice')
        self.assertEqual(row['average_quiz_score'], 0)
        self.assertEqual(row['quiz_attempts_count'], 1)

    def test_3_edited_bank_does_not_hide_pending_essay(self):
        client = self.login('teacher')
        row = self.student_row(client, 'essay')
        self.assertEqual(row['pending_quiz_attempts'], 1)
        self.assertIsNone(row['average_quiz_score'])
        response = client.post(self.base + f'/quiz-attempts/{self.data["attempt"]}/answers/{self.data["questions"][1]}/grade',
            json={'awarded_points': 7}, timeout=10)
        self.assertEqual(response.status_code, 200, response.text)
        row = self.student_row(client, 'essay')
        self.assertEqual(row['pending_quiz_attempts'], 0)
        self.assertEqual(row['average_quiz_score'], 70)

    def test_4_progress_does_not_cross_course_boundary(self):
        client = self.login('teacher')
        first = client.get(self.base + f'/analytics/courses/{self.data["courses"][0]}', timeout=10)
        second = client.get(self.base + f'/analytics/courses/{self.data["courses"][1]}', timeout=10)
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(first.json()['average_completion_percent'], 100)
        self.assertEqual(second.json()['average_completion_percent'], 0)
        self.assertEqual(second.json()['completed_lessons'], 0)

    def test_5_anonymous_upload_denied_before_sending_body(self):
        paths = ['/lessons/{id}/video', '/lessons/{id}/materials',
            '/assignments/{id}/submissions/file', '/payments/orders/{id}/receipt', '/quiz/extract-from-file']
        for path in paths:
            with self.subTest(path=path):
                connection = http.client.HTTPSConnection('proxy', 8000, timeout=5,
                    context=ssl.create_default_context(cafile=self.cert))
                try:
                    connection.putrequest('POST', '/api/v1' + path.format(id=uuid.uuid4()))
                    connection.putheader('Content-Type', 'multipart/form-data; boundary=qa')
                    connection.putheader('Content-Length', '1048576')
                    connection.endheaders()  # Deliberately send zero body bytes.
                    self.assertEqual(connection.getresponse().status, 401)
                finally:
                    connection.close()

    def test_6_paid_progress_denied_then_allowed_after_entitlement(self):
        client = self.login('student')
        paid = self.data['paid']
        url = self.base + '/telemetry/video-events'
        def events():
            return {'events': [{'lesson_id': paid, 'client_event_id': uuid.uuid4().hex,
                'event_type': 'ended', 'position_seconds': 100, 'duration_seconds': 100}]}
        response = client.post(url, json=events(), timeout=10)
        self.assertEqual(response.status_code, 403, response.text)
        response = client.post(self.base + f'/progress/lessons/{paid}/complete', timeout=10)
        self.assertEqual(response.status_code, 403, response.text)
        result = self.execute('''
import json, uuid
from datetime import datetime, timezone
from sqlalchemy import select, func
from app.core.database import SessionLocal
from app.models.progress import LessonProgress, VideoEvent
from app.models.payment import StudentEntitlement, EntitlementType
from app.models.user import User
with SessionLocal() as db:
    student = db.get(User, uuid.UUID(%r))
    paid = uuid.UUID(%r)
    counts = [db.scalar(select(func.count()).select_from(model).where(model.lesson_id == paid)) for model in [LessonProgress, VideoEvent]]
    db.add(StudentEntitlement(institution_id=student.institution_id, student_id=student.id,
        entitlement_type=EntitlementType.LESSON, resource_id=paid, starts_at=datetime(2020,1,1,tzinfo=timezone.utc)))
    db.commit()
    print(json.dumps(counts))
''' % (self.data['users']['student']['id'], paid))
        self.assertEqual(result, [0, 0])
        response = client.post(url, json=events(), timeout=10)
        self.assertEqual(response.status_code, 202, response.text)
        self.assertEqual(response.json()['accepted'], 1)
        response = client.post(self.base + f'/progress/lessons/{paid}/complete', timeout=10)
        self.assertEqual(response.status_code, 200, response.text)

    def test_7_production_mail_default_delivers_to_local_tls_sink(self):
        response = requests.get(self.base + '/auth/features', verify=self.cert, timeout=10)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['password_reset_enabled'])
        response = requests.post(self.base + '/auth/password-reset/request', verify=self.cert,
            json={'email': self.data['users']['student']['email'], 'institution_slug': self.data['slug']}, timeout=10)
        self.assertEqual(response.status_code, 200, response.text)
        for _ in range(80):
            response = requests.get('http://mailpit:8025/api/v1/messages', timeout=5)
            self.assertEqual(response.status_code, 200)
            if response.json()['total'] == 1:
                message = response.json()['messages'][0]
                self.assertEqual(message['To'][0]['Address'], self.data['users']['student']['email'])
                return
            time.sleep(0.25)
        self.fail('Production reset request did not reach the isolated TLS mail sink')


if __name__ == '__main__':
    unittest.main(verbosity=2)
