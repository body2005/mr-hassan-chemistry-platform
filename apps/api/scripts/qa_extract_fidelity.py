"""Strict source-fidelity gate, separate from parser count/resource tests.

python -m scripts.qa_extract_fidelity --output /qa/extract-fidelity.json
Expected content is QA-only and is NEVER imported by the runtime parser.
The report retains every difference, even when counts/types are correct.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import unicodedata

from app.services.document_parsers import PARSER_OCR_VERSION, parse_knowledge_file
from app.services.exam_text_extractor import extract_distant_answer_keys, segment_exam_document


def normalized(text: str) -> str:
    # Presentation-form ligatures/diacritics and layout whitespace only.
    # Do NOT equate Arabic letters, drop negation, reorder numbers/options,
    # flatten superscripts, or repair words using the expected answer.
    text = "".join(unicodedata.normalize("NFKC", c) if "\ufb50" <= c <= "\ufeff" else c for c in text)
    text = re.sub(r"[\u064b-\u065f\u0670\u200e\u200f\u202a-\u202e\u2066-\u2069]", "", text)
    text = re.sub(r"\.{3,}", "<blank>", text)
    # PDF span assembly may surround punctuation with layout spaces. Values,
    # signs, exponents and order are retained; only those spaces are removed.
    text = re.sub(r"\s*([,°.|−])\s*", r"\1", text)
    return re.sub(r"\s+", " ", text).strip()


def distance(a: str, b: str) -> int:
    previous = list(range(len(b) + 1))
    for i, ac in enumerate(a, 1):
        current = [i]
        for j, bc in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[-1] + 1, previous[j - 1] + (ac != bc)))
        previous = current
    return previous[-1]


def compare(filename: str, path: Path, expected: list) -> dict:
    doc = parse_knowledge_file(file_path=str(path), filename=filename)
    actual = segment_exam_document(doc, distant_keys=extract_distant_answer_keys(doc), filename=filename)
    differences, correct = [], 0
    char_errors = total_chars = 0
    for index in range(max(len(expected), len(actual))):
        exp = expected[index] if index < len(expected) else None
        got = actual[index] if index < len(actual) else None
        if exp is None or got is None:
            differences.append({"number": index + 1, "kind": "extra" if exp is None else "missing", "expected": exp, "actual": got})
            continue
        kind, stem, *option_field = exp
        opts = option_field[0] if option_field else []
        got_opts = [o["text"] for o in got.get("options") or []]
        issue = {}
        if kind != got["canonical_type"]:
            issue["type"] = [kind, got["canonical_type"]]
        if normalized(stem) != normalized(got["question_text"]):
            issue["stem"] = [stem, got["question_text"]]
        if [normalized(o) for o in opts] != [normalized(o) for o in got_opts]:
            issue["ordered_options"] = [opts, got_opts]
        if got.get("correct_answer") or any(o.get("is_correct") for o in got.get("options") or []):
            issue["invented_answer"] = got.get("correct_answer") or got["options"]
        if got.get("points") is not None:
            issue["invented_marks"] = got["points"]
        for source, parsed in [(stem, got["question_text"]), *zip(opts, got_opts)]:
            source, parsed = normalized(source), normalized(parsed)
            char_errors += distance(source, parsed)
            total_chars += len(source)
        if issue:
            differences.append({"number": index + 1, **issue, "needs_content_review": got.get("needs_content_review")})
        else:
            correct += 1
    return {"filename": filename, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "expected_count": len(expected), "actual_count": len(actual), "fully_matching_questions": correct,
            "character_error_rate": char_errors / max(1, total_chars), "differences": differences,
            "ocr_pages": doc.ocr_pages, "raw_pages": [p.raw_text for p in doc.pages],
            "actual": actual, "passed": not differences}


def main() -> None:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--fixtures", type=Path, default=Path(__file__).resolve().parents[1] / "tests/fixtures/blind_inputs")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads((args.fixtures / "reference.json").read_text(encoding="utf-8"))
    cases = dict(manifest["files"])
    for name, ref in manifest["image_reference"].items():
        cases[name] = cases[ref["pdf"]][:ref["first_questions"]]
    results = [compare(name, args.fixtures / name, expected) for name, expected in cases.items()]
    report = {"parser_ocr_version": PARSER_OCR_VERSION, "provenance": manifest["provenance"], "results": results,
              "passed": sum(r["passed"] for r in results), "failed": sum(not r["passed"] for r in results), "skipped": 0}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("parser_ocr_version", "passed", "failed", "skipped")}))
    for item in results:
        print(json.dumps({k: item[k] for k in ("filename", "expected_count", "actual_count", "fully_matching_questions", "character_error_rate")}, ensure_ascii=False))
    raise SystemExit(1 if report["failed"] else 0)


if __name__ == "__main__":
    main()
