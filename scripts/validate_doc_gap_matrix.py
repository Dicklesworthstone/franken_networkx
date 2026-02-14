#!/usr/bin/env python3
"""Validate DOC-PASS-00 gap matrix coverage and quantitative targets."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

TARGET_DOCS = [
    "EXHAUSTIVE_LEGACY_ANALYSIS.md",
    "EXISTING_NETWORKX_STRUCTURE.md",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def extract_heading_paths(path: Path) -> list[tuple[str, int]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    stack: list[tuple[int, str]] = []
    out: list[tuple[str, int]] = []
    for idx, line in enumerate(lines, start=1):
        m = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if not m:
            continue
        level = len(m.group(1))
        title = m.group(2).strip()
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, title))
        out.append((" > ".join(item[1] for item in stack), idx))
    return out


def ensure_keys(payload: dict[str, Any], keys: list[str], ctx: str, errors: list[str]) -> None:
    for key in keys:
        if key not in payload:
            errors.append(f"{ctx} missing key `{key}`")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--matrix",
        default="artifacts/docs/v1/doc_pass00_gap_matrix_v1.json",
        help="Path to doc gap matrix json",
    )
    parser.add_argument(
        "--schema",
        default="artifacts/docs/schema/v1/doc_pass00_gap_matrix_schema_v1.json",
        help="Path to doc gap matrix schema json",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Optional output report path",
    )
    args = parser.parse_args()

    matrix_path = Path(args.matrix)
    matrix = load_json(matrix_path)
    schema = load_json(Path(args.schema))

    errors: list[str] = []
    ensure_keys(
        matrix,
        schema["required_top_level_keys"],
        "matrix",
        errors,
    )

    summary = matrix.get("summary")
    if isinstance(summary, dict):
        ensure_keys(summary, schema["required_summary_keys"], "matrix.summary", errors)
    else:
        errors.append("matrix.summary must be an object")

    sections = matrix.get("sections")
    if not isinstance(sections, list) or not sections:
        errors.append("matrix.sections must be a non-empty list")
        sections = []

    section_rows_by_doc: dict[str, list[dict[str, Any]]] = {}
    for row in sections:
        if not isinstance(row, dict):
            errors.append("section row must be an object")
            continue
        ensure_keys(
            row,
            schema["required_section_keys"],
            "section row",
            errors,
        )
        doc = row.get("doc_path")
        if isinstance(doc, str):
            section_rows_by_doc.setdefault(doc, []).append(row)

    for doc in TARGET_DOCS:
        headings = extract_heading_paths(Path(doc))
        expected = {(path, line) for path, line in headings}
        observed = set()
        for row in section_rows_by_doc.get(doc, []):
            observed.add((row.get("heading_path"), row.get("start_line")))

            if row.get("risk_tier") not in {"high", "medium", "low"}:
                errors.append(
                    f"{doc}:{row.get('start_line')} invalid risk_tier `{row.get('risk_tier')}`"
                )
            coverage = row.get("coverage_ratio")
            if not isinstance(coverage, (int, float)) or not (0.0 <= coverage <= 1.0):
                errors.append(f"{doc}:{row.get('start_line')} coverage_ratio out of range")
            multiplier = row.get("expansion_multiplier")
            if not isinstance(multiplier, (int, float)) or multiplier < 1.5:
                errors.append(
                    f"{doc}:{row.get('start_line')} expansion_multiplier must be >= 1.5"
                )
            current_words = row.get("current_word_count")
            target_words = row.get("target_min_words")
            if not isinstance(current_words, int) or current_words < 0:
                errors.append(f"{doc}:{row.get('start_line')} invalid current_word_count")
            if not isinstance(target_words, int) or target_words < current_words:
                errors.append(
                    f"{doc}:{row.get('start_line')} target_min_words must be >= current_word_count"
                )
            if not isinstance(row.get("missing_topics"), list):
                errors.append(f"{doc}:{row.get('start_line')} missing_topics must be list")

        missing = sorted(expected.difference(observed))
        extra = sorted(observed.difference(expected))
        if missing:
            errors.append(f"{doc} missing section mappings: {missing[:10]}")
        if extra:
            errors.append(f"{doc} matrix has non-existent section mappings: {extra[:10]}")

    ranks = sorted(
        (
            row.get("priority_rank")
            for row in sections
            if isinstance(row, dict) and isinstance(row.get("priority_rank"), int)
        )
    )
    if ranks != list(range(1, len(ranks) + 1)):
        errors.append("priority_rank values must form contiguous range 1..N")

    alien = matrix.get("alien_uplift_contract_card", {})
    ev_score = alien.get("ev_score") if isinstance(alien, dict) else None
    if not isinstance(ev_score, (int, float)) or ev_score < 2.0:
        errors.append("alien_uplift_contract_card.ev_score must be >= 2.0")

    high_risk_count = sum(
        1 for row in sections if isinstance(row, dict) and row.get("risk_tier") == "high"
    )
    if high_risk_count == 0:
        errors.append("matrix must contain at least one high-risk section")

    report = {
        "schema_version": "1.0.0",
        "report_id": "doc-pass-00-gap-matrix-validation-v1",
        "matrix_path": matrix_path.as_posix(),
        "ready": len(errors) == 0,
        "error_count": len(errors),
        "errors": errors,
        "summary": {
            "section_count": len(sections),
            "high_risk_count": high_risk_count,
            "doc_count": len(TARGET_DOCS),
        },
    }

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(report, indent=2))
    return 0 if report["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
