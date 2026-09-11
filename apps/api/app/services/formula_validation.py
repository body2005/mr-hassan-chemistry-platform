"""Non-destructive math and chemistry formula extraction/validation."""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.chemistry_normalizer import extract_chemical_formulas, parse_chemical_reaction


MATH_FORMULA_RE = re.compile(r"(?<!\w)(?:[A-Za-z]\w*|\d+)(?:\s*[+\-*/=^]\s*(?:[A-Za-z]\w*|\d+|\([^\n()]+\)))+(?!\w)")


@dataclass
class FormulaValidation:
    raw: str
    kind: str
    valid: bool
    normalized: str


def extract_and_validate_formulas(text: str) -> list[FormulaValidation]:
    results: list[FormulaValidation] = []
    for reaction_line in text.splitlines():
        reaction = parse_chemical_reaction(reaction_line)
        if reaction:
            results.append(FormulaValidation(reaction.raw, "chemical_reaction", True, reaction.raw))
    seen = {result.raw for result in results}
    for formula in extract_chemical_formulas(text):
        if formula.normalized not in seen:
            results.append(FormulaValidation(formula.raw, "chemical_formula", True, formula.normalized))
            seen.add(formula.normalized)
    try:
        from sympy import sympify  # type: ignore[import-not-found]
        from sympy.parsing.sympy_parser import convert_xor, standard_transformations

        for match in MATH_FORMULA_RE.finditer(text):
            raw = match.group(0).strip()
            if raw in seen or len(raw) > 300:
                continue
            expression = raw.split("=", 1)[0].strip()
            try:
                normalized = str(sympify(expression, transformations=standard_transformations + (convert_xor,)))
                results.append(FormulaValidation(raw, "math", True, normalized))
            except Exception:
                results.append(FormulaValidation(raw, "math", False, raw))
            seen.add(raw)
    except ImportError:
        pass
    return results
