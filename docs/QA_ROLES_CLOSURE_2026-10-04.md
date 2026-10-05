# تنفيذ إصلاحات المدرس والطالب — 4 أكتوبر 2026

**ليست موافقة نشر.** النتائج أدناه تخص الصور النهائية المذكورة، لا HEAD وحده.
R14 وتنبيهات HIGH مفتوحة؛ تجارب OCR المرشحة لا تُعد إصلاحات معتمدة.
فحوص الإصلاحات تمت على working tree محلي قبلcommit. في5أكتوبر طلب المستخدم
إكمال العمل ثم رفعه إلى الفرع نفسه؛ الرفع لا يعني إغلاق R14 أو تنبيهات HIGH.
لا merge أو deploy. حالةcommit/push الفعلية تُثبت بمعرف Git ومقارنةremote عند التسليم.

## النسخة وحدود الإثبات

- الفرع `fix/queen-p0-handoff`؛ عند بدء فحوص هذه الجولة وقبل الرفع الجديد، HEAD
  وGitHub كلاهما `da84e3d8e981a8251bcf9f5dd63ba5ca66df3589`، مثبت بـ`git ls-remote`.
  في تلك اللحظة لا commit محلي أحدث؛ الفحوص تخص working tree الذي يحمل الإصلاحات،
  وليست دليلًا على وجودها في commit القديم. يُثبت الرفع الجديد بمعرف remote لاحقًا.
  فحص ما قبل الرفع:30مسارًا متتبعًا متغيرًا و17غير متتبع؛ أحد غير المتتبعة هو عمل
  `pc_builder_3d_cases/` الخارج عن المهمة، فلا يُنسب للإصلاحات.
- مشروع `chemistryaudit2` مستقل ببيانات اصطناعية، قالب الإنتاج الحقيقي مع إضافتي
  QA والفيديو. PostgreSQL/Redis/SeaweedFS حقيقية؛ لا fake storage للتجارب الحية.
- الموقع `https://localhost:18543/`، بوابة الرفع18544، Mailpit18525، loopback.
  الشهادة ذاتية التوقيع محليًا، وليست شهادة عامة أو اختبار سيرفر خارجي.
- صورة API الحالية:
  `sha256:7c65ed17bbf7aa4e60ff18b2f4a4e132c3696c1169b53ffbe065253e57145d28`.
- معالج الفيديو:
  `sha256:1403b7313b088328407af223d50fa577142efa84081453dbb956b2ce20d076e8`.
- Web:
  `sha256:8cb4a7fb8db4063bbfa79277f539ec8de9b3d862bb741e259d40c443eaf567f8`.
- freebuff انتهى بحسب تصريح المستخدم؛ تعديل Extract الجديد عام، وليس قاموسًا
  لعناوين الملفات/الأسئلة أو إجابات العينة. مجلد `pc_builder_3d_cases/` خارج المهمة
  محفوظ دون تعديل. لا reset/rebase/force push أو حذف بيانات المستخدم.

## جدول R01–R15

الأمر D هو تشغيل **كل** `discovery.spec.ts` بواسطة Playwright، عبر
`scripts/qa/run-role-discovery.ps1`؛ F هو `python -m scripts.qa_extract_fidelity`.
الأعداد في صفوف D تخص الحالات المرتبطة بذلك العائق من JUnit، لا مجموع تشغيلات
مستقلة. بعض الحالات مشتركة بين أكثر من عائق، فلا تُجمع للحصول على عدد المجموعة.
المسارات المختصرة: خدمات/مسارات API داخل `apps/api/app/`، واجهات/خدمات Web داخل
`apps/web/src/`. كل صف يشير أيضًا إلى regression في `apps/web/tests/qa/discovery.spec.ts`.

