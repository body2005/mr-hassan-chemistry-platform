# تسليم المراجعة المحلية — 9 أكتوبر 2026

هذه نتيجة إصلاح واختبار محلي، **وليست موافقة نشر**. الكود رُفع إلى
`fix/queen-p0-handoff` عند `6796750664151e180054018ea4fdc97242d46bcb`؛ تحقق التطابق
عبر `git ls-remote` وGitHub API، Exit0. فحص تاريخ الـcommits الثلاثة غير المرفوعة
وقت الفحص:0 أسرار، Exit0. بقي المشروع غير المرتبط خارج Git.

**ملاحظة تاريخية بعد الرفع السابق:** تكامل `vercel[bot]` الموجود نفّذ
نشرًا تلقائيًا لهذا SHA، deployment6960376648، وحالةsuccess. اسم البيئة فيGitHub
`Production` لكن `production_environment=false`؛ لا يمكن الجزم بتغيير النطاق
الإنتاجي من هذا الاسم وحده. عنوان النشر المسجل:
https://mr-hassan-chemistry-platform-ptgtyo6db-body19.vercel.app
لم أطلب نشرًا مستقلًا ولم أختبر هذا السيرفر. أوضح المستخدم لاحقًا أن Vercel
خارج نطاق العمل وأن الرفع العادي مسموح؛ لم أغيّر إعداداته أو أنفّذ rollback.
ثم طلب تنفيذ العمل محليًا والرفع فقط دون تشغيل GitHub Actions: طُلب إلغاء
التشغيل السابق Exit0، والـcommit التالي يحمل `[skip ci]` دون تعطيل البوابات.
CI السابق `Review quality gates`: frontend/secrets نجحا، backend فشل؛ ليس نجاحًا كاملًا:
https://github.com/body2005/mr-hassan-chemistry-platform/actions/runs/37928630587

الاختبارات على `chemistryaudit2` فقط. لا دمج أوforce push أوSMS أو ترجمة نصية
للفيديو أو صور شخصية؛ OCR الأحياء مؤجل.
حد OCR المحفوظ: المقارن الصارم السابق6/1/0، وملف الأحياء7/10 أسئلة مطابقة.
لم يُعد هذا الاختبار ولم تُخفّف المقارنة؛ التأجيل لا يعني اكتمال الدقة.

## استكمال محلي بعد توجيه «ارفع فقط»

| العائق | قبل / السبب | التغيير والنتيجة المحلية | الأمر / Exit / Passed-Failed-Skipped |
|---|---|---|---|
| تجهيز backend في CI | GitHub:468P/1F/0S، Exit1؛ native Expat2.6.1 وPython2.8.5 بدل2.9.0 | `quality.yml` يبني API ثم طبقة `Dockerfile.qa` المطابقة؛ لا حذف أو mock للاختبار. تعذر `FROM sha256:…` في المحاولة الأولى Exit1؛ صُحح بمرجع محلي مع فحصID قبل/بعد، ثم نجح البناء Exit0 | `pytest scripts/qa/tests/test_ci_backend_environment.py tests/test_native_expat_security.py` داخل طبقة QA الجديدة: Exit0،4/0/0؛ `ci-backend-environment-20261009.xml` |
| صعوبة تشخيص502 بلا تسريب | السجل القديم لا يميّز وقت الاتصال عن وصول headers؛ سبب واقعة logout الأصلية غير مثبت | `apps/web/nginx.conf` وملفا `infra/nginx*.conf` يسجّلون upstream address/connect/header/response فقط؛ no raw query/cookies/Authorization.3 حالات Nginx فعلية معزولة اختبرت200/503/502 والتسريب | `pytest scripts/qa/tests/test_proxy_diagnostics_live.py`: Exit0،3/0/0؛ `proxy-diagnostics-20261009.xml`. ليست إصلاحًا مثبتًا لواقعة502 الأصلية |
| تشغيل نسخة التجربة بعد تغيير config | ضرورة تفعيل التشخيص دون إعادة مجموعات التطبيق | بناءweb فقط، `nginx -t` للـweb/proxy وreload؛ API/encoder/DB/S3 دون إعادة بناء أو تغيير | build/up/config/reload Exit0؛ صفحةHTTPS200. تحذير chunk631.81KB باقٍ، لا فشل build |
| حسابات التجربة عند التسليم | التحقق من صلاحية بيانات الدخول، لا إعادة رحلة كاملة | `scripts/qa/handoff_smoke.py`: TLS موثوق، login200/me200/logout204 لكل دور؛ لا reset أو طباعة tokens | `python /qa-tools/handoff_smoke.py`: Exit0؛2 أدوار ناجحة،0 فاشل، ليست مجموعةpytest |

