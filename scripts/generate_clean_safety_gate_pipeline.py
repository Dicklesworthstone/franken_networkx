#!/usr/bin/env python3
"""Generate clean safety gate pipeline artifacts."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def build_artifact() -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "artifact_id": "clean-safety-gate-pipeline-v1",
        "generated_at_utc": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "gate_matrix": [
            {
                "gate_id": "GATE-STATIC-FMT",
                "gate_type": "static",
                "command": "rch exec -- cargo fmt --check",
                "owner": "release-engineering",
                "pass_condition": "rustfmt clean across workspace",
                "fail_condition": "any formatting diff",
                "output_artifact": "artifacts/clean/latest/clean_safety_gate_pipeline_validation_v1.json",
                "reproducibility": {
                    "local": "rch exec -- cargo fmt --check",
                    "ci": "cargo fmt --check"
                }
            },
            {
                "gate_id": "GATE-STATIC-CLIPPY",
                "gate_type": "static",
                "command": "rch exec -- cargo clippy --workspace --all-targets -- -D warnings",
                "owner": "quality-engineering",
                "pass_condition": "no clippy warnings or lint denials",
                "fail_condition": "any clippy warning/error",
                "output_artifact": "artifacts/conformance/latest/logging_final_gate_report_v1.json",
                "reproducibility": {
                    "local": "rch exec -- cargo clippy --workspace --all-targets -- -D warnings",
                    "ci": "cargo clippy --workspace --all-targets -- -D warnings"
                }
            },
            {
                "gate_id": "GATE-DYNAMIC-UNSAFE-POLICY",
                "gate_type": "dynamic",
                "command": "rch exec -- cargo test -p fnx-conformance clean_unsafe_policy_defaults_are_fail_closed -- --exact --nocapture",
                "owner": "safety-audit",
                "pass_condition": "unsafe policy gate passes with fail-closed defaults",
                "fail_condition": "forbid coverage missing, unmapped unsafe, or invalid exception metadata",
                "output_artifact": "artifacts/clean/latest/clean_unsafe_policy_validation_v1.json",
                "reproducibility": {
                    "local": "rch exec -- cargo test -p fnx-conformance clean_unsafe_policy_defaults_are_fail_closed -- --exact --nocapture",
                    "ci": "cargo test -p fnx-conformance clean_unsafe_policy_defaults_are_fail_closed -- --exact --nocapture"
                }
            },
            {
                "gate_id": "GATE-DYNAMIC-PROVENANCE",
                "gate_type": "dynamic",
                "command": "rch exec -- cargo test -p fnx-conformance clean_provenance_ledger_is_lineage_complete_and_separated -- --exact --nocapture",
                "owner": "compat-audit",
                "pass_condition": "lineage + handoff + ambiguity contracts remain complete",
                "fail_condition": "missing lineage links, invalid signoff, or unresolved ambiguities",
                "output_artifact": "artifacts/clean/latest/clean_provenance_validation_v1.json",
                "reproducibility": {
                    "local": "rch exec -- cargo test -p fnx-conformance clean_provenance_ledger_is_lineage_complete_and_separated -- --exact --nocapture",
                    "ci": "cargo test -p fnx-conformance clean_provenance_ledger_is_lineage_complete_and_separated -- --exact --nocapture"
                }
            },
            {
                "gate_id": "GATE-DYNAMIC-READWRITE-PARSER",
                "gate_type": "dynamic",
                "command": "rch exec -- cargo test -p fnx-conformance --test smoke -- --nocapture",
                "owner": "io-hardening",
                "pass_condition": "read/write parser scenarios remain deterministic and fail-closed",
                "fail_condition": "parser drift or malformed-input handling regressions",
                "output_artifact": "artifacts/conformance/latest/generated_readwrite_roundtrip_strict_json.report.json",
                "reproducibility": {
                    "local": "rch exec -- cargo test -p fnx-conformance --test smoke -- --nocapture",
                    "ci": "cargo test -p fnx-conformance --test smoke -- --nocapture"
                }
            },
            {
                "gate_id": "GATE-DYNAMIC-RUNTIME-STATE",
                "gate_type": "dynamic",
                "command": "rch exec -- cargo test -p fnx-conformance --test structured_log_gate -- --nocapture",
                "owner": "runtime-safety",
                "pass_condition": "state transitions + deterministic replay metadata remain intact",
                "fail_condition": "missing replay metadata or state-transition invariants",
                "output_artifact": "artifacts/conformance/latest/generated_runtime_config_optional_strict_json.report.json",
                "reproducibility": {
                    "local": "rch exec -- cargo test -p fnx-conformance --test structured_log_gate -- --nocapture",
                    "ci": "cargo test -p fnx-conformance --test structured_log_gate -- --nocapture"
                }
            }
        ],
        "high_risk_coverage": [
            {
                "target_id": "HR-READWRITE-PARSER",
                "category": "parser",
                "risk_level": "high",
                "coverage_modes": ["unit", "property", "differential", "e2e"],
                "entrypoint_path": "crates/fnx-readwrite/src/lib.rs",
                "fixtures": [
                    "crates/fnx-conformance/fixtures/generated/readwrite_roundtrip_strict.json",
                    "artifacts/conformance/latest/generated_readwrite_roundtrip_strict_json.report.json"
                ],
                "triage_bucket": "parser-malformed-input"
            },
            {
                "target_id": "HR-RUNTIME-STATE",
                "category": "state_transition",
                "risk_level": "high",
                "coverage_modes": ["unit", "property", "differential", "e2e"],
                "entrypoint_path": "crates/fnx-runtime/src/lib.rs",
                "fixtures": [
                    "crates/fnx-conformance/fixtures/generated/runtime_config_optional_strict.json",
                    "artifacts/conformance/latest/generated_runtime_config_optional_strict_json.report.json"
                ],
                "triage_bucket": "state-transition-invariant"
            },
            {
                "target_id": "HR-UNSAFE-POLICY",
                "category": "policy",
                "risk_level": "high",
                "coverage_modes": ["unit", "property", "differential", "e2e"],
                "entrypoint_path": "crates/fnx-conformance/tests/clean_unsafe_policy_gate.rs",
                "fixtures": [
                    "artifacts/clean/latest/clean_unsafe_policy_validation_v1.json",
                    "artifacts/conformance/latest/logging_final_gate_report_v1.json"
                ],
                "triage_bucket": "policy-regression"
            }
        ],
        "execution_workflows": {
            "local_commands": [
                "rch exec -- cargo fmt --check",
                "rch exec -- cargo clippy --workspace --all-targets -- -D warnings",
                "rch exec -- cargo test -p fnx-conformance clean_unsafe_policy_defaults_are_fail_closed -- --exact --nocapture",
                "rch exec -- cargo test -p fnx-conformance clean_provenance_ledger_is_lineage_complete_and_separated -- --exact --nocapture"
            ],
            "ci_commands": [
                "cargo fmt --check",
                "cargo clippy --workspace --all-targets -- -D warnings",
                "cargo test -p fnx-conformance --tests -- --nocapture"
            ],
            "determinism_notes": "All gate commands are stable, seedless checks against deterministic fixture artifacts and versioned reports."
        },
        "artifact_index": [
            {
                "artifact_id": "clean_unsafe_policy_validation",
                "path": "artifacts/clean/latest/clean_unsafe_policy_validation_v1.json",
                "producer_gate_id": "GATE-DYNAMIC-UNSAFE-POLICY"
            },
            {
                "artifact_id": "clean_provenance_validation",
                "path": "artifacts/clean/latest/clean_provenance_validation_v1.json",
                "producer_gate_id": "GATE-DYNAMIC-PROVENANCE"
            },
            {
                "artifact_id": "readwrite_roundtrip_report",
                "path": "artifacts/conformance/latest/generated_readwrite_roundtrip_strict_json.report.json",
                "producer_gate_id": "GATE-DYNAMIC-READWRITE-PARSER"
            },
            {
                "artifact_id": "runtime_config_report",
                "path": "artifacts/conformance/latest/generated_runtime_config_optional_strict_json.report.json",
                "producer_gate_id": "GATE-DYNAMIC-RUNTIME-STATE"
            },
            {
                "artifact_id": "structured_logging_gate_report",
                "path": "artifacts/conformance/latest/logging_final_gate_report_v1.json",
                "producer_gate_id": "GATE-STATIC-CLIPPY"
            },
            {
                "artifact_id": "clean_safety_gate_pipeline_validation",
                "path": "artifacts/clean/latest/clean_safety_gate_pipeline_validation_v1.json",
                "producer_gate_id": "GATE-STATIC-FMT"
            }
        ],
        "triage_taxonomy": [
            {
                "bucket_id": "parser-malformed-input",
                "severity": "high",
                "description": "Malformed-input parser failures, coercion drift, and fail-open regressions.",
                "owner_role": "io-hardening",
                "response_sla_hours": 8
            },
            {
                "bucket_id": "state-transition-invariant",
                "severity": "high",
                "description": "Invalid runtime state transitions, invariant breaks, and replay mismatch.",
                "owner_role": "runtime-safety",
                "response_sla_hours": 8
            },
            {
                "bucket_id": "policy-regression",
                "severity": "critical",
                "description": "Unsafe-policy regressions, exception metadata drift, or fail-open behavior.",
                "owner_role": "safety-audit",
                "response_sla_hours": 4
            },
            {
                "bucket_id": "performance-guardrail",
                "severity": "medium",
                "description": "Unexpected gate-runtime or memory regressions that violate safety budget assumptions.",
                "owner_role": "quality-engineering",
                "response_sla_hours": 24
            }
        ],
        "alien_uplift_contract_card": {
            "artifact_track": "clean-safety-gate-pipeline",
            "ev_score": 2.4,
            "baseline": "ad hoc safety checks with weak ownership and artifact links",
            "notes": "Gate matrix + risk-target taxonomy + artifact index improves reproducibility and safety triage quality."
        },
        "profile_first_artifacts": {
            "baseline": "artifacts/perf/phase2c/perf_baseline_matrix_v1.json",
            "hotspot": "artifacts/perf/phase2c/hotspot_one_lever_backlog_v1.json",
            "delta": "artifacts/perf/phase2c/perf_regression_gate_report_v1.json"
        },
        "optimization_lever_policy": {
            "policy": "exactly_one_optimization_lever_per_change",
            "evidence_path": "artifacts/perf/phase2c/hotspot_one_lever_backlog_v1.json",
            "max_levers_per_change": 1
        },
        "drop_in_parity_contract": {
            "legacy_feature_overlap_target": "100%",
            "intentional_capability_gaps": [],
            "contract_statement": "Safety hardening must preserve scoped legacy-observable behavior and deterministic ties/output contracts."
        },
        "decision_theoretic_runtime_contract": {
            "states": ["green", "yellow", "red", "blocked"],
            "actions": ["run_gate", "escalate", "triage", "block_release"],
            "loss_model": "missed high-risk regression > false-negative gate pass > delayed release",
            "safe_mode_fallback": "block release when any required safety gate fails or artifact index cannot be reconstructed",
            "safe_mode_budget": {
                "max_failed_required_gates": 0,
                "max_unmapped_high_risk_targets": 0,
                "max_missing_artifact_links": 0
            },
            "trigger_thresholds": [
                {
                    "trigger_id": "TRIG-FAILED-REQUIRED-GATE",
                    "condition": "count(required gates with failed status) >= 1",
                    "threshold": 1,
                    "fallback_action": "enter blocked state and deny promotion"
                },
                {
                    "trigger_id": "TRIG-MISSING-HIGH-RISK-COVERAGE",
                    "condition": "count(high-risk targets missing property/fuzz evidence) >= 1",
                    "threshold": 1,
                    "fallback_action": "enter blocked state and require coverage repair"
                },
                {
                    "trigger_id": "TRIG-MISSING-ARTIFACT-LINK",
                    "condition": "count(artifact index paths that do not resolve) >= 1",
                    "threshold": 1,
                    "fallback_action": "block release and force artifact regeneration"
                }
            ]
        },
        "isomorphism_proof_artifacts": [
            "artifacts/proofs/ISOMORPHISM_PROOF_FNX_P2C_001_V1.md",
            "artifacts/proofs/ISOMORPHISM_PROOF_FNX_P2C_005_V1.md",
            "artifacts/proofs/ISOMORPHISM_PROOF_FNX_P2C_009_V1.md"
        ],
        "structured_logging_evidence": [
            "artifacts/conformance/latest/structured_logs.json",
            "artifacts/conformance/latest/structured_logs.jsonl",
            "artifacts/conformance/latest/logging_final_gate_report_v1.json"
        ]
    }


def render_markdown(artifact: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Clean Safety Gate Pipeline")
    lines.append("")
    lines.append(f"- artifact id: `{artifact['artifact_id']}`")
    lines.append(f"- generated at (utc): `{artifact['generated_at_utc']}`")
    lines.append("")

    lines.append("## Gate Matrix")
    lines.append("| gate id | type | owner | output artifact |")
    lines.append("|---|---|---|---|")
    for row in artifact["gate_matrix"]:
        lines.append(
            f"| {row['gate_id']} | {row['gate_type']} | {row['owner']} | {row['output_artifact']} |"
        )

    lines.append("")
    lines.append("## High-Risk Coverage")
    lines.append("| target id | category | risk | coverage modes | triage bucket |")
    lines.append("|---|---|---|---|---|")
    for row in artifact["high_risk_coverage"]:
        lines.append(
            f"| {row['target_id']} | {row['category']} | {row['risk_level']} | {row['coverage_modes']} | {row['triage_bucket']} |"
        )

    lines.append("")
    lines.append("## Artifact Index")
    for row in artifact["artifact_index"]:
        lines.append(
            f"- `{row['artifact_id']}` path=`{row['path']}` producer=`{row['producer_gate_id']}`"
        )

    lines.append("")
    lines.append("## Runtime Contract")
    runtime = artifact["decision_theoretic_runtime_contract"]
    lines.append(f"- states: {runtime['states']}")
    lines.append(f"- actions: {runtime['actions']}")
    lines.append(f"- loss model: {runtime['loss_model']}")
    lines.append(f"- safe mode fallback: {runtime['safe_mode_fallback']}")
    lines.append(f"- safe mode budget: {runtime['safe_mode_budget']}")

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--json-out",
        default="artifacts/clean/v1/clean_safety_gate_pipeline_v1.json",
        help="Output JSON path",
    )
    parser.add_argument(
        "--md-out",
        default="artifacts/clean/v1/clean_safety_gate_pipeline_v1.md",
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
                "gate_count": len(artifact["gate_matrix"]),
                "high_risk_target_count": len(artifact["high_risk_coverage"]),
                "artifact_index_count": len(artifact["artifact_index"]),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
