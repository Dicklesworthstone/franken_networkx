#!/usr/bin/env python3
"""Generate E2E scenario matrix + oracle contract artifacts (bd-315.6.1)."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = REPO_ROOT / "crates/fnx-conformance/fixtures"
OUTPUT_JSON = REPO_ROOT / "artifacts/e2e/v1/e2e_scenario_matrix_oracle_contract_v1.json"
OUTPUT_MD = REPO_ROOT / "artifacts/e2e/v1/e2e_scenario_matrix_oracle_contract_v1.md"

SEED_NAMESPACE = "fnx-e2e-scenario-matrix-v1"

JOURNEY_SPECS: list[dict[str, Any]] = [
    {
        "journey_id": "J-GRAPH-CORE",
        "scoped_api_journey": "graph_core_mutation_and_shortest_path",
        "packet_id": "FNX-P2C-001",
        "description": "Graph mutation semantics and shortest-path observable parity.",
        "strict_fixture_ids": ["graph_core_shortest_path_strict.json"],
        "hardened_fixture_ids": ["graph_core_mutation_hardened.json"],
        "hardened_mode_strategy": "native_fixture",
    },
    {
        "journey_id": "J-VIEWS",
        "scoped_api_journey": "graph_view_neighbor_ordering",
        "packet_id": "FNX-P2C-002",
        "description": "View-layer neighbor ordering and cache-consistent traversal output.",
        "strict_fixture_ids": ["generated/view_neighbors_strict.json"],
        "hardened_fixture_ids": ["generated/view_neighbors_strict.json"],
        "hardened_mode_strategy": "mode_override_fixture",
    },
    {
        "journey_id": "J-DISPATCH",
        "scoped_api_journey": "dispatch_routing_and_fail_closed_guarding",
        "packet_id": "FNX-P2C-003",
        "description": "Backend resolution and decision-theoretic compatibility routing.",
        "strict_fixture_ids": ["generated/dispatch_route_strict.json"],
        "hardened_fixture_ids": ["generated/dispatch_route_strict.json"],
        "hardened_mode_strategy": "mode_override_fixture",
    },
    {
        "journey_id": "J-CONVERT",
        "scoped_api_journey": "edge_list_conversion_and_route_parity",
        "packet_id": "FNX-P2C-004",
        "description": "Conversion pipeline from edge-list payload to deterministic graph state.",
        "strict_fixture_ids": ["generated/convert_edge_list_strict.json"],
        "hardened_fixture_ids": ["generated/convert_edge_list_strict.json"],
        "hardened_mode_strategy": "mode_override_fixture",
    },
    {
        "journey_id": "J-SHORTEST-PATH-COMPONENTS",
        "scoped_api_journey": "components_and_connectivity_queries",
        "packet_id": "FNX-P2C-005",
        "description": "Connected-components and component-count algorithm contracts.",
        "strict_fixture_ids": ["generated/components_connected_strict.json"],
        "hardened_fixture_ids": ["generated/components_connected_strict.json"],
        "hardened_mode_strategy": "mode_override_fixture",
    },
    {
        "journey_id": "J-CENTRALITY",
        "scoped_api_journey": "degree_and_closeness_centrality_contracts",
        "packet_id": "FNX-P2C-005",
        "description": "Deterministic degree/closeness centrality scoring and ordering semantics.",
        "strict_fixture_ids": [
            "generated/centrality_degree_strict.json",
            "generated/centrality_closeness_strict.json",
        ],
        "hardened_fixture_ids": ["generated/centrality_closeness_strict.json"],
        "hardened_mode_strategy": "mode_override_fixture",
    },
    {
        "journey_id": "J-READWRITE",
        "scoped_api_journey": "readwrite_roundtrip_and_hardened_malformed_ingest",
        "packet_id": "FNX-P2C-006",
        "description": "Parser/serializer parity plus hardened malformed-input handling.",
        "strict_fixture_ids": [
            "generated/readwrite_roundtrip_strict.json",
            "generated/readwrite_json_roundtrip_strict.json",
        ],
        "hardened_fixture_ids": ["generated/readwrite_hardened_malformed.json"],
        "hardened_mode_strategy": "native_fixture",
    },
    {
        "journey_id": "J-GENERATORS",
        "scoped_api_journey": "path_cycle_complete_generator_contracts",
        "packet_id": "FNX-P2C-007",
        "description": "Deterministic graph generator edge/node ordering across classic families.",
        "strict_fixture_ids": [
            "generated/generators_path_strict.json",
            "generated/generators_cycle_strict.json",
            "generated/generators_complete_strict.json",
        ],
        "hardened_fixture_ids": ["generated/generators_cycle_strict.json"],
        "hardened_mode_strategy": "mode_override_fixture",
    },
    {
        "journey_id": "J-RUNTIME-OPTIONAL",
        "scoped_api_journey": "runtime_optional_backend_policy",
        "packet_id": "FNX-P2C-008",
        "description": "Optional backend compatibility and risk-aware dispatch behavior.",
        "strict_fixture_ids": ["generated/runtime_config_optional_strict.json"],
        "hardened_fixture_ids": ["generated/runtime_config_optional_strict.json"],
        "hardened_mode_strategy": "mode_override_fixture",
    },
    {
        "journey_id": "J-CONFORMANCE-HARNESS",
        "scoped_api_journey": "harness_execution_and_parity_snapshot",
        "packet_id": "FNX-P2C-009",
        "description": "Harness-level parity execution path and deterministic fixture replay contract.",
        "strict_fixture_ids": [
            "generated/conformance_harness_strict.json",
            "generated/adversarial_regression_bundle_v1.json",
        ],
        "hardened_fixture_ids": [
            "generated/conformance_harness_strict.json",
            "generated/adversarial_regression_bundle_v1.json",
        ],
        "hardened_mode_strategy": "mode_override_fixture",
    },
]

REQUIRED_WORKFLOW_CATEGORIES = [
    "happy_path",
    "regression_path",
    "malformed_input_path",
    "degraded_environment_path",
]

WORKFLOW_CATEGORY_BY_JOURNEY = {
    "J-GRAPH-CORE": "happy_path",
    "J-VIEWS": "regression_path",
    "J-DISPATCH": "regression_path",
    "J-CONVERT": "regression_path",
    "J-SHORTEST-PATH-COMPONENTS": "happy_path",
    "J-CENTRALITY": "regression_path",
    "J-READWRITE": "malformed_input_path",
    "J-GENERATORS": "happy_path",
    "J-RUNTIME-OPTIONAL": "degraded_environment_path",
    "J-CONFORMANCE-HARNESS": "happy_path",
}

UNIT_HOOK_TARGET_BY_JOURNEY = {
    "J-GRAPH-CORE": {
        "crate": "fnx-classes",
        "artifact_ref": "crates/fnx-classes/src/lib.rs",
    },
    "J-VIEWS": {
        "crate": "fnx-views",
        "artifact_ref": "crates/fnx-views/src/lib.rs",
    },
    "J-DISPATCH": {
        "crate": "fnx-dispatch",
        "artifact_ref": "crates/fnx-dispatch/src/lib.rs",
    },
    "J-CONVERT": {
        "crate": "fnx-convert",
        "artifact_ref": "crates/fnx-convert/src/lib.rs",
    },
    "J-SHORTEST-PATH-COMPONENTS": {
        "crate": "fnx-algorithms",
        "artifact_ref": "crates/fnx-algorithms/src/lib.rs",
    },
    "J-CENTRALITY": {
        "crate": "fnx-algorithms",
        "artifact_ref": "crates/fnx-algorithms/src/lib.rs",
    },
    "J-READWRITE": {
        "crate": "fnx-readwrite",
        "artifact_ref": "crates/fnx-readwrite/src/lib.rs",
    },
    "J-GENERATORS": {
        "crate": "fnx-generators",
        "artifact_ref": "crates/fnx-generators/src/lib.rs",
    },
    "J-RUNTIME-OPTIONAL": {
        "crate": "fnx-runtime",
        "artifact_ref": "crates/fnx-runtime/src/lib.rs",
    },
    "J-CONFORMANCE-HARNESS": {
        "crate": "fnx-conformance",
        "artifact_ref": "crates/fnx-conformance/src/lib.rs",
    },
}

DIFFERENTIAL_HOOK_OVERRIDE_BY_JOURNEY = {
    "J-READWRITE": {
        "fixture_id": "generated/readwrite_hardened_malformed.json",
        "mode": "hardened",
    },
    "J-RUNTIME-OPTIONAL": {
        "fixture_id": "generated/runtime_config_optional_strict.json",
        "mode": "hardened",
    },
}

TIE_BREAK_BY_OPERATION = {
    "add_node": "Node insertion order is deterministic and preserved in snapshot iteration.",
    "add_edge": "Edge insertion follows deterministic endpoint ordering tied to node insertion order.",
    "remove_node": "Node deletion deterministically removes incident edges and retains remaining order.",
    "remove_edge": "Explicit endpoint removal is deterministic and side-effect bounded.",
    "shortest_path_query": "BFS predecessor choice follows deterministic neighbor insertion ordering.",
    "degree_centrality_query": "Centrality score ordering is deterministic for serialization and oracle diffs.",
    "closeness_centrality_query": "WF-improved traversal order is deterministic for equal-distance handling.",
    "connected_components_query": "Component enumeration follows deterministic first-seen traversal order.",
    "number_connected_components_query": "Connectivity count invariant is deterministic for identical input graphs.",
    "dispatch_resolve": "Backend selection ties are resolved deterministically by registry order and policy.",
    "convert_edge_list": "Edge-list row order deterministically maps to graph insertion and traversal order.",
    "convert_adjacency": "Adjacency payload normalization is deterministic before graph mutation.",
    "read_edgelist": "Line-order ingest is deterministic; hardened malformed rows emit deterministic warnings.",
    "write_edgelist": "Serializer line ordering is deterministic from canonical edge iteration order.",
    "read_json_graph": "JSON node/edge ingestion normalizes ordering deterministically.",
    "write_json_graph": "JSON output preserves deterministic node/edge ordering for parity checks.",
    "view_neighbors_query": "Neighbor view output preserves deterministic adjacency insertion ordering.",
    "generate_path_graph": "Generator emits path nodes/edges in deterministic ascending order.",
    "generate_cycle_graph": "Cycle closure edge placement is deterministic and fixture-locked.",
    "generate_complete_graph": "Complete graph edges emit in deterministic lexicographic pair order.",
    "generate_empty_graph": "Empty graph node initialization order is deterministic by index.",
}

EXPECTED_REFS_BY_OPERATION = {
    "add_node": ["expected.graph.nodes", "expected.graph.edges"],
    "add_edge": ["expected.graph.nodes", "expected.graph.edges"],
    "remove_node": ["expected.graph.nodes", "expected.graph.edges"],
    "remove_edge": ["expected.graph.edges"],
    "shortest_path_query": ["expected.shortest_path_unweighted"],
    "degree_centrality_query": ["expected.degree_centrality"],
    "closeness_centrality_query": ["expected.closeness_centrality"],
    "connected_components_query": ["expected.connected_components"],
    "number_connected_components_query": ["expected.number_connected_components"],
    "dispatch_resolve": ["expected.dispatch"],
    "convert_edge_list": ["expected.graph", "expected.shortest_path_unweighted"],
    "convert_adjacency": ["expected.graph"],
    "read_edgelist": ["expected.graph", "expected.warnings_contains"],
    "write_edgelist": ["expected.serialized_edgelist"],
    "read_json_graph": ["expected.graph"],
    "write_json_graph": ["expected.serialized_json_graph"],
    "view_neighbors_query": ["expected.view_neighbors"],
    "generate_path_graph": ["expected.graph", "expected.number_connected_components"],
    "generate_cycle_graph": ["expected.graph", "expected.connected_components"],
    "generate_complete_graph": ["expected.graph", "expected.number_connected_components"],
    "generate_empty_graph": ["expected.graph"],
}

FAILURE_CLASS_BY_OPERATION = {
    "add_node": "graph_mutation",
    "add_edge": "graph_mutation",
    "remove_node": "graph_mutation",
    "remove_edge": "graph_mutation",
    "shortest_path_query": "algorithm",
    "degree_centrality_query": "algorithm_centrality",
    "closeness_centrality_query": "algorithm_centrality",
    "connected_components_query": "algorithm_components",
    "number_connected_components_query": "algorithm_components",
    "dispatch_resolve": "dispatch",
    "convert_edge_list": "convert",
    "convert_adjacency": "convert",
    "read_edgelist": "readwrite",
    "write_edgelist": "readwrite",
    "read_json_graph": "readwrite",
    "write_json_graph": "readwrite",
    "view_neighbors_query": "views",
    "generate_path_graph": "generators",
    "generate_cycle_graph": "generators",
    "generate_complete_graph": "generators",
    "generate_empty_graph": "generators",
}

ASSERTION_RULES = {
    "graph": {
        "expected_ref": "expected.graph",
        "contract": "Node and edge snapshots must match oracle values exactly (including deterministic order and attrs).",
        "tie_break_behavior": "Node/edge ordering follows deterministic insertion order parity.",
        "failure_class": "graph_mutation",
    },
    "shortest_path_unweighted": {
        "expected_ref": "expected.shortest_path_unweighted",
        "contract": "Shortest-path output node sequence must match oracle path exactly.",
        "tie_break_behavior": "Equal-length path ties resolve via deterministic BFS neighbor ordering.",
        "failure_class": "algorithm",
    },
    "degree_centrality": {
        "expected_ref": "expected.degree_centrality",
        "contract": "Degree centrality scores must match oracle values and deterministic node ordering.",
        "tie_break_behavior": "Deterministic node ordering is used for equal-score serialization.",
        "failure_class": "algorithm_centrality",
    },
    "closeness_centrality": {
        "expected_ref": "expected.closeness_centrality",
        "contract": "Closeness centrality scores must match oracle values under WF-improved semantics.",
        "tie_break_behavior": "Deterministic traversal and node ordering govern equal-distance resolution.",
        "failure_class": "algorithm_centrality",
    },
    "connected_components": {
        "expected_ref": "expected.connected_components",
        "contract": "Connected components listing must match oracle component partitioning and order.",
        "tie_break_behavior": "Component order follows deterministic first-seen traversal order.",
        "failure_class": "algorithm_components",
    },
    "number_connected_components": {
        "expected_ref": "expected.number_connected_components",
        "contract": "Connected component count must match oracle scalar output exactly.",
        "tie_break_behavior": "Deterministic component traversal ensures reproducible counts and witnesses.",
        "failure_class": "algorithm_components",
    },
    "dispatch": {
        "expected_ref": "expected.dispatch",
        "contract": "Selected backend/action pair must match oracle dispatch policy output.",
        "tie_break_behavior": "Backend tie-breaking follows deterministic registry ordering and risk policy.",
        "failure_class": "dispatch",
    },
    "serialized_edgelist": {
        "expected_ref": "expected.serialized_edgelist",
        "contract": "Serialized edge-list payload must match oracle-normalized text output exactly.",
        "tie_break_behavior": "Serializer emits deterministic edge order from canonical snapshot iteration.",
        "failure_class": "readwrite",
    },
    "serialized_json_graph": {
        "expected_ref": "expected.serialized_json_graph",
        "contract": "Serialized JSON graph payload must match oracle-normalized JSON output exactly.",
        "tie_break_behavior": "Serializer emits deterministic node/edge ordering and field stability.",
        "failure_class": "readwrite",
    },
    "view_neighbors": {
        "expected_ref": "expected.view_neighbors",
        "contract": "Neighbor view output must match oracle sequence exactly.",
        "tie_break_behavior": "Neighbor ordering is deterministic via adjacency insertion order.",
        "failure_class": "views",
    },
    "warnings_contains": {
        "expected_ref": "expected.warnings_contains",
        "contract": "Hardened-mode warning fragments must include documented malformed-input diagnostics.",
        "tie_break_behavior": "Warning emission order follows deterministic parse-line progression.",
        "failure_class": "readwrite",
    },
}

FAILURE_CLASS_TAXONOMY = [
    {
        "failure_class": "fixture_io",
        "description": "Fixture file cannot be read from deterministic fixture inventory.",
        "source": "fnx-conformance fixture loading",
    },
    {
        "failure_class": "fixture_schema",
        "description": "Fixture payload is malformed or violates expected operation schema.",
        "source": "fnx-conformance fixture parsing",
    },
    {
        "failure_class": "graph_mutation",
        "description": "Graph mutation output diverges from expected nodes/edges/attrs parity.",
        "source": "Graph operation execution",
    },
    {
        "failure_class": "algorithm",
        "description": "Algorithm output (e.g., shortest path) diverges from oracle expectation.",
        "source": "fnx-algorithms parity checks",
    },
    {
        "failure_class": "algorithm_centrality",
        "description": "Centrality score/ordering output diverges from oracle expectation.",
        "source": "fnx-algorithms centrality checks",
    },
    {
        "failure_class": "algorithm_components",
        "description": "Component partition/count output diverges from oracle expectation.",
        "source": "fnx-algorithms components checks",
    },
    {
        "failure_class": "dispatch",
        "description": "Dispatch route/action does not match deterministic policy expectation.",
        "source": "fnx-dispatch parity checks",
    },
    {
        "failure_class": "convert",
        "description": "Conversion pipeline output diverges from expected normalized graph state.",
        "source": "fnx-convert parity checks",
    },
    {
        "failure_class": "readwrite",
        "description": "Read/write parser or serializer output diverges from oracle expectations.",
        "source": "fnx-readwrite parity checks",
    },
    {
        "failure_class": "views",
        "description": "Graph view query output diverges from deterministic ordering expectations.",
        "source": "fnx-views parity checks",
    },
    {
        "failure_class": "generators",
        "description": "Generator-produced graph structure/order diverges from oracle fixtures.",
        "source": "fnx-generators parity checks",
    },
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def list_fixture_ids() -> list[str]:
    fixture_ids = [
        path.relative_to(FIXTURE_ROOT).as_posix()
        for path in sorted(FIXTURE_ROOT.rglob("*.json"))
        if path.name != "smoke_case.json"
    ]
    return fixture_ids


def fixture_payloads() -> dict[str, dict[str, Any]]:
    payloads: dict[str, dict[str, Any]] = {}
    for fixture_id in list_fixture_ids():
        payloads[fixture_id] = load_json(FIXTURE_ROOT / fixture_id)
    return payloads


def fnv1a64(text: str) -> int:
    value = 0xCBF29CE484222325
    for byte in text.encode("utf-8"):
        value ^= byte
        value = (value * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return value


def deterministic_seed(journey_id: str, mode: str, fixture_id: str) -> int:
    return fnv1a64(f"{SEED_NAMESPACE}|{journey_id}|{mode}|{fixture_id}")


def expected_refs_for_op(op_name: str, expected_keys: list[str]) -> list[str]:
    refs = EXPECTED_REFS_BY_OPERATION.get(op_name, [])
    available_refs: set[str] = set()
    for key in expected_keys:
        available_refs.add(f"expected.{key}")
    if "graph" in expected_keys:
        available_refs.add("expected.graph.nodes")
        available_refs.add("expected.graph.edges")
    filtered = [ref for ref in refs if ref in available_refs]
    if filtered:
        return sorted(dict.fromkeys(filtered))
    fallback = sorted(f"expected.{key}" for key in expected_keys)
    if "graph" in expected_keys and "expected.graph" not in fallback:
        fallback.append("expected.graph")
    return fallback


def step_contract(primary_fixture: dict[str, Any]) -> list[dict[str, Any]]:
    expected_keys = sorted(primary_fixture.get("expected", {}).keys())
    rows = []
    for idx, operation in enumerate(primary_fixture.get("operations", []), start=1):
        op_name = operation.get("op", "")
        rows.append(
            {
                "step_id": f"S{idx:02d}",
                "operation": op_name,
                "expected_outputs": expected_refs_for_op(op_name, expected_keys),
                "tie_break_behavior": TIE_BREAK_BY_OPERATION.get(
                    op_name,
                    "Deterministic ordering is required for all observable outputs.",
                ),
                "failure_classes": [
                    FAILURE_CLASS_BY_OPERATION.get(op_name, "fixture_schema"),
                ],
            }
        )
    return rows


def oracle_assertions(primary_fixture: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for idx, expected_key in enumerate(sorted(primary_fixture.get("expected", {}).keys()), start=1):
        rule = ASSERTION_RULES.get(
            expected_key,
            {
                "expected_ref": f"expected.{expected_key}",
                "contract": "Expected output must match fixture oracle contract exactly.",
                "tie_break_behavior": "Deterministic ordering is required for replay parity.",
                "failure_class": "fixture_schema",
            },
        )
        rows.append(
            {
                "assertion_id": f"A{idx:02d}",
                "expected_ref": rule["expected_ref"],
                "contract": rule["contract"],
                "tie_break_behavior": rule["tie_break_behavior"],
                "failure_class": rule["failure_class"],
            }
        )
    return rows


def path_failure_classes(primary_fixture: dict[str, Any], steps: list[dict[str, Any]]) -> list[str]:
    classes = {"fixture_io", "fixture_schema"}
    for step in steps:
        classes.update(step["failure_classes"])
    for assertion in oracle_assertions(primary_fixture):
        classes.add(assertion["failure_class"])
    return sorted(classes)


def replay_command(fixture_id: str, mode: str) -> str:
    return (
        "CARGO_TARGET_DIR=target-codex cargo run -q -p fnx-conformance --bin run_smoke -- "
        f"--fixture {fixture_id} --mode {mode}"
    )


def journey_token(journey_id: str) -> str:
    return journey_id.removeprefix("J-")


def journey_slug(journey_id: str) -> str:
    return journey_token(journey_id).lower()


def workflow_scenario_id(journey_id: str) -> str:
    return f"WF-{journey_token(journey_id)}-001"


def build_journey_coverage_hooks(journeys: list[dict[str, Any]]) -> list[dict[str, Any]]:
    matrix_report_ref = "artifacts/e2e/latest/e2e_scenario_matrix_report_v1.json"
    scenario_report_ref = "artifacts/e2e/latest/e2e_user_workflow_scenario_report_v1.json"
    hooks: list[dict[str, Any]] = []

    for journey in journeys:
        journey_id = journey["journey_id"]
        slug = journey_slug(journey_id)
        scenario_id = workflow_scenario_id(journey_id)
        category = WORKFLOW_CATEGORY_BY_JOURNEY[journey_id]

        unit_target = UNIT_HOOK_TARGET_BY_JOURNEY[journey_id]
        unit_hook = {
            "hook_id": f"unit-{slug}",
            "command": f"rch exec -- cargo test -p {unit_target['crate']} -- --nocapture",
            "artifact_ref": unit_target["artifact_ref"],
        }

        diff_override = DIFFERENTIAL_HOOK_OVERRIDE_BY_JOURNEY.get(journey_id)
        if diff_override is None:
            diff_fixture_id = journey["strict_path"]["fixture_id"]
            diff_mode = "strict"
        else:
            diff_fixture_id = diff_override["fixture_id"]
            diff_mode = diff_override["mode"]
        differential_hook = {
            "hook_id": f"diff-{slug}",
            "command": (
                "rch exec -- cargo run -q -p fnx-conformance --bin run_smoke -- "
                f"--fixture {diff_fixture_id} --mode {diff_mode}"
            ),
            "artifact_ref": f"crates/fnx-conformance/fixtures/{diff_fixture_id}",
        }

        e2e_hook = {
            "hook_id": f"e2e-{slug}",
            "command": (
                "rch exec -- cargo test -q -p fnx-conformance "
                "--test e2e_scenario_matrix_gate -- --nocapture"
            ),
            "artifact_ref": matrix_report_ref,
        }

        hooks.append(
            {
                "journey_id": journey_id,
                "scenario_id": scenario_id,
                "category": category,
                "unit_hooks": [unit_hook],
                "differential_hooks": [differential_hook],
                "e2e_hooks": [e2e_hook],
                "report_refs": [matrix_report_ref, scenario_report_ref],
            }
        )

    return hooks


def build_path(
    *,
    journey_id: str,
    mode: str,
    mode_strategy: str,
    fixture_ids: list[str],
    fixtures: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    primary_fixture_id = fixture_ids[0]
    primary_fixture = fixtures[primary_fixture_id]
    steps = step_contract(primary_fixture)
    assertions = oracle_assertions(primary_fixture)
    return {
        "mode": mode,
        "mode_strategy": mode_strategy,
        "fixture_id": primary_fixture_id,
        "fixture_ids": fixture_ids,
        "deterministic_seed": deterministic_seed(journey_id, mode, primary_fixture_id),
        "replay_command": replay_command(primary_fixture_id, mode),
        "step_contract": steps,
        "oracle_assertions": assertions,
        "failure_classes": path_failure_classes(primary_fixture, steps),
    }


def build_payload() -> dict[str, Any]:
    fixtures = fixture_payloads()
    fixture_ids = list_fixture_ids()
    missing = sorted(
        {
            fixture_id
            for journey in JOURNEY_SPECS
            for fixture_id in (
                journey["strict_fixture_ids"] + journey["hardened_fixture_ids"]
            )
            if fixture_id not in fixtures
        }
    )
    if missing:
        raise SystemExit(f"missing fixture ids in JOURNEY_SPECS: {missing}")

    structured_schema_path = "artifacts/conformance/schema/v1/structured_test_log_schema_v1.json"
    e2e_step_schema_path = "artifacts/conformance/schema/v1/e2e_step_trace_schema_v1.json"
    forensics_schema_path = "artifacts/conformance/schema/v1/forensics_bundle_index_schema_v1.json"
    structured_schema = load_json(REPO_ROOT / structured_schema_path)
    e2e_step_schema = load_json(REPO_ROOT / e2e_step_schema_path)
    forensics_schema = load_json(REPO_ROOT / forensics_schema_path)

    journeys: list[dict[str, Any]] = []
    covered_fixture_ids: set[str] = set()

    for spec in JOURNEY_SPECS:
        strict_fixture_ids = list(spec["strict_fixture_ids"])
        hardened_fixture_ids = list(spec["hardened_fixture_ids"])
        covered_fixture_ids.update(strict_fixture_ids)
        covered_fixture_ids.update(hardened_fixture_ids)
        strict_path = build_path(
            journey_id=spec["journey_id"],
            mode="strict",
            mode_strategy="native_fixture",
            fixture_ids=strict_fixture_ids,
            fixtures=fixtures,
        )
        hardened_path = build_path(
            journey_id=spec["journey_id"],
            mode="hardened",
            mode_strategy=spec["hardened_mode_strategy"],
            fixture_ids=hardened_fixture_ids,
            fixtures=fixtures,
        )
        journeys.append(
            {
                "journey_id": spec["journey_id"],
                "scoped_api_journey": spec["scoped_api_journey"],
                "packet_id": spec["packet_id"],
                "description": spec["description"],
                "strict_path": strict_path,
                "hardened_path": hardened_path,
            }
        )

    uncovered_fixture_ids = sorted(set(fixture_ids) - covered_fixture_ids)

    payload = {
        "schema_version": "1.0.0",
        "artifact_id": "e2e-scenario-matrix-oracle-contract-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "baseline_comparator": "legacy_networkx/main@python3.12",
        "journey_summary": {
            "journey_count": len(journeys),
            "strict_journey_count": len(journeys),
            "hardened_journey_count": len(journeys),
            "fixture_inventory_count": len(fixture_ids),
            "covered_fixture_count": len(covered_fixture_ids),
            "uncovered_fixture_count": len(uncovered_fixture_ids),
        },
        "deterministic_seed_policy": {
            "seed_namespace": SEED_NAMESPACE,
            "seed_algorithm": "fnv1a64(namespace|journey_id|mode|fixture_id)",
            "seed_lock_version": "1.0.0",
            "determinism_invariant": "same journey/mode/fixture tuple always yields identical u64 seed",
        },
        "replay_metadata_contract": {
            "schema_refs": [
                structured_schema_path,
                e2e_step_schema_path,
                forensics_schema_path,
            ],
            "structured_log_required_fields": structured_schema["required_fields"],
            "structured_log_replay_critical_fields": structured_schema["replay_critical_fields"],
            "e2e_step_required_fields": e2e_step_schema["required_fields"],
            "e2e_step_invariants": e2e_step_schema["invariants"],
            "forensics_bundle_required_fields": forensics_schema["required_fields"],
            "forensics_bundle_invariants": forensics_schema["invariants"],
            "validation_command": (
                "./scripts/validate_e2e_scenario_matrix.py "
                "--artifact artifacts/e2e/v1/e2e_scenario_matrix_oracle_contract_v1.json"
            ),
        },
        "journeys": journeys,
        "coverage_manifest": {
            "fixture_inventory": fixture_ids,
            "covered_fixture_ids": sorted(covered_fixture_ids),
            "uncovered_fixture_ids": uncovered_fixture_ids,
        },
        "failure_class_taxonomy": FAILURE_CLASS_TAXONOMY,
        "alien_uplift_contract_card": {
            "ev_score": 2.48,
            "baseline_comparator": "legacy_networkx/main@python3.12",
            "optimization_lever": "single canonical journey matrix for strict/hardened e2e orchestration planning",
            "decision_hypothesis": "Explicit scenario/oracle contracts reduce parity drift and replay triage latency.",
        },
        "profile_first_artifacts": {
            "baseline": "artifacts/perf/BASELINE_BFS_V1.md",
            "hotspot": "artifacts/perf/OPPORTUNITY_MATRIX.md",
            "delta": "artifacts/perf/phase2c/bfs_neighbor_iter_delta.json",
        },
        "decision_theoretic_runtime_contract": {
            "states": [
                "scenario_declared",
                "scenario_eligible",
                "scenario_executed",
                "scenario_blocked",
            ],
            "actions": ["allow_run", "full_validate", "fail_closed"],
            "loss_model": (
                "Minimize oracle-parity loss and replay incompleteness while preserving deterministic strict/hardened behavior."
            ),
            "safe_mode_fallback": "fail_closed",
            "fallback_thresholds": {
                "max_uncovered_fixtures": 0,
                "min_journey_count": 10,
                "min_replay_schema_refs": 3,
            },
        },
        "isomorphism_proof_artifacts": [
            "artifacts/proofs/ISOMORPHISM_PROOF_FNX_P2C_001_V1.md",
            "artifacts/proofs/ISOMORPHISM_PROOF_FNX_P2C_005_V1.md",
            "artifacts/proofs/ISOMORPHISM_PROOF_FNX_P2C_006_V1.md",
            "artifacts/proofs/ISOMORPHISM_PROOF_FNX_P2C_007_V1.md",
        ],
        "structured_logging_evidence": [
            "artifacts/conformance/latest/structured_logs.jsonl",
            "artifacts/conformance/latest/structured_log_emitter_normalization_report.json",
            "artifacts/conformance/latest/telemetry_dependent_unblock_matrix_v1.json",
        ],
    }
    return payload


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# E2E Scenario Matrix + Oracle Contract (V1)",
        "",
        f"- generated_at_utc: {payload['generated_at_utc']}",
        f"- baseline_comparator: {payload['baseline_comparator']}",
        f"- journey_count: {payload['journey_summary']['journey_count']}",
        f"- fixture_inventory_count: {payload['journey_summary']['fixture_inventory_count']}",
        f"- covered_fixture_count: {payload['journey_summary']['covered_fixture_count']}",
        f"- uncovered_fixture_count: {payload['journey_summary']['uncovered_fixture_count']}",
        "",
        "## Journey Coverage",
        "",
        "| Journey | Packet | Strict Fixture | Hardened Fixture | Hardened Strategy |",
        "|---|---|---|---|---|",
    ]
    for journey in payload["journeys"]:
        strict_fixture = journey["strict_path"]["fixture_id"]
        hardened_fixture = journey["hardened_path"]["fixture_id"]
        lines.append(
            f"| `{journey['journey_id']}` | `{journey['packet_id']}` | "
            f"`{strict_fixture}` | `{hardened_fixture}` | "
            f"`{journey['hardened_path']['mode_strategy']}` |"
        )

    lines.extend(
        [
            "",
            "## Replay Metadata Contract",
            "",
            "| Schema Ref |",
            "|---|",
        ]
    )
    for schema_ref in payload["replay_metadata_contract"]["schema_refs"]:
        lines.append(f"| `{schema_ref}` |")

    lines.extend(
        [
            "",
            "## Failure Class Taxonomy",
            "",
            "| Failure Class | Source | Description |",
            "|---|---|---|",
        ]
    )
    for row in payload["failure_class_taxonomy"]:
        lines.append(
            f"| `{row['failure_class']}` | `{row['source']}` | {row['description']} |"
        )

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-json",
        default=OUTPUT_JSON.as_posix(),
        help="Output path for JSON artifact",
    )
    parser.add_argument(
        "--output-md",
        default=OUTPUT_MD.as_posix(),
        help="Output path for markdown summary",
    )
    args = parser.parse_args()

    payload = build_payload()
    output_json = Path(args.output_json)
    output_md = Path(args.output_md)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    output_md.write_text(render_markdown(payload), encoding="utf-8")

    print(
        json.dumps(
            {
                "status": "ok",
                "output_json": output_json.as_posix(),
                "output_md": output_md.as_posix(),
                "journey_count": payload["journey_summary"]["journey_count"],
                "fixture_inventory_count": payload["journey_summary"]["fixture_inventory_count"],
                "uncovered_fixture_count": payload["journey_summary"]["uncovered_fixture_count"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
