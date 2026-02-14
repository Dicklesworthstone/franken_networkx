#!/usr/bin/env python3
"""Generate DOC-PASS-00 baseline gap matrix with quantitative expansion targets."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TARGET_DOCS = [
    "EXHAUSTIVE_LEGACY_ANALYSIS.md",
    "EXISTING_NETWORKX_STRUCTURE.md",
]

TOPIC_KEYWORDS = {
    "legacy_anchor_specificity": ["legacy", "anchor", "path", "module", "symbol"],
    "behavioral_invariants": ["invariant", "deterministic", "semantics", "contract"],
    "strict_hardened_split": ["strict", "hardened", "mode", "fail-closed", "compatibility"],
    "verification_coverage": ["unit", "property", "differential", "e2e", "test", "fuzz"],
    "performance_evidence": ["benchmark", "p95", "p99", "latency", "performance", "profile"],
    "durability_forensics": ["raptorq", "decode", "forensics", "replay", "artifact", "logging"],
    "drop_in_parity_claims": ["drop-in", "parity", "overlap", "compatibility", "oracle"],
}


@dataclass
class Section:
    doc_path: str
    level: int
    title: str
    path: str
    start_line: int
    end_line: int
    content: str


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def extract_sections(path: Path) -> list[Section]:
    lines = path.read_text(encoding="utf-8").splitlines()
    section_markers: list[dict[str, Any]] = []
    stack: list[tuple[int, str]] = []

    for idx, line in enumerate(lines, start=1):
        m = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if not m:
            continue
        level = len(m.group(1))
        title = m.group(2).strip()
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, title))
        heading_path = " > ".join(item[1] for item in stack)
        section_markers.append(
            {
                "level": level,
                "title": title,
                "path": heading_path,
                "start_line": idx,
            }
        )

    sections: list[Section] = []
    for idx, marker in enumerate(section_markers):
        start_line = marker["start_line"]
        next_start = (
            section_markers[idx + 1]["start_line"]
            if idx + 1 < len(section_markers)
            else len(lines) + 1
        )
        content_lines = lines[start_line: next_start - 1]
        content = "\n".join(content_lines).strip()
        sections.append(
            Section(
                doc_path=path.as_posix(),
                level=marker["level"],
                title=marker["title"],
                path=marker["path"],
                start_line=start_line,
                end_line=next_start - 1,
                content=content,
            )
        )
    return sections


def section_word_count(content: str) -> int:
    return len(re.findall(r"\b[0-9A-Za-z_/-]+\b", content))


def missing_topics(content: str) -> list[str]:
    lower = content.lower()
    missing = []
    for topic, keywords in TOPIC_KEYWORDS.items():
        if not any(keyword in lower for keyword in keywords):
            missing.append(topic)
    return missing


def classify_risk(title: str, word_count: int, missing_count: int) -> str:
    title_lower = title.lower()
    high_keywords = [
        "risk",
        "security",
        "compatibility",
        "contract",
        "invariant",
        "threat",
        "validation",
        "parity",
    ]
    if any(keyword in title_lower for keyword in high_keywords):
        return "high"
    if word_count < 90 or missing_count >= 5:
        return "high"
    if word_count < 180 or missing_count >= 3:
        return "medium"
    return "low"


def expansion_multiplier(risk_tier: str, word_count: int, level: int) -> float:
    base = {"high": 6.0, "medium": 4.0, "low": 2.5}[risk_tier]
    if word_count < 80:
        base += 1.0
    if level <= 2:
        base += 0.5
    return round(base, 2)


def priority_score(
    risk_tier: str, coverage_ratio: float, missing_count: int, word_count: int, level: int
) -> float:
    risk_weight = {"high": 8.0, "medium": 5.0, "low": 2.5}[risk_tier]
    depth_weight = max(0, 3 - level) * 0.75
    brevity_penalty = max(0.0, (140 - word_count) / 140.0) * 3.5
    coverage_penalty = (1.0 - coverage_ratio) * 4.0
    missing_penalty = missing_count * 0.8
    return round(risk_weight + depth_weight + brevity_penalty + coverage_penalty + missing_penalty, 3)


def doc_sha256(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return f"sha256:{digest}"


def build_gap_matrix(repo_root: Path) -> dict[str, Any]:
    all_sections: list[dict[str, Any]] = []

    for rel_path in TARGET_DOCS:
        path = repo_root / rel_path
        for section in extract_sections(path):
            words = section_word_count(section.content)
            lines = max(0, section.end_line - section.start_line)
            missing = missing_topics(section.content)
            coverage = round(
                (len(TOPIC_KEYWORDS) - len(missing)) / float(len(TOPIC_KEYWORDS)), 4
            )
            risk = classify_risk(section.title, words, len(missing))
            multiplier = expansion_multiplier(risk, words, section.level)
            target_words = max(words + 60, int(math.ceil(words * multiplier)))
            score = priority_score(risk, coverage, len(missing), words, section.level)
            section_id = (
                f"{Path(section.doc_path).name}:{section.start_line}:{slugify(section.path)}"
            )
            all_sections.append(
                {
                    "section_id": section_id,
                    "doc_path": Path(section.doc_path).name,
                    "heading_path": section.path,
                    "heading_level": section.level,
                    "start_line": section.start_line,
                    "end_line": section.end_line,
                    "current_word_count": words,
                    "current_line_count": lines,
                    "coverage_ratio": coverage,
                    "missing_topics": missing,
                    "risk_tier": risk,
                    "expansion_multiplier": multiplier,
                    "target_min_words": target_words,
                    "priority_score": score,
                    "evidence_ref": f"{Path(section.doc_path).name}#L{section.start_line}",
                }
            )

    all_sections.sort(
        key=lambda row: (
            {"high": 0, "medium": 1, "low": 2}[row["risk_tier"]],
            -row["priority_score"],
            row["doc_path"],
            row["start_line"],
        )
    )
    for idx, row in enumerate(all_sections, start=1):
        row["priority_rank"] = idx

    high_count = sum(1 for row in all_sections if row["risk_tier"] == "high")
    medium_count = sum(1 for row in all_sections if row["risk_tier"] == "medium")
    low_count = sum(1 for row in all_sections if row["risk_tier"] == "low")

    return {
        "schema_version": "1.0.0",
        "report_id": "doc-pass-00-gap-matrix-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "baseline_comparator": "legacy_networkx/main@python3.12",
        "target_docs": [
            {
                "path": rel_path,
                "source_hash": doc_sha256(repo_root / rel_path),
            }
            for rel_path in TARGET_DOCS
        ],
        "summary": {
            "section_count": len(all_sections),
            "high_risk_count": high_count,
            "medium_risk_count": medium_count,
            "low_risk_count": low_count,
            "average_expansion_multiplier": round(
                sum(row["expansion_multiplier"] for row in all_sections) / max(1, len(all_sections)),
                3,
            ),
            "total_current_words": sum(row["current_word_count"] for row in all_sections),
            "total_target_words": sum(row["target_min_words"] for row in all_sections),
        },
        "alien_uplift_contract_card": {
            "ev_score": 2.55,
            "baseline_comparator": "legacy_networkx/main@python3.12",
            "optimization_lever": "priority-sorted section expansion by quantified risk/coverage score",
            "decision_hypothesis": "Expand highest-risk, lowest-coverage sections first to maximize parity-risk reduction per editing hour.",
        },
        "profile_first_artifacts": {
            "baseline": "artifacts/perf/BASELINE_BFS_V1.md",
            "hotspot": "artifacts/perf/OPPORTUNITY_MATRIX.md",
            "delta": "artifacts/perf/phase2c/bfs_neighbor_iter_delta.json",
        },
        "decision_theoretic_runtime_contract": {
            "states": ["draft", "review", "approved", "blocked"],
            "actions": ["expand", "defer", "split", "fail_closed"],
            "loss_model": "minimize documentation ambiguity and parity drift risk while controlling expansion cost.",
            "safe_mode_fallback": "fail_closed",
            "fallback_thresholds": {
                "coverage_ratio_min": 0.55,
                "high_risk_section_requires_explicit_target": True,
            },
        },
        "isomorphism_proof_artifacts": [
            "artifacts/proofs/ISOMORPHISM_PROOF_FNX_P2C_001_V1.md",
            "artifacts/proofs/ISOMORPHISM_PROOF_FNX_P2C_009_V1.md",
        ],
        "structured_logging_evidence": [
            "artifacts/conformance/latest/structured_logs.jsonl",
            "artifacts/conformance/latest/structured_log_emitter_normalization_report.json",
        ],
        "sections": all_sections,
    }


def render_markdown(matrix: dict[str, Any]) -> str:
    summary = matrix["summary"]
    rows = matrix["sections"]
    top_rows = rows[:30]
    lines = [
        "# DOC-PASS-00 Baseline Gap Matrix (V1)",
        "",
        f"- generated_at_utc: {matrix['generated_at_utc']}",
        f"- baseline_comparator: {matrix['baseline_comparator']}",
        f"- total_sections: {summary['section_count']}",
        f"- risk_split: high={summary['high_risk_count']}, medium={summary['medium_risk_count']}, low={summary['low_risk_count']}",
        f"- words_current_to_target: {summary['total_current_words']} -> {summary['total_target_words']}",
        "",
        "## Top Priority Sections",
        "",
        "| Rank | Doc | Heading Path | Risk | Coverage | Words | Target Words | Multiplier | Missing Topics |",
        "|---:|---|---|---|---:|---:|---:|---:|---|",
    ]
    for row in top_rows:
        lines.append(
            f"| {row['priority_rank']} | `{row['doc_path']}` | `{row['heading_path']}` | {row['risk_tier']} | "
            f"{row['coverage_ratio']:.2f} | {row['current_word_count']} | {row['target_min_words']} | "
            f"{row['expansion_multiplier']:.2f} | {', '.join(row['missing_topics']) or 'none'} |"
        )

    lines.extend(
        [
            "",
            "## Expansion Rule",
            "",
            "- `target_min_words = max(current_word_count + 60, ceil(current_word_count * expansion_multiplier))`",
            "- `expansion_multiplier` is derived from risk tier + brevity + heading depth.",
            "- high-risk omissions are sorted to earliest ranks by `priority_score`.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-json",
        default="artifacts/docs/v1/doc_pass00_gap_matrix_v1.json",
        help="Output path for JSON matrix",
    )
    parser.add_argument(
        "--output-md",
        default="artifacts/docs/v1/doc_pass00_gap_matrix_v1.md",
        help="Output path for Markdown matrix summary",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    matrix = build_gap_matrix(repo_root)

    json_path = repo_root / args.output_json
    md_path = repo_root / args.output_md
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(matrix, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(matrix), encoding="utf-8")

    print(f"doc_gap_matrix_json:{json_path}")
    print(f"doc_gap_matrix_md:{md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
