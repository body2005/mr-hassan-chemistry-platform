# إغلاق المراجعة الأمنية الإضافية — 6 أكتوبر 2026

## حدود النسخة والنطاق

الفرع `fix/queen-p0-handoff`. عند بدء هذه الجولة كان HEAD المحلي وGitHub
`5cb403bdd4cd818a6004743a63d1da592c7e31dc`؛ لم أعتبر تقرير QA دليلًا على وجود إصلاح في GitHub.
التغييرات التالية جديدة لهذه الجولة. لا نشر خارجي ولا دمج ولا reset/rebase/force push.
مجلد `pc_builder_3d_cases/` غير مرتبط، لم يُعدّل ولم يُدرج في الرفع.
لم تُعدّل طبقة parser/OCR أو `document_parsers.py`، ولم يُدّعَ اجتياز مطابقة OCR النهائية.
تغيّر `QuizGeneratorView.tsx` فقط في منع نشر سؤال Fill Blank بلا إجابة، مع DAL واختبارات مراجعة المصدر.

إعادة التشغيل على مشروع Docker المعزول `chemistryaudit2` ببيانات اصطناعية،
باستخدام قالب الإنتاج نفسه مع SeaweedFS وPostgreSQL وRedis وHTTPS المحلي؛
لا استبدال للتخزين أثناء الاختبارات. الرابط المحلي `https://localhost:18543/`.

## العوائق: السبب، الإصلاح والدليل

الأعداد بصيغة **Passed / Failed / Skipped**. C1–C6 تشير إلى الأوامر في القسم التالي.
الأعداد الجزئية للحالات الجديدة متضمنة في المجموع، وليست اختبارات إضافية.