التشغيل البعيد لإصلاحCI الجديد **لم يُنفذ بطلب المستخدم**؛ نجاح الاختبار
المحلي لا يُسمّى نجاحGitHub. `[skip ci]` يمنع تشغيلات push/pull_request لهذا
الـcommit فقط؛ الفحوص المطلوبة قد تبقى Pending ولا يجيز ذلك الدمج:
[توثيق GitHub](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/skip-workflow-runs).
الاختبارات القديمة الناجحة لم تُعد؛ فحص Expat أعيد وحده لأنه المتأثر بتجهيزCI.

للتجربة على هذا الجهاز: https://localhost:18543/، مؤسسة `demo`.
المدرس `teacher@demo.com` / `qa-teacher-pass`؛ الطالب `student01@demo.com` /
`qa-student-pass`. حسابات اصطناعية محلية فقط، ليست بيانات نشر.
جرّب إنشاء درس ورفع فيديو/مذكرة، نشرQuiz وواجب، ثم من الطالب التشغيل وseek
وحل الاختبار وتسليم الواجب، ومن المدرس التصحيح. جرّب التسجيل بخطوتين وتغيير
كلمة المرور. تنبيهات الصور وسبب502 والحمل الخارجي وOCR الأحياء ليست مغلقة.

## ما نُفذ في الاستكمال الأخير

احترامًا لطلب عدم التكرار، لم تُعد مجموعات Backend464 أو Frontend213 أو
Browser93 أو Integration60 الناجحة. أُبقيت النتائج مرتبطة بالصور التي اختبرتها.
التشغيل المحدد للحالات الجديدة الفاشلة لا يُعرض باعتباره نجاح المجموعة الكاملة.

