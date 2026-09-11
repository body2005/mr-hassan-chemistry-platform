# -*- coding: utf-8 -*-
from __future__ import annotations

import pytest
from app.services.document_parsers import (
    fix_reversed_arabic_text,
    is_valid_data_table,
    is_text_garbled,
)


def test_is_valid_data_table_genuine_tables():
    # 1. Chemical element abundance table (2 columns, multiple rows, short cells)
    headers = ["النسبة المئوية للوزن", "العنصر"]
    rows = [
        ["% 46.6", "الأكسجين"],
        ["% 27.7", "السيليكون"],
        ["% 8.1", "الألومنيوم"],
        ["% 5.0", "الحديد"],
    ]
    valid, reason = is_valid_data_table(headers, rows)
    assert valid is True
    assert "Valid table" in reason

    # 2. Mohs hardness scale (11 columns, 2 rows)
    mohs_headers = ["ماس", "كوراندوم", "توباز", "كوارتز", "أرثوكليز", "أباتيت", "فلوريت", "كالسيت", "جبس", "تلك", "المعدن"]
    mohs_rows = [["10", "9", "8", "7", "6", "5", "4", "3", "2", "1", "الصلادة"]]
    valid, reason = is_valid_data_table(mohs_headers, mohs_rows)
    assert valid is True


def test_is_valid_data_table_rejects_narrative_callout_boxes():
    # 1. 1-cell layout box containing a whole 250-word narrative paragraph
    long_paragraph = " ".join(["هذا النص يمثل فقرة سردية طويلة تم وضعها داخل إطار تزييني في الصفحة"] * 20)
    headers = [""]
    rows = [[long_paragraph]]
    valid, reason = is_valid_data_table(headers, rows)
    assert valid is False
    assert "Fewer than 2" in reason or "Narrative" in reason

    # 2. Multi-cell grid where 1 cell has 60 words and average words > 25
    headers = ["العنوان", "التفاصيل"]
    rows = [["ملاحظة", " ".join(["شرح طويل جداً ومفصل يتجاوز حدود خلايا الجداول الإحصائية الحقيقية"] * 8)]]
    valid, reason = is_valid_data_table(headers, rows)
    assert valid is False
    assert "Narrative text box" in reason


def test_fix_reversed_arabic_text():
    # 1. Reversed phrase from PDF font stream: 'نزولل ةيوئلما ةبسنلا' -> 'النسبة المئوية للوزن'
    reversed_phrase = "نزولل ةيوئلما ةبسنلا"
    fixed = fix_reversed_arabic_text(reversed_phrase)
    assert "النسبة" in fixed
    assert "المئوية" in fixed
    assert "للوزن" in fixed

    # 2. Reversed elements: 'ينجسكلأا' -> 'الأكسجين'
    assert fix_reversed_arabic_text("ينجسكلأا") == "الأكسجين"

    # 3. Reversed mineral: 'ديدلحا' -> 'الحديد'
    assert fix_reversed_arabic_text("ديدلحا") == "الحديد"

    # 4. Normal Arabic should remain intact
    normal = "الجدول الدوري للعناصر الكيميائية"
    assert fix_reversed_arabic_text(normal) == normal
