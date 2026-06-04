"""Parity for native bipartite density / degree_centrality overrides (br-r37-c1-bipdense).

fnx.bipartite re-exported networkx's @nx._dispatchable density / degree_centrality,
so calling them on an fnx graph paid ~4ms of dispatch overhead for trivial O(1)/O(V)
work (80-100x slower than networkx). They now compute networkx's exact formula
directly on the fnx graph -- byte-identical (values + dict key order) and far faster.
"""

import random

import networkx as nx
import networkx.algorithms.bipartite as nxb

import franken_networkx as fnx


def _cp(G):
    F = fnx.Graph()
    F.add_nodes_from(G.nodes(data=True))
    F.add_edges_from(G.edges())
    return F


def test_density_parity():
    for seed in range(250):
        rnd = random.Random(seed)
        a, b = rnd.randint(2, 45), rnd.randint(2, 45)
        g = nx.bipartite.random_graph(a, b, rnd.uniform(0.03, 0.55), seed=seed)
        if seed % 4 == 0:
            g = nx.relabel_nodes(g, {i: f"x{i}" for i in g})
        f = _cp(g)
        top = [n for n, d in g.nodes(data=True) if d["bipartite"] == 0]
        assert fnx.bipartite.density(f, top) == nxb.density(g, top), seed


def test_degree_centrality_parity_value_and_order():
    for seed in range(250):
        rnd = random.Random(seed)
        a, b = rnd.randint(2, 45), rnd.randint(2, 45)
        g = nx.bipartite.random_graph(a, b, rnd.uniform(0.03, 0.55), seed=seed)
        if seed % 4 == 0:
            g = nx.relabel_nodes(g, {i: f"x{i}" for i in g})
        f = _cp(g)
        top = [n for n, d in g.nodes(data=True) if d["bipartite"] == 0]
        a_dc = nxb.degree_centrality(g, top)
        b_dc = fnx.bipartite.degree_centrality(f, top)
        assert a_dc == b_dc and list(a_dc) == list(b_dc), seed


def test_directed_and_empty_and_nx_input():
    gd = nx.DiGraph([(0, 2), (1, 2), (0, 3)])
    fd = fnx.DiGraph()
    fd.add_nodes_from(gd.nodes())
    fd.add_edges_from(gd.edges())
    assert fnx.bipartite.density(fd, [0, 1]) == nxb.density(gd, [0, 1])
    ge = nx.Graph()
    ge.add_nodes_from([0, 1, 2, 3])
    assert fnx.bipartite.density(_cp(ge), [0, 1]) == nxb.density(ge, [0, 1]) == 0.0
    # nx-typed input passthrough
    g = nx.bipartite.random_graph(10, 10, 0.3, seed=1)
    top = [n for n, d in g.nodes(data=True) if d["bipartite"] == 0]
    assert fnx.bipartite.density(g, top) == nxb.density(g, top)
    assert fnx.bipartite.degree_centrality(g, top) == nxb.degree_centrality(g, top)
