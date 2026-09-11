"""
=============================================================================
CHEMISTRY NORMALIZER & SEMANTIC FORMULA PARSER
=============================================================================
Provides chemistry-aware text processing:
1. Chemical formula detection (organic, inorganic, acids, salts, ions, gases).
2. Stoichiometric decomposition (separating coefficients from compounds).
3. Bilingual Arabic <-> English <-> Chemical Formula synonym expansion.
4. Non-destructive tokenization protecting formula subscripts and charge signs.
5. Reaction scheme parsing (reactants, products, reaction conditions).
=============================================================================
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ChemicalFormula:
    raw: str
    normalized: str
    coefficient: int = 1
    state: str | None = None  # s, l, g, aq


@dataclass
class ChemicalReaction:
    raw: str
    reactants: list[ChemicalFormula] = field(default_factory=list)
    products: list[ChemicalFormula] = field(default_factory=list)
    conditions: str | None = None


# Comprehensive bilingual Arabic/English chemistry concept dictionary
CHEMISTRY_SYNONYM_MAP: dict[str, dict[str, Any]] = {
    "h2so4": {
        "formula": "H2SO4",
        "arabic_names": ["حمض الكبريتيك", "حمض كبريتيك", "زيت الزاج"],
        "english_names": ["sulfuric acid", "sulphuric acid"],
        "category": "acid",
    },
    "feo": {
        "formula": "FeO",
        "arabic_names": ["أكسيد الحديد الثنائي", "أكسيد الحديد (II)", "أكسيد الحديد (11)", "أكسيد الحديدوز", "أكسيد حديد ثنائي", "أكسيد حديد (II)"],
        "english_names": ["iron(II) oxide", "ferrous oxide"],
        "category": "oxide",
    },
    "fe2o3": {
        "formula": "Fe2O3",
        "arabic_names": ["أكسيد الحديد الثلاثي", "أكسيد الحديد (III)", "أكسيد الحديد (111)", "أكسيد الحديديك", "الهيماتيت"],
        "english_names": ["iron(III) oxide", "ferric oxide", "hematite"],
        "category": "oxide",
    },
    "fe3o4": {
        "formula": "Fe3O4",
        "arabic_names": ["أكسيد الحديد المغناطيسي", "الميجنتايت", "المغنتيت", "أكسيد الحديد الأسود"],
        "english_names": ["magnetic iron oxide", "iron(II,III) oxide", "magnetite"],
        "category": "oxide",
    },
    "fecl2": {
        "formula": "FeCl2",
        "arabic_names": ["كلوريد الحديد الثنائي", "كلوريد الحديد (II)", "كلوريد الحديد (11)", "كلوريد الحديدوز"],
        "english_names": ["iron(II) chloride", "ferrous chloride"],
        "category": "salt",
    },
    "fecl3": {
        "formula": "FeCl3",
        "arabic_names": ["كلوريد الحديد الثلاثي", "كلوريد الحديد (III)", "كلوريد الحديد (111)", "كلوريد الحديديك"],
        "english_names": ["iron(III) chloride", "ferric chloride"],
        "category": "salt",
    },
    "feso4": {
        "formula": "FeSO4",
        "arabic_names": ["كبريتات الحديد الثنائية", "كبريتات الحديد (II)", "كبريتات الحديدوز"],
        "english_names": ["iron(II) sulfate", "ferrous sulfate"],
        "category": "salt",
    },
    "fe(oh)2": {
        "formula": "Fe(OH)2",
        "arabic_names": ["هيدروكسيد الحديد الثنائي", "هيدروكسيد الحديد (II)", "هيدروكسيد الحديدوز"],
        "english_names": ["iron(II) hydroxide", "ferrous hydroxide"],
        "category": "base",
    },
    "fe(oh)3": {
        "formula": "Fe(OH)3",
        "arabic_names": ["هيدروكسيد الحديد الثلاثي", "هيدروكسيد الحديد (III)", "هيدروكسيد الحديديك"],
        "english_names": ["iron(III) hydroxide", "ferric hydroxide"],
        "category": "base",
    },
    "fe": {
        "formula": "Fe",
        "arabic_names": ["الحديد", "عنصر الحديد", "فلز الحديد", "برادة الحديد"],
        "english_names": ["iron"],
        "category": "element",
    },
    "hcl": {
        "formula": "HCl",
        "arabic_names": ["حمض الهيدروكلوريك", "حمض هيدروكلوريك", "كلوريد الهيدروجين", "روح الملح"],
        "english_names": ["hydrochloric acid", "hydrogen chloride"],
        "category": "acid",
    },
    "hno3": {
        "formula": "HNO3",
        "arabic_names": ["حمض النيتريك", "حمض نيتريك", "ماء النار"],
        "english_names": ["nitric acid"],
        "category": "acid",
    },
    "naoh": {
        "formula": "NaOH",
        "arabic_names": ["هيدروكسيد الصوديوم", "الصودا الكاوية", "صودا كاوية"],
        "english_names": ["sodium hydroxide", "caustic soda"],
        "category": "base",
    },
    "koh": {
        "formula": "KOH",
        "arabic_names": ["هيدروكسيد البوتاسيوم", "البوتاسا الكاوية", "بوتاسا كاوية"],
        "english_names": ["potassium hydroxide", "caustic potash"],
        "category": "base",
    },
    "ca(oh)2": {
        "formula": "Ca(OH)2",
        "arabic_names": ["هيدروكسيد الكالسيوم", "ماء الجير الرائق", "الجير المطفأ"],
        "english_names": ["calcium hydroxide", "limewater", "slaked lime"],
        "category": "base",
    },
    "caco3": {
        "formula": "CaCO3",
        "arabic_names": ["كربونات الكالسيوم", "الحجر الجيري", "الرخام", "الطباشير"],
        "english_names": ["calcium carbonate", "limestone"],
        "category": "salt",
    },
    "nacl": {
        "formula": "NaCl",
        "arabic_names": ["كلوريد الصوديوم", "ملح الطعام", "الملح الصخري"],
        "english_names": ["sodium chloride", "table salt", "halite"],
        "category": "salt",
    },
    "cuso4": {
        "formula": "CuSO4",
        "arabic_names": ["كبريتات النحاس", "كبريتات النحاس الثنائية", "التوتيا الزرقاء"],
        "english_names": ["copper sulfate", "copper(II) sulfate"],
        "category": "salt",
    },
    "zn": {
        "formula": "Zn",
        "arabic_names": ["الخارصين", "الزنك", "عنصر الخارصين", "فلز الخارصين", "زنك"],
        "english_names": ["zinc"],
        "category": "element",
    },
    "zncl2": {
        "formula": "ZnCl2",
        "arabic_names": ["كلوريد الخارصين", "كلوريد الزنك"],
        "english_names": ["zinc chloride"],
        "category": "salt",
    },
    "fe": {
        "formula": "Fe",
        "arabic_names": ["الحديد", "فلز الحديد", "عنصر الحديد"],
        "english_names": ["iron"],
        "category": "element",
    },
    "fe2o3": {
        "formula": "Fe2O3",
        "arabic_names": ["أكسيد الحديد الثلاثي", "الهيماتيت", "أكسيد الحديد الاحمر"],
        "english_names": ["iron(III) oxide", "hematite", "ferric oxide"],
        "category": "oxide",
    },
    "fe3o4": {
        "formula": "Fe3O4",
        "arabic_names": ["أكسيد الحديد المغناطيسي", "المغناتيت"],
        "english_names": ["iron(II,III) oxide", "magnetite", "magnetic iron oxide"],
        "category": "oxide",
    },
    "feo": {
        "formula": "FeO",
        "arabic_names": ["أكسيد الحديد الثنائي", "أكسيد حديدوز", "أكسيد الحديد II", "أكسيد الحديد (II)"],
        "english_names": ["iron(II) oxide", "ferrous oxide"],
        "category": "oxide",
    },
    "fecl2": {
        "formula": "FeCl2",
        "arabic_names": ["كلوريد الحديد الثنائي", "كلوريد حديدوز", "كلوريد الحديد II", "كلوريد الحديد (II)", "ملح كلوريد الحديد (II)"],
        "english_names": ["iron(II) chloride", "ferrous chloride"],
        "category": "salt",
    },
    "fecl3": {
        "formula": "FeCl3",
        "arabic_names": ["كلوريد الحديد الثلاثي", "كلوريد حديديك", "كلوريد الحديد III", "كلوريد الحديد (III)"],
        "english_names": ["iron(III) chloride", "ferric chloride"],
        "category": "salt",
    },
    "feso4": {
        "formula": "FeSO4",
        "arabic_names": ["كبريتات الحديد الثنائية", "كبريتات حديدوز", "كبريتات الحديد II", "كبريتات الحديد (II)"],
        "english_names": ["iron(II) sulfate", "ferrous sulfate"],
        "category": "salt",
    },
    "fe(oh)2": {
        "formula": "Fe(OH)2",
        "arabic_names": ["هيدروكسيد الحديد الثنائي", "هيدروكسيد حديدوز", "هيدروكسيد الحديد II", "هيدروكسيد الحديد (II)"],
        "english_names": ["iron(II) hydroxide", "ferrous hydroxide"],
        "category": "base",
    },
    "fe(oh)3": {
        "formula": "Fe(OH)3",
        "arabic_names": ["هيدروكسيد الحديد الثلاثي", "هيدروكسيد حديديك", "هيدروكسيد الحديد III", "هيدروكسيد الحديد (III)"],
        "english_names": ["iron(III) hydroxide", "ferric hydroxide"],
        "category": "base",
    },
    "fe2+": {
        "formula": "Fe2+",
        "arabic_names": ["كاتيون الحديد الثنائي", "أيون الحديد الثنائي", "أيونات الحديد الثنائية", "كاتيونات الحديد الثنائية", "Fe2+"],
        "english_names": ["iron(II) ion", "ferrous ion"],
        "category": "ion",
    },
    "fe3+": {
        "formula": "Fe3+",
        "arabic_names": ["كاتيون الحديد الثلاثي", "أيون الحديد الثلاثي", "أيونات الحديد الثلاثية", "كاتيونات الحديد الثلاثية", "Fe3+"],
        "english_names": ["iron(III) ion", "ferric ion"],
        "category": "ion",
    },
    "h2o": {
        "formula": "H2O",
        "arabic_names": ["الماء", "ماء", "بخار الماء"],
        "english_names": ["water", "water vapor"],
        "category": "solvent",
    },
    "h2": {
        "formula": "H2",
        "arabic_names": ["غاز الهيدروجين", "الهيدروجين"],
        "english_names": ["hydrogen gas", "hydrogen"],
        "category": "gas",
    },
    "o2": {
        "formula": "O2",
        "arabic_names": ["غاز الأكسجين", "الأكسجين"],
        "english_names": ["oxygen gas", "oxygen"],
        "category": "gas",
    },
    "n2": {
        "formula": "N2",
        "arabic_names": ["غاز النيتروجين", "النيتروجين"],
        "english_names": ["nitrogen gas", "nitrogen"],
        "category": "gas",
    },
    "co2": {
        "formula": "CO2",
        "arabic_names": ["ثاني أكسيد الكربون", "غاز ثاني أكسيد الكربون"],
        "english_names": ["carbon dioxide"],
        "category": "gas",
    },
    "co": {
        "formula": "CO",
        "arabic_names": ["أول أكسيد الكربون", "غاز أول أكسيد الكربون"],
        "english_names": ["carbon monoxide"],
        "category": "gas",
    },
    "nh3": {
        "formula": "NH3",
        "arabic_names": ["الأمونيا", "النشادر", "غاز النشادر", "غاز الأمونيا"],
        "english_names": ["ammonia", "ammonia gas"],
        "category": "gas",
    },
    "ch4": {
        "formula": "CH4",
        "arabic_names": ["الميثان", "غاز الميثان", "غاز المستنقعات"],
        "english_names": ["methane"],
        "category": "organic",
    },
    "c2h5oh": {
        "formula": "C2H5OH",
        "arabic_names": ["الإيثانول", "الكحول الإيثيلي", "كحول إيثيلي"],
        "english_names": ["ethanol", "ethyl alcohol"],
        "category": "organic",
    },
    "ch3cooh": {
        "formula": "CH3COOH",
        "arabic_names": ["حمض الأسيتيك", "حمض الخليك", "حمض الإيثانويك", "الخل"],
        "english_names": ["acetic acid", "ethanoic acid"],
        "category": "organic_acid",
    },
    "kmno4": {
        "formula": "KMnO4",
        "arabic_names": ["برمنجنات البوتاسيوم", "برمنجانات البوتاسيوم"],
        "english_names": ["potassium permanganate"],
        "category": "oxidizing_agent",
    },
    "k2cr2o7": {
        "formula": "K2Cr2O7",
        "arabic_names": ["ثاني كرومات البوتاسيوم", "دايكرومات البوتاسيوم"],
        "english_names": ["potassium dichromate"],
        "category": "oxidizing_agent",
    },
    "agno3": {
        "formula": "AgNO3",
        "arabic_names": ["نترات الفضة"],
        "english_names": ["silver nitrate"],
        "category": "salt",
    },
    "bacl2": {
        "formula": "BaCl2",
        "arabic_names": ["كلوريد الباريوم"],
        "english_names": ["barium chloride"],
        "category": "salt",
    },
    "baso4": {
        "formula": "BaSO4",
        "arabic_names": ["كبريتات الباريوم"],
        "english_names": ["barium sulfate"],
        "category": "salt",
    },
    "na2so4": {
        "formula": "Na2SO4",
        "arabic_names": ["كبريتات الصوديوم"],
        "english_names": ["sodium sulfate"],
        "category": "salt",
    },
}

_AR_TO_FORMULA: dict[str, str] = {}
for formula_key, data in CHEMISTRY_SYNONYM_MAP.items():
    for ar_name in data["arabic_names"]:
        norm_ar = re.sub(r"[إأآا]", "ا", ar_name).strip()
        _AR_TO_FORMULA[norm_ar] = data["formula"]
        _AR_TO_FORMULA[ar_name] = data["formula"]

STATE_PATTERN = re.compile(r"(?:_?[\({](?:s|l|g|aq|dil|conc|heat)[\)}]|_\((?:s|l|g|aq)\))", re.IGNORECASE)
ARROW_PATTERN = re.compile(r"\s*(?:->|→|⇌|<=>|—>)\s*")


def normalize_chemical_formula(raw_formula: str) -> ChemicalFormula:
    s = raw_formula.strip()
    # Strip LaTeX markup like \mathrm{}, \text{}, etc.
    s = re.sub(r"\\[a-zA-Z]+", "", s)
    # Strip state subscripts like _{s}, _{(aq)}, (dil), etc.
    s = re.sub(r"_[{(]?(?:s|l|g|aq|dil|conc|heat)[)}]?", "", s, flags=re.IGNORECASE)
    # Simplify LaTeX number subscripts like _{2} -> 2
    s = re.sub(r"_{(\d+)}", r"\1", s)
    s = s.rstrip("_").strip()

    state_match = STATE_PATTERN.search(s)
    state = state_match.group(0).lower() if state_match else None
    s = STATE_PATTERN.sub("", s).strip()

    coeff = 1
    coeff_match = re.match(r"^(\d+)\s*([A-Za-z].*)$", s)
    if coeff_match:
        coeff = int(coeff_match.group(1))
        formula = coeff_match.group(2).strip()
    else:
        formula = s

    formula = formula.strip("()[]{}").rstrip("_").strip()

    return ChemicalFormula(raw=raw_formula, normalized=formula, coefficient=coeff, state=state)


def extract_chemical_formulas(text: str) -> list[ChemicalFormula]:
    if not text:
        return []

    COMMON_ENGLISH_WORDS = {
        "the", "and", "for", "with", "from", "this", "that", "page", "unit",
        "chapter", "exam", "test", "quiz", "step", "part", "note", "type",
        "high", "low", "table", "figure", "date", "name", "view", "role",
    }

    # Pre-clean LaTeX math phase notations like _{(s)}, _{(aq)}, _{(dil)}, _{2}
    clean_text = re.sub(r"_[{(]?(?:s|l|g|aq|dil|conc|heat)[)}]?", "", text, flags=re.IGNORECASE)
    clean_text = re.sub(r"_{(\d+)}", r"\1", clean_text)
    clean_text = clean_text.replace("$", " ")

    results: list[ChemicalFormula] = []
    raw_tokens = re.findall(r"[\w\(\)\+\-]+", clean_text)

    for token in raw_tokens:
        clean = STATE_PATTERN.sub("", token).strip().rstrip("_")
        clean_no_coeff = re.sub(r"^\d+", "", clean)
        if not clean_no_coeff:
            continue

        clean_strip_parens = re.sub(r"[\(\)]", "", clean_no_coeff).rstrip("_")
        if clean_strip_parens in {"I", "II", "III", "IV", "V", "VI", "VII", "VIII", "s", "l", "g", "aq", "dil", "conc"}:
            continue
        if (
            re.search(r"[A-Z][a-z]?\d+", clean_strip_parens)
            or (
                re.search(r"^[A-Z][a-z]?[A-Z][a-z]?", clean_strip_parens)
                and clean_strip_parens.lower() not in COMMON_ENGLISH_WORDS
            )
            or clean_strip_parens in [
                "Zn", "Fe", "Cu", "Al", "Ag", "Au", "Na", "Ca", "Mg", "Ba",
                "Cl2", "Br2", "I2", "F2", "H2", "O2", "N2", "HCl", "CO", "NO", "FeO"
            ]
        ):
            parsed = normalize_chemical_formula(token)
            norm = parsed.normalized.rstrip("_").strip()
            if len(norm) >= 1 and norm.lower() not in COMMON_ENGLISH_WORDS:
                parsed.normalized = norm
                results.append(parsed)

    return results


def parse_chemical_reaction(line: str) -> ChemicalReaction | None:
    if not ARROW_PATTERN.search(line):
        return None

    parts = ARROW_PATTERN.split(line, maxsplit=1)
    if len(parts) != 2:
        return None

    reactants_raw, products_raw = parts[0], parts[1]

    conditions = None
    cond_match = re.search(r"\[(.*?)\]|\((dil|conc|heat|∆|Δ)\)", products_raw, re.IGNORECASE)
    if cond_match:
        conditions = cond_match.group(0)
        products_raw = products_raw.replace(conditions, "")

    reactants = [
        normalize_chemical_formula(r.strip())
        for r in reactants_raw.split("+")
        if r.strip()
    ]
    products = [
        normalize_chemical_formula(p.strip())
        for p in products_raw.split("+")
        if p.strip()
    ]

    return ChemicalReaction(
        raw=line.strip(),
        reactants=reactants,
        products=products,
        conditions=conditions,
    )


def expand_chemistry_synonyms(query: str) -> list[str]:
    clean_q = query.lower()
    norm_ar_q = re.sub(r"[إأآا]", "ا", clean_q)
    synonyms: list[str] = []

    for ar_term, formula in _AR_TO_FORMULA.items():
        if ar_term in clean_q or ar_term in norm_ar_q:
            synonyms.append(formula)
            syn_entry = CHEMISTRY_SYNONYM_MAP.get(formula.lower())
            if syn_entry:
                synonyms.extend(syn_entry.get("english_names", []))

    extracted_formulas = extract_chemical_formulas(query)
    for f in extracted_formulas:
        f_key = f.normalized.lower()
        if f_key in CHEMISTRY_SYNONYM_MAP:
            data = CHEMISTRY_SYNONYM_MAP[f_key]
            synonyms.extend(data["arabic_names"])
            synonyms.extend(data["english_names"])

    seen = set()
    result = []
    for s in synonyms:
        s_norm = s.strip()
        if s_norm and s_norm.lower() not in seen:
            seen.add(s_norm.lower())
            result.append(s_norm)

    return result


def chemistry_aware_tokenize(text: str) -> list[str]:
    if not text:
        return []

    tokens: list[str] = []
    formulas = extract_chemical_formulas(text)
    protected_formulas = {f.normalized.lower() for f in formulas}

    raw_tokens = re.findall(r"\d+(?:\.\d+)?|[\wء-ي]+", text)

    for tok in raw_tokens:
        tok_low = tok.lower()
        if tok_low in protected_formulas:
            tokens.append(tok_low)
            continue

        if re.match(r"^\d+(?:\.\d+)?$", tok_low):
            tokens.append(tok_low)
            continue

        w = re.sub(r"[ً-ْـ]", "", tok_low)
        w = re.sub(r"[إأآا]", "ا", w)
        w = re.sub(r"[ة]", "ه", w)
        w = re.sub(r"[ى]", "ي", w)
        if len(w) >= 2:
            tokens.append(w)

    return tokens
