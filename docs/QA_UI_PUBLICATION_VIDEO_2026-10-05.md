# إصلاحات الساعة ونشر الكويز ومتابعة الفيديو — 5 أكتوبر 2026

هذه جولة خاصة بالمشاكل في الصور الأخيرة، وليست إعلان إغلاق كل بوابات
إصدار المنصة. التقرير السابق `QA_FIXES_2026-10-05.md` محفوظ مستقلًا؛
نتائج Backend/OCR/Scanner السابقة لا تُنسب إلى اختبار جديد في هذه الجولة.

## حدود Git والبيئة

قبل التعديل: `fix/queen-p0-handoff`؛ HEAD وGitHub كلاهما
`8558cf4224fd3661d0c5bc5bbbbe750f21eecf49`، تحقق بواسطة `git rev-parse HEAD`
و`git ls-remote origin refs/heads/fix/queen-p0-handoff`. لا commit محلي أحدث.
إصلاحات الجولة بدأت كتعديلات غير محفوظة. مجلد `pc_builder_3d_cases/` خارج
المهمة وغير متتبع، محفوظ وغير مشمول بالرفع.

الاختبار الحي على `chemistryaudit2` في `https://localhost:18543/`؛
حسابات ومحتوى QA اصطناعيان. أعيد إنشاء web وإعادة تشغيل proxy فقط؛
لم تُحذف ملفات المستخدم أو volumes، ولم تُعد إنشاء خدمة التخزين.
`chemistryprodlocal` وبياناته لم تُمس. لا نشر أو دمج أو force push.

## العوائق، السبب، والإثبات

P/F/S = Passed/Failed/Skipped؛ المجموعات المتداخلة لا تُجمع.

