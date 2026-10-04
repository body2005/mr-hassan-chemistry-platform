# فحص المدرس والطالب - 4 أكتوبر 2026

هذه جولة **تشخيص وتجربة، وليست إصلاحًا أو موافقة نشر**. اختُبرت الواجهة فعليًا
في Chromium بحسابات QA مدرس/طالب، مع مراجعة بصرية في Chrome وفحص استجابات API
وحالة البيانات. لم أعدّل كود التطبيق أو ملفات Extract، ولم أحذف محتوى المستخدم.
أضفت حسابات ومقررات وتسليمات وإشعارات اصطناعية في مشروع الاختبار فقط.

## البيئة والنسخة

- الرابط المختبر: `https://localhost:18543/`، مشروع Docker `chemistryaudit2`.
- PostgreSQL وRedis وSeaweedFS حقيقية، مع proxy وقالب الإنتاج وإضافتي QA والفيديو.
- الشهادة محلية ذاتية التوقيع؛ ليس اختبار شهادة عامة أو سيرفر خارجي.
- الفرع: `fix/queen-p0-handoff`؛ HEAD: `ce5a73137b81d81e42f5283189ae5519bba4eef7`.
- النسخة المختبرة هي working tree، **وليست HEAD وحده**. قبل أدوات هذه الجولة:
  79 ملفًا متتبعًا متغيرًا و62 مسارًا غير متتبع. لا commit/push/merge/deploy جديد.
  لم أعد فحص GitHub في هذه الجولة، ولا أنسب التغييرات المحلية للنسخة المرفوعة.
- API: `sha256:984c0da27cd2beb721a3f64b79237527a8c674c17a5e39263759a36920ab985b`.
- Video worker: `sha256:1c5e510aad99c6aa47dff4ba60eb8ee7b01029412dbccbe7f0053aeb87eefba4`.
- Web: `sha256:fb4a49767cde0f243cbf6067c119f6545a81702d9525ea2452e43a924f5f7df2`.
- `verify-runtime-source.ps1`: Exit 0، 72 ملفًا في كل من API/worker، صفر اختلافات؛
  أُعيد قبل التقرير. لا تعتبر اختبارات المسارات الأخرى دليلًا على دقة Extract.

## النتائج المؤكدة المفتوحة

P1 هنا خلل وظيفي مهم أو مخالفة لحدود الإتاحة/الجمهور؛ P2 خلل حساب/عرض أقل أولوية.
ليست هذه درجات CVSS. كل حالة أدناه بقيت كما هي: **قبل: معيبة؛ بعد الفحص: معيبة،
لم تُصلح محليًا ولم تُرفع**. عمود الملفات يحدد سببًا في الكود، لا ملفات أصلحتها.