| العائق | قبل / السبب الفعلي | بعد / ما يتغير للمستخدم | الملفات الأساسية المتغيرة | الاختبار، Exit، P/F/S | الحالة المحلية |
|---|---|---|---|---|---|
| R01 | الواجب يحفظ `question_text` وحده، فتختفي الاختيارات | prompt مرقّم مع كل الاختيارات بترتيبها؛ ورقة الطالب تحتويها | `views/QuizGeneratorView.tsx`, `services/lmsService.ts` | D: options؛ 0؛ 1/0/0 | أصلح واختبر في Docker |
| R02 | مجموع الدرجات لا يُرسل؛ الافتراضي100 | اختيار7 يعطي `max_score=7` محفوظًا | نفس ملفي R01 | D: score؛ 0؛ 1/0/0 | أصلح واختبر |
| R03 | بداية الواجب لا تصل للسيرفر ولا تُحفظ | حقل `starts_at` مع migration؛ منع sheet/solve/start/submit قبل البداية، والواجب القديم بلا بداية يبقى صالحًا | `models/platform.py`, `schemas.py`, `services/platform_service.py`, `services/content_access.py`, ملفا R01، migration `d5f7b9c1e3a5` | D: future start؛ 0؛ 1/0/0، واختبارات API للوصول إلى الورقة/الواجب القديم | أصلح واختبر |
| R04 | POST منفصل لكل سؤال؛ فشل السؤال التالي يترك أسئلة يتيمة ويكررها | POST ذري `/quizzes/publish-draft`، تحقق شامل قبل الكتابة، قفل وunique/idempotency/hash؛ الخطأ داخل التأكيد والمسودة باقية | `services/platform_service.py`, `routes/platform.py`, `schemas.py`, `models/platform.py`, migration، ملفا R01 | D: failed publication + lost response؛ 0؛ 2/0/0؛ تزامن PostgreSQL أيضًا | أصلح واختبر |
| R05 | رسالة اختيارية فارغة تسبب422، وحفظ عبر callback ومسار آخر | نص افتراضي غير فارغ، إرسال واحد awaited؛ retry بالمفتاح نفسه | `views/NotificationsView.tsx`, `App.tsx`, `services/lmsService.ts` | D: empty notification body؛ 0؛ 1/0/0 | أصلح واختبر |
| R06 | إظهار نجاح وإغلاق قبل تأكيد حفظ التقويم؛ catch يبتلع الفشل | await للحفظ؛ خطأ503 ظاهر والمدخلات باقية؛ عند الحفظ الجزئي يُذكر أن الموعد حُفظ والإشعار فشل، retry لا يكرر | ملفات R05، `services/platform_service.py`, `models/platform.py`, `schemas.py`, migration | D: calendar outage + partial save/retry؛ 0؛ 2/0/0 | أصلح واختبر |
| R07 | avatar يتغير في الذاكرة فقط ثم يختفي؛ قراءات avatar/profile تُستهلك خطأً من حصة الدخول | upload حقيقي محدود/متحقق، PNG منزوع metadata في مخزن خاص، رابط self-auth من API؛ يبقى بعد reload/logout/login؛ تصنيف القراءات فقط إلى read | `routes/auth.py`, `models/user.py`, `schemas.py`, migration، `main.py`, `views/ProfileView.tsx`, `services/lmsService.ts`, `types/lms.ts` | D: teacher/student avatar؛ 0؛ 2/0/0؛ focused4/0/0 شمل R08؛ classification قبل12/6/0 ثم18/0/0 | أصلح واختبر |
| R08 | `courses.find` حسب الصف يخفي أحد المقررين ويربط النشر بالأول | selector للمقرر في إدارة الدروس وصانع الاختبارات؛ draft يحفظ الاختيار، والسيرفر يؤكد course/lesson الصحيحين | `views/LessonManagementView.tsx`, `views/QuizGeneratorView.tsx` | D: selector + quiz/assignment persisted binding؛ 0؛ 3/0/0 | أصلح واختبر |
| R09 | نص ثابت يدّعي توثيق الهوية/العقد لكل مدرس | حذف الادعاء من الصفحة والنافذة؛ لا حالة موثوقة من API تعني لا ادعاء اعتماد | `views/ProfileView.tsx`, `components/ProfileModal.tsx` | D: fabricated verified identity؛ 0؛ 1/0/0 | أصلح واختبر |
| R10 | دروس ونسب100/92/60 ثابتة | progress حقيقي خاص بالطالب مع عنوان الدرس؛ حساب جديد يعرض الحالة الفارغة | `routes/auth.py`, `views/ProfileView.tsx`, `services/lmsService.ts` | D: invented completed history؛ 0؛ 1/0/0؛ API profile-summary يثبت تقدمًا فعليًا أيضًا | أصلح واختبر |
| R11 | callback لا يعيد/ينتظر Promise؛ إغلاق وفقدان draft عند503 | callback awaited، لا نجاح وهمي؛ retry مع نفس المفاتيح؛ إلغاء الموعد أيضًا awaited ولا يرسل مرتين | `App.tsx`, `views/NotificationsView.tsx`, `services/lmsService.ts` | D: retained draft + partial save/retry؛ 0؛ 2/0/0 | أصلح واختبر للحالات المحددة؛ الإلغاء await راجع في الكود ولا يُنسب لاختبار browser مستقل |
| R12 | mapApiUser يضع صفرًا ثابتًا | عدد طلاب فريدين active/completed غير محذوفين في مقررات المدرس؛ فيديوهات الدروس ذات مصدر جاهز فقط، لا jobs معلقة؛ مجهول يعرض—لا صفرًا مخترعًا | `routes/auth.py`, `schemas.py`, `services/lmsService.ts`, `types/lms.ts`, `views/ProfileView.tsx`, `components/ProfileModal.tsx` | D: enrollment count؛ 0؛ 1/0/0؛ API unit يغطي العدّين والنطاق | أصلح واختبر |
| R13 | الصف في URL فقط؛ إرسال لكل المؤسسة | `target_grade` و`course_id` صريحان؛ الجمهور في السيرفر طلاب مقررات المدرس والصف المطلوب، لا مدرس آخر أو طالب غير مرتبط | `schemas.py`, `services/platform_service.py`, `services/lmsService.ts` | D: wrong-grade delivery؛ 0؛ 1/0/0؛ DB recipient isolation في unit | أصلح واختبر |
| R14 | OCR يفقد حروفًا وفراغًا ويشوّه3أسئلة الأحياء رغم العدد الصحيح | استعادة dotted blanks من نفس الصورة والهندسة، دون كلمات/إجابات تخمينية؛ CER تحسن، لكن3أسئلة لا تزال غير مطابقة | `services/ocr_quality.py`, `services/document_parsers.py`, `tests/test_ocr_quality.py`, `tests/test_extraction_contract.py` | F النهائي بعد recovery/load/restore:1؛ 6/1/0، biology7/10 | مفتوح، تحسن جزئي فقط |
| R15 | خط Arabic وحيد بلا glyphs لاتينية | shaping عربي مرة واحدة وglyph fallback للاتينية والرموز، لا حذف/تبديل محتوى السؤال؛ فشل واضح إن الرمز غير متاح | `services/assignment_sheet.py`, `infra/Dockerfile.api`, `tests/test_assignment_pdf_fonts.py`, `scripts/qa_assignment_pdf.py` | D: Latin PDF؛ 0؛ 1/0/0؛ unit glyph/science، ومراجعة صفحة عربية/إنجليزية/مختلطة/علمية بصريًا أثناء الإصلاح | أصلح واختبر للحروف/الرموز التي شملها الاختبار، لا ادعاء كل Unicode |

