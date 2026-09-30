# إغلاق عوائق قالب الإنتاج والتخزين — 30 سبتمبر 2026

> ملاحظة التسليم: أذن المستخدم لاحقًا بحفظ جميع الإصلاحات ورفعها إلى فرع `fix/queen-p0-handoff`. وصف «محلي فقط» وحالة Git أدناه لقطة تاريخية وقت تنفيذ QA قبل commit؛ لا تصف حالة الفرع بعد رفع هذه النسخة. استعمل Git HEAD/سجل الفرع لمعرفة commit التسليم. الرفع لا يعني دمجًا أو نشر الموقع أو اعتماد الإصدار؛ عوائق High الأربعة ما زالت قائمة. الأسرار والبيانات والنسخ الاحتياطية تحت `.qa/` مستثناة من Git.

التعديلات محلية فقط، لا push ولا دمج ولا نشر خارجي. **لا اعتماد نشر** مع بقاء أربعة تنبيهات High في API دون إصلاح Debian Trixie متاح. هذا التقرير يحدّث تقرير أول اليوم، ولا يمحو نتائج الفشل التي أعيد إنتاجها.

## Git والنسخة المختبرة

- الفرع `fix/queen-p0-handoff`، وHEAD=`d70eea083e33cca7e042170a9cdd7c74aab3e44d`. نجح التحقق المباشر `git ls-remote origin refs/heads/fix/queen-p0-handoff`، Exit 0، والفرع المرفوع على GitHub يحمل الـSHA نفسه. لا توجد commits محلية زائدة ولا staged changes؛ الإصلاحات كلها working tree غير محفوظة في commit، أو ملفات جديدة غير متتبعة. ليست مرفوعة إلى GitHub. الملفات محفوظة على القرص، لا داخل commit. آخر status: 52 ملفًا متتبعًا معدّلًا و58 ملفًا جديدًا غير متتبع (المجلدات grouped في git status)؛ يشمل ذلك عمل الوكيل الآخر المحفوظ.
- النسخة النهائية المعاد بناؤها: API `sha256:8eda6e4b1c569d6f88d0e746b4630ef2616cd266c62fe0718ef90e006edae486`، web `sha256:3c9900ab46037338e261d9542721b958de85d370533e9d0c5f56e899ec2ad6c8`، SeaweedFS `4.48@sha256:4e61d15fd35994cb1e43e1e553dff106794841fd9a99ade2fc8c8bfce4d7872d`. صور التطبيق محلية مبنية وليست releases منشورة.
- المشروع النشط `chemistryprodlocal` هو **قالب الإنتاج نفسه** `infra/docker-compose.yml` مع overlay اختبارات واضح `infra/qa/production.override.yml`. HTTPS محلي `https://localhost:18443`، HTTP محلي 18480، صندوق بريد اختباري 18425. لا منافذ PostgreSQL أو Redis أو S3 منشورة. `chemistryqa` القديم موقوف وvolumes محفوظة، وليس دليل اختبار القالب الحالي.
- لم أكتب فوق `document_parsers.py` أو `exam_text_extractor.py` في هذه الجولة. بصماتهما داخل API تطابقت مع working tree: `f826e428…e1a95` و`ac9e3aae…17418`. مجموعة API تشمل اختبارات Extract وملفات blind inputs، وليست نجاحًا مستنتجًا من اختبارات خارج Extract. نجاح العينات لا يعني «استخراج مثالي» لكل مستند ممكن.

## أوامر قابلة لإعادة التشغيل

من جذر المشروع في PowerShell 7، مع Docker Desktop Linux Engine وNode/npm:

```powershell
./scripts/qa/run-production.ps1 -Stage All
```

تفاصيل التشغيل، prerequisites، الشبكات والأسرار والترحيل في [دليل الإنتاج](PRODUCTION_DOCKER_RUNBOOK.md). الإعدادات والأدوات المهمة أصبحت تحت `infra/qa/`، `scripts/qa/` و`apps/api/scripts/`، لا تعتمد على ملفات scratch الشخصية. المخرجات المولّدة والأسرار والشهادات تحت `.qa/production` ignored. الاختبارات المباشرة لا يجوز تشغيلها على بيانات حقيقية: تتحقق من اسم مشروع QA، وتتحكم فقط في حاوياته.