| ID / أولوية | الدور وخطوات إعادة الإنتاج | المتوقع / الفعلي المثبت | السبب والملفات المعنية | اختبار الحالة / Passed-Failed-Skipped |
|---|---|---|---|---|
| R01 / P1 | مدرس: انشر واجب MCQ باختيارين؛ طالب: التحق وافتح ورقة الواجب PDF | يجب بقاء الاختيارات؛ prompt يحتوي السؤال فقط، فتفقد ورقة الطالب الاختيارات | `QuizGeneratorView.tsx`: يحوّل الأسئلة إلى `question_text` فقط عند إنشاء Assignment، دون options؛ `assignment_sheet.py` يرندر هذا prompt | `assignment preserves options...` / 0-1-0 |
| R02 / P1 | حدد 7 درجات للسؤال وانشره كواجب | المتوقع max_score=7؛ API أعاد 100 | `QuizGeneratorView.tsx` لا يرسل مجموع الدرجات؛ `lmsService.ts` يستعمل الافتراضي 100 | `assignment preserves score...` / 0-1-0 |
| R03 / P1 | حدد نشر الواجب غدًا؛ طالب مخوّل يفتحه ويسلمه اليوم | يجب منع البدء والتسليم؛ كلا طلبَي attempts/submissions أعادا 200 قبل الموعد | الواجهة تجمع موعد البدء لكن payload الواجب يرسل `due_at` فقط؛ schema/model/service لا تحمل موعد بدء للواجب | `assignment preserves future start...` / 0-1-0 |
| R04 / P1 | كويز بسؤال أول سليم وثانٍ نصه `x`؛ انشر ثم أعد التأكيد | الفشل يجب ألا يخلّف أسئلة أو يكررها؛ POST questions أعاد 201 ثم422، وبقي سؤال؛ الإعادة 201 ثم422، وأصبح العدد2، دون كويز ناجح | `lmsService.ts`: POST لكل سؤال على حدة قبل إنشاء الكويز، دون تحقق شامل/معاملة نشر atomic أو idempotency للنشر. `QuizGeneratorView.tsx`: نافذة التأكيد تبقى مفتوحة، والخطأ تحتها | `failed quiz publishing is atomic...` / 0-1-0 |
| R05 / P1 | الإشعارات: إضافة موعد جديد، النوع الافتراضي درس، اترك النص الاختياري فارغًا، أكمل المعالج | يجب نجاح الإشعار الافتراضي أو بيان أنه لم يُرسل؛ broadcast يعود422 | `NotificationsView.tsx`: ينشئ `message:""`؛ `NotificationBroadcastRequest` يتطلب طولًا>=1. توجد محاولتا حفظ عبر callback والمزامنة الخلفية | `calendar wizard reports empty notification body...` / 0-1-0 |
| R06 / P1 | نفس المعالج، مع حقن 503 على POST calendar فقط في متصفح QA | يجب إظهار فشل وعدم ادعاء الحفظ؛ ظهرت رسالة «تم حفظ وتحديث الموعد...بنجاح» رغم503 | `NotificationsView.tsx`: إغلاق/تحديث متفائل قبل الحفظ؛ catch المزامنة يكتفي بـconsole.error، دون rollback/خطأ ظاهر | `calendar wizard reports calendar outage...` / 0-1-0 |
| R07 / P2 | مدرس أو طالب: اختر PNG من تغيير الصورة الشخصية وانتظر reload التلقائي | يجب حفظ الصورة؛ اختفت بعد reload لكلا الدورين | `ProfileView.tsx`: تعديل كائن user بالذاكرة ثم reload، دون حفظ أو upload. `mapApiUser` لا يعيد avatar | اختبارا avatar teacher/student / 0-2-0 |
| R08 / P1 | مدرس واحد يملك مقررين A وB لنفس الصف، ولكل منهما درس؛ افتح إدارة الدروس واختر الصف | يجب الوصول لكلا المقررين؛ درسB ظهر ودرسA اختفى ولا اختيار للمقرر | `LessonManagementView.tsx`: `courses.find` حسب الصف فقط؛ نفس الاختيار الأحادي في `QuizGeneratorView.tsx` | `teacher can select both courses...` / 0-1-0 |
| R09 / P2 | مدرس QA جديد ليس له national_id، افتح ملفه وانتظر اكتمال الصفحة | يجب عدم تأكيد توثيق لم يحدث؛ ظهرت عبارة التحقق من الرقم القومي واعتماد العقد | `ProfileView.tsx`: النص مثبت لكل مدرس، لا يعتمد على حالة تحقق من السيرفر | `new teacher does not show...` / 0-1-0 |
| R10 / P2 | طالب مسجل الآن، GET progress/me=[]، افتح الملف | يجب عدم وجود سجل مشاهدة؛ تظهر3دروس بنسب100% و92% و60% | `ProfileView.tsx`: سجل ودروس ونسب مكتوبة في JSX، لا تعتمد على التقدم الحقيقي | `new student profile has no invented...` / 0-1-0 |
| R11 / P1 | اكتب إشعارًا فوريًا، احقن503 على broadcast فقط ثم أرسل | يجب الاحتفاظ بالمسودة وإظهار فشل؛ النافذة تغلق وتفقد المسودة ويظهر نجاح عام غير متعلق بالإرسال | `App.tsx`: callback يحفظ دون await ويبتلع الخطأ؛ `NotificationsView.tsx` يعامل استدعاء callback كنجاح ويصفّر المسودة | `teacher retains notification draft...` / 0-1-0 |
| R12 / P2 | مدرس QA جديد لديه مقرر، التحق به طالب QA فعلي، افتح الملف | يجب احتساب الطالب؛ العداد بقي0 رغم نجاح enroll200 | `lmsService.ts/mapApiUser`: `enrolledStudentsCount:0` و`uploadedVideosCount:0` ثابتة. عداد التسجيل هو الذي أُعيد إنتاجه آليًا | `teacher profile enrollment count...` / 0-1-0 |
| R13 / P1 | مدرس: أرسل من الواجهة إشعارًا يستهدف الأول الثانوي؛ حساب جديد ثاني ثانوي: GET notifications | يجب ألا يُسلّم للجمهور الآخر؛ وصل إشعار واحد مع النص كاملًا وaction_url يحملgrade=1st_secondary | `lmsService.ts`: الصف في URL فقط؛ `platform_service.broadcast_notification`: كل مستخدمي المؤسسة دون gradefilter. إخفاء الواجهة ليس حدًا من السيرفر. لا يثبت هذا وصول الطالب إلى مادة مدفوعة | `grade-targeted teacher notification...` / 0-1-0 |
| R14 / P1 | شغّل strict fidelity على ملفات المستخدم السبعة، وراجع صفحتَي PDF الأحياء بصريًا | العدد10 صحيح، لكن3أسئلة غير مطابقة: اختيار3 «نقل الأكسج» بدل «نقل الأكسجين»؛ السؤال6 فقد موضع الفراغ؛ السؤال7 نص مشوّه | `document_parsers.py`/`exam_text_extractor.py` ومسار OCR. `needs_content_review=true` موجود لهذه الحالات؛ لم يختلق answer key أو marks في هذه العينة، لكنه ليس استخراجًا مطابقًا بالكامل | `qa_extract_fidelity` / 6-1-0 |
| R15 / P1 | انشر واجبًا بعنوان `QA Science Units` ونص `Choose the mass unit. 12 kg.`؛ الطالب ينزّل sheet.pdf200 | عنوان/سؤال API صحيحان، لكن الحروف اللاتينية تختفي من PDF. تأكد بصريًا على ورقة R01 أيضًا: لا يبقى من عنوانه إلا الأرقام، والسؤال يصبح نقطة وفراغات | `assignment_sheet.py`: يستخدم Noto Arabic واحدًا لكل النصوص، دون font fallback/تغطية Latin؛ rendering لا يراجع توفر glyphs. لم أخلط خطأ text extraction مع النتيجة البصرية | `student PDF retains Latin question...` / 0-1-0 |

