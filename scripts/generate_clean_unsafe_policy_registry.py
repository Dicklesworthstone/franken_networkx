#!/usr/bin/env python3
"""Generate clean-room unsafe policy + exception registry artifacts."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


WORKSPACE_CRATES = [
    "fnx-classes",
    "fnx-views",
    "fnx-dispatch",
    "fnx-convert",
    "fnx-algorithms",
    "fnx-generators",
    "fnx-readwrite",
    "fnx-durability",
    "fnx-conformance",
    "fnx-runtime",
]

UNSAFE_TOKEN_RE = re.compile(r"\bunsafe\b")


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def scan_forbid_and_unsafe(root: Path) -> tuple[list[str], list[dict[str, Any]]]:
    missing_forbid: list[str] = []
    unsafe_findings: list[dict[str, Any]] = []

    for crate in WORKSPACE_CRATES:
        crate_src = root / "crates" / crate / "src"
        lib_path = crate_src / "lib.rs"
        if not lib_path.exists() or "#![forbid(unsafe_code)]" not in lib_path.read_text(
            encoding="utf-8"
        ):
            missing_forbid.append(f"crates/{crate}/src/lib.rs")

        for rs_path in crate_src.rglob("*.rs"):
            rel_path = rs_path.relative_to(root).as_posix()
            for idx, line in enumerate(rs_path.read_text(encoding="utf-8").splitlines(), start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                if stripped.startswith("//"):
                    continue
                if "forbid(unsafe_code)" in stripped:
                    continue
                if UNSAFE_TOKEN_RE.search(stripped):
                    unsafe_findings.append(
                        {
                            "path": rel_path,
                            "line": idx,
                            "snippet": stripped[:160],
                        }
                    )

    return missing_forbid, unsafe_findings


def build_artifact() -> dict[str, Any]:
    root = repo_root()
    missing_forbid, unsafe_findings = scan_forbid_and_unsafe(root)

    return {
        "schema_version": "1.0.0",
        "artifact_id": "clean-unsafe-exception-registry-v1",
        "generated_at_utc": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "policy_defaults": {
            "workspace_default": "#![forbid(unsafe_code)] required in every workspace crate root",
            "lint_gate": "cargo clippy --workspace --all-targets -- -D warnings",
            "ci_enforcement": "deny release if forbid-missing or unresolved unsafe findings are present",
            "unknown_unsafe_behavior": "fail_closed",
        },
        "coverage_snapshot": {
            "workspace_crates": [f"crates/{crate}" for crate in WORKSPACE_CRATES],
            "forbid_unsafe_missing": missing_forbid,
            "unsafe_findings": unsafe_findings,
        },
        "exception_registry": [],
        "fail_closed_controls": [
            {
                "control_id": "UFC-1",
                "description": "Unknown unsafe usage blocks promotion by default.",
                "trigger": "unsafe_findings.count > approved_exceptions.count",
                "action": "deny release and require explicit exception registration",
            },
            {
                "control_id": "UFC-2",
                "description": "Missing crate-level forbid attribute is treated as policy violation.",
                "trigger": "forbid_unsafe_missing.count >= 1",
                "action": "deny release and require crate-level policy restoration",
            },
            {
                "control_id": "UFC-3",
                "description": "Expired exception records are invalid without renewal.",
                "trigger": "approved exception expires_at_utc < now",
                "action": "deny release until renewal or revocation",
            },
        ],
        "audit_enforcement": {
            "scanner_command": "rg -n --glob 'crates/**/src/*.rs' '#![forbid(unsafe_code)]|unsafe\\s*\\{|unsafe\\s+fn|extern\\s+\"C\"'",
            "ci_gate": "cargo clippy --workspace --all-targets -- -D warnings && cargo test -p fnx-conformance clean_unsafe_policy_defaults_are_fail_closed -- --exact --nocapture",
            "renewal_command": "update exception status/expiry + link mitigation evidence before CI rerun",
            "registry_policy": "exceptions must remain empty unless narrowly justified and fully reviewed",
        },
        "alien_uplift_contract_card": {
            "artifact_track": "clean-room-unsafe-policy",
            "ev_score": 2.3,
            "baseline": "ad hoc unsafe review without machine-checkable registry",
            "notes": "Fail-closed registry + conformance gate reduces accidental unsafe drift and ownership gaps.",
        },
        "profile_first_artifacts": {
            "baseline": "artifacts/perf/phase2c/perf_baseline_matrix_v1.json",
            "hotspot": "artifacts/perf/phase2c/hotspot_one_lever_backlog_v1.json",
            "delta": "artifacts/perf/phase2c/perf_regression_gate_report_v1.json",
        },
        "optimization_lever_policy": {
            "policy": "exactly_one_optimization_lever_per_change",
            "evidence_path": "artifacts/perf/phase2c/hotspot_one_lever_backlog_v1.json",
            "max_levers_per_change": 1,
        },
        "drop_in_parity_contract": {
            "legacy_feature_overlap_target": "100%",
            "intentional_capability_gaps": [],
            "contract_statement": "No reduced-scope compatibility profile is permitted; safety hardening cannot alter observable scoped behavior.",
        },
        "decision_theoretic_runtime_contract": {
            "states": ["clean", "exception_pending", "exception_approved", "blocked"],
            "actions": ["scan", "approve_exception", "revoke_exception", "block_release"],
            "loss_model": "undocumented unsafe usage > expired exception usage > delayed release",
            "safe_mode_fallback": "block release whenever scanner findings exceed approved exception budget",
            "safe_mode_budget": {
                "max_unmapped_unsafe_findings": 0,
                "max_expired_approved_exceptions": 0,
                "max_missing_forbid_crates": 0,
            },
            "trigger_thresholds": [
                {
                    "trigger_id": "TRIG-UNMAPPED-UNSAFE",
                    "condition": "unsafe_findings.count > approved_exceptions.count",
                    "threshold": 1,
                    "fallback_action": "enter blocked state and reject release",
                },
                {
                    "trigger_id": "TRIG-MISSING-FORBID",
                    "condition": "forbid_unsafe_missing.count >= 1",
                    "threshold": 1,
                    "fallback_action": "enter blocked state and require policy repair",
                },
                {
                    "trigger_id": "TRIG-EXPIRED-EXCEPTION",
                    "condition": "approved exception expires_at_utc < now",
                    "threshold": 1,
                    "fallback_action": "revoke exception and block release until renewed",
                },
            ],
        },
        "isomorphism_proof_artifacts": [
            "artifacts/proofs/ISOMORPHISM_PROOF_FNX_P2C_001_V1.md",
            "artifacts/proofs/ISOMORPHISM_PROOF_FNX_P2C_005_V1.md",
            "artifacts/proofs/ISOMORPHISM_PROOF_FNX_P2C_009_V1.md",
        ],
        "structured_logging_evidence": [
            "artifacts/conformance/latest/structured_logs.json",
            "artifacts/conformance/latest/structured_logs.jsonl",
            "artifacts/conformance/latest/logging_final_gate_report_v1.json",
        ],
    }


def render_markdown(artifact: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Clean Unsafe Policy + Exception Registry")
    lines.append("")
    lines.append(f"- artifact id: `{artifact['artifact_id']}`")
    lines.append(f"- generated at (utc): `{artifact['generated_at_utc']}`")
    lines.append("")

    policy = artifact["policy_defaults"]
    lines.append("## Policy Defaults")
    lines.append(f"- workspace default: {policy['workspace_default']}")
    lines.append(f"- lint gate: `{policy['lint_gate']}`")
    lines.append(f"- ci enforcement: {policy['ci_enforcement']}")
    lines.append(f"- unknown unsafe behavior: `{policy['unknown_unsafe_behavior']}`")
    lines.append("")

    snapshot = artifact["coverage_snapshot"]
    lines.append("## Coverage Snapshot")
    lines.append(f"- workspace crates: {snapshot['workspace_crates']}")
    lines.append(f"- forbid missing: {snapshot['forbid_unsafe_missing']}")
    lines.append(f"- unsafe findings count: {len(snapshot['unsafe_findings'])}")
    lines.append("")

    lines.append("## Fail-Closed Controls")
    for control in artifact["fail_closed_controls"]:
        lines.append(
            f"- `{control['control_id']}` trigger=`{control['trigger']}` action={control['action']}"
        )
    lines.append("")

    runtime = artifact["decision_theoretic_runtime_contract"]
    lines.append("## Runtime Contract")
    lines.append(f"- states: {runtime['states']}")
    lines.append(f"- actions: {runtime['actions']}")
    lines.append(f"- loss model: {runtime['loss_model']}")
    lines.append(f"- safe mode fallback: {runtime['safe_mode_fallback']}")
    lines.append(f"- safe mode budget: {runtime['safe_mode_budget']}")
    lines.append("- trigger thresholds:")
    for row in runtime["trigger_thresholds"]:
        lines.append(
            f"  - `{row['trigger_id']}` condition={row['condition']} threshold={row['threshold']} fallback={row['fallback_action']}"
        )

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--json-out",
        default="artifacts/clean/v1/clean_unsafe_exception_registry_v1.json",
        help="Output JSON path",
    )
    parser.add_argument(
        "--md-out",
        default="artifacts/clean/v1/clean_unsafe_exception_registry_v1.md",
        help="Output markdown path",
    )
    args = parser.parse_args()

    root = repo_root()
    artifact = build_artifact()

    json_path = root / args.json_out
    md_path = root / args.md_out
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)

    json_path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(artifact), encoding="utf-8")

    print(
        json.dumps(
            {
                "artifact_json": str(json_path.relative_to(root)),
                "artifact_markdown": str(md_path.relative_to(root)),
                "workspace_crate_count": len(artifact["coverage_snapshot"]["workspace_crates"]),
                "forbid_missing_count": len(
                    artifact["coverage_snapshot"]["forbid_unsafe_missing"]
                ),
                "unsafe_finding_count": len(artifact["coverage_snapshot"]["unsafe_findings"]),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
