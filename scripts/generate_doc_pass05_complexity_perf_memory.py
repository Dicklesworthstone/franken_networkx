#!/usr/bin/env python3
"""Generate DOC-PASS-05 complexity/performance/memory characterization artifact."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_JSON = REPO_ROOT / "artifacts/docs/v1/doc_pass05_complexity_perf_memory_v1.json"
OUTPUT_MD = REPO_ROOT / "artifacts/docs/v1/doc_pass05_complexity_perf_memory_v1.md"

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
    "ev_score": 2.33,
    "baseline_comparator": BASELINE_COMPARATOR,
    "expected_value_statement": (
        "Explicit complexity/memory envelopes and hotspot hypotheses reduce optimization churn "
        "while preserving strict/hardened parity guarantees."
    ),
}
DECISION_THEORETIC_RUNTIME_CONTRACT = {
    "states": ["measure", "hypothesize", "optimize", "verify", "fail_closed"],
    "actions": [
        "record_baseline",
        "declare_hotspot_hypothesis",
        "apply_single_lever",
        "prove_isomorphism",
        "rollback",
    ],
    "loss_model": (
        "Minimize expected semantic drift by allowing optimizations only when complexity "
        "improves without changing tie-break or observable output semantics."
    ),
    "loss_budget": {
        "max_expected_loss": 0.02,
        "max_unverified_hotspots": 0,
        "max_parity_breaking_optimizations": 0,
    },
    "safe_mode_fallback": {
        "trigger_thresholds": {
            "missing_complexity_rows": 1,
            "missing_hotspot_hypotheses": 1,
            "missing_risk_notes": 1,
            "parity_mismatch_events": 1,
        },
        "fallback_action": "halt optimization rollout and require fail-closed verification rerun",
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

FAMILY_META: dict[str, dict[str, Any]] = {
    "graph_storage_semantics": {
        "name": "Graph Storage and Mutation Semantics",
        "legacy_scope_paths": [
            "networkx/classes/graph.py",
            "networkx/classes/digraph.py",
            "networkx/classes/multigraph.py",
        ],
        "rust_crates": ["fnx-classes"],
    },
    "algorithmic_core": {
        "name": "Algorithms: Path, Components, and Centrality",
        "legacy_scope_paths": [
            "networkx/algorithms/shortest_paths/unweighted.py",
            "networkx/algorithms/components/connected.py",
            "networkx/algorithms/centrality/",
        ],
        "rust_crates": ["fnx-algorithms"],
    },
    "generator_workloads": {
        "name": "Graph Generator Workloads",
        "legacy_scope_paths": [
            "networkx/generators/classic.py",
            "networkx/generators/random_graphs.py",
        ],
        "rust_crates": ["fnx-generators"],
    },
    "conversion_and_io": {
        "name": "Conversion and Read/Write Pipelines",
        "legacy_scope_paths": [
            "networkx/convert.py",
            "networkx/readwrite/edgelist.py",
            "networkx/readwrite/json_graph/",
        ],
        "rust_crates": ["fnx-convert", "fnx-readwrite"],
    },
    "dispatch_runtime_policy": {
        "name": "Dispatch + Runtime Policy Evaluation",
        "legacy_scope_paths": [
            "networkx/utils/backends.py",
            "networkx/exception.py",
        ],
        "rust_crates": ["fnx-dispatch", "fnx-runtime"],
    },
    "conformance_execution": {
        "name": "Conformance Harness Execution",
        "legacy_scope_paths": [
            "networkx/tests/",
            "networkx/testing/",
        ],
        "rust_crates": ["fnx-conformance"],
    },
}

DEFAULT_HOTSPOT_SIGNALS = [
    "artifacts/perf/phase2c/perf_baseline_matrix_v1.json",
    "artifacts/perf/phase2c/hotspot_one_lever_backlog_v1.json",
    "artifacts/perf/phase2c/perf_regression_gate_report_v1.json",
]


def find_line(file_path: str, marker: str) -> int:
    path = REPO_ROOT / file_path
    lines = path.read_text(encoding="utf-8").splitlines()
    for idx, line in enumerate(lines, start=1):
        if marker in line:
            return idx
    raise RuntimeError(f"unable to locate marker `{marker}` in {file_path}")


def anchor(crate_name: str, file_path: str, symbol: str, marker: str) -> dict[str, Any]:
    return {
        "crate_name": crate_name,
        "file_path": file_path,
        "symbol": symbol,
        "line_start": find_line(file_path, marker),
    }


def hooks(
    unit: list[str],
    prop: list[str],
    differential: list[str],
    e2e: list[str],
) -> dict[str, list[str]]:
    return {
        "unit": unit,
        "property": prop,
        "differential": differential,
        "e2e": e2e,
    }


def operation(
    *,
    family_id: str,
    operation_id: str,
    symbol: str,
    code_anchor: dict[str, Any],
    complexity_time: str,
    complexity_space: str,
    memory_growth_driver: str,
    hotspot_signals: list[str],
    parity_constraints: list[str],
    validation_hooks: dict[str, list[str]],
    replay_command: str,
    risk_tier: str,
) -> dict[str, Any]:
    return {
        "family_id": family_id,
        "operation_id": operation_id,
        "symbol": symbol,
        "code_anchor": code_anchor,
        "complexity_time": complexity_time,
        "complexity_space": complexity_space,
        "memory_growth_driver": memory_growth_driver,
        "hotspot_signals": hotspot_signals,
        "parity_constraints": parity_constraints,
        "validation_hooks": validation_hooks,
        "replay_command": replay_command,
        "risk_tier": risk_tier,
        "optimization_risk_note_ids": [],
    }


def build_operations() -> list[dict[str, Any]]:
    return [
        operation(
            family_id="graph_storage_semantics",
            operation_id="graph_add_node_with_attrs",
            symbol="Graph::add_node_with_attrs",
            code_anchor=anchor(
                "fnx-classes",
                "crates/fnx-classes/src/lib.rs",
                "Graph::add_node_with_attrs",
                "pub fn add_node_with_attrs(",
            ),
            complexity_time="O(1) amortized",
            complexity_space="O(1) incremental",
            memory_growth_driver="node table growth and per-node attribute map expansion",
            hotspot_signals=DEFAULT_HOTSPOT_SIGNALS,
            parity_constraints=[
                "Deterministic insertion order for node iteration is preserved.",
                "Strict/hardened mode cannot silently drop nodes.",
            ],
            validation_hooks=hooks(
                ["fnx_classes::tests::add_node_with_attrs"],
                ["property::fnx_classes::mutation_invariants"],
                ["fixture::graph_core_mutation_hardened"],
                ["scripts/run_phase2c_readiness_e2e.sh::graph_core"],
            ),
            replay_command="rch exec -- cargo test -q -p fnx-classes --lib -- --nocapture",
            risk_tier="medium",
        ),
        operation(
            family_id="graph_storage_semantics",
            operation_id="graph_add_edge_with_attrs",
            symbol="Graph::add_edge_with_attrs",
            code_anchor=anchor(
                "fnx-classes",
                "crates/fnx-classes/src/lib.rs",
                "Graph::add_edge_with_attrs",
                "pub fn add_edge_with_attrs(",
            ),
            complexity_time="O(1) amortized",
            complexity_space="O(1) incremental",
            memory_growth_driver="adjacency map expansion and edge attribute clone cost",
            hotspot_signals=DEFAULT_HOTSPOT_SIGNALS,
            parity_constraints=[
                "Edge endpoint ordering and tie-break behavior must remain deterministic.",
                "Unknown incompatible metadata paths remain fail-closed.",
            ],
            validation_hooks=hooks(
                ["fnx_classes::tests::add_edge_autocreates_nodes_and_preserves_order"],
                ["property::fnx_classes::mutation_invariants"],
                ["fixture::graph_core_mutation_hardened"],
                ["scripts/run_phase2c_readiness_e2e.sh::graph_core"],
            ),
            replay_command="rch exec -- cargo test -q -p fnx-classes --lib -- --nocapture",
            risk_tier="high",
        ),
        operation(
            family_id="graph_storage_semantics",
            operation_id="graph_remove_node",
            symbol="Graph::remove_node",
            code_anchor=anchor(
                "fnx-classes",
                "crates/fnx-classes/src/lib.rs",
                "Graph::remove_node",
                "pub fn remove_node(",
            ),
            complexity_time="O(deg(v))",
            complexity_space="O(1) additional",
            memory_growth_driver="neighbor edge tear-down touching incident adjacency sets",
            hotspot_signals=DEFAULT_HOTSPOT_SIGNALS,
            parity_constraints=[
                "Incident edge cleanup must be complete and deterministic.",
                "Revision bumps occur exactly once per committed mutation.",
            ],
            validation_hooks=hooks(
                ["fnx_classes::tests::remove_node_removes_incident_edges"],
                ["property::fnx_classes::mutation_invariants"],
                ["fixture::graph_core_mutation_hardened"],
                ["scripts/run_phase2c_readiness_e2e.sh::graph_core"],
            ),
            replay_command="rch exec -- cargo test -q -p fnx-classes --lib -- --nocapture",
            risk_tier="high",
        ),
        operation(
            family_id="graph_storage_semantics",
            operation_id="graph_neighbors_projection",
            symbol="Graph::neighbors",
            code_anchor=anchor(
                "fnx-classes",
                "crates/fnx-classes/src/lib.rs",
                "Graph::neighbors",
                "pub fn neighbors(&self, node: &str) -> Option<Vec<&str>> {",
            ),
            complexity_time="O(deg(v))",
            complexity_space="O(deg(v)) output-bound",
            memory_growth_driver="temporary neighbor vector materialization for deterministic reads",
            hotspot_signals=DEFAULT_HOTSPOT_SIGNALS,
            parity_constraints=[
                "Neighbor ordering must mirror canonical adjacency insertion order.",
                "Missing node behavior remains NetworkX-observable for scoped API.",
            ],
            validation_hooks=hooks(
                ["fnx_classes::tests::neighbors_are_deterministic"],
                ["property::fnx_classes::mutation_invariants"],
                ["fixture::view_neighbors_strict"],
                ["scripts/run_phase2c_readiness_e2e.sh::view_api"],
            ),
            replay_command="rch exec -- cargo test -q -p fnx-classes --lib -- --nocapture",
            risk_tier="medium",
        ),
        operation(
            family_id="algorithmic_core",
            operation_id="algo_shortest_path_unweighted",
            symbol="shortest_path_unweighted",
            code_anchor=anchor(
                "fnx-algorithms",
                "crates/fnx-algorithms/src/lib.rs",
                "shortest_path_unweighted",
                "pub fn shortest_path_unweighted(",
            ),
            complexity_time="O(V + E)",
            complexity_space="O(V)",
            memory_growth_driver="BFS frontier, predecessor maps, and visited set growth",
            hotspot_signals=DEFAULT_HOTSPOT_SIGNALS
            + ["artifacts/perf/phase2c/bfs_neighbor_iter_delta.json"],
            parity_constraints=[
                "Tie-break ordering in frontier traversal must remain deterministic.",
                "Unreachable target semantics must match legacy output contract.",
            ],
            validation_hooks=hooks(
                ["fnx_algorithms::tests::shortest_path_handles_unreachable"],
                ["property::fnx_algorithms::shortest_path_invariants"],
                ["fixture::generated/shortest_path_basic"],
                ["scripts/run_phase2c_readiness_e2e.sh::algo_core"],
            ),
            replay_command="rch exec -- cargo test -q -p fnx-algorithms --lib -- --nocapture",
            risk_tier="high",
        ),
        operation(
            family_id="algorithmic_core",
            operation_id="algo_connected_components",
            symbol="connected_components",
            code_anchor=anchor(
                "fnx-algorithms",
                "crates/fnx-algorithms/src/lib.rs",
                "connected_components",
                "pub fn connected_components(",
            ),
            complexity_time="O(V + E)",
            complexity_space="O(V)",
            memory_growth_driver="visited bookkeeping plus component vector materialization",
            hotspot_signals=DEFAULT_HOTSPOT_SIGNALS,
            parity_constraints=[
                "Component ordering and membership ordering stay deterministic.",
                "Strict/hardened mode cannot alter component cardinality outputs.",
            ],
            validation_hooks=hooks(
                ["fnx_algorithms::tests::connected_components_empty_graph"],
                ["property::fnx_algorithms::component_partition_invariants"],
                ["fixture::generated/components_basic"],
                ["scripts/run_phase2c_readiness_e2e.sh::algo_core"],
            ),
            replay_command="rch exec -- cargo test -q -p fnx-algorithms --lib -- --nocapture",
            risk_tier="high",
        ),
        operation(
            family_id="algorithmic_core",
            operation_id="algo_degree_centrality",
            symbol="degree_centrality",
            code_anchor=anchor(
                "fnx-algorithms",
                "crates/fnx-algorithms/src/lib.rs",
                "degree_centrality",
                "pub fn degree_centrality(",
            ),
            complexity_time="O(V + E)",
            complexity_space="O(V)",
            memory_growth_driver="centrality score map over all nodes",
            hotspot_signals=DEFAULT_HOTSPOT_SIGNALS,
            parity_constraints=[
                "Normalized score computation preserves exact legacy denominator semantics.",
                "Output key ordering remains deterministic for equal scores.",
            ],
            validation_hooks=hooks(
                ["fnx_algorithms::tests::degree_centrality_path_graph"],
                ["property::fnx_algorithms::centrality_bounds"],
                ["fixture::generated/degree_centrality_basic"],
                ["scripts/run_phase2c_readiness_e2e.sh::algo_core"],
            ),
            replay_command="rch exec -- cargo test -q -p fnx-algorithms --lib -- --nocapture",
            risk_tier="medium",
        ),
        operation(
            family_id="algorithmic_core",
            operation_id="algo_closeness_centrality",
            symbol="closeness_centrality",
            code_anchor=anchor(
                "fnx-algorithms",
                "crates/fnx-algorithms/src/lib.rs",
                "closeness_centrality",
                "pub fn closeness_centrality(",
            ),
            complexity_time="O(V * (V + E))",
            complexity_space="O(V)",
            memory_growth_driver="all-source shortest-path sweeps and score accumulation",
            hotspot_signals=DEFAULT_HOTSPOT_SIGNALS,
            parity_constraints=[
                "WF-improved normalization behavior remains identical to scoped legacy semantics.",
                "Node ordering and floating-point output stability are preserved within drift budget.",
            ],
            validation_hooks=hooks(
                ["fnx_algorithms::tests::closeness_centrality_path_graph"],
                ["property::fnx_algorithms::centrality_bounds"],
                ["fixture::generated/closeness_centrality_basic"],
                ["scripts/run_phase2c_readiness_e2e.sh::algo_core"],
            ),
            replay_command="rch exec -- cargo test -q -p fnx-algorithms --lib -- --nocapture",
            risk_tier="high",
        ),
        operation(
            family_id="generator_workloads",
            operation_id="gen_cycle_graph",
            symbol="GraphGenerator::cycle_graph",
            code_anchor=anchor(
                "fnx-generators",
                "crates/fnx-generators/src/lib.rs",
                "GraphGenerator::cycle_graph",
                "pub fn cycle_graph(",
            ),
            complexity_time="O(V)",
            complexity_space="O(V)",
            memory_growth_driver="deterministic node and edge insertion for cycle topology",
            hotspot_signals=DEFAULT_HOTSPOT_SIGNALS,
            parity_constraints=[
                "Edge insertion order must match NetworkX cycle contract.",
                "Strict/hardened guards cannot reorder generated topology.",
            ],
            validation_hooks=hooks(
                ["fnx_generators::tests::cycle_graph_edge_order_matches_networkx_for_n_five"],
                ["property::fnx_generators::edge_count_invariants"],
                ["fixture::generated/generator_cycle_graph"],
                ["scripts/run_phase2c_readiness_e2e.sh::generators"],
            ),
            replay_command="rch exec -- cargo test -q -p fnx-generators --lib -- --nocapture",
            risk_tier="medium",
        ),
        operation(
            family_id="generator_workloads",
            operation_id="gen_complete_graph",
            symbol="GraphGenerator::complete_graph",
            code_anchor=anchor(
                "fnx-generators",
                "crates/fnx-generators/src/lib.rs",
                "GraphGenerator::complete_graph",
                "pub fn complete_graph(",
            ),
            complexity_time="O(V^2)",
            complexity_space="O(V^2)",
            memory_growth_driver="quadratic edge surface materialization for dense topology",
            hotspot_signals=DEFAULT_HOTSPOT_SIGNALS,
            parity_constraints=[
                "Dense edge ordering remains deterministic and reproducible.",
                "Validation guards preserve strict/hardened observable behavior.",
            ],
            validation_hooks=hooks(
                ["fnx_generators::tests::complete_graph_node_and_edge_counts"],
                ["property::fnx_generators::edge_count_invariants"],
                ["fixture::generated/generator_complete_graph"],
                ["scripts/run_phase2c_readiness_e2e.sh::generators"],
            ),
            replay_command="rch exec -- cargo test -q -p fnx-generators --lib -- --nocapture",
            risk_tier="medium",
        ),
        operation(
            family_id="generator_workloads",
            operation_id="gen_gnp_random_graph",
            symbol="GraphGenerator::gnp_random_graph",
            code_anchor=anchor(
                "fnx-generators",
                "crates/fnx-generators/src/lib.rs",
                "GraphGenerator::gnp_random_graph",
                "pub fn gnp_random_graph(",
            ),
            complexity_time="O(V^2) expected",
            complexity_space="O(V + E)",
            memory_growth_driver="pairwise edge sampling loop and seeded RNG state",
            hotspot_signals=DEFAULT_HOTSPOT_SIGNALS,
            parity_constraints=[
                "Seeded randomness remains deterministic for identical seed/p parameters.",
                "Tie-break and edge-order outputs are reproducible across runs.",
            ],
            validation_hooks=hooks(
                ["fnx_generators::tests::gnp_random_graph_seed_is_deterministic"],
                ["property::fnx_generators::seeded_reproducibility"],
                ["fixture::generated/generator_gnp_seeded"],
                ["scripts/run_phase2c_readiness_e2e.sh::generators"],
            ),
            replay_command="rch exec -- cargo test -q -p fnx-generators --lib -- --nocapture",
            risk_tier="high",
        ),
        operation(
            family_id="conversion_and_io",
            operation_id="convert_from_edge_list",
            symbol="GraphConverter::from_edge_list",
            code_anchor=anchor(
                "fnx-convert",
                "crates/fnx-convert/src/lib.rs",
                "GraphConverter::from_edge_list",
                "pub fn from_edge_list(",
            ),
            complexity_time="O(V + E)",
            complexity_space="O(V + E)",
            memory_growth_driver="intermediate edge payload and graph builder state",
            hotspot_signals=DEFAULT_HOTSPOT_SIGNALS,
            parity_constraints=[
                "Strict mode malformed endpoint handling stays fail-closed.",
                "Hardened mode bounded recovery emits explicit warnings.",
            ],
            validation_hooks=hooks(
                ["fnx_convert::tests::edge_list_conversion_is_deterministic"],
                ["property::fnx_convert::roundtrip_payload_invariants"],
                ["fixture::generated/convert_edge_list_strict"],
                ["scripts/run_phase2c_readiness_e2e.sh::convert_rw"],
            ),
            replay_command="rch exec -- cargo test -q -p fnx-convert --lib -- --nocapture",
            risk_tier="high",
        ),
        operation(
            family_id="conversion_and_io",
            operation_id="convert_from_adjacency",
            symbol="GraphConverter::from_adjacency",
            code_anchor=anchor(
                "fnx-convert",
                "crates/fnx-convert/src/lib.rs",
                "GraphConverter::from_adjacency",
                "pub fn from_adjacency(",
            ),
            complexity_time="O(V + E)",
            complexity_space="O(V + E)",
            memory_growth_driver="adjacency list fan-out and warning accumulation",
            hotspot_signals=DEFAULT_HOTSPOT_SIGNALS,
            parity_constraints=[
                "Strict mode rejects malformed adjacency entries deterministically.",
                "Hardened recovery remains bounded and fully auditable.",
            ],
            validation_hooks=hooks(
                ["fnx_convert::tests::adjacency_conversion_preserves_edges"],
                ["property::fnx_convert::roundtrip_payload_invariants"],
                ["fixture::generated/convert_adjacency_hardened"],
                ["scripts/run_phase2c_readiness_e2e.sh::convert_rw"],
            ),
            replay_command="rch exec -- cargo test -q -p fnx-convert --lib -- --nocapture",
            risk_tier="high",
        ),
        operation(
            family_id="conversion_and_io",
            operation_id="rw_read_edgelist",
            symbol="EdgeListEngine::read_edgelist",
            code_anchor=anchor(
                "fnx-readwrite",
                "crates/fnx-readwrite/src/lib.rs",
                "EdgeListEngine::read_edgelist",
                "pub fn read_edgelist(",
            ),
            complexity_time="O(L) where L is input lines",
            complexity_space="O(V + E)",
            memory_growth_driver="line tokenization plus warning buffers for malformed rows",
            hotspot_signals=DEFAULT_HOTSPOT_SIGNALS,
            parity_constraints=[
                "Line-level malformed input behavior must remain strict/hardened split.",
                "Parser must preserve deterministic edge insertion sequence.",
            ],
            validation_hooks=hooks(
                ["fnx_readwrite::tests::strict_mode_fails_closed_for_malformed_line"],
                ["property::fnx_readwrite::roundtrip_stability"],
                ["fixture::generated/readwrite_hardened_malformed"],
                ["scripts/run_phase2c_readiness_e2e.sh::convert_rw"],
            ),
            replay_command="rch exec -- cargo test -q -p fnx-readwrite --lib -- --nocapture",
            risk_tier="high",
        ),
        operation(
            family_id="conversion_and_io",
            operation_id="rw_write_json_graph",
            symbol="EdgeListEngine::write_json_graph",
            code_anchor=anchor(
                "fnx-readwrite",
                "crates/fnx-readwrite/src/lib.rs",
                "EdgeListEngine::write_json_graph",
                "pub fn write_json_graph(",
            ),
            complexity_time="O(V + E)",
            complexity_space="O(V + E) serialization buffer",
            memory_growth_driver="snapshot serialization and pretty-print buffer expansion",
            hotspot_signals=DEFAULT_HOTSPOT_SIGNALS,
            parity_constraints=[
                "Serialized graph ordering remains deterministic across identical snapshots.",
                "Serialization failures stay fail-closed with diagnostics.",
            ],
            validation_hooks=hooks(
                ["fnx_readwrite::tests::json_roundtrip_is_deterministic"],
                ["property::fnx_readwrite::roundtrip_stability"],
                ["fixture::generated/readwrite_json_roundtrip"],
                ["scripts/run_phase2c_readiness_e2e.sh::convert_rw"],
            ),
            replay_command="rch exec -- cargo test -q -p fnx-readwrite --lib -- --nocapture",
            risk_tier="medium",
        ),
        operation(
            family_id="conversion_and_io",
            operation_id="rw_read_json_graph",
            symbol="EdgeListEngine::read_json_graph",
            code_anchor=anchor(
                "fnx-readwrite",
                "crates/fnx-readwrite/src/lib.rs",
                "EdgeListEngine::read_json_graph",
                "pub fn read_json_graph(",
            ),
            complexity_time="O(V + E)",
            complexity_space="O(V + E)",
            memory_growth_driver="decoded snapshot objects and warning recovery queue",
            hotspot_signals=DEFAULT_HOTSPOT_SIGNALS,
            parity_constraints=[
                "JSON parse errors preserve strict fail-closed versus hardened bounded recovery.",
                "Node/edge reconstruction ordering remains deterministic.",
            ],
            validation_hooks=hooks(
                ["fnx_readwrite::tests::hardened_mode_recovers_from_invalid_json"],
                ["property::fnx_readwrite::roundtrip_stability"],
                ["fixture::generated/readwrite_json_hardened_invalid"],
                ["scripts/run_phase2c_readiness_e2e.sh::convert_rw"],
            ),
            replay_command="rch exec -- cargo test -q -p fnx-readwrite --lib -- --nocapture",
            risk_tier="high",
        ),
        operation(
            family_id="dispatch_runtime_policy",
            operation_id="dispatch_backend_resolve",
            symbol="BackendRegistry::resolve",
            code_anchor=anchor(
                "fnx-dispatch",
                "crates/fnx-dispatch/src/lib.rs",
                "BackendRegistry::resolve",
                "pub fn resolve(",
            ),
            complexity_time="O(B * F) where B=backends and F=feature checks",
            complexity_space="O(B)",
            memory_growth_driver="backend candidate filtering and decision ledger updates",
            hotspot_signals=DEFAULT_HOTSPOT_SIGNALS,
            parity_constraints=[
                "Unknown incompatible features fail closed in both strict and hardened mode.",
                "Priority then lexical tie-break ordering remains deterministic.",
            ],
            validation_hooks=hooks(
                ["fnx_dispatch::tests::strict_mode_rejects_unknown_incompatible_request"],
                ["property::fnx_dispatch::deterministic_selection"],
                ["fixture::generated/dispatch_route_strict"],
                ["scripts/run_phase2c_readiness_e2e.sh::dispatch"],
            ),
            replay_command="rch exec -- cargo test -q -p fnx-dispatch --lib -- --nocapture",
            risk_tier="high",
        ),
        operation(
            family_id="dispatch_runtime_policy",
            operation_id="runtime_decision_theoretic_action",
            symbol="decision_theoretic_action",
            code_anchor=anchor(
                "fnx-runtime",
                "crates/fnx-runtime/src/lib.rs",
                "decision_theoretic_action",
                "pub fn decision_theoretic_action(",
            ),
            complexity_time="O(1)",
            complexity_space="O(1)",
            memory_growth_driver="constant-size decision state and risk threshold checks",
            hotspot_signals=DEFAULT_HOTSPOT_SIGNALS,
            parity_constraints=[
                "Risk-threshold transitions preserve strict/hardened policy semantics.",
                "Unknown incompatible features must map to fail-closed action.",
            ],
            validation_hooks=hooks(
                ["fnx_runtime::tests::strict_mode_fail_closed_for_unknown_incompatible_feature"],
                ["property::fnx_runtime::decision_action_threshold_monotonicity"],
                ["fixture::generated/dispatch_route_strict"],
                ["scripts/run_phase2c_readiness_e2e.sh::dispatch"],
            ),
            replay_command="rch exec -- cargo test -q -p fnx-runtime --lib -- --nocapture",
            risk_tier="medium",
        ),
        operation(
            family_id="conformance_execution",
            operation_id="conformance_run_smoke",
            symbol="run_smoke",
            code_anchor=anchor(
                "fnx-conformance",
                "crates/fnx-conformance/src/lib.rs",
                "run_smoke",
                "pub fn run_smoke(",
            ),
            complexity_time="O(F * (V + E)) where F is fixture count",
            complexity_space="O(F + mismatch_count)",
            memory_growth_driver="fixture reports, mismatch vectors, and structured log emission",
            hotspot_signals=DEFAULT_HOTSPOT_SIGNALS + ["artifacts/conformance/latest/structured_logs.jsonl"],
            parity_constraints=[
                "Fixture execution order and packet routing remain deterministic.",
                "Structured logs must keep replay metadata complete.",
            ],
            validation_hooks=hooks(
                ["fnx_conformance::tests::smoke_harness_reports_zero_drift_for_bootstrap_fixtures"],
                ["property::fnx_conformance::log_schema_invariants"],
                ["fixture::all_generated_fixtures"],
                ["scripts/run_phase2c_readiness_e2e.sh::conformance"],
            ),
            replay_command="rch exec -- cargo test -q -p fnx-conformance --test smoke -- --nocapture",
            risk_tier="high",
        ),
        operation(
            family_id="conformance_execution",
            operation_id="conformance_run_fixture",
            symbol="run_fixture",
            code_anchor=anchor(
                "fnx-conformance",
                "crates/fnx-conformance/src/lib.rs",
                "run_fixture",
                "fn run_fixture(",
            ),
            complexity_time="O(op_count * (V + E)) per fixture",
            complexity_space="O(mismatch_count + witness_count)",
            memory_growth_driver="operation result aggregation and mismatch serialization",
            hotspot_signals=DEFAULT_HOTSPOT_SIGNALS + ["artifacts/conformance/latest/structured_logs.jsonl"],
            parity_constraints=[
                "Mismatch taxonomy separation (strict violation vs hardened allowlist) remains intact.",
                "Replay command references stay deterministic and complete.",
            ],
            validation_hooks=hooks(
                ["fnx_conformance::tests::packet_id_for_fixture_maps_known_prefixes"],
                ["property::fnx_conformance::log_schema_invariants"],
                ["fixture::all_generated_fixtures"],
                ["scripts/run_phase2c_readiness_e2e.sh::conformance"],
            ),
            replay_command="rch exec -- cargo test -q -p fnx-conformance --lib -- --nocapture",
            risk_tier="high",
        ),
    ]


def assign_risk_notes(operations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    risk_notes: list[dict[str, Any]] = []
    for row in operations:
        operation_id = row["operation_id"]
        risk_note_id = f"risk::{operation_id}"
        row["optimization_risk_note_ids"] = [risk_note_id]
        risk_notes.append(
            {
                "risk_note_id": risk_note_id,
                "operation_id": operation_id,
                "parity_constraint": row["parity_constraints"][0],
                "risk_statement": (
                    f"Optimization drift in `{row['symbol']}` can violate deterministic behavior "
                    "or strict/hardened compatibility boundaries."
                ),
                "allowed_optimization_levers": [
                    "allocation pre-sizing with identical iteration order",
                    "branch hoisting that preserves observable outcomes",
                    "single-lever data-structure tuning under differential parity checks",
                ],
                "forbidden_changes": [
                    "non-deterministic iteration or randomized tie-break behavior",
                    "strict/hardened policy collapse or silent fallback broadening",
                    "output-schema changes without explicit contract update",
                ],
                "rollback_trigger": (
                    f"Any strict-mode parity mismatch or missing replay metadata in `{operation_id}` gate runs."
                ),
                "verification_requirements": [
                    f"differential parity remains drift-free for `{operation_id}`",
                    f"structured logs include replay metadata for `{operation_id}`",
                    "benchmark delta does not exceed declared regression thresholds",
                ],
            }
        )
    return risk_notes


def build_hotspot_hypotheses() -> list[dict[str, Any]]:
    return [
        {
            "hypothesis_id": "HS-001",
            "operation_id": "algo_shortest_path_unweighted",
            "statement": "BFS frontier allocation churn dominates p95 latency on medium-density graphs.",
            "evidence_refs": [
                "artifacts/perf/phase2c/perf_baseline_matrix_v1.json",
                "artifacts/perf/phase2c/bfs_neighbor_iter_delta.json",
            ],
            "test_plan": "Profile queue growth + allocator samples on fixed graph density buckets.",
            "expected_signal": "queue push/pop hotspots exceed 30% of inclusive CPU time.",
            "linked_bead_ids": ["bd-315.24.6", "bd-315.8.1", "bd-315.8.2"],
        },
        {
            "hypothesis_id": "HS-002",
            "operation_id": "algo_connected_components",
            "statement": "Visited-set hash pressure is the dominant memory tail contributor for large sparse graphs.",
            "evidence_refs": [
                "artifacts/perf/phase2c/perf_baseline_matrix_v1.json",
                "artifacts/perf/phase2c/hotspot_one_lever_backlog_v1.json",
            ],
            "test_plan": "Track allocations and resident memory while sweeping node cardinality with fixed degree.",
            "expected_signal": "visited-state allocations account for majority of retained bytes at p99.",
            "linked_bead_ids": ["bd-315.24.6", "bd-315.8.1"],
        },
        {
            "hypothesis_id": "HS-003",
            "operation_id": "algo_closeness_centrality",
            "statement": "Repeated all-source traversals dominate runtime; batch-level caching may reduce wall-clock without parity drift.",
            "evidence_refs": [
                "artifacts/perf/phase2c/perf_baseline_matrix_v1.json",
                "artifacts/perf/phase2c/perf_regression_gate_report_v1.json",
            ],
            "test_plan": "Compare baseline against one-lever cache memoization with deterministic keying.",
            "expected_signal": "single-lever memoization lowers p95 latency while preserving exact output ordering.",
            "linked_bead_ids": ["bd-315.24.6", "bd-315.8.2", "bd-315.8.4"],
        },
        {
            "hypothesis_id": "HS-004",
            "operation_id": "rw_read_edgelist",
            "statement": "Line tokenization and malformed-row handling dominate parser CPU under adversarial input mix.",
            "evidence_refs": [
                "artifacts/perf/phase2c/hotspot_one_lever_backlog_v1.json",
                "artifacts/conformance/latest/structured_logs.jsonl",
            ],
            "test_plan": "Replay malformed-heavy corpora and sample parser branch hit rates.",
            "expected_signal": "malformed-row branches exceed nominal parse path in adversarial fixtures.",
            "linked_bead_ids": ["bd-315.24.6", "bd-315.6"],
        },
        {
            "hypothesis_id": "HS-005",
            "operation_id": "convert_from_adjacency",
            "statement": "High fan-out adjacency payloads create allocation spikes in edge materialization.",
            "evidence_refs": [
                "artifacts/perf/phase2c/perf_baseline_matrix_v1.json",
                "artifacts/e2e/latest/e2e_script_pack_events_v1.jsonl",
            ],
            "test_plan": "Run adjacency fan-out sweeps and compare allocation histograms.",
            "expected_signal": "allocation peaks scale superlinearly with fan-out unless pre-sized buffers are used.",
            "linked_bead_ids": ["bd-315.24.6", "bd-315.6"],
        },
        {
            "hypothesis_id": "HS-006",
            "operation_id": "gen_gnp_random_graph",
            "statement": "Random graph generation becomes quadratic bottleneck at higher node counts.",
            "evidence_refs": [
                "artifacts/perf/phase2c/perf_baseline_matrix_v1.json",
                "artifacts/perf/phase2c/hotspot_one_lever_backlog_v1.json",
            ],
            "test_plan": "Sweep n/p grids with fixed seed to isolate candidate loop costs.",
            "expected_signal": "edge sampling loop dominates total runtime above target density threshold.",
            "linked_bead_ids": ["bd-315.24.6", "bd-315.8.1"],
        },
        {
            "hypothesis_id": "HS-007",
            "operation_id": "dispatch_backend_resolve",
            "statement": "Backend capability filtering is negligible at current scale but can become visible with expanded registry breadth.",
            "evidence_refs": [
                "artifacts/perf/phase2c/perf_baseline_matrix_v1.json",
                "artifacts/conformance/latest/structured_logs.jsonl",
            ],
            "test_plan": "Synthetic backend fan-out benchmark with deterministic feature vectors.",
            "expected_signal": "resolve latency scales linearly with backend count and feature cardinality.",
            "linked_bead_ids": ["bd-315.24.6", "bd-315.23"],
        },
        {
            "hypothesis_id": "HS-008",
            "operation_id": "conformance_run_fixture",
            "statement": "Structured-log emission and mismatch serialization dominate harness runtime for larger fixture bundles.",
            "evidence_refs": [
                "artifacts/conformance/latest/structured_logs.jsonl",
                "artifacts/e2e/latest/e2e_script_pack_bundle_index_v1.json",
            ],
            "test_plan": "Measure fixture replay with/without structured log compression while preserving schema fidelity.",
            "expected_signal": "log serialization and mismatch formatting consume majority of post-execution wall-clock.",
            "linked_bead_ids": ["bd-315.24.6", "bd-315.6", "bd-315.10"],
        },
    ]


def build_crosswalk() -> list[dict[str, Any]]:
    return [
        {
            "bead_id": "bd-315.24.6",
            "title": "[DOC-PASS-05] Complexity, Performance, and Memory Characterization",
            "linked_operation_ids": [
                "algo_shortest_path_unweighted",
                "algo_connected_components",
                "algo_closeness_centrality",
                "rw_read_edgelist",
                "conformance_run_fixture",
            ],
            "status": "in_progress",
            "closure_signal": "artifact + schema + gate test all pass",
        },
        {
            "bead_id": "bd-315.8.1",
            "title": "[PERF-A] Baseline matrix + reproducible perf protocol",
            "linked_operation_ids": [
                "algo_shortest_path_unweighted",
                "algo_connected_components",
                "gen_gnp_random_graph",
            ],
            "status": "linked",
            "closure_signal": "baseline matrix evidence refreshed for hotspot families",
        },
        {
            "bead_id": "bd-315.8.2",
            "title": "[PERF-B] Hotspot profiling evidence + one-lever backlog",
            "linked_operation_ids": [
                "algo_closeness_centrality",
                "rw_read_edgelist",
                "convert_from_adjacency",
            ],
            "status": "linked",
            "closure_signal": "hotspot hypotheses map to profiler-backed one-lever candidates",
        },
        {
            "bead_id": "bd-315.8.4",
            "title": "[PERF-D] Continuous perf regression gate + drift forensics",
            "linked_operation_ids": [
                "algo_shortest_path_unweighted",
                "algo_closeness_centrality",
                "conformance_run_smoke",
            ],
            "status": "linked",
            "closure_signal": "p50/p95/p99 deltas bounded and forensics artifact attached",
        },
        {
            "bead_id": "bd-315.6",
            "title": "[FOUNDATION] E2E orchestrator + replay/forensics logging",
            "linked_operation_ids": [
                "rw_read_edgelist",
                "rw_read_json_graph",
                "conformance_run_fixture",
            ],
            "status": "linked",
            "closure_signal": "e2e replay logs cover hotspot failure envelopes",
        },
        {
            "bead_id": "bd-315.5",
            "title": "[FOUNDATION] Unit/property conventions + structured log contract",
            "linked_operation_ids": [
                "graph_add_edge_with_attrs",
                "dispatch_backend_resolve",
                "runtime_decision_theoretic_action",
            ],
            "status": "linked",
            "closure_signal": "unit/property evidence traces include deterministic replay metadata",
        },
    ]


def build_payload() -> dict[str, Any]:
    operations = build_operations()
    risk_notes = assign_risk_notes(operations)
    hotspot_hypotheses = build_hotspot_hypotheses()
    crosswalk = build_crosswalk()

    operations_by_family: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in operations:
        family_id = row["family_id"]
        payload_row = dict(row)
        payload_row.pop("family_id")
        operations_by_family[family_id].append(payload_row)

    families = []
    for family_id, meta in FAMILY_META.items():
        families.append(
            {
                "family_id": family_id,
                "name": meta["name"],
                "legacy_scope_paths": meta["legacy_scope_paths"],
                "rust_crates": meta["rust_crates"],
                "operations": operations_by_family.get(family_id, []),
            }
        )

    high_risk_count = sum(1 for row in operations if row["risk_tier"] == "high")
    summary = {
        "family_count": len(families),
        "operation_count": len(operations),
        "high_risk_operation_count": high_risk_count,
        "hotspot_hypothesis_count": len(hotspot_hypotheses),
        "optimization_risk_note_count": len(risk_notes),
    }

    return {
        "schema_version": "1.0.0",
        "artifact_id": "doc-pass-05-complexity-perf-memory-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "baseline_comparator": BASELINE_COMPARATOR,
        "characterization_summary": summary,
        "operation_families": families,
        "hotspot_hypotheses": hotspot_hypotheses,
        "optimization_risk_notes": risk_notes,
        "verification_bead_crosswalk": crosswalk,
        "alien_uplift_contract_card": ALIEN_UPLIFT_CONTRACT_CARD,
        "profile_first_artifacts": PROFILE_FIRST_ARTIFACTS,
        "optimization_lever_policy": OPTIMIZATION_LEVER_POLICY,
        "decision_theoretic_runtime_contract": DECISION_THEORETIC_RUNTIME_CONTRACT,
        "isomorphism_proof_artifacts": ISOMORPHISM_PROOF_ARTIFACTS,
        "structured_logging_evidence": STRUCTURED_LOGGING_EVIDENCE,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["characterization_summary"]
    lines = [
        "# DOC-PASS-05 Complexity, Performance, and Memory Characterization (V1)",
        "",
        f"- generated_at_utc: {payload['generated_at_utc']}",
        f"- baseline_comparator: {payload['baseline_comparator']}",
        f"- operation_families: {summary['family_count']}",
        f"- operations: {summary['operation_count']}",
        f"- high_risk_operations: {summary['high_risk_operation_count']}",
        f"- hotspot_hypotheses: {summary['hotspot_hypothesis_count']}",
        "",
        "## Family Overview",
        "",
        "| Family | Operations | High Risk Ops |",
        "|---|---:|---:|",
    ]

    for family in payload["operation_families"]:
        operations = family["operations"]
        high_risk = sum(1 for row in operations if row["risk_tier"] == "high")
        lines.append(
            f"| `{family['family_id']}` | {len(operations)} | {high_risk} |"
        )

    lines.extend(
        [
            "",
            "## Operation Matrix",
            "",
            "| Operation | Time | Space | Risk |",
            "|---|---|---|---|",
        ]
    )

    for family in payload["operation_families"]:
        for row in family["operations"]:
            lines.append(
                f"| `{row['operation_id']}` | {row['complexity_time']} | "
                f"{row['complexity_space']} | {row['risk_tier']} |"
            )

    lines.extend(["", "## Hotspot Hypotheses", ""])
    for hypothesis in payload["hotspot_hypotheses"]:
        lines.extend(
            [
                f"- `{hypothesis['hypothesis_id']}` ({hypothesis['operation_id']}): {hypothesis['statement']}",
                f"  - test_plan: {hypothesis['test_plan']}",
                f"  - expected_signal: {hypothesis['expected_signal']}",
            ]
        )

    lines.extend(
        [
            "",
            "## Optimization Risk Note Policy",
            "",
            "- Every operation is linked to at least one explicit parity risk note.",
            "- One-lever optimization policy is mandatory and enforced by validation.",
            "- Replay commands for all operation families are rch-offloaded.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    payload = build_payload()
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    OUTPUT_MD.write_text(render_markdown(payload), encoding="utf-8")
    print(f"doc_pass05_json:{OUTPUT_JSON}")
    print(f"doc_pass05_md:{OUTPUT_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
