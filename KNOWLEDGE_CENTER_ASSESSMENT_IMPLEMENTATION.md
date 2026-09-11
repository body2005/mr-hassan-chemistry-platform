# Knowledge Center and Assessment Isolation Implementation

This project now treats uploaded educational documents as the retrievable source of truth for AI interactions, and separates teacher AI workflows from student assessment runtime.

## Implemented

- Knowledge sources support `KNOWLEDGE`, `ASSESSMENT`, and `ANSWER_KEY` roles.
- Document ingestion stores source structure, provenance, and embeddings for hybrid lexical plus vector retrieval.
- Exam/worksheet/test uploads in document formats are parsed into extracted question records, then materialized into canonical `AssessmentQuestion` rows.
- Answer resolution records whether an answer came from the assessment text, answer key, teacher edit, or Knowledge Center retrieval.
- Missing or conflicting answers are marked `needs_review` instead of guessed.
- Teachers can inspect, edit, link answer keys, and approve extracted assessment questions into the platform question bank.
- Students are denied AI access during active quiz or assignment attempts by server-side policy.
- Denied AI access is audited with generic metadata and no answer leakage.
- The Knowledge Center UI supports assessment upload type, answer key upload/selection, review, save, and approval.
- Batch upload accepts up to 25 books in one request and starts an independent indexing job for each source.
- Every parsed book now has a persisted source-scoped outline (`book → unit → lesson → topic`). Text units, extracted questions, and visual assets are linked to the most specific outline node and retain page ranges.
- Standalone JPG/PNG files and original images extracted from PDF/DOCX/PPTX are preserved as assets. Their Arabic/English OCR text is stored with the asset and made available to multimodal retrieval.
- PDF image extraction uses PyMuPDF when installed; scanned-page fallback remains bilingual Tesseract. PaddleOCR is optional and only used when explicitly enabled.
- Image analysis has a safe local OCR fallback and an optional OpenAI-compatible VLM adapter. The VLM receives an instruction-isolated prompt and returns Pydantic-validated JSON only.
- A course-scoped knowledge graph stores concepts plus evidence-bearing links to units, questions, and images. Graph edges are source-version aware.
- Retrieval combines BM25, local embeddings, optional Qdrant vector search, and an optional cross-encoder reranker. It supports source and outline filters, visual units, page citations, and hybrid evidence scoring.
- Answers use strict grounding, response/semantic cache keys that include the active source editions, contradiction refusal, confidence telemetry, and source/page/unit/lesson citations.
- New editions sharing a filename or explicit `document_key` automatically supersede the prior current edition for retrieval while preserving the prior source for audit.
- Conversation turns are stored separately from the knowledge base and follow-up questions are rewritten only with the caller's recent course session context.
- Question generation now supports short-answer, source-numerical, and image-linked questions in addition to MCQ, true/false, essay, and fill-in-the-blank. Source numerical questions never fabricate operands or answers.
- Optional Celery processing can move ingestion/re-indexing to a Celery + Redis worker. Query analytics exposes outcomes, frequent outlines, and unanswered questions.
- Instruction-like lines are stripped from indexed retrieval text only; the original upload remains untouched.
- Extracted questions now have a stable source order and hierarchy metadata (`unit`, `lesson`, `topic`, page/slide) plus a separate verified `Question → Image` relation. Page co-location alone is not sufficient to attach an image.
- The quiz preview renders every verified linked image from the Knowledge Center asset endpoint. When an extracted assessment is approved into the platform question bank, its verified image IDs are retained on the resulting question.
- Source-scoped lesson relations store `previous`, `next`, `builds_on`, and defensible `same_topic` links. Question generation and search can optionally include only trusted prerequisite/previous outline nodes; unrelated lessons are not mixed in.

## Migration

Run:

```bash
cd apps/api
alembic upgrade head
```

## Optional Embedding Provider

By default, deterministic local hash embeddings are used so tests and local development work without secrets. To use an external embedding service:

```bash
EMBEDDING_ENDPOINT=https://your-provider/embeddings
EMBEDDING_API_KEY=...
```

## Optional OCR configuration

Install the Tesseract Arabic and English language packs for the default OCR path.
To use PaddleOCR for images in a deployment where it is installed, set:

```bash
PADDLE_OCR_ENABLED=true
IMAGE_OCR_MAX_PER_PAGE=12
```

The original uploaded file is never modified by OCR or indexing.

## Optional production integrations

All of these integrations are opt-in. Without them the application continues to use its local, deterministic fallbacks.

```bash
# VLM: an OpenAI-compatible multimodal chat endpoint
VLM_ENDPOINT=https://your-provider/v1/chat/completions
VLM_API_KEY=...
VLM_MODEL=...

# Qdrant vector storage (otherwise JSON/local embedding similarity is used)
QDRANT_URL=https://your-qdrant
QDRANT_API_KEY=...
QDRANT_COLLECTION=knowledge_units

# Optional reranker endpoint accepting {query, documents}
RERANKER_ENDPOINT=https://your-reranker/rerank
RERANKER_API_KEY=...

# Background ingestion worker
USE_CELERY_INGESTION=true
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1
```

Start the optional worker with:

```bash
cd apps/api
celery -A app.tasks.celery_app.celery_app worker --loglevel=INFO
```

## Verification

Backend:

```bash
cd apps/api
uv sync --extra dev
.venv/bin/pytest -q
```

Frontend:

```bash
cd apps/web
npm install
npm run build
```
