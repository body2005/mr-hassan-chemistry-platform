# مراجعة جاهزية منصة الكيمياء — 30 سبتمبر 2026

> تحديث لاحق في اليوم نفسه: راجع [تقرير قالب الإنتاج وSeaweedFS والاختبارات الكاملة](QA_PRODUCTION_STORAGE_2026-09-30.md). ما أدناه سجل الجولة الأولى، لا الحالة النهائية الحالية.

**القرار: غير جاهزة للنشر بعد.** الإصلاحات الحالية محلية وغير مرفوعة، وفي صورة API خمسة تنبيهات High مفتوحة، وصورة MinIO المثبتة في قالب الإنتاج لا تُسحب من السجل، ولم يُختبر خادم خارجي أو شهادة حقيقية. لا نشر ولا دمج ولا push في هذه الجولة. تقرير 29 سبتمبر سجل تاريخي لا يثبت حالة GitHub الحالية.

## نطاق Git والبيئات

- الفرع `fix/queen-p0-handoff`، و`HEAD=d70eea083e33cca7e042170a9cdd7c74aab3e44d` بتاريخ 25 سبتمبر؛ مرجع `origin/fix/queen-p0-handoff` المحلي المخزن هو الـSHA نفسه. `git log origin/fix/queen-p0-handoff..HEAD` و`git diff --cached --name-only` فارغان: **صفر commit محلي زائد، وصفر تعديل staged**. كل الملفات المدرجة في `git status --short` تعديلات working tree غير محفوظة في commit أو ملفات جديدة. من بينها `apps/api/app/core/access_log.py` و`apps/web/playwright.qa.config.ts` واستبدال `xlsx`، لذلك لا يجوز نسبتها إلى GitHub. تعذر التحقق المباشر من GitHub: `git ls-remote origin refs/heads/fix/queen-p0-handoff` خرج 1 بسبب `SEC_E_NO_CREDENTIALS`. لا نعرف إن كان الفرع البعيد تغير بعد آخر fetch؛ المعلوم فقط أن المرجع المحلي عند `d70eea0`.
- حُفظت تعديلات freebuff على Extract. لم تُستخدم `reset` أو `rebase` أو `force push`. بعد انتهاء عمله أُصلح ترتيب جداول Word وOCR الصور المضمنة، وأعيد بناء API والواجهة. المدخلات الستة المنسوخة من `science_extract_blind_inputs` مستخدمة كـfixtures؛ اختبارات البنية/الترتيب/علامات مراجعة OCR نجحت، لكنها ليست ضمان دقة نصية كاملة لكل PDF أو صورة أو Word.
- المشروع الجاري للتجربة هو **`chemistryqa` فقط** على loopback: الواجهة `http://127.0.0.1:18080`، API `18000`، PostgreSQL `15434`، Redis `16379`، S3 QA `19000`، Mailpit `18025`. حسابات وملفات اصطناعية. المشروع والـvolumes السابقة حذفها المستخدم عمدًا؛ لم تُستعد. لم يُختبر production Compose الحالي تشغيلًا، ولم يُختبر سيرفر خارجي.
- مخزن QA الحالي SeaweedFS 4.48 مثبت بالـdigest وليس MinIO إنتاجيًا. LocalStack السابق فشل اختبار الثبات: السلة اختفت بعد إعادة إنشاء الحاوية وأعاد `/ready` 503. بعد الاستبدال: رفع التطبيق فيديو وإيصالًا، ثم `up -d --force-recreate --no-deps minio api`؛ بقيت 4 كائنات، وتطابقت بصمة الفيديو `fa6fb82c…d1` والإيصال `af9cb484…7f1`، وعاد `/ready` 200. هذه بيانات QA فقط ولا تثبت ترحيل بيانات إنتاجية.

## بوابات الإصدار — قبل/بعد ودليل حي

في عمود العدّ، `ناجح/فاشل/متخطّى` خاص بالأمر المذكور، و`—` يعني أنه ليس تشغيل مجموعة اختبارات. اختصار `DC` أدناه يعادل `docker compose -f scratch/qa-compose.yml -p chemistryqa` من جذر المستودع؛ أمر Docker نُفذ بمسار `docker.exe` الكامل على Windows.

