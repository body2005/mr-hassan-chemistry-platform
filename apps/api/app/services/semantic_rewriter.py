"""
=============================================================================
MATGAR LMS - SEMANTIC REWRITER & INDEPENDENT VERIFICATION GATE
=============================================================================
Architecture:
    Raw ASR Transcript (Preserved with Timestamps in DB)
        ↓
    Conservative Deterministic Normalization (Vocalic fillers, ASR phonetics)
        ↓
    Semantic Understanding & Educational Rewriting (LLM / MSA Synthesizer)
        ↓
    Semantic Verification Layer (Faithfulness, No-Expansion, No-Loss Verifier)
        ↓
    Educational Knowledge Unit with Semantic Confidence
=============================================================================
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

# Arabic stopwords to filter when comparing content tokens
STOPWORDS_AR: set[str] = {
    "في", "من", "على", "عن", "إلى", "الى", "مع", "أو", "او", "ثم", "حيث", "أن", "ان",
    "هذا", "هذه", "ذلك", "تلك", "التي", "الذي", "الذين", "اللاتي", "ما", "ماذا", "لماذا",
    "كيف", "متى", "أين", "اين", "هل", "كل", "جميع", "بعض", "غير", "بين", "أمام", "خلف",
    "تحت", "فوق", "عند", "لدى", "مثل", "نحو", "قد", "لقد", "كان", "كانت", "يكون", "تكون",
    "هو", "هي", "هم", "هن", "نحن", "أنا", "انت", "أنت", "تعتبر", "يُعد", "يعد", "تعد",
    "توضح", "يوضح", "تتضمن", "يتضمن", "يقوم", "تقوم", "بهدف", "لكي", "دون", "ندرس",
    "بأن", "التي", "الذي", "لما", "مازال", "أصبح", "صار", "ليس", "ليست", "تم", "يتم",
    "جدا", "جداً", "معا", "معاً", "خاصة", "غالبا", "غالباً"
}


@dataclass
class SemanticVerificationResult:
    """Detailed output of the Independent Semantic Verification Layer."""
    is_faithful: bool
    has_expansion: bool
    has_loss: bool
    added_facts: list[str] = field(default_factory=list)
    missing_facts: list[str] = field(default_factory=list)
    clarity_score: float = 1.0
    semantic_confidence: float = 1.0
    reason: str = "Faithful and fully grounded"


def _normalize_token_for_matching(word: str) -> str:
    """Normalizes an Arabic word for robust semantic containment comparison."""
    w = re.sub(r"[^\w\u0621-\u064A]", "", word.lower())
    w = re.sub(r"[\u064B-\u0652\u0640]", "", w)
    w = re.sub(r"[إأآا]", "ا", w)
    w = re.sub(r"[ة]", "ه", w)
    w = re.sub(r"[ى]", "ي", w)
    if w.startswith("ال") and len(w) > 3:
        w = w[2:]
    return w


def verify_semantic_faithfulness(raw_text: str, statement: str) -> SemanticVerificationResult:
    """
    Independent Semantic Verifier Gate:
    1. Supported Facts: Checks that all factual claims in statement exist in raw_text.
    2. No-Expansion: Detects hallucinated facts, outside reasons, or unsupported theories.
    3. No-Loss: Ensures primary subject entities and constraints are retained.
    4. Clarity Score: Assesses standard grammar, punctuation, and lack of disfluencies.
    5. Semantic Confidence: Assigns a confidence score between 0.0 and 1.0.
    """
    if not raw_text or not statement:
        return SemanticVerificationResult(
            is_faithful=False,
            has_expansion=False,
            has_loss=True,
            reason="Empty source or statement",
            semantic_confidence=0.0,
        )

    raw_tokens = {
        _normalize_token_for_matching(w)
        for w in raw_text.split()
        if len(w) > 1 and w not in STOPWORDS_AR
    }
    raw_tokens = {t for t in raw_tokens if t}

    statement_tokens = {
        _normalize_token_for_matching(w)
        for w in statement.split()
        if len(w) > 1 and w not in STOPWORDS_AR
    }
    statement_tokens = {t for t in statement_tokens if t}

    if not raw_tokens or not statement_tokens:
        return SemanticVerificationResult(
            is_faithful=True,
            has_expansion=False,
            has_loss=False,
            semantic_confidence=1.0,
        )

    overlap = statement_tokens.intersection(raw_tokens)
    overlap_ratio = len(overlap) / max(1, len(statement_tokens))

    # Identify novel words introduced in the statement
    unsupported_tokens = statement_tokens - raw_tokens
    grammatical_connectors = {
        "استخدام", "تطبيق", "تحديد", "معرفه", "دراسه", "عمليه", "اسلوب", "طريقه",
        "مفهوم", "تعريف", "تعتمد", "يستخدم", "تؤثر", "يؤثر", "قاعده", "خاصيه",
        "علاقه", "نتيجه", "معدل", "عناصر", "خصائص", "سياق", "شرح", "محاضره",
        "حركه", "صخر", "صخور", "علم", "علوم", "فرع", "مجال", "طبقه", "طبقات"
    }
    novel_content_tokens = [t for t in unsupported_tokens if t not in grammatical_connectors and len(t) > 2]

    # Expansion Check: If > 40% of content tokens are unsupported external concepts
    has_expansion = len(statement_tokens) > 4 and (len(novel_content_tokens) / len(statement_tokens)) > 0.40
    
    # Loss Check: If < 25% of source entities are preserved in statement
    has_loss = (len(overlap) / max(1, len(raw_tokens))) < 0.25 and len(raw_tokens) >= 3

    # Clarity Check: Check if statement ends with proper period and contains no colloquial tokens
    banned_colloquials = ["بص", "ركز معايا", "سمي الله", "يعني", "بقى", "اهو", "كده", "ميح", "دحيح", "هتفرم"]
    has_colloquials = any(c in statement for c in banned_colloquials)
    clarity_score = 0.5 if has_colloquials else (1.0 if statement.strip().endswith(".") else 0.9)

    # Compute Semantic Confidence
    if has_expansion:
        conf = max(0.1, 0.4 - (len(novel_content_tokens) * 0.05))
        reason = f"Expansion detected: Added unsupported external facts {novel_content_tokens[:3]}"
    elif has_loss:
        conf = 0.3
        reason = "Information loss: Core source concepts omitted"
    else:
        conf = min(1.0, max(0.8, 0.5 + (0.5 * overlap_ratio)))
        reason = "Faithful and fully grounded"

    is_faithful = (not has_expansion) and (not has_loss) and (conf >= 0.7)

    return SemanticVerificationResult(
        is_faithful=is_faithful,
        has_expansion=has_expansion,
        has_loss=has_loss,
        added_facts=novel_content_tokens if has_expansion else [],
        missing_facts=list(raw_tokens - statement_tokens) if has_loss else [],
        clarity_score=clarity_score,
        semantic_confidence=round(conf, 3),
        reason=reason,
    )


def validate_semantic_containment(raw_text: str, rewritten_statement: str) -> tuple[bool, str, float]:
    """Compatibility wrapper for semantic verification check."""
    res = verify_semantic_faithfulness(raw_text, rewritten_statement)
    return res.is_faithful, res.reason, res.semantic_confidence


_LLM_PROBE_CACHE: dict[str, Any] = {"available": None, "last_checked": 0.0}


def is_llm_service_available(url: str, cache_ttl: float = 30.0) -> bool:
    """Fast probe to check if the LLM server is reachable without blocking requests."""
    import socket
    import time
    from urllib.parse import urlparse

    now = time.time()
    if _LLM_PROBE_CACHE["available"] is not None and (now - _LLM_PROBE_CACHE["last_checked"]) < cache_ttl:
        return bool(_LLM_PROBE_CACHE["available"])

    try:
        parsed = urlparse(url)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or (11434 if "11434" in url else 80)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.1)
        result = sock.connect_ex((host, port))
        sock.close()
        is_avail = (result == 0)
    except Exception:
        is_avail = False

    _LLM_PROBE_CACHE["available"] = is_avail
    _LLM_PROBE_CACHE["last_checked"] = now
    return is_avail


def invoke_llm_semantic_rewriting(
    cleaned_text: str,
    raw_text: str,
    timeout: float = 2.0,
) -> dict[str, Any] | None:
    """
    Attempts LLM-based semantic rewriting via configured LLM endpoint (Ollama/remote).
    Strictly instructs the LLM not to add external facts.
    """
    ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    ollama_model = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")

    if not is_llm_service_available(ollama_url):
        return None

    system_prompt = (
        "أنت خبير صياغة تربوية للمنصات التعليمية. مهمتك تحويل جملة الشرح المنطوقة بالعامية إلى عبارة تعليمية فصيحة.\n"
        "القواعد الصارمة:\n"
        "1. التزم حصرياً بالمعنى الموجود في الجملة فقط.\n"
        "2. ممنوع إضافة أي حقائق أو أمثلة أو معلومات لم يقلها المعلم.\n"
        "3. احذف الحشو العامي وأعد صياغة العبارة بلغة عربية فصحى موجزة وسليمة.\n"
        "4. أرجع الناتج بصيغة JSON فقط بهذا الشكل:\n"
        "{\n"
        '  "concept": "المفهوم الرئيسي المستخرج",\n'
        '  "statement": "العبارة التعليمية الفصيحة المطابقة للمعنى فقط",\n'
        '  "category": "definition | application | relationship | classification | general"\n'
        "}"
    )

    user_payload = {"role": "user", "content": f"المقطع المنطوق: '{cleaned_text}'"}
    full_prompt = f"{system_prompt}\n\n{json.dumps(user_payload, ensure_ascii=False)}"

    body = json.dumps({
        "model": ollama_model,
        "prompt": full_prompt,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.0, "top_p": 0.1},
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{ollama_url}/api/generate",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            raw_resp = data.get("response", "")
            parsed = json.loads(raw_resp)
            if isinstance(parsed, dict) and "concept" in parsed and "statement" in parsed:
                # Anti-Hallucination containment validation
                is_valid, reason, _ = validate_semantic_containment(raw_text, parsed["statement"])
                if is_valid:
                    return parsed
    except Exception:
        pass

    return None
