# تسليم تعديلات المنصة — 2026-10-11

**لم تُشغّل اختبارات في هذه الجولة؛ التعديلات غير متحقق منها بالتشغيل.**

هذا تقرير تعديل كود وقراءة سجلات وإعدادات، وليس اعتمادًا للإنتاج. لم تُشغّل pytest أو Vitest أو Playwright أو integration/load أو build أو Docker QA أو مسح ثغرات جديد. `git diff --check` مراجعة تنسيق فقط. نتائج الجولات القديمة لا تغطي هذه التعديلات.

## نطاق الحفظ

- الفرع المحلي المطلوب: `fix/queen-p0-handoff`.
- البداية المحلية: `339fc3e1abc994d2b7b261712bf2d7524b34c10a`؛ حُفظت جميع الـcommits السابقة بلا reset/rebase/force push.
- البداية البعيدة المقروءة: `2b4cb7d05ba499876140ab2193825388516ce02e`؛ المحلي متقدم بثمانية commits قبل هذه الجولة.
- `pc_builder_3d_cases/` خارج المهمة ولم يُضمّن. الأدلة والسجلات الخاصة داخل `.qa/` المستبعدة من Git.
- SHA النهائي ونتيجة مطابقة البعيد يردان في رسالة التسليم بعد الحفظ؛ لا يمكن كتابة SHA الـcommit داخل نفسه.

## البنود الـ22

كل «عُدّل» أدناه يعني تعديل المصدر فقط، بلا إثبات تشغيل.