| العائق / السبب قبل الإصلاح | بعد الإصلاح | الملفات | الأمر والدليل المحلي تحت `.qa/audit2` | Exit؛ ناجح/فاشل/متخطى |
|---|---|---|---|---|
| دفعة أحداث فيديو تنشئ عدة سجلات تقدم مع `autoflush=False`؛ PostgreSQL500 | إعادة استخدام سجل الدرس داخل الدفعة وقفل الطالب عبر الطلبات؛ لا مضاعفة للسجل أو وقت المشاهدة | `apps/api/app/api/routes/telemetry.py`, `platform.py`؛ اختبارا telemetry الجديدان | pytest المحدد: `telemetry-batch-after-20261009.xml`؛ TCP/PostgreSQL المتزامن: `telemetry-postgres-after-20261009.xml` | 0؛10/0/0 محليًا،0؛3/0/0 PostgreSQL؛ قبلها PostgreSQL0/3/0 Exit1 |
| الحدث الأول قبل وصول مدة الفيديو يقارن `None >= 100`؛500 | تهيئة نسبة التقدم0.0 قبل INSERT، ثم تحديثها عند وصول المدة | `telemetry.py`, `tests/test_telemetry_batch_review.py` | pytest `::test_first_browser_event_before_metadata_has_zero_completion`؛ `telemetry-no-duration-{before,after}-20261009.xml` | قبل1؛0/1/0،بعد0؛1/0/0 |
| إجابة المقالي14px في فحص القراءة الجديد |16px وline-height1.6؛ Cairo وRTL وألوان المنصة محفوظة | `apps/web/src/views/MyCoursesView.tsx` | `run-trusted-browser.ps1 -Build -SpecPattern qa/reading-matrix.spec.ts -Grep 'student study/video/quiz/homework'`؛ `trusted-browser-20261009-114742/{browser.xml,command.json}` |0؛2/0/0؛ استجابات أحداث الفيديو202 حقيقية |
| فحص تكبير الواجب يمرّر الخلفية بدل نافذة الواجب المستقلة ويصطدم بالـsticky header | إصلاح أداة الفحص للتمرير في أقرب حاوية فعلية؛ شروط hit-test والتكبير لم تُخفف، ولا تعديل CSS لإخفاء المشكلة | `apps/web/tests/qa/reading-matrix.spec.ts` | نفس التشغيل المحدد السابق؛ لقطات320×720 و640×360 والوضعين والتكبير الحقيقي2 عبر Chromium |0؛2/0/0؛ ليست شهادة هاتف فعلي أو تكبير شريط المتصفح |
| قاعدة بيانات جديدة بعد ترحيل snapshots لم يكن لها دليل استعادة حديث | استعادة في PostgreSQL جديد ومقارنة53 جدولًا/54,192 صفًا،0 اختلاف،head=`f4a6c8e0b2d4` | `scripts/qa/video-storage-drill.ps1 -DatabaseOnly`؛ الترحيل `apps/api/alembic/versions/f4a6c8e0b2d4_quiz_evidence_snapshots.py` | `video-storage-20261009t115157z-d18ba302.json`؛ كل الكتّاب مجمّدون أثناء المقارنة ثم استعادة readiness |0؛12 خطوة أوامر، ليست12 pytest؛ لا إعادة نسخ S3/الفيديو |
| البناء النظيف كان يعيد مجموعات ناجحة بالكامل | وضع اختياري صريحBuildOnly؛ البوابات الافتراضية وCI بلا تخفيف؛ البناء النظيف نجح | `scripts/qa/check-clean.ps1`, `docs/QA_TRUSTED_BROWSER.md` | `check-clean.ps1 -BuildOnly`؛ `clean-results-20261009-115723/commands.json`؛ تصديرindex،Gitleaks بلا أسرار،npm ci،بناء Web/API،90 بصمة ملفات واجهة متطابقة |0؛6 خطوات ناجحة،3 NOT RUN للـlint/الوحدات الكاملة؛ ليست3 اختبارات متخطاة |

فحص القراءة الجديد اكتمل6 حالات عبر تشغيلات محددة3+1+2. لم تُعد الحالات
الناجحة الأربع للزائر/المدرس في التشغيل الأخير. أداة الاختيار `-Grep` تحفظ
الاختيار ومعرفات الصور في `command.json`؛ افتراضي المجموعة الكاملة لم يتغير.
الفحص الجديد وجد logout502 مرة واحدة؛ نجاح204 اللاحق لا يثبت سببها أو إصلاحها.

## بنود الطلب المكتوب21

المراجع التفصيلية وأوامر الإثبات والصور التاريخية موجودة في
[سجل التنفيذ](QA_REVIEW_PROGRESS_2026-10-09.md). «نجح سابقًا» هنا لا تعني إعادة
اختباره ولا تنقل أرقامه تلقائيًا إلى صورة أحدث.

