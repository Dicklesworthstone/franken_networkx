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


def _assert_payload_close(actual, expected, *, rel_tol=1e-12, abs_tol=0.0):
    """Compare two snapshot payloads, tolerating last-digit ULP drift.

    br-r37-c1-i7wr1: ``.15g`` formatting sits at the float64 precision
    boundary, so equally-correct implementations differ by 1 ULP in the
    final digit (BLAS/CPU/opt variance).  Compare the score *values*
    numerically with math.isclose; keep strict equality on the
    structural metadata (factory names, node/edge counts, schema).
    """
    import math

    assert actual["schema_version"] == expected["schema_version"]
    assert actual["numeric_format"] == expected["numeric_format"]
    assert set(actual["graphs"]) == set(expected["graphs"])
    for graph_id in actual["graphs"]:
        a_graph = actual["graphs"][graph_id]
        e_graph = expected["graphs"][graph_id]
        assert a_graph["factory"] == e_graph["factory"], graph_id
        assert a_graph["node_count"] == e_graph["node_count"], graph_id
        assert a_graph["edge_count"] == e_graph["edge_count"], graph_id
        assert set(a_graph["algorithms"]) == set(e_graph["algorithms"]), graph_id
        for alg_name in a_graph["algorithms"]:
            a_scores = a_graph["algorithms"][alg_name]
            e_scores = e_graph["algorithms"][alg_name]
            assert len(a_scores) == len(e_scores), f"{graph_id}/{alg_name}"
            for (a_node, a_value), (e_node, e_value) in zip(a_scores, e_scores):
                assert a_node == e_node, f"{graph_id}/{alg_name}: node order"
                assert math.isclose(
                    float(a_value), float(e_value),
                    rel_tol=rel_tol, abs_tol=abs_tol,
                ), (
                    f"{graph_id}/{alg_name} at node {a_node!r}: "
                    f"actual={a_value} expected={e_value}"
                )


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

    _assert_payload_close(actual, expected)