## سجل الأوامر والنسخة النهائية

P/F/S تعني Passed/Failed/Skipped؛ «—» لأوامر البناء/المسح التي ليست مجموعات tests.
النتيجة الجارية ليست Passed. سجلات JSON/JUnit/SARIF الخام داخل `.qa/audit2/`
المتجاهلة؛ لا تُنشر traces/cookies/secrets أو بيانات حسابات المستخدم.

| الأمر | Exit | P/F/S أو النتيجة | الدليل |
|---|---|---|---|
| `run-video.ps1 -Stage Build` | 0 | —؛ API/migration/worker/web/encoder/QA وup --wait | `video-commands-Build-20261004-174251.json` |
| QA `pytest tests --ignore=tests/integration -q` | 0 | 209/0/0 | `role-api-unit-read-budget-final.xml` |
| Playwright focused `--grep 'avatar\|explicitly selected'` | 0 | 4/0/0 | `role-focused-avatar-course-final.xml` |
| `npm run lint` | 0 | صفر errors،3warnings Fast Refresh development | Browser command ledger |
| `npm run build` | 0 | تحذير chunk مشغل الفيديو633.87kB، لا رفع threshold لإخفائه | Browser command ledger |
| `npm test` | 0 | 20/0/0 | Vitest actual output |
| `run-video.ps1 -Stage Browser` بعد إعادة إنشاءWeb | 0 | 64/0/0، 323.204s؛ npm audit صفر vulnerabilities | `video-commands-Browser-20261004-183312.json` / `video-browser-Browser-20261004-183312.xml` |
| `run-video.ps1 -Stage Integration` على الصور الأخيرة | 0 | 31/0/0، 616.289s | `api-integration-video-20261004-175348.xml` |
| `verify-runtime-source.ps1` ثم `git diff --check` | 0 /0 | API72/encoder72/web89ملفًا، صفر اختلافات؛ صورة Web الحالية مطابقة؛ بلا أخطاء diff | `runtime-source-*.json` |
| `run-role-discovery.ps1` بعد recovery/load/restore | wrapper1؛ D0/F1/diff0 | D20/0/0؛ F6/1/0؛ كل الحالات دون skips/masks | `role-commands-20261004-182725.json`, `role-browser-20261004-182725.xml`, `role-extract-20261004-182725.json` |
| `run-role-discovery.ps1` بعد إصلاحDocker،5أكتوبر | wrapper1؛ D0/F1/diff0 | D20/0/0؛ F6/1/0؛ إعادة فعلية لا إعادة تسمية للنتائج السابقة | `role-commands-20261005-102252.json`, `role-browser-20261005-102252.xml`, `role-extract-20261005-102252.json` |
| `run-video.ps1 -Stage Assets` | 0 | بصمات5أصول ووجود85مخرج HLS؛ anonymous S3 GET403 | `video-commands-Assets-20261004-180432.json` |
| `run-video.ps1 -Stage Recovery` | 0 | queue/outage/crash، attempt2، generation ready واحدة، recovery27.326s؛ Range206 وأصل مطابق | `video-commands-Recovery-20261004-180436.json` |
| `run-video.ps1 -Stage Load` | 0 | 1/5/10جلسات ×180s؛ صفر errors بكل مرحلة؛ التفاصيل أدناه | `load-20261004T181533Z.json` |
| `video-storage-drill.ps1` | 0 | 23أمرًا Exit0؛ 990كائنًا SHA/metadata مطابقًا؛ 51جدولًا/20840صفًا مطابقًا؛ browser1/0/0 | `video-storage-20261004t181534z-fdb0d8b5.json` / `restored-video-20261004t181534z-fdb0d8b5.xml` |
| Scout الصورتين الأخيرتين | wrapper1؛ Scout2/2 | API6 HIGH /worker10 HIGH؛ صفر CRITICAL | `scout-video-*-20261004-174630.sarif` |
| `run-ocr-paddle.ps1 -Mode lines`،5أكتوبر؛ QA-only | 1 | 0/2/0ملفات؛ PDF4/10 وPNG3/5 أسئلة مطابقة | `paddle-candidate/result.json` (أول line run) |
| `run-ocr-paddle.ps1 -Mode words`،5أكتوبر؛ QA-only | 1 | 0/2/0ملفات؛ PDF7/10 وPNG4/5؛ رفض اعتماد النموذج | `paddle-candidate/result-words.json` |