جميع R01-R13 وR15 في `apps/web/tests/qa/discovery.spec.ts`. نسخةv4 قبل R15:
Exit1، **1 Passed /14 Failed /0 Skipped**. دمج فشل avatar للدورين في R07 يترك
13 مجموعة مشاكل وظيفية فيv4؛ ومع R14 وR15 يصبح الإجمالي **15 مجموعة مؤكدة**، لا ادعاء
أن عددها يساوي جميع العيوب الممكنة في الموقع.

الحالة الإيجابية الإضافية: واجب منتهٍ الموعد رفض attempts403 ثم submissions403
حتى دون active attempt. شبهة تجاوز الموعد عبر API **لم تتأكد**؛ بقي الاختبار
ناجحًا ولا أدرجته كعائق. وفشل test helper الأول بسبب محاولة sign-in بعد register
لم يُحسب عيبًا: التسجيل يصدر session بالفعل. كذلك أُصلح انتظار اكتمال profile
في اختبار التوثيق حتى لا يمر بسبب صفحة لم تكتمل.

## ما نجح فعليًا في هذه الجولة

قبل إضافة discovery، المجموعة الكاملة القائمة نجحت: **44 Passed /0 Failed /0 Skipped**،
وليس مجرد فتح الصفحة. شملت:

- تسجيل الطالب من الواجهة، الدخول والخروج، حساب المدرس، حفظ الصف والتسجيل.
- تغيير كلمة المرور من المعالج، كلمة حالية خاطئة، استرجاع عبر Mailpit محلي،
  وإبطال الجلسات والدخول بالكلمة الجديدة، على حسابات اصطناعية فقط.
- نشر Quiz/Assignment أساسيين وربطهما بالدرس؛ أوقات عربية، bootstrap بطيء،
  وقت غير صالح ودرس stale دون كتابة تقييم/أسئلة، عنوان200حرف.
- حل كويز مقالي، إرسال صورة واجب وتصحيحهما من واجهة المدرس، وإثبات النتيجة من API.
- رفع إيصال QA، مراجعة المدرس وموافقته، وصول الطالب الدافع دون الطالب الآخر.
- ملكية الموارد والاستحقاقات، رفض فيديو/PDF/إيصال مزيف، CSRF وCORS.
- رفع فيديو حقيقي ~35.4MB وPDF ~25.9MB، معالجة HLS، تشغيل وseek وRange،
  انتهاء رابط المشاهدة والمنع دون استحقاق/جلسة، واستئناف multipart بعد انقطاع/reload.
