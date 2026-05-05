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


def _directed_cycle5():
    G = fnx.DiGraph()
    G.add_edges_from([(i, (i + 1) % 5) for i in range(5)])
    return G


def _directed_cycle5_with_chord():
    G = fnx.DiGraph()
    G.add_edges_from([(i, (i + 1) % 5) for i in range(5)] + [(0, 2)])
    return G


GRAPH_FACTORIES = (
    ("karate", "karate_club_graph", fnx.karate_club_graph),
    ("florentine", "florentine_families_graph", fnx.florentine_families_graph),
    ("path7", "path_graph(7)", lambda: fnx.path_graph(7)),
    ("cycle6", "cycle_graph(6)", lambda: fnx.cycle_graph(6)),
    ("k4", "complete_graph(4)", lambda: fnx.complete_graph(4)),
    ("k33", "complete_bipartite_graph(3,3)", lambda: fnx.complete_bipartite_graph(3, 3)),
    # br-r37-c1-{89n9d,wojl3,e04a1}: lock the directed distance-metric
    # fix surface against future regressions.
    ("dicycle5", "DiGraph cycle5", _directed_cycle5),
    ("dicycle5+chord", "DiGraph cycle5+(0,2) chord", _directed_cycle5_with_chord),
    # br-r37-c1-{gttlp, fbons, 7t95c}: lock is_planar, core_number,
    # square_clustering on canonical Kuratowski-pair fixtures.
    ("petersen", "petersen_graph", lambda: fnx.petersen_graph()),
    ("k5", "complete_graph(5)", lambda: fnx.complete_graph(5)),
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
    is_directed = graph.is_directed()
    payload = {
        "transitivity": _norm_number(fnx.transitivity(graph)),
        "wiener_index": _norm_number(fnx.wiener_index(graph)),
        "load_centrality": _norm_dict_centrality(fnx.load_centrality(graph)),
        "harmonic_centrality": _norm_dict_centrality(fnx.harmonic_centrality(graph)),
        "degree_centrality": _norm_dict_centrality(fnx.degree_centrality(graph)),
        "clustering": _norm_dict_centrality(fnx.clustering(graph)),
        "triangles": _norm_dict_centrality(fnx.triangles(graph)) if not is_directed else None,
        # br-r37-c1-89n9d, br-r37-c1-wojl3, br-r37-c1-e04a1: lock the
        # directed-distance-metric surface fix into the golden so a
        # future regression that reroutes via the buggy raw _fnx
        # produces a visible diff.
        "eccentricity": _norm_dict_centrality(fnx.eccentricity(graph)),
        "diameter": _norm_number(fnx.diameter(graph)),
        "radius": _norm_number(fnx.radius(graph)),
        "center": sorted([_norm_node(n) for n in fnx.center(graph)], key=str),
        "periphery": sorted([_norm_node(n) for n in fnx.periphery(graph)], key=str),
        "find_cliques": _norm_find_cliques(fnx.find_cliques(graph)) if not is_directed else None,
        "complement_edges": _norm_edges(fnx.complement(graph).edges()),
        # cycle_basis / connected_components are undirected-only;
        # keep them in the snapshot for non-directed fixtures.
    }
    if not is_directed:
        payload["connected_components"] = _norm_components(fnx.connected_components(graph))
        payload["cycle_basis"] = _norm_cycle_basis(fnx.cycle_basis(graph))
        # br-r37-c1-{gttlp, fbons, 7t95c}: snapshot the recently-fixed
        # is_planar fast path, core_number perf surface, and
        # square_clustering wrapper-bypass output. Undirected-only
        # because is_planar / core_number raise on directed in fnx
        # (matching nx's contract).
        payload["is_planar"] = bool(fnx.is_planar(graph))
        try:
            payload["core_number"] = _norm_dict_centrality(fnx.core_number(graph))
        except Exception as exc:  # pragma: no cover
            payload["core_number"] = f"<{type(exc).__name__}>"
        payload["square_clustering"] = _norm_dict_centrality(fnx.square_clustering(graph))
        # br-r37-c1-8e60l: lock the link-prediction family's score
        # outputs into the golden. The lazy-delegate fix could silently
        # regress score precision and pass diff tests but visibly
        # drift here.
        #
        # Keying on the (u, v) tuple is unstable across runs because
        # nx.non_edges iteration depends on PYTHONHASHSEED for string
        # nodes. So instead we snapshot the AGGREGATED scores: sorted
        # by score (descending), then by canonical str-tuple to break
        # ties. The aggregate is deterministic because the score
        # multiset is invariant under iteration order.
        def _norm_link_pred_aggregate(triples):
            # nx.non_edges emits each unordered pair once but the
            # (u, v) ORIENTATION depends on PYTHONHASHSEED for string
            # nodes. For undirected scores the value is symmetric, so
            # canonicalize to (min, max) by string then dedupe.
            seen = {}
            for u, v, s in triples:
                a, b = sorted([_norm_node(u), _norm_node(v)], key=str)
                seen[(a, b)] = _norm_number(s)
            scored = [(a, b, s) for (a, b), s in seen.items()]
            scored.sort(key=lambda t: (str(t[2]), str(t[0]), str(t[1])))
            return [list(t) for t in scored]
        payload["jaccard_coefficient"] = _norm_link_pred_aggregate(
            fnx.jaccard_coefficient(graph)
        )
        payload["preferential_attachment"] = _norm_link_pred_aggregate(
            fnx.preferential_attachment(graph)
        )
        # br-r37-c1-{qkq2h, jy2ea, ni9va}: lock common_neighbors and
        # non_neighbors on the wrapper-bypass family. Pick the
        # lexicographically-smallest two nodes by str() to keep the
        # probe-pair stable across runs (PYTHONHASHSEED-safe).
        nodes_sorted = sorted(graph.nodes(), key=str)
        if len(nodes_sorted) >= 2:
            u, v = nodes_sorted[0], nodes_sorted[1]
            payload["common_neighbors_first_pair"] = sorted(
                [_norm_node(n) for n in fnx.common_neighbors(graph, u, v)],
                key=str,
            )
            payload["non_neighbors_first_node"] = sorted(
                [_norm_node(n) for n in fnx.non_neighbors(graph, u)],
                key=str,
            )
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