## المحاولات الفاشلة ليست نجاحًا نهائيًا

- baseline discovery `20261004-155151`:1/15/0، Exit1؛ baseline fidelity6/1/0.
- أول frontend كامل:56/4/0؛ duplicate error text في نافذة النشر أصلح، ثم نجحت
  الحالات الأربع في الجولات التالية. لم نغيّر assertion ليقبل خطأً مخفيًا.
- full62:60/2/0؛ helper استخدم hash بدل زر الدخول بعد logout، فأصلح navigation.
- full64 على `cbf68b53…`:60/4/0. سبب جديد حقيقي: GET avatar/profile يُحسب auth،
  فيمنع logout بـ429. reproduction unit قبل التعديل12/6/0 ثم18/0/0 بعده.
  ALL credential mutation budgets باقية؛ لا تعطيل rate limiting أو مسح user keys.
  السببان الآخران في R08 كانا GET /{id} غير موجود؛ الآن يُقرأ السجل من collection
 200 مستقلة ويُتحقق من id/course/lesson ومن غيابه عن المقرر الخاطئ، لا مجرد201.
- integration السابق على `3171b8b9…`:29/2/0، Exit1. فشل حد5GiB أعاد500؛ سبب
  SDK الفعلي غير مثبت. أضيف diagnostic للنوع فقط دون token/URL، ومعالجة503 لأخطاء
  التخزين الفعلية دون تحويل RuntimeError البرمجي إلى503. focused live2/0/0 ثم
  ALL integration على `cbf68b53…`:31/0/0 في698.519s. لا يُعلن أن السبب العارض
  أُزيل لمجرد أنه لم يتكرر؛ المجموعة على صورة7c65 نجحت أيضًا31/0/0 في616.289s.
