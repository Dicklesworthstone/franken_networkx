"""node/edge_disjoint_paths parity with networkx: the paths, their order, and
the exception contract.

When s and t are disconnected, networkx's disjoint-path generators raise
``NetworkXNoPath`` on iteration; the Rust fast path used to yield an empty
generator instead (silent divergence). The degenerate ``s == t`` case for
``node_disjoint_paths`` (nx yields the cycles through s) was also wrong.

Found via the Menger disjoint-paths cross-check (the same metamorphic method
that surfaced the two P1 node_connectivity bugs). br-r37-c1-xn2ho

br-r37-c1-r6ce1: the native kernel used to find *a* maximum set of disjoint
paths over hash-set adjacency, so the paths - not just their order - moved
from run to run and differed from networkx's. It is now networkx's algorithm
step for step (auxiliary digraph, residual network, bidirectional-BFS
Edmonds-Karp, flow-dict rebuild), so every row here compares the whole list,
exceptions by type and args.
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
from networkx.exception import NetworkXNoPath
import franken_networkx as fnx


def _outcome(fn, *args):
    try:
        return ("ok", list(fn(*args)))
    except Exception as exc:  # noqa: BLE001 — exception parity is the point
        return ("err", type(exc).__name__, exc.args)


_PAIRS = [
    (fnx.node_disjoint_paths, nx.node_disjoint_paths),
    (fnx.edge_disjoint_paths, nx.edge_disjoint_paths),
]

_CLASSES = [
    (fnx.Graph, nx.Graph),
    (fnx.DiGraph, nx.DiGraph),
    (fnx.MultiGraph, nx.MultiGraph),
    (fnx.MultiDiGraph, nx.MultiDiGraph),
]


def _assert_same(G, NG, s, t):
    for ff, nf in _PAIRS:
        assert _outcome(ff, G, s, t) == _outcome(nf, NG, s, t), (
            nf.__name__, s, t, list(NG.edges()),
        )


def test_disconnected_raises_networkx_no_path():
    g = fnx.Graph([(0, 1), (2, 3)])
    with pytest.raises(NetworkXNoPath):
        list(fnx.node_disjoint_paths(g, 0, 3))
    with pytest.raises(NetworkXNoPath):
        list(fnx.edge_disjoint_paths(g, 0, 3))


def test_directed_disconnected_raises():
    d = fnx.DiGraph([(0, 1), (1, 0), (2, 3)])
    with pytest.raises(NetworkXNoPath):
        list(fnx.node_disjoint_paths(d, 0, 3))
    with pytest.raises(NetworkXNoPath):
        list(fnx.edge_disjoint_paths(d, 0, 3))


def test_node_disjoint_same_source_sink_matches_networkx():
    g = fnx.Graph([(0, 1), (1, 2)])
    ng = nx.Graph([(0, 1), (1, 2)])
    assert _outcome(fnx.node_disjoint_paths, g, 0, 0) == _outcome(
        nx.node_disjoint_paths, ng, 0, 0
    )


@pytest.mark.parametrize("fcls,ncls", _CLASSES)
def test_same_source_sink_and_self_loops_match_networkx(fcls, ncls):
    # s == t: node_disjoint_paths yields the cycles through s (each node
    # once); edge_disjoint_paths raises NetworkXNoPath for a node without
    # edges and "source and sink are the same node" otherwise - networkx's
    # order of checks, which fnx used to invert (it raised the same-node
    # error first, even for a node that is not in the graph).
    edges = [(0, 1), (1, 2), (2, 0), (2, 3), (3, 0)]
    G, NG = fcls(edges), ncls(edges)
    G.add_node(9)
    NG.add_node(9)
    for s in (0, 2, 9):
        _assert_same(G, NG, s, s)
    # A self-loop is one auxiliary arc: counted in the degrees that bound
    # the paths, dropped from the edge residual, a B -> A arc in the
    # node-split graph (so node_disjoint_paths(G, s, s) yields [s]).
    G.add_edge(0, 0)
    NG.add_edge(0, 0)
    for s, t in [(0, 0), (0, 2), (2, 0), (3, 3)]:
        _assert_same(G, NG, s, t)
    for ff, nf in _PAIRS:
        assert _outcome(ff, G, 7, 7) == _outcome(nf, NG, 7, 7)
        assert _outcome(ff, G, 0, 7) == _outcome(nf, NG, 0, 7)


@pytest.mark.parametrize("seed", range(70))
def test_paths_and_order_are_networkxs(seed):
    r = random.Random(seed)
    n = r.randint(5, 9)
    directed = r.random() < 0.5
    G = fnx.DiGraph() if directed else fnx.Graph()
    NG = nx.DiGraph() if directed else nx.Graph()
    G.add_nodes_from(range(n))
    NG.add_nodes_from(range(n))
    for u in range(n):
        for v in range(n):
            if u != v and (directed or u < v) and r.random() < 0.45:
                G.add_edge(u, v)
                NG.add_edge(u, v)
    for _ in range(3):
        s, t = r.sample(range(n), 2)
        _assert_same(G, NG, s, t)


@pytest.mark.parametrize("seed", range(12))
@pytest.mark.parametrize("fcls,ncls", _CLASSES)
def test_larger_graphs_every_class(seed, fcls, ncls):
    # Edges in a shuffled insertion order with string labels, parallel
    # edges on the multigraphs, self-loops, and nodes removed afterwards so
    # the storage slots no longer line up with node positions.
    r = random.Random(1000 + seed)
    n = r.randint(20, 45)
    labels = [f"v{r.randrange(10**6)}" for _ in range(n)]
    labels = list(dict.fromkeys(labels))
    edges = [
        (r.choice(labels), r.choice(labels))
        for _ in range(r.randint(2 * n, 5 * n))
    ]
    G, NG = fcls(), ncls()
    G.add_nodes_from(labels)
    NG.add_nodes_from(labels)
    G.add_edges_from(edges)
    NG.add_edges_from(edges)
    for node in r.sample(labels, 3):
        G.remove_node(node)
        NG.remove_node(node)
    nodes = list(NG)
    for _ in range(6):
        s, t = r.choice(nodes), r.choice(nodes)
        _assert_same(G, NG, s, t)


def test_mixed_label_types_keep_networkx_order():
    edges = [(0, "a"), ("a", 2.5), (2.5, (1, 2)), ((1, 2), 0), (0, 2.5),
             ("a", (1, 2)), (True, 0), (True, (1, 2))]
    for fcls, ncls in _CLASSES:
        G, NG = fcls(edges), ncls(edges)
        for s in NG:
            for t in NG:
                _assert_same(G, NG, s, t)
