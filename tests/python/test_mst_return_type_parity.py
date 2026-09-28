"""Parity for ``minimum_spanning_tree`` / ``maximum_spanning_tree``
return type.

Bead br-r37-c1-rtak4. The MST wrappers delegated through
_call_networkx_for_parity which returns the nx.Graph result
unchanged. Downstream fnx.* calls (is_connected, is_tree, etc.)
type-check for fnx.Graph and rejected the foreign nx.Graph.

Pre-existing test_hypothesis.py::TestMSTInvariants::test_mst_is_connected
and test_mst_is_tree failed for this reason.

Repro:
  fnx.minimum_spanning_tree(g) -> nx.Graph (pre-fix)
  fnx.is_connected(mst) -> TypeError "expected Graph, DiGraph, ..."

Fix replaces the _call_networkx_for_parity call with a direct
nx.minimum_spanning_tree + _from_nx_graph rehydration so the
result is an fnx.Graph.
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


def _make_weighted(lib, edges):
    g = lib.Graph()
    for u, v, w in edges:
        g.add_edge(u, v, weight=w)
    return g


@needs_nx
def test_min_spanning_tree_returns_fnx_graph():
    g = _make_weighted(fnx, [(0, 1, 1), (1, 2, 2), (2, 0, 3)])
    mst = fnx.minimum_spanning_tree(g)
    assert isinstance(mst, fnx.Graph)
    assert type(mst).__module__.startswith("franken_networkx") or isinstance(mst, fnx.Graph)


@needs_nx
def test_max_spanning_tree_returns_fnx_graph():
    g = _make_weighted(fnx, [(0, 1, 1), (1, 2, 2), (2, 0, 3)])
    mst = fnx.maximum_spanning_tree(g)
    assert isinstance(mst, fnx.Graph)


@needs_nx
def test_min_spanning_tree_compatible_with_is_connected():
    """is_connected should accept the returned MST (regression)."""
    g = _make_weighted(fnx, [(0, 1, 1), (1, 2, 2), (2, 0, 3), (2, 3, 1)])
    mst = fnx.minimum_spanning_tree(g)
    assert fnx.is_connected(mst)


@needs_nx
def test_min_spanning_tree_compatible_with_is_tree():
    g = _make_weighted(fnx, [(0, 1, 1), (1, 2, 2), (2, 0, 3), (2, 3, 1)])
    mst = fnx.minimum_spanning_tree(g)
    assert fnx.is_tree(mst)


@needs_nx
def test_max_spanning_tree_compatible_with_is_connected():
    g = _make_weighted(fnx, [(0, 1, 1), (1, 2, 2), (2, 0, 3), (2, 3, 1)])
    mst = fnx.maximum_spanning_tree(g)
    assert fnx.is_connected(mst)


@needs_nx
def test_min_spanning_tree_edges_match_nx():
    """The returned MST's edges should still match nx's contract."""
    edges = [(0, 1, 1), (1, 2, 2), (2, 0, 3), (2, 3, 1), (3, 0, 5)]
    g = _make_weighted(fnx, edges)
    gx = _make_weighted(nx, edges)
    f = fnx.minimum_spanning_tree(g)
    n = nx.minimum_spanning_tree(gx)
    assert sorted(f.edges()) == sorted(n.edges())


@needs_nx
def test_max_spanning_tree_edges_match_nx():
    edges = [(0, 1, 1), (1, 2, 2), (2, 0, 3), (2, 3, 1), (3, 0, 5)]
    g = _make_weighted(fnx, edges)
    gx = _make_weighted(nx, edges)
    f = fnx.maximum_spanning_tree(g)
    n = nx.maximum_spanning_tree(gx)
    assert sorted(f.edges()) == sorted(n.edges())


@needs_nx
def test_min_spanning_tree_with_prim_returns_fnx_graph():
    g = _make_weighted(fnx, [(0, 1, 1), (1, 2, 2), (2, 0, 3)])
    mst = fnx.minimum_spanning_tree(g, algorithm="prim")
    assert isinstance(mst, fnx.Graph)


@needs_nx
def test_min_spanning_tree_with_callable_weight_returns_fnx_graph():
    """Callable weight forces the nx-delegation path."""
    g = fnx.Graph()
    for u, v in [(0, 1), (1, 2), (2, 0)]:
        g.add_edge(u, v)
    mst = fnx.minimum_spanning_tree(g, weight=lambda u, v, d: 1.0)
    assert isinstance(mst, fnx.Graph)


@needs_nx
def test_unweighted_graph_uses_rust_fast_path_still_fnx_graph():
    """Unweighted graph hits the Rust fast path; verify result is
    still fnx.Graph (was already correct before the fix)."""
    g = fnx.path_graph(5)
    mst = fnx.minimum_spanning_tree(g)
    assert isinstance(mst, fnx.Graph)


@needs_nx
def test_directed_input_raises():
    dg = fnx.DiGraph([(0, 1)])
    with pytest.raises(fnx.NetworkXNotImplemented, match="directed"):
        fnx.minimum_spanning_tree(dg)


@needs_nx
def test_min_spanning_tree_with_ignore_nan_returns_fnx_graph():
    g = fnx.Graph()
    g.add_edge(0, 1, weight=1.0)
    g.add_edge(1, 2, weight=float("nan"))
    g.add_edge(2, 0, weight=2.0)
    mst = fnx.minimum_spanning_tree(g, ignore_nan=True)
    assert isinstance(mst, fnx.Graph)


@needs_nx
def test_class_preserved_on_multigraph_subclass():
    """If input is a MultiGraph the result should be a MultiGraph."""
    mg = fnx.MultiGraph()
    mg.add_edge(0, 1, weight=1)
    mg.add_edge(1, 2, weight=2)
    mst = fnx.minimum_spanning_tree(mg)
    assert isinstance(mst, fnx.MultiGraph)


# br-r37-c1-w0902: networkx builds every spanning tree as ``G.__class__()`` from
# the spanning edges. fnx's native Kruskal trees and its prim / boruvka trees
# were plain Graphs for a Graph subclass, maximum prim / boruvka went through a
# networkx round trip (0.26-0.28x), and the Boruvka a subclass takes walked each
# component in graph order where networkx walks the set it builds from it - so
# on tied weights it returned another spanning tree.


class _FnxSub(fnx.Graph):
    pass


class _NxSub(nx.Graph if HAS_NX else object):
    pass


def _tied(lib, kind, seed):
    cls = {"plain": lib.Graph, "subclass": _FnxSub if lib is fnx else _NxSub}.get(kind, lib.Graph)
    G = cls()
    G.graph["name"] = f"g{seed}"
    G.add_nodes_from((i, {"c": i % 3}) for i in range(14))
    G.add_weighted_edges_from(
        (i, (i * (seed + 3) + 1) % 14, (i * seed) % 3 + 1) for i in range(14)
    )
    G.add_weighted_edges_from((i, (i + 1) % 14, 2) for i in range(14))
    G.add_node("isolated")
    if kind == "view":
        return G.subgraph([n for n in G if n != 3])
    return G


def _tree_state(T):
    kind = type(T).__name__
    return (
        {"_FnxSub": "subclass", "_NxSub": "subclass"}.get(kind, kind),
        dict(T.graph),
        list(T.nodes(data=True)),
        list(T.edges(data=True)),
    )


@needs_nx
@pytest.mark.parametrize("seed", range(4))
@pytest.mark.parametrize("kind", ["plain", "subclass", "view"])
@pytest.mark.parametrize("algorithm", ["kruskal", "prim", "boruvka"])
@pytest.mark.parametrize("fn", ["minimum_spanning_tree", "maximum_spanning_tree"])
def test_spanning_tree_matches_networkx_on_tied_weights(fn, algorithm, kind, seed):
    actual = getattr(fnx, fn)(_tied(fnx, kind, seed), algorithm=algorithm)
    expected = getattr(nx, fn)(_tied(nx, kind, seed), algorithm=algorithm)
    assert _tree_state(actual) == _tree_state(expected)


@needs_nx
@pytest.mark.parametrize("algorithm", ["prim", "boruvka"])
def test_maximum_prim_and_boruvka_do_not_round_trip_through_networkx(algorithm, monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("maximum_spanning_tree converted to networkx")

    monkeypatch.setattr(fnx, "_maximum_spanning_tree_via_parity", refuse)
    T = fnx.maximum_spanning_tree(_tied(fnx, "plain", 1), algorithm=algorithm)
    assert _tree_state(T) == _tree_state(
        nx.maximum_spanning_tree(_tied(nx, "plain", 1), algorithm=algorithm)
    )
