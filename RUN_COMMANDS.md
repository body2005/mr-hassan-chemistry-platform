# دليل تشغيل منصة متجر (Matgar LMS) وهيكلة الذكاء الاصطناعي (AI)

تم تجميع المشروع بالكامل في مجلد موحد تحت المسار:
📂 `D:\learning project`

---

## 🏗️ 1. هيكل المشروع الموحد (Project Structure)

```
D:\learning project\
├── apps\
│   ├── web\             # الواجهة الأمامية (React + Vite + TypeScript + Tailwind)
│   ├── api\             # الباك إند الأساسي (FastAPI + SQLite/PostgreSQL + Auth + LMS Data)
│   └── ai-service\      # خادم الذكاء الاصطناعي والتوليد التنبؤي (FastAPI + Ollama / Cloud LLMs)
│
├── START_ALL.bat        # ملف نقرة واحدة لتشغيل المنصة كاملة (الواجهة + السيرفر + الـ AI)
├── START_FRONTEND.bat   # تشغيل الواجهة الأمامية فقط (:5173)
├── START_API.bat        # تشغيل الباك إند الأساسي فقط (:8000)
├── START_AI_SERVICE.bat # تشغيل خادم الذكاء الاصطناعي فقط (:8001)
├── SETUP.bat            # تثبيت كافة الاعتماديات والحزم للـ 3 تطبيقات تلقائياً
└── RUN_COMMANDS.md      # هذا الدليل الشامل
```

---

## ⚡ 2. أوامر التشغيل اليدوية (Terminal Commands)

### أ) التثبيت لأول مرة (Setup):
```bash
# 1. تثبيت حزم الواجهة الأمامية:
cd "D:\learning project\apps\web"
npm install

# 2. إنشاء بيئة الباك إند الأساسي وتثبيت الحزم:
cd "D:\learning project\apps\api"
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt

# 3. إنشاء بيئة خادم الذكاء الاصطناعي وتثبيت الحزم:
cd "D:\learning project\apps\ai-service"
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

---

### ب) أوامر تشغيل كل خدمة (Running Services):

#### 1. تشغيل الواجهة الأمامية (Frontend):
```bash
cd "D:\learning project\apps\web"
npm run dev
```
> يفتح التطبيق على الرابط: `http://localhost:5173`

#### 2. تشغيل الباك إند الأساسي (LMS Core API):
```bash
cd "D:\learning project\apps\api"
.venv\Scripts\python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
> يعمل على الرابط: `http://localhost:8000` (التوثيق: `http://localhost:8000/docs`)

#### 3. تشغيل خادم الذكاء الاصطناعي (AI Service):
```bash
cd "D:\learning project\apps\ai-service"
.venv\Scripts\python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```
> يعمل على الرابط: `http://localhost:8001` (التوثيق: `http://localhost:8001/docs`)

---

## 🤖 3. كيف يعمل الذكاء الاصطناعي (AI Architecture & Providers)

### هل الـ AI معتمد على API خارجي أم محلي؟
نظام الـ AI في المنصة مصمم بهندسة **متعددة المزودات (Multi-Provider Architecture)** تمنحك الحرية الكاملة للاختيار بين 3 أنماط عبر ملف `apps/ai-service/.env` أو `app/config.py`:

```
┌────────────────────────────────────────────────────────┐
│                   LMS AI SERVICE                       │
├────────────────────────────────────────────────────────┤
│  1. Local Mode (Ollama)      -> مجاني 100% وبدون إنترنت │
│  2. Cloud API Mode (OpenAI)  -> GPT-4o / Gemini / Groq │
│  3. Mock Mode                -> للتطوير والتجربة السريعة │
└────────────────────────────────────────────────────────┘
```

---

### تفصيل الأنماط الثلاثة:

### 1️⃣ النمط المحلي المجاني (Local Mode - الافتراضي):
* **كيف يعمل:** يتصل بمحرك **Ollama** المثبت محلياً على جهازك (`http://localhost:11434`).
* **النماذج المدعومة:** `qwen2.5:7b` أو `llama3.1:8b` أو `mistral`.
* **المميزات:**
  * مجاني 100% بدون أي تكلفة أو اشتراكات.
  * يعمل بدون إنترنت مع حماية تامة لخصوصية بيانات الطلاب.
* **كيفية تفعيله في `.env`:**
  ```env
  DEFAULT_PROVIDER=ollama
  OLLAMA_BASE_URL=http://localhost:11434
  OLLAMA_MODEL=qwen3:8b
  ```

---

### 2️⃣ نمط السحابة عبر API خارجي (Cloud API Mode):
* **كيف يعمل:** يرسل الطلبات عبر مفتاح API إلى مزودي النماذج السحابية (OpenAI / Groq / Google Gemini / DeepSeek).
* **المميزات:** سرعة فائقة وجودة لغوية ممتازة بدون استهلاك موارد كرت الشاشة (GPU) على جهازك.
* **كيفية تفعيله في `.env`:**
  ```env
  DEFAULT_PROVIDER=external
  EXTERNAL_BASE_URL=https://api.openai.com/v1
  EXTERNAL_API_KEY=sk-your-api-key-here
  EXTERNAL_MODEL=gpt-4o-mini
  ```
  *(يمكنك أيضاً وضع رابط Groq السريع: `https://api.groq.com/openai/v1` ومفتاح Groq الخاص بك)*.

---

### 3️⃣ نمط المحاكاة (Mock Mode):
* **كيف يعمل:** يقوم بتوليد أسئلة وتقييمات تجريبية ذكية فورية بدون الحاجة لتشغيل Ollama وبدون مفتاح API.
* **كيفية تفعيله في `.env`:**
  ```env
  DEFAULT_PROVIDER=mock
  ```

---

## 🎯 وظائف الذكاء الاصطناعي المدمجة بالمنصة:
1. **توليد الامتحانات والأسئلة (`/api/v1/quiz/draft`):** توليد أسئلة اختيار من متعدد، مقالي، وصواب وخطأ من نص الدرس.
2. **تصحيح الإجابات المقالية (`/api/v1/grading/essay`):** تقييم إجابات الطلاب وفق معايير ونقاط محددة وإعطاء تغذية راجعة توجيهية.
3. **المعلم الذكي والمساعد التفاعلي (`/api/v1/tutor/chat`):** الإجابة على استفسارات الطلاب من واقع محتوى الدروس فقط (RAG).
4. **التنبؤ بالطلاب المعرضين للتعثر (`/api/v1/risk/predict`):** تحليل نسبة الحضور وحل الواجبات عبر خوارزميات تعلم الآلة للتنبؤ بمستوى الطالب.
5. **التحليلات وتلخيص التقارير (`/api/v1/analytics/interpret` & `/reports/narrative`):** تحويل الرسوم والدرجات إلى تقارير سردية للمعلم.
