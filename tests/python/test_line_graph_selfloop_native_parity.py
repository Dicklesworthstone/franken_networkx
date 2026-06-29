"""Regression: line_graph() native fast path now handles self-loops.

br-r37-c1-lgself (cc): the native ``line_graph_fast`` kernel bailed (returned
None) on ANY self-loop, so a simple graph with even one self-loop fell to the slow
Python tuple-rebuild path (~0.65x nx). A self-loop ``(u, u)`` is an undirected edge
-> an L-node incident at u exactly once, paired with u's other incident edges (it
shares only endpoint u with them, so the kernel's no-dedup clique emission stays
correct); the directed kernel likewise reproduces nx's ``(u,u)->(u,w)`` L-edges
(including the L self-loop ``(u,u)->(u,u)``). These lock byte-parity with networkx
for self-loop inputs through the native path.

line_graph parity is order-insensitive (the L-node set + L-edge set, undirected
endpoints normalised), matching how the rest of the line_graph suite compares.
"""

import random

import networkx as nx
import pytest

import franken_networkx as fnx


def _sig(L):
    nodes = sorted(tuple(sorted(n)) if isinstance(n, tuple) else n for n in L.nodes())
    if L.is_directed():
        edges = sorted((a, b) for a, b in L.edges())
    else:
        edges = sorted(tuple(sorted((a, b))) for a, b in L.edges())
    return nodes, edges


@pytest.mark.parametrize("directed", [False, True])
def test_line_graph_with_selfloops_matches_networkx(directed):
    for seed in range(80):
        r = random.Random(seed)
        n = r.randint(1, 25)
        es = set()
        for _ in range(r.randint(0, 60)):
            u, v = r.randrange(n), r.randrange(n)
            es.add((u, v) if directed else tuple(sorted((u, v))))
        gf = (fnx.DiGraph if directed else fnx.Graph)()
        gx = (nx.DiGraph if directed else nx.Graph)()
        for g in (gf, gx):
            g.add_nodes_from(range(n))
            g.add_edges_from(es)
        assert _sig(fnx.line_graph(gf)) == _sig(nx.line_graph(gx)), (directed, seed)


def test_undirected_selfloop_explicit():
    gf, gx = fnx.Graph(), nx.Graph()
    for g in (gf, gx):
        g.add_edges_from([(0, 1), (1, 2), (2, 0), (0, 0), (1, 1)])
    Lf = fnx.line_graph(gf)
    assert _sig(Lf) == _sig(nx.line_graph(gx))
    # the self-loop edges become L-nodes
    assert (0, 0) in Lf.nodes()
    assert (1, 1) in Lf.nodes()


def test_directed_selfloop_creates_l_selfloop():
    gf, gx = fnx.DiGraph(), nx.DiGraph()
    for g in (gf, gx):
        g.add_edges_from([(0, 1), (1, 2), (0, 0)])
    Lf, Lx = fnx.line_graph(gf), nx.line_graph(gx)
    assert _sig(Lf) == _sig(Lx)
    # nx: directed self-loop (0,0) -> out-edges of head 0 include (0,0) and (0,1),
    # so L has (0,0)->(0,0) and (0,0)->(0,1).
    assert Lf.has_edge((0, 0), (0, 0))
    assert Lf.has_edge((0, 0), (0, 1))


def test_lone_selfloop_is_isolated_lnode():
    gf, gx = fnx.Graph(), nx.Graph()
    for g in (gf, gx):
        g.add_edge(3, 3)
    Lf = fnx.line_graph(gf)
    assert _sig(Lf) == _sig(nx.line_graph(gx))
    assert list(Lf.nodes()) == [(3, 3)]
    assert Lf.number_of_edges() == 0
