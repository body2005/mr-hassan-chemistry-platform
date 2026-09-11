# تقرير التدقيق الهندسي الساكن (Static Audit Report)

**تاريخ التدقيق:** 2026-08-27  
**طبيعة الفحص:** تدقيق هندسي مستقل لمطابقة ادعاءات المعمارية والأداء بالأسطر البرمجية الفعلية في مستودع المشروع.

---

## 1. جدول مطابقة الادعاءات ضد الكود الفعلي (Audit Matrix)

| # | ادعاء الـ Dossier المعماري | الملف والسطر في الكود | التصنيف | الدليل الهندسي |
|---|---------------------------|----------------------|---------|----------------|
| 1 | **دعم البث التدفقي للفيديو بنطاق HTTP 206 (Range Requests)** | apps/api/app/main.py:102-104 | **VERIFIED** | تم تركيب مسار /static/uploads عبر StaticFiles(directory=UPLOAD_DIR). مكتبة Starlette/FastAPI تدعم ترويسات Range: bytes=start-end وترجع تلقائياً كود 206 Partial Content مع Content-Range مما يتيح التقديم والتأخير (scrubbing) في مشغل الفيديو. |
| 2 | **تطبيق حارس التزامن Bounded Concurrency عبر Semaphore(2)** | apps/api/app/services/transcript_indexer.py:16, 88-90 | **VERIFIED** | تم تعريف _INDEXING_SEMAPHORE = asyncio.Semaphore(2) في السطر 16، ويتم إحاطة دالة execute_lesson_indexing بالكامل داخل async with _INDEXING_SEMAPHORE: في السطر 90 لمنع استنزاف موارد المعالج. |
| 3 | **حارس الرفض 422 لمنع حفظ كويز بأسئلة غير مفهرسة في الخلفية** | apps/api/app/api/routes/platform.py:392-401 | **VERIFIED** | في دالة create_quiz بالسطر 393 يتم فحص Question.learning_objective == "محتوى غير مفهرس" وإطلاق HTTPException(422, "لا يمكن إنشاء أو حفظ كويز يحتوي على أسئلة بمحتوى غير مفهرس.") قبل الحفظ. |
| 4 | **ربط رسالة انتظار المشاهدات بصفر مشاهدات حقيقي واستئصال التخمينات** | apps/api/app/api/routes/ai_demo.py:319, 326, 331 | **VERIFIED** | عند استعلام التحليلات الحية، إذا كانت المشاهدات أو التسليمات = 0 تظهر رسائل واضحة مثل "• مشاهدات الفيديو: لم تسجل بيانات مشاهدة مكتملة بعد." و "• الكويزات: لا توجد تسليمات كويزات مسجلة بعد" وصفر نسب مخترعة. |
| 5 | **فحص إبطال الجلسات عبر جدول RevokedSession ومعرف jti** | apps/api/app/models/platform.py:80-89, apps/api/app/core/security.py:38, apps/api/app/api/dependencies.py:53-55, 88-90 | **VERIFIED** | يتم توليد jti لكل توكن جلسة، ويتم التحقق في كل طلب عبر db.scalar(select(RevokedSession.id).where(RevokedSession.jti == jti)) وفي حالة الإبطال يرجع 401 Unauthorized فوراً. |
| 6 | **حارس منع تكرار الفهرسة 409 Conflict أثناء in_progress** | apps/api/app/api/routes/platform.py:167-171 | **VERIFIED** | في مسار POST /lessons/{id}/reindex يتم فحص lesson.indexing_status == IndexingStatus.IN_PROGRESS وإرجاع 409 Conflict برسالة "عملية الفهرسة جارية بالفعل لهذا الدرس حالياً.". |
| 7 | **عزل فشل خدمة RAG الخارجية عن حفظ نص التفريغ rag_synced** | apps/api/app/models/course.py:127, apps/api/app/services/transcript_indexer.py:74-80, 137-142 | **VERIFIED** | تم إضافة عمود rag_synced لجدول lessons؛ عند تعذر خدمة الـ RAG، تظل حالة الفهرسة INDEXED طالما تم تفريغ النص وحفظه محلياً في transcript_text و content. |
| 8 | **أولوية قراءة نص الفيديو transcript_text أولاً في الكويزات والاستشهادات** | apps/api/app/api/routes/ai_demo.py:229, 489 | **VERIFIED** | يتم سحب lesson.transcript_text أولاً ثم lesson.content كبديل احتياطي، مع استبعاد الاعتماد على العناوين فقط ومنع توليد أسئلة غير موثقة. |
| 9 | **سجل الرفض الصريح AIRefusalLog وصلاحيات الوصول** | apps/api/app/models/platform.py:359-373, apps/api/app/api/routes/ai_demo.py:401-413, 420-452 | **VERIFIED** | يتم تسجيل كل استفسار خارج التغطية تلقائياً في ai_refusal_logs، ويوفر مسار GET /ai/refusal-log صلاحية كاملة للمدير، وصلاحية مقيدة للمعلم للمقررات التي يدرسها فقط. |
| 10 | **توضيح الطبيعة التقديرية للطوابع الزمنية للحزم** | apps/api/app/services/transcript_indexer.py:15, 41 | **VERIFIED** | تم توثيق أن الطوابع الزمنية للحزم تقديرية بنافذة 30 ثانية لكل حزمة (TIMESTAMP_EVERY_S = 30). |

---

## 2. فحص بيئة التشغيل ومحركات التفريغ (Runtime Environment Audit)

- **FFmpeg Binary Path:**  
  `%LOCALAPPDATA%\Microsoft\WinGet\Packages\...\ffmpeg.exe` أو عبر `PATH` (تم التحقق من تواجده وتشغيله بنجاح).
- **Whisper Speech-to-Text Model:**  
  تم تثبيت whisper عالمياً واستدعاؤه عبر بايثون 3.10 مع معالجة ترميز UTF-8 لتجنب مشاكل تشفير الحروف العربية في Windows console.
- **فحص دوال الـ Stubs / Mocks في الخدمات:**  
  تم إجراء فحص شامل لكافة دوال apps/api/app/services ولم يتم العثور على أي دوال تفريغ وهمية (Zero Stubs Found - CLEAN).

---

## 3. الحكم النهائي للتدقيق الساكن
- إجمالي البنود المفحوصة: **10 بنود**
- البنود المحققة فعلياً بالكود (VERIFIED): **10 / 10**
- البنود الجزئية (PARTIAL): **0**
- الادعاءات غير المحققة (UNVERIFIED / CLAIMED ONLY): **0**
