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
                "risk_probability": 0.2,
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
    write_json(fixture_root / "centrality_closeness_strict.json", closeness_fixture)
    write_json(fixture_root / "centrality_pagerank_strict.json", pagerank_fixture)

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
            "centrality_closeness_strict.json",
            "centrality_pagerank_strict.json",
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
        },
    }
    write_json(artifact_root / "legacy_networkx_capture.json", oracle_capture)

    print("Generated oracle-backed fixtures in", fixture_root)
    print("Wrote oracle capture artifact to", artifact_root / "legacy_networkx_capture.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
