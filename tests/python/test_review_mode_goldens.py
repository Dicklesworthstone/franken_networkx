"""Golden-output snapshots for the algorithms touched by 2026-05-03 REVIEW MODE.

Pins the *exact* serialized output (canonicalized) on the named-graph
fixtures so that a silent change to ordering, precision, or set-vs-list
contract trips a hard mismatch — independent of nx parity. Conformance
tests can become stale when both libs drift together; goldens never
do.

To regenerate after an intentional output change:

  UPDATE_GOLDENS=1 pytest tests/python/test_review_mode_goldens.py
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path

import franken_networkx as fnx


GOLDEN_DIR = Path(__file__).with_name("goldens")
GOLDEN_PATH = GOLDEN_DIR / "review_mode_algorithms.json"
NUMERIC_FORMAT = ".15g"


GRAPH_FACTORIES = (
    ("karate", "karate_club_graph", fnx.karate_club_graph),
    ("florentine", "florentine_families_graph", fnx.florentine_families_graph),
    ("path7", "path_graph(7)", lambda: fnx.path_graph(7)),
    ("cycle6", "cycle_graph(6)", lambda: fnx.cycle_graph(6)),
    ("k4", "complete_graph(4)", lambda: fnx.complete_graph(4)),
    ("k33", "complete_bipartite_graph(3,3)", lambda: fnx.complete_bipartite_graph(3, 3)),
)


def _norm_node(node):
    """Stable, JSON-serializable representation of a node label."""
    if isinstance(node, str | int | float) or node is None:
        return node
    return repr(node)


def _norm_number(value):
    """Stable string representation of a float (handles ±inf, NaN)."""
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if math.isnan(value):
            return "nan"
        if math.isinf(value):
            return "inf" if value > 0 else "-inf"
        return format(value, NUMERIC_FORMAT)
    return value


def _norm_edge(u, v):
    a, b = _norm_node(u), _norm_node(v)
    return [a, b] if (str(a), str(b)) <= (str(b), str(a)) else [b, a]


def _norm_dict_centrality(d):
    return [[_norm_node(k), _norm_number(v)] for k, v in sorted(d.items(), key=lambda kv: str(kv[0]))]


def _norm_components(generator):
    """Components: sort each component's nodes, then sort components."""
    out = [sorted([_norm_node(n) for n in comp], key=str) for comp in generator]
    out.sort(key=lambda comp: (len(comp), [str(x) for x in comp]))
    return out


def _norm_edges(edges):
    norm = [sorted([_norm_node(u), _norm_node(v)], key=str) for u, v in edges]
    norm.sort(key=lambda e: (str(e[0]), str(e[1])))
    return norm


def _norm_cycle_basis(basis):
    out = [sorted([_norm_node(n) for n in cycle], key=str) for cycle in basis]
    out.sort(key=lambda c: (len(c), [str(x) for x in c]))
    return out


def _norm_find_cliques(cliques):
    out = [sorted([_norm_node(n) for n in clique], key=str) for clique in cliques]
    out.sort(key=lambda c: (len(c), [str(x) for x in c]))
    return out


def _algorithms_for(graph):
    """Return canonicalized outputs for each REVIEW MODE-touched algo
    on the given graph."""
    payload = {
        "transitivity": _norm_number(fnx.transitivity(graph)),
        "wiener_index": _norm_number(fnx.wiener_index(graph)),
        "load_centrality": _norm_dict_centrality(fnx.load_centrality(graph)),
        "connected_components": _norm_components(fnx.connected_components(graph)),
        "cycle_basis": _norm_cycle_basis(fnx.cycle_basis(graph)),
        "find_cliques": _norm_find_cliques(fnx.find_cliques(graph)),
        "complement_edges": _norm_edges(fnx.complement(graph).edges()),
        # barycenter only valid for connected graphs; protect with a try.
    }
    try:
        payload["barycenter"] = sorted([_norm_node(n) for n in fnx.barycenter(graph)], key=str)
    except Exception as exc:  # pragma: no cover — record reason if it fails
        payload["barycenter"] = f"<{type(exc).__name__}>"
    return payload


def _snapshot_payload():
    graphs = {}
    for graph_id, factory_name, factory in GRAPH_FACTORIES:
        graph = factory()
        graphs[graph_id] = {
            "factory": factory_name,
            "node_count": graph.number_of_nodes(),
            "edge_count": graph.number_of_edges(),
            "algorithms": _algorithms_for(graph),
        }
    return {
        "schema_version": 1,
        "numeric_format": NUMERIC_FORMAT,
        "graphs": graphs,
    }


def test_review_mode_algorithm_outputs_match_json_golden():
    actual = _snapshot_payload()

    if os.environ.get("UPDATE_GOLDENS") == "1":
        GOLDEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN_PATH.write_text(
            json.dumps(actual, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    try:
        with GOLDEN_PATH.open(encoding="utf-8") as golden_file:
            expected = json.load(golden_file)
    except FileNotFoundError as exc:  # pragma: no cover — first run
        raise AssertionError(
            f"missing golden {GOLDEN_PATH}; regenerate with UPDATE_GOLDENS=1"
        ) from exc
    except json.JSONDecodeError as exc:
        raise AssertionError(f"invalid review-mode golden JSON: {GOLDEN_PATH}") from exc

    assert actual == expected
