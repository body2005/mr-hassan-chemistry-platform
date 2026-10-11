# مراجعة واستكمال 11 أكتوبر — مصدر وإعدادات فقط

**لم تُشغّل اختبارات أو scanners أو build في هذه الجولة. لم يحدث نشر أو migration
أو تعديل Environment حي. لا اعتماد جاهزية إنتاج.**

البداية المحلية والبعيدة متطابقتان:
`b6f6320b91235e2172da0c661db4b4e95107cf7d` على `fix/queen-p0-handoff`.
هذا أحدث من `5844024` ويضيف حساب النسبة الكلية من أنواع التقييم ذات نتائج فعلية؛
الصفر الحقيقي يدخل المتوسط، النوع الغائب/غير المصحح لا يضيف وزنًا. لم يُعدّل
تاريخ Git ولا العمل غير المرتبط `pc_builder_3d_cases/`.

## جدول الطلبات الوظيفية السابقة

«أصلح في المصدر» يعني أن الربط قرئ في الكود، **ولا يعني أنه اجتاز اختبار تشغيل**.
كل صف أدناه غير متحقق منه بالتشغيل في الجولة الحالية. أرقام الصفوف هي أرقام
تقرير `PLATFORM_UPDATES_2026-10-11.md` السابق لتسهيل المطابقة.