- انقطاع bootstrap والتعافي دون request storm؛ 429 فعلي دون إعادة تلقائية لا نهائية؛
  SSE يجدد cookie منتهية. النص الطويل للإشعارات يلتف في desktop/mobile،
  ومدخلات التصحيح/معالج كلمة المرور تعمل في dark mode.
- صفحة البداية/التسجيل responsive وعددها12حالة (6أحجام × لغتين)؛ نجاحها لا يثبت
  جميع تفاصيل كل صفحة للمدرس/الطالب على كل جهاز.

**نجاح الوظائف الأساسية لا يلغي حالات discovery الجديدة.** على سبيل المثال:
نجاح واجب مقالي افتراضي لا يثبت حفظ اختيارات MCQ/درجاته/موعد بدايته.

## Extract: مقارنة مستقلة بالمصدر

المهارة البصرية PDF أثّرت على التشخيص: لم أعتمد على العدد أو تقرير OCR وحده؛
رندرت صفحتَي الأحياء وراجعت الأسئلة3 و6 و7 مع المصدر. SHA-256 لملف المستخدم
في Downloads ولنسخته في fixtures متطابق:
`f612beeda9975b82054796c714fd863b452c4be3ff3922b4ca438534ed0def36`.
ملف المرجع QA-only، منسوخ يدويًا من المصدر، ولا يدخل كود التشغيل.

| الملف | المتوقع/المستخرج | أسئلة مطابقة بالكامل | CER |
|---|---|---|---|
| physics PDF |12/12|12|0|
| mathematics two columns PDF |10/10|10|0|
| geology PDF |10/10|10|0|
| integrated science PDF |12/12|12|0|
| biology image-only PDF |10/10|7|2.1614%|
| no questions negative PDF |0/0|0، لا أسئلة زائدة|0|
| biology first page PNG |5/5|5|0|

6 ملفات ناجحة/1فاشل/0متخطى؛ 56 من59سؤالًا مطابقًا بالكامل عبر الملفات، لكن PNG
يكرر أول صفحة الأحياء: ليست59عينة مستقلة. CER ليس نسبة نجاح وظيفي عامة ولا
دليل دقة100% على أي صور/PDF/Word. Word مغطى بعقود unit، وليس بعينة blind
DOCX من هذا المجلد في الجولة الحالية. لم ألمس ملفات freebuff.

## أوامر ونتائج قابلة للمراجعة

الأوامر نفذت على Windows؛ أوامر Docker تستعمل executable المحدد في أدوات QA.
نتائج `.qa` محلية ignored وقد تحتوي trace/cookies؛ لا ترفعها كما هي.

| الأمر | Exit | Passed / Failed / Skipped | الدليل المحلي |
|---|---|---|---|
| `scripts/qa/verify-runtime-source.ps1`، مرتان |0|مطابقة72ملفًا لكل خدمة؛ ليس عداد tests|إخراج72/صفرmismatch|
| `scripts/qa/run-video.ps1 -Stage Browser` قبل discovery |0|Playwright44/0/0؛ unit20/0/0|`video-browser-Browser-20261004-134019.xml`، `video-commands-Browser-20261004-134019.json`|
| `scripts/qa/run-video.ps1 -Stage Browser` بعد discovery، جميع الحالات دون استبعاد |1|Playwright45/14/0؛ unit20/0/0|`video-browser-Browser-20261004-140305.xml`، `video-commands-Browser-20261004-140305.json`|
| `npm run lint` بعد إضافة discovery |0|0errors،3FastRefresh warnings؛ ليست عيوب runtime مؤكدة|إخراج lint|
| `npm run build` |0|لا عداد tests؛ تحذير chunk كبير، ليس benchmark|إخراج Vite|
| `npx playwright test --config playwright.qa.config.ts tests/qa/discovery.spec.ts --reporter=list,junit`، نسخةv4 |1|1/14/0|`role-discovery-v4.xml`, `role-discovery-results-v4/`|
| `scripts/qa/run-role-discovery.ps1 -Python <Python-with-pypdf>`، النسخة النهائية16حالة |1|browser1/15/0؛ fidelity6/1/0؛ diffcheck0|`role-browser-20261004-141609.xml`, `role-extract-20261004-141609.json`, `role-commands-20261004-141609.json`|
| `docker compose ... run --rm --no-deps qa-tests python -m pytest tests --ignore=tests/integration -q --junitxml=/qa/role-api-unit.xml` |0|187/0/0|`role-api-unit.xml`؛ integration ليست ضمن الأمر ولا مصنفةskip|
| `docker compose ... run ... qa-tests python -m scripts.qa_extract_fidelity --output /qa/role-extract-fidelity.json` |1|6/1/0|`role-extract-fidelity.json`|
| `npm audit --audit-level=high` في التشغيل الأول |0|0npmvulnerabilities؛ ليس فحص Docker|سجل تشغيل Browser الأول|
| `git -c core.safecrlf=false diff --check` |0|لا عداد tests|صفر أخطاء whitespace|
| فحص glyphs للخط الفعلي داخلAPI بواسطةReportLab TTFont |0|ليس testcount؛ Latin A/C=None، كاف=371، رقم1=1229|إخراجDockerexec؛ يثبت سببR15|