| العائق | قبل / السبب | بعد | الملفات | الأمر وExit وP/F/S والدليل الحي |
|---|---|---|---|---|
| نشر سؤال أكمل يرجع 400 | UI يتعرف على `FILL_BLANK` لكنه يرسل النوع الخام؛ API يقبل `fill_in_blank` | تطبيع صريح عند حدود API؛ المجهول يُرفض قبل أي طلب وليس تحويله تخمينًا إلى MCQ | `questionType.ts`, `lmsService.ts`, `QuizGeneratorView.tsx`, `publicationContract.test.ts`, `discovery.spec.ts` | قبل: Playwright `--grep 'reviewed FILL_BLANK'`، Exit1، 0/1/0؛ response400 بنفس رسالة المستخدم. بعد أول بناء: نفس الرحلة Exit0 ضمن 1/2/0؛ بعد تصحيح الاستعادة: 2/1/0؛ الحالة الخاصة بالنشر نجحت 201، وGET solve أثبت النوع المحفوظ `fill_in_blank`. نتيجة المجموعة النهائية أدناه |
| الوقت صغير وfree-text | حقل صغير يحتم كتابة الصيغة كاملة ولا يقدم اختيارات | ساعة ودقيقة قابلتان للكتابة بالأرقام العربية/اللاتينية، قوائم 01–12 و00–59، اختيار ص/م، font20px؛ التاريخ18px وملخص التأكيد18px | `TimeField.tsx`, `clockField.ts`, `clockField.test.ts`, `QuizGeneratorView.tsx`, `discovery.spec.ts` | unit ساعتان ضمن المجموعة؛ الحي أدخل 03:30م واختار 08:45م، وقارن التوقيت المحلي بعد تحويله لـUTC؛ no horizontal overflow عند390px. الصور `segmented-clock-{desktop,mobile}.png` محفوظة في QA المحلي |
| قائمة وقت تغطي الحقل التالي | أول تنفيذ popup مطلق يعلو حقل نهاية الإتاحة | الخيارات جزء من التخطيط وتغلق عند الكتابة/الخروج/Escape، لا استخدام force-click لتجاوز الخلل | `TimeField.tsx` | الحي الأول فشل بالنقر: خيار09 اعترض حقل الساعة التالي، Exit1 ضمن1/2/0. بعد إصلاح التخطيط اكتملت الرحلة؛ فشل المقارنة التالية كان خطأ اختبار UTC لا خطأ منتج، ثم صححت المقارنة إلى ساعات المتصفح الفعلية |
| 99% يوحي بتعطل المعالجة | نقل الملف100% لكن progress محبوس99؛ لا نسبة ترميز فعلية يرسلها API | يظهر «الرفع100%» مستقلًا عن حالة انتظار المعالج/تجهيز الجودات؛ اكتمال المهمة لا يُعلن قبل server ready | `uploadManager.ts`, `GlobalUploadWidget.tsx`, `uploadManager.test.ts` | unit يعطل رد ready مؤقتًا ويثبت statusprocessing وuploadPercent/progress100 ثم completed؛ لا ادعاء قياس نسبة الترميز. فحص قراءة فقط لفيديو الصورة وجد79,379,330B وready ومحاولة1 ومدته2130s؛ worker سجل ready/renditions2. هذا تشخيص حالة الفيديو لا إعادة رفع محتوى المستخدم |
| reload/انتهاء جلسة يفقد متابعة فيديو محفوظ | المهام المحفوظة تتحول إلى error عند reload؛ الحساب المحفوظ قد يظهر قبل bootstrap، فلا تتكرر effect عند ثبات user.id | فحص job بعد التحقق من scope؛ متابعة المعالجة دون إعادة bytes؛ حدث مستقل عند تغير API scope يعالج السباق؛ cache المقررات يبطل قبل تحديث الواجهة | `apiClient.ts`, `uploadManager.ts`, `GlobalUploadWidget.tsx`, `uploadManager.test.ts`, `discovery.spec.ts` | اختبار reload الأول: Exit1 ضمن1/2/0، jobready لكن localerror. بعد إصلاح scope: رحلة الفيديو ناجحة ضمن2/1/0. رفع S3 multipart حقيقي، workerready ثم reload→completed، صفر POST/PUT متكرر إلى مسار الرفع بعد reload |
| خلط مهام حسابين | task metadata عام دون ownerScope؛ أتمتة الاستئناف دون عزل قد تفحص مهام حساب آخر | ربط المهام الجديدة بالحساب؛ القديمة تربط فقط بعد GET ينجح بتحقق ملكية السيرفر؛ فلترة عند render، ومنع retry/cancel/clear للحساب الآخر، وإيقاف نقل محلي عند تبديل الحساب دون حذف السيرفر | `uploadManager.ts`, `GlobalUploadWidget.tsx`, `uploadManager.test.ts` | 5unit لمتابعة الفيديو تشمل منع fetch لحساب مختلف، عدم ربط legacy403، و429 طلب واحد دون حلقة؛ لا تعديل صلاحيات السيرفر. `video_uploads.owned` يقيد owner_id بالفعل |
| تكرار 401 لهوية/تقدم بعد انتهاء الجلسة | علامة انتهاء الجلسة لا تمنع apiRequest الخاص المتكرر؛ 401 حقيقي يبقى واجبًا لجلسة غير صالحة | تصفير scope والكاش عند ثبوت انتهاء الجلسة، ثم منع probes الخاصة المعروفة محليًا؛ login/public browsing متاحان؛ لا رد200 مزيف ولا إضعاف rate limits | `apiClient.ts`, `requestStorm.test.ts` | 12unit ضمن المجموعة تشمل أول401/refresh401 ثم4probes بلا fetch إضافي، login يعيد إمكانية الطلب. محاولات before-unit في التشغيل المقيد فشلت EPERM ولم تنفذ أي test؛ ليست إثبات فشل وظيفي. سبب401 بعينه في جلسة المستخدم القديمة غير مثبت من console وحده |
| 401 بعد تسجيل خروج الطالب مع مقررات كثيرة | المجموعة الشاملة كشفت طلبَي assessments401 بعد POST logout204؛ الصف يظل في جيل الحساب القديم حتى عودة logout، فيبدأ طلبات أخرى بعد إلغاء cookie | سياج جيل الحساب وإلغاء fetch الفعلي من بداية logout؛ logout نفسه يحتفظ بالاعتماد الملتقط ويلغي جلسة السيرفر؛ UI ينتظر اكتمال الطلب حتى لا يتسابق cookie-clearing مع login جديد | `apiClient.ts`, `lmsService.ts`, `requestStorm.test.ts` | قبل حي: المجموعة الشاملة Exit1، 69/1/0، رحلة الطالب فاشلة. قبل unit: `npm run test -- --run src/services/requestStorm.test.ts` Exit1، 12/1/0؛20طلبًا منها4active، release أثناء logout عالق بدأ4أخرى (8بدل4). بعد إصلاحه: نفس الأمر Exit0،13/0/0؛ المجموعة الكليةunit41/0/0، Exit0. لا تعديل مرشح console/errors أو استبعاد الاختبار |

## الأوامر والنسخة النهائية

آخر تشغيل شامل بعد آخر تعديل للكود، بلا استثناءات أو expected failures:

| الأمر | Exit Code | Passed / Failed / Skipped | النتيجة |
|---|---|---|---|
| Docker Compose `build web` ثم `up --no-deps --force-recreate --wait web` و`restart proxy`، بنفس ملفات القالب أعلاه | 0 لكل أمر | — | تشغيل الصورة الأخيرة، بلا إعادة إنشاء المخزن/حذف volumes |
| بدء Mailpit المحلي المعزول وفحص readiness من wrapper | 0 لكل أمر | — | صندوق اختبار البريد جاهز، لا بريد خارجي |
| `npm run lint` | 0 | — | صفر errors، ثلاثة warnings قديمة تخص Fast Refresh عند تصدير hooks مع components؛ لا خلل وظيفي إنتاجي مثبت فيها |
| `npm run build` | 0 | — | TypeScript وVite ناجحان؛ تحذير chunk فيديو أكبر من500kB محفوظ، ليس مخفيًا بتعديل الحد |
| `npm test` | 0 | 41 / 0 / 0 | كل اختبارات الواجهة، بما فيها العقد والوقت وملكية مهام الفيديو والجلسة/الخروج |
| `npx playwright test --config playwright.qa.config.ts --reporter=list,junit` | 0 | 70 / 0 / 0 | 6.0دقائق، كل الرحلات بما فيها تسجيل/استرجاع كلمة المرور/الملكية/الدفع/تصحيح الواجب/الإشعارات/الانقطاع/الفيديو/CSRF/CORS |
| `npm audit --audit-level=high` | 0 | — | found0vulnerabilities في تبعيات npm فقط، لا تصفير لـDocker Scout |
| `git -c core.safecrlf=false diff --check` | 0 | — | بلا أخطاء whitespace |
| `./scripts/qa/verify-runtime-source.ps1` | 0 | — | API107/encoder107/web89، صفر اختلاف بصمات |