| # | البند | الحالة والدليل المصدر وحدودها |
|---|---|---|
| 1 | bootstrap/refresh وتبديل الحساب | أصلح في المصدر سابقًا: apiClient ينتظر refresh واحدًا ويحمي auth generation؛ bootstrap لا يكتب هوية من جيل سابق. 503 لا يمسح الجلسة؛ refresh المرفوض 401 وحده ينظف cookies بالخادم. الآن فُصل refresh عن ميزانية محاولات login وربط حد الحساب بهوية مالك refresh الموثوق من DB. لا دليل حي لسبب كل 401 سابق. |
| 2 | Toast 5/10 ثوانٍ | المصدر: Map لمؤقتات مستقلة، dismiss/unmount/auth-change cleanup، أربع رسائل كحد أقصى وإغلاق واحد. الطويلة أكثر من 120 حرفًا أو متعددة السطور 10 ثوانٍ. |
| 3 | إخفاء الدرس حتى الجاهزية والموعد | lesson_release تُستخدم في catalog وstudent content entitlement قبل الفيديو/المرفقات/المناقشة/التقدم والتقييم. آخر VideoUpload غير ready يمنع الإتاحة؛ content/files لها سياسة مختلفة. سجلات DB لا تثبت أن الملف القديم ما زال موجودًا على filesystem. |
| 4 | جدولة الدرس وتعديلها وإلغاؤها | cairoTime يستخدم Africa/Cairo، API يرفض وقتًا دون timezone، DB UTC. PATCH لا يمس الملفات. الإشعار محفوظ وله dedup؛ cold start قد يؤخر إرسال الإشعار، بينما الإتاحة تفحص الموعد عند القراءة. |
| 5 | درس دون وحدة وMulti-select | Lesson.course_id مستقل؛ course_modules اختيارية، استعلامات المحتوى والتقارير تعتمد course_id. AssessmentScopePicker حقلان، و_apply_assessment_scope يستخدم dict.fromkeys ثم يتحقق من كل وحدة ودرس. أضيف منع إنشاء chapter في مقرر مدرس آخر. |
| 6 | رابط مشاركة ثابت | UUID لدرس/مقرر في hash فقط، sessionStorage يحفظ الوجهة قبل الدخول، التحقق من وصول الطالب في API. لا token أو URL S3 في رابط المشاركة. |
| 7 | المدة الفعلية والانتظار | API يرسل video_duration_seconds الذي يسجله encoder؛ UI يعرضه قبل metadata ثم يحدثه. المشغل ينتظر token ثم manifest ثم playlist/segments، وهي تبعيات حقيقية. لا انتظار ثابت 5 ثوانٍ في المصدر المقروء؛ زمن الشبكة/free cold start لم يُقَس. |
| 8 | تقديم/ترجيع الكيبورد | المصدر يحسب الانتقال الفعلي ويجمع ضغطات متتابعة ويفصل الاتجاهين، يتجنب input/editable ويحافظ على قيود الطالب. focus-visible أخضر. لم يُجرّب في المتصفح الآن. |
| 9 | SSE للتعليقات | commit قبل hint IDs فقط، مستلمون مصرح لهم، debounce 300ms/reconnect reload، drafts محفوظة وتنظيف الحساب/الدرس. لا SSE إضافي لكل نقاش. أُغلق الآن fallback محلي في الإنتاج عند غياب Redis. |
| 10 | زر ترتيب التعليقات | أزيل سابقًا، أحدث تعليق أولًا وردوده تحته. |
| 11 | الدرجة النهائية للمحاولة | ExamGradingModal يرسل attempt ID؛ calculated_score منفصل عن final_percentage/score والاعتماد له فاعل ووقت. المحاولة المعتمدة مقفلة ضد تعديل عابر؛ النتيجة الرسمية لا تأتي من تعديل السؤال العام. |
| 12 | إخفاء نتيجة المقالي حتى الاعتماد | quiz_results ينقح score/calculated_score/final_percentage قبل approval؛ solution API يعيد إجابة الطالب فقط ولا correct_answer/awarded/feedback قبل الاعتماد. practice منفصل، graded_at لازم حتى لو الدرجة صفر. |
| 13 | لون إلغاء الموعد | المصدر السابق: #762828 وأبيض وحد #B91C1C. |
| 14 | منطقة تفريغ الدروس | ألوان #9C1B28/#762828 وأبيض في ProfileView/ProfileModal؛ تأكيدات وصلاحيات الحذف محفوظة. لم يُنفذ حذف. |
| 15 | مربع الاعتماد الأكاديمي | أزيل من الملف الشخصي للغتين. |
| 16 | placeholder البريد واستعادته | حقل فارغ وplaceholder فقط وrequired/email؛ Resend عبر HTTPS دون redirect أو logging للرابط، والرد عام. يحتاج مرسلًا موثقًا وتسليمًا فعليًا غير مثبت. |
| 17 | وصف أيقونات التنقل | أزيل العرض الصغير من Sidebar المشترك. |
| 18 | الفيديو الخاص | الأصل/manifest/segments تفحص token وcookie الحية وعائلة الجلسة والاستحقاق والجيل الحالي وallowlist. عند تعطل Redis الآن قراءة الإبطال تفشل 503 ولا تعتمد على ذاكرة process. هذا ليس DRM. |
| 19 | أعطال الأدلة السابقة | إصلاح s3-init/OCR launcher السابق محفوظ؛ تنبيه السر غير محدد وnative HIGH وذاكرة S3 وreadiness ما زالت بلا إثبات إغلاق. أُعد CI history scan ولم يُشغّل. |
| 20 | حدود ونطاق العمل | الفيديو 5GiB والملفات 1GiB دون رفع حدود/TTL. لا تعديل parser/OCR/ملف الأحياء ولا إعادة AI أو الفهرسة. |
| 21 | الحفظ دون نشر | commit بعلامات skip ci/render/vercel؛ Vercel ignoreCommand الموجود يخرج 0 عند skip vercel. يُوثّق SHA ونتيجة التخطي بعد push في التسليم. |
| 22 | التسليم الصادق | هذا التقرير وملف RLS يميزان الكود من الإعداد الفعلي والتحقق؛ لا نتائج اختبار مصطنعة. |

## بقية الطلب الحالي

