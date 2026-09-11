"""
=============================================================================
ZERO-HALLUCINATION GROUNDED ANSWER ENGINE & DEDUCTION VERIFIER
=============================================================================
Strict RAG synthesis, deduction, and verification layer:
1. Grounded answer generation and scientific deduction using ONLY retrieved evidence.
2. Refusal when evidence is insufficient: "يجب أن يكون السؤال في إطار المادة."
3. Automated verification layer (SUPPORTED / PARTIALLY_SUPPORTED / UNSUPPORTED).
4. Validation of page citations, numerical values, and chemical formulas.
=============================================================================
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
import urllib.request
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from app.services.chemistry_normalizer import (
    extract_chemical_formulas,
    expand_chemistry_synonyms,
)

if TYPE_CHECKING:
    from app.services.knowledge_retriever import KnowledgeSearchResult


logger = logging.getLogger(__name__)

STRICT_REFUSAL_MESSAGE = "يجب أن يكون السؤال في إطار المادة."
INSUFFICIENT_EVIDENCE_MESSAGE = "يجب أن يكون السؤال في إطار المادة."


@dataclass
class VerificationResult:
    verdict: str  # SUPPORTED, PARTIALLY_SUPPORTED, UNSUPPORTED
    is_valid: bool
    confidence: float
    violations: list[str] = field(default_factory=list)
    citations_verified: bool = True


def generate_llm_grounded_answer(
    question: str,
    evidence_items: list[KnowledgeSearchResult],
) -> str | None:
    """
    Invokes Gemini / LLM to perform scientific deduction and synthesis across retrieved course evidence.
    Returns synthesized answer or None on failure.
    """
    gemini_key = os.getenv("GEMINI_API_KEY")
    qa_model = os.getenv("QA_MODEL", "gemini-2.5-flash")

    evidence_texts = []
    for item in evidence_items[:18]:
        cit = item.citation_text
        page_info = f"صفحة {item.page_number}" if item.page_number else ""
        header = f"[{cit} - {page_info}]" if page_info else f"[{cit}]"
        stmt = item.statement.strip()
        details = (item.details or "").strip()
        content = stmt
        if details and details != stmt and len(details) > len(stmt):
            content = f"{stmt}\n{details}"
        evidence_texts.append(f"{header}:\n{content}")
    combined_evidence = "\n\n".join(evidence_texts)

    prompt = (
        "أنت المعلم الخبير والمساعد التعليمي الذكي للمقرر الدراسي.\n"
        "مهمتك: مساعدة الطالب وتقديم شرح تعليمي مبسط، وافٍ، وممتع، معتمداً بصورة كلية وحصرية على مصادر المقرر المرفقة أدناه.\n\n"
        "=== مصادر المقرر المسترجعة ===\n"
        f"{combined_evidence}\n\n"
        "=== سؤال الطالب ===\n"
        f"{question}\n\n"
        "=== منهجية الإجابة وأسلوب العرض ===\n"
        "1. التبسيط والشرح التعليمي المتدرج (Pedagogical Explanation):\n"
        "   - اشرح للطالب بطريقة سهلة وميسرة كمعلم يشرح لتلميذه خطوة بخطوة.\n"
        "   - فكك معطيات السؤال، وبيّن دلالة كل معطى وكيف يقودنا للحل بالرجوع للمقرر.\n"
        "2. كتابة المعادلات الكيميائية كما في كتب الوزارة المعتمدة:\n"
        "   - اكتب المعادلات الكيميائية واضحة وموزونة ومنسقة في سطر مستقل بخط بارز، مع كتابة الحالة الفيزيائية وشروط التفاعل فوق السهم إن وُجدت كما في كتب الكيمياء المعتمدة.\n"
        "   - وضّح دلالة كل متفاعل وناتج بلغة علمية بسيطة (مثلاً: لون المحلول، الراسب، الغاز المتصاعد).\n"
        "3. الاستنتاج والربط العلمي النزيه (Scientific Deduction):\n"
        "   - إذا كان السؤال يتضمن مادة مجهولة أو عنصراً مجهولاً، فاستنتج هويته وصيغته بدقة وبرر الاستنتاج بأدلة الكتاب.\n"
        "4. الأمانة العلمية والالتزام بنطاق المقرر:\n"
        "   - لا تخترع معلومات غير موجودة في المنهج، ولا تناقض مصادر المقرر.\n"
        f"   - إذا كان السؤال خارج نطاق المنهج تماماً أو لا يمكن استنتاجه من الأدلة، اكتب فقط النص التالي دون أي زيادة: '{STRICT_REFUSAL_MESSAGE}'\n"
        "5. التوثيق:\n"
        "   - اختتم الإجابة بقسم توثيق المصادر والصفحات تحت عنوان: '📌 **المصدر بالمقرر:**'.\n"
    )

    # 1. Try Groq API (ultra-low latency, resilient Arabic models: Qwen 27B / GPT-OSS / Allam)
    groq_key = os.getenv("GROQ_API_KEY")
    groq_model = os.getenv("GROQ_MODEL", "qwen/qwen3.6-27b")
    if groq_key and not groq_key.startswith("your_"):
        candidate_groq_models = [groq_model, "qwen/qwen3.8-27b", "openai/gpt-oss-20b", "allam-2-7b", "groq/compound"]
        for g_model in candidate_groq_models:
            try:
                g_payload = {
                    "model": g_model,
                    "messages": [
                        {"role": "system", "content": "أنت المعلم الخبير والمساعد التعليمي الذكي للمقرر الدراسي. تجيب باللغة العربية بأسلوب تعليمي مبسط وموثق."},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.2,
                    "max_tokens": 4096,
                }
                g_req = urllib.request.Request(
                    "https://api.groq.com/openai/v1/chat/completions",
                    data=json.dumps(g_payload).encode("utf-8"),
                    headers={
                        "Authorization": f"Bearer {groq_key}",
                        "Content-Type": "application/json",
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                    },
                    method="POST",
                )
                with urllib.request.urlopen(g_req, timeout=20.0) as g_resp:
                    if g_resp.status == 200:
                        g_data = json.loads(g_resp.read().decode("utf-8"))
                        g_choices = g_data.get("choices", [])
                        if g_choices:
                            g_text = g_choices[0].get("message", {}).get("content", "").strip()
                            clean_ans = re.sub(r"<think>[\s\S]*?</think>", "", g_text).strip()
                            if clean_ans:
                                return clean_ans
            except Exception as exc:
                logger.warning(f"Groq model {g_model} failed: {exc}")
                continue

    # 2. Try Gemini API with candidate model cascade and retries
    if gemini_key and not gemini_key.startswith("your_") and not gemini_key.startswith("AQ."):
        candidate_models: list[str] = []
        if qa_model:
            candidate_models.append(qa_model)
        for fallback in ["gemini-3-flash-preview", "gemini-3.6-flash", "gemini-3.5-flash", "gemini-flash-latest"]:
            if fallback not in candidate_models:
                candidate_models.append(fallback)

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 8192,
            },
        }
        body = json.dumps(payload).encode("utf-8")

        for current_model in candidate_models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{current_model}:generateContent?key={gemini_key}"
            try:
                req = urllib.request.Request(
                    url,
                    data=body,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=22.0) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode("utf-8"))
                        candidates = data.get("candidates", [])
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            if parts and "text" in parts[0]:
                                return parts[0]["text"].strip()
            except urllib.error.HTTPError as exc:
                if exc.code in (429, 404):
                    logger.warning(f"Gemini model {current_model} returned {exc.code}, falling back to next model.")
                    continue
                if exc.code in (503, 500):
                    logger.warning(f"Gemini model {current_model} returned {exc.code}, falling back to next model.")
                    continue
                logger.warning(f"Gemini model {current_model} failed (HTTP {exc.code}): {exc}")
                continue
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                logger.warning(f"Gemini model {current_model} connection/timeout ({exc}), falling back to next model.")
                continue
            except Exception as exc:
                logger.warning(f"Gemini model {current_model} failed: {exc}")
                continue


    # 2. Try Ollama fallback
    ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    ollama_model = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
    try:
        req = urllib.request.Request(f"{ollama_url}/api/tags", headers={"User-Agent": "LMS/1.0"})
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            if resp.status == 200:
                body = json.dumps({
                    "model": ollama_model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.2},
                }).encode("utf-8")
                req2 = urllib.request.Request(
                    f"{ollama_url}/api/generate",
                    data=body,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req2, timeout=15.0) as resp2:
                    if resp2.status == 200:
                        data = json.loads(resp2.read().decode("utf-8"))
                        if "response" in data:
                            return data["response"].strip()
    except Exception:
        pass

    return None


def verify_grounded_answer(
    question: str,
    evidence_items: list[KnowledgeSearchResult],
    candidate_answer: str,
) -> VerificationResult:
    """
    Rigorous verification layer inspecting candidate answer against source evidence:
    - Rule 1: Claims must be grounded in evidence text.
    - Rule 2: Chemical formulas must match formulas in evidence or valid synonyms.
    - Rule 3: Numbers must match numbers in evidence.
    - Rule 4: Citations must reference actual retrieved pages.
    """
    if not candidate_answer or not candidate_answer.strip():
        return VerificationResult(
            verdict="UNSUPPORTED",
            is_valid=False,
            confidence=0.0,
            violations=["Empty answer received"],
        )

    # If the answer is an explicit refusal, it is valid by definition
    if STRICT_REFUSAL_MESSAGE in candidate_answer or INSUFFICIENT_EVIDENCE_MESSAGE in candidate_answer:
        return VerificationResult(
            verdict="SUPPORTED",
            is_valid=True,
            confidence=1.0,
            violations=[],
        )

    severe_violations: list[str] = []
    soft_violations: list[str] = []
    combined_evidence = " ".join([
        f"{item.concept} {item.statement} {item.details or ''} {item.page_number or ''} {item.citation_text}"
        for item in evidence_items
    ]).lower()

    # Split off citation footer for numerical checks to avoid flagging page numbers
    ans_body = candidate_answer
    citation_split = re.split(r"\n+(?:📌\s*)?\*?\*?المصدر بالمقرر:?\*?\*?", ans_body)
    if len(citation_split) > 1:
        ans_body = citation_split[0]

    # 1. Check chemical formula fidelity
    ans_formulas = extract_chemical_formulas(ans_body)
    # OCR often turns Roman numerals (II) into (11) or (III) into (111)
    ev_normalized = (
        combined_evidence
        .replace("(11)", "(ii)")
        .replace(" (11)", " (ii)")
        .replace("(111)", "(iii)")
        .replace(" (111)", " (iii)")
    )
    for f in ans_formulas:
        f_norm = f.normalized.lower().replace("_", "").strip()
        if f_norm not in combined_evidence and f_norm not in ev_normalized:
            syns = expand_chemistry_synonyms(f.normalized)
            grounded_by_syn = any(
                s.lower() in combined_evidence or s.lower() in ev_normalized
                for s in syns
            )
            if not grounded_by_syn:
                severe_violations.append(f"Chemical formula '{f.normalized}' has no grounding in retrieved evidence.")

    # 2. Check numerical constants in answer body (ignore atomic numbers 1-118, oxidation states, coefficients, and school years)
    ans_numbers = [
        n for n in re.findall(r"\b\d+(?:\.\d+)?\b", ans_body)
        if (float(n) > 118 and n not in {"2024", "2025", "2026", "2027"}) or ("." in n and float(n) > 10)
    ]
    for num in ans_numbers:
        if num not in combined_evidence:
            severe_violations.append(f"Number '{num}' not found in retrieved evidence.")

    # 3. Check page citations
    pages_in_evidence = {str(item.page_number) for item in evidence_items if item.page_number}
    cited_matches = re.findall(r"(?:الصفحة|صفحة|ص)\s*[:\-]?\s*(\d+)", candidate_answer)
    for cp in cited_matches:
        if cp not in pages_in_evidence:
            severe_violations.append(f"Citation references page {cp} which is not in retrieved evidence.")

    # 4. Check question topical coverage (prevent answering completely out-of-scope questions)
    from app.services.knowledge_retriever import _tokenize_for_search
    q_tokens = [t for t in _tokenize_for_search(question) if len(t) >= 3]
    if q_tokens:
        ev_tokens = set(_tokenize_for_search(combined_evidence))
        matched_q = [t for t in q_tokens if t in ev_tokens]
        if not matched_q:
            soft_violations.append(
                f"Question subject terms have no grounding in course evidence (0/{len(q_tokens)} matched)."
            )

    violations = severe_violations + soft_violations
    if not violations:
        return VerificationResult(
            verdict="SUPPORTED",
            is_valid=True,
            confidence=1.0,
            violations=[],
        )
    if severe_violations:
        return VerificationResult(
            verdict="UNSUPPORTED",
            is_valid=False,
            confidence=0.2,
            violations=violations,
        )
    return VerificationResult(
        verdict="PARTIALLY_SUPPORTED",
        is_valid=True,
        confidence=0.8,
        violations=violations,
    )


def build_grounded_answer(
    question: str,
    evidence_items: list[KnowledgeSearchResult],
) -> tuple[str, bool, bool, list[dict[str, Any]]]:
    """
    Builds a strictly grounded answer accompanied by source citations.
    Returns: (answer_text, is_grounded, is_refusal, citations)
    """
    clean_q = question.strip()
    if not clean_q:
        return ("يرجى كتابة السؤال المطلوب.", False, False, [])

    # If no evidence retrieved, strictly refuse
    if not evidence_items:
        return (STRICT_REFUSAL_MESSAGE, False, True, [])

    # Filter for relevant evidence with score > 0.0
    relevant = [e for e in evidence_items if e.relevance_score > 0.0]
    if not relevant:
        return (STRICT_REFUSAL_MESSAGE, False, True, [])

    citations_data = [
        {
            "unit_id": item.unit_id,
            "filename": item.source_filename,
            "page_number": item.page_number,
            "slide_number": item.slide_number,
            "citation": item.citation_text,
            "snippet": item.statement,
        }
        for item in relevant
    ]

    # 1. Try LLM generation with scientific deduction & reasoning
    llm_ans = generate_llm_grounded_answer(clean_q, relevant)
    if llm_ans:
        # If LLM explicitly refused
        if STRICT_REFUSAL_MESSAGE in llm_ans or INSUFFICIENT_EVIDENCE_MESSAGE in llm_ans:
            return (STRICT_REFUSAL_MESSAGE, False, True, citations_data)

        # Run verification layer
        verif = verify_grounded_answer(clean_q, relevant, llm_ans)
        if verif.is_valid:
            # Ensure citation footer exists
            if "📌 **المصدر بالمقرر:**" not in llm_ans and "المصدر بالمقرر" not in llm_ans:
                unique_citations = set(c["citation"] for c in citations_data if c.get("citation"))
                if unique_citations:
                    llm_ans += "\n\n📌 **المصدر بالمقرر:**\n" + "\n".join(f"• {cit}" for cit in unique_citations)
            return (llm_ans, True, False, citations_data)
        else:
            logger.warning(f"LLM answer rejected by verification layer: {verif.violations}")

    # 2. Fallback to deterministic concatenation
    best = relevant[0]
    best_stmt = best.statement.strip()
    best_details = (best.details or "").strip()

    answer_lines = [f"{best_stmt}\n"]
    if best_details and len(best_details) > len(best_stmt) and best_stmt not in best_details:
        answer_lines.append(f"{best_details}\n")

    if best.media_urls:
        answer_lines.append(f"🖼️ [عرض المخطط التوضيحي المرفق بالمستند]({best.media_urls[0]})\n")

    answer_lines.append("📌 **المصدر بالمقرر:**")
    unique_citations = set(c["citation"] for c in citations_data if c.get("citation"))
    for cit in unique_citations:
        answer_lines.append(f"• {cit}")

    full_answer = "\n".join(answer_lines)
    verif = verify_grounded_answer(clean_q, relevant, full_answer)
    if not verif.is_valid:
        return (INSUFFICIENT_EVIDENCE_MESSAGE, False, True, citations_data)

    return (full_answer, True, False, citations_data)