| العائق | قبل / السبب | بعد والحالة | الملفات المتغيرة الأساسية | الأمر والدليل الحي | Exit؛ ناجح/فاشل/متخطّى |
|---|---|---|---|---|---|
| تباين Git والتقرير | التقرير أحدث من HEAD البعيد المخزن؛ ملفات الإصلاح لم تكن commits | تغييرات محلية قابلة للمراجعة فقط؛ GitHub المباشر غير مؤكد | جميع ملفات `git status`، التقرير الحالي | `git branch --show-current`, `git rev-parse HEAD`, `git status --short`, `git diff --cached --name-only`؛ `git ls-remote` فشل اعتمادًا | 0 للفحوص المحلية، 1 للبعيد؛ — |
| ESLint والبناء | تقرير 29 سبتمبر: 27 error و30 warning؛ أخطاء Hooks/typing/Extract | 0 error، 3 تحذيرات Fast Refresh تطويرية لا تشير إلى خلل runtime معروف؛ build ناجح | `apps/web/src/**`, `apps/web/package*.json` | `npm run lint`; `npm run build`; `npm run test -- --run` من `apps/web` | 0/0/0؛ lint 0 خطأ و3 تحذيرات، build 0، Vitest 5/0/0 |
| اعتماد XLSX | `xlsx` القديم بتنبيهات إنتاجية وتحميل كبير | `write-excel-file` وملف XLSX صالح RTL من الواجهة، audit صفر | `package*.json`, `src/utils/exportEngine.ts` | `npx playwright test -c playwright.qa.config.ts`; `npm audit --package-lock-only --audit-level=high` داخل Node Docker قراءة فقط | 0؛ Playwright 25/0/0، audit 0 ثغرات |
| Extract وOCR | عمل freebuff لم يكن كافيًا لجداول Word/صور Word وترتيب أسئلة PDF ذي عمودين | Word بالترتيب، OCR الصور مؤشّر للمراجعة، six blind PDFs/negative case؛ دقة المحتوى الإنساني لم تُحسم | `document_parsers.py`, `exam_text_extractor.py`, `test_extract_word_and_image.py`, `test_blind_inputs_extraction.py` وfixtures | `DC exec -T api python -m pytest tests/test_extract_word_and_image.py tests/test_blind_inputs_extraction.py -q -ra -o addopts= --basetemp=/tmp/pytest-blind-final`; ثم full API | 0؛ 17/0/0، ثم 137/0/1 |
| الجلسات والاسترجاع | تغيير كلمة المرور/إلغاء الجلسات/البريد لم يكن دليلها حيًا | تسجيل من الواجهة، revoke-all وتغيير كلمة، بريد reset حقيقي عبر Mailpit، رفض القديمة ورابط مستخدم | `auth.py`, `auth_service.py`, `mail_service.py`, `AuthView.tsx`, `ProfileView.tsx`, `auth-reset-ui.spec.ts` | `npx playwright test -c playwright.qa.config.ts`؛ Mailpit API؛ TestClient | 0؛ 25/0/0 شامل الرحلات؛ API 137/0/1 |
| حدود الملكية والدفع والتصحيح والإشعارات | كشف قوائم/موارد خارج نطاق المدرس، بعض استحقاقات التحميل، ورحلات غير مختبرة | عزل مدرس/طالب، دفع بإيصال وموافقة/رفض واستحقاق وإشعار، وتصحيح واجب عبر الواجهة؛ اختبارات رفض 401/403/422 | `platform.py`, `payments.py`, `lesson_materials.py`, `payment-flow.spec.ts`, `api-ownership.spec.ts`, `SubmissionsView.tsx` | `npx playwright test -c playwright.qa.config.ts` على PostgreSQL/S3 الحقيقيين في QA | 0؛ 25/0/0، اختبارات الدفع والملكية ضمنها |
| Quiz المتزامن و429 | قبل الإصلاح `UniqueViolation` و500 عند التسليم المتزامن؛ إعادة تشغيل Playwright سريعًا اصطدمت بحد IP | 8 طلبات PostgreSQL فعلية للـattempt نفسه = 8×200، SQL: 6 محاولات QA متزامنة لكل واحدة إجابة واحدة، 0 زوج إجابات مكرر. اختبارات serial تعزل عدادات QA المؤقتة فقط قبل كل حالة؛ rate limiting الفعلي باقٍ | `platform.py`, `api-ownership.spec.ts`, `qaTest.ts`, `playwright.qa.config.ts` | `npx playwright test -c playwright.qa.config.ts`; استعلام `quiz_attempts` و`quiz_attempt_answers` | 0؛ 25/0/0؛ SQL 0 تكرار |
| روابط الفيديو والأسرار | token URL يُكتب في access log؛ stream لم يعِد فحص الجلسة/الاستحقاق؛ روابط سحابية مباشرة تتجاوز الحماية؛ انتهاء token يعطل المشغل | حجب الرمز بالسجل، ربط stream بجلسة حية وإعادة فحص الاستحقاق، رفض Bearer بلا cookie، تعطيل URL خارجي جديد وإخفاء القديم عن الطالب، تجديد رابط المشغل بعد الخطأ. فحص سجل QA: 9 روابط محجوبة، 0 `token=eyJ` | `access_log.py`, `platform.py`, `courses.py`, `schemas.py`, `VideoLessonPage.tsx`, `LessonManagementView.tsx`, `video-playback.spec.ts` | `npx playwright test -c playwright.qa.config.ts tests/qa/video-playback.spec.ts`; `DC logs --tail 400 api` مع عدّ دون عرض الرموز | 0؛ فيديو 1/0/0؛ كامل 25/0/0 |
| ملفات مزيفة وCSRF/CORS/انقطاع الشبكة | امتداد مزيف يمكن قبوله؛ غياب إثبات حالات الشبكة | تواقيع ملفات، رفض MP4/PDF مزيف 422، CSRF/Origin/CORS، وتعافي bootstrap بلا عاصفة طلبات | `platform.py`, `lesson_materials.py`, `security-boundaries.spec.ts`, `network-recovery.spec.ts` | `npx playwright test -c playwright.qa.config.ts` | 0؛ 25/0/0 شامل حالات الرفض |
| Docker الإنتاجي | منافذ DB/Redis/MinIO عامة و`latest`، ملفات الفيديو غير مثبتة، غياب أسرار/health/backup/HTTPS | قالب محلي: شبكات خاصة، digests، volumes، secrets، health، backup jobs، HTTPS proxy قابل للمراجعة. لكن صور MinIO/`mc` المثبتة ترجع 401 عند pull الآن؛ **بوابة تشغيل الإنتاج مفتوحة** | `infra/docker-compose.yml`, `nginx-https.conf`, `entrypoint-prod.sh`, `PRODUCTION_DOCKER_RUNBOOK.md` | `. .\scratch\prod-qa-env.ps1` ثم `docker compose -f infra/docker-compose.yml -p chemistryprodqa config -q`؛ تجربة QA recreate مستقلة | config 0؛ —. pull MinIO 1؛ لا full production test حالي |
| الثبات في QA | LocalStack مع volume فقد سلة S3 بعد recreate وأنتج ready 503 | SeaweedFS QA بvolume: فيديو وإيصال SHA متطابقان بعد recreate، ready 200؛ لا يماثل اختبار MinIO إنتاجي | `scratch/qa-compose.yml` | `DC up -d --force-recreate --no-deps minio api`; `DC exec -T api python -c ...` لفحص SHA/S3/ready | 0 بعد الإصلاح؛ 4 كائنات / 0 مفقود |
| ثغرات صور Docker | التقرير القديم ذكر 8 High في صورة قديمة حُذفت؛ لا يمكن إعادة بناء قائمتها فرديًا | الصورة الحالية بعد تحديث base والحزم: 0 Critical، **5 High مفتوحة في 4 حزم**؛ صورة web 0. لم تُخف أو تُخفض | `infra/Dockerfile.api`, `infra/Dockerfile.web` | `docker scout cves chemistryqa-api:latest --only-severity high`; الأمر نفسه `chemistryqa-web:latest` | Exit الأداة 0/0؛ High API=5، web=0؛ ليست بوابة خضراء |
| الأداء والسعة | اختبار 10 جلسات لا يثبت 1000 مستخدم | تصفح/فيديو/رفع متدرج 1/5/10 و1/2/4؛ صفر أخطاء في عينات قصيرة؛ لا اعتماد سعة إنتاج | `scripts/qa-mixed-load.mjs` | `node scripts/qa-mixed-load.mjs`, `docker stats --no-stream`, `pg_stat_activity` | 0؛ 1,449 طلبًا/رفعًا، 0 خطأ؛ ليس 1000 مستخدم |
| مجموعة التكامل القديمة | `pytest tests` يجمع ملفات تستورد `requests` غير الموجود في الصورة، وبعضها يقتل worker باسم قديم | لم أضمها خطأ إلى نجاح suite؛ تحتاج فصل harness وتحديث بيئة/أسماء الحاويات قبل الاعتماد | `tests/integration/` لم تُغيَّر | `DC exec -T api python -m pytest tests -q -ra -o addopts= ...` ثم `--ignore=tests/integration` | الجمع الكامل 1، 3 errors؛ المجموعة الاعتيادية 0، 137/0/1 |