| البند | الحالة |
|---|---|
| Redis في readiness | أصلح في المصدر: إلزامي في deployment مهما كانت REDIS_REQUIRED، واسم الاعتماد محفوظ في جسم خطأ جاهزية structured. |
| Celery | أصلح في المصدر: default ingestion_backend=disabled لأن البحث في التطبيق لم يجد مهام ingestion أو dispatch بعد حذف الفهرسة؛ استخراج التقييم الحالي مباشر. disabled يظهر not_configured وليس ok. الاختيار الصريح celery يستمر يفحص broker/worker ويعطي 503 عند غيابهما. لا تشغيل Celery فارغ فقط لتلوين ready. |
| حفظ Render المؤقت | أصلح في المصدر: رفض كتابة ملفات نهائية إلى LocalStorageProvider في الإنتاج دون mount فعلي؛ اسم /var/data أو RENDER_DISK_PATH وحده لم يعد إثباتًا. هذا سيمنع الرفع بعد النشر إذا لم يجهز التخزين الدائم أولًا. |
| S3/R2 | أُعدت قوالب خارجية فقط، لم يُنشأ حساب/bucket/key ولم تُطبق. حساب الخدمة يحتاج bucket خاصًا وبيانات صحيحة. |
| معالج الكمبيوتر | ملف موجود؛ أضيف توجيه مفتاح منفصل محدود. يحتاج نفس DB/bucket وبقاء الكمبيوتر متصلًا ومساحة العمل؛ لم يُشغّل ولم يُربط. |
| ذاكرة S3 | أصلح عامل ضغط في المصدر: SDK ينقل جزءًا واحدًا دون threads داخل كل transfer؛ لا قراءة كامل الفيديو في RAM. هذا **لا يثبت** حل تجاوز ذاكرة خدمة S3 في حمل عشر جلسات. |
| ملفات كبيرة وحجوزات | أصلح في المصدر: لا fallback admission محلي في الإنتاج؛ تجديد الـlease وفشلها يلغيان العمل، دون تغيير 120s/30s. ميزانية spool/staging المشتركة تشمل receipt/assignment/extraction إضافة للفيديو والملفات. نقل الإيصال غير متزامن مع shield وتنظيف/تعويض عند الإلغاء. |
| Rate Limiting | أصلح في المصدر، إعداد proxy الفعلي يحتاج حسمًا؛ التفاصيل أدناه. |
| صلاحيات التطبيق | حماية سابقة في report tenant/requested_by، teacher-course scope في grades/mastery، owner scopes في التقييم/التسليم/الدفع/الملفات. الآن chapter يتحقق من teacher_id، وإنشاء سؤال لا يقبل ربطه بمقرر مؤسسة أخرى حتى عبر مسار الإدارة. الاستثناءات العالمية الصريحة لـPLATFORM_ADMIN باقية وتحتاج قرارًا عند تصميم RLS. |
| RLS | أُعدت مسودة جزئية وسياق اختياري، غير مفعّلة وغير متوافقة مع كل workers/public/auth بعد. لا دليل على pg_roles/pg_policies الحية. |
| Secrets Control | أصلح تحكمًا بالمصدر/CI، لكن الاكتشاف القديم نفسه غير مغلق وغير معروف الموضع. |
| native HIGH | غير متحقق منه؛ لا تحديث أعمى ولا تغيير شدة/اسم إصدار. الملفات القديمة التي قُرئت لا تعطي إصدار إصلاحًا قابلاً للاعتماد. |
| DRM | خطة فقط، يحتاج مزود ترخيص/packager ومشغل EME. لا شراء ولا ادعاء منع تسجيل الشاشة. |
| النشر/الـmigration | خطة فقط. f8d0 مطبقة سابقًا حسب logs النشر المأذون، وليس في هذه الجولة. لا migration جديدة لهذه الإصلاحات. |

## Rate Limiting — الدليل وحدوده

`core/rate_limit.py` يستخدم sliding-window Lua atomic على Redis مشترك ووقت Redis
نفسه بدل ساعة كل API. المفاتيح للمستخدم المؤسسة+sub عند credential موقّع صالح؛
Bearer له الأولوية مثل المصادقة. حسابات الدخول/الاستعادة HMAC وليست بريدًا/رمزًا
مكشوفًا في Redis. فشل استعلام Redis يدخل cooldown و503، لا fallback إنتاج محلي.

