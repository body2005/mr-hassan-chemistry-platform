# HANDOFF.md — حالة المشروع الموثقة
## هوية المشروع
- منصة LMS قائمة وناضجة: FastAPI + React/Vite + SQLite. ممنوع البدء من الصفر.
- المسارات: apps/api (venv في apps/api/.venv، Python 3.10) و apps/web فقط.
- المنافذ: API على 8000، خدمة AI اختيارية على 8001 (مطفأة — rag_synced=False سلوك صحيح).

## حقائق بيئة مثبتة
- openai-whisper 20250625، gTTS 2.5.4، pdfplumber، python-docx، python-pptx 
  مثبتة يدوياً في venv وغير مسجلة في requirements.txt.
- ffmpeg مثبت: Gyan.FFmpeg 8.0.1-full_build.
- video_transcriber.py يستدعي whisper عبر subprocess (أسطر 65-80).
- similarity_score = مطابقة كلمات محلية (matches/len(tokens، حد أقصى 0.98) 
  وليس vector RAG → يوثَّق كـ local text-matching grounding.

## الإنجازات الموثقة (تفاصيلها في AUDIT_REPORT.md)
- 21/21 اختبار قديم ناجح + npm run build ناجح.
- lesson.content محمي من الفهرسة. rag_synced مربوط بالاستدعاء الفعلي.
- ai_refusal_logs + endpoint شغالان. 
- transcript-first في توليد الكويز والاستشهادات.
- ffmpeg غير مفحوص سابقاً في smoke → الآن مثبت.

## المتبقي P0
1. requirements.txt: أضف openai-whisper, gTTS, pdfplumber, python-docx, python-pptx.
2. e2e_video_test.py: gTTS جملة عربية → mp4 عبر ffmpeg → upload → indexed 
   → اطبع transcript_text (أول 300 حرف كما خرج) → GET بـ Range: bytes=0-1023 
   (المطلوب 206؛ لو 200 → نفّذ StreamingResponse يدعم Range) → tutor استشهاد 
   من transcript الفيديو الحقيقي.
3. املا جدول الـ 5 ادعاءات الحرجة في AUDIT_REPORT.md بالدليل الحي.

## ميزة معلقة بعد الـ P0
مرفقات الدرس (PDF/DOCX/PPTX/TXT) + توليد كويز متحكم فيه + سجل وإلغاء 
الكويزات — المواصفات الكاملة عند المستخدم (اطلبها عند الوصول لكل مرحلة).

## القواعد الثابتة
عربي للتواصل/إنجليزي للكود. ممنوع Confirm. مخرجات كاملة مطبوعة كما خرجت. 
الفشل يُطبع بصدق. ممنوع ملفات خارج apps/api و apps/web.
