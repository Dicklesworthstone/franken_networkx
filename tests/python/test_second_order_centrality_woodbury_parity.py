"""Parity for the O(n^3) Woodbury second_order_centrality weighted path.

br-socwoodbury: the weighted path (``weight=None``, a custom weight key, or a
graph carrying a ``weight`` attribute) solved ``(I - Q_j) x = 1`` for every
column ``j`` -- ``n`` dense O(n^3) solves, i.e. O(n^4) overall (catastrophic on
a weighted graph). Each system is a rank-2 update of the common non-singular
anchor ``A = I - Q_0`` (the absorbing fundamental matrix for sink node 0), so a
single shared LU plus a Sherman-Morrison-Woodbury correction per column gives
every column in O(n) extra work -- O(n^3) total. The per-column vectors are
reproduced to ~1e-11 and the centrality formula is unchanged, so values match
networkx to floating-point rounding; a non-finite fast-path entry falls back to
the exact per-column solves. The unweighted default still uses the Rust kernel.
"""

import math
import random

import networkx as nx

import franken_networkx as fnx


def _cp(Gx):
    Gf = fnx.Graph()
    Gf.add_nodes_from(Gx.nodes())
    Gf.add_edges_from(Gx.edges(data=True))
    return Gf


def _close(a, b, tol=1e-6):
    if set(a) != set(b):
        return False
    if list(a) != list(b):  # nx iterates in node-insertion order
        return False
    for k in a:
        av, bv = a[k], b[k]
        if math.isnan(av) and math.isnan(bv):
            continue
        if abs(av - bv) > tol:
            return False
    return True


def test_weighted_matches_networkx_random():
    for seed in range(40):
        rnd = random.Random(seed)
        n = rnd.randint(2, 45)
        Gx = nx.connected_watts_strogatz_graph(max(4, n), 4, 0.35, seed=seed)
        for u, v in Gx.edges():
            Gx[u][v]["weight"] = rnd.uniform(0.3, 6.0)
            Gx[u][v]["cost"] = rnd.uniform(1.0, 3.0)
        Gf = _cp(Gx)
        for weight in ("weight", "cost"):
            assert _close(
                nx.second_order_centrality(Gx, weight=weight),
                fnx.second_order_centrality(Gf, weight=weight),
            ), (seed, weight)


def test_custom_weight_key_uses_python_path():
    # A graph with a non-"weight" key forces the Woodbury path (the Rust
    # kernel is only taken for the unweighted default).
    Gx = nx.connected_watts_strogatz_graph(60, 6, 0.3, seed=7)
    rnd = random.Random(7)
    for u, v in Gx.edges():
        Gx[u][v]["w2"] = rnd.uniform(0.5, 5.0)
    Gf = _cp(Gx)
    assert _close(
        nx.second_order_centrality(Gx, weight="w2"),
        fnx.second_order_centrality(Gf, weight="w2"),
    )


def test_unweighted_default_still_matches():
    # Sanity: the Rust kernel path stays correct alongside the new helper.
    for seed in (1, 2, 3):
        Gx = nx.connected_watts_strogatz_graph(50, 6, 0.3, seed=seed)
        Gf = _cp(Gx)
        assert _close(
            nx.second_order_centrality(Gx),
            fnx.second_order_centrality(Gf),
        )


def test_larger_weighted_graph_parity():
    Gx = nx.connected_watts_strogatz_graph(150, 6, 0.3, seed=99)
    rnd = random.Random(99)
    for u, v in Gx.edges():
        Gx[u][v]["weight"] = rnd.uniform(0.5, 4.0)
    Gf = _cp(Gx)
    assert _close(
        nx.second_order_centrality(Gx, weight="weight"),
        fnx.second_order_centrality(Gf, weight="weight"),
    )


def test_single_node_returns_zero():
    G = fnx.Graph()
    G.add_node(0)
    assert fnx.second_order_centrality(G) == {0: 0.0}
    assert nx.second_order_centrality(G) == {0: 0.0}


def test_negative_weight_raises_networkxexception():
    G = fnx.Graph([(0, 1)])
    G[0][1]["weight"] = -1.0
    try:
        fnx.second_order_centrality(G, weight="weight")
    except nx.NetworkXException:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected NetworkXException for negative weight")


def test_disconnected_raises():
    G = fnx.Graph([(0, 1), (2, 3)])
    G[0][1]["weight"] = 1.0
    G[2][3]["weight"] = 1.0
    try:
        fnx.second_order_centrality(G, weight="weight")
    except nx.NetworkXException:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected NetworkXException for disconnected graph")


# br-r37-c1-vwh94: networkx runs on nx.DiGraph(G), which keeps ONE edge per pair
# whose dict is every parallel edge's data merged in key order - the last
# 'weight' wins, and an edge without one keeps the earlier value. Summing the
# parallel edges (or reading a missing weight as 1) gives other numbers.
_MULTI_BUNCHES = {
    "heavier_later": [
        (0, 1, {"weight": 1.0}), (1, 2, {"weight": 1.0}), (2, 0, {"weight": 2.0}),
        (0, 1, {"weight": 3.0}),
    ],
    "lighter_later": [
        (0, 1, {"weight": 3.0}), (1, 2, {"weight": 1.0}), (2, 0, {"weight": 2.0}),
        (0, 1, {"weight": 0.5}), (2, 3, {"weight": 1.5}),
    ],
    "weightless_parallel": [
        (0, 1, {"weight": 3.0, "cost": 1.0}), (1, 2, {"weight": 1.0, "cost": 2.0}),
        (2, 0, {"weight": 2.0, "cost": 1.0}), (0, 1, {"cost": 5.0}),
    ],
    "parallel_selfloops": [
        (0, 1, {"weight": 3.0}), (1, 2, {"weight": 1.0}), (2, 0, {"weight": 2.0}),
        (0, 1, {"weight": 0.5}), (1, 1, {"weight": 2.0}), (1, 1, {"weight": 1.0}),
    ],
}


def _multi_pair(bunch):
    Gf, Gx = fnx.MultiGraph(), nx.MultiGraph()
    Gf.add_edges_from(_MULTI_BUNCHES[bunch])
    Gx.add_edges_from(_MULTI_BUNCHES[bunch])
    return Gf, Gx


def test_multigraph_parallel_edges_merge_like_networkx_digraph():
    for bunch in sorted(_MULTI_BUNCHES):
        Gf, Gx = _multi_pair(bunch)
        for weight in ("weight", "cost", None):
            expected = nx.second_order_centrality(Gx, weight=weight)
            got = fnx.second_order_centrality(Gf, weight=weight)
            assert _close(expected, got, tol=1e-9), (bunch, weight, expected, got)


def test_balancing_replaces_an_existing_selfloop_weight_like_networkx():
    # nx balances node i with G.add_edge(i, i, weight=d_max - deg), which
    # REPLACES a selfloop's weight; adding to it gave other numbers even on a
    # simple Graph. Node 1 (loop 1.0, in-degree 2.5 < d_max 3.0) is balanced.
    edges = [(0, 1, {"weight": 0.5}), (1, 2, {"weight": 1.0}), (2, 0, {"weight": 2.0}), (1, 1, {"weight": 1.0})]
    Gf, Gx = fnx.Graph(edges), nx.Graph(edges)
    for weight in ("weight", None):
        expected = nx.second_order_centrality(Gx, weight=weight)
        got = fnx.second_order_centrality(Gf, weight=weight)
        assert _close(expected, got, tol=1e-9), (weight, expected, got)
