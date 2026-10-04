# منظومة الفيديو — تنفيذ محلي ومحددات التفعيل الخارجي

هذا المسار إضافة محلية غير مرفوعة، وليس إعلان جاهزية نشر. يُفعّل حاليًا
في مشروع QA فقط بإضافة `infra/video-pipeline.override.yml`. قالب الإنتاج
الأساسي يحتفظ بالتوافق مع الفيديوهات السابقة؛ لا تُفعّل الإضافة على سيرفر
قبل إغلاق اختبارات الاستعادة والحمل والثغرات وتوفير HTTPS حقيقي.

## المنفذ في الكود

1. API ينشئ intent دائمًا في PostgreSQL، بعد فحص المدرس/ملكية الدرس والحجم
   والنوع. الحد 5 GiB، وليس 20 GB. ثلاث جلسات نشطة لكل مالك، وجلسة لكل درس.
2. الواجهة ترفع أجزاء 32 MiB مباشرة إلى S3 عبر بوابة HTTPS مخصصة. الرابط
   صالح 300 ثانية وموقّع لجزء ورقم جلسة وحجم محدد. البوابة لا تسمح بالقراءة،
   أو listing أو admin أو completion. PostgreSQL وRedis وS3 نفسها غير منشورة.
3. الاستئناف مبني على S3 multipart وليس تطبيقًا لبروتوكول tus على السلك.
   API يستعلم عن الأجزاء الحقيقية. إغلاق الصفحة يحتاج اختيار نفس الملف
   بسبب قيود المتصفح؛ localStorage يحفظ الهوية والحالة فقط، لا الملف ولا الروابط.
   بصمة الحواف للتمييز عند إعادة الاختيار وليست checksum للملف الكامل.
4. completion قابل لإعادة المحاولة، يحفظ `completing` قبل تنفيذ S3، ويستعيد
   نجاح التخزين إذا ضاعت استجابة API. الأجزاء الناقصة/مختلفة الحجم تُرفض.
5. طابور PostgreSQL دائم، ومعالج منفصل محدود الموارد غير root. قفل advisory
   لكل job يمنع تنفيذ متزامن بين المعالجات. انقطاع Redis لا يفقد jobs؛ هذا
   الطابور مستقل عن Celery الموجود للإشعارات. إعادة معالجة crash محدودة بثلاث
   محاولات؛ الفشل ظاهر للمدرس ولا يدخل حلقة رفع أو إعادة طلبات غير محدودة.
6. FFprobe/FFmpeg يتحققان من المحتوى الفعلي؛ يمنعان بروتوكولات الإدخال الشبكية،
   وتُحذف الأسرار من بيئة عملية FFmpeg. سقف مدة المصدر أربع ساعات، ودقة
   7680×4320/33.2 MP و120 fps. حدود CPU/address-space والـcontainer ليست
   ضمانًا ضد كل ثغرة native؛ صورة المعالج تحتاج مسحًا مستقلًا.
   مخرجات المعالجة المحلية محدودة إلى 24 GiB، مع مراقبة المساحة أثناء
   الترميز؛ هذه ليست قدرة غير محدودة على معالجة محاضرات 4K الطويلة.
7. HLS H.264/AAC، مقاطع ست ثوانٍ، وسلم 360/480/720/1080/2160 عندما يسمح
   المصدر؛ لا upscaling. اختيار الجودة أصبح فعليًا وتلقائيًا في hls.js، بدل
   قائمة تجميلية لا تغير المصدر. WebM بلا Duration يُقاس من الناتج المفكوك.
8. الملف الأصلي يبقى خاصًا في `video-originals/` ببصمة SHA-256 كاملة محسوبة
   بتدفق محدود الذاكرة. مخرجات كل محاولة لها generation منفصل، وintent
   cleanup يسبق كتابة المخرجات. استبدال pointer وcleanup القديم يلتزمان
   معًا بعد نجاح الناتج والأصل؛ الفيديو السابق يبقى حتى ذلك الحين.