| المسارات | التغطية المقروءة |
|---|---|
| login | IP + المؤسسة/هوية الحساب + الزوج القصير، قبل فحص كلمة المرور. |
| register | IP مستقل وهوية حساب مستقلة أضيفا مع حد auth القائم. |
| reset request/confirm | IP مستقل + account أو opaque token HMAC؛ رد طلب الاستعادة لا يكشف وجود الحساب. |
| refresh/logout | فصل تصنيفهما عن login؛ refresh محدود IP وبمالك session الموثوق بعد قراءة hash من DB. |
| GET/HEAD بما فيها المحتوى وtoken/SSE | read؛ stream وHLS يتفحصان صلاحياتهما وعدادات التزامن مستقلة للفيديو وSSE. |
| video/material/receipt/assignment file POST | upload؛ middleware يمنع parsing قبل تحقق الهوية، ثم حدود جسم وlease عالمي. Multipart control له حدود إنشاء وقراءة مستقلة. |
| quiz extract/exam | quiz_extraction وguard ثقيل؛ لم يغيّر parser أو نصه. |
| users/submissions/analytics/payment orders/reports | heavy_query؛ reports أضيفت للتصنيف الثقيل بدل read العام، وللتقرير الملخص حد إضافي 10/دقيقة. |
| باقي mutations | mutation/default بجانب صلاحيات المسار. health/ready مستثنيان من limiter، وفحص ready مجمع بمهمة واحدة وكاش قصير. |

429 وRetry-After محفوظان، وأضيف expose لـRetry-After في CORS للواجهات cross-origin.
apiClient يعيد محاولة واحدة بعد refresh فقط؛ HLS auto retries معطلة عند الفشل،
وSSE reconnect محدود بعدد محاولات وbackoff. لا تغيير limits عام لإخفاء 429.

الإعداد الحي: اسما REDIS_URL وREDIS_REQUIRED موجودان؛ لم تقرأ قيمهما أو تختبر
اتصال Redis. TRUSTED_PROXIES غير موجود ضمن أسماء Environment المقروءة. المصدر
يفحص proxy peer قبل XFF ويرفض wildcard، لكن Uvicorn الحي قد يعيد كتابة peer
بإعداداته الافتراضية قبل وصول التطبيق؛ سجلات قديمة تُظهر remote IP:0. لا يمكن
تأكيد سلسلة الثقة أو عزل IP حيًا دون معرفة proxy topology. جهّز CIDRs الفعلية
من Render/Vercel/بوابة الرفع؛ لا تخمّنها ولا تستخدم `*` أو كامل private network.
استخدم طبقة واحدة لفك XFF: `--no-proxy-headers` مع peer CIDRs موثقة في التطبيق،
أو إعداد Uvicorn موثق يمنع إعادة فك السلسلة في التطبيق. لا تغيير حي الآن.
المستخدمون الموثقون لهم عدادات مختلفة؛ الضيوف خلف IP واحد يظلون يتشاركون حد IP.

Blueprint غُيّر إلى noeviction كي لا تُطرد حجوزات/إبطال جلسات بسبب LRU. إعداد
Valkey الحي لم يُقرأ أو يُغيّر؛ إصلاح Blueprint لا يطبّق نفسه على الخدمة القائمة.

## RLS — الدليل وحدوده

راجع `RLS_ROLLOUT_2026-10-11.md`. لا يوجد ENABLE RLS في migrations المقروءة، ولا
توجد معرفة موثقة بدور PostgreSQL الحي. السياسات المقترحة tenant barrier وليست
تفويض المدرس/الطالب داخل المؤسسة. لا تمنح المستخدم DB credentials. worker
dispatcher/auth bootstrap/public catalog وmedia context تحتاج استكمالًا قبل التفعيل.

## Secrets Control — الدليل وحدوده

السجل الموجود `.qa/release1011-secrets-ci.log` من run 38030511325 يعرض فقط
`leaks found: 1`؛ ليس فيه File/Line/RuleID يتيح تحديد الاكتشاف. لم يُجرَ scanner
بديل ولا أُضيف ignore. لا يمكن نسبته لملف معين أو القول إنه false positive.
يلزم لاحقًا، بإذن تشغيل، scan redacted يخرج metadata/موضع الاكتشاف فقط؛ فرّق
بين القيمة المسربة وfingerprint/موضعها. إن ثبت سر فعلي: سجّل مزوده/نطاقه، جهّز
مفتاحًا بديلًا بنفس أو أقل صلاحيات، انقله إلى API/worker خارج Git، تحقق من
الانتقال بإذن، ثم ألغِ القديم عند المزود. لا تطبع القيم، ولا تعيد كتابة التاريخ
أو force-push في هذه الجولة. حذف أحدث سطر لا يبطل السر أو يمحو تاريخ Git.

