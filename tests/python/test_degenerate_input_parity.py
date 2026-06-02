"""Systematic degenerate-input parity: run a battery of algorithms against the
empty graph, a single node, isolated nodes, a lone self-loop, and disconnected
graphs, asserting franken_networkx matches networkx on BOTH the return value
and the raised-exception *type*.

Degenerate inputs are a recurring source of silent divergence — the
session-1 ``degree(weight=)`` self-loop bug (nx counts a self-loop twice,
fnx counted it once) was exactly this shape, as was the ``transitivity``
empty-graph int-vs-float return. Per-feature tests rarely sweep the full
algorithm × degenerate-shape cross product; this does, cheaply, so a future
refactor that changes how an empty/self-loop/disconnected graph is handled
trips a test instead of shipping.
"""

import math

import networkx as nx
import franken_networkx as fnx

import pytest


# --- degenerate graph shapes, built identically on each library ------------

def _shapes(mod):
    shapes = {}
    shapes["empty"] = mod.Graph()
    g = mod.Graph(); g.add_node(0); shapes["single"] = g
    g = mod.Graph(); g.add_nodes_from([0, 1]); shapes["two_isolated"] = g
    g = mod.Graph(); g.add_edge(0, 0); shapes["self_loop"] = g
    g = mod.Graph(); g.add_edge(0, 1); shapes["one_edge"] = g
    g = mod.Graph(); g.add_edge(0, 1); g.add_edge(2, 3); shapes["two_components"] = g
    shapes["complete2"] = mod.complete_graph(2)
    return shapes


_NX_SHAPES = _shapes(nx)
_FNX_SHAPES = _shapes(fnx)
_SHAPE_NAMES = sorted(_NX_SHAPES)


# --- algorithms keyed by name -> (nx_callable, fnx_callable) ----------------
# Only deterministic, value-comparable algorithms (no unseeded randomness).

_ALGOS = {
    "density": (nx.density, fnx.density),
    "transitivity": (nx.transitivity, fnx.transitivity),
    "average_clustering": (nx.average_clustering, fnx.average_clustering),
    "number_connected_components": (nx.number_connected_components, fnx.number_connected_components),
    "is_connected": (nx.is_connected, fnx.is_connected),
    "diameter": (nx.diameter, fnx.diameter),
    "radius": (nx.radius, fnx.radius),
    "degree_assortativity_coefficient": (nx.degree_assortativity_coefficient, fnx.degree_assortativity_coefficient),
    "is_tree": (nx.is_tree, fnx.is_tree),
    "is_forest": (nx.is_forest, fnx.is_forest),
    "is_bipartite": (nx.is_bipartite, fnx.is_bipartite),
    "is_eulerian": (nx.is_eulerian, fnx.is_eulerian),
    "is_chordal": (nx.is_chordal, fnx.is_chordal),
    "wiener_index": (nx.wiener_index, fnx.wiener_index),
    "clustering": (nx.clustering, fnx.clustering),
    "triangles": (nx.triangles, fnx.triangles),
    "core_number": (nx.core_number, fnx.core_number),
    "pagerank": (nx.pagerank, fnx.pagerank),
    "degree_centrality": (nx.degree_centrality, fnx.degree_centrality),
    "closeness_centrality": (nx.closeness_centrality, fnx.closeness_centrality),
    "betweenness_centrality": (nx.betweenness_centrality, fnx.betweenness_centrality),
    "harmonic_centrality": (nx.harmonic_centrality, fnx.harmonic_centrality),
    "average_shortest_path_length": (nx.average_shortest_path_length, fnx.average_shortest_path_length),
    "global_efficiency": (nx.global_efficiency, fnx.global_efficiency),
    "local_efficiency": (nx.local_efficiency, fnx.local_efficiency),
    "degree_histogram": (nx.degree_histogram, fnx.degree_histogram),
    "overall_reciprocity": (nx.overall_reciprocity, fnx.overall_reciprocity),
    "is_planar": (lambda G: nx.check_planarity(G)[0], lambda G: fnx.check_planarity(G)[0]),
    "find_cliques_count": (
        lambda G: sum(1 for _ in nx.find_cliques(G)),
        lambda G: sum(1 for _ in fnx.find_cliques(G)),
    ),
    "maximal_matching_size": (
        lambda G: len(nx.maximal_matching(G)),
        lambda G: len(fnx.maximal_matching(G)),
    ),
}


def _normalize(x):
    if isinstance(x, dict):
        return {k: _normalize(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return type(x)(_normalize(v) for v in x)
    if isinstance(x, float):
        return round(x, 7) if math.isfinite(x) else repr(x)
    return x


def _outcome(fn, graph):
    """Return ('ok', value) or ('err', ExceptionTypeName)."""
    try:
        return ("ok", _normalize(fn(graph)))
    except Exception as exc:  # noqa: BLE001 — exception-type parity is the point
        return ("err", type(exc).__name__)


@pytest.mark.parametrize("algo", sorted(_ALGOS))
@pytest.mark.parametrize("shape", _SHAPE_NAMES)
def test_degenerate_input_matches_networkx(algo, shape):
    nx_fn, fnx_fn = _ALGOS[algo]
    nx_out = _outcome(nx_fn, _NX_SHAPES[shape])
    fnx_out = _outcome(fnx_fn, _FNX_SHAPES[shape])
    assert fnx_out == nx_out, (
        f"{algo} on '{shape}' graph: networkx -> {nx_out}, "
        f"franken_networkx -> {fnx_out}"
    )


def test_self_loop_weighted_degree_still_double_counts():
    # Direct guard for the session-1 regression: a self-loop's weight is
    # counted twice in the (undirected) weighted degree.
    Gn = nx.Graph(); Gn.add_edge(0, 1, weight=4.0); Gn.add_edge(1, 1, weight=5.0)
    Gf = fnx.Graph(); Gf.add_edge(0, 1, weight=4.0); Gf.add_edge(1, 1, weight=5.0)
    assert dict(Gf.degree(weight="weight")) == dict(Gn.degree(weight="weight"))
    assert Gf.degree(1, weight="weight") == 14.0
