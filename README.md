# Educational LMS Platform

منصة تعليمية (LMS) متكاملة Production-Ready تخدم الطلاب والمعلمين ومسؤولي المؤسسات
وإدارة المنصة، مع طبقة ذكاء اصطناعي منفصلة (توليد اختبارات، تصحيح مقالي، مساعد
تعليمي grounded، تحليلات مخاطر).

## Components

| Path | Stack | Purpose |
|---|---|---|
| `apps/api` | FastAPI · SQLAlchemy · Alembic · Argon2id | Backend الأساسي: Auth، RBAC، Tenant isolation، Courses، Quizzes، Assignments، Grades، Notifications، Certificates، AI jobs، Reports، Analytics |
| `apps/ai-service` | FastAPI · Ollama/Groq adapters · scikit-learn | طبقة الذكاء: quiz generation، essay grading بـrubrics، RAG tutor، risk ML |
| `apps/web` | React 19 · TypeScript strict · Vite · Tailwind 4 | الواجهة: 18 views، RTL/LTR كامل، Dark mode، جلسات HttpOnly |
| `workers` | Celery · Redis | مهام خلفية: AI، إشعارات مجدولة، تقارير، تحليلات |
| `infra` | Docker Compose · Nginx | Postgres+pgvector، Redis، MinIO، API، Worker، Web + سكربتات backup/restore |
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

```bash
cd infra
cp ../.env.example .env   # ثم املأ الأسرار الحقيقية
docker compose up --build
# Backup يومي
./scripts/backup.sh
```

قواعد ثابتة: PostgreSQL هو مصدر الحقيقة الوحيد للبيانات؛ localStorage في المتصفح
يُستخدم فقط للثيم واللغة وتفضيلات الواجهة. كل صلاحية تُفحص على السيرفر
(Authentication → Role → Tenant → Ownership). الأخطاء بصيغة موحدة
`{error:{code,message}, request_id}`.

التوثيق الكامل في [`docs/`](docs/).
