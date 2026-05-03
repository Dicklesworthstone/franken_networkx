"""Parity for fnx.pagerank weight-attribute handling.

Bead: br-r37-c1-f64cy. The concern was that ``fnx.pagerank`` might
silently fall back to unweighted whenever an edge lacks the named
weight attribute. NetworkX's contract is that missing attributes
default to ``1`` per edge — the result is the per-edge fallback, not
a global fallback. Probing confirms ``fnx.pagerank`` matches nx to
floating-point precision across:

- All edges weighted
- No edges weighted (key missing on every edge)
- Partial: some edges weighted, others missing
- Explicit ``weight=None``

These tests freeze that contract.
"""

from __future__ import annotations

import pytest

import franken_networkx as fnx

try:
    import networkx as nx
    HAS_NX = True
except ImportError:
    HAS_NX = False

needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


def _build_pair(builder):
    nx_graph = builder()
    f_graph = fnx.Graph()
    f_graph.add_nodes_from(nx_graph.nodes(data=True))
    f_graph.add_edges_from(nx_graph.edges(data=True))
    return f_graph, nx_graph


def _max_pagerank_diff(p1: dict, p2: dict) -> float:
    return max(abs(p1[k] - p2[k]) for k in p1)


@needs_nx
def test_pagerank_partial_weights_match_networkx():
    """Half-weighted graph: some edges have ``weight``, others don't.
    Each missing attribute should default to 1 per edge (not trigger a
    global unweighted fallback)."""
    def builder():
        g = nx.Graph()
        g.add_edge(0, 1, weight=2.0)
        g.add_edge(1, 2)
        g.add_edge(2, 3, weight=3.0)
        g.add_edge(3, 0)
        g.add_edge(0, 2, weight=1.0)
        return g

    f_graph, nx_graph = _build_pair(builder)
    r_fnx = fnx.pagerank(f_graph, weight="weight")
    r_nx = nx.pagerank(nx_graph, weight="weight")
    assert set(r_fnx) == set(r_nx)
    assert _max_pagerank_diff(r_fnx, r_nx) < 1e-9


@needs_nx
def test_pagerank_missing_weight_attribute_match_networkx():
    """``weight='nope'`` on a graph with no such attribute — nx treats
    every missing edge as weight=1 (i.e. unweighted-equivalent). fnx
    must agree."""
    def builder():
        g = nx.Graph()
        g.add_edges_from([(0, 1), (1, 2), (2, 3), (3, 0), (0, 2)])
        return g

    f_graph, nx_graph = _build_pair(builder)
    r_fnx = fnx.pagerank(f_graph, weight="nope")
    r_nx = nx.pagerank(nx_graph, weight="nope")
    assert _max_pagerank_diff(r_fnx, r_nx) < 1e-9


@needs_nx
def test_pagerank_weight_none_matches_networkx():
    """``weight=None`` short-circuits to unweighted on both sides."""
    def builder():
        g = nx.Graph()
        g.add_weighted_edges_from(
            [(0, 1, 2.0), (1, 2, 3.0), (2, 3, 1.0), (3, 0, 4.0)]
        )
        return g

    f_graph, nx_graph = _build_pair(builder)
    r_fnx = fnx.pagerank(f_graph, weight=None)
    r_nx = nx.pagerank(nx_graph, weight=None)
    assert _max_pagerank_diff(r_fnx, r_nx) < 1e-9


@needs_nx
@pytest.mark.parametrize("max_iter", [0, 1])
def test_pagerank_non_convergence_matches_networkx(max_iter):
    nx_graph = nx.DiGraph()
    nx_graph.add_edges_from([(0, 1), (1, 2), (2, 0), (2, 3)])
    f_graph = fnx.DiGraph()
    f_graph.add_edges_from(nx_graph.edges())

    with pytest.raises(nx.PowerIterationFailedConvergence):
        nx.pagerank(nx_graph, max_iter=max_iter, tol=1e-20)
    with pytest.raises(fnx.PowerIterationFailedConvergence):
        fnx.pagerank(f_graph, max_iter=max_iter, tol=1e-20)


@needs_nx
def test_pagerank_singleton_max_iter_zero_matches_networkx():
    nx_graph = nx.Graph()
    nx_graph.add_node(0)
    f_graph = fnx.Graph()
    f_graph.add_node(0)

    with pytest.raises(nx.PowerIterationFailedConvergence):
        nx.pagerank(nx_graph, max_iter=0)
    with pytest.raises(fnx.PowerIterationFailedConvergence):
        fnx.pagerank(f_graph, max_iter=0)