CI المجهز يفحص checkout وتاريخ Git المجلوب كخطوتين مستقلتين، full-depth مع
redact/verbose وexit 1، دون رفع secret reports. لم يُشغّل. التاريخ غير المجلوب
أو commits المحذوفة من كل refs لا يدّعي الفحص تغطيتها. مصدر frontend يستخدم
VITE_API_URL فقط؛ لا S3/mail/DB keys فيه ضمن البحث المقروء. لم يُبنَ bundle جديد
ولا يُعتمد عدم تسرب كل متغير على Vercel؛ قيم إعداداتها لم تقرأ.

أُزيل تضمين exception/traceback الخام من أخطاء الطلب العامة ومسار presign/reset
rate-limit helper؛ توسع access-log redaction لرموز reset/refresh وAWS signatures/
credentials/security tokens. logging الموجود داخل parser/OCR لم يُمس طبقًا
لمنع المستخدم؛ ما زال يحتاج مراجعة خصوصية منفصلة عند السماح بهذا النطاق.

native: تقرير سابق سجّل 63/79 HIGH لـAPI/encoder. SARIF الموجود بتاريخ 9 أكتوبر
الذي قُرئ هنا يذكر Expat/zlib وfixed_version='not fixed'؛ هذا سجل تاريخي وليس
دليل غياب إصلاح اليوم. لا نسخة إصلاح موثقة من الأدلة المتاحة لهذا التغيير، لذلك
لم يُزعم إغلاقها ولم تُعدّل severity أو provenance. Docker النهائي يزيل build
tools بالفعل؛ Render Native Python لا يستخدم هذه الصورة أصلًا.

## إعداد الاستضافة الفعلي المقروء

Render `srv-dahtu7h42hec73agru80`: Native Python / Free، root apps/api، build
requirements.txt، start migrations ثم seed ثم uvicorn، Health Check Path فارغ.
آخر Live في بداية المراجعة b6f6320، deploy dep-db5i3n0u01pc73embn00. شاشة Render
تنبه إلى cold start قدره 50 ثانية أو أكثر؛ لم يُقَس تشغيل فيديو في هذه الجولة.

قُرئت **أسماء** Environment فقط دون قيم: REDIS_URL/REDIS_REQUIRED وEMAIL_ENABLED/
EMAIL_PROVIDER/EMAIL_FROM_EMAIL/RESEND_API_KEY موجودة. أسماء STORAGE_BACKEND وS3_*
وVIDEO_PROCESSING_ENABLED وVIDEO_DIRECT_UPLOAD_ENABLED وVIDEO_UPLOAD_PUBLIC_ENDPOINT
وTRUSTED_PROXIES وINGESTION_BACKEND وCELERY_BROKER_URL غير موجودة ضمن القائمة.
لذلك defaults في المصدر مهمة: local storage وCelery القديم يفسران مسارات فشل
محتملة، ولا يثبتان سبب استجابة ready بعينها دون dependency details في السجل.
اسم INITIAL_TEACHER_EMAIL مكتوب NITIAL_TEACHER_EMAIL؛ السجل يقول seed skipped.
لم يُصحح حيًا لأن تغيير البيئة قد يبدأ نشرًا، ولم تعَد كلمات مرور أي حساب.

Vercel الإنتاج b6f6320، deployment 4Uw5ZAGCXRkQasbJBPPmPosZaLkm، root apps/web.
Vercel Ready هو نجاح نشر سابق، وليس اعتمادًا لصحة التغييرات الجديدة.

## تجهيز التخزين والمعالج والبريد

1. ينشئ المالك حساب S3/R2 وbucket **خاصًا**. امنع public ACL/policy وR2 public
   domain، ولا تمنح frontend مفتاحًا. القوالب s3-*-policy.json.example للـAPI
   ولـencoder بمفتاحين منفصلين، بدون إدارة bucket أو IAM أو '*' لكل الخدمات.
   القوالب AWS IAM؛ R2 token permissions تضبط وفق إمكانات المزود/bucket scope
   ولا يُدّعى أن صياغة IAM تعمل تلقائيًا في R2. تخزين قديم خارج prefixes يحتاج
   جردًا ونقلًا مدروسًا وصلاحيات مؤقتة محددة، لا توسيعًا عامًا.
