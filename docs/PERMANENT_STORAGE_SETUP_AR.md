# تفعيل التخزين الدائم للفيديوهات والمرفقات

الربط البرمجي يدعم S3 وCloudflare R2. لم يُفعّل حساب تخزين حي بعد؛ تغيير الإعدادات لا يسترجع الملفات التي حُذفت من قرص Render المؤقت. بعد نجاح الربط أعد رفع الملفات الأصلية من إدارة الدروس.

## المطلوب منك مرة واحدة

1. أنشئ حساب Cloudflare وفعّل R2، ثم أنشئ bucket خاصًا مثل `chemistry-media`. اترك Public Development URL وCustom Domain غير مفعّلين.
2. من R2 API Tokens أنشئ صلاحية **Object Read & Write** لهذا الـbucket فقط. احتفظ بـ **Access Key ID** و**Secret Access Key** و**S3 API endpoint**. هذه بيانات S3 وليست Cloudflare Global API Key.
3. أدخل القيم في Environment لخدمة API على Render باستخدام أسماء الملف [render-storage.env.example](../infra/render-storage.env.example). لا تضعها في Vercel أو في أي متغير `VITE_*`، ولا ترسلها في المحادثة أو تحفظها في Git.

| المتغير | القيمة |
| --- | --- |
| `STORAGE_BACKEND` | `s3` |
| `S3_ENDPOINT_URL` | عنوان S3 API الذي يعرضه R2، دون اسم bucket في آخره |
| `S3_BUCKET_NAME` | اسم bucket |
| `S3_ACCESS_KEY_ID` | Access Key ID |
| `S3_SECRET_ACCESS_KEY` | Secret Access Key |
| `S3_REGION` | `auto` |

المصدر الرسمي لإنشاء بيانات الاتصال: [Cloudflare R2 S3 setup](https://developers.cloudflare.com/r2/get-started/s3/).

## التحقق والتفعيل

بعد إدخال القيم في Render، شغّل من Shell الخدمة داخل `apps/api` (أو مجلد الخدمة الحالي):

```sh
python -m scripts.storage_preflight
```

الفحص يكتب ويقرأ ويحذف ملف اختبار صغيرًا باسم فريد. لا يعرض القيم السرية ولا يلمس ملفات الدروس. المطلوب ظهور `Private object storage read/write/delete: OK`، ثم إعادة نشر الخدمة لتقرأ المتغيرات الجديدة. إذا لم تتوفر Shell، يمكن تشغيل نفس الفحص محليًا بمتغيرات البيئة نفسها.

ارفع فيديو ومرفقًا جديدين من المنصة، اختبر التشغيل والتنزيل من حساب طالب مخوّل، ثم أعد نشر Render واختبرهما مجددًا. هذا الاختبار يثبت بقاء الملفات بعد النشر؛ لا يكفي ظهور بيانات الدرس في قاعدة البيانات.

## تجهيز الجودات على جهازك

التخزين الدائم مستقل عن معالجة الفيديو. يبقى `VIDEO_PROCESSING_ENABLED=false` و`VIDEO_DIRECT_UPLOAD_ENABLED=false` حتى تشغيل المعالج بنجاح.

1. جهّز Docker Desktop بمحرك Linux.
2. شغّل `scripts/start-video-worker.ps1 -BuildOnly` لبناء المعالج وإنشاء `.env.video-worker.local` الخاص والمستبعد من Git.
3. أكمل الملف بقيم التخزين نفسه، وبيانات PostgreSQL الخارجية من Render مع `sslmode=require`، وبيانات الدفع العامة المطلوبة في النموذج. يفضّل مفتاح منفصل للمعالج؛ لا تنسخ مفتاح جلسات API أو البريد.
4. شغّل `scripts/start-video-worker.ps1 -CheckOnly` ثم السكربت دون خيارات. الفحص يتأكد من التخزين وقاعدة البيانات وFFmpeg والمساحة قبل التشغيل.
5. بعد نجاح تشغيل المعالج فعّل `VIDEO_PROCESSING_ENABLED=true` على Render. اترك الرفع المباشر معطّلًا ما لم تُجهّز إعداداته وCORS منفصلة.

الجهاز وDocker يحتاجان البقاء شغّالين لمعالجة فيديوهات جديدة. بعد اكتمال المعالجة، التشغيل يعتمد على Render والتخزين الدائم؛ إيقاف الجهاز يوقف تجهيز الفيديوهات الجديدة. خيارات الجودة تُعرض من النسخ التي أُنتجت فعليًا حتى دقة المصدر وحدّ 1080p.

الـbucket الخاص والتوثيق يقللان مشاركة الروابط، لكن منع تنزيل فيديو قابل للمشاهدة منعًا مطلقًا ليس ضمانًا يقدمه هذا الربط.