اختبارات API والمتصفح متتابعة، لا متزامنة، لمنع تداخل عزل counters. معدلات الحماية الحقيقية تبقى مفعّلة داخل الحالة. إنهاء اتصالات QA يسجّل الخروج عبر API؛ تكرار storage drill لا يرفع الحد ولا يمحو ledger مباشرة.

## جدول العوائق والأدلة الحية

`DC` اختصار لـ `docker compose --env-file .qa/production/compose.env -p chemistryprodlocal -f infra/docker-compose.yml -f infra/qa/production.override.yml`. العدّ = Passed / Failed / Skipped؛ «—» أمر تشغيلي وليس عدد اختبارات.

| العائق | قبل / السبب | بعد الإصلاح المحلي واختبار Docker | الملفات الأساسية | الأمر / Exit / العدّ |
|---|---|---|---|---|
| MinIO/mc 401 | الـmanifest رفض pull حتى بعد Bearer token ناجح؛ غياب auths وتكرار بمصادقة محايدة يستبعد cache credentials، ولا يثبت وجود tag/digest خلف الرفض | بموافقة المستخدم: SeaweedFS ثابت بدل MinIO/mc، volume جديد، S3 secret، bucket خاص، المخزن نفسه في قالب الإنتاج والاختبار | `infra/docker-compose.yml`, `.env.production.example`, `scripts/qa/registry_probe.py`, `apps/api/scripts/s3_snapshot.py` | probe Exit 0، pulls Exit 1؛ `DC up -d --wait` Exit 0؛ — |
| بدء migrations مع أسرار عشوائية | تشغيل القالب فعليًا فشل لأن `%2B/%2F` في كلمة المرور المرمّزة اعتُبرت ConfigParser interpolation | escape `%` في طبقة Alembic فقط؛ PostgreSQL يرى كلمة المرور الأصلية | `apps/api/alembic/env.py`, `test_migration_credentials.py` | migration أولًا 1، بعد الإصلاح 0؛ اختبار regression ضمن API النهائي |
| OpenSSL CVE-2026-84782 | installed `3.5.7-1~deb13u2` مع candidate مصحح من trixie-security؛ طبقة apt cached | `openssl` و`libssl3t64` أصبحا `3.5.7-1~deb13u3`، مع حد أدنى يفشل البناء إن لم يتوفر الإصلاح | `infra/Dockerfile.api` | apt policy/rebuild/dpkg Exit 0؛ Scout النهائي لا يحتوي هذا CVE |
| أخطاء integration والجمع | ثلاثة collection errors بسبب requests مفقود؛ harness استعمل routes Knowledge Center المحذوفة وأسماء حاويات قديمة، اختبار advisory lock كان importorskip | image QA مستقل يضيف dependencies دون إدخالها إلى runtime؛ أسماء خدمات من Compose labels؛ اختبارات فعلية current uploads/PG/rate/worker؛ لا حذف أو exclusion لاختبارات | `infra/Dockerfile.qa`, `tests/integration/`, QA overlay | `DC run --rm --no-deps qa-tests python -m pytest tests --tb=short --junitxml=/qa/api-tests.xml` Exit 0؛ **155 / 0 / 0** |
| OCR المتخطى | fixture كان يشير إلى upload شخصي محذوف | يستخدم `textbook_sample_5pages.pdf` المشحون، ويتحقق من OCR عربي فعلي؛ لا skip | `test_pdf_garbling_and_ocr.py` | ضمن المجموعة النهائية، passed؛ 0 skipped |
| Worker recovery | اختبار جديد بدأ task ثم kill فعلي، لكن timeout 100s انتهى قبل Kombu QoS restore sweep + 20s runtime | timeout يراعي sweep، واستُعيد delivery فعليًا مع starts≥2 وdurable marker واحد؛ API يخدم أثناء غياب worker | `tests/integration/worker_probe.py`, `test_worker_crash_recovery.py` | أولًا failed، أخيرًا passed ضمن 155؛ لا ادعاء بأن indexer المحذوف يعمل |
| توقف PostgreSQL | GET courses أعاد 500 | sanitized 503 + Retry-After، connect_timeout 5s، عودة readiness والبيانات | `core/database.py`, `core/errors.py`, `test_service_recovery.py` | fault injection قبل 500؛ بعد 503، recovery passed ضمن API |
| توقف S3 | ملف موجود ظهر 404 عند تعطل المخزن؛ exists ابتلع كل exceptions | 404 فقط للمفتاح المفقود؛ الانقطاع 503؛ timeouts وclose stream عند disconnect؛ readiness cache 5s | `core/storage.py`, `core/errors.py`, `test_storage_outages.py` | قبل 404؛ بعد 503، recovery passed؛ ثلاثة unit regressions ضمن API |
| توقف web/proxy | proxy انتظر أكثر من 30s؛ bind-mounted config لم يُعاد تحميله بـup وحده | connect timeout 3s + nginx reload؛ web outage 502/504 حسب DNS/cache، proxy outage connection error؛ تعافٍ وبيانات دون تغيير | `infra/nginx-https.conf`, `apps/web/nginx.conf`, recovery harness | nginx -t/reload Exit 0؛ web بعد reload 504 خلال 3.005s؛ كلا الحالتين passed |
| Redis وSMTP | Redis required، لا بد من fail-closed. SMTP configured failures لا يجب كشف وجود بريد معيّن | Redis outage 503 وتعافى؛ SMTP outage رسالة عامة 200 + log sanitized، ثم رحلة بريد/reset ناجحة بعد التعافي؛ TLS يتحقق من الشهادة محليًا | `mail_service.py`, config, production overlay, recovery/browser tests | ضمن API والمتصفح؛ 200 ليس دليل وصول البريد الخارجي |
| جلسات الفيديو بعد إلغاء كل الجلسات | storage drill اصطدم بـ429 من خانات جلسات ميتة؛ close TCP لا يساوي logout، revoke-all لم يحرر ledger | client cleanup يسجّل الخروج؛ revoke-all/change/reset يحرر خانات الحساب بعد إلغاء refresh families، دون تغيير الحد؛ drill reauth عبر API | auth routes/service, platform slots, live_helpers, storage_drill, regression test | أول drill فشل 1 عند 429؛ drill النهائي Exit 0؛ regression ضمن API |
| سجلات رموز الفيديو في Nginx | فحص حي بعد playback الكبير وجد 14 تطابقًا لرمز خام في web و22 في proxy؛ تحذيرات temporary buffering تطبع request وupstream، رغم access_log off | proxy_buffering off؛ privacy access format بالمسار دون query/cookies/referer، يحفظ status/upstream/time؛ تعطيل error log الخام على مستوى server لأن Nginx لا يتيح تنقيحه، مع بقاء diagnostics بدء التشغيل وأخطاء التطبيق المنقحة | `apps/web/nginx.conf`, `infra/nginx.conf`, `infra/nginx-https.conf`, `tests/integration/test_playback_log_privacy.py` | nginx -t/reload Exit 0؛ regression حي: full video ثم stop API/502 أو504/recovery/range؛ **1 / 0 / 0**، ولا ظهور للرمز الفعلي في أي hop؛ ضمن API النهائي |
| ثبات التخزين والمحتوى | اختبار قالب الإنتاج الحقيقي كان غير مكتمل | فيديو صالح 35,382,809B وPDF صالح 25,928,857B وإيصال؛ full download + ثلاث ranges/seek + ملكية/استحقاق، وبعد force-recreate للـS3/PG/API بقيت البصمات | `storage_drill.py`, generator scripts, storage drill PS | `./scripts/qa/production-storage-drill.ps1` Exit 0؛ 0 checksum/permission mismatches |
| Backup/restore فعلي | mirror قديم ليس snapshot بمراجعة checksum؛ التخزين البديل لم يكن معتمدًا | freeze writers، PostgreSQL dump + S3 snapshot نهائي 40 objects/766,257,275B؛ restore على server/volumes جديدة؛ 49 tables/1,181 rows متطابقة؛ API جُرّب فعليًا على S3 المستعاد ثم أعيد للأصل | `s3_snapshot.py`, `verify_db_restore.py`, production/QA Compose, drill PS | jobs/restore/verify Exit 0؛ 40/0 اختلاف، 49 جدولًا و1,181 صفًا/0 اختلاف؛ originals محفوظة |
| جاهزية بعد الاستعادة | إعادة drill الأكبر أكملت hashes وDB restore ثم فشلت Exit 1 لأن sleep(5) ثم request واحدة سبقت جاهزية Celery | worker --wait مع health check، ثم polling لreadiness HTTPS حقيقية بمهلة 160s، لا قبول 503/degraded؛ التحقق على restored وعلى source عند العودة | `scripts/qa/production-storage-drill.ps1` | إعادة drill كاملة Exit 0؛ worker/storage/DB readiness عادت؛ لم يتغيّر كود التطبيق أو شدة health checks |
| الملفات الكبيرة والذاكرة | 501MB على route محذوف، buffering في client وأسماء docker stats خاطئة | upload PDF 25.9MB streaming + تنزيل SHA مطابق؛ ملف 101MiB رُفض 413 وفق الحد الحالي 100MiB؛ memory samples من container الفعلي تحت 1536MiB | large-file test, `generate_qa_pdf.py` | passed ضمن API؛ العينة السابقة peak API 344,002,560B، لا تعميم سعة |
| lint/build ووظائف المتصفح | التقرير الأول 27 ESLint errors و30 warnings ورحلات غير مكتملة | أخطاء ESLint صفر؛ ثلاث warnings Fast Refresh تطويرية، لا runtime bug؛ الحساب/reset/جلسات/دفع/إيصال/اعتماد/تصحيح/إشعارات/شبكة/CSRF/CORS/ملفات/فيديو تختبر على HTTPS والقالب الحقيقي | web source + QA specs/config | النتائج النهائية أدناه |
| حمل واقعي | 10 ثوانٍ، فيديو 784B وranges 100B لا تثبت سعة | 3 مراحل ×60s، جلسات 1/5/10؛ video chunks 512KiB مع offsets، PDF 25.9MB ورفع متزامن؛ sampling RAM/PG، لا retry أوتوماتيكي لـ429 | `scripts/qa_load.py`, QA orchestration | النتائج النهائية أدناه؛ لا ادعاء 1000 مستخدم |