2. CORS: PUT من production alias فقط مع ETag؛ previews المصرح بها تضاف صراحة
   عند الحاجة. CORS لا تمنح صلاحية قراءة. Lifecycle يوقف multipart المهجور بعد
   7 أيام دون حذف ملفات نهائية، مع استمرار durable outbox و48 ساعة لتطبيق الرفع.
3. `infra/render-native.env.example` يحدد الأسماء والقيم التي يجب توفيرها؛
   REPLACE_* وصف للمتطلب وليس بيانات وهمية صالحة للنشر. أعط API ونفس bucket
   للمعالج مع DATABASE_URL الخارجي الصحيح TLS. جهّز gateway HTTPS للرفع المباشر
   الموجود في infra/video-upload.conf.template قبل تمكين direct uploads.
4. encoder يقرأ PostgreSQL queue ولا يستعمل Celery. Celery skeleton/Blueprint
   worker القديم غير مطلوب لوظائف المنتج الحالية بعد حذف ingestion؛ لا تشغله
   لتجاوز ready. لا تعِد الفهرسة/AI، ولا تطبق Blueprint كاملًا على الخدمات الحية.
5. Resend: إرسال HTTPS موجود، لكن verified sender/domain وحالة sending key
   وتسليم الرسائل غير مثبتة. لا تستخدم noreply@yourdomain.com غير المملوك كقيمة.
   لا حاجة لإضافة SMS أو automation خارجي لتوليد الأكواد.

## حماية الفيديو وDRM

الملفات النهائية خاصة ومسارات Range/HLS محمية بالجهاز صاحب الجلسة والاستحقاق
والـtoken قصير العمر. allowlist تمنع arbitrary paths، والـmanifest بحجم محدود
1MiB والـsegments تُبث 64KiB، لا تحميل فيديو كامل في RAM في المسار المقروء.
لكن المستخدم المصرح له يستقبل الفيديو في جهازه وقد تلتقطه الإضافات أو التسجيل.
إخفاء زر/Content-Disposition ليس DRM ولا ضمان منع Download Manager.

دمج DRM يحتاج مزودًا يغلّف MPEG-CENC/DASH وFairPlay HLS، معرف asset/KID فقط في
DB، مفاتيح content عند packager/KMS خارج API/frontend، license endpoint يتحقق
من نفس الجلسة/الاستحقاق/المؤسسة/الجهاز قبل الترخيص قصير العمر، ومشغل EME مع
Widevine/FairPlay/PlayReady حسب المتصفح. لا public original أو fallback واضح عند
رفض DRM. يلزم تقييم التوافق والتكلفة وإذن قبل شراء/تفعيل؛ لا منع تسجيل شاشة100%.

## خطة نشر منسقة لاحقًا — لا تنفيذ الآن

1. حل الأسرار/native HIGH/التخزين/proxy والـworker وإتاحة تحقق تشغيل مأذون أولًا.
   جرد الملفات المحلية ونسخ الأصل المتاحة؛ تغيير backend وحده لا ينقلها.
2. نسخة PostgreSQL حديثة بصيغة custom باستخدام عميل متوافق مع الخادم، ونسخة
   ملفات ومرفقات/إيصالات محفوظة ومشفرة خارج Git، مع خطوات restore مخطط لها.
   Free Render لا يوفر Recovery Export في اللوحة التي قُرئت سابقًا؛ الملف المحلي
   القديم ليس backup حديثًا. لا توجد نسخة احتياطية أُنشئت بهذه الجولة.
3. f7c9e1a3b5d7 وf8d0a2c4e6b8 طُبّقتا في نشر 5844024 المأذون سابقًا حسب logs؛
   لا تطبقهما يدويًا ثانية الآن. في النشر التالي راجع alembic_version والـheads
   على النسخة المستهدفة بعد إذن؛ النسخة الجديدة لا تضيف migration.
4. أوقف auto-deploy أثناء التنسيق، وحافظ على schema additive. إعداد S3/نقل الملفات
   ثم API + encoder على نفس schema/store، بعدها واجهة Vercel المطابقة. لا تنشر
   تغييرات RLS كتَبَعية لهذه الدفعة؛ لها rollout مستقل بعد شروط وثيقتها.