تسجيل الأوامر المحلي: `.qa/audit2/video-commands-Browser-20261005-172324.json`؛
JUnit: `.qa/audit2/video-browser-Browser-20261005-172324.xml`؛ الصور في
`.qa/audit2/video-results-20261005-172325/`. هذه الآثار غير مرفوعة لأنها قد
تحتوي بيانات جلسات QA؛ أدوات الإعادة والاختبارات نفسها ملفات مشروع.

تأكيد QA حي بعد آخر إصلاح: رحلة الطالب انتهت بـlogout204 وصفرissues؛
لا إسكات errors/console في الاختبار. الكتالوج الحقيقي84مقررًا،84طلبًا
مكتملًا، peak4 وصفر failures. نشر `FILL_BLANK`201 وحفظ النوع
`fill_in_blank`؛ إدخال/اختيار الوقت ثم نشره مع ساعات المتصفح الصحيحة؛
reload لفيديوready→completed دون POST/PUT إضافي؛ رفع فيديو ومذكرات من
الواجهة واستئناف فيديو بعد انقطاع/reload، وHLS/seek/ranges والصلاحيات
كلها ناجحة في المجموعة. هذه قياسات وظائف، وليست اختبار قدرة حمل.

إعادة التشغيل بنفس القالب المحلي المعزول:

```powershell
# اضبط QA_PYTHON إلى Python المثبت لديك إذا كانت رحلة استخراج نص PDF تحتاجه.
./scripts/qa/run-video.ps1 -Stage Browser -Project chemistryaudit2
./scripts/qa/verify-runtime-source.ps1
git -c core.safecrlf=false diff --check
```

بناء web وتشغيله في هذه الجولة استعملا نفس ملفات Compose:
`infra/docker-compose.yml` + `infra/qa/production.override.yml` +
`infra/video-pipeline.override.yml`، وبيئة QA المحلية غير المتتبعة.
`VITE_API_URL=/api/v1` في host build مطابق لبناء Docker؛ لا أسرار أو traces
أو ملفات المستخدم في commit. تفاصيل تهيئة بيئة الاختبار في دليل QA السابق.

فحص بصمات runtime بعد آخر تعديل: Exit0؛ API107/encoder107/web89 ملفًا،
صفر اختلاف. الصور الفعلية:

- API: `sha256:8a68651b97b9db47ee7d4b8599ba255ebddc07c9bb3d65a6643bff3575c855b9`
- video-worker: `sha256:f0c01447d3efb7667906991cf13913afc3d8394103bcc129ce9ed8f05ec055e7`
- web: `sha256:355d53f17127472ada1ade27c0c2d32a1c929bcb166dbbf6954d7e3e855db865`

API/encoder لم يتغير كودهما أو صورهما في هذه الجولة؛ لا ننسب اختبارات
PostgreSQL/fault/load أو scan سابقة إلى تنفيذ جديد. الرحلات الحية تستخدم
PostgreSQL وSeaweedFS وworker القائمين، مع إعادة بناء web للتغييرات الحالية.
ملف الفيديو التجريبي الفعلي `video.webm` حجمه35,382,809B (حوالي33.7MiB)،
لا bytes وهمية ولا رابط خارجي بدل الاختبار. فحص Docker readiness: Exit0،
خدمات QA العشر healthy. هذا ليس benchmark حمل ولا إثبات تحمل1000مستخدم.

## ما لم يُغلق

بوابة OCR الصارمة السابقة ما زالت بهاbiology case لا يطابق المصدر بالكامل،
وScanner السابق ما زال يعرض API6High/encoder8High بلاCritical. لم يُعد
scan أو strictOCR في الجولة الحالية ولا ندعي تغير نتائجهما. راجع التقرير
السابق للتفاصيل والتخفيف؛ هذه الجولة لا تمنح موافقة نشر شاملة.

شهادة localhost ذاتية التوقيع وما زال تحذير الثقة متوقعًا؛ لم نغير مخزن
الشهادات أو نعطل TLS. لا اختبار سيرفر خارجي أو شهادة عامة أو CDN/DRM
مرخص. الحماية المحلية لا تمنع تسجيل الشاشة أو تضمن منع كل طرق النسخ.