| # | النتيجة والحدود | مسارات الإصلاح الرئيسية |
|---:|---|---|
|1| نسب التقارير والمقامات والمحاولات المسلّمة/المصحّحة والصفر/الإعادة: نجاح Backend السابق محفوظ | `analytics_report.py`, `test_analytics_units_review.py` |
|2| حفظ أوزان/محتوى التقييم التاريخي؛ البيانات القديمة غير المثبتة لا يعاد تفسيرها؛ ترحيل PostgreSQL واختبار الاستعادة الجديدة أعلاه | `quiz_snapshot.py`, `extended_service.py`, migration f4 |
|3| سياسة واحدة للإنشاء والنسخة المدمجة والنشر؛ MCQ2–26 ومفاتيحA–Z، ورفض27 بلا500 | `question_policy.py`, `extended_routes.py`, `mcqOptions.ts` |
|4| رفض الأسرار الافتراضية/المكشوفة عند التشغيل؛ قالب Compose القديم fail-closed وليس بديل TLS ضعيف | `config.py`, `compose.prod-like.yml`, اختباراتstartup |
|5| رفع الحدود الحقيقية1GiB/5GiB وحالة+1 بايت والتخزين والleases: Integration60 السابق محفوظ؛ لا ادعاء قدرة حمل من اختبارات الحدود | `storage_async.py`, `lesson_materials.py`, `leases.py` |
|6| بوابة الثغرات OPEN؛ فحص الصور الجديدة وعدم إخفاء أي تنبيه، والتفصيل لكل CVE في التقرير الأمني | `docs/NATIVE_CVE_REVIEW_2026-10-06.md`, أدواتScout/Trivy |
|7| تعافي encoder الحقيقي نجح سابقًا؛ استعادة S3 الكاملة25 خطوة سابقة محفوظة؛ استعادة قاعدة البيانات الجديدة12 خطوة نجحت دون تكرارهما | أدواتRecovery/Storage/DatabaseOnly |
|8| حمل25/100/250/500×10د يحتاج staging مخصصًا؛1/5/10×180ث السابقة لا تثبته ولم تُكرر | `qa_load.py` وأدلةالحمل/runbook |
|9| البناء النظيف المحدود والرفع والتحقق منSHA؛ Actions الخارجية لا تُعلن ناجحة قبل نتيجتها | `check-clean.ps1`, `.github/workflows/quality.yml` |
|10| auth scope/401 مقابل الشبكة/refresh/revocation/multi-tab: نجاحBrowser93 السابق محفوظ؛502 العارضة أعلاه مفتوحة | `useProtectedPlayback.ts`, `lmsService.ts` |
|11| فصل مسؤوليات حماية المشغل والتحقق/خطوات النشر؛ الاختبارات الوظيفية السابقة محفوظة، لا ادعاء أداء من عدد الأسطر | `QuizEditorJourney.tsx`, `assessmentPublication.ts`, `useProtectedPlayback.ts` |
|12| TLS محلي موجب/سالب موثوق داخل QA؛ لا نطاق عام/CDN/DRM أو سيرفر خارجي مختبر | قالبالإنتاج،TLS runner |
|13| بحث وفلترة فعلية للزائر والطالب، click/touch،reset/empty/persist: نجاحBrowser السابق محفوظ | `LandingPageView.tsx`, `usePublicCatalog.ts`, `courses.py` |
|14| إنجاز المقرر المختار وبناءالنسبة على التسليم الحقيقي وعدم تغطية محتوى الهاتف: نجاحDOM/Browser محفوظ | `FloatingProgressFab.tsx`, `assessmentOutcome.ts`, `platform.py` |
|15| التباين الداكن الفعلي/hover: نجاح Browser محفوظ | `index.css`, `discovery.spec.ts` |
|16| عنوان ثابت دون مؤقتات الكتابة والحذف؛ نجاح DOM محفوظ | `LandingPageView.tsx` |
|17| تحذيرات/أخطاء ثابتة قرب الإجراء، قراءة مناسبة ومنع التكرار؛ نجاح DOM/Browser محفوظ | `ToastProvider.tsx`, `QuizGeneratorView.tsx` |
|18| تسميات reset/الشروط/الإكمال وإرسال Mailpit واستعادة فعلية: نجاح Browser محفوظ؛ تسجيل خطوتين بلا SMS | `AuthView.tsx`, `PasswordResetLabels.test.tsx` |
|19| إعداد←مراجعة←نشر واضح على الهاتف مع حفظ المسودة ومراجعة المصدر وإعادة المحاولة؛ نجاح Browser محفوظ وفحص قراءة المدرس الجديد ناجح | `QuizEditorJourney.tsx`, `QuizGeneratorView.tsx` |
|20| القراءة وأهداف لمس الفيديو؛ فحص الجوال/الأفقي/التكبير/الثيمات الجديد مكتمل عبر التشغيلات المحددة أعلاه | `index.css`, `VideoLessonPage.tsx`, `MyCoursesView.tsx` |
|21| CTA صريح بضرورة التسجيل، وحفظ نية المقرر، ولا نجاح اشتراك قبل استجابة السيرفر؛ نجاح Browser محفوظ | `catalogState.ts`, `authNavigation.ts`, `App.tsx` |