- فشل cleanup harness كان ينتظر بقاء كائن مطلوب حذفه بعد التعافي. readiness
  أصبحت head_bucket، مع بقاء assertions للـoutbox أثناء الانقطاع ثم حذف الملفات
  والصفوف بعده. ليس استبعادًا للتنظيف أو تنازلًا عن التحقق.
- run integration متداخل سابقًا مع Browser أوقف وخرج137؛ تجربة غير صالحة، ليست
  فشل منتج ولا نجاح اختبار، ولم تُستخدم دليلًا نهائيًا.
- الفحص الأخير كشف Web يعمل بصورة`e15f1e1b…` بدل tag`8cb4a7fb…`.
  كل الملفات المنشورة وnginx config متطابقة، لكنه اختلاف هوية حقيقي: أُعيد إنشاء
  Web صراحةً على8cb وأُعيدت مجموعةBrowser. أداةruntime أصبحت تتحقق منWeb أيضًا.
  build محلي دونVITE_API_URL قد يستعمل`.env.local`؛ أُعيدbuild مع`/api/v1`،
  و89ملفًا/إعدادًا تطابقت بالبايت. wrapper الآن يضبط نفس القيمة صراحةً.

## Extract: حدود التحسن

نسخة OCR `v7-bounded-108dpi-source-placeholders` تمنع استعمال cache القديمة.
آخر strict مقارنة:6ملفات ناجحة و1فاشل؛ text PDFs الأربعة، negative PDF والصورة
المستقلة مطابقة، PDF الأحياء7/10. CER كان0.02161383 ثم0.00864553.
تبقى حروف في اختيار3، و«بـ»/علامة نهاية في6، و«ينقل/المصنّع» في7.
`needs_content_review=true` باقٍ، دون اختراع answer key أو marks.

تجارب دقة/دقة عرض/PSM/لغة/model/crops/consensus لم تُعتمد عندما خرّبت سؤالًا
صحيحًا أو الصورة المستقلة. أدواتها QA-only محفوظة، والمرجع من نسخ بصري مستقل
للمصدر؛ لا يدخل المصحح أو code runtime. لم توجد Word blind عينة في مجموعة
المستخدم هذه؛ نجاح DOCX unit لا يساوي ضمان تطابق كل Word حقيقي.

مهارة PDF أثّرت في التحقق البصري لورقة الواجب: العربية والإنجليزية والنص المختلط
والرموز H₂O/Na⁺/→/ΔH/−/x²/β/×/10⁻³/°C، لا نجاح تنزيل200 وحده.

## اختبارات التعطل والتعافي على إعداد الإنتاج المحلي