| العائق والحالة قبل | سبب المشكلة | الحالة بعد والتغييرات القابلة للمراجعة | أمر التحقق / Exit / الحالات الخاصة |
|---|---|---|---|
| session token في localStorage ومُعاد في JSON | عميل API يقرأ/يكتب credential ويحقنه في Authorization، رغم وجود cookies؛ bootstrap يعامل انتهاء access كنجاح ضيف أثناء التجديد | أزيلت القراءة والكتابة والاستخدام التلقائي؛ يُحذف المفتاح القديم دون قراءته. login/register/refresh لا تسلسل credential في JSON. تجديد bootstrap عند انتهاء/غياب access مع بقاء CSRF، وفصل DB503 عن auth401. `apiClient.ts`, `lmsService.ts`, `routes/auth.py`, `routes/platform.py`, `dependencies.py`, `schemas.py`؛ تحديث QA إلى cookies+CSRF | C1: auth/renewal/outage4/0/0، Exit0؛ C3: cookieSession1/0/0 وregistration/reload/SSE refresh الحية3/0/0، Exit0 |
| المدرس يقرأ طالبًا لا يدرّسه أو نتائج مقررات زميله لطالب مشترك | تحقق المؤسسة فقط؛ تجميع mastery يخلط الأدلة عند تكرار objective code | نطاق المقررات المملوكة للمدرس والالتحاق active/completed؛ غير المرتبط404. الدرجات تُرشّح بالمقرر، وأدلة mastery بالمقرر الفعلي للامتحان في استعلام aggregate واحد. `extended_service.py` | C1: 3/0/0، Exit0؛ C2: cookie-auth على PostgreSQL بثلاثة مدرسين وطالب مشترك1/0/0، Exit0 |
| نشر legacy quiz فارغ أو بمحتوى غير صالح | المسار يغيّر الحالة دون فحص الأسئلة؛ الواجهة لا تمنع Fill Blank بلا مفتاح وتحتاج تحويل الخيار المحدد صراحة إلى نص الإجابة | قفل صف الامتحان، فحص وجود الأسئلة ونشاطها ومؤسستها/مقررها/كاتبها، النص والنوع والنقاط ومفتاح الإجابة وخيارات MCQ، والعنوان/النطاق/التواريخ قبل تغيير الحالة. validator مشترك مع atomic publish، يقبل مفتاح أو نص خيار صحيح. UI تمنع الفراغ بلا إجابة وDAL تمرر خيار المدرس المحدد، لا تخمّن إجابة. `platform_service.py`, `lmsService.ts`, `QuizGeneratorView.tsx` | C1: 7رفض+2قبول/0/0، Exit0؛ كل رفض400 يبقي draft وpublished_at فارغًا؛ contract4/0/0 وbrowser focused Fill/OCR/SSE4/0/0؛ المجموعة النهائية C3 |
| fallback المعادلات يعيد HTML غير escaped | catch يعيد النص مباشرة إلى dangerouslySetInnerHTML | escape للحروف `& < > " '` و`trust:false` صريح. `FormulaRenderer.tsx` وtest، وتوسيع Vitest include إلى ts/tsx | C3: test forced-render-failure1/0/0؛ لا عنصر img أو onerror في DOM. لا أدّعي إثبات استغلال XSS فعلي كامل |
| N+1 في عرض تقييمات محتوى المقرر | select للدروس لكل module، فحص entitlement لكل درس، count للمحاولات لكل quiz | استعلام واحد للدروس عبر join، entitlement batch، ومحاولات مجمعة؛ عدم فتح unscoped assessment لغير الملتحق؛ teacher ownership. `routes/platform.py`, `payment_service.py`، وmastery aggregate | C1: query-budget1/0/0، Exit0؛ قبل9→201 SELECT، بعد11→11 لزيادة المحتوى من0 إلى12modules/36lessons/36quizzes؛ 24درسًا مجانيًا مسموحًا و12مدفوعًا مرفوضًا |
| API يعمل root | Dockerfile بلا USER؛ الاعتماد الضمني على كتابة مجلد storage قرب الكود | `USER 10001:10001`؛ source root-owned، staging `/srv/uploads` قابل للكتابة؛ cap_drop ALL وno-new-privileges لـAPI/worker. one-shot لترحيل ملكية staging فقط بلا شبكة/أسرار. `Dockerfile.api`, `.video`, `.qa`, `docker-compose.yml`, wrapper وprobe | C2: runtime permission probe1/0/0، Exit0؛ UID/GID10001، CapEff0، NoNewPrivs1، الكود/الأسرار RO وstaging writable؛ upload/download/حدود الملفات5/0/0 ضمن C2 |
| تنبيه npm High ظهر خلال الجولة النهائية | `source-map-js 1.2.1` اعتماد مشترك لـPostCSS/Tailwind وjsdom/css-tree؛ indexed source maps قد تضخم العمل والذاكرة | lockfile فقط إلى1.2.2 ضمن نطاقات الآباء المتوافقة، مع integrity من npm؛ regression ترفض offset ضخمة في constructor دون تنفيذ التضخيم، وتحافظ على mappings الطبيعية. `package-lock.json`, `sourceMapSecurity.test.ts` | npm ci Exit0،0ثغرات؛ focused2/0/0، Exit0؛ C3 النهائي يعيد كل الاختبارات والتدقيق |