## تنبيهات API الخمسة — فرز فردي

Docker Scout على `chemistryqa-api:latest` digest `a84e789f7fa3`، Debian Trixie، 369 حزمة، 0C/5H. النسخ والمواقف أدناه من المسح الحالي ومتتبع Debian؛ «لا يظهر مسار مباشر» لا يعني إثبات عدم الاستغلال.

| CVE / الحزمة في الصورة | هل إصدار Trixie مصحح؟ | الوصول المحتمل من التطبيق والحالة |
|---|---|---|
| [CVE-2026-74860](https://security-tracker.debian.org/tracker/CVE-2026-74860) — `libxml2 2.12.7+dfsg+really2.9.14-2.1+deb13u3` | لا؛ upstream 2.15.3، Trixie vulnerable | الخلل في Python SAX bindings مع DTD؛ التطبيق لا يستدعي binding مباشرة، لكن libxml2 موجودة مع أدوات المستندات؛ لم يُثبت مسار استغلال، يبقى High مفتوحًا. |
| [CVE-2026-86140](https://security-tracker.debian.org/tracker/CVE-2026-86140) — `libxml2` النسخة نفسها | لا؛ upstream 2.15.4، Trixie vulnerable | خلل `xmlSnprintfElements`؛ معالجة مستندات غير موثوقة تجعل استبعاد المسار دون اختبار تعقبي غير مقبول؛ مفتوح. |
| [CVE-2026-93990](https://security-tracker.debian.org/tracker/CVE-2026-93990) — `expat 2.8.3-1~deb13u1` | لا؛ upstream 2.8.5، Trixie vulnerable | UTF-16 XML غير سليم؛ أدوات PDF/metadata مرتبطة بالمكتبة وقد تستقبل مدخلات مستخدم؛ مفتوح. |
| [CVE-2026-85091](https://security-tracker.debian.org/tracker/CVE-2026-85091) — `zlib 1:1.3.dfsg+really1.3.1-1` | لا؛ Debian يقول unfixed | المسار المحدد `gz_vacate` بعد non-blocking `gzwrite` غير ظاهر في كود التطبيق، لكن الحزمة موجودة في سلسلة معالجة/ضغط؛ مفتوح، لا suppress. |
| [CVE-2026-84782](https://security-tracker.debian.org/tracker/CVE-2026-84782) — `openssl 3.5.7-1~deb13u2` | لا؛ upstream/Debian sid 3.6.5، Trixie vulnerable | الخلل DTLS؛ التطبيق يستخدم HTTP/TLS عبر proxy ولا يستخدم DTLS بحسب الكود الحالي، لكن الصورة مصابة وتحتاج تحديث Trixie؛ مفتوح. |

لا يوجد إصدار مصحح في قناة Trixie لهذه الحزم وقت المسح؛ الانتقال إلى `sid/forky` أو إسقاط أدوات استخراج دون اختبار توافق لا يصلح ترقيعًا آمنًا. يعاد المسح بعد صدور تحديث أمني لصورة الأساس/الحزم. تنبيهات الـ8 القديمة ليست قائمة مستقلة موثقة بالصورة المحذوفة.

## الأداء النهائي المحلي على QA

عامل API واحد وحدّه 1GiB/CPU واحد؛ 10 ثوان لكل مرحلة تصفح/فيديو مع 200ms think time. الرفع PDF صحيح 814,131 بايت، ثلاث مرات لكل عامل؛ فيديو WebM الاصطناعي **784 بايت فقط** فلا يمثل بث فيديو حقيقي الحجم أو CDN. كل الاستجابات قُرئت. القياسات من آخر تشغيل بعد تحويل QA إلى SeaweedFS.

| المسار | تزامن | عدد الطلبات | p95 ms | p99 ms | أخطاء |
|---|---:|---:|---:|---:|---:|
| تصفح طالب | 1 | 47 | 22.5 | 27.1 | 0 |
| تصفح طالب | 5 | 216 | 46.8 | 148.4 | 0 |
| تصفح طالب | 10 | 434 | 86.4 | 164.2 | 0 |
| فيديو محمي Range | 1 | 47 | 17.8 | 18.4 | 0 |
| فيديو محمي Range | 5 | 230 | 33.9 | 63.6 | 0 |
| فيديو محمي Range | 10 | 454 | 55.8 | 155.2 | 0 |
| رفع PDF | 1 | 3 | 34.8 | 34.8 | 0 |
| رفع PDF | 2 | 6 | 54.0 | 54.0 | 0 |
| رفع PDF | 4 | 12 | 160.7 | 160.7 | 0 |

عينة `docker stats` أثناء الحمل الأخير: API 198.7MiB/1GiB و46.29% CPU؛ PostgreSQL 74.14MiB/1GiB و7.38%، S3 QA 172.3MiB/1GiB و4.39%، Redis 5.574MiB/256MiB، web 12.79MiB/512MiB؛ `pg_stat_activity` = 11 اتصالًا. هذه لقطة، **ليست ذروة مضمونة**. مجموع الطلبات/الرفع 1,449 (47+216+434+47+230+454+3+6+12). لا يستنتج منها تحمل 1000 مستخدم نشط أو ملفات فيديو كبيرة. يلزم اختبار أطول بفيديو حقيقي متعدد الميغابايت ومراقبة p95/p99 والذاكرة/الاتصالات على البنية المرشحة للنشر.

## حدود حماية الفيديو وخطوات الإصدار المتبقية

الرابط وحده أو Bearer وOrigin/Referer منسوخان لا يكفيان؛ يلزم cookie جلسة حية بنفس nonce والمستخدم والاستحقاق عند كل Range، وتبطل الروابط بعد logout/revoke-all أو سحب الالتحاق. أوقفنا روابط الفيديو الخارجية الجديدة، وأخفينا القديمة عن الطلاب؛ **الدروس القديمة ذات URL خارجي تحتاج إعادة رفع**، وأي رابط سبق كشفه لا نستطيع إبطاله على خادم طرف ثالث. حجب الرموز من السجلات و`no-store` و`no-referrer` يقللان التسرب.

**لا يمكن تقنيًا ضمان منع طالب مخوّل من حفظ بايتات فيديو يعرضها له المتصفح**: مدير التحميل يستطيع تقليد طلبات المتصفح باستخدام cookies الجلسة، وNetwork يعرض طلبات Range؛ كما يمكن تصوير الشاشة. `controlsList=nodownload` وإخفاء زر التنزيل ليست DRM. إذا كان الشرط التجاري منع النسخ بقدر الإمكان، فالمطلوب اختيار مزود DRM/EME وتغليف HLS/DASH مشفر وخادم تراخيص وربما watermark فردي؛ حتى هذا لا يمنع تصوير الشاشة. لا أدّعي تحقيق شرط «مستحيل التحميل».

قبل تقييم نشر جديد: اختيار مخزن إنتاج متاح ودائم وخطة ترحيل واختبار backup/restore حالي؛ معالجة أو قبول أمني موثق لكل High دون تخفيض مصطنع؛ تحديث harness التكامل؛ مراجعة بشرية لدقة Extract على OCR ومحتوى Word/PDF؛ اختبار خدمة SMTP ومدفوعات وHTTPS/شهادة وخادم **خارجي حقيقي**؛ حمل أطول بفيديو حقيقي؛ ثم commit/push ومراجعة GitHub بعد تفويض المستخدم. الحالة الحالية: **أُصلح محليًا واختُبر على Docker QA؛ غير مرفوع إلى GitHub، وغير مختبر على سيرفر خارجي، وغير معتمد للنشر**.