طلبات حقيقية أثناء إيقاف كل خدمة ثم استعادتها؛ كل مرة انتهت readiness200 وبقيت
مجموعة معرفات المقررات كما كانت. هذه اختبارات API/شبكة، لا ادعاء مراجعة بصرية
للواجهة أثناء كل واحد من الانقطاعات السبعة؛ انقطاع الشبكة و429 لهما browser منفصل.

| الخدمة المتوقفة | نتيجة الطلب أثناء التعطل | زمن الطلب بالثانية |
|---|---|---|
| PostgreSQL |503|7.738|
| Redis |503|3.931|
| SeaweedFS |503|17.890|
| worker |200؛ الطلب لا يتطلب إنهاء مهمة الخلفية|0.027|
| SMTP |200 عام لحماية خصوصية الحساب؛ فشل التسليم مسجل، لا بريد مُسلَّم|4.011|
| web |504|3.006|
| proxy |connection error|3.964|

اختبار crash العامل/QoS نجح في113.711s. رفع الفيديو الكامل عند حد5GiB نجح على
الصورة الأخيرة في149.7s مع مطابقة SHA، دون OOM/restart؛ ذروة anonymous buffer
407,896,064bytes دون512MiB. ذروة raw memory نحو1.610GB وworking set نحو1.529GB؛
لا تُخفى زيادة accounting العابرة عند سقف1.5GiB. هذا لا يثبت سبب500 السابق.

## الحمل المتدرج وحدوده

فيديو صالح35,382,809bytes وPDF25,928,857bytes. لكل مرحلة180ثانية فعلية تقريبًا؛
تصفح مقررات/bootstrap/إشعارات/progress، وطلبات مقاطع HLS/Range512KiB متغيرة،
و5رفعات PDF إجمالًا، بحد رفعين متزامنين. ليست10مشغلات متصفح كاملة ولا اختبار
ضغط لبوابة الرفع المباشر للفيديو: فيديو الحمل seeded في مخزن QA الخاص.

| الجلسات | الطلبات | throughput req/s | p95 ms | p99 ms | أخطاء |
|---|---|---|---|---|---|
|1|659|3.66|37.56|102.38|0|
|5|3256|18.04|47.99|129.70|0|
|10|6244|34.59|91.55|195.38|0|

عند10جلسات: browse p95/p99=85.58/201.19ms، الفيديو94.13/181.03ms، رفع PDF
3580.67/3580.67ms لعَيّنتين فقط؛ لا تقدير موثوق لذيل رفع الملفات من هذا العدد.
38عينة موارد،0sampling errors؛ الفاصل الفعلي نحو14s بسبب قراءات Docker stats
التتابعية، وليس ادعاء دقة2s. ذروة الذاكرة bytes: API497,344,512، worker66,408,448،
S3 1,073,098,752، PostgreSQL109,060,096، Redis10,866,688، encoder90,275,840،
gateway27,963,392. CPU% المرصود الأقصى بالترتيب نفسه:
77.36/7.66/13.62/11.30/2.59/3.31/4.04. اتصالات PostgreSQL20، active2.
لا429في هذا الحمل؛ الأداة ترسل مرة واحدة دون retry، واختبارات429الحقيقية منفصلة
نجحت. لا استنتاج1000مستخدم أو كل شبكات/أجهزة المشاهدة من هذه الأرقام.

## بقاء البيانات والنسخ والاستعادة

أوقف drill جميع الكُتّاب وgateway، أعاد إنشاء SeaweedFS دون حذف volume، وراجع
الأصول والصلاحيات قبل النسخ. استعمل backup صورة API نفسها، لا rebuild من مصدر
متغير. snapshot990كائنًا/9,663,148,198bytes إلى مجلد QA؛ استعادها إلى volume S3
جديد وقاعدة PostgreSQL فارغة جديدة. صفر SHA256 mismatches، صفر metadata
mismatches،51جدولًا/20840صفًا وصفر اختلافات.