أُعيد تشغيل مجموعة المتصفح كاملة بعد إضافة حالات discovery:45ناجح/14فاشل،
وExit1 حقيقي. الـwrapper يتوقف عند فشل browser؛ لذلك شُغّل npm audit وdiffcheck
يدويًا أيضًا، وكلاهماExit0. بعد ذلك عُدّل **اختبار** R01 فقط ليقرأ ورقةPDF
الحقيقية بدل توقع ظهور الاختيارات في HTML؛ تُعاد discovery كاملة بهذا التعديل
عبر أداة إعادة التشغيل. كشف PDF عيب R15، فأضيف اختبار مستقل له؛ لذلك النسخة
النهائية من discovery فيها16حالة، والمجموعة59 السابقة لا تشمل هذا الاختبار
الإضافي المستقل. لم يتغير كود التطبيق أو صوره بين هذه التشغيلات.

## إعادة التشغيل

من نسخة نظيفة، اتبع `docs/PRODUCTION_DOCKER_RUNBOOK.md` و`docs/VIDEO_PIPELINE.md`
لتجهيز `.qa/audit2/compose.env` والأسرار المحلية وشهادة QA وبيانات QA الاصطناعية
وfixtures الفيديو/PDF، ثم شغّل مشروع `chemistryaudit2` مع video overlay.
لا تضع secrets أو artifacts الخام في Git. المنافذ18543/18544/18525 loopback.
استخدم `prepare-production.ps1 -Project chemistryaudit2`، لا المشروع الافتراضي
المختلف. أداة قراءة ورقة الطالب تحتاج Python مع `pypdf`؛ لا OCR/API خارجي.

```powershell
./scripts/qa/run-role-discovery.ps1
# إن لم يكن Python المناسب في PATH:
./scripts/qa/run-role-discovery.ps1 -Python 'C:/absolute/path/to/python.exe'
# أو المجموعة الكاملة، تشمل discovery ولا تستبعد عيوبه:
./scripts/qa/run-video.ps1 -Stage Browser
```

`run-role-discovery.ps1` يجمع discovery وfidelity وdiffcheck، يحفظ نتائج Exit
ويتوقع Exit1 ما دامت العيوب مفتوحة؛ لا يستخدم test.fail/skip ولا يخفض الحماية.
لا تشغّل مجموعتَي browser بالتوازي: fixture يعزل فقط IP-auth counters في Redis
مشروع QA المسموح بين الحالات؛ لا يمس حدود المستخدم/الفيديو أو إعداد rate limiting الحقيقي.
الـwrapper يحفظ Exit لكل مرحلة ويكمل fidelity رغم فشل discovery. النسخة الأولى
فُحصت syntax ثم شُغّلت بنفسها؛ نتيجة تشغيل النسخة النهائية في ملحق الإغلاق.

## أدلة بصرية محلية

ضمن `.qa/audit2/role-discovery-results-v4/`:

- `qa-discovery-assignment-pr-6e473-ons-from-teacher-to-student/assignment-options.png`:
  واجب الطالب لا يحوي خيارات المدرس.
- `qa-discovery-new-student-p-93520-ted-completed-watch-history/student-invented-history.png`:
  حساب جديد يعرض تقدمًا لم يفعله.
- `qa-discovery-new-teacher-d-1f24e-abricated-verified-identity/teacher-verification.png`:
  تأكيد توثيق غير حقيقي.
- `qa-discovery-calendar-wiza-91558-ts-calendar-outage-honestly/calendar-calendar-outage.png`:
  رسالة نجاح أثناء503.