| # | الحالة والتعديل | الملفات الأساسية |
|---|---|---|
| 1 | انتظار refresh الجاري قبل probe خاص، وحماية bootstrap قبل كتابة الهوية/cache من تبديل الحساب. 401 بعد فشل التجديد الدائم يتحول إلى حالة دخول؛ الإلغاء لا يسجل خروجًا ولا يبدأ حلقة retries. فشل تحميل بيانات bootstrap يعطي 503 بدل نجاح جزئي. السبب الحي لكل 401 لم يُثبت من سجلات جلسة مستخدم. HttpOnly/Secure/CSRF/Origin محفوظة. | `services/apiClient.ts`, `services/lmsService.ts`, `App.tsx`, API `routes/platform.py` |
| 2 | مؤقت مستقل لكل Toast: 5 ثوانٍ، أو 10 ثوانٍ عند أكثر من 120 حرفًا/سطر جديد. إزالة المؤقت عند الإغلاق وتبديل الحساب وunmount. منع تكرار الرسالة وحصر المعروض في أربع رسائل. | `components/ToastProvider.tsx` |
| 3 | سياسة خادم مشتركة تتطلب مقررًا منشورًا ودرسًا منشورًا وموعدًا وصل ومحتوى جاهزًا. آخر رفع غير جاهز يمنع إتاحة الفيديو؛ عدد المرفقات المحفوظة يجب أن يبلغ العدد المطلوب. درس الملفات لا يحتاج فيديو. فلترة القوائم العامة والطالب وbootstrap وأسماء الدروس بالتقييم، وتطبيق السياسة عبر صلاحيات الفيديو/الملفات/المناقشة/التقدم. المدرس يستمر في رؤية الحالات غير الجاهزة. | API `services/lesson_release.py`, `payment_service.py`, `routes/courses.py`, `routes/platform.py` |
| 4 | إنشاء وتعديل حالة النشر: بعد الجاهزية/موعد محدد/مسودة. Africa/Cairo عبر IANA مع رفض الوقت غير الموجود عند تغير التوقيت الصيفي؛ التخزين UTC ورفض datetime بلا timezone من API. تعديل وإلغاء الجدولة لا يمس الملفات. إشعار محفوظ مرة واحدة بعد الجاهزية والموعد، مع hint عبر SSE؛ الفحص الخلفي كل نحو دقيقة وقد يتأخر عند توقف الخدمة. الإتاحة نفسها تفحص الموعد في كل طلب ولا تنتظر الفحص الخلفي. | `views/LessonManagementView.tsx`, `utils/cairoTime.ts`, API model/schema/migration, `lesson_announcements.py`, `session_maintenance.py` |
| 5 | `Lesson.course_id` مستقل و`module_id` اختياري، backfill للدروس القديمة. «بدون وحدة» مجموعة عرض فقط وليست وحدة مصطنعة. إنشاء وحذف وتعديل النشر يعمل للدروس دون وحدة. تحديث استعلامات الصلاحيات والتقارير والدفع والمرفقات. حقل الوحدات بالتقييم اختياري، والدروس والوحدات Multi-select منفصلان؛ توسعة الوحدات تستخدم set لتجنب التكرار. | API `models/course.py`, migration, `platform_service.py`, مسارات الصلاحيات؛ `lmsService.ts`, `LessonManagementView.tsx`, `AssessmentScopePicker.tsx` |
| 6 | رابط ثابت `#mycourses?course=<uuid>&lesson=<uuid>` بلا token/رابط وسائط. Web Share ثم clipboard، والإلغاء لا يعرض نجاحًا. حفظ هوية الوجهة فقط أثناء الدخول. الطالب يتحقق من إتاحة الدرس عبر API قبل فتحه؛ غير المشترك يحتاج اشتراكًا. المدرس يفتح الدرس من بيانات مقرراته المصرح بها. | `VideoLessonPage.tsx`, `utils/sharedLesson.ts`, `App.tsx`, `MyCoursesView.tsx`, `LessonManagementView.tsx` |
| 7 | وقت المشغل يبدأ من المدة الفعلية المحفوظة ويتحدث من metadata، وصيغة الساعة `h:mm:ss`. إزالة مدة البطاقة التخَمينية. loading يعكس انتظار التشغيل والشبكة، و`play()` لا يعلن التشغيل قبل الحدث الفعلي. المعالج الموجود يحفظ المدة المستخرجة؛ token/HLS لهما مالك واحد بالفعل وpreload=metadata. لم يوجد انتظار ثابت 5 ثوانٍ في المسار المقروء؛ تأخير الشبكة أو cold start لم يُقَس أو يُعلن إصلاحه. | `VideoLessonPage.tsx`, `LessonManagementView.tsx`, `lmsService.ts`؛ مراجعة `useProtectedPlayback.ts`, `useHlsTransport.ts`, `scripts/video_worker.py` |
| 8 | focus-visible أخضر على المشغل وحده. الحفاظ على اختصارات الأسهم والإشارة الفعلية المتراكمة يمينًا/يسارًا وحدود الفيديو وقيود الطالب وعدم اعتراض الكتابة. | `index.css`, مراجعة `VideoLessonPage.tsx` |
| 9 | حدث تعليق/رد بعد commit، hints بهويات الدرس والتعليق فقط لمستلمين مصرح لهم. فشل hint لا يلغي التعليق المحفوظ. اشتراك في SSE الموجود، تنظيف عند تبديل الحساب/الدرس، تحديث مؤجل ومجمّع 300ms وعند reconnect، حفظ المسودات ومنع تكرار response/event. لا اتصال منفصل ولا polling سريع. | `LessonDiscussion.tsx`, `realtimeService.ts`, API `routes/platform.py` |
| 10 | إزالة زر ترتيب التعليقات وثبات الأحدث أولًا مع الردود تحت الأب. | `LessonDiscussion.tsx` |
| 11 | اختيار محاولة محددة بالعنوان/رقم المحاولة/وقت التسليم. نسبة نهائية قابلة للتعديل 0–100 وأزرار النسب والعودة للمحسوب. الحفظ بعقد attempt ID مع مجموع الأسئلة المحسوب منفصلًا وoverride وملاحظات الاعتماد والفاعل والتاريخ. `attempt.score` النهائي يظل مصدر التقارير المعتمدة؛ لا تعديل للحد الأقصى أو نسبة المقرر. callback متابعة الطلاب يعيد قراءة الإحصاءات كما كان. | `ExamGradingModal.tsx`, API `routes/platform.py`, `models/platform.py`, `schemas.py`, migration؛ مراجعة `SubmissionsView.tsx` |
| 12 | الحفاظ على اعتماد المدرس قبل كشف النتيجة الرسمية. عدم اعتماد مقال غير مصحح، صفر مختلف عن غياب graded_at، فصل التدريب. تنقيح حقول المحسوب/override الجديدة أيضًا قبل الاعتماد. لا تصحيح حرفي ولا AI جديد. | API `services/quiz_results.py`, `routes/platform.py`, `ExamGradingModal.tsx` |
| 13 | زر إلغاء الموعد #762828، نص/أيقونة أبيض وحدود #B91C1C مع hover/focus واضحين. وظيفة الإلغاء الأصلية محفوظة. | `NotificationsView.tsx`, `index.css` |
| 14 | قسم تفريغ الدروس #9C1B28، عنوان ووصف أبيض، زر #762828 أبيض، وتوحيد ProfileModal. لم يُنفّذ حذف فعلي ولم تُزل التأكيدات أو قيود الإدارة. | `ProfileView.tsx`, `ProfileModal.tsx` |
| 15 | إزالة مربع الاعتماد الأكاديمي بالعربية والإنجليزية من الملف الشخصي. | `ProfileView.tsx` |
| 16 | resetEmail فارغ، البريد الحالي placeholder فقط، وإرسال النص الذي كتبه المستخدم مع required/type=email. مسار الاستعادة يحافظ على الرد العام. دعم Resend HTTPS موجود مسبقًا؛ مزود/اعتماد مرسل فعلي متطلب خارجي ولم تُرسل رسالة. | `PasswordChangeWizard.tsx`؛ مراجعة API `mail_service.py`, `config.py` |
| 17 | حذف عرض الوصف الصغير تحت عناصر القائمة في المكون المشترك للغات والأدوار والكمبيوتر/الموبايل. المحاذاة الأفقية القائمة محفوظة. | `Sidebar.tsx` |
| 18 | مراجعة الأصل/Range/HLS/manifest/segments: تفحص cookie الحية وtoken المقيّد والجلسة والاستحقاق والإبطال، وكل مسارات المحتوى تمر الآن أيضًا بسياسة جاهزية/موعد الدرس. المفاتيح الخاصة لا تُسلسل للطالب والمشاركة لا تحمل token. خصوصية bucket الفعلي تحتاج إعدادًا خارجيًا؛ HLS ليس DRM ولا ضمان منع تسجيل الشاشة/النسخ 100%. | API `routes/platform.py`, `routes/video_uploads.py`, `payment_service.py`, `lesson_release.py` |
| 19 | قراءة سجلات Actions القديمة، إصلاح صورة s3-init المفقودة في قائمة بناء QA، وإضافة verbose مع redact لفحص الأسرار المقبل لتحديد موضع تنبيه بلا إظهار قيمته أو إضعاف الفحص. readiness/storage/worker والذاكرة وnative vulnerabilities موضحة أدناه كعوائق غير معتمدة. لم يُشغّل أي فحص جديد. | `scripts/qa/run-video.ps1`, `.github/workflows/quality.yml`, التقرير السابق والإعدادات القائمة |
| 20 | حدود الفيديو 5GiB والملفات 1GiB لم تتغير. لا حذف/تصفير بيانات أو volumes أو كلمات مرور. لا AI/Knowledge Center/SMS/صور حساب/subtitles/transcripts جديدة. التعديل الوحيد في extraction_staging استعلام تحقق ربط درس بالمقرر لدعم درس بلا وحدة، وليس parser/OCR. Biology مؤجل. | حدود المشروع القائمة؛ `services/extraction_staging.py` استعلام الصلاحية فقط |
| 21 | commit بعلامات `[skip ci] [skip render] [skip vercel]`، وignoreCommand في apps/web/vercel.json يتجاهل الـcommit المحتوي على `[skip vercel]` فقط. لا تعطيل دائم للـworkflows ولا نشر يدوي أو restart. راجع رسالة التسليم للحكم الفعلي على push/skip بعد المحاولة. | `apps/web/vercel.json`, Git؛ قراءة لوحتي النشر |
| 22 | هذا التقرير لكل البنود والملفات والمتطلبات الخارجية، مع تصريح عدم تشغيل الاختبارات. لا اعتماد إنتاج. | هذا الملف ورسالة التسليم |

