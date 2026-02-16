#!/usr/bin/env python3
"""Generate DOC-PASS-04 execution-path tracing artifact."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_JSON = REPO_ROOT / "artifacts/docs/v1/doc_pass04_execution_path_tracing_v1.json"
OUTPUT_MD = REPO_ROOT / "artifacts/docs/v1/doc_pass04_execution_path_tracing_v1.md"

BASELINE_COMPARATOR = "legacy_networkx/main@python3.12"
PROFILE_FIRST_ARTIFACTS = {
    "baseline": "artifacts/perf/phase2c/perf_baseline_matrix_v1.json",
    "hotspot": "artifacts/perf/phase2c/hotspot_one_lever_backlog_v1.json",
    "delta": "artifacts/perf/phase2c/perf_regression_gate_report_v1.json",
}
OPTIMIZATION_LEVER_POLICY = {
    "rule": "exactly_one_optimization_lever_per_change",
    "evidence_path": "artifacts/perf/phase2c/hotspot_one_lever_backlog_v1.json",
}
ALIEN_UPLIFT_CONTRACT_CARD = {
    "ev_score": 2.21,
    "baseline_comparator": BASELINE_COMPARATOR,
    "expected_value_statement": (
        "Explicit execution-path tracing reduces behavioral ambiguity and tightens replayable "
        "parity guarantees under strict/hardened branching."
    ),
}
DECISION_THEORETIC_RUNTIME_CONTRACT = {
    "states": ["trace", "branch", "fallback", "verify", "fail_closed"],
    "actions": [
        "record_branch",
        "bind_fallback",
        "attach_forensics_link",
        "emit_replay_command",
        "fail_closed",
    ],
    "loss_model": (
        "Minimize expected compatibility loss by ensuring every control-flow branch and fallback "
        "is explicitly documented and replay-linked."
    ),
    "loss_budget": {
        "max_expected_loss": 0.02,
        "max_untracked_branches": 0,
        "max_missing_fallback_paths": 0,
    },
    "safe_mode_fallback": {
        "trigger_thresholds": {
            "missing_execution_paths": 1,
            "missing_branch_paths": 1,
            "missing_fallback_paths": 1,
            "missing_verification_links": 1,
        },
        "fallback_action": "halt publication and emit fail-closed diagnostics",
        "budgeted_recovery_window_ms": 30000,
    },
}
ISOMORPHISM_PROOF_ARTIFACTS = [
    "artifacts/perf/phase2c/isomorphism_harness_report_v1.json",
    "artifacts/perf/phase2c/isomorphism_golden_signatures_v1.json",
]
STRUCTURED_LOGGING_EVIDENCE = [
    "artifacts/conformance/latest/structured_logs.jsonl",
    "artifacts/e2e/latest/e2e_script_pack_events_v1.jsonl",
    "artifacts/e2e/latest/e2e_script_pack_bundle_index_v1.json",
    "artifacts/e2e/latest/e2e_script_pack_replay_report_v1.json",
]

BEAD_TITLES = {
    "bd-315.24.5": "[DOC-PASS-04] Execution-Path Tracing and Control-Flow Narratives",
    "bd-315.24.10": "[DOC-PASS-09] Unit/E2E Test Corpus and Logging Evidence Crosswalk",
    "bd-315.23": "[FOUNDATION] Coverage/Flake Budgets + Reliability Gates",
    "bd-315.10": "[FOUNDATION] CI Gate Topology (G1..G8) + Failure Forensics",
    "bd-315.6": "[FOUNDATION] E2E Orchestrator + Replay/Forensics Logging",
    "bd-315.5": "[FOUNDATION] Unit/Property Test Conventions + Structured Log Contract",
    "bd-315.26.4": "[ASUP-D] E2E Recovery Scenarios + Decode-Proof Replay",
}

WORKFLOW_BLUEPRINTS = [
    {
        "path_id": "graph_mutation_lifecycle",
        "title": "Graph Mutation and Fail-Closed Edge Admission",
        "subsystem_family": "graph-storage",
        "objective": "Mutate adjacency/edge state deterministically while enforcing strict fail-closed metadata policy.",
        "entrypoints": [
            ("fnx-classes", "crates/fnx-classes/src/lib.rs", "Graph::add_node_with_attrs", "pub fn add_node_with_attrs"),
            ("fnx-classes", "crates/fnx-classes/src/lib.rs", "Graph::add_edge_with_attrs", "pub fn add_edge_with_attrs"),
            ("fnx-classes", "crates/fnx-classes/src/lib.rs", "Graph::remove_node", "pub fn remove_node"),
        ],
        "steps": [
            ("mutation_intent", "Capture mutation intent and existing-node/attribute evidence."),
            ("compatibility_gate", "Evaluate incompatibility probability and strict/hardened decision action."),
            ("state_commit", "Apply deterministic node/edge mutations and revision bump only on state change."),
        ],
        "branches": [
            {
                "branch_id": "unknown_feature_fail_closed",
                "condition": "Unknown incompatible edge metadata encountered.",
                "strict_behavior": "Return GraphError::FailClosed before state mutation.",
                "hardened_behavior": "Also fail closed to preserve compatibility contract.",
                "fallback_behavior": "Emit evidence ledger record with reason `unknown_incompatible_feature`.",
                "outcome": "mutation_rejected",
                "anchor_symbol": "Graph::add_edge_with_attrs",
            },
            {
                "branch_id": "autocreate_missing_nodes",
                "condition": "Edge endpoint not present in node table.",
                "strict_behavior": "Autocreate endpoint nodes and continue.",
                "hardened_behavior": "Autocreate endpoint nodes and continue.",
                "fallback_behavior": "Record left/right autocreate signals in evidence ledger.",
                "outcome": "mutation_committed",
                "anchor_symbol": "Graph::add_edge_with_attrs",
            },
        ],
        "fallbacks": [
            {
                "fallback_id": "graph_mutation_forensics",
                "branch_id": "unknown_feature_fail_closed",
                "trigger": "DecisionAction::FailClosed",
                "recovery_actions": [
                    "preserve prior graph snapshot",
                    "emit deterministic replay command",
                    "attach structured log forensics bundle ref",
                ],
                "terminal_state": "fail_closed",
                "evidence_refs": [
                    "artifacts/conformance/latest/structured_logs.jsonl",
                    "artifacts/e2e/latest/e2e_script_pack_replay_report_v1.json",
                ],
            }
        ],
        "verification_links": {
            "unit": [
                "fnx_classes::tests::add_edge_autocreates_nodes_and_preserves_order",
                "fnx_classes::tests::remove_node_removes_incident_edges",
            ],
            "property": ["property::fnx_classes::mutation_invariants"],
            "differential": ["fixture::graph_core_mutation_hardened"],
            "e2e": ["scripts/run_e2e_script_pack_gate.sh::happy_path"],
        },
        "linked_bead_ids": ["bd-315.24.5", "bd-315.24.10", "bd-315.23", "bd-315.10"],
        "replay_command": "rch exec -- cargo test -q -p fnx-classes --lib -- --nocapture",
        "structured_log_refs": [
            "artifacts/conformance/latest/structured_logs.jsonl",
            "artifacts/e2e/latest/e2e_script_pack_events_v1.jsonl",
        ],
        "risk_notes": [
            "Fail-closed branch must not partially mutate adjacency maps.",
            "Autocreate path must preserve deterministic insertion order.",
        ],
    },
    {
        "path_id": "view_cache_projection_refresh",
        "title": "Graph View Projection and Cached Snapshot Refresh",
        "subsystem_family": "graph-view-api",
        "objective": "Serve deterministic read views while refreshing stale cache snapshots on revision drift.",
        "entrypoints": [
            ("fnx-views", "crates/fnx-views/src/lib.rs", "GraphView::neighbors", "pub fn neighbors(&self, node: &str)"),
            ("fnx-views", "crates/fnx-views/src/lib.rs", "CachedSnapshotView::is_stale", "pub fn is_stale(&self, graph: &Graph)"),
            ("fnx-views", "crates/fnx-views/src/lib.rs", "CachedSnapshotView::refresh_if_stale", "pub fn refresh_if_stale(&mut self, graph: &Graph)"),
        ],
        "steps": [
            ("projection_read", "Resolve live graph projection for nodes/edges/neighbors."),
            ("stale_detection", "Compare cached revision with graph revision."),
            ("cache_refresh", "Refresh snapshot only when revision drift is observed."),
        ],
        "branches": [
            {
                "branch_id": "cache_fresh_no_refresh",
                "condition": "Cached revision matches current graph revision.",
                "strict_behavior": "Return cached snapshot unchanged.",
                "hardened_behavior": "Return cached snapshot unchanged.",
                "fallback_behavior": "No-op branch with deterministic snapshot identity.",
                "outcome": "cache_hot",
                "anchor_symbol": "CachedSnapshotView::refresh_if_stale",
            },
            {
                "branch_id": "cache_stale_refresh",
                "condition": "Cached revision differs from graph revision.",
                "strict_behavior": "Rebuild snapshot and update cached revision.",
                "hardened_behavior": "Rebuild snapshot and update cached revision.",
                "fallback_behavior": "Force snapshot recomputation before returning reads.",
                "outcome": "cache_refreshed",
                "anchor_symbol": "CachedSnapshotView::refresh_if_stale",
            },
        ],
        "fallbacks": [
            {
                "fallback_id": "view_refresh_recompute",
                "branch_id": "cache_stale_refresh",
                "trigger": "revision_mismatch",
                "recovery_actions": [
                    "discard stale snapshot",
                    "recompute from graph snapshot",
                    "record updated revision anchor",
                ],
                "terminal_state": "cache_hot",
                "evidence_refs": [
                    "artifacts/conformance/latest/structured_logs.jsonl",
                    "artifacts/e2e/latest/e2e_script_pack_events_v1.jsonl",
                ],
            }
        ],
        "verification_links": {
            "unit": ["fnx_views::tests::cached_snapshot_refreshes_on_revision_change"],
            "property": ["property::fnx_views::cache_coherence"],
            "differential": ["fixture::view_neighbors_strict"],
            "e2e": ["scripts/run_e2e_script_pack_gate.sh::edge_path"],
        },
        "linked_bead_ids": ["bd-315.24.5", "bd-315.24.10", "bd-315.23"],
        "replay_command": "rch exec -- cargo test -q -p fnx-views --lib -- --nocapture",
        "structured_log_refs": [
            "artifacts/conformance/latest/structured_logs.jsonl",
            "artifacts/e2e/latest/e2e_script_pack_bundle_index_v1.json",
        ],
        "risk_notes": [
            "Snapshot staleness branch must always refresh before read exposure.",
            "View ordering must remain deterministic across refreshes.",
        ],
    },
    {
        "path_id": "dispatch_resolution_runtime",
        "title": "Compatibility-Aware Dispatch Resolution",
        "subsystem_family": "compat-dispatch",
        "objective": "Resolve backend deterministically with fail-closed handling for incompatible requests.",
        "entrypoints": [
            ("fnx-dispatch", "crates/fnx-dispatch/src/lib.rs", "BackendRegistry::resolve", "pub fn resolve("),
            ("fnx-dispatch", "crates/fnx-dispatch/src/lib.rs", "BackendRegistry::record_dispatch", "fn record_dispatch("),
            ("fnx-runtime", "crates/fnx-runtime/src/lib.rs", "decision_theoretic_action", "pub fn decision_theoretic_action("),
        ],
        "steps": [
            ("risk_scoring", "Compute decision action from mode, risk probability, and incompatibility feature flag."),
            ("backend_filtering", "Filter backend registry by mode permissions and required features."),
            ("deterministic_selection", "Select backend by priority then lexical order and log decision evidence."),
        ],
        "branches": [
            {
                "branch_id": "dispatch_unknown_feature_fail_closed",
                "condition": "unknown_incompatible_feature=true",
                "strict_behavior": "Fail closed and return DispatchError::FailClosed.",
                "hardened_behavior": "Fail closed and return DispatchError::FailClosed.",
                "fallback_behavior": "Persist ledger entry tagged unknown_incompatible_feature.",
                "outcome": "dispatch_rejected",
                "anchor_symbol": "BackendRegistry::resolve",
            },
            {
                "branch_id": "dispatch_no_backend",
                "condition": "No backend satisfies compatibility + feature constraints.",
                "strict_behavior": "Return DispatchError::NoCompatibleBackend.",
                "hardened_behavior": "Return DispatchError::NoCompatibleBackend.",
                "fallback_behavior": "Record reason code `no_compatible_backend` for forensics.",
                "outcome": "dispatch_rejected",
                "anchor_symbol": "BackendRegistry::resolve",
            },
        ],
        "fallbacks": [
            {
                "fallback_id": "dispatch_failure_forensics",
                "branch_id": "dispatch_unknown_feature_fail_closed",
                "trigger": "decision_action_fail_closed",
                "recovery_actions": [
                    "emit deterministic dispatch replay command",
                    "capture requested backend and required feature evidence",
                    "link failure reason code in structured logs",
                ],
                "terminal_state": "fail_closed",
                "evidence_refs": [
                    "artifacts/conformance/latest/structured_logs.jsonl",
                    "artifacts/e2e/latest/e2e_script_pack_replay_report_v1.json",
                ],
            }
        ],
        "verification_links": {
            "unit": [
                "fnx_dispatch::tests::strict_mode_rejects_unknown_incompatible_request",
                "fnx_dispatch::tests::deterministic_priority_selects_highest_then_name",
            ],
            "property": ["property::fnx_dispatch::deterministic_selection"],
            "differential": ["fixture::dispatch_route_strict"],
            "e2e": ["scripts/run_e2e_script_pack_gate.sh::malformed_input"],
        },
        "linked_bead_ids": ["bd-315.24.5", "bd-315.24.10", "bd-315.10", "bd-315.23"],
        "replay_command": "rch exec -- cargo test -q -p fnx-dispatch --lib -- --nocapture",
        "structured_log_refs": [
            "artifacts/conformance/latest/structured_logs.jsonl",
            "artifacts/e2e/latest/e2e_script_pack_events_v1.jsonl",
        ],
        "risk_notes": [
            "Dispatch fail-closed branches must not silently degrade to alternate backends.",
        ],
    },
    {
        "path_id": "conversion_payload_ingest",
        "title": "Conversion Ingest (Edge List + Adjacency)",
        "subsystem_family": "conversion-ingest",
        "objective": "Convert external graph payloads into native graph state with strict/hardened parsing branches.",
        "entrypoints": [
            ("fnx-convert", "crates/fnx-convert/src/lib.rs", "GraphConverter::from_edge_list", "pub fn from_edge_list("),
            ("fnx-convert", "crates/fnx-convert/src/lib.rs", "GraphConverter::from_adjacency", "pub fn from_adjacency("),
            ("fnx-convert", "crates/fnx-convert/src/lib.rs", "GraphConverter::record", "fn record("),
        ],
        "steps": [
            ("dispatch_gate", "Resolve conversion backend compatibility contract."),
            ("node_edge_parse", "Parse payload rows and classify malformed/empty identifiers."),
            ("graph_apply", "Apply converted rows into graph mutation API with warning accumulation."),
        ],
        "branches": [
            {
                "branch_id": "convert_strict_malformed_fail_closed",
                "condition": "Strict mode receives malformed node/edge payload.",
                "strict_behavior": "Return ConvertError::FailClosed and stop conversion.",
                "hardened_behavior": "Not applicable (hardened path differs).",
                "fallback_behavior": "Emit fail-closed ledger event with malformed payload context.",
                "outcome": "conversion_failed",
                "anchor_symbol": "GraphConverter::from_edge_list",
            },
            {
                "branch_id": "convert_hardened_warn_skip",
                "condition": "Hardened mode receives malformed row.",
                "strict_behavior": "Not applicable (strict fails closed).",
                "hardened_behavior": "Record warning + FullValidate and skip malformed row.",
                "fallback_behavior": "Continue conversion with deterministic warning list.",
                "outcome": "conversion_degraded_but_completed",
                "anchor_symbol": "GraphConverter::from_adjacency",
            },
        ],
        "fallbacks": [
            {
                "fallback_id": "convert_hardened_continuation",
                "branch_id": "convert_hardened_warn_skip",
                "trigger": "malformed_input_hardened_mode",
                "recovery_actions": [
                    "append warning",
                    "emit full-validate decision record",
                    "continue ingest of well-formed rows",
                ],
                "terminal_state": "completed_with_warnings",
                "evidence_refs": [
                    "artifacts/conformance/latest/structured_logs.jsonl",
                    "artifacts/e2e/latest/e2e_script_pack_events_v1.jsonl",
                ],
            }
        ],
        "verification_links": {
            "unit": [
                "fnx_convert::tests::edge_list_conversion_is_deterministic",
                "fnx_convert::tests::strict_mode_fails_closed_for_malformed_edge",
            ],
            "property": ["property::fnx_convert::roundtrip_stability"],
            "differential": ["fixture::convert_adjacency_hardened"],
            "e2e": ["scripts/run_e2e_script_pack_gate.sh::malformed_input"],
        },
        "linked_bead_ids": ["bd-315.24.5", "bd-315.24.10", "bd-315.23"],
        "replay_command": "rch exec -- cargo test -q -p fnx-convert --lib -- --nocapture",
        "structured_log_refs": [
            "artifacts/conformance/latest/structured_logs.jsonl",
            "artifacts/e2e/latest/e2e_script_pack_bundle_index_v1.json",
        ],
        "risk_notes": [
            "Strict/hardened divergence must remain explicit and replay-verifiable.",
        ],
    },
    {
        "path_id": "readwrite_serialization_roundtrip",
        "title": "Read/Write Serialization and Parse Recovery",
        "subsystem_family": "io-serialization",
        "objective": "Enforce deterministic edge-list/json serialization with strict fail-closed parse branches and hardened bounded recovery.",
        "entrypoints": [
            ("fnx-readwrite", "crates/fnx-readwrite/src/lib.rs", "EdgeListEngine::read_edgelist", "pub fn read_edgelist("),
            ("fnx-readwrite", "crates/fnx-readwrite/src/lib.rs", "EdgeListEngine::read_json_graph", "pub fn read_json_graph("),
            ("fnx-readwrite", "crates/fnx-readwrite/src/lib.rs", "decode_attrs", "fn decode_attrs("),
        ],
        "steps": [
            ("serializer_dispatch", "Resolve read/write dispatch capability for selected format."),
            ("parse_validate", "Parse incoming rows/json and classify malformed records."),
            ("materialize_graph", "Apply parsed content to graph state with deterministic warnings and ledger records."),
        ],
        "branches": [
            {
                "branch_id": "readwrite_strict_fail_closed",
                "condition": "Strict parser encounters malformed edge-list line or invalid JSON.",
                "strict_behavior": "Return ReadWriteError::FailClosed and stop.",
                "hardened_behavior": "Not applicable (hardened path differs).",
                "fallback_behavior": "Persist fail-closed reason in decision ledger.",
                "outcome": "parse_failed",
                "anchor_symbol": "EdgeListEngine::read_edgelist",
            },
            {
                "branch_id": "readwrite_hardened_warning_recovery",
                "condition": "Hardened parser sees malformed row/json payload.",
                "strict_behavior": "Not applicable (strict fails closed).",
                "hardened_behavior": "Emit warning and continue with valid rows.",
                "fallback_behavior": "Return report with warnings and deterministic graph snapshot.",
                "outcome": "parse_completed_with_warnings",
                "anchor_symbol": "EdgeListEngine::read_json_graph",
            },
        ],
        "fallbacks": [
            {
                "fallback_id": "readwrite_replay_recovery",
                "branch_id": "readwrite_hardened_warning_recovery",
                "trigger": "hardened_malformed_payload",
                "recovery_actions": [
                    "record warning entries",
                    "retain valid graph rows",
                    "emit replay command for independent verification",
                ],
                "terminal_state": "completed_with_warnings",
                "evidence_refs": [
                    "artifacts/conformance/latest/structured_logs.jsonl",
                    "artifacts/e2e/latest/e2e_script_pack_replay_report_v1.json",
                ],
            }
        ],
        "verification_links": {
            "unit": [
                "fnx_readwrite::tests::round_trip_is_deterministic",
                "fnx_readwrite::tests::strict_mode_fails_closed_for_malformed_line",
                "fnx_readwrite::tests::hardened_mode_warns_and_recovers_for_malformed_json",
            ],
            "property": ["property::fnx_readwrite::roundtrip_stability"],
            "differential": ["fixture::readwrite_hardened_malformed"],
            "e2e": ["scripts/run_e2e_script_pack_gate.sh::edge_path"],
        },
        "linked_bead_ids": ["bd-315.24.5", "bd-315.24.10", "bd-315.23"],
        "replay_command": "rch exec -- cargo test -q -p fnx-readwrite --lib -- --nocapture",
        "structured_log_refs": [
            "artifacts/conformance/latest/structured_logs.jsonl",
            "artifacts/e2e/latest/e2e_script_pack_events_v1.jsonl",
        ],
        "risk_notes": [
            "Malformed-row recovery must never hide strict-mode failures.",
        ],
    },
    {
        "path_id": "algorithm_execution_bfs_centrality",
        "title": "Algorithm Execution (Shortest Path + Components + Centrality)",
        "subsystem_family": "algorithm-engine",
        "objective": "Execute deterministic algorithm routines with complexity witness artifacts and edge-case branch handling.",
        "entrypoints": [
            ("fnx-algorithms", "crates/fnx-algorithms/src/lib.rs", "shortest_path_unweighted", "pub fn shortest_path_unweighted("),
            ("fnx-algorithms", "crates/fnx-algorithms/src/lib.rs", "connected_components", "pub fn connected_components("),
            ("fnx-algorithms", "crates/fnx-algorithms/src/lib.rs", "degree_centrality", "pub fn degree_centrality("),
        ],
        "steps": [
            ("query_setup", "Validate source/target and initialize queue/visited maps."),
            ("deterministic_walk", "Traverse graph using ordered neighbor iteration."),
            ("witness_emission", "Emit complexity witness with nodes_touched/edges_scanned/queue_peak."),
        ],
        "branches": [
            {
                "branch_id": "algorithm_missing_nodes",
                "condition": "Source or target node absent for shortest-path query.",
                "strict_behavior": "Return path=None with zero-touch witness.",
                "hardened_behavior": "Return path=None with zero-touch witness.",
                "fallback_behavior": "No panic; deterministic null result.",
                "outcome": "query_no_path",
                "anchor_symbol": "shortest_path_unweighted",
            },
            {
                "branch_id": "algorithm_singleton_special_case",
                "condition": "Singleton graph centrality denominator edge case.",
                "strict_behavior": "Return score=1.0 for singleton degree centrality.",
                "hardened_behavior": "Return score=1.0 for singleton degree centrality.",
                "fallback_behavior": "Bypass divide-by-zero via guarded denominator.",
                "outcome": "query_completed",
                "anchor_symbol": "degree_centrality",
            },
        ],
        "fallbacks": [
            {
                "fallback_id": "algorithm_null_result_contract",
                "branch_id": "algorithm_missing_nodes",
                "trigger": "invalid_query_endpoints",
                "recovery_actions": [
                    "emit witness with zeroed counters",
                    "return deterministic null result",
                    "preserve graph state",
                ],
                "terminal_state": "completed_without_path",
                "evidence_refs": [
                    "artifacts/conformance/latest/structured_logs.jsonl",
                    "artifacts/e2e/latest/e2e_script_pack_events_v1.jsonl",
                ],
            }
        ],
        "verification_links": {
            "unit": [
                "fnx_algorithms::tests::bfs_shortest_path_uses_deterministic_neighbor_order",
                "fnx_algorithms::tests::connected_components_are_deterministic_and_partitioned",
                "fnx_algorithms::tests::degree_centrality_matches_expected_values_and_order",
            ],
            "property": ["property::fnx_algorithms::deterministic_bfs_invariants"],
            "differential": ["fixture::generated/algorithm_strict_parity"],
            "e2e": ["scripts/run_e2e_script_pack_gate.sh::adversarial_soak"],
        },
        "linked_bead_ids": ["bd-315.24.5", "bd-315.24.10", "bd-315.23"],
        "replay_command": "rch exec -- cargo test -q -p fnx-algorithms --lib -- --nocapture",
        "structured_log_refs": [
            "artifacts/conformance/latest/structured_logs.jsonl",
            "artifacts/e2e/latest/e2e_script_pack_bundle_index_v1.json",
        ],
        "risk_notes": [
            "Algorithm edge-case branches must remain deterministic and witness-backed.",
        ],
    },
    {
        "path_id": "conformance_harness_fixture_execution",
        "title": "Conformance Harness Fixture Execution and Artifact Emission",
        "subsystem_family": "conformance-harness",
        "objective": "Run fixture pipelines, compare expected behavior, and emit structured logs + replay metadata.",
        "entrypoints": [
            ("fnx-conformance", "crates/fnx-conformance/src/lib.rs", "run_smoke", "pub fn run_smoke("),
            ("fnx-conformance", "crates/fnx-conformance/src/lib.rs", "run_fixture", "fn run_fixture("),
            ("fnx-conformance", "crates/fnx-conformance/src/lib.rs", "build_structured_log", "fn build_structured_log("),
        ],
        "steps": [
            ("fixture_discovery", "Discover fixture paths and apply optional fixture filter."),
            ("operation_execution", "Execute fixture operations through graph/dispatch/convert/readwrite/generator stack."),
            ("artifact_emit", "Emit smoke report, structured logs, normalization report, and dependent-unblock matrix."),
        ],
        "branches": [
            {
                "branch_id": "fixture_read_or_parse_error",
                "condition": "Fixture file unreadable or parse fails.",
                "strict_behavior": "Emit failed FixtureReport with reason_code read_error/parse_error.",
                "hardened_behavior": "Emit failed FixtureReport with reason_code read_error/parse_error.",
                "fallback_behavior": "Continue suite execution with remaining fixtures.",
                "outcome": "fixture_failed_continue_suite",
                "anchor_symbol": "run_fixture",
            },
            {
                "branch_id": "fixture_operation_mismatch",
                "condition": "Observed output diverges from expected fixture contract.",
                "strict_behavior": "Record mismatch and include failure repro payload.",
                "hardened_behavior": "Record mismatch and include failure repro payload.",
                "fallback_behavior": "Preserve structured logs and forensics bundle index for replay.",
                "outcome": "suite_failed_with_forensics",
                "anchor_symbol": "build_structured_log",
            },
        ],
        "fallbacks": [
            {
                "fallback_id": "conformance_structured_forensics",
                "branch_id": "fixture_operation_mismatch",
                "trigger": "mismatch_count>0",
                "recovery_actions": [
                    "write fixture report artifact",
                    "attach replay command + failure repro",
                    "persist forensics bundle index row",
                ],
                "terminal_state": "diagnostic_artifacts_ready",
                "evidence_refs": [
                    "artifacts/conformance/latest/smoke_report.json",
                    "artifacts/conformance/latest/structured_logs.jsonl",
                ],
            }
        ],
        "verification_links": {
            "unit": ["fnx_conformance::tests::smoke_harness_reports_zero_drift_for_bootstrap_fixtures"],
            "property": ["property::fnx_conformance::fixture_roundtrip_invariants"],
            "differential": ["crates/fnx-conformance/src/bin/run_smoke.rs"],
            "e2e": ["scripts/run_e2e_script_pack_gate.sh::happy_path"],
        },
        "linked_bead_ids": ["bd-315.24.5", "bd-315.24.10", "bd-315.10", "bd-315.6", "bd-315.5"],
        "replay_command": "rch exec -- cargo run -q -p fnx-conformance --bin run_smoke -- --mode strict",
        "structured_log_refs": [
            "artifacts/conformance/latest/structured_logs.jsonl",
            "artifacts/conformance/latest/smoke_report.json",
        ],
        "risk_notes": [
            "Mismatch branches must always preserve replay and forensics references.",
        ],
    },
    {
        "path_id": "durability_sidecar_scrub_decode",
        "title": "Durability Sidecar Generation, Scrub Recovery, and Decode Drill",
        "subsystem_family": "durability-repair",
        "objective": "Guarantee recoverable artifact durability with RaptorQ sidecars and decode-proof events.",
        "entrypoints": [
            ("fnx-durability", "crates/fnx-durability/src/lib.rs", "generate_sidecar_for_file", "pub fn generate_sidecar_for_file("),
            ("fnx-durability", "crates/fnx-durability/src/lib.rs", "scrub_artifact", "pub fn scrub_artifact("),
            ("fnx-durability", "crates/fnx-durability/src/lib.rs", "run_decode_drill", "pub fn run_decode_drill("),
        ],
        "steps": [
            ("sidecar_encode", "Generate RaptorQ packets and write envelope with symbol hashes."),
            ("integrity_scrub", "Compare source hash and trigger decode recovery when corrupted/missing."),
            ("decode_proof_emit", "Write decode proof entries for scrub recovery and decode drills."),
        ],
        "branches": [
            {
                "branch_id": "scrub_hash_match_fastpath",
                "condition": "Artifact hash matches envelope source hash.",
                "strict_behavior": "Set scrub status to Ok and return.",
                "hardened_behavior": "Set scrub status to Ok and return.",
                "fallback_behavior": "No recovery decode required.",
                "outcome": "scrub_ok",
                "anchor_symbol": "scrub_artifact",
            },
            {
                "branch_id": "scrub_decode_recovery",
                "condition": "Artifact hash mismatch or artifact missing.",
                "strict_behavior": "Attempt decode and fail with HashMismatch on mismatch after decode.",
                "hardened_behavior": "Attempt decode and fail with HashMismatch on mismatch after decode.",
                "fallback_behavior": "Write recovered artifact and append decode proof when successful.",
                "outcome": "recovered_or_failed",
                "anchor_symbol": "scrub_artifact",
            },
        ],
        "fallbacks": [
            {
                "fallback_id": "durability_decode_drill_retry",
                "branch_id": "scrub_decode_recovery",
                "trigger": "decode_with_reduced_packets_failed",
                "recovery_actions": [
                    "retry with full packet envelope",
                    "emit decode proof on success",
                    "mark scrub status as Recovered",
                ],
                "terminal_state": "recovered",
                "evidence_refs": [
                    "artifacts/e2e/latest/e2e_script_pack_bundle_index_v1.json",
                    "artifacts/e2e/latest/e2e_script_pack_replay_report_v1.json",
                ],
            }
        ],
        "verification_links": {
            "unit": [
                "fnx_durability::tests::sidecar_generation_and_scrub_recovery_work",
                "fnx_durability::tests::decode_drill_emits_recovered_output",
            ],
            "property": ["property::fnx_durability::decode_proof_invariants"],
            "differential": ["fixture::durability_scrub_recovery"],
            "e2e": ["scripts/run_e2e_script_pack_gate.sh::adversarial_soak"],
        },
        "linked_bead_ids": ["bd-315.24.5", "bd-315.24.10", "bd-315.26.4", "bd-315.23"],
        "replay_command": "rch exec -- cargo test -q -p fnx-durability --lib -- --nocapture",
        "structured_log_refs": [
            "artifacts/e2e/latest/e2e_script_pack_events_v1.jsonl",
            "artifacts/e2e/latest/e2e_script_pack_bundle_index_v1.json",
        ],
        "risk_notes": [
            "Recovery path must always emit decode-proof metadata for auditability.",
        ],
    },
]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def find_line(path: Path, token: str) -> int:
    lines = path.read_text(encoding="utf-8").splitlines()
    for idx, line in enumerate(lines, start=1):
        if token in line:
            return idx
    raise RuntimeError(f"unable to locate token `{token}` in {path.as_posix()}")


def anchor(crate_name: str, file_path: str, symbol: str, token: str) -> dict[str, Any]:
    abs_path = REPO_ROOT / file_path
    line = find_line(abs_path, token)
    return {
        "crate_name": crate_name,
        "file_path": file_path,
        "symbol": symbol,
        "line_start": line,
    }


def build_payload() -> dict[str, Any]:
    execution_paths: list[dict[str, Any]] = []
    branch_catalog: list[dict[str, Any]] = []
    fallback_index: list[dict[str, Any]] = []

    for blueprint in WORKFLOW_BLUEPRINTS:
        entrypoints = [
            anchor(crate, file_path, symbol, token)
            for crate, file_path, symbol, token in blueprint["entrypoints"]
        ]
        anchor_by_symbol = {row["symbol"]: row for row in entrypoints}
        default_anchor = entrypoints[0]

        primary_steps = []
        for idx, (step_id, description) in enumerate(blueprint["steps"], start=1):
            primary_steps.append(
                {
                    "step_id": f"{blueprint['path_id']}-{idx:02d}-{step_id}",
                    "description": description,
                    "code_anchor": default_anchor,
                    "output_artifacts": list(blueprint["structured_log_refs"]),
                }
            )

        branches = []
        for row in blueprint["branches"]:
            branch = {
                "branch_id": row["branch_id"],
                "condition": row["condition"],
                "strict_behavior": row["strict_behavior"],
                "hardened_behavior": row["hardened_behavior"],
                "fallback_behavior": row["fallback_behavior"],
                "outcome": row["outcome"],
                "code_anchor": anchor_by_symbol.get(row["anchor_symbol"], default_anchor),
                "forensics_links": list(blueprint["structured_log_refs"]),
            }
            branches.append(branch)
            branch_catalog.append(
                {
                    "path_id": blueprint["path_id"],
                    "branch_id": branch["branch_id"],
                    "condition": branch["condition"],
                    "outcome": branch["outcome"],
                    "code_anchor": branch["code_anchor"],
                }
            )

        fallback_rows = []
        for row in blueprint["fallbacks"]:
            fallback = {
                "fallback_id": row["fallback_id"],
                "branch_id": row["branch_id"],
                "trigger": row["trigger"],
                "recovery_actions": list(row["recovery_actions"]),
                "terminal_state": row["terminal_state"],
                "evidence_refs": list(row["evidence_refs"]),
            }
            fallback_rows.append(fallback)
            fallback_index.append(
                {
                    "path_id": blueprint["path_id"],
                    "fallback_id": fallback["fallback_id"],
                    "branch_id": fallback["branch_id"],
                    "trigger": fallback["trigger"],
                    "terminal_state": fallback["terminal_state"],
                }
            )

        execution_paths.append(
            {
                "path_id": blueprint["path_id"],
                "title": blueprint["title"],
                "subsystem_family": blueprint["subsystem_family"],
                "objective": blueprint["objective"],
                "entrypoints": entrypoints,
                "primary_steps": primary_steps,
                "branch_paths": branches,
                "fallback_paths": fallback_rows,
                "verification_links": dict(blueprint["verification_links"]),
                "linked_bead_ids": list(blueprint["linked_bead_ids"]),
                "replay_command": blueprint["replay_command"],
                "structured_log_refs": list(blueprint["structured_log_refs"]),
                "risk_notes": list(blueprint["risk_notes"]),
            }
        )

    all_beads = sorted(
        {
            bead_id
            for row in execution_paths
            for bead_id in row["linked_bead_ids"]
        }
    )
    crosswalk = [
        {
            "bead_id": bead_id,
            "title": BEAD_TITLES.get(bead_id, "Unknown bead"),
            "path_ids": sorted(
                [row["path_id"] for row in execution_paths if bead_id in row["linked_bead_ids"]]
            ),
            "status": "tracked",
            "closure_signal": "mapped_to_verification_assets",
        }
        for bead_id in all_beads
    ]

    return {
        "schema_version": "1.0.0",
        "artifact_id": "doc-pass-04-execution-path-tracing-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "baseline_comparator": BASELINE_COMPARATOR,
        "execution_summary": {
            "workflow_count": len(execution_paths),
            "branch_count": sum(len(row["branch_paths"]) for row in execution_paths),
            "fallback_count": sum(len(row["fallback_paths"]) for row in execution_paths),
            "workspace_crate_count": len(
                {
                    entry["crate_name"]
                    for row in execution_paths
                    for entry in row["entrypoints"]
                }
            ),
            "verification_bead_count": len(crosswalk),
        },
        "execution_paths": execution_paths,
        "branch_catalog": branch_catalog,
        "fallback_index": fallback_index,
        "verification_bead_crosswalk": crosswalk,
        "alien_uplift_contract_card": dict(ALIEN_UPLIFT_CONTRACT_CARD),
        "profile_first_artifacts": dict(PROFILE_FIRST_ARTIFACTS),
        "optimization_lever_policy": dict(OPTIMIZATION_LEVER_POLICY),
        "decision_theoretic_runtime_contract": dict(DECISION_THEORETIC_RUNTIME_CONTRACT),
        "isomorphism_proof_artifacts": list(ISOMORPHISM_PROOF_ARTIFACTS),
        "structured_logging_evidence": list(STRUCTURED_LOGGING_EVIDENCE),
    }


def build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# DOC-PASS-04 Execution-Path Tracing v1",
        "",
        f"Generated at: `{payload['generated_at_utc']}`",
        f"Baseline comparator: `{payload['baseline_comparator']}`",
        "",
        "## Summary",
    ]
    summary = payload["execution_summary"]
    for key in [
        "workflow_count",
        "branch_count",
        "fallback_count",
        "workspace_crate_count",
        "verification_bead_count",
    ]:
        lines.append(f"- {key}: `{summary[key]}`")

    lines.extend(
        [
            "",
            "## Workflow Index",
            "",
            "| path_id | subsystem | branches | fallbacks | replay |",
            "|---|---|---:|---:|---|",
        ]
    )
    for row in payload["execution_paths"]:
        lines.append(
            "| {path_id} | {subsystem_family} | {branches} | {fallbacks} | `{replay}` |".format(
                path_id=row["path_id"],
                subsystem_family=row["subsystem_family"],
                branches=len(row["branch_paths"]),
                fallbacks=len(row["fallback_paths"]),
                replay=row["replay_command"],
            )
        )

    lines.append("")
    for row in payload["execution_paths"]:
        lines.extend(
            [
                f"## {row['title']}",
                "",
                f"- path_id: `{row['path_id']}`",
                f"- objective: {row['objective']}",
                f"- linked beads: {', '.join(f'`{item}`' for item in row['linked_bead_ids'])}",
                "",
                "### Branches",
            ]
        )
        for branch in row["branch_paths"]:
            lines.append(
                "- `{branch_id}`: {condition} -> {outcome}".format(
                    branch_id=branch["branch_id"],
                    condition=branch["condition"],
                    outcome=branch["outcome"],
                )
            )
        lines.extend(["", "### Fallbacks"])
        for fallback in row["fallback_paths"]:
            lines.append(
                "- `{fallback_id}`: trigger `{trigger}` -> terminal `{terminal}`".format(
                    fallback_id=fallback["fallback_id"],
                    trigger=fallback["trigger"],
                    terminal=fallback["terminal_state"],
                )
            )
        lines.extend(["", "### Verification"])
        verification = row["verification_links"]
        for key in ["unit", "property", "differential", "e2e"]:
            lines.append(f"- {key}: {len(verification[key])} references")
        lines.append("")

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-json", default=str(OUTPUT_JSON))
    parser.add_argument("--output-md", default=str(OUTPUT_MD))
    args = parser.parse_args()

    payload = build_payload()

    output_json = Path(args.output_json)
    output_md = Path(args.output_md)
    if not output_json.is_absolute():
        output_json = REPO_ROOT / output_json
    if not output_md.is_absolute():
        output_md = REPO_ROOT / output_md

    write_json(output_json, payload)
    write_text(output_md, build_markdown(payload))
    print(f"doc_pass04_json:{output_json}")
    print(f"doc_pass04_md:{output_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
