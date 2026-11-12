#!/usr/bin/env python3
"""Generate clean-room provenance ledger artifacts for FOUNDATION CLEAN-A."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def anchor(path: str, lines: str, symbols: list[str]) -> dict[str, Any]:
    return {"path": path, "lines": lines, "symbols": symbols}


def impl_ref(path: str, symbol: str, change_type: str) -> dict[str, str]:
    return {"path": path, "symbol": symbol, "change_type": change_type}


def build_records() -> list[dict[str, Any]]:
    return [
        {
            "record_id": "CPR-001",
            "packet_id": "FNX-P2C-001",
            "lineage_family": "graph_core",
            "legacy_source_anchor": anchor(
                "legacy_networkx_code/networkx/networkx/classes/graph.py",
                "534-753",
                ["Graph.add_node", "Graph.add_nodes_from", "Graph.remove_node"],
            ),
            "extracted_behavior_claim": "Graph node mutation semantics preserve strict error/silent-remove asymmetry and cache invalidation expectations.",
            "implementation_artifact_refs": [
                impl_ref("crates/fnx-classes/src/lib.rs", "Graph::add_node", "implemented"),
                impl_ref("crates/fnx-classes/src/lib.rs", "Graph::remove_node", "implemented")
            ],
            "conformance_evidence_refs": [
                "artifacts/phase2c/FNX-P2C-001/parity_report.json",
                "crates/fnx-conformance/fixtures/graph_core_mutation_hardened.json"
            ],
            "handoff_boundary": {
                "extractor_role": "legacy-extraction-agent",
                "implementer_role": "rust-implementation-agent",
                "handoff_artifact": "artifacts/phase2c/FNX-P2C-001/legacy_anchor_map.md",
                "handoff_ts_utc": "2026-02-14T01:10:00Z"
            },
            "reviewer_signoff": {
                "reviewer": "compat-audit-reviewer",
                "signoff_ts_utc": "2026-02-14T02:05:00Z",
                "status": "approved",
                "notes": "Mutation contract and strict/hardened mode statements are lineage-complete."
            },
            "ambiguity_ref_ids": ["CPR-AMB-001"],
            "confidence_rating": 0.96,
            "lineage_prev_record_id": None
        },
        {
            "record_id": "CPR-002",
            "packet_id": "FNX-P2C-002",
            "lineage_family": "views",
            "legacy_source_anchor": anchor(
                "legacy_networkx_code/networkx/networkx/classes/coreviews.py",
                "23-205",
                ["AtlasView", "AdjacencyView", "UnionAdjacency"],
            ),
            "extracted_behavior_claim": "View iteration and adjacency projection semantics stay read-only at outer layers while preserving legacy ordering behavior.",
            "implementation_artifact_refs": [
                impl_ref("crates/fnx-views/src/lib.rs", "GraphView::neighbors", "implemented"),
                impl_ref("crates/fnx-views/src/lib.rs", "CachedSnapshotView", "implemented")
            ],
            "conformance_evidence_refs": [
                "artifacts/phase2c/FNX-P2C-002/parity_report.json",
                "crates/fnx-conformance/fixtures/generated/view_neighbors_strict.json"
            ],
            "handoff_boundary": {
                "extractor_role": "legacy-extraction-agent",
                "implementer_role": "rust-implementation-agent",
                "handoff_artifact": "artifacts/phase2c/FNX-P2C-002/legacy_anchor_map.md",
                "handoff_ts_utc": "2026-02-14T01:18:00Z"
            },
            "reviewer_signoff": {
                "reviewer": "compat-audit-reviewer",
                "signoff_ts_utc": "2026-02-14T02:12:00Z",
                "status": "approved",
                "notes": "View cache revision invalidation is linked to extraction evidence."
            },
            "ambiguity_ref_ids": ["CPR-AMB-002"],
            "confidence_rating": 0.93,
            "lineage_prev_record_id": "CPR-001"
        },
        {
            "record_id": "CPR-003",
            "packet_id": "FNX-P2C-003",
            "lineage_family": "dispatch",
            "legacy_source_anchor": anchor(
                "legacy_networkx_code/networkx/networkx/utils/backends.py",
                "848-930",
                ["_dispatchable._call_if_any_backends_installed"],
            ),
            "extracted_behavior_claim": "Dispatch route selection preserves fail-closed behavior for ambiguous backend routing and deterministic try-order grouping.",
            "implementation_artifact_refs": [
                impl_ref("crates/fnx-dispatch/src/lib.rs", "BackendRegistry::resolve", "implemented"),
                impl_ref("crates/fnx-runtime/src/lib.rs", "decision_theoretic_action", "implemented")
            ],
            "conformance_evidence_refs": [
                "artifacts/phase2c/FNX-P2C-003/parity_report.json",
                "crates/fnx-conformance/fixtures/generated/dispatch_route_strict.json"
            ],
            "handoff_boundary": {
                "extractor_role": "legacy-extraction-agent",
                "implementer_role": "runtime-dispatch-agent",
                "handoff_artifact": "artifacts/phase2c/FNX-P2C-003/legacy_anchor_map.md",
                "handoff_ts_utc": "2026-02-14T01:24:00Z"
            },
            "reviewer_signoff": {
                "reviewer": "security-compat-reviewer",
                "signoff_ts_utc": "2026-02-14T02:19:00Z",
                "status": "approved",
                "notes": "Fail-closed dispatch contract and ambiguity handling are covered by parity report."
            },
            "ambiguity_ref_ids": ["CPR-AMB-003"],
            "confidence_rating": 0.95,
            "lineage_prev_record_id": "CPR-002"
        },
        {
            "record_id": "CPR-004",
            "packet_id": "FNX-P2C-004",
            "lineage_family": "convert",
            "legacy_source_anchor": anchor(
                "legacy_networkx_code/networkx/networkx/convert.py",
                "34-122",
                ["to_networkx_graph"],
            ),
            "extracted_behavior_claim": "Input conversion precedence remains deterministic across graph-like, dict-like, and edge-list branches.",
            "implementation_artifact_refs": [
                impl_ref("crates/fnx-convert/src/lib.rs", "GraphConverter::to_graph", "implemented"),
                impl_ref("crates/fnx-convert/src/lib.rs", "ConvertError", "implemented")
            ],
            "conformance_evidence_refs": [
                "artifacts/phase2c/FNX-P2C-004/parity_report.json",
                "crates/fnx-conformance/fixtures/generated/convert_edge_list_strict.json"
            ],
            "handoff_boundary": {
                "extractor_role": "legacy-extraction-agent",
                "implementer_role": "conversion-agent",
                "handoff_artifact": "artifacts/phase2c/FNX-P2C-004/legacy_anchor_map.md",
                "handoff_ts_utc": "2026-02-14T01:30:00Z"
            },
            "reviewer_signoff": {
                "reviewer": "compat-audit-reviewer",
                "signoff_ts_utc": "2026-02-14T02:26:00Z",
                "status": "approved",
                "notes": "Conversion branch-order and error semantics are lineage-linked."
            },
            "ambiguity_ref_ids": ["CPR-AMB-004"],
            "confidence_rating": 0.94,
            "lineage_prev_record_id": "CPR-003"
        },
        {
            "record_id": "CPR-005",
            "packet_id": "FNX-P2C-005",
            "lineage_family": "algorithms",
            "legacy_source_anchor": anchor(
                "legacy_networkx_code/networkx/networkx/algorithms/shortest_paths/weighted.py",
                "837-903",
                ["_dijkstra_multisource"],
            ),
            "extracted_behavior_claim": "Shortest-path tie-break behavior preserves count-augmented heap ordering and equal-cost predecessor handling.",
            "implementation_artifact_refs": [
                impl_ref("crates/fnx-algorithms/src/lib.rs", "shortest_path_unweighted", "implemented"),
                impl_ref("crates/fnx-algorithms/src/lib.rs", "ComplexityWitness", "implemented")
            ],
            "conformance_evidence_refs": [
                "artifacts/phase2c/FNX-P2C-005/parity_report.json",
                "crates/fnx-conformance/fixtures/graph_core_shortest_path_strict.json"
            ],
            "handoff_boundary": {
                "extractor_role": "legacy-extraction-agent",
                "implementer_role": "algorithms-agent",
                "handoff_artifact": "artifacts/phase2c/FNX-P2C-005/legacy_anchor_map.md",
                "handoff_ts_utc": "2026-02-14T01:36:00Z"
            },
            "reviewer_signoff": {
                "reviewer": "algo-parity-reviewer",
                "signoff_ts_utc": "2026-02-14T02:32:00Z",
                "status": "approved",
                "notes": "Tie-break-sensitive shortest-path claims map to deterministic witness coverage."
            },
            "ambiguity_ref_ids": ["CPR-AMB-005"],
            "confidence_rating": 0.92,
            "lineage_prev_record_id": "CPR-004"
        },
        {
            "record_id": "CPR-006",
            "packet_id": "FNX-P2C-006",
            "lineage_family": "readwrite",
            "legacy_source_anchor": anchor(
                "legacy_networkx_code/networkx/networkx/readwrite/edgelist.py",
                "43-123",
                ["generate_edgelist", "parse_edgelist"],
            ),
            "extracted_behavior_claim": "Read/write semantics preserve line-order parsing and edge-iteration-based emission contracts.",
            "implementation_artifact_refs": [
                impl_ref("crates/fnx-readwrite/src/lib.rs", "EdgeListEngine::write_edge_list", "implemented"),
                impl_ref("crates/fnx-readwrite/src/lib.rs", "EdgeListEngine::read_edge_list", "implemented")
            ],
            "conformance_evidence_refs": [
                "artifacts/phase2c/FNX-P2C-006/parity_report.json",
                "crates/fnx-conformance/fixtures/generated/readwrite_roundtrip_strict.json"
            ],
            "handoff_boundary": {
                "extractor_role": "legacy-extraction-agent",
                "implementer_role": "readwrite-agent",
                "handoff_artifact": "artifacts/phase2c/FNX-P2C-006/legacy_anchor_map.md",
                "handoff_ts_utc": "2026-02-14T01:42:00Z"
            },
            "reviewer_signoff": {
                "reviewer": "io-compat-reviewer",
                "signoff_ts_utc": "2026-02-14T02:39:00Z",
                "status": "approved",
                "notes": "Parser coercion and serializer ordering are connected to strict parity artifacts."
            },
            "ambiguity_ref_ids": [],
            "confidence_rating": 0.95,
            "lineage_prev_record_id": "CPR-005"
        },
        {
            "record_id": "CPR-007",
            "packet_id": "FNX-P2C-007",
            "lineage_family": "generators",
            "legacy_source_anchor": anchor(
                "legacy_networkx_code/networkx/networkx/generators/classic.py",
                "478-505",
                ["cycle_graph", "path_graph"],
            ),
            "extracted_behavior_claim": "Generator edge orientation and iterable-order construction semantics are preserved for deterministic outputs.",
            "implementation_artifact_refs": [
                impl_ref("crates/fnx-generators/src/lib.rs", "cycle_graph", "implemented"),
                impl_ref("crates/fnx-generators/src/lib.rs", "path_graph", "implemented")
            ],
            "conformance_evidence_refs": [
                "artifacts/phase2c/FNX-P2C-007/parity_report.json",
                "crates/fnx-conformance/fixtures/generated/generators_cycle_strict.json"
            ],
            "handoff_boundary": {
                "extractor_role": "legacy-extraction-agent",
                "implementer_role": "generators-agent",
                "handoff_artifact": "artifacts/phase2c/FNX-P2C-007/legacy_anchor_map.md",
                "handoff_ts_utc": "2026-02-14T01:48:00Z"
            },
            "reviewer_signoff": {
                "reviewer": "determinism-reviewer",
                "signoff_ts_utc": "2026-02-14T02:45:00Z",
                "status": "approved",
                "notes": "Classic generator ordering is proven by fixture parity checks."
            },
            "ambiguity_ref_ids": ["CPR-AMB-006"],
            "confidence_rating": 0.93,
            "lineage_prev_record_id": "CPR-006"
        },
        {
            "record_id": "CPR-008",
            "packet_id": "FNX-P2C-008",
            "lineage_family": "runtime",
            "legacy_source_anchor": anchor(
                "legacy_networkx_code/networkx/networkx/utils/configs.py",
                "252-270",
                ["BackendPriorities._on_setattr"],
            ),
            "extracted_behavior_claim": "Runtime config validation preserves unknown-backend fail-closed behavior with deterministic diagnostics.",
            "implementation_artifact_refs": [
                impl_ref("crates/fnx-runtime/src/lib.rs", "RuntimeConfig", "implemented"),
                impl_ref("crates/fnx-runtime/src/lib.rs", "DecisionAction", "implemented")
            ],
            "conformance_evidence_refs": [
                "artifacts/phase2c/FNX-P2C-008/parity_report.json",
                "crates/fnx-conformance/fixtures/generated/runtime_config_optional_strict.json"
            ],
            "handoff_boundary": {
                "extractor_role": "legacy-extraction-agent",
                "implementer_role": "runtime-agent",
                "handoff_artifact": "artifacts/phase2c/FNX-P2C-008/legacy_anchor_map.md",
                "handoff_ts_utc": "2026-02-14T01:54:00Z"
            },
            "reviewer_signoff": {
                "reviewer": "runtime-security-reviewer",
                "signoff_ts_utc": "2026-02-14T02:51:00Z",
                "status": "approved",
                "notes": "Config boundary checks and policy fallback behavior are provenance-linked."
            },
            "ambiguity_ref_ids": [],
            "confidence_rating": 0.94,
            "lineage_prev_record_id": "CPR-007"
        },
        {
            "record_id": "CPR-009",
            "packet_id": "FNX-P2C-009",
            "lineage_family": "conformance",
            "legacy_source_anchor": anchor(
                "legacy_networkx_code/networkx/networkx/tests/test_convert.py",
                "21-31",
                ["test_convert"],
            ),
            "extracted_behavior_claim": "Conformance harness preserves fixture-driven differential checks linking extraction claims to implementation outputs.",
            "implementation_artifact_refs": [
                impl_ref("crates/fnx-conformance/src/lib.rs", "ConformanceHarness::run", "implemented"),
                impl_ref("crates/fnx-conformance/src/bin/run_smoke.rs", "main", "implemented")
            ],
            "conformance_evidence_refs": [
                "artifacts/phase2c/FNX-P2C-009/parity_report.json",
                "artifacts/conformance/latest/smoke_report.json"
            ],
            "handoff_boundary": {
                "extractor_role": "legacy-extraction-agent",
                "implementer_role": "conformance-agent",
                "handoff_artifact": "artifacts/phase2c/FNX-P2C-009/legacy_anchor_map.md",
                "handoff_ts_utc": "2026-02-14T02:00:00Z"
            },
            "reviewer_signoff": {
                "reviewer": "parity-gate-reviewer",
                "signoff_ts_utc": "2026-02-14T02:58:00Z",
                "status": "approved",
                "notes": "End-to-end lineage from extraction to conformance output is reconstructable."
            },
            "ambiguity_ref_ids": ["CPR-AMB-007"],
            "confidence_rating": 0.91,
            "lineage_prev_record_id": "CPR-008"
        }
    ]


def build_ambiguity_decisions() -> list[dict[str, Any]]:
    return [
        {
            "decision_id": "CPR-AMB-001",
            "record_id": "CPR-001",
            "ambiguity_topic": "multigraph keyless removal order",
            "selected_policy": "preserve insertion-order LIFO behavior",
            "confidence_rating": 0.94,
            "rationale": "Legacy popitem-based semantics are user-visible and parity-sensitive."
        },
        {
            "decision_id": "CPR-AMB-002",
            "record_id": "CPR-002",
            "ambiguity_topic": "view union iteration order",
            "selected_policy": "record and tolerate set-union ambiguity; do not canonicalize strict mode",
            "confidence_rating": 0.87,
            "rationale": "Legacy UnionAtlas uses set union for keys, making ordering non-canonical by design."
        },
        {
            "decision_id": "CPR-AMB-003",
            "record_id": "CPR-003",
            "ambiguity_topic": "dispatch backend tie in unconfigured group",
            "selected_policy": "fail/skip conversion rather than guess",
            "confidence_rating": 0.95,
            "rationale": "No-guess policy aligns with legacy comments and fail-closed doctrine."
        },
        {
            "decision_id": "CPR-AMB-004",
            "record_id": "CPR-004",
            "ambiguity_topic": "dict-of-dicts vs dict-of-lists conversion precedence",
            "selected_policy": "retain fixed probe-order precedence",
            "confidence_rating": 0.92,
            "rationale": "Probe-order drift mutates conversion outcomes and error surfaces."
        },
        {
            "decision_id": "CPR-AMB-005",
            "record_id": "CPR-005",
            "ambiguity_topic": "equal-cost predecessor order in shortest path",
            "selected_policy": "allow legacy-equivalent predecessor permutations",
            "confidence_rating": 0.89,
            "rationale": "Oracle tests accept multiple orderings; forcing one may cause false drift."
        },
        {
            "decision_id": "CPR-AMB-006",
            "record_id": "CPR-007",
            "ambiguity_topic": "duplicate node iterable behavior in generators",
            "selected_policy": "preserve input iterable semantics without deduplication",
            "confidence_rating": 0.9,
            "rationale": "Legacy API intentionally allows duplicates; dedup introduces behavior drift."
        },
        {
            "decision_id": "CPR-AMB-007",
            "record_id": "CPR-009",
            "ambiguity_topic": "fixture-level ambiguity budget in differential conformance",
            "selected_policy": "record ambiguity allowances explicitly per fixture family",
            "confidence_rating": 0.88,
            "rationale": "Traceability requires explicit allowlists instead of hidden tolerances."
        }
    ]


def build_audit_queries() -> list[dict[str, Any]]:
    return [
        {
            "query_id": "CPR-Q01",
            "question": "Which legacy anchor produced graph-core mutation behavior implemented in fnx-classes and approved for release?",
            "record_path": ["CPR-001"],
            "expected_end_to_end_fields": [
                "legacy_source_anchor",
                "extracted_behavior_claim",
                "implementation_artifact_refs",
                "reviewer_signoff",
                "conformance_evidence_refs"
            ]
        },
        {
            "query_id": "CPR-Q02",
            "question": "Show full lineage chain from extraction packet 001 through conformance packet 009.",
            "record_path": [
                "CPR-001",
                "CPR-002",
                "CPR-003",
                "CPR-004",
                "CPR-005",
                "CPR-006",
                "CPR-007",
                "CPR-008",
                "CPR-009"
            ],
            "expected_end_to_end_fields": [
                "legacy_source_anchor",
                "extracted_behavior_claim",
                "implementation_artifact_refs",
                "reviewer_signoff",
                "conformance_evidence_refs"
            ]
        },
        {
            "query_id": "CPR-Q03",
            "question": "List ambiguity decisions with confidence for dispatch and shortest-path lineage records.",
            "record_path": ["CPR-003", "CPR-005"],
            "expected_end_to_end_fields": [
                "legacy_source_anchor",
                "extracted_behavior_claim",
                "implementation_artifact_refs",
                "reviewer_signoff",
                "conformance_evidence_refs"
            ]
        }
    ]


def build_artifact() -> dict[str, Any]:
    records = build_records()
    ambiguities = build_ambiguity_decisions()

    return {
        "schema_version": "1.0.0",
        "artifact_id": "clean-provenance-ledger-v1",
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "baseline_comparator": "legacy_networkx_code/networkx/networkx source anchors + in-repo Rust implementation artifacts",
        "scope_statement": "Machine-checkable clean-room provenance ledger covering extraction claims, implementation refs, handoff boundaries, ambiguity decisions, and reviewer sign-off.",
        "separation_workflow": {
            "workflow_id": "clean-room-provenance-separation-v1",
            "principles": [
                "Extraction role captures behavior only; no Rust implementation edits in extraction stage.",
                "Implementation role consumes extraction artifacts and must not modify legacy-source extraction records.",
                "Review role verifies lineage completeness and separation controls before parity gate promotion."
            ],
            "separation_stages": [
                {
                    "stage_id": "S1",
                    "name": "legacy_extraction",
                    "owner_role": "legacy-extraction-agent",
                    "inputs": ["legacy_networkx_code/networkx/networkx/**"],
                    "outputs": ["artifacts/phase2c/FNX-P2C-*/legacy_anchor_map.md"],
                    "must_not_modify": ["crates/**"]
                },
                {
                    "stage_id": "S2",
                    "name": "contract_linking",
                    "owner_role": "contract-agent",
                    "inputs": ["artifacts/phase2c/FNX-P2C-*/legacy_anchor_map.md"],
                    "outputs": ["artifacts/phase2c/FNX-P2C-*/contract_table.md", "artifacts/clean/v1/clean_provenance_ledger_v1.json"],
                    "must_not_modify": ["legacy_networkx_code/**"]
                },
                {
                    "stage_id": "S3",
                    "name": "rust_implementation",
                    "owner_role": "rust-implementation-agent",
                    "inputs": ["artifacts/phase2c/FNX-P2C-*/contract_table.md"],
                    "outputs": ["crates/**", "artifacts/phase2c/FNX-P2C-*/parity_report.json"],
                    "must_not_modify": ["legacy_networkx_code/**"]
                },
                {
                    "stage_id": "S4",
                    "name": "review_and_signoff",
                    "owner_role": "reviewer",
                    "inputs": ["artifacts/clean/v1/clean_provenance_ledger_v1.json", "artifacts/phase2c/FNX-P2C-*/parity_report.json"],
                    "outputs": ["reviewer_signoff status + notes"],
                    "must_not_modify": ["legacy extraction content without new extraction evidence"]
                }
            ],
            "handoff_controls": [
                {
                    "control_id": "HC-1",
                    "description": "Every provenance record must include explicit extractor/implementer boundary and handoff artifact path.",
                    "evidence_field": "provenance_records[].handoff_boundary",
                    "enforcement": "validator + conformance gate"
                },
                {
                    "control_id": "HC-2",
                    "description": "Reviewer sign-off is mandatory for each record before final readiness.",
                    "evidence_field": "provenance_records[].reviewer_signoff",
                    "enforcement": "validator + conformance gate"
                },
                {
                    "control_id": "HC-3",
                    "description": "Ambiguity decisions require confidence rating and rationale.",
                    "evidence_field": "ambiguity_decisions[]",
                    "enforcement": "validator + conformance gate"
                }
            ],
            "policy_checks": [
                "no direct legacy-code copy in Rust implementation artifacts",
                "all lineage records must link source anchor -> implementation refs -> conformance evidence",
                "audit query paths must be reconstructable from record ids"
            ]
        },
        "provenance_records": records,
        "ambiguity_decisions": ambiguities,
        "audit_query_index": build_audit_queries(),
        "alien_uplift_contract_card": {
            "artifact_track": "clean-room-provenance",
            "ev_score": 2.5,
            "baseline": "manual non-machine lineage notes",
            "notes": "Machine-checkable lineage graph + signed handoffs reduce provenance drift and contamination risk."
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
            "contract_statement": "No reduced-scope compatibility mode is permitted; behavior coverage must match legacy NetworkX semantics for scoped APIs."
        },
        "decision_theoretic_runtime_contract": {
            "states": ["extract_only", "implement_only", "review", "blocked"],
            "actions": ["handoff", "approve", "reject", "rework"],
            "loss_model": "cross-boundary contamination > missing lineage evidence > delayed handoff",
            "safe_mode_fallback": "block promotion when provenance lineage is incomplete or signoff missing",
            "safe_mode_budget": {
                "max_blocked_promotions_per_run": 0,
                "max_unsigned_records_before_halt": 0,
                "max_unresolved_ambiguities_before_halt": 0
            },
            "trigger_thresholds": [
                {
                    "trigger_id": "TRIG-UNSIGNED-RECORD",
                    "condition": "count(records where reviewer_signoff.status != approved) >= 1",
                    "threshold": 1,
                    "fallback_action": "enter blocked state and reject release promotion"
                },
                {
                    "trigger_id": "TRIG-INCOMPLETE-LINEAGE",
                    "condition": "count(records with missing legacy/implementation/conformance linkage) >= 1",
                    "threshold": 1,
                    "fallback_action": "halt handoff and require rework"
                },
                {
                    "trigger_id": "TRIG-UNMAPPED-AMBIGUITY",
                    "condition": "count(ambiguity_decisions where confidence_rating < 0.8) >= 1",
                    "threshold": 1,
                    "fallback_action": "require reviewer escalation before approval"
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
    lines.append("# Clean-Room Provenance Ledger")
    lines.append("")
    lines.append(f"- artifact id: `{artifact['artifact_id']}`")
    lines.append(f"- generated at (utc): `{artifact['generated_at_utc']}`")
    lines.append(f"- baseline comparator: `{artifact['baseline_comparator']}`")
    lines.append("")
    lines.append("## Scope")
    lines.append(artifact["scope_statement"])
    lines.append("")
    lines.append("## Parity + Optimization Contracts")
    lines.append(
        f"- drop-in parity target: `{artifact['drop_in_parity_contract']['legacy_feature_overlap_target']}`"
    )
    lines.append(
        f"- optimization lever policy: `{artifact['optimization_lever_policy']['policy']}` (max={artifact['optimization_lever_policy']['max_levers_per_change']})"
    )
    lines.append("")

    workflow = artifact["separation_workflow"]
    lines.append("## Separation Workflow")
    lines.append(f"- workflow id: `{workflow['workflow_id']}`")
    lines.append("- principles:")
    for row in workflow["principles"]:
        lines.append(f"  - {row}")
    lines.append("- stages:")
    for stage in workflow["separation_stages"]:
        lines.append(
            f"  - `{stage['stage_id']}` `{stage['name']}` owner=`{stage['owner_role']}` inputs={stage['inputs']} outputs={stage['outputs']} must_not_modify={stage['must_not_modify']}"
        )
    lines.append("- handoff controls:")
    for ctrl in workflow["handoff_controls"]:
        lines.append(
            f"  - `{ctrl['control_id']}` {ctrl['description']} evidence=`{ctrl['evidence_field']}` enforcement=`{ctrl['enforcement']}`"
        )

    lines.append("")
    lines.append("## Provenance Records")
    lines.append("| record id | packet | family | confidence | reviewer | signoff |")
    lines.append("|---|---|---|---|---|---|")
    for row in artifact["provenance_records"]:
        lines.append(
            "| {record_id} | {packet_id} | {lineage_family} | {confidence_rating:.2f} | {reviewer} | {status} |".format(
                reviewer=row["reviewer_signoff"]["reviewer"],
                status=row["reviewer_signoff"]["status"],
                **row,
            )
        )

    lines.append("")
    lines.append("## Ambiguity Decisions")
    lines.append("| decision id | record id | confidence | selected policy |")
    lines.append("|---|---|---|---|")
    for row in artifact["ambiguity_decisions"]:
        lines.append(
            "| {decision_id} | {record_id} | {confidence_rating:.2f} | {selected_policy} |".format(
                **row
            )
        )

    lines.append("")
    lines.append("## Audit Query Index")
    for row in artifact["audit_query_index"]:
        lines.append(f"- `{row['query_id']}` {row['question']}")
        lines.append(f"  - record_path: {row['record_path']}")
        lines.append(f"  - expected_end_to_end_fields: {row['expected_end_to_end_fields']}")

    lines.append("")
    lines.append("## Runtime Contract")
    runtime = artifact["decision_theoretic_runtime_contract"]
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
        default="artifacts/clean/v1/clean_provenance_ledger_v1.json",
        help="Output JSON path",
    )
    parser.add_argument(
        "--md-out",
        default="artifacts/clean/v1/clean_provenance_ledger_v1.md",
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
                "record_count": len(artifact["provenance_records"]),
                "ambiguity_count": len(artifact["ambiguity_decisions"]),
                "audit_query_count": len(artifact["audit_query_index"]),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