@needs_nx
def test_pagerank_non_string_weight_key_matches_networkx():
    """NetworkX accepts any hashable edge-attribute key for ``weight``.
    The Rust binding only accepts str/None, so integer keys must stay on
    the Python parity path instead of surfacing a PyO3 TypeError.
    """
    nx_graph = nx.path_graph(3)
    f_graph = fnx.path_graph(3)

    r_fnx = fnx.pagerank(f_graph, weight=1)
    r_nx = nx.pagerank(nx_graph, weight=1)
    assert _max_pagerank_diff(r_fnx, r_nx) < 1e-9


@needs_nx
def test_pagerank_all_edges_weighted_match_networkx():
    """Sanity check: when every edge carries ``weight`` the weighted
    PageRank matches nx exactly."""
    def builder():
        g = nx.Graph()
        g.add_weighted_edges_from(
            [(0, 1, 5.0), (1, 2, 2.0), (2, 0, 3.0), (2, 3, 1.0)]
        )
        return g

    f_graph, nx_graph = _build_pair(builder)
    r_fnx = fnx.pagerank(f_graph, weight="weight")
    r_nx = nx.pagerank(nx_graph, weight="weight")
    assert _max_pagerank_diff(r_fnx, r_nx) < 1e-9


@needs_nx
def test_pagerank_directed_partial_weights_match_networkx():
    """Same partial-weight contract on DiGraph — pagerank is the
    canonical use case."""
    def builder():
        g = nx.DiGraph()
        g.add_edge(0, 1, weight=2.0)
        g.add_edge(1, 2)  # no weight
        g.add_edge(2, 0, weight=3.0)
        g.add_edge(0, 2)  # no weight
        g.add_edge(1, 0, weight=1.0)
        return g

    nx_graph = builder()
    f_graph = fnx.DiGraph()
    f_graph.add_nodes_from(nx_graph.nodes(data=True))
    f_graph.add_edges_from(nx_graph.edges(data=True))

    r_fnx = fnx.pagerank(f_graph, weight="weight")
    r_nx = nx.pagerank(nx_graph, weight="weight")
    assert _max_pagerank_diff(r_fnx, r_nx) < 1e-9


@needs_nx
def test_pagerank_partial_differs_from_unweighted():
    """Sanity: when one edge dominates the weight distribution, the
    weighted PageRank must differ from the unweighted result. If fnx
    silently fell back to unweighted on a missing-attr edge, the two
    results would coincide and this test would fail."""
    g = nx.DiGraph()
    g.add_edge(0, 1, weight=10.0)
    g.add_edge(0, 2, weight=1.0)
    g.add_edge(1, 2)  # missing -> default 1
    g.add_edge(2, 0)
    fG = fnx.DiGraph()
    fG.add_edges_from(g.edges(data=True))

    weighted = fnx.pagerank(fG, weight="weight")
    unweighted = fnx.pagerank(fG, weight=None)
    assert any(abs(weighted[k] - unweighted[k]) > 1e-3 for k in weighted)


@needs_nx
def test_pagerank_nonnumeric_present_weight_matches_networkx_error():
    nx_graph = nx.DiGraph()
    nx_graph.add_edge("a", "b", weight="heavy")
    nx_graph.add_edge("b", "a", weight=1.0)
    f_graph = fnx.DiGraph()
    f_graph.add_edges_from(nx_graph.edges(data=True))

    with pytest.raises(ValueError, match="could not convert string to float"):
        nx.pagerank(nx_graph, weight="weight", max_iter=1000)
    with pytest.raises(ValueError, match="could not convert string to float"):
        fnx.pagerank(f_graph, weight="weight", max_iter=1000)


@needs_nx
def test_pagerank_infinite_present_weight_matches_networkx():
    nx_graph = nx.DiGraph()
    nx_graph.add_edge("a", "b", weight=float("inf"))
    nx_graph.add_edge("b", "a", weight=1.0)
    nx_graph.add_edge("a", "c", weight=2.0)
    nx_graph.add_edge("c", "a", weight=1.0)
    f_graph = fnx.DiGraph()
    f_graph.add_edges_from(nx_graph.edges(data=True))

    r_fnx = fnx.pagerank(f_graph, weight="weight", max_iter=1000)
    r_nx = nx.pagerank(nx_graph, weight="weight", max_iter=1000)
    assert _max_pagerank_diff(r_fnx, r_nx) < 1e-9
