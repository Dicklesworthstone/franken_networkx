#!/usr/bin/env python3
"""Generate DOC-PASS-03 data model/state/invariant mapping artifact."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_JSON = REPO_ROOT / "artifacts/docs/v1/doc_pass03_data_model_state_invariant_v1.json"
OUTPUT_MD = REPO_ROOT / "artifacts/docs/v1/doc_pass03_data_model_state_invariant_v1.md"


def component(
    component_id: str,
    name: str,
    legacy_scope_paths: list[str],
    rust_crates: list[str],
    mutable_fields: list[str],
    transitions: list[dict[str, Any]],
    invariants: list[dict[str, Any]],
    ambiguity_tags: list[dict[str, Any]],
    verification_hooks: dict[str, list[str]],
) -> dict[str, Any]:
    return {
        "component_id": component_id,
        "name": name,
        "legacy_scope_paths": legacy_scope_paths,
        "rust_crates": rust_crates,
        "state_model": {
            "states": sorted(
                {
                    transition["from_state"]
                    for transition in transitions
                }.union({transition["to_state"] for transition in transitions})
            ),
            "mutable_fields": mutable_fields,
            "mutability_boundary": "mutations must preserve deterministic observable API contract",
        },
        "state_transitions": transitions,
        "invariants": invariants,
        "ambiguity_tags": ambiguity_tags,
        "verification_hooks": verification_hooks,
    }


def build_payload() -> dict[str, Any]:
    components = [
        component(
            component_id="graph_store",
            name="Graph Adjacency Store",
            legacy_scope_paths=[
                "networkx/classes/graph.py",
                "networkx/classes/digraph.py",
                "networkx/classes/multigraph.py",
            ],
            rust_crates=["fnx-classes"],
            mutable_fields=["nodes", "adjacency", "attrs", "revision"],
            transitions=[
                {
                    "from_state": "empty",
                    "to_state": "mutating",
                    "trigger": "add_node/add_edge",
                    "guards": ["input node/edge shape valid"],
                    "action": "apply mutation in deterministic endpoint order",
                    "failure_behavior": "fail_closed",
                },
                {
                    "from_state": "mutating",
                    "to_state": "stable",
                    "trigger": "mutation commit",
                    "guards": ["adjacency invariants satisfied"],
                    "action": "increment revision and publish snapshot",
                    "failure_behavior": "rollback_then_fail_closed",
                },
            ],
            invariants=[
                {
                    "invariant_id": "GM-INV-001",
                    "statement": "Adjacency map remains symmetric for undirected graph mode.",
                    "severity": "critical",
                    "strict_mode_response": "fail_closed",
                    "hardened_mode_response": "rollback_then_fail_closed_with_audit",
                    "recovery_steps": ["discard partial mutation", "emit forensics bundle reference"],
                    "test_hooks": [
                        "unit::fnx_classes::adjacency_symmetry",
                        "property::fnx_classes::mutation_invariants",
                        "differential::graph_core_mutation_hardened",
                    ],
                },
                {
                    "invariant_id": "GM-INV-002",
                    "statement": "Revision counter increments exactly once per committed mutation.",
                    "severity": "high",
                    "strict_mode_response": "fail_closed",
                    "hardened_mode_response": "fail_closed_with_diagnostic",
                    "recovery_steps": ["reset to last stable snapshot"],
                    "test_hooks": ["unit::fnx_classes::revision_increments_on_mutation"],
                },
            ],
            ambiguity_tags=[
                {
                    "topic": "edge attribute merge precedence on repeated add_edge",
                    "policy_options": [
                        "last-write-wins",
                        "first-write-wins",
                        "merge-reject",
                    ],
                    "selected_policy": "last-write-wins",
                    "risk_note": "divergence here causes observable mismatch in edge attrs",
                }
            ],
            verification_hooks={
                "unit": [
                    "fnx_classes::tests::add_edge_autocreates_nodes_and_preserves_order",
                    "fnx_classes::tests::repeated_edge_updates_attrs_in_place",
                ],
                "property": ["property::fnx_classes::mutation_invariants"],
                "differential": ["fixture::graph_core_mutation_hardened"],
                "e2e": ["phase2c-readiness step: run_smoke_harness"],
            },
        ),
        component(
            component_id="view_cache",
            name="View Cache and Projection Layer",
            legacy_scope_paths=[
                "networkx/classes/coreviews.py",
                "networkx/classes/graphviews.py",
            ],
            rust_crates=["fnx-views", "fnx-classes"],
            mutable_fields=["cached_snapshot", "parent_revision", "filters"],
            transitions=[
                {
                    "from_state": "cache_cold",
                    "to_state": "cache_hot",
                    "trigger": "first view read",
                    "guards": ["graph revision known"],
                    "action": "build deterministic cached snapshot",
                    "failure_behavior": "fail_closed",
                },
                {
                    "from_state": "cache_hot",
                    "to_state": "cache_stale",
                    "trigger": "parent graph revision change",
                    "guards": ["revision mismatch observed"],
                    "action": "mark stale before serving reads",
                    "failure_behavior": "fail_closed",
                },
                {
                    "from_state": "cache_stale",
                    "to_state": "cache_hot",
                    "trigger": "refresh",
                    "guards": ["new snapshot validates ordering invariants"],
                    "action": "recompute snapshot deterministically",
                    "failure_behavior": "reset_cache_then_fail_closed",
                },
            ],
            invariants=[
                {
                    "invariant_id": "VW-INV-001",
                    "statement": "View neighbor ordering must match canonical graph ordering.",
                    "severity": "high",
                    "strict_mode_response": "fail_closed",
                    "hardened_mode_response": "cache_reset_then_fail_closed",
                    "recovery_steps": ["drop stale cache", "recompute from stable graph snapshot"],
                    "test_hooks": [
                        "unit::fnx_views::view_preserves_deterministic_ordering",
                        "differential::view_neighbors_strict",
                    ],
                }
            ],
            ambiguity_tags=[
                {
                    "topic": "cache invalidation timing under rapid mutation",
                    "policy_options": ["lazy_invalid", "eager_invalid"],
                    "selected_policy": "eager_invalid",
                    "risk_note": "lazy invalidation can leak stale view semantics",
                }
            ],
            verification_hooks={
                "unit": ["fnx_views::tests::cached_snapshot_refreshes_on_revision_change"],
                "property": ["property::fnx_views::cache_coherence"],
                "differential": ["fixture::generated/view_neighbors_strict"],
                "e2e": ["phase2c-readiness step: run_smoke_harness"],
            },
        ),
        component(
            component_id="dispatch_registry",
            name="Backend Dispatch Registry",
            legacy_scope_paths=["networkx/utils/backends.py"],
            rust_crates=["fnx-dispatch", "fnx-runtime"],
            mutable_fields=["backend_specs", "decision_ledger"],
            transitions=[
                {
                    "from_state": "registered",
                    "to_state": "resolved",
                    "trigger": "dispatch_resolve",
                    "guards": ["compatible backend exists", "unknown_incompatible_feature == false"],
                    "action": "select backend by priority then lexical tie-break",
                    "failure_behavior": "fail_closed",
                },
                {
                    "from_state": "registered",
                    "to_state": "rejected",
                    "trigger": "dispatch_resolve",
                    "guards": ["unknown_incompatible_feature == true OR no compatible backend"],
                    "action": "emit decision ledger fail_closed record",
                    "failure_behavior": "fail_closed",
                },
            ],
            invariants=[
                {
                    "invariant_id": "DP-INV-001",
                    "statement": "Unknown incompatible feature always yields fail_closed.",
                    "severity": "critical",
                    "strict_mode_response": "fail_closed",
                    "hardened_mode_response": "fail_closed",
                    "recovery_steps": ["none (explicit rejection path)"],
                    "test_hooks": [
                        "unit::fnx_dispatch::strict_mode_rejects_unknown_incompatible_request",
                        "differential::generated/dispatch_route_strict",
                    ],
                }
            ],
            ambiguity_tags=[
                {
                    "topic": "equal-priority backend tie-break",
                    "policy_options": ["first_registered", "lexical_name", "randomized"],
                    "selected_policy": "lexical_name",
                    "risk_note": "non-deterministic tie-break breaks reproducibility",
                }
            ],
            verification_hooks={
                "unit": ["fnx_dispatch::tests::deterministic_priority_selects_highest_then_name"],
                "property": ["property::fnx_dispatch::deterministic_selection"],
                "differential": ["fixture::generated/dispatch_route_strict"],
                "e2e": ["phase2c-readiness step: run_smoke_harness"],
            },
        ),
        component(
            component_id="conversion_readwrite",
            name="Conversion and Read/Write Pipeline",
            legacy_scope_paths=[
                "networkx/convert.py",
                "networkx/readwrite/edgelist.py",
            ],
            rust_crates=["fnx-convert", "fnx-readwrite"],
            mutable_fields=["parse_cursor", "warnings", "graph_builder_state"],
            transitions=[
                {
                    "from_state": "parsing",
                    "to_state": "parsed",
                    "trigger": "input row accepted",
                    "guards": ["schema-conformant row"],
                    "action": "append normalized edge",
                    "failure_behavior": "fail_closed",
                },
                {
                    "from_state": "parsing",
                    "to_state": "recovered",
                    "trigger": "malformed row in hardened mode",
                    "guards": ["bounded recovery budget available"],
                    "action": "skip row and emit warning",
                    "failure_behavior": "fail_closed_when_budget_exhausted",
                },
            ],
            invariants=[
                {
                    "invariant_id": "RW-INV-001",
                    "statement": "Round-trip serialization must be deterministic for scoped formats.",
                    "severity": "high",
                    "strict_mode_response": "fail_closed",
                    "hardened_mode_response": "fail_closed_with_diagnostics",
                    "recovery_steps": ["emit mismatch report and reproduction command"],
                    "test_hooks": [
                        "unit::fnx_readwrite::round_trip_is_deterministic",
                        "differential::generated/readwrite_roundtrip_strict",
                    ],
                }
            ],
            ambiguity_tags=[
                {
                    "topic": "malformed line tolerance",
                    "policy_options": ["strict_reject", "bounded_skip"],
                    "selected_policy": "strict_reject (strict) / bounded_skip (hardened)",
                    "risk_note": "overly permissive parsing can hide incompatibilities",
                }
            ],
            verification_hooks={
                "unit": ["fnx_readwrite::tests::strict_mode_fails_closed_for_malformed_line"],
                "property": ["property::fnx_readwrite::roundtrip_stability"],
                "differential": ["fixture::generated/readwrite_hardened_malformed"],
                "e2e": ["phase2c-readiness step: run_smoke_harness"],
            },
        ),
        component(
            component_id="algo_conformance",
            name="Algorithm Engine and Conformance Harness",
            legacy_scope_paths=[
                "networkx/algorithms/shortest_paths/weighted.py",
                "networkx/algorithms/centrality/",
                "networkx/algorithms/components/",
                "networkx/tests/",
            ],
            rust_crates=["fnx-algorithms", "fnx-conformance"],
            mutable_fields=["work_queue", "witness", "mismatch_vector", "structured_logs"],
            transitions=[
                {
                    "from_state": "fixture_loaded",
                    "to_state": "executing",
                    "trigger": "run_fixture",
                    "guards": ["fixture parses cleanly"],
                    "action": "execute operations and capture witness",
                    "failure_behavior": "emit failed fixture report",
                },
                {
                    "from_state": "executing",
                    "to_state": "validated",
                    "trigger": "expected checks complete",
                    "guards": ["mismatch_count == 0"],
                    "action": "emit structured_test_log + forensics bundle index",
                    "failure_behavior": "emit mismatch taxonomy + repro metadata",
                },
            ],
            invariants=[
                {
                    "invariant_id": "CF-INV-001",
                    "statement": "Packet routing for structured logs is deterministic by fixture family.",
                    "severity": "high",
                    "strict_mode_response": "fail_closed",
                    "hardened_mode_response": "fail_closed_with_audit",
                    "recovery_steps": ["re-run fixture with deterministic packet mapping checks"],
                    "test_hooks": [
                        "unit::fnx_conformance::packet_id_for_fixture",
                        "integration::smoke_emits_structured_logs_with_replay_metadata",
                    ],
                },
                {
                    "invariant_id": "CF-INV-002",
                    "statement": "E2E/readiness scripts emit deterministic step-level logs with replay references.",
                    "severity": "medium",
                    "strict_mode_response": "fail_closed",
                    "hardened_mode_response": "fail_closed_with_diagnostic",
                    "recovery_steps": ["re-run e2e script and compare step hash chain"],
                    "test_hooks": [
                        "script::run_phase2c_readiness_e2e.sh",
                        "script::run_doc_pass00_gap_matrix.sh",
                    ],
                },
            ],
            ambiguity_tags=[
                {
                    "topic": "fixture-to-packet routing fallback behavior",
                    "policy_options": ["foundation_fallback", "hard_error"],
                    "selected_policy": "foundation_fallback",
                    "risk_note": "hard error would reduce coverage for uncategorized fixtures",
                }
            ],
            verification_hooks={
                "unit": ["fnx_conformance::tests::smoke_harness_reports_zero_drift_for_bootstrap_fixtures"],
                "property": ["property::fnx_conformance::log_schema_invariants"],
                "differential": ["fixture::all_generated_fixtures"],
                "e2e": [
                    "script::run_phase2c_readiness_e2e.sh",
                    "script::run_doc_pass00_gap_matrix.sh",
                ],
            },
        ),
    ]

    return {
        "schema_version": "1.0.0",
        "artifact_id": "doc-pass-03-data-model-state-invariant-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "baseline_comparator": "legacy_networkx/main@python3.12",
        "components": components,
        "alien_uplift_contract_card": {
            "ev_score": 2.45,
            "baseline_comparator": "legacy_networkx/main@python3.12",
            "optimization_lever": "single-source state/invariant tables for faster packet extraction passes",
            "decision_hypothesis": "Explicit state machine contracts reduce downstream extraction ambiguity and rework.",
        },
        "profile_first_artifacts": {
            "baseline": "artifacts/perf/BASELINE_BFS_V1.md",
            "hotspot": "artifacts/perf/OPPORTUNITY_MATRIX.md",
            "delta": "artifacts/perf/phase2c/bfs_neighbor_iter_delta.json",
        },
        "decision_theoretic_runtime_contract": {
            "states": ["stable", "mutating", "validated", "failed"],
            "actions": ["commit", "rollback", "quarantine", "fail_closed"],
            "loss_model": "minimize semantic drift and silent state corruption risk",
            "safe_mode_fallback": "fail_closed",
            "fallback_thresholds": {
                "invariant_violation_count_max": 0,
                "unknown_state_transition_allowed": False,
            },
        },
        "isomorphism_proof_artifacts": [
            "artifacts/proofs/ISOMORPHISM_PROOF_FNX_P2C_001_V1.md",
            "artifacts/proofs/ISOMORPHISM_PROOF_FNX_P2C_005_V1.md",
            "artifacts/proofs/ISOMORPHISM_PROOF_FNX_P2C_009_V1.md",
        ],
        "structured_logging_evidence": [
            "artifacts/conformance/latest/structured_logs.jsonl",
            "artifacts/conformance/latest/structured_log_emitter_normalization_report.json",
            "artifacts/phase2c/latest/phase2c_readiness_e2e_steps_v1.jsonl",
        ],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# DOC-PASS-03 Data Model, State, and Invariant Mapping (V1)",
        "",
        f"- generated_at_utc: {payload['generated_at_utc']}",
        f"- baseline_comparator: {payload['baseline_comparator']}",
        "",
        "## Component Matrix",
        "",
        "| Component | Mutable Fields | Transition Count | Invariant Count |",
        "|---|---|---:|---:|",
    ]
    for component_row in payload["components"]:
        lines.append(
            f"| `{component_row['component_id']}` | "
            f"{', '.join(component_row['state_model']['mutable_fields'])} | "
            f"{len(component_row['state_transitions'])} | "
            f"{len(component_row['invariants'])} |"
        )
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- Strict mode invariant violations are fail-closed.",
            "- Hardened mode allows bounded recovery only when explicitly documented and auditable.",
            "- Each invariant row maps to unit/property/differential/e2e hooks.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    payload = build_payload()
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    OUTPUT_MD.write_text(render_markdown(payload), encoding="utf-8")
    print(f"doc_pass03_json:{OUTPUT_JSON}")
    print(f"doc_pass03_md:{OUTPUT_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
