# إغلاق مراجعة 8558cf4 — 5 أكتوبر 2026

اكتملت الاختبارات يوم5 أكتوبر؛ حُققت سجلات النهاية واستُكمل تسليم Git يوم6 أكتوبر2026 بتوقيت القاهرة.

## حدود الإثبات وGit

المراجعة المرفقة تخص `8558cf4224fd3661d0c5bc5bbbbe750f21eecf49`، لكن بداية هذه الجولة كانت
`d0806d5754e07328494af55b5c1d45f0dfcf2dc3` على `fix/queen-p0-handoff`.
تحققت من `git branch --show-current`, `git rev-parse HEAD`, `git status --short`
و`git ls-remote origin refs/heads/fix/queen-p0-handoff`: المحلي والمرفوع متطابقان عند البداية.
التعديل الوحيد غير المحفوظ عند البداية: `pc_builder_3d_cases/`، عمل غير مرتبط، لم أعدله أو أضفه للرفع.
كل إصلاح موصوف أدناه جديد محليًا في هذه الجولة، وليس مستنتجًا من التقرير القديم.
حالة commit/الرفع النهائية تُذكر في رسالة التسليم بعد التحقق من GitHub.

البيئة الحية: مشروع `chemistryaudit2` الاصطناعي، [رابط QA المحلي](https://localhost:18543/)،
PostgreSQL وSeaweedFS الفعليان في قالب الإنتاج `infra/docker-compose.yml` مع overlays QA/video.
لم أنشر على سيرفر خارجي، ولم أدمج أو أستخدم reset/rebase/force push، ولم أغير مشروع `chemistryprodlocal`.
لم أعدل ملفات Extract في هذه الجولة؛ نجاح اختبارات API العامة ليس إثباتًا لإغلاق بوابة OCR الصارمة القديمة.

## إعادة الإنتاج قبل الإصلاح

شغلت أداة المراجعة بعد قراءة كودها داخل حاوية مؤقتة بلا شبكة:

```powershell
docker run --rm --network none -v 'D:/learning project/apps/api:/review:ro' `
  -v 'D:/learning project/.qa/council-http-probes.py:/probe.py:ro' `
  -w /review --entrypoint python chemistryaudit2-api /probe.py
```

Exit 0؛ أعادت إنتاج **أربع ثغرات/أخطاء HTTP** باستخدام login وCSRF الحقيقيين وقاعدة ذاكرة منفصلة:
الطالب يحصل على الإجابة 200 قبل التسليم؛ المدرس الأجنبي يكتب درجة 201 ويخفي درجة الضحية؛
POST التقرير يرجع metadata الأجنبية 202 رغم GET 404؛ إعادة التصحيح 400 بعد إنشاء 201.
حقل commit في الأداة الأصلية ثابت `8558cf4`، **ليس مصدرًا لتحديد النسخة المختبرة**:
الـmount أعلاه هو working tree الحالي عند `d0806d5` قبل التعديل.

أضفت `tests/test_review_regressions.py` ثم شغلته قبل التعديل: **1 Passed / 6 Failed / 0 Skipped، Exit 1**.
بعد الإصلاح مع `test_security_and_tenancy.py`: **23/0/0، Exit 0**.

## العوائق العشرة

الأوامر C1–C6 مفصلة أدناه. الأعداد الجزئية متداخلة داخل المجموعات، ولا تُجمع كأنها اختبارات إضافية.
مسارات Python نسبية إلى `apps/api`، ومسارات الواجهة إلى `apps/web` ما لم يذكر خلاف ذلك.

| # | قبل / سبب المشكلة | بعد الإصلاح وQA | الملفات الأساسية | الأمر، Exit، P/F/S |
|---|---|---|---|---|
| 1 P1 | إعادة إنتاج 201 بين مؤسستين؛ بحث الدرجة السابقة بلا مؤسسة أو تفويض | التحقق من مؤسسة الطالب، ملكية المقرر، صحة ربط التقييم، والتسجيل قبل أي تغيير؛ مدرس زميل/أجنبي ممنوع ولا تتغير الدرجة | `app/services/extended_service.py`, `tests/test_review_regressions.py` | C1؛ 0؛ اختبارا التفويض 2/0/0 |
| 2 P1 | طالب يحصل على correct_answer/explanation عبر versions، 200 | الطالب ممنوع؛ المدرس غير المسؤول ممنوع في القراءة والتعديل؛ إنشاء نسخة مرتبطة بمقرر يتحقق من ملكيته أيضًا | نفس service/tests | C1؛ 0؛ اختبارات الخصوصية 2/0/0 + اختبار حفظ النسخ القديم |
| 3 P1 | `render.yaml` production ينشئ حسابات demo بكلمة عامة ويعيد كلماتها | bootstrap password مدخل secret؛ demo/reset false؛ seed يرفض demo/reset وكلمة bootstrap قصيرة في production، قبل الكتابة | `render.yaml`, `scripts/seed_teacher.py`, `tests/test_seed_teacher_idempotency.py`, `tests/test_render_blueprint.py` | C1؛ 0؛ حالات الحظر الجديدة 4/0/0، وفحص القالب 1/0/0 |
| 4 P1 | SMTP المطلوبة مفقودة من القالب؛ فرع `fix/unified-p1` لا يطابق العمل | فرع handoff الحالي؛ SMTP secrets وTLS ضمن config لـAPI والـworker، port465 مطابق لـSMTP_SSL؛ payment destination مرجع في worker؛ autodeploy off | `render.yaml`, `tests/test_render_blueprint.py` | C1؛ 0؛ 1/0/0، تحميل Settings production ببدائل اصطناعية، ليس تشغيلًا على Render |
| 5 P1 | فحص كود: قائمة المسجلين فقط، زر التصفح يذهب للدفع ويدفن المقرر المجاني | كتالوج مقررات منشورة مجاني بصفحات، مرشح للصف الدراسي؛ طالب جديد بلا تسجيل يضغط التسجيل الحقيقي وتظهر دروسه وتقييماته | `src/components/FreeCourseCatalog.tsx`, `src/views/MyCoursesView.tsx`, `src/App.tsx`, `src/services/lmsService.ts`, `tests/qa/discovery.spec.ts` | C3؛ 0 في الرحلة المحددة؛ 1/0/0 |
| 6 P2 | فحص كود: payment_reviewed يطلق unlock حتى للرفض، وaccess يتراكم محليًا | review يحدث الاستحقاقات فقط؛ approval event واحد؛ واجهة الوصول مشتقة من الاستحقاقات الحالية؛ رفض فعلي عبر SSE لم يفتح الدرس/يظهر نجاحًا، playback token بقي 403 | `src/services/realtimeService.ts`, `src/services/realtimeReview.test.ts`, `src/views/MyCoursesView.tsx`, `tests/qa/discovery.spec.ts` | C3؛ unit1/0/0 وlive1/0/0؛ 0 |
| 7 P2 | فحص كود: solve GET المخزّن15 ثانية يبدأ محاولة؛ submit لا يبطل النتائج | solve no-store بلا cache أو dedup مركزيًا؛ submit يبطل quizzes/results/history/course caches؛ إعادة فورية تحت15ث أنشأت ID جديد practice، وإجابات مختلفة أعطت نتيجة مختلفة | `src/services/apiClient.ts`, `src/services/requestStorm.test.ts`, `src/views/MyCoursesView.tsx`, `tests/qa/discovery.spec.ts` | C3؛ unit1/0/0 وlive1/0/0؛ 0 |
| 8 P2 | فحص كود: producer يعمل في production_like لكن lifespan يبدأ consumer في production فقط | consumer في كل runtime غير test؛ subprocess production_like داخل مخطط PostgreSQL جديد ومخزن S3 الحقيقي حذف object وintent دوريًا | `app/main.py`, `scripts/qa_cleanup_runtime.py`, `tests/integration/test_cleanup_runtime.py` | C2؛ الرحلة المحددة 1/0/0، 0 |
| 9 P2 | إعادة إنتاج: مفتاح التقرير عالمي يرجع سجل المؤسسة الأخرى؛ لا يتحقق من payload | بحث وقيد unique حسب مؤسسة/صاحب الطلب، GET حسب صاحب الطلب، payload mismatch409؛ قفل صف المستخدم يسلسل أول إنشاء وreplay بين العمال | service/model/migration، `tests/test_review_regressions.py`, `tests/integration/test_review_ledger.py` | C1 + C2؛ HTTP isolation1/0/0 وPG concurrent1/0/0؛ 0 |
| 10 P2 | إعادة التصحيح item_id غير NULL يرجع400؛ unique يشمل التاريخ كله | فهرس current-only بمؤسسة/طالب/مقرر/item مع معالجة NULL؛ flush retiring قبل insert، قفل الطالب يمنع سباق أول كتابة؛ ترحيل يحفظ التاريخ ويختار أحدث current من duplicates | `app/models/extended.py`, service، migration`e8a0c2d4f6b8`، اختبارات review/ledger/migration | C1+C2؛ revision2/0/0، PG concurrency2/0/0، PG migration1/0/0؛ 0 |

**ملاحظة 8:** اختبرت مسار `APP_ENV=production_like` نفسه على PG وSeaweedFS بمخطط منفصل.
لم أدّع تشغيل stack MinIO القديم في `compose.prod-like.yml`؛ هذا قالب محلي قديم وليس مرشح السيرفر المختبر.
القالب المرشح هو `infra/docker-compose.yml` الذي يستخدم SeaweedFS.

## الأوامر القابلة لإعادة التشغيل

يهيّئ runbook أسرار QA خارج Git. لا تنسخ كلمات الإنتاج إلى ملفات المشروع.
التفاصيل في `docs/PRODUCTION_DOCKER_RUNBOOK.md`؛ التنفيذ داخل مستودع نظيف بعد تجهيز بيئة QA:

```powershell
./scripts/qa/run-video.ps1 -Stage Build
./scripts/qa/run-video.ps1 -Stage Backend       # C1: unit/protection/native/lost multipart
./scripts/qa/run-video.ps1 -Stage Integration   # C2: live PG/S3/services, includes 5 review cases
./scripts/qa/run-video.ps1 -Stage Browser       # C3: lint/build/Vitest/ALL Playwright/audit/diff
./scripts/qa/verify-runtime-source.ps1          # C4: actual runtime hashes
./scripts/qa/run-video.ps1 -Stage Scan -ApproveScout # C5: external SBOM upload, needs explicit consent
git -c core.safecrlf=false diff --check         # C6
```

بعض الاختبارات القديمة تستعمل حسابات demo المحلية؛ لا تشغلها على إنتاج أو أثناء تجربة المستخدم.
الحالات الجديدة تستعمل طلابًا/مدرسين اصطناعيين مستقلين؛ لا يتم إضعاف rate limiting الحقيقي.
تم تحويل probes الحالية إلى ملفات مشروع، وليس الاعتماد على أدوات scratch لإغلاق الإصلاح.
فحص Render يركّب القالب الحقيقي read-only، ويستبدل الأسرار بقيم اصطناعية فقط داخل الاختبار.

## نتائج البوابات النهائية

| البوابة / الأمر | Exit Code | Passed / Failed / Skipped أو نتيجة التشغيل | الدليل المحلي |
|---|---|---|---|
| `run-video.ps1 -Stage Build` | 0؛ كل خطواته الأربع 0 | إعادة بناء API/migration/Celery/web ثم encoder/QA؛ تشغيل القالب الفعلي محليًا | `.qa/audit2/video-commands-Build-20261005-175742.json` |
| C1 `-Stage Backend` | 0؛ كل خطواته الأربع 0 | unit241/0/0؛ native Expat4/0/0 لكل صورة؛ lost multipart200 ثم409 ثم إنشاء جديد201، بلا500 | `video-commands-Backend-20261005-175847.json`, `api-unit-video-20261005-175847.xml` |
| unit بعد آخر تعديل لقالب Render | 0 | 241/0/0 | `.qa/audit2/review-final-unit.xml` |
| C2 `-Stage Integration` | 0 | **37/0/0**؛ 609.930 ثانية، PostgreSQL وS3 الفعليان | `.qa/audit2/api-integration-video-20261005-180951.xml` |
| C3 `npm run lint` | 0 | 0 errors؛ 3 warnings Fast Refresh القديمة، ليست أخطاء صلاحيات/تدفق | سجل Browser النهائي |
| C3 `npm run build` | 0 | TypeScript/Vite ناجح؛ تحذير chunk الفيديو633.87kB باقٍ، لم أغيّر حد التحذير لإخفائه | سجل Browser النهائي |
| C3 `npm test` | 0 | **43/0/0**، 7 ملفات | سجل Browser النهائي |
| C3 Playwright كامل | 0 | **73/0/0**؛ 378.538 ثانية؛ لا اختبارات مستبعدة أو متخطاة | `.qa/audit2/video-browser-Browser-20261005-182019.xml` |
| C4 `verify-runtime-source.ps1` | 0 | API108/encoder108/web89 ملفًا؛ mismatches0؛ assets مقارنة ببناء الواجهة الحالي | `.qa/audit2/runtime-source-20261005T182237Z.json` |
| C4 إعادة التأكيد بعد المجموعة كاملة | 0 | نفس الصور وعدد الملفات؛ mismatches0 | `.qa/audit2/runtime-source-20261005T182753Z.json` |
| C3 `npm audit --audit-level=high` | 0 | بوابة npm اجتازت؛ ليست بديلًا لفحص حزم النظام في Docker | `.qa/audit2/video-commands-Browser-20261005-182019.json` |
| C5 Docker Scout، الصورتان الفعليتان | raw2 لكل صورة؛ wrapper1 | API6 High / encoder8 High / Critical0؛ بوابة مفتوحة | `video-commands-Scan-20261005-180151.json` وملفاSARIF |
| C6 `git -c core.safecrlf=false diff --check` | 0 | لا أخطاء whitespace | أُعيد بعد التعديلات |

كل خطوات wrapper Browser الثماني Exit0؛ نتائج lint/build/unit/Playwright/audit/diff في
`.qa/audit2/video-commands-Browser-20261005-182019.json`.
الحاويات العشر كانت healthy، وmigration head=`e8a0c2d4f6b8` عند نهاية5 أكتوبر.
إعادة فحص التشغيل يوم6 أكتوبر فشلت **Exit1** لأن pipe محرك Docker Desktop Linux غير موجود.
لذلك لا أؤكد أن الرابط المحلي متاح الآن؛ هذا لا يلغي نتائج الجولة المكتملة، ولا يُحسب إعادة اختبار حية ناجحة.

مسارات الأدلة غير المطلقة في الجدول ضمن `.qa/audit2/`. لا تُرفع بيئة `.qa` أو أسرارها إلى Git.
الأدوات والاختبارات القابلة لإعادة التشغيل نفسها ضمن ملفات المشروع.

اختبار ترحيل PostgreSQL المنفصل:1/0/0، Exit0؛ احتفظ بدرجتين90 و95، واختار95 كالحالية دون حذف.
اختبار concurrent regrade المنفصل:2/0/0؛ ثلاث طلبات فعلية متزامنة لكل مفتاحNULL وغيرNULL أعادت201،
واحتفظت بالدرجات الثلاث وبدرجة حالية واحدة. replay reports:1/0/0، طلبات متزامنة تعيد معرفًا واحدًا وpayload مختلف409.
هذه الاختبارات نفسها متضمنة في37integration، وليست أعدادًا إضافية.

هويات الصور **المشغّلة فعلًا** والمفحوصة؛ لا أعتمد على tag متغير:

```text
API          sha256:d718c4836c697a6c755de4a1187442efe9ede72c9d613e6f239dea9d246bbdad
video-worker sha256:adffd9085c5fb4f8fa47034da65dd2f362dfe9d13a298117fd2dc52579d2c26b
web          sha256:157ab5152b78f2bb38584d02e4b9ba3827da67069efa49a59367022998eb54e0
```

## ملخص التغييرات القابلة للمراجعة

24 ملفًا، دون أسرار أو ملفات QA الخام أو مجلد `pc_builder_3d_cases/` غير المرتبط:

- خدمة extended/model وترحيل واحد: تفويض الدرجات/نسخ الأسئلة، سجل درجات current-only، مفاتيح تقارير scoped.
- lifespan وseed وRender: استهلاك تنظيف دائم وحظر bootstrap/demo غير الآمن وإعداد SMTP/الفرع/autodeploy.
- الواجهة: كتالوج مجاني، ربط الالتحاق، وصول مشتق من الخادم، ومنع cache محاولة quiz.
- الاختبارات والأدوات: HTTP login/CSRF، PostgreSQL concurrency/migration، cleanup S3، Render Settings، Vitest/SSE/Playwright، وتحديث harness + هذا التقرير.

## الجولات الفاشلة وتصحيح البيئة

- أول تشغيل شامل مع كود mounted read-only بلا `STORAGE_DIR` قابل للكتابة: Exit1، 224/17/0.
  الأسباب كتابات staging/avatar/material داخل RO mount؛ أعيد بمخزن `/tmp/qa-storage`:241/0/0.
  ليس إصلاحًا في Extract، ولا حذفًا لاختبار.
- أول Browser focused:1/2/0؛ أخطاء في إعداد اختباراتنا (pricing endpoint غير صحيح وغياب idempotency_key).
  جولة focused التالية0/2/0: طريقة GET بدل POST لـvideo-token، واسم زر الاختبار غير مطابق.
  بعد مطابقة العقود دون تغيير شرط النجاح: rejection/practice2/0/0، وcatalog1/0/0.
- أول cleanup subprocess ورث `STORAGE_BACKEND=local` من تطبيق unit:0/1/0.
  صححت بيئة الطفل لتستخدم S3 وأضفت شرط رؤية object قبل الحذف؛1/0/0.
- أول Playwright كامل: **71/2/0، Exit1**. trace أظهر `/submissions`200 و`/users`500.
  حسابا ledger من اختبار PG الجديد استعملا نطاق البريد المحجوز `.test`؛ أكدت خطأ `ManagedUserResponse.email`.
  صححت هذين الحسابين الاصطناعيين فقط إلى `@qa.example.com` دون حذف، وصححت fixture.
  اختبارات ownership/manual-grading بعدها **2/0/0، Exit0**؛ نتيجة إعادة المجموعة الكاملة موضحة أعلاه، لا يُستخدم rerun جزئي كبديل لها.

## Render: حدود مهمة قبل أي نشر خارجي

القالب اختبار إعداد محلي، لا اتصال بحساب Render ولا اختبار SMTP خارجي أو شهادة عامة.
وفق [مرجع Render الرسمي](https://render.com/docs/blueprint-spec)، `sync:false` يطلب قيمة عند الإنشاء
ولا يُحدّث الأسرار تلقائيًا في Blueprint موجود: يجب على المشغّل إدخال SMTP وbootstrap/destinations الخاصة
في الخدمات الموجودة والتحقق منها، وإلغاء أي إعدادات demo قديمة.
استخدمت `autoDeployTrigger: "off"` بدل الحقل القديم. إذا سبق استعمال كلمات demo المنشورة فعليًا،
إزالة الكلمات من القالب لا تُبطل القديمة ولا تمحو Git history: يلزم تدويرها والجلسات بموافقة المشغّل.
لم أغيّر خدمات خارجية أو أختبر وصول أي كلمة إلى خدمة حقيقية.

## بوابات أوسع لا تزال مفتوحة — لا إعلان جاهزية نشر

Scout الحالي: **API6 High، encoder8 High، Critical0**؛ rawExit2 لكل صورة، wrapperExit1، بلا suppression.
ملفات `.qa/audit2/scout-video-{api,video-worker}-20261005-180151.sarif` تحفظ الأدلة المحلية، لا تحتوي أسرار بيئة.
الحزم لم تتغير في هذه الجولة؛ طبقات native المثبتة سابقًا أُعيد اختبارها، والفحص لا يزال يرفع التنبيهات.

| CVE | صور / نسخة source package في Scout | حالة الفحص الحالي |
|---|---|---|
|2026-102010،2026-95619|الصورتان، gcc-14 `14.2.0-19`|High، scanner not fixed؛ لم أجر إثبات وصول/استبعاد جديدًا في هذه الجولة |
|2026-86140،2026-74860|الصورتان، libxml2 `2.12.7+dfsg+really2.9.14-2.1+deb13u3`|High، scanner not fixed؛ الفرز السابق باقٍ، ليست مكتبة مصححة بناءً على نجاح اختبارات الوظائف |
|2026-85091|الصورتان، zlib `1:1.3.dfsg+really1.3.1-1`|High، scanner not fixed؛ لم أثبت انعدام الوصول |
|2026-93990|الصورتان، expat `2.8.5-0chemistry1`|High باقٍ؛ حزمة stable upstream محلية شفافة، native UTF-16 regression4/0/0 لكل صورة، ليس تحديث Debian الرسمي |
|2026-30997،2026-38347|encoder، ffmpeg `7:7.1.5-0chemistry1`|High باقٍ؛ Scanner يقترح `7:7.1.5-0+deb13u1`؛ لم أعد تسمية الحزمة لمجرد تصفيره، ولا أعلن إغلاقه |

مراجع الفرز والبناء السابق في `docs/QA_FIXES_2026-10-05.md` و`docs/QA_SECURITY_RECHECK_2026-10-04.md`.
Scout حذّر أيضًا من فشل إزالة أرشيف مؤقت بسبب file lock في Windows؛ ملفات SARIF الفعلية كُتبت كاملة.
لم أحذف ملفات Docker أو أصفّر scanner للتحايل على الفحص.

بوابة OCR الصارمة الأقدم:6/1/0، لم تُعد هذه الجولة ولم تُغلق. CDN/DRM خارجي غير مفعّل؛
الفيديو المحمي محليًا ليس ضمانًا مطلقًا ضد التنزيل/تسجيل الشاشة. شهادة localhost غير موثوقة عامًا.
لم أجر حملًا جديدًا أو backup/restore كاملًا في هذه الجولة؛ تقاريرها السابقة منفصلة وليست دليلًا جديدًا.
إغلاق نقاط المراجعة العشر محليًا **لا يعني** أن هذه البوابات أو سيرفرًا خارجيًا أصبح جاهزًا.