التطبيق الفعلي وCelery/encoder/gateway عملت على المخزن/القاعدة المستعادين:
الفيديو/المذكرة/الإيصال وبصماتها و3Range checks وملكية الموارد نجحت؛ HLS206،
مقطع anonymous403، manifest بعد إبطال الجلسة403. missing-multipart أعاد حالة
expired200 وcompletion409 وintentجديد201 وcleanup204، دون500. متصفح حقيقي رفع
فيديو جديدًا وانتظر الترميز وشغّله وseek وتحقق من الإبطال:1/0/0 في51.213s.
عاد الإعداد الأصلي وكل كُتّابه إلى healthy وHTTPS readiness200؛ أُوقفت خدمتا
restore فقط، وحُفظت volumes الأصلية والجديدة والنسخ، ولم تُحذف بيانات المستخدم.

## ما يمنع إعلان الجاهزية

1. R14 ليس مطابقًا بالكامل؛ بوابات الحمل/النسخ/الاستعادة المذكورة نجحت محليًا،
   لكنها لا تعوّض إخفاق دقة Extract.
2. تنبيهات المكتبات الأصلية HIGH باقية بلا suppression أو توزيع unstable.
   النسخ والمسارات والتخفيف وحالة stable في `QA_SECURITY_RECHECK_2026-10-04.md`.
3. سبب500 العارض السابق عند الحد5GiB لم يُثبت أنه أُزيل، رغم نجاح إعادات حية.
4. لا سيرفر/شهادة عامة أو CDN/DRM خارجي مختبر؛ HLS المحمي بالجلسة والاستحقاق
   ليس DRM ولا ضمانًا مطلقًا ضد نسخ البايتات أو تسجيل الشاشة.
5. لا قياس يثبت1000مستخدم نشط؛ الحمل المحلي المحدود لا يبرر ذلك الاستنتاج.

تعليمات إعادة التشغيل من نسخة نظيفة: `QA_ROLE_REPRODUCTION.md`.

## استئناف5أكتوبر

Docker Desktop تعطل في Secrets Engine/socket قبل المحرك، وليس في API الموقع.
أُعيد تشغيله بعد حفظ مجلدsocketالصغير باسم آخر، دونfactory reset أو حذفvolumes؛
التفاصيل والحدود في `QA_DOCKER_RECOVERY_2026-10-05.md`. فحصruntime بعد عودته:
API72/encoder72/Web89، صفر اختلافات،Exit0؛ لا تُنسب نتائج4أكتوبر إلى تشغيل جديد.

تجربتاOCR إضافيتان محليتان بلاnetwork وقت قراءة الصور، وليستا featureAI جديدة:
النموذج مثبت بالبصمة، Paddle3.2.0/OCR3.3.2/X3.3.13 فيvenv وصورةQA فقط.
المحاولة الأولية افتقدتlibGL وخرجت1قبل قراءة المصدر؛ وُفرت المتطلبات في صورة
تجريبية منفصلة، ثم نفذت المقارنة فعلًا. line CER فيPDF0.01873199 وPNG0.10277778،
word CER فيPDF0.01440922 وPNG0.01036269؛ كلاهما أسوأ من قارئ التطبيق الحالي.
لم تُخفَ الأسئلة الفاسدة أو تتغيرassertions ولم تُعتمد dependencies/المخرجات
فيproduction. أدوات التجارب موجودة لإعادة التشغيل، لا دليل «أُصلحR14».

بعد عودةDocker أُعيدتdiscovery كاملة20/0/0 ثمfidelity6/1/0 وdiffcheck0؛
wrapper1 صادق بسببR14. readiness عبرurllib فيAPI200،Exit0. محاولة diagnostic
أولية باستخدامrequests خرجت1لأن الحزمة غير مثبتة فيAPI؛ لا عيب منتج ولا نجاح
health يُستنتج منها. PowerShell syntax للأدوات الثلاث:0errors،Exit0.
فحص أسرار نصي محدود لـ46ملفًا معدّلًا/جديدًا داخل نطاق المنصة:لا تطابق،Exit0؛
ليس بديلًا عن فحص أمني شامل. `.qa` والأسرار والنماذج والنسخ/traces ignored،
ومجلدPCغير متعلق محفوظ خارجcommit الإصلاحات.