9. manifests وكل segment تعيد التحقق من الكوكي الحية والتوكن والاستحقاق
   والمالك/current generation، دون كشف URL للمخزن. روابط منسوخة إلى جلسة
   أخرى/مجهولة تُرفض. لا caching عام لمحتوى محمي في المسار المحلي.
10. إنهاء/إلغاء multipart وتنظيف staging المنتهي بعد 48 ساعة، مع cleanup outbox
    يتحمل تعطل المخزن. حذف درس يحتفظ بالسجل للتنظيف الآمن. توجد حالات job
    وerror codes وسجلات `video_id`، وتبقى telemetry المشغل الحالية قائمة.

## CDN وDRM — مزودان مختاران، غير مفعّلين

المزود المقترح للتوزيع **AWS CloudFront**، وDRM **Axinom** (Widevine/
PlayReady/FairPlay). لا حساب أو موارد أو مفاتيح أو مشتريات أُنشئت.

خطة التفعيل المطلوبة بعد تزويد الحسابات:

- hostname/CDN TLS ومصدر HTTPS خاص، لا كشف bucket أو فتح S3 admin.
- CloudFront trusted key group، cookies أو tokens قصيرة العمر محددة إلى
  asset/generation. CDN يجب أن يتحقق من الصلاحية حتى مع cache hit. الكوكي
  الموقعة وحدها لا توفر revocation الفوري الذي يوفره API الحالي؛ يجب تحديد
  سياسة edge authorization صريحة قبل التحويل إليه.
- Axinom packaging/CPIX + license service URLs وentitlement signing secret
  خارج Git. ترميز HLS الحالي **ليس CENC/DRM**؛ لا يكفي إضافة license URL
  لمشغل يعرض مقاطع غير مشفرة. Windows Widevine/PlayReady يحتاج DASH/EME؛
  FairPlay على Safari يحتاج HLS مشفرًا وشهادة مزود. يلزم encoder/packager
  وتكامل player مرخّص واختبار الأجهزة الحقيقي قبل التفعيل.
- callback/webhook خارجي، إن استُخدم، يحتاج توقيعًا يتحقق من raw body،
  timestamp/replay window، event-id idempotency وasset ownership. لم يُفتح
  endpoint يقبل `ready` من متصفح أو webhook غير موثوق. المعالج المحلي يكتب
  الحالة بنفسه بدل webhook ذاتية يمكن تزويرها.
- `VIDEO_DRM_REQUIRED=true` يفشل بصورة مغلقة للرفع ولإصدار روابط الطالب،
  ولا يبدّل إلى فيديو غير مشفر. لا تستخدمه قبل تركيب provider فعلي.