## فحص الثغرات الحالي — دون إخفاء أو تخفيض شدة

Debian sources داخل الصورة: `trixie`, `trixie-updates` من `deb.debian.org/debian`، و`trixie-security` من `deb.debian.org/debian-security`، موقعة بمفتاح Debian. لم أستخدم sid/forky. Scout على النسخة النهائية: **API 0 Critical / 4 High؛ web 0 C/H؛ SeaweedFS 0 C/H**. جميع scanner commands Exit 0 تعني نجاح الفحص لا قبول الإصدار. الأداة نبّهت إلى فشل حذف archive مؤقت لأنه مقفول في Windows، لكنها أتمّت indexing وكتبت SARIF؛ لم تُحذف ملفات المستخدم لتجاوز التنبيه.

| التنبيه | نسخة الصورة / أحدث إصلاح | دليل reachability وتخفيفه / ما بقي |
|---|---|---|
| [CVE-2026-84782 — OpenSSL](https://security-tracker.debian.org/tracker/CVE-2026-84782) | `3.5.7-1~deb13u3` مصحح رسميًا في trixie-security | أُغلق بالتحديث وإعادة البناء/المسح؛ HTTPS/SMTP والتخزين واختبارات API أعيدت على النسخة الجديدة، لا استعمال DTLS في التطبيق |
| [CVE-2026-74860 — libxml2](https://security-tracker.debian.org/tracker/CVE-2026-74860) | OS `2.12.7+dfsg+really2.9.14-2.1+deb13u3`؛ لا إصلاح Trixie؛ upstream 2.15.3 | binding Python `libxml2` SAX **غير مثبت** (فحص runtime)، وهو شرط المسار الموصوف؛ lxml ليس binding SAX المذكور. لا يظهر وصول مباشر لهذا المسار، لكن scanner High محفوظ وليس suppressed |
| [CVE-2026-86140 — libxml2](https://security-tracker.debian.org/tracker/CVE-2026-86140) | OS النسخة نفسها؛ no Trixie fix، upstream 2.15.4. lxml bundled **2.14.6** أيضًا يجب أخذه في الحساب | DOCX parser لم يحل external entity في فحص واقعي، ولا يفعّل DTD validation؛ لا استدعاء xmlSnprintfElements مباشر. Tesseract مرتبط بمكتبة OS عبر libarchive، فلا أجزم باستبعاد كل مسار غير مباشر. يبقى عائقًا؛ تجنب DTD، حافظ على limits/isolation، يحتاج backport مستقر أو تحديث upstream مُختبر |
| [CVE-2026-93990 — Expat](https://security-tracker.debian.org/tracker/CVE-2026-93990) | OS `2.8.3-1~deb13u1` دون Trixie fix؛ upstream 2.8.5. Python pyexpat **2.8.3 statically bundled** (ldd لا يربطه بـlibexpat OS) | PDF/metadata وأي XML UTF-16 غير موثوق لا يمكن استبعادها. تحديث حزمة OS وحده لن يغيّر pyexpat؛ مراجعة base/CPython مطلوبة أيضًا. لا قراءة XML خام مقصودة، وDOCX entities لا تُحل؛ يبقى High |
| [CVE-2026-85091 — zlib](https://security-tracker.debian.org/tracker/CVE-2026-85091) | OS `1:1.3.dfsg+really1.3.1-1+b1`, Python runtime 1.3.1؛ Debian يسجّل unfixed | المسار الموصوف nonblocking gzwrite ثم gzprintf/gz_vacate؛ لا يظهر استخدامه في التطبيق. ضغط Python/ZIP/backup ليس وحده إثبات الوصول إلى هذا المسار، لكن أدوات أصلية مرتبطة بـzlib. الاحتفاظ بالتحذير وعدم بناء استثناء اعتماد دون trace أو patch مُراجع |

التنبيهات الثمانية القديمة ليست قائمة موثقة كاملة في تقرير 29 سبتمبر، والصورة القديمة حُذفت؛ لا يمكن اختراع هوية كل واحد منها. أُزيل pip وvendored dependencies من runtime خلال الجولة السابقة، والـSARIF الحالي يعرض كل C/H الموجودة بعد rebuild. لا ندّعي أن أي تنبيه تاريخي مجهول أُصلح دون معرف/دليل.

## الحدود المتبقية

- ما زالت أربعة High أعلاه بلا إصلاح Trixie متاح، مع reachability موثقة لا ضمان عدم الاستغلال. لا release approval آليًا من نتائج الاختبارات.
- لا خادم خارجي ولا شهادة عامة ولا real payment settlement ولا خارجية inbox delivery. الشهادة المحلية اصطناعية ومحدودة العمر؛ قالب الإنتاج يحتاج إعدادًا وتشغيلًا ومراقبة منفصلة على السيرفر.
- SeaweedFS mini عقدة واحدة، والنسخ المحلية ليست HA أو offsite/encrypted backups. bucket IAM/version history يحتاجان إدارة منفصلة؛ default private اختُبر قبل/بعد restore.
- المستخدم حذف بيانات learningproject عمدًا سابقًا. volume القديم المسمى `chemistryqa_qa_minio` فُحص read-only: 4 ملفات/22,528B ومجلدات LocalStack metadata، ليس مخزن MinIO صالحًا بكائنات للتَرحيل. احتُفظ به وبجميع volumes القديمة/المستعادة. لا ادعاء بترحيل بيانات MinIO فعلية؛ إن ظهرت لاحقًا تُرحّل عبر S3 فقط وبصمات.
- حماية الفيديو تمنع مشاركة الرابط والمشاهدة بلا استحقاق/جلسة، ولا تمنع نسخ bytes التي تصل لطالب مخوّل أو تسجيل الشاشة منعًا مطلقًا. لا DRM provider متاح؛ هذا القيد لا يمكن إغلاقه بوعد HTML/Network مضلل.
- Extract اجتاز مجموعة fixtures الحالية، وليس ضمان دقة 100% لكل صور/PDF/Word ممكنة. لا تُستنتج سلامته من اختبارات الواجهة وحدها.

## النتائج النهائية للواجهة والأداء

هذه النتائج أعيدت بعد تعديل رسائل auth وخصوصية سجلات Nginx، على صور API/web المثبتة أعلاه، لا على الصورة السابقة. الجولات المتتابعة انتهت دون تغيير آخر في كود التطبيق. إعادة التحقق بعد الحمل أثبتت full video/PDF/receipt SHA وثلاث ranges والصلاحيات؛ المخزن الأصلي أصبح يحتوي 40 كائنًا تجريبيًا، وأعيدت تجربة الإنقاذ على الصور النهائية وبنفس هذه البيانات: snapshot 40 كائنًا، واستعادة جديدة، وتشغيل API على S3 المستعاد ثم العودة للأصل. snapshot الأولى كانت 9 كائنات؛ النتيجتان محفوظتان، لا تخلط بين نقطتي الزمن.

| الأمر النهائي | Exit Code | Passed | Failed | Skipped | QA حي / ملاحظات |
|---|---:|---:|---:|---:|---|
| `DC build api worker migration s3-init web` ثم `DC build qa-tests` | 0 لكل أمر | — | — | — | بناء صور التطبيق والمخزن المرشح نفسه؛ لا تبديل إلى test storage |
| `DC up -d --wait --wait-timeout 160` | 0 | — | — | — | الخدمات الثماني running/healthy، migration وs3-init انتهيا 0 |
| `DC exec -T proxy nginx -t`، `nginx -s reload`، و`DC exec -T web nginx -t` | 0 لكل أمر | — | — | — | HTTPS محلي وشهادة اصطناعية؛ لا اختبار شهادة عامة |
| `DC run --rm --no-deps qa-tests python -m pytest tests --tb=short --junitxml=/qa/api-tests.xml` | 0 | **155** | **0** | **0** | 210.642s، منها 12 integration حية، وبقية المجموعة unit/fixtures؛ 5 تحذيرات Starlette deprecation، ليست فشلًا |
| `npm run lint` | 0 | — | — | — | 0 errors، 3 warnings Fast Refresh تطويرية في ConfirmWizard:115 وToastProvider:45 وi18nContext:101؛ لم أُعطّل القاعدة |
| `npm run build` | 0 | — | — | — | TypeScript + Vite؛ بناء Docker للواجهة نجح أيضًا |
| `npm run test -- --run` | 0 | **5** | **0** | **0** | request-storm regressions |
| `npx playwright test --config playwright.qa.config.ts --reporter=list,junit` | 0 | **26** | **0** | **0** | 48.119s، منها 12 responsive و14 رحلات QA؛ HTTPS فعلي، 35.4MB WebM، تسجيل/reset/تغيير كلمة المرور وإلغاء الجلسات/دفع وموافقة وتصحيح وإشعارات/ملكية/CSRF/CORS وشبكة |
| `npm audit --audit-level=high` | 0 | — | — | — | 0 vulnerabilities؛ dependency xlsx القديمة مستبدلة في working tree |
| `DC run --rm --no-deps qa-tests python -m scripts.qa_load` | 0 | — | — | — | 3,507 requests، 0 errors؛ تفاصيل المراحل أدناه |
| `docker scout cves chemistryprodlocal-api --only-severity critical,high --format sarif --output .qa/production/scout-api.sarif` | 0 | — | — | — | 369 packages؛ **0 Critical / 4 High** في 3 حزم، لا قبول إصدار |
| الأمر نفسه للـweb، ثم SeaweedFS بالـdigest المثبت | 0 لكل أمر | — | — | — | web: 26 packages / 0 C/H؛ S3: 292 packages / 0 C/H؛ هذا فحص C/H فقط |
| `DC run --rm --no-deps qa-tests python -m scripts.storage_drill verify` بعد الحمل | 0 | — | — | — | 40 كائنًا، full hashes وثلاث ranges، 0 checksum/permission failures |
| `./scripts/qa/production-storage-drill.ps1` على الصور النهائية وبعد الحمل | 0 | — | — | — | snapshot `20260930T131235Z-409b5a55`؛ 40 كائنًا/766,257,275B؛ 49 جدولًا/1,181 صفًا، صفر اختلاف؛ API على restored ثم source مع readiness TLS متحققة، volumes محفوظة |
| `git diff --check` | 0 | — | — | — | لا whitespace errors؛ تنبيهات تحويل LF إلى CRLF معلوماتية فقط |

الجولة السابقة لا تُمحى: اختبار 429 الجديد كان **25/1/0، Exit 1**؛ الرد الحقيقي 429 وصل والرسالة ظهرت لكن بلا `role=alert`. الإصلاح في `apps/web/src/views/AuthView.tsx` أضاف إعلان الخطأ لقارئ الشاشة، ولم يغيّر rate limits أو يحذف الحالة. بعد إعادة البناء أصبحت 26/0/0، واختبار 429 سجّل POST واحدًا فقط دون retry تلقائي. نتيجة ما قبل الإصلاح محفوظة في `.qa/production/browser-before-alert.xml` و`.md`، وتقرير Playwright النهائي منفصل.

التسليم المتزامن: حالة `api-ownership.spec.ts` أرسلت **8 POSTs فعلية متزامنة** إلى PostgreSQL عبر API ذي عاملَي Uvicorn؛ جميعها 200، بلا 500. بعد آخر مجموعة: SQL أعطى **12 answer rows / 12 unique (attempt_id,question_id) pairs** و**0 duplicate pairs**. العدد الإجمالي يشمل الجولات السابقة؛ لكل attempt زوج واحد رغم تكرار التسليم.

```sql
SELECT count(*) AS answer_rows,
       count(DISTINCT (attempt_id,question_id)) AS unique_pairs
FROM quiz_attempt_answers;
SELECT count(*) AS duplicate_pairs FROM (
  SELECT attempt_id,question_id FROM quiz_attempt_answers
  GROUP BY attempt_id,question_id HAVING count(*) > 1
) duplicates;
```

خصوصية logs بعد `2026-09-30T12:53:00Z`: فحص حي وقت الجولة النهائية وجد api **419 tokens redacted / 0 raw**، web **0 raw** مع 1,496 safe upstream lines، proxy **0 raw** مع 1,503 safe upstream lines؛ الأعداد لقطة زمنية لا إجمالي نهائي متوقف. regression الحي يتحقق أيضًا من عدم وجود الرمز الفعلي خلال full playback وتعطل API وتعافيه. سجلات proxy قبل reload قد تبقى محتوية رموز QA قصيرة العمر المنتهية؛ لم أستخدم حذف logs لتمرير الفحص أو أنشر رموزها. إعادة إنشاء web عند بناء الصورة الجديدة تستبدل سجلات حاويتها الاعتيادية؛ لا ادعاء بأن تاريخ كل حاوية محفوظ. أمن السجلات القديمة وretention مسؤولية تشغيلية منفصلة.

### الحمل النهائي بعد تعديل proxy

لكل مرحلة نحو 60s، فيديو صالح **35,382,809B**، وPDF صالح **25,928,857B**. الطلاب يتصفحون courses/bootstrap/notifications/progress، وينقلون مقاطع فيديو متزامنة **512KiB** عند offsets مختلفة. هناك 1/3/3 uploads متزامنة (7 ملفات PDF إجمالًا، نحو 181.5MB مرفوع). هذه حركة بث/range متزامنة، **ليست عشرة متصفحات تفك ترميز الفيديو**؛ تشغيل HTML video وseek اختُبرا منفصلًا في Playwright. لا retry لرد 429 في harness؛ يسجّل الخطأ وRetry-After ويُفشل الحمل عند أي خطأ.

| جلسات | مدة s | Requests | Throughput req/s | p95 ms | p99 ms | أخطاء / معدل |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 60.25 | 225 | 3.73 | 23.83 | 45.86 | 0 / 0% |
| 5 | 60.53 | 1,105 | 18.26 | 39.95 | 127.52 | 0 / 0% |
| 10 | 60.54 | 2,177 | 35.96 | 52.94 | 180.44 | 0 / 0% |

| نوع الطلب | p95/p99 عند 1 جلسة ms | عند 5 ms | عند 10 ms |
|---|---:|---:|---:|
| Browse | 21.65 / 28.57 | 30.97 / 81.04 | 41.56 / 158.05 |
| Video chunk | 26.12 / 45.86 | 46.09 / 103.13 | 70.89 / 181.18 |
| Upload (عينات 1/3/3 فقط) | 2,393.90 / 2,393.90 | 3,533.16 / 3,533.16 | 3,684.27 / 3,684.27 |

Upload percentiles بعينات قليلة هي وصف لهذه العينات فقط، لا تقدير tail latency موثوق عام. Timings تشمل الاستجابة كاملة، لا headers فقط. `transferred_bytes` في artifact يمثل bytes المستلمة من responses، لا مجموع الاتجاهين؛ الإجمالي المستلم **939,951,739B**. التشغيل لم يختبر حمولة أطول من المراحل الثلاث، ولا 1000 مستخدم نشط.

| الخدمة | أعلى memory usage مرصود B | MiB تقريبًا |
|---|---:|---:|
| API | 398,376,960 | 379.92 |
| Worker | 65,048,576 | 62.04 |
| SeaweedFS | 966,619,136 | 921.84 |
| PostgreSQL | 64,331,776 | 61.35 |
| Redis | 6,713,344 | 6.40 |

Memory هي Docker charged usage وتشمل cache، ليست RSS فقط؛ sampler دوري وقد يفوّت قمم قصيرة. أعلى اتصالات PostgreSQL المرصودة **17**، وأعلى active connections مرصودة **1**؛ هما maxima منفصلان. بعد الحمل OOM=false وRestartCount=0 للخدمات الخمس. S3 قريب نسبيًا من حد QA البالغ 1GiB؛ يلزم headroom ومراقبة/تحديد موارد السيرفر، ولا أستنتج سعة production من هذه العينة. جولة ما قبل إصلاح logs محفوظة `load-before-log-privacy.json`؛ نتائجها ليست المستخدمة في الجدول النهائي.

### ملخص ملفات المراجعة وحالة التسليم

- **أُصلح محليًا:** قالب S3/الأسرار/TLS/backups في `infra/docker-compose.yml`, `infra/.env.production.example`, `infra/nginx-https.conf` و`apps/api/entrypoint-prod.sh`؛ OpenSSL في `infra/Dockerfile.api`؛ خطأ migrations في `apps/api/alembic/env.py`؛ dependency outages في `core/database.py`, `core/errors.py`, `core/storage.py`؛ lifecycle جلسات الفيديو في auth/platform/auth_service؛ accessibility في AuthView؛ خصوصية logs في تكوينَي Nginx.
- **أدوات قابلة لإعادة التشغيل:** `infra/Dockerfile.qa`, `infra/qa/production.override.yml`, `scripts/qa/prepare-production.ps1`, `run-production.ps1`, `production-storage-drill.ps1`, `registry_probe.py`؛ `apps/api/scripts/s3_snapshot.py`, `storage_drill.py`, `verify_db_restore.py`, `qa_load.py`, `generate_qa_pdf.py`, `security_runtime_inventory.py`, `seed_qa.py`؛ `apps/web/scripts/generate-qa-video.mjs`، QA specs وconfig؛ runbook. لا تعتمد هذه الأدوات على scratch أو ملفات Downloads الشخصية.
- **Extract محفوظ دون كتابة فوق عمل الوكيل:** fixtures المشحونة + 13 blind structural cases و4 Word/image و20 contract و6 PDF/OCR و3 table و11 classification = **57/0/0** ضمن 155. هذه اختبارات هيكلية/تصنيف/OCR، وليست مراجعة بشرية تثبت كل كلمة أو معادلة؛ OCR يُعلَّم للمراجعة ولا نعلن كمالًا مطلقًا.
- **مرفوع إلى GitHub:** فقط الفرع عند `d70eea0…`. آخر `git ls-remote` Exit 0 يؤكد SHA نفسه، 0 commits محلية إضافية و0 staged. كل 52 modified و58 untracked محلية؛ لا نسبتها إلى GitHub ولا نسب كل التغييرات الموروثة إلى هذه الجولة.
- **اختُبر على Docker:** القالب نفسه مع overlay محدد، المخزن نفسه، local HTTPS، 155 API/26 browser/5 frontend-unit، faults/recovery، snapshot/restore/checksums/ملكية، وحمل متدرج. لا حذف لبيانات أو volumes الأصلية/المستعادة.
- **لم يُختبر على سيرفر خارجي:** شهادة عامة، ingress خارجي، موارد السيرفر، تسوية مالية حقيقية، SMTP إلى inbox خارجي، HA وoffsite backup. تبقى أربعة High مفروزة لكن دون patch Trixie متاح؛ **لا موافقة نشر، ولا push/merge/deploy**.

أدلة التشغيل: `.qa/production/commands-Tests.json`, `commands-Load.json`, `commands-Scan.json`, `api-tests.xml`, `browser-tests.xml`, `load.json`, `scout-api.sarif`, `scout-web.sarif`, `scout-s3.sarif`، snapshot النهائية `backups/s3/20260930T131235Z-409b5a55/manifest.json`، والأولى `backups/s3/20260930T122446Z-4ca6f5d9/manifest.json`. كلها artifacts محلية ignored، لا تُرفع مع الأسرار.