HttpOnly يقلل سرقة credential عبر JavaScript، لكنه لا يمنع XSS من تنفيذ طلبات بصلاحية المستخدم؛
لم أضعف CSRF أو Origin/CORS أو SameSite. انظر
[OWASP Session Management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html).
KaTeX catch اختُبر بإجبار renderToString على throw؛ مع `throwOnError:false` لا تصل كل أخطاء الصيغة إلى catch،
ولذلك لا أصف ذلك كاستغلال مثبت. [خيارات KaTeX الرسمية](https://katex.org/docs/options.html).
إصدار source-map-js1.2.2 معلن كمصحح في [إصدار المشروع الرسمي](https://github.com/7rulnik/source-map-js/releases/tag/v1.2.2)
و[تنبيه CVE-2026-93749](https://github.com/advisories/GHSA-68fv-2mgg-jv7q).
وجوده هنا عبر أدوات البناء/الاختبار لا يثبت استغلالًا في API؛ أُصلح الاعتماد بدل استثناء dev packages من audit.

### أثر عقد الجلسة وتقليل الصلاحيات

- لم يعد JSON auth يحمل `token`. العملاء يستخدمون Set-Cookie وcredentials/include مع CSRF للطلبات المعدّلة.
  تبقى validation لـBearer المقدم صراحة من عملاء API، لكنها ليست fallback تلقائيًا للمتصفح ولا credential يُصدر في JSON.
  لا tokens للجلسة في localStorage أو sessionStorage؛ cached user/tab ليس credential ويظل غير موثوق للصلاحيات.
- refresh cookie محدودة بمسار `/api/v1/auth`. عندما ينتهي access، بقاء CSRF cookie مجرد hint لإرجاع401
  من bootstrap وتمكين تجديد واحد؛ ليست إثبات هوية. الطلب العام بلا cookies يبقى200 كضيف. أخطاء SQLAlchemy
  في optional identity تُرفع إلى معالج503، فلا يُسجَّل خروج بسبب تعطل DB. الاختبار الحي C2 يعطل PostgreSQL
  ويتحقق من bootstrap503 ثم authenticated200 بعد التعافي.
- اختبارات المتصفح تتحقق أن credential لا يظهر في document.cookie وأن cookie فعلية HttpOnly/Secure،
  وأن المفتاح القديم يُزال بعد registration/reload وأن browser requests لا تحمل Authorization.
- تم تحويل contexts الخاصة باختبارات ownership/payments/hydration/course switching/video إلى cookies+CSRF.
  اختبار الرابط المنسوخ يستعمل login ثانيًا صالحًا لنفس الطالب بنَفَس session مختلف، وليس طلبًا مجهولًا فقط.
- API وCelery/encoder النهائيون غير root. build steps وQA runner المؤقت للتجارب فقط يمكن أن تعمل root.
  خدمة `upload-permissions` استثناء one-shot محدود: CHOWN/DAC_OVERRIDE فقط، network none، read-only rootfs،
  بلا أسرار، تستهدف volume staging فقط ولا تحذف ملفًا ولا تمس S3/DB. لا تحويل volume MinIO إلى SeaweedFS.
  [Docker: استخدام USER](https://docs.docker.com/build/building/best-practices/).
- `STORAGE_DIR=/srv/uploads` ضروري: اختبار التكامل الأول كشف أن material upload يكتب `storage/extraction_tmp`
  قرب الكود؛ الإصلاح إعداد مسار staging، لا إعادة root أو جعل الكود writable.

## أوامر إعادة التشغيل

من جذر المستودع بعد إعداد البيئة المعزولة عبر أدوات `scripts/qa` الموثقة؛ لا تُشغّل fault tests على الإنتاج
أو بالتزامن مع تجربة بشرية أو Browser/Load. تحتاج media fixtures الواقعية وsecrets المحلية، لا أسرار في Git.

```powershell
./scripts/qa/run-video.ps1 -Stage Build
./scripts/qa/run-video.ps1 -Stage Backend                # C1
./scripts/qa/run-video.ps1 -Stage Integration            # C2: PostgreSQL/S3/faults
./scripts/qa/run-video.ps1 -Stage Browser                # C3: lint/build/unit/ALL browser/audit/diff
./scripts/qa/verify-runtime-source.ps1                   # C4: actual served source/asset hashes
./scripts/qa/run-video.ps1 -Stage Scan -ApproveScout      # C5: consent required for external SBOM
git -c core.safecrlf=false diff --check                  # C6
```

الـwrapper يحفظ ledger مستقلًا باسم وقت UTC مع Exit لكل أمر وJUnit/SARIF داخل `.qa/audit2`.
ملفات `.qa` الخام والبيانات والأسرار لا تُرفع؛ أدوات إعادة التشغيل والاختبارات نفسها ضمن المشروع.
لا استبعاد لاختبارات ولا تعطيل لـrate limiting؛ انتظار نافذة الحسابات التجريبية الحقيقية بين التجارب.
الـharness القائم يعزل عدادات auth للـIP المشترك فقط بين الحالات في Redis الخاص بمشروعي QA
المسموحين؛ لا يحذف حدود المستخدم أو video/session ledgers، ولا يغير إعدادات الإنتاج أو limits أثناء الحالة.

### ملخص الملفات

43 ملفًا لهذه الجولة: 7 ملفات API runtime للعقد والصلاحيات والنشر والاستعلامات؛
5 ملفات frontend runtime للكوكيز والنشر والمعادلات؛ 24 ملف اختبار أو أداة QA (يشمل إعداد Vitest)؛
4 ملفات Docker/Compose؛ wrapper واحد؛ lockfile؛ وهذا التقرير. تشمل الأدوات الجديدة probe للصلاحيات،
اختبارات HTTP/query budget، اختبار PostgreSQL للصلاحيات، وحالات cookie/KaTeX/browser.
المجلد غير المرتبط `pc_builder_3d_cases/` ليس ضمن هذا العدد أو الرفع.

## النتائج النهائية على نفس النسخة

| الأمر / البوابة | Exit Code | Passed / Failed / Skipped أو نتيجة | الدليل المحلي |
|---|---|---|---|
| Build / compose validation + rebuilding + actual startup | 0؛ أربع خطوات0 | API/migration/worker/web/staging ثم encoder/QA؛ force-recreate للصور المختارة دون حذف volumes | `video-commands-Build-20261006-035940.json`؛ تحديث QA tooling بعده Exit0 لإدراج أحدث fault assertion |
| إعادة web بعد تحديث source-map-js | 0 للبناء و0 للتشغيل | بنفس compose/project/env أعلاه: `build web` ثم `up -d --no-deps --no-build --force-recreate --wait --wait-timeout 90 web`؛ npm ci داخل Docker0ثغرات | image النهائي أدناه؛ backend لم يُعد بناؤه أو تغيير بياناته |
| C1 Backend | 0؛ أربع خطوات0 | **258/0/0**، 51.325ث؛ native Expat4/0/0 لكل صورة؛ lost multipart200، completion409، intent201، cleanup204، server5000 | `video-commands-Backend-20261006-040140.json`, `api-unit-video-20261006-040140.xml` |
| C2 all live integration | 0 | **39/0/0**، 619.053ث؛ PostgreSQL/concurrency/teacher scope/permissions/storage/faults | `video-commands-Integration-20261006-040400.json`, `api-integration-video-20261006-040400.xml` |
| C3 npm run lint | 0 | 0errors/3warnings: Fast Refresh export organization؛ ليست عيوب runtime | `video-commands-Browser-20261006-042533.json` |
| C3 npm run build | 0 | tsc/Vite ناجح؛ chunk فيديو633.87kB تحذير أداء باقٍ، لا تغيير حد التحذير | نفس ledger |
| C3 npm test | 0 | **49/0/0**، 10ملفات،2.51ث؛ cookieSession/fallback والنشر/request storms وsource-map regression | نفس ledger |
| C3 ALL Playwright | 0 | **74/0/0**،382.315ث؛ 1worker، دون استبعاد/تخطٍّ/إعادة حالة فاشلة | `video-browser-Browser-20261006-042533.xml` |
| C3 npm audit --audit-level=high | 0 | **0vulnerabilities**؛ لا استثناء للـdev dependencies | نفس ledger |
| C4 runtime-source + actual runtime permissions | 0 لكل أمر | API109/encoder109/web89 ملفات، mismatches0؛ probe UID/GID10001 CapEff0 NoNewPrivs1؛ HTTPS readiness200 وكل dependencies ok | `runtime-source-20261006T042641Z.json`؛ `docker exec chemistryaudit2-api-1 python -m scripts.verify_runtime_permissions` وGET `/api/v1/ready` |
| C5 Scout actual API/encoder images | raw2 لكل صورة؛ wrapper1 | API6High / encoder8High / Critical0؛ مفتوحة | `video-commands-Scan-20261006-040155.json` وملفا `scout-video-{api,video-worker}-20261006-040155.sarif` |
| C6 git diff --check | 0 | لا whitespace errors؛ أعيد بعد إنهاء التقرير وقبل commit | final command قبل commit |

مسارات الأدلة في الجدول ضمن `.qa/audit2/`. لا تُحسب جولات5 أكتوبر كإعادة اختبار لهذه النسخة.
الـquery budget يقيس SELECTs على SQLite/TestClient، لا p95/p99 ولا قدرة1000مستخدم.
بعد انتهاء C3، أعيد probe الصلاحيات بنجاح وGET الصفحة و`/api/v1/ready` أعادا200؛ الحاويات
API/encoder/Celery/web/proxy/upload-gateway/S3/PostgreSQL/Redis/mailpit كلها healthy.
طلبات HTTPS هذه تستخدم `-SkipCertificateCheck` للشهادة المحلية فقط؛ ليست اختبار ثقة الشهادة.

### نتائج byte boundaries الحية بعد إصلاح non-root staging

هذه ملفات ZIP/WebM صحيحة ومبطّنة لاختبار الحدود، وليست اختبار حمل واقعي متعدد المستخدمين.
في الحالتين المقبولتين طابقت بصمة SHA-256 وعدد بايتات download الملف الأصلي، وأُزيلت بيانات الدرس
الاصطناعي عبر API فقط. الجولة تضمنت كذلك PDF صالحًا أكبر من20MiB رفعًا وتنزيلًا مع تطابق البصمة.

| الملف بالبايت | HTTP | peak anonymous bytes | peak working-set bytes |
|---|---|---|---|
| material 1,073,741,824 | 201 | 368,504,832 | 1,442,041,856 |
| material 1,073,741,825 | 413 | 362,160,128 | 974,381,056 |
| video 5,368,709,120 | 200 | 375,615,488 | 1,458,704,384 |
| video 5,368,709,121 | 413 | 320,794,624 | 384,897,024 |

الـcgroup cap بقي1,610,612,736bytes (1.5GiB). total usage وصل الحد مع page cache،
وسجلت العينات تجاوزًا لحظيًا قدره184,320bytes في فيديو5GiB؛ لا تغيير للحد نفسه.
memory.events.max زاد512في PDF الكبير و627/215/87015/88405في حالات الحدود بالترتيب.
لا أخفي ضغط cache ولا أصفه كذاكرة فارغة: settled within same cap، OOM/kill delta0،
ولا restart جديد. كل anonymous/working-set بقي تحت الحدود الثابتة للاختبار، دون رفع cap.

## الجولات الفاشلة وتصحيح السبب

- قبل تطبيق الإصلاحات، regression API الجديدة فشلت12/12:11فشلًا وظيفيًا/أمنيًا حقيقيًا وحالة fixture
  فيها AttemptStatus غير موجود، ثم صُححت fixture وinstitution_id. الحالات الجديدة بعد التوسيع17/0/0 ضمن258.
- cookieSession regression قبل الإصلاح0/1/0؛ مسار fallback لم يُجمع في الجولة الأولى لأن Vitest include
  كان يقتصر على `.test.ts`؛ صُحح include، ولا يُدّعى إثبات before exploit منه.
- أول lint بعد تحديث contexts:3unused-variable errors؛ أزيلت المتغيرات المهجورة. أول Docker web build
  فشل بسبب unused React import في test الجديد؛ صُحح. أول startup افتقد image upload-permissions مع
  `--no-build`؛ wrapper أصبح يبني هذه الخدمة صراحة قبل التشغيل.
- أول integration كامل: **35/4/0، Exit1، 575.287ث**،
  `api-integration-video-20261006-032257.xml`. حالة fixture PostgreSQL افتقدت started_at الإلزامي،
  وثلاث حالات رفع material أعادت500 بسبب PermissionError على `storage` بعد خفض الصلاحيات.
  أضيف started_at للبيانات الاصطناعية وSTORAGE_DIR لصورة API؛ لا حذف لشيء ولا تغيير assertion للنجاح.
  أعيد بناء الصور ثم C1 ثم C2/C3 بالكامل؛ النتائج النهائية أعلاه هي الدليل، لا الجولة الفاشلة.
- إعادة integration التالية39/0/0، Exit0،630.304ث (`api-integration-video-20261006-033622.xml`)؛
  أُعيدت مرة أخرى بعد إصلاحات النشر/التجديد اللاحقة، فلا أستعمل نجاح النسخة السابقة كدليل نهائي.
- أول Browser كامل بعد التحويل: **70/3/0، Exit1** (`video-browser-Browser-20261006-034714.xml`):
  Fill Blank fixture بلا إجابة، وOCR quiz بمفاتيح ناقصة، وسباق bootstrap guest200 مع refresh أثناء reload.
  أُبقي رفض الأسئلة الناقصة؛ أضيف منع UI وإدخال الإجابة الفعلية في رحلة Fill Blank، وتحويل اختيار MCQ
  الصريح إلى نص، وbootstrap401 للتجديد مع المحافظة على DB503. السيناريوهان expired/absent في SSE كلاهما
  مرّا في focused4/0/0،32.4ث (`followup-cookie-publication-focused.xml`). OCR source-review fixtures
  تستخدم مفاتيح اصطناعية لهذا التدفق، وليست إثباتًا لصحة إجابات الملف علميًا أو اجتياز المطابقة الصارمة.
- فحص هوية الصورة أعادExit1 لأن Compose أبقى هوية web أقدم عند تغيير BuildKit attestation.
  API/encoder source hashes كانت متطابقة109/109؛ لم أضعف الفحص. أضيف force-recreate للقالب ثم أعيد
  بناء وتشغيل الصور واختبار الواجهة. المطابقة النهائية أعلاه تشمل هوية الصورة والبايتات، لا tag فقط.
- focused Vitest تعثر بـEPERM/realpath داخل العزل: Exit1، لا حالات مجمعة (فشل suite واحد).
  إعادة نفس الأمر بصلاحية التشغيل المناسبة أعطت contract4/0/0، Exit0؛ لا تغييرات لاستبعاد الحالات.
- اختبار DB outage الجديد أولًا حقن الخطأ في session التجهيز لا session HTTP، فرجع200؛ صُححت fixture
  إلى Session class، وأُعيد إنتاج الخلل الحقيقي401 بدل503، ثم أُصلح optional dependency وأصبح503.
  كل هذه الحالات متضمنة في258 النهائية.
- جولة Browser التالية اجتازت **74/0/0، Exit0،383.117ث**
  (`video-browser-Browser-20261006-041448.xml`)، ومعها47اختبار وحدة ناجح؛ لكن wrapper أعادExit1
  لأن npm audit كشف High جديدًا في source-map-js1.2.1 (CVE-2026-93749). لم يُستثنَ dev dependency
  ولم يُخفض مستوى audit؛ lockfile حُدّث إلى1.2.2، وnpm ci Exit0/0vulnerabilities. أول focused جديد
  **1/1/0، Exit1**: رفض المدخل الخبيث نجح، لكن اختبار positive استخدم originalPositionFor عند بداية
  indexed section، حيث ترجع المكتبة null. أصبح positive يتحقق مباشرة من eachMapping للملف الطبيعي
  مع إحداثياتها كاملة؛ لا حذف للاختبار السلبي أو اختبارات المشروع، وأصبح focused2/0/0، Exit0.
  لا ادعاء بإصلاح سلوك boundary في مكتبة upstream؛ ليس مسارًا يستخدمه التطبيق لمعالجة ملفات الطلاب.
  أُعيد بناء web فقط وتشغيله بـforce-recreate، ثم C3 كاملة (النتائج النهائية أعلاه). API/encoder لم
  يتغيرا في هذه الخطوة؛ C4 النهائي يعيد التحقق من هويتيهما وكل ملفات109/109، لذلك C1/C2 أعلاه
  ما زالت على نفس API النهائي، لا نجاح نسخة أخرى.

## فصل الإصلاح عن بوابات النشر الأوسع

التغييرات محلية قابلة للمراجعة ومختبرة على Docker بحسب نتائج هذا التقرير؛ رفعها إلى GitHub لا يعني نشر موقع.
الـcommit الذي يحتوي هذا التقرير يُحدد بـ`git log -1 -- docs/QA_FOLLOWUP_SECURITY_2026-10-06.md`؛
التطابق النهائي مع GitHub يُتحقق عبر `git ls-remote origin refs/heads/fix/queen-p0-handoff`.

هويات الصور المشغلة فعلًا في الجولة النهائية؛ ليس الاعتماد على tag متغير:

```text
backend      sha256:cf32269c86c6ad219316514d63943c311d1c908eed28de91052344bc1271f8e6
video-worker sha256:7b02402eea811fbccf51f3d2c430ffb799be0dcf3fb71d13aebceace95d3645e
web          sha256:a63ad27f295276c1afe557daa5aa673ff941356eb931cf6e230ba4e06ec077cb
```

Scout لا يزال بوابة مستقلة مفتوحة، بلا suppressions أو تخفيض severity. الفرز التفصيلي السابق في
`docs/QA_SECURITY_RECHECK_2026-10-04.md` و`docs/QA_FIXES_2026-10-05.md`؛ لم أجر reachability audit
جديدًا لكل CVE في هذه الجولة. لا تُعتبر non-root أو نجاح الاختبارات إصلاحًا للثغرات نفسها.

| تنبيهات High الباقية | حزم source / نسخة Scout | حالة الجولة |
|---|---|---|
| CVE-2026-102010، CVE-2026-95619 | gcc-14 `14.2.0-19` | الصورتان؛ scanner not fixed |
| CVE-2026-86140، CVE-2026-74860 | libxml2 `2.12.7+dfsg+really2.9.14-2.1+deb13u3` | الصورتان؛ scanner not fixed |
| CVE-2026-85091 | zlib `1:1.3.dfsg+really1.3.1-1` | الصورتان؛ scanner not fixed، لا إثبات انعدام الوصول |
| CVE-2026-93990 | expat `2.8.5-0chemistry1` | الصورتان؛ native regression ينجح لكن التنبيه باقٍ، حزمة upstream مستقرة محلية شفافة |
| CVE-2026-30997، CVE-2026-38347 | ffmpeg `7:7.1.5-0chemistry1` | encoder؛ scanner يقترح `7:7.1.5-0+deb13u1`؛ لم أعِد تسمية الحزمة لتصفيره ولا أدّعي إغلاقه |

Scout كتب SARIF رغم تحذير Windows file lock عند تنظيف أرشيف مؤقت؛ لم أحذف ملفات Docker للتحايل.
بوابة OCR الصارمة الأقدم6/1/0 لم تُعد ولم تُغلق هنا. CDN/DRM خارجي غير مفعّل؛ لا ضمان مطلق لمنع
تنزيل الفيديو أو تسجيل الشاشة. شهادة localhost غير موثوقة عامًا؛ لم تُختبر شهادة/سيرفر خارجي.
لم تُجر جولة حمل أو backup/restore كاملة جديدة؛ الأدلة السابقة منفصلة. لذلك **لا إعلان جاهزية نشر عامة**.
