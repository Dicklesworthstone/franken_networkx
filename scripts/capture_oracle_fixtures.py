#!/usr/bin/env python3
"""Capture conformance fixtures from the legacy NetworkX oracle."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def to_attr_str_map(attrs: dict[str, Any]) -> dict[str, str]:
    return {str(k): str(v) for k, v in attrs.items()}


def canonical_edge(left: str, right: str) -> tuple[str, str]:
    return (left, right) if left <= right else (right, left)


def graph_snapshot(nx_graph: Any) -> dict[str, Any]:
    edges: list[dict[str, Any]] = []
    for left, right, attrs in nx_graph.edges(data=True):
        canonical_left, canonical_right = canonical_edge(str(left), str(right))
        edges.append(
            {
                "left": canonical_left,
                "right": canonical_right,
                "attrs": to_attr_str_map(dict(attrs)),
            }
        )
    return {
        "nodes": [str(node) for node in nx_graph.nodes()],
        "edges": edges,
    }


def node_ops(nx_graph: Any) -> list[dict[str, Any]]:
    """Generate add_node operations list from a NetworkX graph to preserve order."""
    return [{"op": "add_node", "node": str(node)} for node in nx_graph.nodes()]


def edge_ops(nx_graph: Any) -> list[dict[str, Any]]:
    """Generate add_edge operations list from a NetworkX graph."""
    ops: list[dict[str, Any]] = []
    # Use explicit node order from graph to try and keep edge discovery stable
    for u in nx_graph.nodes():
        for v in nx_graph.neighbors(u):
            if u <= v:
                attrs = nx_graph.get_edge_data(u, v)
                canonical_left, canonical_right = canonical_edge(str(u), str(v))
                entry: dict[str, Any] = {
                    "op": "add_edge",
                    "left": canonical_left,
                    "right": canonical_right,
                }
                if attrs:
                    entry["attrs"] = to_attr_str_map(dict(attrs))
                ops.append(entry)
    return ops


def connected_components_snapshot(nx_graph: Any) -> list[list[str]]:
    import networkx as nx  # type: ignore

    components: list[list[str]] = []
    for component in nx.connected_components(nx_graph):
        components.append(sorted(str(node) for node in component))
    return components


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    legacy_root = repo_root / "legacy_networkx_code" / "networkx"
    fixture_root = repo_root / "crates" / "fnx-conformance" / "fixtures" / "generated"
    artifact_root = repo_root / "artifacts" / "conformance" / "oracle_capture"

    sys.path.insert(0, str(legacy_root))
    import networkx as nx  # type: ignore
    from networkx.algorithms.link_analysis.hits_alg import _hits_python  # type: ignore
    from networkx.algorithms.link_analysis.pagerank_alg import (  # type: ignore
        _pagerank_python,
    )

    convert_graph = nx.Graph()
    convert_graph.add_edge("a", "b", weight=1)
    convert_graph.add_edge("b", "c")
    convert_path = [str(node) for node in nx.shortest_path(convert_graph, "a", "c")]

    convert_fixture = {
        "suite": "convert_v1",
        "mode": "strict",
        "operations": [
            {
                "op": "convert_edge_list",
                "payload": {
                    "nodes": ["a", "b", "c"],
                    "edges": [
                        {"left": "a", "right": "b", "attrs": {"weight": "1"}},
                        {"left": "b", "right": "c", "attrs": {}},
                    ],
                },
            },
            {"op": "shortest_path_query", "source": "a", "target": "c"},
        ],
        "expected": {
            "graph": graph_snapshot(convert_graph),
            "shortest_path_unweighted": convert_path,
        },
    }

    readwrite_graph = nx.parse_edgelist(["a b", "b c"], nodetype=str, data=False)
    readwrite_path = [str(node) for node in nx.shortest_path(readwrite_graph, "a", "c")]
    readwrite_fixture = {
        "suite": "readwrite_v1",
        "mode": "strict",
        "operations": [
            {"op": "read_edgelist", "input": "a b\nb c"},
            {"op": "write_edgelist"},
            {"op": "shortest_path_query", "source": "a", "target": "c"},
        ],
        "expected": {
            "graph": graph_snapshot(readwrite_graph),
            "shortest_path_unweighted": readwrite_path,
            "serialized_edgelist": "a b -\nb c -",
        },
    }

    dispatch_fixture = {
        "suite": "dispatch_v1",
        "mode": "strict",
        "operations": [
            {
                "op": "dispatch_resolve",
                "operation": "shortest_path",
                "required_features": ["shortest_path"],
                "risk_probability": 0.3,
                "unknown_incompatible_feature": False,
            }
        ],
        "expected": {
            "dispatch": {
                "selected_backend": "native",
                "action": "full_validate",
            }
        },
    }

    view_graph = nx.Graph()
    view_graph.add_edge("a", "b")
    view_graph.add_edge("a", "c")
    view_fixture = {
        "suite": "views_v1",
        "mode": "strict",
        "operations": [
            {"op": "add_edge", "left": "a", "right": "b"},
            {"op": "add_edge", "left": "a", "right": "c"},
            {"op": "view_neighbors_query", "node": "a"},
        ],
        "expected": {
            "graph": graph_snapshot(view_graph),
            "view_neighbors": ["b", "c"],
        },
    }

    json_graph = nx.Graph()
    json_graph.add_edge("a", "b")
    json_graph.add_edge("a", "c")
    json_payload = {
        "mode": "strict",
        "nodes": [str(node) for node in json_graph.nodes()],
        "edges": graph_snapshot(json_graph)["edges"],
    }
    readwrite_json_fixture = {
        "suite": "readwrite_v1",
        "mode": "strict",
        "operations": [
            {"op": "read_json_graph", "input": json.dumps(json_payload, separators=(",", ":"))},
            {"op": "write_json_graph"},
            {"op": "view_neighbors_query", "node": "a"},
        ],
        "expected": {
            "graph": graph_snapshot(json_graph),
            "view_neighbors": ["b", "c"],
        },
    }

    components_graph = nx.Graph()
    components_graph.add_edge("a", "b")
    components_graph.add_edge("c", "d")
    components_graph.add_node("solo")
    components_fixture = {
        "suite": "components_v1",
        "mode": "strict",
        "operations": [
            {"op": "add_edge", "left": "a", "right": "b"},
            {"op": "add_edge", "left": "c", "right": "d"},
            {"op": "add_node", "node": "solo"},
            {"op": "connected_components_query"},
            {"op": "number_connected_components_query"},
        ],
        "expected": {
            "graph": graph_snapshot(components_graph),
            "connected_components": connected_components_snapshot(components_graph),
            "number_connected_components": nx.number_connected_components(components_graph),
        },
    }

    path_graph = nx.path_graph(5)
    generate_path_fixture = {
        "suite": "generators_v1",
        "mode": "strict",
        "operations": [
            {"op": "generate_path_graph", "n": 5},
            {"op": "number_connected_components_query"},
        ],
        "expected": {
            "graph": graph_snapshot(path_graph),
            "number_connected_components": 1,
        },
    }

    centrality_graph = nx.Graph()
    centrality_graph.add_edge("a", "b")
    centrality_graph.add_edge("a", "c")
    centrality_graph.add_edge("b", "d")
    centrality_scores = nx.degree_centrality(centrality_graph)
    centrality_fixture = {
        "suite": "centrality_v1",
        "mode": "strict",
        "operations": [
            {"op": "add_edge", "left": "a", "right": "b"},
            {"op": "add_edge", "left": "a", "right": "c"},
            {"op": "add_edge", "left": "b", "right": "d"},
            {"op": "degree_centrality_query"},
        ],
        "expected": {
            "graph": graph_snapshot(centrality_graph),
            "degree_centrality": [
                {"node": str(node), "score": float(score)}
                for node, score in centrality_scores.items()
            ],
        },
    }

    betweenness_scores = nx.betweenness_centrality(centrality_graph)
    betweenness_fixture = {
        "suite": "centrality_v1",
        "mode": "strict",
        "operations": [
            {"op": "add_edge", "left": "a", "right": "b"},
            {"op": "add_edge", "left": "a", "right": "c"},
            {"op": "add_edge", "left": "b", "right": "d"},
            {"op": "betweenness_centrality_query"},
        ],
        "expected": {
            "graph": graph_snapshot(centrality_graph),
            "betweenness_centrality": [
                {"node": str(node), "score": float(score)}
                for node, score in betweenness_scores.items()
            ],
        },
    }

    edge_betweenness_items = []
    for edge, score in nx.edge_betweenness_centrality(centrality_graph).items():
        left, right = sorted((str(edge[0]), str(edge[1])))
        edge_betweenness_items.append(
            {"left": left, "right": right, "score": float(score)}
        )
    edge_betweenness_items.sort(key=lambda item: (item["left"], item["right"]))
    edge_betweenness_fixture = {
        "suite": "centrality_v1",
        "mode": "strict",
        "operations": [
            {"op": "add_edge", "left": "a", "right": "b"},
            {"op": "add_edge", "left": "a", "right": "c"},
            {"op": "add_edge", "left": "b", "right": "d"},
            {"op": "edge_betweenness_centrality_query"},
        ],
        "expected": {
            "graph": graph_snapshot(centrality_graph),
            "edge_betweenness_centrality": edge_betweenness_items,
        },
    }

    closeness_graph = nx.Graph()
    closeness_graph.add_edge("a", "b")
    closeness_graph.add_node("c")
    closeness_scores = nx.closeness_centrality(closeness_graph)
    closeness_fixture = {
        "suite": "centrality_v1",
        "mode": "strict",
        "operations": [
            {"op": "add_edge", "left": "a", "right": "b"},
            {"op": "add_node", "node": "c"},
            {"op": "closeness_centrality_query"},
        ],
        "expected": {
            "graph": graph_snapshot(closeness_graph),
            "closeness_centrality": [
                {"node": str(node), "score": float(score)}
                for node, score in closeness_scores.items()
            ],
        },
    }

    harmonic_scores = nx.harmonic_centrality(centrality_graph)
    harmonic_fixture = {
        "suite": "centrality_v1",
        "mode": "strict",
        "operations": [
            {"op": "add_edge", "left": "a", "right": "b"},
            {"op": "add_edge", "left": "a", "right": "c"},
            {"op": "add_edge", "left": "b", "right": "d"},
            {"op": "harmonic_centrality_query"},
        ],
        "expected": {
            "graph": graph_snapshot(centrality_graph),
            "harmonic_centrality": [
                {"node": str(node), "score": float(harmonic_scores[node])}
                for node in centrality_graph.nodes()
            ],
        },
    }

    katz_scores = nx.katz_centrality(centrality_graph)
    katz_fixture = {
        "suite": "centrality_v1",
        "mode": "strict",
        "operations": [
            {"op": "add_edge", "left": "a", "right": "b"},
            {"op": "add_edge", "left": "a", "right": "c"},
            {"op": "add_edge", "left": "b", "right": "d"},
            {"op": "katz_centrality_query"},
        ],
        "expected": {
            "graph": graph_snapshot(centrality_graph),
            "katz_centrality": [
                {"node": str(node), "score": float(katz_scores[node])}
                for node in centrality_graph.nodes()
            ],
        },
    }

    hits_hubs, hits_authorities = _hits_python(centrality_graph)
    hits_fixture = {
        "suite": "centrality_v1",
        "mode": "strict",
        "operations": [
            {"op": "add_edge", "left": "a", "right": "b"},
            {"op": "add_edge", "left": "a", "right": "c"},
            {"op": "add_edge", "left": "b", "right": "d"},
            {"op": "hits_centrality_query"},
        ],
        "expected": {
            "graph": graph_snapshot(centrality_graph),
            "hits_hubs": [
                {"node": str(node), "score": float(hits_hubs[node])}
                for node in centrality_graph.nodes()
            ],
            "hits_authorities": [
                {"node": str(node), "score": float(hits_authorities[node])}
                for node in centrality_graph.nodes()
            ],
        },
    }

    pagerank_graph = nx.Graph()
    pagerank_graph.add_edge("a", "b")
    pagerank_scores = _pagerank_python(pagerank_graph)
    pagerank_fixture = {
        "suite": "centrality_v1",
        "mode": "strict",
        "operations": [
            {"op": "add_edge", "left": "a", "right": "b"},
            {"op": "pagerank_query"},
        ],
        "expected": {
            "graph": graph_snapshot(pagerank_graph),
            "pagerank": [
                {"node": str(node), "score": float(score)}
                for node, score in pagerank_scores.items()
            ],
        },
    }

    eigenvector_scores = nx.eigenvector_centrality(centrality_graph)
    eigenvector_fixture = {
        "suite": "centrality_v1",
        "mode": "strict",
        "operations": [
            {"op": "add_edge", "left": "a", "right": "b"},
            {"op": "add_edge", "left": "a", "right": "c"},
            {"op": "add_edge", "left": "b", "right": "d"},
            {"op": "eigenvector_centrality_query"},
        ],
        "expected": {
            "graph": graph_snapshot(centrality_graph),
            "eigenvector_centrality": [
                {"node": str(node), "score": float(eigenvector_scores[node])}
                for node in centrality_graph.nodes()
            ],
        },
    }

    cycle_graph = nx.cycle_graph(5)
    generate_cycle_fixture = {
        "suite": "generators_v1",
        "mode": "strict",
        "operations": [
            {"op": "generate_cycle_graph", "n": 5},
            {"op": "connected_components_query"},
        ],
        "expected": {
            "graph": graph_snapshot(cycle_graph),
            "connected_components": connected_components_snapshot(cycle_graph),
        },
    }

    complete_graph = nx.complete_graph(4)
    generate_complete_fixture = {
        "suite": "generators_v1",
        "mode": "strict",
        "operations": [
            {"op": "generate_complete_graph", "n": 4},
            {"op": "number_connected_components_query"},
        ],
        "expected": {
            "graph": graph_snapshot(complete_graph),
            "number_connected_components": 1,
        },
    }

    matching_graph = nx.Graph()
    matching_graph.add_edge("a", "b", weight=5)
    matching_graph.add_edge("a", "c", weight=1)
    matching_graph.add_edge("b", "c", weight=3)
    matching_graph.add_edge("b", "d", weight=2)
    matching_graph.add_edge("c", "d", weight=4)
    matching_graph.add_edge("d", "e", weight=6)

    maximal = nx.maximal_matching(matching_graph)
    maximal_sorted = sorted(
        tuple(sorted((str(u), str(v)))) for u, v in maximal
    )
    maximal_matching_fixture = {
        "suite": "matching_v1",
        "mode": "strict",
        "operations": [
            {"op": "add_edge", "left": "a", "right": "b", "attrs": {"weight": "5"}},
            {"op": "add_edge", "left": "a", "right": "c", "attrs": {"weight": "1"}},
            {"op": "add_edge", "left": "b", "right": "c", "attrs": {"weight": "3"}},
            {"op": "add_edge", "left": "b", "right": "d", "attrs": {"weight": "2"}},
            {"op": "add_edge", "left": "c", "right": "d", "attrs": {"weight": "4"}},
            {"op": "add_edge", "left": "d", "right": "e", "attrs": {"weight": "6"}},
            {"op": "maximal_matching_query"},
        ],
        "expected": {
            "graph": graph_snapshot(matching_graph),
            "maximal_matching": [list(pair) for pair in maximal_sorted],
        },
    }

    max_wt = nx.max_weight_matching(matching_graph, maxcardinality=False, weight="weight")
    max_wt_sorted = sorted(
        tuple(sorted((str(u), str(v)))) for u, v in max_wt
    )
    max_wt_total = sum(
        matching_graph[u][v]["weight"] for u, v in max_wt
    )
    max_weight_matching_fixture = {
        "suite": "matching_v1",
        "mode": "strict",
        "operations": [
            {"op": "add_edge", "left": "a", "right": "b", "attrs": {"weight": "5"}},
            {"op": "add_edge", "left": "a", "right": "c", "attrs": {"weight": "1"}},
            {"op": "add_edge", "left": "b", "right": "c", "attrs": {"weight": "3"}},
            {"op": "add_edge", "left": "b", "right": "d", "attrs": {"weight": "2"}},
            {"op": "add_edge", "left": "c", "right": "d", "attrs": {"weight": "4"}},
            {"op": "add_edge", "left": "d", "right": "e", "attrs": {"weight": "6"}},
            {"op": "max_weight_matching_query", "weight_attr": "weight"},
        ],
        "expected": {
            "graph": graph_snapshot(matching_graph),
            "max_weight_matching": {
                "matching": [list(pair) for pair in max_wt_sorted],
                "total_weight": float(max_wt_total),
            },
        },
    }

    min_wt = nx.min_weight_matching(matching_graph, weight="weight")
    min_wt_sorted = sorted(
        tuple(sorted((str(u), str(v)))) for u, v in min_wt
    )
    min_wt_total = sum(
        matching_graph[u][v]["weight"] for u, v in min_wt
    )
    min_weight_matching_fixture = {
        "suite": "matching_v1",
        "mode": "strict",
        "operations": [
            {"op": "add_edge", "left": "a", "right": "b", "attrs": {"weight": "5"}},
            {"op": "add_edge", "left": "a", "right": "c", "attrs": {"weight": "1"}},
            {"op": "add_edge", "left": "b", "right": "c", "attrs": {"weight": "3"}},
            {"op": "add_edge", "left": "b", "right": "d", "attrs": {"weight": "2"}},
            {"op": "add_edge", "left": "c", "right": "d", "attrs": {"weight": "4"}},
            {"op": "add_edge", "left": "d", "right": "e", "attrs": {"weight": "6"}},
            {"op": "min_weight_matching_query", "weight_attr": "weight"},
        ],
        "expected": {
            "graph": graph_snapshot(matching_graph),
            "min_weight_matching": {
                "matching": [list(pair) for pair in min_wt_sorted],
                "total_weight": float(min_wt_total),
            },
        },
    }

    clustering_graph = nx.Graph()
    clustering_graph.add_edge("a", "b")
    clustering_graph.add_edge("a", "c")
    clustering_graph.add_edge("b", "c")
    clustering_graph.add_edge("b", "d")
    clustering_graph.add_edge("c", "d")
    clustering_scores = nx.clustering(clustering_graph)
    avg_clustering = nx.average_clustering(clustering_graph)
    transitivity = nx.transitivity(clustering_graph)
    clustering_fixture = {
        "suite": "clustering_v1",
        "mode": "strict",
        "operations": [
            {"op": "add_edge", "left": "a", "right": "b"},
            {"op": "add_edge", "left": "a", "right": "c"},
            {"op": "add_edge", "left": "b", "right": "c"},
            {"op": "add_edge", "left": "b", "right": "d"},
            {"op": "add_edge", "left": "c", "right": "d"},
            {"op": "clustering_coefficient_query"},
        ],
        "expected": {
            "graph": graph_snapshot(clustering_graph),
            "clustering_coefficient": [
                {"node": str(node), "score": float(score)}
                for node, score in clustering_scores.items()
            ],
            "average_clustering": float(avg_clustering),
            "transitivity": float(transitivity),
        },
    }

    write_json(fixture_root / "convert_edge_list_strict.json", convert_fixture)
    write_json(fixture_root / "readwrite_roundtrip_strict.json", readwrite_fixture)
    write_json(fixture_root / "dispatch_route_strict.json", dispatch_fixture)
    write_json(fixture_root / "view_neighbors_strict.json", view_fixture)
    write_json(fixture_root / "readwrite_json_roundtrip_strict.json", readwrite_json_fixture)
    write_json(fixture_root / "components_connected_strict.json", components_fixture)
    write_json(fixture_root / "generators_path_strict.json", generate_path_fixture)
    write_json(fixture_root / "generators_cycle_strict.json", generate_cycle_fixture)
    write_json(fixture_root / "generators_complete_strict.json", generate_complete_fixture)
    write_json(fixture_root / "centrality_degree_strict.json", centrality_fixture)
    write_json(fixture_root / "centrality_betweenness_strict.json", betweenness_fixture)
    write_json(
        fixture_root / "centrality_edge_betweenness_strict.json",
        edge_betweenness_fixture,
    )
    write_json(fixture_root / "centrality_closeness_strict.json", closeness_fixture)
    write_json(fixture_root / "centrality_harmonic_strict.json", harmonic_fixture)
    write_json(fixture_root / "centrality_katz_strict.json", katz_fixture)
    write_json(fixture_root / "centrality_hits_strict.json", hits_fixture)
    write_json(fixture_root / "centrality_pagerank_strict.json", pagerank_fixture)
    write_json(
        fixture_root / "centrality_eigenvector_strict.json", eigenvector_fixture
    )
    write_json(
        fixture_root / "matching_maximal_strict.json", maximal_matching_fixture
    )
    write_json(
        fixture_root / "matching_max_weight_strict.json", max_weight_matching_fixture
    )
    write_json(
        fixture_root / "matching_min_weight_strict.json", min_weight_matching_fixture
    )
    write_json(
        fixture_root / "clustering_coefficient_strict.json", clustering_fixture
    )

    # --- Distance measures fixture ---
    distance_graph = nx.Graph()
    distance_graph.add_edge("a", "b")
    distance_graph.add_edge("b", "c")
    distance_graph.add_edge("c", "d")
    distance_graph.add_edge("d", "e")
    distance_graph.add_edge("b", "d")
    ecc = nx.eccentricity(distance_graph)
    distance_fixture = {
        "suite": "distance_v1",
        "mode": "strict",
        "operations": [
            {"op": "add_edge", "left": "a", "right": "b"},
            {"op": "add_edge", "left": "b", "right": "c"},
            {"op": "add_edge", "left": "c", "right": "d"},
            {"op": "add_edge", "left": "d", "right": "e"},
            {"op": "add_edge", "left": "b", "right": "d"},
            {"op": "distance_measures_query"},
        ],
        "expected": {
            "graph": graph_snapshot(distance_graph),
            "eccentricity": [
                {"node": str(node), "value": ecc[node]}
                for node in distance_graph.nodes()
            ],
            "diameter": nx.diameter(distance_graph),
            "radius": nx.radius(distance_graph),
            "center": sorted(str(n) for n in nx.center(distance_graph)),
            "periphery": sorted(str(n) for n in nx.periphery(distance_graph)),
        },
    }
    write_json(
        fixture_root / "distance_measures_strict.json", distance_fixture
    )

    # --- Average shortest path length fixture ---
    aspl_graph = nx.Graph()
    aspl_graph.add_edge("a", "b")
    aspl_graph.add_edge("b", "c")
    aspl_graph.add_edge("c", "d")
    aspl_graph.add_edge("d", "e")
    aspl_graph.add_edge("b", "d")
    aspl_value = nx.average_shortest_path_length(aspl_graph)
    aspl_fixture = {
        "suite": "average_shortest_path_length_v1",
        "mode": "strict",
        "operations": [
            {"op": "add_edge", "left": "a", "right": "b"},
            {"op": "add_edge", "left": "b", "right": "c"},
            {"op": "add_edge", "left": "c", "right": "d"},
            {"op": "add_edge", "left": "d", "right": "e"},
            {"op": "add_edge", "left": "b", "right": "d"},
            {"op": "average_shortest_path_length_query"},
        ],
        "expected": {
            "graph": graph_snapshot(aspl_graph),
            "average_shortest_path_length": float(aspl_value),
        },
    }
    write_json(
        fixture_root / "average_shortest_path_length_strict.json", aspl_fixture
    )

    # --- is_connected + density fixture ---
    conn_graph = nx.Graph()
    conn_graph.add_edge("a", "b")
    conn_graph.add_edge("b", "c")
    conn_graph.add_edge("c", "d")
    conn_graph.add_edge("d", "e")
    conn_graph.add_edge("b", "d")
    conn_fixture = {
        "suite": "is_connected_density_v1",
        "mode": "strict",
        "operations": [
            {"op": "add_edge", "left": "a", "right": "b"},
            {"op": "add_edge", "left": "b", "right": "c"},
            {"op": "add_edge", "left": "c", "right": "d"},
            {"op": "add_edge", "left": "d", "right": "e"},
            {"op": "add_edge", "left": "b", "right": "d"},
            {"op": "is_connected_query"},
            {"op": "density_query"},
        ],
        "expected": {
            "graph": graph_snapshot(conn_graph),
            "is_connected": bool(nx.is_connected(conn_graph)),
            "density": float(nx.density(conn_graph)),
        },
    }
    write_json(
        fixture_root / "is_connected_density_strict.json", conn_fixture
    )

    # --- has_path + shortest_path_length fixture ---
    hp_graph = nx.Graph()
    hp_graph.add_edge("a", "b")
    hp_graph.add_edge("b", "c")
    hp_graph.add_edge("c", "d")
    hp_graph.add_edge("d", "e")
    hp_graph.add_edge("b", "d")
    hp_graph.add_node("f")
    hp_fixture = {
        "suite": "has_path_v1",
        "mode": "strict",
        "operations": [
            {"op": "add_edge", "left": "a", "right": "b"},
            {"op": "add_edge", "left": "b", "right": "c"},
            {"op": "add_edge", "left": "c", "right": "d"},
            {"op": "add_edge", "left": "d", "right": "e"},
            {"op": "add_edge", "left": "b", "right": "d"},
            {"op": "add_node", "node": "f"},
            {"op": "has_path_query", "source": "a", "target": "e"},
            {"op": "shortest_path_length_query", "source": "a", "target": "e"},
        ],
        "expected": {
            "graph": graph_snapshot(hp_graph),
            "has_path": bool(nx.has_path(hp_graph, "a", "e")),
            "shortest_path_length": int(nx.shortest_path_length(hp_graph, "a", "e")),
        },
    }
    write_json(fixture_root / "has_path_strict.json", hp_fixture)

    # --- minimum spanning tree fixture ---
    mst_graph = nx.Graph()
    mst_graph.add_edge("a", "b", weight=5)
    mst_graph.add_edge("a", "c", weight=1)
    mst_graph.add_edge("b", "c", weight=3)
    mst_graph.add_edge("b", "d", weight=2)
    mst_graph.add_edge("c", "d", weight=4)
    mst_graph.add_edge("d", "e", weight=6)
    T = nx.minimum_spanning_tree(mst_graph, algorithm="kruskal")
    mst_edges = sorted(
        [
            {"left": min(u, v), "right": max(u, v), "weight": float(d["weight"])}
            for u, v, d in T.edges(data=True)
        ],
        key=lambda e: (e["weight"], e["left"], e["right"]),
    )
    mst_weight = sum(d["weight"] for u, v, d in T.edges(data=True))
    mst_fixture = {
        "suite": "mst_v1",
        "mode": "strict",
        "operations": [
            {"op": "add_edge", "left": "a", "right": "b", "attrs": {"weight": "5"}},
            {"op": "add_edge", "left": "a", "right": "c", "attrs": {"weight": "1"}},
            {"op": "add_edge", "left": "b", "right": "c", "attrs": {"weight": "3"}},
            {"op": "add_edge", "left": "b", "right": "d", "attrs": {"weight": "2"}},
            {"op": "add_edge", "left": "c", "right": "d", "attrs": {"weight": "4"}},
            {"op": "add_edge", "left": "d", "right": "e", "attrs": {"weight": "6"}},
            {"op": "minimum_spanning_tree_query", "weight_attr": "weight"},
        ],
        "expected": {
            "graph": graph_snapshot(mst_graph),
            "minimum_spanning_tree": {
                "edges": mst_edges,
                "total_weight": float(mst_weight),
            },
        },
    }
    write_json(fixture_root / "minimum_spanning_tree_strict.json", mst_fixture)

    # --- triangles + square_clustering fixture ---
    tri_graph = nx.Graph()
    tri_graph.add_edge("a", "b")
    tri_graph.add_edge("a", "c")
    tri_graph.add_edge("b", "c")
    tri_graph.add_edge("b", "d")
    tri_graph.add_edge("c", "d")
    tri_graph.add_edge("d", "e")
    tri_counts = nx.triangles(tri_graph)
    sq_clust = nx.square_clustering(tri_graph)
    tri_fixture = {
        "suite": "triangles_v1",
        "mode": "strict",
        "operations": [
            {"op": "add_edge", "left": "a", "right": "b"},
            {"op": "add_edge", "left": "a", "right": "c"},
            {"op": "add_edge", "left": "b", "right": "c"},
            {"op": "add_edge", "left": "b", "right": "d"},
            {"op": "add_edge", "left": "c", "right": "d"},
            {"op": "add_edge", "left": "d", "right": "e"},
            {"op": "triangles_query"},
            {"op": "square_clustering_query"},
        ],
        "expected": {
            "graph": graph_snapshot(tri_graph),
            "triangles": [
                {"node": n, "count": tri_counts[n]}
                for n in sorted(tri_counts)
            ],
            "square_clustering": [
                {"node": n, "score": float(sq_clust[n])}
                for n in sorted(sq_clust)
            ],
        },
    }
    write_json(
        fixture_root / "triangles_square_clustering_strict.json", tri_fixture
    )

    # --- is_tree / is_forest fixture ---
    tree_graph = nx.Graph()
    tree_graph.add_edge("a", "b")
    tree_graph.add_edge("a", "c")
    tree_graph.add_edge("b", "d")
    tree_graph.add_edge("b", "e")
    tree_fixture = {
        "suite": "tree_v1",
        "mode": "strict",
        "operations": node_ops(tree_graph) + edge_ops(tree_graph) + [
            {"op": "is_tree_query"},
            {"op": "is_forest_query"},
        ],
        "expected": {
            "graph": graph_snapshot(tree_graph),
            "is_tree": bool(nx.is_tree(tree_graph)),
            "is_forest": bool(nx.is_forest(tree_graph)),
        },
    }
    write_json(fixture_root / "tree_forest_strict.json", tree_fixture)

    # --- greedy coloring fixture ---
    color_graph = nx.Graph()
    color_graph.add_edge("a", "b")
    color_graph.add_edge("a", "c")
    color_graph.add_edge("b", "c")
    color_graph.add_edge("b", "d")
    color_graph.add_edge("c", "d")
    color_graph.add_edge("d", "e")
    # Greedy coloring using NetworkX default (largest_first)
    coloring = nx.greedy_color(color_graph, strategy="largest_first")
    num_colors = max(coloring.values()) + 1 if coloring else 0
    # Use sorted nodes for consistent JSON output of the coloring
    sorted_nodes = sorted(color_graph.nodes())
    color_fixture = {
        "suite": "coloring_v1",
        "mode": "strict",
        "operations": node_ops(color_graph) + edge_ops(color_graph) + [
            {"op": "greedy_color_query"},
        ],
        "expected": {
            "graph": graph_snapshot(color_graph),
            "greedy_coloring": [
                {"node": str(n), "color": coloring[n]} for n in sorted_nodes
            ],
            "num_colors": num_colors,
        },
    }
    write_json(fixture_root / "greedy_color_strict.json", color_fixture)

    # --- bipartite fixture ---
    bip_graph = nx.Graph()
    bip_graph.add_edge("a", "b")
    bip_graph.add_edge("a", "d")
    bip_graph.add_edge("c", "b")
    bip_graph.add_edge("c", "d")
    bip_graph.add_edge("e", "b")
    from networkx.algorithms.bipartite import is_bipartite as nx_is_bipartite
    from networkx.algorithms.bipartite import sets as nx_bipartite_sets
    bip_top, bip_bottom = nx_bipartite_sets(bip_graph)
    bip_fixture = {
        "suite": "bipartite_v1",
        "mode": "strict",
        "operations": node_ops(bip_graph) + edge_ops(bip_graph) + [
            {"op": "is_bipartite_query"},
            {"op": "bipartite_sets_query"},
        ],

        "expected": {
            "graph": graph_snapshot(bip_graph),
            "is_bipartite": bool(nx_is_bipartite(bip_graph)),
            "bipartite_sets": {
                "set_a": sorted(bip_top),
                "set_b": sorted(bip_bottom),
            },
        },
    }
    write_json(fixture_root / "bipartite_strict.json", bip_fixture)

    # --- Core number oracle ---
    core_graph = matching_graph  # reuse: a-b(5), a-c(1), b-c(3), b-d(2), c-d(4), d-e(6)
    cn = nx.core_number(core_graph)
    cn_fixture = {
        "suite": "core_number_v1",
        "mode": "strict",
        "operations": node_ops(core_graph) + edge_ops(core_graph) + [
            {"op": "core_number_query"},
        ],
        "expected": {
            "graph": graph_snapshot(core_graph),
            "core_numbers": [
                {"node": n, "core": cn[n]} for n in sorted(cn)
            ],
        },
    }
    write_json(fixture_root / "core_number_strict.json", cn_fixture)

    # --- Average neighbor degree + assortativity + voterank oracle ---
    and_graph = matching_graph
    avg_nd = nx.average_neighbor_degree(and_graph)
    assort_r = nx.degree_assortativity_coefficient(and_graph)
    vr = nx.voterank(and_graph)
    and_fixture = {
        "suite": "avg_neighbor_degree_v1",
        "mode": "strict",
        "operations": node_ops(and_graph) + edge_ops(and_graph) + [
            {"op": "average_neighbor_degree_query"},
            {"op": "degree_assortativity_query"},
            {"op": "voterank_query"},
        ],
        "expected": {
            "graph": graph_snapshot(and_graph),
            "average_neighbor_degree": [
                {"node": n, "avg_neighbor_degree": round(avg_nd[n], 10)}
                for n in sorted(avg_nd)
            ],
            "degree_assortativity": assort_r,
            "voterank": vr,
        },
    }
    write_json(fixture_root / "avg_neighbor_degree_strict.json", and_fixture)

    # --- Node connectivity oracle ---
    nc_graph = nx.Graph()
    nc_graph.add_edge("a", "b", weight=5)
    nc_graph.add_edge("a", "c", weight=1)
    nc_graph.add_edge("b", "c", weight=3)
    nc_graph.add_edge("b", "d", weight=2)
    nc_graph.add_edge("c", "d", weight=4)
    nc_graph.add_edge("d", "e", weight=6)
    nc_ae = nx.node_connectivity(nc_graph, "a", "e")
    mnc_ae = sorted(nx.minimum_node_cut(nc_graph, "a", "e"))
    gnc = nx.node_connectivity(nc_graph)
    gmnc = sorted(nx.minimum_node_cut(nc_graph))
    nc_fixture = {
        "suite": "node_connectivity_v1",
        "mode": "strict",
        "operations": node_ops(nc_graph) + edge_ops(nc_graph) + [
            {"op": "node_connectivity_query", "source": "a", "target": "e"},
            {"op": "minimum_node_cut_query", "source": "a", "target": "e"},
            {"op": "global_node_connectivity_query"},
            {"op": "global_minimum_node_cut_query"},
        ],
        "expected": {
            "graph": graph_snapshot(nc_graph),
            "node_connectivity": nc_ae,
            "minimum_node_cut": mnc_ae,
            "global_node_connectivity": gnc,
            "global_minimum_node_cut": gmnc,
        },
    }
    write_json(fixture_root / "node_connectivity_strict.json", nc_fixture)

    # --- Clique enumeration oracle ---
    clique_graph = nx.Graph()
    clique_graph.add_edge("a", "b", weight=5)
    clique_graph.add_edge("a", "c", weight=1)
    clique_graph.add_edge("b", "c", weight=3)
    clique_graph.add_edge("b", "d", weight=2)
    clique_graph.add_edge("c", "d", weight=4)
    clique_graph.add_edge("d", "e", weight=6)
    cliques = sorted([sorted(c) for c in nx.find_cliques(clique_graph)])
    clique_number = max(len(c) for c in cliques)
    clique_fixture = {
        "suite": "cliques_v1",
        "mode": "strict",
        "operations": node_ops(clique_graph) + edge_ops(clique_graph) + [{"op": "find_cliques_query"}],
        "expected": {
            "graph": graph_snapshot(clique_graph),
            "cliques": cliques,
            "clique_number": clique_number,
        },
    }
    write_json(fixture_root / "cliques_strict.json", clique_fixture)

    # --- Cycle basis oracle ---
    cb_graph = matching_graph  # reuse: a-b(5), a-c(1), b-c(3), b-d(2), c-d(4), d-e(6)
    cycles = [sorted(c) for c in nx.cycle_basis(cb_graph)]
    cycles.sort()
    cb_fixture = {
        "suite": "cycle_basis_v1",
        "mode": "strict",
        "operations": node_ops(cb_graph) + edge_ops(cb_graph) + [{"op": "cycle_basis_query"}],
        "expected": {
            "graph": graph_snapshot(cb_graph),
            "cycle_basis": cycles,
        },
    }
    write_json(fixture_root / "cycle_basis_strict.json", cb_fixture)

    # --- Paths, efficiency, edge cover oracle ---
    pec_graph = matching_graph  # reuse same graph
    all_paths = sorted(
        [list(p) for p in nx.all_simple_paths(pec_graph, "a", "e")]
    )
    ge = nx.global_efficiency(pec_graph)
    le = nx.local_efficiency(pec_graph)
    cover = nx.min_edge_cover(pec_graph)
    cover_sorted = sorted(
        [{"left": min(str(u), str(v)), "right": max(str(u), str(v))} for u, v in cover]
    , key=lambda e: (e["left"], e["right"]))
    pec_fixture = {
        "suite": "paths_efficiency_cover_v1",
        "mode": "strict",
        "operations": node_ops(pec_graph) + edge_ops(pec_graph) + [
            {"op": "all_simple_paths_query", "source": "a", "target": "e"},
            {"op": "global_efficiency_query"},
            {"op": "local_efficiency_query"},
            {"op": "min_edge_cover_query"},
        ],
        "expected": {
            "graph": graph_snapshot(pec_graph),
            "all_simple_paths": all_paths,
            "global_efficiency": round(ge, 10),
            "local_efficiency": round(le, 10),
            "min_edge_cover": cover_sorted,
        },
    }
    write_json(fixture_root / "paths_efficiency_cover_strict.json", pec_fixture)

    # --- Euler oracle ---
    # Eulerian circuit graph: all even degrees, connected
    # Butterfly/bowtie: a-b, a-c, b-c, c-d, c-e, d-e (all even degrees)
    euler_circuit_graph = nx.Graph()
    euler_circuit_graph.add_edge("a", "b")
    euler_circuit_graph.add_edge("a", "c")
    euler_circuit_graph.add_edge("b", "c")
    euler_circuit_graph.add_edge("c", "d")
    euler_circuit_graph.add_edge("c", "e")
    euler_circuit_graph.add_edge("d", "e")

    # Eulerian path graph: exactly 2 odd-degree nodes
    # House graph: a-b, b-c, c-d, d-a, c-e, d-e
    # Degrees: a=2, b=2, c=3, d=3, e=2 → 2 odd nodes (c,d)
    euler_path_graph = nx.Graph()
    euler_path_graph.add_edge("a", "b")
    euler_path_graph.add_edge("b", "c")
    euler_path_graph.add_edge("c", "d")
    euler_path_graph.add_edge("d", "a")
    euler_path_graph.add_edge("c", "e")
    euler_path_graph.add_edge("d", "e")

    is_eul = nx.is_eulerian(euler_circuit_graph)
    has_eul_path_circuit = nx.has_eulerian_path(euler_circuit_graph)
    is_semi_circuit = nx.is_semieulerian(euler_circuit_graph)

    # Get Eulerian circuit edges
    circuit_edges = list(nx.eulerian_circuit(euler_circuit_graph, source="a"))
    circuit_edges_fmt = [{"from": str(u), "to": str(v)} for u, v in circuit_edges]

    is_eul_path = nx.is_eulerian(euler_path_graph)
    has_eul_path = nx.has_eulerian_path(euler_path_graph)
    is_semi_path = nx.is_semieulerian(euler_path_graph)

    # Get Eulerian path edges (start from smallest odd-degree node)
    path_edges = list(nx.eulerian_path(euler_path_graph, source="c"))
    path_edges_fmt = [{"from": str(u), "to": str(v)} for u, v in path_edges]

    euler_fixture = {
        "suite": "euler_v1",
        "mode": "strict",
        "operations": node_ops(euler_circuit_graph) + edge_ops(euler_circuit_graph) + [
            {"op": "is_eulerian_query"},
            {"op": "has_eulerian_path_query"},
            {"op": "is_semieulerian_query"},
            {"op": "eulerian_circuit_query", "source": "a"},
        ],
        "expected": {
            "graph": graph_snapshot(euler_circuit_graph),
            "is_eulerian": is_eul,
            "has_eulerian_path": has_eul_path_circuit,
            "is_semieulerian": is_semi_circuit,
            "eulerian_circuit": circuit_edges_fmt,
        },
    }
    write_json(fixture_root / "euler_circuit_strict.json", euler_fixture)

    euler_path_fixture = {
        "suite": "euler_path_v1",
        "mode": "strict",
        "operations": node_ops(euler_path_graph) + edge_ops(euler_path_graph) + [
            {"op": "is_eulerian_query"},
            {"op": "has_eulerian_path_query"},
            {"op": "is_semieulerian_query"},
            {"op": "eulerian_path_query", "source": "c"},
        ],
        "expected": {
            "graph": graph_snapshot(euler_path_graph),
            "is_eulerian": is_eul_path,
            "has_eulerian_path": has_eul_path,
            "is_semieulerian": is_semi_path,
            "eulerian_path": path_edges_fmt,
        },
    }
    write_json(fixture_root / "euler_path_strict.json", euler_path_fixture)

    oracle_capture = {
        "oracle": "legacy_networkx",
        "legacy_root": str(legacy_root),
        "fixtures_generated": [
            "dispatch_route_strict.json",
            "convert_edge_list_strict.json",
            "readwrite_roundtrip_strict.json",
            "view_neighbors_strict.json",
            "readwrite_json_roundtrip_strict.json",
            "components_connected_strict.json",
            "generators_path_strict.json",
            "generators_cycle_strict.json",
            "generators_complete_strict.json",
            "centrality_degree_strict.json",
            "centrality_betweenness_strict.json",
            "centrality_edge_betweenness_strict.json",
            "centrality_closeness_strict.json",
            "centrality_harmonic_strict.json",
            "centrality_katz_strict.json",
            "centrality_hits_strict.json",
            "centrality_pagerank_strict.json",
            "centrality_eigenvector_strict.json",
            "matching_maximal_strict.json",
            "matching_max_weight_strict.json",
            "matching_min_weight_strict.json",
            "clustering_coefficient_strict.json",
            "distance_measures_strict.json",
            "average_shortest_path_length_strict.json",
            "is_connected_density_strict.json",
            "has_path_strict.json",
            "minimum_spanning_tree_strict.json",
            "triangles_square_clustering_strict.json",
            "tree_forest_strict.json",
            "greedy_color_strict.json",
            "bipartite_strict.json",
            "core_number_strict.json",
            "avg_neighbor_degree_strict.json",
            "cliques_strict.json",
            "node_connectivity_strict.json",
            "cycle_basis_strict.json",
            "paths_efficiency_cover_strict.json",
            "euler_circuit_strict.json",
            "euler_path_strict.json",
        ],
        "snapshots": {
            "convert_graph": graph_snapshot(convert_graph),
            "readwrite_graph": graph_snapshot(readwrite_graph),
            "view_graph": graph_snapshot(view_graph),
            "json_graph": graph_snapshot(json_graph),
            "components_graph": graph_snapshot(components_graph),
            "path_graph": graph_snapshot(path_graph),
            "cycle_graph": graph_snapshot(cycle_graph),
            "complete_graph": graph_snapshot(complete_graph),
            "centrality_graph": graph_snapshot(centrality_graph),
            "closeness_graph": graph_snapshot(closeness_graph),
            "pagerank_graph": graph_snapshot(pagerank_graph),
            "matching_graph": graph_snapshot(matching_graph),
            "clustering_graph": graph_snapshot(clustering_graph),
            "distance_graph": graph_snapshot(distance_graph),
            "aspl_graph": graph_snapshot(aspl_graph),
            "conn_graph": graph_snapshot(conn_graph),
            "hp_graph": graph_snapshot(hp_graph),
            "mst_graph": graph_snapshot(mst_graph),
            "tri_graph": graph_snapshot(tri_graph),
            "tree_graph": graph_snapshot(tree_graph),
            "color_graph": graph_snapshot(color_graph),
            "bip_graph": graph_snapshot(bip_graph),
            "core_graph": graph_snapshot(core_graph),
            "and_graph": graph_snapshot(and_graph),
            "clique_graph": graph_snapshot(clique_graph),
            "nc_graph": graph_snapshot(nc_graph),
            "cb_graph": graph_snapshot(cb_graph),
            "pec_graph": graph_snapshot(pec_graph),
            "euler_circuit_graph": graph_snapshot(euler_circuit_graph),
            "euler_path_graph": graph_snapshot(euler_path_graph),
        },
    }
    write_json(artifact_root / "legacy_networkx_capture.json", oracle_capture)

    print("Generated oracle-backed fixtures in", fixture_root)
    print("Wrote oracle capture artifact to", artifact_root / "legacy_networkx_capture.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