## قراءة السجلات القائمة — ليست جولة تحقق

المصدر: run `38030511325` على commit `2b4cb7d` في GitHub Actions، سجلات محفوظة محليًا فقط ولم تُرفع.

- **backend**: الملخص يسجل سبعة إخفاقات extraction/OCR، وبين أسبابها PermissionError على `/srv/scripts/tesseract_limited.py`. المصدر المحلي السابق يتضمن chmod وlauncher بإصلاح LF؛ حُفظ ولم يُعاد تشغيله. اسم خطوة «native Expat» لا يعني أن الإخفاق المثبت هنا عيب Expat.
- **browser-and-images**: السبب المباشر لانهيار startup هو `No such image: chemistryaudit2-s3-init:latest` مع `up --no-build`. أضيف s3-init إلى build. خطوات fidelity والصور التابعة لم تجد حاوية API؛ هذا ليس نتيجة قياس fidelity أو مسح ثغرات ناجح أو فاشل على صورة فعلية. لم تُضعّف assertions ولم تُحذف خطوات.
- **secrets**: السجل يقول `leaks found: 1`، دون ملف/قاعدة/سطر، ولا يحتوي تقريرًا يحدد السبب. لا تصنيف كاذب بأنه false positive ولا ادعاء إصلاح. أضيف `--verbose` مع استمرار `--redact` وexit-code=1 للتشغيل اللاحق المأذون. لم يُعَد الفحص الآن.
- **الحمل القديم**: توقف التشغيل عند 10 جلسات مع تجاوز ذاكرة S3 حد الأمان القائم 1GiB لثلاث عينات. لم تُرفع الحدود ولم يُخف هذا العائق. لا دليل على سعة إنتاجية ناجحة.
- **التكامل القديم**: التشغيل قوطع بطلب المستخدم، ولا يوجد ملخص نهائي يثبت سببية أول إخفاق متعلق بالملف الكبير. admission leases موجود بها تجديد دوري وإغلاق العمل عند فقد الحجز؛ لا تغيير اعتباطي للـTTL/limits ولا ادعاء إصلاح عيب غير مشخّص.
- **native security القديمة**: تقرير 10 أكتوبر يحتفظ بـ63 HIGH للـAPI و79 HIGH للـencoder؛ لا اعتماد أمان جديد. إصلاح PCRE2 10.49 السابق محفوظ ضمن commits غير المرفوعة. عدم وجود تحديث مستقر في مستودعات التوزيعة وقت التقرير السابق لا يثبت حالة اليوم.

