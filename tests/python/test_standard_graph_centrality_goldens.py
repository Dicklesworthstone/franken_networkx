"""Golden snapshots for centrality outputs on named social graphs."""

from __future__ import annotations

import json
import os
from pathlib import Path

import franken_networkx as fnx


GOLDEN_DIR = Path(__file__).with_name("goldens")
GOLDEN_PATH = GOLDEN_DIR / "standard_graph_centralities.json"
NUMERIC_FORMAT = ".15g"

GRAPH_FACTORIES = (
    ("karate", "karate_club_graph", fnx.karate_club_graph),
    ("davis_southern_women", "davis_southern_women_graph", fnx.davis_southern_women_graph),
    ("florentine_families", "florentine_families_graph", fnx.florentine_families_graph),
)

ALGORITHMS = (
    ("pagerank", lambda graph: fnx.pagerank(graph, max_iter=1000, tol=1.0e-12)),
    ("degree_centrality", fnx.degree_centrality),
    ("closeness_centrality", fnx.closeness_centrality),
    ("betweenness_centrality", fnx.betweenness_centrality),
    (
        "eigenvector_centrality",
        lambda graph: fnx.eigenvector_centrality(graph, max_iter=1000, tol=1.0e-12),
    ),
)


def _json_node(node):
    if isinstance(node, str | int | float) or node is None:
        return node
    return repr(node)


def _canonical_scores(scores):
    return [
        [_json_node(node), format(float(value), NUMERIC_FORMAT)]
        for node, value in scores.items()
    ]


def _snapshot_payload():
    graphs = {}
    for graph_id, factory_name, factory in GRAPH_FACTORIES:
        graph = factory()
        graphs[graph_id] = {
            "factory": factory_name,
            "node_count": graph.number_of_nodes(),
            "edge_count": graph.number_of_edges(),
            "algorithms": {
                algorithm_name: _canonical_scores(algorithm(graph))
                for algorithm_name, algorithm in ALGORITHMS
            },
        }
    return {
        "schema_version": 1,
        "numeric_format": NUMERIC_FORMAT,
        "graphs": graphs,
    }


def test_standard_graph_centralities_match_json_golden():
    actual = _snapshot_payload()

    if os.environ.get("UPDATE_GOLDENS") == "1":
        GOLDEN_PATH.write_text(
            json.dumps(actual, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    try:
        with GOLDEN_PATH.open(encoding="utf-8") as golden_file:
            expected = json.load(golden_file)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"invalid centrality golden JSON: {GOLDEN_PATH}") from exc

    assert actual == expected
