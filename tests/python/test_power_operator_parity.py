"""Differential + metamorphic parity for the graph ``power`` operator.

``power(G, k)`` returns the k-th power of an undirected graph: the graph
on the same nodes with an edge ``(u, v)`` whenever ``G`` has a path of
length at most ``k`` (and at least 1) between ``u`` and ``v``.

It had no dedicated test file. This locks fnx against the real upstream
networkx with:

* a randomized differential sweep (edges match nx exactly), and
* metamorphic invariants that hold regardless of the reference:
  - ``G**1`` has exactly ``G``'s edges,
  - edge-set monotonicity ``E(G**k) ⊆ E(G**(k+1))``,
  - ``G**(n-1)`` is complete when ``G`` is connected (diameter ≤ n-1),
  - node attributes are dropped (matching nx), and
  - error contracts: ``k < 1`` raises ``ValueError`` and directed input
    raises ``NetworkXNotImplemented`` — in both libraries.

br-r37-c1-oubqy
"""

from __future__ import annotations

import random

import pytest
import networkx as nx

import franken_networkx as fnx


def _canon_edges(G):
    # Canonicalize each undirected edge to a sorted (str, str) tuple so the
    # outer sort uses a total order. (sorted() over frozensets would use the
    # subset partial-order and give input-order-dependent, unreliable results.)
    return sorted(tuple(sorted((str(u), str(v)))) for u, v in G.edges())


def _build_pair(seed, p=0.4):
    rng = random.Random(seed)
    n = rng.randint(4, 9)
    fg = fnx.Graph()
    ng = nx.Graph()
    fg.add_nodes_from(range(n))
    ng.add_nodes_from(range(n))
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if rng.random() < p]
    fg.add_edges_from(edges)
    ng.add_edges_from(edges)
    return fg, ng, n


# ---------------------------------------------------------------------------
# Differential sweep vs upstream networkx.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("seed", range(40))
@pytest.mark.parametrize("k", [1, 2, 3, 4])
def test_power_edges_match_networkx(seed, k):
    fg, ng, _ = _build_pair(seed)
    fr = fnx.power(fg, k)
    nr = nx.power(ng, k)
    assert sorted(map(str, fr.nodes())) == sorted(map(str, ng.nodes()))
    assert _canon_edges(fr) == _canon_edges(nr), (
        f"seed={seed} k={k}: fnx={_canon_edges(fr)} nx={_canon_edges(nr)}"
    )
    assert fr.is_directed() == nr.is_directed()
    assert fr.is_multigraph() == nr.is_multigraph()


@pytest.mark.parametrize("seed", range(15))
def test_power_structured_paths(seed):
    # Path graph P_n: P_n ** k connects nodes within distance k.
    rng = random.Random(seed)
    n = rng.randint(3, 8)
    fpath = fnx.path_graph(n)
    npath = nx.path_graph(n)
    for k in range(1, n):
        assert _canon_edges(fnx.power(fpath, k)) == _canon_edges(nx.power(npath, k))


# ---------------------------------------------------------------------------
# Metamorphic invariants.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("seed", range(30))
def test_power_one_is_identity_on_edges(seed):
    fg, _, _ = _build_pair(seed)
    assert _canon_edges(fnx.power(fg, 1)) == _canon_edges(fg)


@pytest.mark.parametrize("seed", range(30))
def test_power_edge_set_is_monotone_in_k(seed):
    fg, _, _ = _build_pair(seed)
    for k in (1, 2, 3, 4):
        lower = set(map(frozenset, fnx.power(fg, k).edges()))
        higher = set(map(frozenset, fnx.power(fg, k + 1).edges()))
        assert lower.issubset(higher), f"seed={seed} k={k}: E(G**k) ⊄ E(G**(k+1))"


@pytest.mark.parametrize("seed", range(30))
def test_power_diameter_makes_connected_graph_complete(seed):
    fg, ng, n = _build_pair(seed, p=0.55)
    if n < 2 or not nx.is_connected(ng):
        pytest.skip("needs a connected graph")
    powered = fnx.power(fg, n - 1)
    complete = fnx.complete_graph(n)
    assert _canon_edges(powered) == _canon_edges(complete)


def test_power_drops_node_attributes_like_networkx():
    fg = fnx.Graph()
    ng = nx.Graph()
    for G in (fg, ng):
        G.add_node(0, color="red", weight=3)
        G.add_node(1)
        G.add_edge(0, 1)
    fpow = fnx.power(fg, 2)
    npow = nx.power(ng, 2)
    assert dict(fpow.nodes(data=True)) == dict(npow.nodes(data=True))
    assert all(not data for _, data in fpow.nodes(data=True))


# ---------------------------------------------------------------------------
# Error contracts (must mirror networkx).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("k", [0, -1, -5])
def test_power_rejects_nonpositive_k_like_networkx(k):
    fg = fnx.path_graph(4)
    ng = nx.path_graph(4)
    with pytest.raises(ValueError):
        fnx.power(fg, k)
    with pytest.raises(ValueError):
        nx.power(ng, k)


@pytest.mark.parametrize(
    "fnx_cls,nx_cls",
    [(fnx.DiGraph, nx.DiGraph), (fnx.MultiDiGraph, nx.MultiDiGraph)],
)
def test_power_rejects_directed_like_networkx(fnx_cls, nx_cls):
    fg = fnx_cls([(0, 1), (1, 2)])
    ng = nx_cls([(0, 1), (1, 2)])
    with pytest.raises(nx.NetworkXNotImplemented):
        fnx.power(fg, 2)
    with pytest.raises(nx.NetworkXNotImplemented):
        nx.power(ng, 2)