## إعداد النشر الفعلي المقروء في 11 أكتوبر

لم تُعرض أو تُنسخ مفاتيح أو قيم Environment سرية، ولم تُعدل إعدادات حية.

- Render service `srv-dahtu7h42hec73agru80`: الفرع `fix/queen-p0-handoff`، Auto-Deploy **On Commit**. النسخة الحية الظاهرة `2b4cb7d`، نُشرت يدويًا من اللوحة 11 أكتوبر. الخدمة **Free / native Python**، Root Directory `apps/api`، Build `pip install -r requirements.txt`، Start migrations ثم seed ثم uvicorn؛ health check path فارغ. لذلك تعديلات Docker/Blueprint لا تثبت تغير البيئة الحية.
- Vercel: الفرع نفسه فرع الإنتاج، Root Directory **apps/web** وIgnored Build Step في اللوحة **Automatic**. `ignoreCommand` في ملف المشروع يتجاوز الإعداد الافتراضي لهذا البناء. Node الظاهر في اللوحة 24.x. لا تغيير لأزرار Save أو Promote أو Deploy.
- وثائق التخطي: [Render skip phrase](https://render.com/docs/deploys#skipping-an-auto-deploy)، [Vercel ignoreCommand](https://vercel.com/docs/project-configuration/vercel-json#ignorecommand). كود تجاهل Vercel يعيد 0 لهذا الـcommit عند وجود العلامة و1 للسير العادي في commits الأخرى.
- لا يُستنتج نجاح readiness من ظهور «Live» أو استجابة `/` أو bootstrap في سجلات تشغيل قديمة. آخر دليل `/ready` المعتمد في التقرير السابق كان 503؛ لم يُفحص endpoint مجددًا في هذه الجولة.

## متطلبات خارجية وما لم يُعتمد

1. تطبيق migration `f8d0a2c4e6b8` فقط في نشر لاحق مأذون ومخطط مع نسخة احتياطية. لم تُطبق على قاعدة محلية أو حية الآن. API والواجهة الجديدة يحتاجان schema الجديدة معًا.
2. تخزين S3/R2 دائم **خاص**: bucket بلا public access، endpoint/region، صلاحيات حساب الخدمة المقيدة، Lifecycle للمرفوعات multipart غير المكتملة وCORS للرفع المباشر وفق origins الفعلية. الإعدادات المطلوبة في API ومعالج الكمبيوتر متطابقة: `STORAGE_BACKEND`, `S3_ENDPOINT_URL`, `S3_BUCKET_NAME`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `S3_REGION`؛ الأسرار خارج Git.
3. المعالج الموجود `infra/video-worker.pc.yml` يستخدم اتصالًا صادرًا فقط وملف `.env.video-worker.local` غير المرفوع. يحتاج DATABASE_URL لنفس DB وبيانات التخزين أعلاه وVIDEO_PROCESSING_ENABLED، وبقاء الكمبيوتر متصلًا. رفع الفيديو المباشر يحتاج VIDEO_DIRECT_UPLOAD_ENABLED وVIDEO_UPLOAD_PUBLIC_ENDPOINT فعليًا مع بوابة الرفع المجهزة. لم يُشغّل أو يُربط PC worker بخدمات حية الآن.
4. معالج ترميز الفيديو يختلف عن Celery ingestion worker. Render السابق أظهر API/DB/Valkey دون worker في المشروع، بينما defaults تستخدم Celery؛ هذا سبب محتمل لـ503 لا سبب مثبت. يلزم فحص dependency details المصرح بها ثم ربط worker والـbroker/queues بالإعداد الصحيح، دون إجبار ready على النجاح أو تعويضه بنجاح شكلي. يوجد Blueprint وإعدادات خاصة بالفعل، لكنها ليست تطبيقًا على الحساب الحي.
5. البريد: `EMAIL_ENABLED=true`, `EMAIL_PROVIDER=resend`, `RESEND_API_KEY` خاص، و`EMAIL_FROM_EMAIL` من نطاق/مرسل معتمد عند Resend. لا تستخدم yourdomain.com كمرسل فعلي غير مملوك/موثق. لم تُرسل رسائل ولم يُشتر حساب أو نطاق.
6. DRM أقوى يحتاج مزود ترخيص وتغليف ومشغل متوافق؛ لم يُفعّل أو يُشتر. الحد من تنزيل غير المصرح له لا يساوي استحالة نسخ ما يعرضه جهاز الطالب.
7. ما زال تنبيه الأسرار غير المحدد ونتائج native HIGH والحمل القديم وغياب إثبات readiness/ربط التخزين والمعالجات عوائق مفتوحة؛ الكود الحالي غير معتمد للإنتاج.

## الملفات

القائمة الدقيقة النهائية يمكن قراءتها من `git show --stat <SHA>`؛ الملحق التالي يسجل ملفات هذه الجولة، بينما الـpush يحفظ أيضًا الـcommits المحلية السابقة دون تغييرها.
- `.github/workflows/quality.yml`
- `apps/api/alembic/versions/f8d0a2c4e6b8_lesson_release_and_final_grade.py`
- `apps/api/app/api/routes/access_requests.py`
- `apps/api/app/api/routes/analytics_report.py`
- `apps/api/app/api/routes/auth.py`
- `apps/api/app/api/routes/courses.py`
- `apps/api/app/api/routes/payments.py`
- `apps/api/app/api/routes/platform.py`
- `apps/api/app/api/routes/telemetry.py`
- `apps/api/app/models/course.py`
- `apps/api/app/models/platform.py`
- `apps/api/app/schemas.py`
- `apps/api/app/services/extended_service.py`
- `apps/api/app/services/extraction_staging.py`
- `apps/api/app/services/lesson_announcements.py`
- `apps/api/app/services/lesson_materials.py`
- `apps/api/app/services/lesson_release.py`
- `apps/api/app/services/payment_service.py`
- `apps/api/app/services/platform_service.py`
- `apps/api/app/services/quiz_results.py`
- `apps/api/app/services/session_maintenance.py`
- `apps/web/src/App.tsx`
- `apps/web/src/components/AssessmentScopePicker.tsx`
- `apps/web/src/components/ExamGradingModal.tsx`
- `apps/web/src/components/LessonDiscussion.tsx`
- `apps/web/src/components/PasswordChangeWizard.tsx`
- `apps/web/src/components/ProfileModal.tsx`
- `apps/web/src/components/Sidebar.tsx`
- `apps/web/src/components/ToastProvider.tsx`
- `apps/web/src/components/VideoLessonPage.tsx`
- `apps/web/src/index.css`
- `apps/web/src/services/apiClient.ts`
- `apps/web/src/services/lmsService.ts`
- `apps/web/src/services/realtimeService.ts`
- `apps/web/src/types/lms.ts`
- `apps/web/src/utils/cairoTime.ts`
- `apps/web/src/utils/sharedLesson.ts`
- `apps/web/src/views/LessonManagementView.tsx`
- `apps/web/src/views/MyCoursesView.tsx`
- `apps/web/src/views/NotificationsView.tsx`
- `apps/web/src/views/ProfileView.tsx`
- `apps/web/vercel.json`
- `docs/PLATFORM_UPDATES_2026-10-11.md`
- `scripts/qa/run-video.ps1`
