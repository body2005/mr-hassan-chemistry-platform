# Deployment Guide — نشر المنصة للعميل

مساران حسب الميزانية والوقت. **المسار أ هو الأسرع لتجربة العميل اليوم**،
والمسار ب هو نفس شكل الإنتاج النهائي.

---

## المسار أ: نشر سحابي سريع (مجانًا تقريبًا، ~30 دقيقة)

### 1) قاعدة البيانات — Neon (Postgres مجاني)
1. أنشئ مشروعًا على [neon.tech](https://neon.tech) وانسخ الـconnection string.
2. حوّله لصيغة SQLAlchemy: `postgresql+asyncpg://user:pass@host/db?sslmode=require`

### 2) الباكند — Render (Web Service مجاني)
1. ارفع الكود على GitHub.
2. على [render.com](https://render.com): **New → Web Service** واختر المستودع.
3. الإعدادات:
   - Root Directory: `apps/api`
   - Build Command: `pip install -r requirements.txt`
   - Start Command:
     ```bash
     alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT
     ```
4. Environment Variables:
   | Key | Value |
   |---|---|
   | `APP_ENV` | `production` |
   | `SECRET_KEY` | قيمة عشوائية طويلة (`python -c "import secrets;print(secrets.token_urlsafe(48))"`) |
   | `DATABASE_URL` | رابط Neon من الخطوة 1 |
   | `FRONTEND_ORIGINS` | رابط الواجهة من الخطوة 3 (مهم للـCORS) |
   | `COOKIE_CROSS_SITE` | `true` — ضروري لأن الباكند والواجهة على دومينات مختلفة (بدونه المتصفح يرمي كوكي الجلسة والدخول لا يثبت) |

### 3) الواجهة — Vercel
1. **New Project** ← نفس المستودع، Root Directory: `apps/web`
2. Framework: Vite (يكتشفه تلقائيًا). Build: `npm run build`
3. Environment Variable: `VITE_API_URL = https://<your-api>.onrender.com/api/v1`
4. بعد أول Deploy انسخ الرابط وحدّث `FRONTEND_ORIGINS` في Render ثم أعد النشر.

### 4) بيانات التجربة
من جهازك محليًا (بعد ضبط `DATABASE_URL` برابط Neon):
```bash
cd apps/api && python scripts/seed_demo.py
```
أو مؤقتًا اجعل Start Command في Render:
`alembic upgrade head && python scripts/seed_demo.py && uvicorn ...`
ثم احذف السطر بعد أول تشغيل ناجح.

> ⚠️ حسابات seed للتجربة فقط — لا تستخدمها إنتاجًا فعليًا.

---

## المسار ب: خادم VPS مع Docker (شكل الإنتاج النهائي)

```bash
# على أي VPS (Ubuntu 22+) بعد تثبيت docker + docker compose plugin
git clone <your-repo> && cd learning-project/infra
cp ../.env.example .env    # ثم حرّر القيم الحقيقية كلها

docker compose up --build -d
docker compose exec api alembic upgrade head
docker compose exec api python scripts/seed_demo.py   # اختياري للتجربة

# الموقع: http://SERVER_IP (nginx يخدم الواجهة ويحوّل /api للباكند)
```
لـHTTPS (ضروري قبل عملاء حقيقيين): ضع الدومين وأضف Caddy أو certbot أمام nginx.

---

## ✅ Checklist قبل تسليم الرابط للعميل

| # | البند | كيف تتحقق |
|---|---|---|
| 1 | `SECRET_KEY` حقيقي غير الافتراضي | التطبيق يرفض الإقلاع في production بقيمة default |
| 2 | `APP_ENV=production` | الكوكيز تصبح `Secure` + HSTS headers |
| 3 | الموقع يعمل على **HTTPS** | Render/Vercel يوفرونه تلقائيًا؛ VPS يحتاج إعداد يدوي |
| 4 | `FRONTEND_ORIGINS` = دومين الواجهة بالضبط | Login من الواجهة يعمل بلا أخطاء CORS في console |
| 5 | قاعدة بيانات **Postgres وليست SQLite** | متحقق تلقائيًا في المسارين أعلاه |
| 6 | Migrations طبّقت | `alembic upgrade head` ضمن أمر التشغيل |
| 7 | Seed اشتغل وبيانات تجريبية ظاهرة | سجّل دخول بحساب الطالب وشوف الكورس |
| 8 | اختبار دخول كامل من متصفح | login كطالب → كورس → درس → quiz → submit |

## 🧪 حسابات التجربة الجاهزة

| الدور | البريد | كلمة المرور |
|---|---|---|
| معلم | `teacher@demo.com` | `Demo-Pass-2026!` |
| طالب | `student@demo.com` | `Demo-Pass-2026!` |

المؤسسة: `demo` — فيها مقرر فيزياء منشور بوحدة ودرس واختبار MCQ مسجل به الطالب.

## ما لن يعمل في المعاينة السحابية (متوقع)

- **توليد الاختبارات بالذكاء الاصطناعي وتصحيح المقالات**: تحتاج Ollama/Groq.
  على Render المجاني أضف `GROQ_API_KEY` كمتغير بيئة لو متاح، وإلا ستظهر رسالة
  خطأ صريحة (بلا silent fallback — هذا مقصود أمنيًا). باقي المنصة يعمل كامل.
- الفيديوهات المرفوعة تحتاج MinIO/S3 (متوفر في المسار ب فقط).
