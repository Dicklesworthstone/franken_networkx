#!/usr/bin/env python3
"""Generate final logging gate report and release checklist artifacts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class GateCheck:
    name: str
    passed: bool
    details: str
    evidence_paths: list[str]


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    latest = root / "artifacts" / "conformance" / "latest"

    smoke_report = latest / "smoke_report.json"
    structured_logs = latest / "structured_logs.jsonl"
    normalization_report = latest / "structured_log_emitter_normalization_report.json"
    unblock_matrix = latest / "telemetry_dependent_unblock_matrix_v1.json"
    durability_report = latest / "durability_pipeline_report.json"

    checks: list[GateCheck] = []

    smoke_exists = smoke_report.exists()
    structured_exists = structured_logs.exists()
    checks.append(
        GateCheck(
            name="core_artifacts_present",
            passed=smoke_exists and structured_exists,
            details="smoke_report + structured_logs artifacts are present",
            evidence_paths=[str(smoke_report), str(structured_logs)],
        )
    )

    normalization_data = read_json(normalization_report) if normalization_report.exists() else None
    normalization_passed = bool(
        normalization_data
        and normalization_data.get("valid_log_count") == normalization_data.get("fixture_count")
        and normalization_data.get("normalized_fields")
    )
    checks.append(
        GateCheck(
            name="emitter_normalization",
            passed=normalization_passed,
            details=(
                "normalization report exists and valid_log_count == fixture_count "
                "with non-empty normalized_fields"
            ),
            evidence_paths=[str(normalization_report)],
        )
    )

    matrix_data = read_json(unblock_matrix) if unblock_matrix.exists() else None
    matrix_rows = matrix_data.get("rows", []) if matrix_data else []
    matrix_passed = bool(
        matrix_data
        and matrix_data.get("source_bead_id") == "bd-315.5.4"
        and any(row.get("blocked_bead_id") == "bd-315.5.5" for row in matrix_rows)
        and any(row.get("blocked_bead_id") == "bd-315.21" for row in matrix_rows)
    )
    checks.append(
        GateCheck(
            name="dependent_unblock_matrix",
            passed=matrix_passed,
            details=(
                "dependent-unblock matrix exists, is sourced from bd-315.5.4, "
                "and includes key downstream rows"
            ),
            evidence_paths=[str(unblock_matrix)],
        )
    )

    durability_data = read_json(durability_report) if durability_report.exists() else None
    entries = durability_data.get("entries", []) if durability_data else []
    durability_passed = bool(
        durability_data
        and len(entries) >= 4
        and all(entry.get("decode_proof_count", 0) >= 1 for entry in entries)
        and all(entry.get("scrub_status") == "Ok" for entry in entries)
    )
    checks.append(
        GateCheck(
            name="durability_decode_proofs",
            passed=durability_passed,
            details=(
                "durability pipeline report includes >=4 artifacts and each has "
                "scrub_status=Ok with decode_proof_count>=1"
            ),
            evidence_paths=[str(durability_report)],
        )
    )

    gate_passed = all(check.passed for check in checks)
    generated_at = datetime.now(timezone.utc).isoformat()

    report_payload = {
        "schema_version": "1.0.0",
        "generated_at_utc": generated_at,
        "gate_id": "LOGC-F",
        "source_bead_id": "bd-315.5.6",
        "status": "pass" if gate_passed else "fail",
        "checks": [
            {
                "name": check.name,
                "passed": check.passed,
                "details": check.details,
                "evidence_paths": check.evidence_paths,
            }
            for check in checks
        ],
        "downstream_release_targets": [
            "bd-315.21",
            "bd-315.6.1",
            "bd-315.7.1",
            "bd-315.8.1",
        ],
    }

    report_path = latest / "logging_final_gate_report_v1.json"
    report_path.write_text(json.dumps(report_payload, indent=2) + "\n", encoding="utf-8")

    checklist_lines = [
        "# Logging Final Release Checklist (LOGC-F)",
        "",
        f"- generated_at_utc: {generated_at}",
        f"- gate_status: {'PASS' if gate_passed else 'FAIL'}",
        "",
        "## Gate Checks",
    ]
    for check in checks:
        checkbox = "x" if check.passed else " "
        checklist_lines.append(f"- [{checkbox}] `{check.name}`: {check.details}")
        for evidence_path in check.evidence_paths:
            checklist_lines.append(f"  - evidence: `{evidence_path}`")

    checklist_lines.extend(
        [
            "",
            "## Downstream Release Targets",
            "- [ ] `bd-315.21`",
            "- [ ] `bd-315.6.1`",
            "- [ ] `bd-315.7.1`",
            "- [ ] `bd-315.8.1`",
            "",
            "Gate must remain PASS at release time.",
            "",
        ]
    )
    checklist_path = latest / "logging_release_checklist_v1.md"
    checklist_path.write_text("\n".join(checklist_lines), encoding="utf-8")

    print(f"logging_gate_report:{report_path}")
    print(f"logging_release_checklist:{checklist_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