## حدود القبول

فحص الصور الفعلية الجديدة بعد نجاح المتصفح:

| الفحص | API | Encoder | Exit | الدليل تحت `.qa/audit2` |
|---|---|---|---|---|
| Scout |3 High/0 Critical|3 High/0 Critical|2 لكل صورة،1 للتحكم|`scout-video-{api,video-worker}-20261009-115314.sarif`|
| Trivy |63 High/21 CVE|79 High/37 CVE|1 لكل صورة وللتحكم|`trivy-20261009-115547/`|

اتحاد38 CVE دون إضافة ID جديد مقارنة بالمراجعة السابقة. التنبيهات المتكررة
لحزم متعددة ليست CVEs مستقلة. التقييم لكل حالة ونسختها والمسار المتأثر في
[المراجعة الأمنية](NATIVE_CVE_REVIEW_2026-10-06.md)، بما يشمل حدود الدليل
للمكتبات المبنية من المصدر وغياب إصلاح رسمي ثابت لبعض الحزم. لا suppression
أو تغيير أسماء نسخ أو انتقال لتوزيعة غير مستقرة. بوابة الصور **OPEN**.

- البناء النظيف نجح Exit0. صورة البناء المعزولة `sha256:42adb4da5f99ace5bb4cc99f6f7eab21ca864c69fc4253047547ce03c54a4f5c` ليست صورة API العاملة/الممسوحة659e1c3f…؛ لم تُنشر أو تحل محلها. الاختلافات الخام بين نصوص التصدير وWindows كانت107 حالات CRLF/LF فقط،0 اختلاف محتوى آخر؛ لا ادعاء تطابق byte-for-byte لـAPI.
- ESLint للملف الجديد بعد آخر تعديل نجح Exit0؛ lint السابق للمشروع بقي0 أخطاء/4 تحذيرات Fast Refresh ولم يُعد بالكامل.
- إثبات رفع GitHub يأتي من مقارنةSHA بعدcommit/push، وليس من وجود هذا التقرير أو بناءDocker. إجراءاتCI الخارجية لا تُعلن ناجحة قبل اكتمالها.
- CVEs المفتوحة و502 غير المشخّصة تمنع إعلان «كل شيء أُغلق» أو جاهزية نشر.
- قياس الحمل الكبير وTLS/CDN/DRM والتخزين الخارجي تحتاج بيئة واعتمادات وتفويضًا خارجيًا؛ Git push ليس deploy.
- استُخدمت مهارتا `ui-ux-pro-max` و`frontend-design` لتوجيه القراءة، الماوس/اللمس، الحفاظ على Cairo/RTL/الأخضر والتغذية الراجعة غير المتداخلة؛ لا عمل كيبورد إضافي خارج طلب المستخدم.
- الأدلة الأصلية الخاصة/التوكنات/المفاتيح و`.qa` و`pc_builder_3d_cases` ليست ضمن رفع المصدر.