- `qa-discovery-failed-quiz-p-3908e-oes-not-duplicate-questions/partial-quiz.png`:
  نافذة التأكيد بعد فشل جزئي.

ورقة الطالب الفعلية200 استُخرجت من trace QA إلى
`.qa/audit2/role-pdf-review/student-assignment-sheet.pdf`، ورندرت بواسطة Poppler
إلى `student-sheet-1.png`. المعاينة أكدت غياب Latin، وليس فقط فشل pypdf في
قراءة النص. test R01 يراجع prompt المحفوظ أيضًا؛ غياب خياراته مثبت حتى بغض
النظر عن عيب الخط في R15. اللقطة HTML وحدها ليست دليلًا على محتوى PDF.

## حدود النتائج وبوابات أخرى لم تُغلق بهذه الجولة

- ليست كل المشاكل الممكنة مكتشفة؛ لم أجرّب Safari/iOS/Firefox، إنترنت حقيقي
  ضعيف على أجهزة مختلفة، ملفات5GB/1GB كاملة، أو كل edgecase لتعديل/حذف المحتوى.
- لم أعد تشغيل fault/backup/restore/load/كل integration races أو Docker Scout
  في هذه الجولة؛ نتائجها السابقة لا تتحول تلقائيًا إلى نتائج جديدة هنا.
- آخر فحص ثغرات موثق في `QA_VIDEO_2026-10-04.md` يبقي5High فيAPI و9High فيworker
  مع سجل zlib إضافي؛ هذه أرقام الفحص السابق، لا فحص محدث الآن، ولا vulnerabilities
  أخفيتها بمرور npm audit. يلزم إعادة الفرز قبل قبول نشر.
- DRM/CDN خارجيان غير مفعلين. حماية session/token/entitlement التي نجحت ليست DRM؛
  الطالب المخوّل يستطيع تقنيًا التقاط وسائط غير مشفرة/تسجيل الشاشة. لا ضمان
  «استحالة التحميل» من network أو download manager.
- لا استنتاج1000مستخدم من أحمال صغيرة؛ لم ينفذ load benchmark جديد في هذه الجولة.
- المضاف في هذه الجولة أدوات اختبار/تقرير فقط. الحالة ليست «أصلح محليًا» ولا
  «مرفوع إلىGitHub»، والاختبارات المحلية علىDocker لا تعني «اختُبر خارجيًا».

## ملحق الإغلاق

- مجموعة المتصفح الكاملة:59حالة،45Passed/14Failed/0Skipped/0Errors، مدة7.9دقيقة،Exit1.
- الـ44حالة السابقة نجحت ثانية، مع حالة التحكم الجديدة لمنع تسليم الواجب المنتهي.
- runtime healthy لكل الخدمات العشر، لكنه لا يعني خلو الموقع من عيوب الوظائف.
- التغييرات الخاصة بهذه الجولة: `apps/web/tests/qa/discovery.spec.ts`،
  `scripts/qa/run-role-discovery.ps1`، وهذا التقرير فقط. 79ملفًا متتبعًا متغيرًا
  و65مسارًا غير متتبع بعد إضافتها؛ الباقي تغييرات موجودة قبل الجولة ومحفوظة.
- فحص PowerShell syntax:0أخطاء. `git diff --check`:Exit0،HEAD لم يتغير.
- الـwrapper النهائي نُفّذ كاملًا:16حالةbrowser،1Passed/15Failed/0Skipped/0Errors؛
  fidelity6Passed/1Failed/0Skipped، ثمdiffcheck0، والـwrapperExit1. مدةbrowser2.0دقيقة.
  لا يُجمع عدد16مع59 كأنها75حالة فريدة؛ حالاتdiscovery مكررة عداR15 الإضافي.
- R01: sheet.pdf200 وcontains_choices=false، والـprompt بلاoptions. R15 مستقل:
  stored_text_correct=true،sheet200،contains_question=false،contains_title=false.
  فحص cmap من نفسخطAPI أثبت absence لغليفA/C، مع وجود العربية والأرقام.
- آخرverify-runtime-source بعد اكتمال الجولات:Exit0،صفرmismatch؛ آخرlintExit0
  و3warnings؛ آخرdiffcheckExit0. لا تعديل/إصلاح لكود التطبيق أثناء الجولة.
- ملفاتالنتائجالنهائية: `role-commands-20261004-141609.json`،
  `role-browser-20261004-141609.xml`، `role-extract-20261004-141609.json`.
