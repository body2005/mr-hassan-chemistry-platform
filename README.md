# Educational LMS Platform

منصة تعليمية (LMS) تخدم الطلاب والمعلمين ومسؤولي المؤسسات وإدارة المنصة.
جاهزية النشر ليست معلنة: راجع نتائج الاختبارات والعوائق الحالية في
[`docs/QA_2026-10-08.md`](docs/QA_2026-10-08.md) قبل اعتماد أي إصدار.

## Components

| Path | Stack | Purpose |
|---|---|---|
| `apps/api` | FastAPI · SQLAlchemy · Alembic · Argon2id | Backend الأساسي: Auth، RBAC، Tenant isolation، Courses، Quizzes، Assignments، Grades، Notifications، Certificates، Reports، Analytics |
| `apps/web` | React 19 · TypeScript strict · Vite · Tailwind 4 | الواجهة: 18 views، RTL/LTR كامل، Dark mode، جلسات HttpOnly |
| `workers` | Celery · Redis | مهام خلفية: إشعارات مجدولة، تقارير، تحليلات |
| `infra` | Docker Compose · Nginx | Postgres+pgvector، Redis، SeaweedFS بواجهة S3، API، Worker، Web + إعدادات backup/restore |
| `docs` | Markdown | ARCHITECTURE · PRODUCTION_READINESS · API · SECURITY |

## Quick Start (development)

```bash
# Backend
cd apps/api
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt   # Windows
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# Frontend
cd apps/web
npm install
npm run dev          # http://localhost:5173

# Tests
cd apps/api && python -m pytest tests -q
```

## Production

اقرأ [`docs/PRODUCTION_DOCKER_RUNBOOK.md`](docs/PRODUCTION_DOCKER_RUNBOOK.md)
للأسرار والشبكات وHTTPS والتخزين. للتجارب المحلية المعزولة وأوامر الاختبار
والنسخ الاحتياطي/الاسترجاع، اتبع
[`docs/QA_ROLE_REPRODUCTION.md`](docs/QA_ROLE_REPRODUCTION.md).
المساران القديمان `infra/scripts/backup.sh` و`restore.sh` أصبحا يرفضان التشغيل
بـExit64 دون لمس البيانات؛ لا يمثلان نسخًا احتياطيًا أو استرجاعًا ناجحًا.
استخدم المسار الموثّق لقالب SeaweedFS الحالي، ولا تسترجع فوق قاعدة موجودة.
لا تكفي نتيجة `docker compose config -q` أو بناء الصور لإعلان جاهزية النشر.

قواعد ثابتة: PostgreSQL هو مصدر الحقيقة للبيانات؛ رموز الجلسة ليست في
localStorage، والهوية تستخدم cookies محمية بـHttpOnly. التخزين المحلي للتفضيلات
وبعض المسودات ومعلومات العرض المخبأة، وليس مصدر الصلاحيات. كل صلاحية تُفحص على السيرفر
(Authentication → Role → Tenant → Ownership). الأخطاء بصيغة موحدة
`{error:{code,message}, request_id}`.

التوثيق الكامل في [`docs/`](docs/).