المراجع الأولية: [CloudFront signed cookies](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-signed-cookies.html)،
[Axinom DRM](https://docs.axinom.com/services/drm/)،
[player integration](https://docs.axinom.com/services/drm/quickstart/drm-only/integrate-player)،
[FFmpeg HLS](https://www.ffmpeg.org/ffmpeg-formats.html).

## دورة حياة التخزين

SeaweedFS الحالي ليس خدمة S3 Glacier؛ لا ندّعي أن تغيير `StorageClass`
يوفر أرشفة باردة فيه. التنظيف المنفذ يزيل multipart/staging المؤقت ومخرجات
الاستبدال والحذف، ويحافظ على الأصل الحالي. سياسة AWS المقترحة مستقبلًا:
abort-incomplete بعد يومين، ونقل **الأصول فقط** إلى Standard-IA بعد 30 يومًا
إذا كان نمط الاستخدام مناسبًا. لا تنقل HLS المنشور إلى archive يحتاج restore
قبل التشغيل. أرشفة المحتوى غير المنشور تتطلب موافقة واختبار restore وفهم
رسوم الطلب والحد الأدنى لمدة الاحتفاظ؛ لا تُفعّل حذفًا دوريًا تلقائيًا للأصل.

## تشغيل قابل للتكرار

على الجهاز الحالي، `.qa/audit2/compose.env` والأسرار والشهادة محلية ومهملة من Git:

الاختصار المحفوظ، مع تسجيل Exit Code لكل بوابة في `.qa`:

```powershell
pwsh -File scripts/qa/run-video.ps1 -Project chemistryaudit2 -Stage All
# المجموعة الكاملة للواجهة، ثم integration، بالتتابع وليس بالتوازي.
pwsh -File scripts/qa/run-video.ps1 -Project chemistryaudit2 -Stage Browser
pwsh -File scripts/qa/run-video.ps1 -Project chemistryaudit2 -Stage Integration
# إيقاف المعالج وحده، ثم hard crash أثناء encoding، مع فحص الاستعادة.
pwsh -File scripts/qa/run-video.ps1 -Project chemistryaudit2 -Stage Recovery
# 3 مراحل، كل منها 180 ثانية: 1 ثم 5 ثم 10 جلسات، HLS وPDF كبير.
pwsh -File scripts/qa/run-video.ps1 -Project chemistryaudit2 -Stage Load
# تحقق read-only من SHA-256 للأصول ووجود جميع المخرجات ورفض S3 anonymous.
pwsh -File scripts/qa/run-video.ps1 -Project chemistryaudit2 -Stage Assets
# بعد موافقة صريحة على مشاركة بيانات الصورة/SBOM فقط:
pwsh -File scripts/qa/run-video.ps1 -Project chemistryaudit2 -Stage Scan -ApproveScout
# لا تشغله بالتوازي مع المتصفح/integration/load: يوقف بيئة QA مؤقتًا.
pwsh -File scripts/qa/video-storage-drill.ps1 -Project chemistryaudit2
```

التفصيل المكافئ:

```powershell
$env:VIDEO_UPLOAD_PUBLIC_ENDPOINT='https://localhost:18544'
$dc=@('compose','--env-file','.qa/audit2/compose.env','-p','chemistryaudit2',
  '-f','infra/docker-compose.yml','-f','infra/qa/production.override.yml',
  '-f','infra/video-pipeline.override.yml')
docker @dc build api migration web
# ترتيب منفصل يضمن أن dependencies للمعالج والاختبارات من API الجديد.
docker @dc build video-worker qa-tests
docker @dc up -d --no-build migration s3-init api web proxy video-worker upload-gateway
docker @dc run --rm --no-deps -e STORAGE_DIR=/tmp/qa-storage qa-tests python -m pytest tests --ignore=tests/integration -q --junitxml=/qa/api-unit-video.xml
```

الواجهة `https://localhost:18543/` والبوابة upload-only `https://localhost:18544`.
لا تعتمد قبول شهادة QA ذاتية التوقيع على أنه اختبار شهادة خارجية. لتشغيل QA
من نسخة جديدة استخدم `scripts/qa/prepare-production.ps1` ثم خطوات البناء أعلاه
وإنتاج ملفات QA المشار إليها في runbook؛ استخدم بيانات اصطناعية فقط.

Playwright: اضبط `QA_BASE_URL`, `QA_LOCAL_TLS=true`, `QA_REDIS_CONTAINER`,
`QA_DOCKER`, `QA_VIDEO_FILE` و`QA_MEDIA_DIR` كما في runbook، ثم:

```powershell
npx playwright test --config playwright.qa.config.ts tests/qa/publication.spec.ts tests/qa/video-playback.spec.ts --reporter=list,junit
```

اختبار الاستئناف يحتاج هذه الإضافة فعليًا؛ لا يستثنيه الـharness للنجاح.
429/401/503 توقف محاولة الرفع/المتابعة مع زر استئناف صريح، لا retry storm.
المشغل يوقف أيضًا تحميل HLS عند 403 بدل التحول بين جودات غير مصرح بها.
بوابة Scan تفحص الصورتين حتى إذا فشل فحص الأولى، ثم تفشل إذا بقيت تنبيهات؛
لا تعني صلاحية ملف SARIF أن الصورة اجتازت بوابة الأمان.

`video-storage-drill.ps1` يحفظ جميع volumes، ويجمّد API/Celery/معالج الفيديو
وبوابة الرفع، ثم يعيد إنشاء SeaweedFS دون حذف volume. يستعيد snapshot إلى
المخزن الجديد مستخدمًا خدمة backup الإنتاجية نفسها على ID صورة API المختبَرة
(`run --pull never` دون `--build`)؛ لا يعيد بناء checkout أثناء عمل Extract. ثم يستخدم
**PG جديد + SeaweedFS جديد**، ويقارن كل جدول/صف قبل تشغيل التطبيق عليهما
فعليًا. يختبر الملفات والإيصال والفيديو القديم وHLS/Range/الصلاحيات، ثم يعيد
أيضًا رفع فيديو جديد وترميزه وتشغيله من المتصفح عبر بوابة ومعالج متصلين
بالمخزن المستعاد، ويعيد البيئة الأصلية في `finally`. لا تُستخدم هذه الإضافة على السيرفر.
في restore، إنشاء الجلسة وPUT الأجزاء ينفذه Playwright APIRequestContext عبر
HTTPS الحقيقي، ثم التشغيل/seek داخل Chromium. اختبار زر الرفع/الاستئناف
في واجهة المدرس نفسها ضمن `publication.spec.ts` على البيئة الأصلية؛ لا نخلط
بين نقل HTTP بالـharness وبين رفع الملف من input الواجهة.
Snapshot الكائنات لا ينقل أجزاء multipart غير المكتملة أو جلسات رفعها؛
استعادة الفيديوهات الجاهزة ليست إثباتًا لاستئناف تلك الجلسات بعد كارثة.
إذا فقد المخزن جلسة MPU، يعرض API الحالة `expired` ورمز
`VIDEO_UPLOAD_STORAGE_SESSION_LOST`؛ يعيد المستخدم اختيار الملف ويبدأ جلسة
جديدة. لا يستطيع هذا استعادة bytes مفقودة. أخطاء المخزن الأخرى تظل 503
ولا تُفسَّر على أنها فقد الجلسة. الاختبار `infra/qa/test-lost-multipart.py`
يحذف فقط MPU جديدة أنشأها للاختبار، ويتحقق من هذا المسار على PostgreSQL.

كل مرحلة في `run-video.ps1` تحفظ Exit Code بملف مؤرخ؛ `Browser` يحفظ JUnit
مؤرخًا أيضًا. `All` يعني build + unit/lint/build + اختبار النشر/الفيديو، ولا
يعني integration أو الحمل أو restore أو نجاح بوابة الثغرات. تُشغّل المراحل
المذكورة أعلاه منفصلة بالتتابع. ملفات `.qa` تتضمن جلسات/traces وبيانات محلية
مهملة من Git، وليست ضمن الملفات التي تُرفع.

أدوات تشخيص QA محفوظة أيضًا:

```powershell
# read-only: يقارن hashes ملفات Python داخل API والمعالج مع المصدر الحالي.
pwsh -File scripts/qa/verify-runtime-source.ps1
# chemistryaudit2 فقط: يفحص ملفات json-file الفعلية read-only، ويؤرشف
# السجلات التالفة قبل إعادة إنشاء الخدمات المتضررة بنفس الصور/volumes.
pwsh -File scripts/qa/repair-qa-log-corruption.ps1
```

لا تشغّل أداة إصلاح السجلات بجانب الحمل/fault/restore. تحفظ archive كاملًا
تحت `.qa` وقد يحتوي جلسات/روابط موقعة؛ لا ترفعه أو تعرض محتواه. اختلاف
source hashes لا يجيز الكتابة فوق عمل Extract الجاري أو إعادة بنائه دون
تنسيق. مطابقة hashes ليست بديلًا لاختبار جودة الاستخراج.

## حدود الادعاء

HLS والتوكن والكوكي يمنعون الوصول غير المصرح ومشاركة رابط دون جلسة؛ **لا
يمنعون مالك جلسة صالحة من استخراج المقاطع غير المشفرة عبر أدواته**. DRM
الحقيقي لم يُفعّل ولا يُختبر هنا، وحتى بعده لا يمكن ضمان منع تصوير الشاشة
أو الكاميرا أو جميع الأجهزة المخترقة. CDN/أرشفة باردة/مزود DRM/سيرفر خارجي
وحمل واقعي متعدد المستخدمين تبقى بوابات مستقلة، ولا يُستنتج دعم 1000 طالب.
