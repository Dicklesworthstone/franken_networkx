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
        "strict_fixture_ids": [
            "generated/convert_edge_list_strict.json",
            "generated/convert_adjacency_strict.json",
        ],
        "hardened_fixture_ids": [
            "generated/convert_edge_list_strict.json",
            "generated/convert_adjacency_strict.json",
        ],
        "hardened_mode_strategy": "mode_override_fixture",
    },
    {
        "journey_id": "J-SHORTEST-PATH-COMPONENTS",
        "scoped_api_journey": "components_weighted_path_and_flow_queries",
        "packet_id": "FNX-P2C-005",
        "description": (
            "Connected-components, weighted-shortest-path, max-flow, and minimum-cut "
            "algorithm contracts."
        ),
        "strict_fixture_ids": [
            "generated/components_connected_strict.json",
            "generated/shortest_path_weighted_strict.json",
            "generated/shortest_path_bellman_ford_strict.json",
            "generated/shortest_path_multi_source_dijkstra_strict.json",
            "generated/flow_max_strict.json",
            "generated/flow_min_cut_strict.json",
            "generated/flow_edge_connectivity_petersen_strict.json",
            "generated/flow_max_large_strict.json",
            "generated/flow_max_serial_bottleneck_strict.json",
            "generated/flow_max_zero_capacity_strict.json",
            "generated/flow_min_cut_bottleneck_strict.json",
            "generated/flow_st_edge_cut_bottleneck_strict.json",
            "generated/flow_edge_connectivity_strict.json",
        ],
        "hardened_fixture_ids": [
            "generated/flow_max_missing_capacity_hardened.json",
            "generated/shortest_path_disconnected_hardened.json",
            "generated/components_connected_strict.json",
            "generated/shortest_path_weighted_strict.json",
            "generated/shortest_path_bellman_ford_strict.json",
            "generated/shortest_path_multi_source_dijkstra_strict.json",
            "generated/flow_max_strict.json",
            "generated/flow_min_cut_strict.json",
            "generated/flow_edge_connectivity_petersen_strict.json",
            "generated/flow_max_large_strict.json",
            "generated/flow_max_serial_bottleneck_strict.json",
            "generated/flow_max_zero_capacity_strict.json",
            "generated/flow_min_cut_bottleneck_strict.json",
            "generated/flow_st_edge_cut_bottleneck_strict.json",
            "generated/flow_edge_connectivity_strict.json",
        ],
        "hardened_mode_strategy": "mode_override_fixture",
    },
    {
        "journey_id": "J-STRUCTURE",
        "scoped_api_journey": "articulation_and_bridge_structure_contracts",
        "packet_id": "FNX-P2C-005",
        "description": "Deterministic articulation-point and bridge-structure parity contracts.",
        "strict_fixture_ids": [
            "generated/structure_articulation_points_strict.json",
            "generated/structure_bridges_strict.json",
            "generated/distance_measures_strict.json",
            "generated/average_shortest_path_length_strict.json",
            "generated/is_connected_density_strict.json",
            "generated/has_path_strict.json",
            "generated/minimum_spanning_tree_strict.json",
            "generated/tree_forest_strict.json",
            "generated/greedy_color_strict.json",
            "generated/bipartite_strict.json",
            "generated/core_number_strict.json",
            "generated/cliques_strict.json",
            "generated/node_connectivity_strict.json",
            "generated/cycle_basis_strict.json",
            "generated/paths_efficiency_cover_strict.json",
            "generated/euler_circuit_strict.json",
            "generated/euler_path_strict.json",
        ],
        "hardened_fixture_ids": [
            "generated/structure_articulation_points_strict.json",
            "generated/structure_bridges_strict.json",
            "generated/distance_measures_strict.json",
            "generated/average_shortest_path_length_strict.json",
            "generated/is_connected_density_strict.json",
            "generated/has_path_strict.json",
            "generated/minimum_spanning_tree_strict.json",
            "generated/tree_forest_strict.json",
            "generated/greedy_color_strict.json",
            "generated/bipartite_strict.json",
            "generated/core_number_strict.json",
            "generated/cliques_strict.json",
            "generated/node_connectivity_strict.json",
            "generated/cycle_basis_strict.json",
            "generated/paths_efficiency_cover_strict.json",
            "generated/euler_circuit_strict.json",
            "generated/euler_path_strict.json",
        ],
        "hardened_mode_strategy": "mode_override_fixture",
    },
    {
        "journey_id": "J-CENTRALITY",
        "scoped_api_journey": "degree_closeness_and_edge_betweenness_centrality_contracts",
        "packet_id": "FNX-P2C-005",
        "description": (
            "Deterministic degree/closeness/edge-betweenness centrality scoring and "
            "ordering semantics."
        ),
        "strict_fixture_ids": [
            "generated/centrality_edge_betweenness_strict.json",
            "generated/centrality_degree_strict.json",
            "generated/centrality_betweenness_strict.json",
            "generated/centrality_closeness_strict.json",
            "generated/centrality_harmonic_strict.json",
            "generated/centrality_katz_strict.json",
            "generated/centrality_hits_strict.json",
            "generated/centrality_pagerank_strict.json",
            "generated/centrality_betweenness_petersen_strict.json",
            "generated/centrality_closeness_turan_strict.json",
            "generated/centrality_degree_petersen_strict.json",
            "generated/centrality_eigenvector_wheel_strict.json",
            "generated/centrality_harmonic_grid_strict.json",
            "generated/centrality_katz_barbell_strict.json",
            "generated/centrality_pagerank_barabasi_strict.json",
            "generated/centrality_eigenvector_strict.json",
            "generated/clustering_coefficient_strict.json",
            "generated/triangles_square_clustering_strict.json",
            "generated/avg_neighbor_degree_strict.json",
        ],
        "hardened_fixture_ids": [
            "generated/centrality_degree_selfloop_hardened.json",
            "generated/centrality_closeness_strict.json",
            "generated/triangles_square_clustering_strict.json",
            "generated/avg_neighbor_degree_strict.json",
        ],
        "hardened_mode_strategy": "mode_override_fixture",
    },
    {
        "journey_id": "J-MATCHING",
        "scoped_api_journey": "matching_maximal_and_weighted_contracts",
        "packet_id": "FNX-P2C-005",
        "description": (
            "Deterministic maximal matching, max-weight matching, and min-weight matching "
            "algorithm contracts."
        ),
        "strict_fixture_ids": [
            "generated/matching_maximal_strict.json",
            "generated/matching_max_weight_strict.json",
            "generated/matching_min_weight_strict.json",
            "generated/matching_max_weight_large_strict.json",
            "generated/matching_min_weight_bipartite_strict.json",
        ],
        "hardened_fixture_ids": [
            "generated/matching_maximal_isolated_hardened.json",
            "generated/matching_maximal_strict.json",
            "generated/matching_max_weight_strict.json",
            "generated/matching_min_weight_strict.json",
            "generated/matching_max_weight_large_strict.json",
            "generated/matching_min_weight_bipartite_strict.json",
        ],
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
            "generated/readwrite_adjlist_roundtrip_strict.json",
            "generated/readwrite_graphml_roundtrip_strict.json",
        ],
        "hardened_fixture_ids": [
            "generated/readwrite_hardened_malformed.json",
            "generated/readwrite_incompatible_feature_hardened.json",
            "adversarial/empty_input.json",
            "adversarial/huge_star.json",
            "adversarial/negative_weights.json",
            "adversarial/self_loops_only.json",
            "adversarial/unicode_nodes.json",
        ],
        "hardened_mode_strategy": "native_fixture",
    },
    {
        "journey_id": "J-GENERATORS",
        "scoped_api_journey": "path_cycle_complete_generator_contracts",
        "packet_id": "FNX-P2C-007",
        "description": "Deterministic graph generator edge/node ordering across classic families.",
        "strict_fixture_ids": [
            "generated/generators_path_strict.json",
            "generated/generators_star_strict.json",
            "generated/generators_cycle_strict.json",
            "generated/generators_complete_strict.json",
            "generated/generators_empty_strict.json",
            "generated/generators_gnp_random_graph_strict.json",
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
    "J-STRUCTURE": "regression_path",
    "J-CENTRALITY": "regression_path",
    "J-MATCHING": "regression_path",
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
    "J-STRUCTURE": {
        "crate": "fnx-algorithms",
        "artifact_ref": "crates/fnx-algorithms/src/lib.rs",
    },
    "J-CENTRALITY": {
        "crate": "fnx-algorithms",
        "artifact_ref": "crates/fnx-algorithms/src/lib.rs",
    },
    "J-MATCHING": {
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
    "edge_betweenness_centrality_query": (
        "Edge score serialization follows deterministic canonical edge ordering."
    ),
    "articulation_points_query": "Cut-vertex ordering is deterministic by canonical node traversal order.",
    "bridges_query": "Bridge edge ordering is deterministic by canonical endpoint ordering.",
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
    "generate_gnp_random_graph": "GNP random graph generation is deterministic for identical seed/n/p parameters.",
    "bellman_ford_query": "Bellman-Ford predecessor choice follows deterministic relaxation ordering.",
    "multi_source_dijkstra_query": "Multi-source Dijkstra predecessor choice follows deterministic priority-queue ordering.",
    "maximal_matching_query": "Maximal matching is deterministic via greedy canonical edge ordering.",
    "max_weight_matching_query": "Max-weight matching is deterministic via blossom algorithm with canonical tie-breaking.",
    "min_weight_matching_query": "Min-weight matching is deterministic via blossom algorithm with canonical tie-breaking.",
    "edge_connectivity_query": "Edge connectivity is deterministic via Edmonds-Karp max-flow computation.",
    "read_adjlist": "Adjacency-list ingest follows deterministic line-order parsing.",
    "write_adjlist": "Adjacency-list serializer emits deterministic node/neighbor ordering.",
    "read_graphml": "GraphML XML ingest follows deterministic element-order parsing.",
    "write_graphml": "GraphML serializer emits deterministic node/edge ordering.",
    "clustering_coefficient_query": "Clustering coefficient scoring is deterministic by canonical neighbor-pair enumeration.",
    "distance_measures_query": "Distance measures (eccentricity, diameter, radius, center, periphery) are deterministic via canonical BFS traversal.",
    "average_shortest_path_length_query": "Average shortest path length is deterministic via all-pairs BFS distance computation.",
    "is_connected_query": "Connectivity check is deterministic via BFS reachability from canonical first node.",
    "density_query": "Graph density is deterministic from node and edge counts.",
    "has_path_query": "Path existence check is deterministic via BFS reachability.",
    "shortest_path_length_query": "Single-pair shortest path length is deterministic via BFS distance.",
    "minimum_spanning_tree_query": "Minimum spanning tree is deterministic via Kruskal with canonical edge-weight tie-breaking.",
    "triangles_query": "Triangle count per node is deterministic via canonical neighbor-set intersection.",
    "square_clustering_query": "Square clustering coefficient is deterministic via canonical neighbor-pair enumeration.",
    "is_tree_query": "Tree check is deterministic via edge count and BFS connectivity.",
    "is_forest_query": "Forest check is deterministic via edge count and component count.",
    "greedy_color_query": "Greedy coloring is deterministic via canonical sorted node processing order.",
    "is_bipartite_query": "Bipartiteness check is deterministic via BFS 2-coloring.",
    "bipartite_sets_query": "Bipartite set partition is deterministic via BFS 2-coloring from canonical node order.",
    "core_number_query": "Core number is deterministic via iterative degree-peeling algorithm.",
    "average_neighbor_degree_query": "Average neighbor degree is deterministic from neighbor degree summation.",
    "degree_assortativity_query": "Degree assortativity is deterministic via Pearson correlation on edge degree pairs.",
    "voterank_query": "VoteRank is deterministic via canonical node ordering for tie-breaking.",
    "find_cliques_query": "Clique enumeration is deterministic via Bron-Kerbosch with canonical pivot selection and lexicographic output sorting.",
    "node_connectivity_query": "Node connectivity is deterministic via node-splitting max-flow computation.",
    "minimum_node_cut_query": "Minimum node cut is deterministic via node-splitting max-flow with canonical residual BFS.",
    "global_node_connectivity_query": "Global node connectivity is deterministic via Esfahanian algorithm 11 with canonical pair selection.",
    "global_minimum_node_cut_query": "Global minimum node cut is deterministic via Esfahanian algorithm 11 with canonical pair selection.",
    "cycle_basis_query": "Cycle basis enumeration is deterministic via Paton's algorithm with canonical spanning tree traversal.",
    "all_simple_paths_query": "All simple paths enumeration is deterministic via DFS with canonical neighbor ordering.",
    "global_efficiency_query": "Global efficiency is deterministic via all-pairs BFS distance computation.",
    "local_efficiency_query": "Local efficiency is deterministic via per-node neighbor subgraph BFS computation.",
    "min_edge_cover_query": "Minimum edge cover is deterministic via max-weight matching with greedy canonical extension.",
    "is_eulerian_query": "Eulerian circuit check is deterministic via degree parity and BFS connectivity.",
    "has_eulerian_path_query": "Eulerian path check is deterministic via odd-degree count and BFS connectivity.",
    "is_semieulerian_query": "Semi-Eulerian check is deterministic via path/circuit check composition.",
    "eulerian_circuit_query": "Eulerian circuit is deterministic via Hierholzer's algorithm with sorted neighbor traversal.",
    "eulerian_path_query": "Eulerian path is deterministic via Hierholzer's algorithm with sorted neighbor traversal.",
}

EXPECTED_REFS_BY_OPERATION = {
    "add_node": ["expected.graph.nodes", "expected.graph.edges"],
    "add_edge": ["expected.graph.nodes", "expected.graph.edges"],
    "remove_node": ["expected.graph.nodes", "expected.graph.edges"],
    "remove_edge": ["expected.graph.edges"],
    "shortest_path_query": ["expected.shortest_path_unweighted"],
    "degree_centrality_query": ["expected.degree_centrality"],
    "closeness_centrality_query": ["expected.closeness_centrality"],
    "edge_betweenness_centrality_query": ["expected.edge_betweenness_centrality"],
    "articulation_points_query": ["expected.articulation_points"],
    "bridges_query": ["expected.bridges"],
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
    "generate_gnp_random_graph": ["expected.graph", "expected.number_connected_components"],
    "bellman_ford_query": [
        "expected.bellman_ford_distances",
        "expected.bellman_ford_predecessors",
        "expected.bellman_ford_negative_cycle",
    ],
    "multi_source_dijkstra_query": [
        "expected.multi_source_dijkstra_distances",
        "expected.multi_source_dijkstra_predecessors",
    ],
    "maximal_matching_query": ["expected.maximal_matching"],
    "max_weight_matching_query": ["expected.max_weight_matching"],
    "min_weight_matching_query": ["expected.min_weight_matching"],
    "edge_connectivity_query": ["expected.edge_connectivity"],
    "read_adjlist": ["expected.graph"],
    "write_adjlist": ["expected.serialized_adjlist"],
    "read_graphml": ["expected.graph"],
    "write_graphml": ["expected.serialized_graphml"],
    "clustering_coefficient_query": [
        "expected.clustering_coefficient",
        "expected.average_clustering",
        "expected.transitivity",
    ],
    "distance_measures_query": [
        "expected.eccentricity",
        "expected.diameter",
        "expected.radius",
        "expected.center",
        "expected.periphery",
    ],
    "average_shortest_path_length_query": [
        "expected.average_shortest_path_length",
    ],
    "is_connected_query": ["expected.is_connected"],
    "density_query": ["expected.density"],
    "has_path_query": ["expected.has_path"],
    "shortest_path_length_query": ["expected.shortest_path_length"],
    "minimum_spanning_tree_query": ["expected.minimum_spanning_tree"],
    "triangles_query": ["expected.triangles"],
    "square_clustering_query": ["expected.square_clustering"],
    "is_tree_query": ["expected.is_tree"],
    "is_forest_query": ["expected.is_forest"],
    "greedy_color_query": ["expected.greedy_coloring", "expected.num_colors"],
    "is_bipartite_query": ["expected.is_bipartite"],
    "bipartite_sets_query": ["expected.bipartite_sets"],
    "core_number_query": ["expected.core_numbers"],
    "average_neighbor_degree_query": ["expected.average_neighbor_degree"],
    "degree_assortativity_query": ["expected.degree_assortativity"],
    "voterank_query": ["expected.voterank"],
    "find_cliques_query": ["expected.cliques", "expected.clique_number"],
    "node_connectivity_query": ["expected.node_connectivity"],
    "minimum_node_cut_query": ["expected.minimum_node_cut"],
    "global_node_connectivity_query": ["expected.global_node_connectivity"],
    "global_minimum_node_cut_query": ["expected.global_minimum_node_cut"],
    "cycle_basis_query": ["expected.cycle_basis"],
    "all_simple_paths_query": ["expected.all_simple_paths"],
    "global_efficiency_query": ["expected.global_efficiency"],
    "local_efficiency_query": ["expected.local_efficiency"],
    "min_edge_cover_query": ["expected.min_edge_cover"],
    "is_eulerian_query": ["expected.is_eulerian"],
    "has_eulerian_path_query": ["expected.has_eulerian_path"],
    "is_semieulerian_query": ["expected.is_semieulerian"],
    "eulerian_circuit_query": ["expected.eulerian_circuit_edge_count"],
    "eulerian_path_query": ["expected.eulerian_path_edge_count"],
}

FAILURE_CLASS_BY_OPERATION = {
    "add_node": "graph_mutation",
    "add_edge": "graph_mutation",
    "remove_node": "graph_mutation",
    "remove_edge": "graph_mutation",
    "shortest_path_query": "algorithm",
    "degree_centrality_query": "algorithm_centrality",
    "closeness_centrality_query": "algorithm_centrality",
    "edge_betweenness_centrality_query": "algorithm_centrality",
    "articulation_points_query": "algorithm_structure",
    "bridges_query": "algorithm_structure",
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
    "generate_gnp_random_graph": "generators",
    "bellman_ford_query": "algorithm",
    "multi_source_dijkstra_query": "algorithm",
    "maximal_matching_query": "algorithm_matching",
    "max_weight_matching_query": "algorithm_matching",
    "min_weight_matching_query": "algorithm_matching",
    "edge_connectivity_query": "algorithm_flow",
    "read_adjlist": "readwrite",
    "write_adjlist": "readwrite",
    "read_graphml": "readwrite",
    "write_graphml": "readwrite",
    "clustering_coefficient_query": "algorithm_centrality",
    "distance_measures_query": "algorithm_distance",
    "average_shortest_path_length_query": "algorithm_distance",
    "is_connected_query": "algorithm_components",
    "density_query": "algorithm_components",
    "has_path_query": "algorithm",
    "shortest_path_length_query": "algorithm",
    "minimum_spanning_tree_query": "algorithm_mst",
    "triangles_query": "algorithm_centrality",
    "square_clustering_query": "algorithm_centrality",
    "is_tree_query": "algorithm_structure",
    "is_forest_query": "algorithm_structure",
    "greedy_color_query": "algorithm_coloring",
    "is_bipartite_query": "algorithm_structure",
    "bipartite_sets_query": "algorithm_structure",
    "core_number_query": "algorithm_structure",
    "average_neighbor_degree_query": "algorithm_centrality",
    "degree_assortativity_query": "algorithm_centrality",
    "voterank_query": "algorithm_centrality",
    "find_cliques_query": "algorithm_structure",
    "node_connectivity_query": "algorithm_connectivity",
    "minimum_node_cut_query": "algorithm_connectivity",
    "global_node_connectivity_query": "algorithm_connectivity",
    "global_minimum_node_cut_query": "algorithm_connectivity",
    "cycle_basis_query": "algorithm_structure",
    "all_simple_paths_query": "algorithm",
    "global_efficiency_query": "algorithm",
    "local_efficiency_query": "algorithm",
    "min_edge_cover_query": "algorithm",
    "is_eulerian_query": "algorithm_euler",
    "has_eulerian_path_query": "algorithm_euler",
    "is_semieulerian_query": "algorithm_euler",
    "eulerian_circuit_query": "algorithm_euler",
    "eulerian_path_query": "algorithm_euler",
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
    "edge_betweenness_centrality": {
        "expected_ref": "expected.edge_betweenness_centrality",
        "contract": "Edge betweenness centrality scores must match oracle values for canonical edge tuples.",
        "tie_break_behavior": "Edge tuple ordering is deterministic via canonical endpoint normalization.",
        "failure_class": "algorithm_centrality",
    },
    "articulation_points": {
        "expected_ref": "expected.articulation_points",
        "contract": "Articulation point output must match oracle cut-vertex set and deterministic order.",
        "tie_break_behavior": "Node ordering is deterministic via stable traversal and canonical comparison.",
        "failure_class": "algorithm_structure",
    },
    "bridges": {
        "expected_ref": "expected.bridges",
        "contract": "Bridge edge output must match oracle bridge-set membership and deterministic ordering.",
        "tie_break_behavior": "Bridge tuple ordering is deterministic via canonical endpoint normalization.",
        "failure_class": "algorithm_structure",
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
    "eccentricity": {
        "expected_ref": "expected.eccentricity",
        "contract": "Per-node eccentricity values must match oracle BFS-derived eccentricities exactly.",
        "tie_break_behavior": "Eccentricity computation is deterministic via canonical BFS traversal.",
        "failure_class": "algorithm_distance",
    },
    "diameter": {
        "expected_ref": "expected.diameter",
        "contract": "Graph diameter must match oracle max-eccentricity value exactly.",
        "tie_break_behavior": "Diameter is a scalar derived deterministically from eccentricity.",
        "failure_class": "algorithm_distance",
    },
    "radius": {
        "expected_ref": "expected.radius",
        "contract": "Graph radius must match oracle min-eccentricity value exactly.",
        "tie_break_behavior": "Radius is a scalar derived deterministically from eccentricity.",
        "failure_class": "algorithm_distance",
    },
    "center": {
        "expected_ref": "expected.center",
        "contract": "Graph center nodes must match oracle minimum-eccentricity node set.",
        "tie_break_behavior": "Center node ordering follows deterministic sorted canonical comparison.",
        "failure_class": "algorithm_distance",
    },
    "periphery": {
        "expected_ref": "expected.periphery",
        "contract": "Graph periphery nodes must match oracle maximum-eccentricity node set.",
        "tie_break_behavior": "Periphery node ordering follows deterministic sorted canonical comparison.",
        "failure_class": "algorithm_distance",
    },
    "average_shortest_path_length": {
        "expected_ref": "expected.average_shortest_path_length",
        "contract": "Average shortest path length must match oracle all-pairs BFS computation.",
        "tie_break_behavior": "Scalar value is deterministic from BFS all-pairs distance sum.",
        "failure_class": "algorithm_distance",
    },
    "is_connected": {
        "expected_ref": "expected.is_connected",
        "contract": "Connectivity boolean must match oracle BFS reachability check.",
        "tie_break_behavior": "Boolean result is deterministic from BFS reachability.",
        "failure_class": "algorithm_components",
    },
    "density": {
        "expected_ref": "expected.density",
        "contract": "Graph density must match oracle 2|E|/(|V|(|V|-1)) computation.",
        "tie_break_behavior": "Scalar value is deterministic from node and edge counts.",
        "failure_class": "algorithm_components",
    },
    "has_path": {
        "expected_ref": "expected.has_path",
        "contract": "Path existence boolean must match oracle BFS reachability.",
        "tie_break_behavior": "Boolean result is deterministic from BFS reachability.",
        "failure_class": "algorithm",
    },
    "shortest_path_length": {
        "expected_ref": "expected.shortest_path_length",
        "contract": "Single-pair shortest path length must match oracle BFS distance.",
        "tie_break_behavior": "Integer distance is deterministic from BFS traversal.",
        "failure_class": "algorithm",
    },
    "minimum_spanning_tree": {
        "expected_ref": "expected.minimum_spanning_tree",
        "contract": "MST edges and total weight must match oracle Kruskal output.",
        "tie_break_behavior": "Edge ordering is deterministic via weight then lexicographic node tie-break.",
        "failure_class": "algorithm_mst",
    },
    "triangles": {
        "expected_ref": "expected.triangles",
        "contract": "Triangle count per node must match oracle output exactly.",
        "tie_break_behavior": "Integer counts are deterministic from canonical neighbor enumeration.",
        "failure_class": "algorithm_centrality",
    },
    "square_clustering": {
        "expected_ref": "expected.square_clustering",
        "contract": "Square clustering coefficient per node must match oracle output within tolerance.",
        "tie_break_behavior": "Scores are deterministic from canonical neighbor-pair enumeration.",
        "failure_class": "algorithm_centrality",
    },
    "is_tree": {
        "expected_ref": "expected.is_tree",
        "contract": "Tree check must match oracle output exactly.",
        "tie_break_behavior": "Boolean result is deterministic from edge count and connectivity.",
        "failure_class": "algorithm_structure",
    },
    "is_forest": {
        "expected_ref": "expected.is_forest",
        "contract": "Forest check must match oracle output exactly.",
        "tie_break_behavior": "Boolean result is deterministic from edge count and component count.",
        "failure_class": "algorithm_structure",
    },
    "greedy_coloring": {
        "expected_ref": "expected.greedy_coloring",
        "contract": "Greedy coloring per node must match oracle output exactly.",
        "tie_break_behavior": "Color assignment is deterministic via canonical sorted node processing.",
        "failure_class": "algorithm_coloring",
    },
    "num_colors": {
        "expected_ref": "expected.num_colors",
        "contract": "Number of colors used must match oracle output.",
        "tie_break_behavior": "Integer count is deterministic.",
        "failure_class": "algorithm_coloring",
    },
    "is_bipartite": {
        "expected_ref": "expected.is_bipartite",
        "contract": "Bipartiteness check must match oracle output exactly.",
        "tie_break_behavior": "Boolean result is deterministic from BFS 2-coloring.",
        "failure_class": "algorithm_structure",
    },
    "bipartite_sets": {
        "expected_ref": "expected.bipartite_sets",
        "contract": "Bipartite set partition must match oracle output (up to set ordering).",
        "tie_break_behavior": "Sets are deterministic from BFS 2-coloring in canonical node order.",
        "failure_class": "algorithm_structure",
    },
    "core_numbers": {
        "expected_ref": "expected.core_numbers",
        "contract": "Core number per node must match oracle iterative peeling output.",
        "tie_break_behavior": "Core numbers are deterministic from degree-peeling bin-sort.",
        "failure_class": "algorithm_structure",
    },
    "average_neighbor_degree": {
        "expected_ref": "expected.average_neighbor_degree",
        "contract": "Average neighbor degree per node must match oracle output within tolerance.",
        "tie_break_behavior": "Scores are deterministic from neighbor degree summation.",
        "failure_class": "algorithm_centrality",
    },
    "degree_assortativity": {
        "expected_ref": "expected.degree_assortativity",
        "contract": "Degree assortativity coefficient must match oracle Pearson correlation.",
        "tie_break_behavior": "Scalar value is deterministic from edge degree pair correlation.",
        "failure_class": "algorithm_centrality",
    },
    "voterank": {
        "expected_ref": "expected.voterank",
        "contract": "VoteRank ranking must match oracle iterative voting output.",
        "tie_break_behavior": "Ranking order is deterministic via canonical node tie-breaking.",
        "failure_class": "algorithm_centrality",
    },
    "cliques": {
        "expected_ref": "expected.cliques",
        "contract": "Maximal clique enumeration must match oracle Bron-Kerbosch output exactly.",
        "tie_break_behavior": "Cliques are sorted internally and lexicographically for deterministic output.",
        "failure_class": "algorithm_structure",
    },
    "clique_number": {
        "expected_ref": "expected.clique_number",
        "contract": "Graph clique number (largest clique size) must match oracle value.",
        "tie_break_behavior": "Scalar value is deterministic from maximal clique enumeration.",
        "failure_class": "algorithm_structure",
    },
    "node_connectivity": {
        "expected_ref": "expected.node_connectivity",
        "contract": "Node connectivity must match oracle value from node-splitting max-flow.",
        "tie_break_behavior": "Scalar value is deterministic from max-flow computation.",
        "failure_class": "algorithm_connectivity",
    },
    "minimum_node_cut": {
        "expected_ref": "expected.minimum_node_cut",
        "contract": "Minimum node cut set must match oracle value (sorted).",
        "tie_break_behavior": "Cut set is sorted lexicographically for deterministic output.",
        "failure_class": "algorithm_connectivity",
    },
    "global_node_connectivity": {
        "expected_ref": "expected.global_node_connectivity",
        "contract": "Global node connectivity must match oracle value.",
        "tie_break_behavior": "Scalar value is deterministic via Esfahanian algorithm 11.",
        "failure_class": "algorithm_connectivity",
    },
    "global_minimum_node_cut": {
        "expected_ref": "expected.global_minimum_node_cut",
        "contract": "Global minimum node cut set must match oracle value (sorted).",
        "tie_break_behavior": "Cut set is sorted lexicographically for deterministic output.",
        "failure_class": "algorithm_connectivity",
    },
    "cycle_basis": {
        "expected_ref": "expected.cycle_basis",
        "contract": "Cycle basis must match oracle cycles (sorted per-cycle and across cycles).",
        "tie_break_behavior": "Cycles are sorted element-wise and then lexicographically for deterministic output.",
        "failure_class": "algorithm_structure",
    },
    "all_simple_paths": {
        "expected_ref": "expected.all_simple_paths",
        "contract": "All simple paths between source and target must match oracle set (sorted).",
        "tie_break_behavior": "Paths are sorted lexicographically for deterministic output.",
        "failure_class": "algorithm",
    },
    "global_efficiency": {
        "expected_ref": "expected.global_efficiency",
        "contract": "Global efficiency value must match oracle within floating-point tolerance.",
        "tie_break_behavior": "Scalar metric — no tie-breaking required.",
        "failure_class": "algorithm",
    },
    "local_efficiency": {
        "expected_ref": "expected.local_efficiency",
        "contract": "Local efficiency value must match oracle within floating-point tolerance.",
        "tie_break_behavior": "Scalar metric — no tie-breaking required.",
        "failure_class": "algorithm",
    },
    "min_edge_cover": {
        "expected_ref": "expected.min_edge_cover",
        "contract": "Minimum edge cover set must match oracle edges (canonical edge ordering).",
        "tie_break_behavior": "Edge pairs are canonicalized and sorted for deterministic output.",
        "failure_class": "algorithm",
    },
    "is_eulerian": {
        "expected_ref": "expected.is_eulerian",
        "contract": "Eulerian circuit existence must match oracle boolean.",
        "tie_break_behavior": "Deterministic via degree parity check and BFS connectivity.",
        "failure_class": "algorithm_euler",
    },
    "has_eulerian_path": {
        "expected_ref": "expected.has_eulerian_path",
        "contract": "Eulerian path existence must match oracle boolean.",
        "tie_break_behavior": "Deterministic via odd-degree count and BFS connectivity.",
        "failure_class": "algorithm_euler",
    },
    "is_semieulerian": {
        "expected_ref": "expected.is_semieulerian",
        "contract": "Semi-Eulerian classification must match oracle boolean.",
        "tie_break_behavior": "Deterministic via composition of path and circuit checks.",
        "failure_class": "algorithm_euler",
    },
    "eulerian_circuit": {
        "expected_ref": "expected.eulerian_circuit_edge_count",
        "contract": "Eulerian circuit must have correct edge count and form valid circuit (structural validation).",
        "tie_break_behavior": "Hierholzer's algorithm with sorted neighbor traversal ensures deterministic circuit.",
        "failure_class": "algorithm_euler",
    },
    "eulerian_path": {
        "expected_ref": "expected.eulerian_path_edge_count",
        "contract": "Eulerian path must have correct edge count and consecutive edges must share endpoints (structural validation).",
        "tie_break_behavior": "Hierholzer's algorithm with sorted neighbor traversal ensures deterministic path.",
        "failure_class": "algorithm_euler",
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
        "failure_class": "algorithm_structure",
        "description": "Structural graph outputs (articulation points/bridges) diverge from oracle expectation.",
        "source": "fnx-algorithms structure checks",
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
    {
        "failure_class": "algorithm_matching",
        "description": "Matching algorithm output diverges from oracle expectation.",
        "source": "fnx-algorithms matching checks",
    },
    {
        "failure_class": "algorithm_flow",
        "description": "Flow/connectivity algorithm output diverges from oracle expectation.",
        "source": "fnx-algorithms flow checks",
    },
    {
        "failure_class": "algorithm_distance",
        "description": "Distance measure output (eccentricity/diameter/radius/center/periphery) diverges from oracle expectation.",
        "source": "fnx-algorithms distance checks",
    },
    {
        "failure_class": "algorithm_mst",
        "description": "Minimum spanning tree output (edges/total_weight) diverges from oracle expectation.",
        "source": "fnx-algorithms MST checks",
    },
    {
        "failure_class": "algorithm_coloring",
        "description": "Graph coloring output diverges from oracle expectation.",
        "source": "fnx-algorithms coloring checks",
    },
    {
        "failure_class": "algorithm_connectivity",
        "description": "Node connectivity or minimum node cut output diverges from oracle expectation.",
        "source": "fnx-algorithms connectivity checks",
    },
    {
        "failure_class": "algorithm_euler",
        "description": "Euler path/circuit algorithm output diverges from oracle expectation.",
        "source": "fnx-algorithms euler checks",
    },
]


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        print(f"FAILED TO LOAD JSON: {path} - returning empty dict")
        return {}


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
    journey_ids = [journey["journey_id"] for journey in journeys]
    journey_coverage_hooks = build_journey_coverage_hooks(journeys)
    scenario_log_report = "artifacts/e2e/latest/e2e_user_workflow_scenario_report_v1.json"
    matrix_report_ref = "artifacts/e2e/latest/e2e_scenario_matrix_report_v1.json"

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
        "user_workflow_corpus": {
            "corpus_id": "fnx-user-workflow-scenario-corpus-v1",
            "corpus_version": "1.0.0",
            "stability_policy": (
                "scenario_id values are immutable once published; "
                "replacements require explicit new ids and mapping notes"
            ),
            "golden_journey_ids": journey_ids,
            "required_categories": REQUIRED_WORKFLOW_CATEGORIES,
            "scenario_log_report": scenario_log_report,
        },
        "journey_coverage_hooks": journey_coverage_hooks,
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
            matrix_report_ref,
            scenario_log_report,
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
