"""Parity for edge_betweenness_centrality_subset (unhashable),
find_negative_cycle (unhashable), and triad_type (wrong-size graph
exception class).

Bead br-r37-c1-39gx2 (ninth follow-up to the unhashable-node series
plus a triad_type exception-class drift).

Three drifts found in the post-tm1tq probe:

  edge_betweenness_centrality_subset(sources=[unhashable])  fnx: <silent ok>      nx: TypeError
  find_negative_cycle(source=unhashable)                    fnx: NetworkXError    nx: TypeError
  triad_type(G with order != 3)                             fnx: NetworkXError    nx: NetworkXAlgorithmError

``edge_betweenness_centrality_subset`` was UNDER-strict (silent on
unhashable members) — same fix as ``betweenness_centrality_subset``.
``find_negative_cycle`` raised the wrong class (its Rust impl
silently returns 'no cycle' on unhashable, then NetworkXError fires);
nx delegates to bellman_ford which raises TypeError.  ``triad_type``
used the generic ``NetworkXError`` class for size-violations;
nx uses the more specific ``NetworkXAlgorithmError`` so callers can
distinguish algorithm-invariant breaches from misc usage errors.
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

UNHASHABLE = [
    pytest.param([1, 2], id="list"),
    pytest.param({1, 2}, id="set"),
    pytest.param({"a": 1}, id="dict"),
]


# ---------------------------------------------------------------------------
# edge_betweenness_centrality_subset — TypeError on unhashable sources/targets
# ---------------------------------------------------------------------------

@needs_nx
@pytest.mark.parametrize("val", UNHASHABLE)
def test_edge_betweenness_subset_unhashable_sources_typeerror(val):
    G = fnx.Graph([(1, 2), (2, 3)])
    GX = nx.Graph([(1, 2), (2, 3)])
    with pytest.raises(TypeError, match=r"unhashable type"):
        fnx.edge_betweenness_centrality_subset(G, [val], [1])
    with pytest.raises(TypeError, match=r"unhashable type"):
        nx.edge_betweenness_centrality_subset(GX, [val], [1])


@needs_nx
@pytest.mark.parametrize("val", UNHASHABLE)
def test_edge_betweenness_subset_unhashable_targets_typeerror(val):
    G = fnx.Graph([(1, 2), (2, 3)])
    GX = nx.Graph([(1, 2), (2, 3)])
    with pytest.raises(TypeError, match=r"unhashable type"):
        fnx.edge_betweenness_centrality_subset(G, [1], [val])
    with pytest.raises(TypeError, match=r"unhashable type"):
        nx.edge_betweenness_centrality_subset(GX, [1], [val])


# ---------------------------------------------------------------------------
# find_negative_cycle — TypeError on unhashable source
# ---------------------------------------------------------------------------

@needs_nx
@pytest.mark.parametrize("val", UNHASHABLE)
def test_find_negative_cycle_unhashable_source_typeerror(val):
    G = fnx.Graph([(1, 2), (2, 3)])
    GX = nx.Graph([(1, 2), (2, 3)])
    with pytest.raises(TypeError, match=r"unhashable type"):
        fnx.find_negative_cycle(G, val)
    with pytest.raises(TypeError, match=r"unhashable type"):
        nx.find_negative_cycle(GX, val)


@needs_nx
@pytest.mark.parametrize("val", UNHASHABLE)
def test_find_negative_cycle_unhashable_source_typeerror_directed(val):
    """Directed path delegates to nx — verify TypeError parity there too."""
    G = fnx.DiGraph([(1, 2), (2, 3)])
    GX = nx.DiGraph([(1, 2), (2, 3)])
    with pytest.raises(TypeError, match=r"unhashable type"):
        fnx.find_negative_cycle(G, val)
    with pytest.raises(TypeError, match=r"unhashable type"):
        nx.find_negative_cycle(GX, val)


# ---------------------------------------------------------------------------
# triad_type — NetworkXAlgorithmError on order != 3
# ---------------------------------------------------------------------------

@needs_nx
def test_triad_type_too_few_nodes_raises_algorithm_error():
    G = fnx.DiGraph([(1, 2)])
    GX = nx.DiGraph([(1, 2)])
    with pytest.raises(fnx.NetworkXAlgorithmError, match=r"order-3"):
        fnx.triad_type(G)
    with pytest.raises(nx.NetworkXAlgorithmError, match=r"order-3"):
        nx.triad_type(GX)


@needs_nx
def test_triad_type_too_many_nodes_raises_algorithm_error():
    G = fnx.DiGraph([(1, 2), (2, 3), (3, 4)])
    GX = nx.DiGraph([(1, 2), (2, 3), (3, 4)])
    with pytest.raises(fnx.NetworkXAlgorithmError, match=r"order-3"):
        fnx.triad_type(G)
    with pytest.raises(nx.NetworkXAlgorithmError, match=r"order-3"):
        nx.triad_type(GX)


@needs_nx
def test_triad_type_undirected_still_raises_not_implemented():
    """Undirected guard (br-r37-c1-n7rgh) takes precedence over the
    order-3 check — both nx and fnx fire the @not_implemented_for
    decorator first."""
    G = fnx.Graph([(1, 2), (2, 3), (3, 1)])
    GX = nx.Graph([(1, 2), (2, 3), (3, 1)])
    with pytest.raises(fnx.NetworkXNotImplemented):
        fnx.triad_type(G)
    with pytest.raises(nx.NetworkXNotImplemented):
        nx.triad_type(GX)


# ---------------------------------------------------------------------------
# Regressions — hashable inputs unaffected
# ---------------------------------------------------------------------------

@needs_nx
def test_edge_betweenness_subset_hashable_unchanged():
    G = fnx.Graph([(1, 2), (2, 3), (3, 4)])
    GX = nx.Graph([(1, 2), (2, 3), (3, 4)])
    f = fnx.edge_betweenness_centrality_subset(G, [1], [4])
    n = nx.edge_betweenness_centrality_subset(GX, [1], [4])
    f_norm = {tuple(sorted(k)): round(v, 9) for k, v in f.items()}
    n_norm = {tuple(sorted(k)): round(v, 9) for k, v in n.items()}
    assert f_norm == n_norm


@needs_nx
def test_find_negative_cycle_hashable_unchanged():
    """Find a real negative cycle on a hashable directed graph."""
    G = fnx.DiGraph()
    G.add_weighted_edges_from([(0, 1, 1), (1, 2, -3), (2, 0, 1)])
    GX = nx.DiGraph()
    GX.add_weighted_edges_from([(0, 1, 1), (1, 2, -3), (2, 0, 1)])
    f = fnx.find_negative_cycle(G, 0)
    n = nx.find_negative_cycle(GX, 0)
    # Order-of-emission may vary; compare as a cycle set.
    assert set(f) == set(n)


@needs_nx
def test_triad_type_3node_unchanged():
    G = fnx.DiGraph([(1, 2), (2, 3), (3, 1)])
    GX = nx.DiGraph([(1, 2), (2, 3), (3, 1)])
    assert fnx.triad_type(G) == nx.triad_type(GX)


@needs_nx
def test_triad_type_algorithm_error_inherits_from_networkx_exception():
    """NetworkXAlgorithmError descends from NetworkXException (not
    NetworkXError) — both fnx and nx agree on this hierarchy.  Code
    catching NetworkXException still works after the class refinement."""
    G = fnx.DiGraph([(1, 2)])
    with pytest.raises(fnx.NetworkXException):
        fnx.triad_type(G)
    assert issubclass(fnx.NetworkXAlgorithmError, fnx.NetworkXException)
    assert not issubclass(fnx.NetworkXAlgorithmError, fnx.NetworkXError)
