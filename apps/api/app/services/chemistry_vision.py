"""
=============================================================================
CHEMISTRY MULTIMODAL VISION & DIAGRAM ANALYZER
=============================================================================
Extracts semantic meaning from chemistry images, charts, and diagrams:
1. Detects reaction schemes, lab apparatus, tables, and energy graphs.
2. Generates structured textual descriptions (extracted equations, reactants, products).
3. Indexes image semantics directly into KnowledgeUnitRecords linked to KnowledgeAssets.
=============================================================================
"""
from __future__ import annotations

import logging
import os
import re
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.knowledge_center import KnowledgeAsset, KnowledgeUnitRecord
from app.services.chemistry_normalizer import (
    extract_chemical_formulas,
    parse_chemical_reaction,
)

logger = logging.getLogger(__name__)


def analyze_chemistry_diagram_content(
    caption: str | None,
    surrounding_text: str | None,
    extracted_ocr: str | None = None,
) -> dict[str, Any]:
    """
    Performs multimodal understanding on an image asset based on its visual context,
    captions, and OCR-extracted text layer.
    """
    combined = " ".join([caption or "", surrounding_text or "", extracted_ocr or ""]).strip()
    
    # 1. Detect if image is a chemical reaction scheme
    reactions = []
    for line in combined.split("\n"):
        rx = parse_chemical_reaction(line)
        if rx:
            reactions.append(rx)

    formulas = extract_chemical_formulas(combined)
    unique_formulas = list({f.normalized for f in formulas})

    # 2. Detect apparatus or experimental setup
    apparatus_terms = [
        "سحاحة", "دورق", "مخبار", "أنبوبة اختبار", "ماصة", "لهب بنزن",
        "ميزان حساس", "حامل", "ورقة ترشيح", "جهاز تحضير", "خلية جلفانية", "خلية إلكتروليتية"
    ]
    detected_apparatus = [app for app in apparatus_terms if app in combined]

    # 3. Classify asset category
    if reactions:
        category = "reaction_scheme"
        summary = f"مخطط تفاعل كيميائي يوضح: {reactions[0].raw}"
    elif detected_apparatus:
        category = "experimental_setup"
        summary = f"رسم تجربة معملية وجهاز يشتمل على: {', '.join(detected_apparatus)}"
    elif any(k in combined for k in ["منحنى", "رسم بياني", "طاقة التنشيط", "مخطط طاقة"]):
        category = "graph"
        summary = "رسم بياني أو منحنى يوضح تغيرات الطاقة أو معدل التفاعل الكيميائي"
    elif unique_formulas:
        category = "chemical_diagram"
        summary = f"رسم توضيحي لمركبات كيميائية تشمل: {', '.join(unique_formulas)}"
    else:
        category = "figure"
        summary = caption or "شكل توضيحي بالمقرر"

    # 4. Generate anticipated questions covering all possible exam and study inquiries
    anticipated_questions: list[str] = []
    if reactions:
        r_raw = reactions[0].raw
        anticipated_questions.extend([
            f"ما نوع التفاعل الكيميائي الموضح في المعادلة ({r_raw})؟",
            f"ما هي المواد المتفاعلة والناتجة وشروط التفاعل في ({r_raw})؟",
            "اكتب معادلة التفاعل الرمزية الموزونة للتفاعل الموضح.",
            "ما هي المشاهدات المعملية والتغيرات المصاحبة لهذا التفاعل؟",
        ])
    if detected_apparatus:
        app_name = detected_apparatus[0]
        anticipated_questions.extend([
            f"ما اسم الجهاز أو الأداة المعملية المستخدمة ({app_name}) وما وظيفتها في التجربة؟",
            "ما هي خطوات التجربة المعملية الموضحة في الرسم؟",
            "ما هي الملاحظات والاستنتاجات المستفادة من هذه التجربة؟",
        ])
    if category == "graph":
        anticipated_questions.extend([
            "ما العلاقة البيانية الموضحة بين المتغيرات في المنحنى؟",
            "كيف يؤثر تغير الحرارة أو التركيز أو العامل الحفاز على سير التفاعل وطاقة التنشيط؟",
        ])
    if unique_formulas:
        f_list = ", ".join(unique_formulas[:3])
        anticipated_questions.extend([
            f"ما هي خواص واستخدامات المركبات ({f_list}) بالمقرر؟",
            f"كيف يمكن الكشف عن أو تحضير ({f_list}) عملياً؟",
        ])

    return {
        "category": category,
        "summary": summary,
        "formulas": unique_formulas,
        "reactions": [r.raw for r in reactions],
        "apparatus": detected_apparatus,
        "anticipated_questions": anticipated_questions,
    }


def index_asset_as_knowledge_unit(
    db: Session,
    asset: KnowledgeAsset,
    course_id: uuid.UUID,
    lesson_id: uuid.UUID | None,
    source_id: uuid.UUID,
    version: int = 1,
) -> KnowledgeUnitRecord | None:
    """
    Indexes an image asset into a searchable KnowledgeUnitRecord with full media provenance
    and anticipated question-answering cues.
    """
    vision_analysis = (asset.metadata_json or {}).get("vision_analysis") or {}
    analysis = analyze_chemistry_diagram_content(
        caption=asset.caption,
        surrounding_text=asset.surrounding_text,
        extracted_ocr="\n".join(filter(None, [
            (asset.metadata_json or {}).get("ocr_text"),
            vision_analysis.get("description"),
            vision_analysis.get("table_markdown"),
            " ".join(vision_analysis.get("formulas", [])),
        ])),
    )

    concept = f"شكل توضيحي: {analysis['category']}"
    if analysis["formulas"]:
        concept = f"مخطط كيميائي ({', '.join(analysis['formulas'][:3])})"
    elif analysis["apparatus"]:
        concept = f"تجربة: {analysis['apparatus'][0]}"

    statement = analysis["summary"]
    if asset.caption and asset.caption not in statement:
        statement = f"{statement}. ({asset.caption})"

    details_parts: list[str] = []
    if asset.surrounding_text:
        details_parts.append(asset.surrounding_text)
    ocr_text = (asset.metadata_json or {}).get("ocr_text")
    if ocr_text:
        details_parts.append(f"النص المقروء داخل الصورة:\n{ocr_text}")
    if vision_analysis.get("description"):
        details_parts.append(f"وصف الصورة: {vision_analysis['description']}")
    if vision_analysis.get("table_markdown"):
        details_parts.append(f"الجدول المستخرج من الصورة:\n{vision_analysis['table_markdown']}")
    if analysis.get("anticipated_questions"):
        details_parts.append("الأسئلة المتوقعة حول هذا المخطط بالمقرر:\n" + "\n".join(f"• {q}" for q in analysis["anticipated_questions"]))

    ku_rec = KnowledgeUnitRecord(
        course_id=course_id,
        lesson_id=lesson_id,
        source_id=source_id,
        source_type="diagram",
        concept=concept[:250],
        knowledge_type="diagram",
        statement=statement,
        details="\n\n".join(details_parts) if details_parts else None,
        importance=0.85,
        semantic_confidence=1.0,
        needs_review=False,
        source_document_id=asset.document_id,
        outline_node_id=asset.outline_node_id,
        page_number=asset.page_number,
        slide_number=asset.slide_number,
        block_id=f"asset_{asset.id.hex[:8]}",
        source_media_ids_json=[str(asset.id)],
        version=version,
    )
    db.add(ku_rec)
    return ku_rec