5. native start الحالي يجري migrations في كل start؛ لا تعتمد ذلك لإجراء DDL
   متزامن من replicas متعددة. استخدم خطوة migration واحدة مخططة بعد backup،
   ثم start للخدمة؛ لا تغيير Dashboard الآن. اضبط healthCheckPath=/api/v1/ready
   بعد اكتمال الاعتمادات، دون جعل الفحص ينجح شكليًا.
6. rollback: أعد API/web السابقين المتوافقين مع schema additive واحتفظ بـS3
   والمفاتيح المتوافقة؛ لا downgrade تدميري. f8d0 downgrade يرفض دروسًا بلا وحدة
   عمدًا. عند تلف بيانات توقف الكتابة ثم استعد backup موثقًا بإذن، لا restore
   أعمى فوق معاملات جديدة. جهّز استعادة المعالج وإعدادات النشر/البريد أيضًا.

التخطي لهذه الدفعة يستخدم [skip render] الموثق في
[Render](https://render.com/docs/deploys#skipping-an-auto-deploy)، وignoreCommand
الموجود في [Vercel](https://vercel.com/docs/project-configuration/vercel-json#ignorecommand)
مع [skip vercel]، و[skip ci]. لا تشغيل يدوي لأي deploy أو QA.

## الملفات المتغيرة في هذه الجولة

| الملف أو المجموعة | الغرض |
|---|---|
| core/rate_limit.py | وقت Redis، أولوية credential، cooldown وسجل دون traceback. |
| main.py | فصل refresh/logout، تصنيف assignment uploads/reports، expose Retry-After وسجل خطأ آمن. |
| api/routes/auth.py | حدود IP/حساب للتسجيل والاستعادة، فصل refresh وربطه بمالك موثوق. |
| core/leases.py وcore/events.py | منع fallback لكل process في الإنتاج. |
| api/routes/platform.py | فيديو يفشل مغلقًا عند غياب Redis بدل markers محلية؛ logout يحتفظ بالإبطال الدائم في DB. |
| api/routes/health.py وcore/errors.py | إزالة اعتماد ingestion المحذوف، Redis إلزامي، إخفاق DB مسمى وجسم dependencies قابل للقراءة. |
| core/storage.py | multipart مفرد ورفض كتابة إنتاج مؤقتة والتحقق من mount وسجل presign. |
| core/upload_limits.py وapi/routes/payments.py | ميزانية موارد لكل file endpoints، إيصال off-loop وتنظيف cancellation. |
| services/extended_service.py | منع مدرس من إنشاء chapter في مقرر لا يملكه. |
| services/platform_service.py | منع ربط سؤال بمقرر مؤسسة أخرى. |
| core/rls_context.py وapi/dependencies.py وcore/database.py | سياق هوية معاملات opt-in وتنظيفه، دون تفعيل سياسات. |
| infra/rls-review.sql.example وinfra/rls-status.sql.example | مسودة سياسة وقراءة metadata غير منفذتين. |
| infra/s3-api-policy.json.example وs3-video-worker-policy.json.example | مفاتيح API/encoder منفصلة بنطاق bucket/prefix. |
| infra/s3-cors.json.example وs3-lifecycle.json.example | تجهيز PUT/CORS ووقف multipart المهجور فقط. |
| infra/render-native.env.example وvideo-worker.pc.env.example | إعدادات الخدمة الفعلية المطلوبة وتوجيه مفتاح encoder منفصل. |
| render.yaml | noeviction مقترح لـValkey؛ لا يغيّر الخدمة الحالية. |
| .github/workflows/quality.yml | تجهيز history scan redacted مستقل، دون تشغيل أو رفع secret artifacts. |
| وثيقتا المراجعة وRLS الجديدتان | مصفوفة البنود والقيود وخطة الإعداد والنشر والـrollback. |

القائمة التقنية الدقيقة في `git show --name-only <SHA النهائي>`. جميع المسارات
المختصرة في الجدول نسبية إلى apps/api/app ما لم تبدأ infra أو docs أو .github.
