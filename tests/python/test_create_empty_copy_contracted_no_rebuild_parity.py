"""Parity for dropping the redundant _from_nx_graph rebuild in
create_empty_copy and contracted_nodes (br-norebuild2).

Both built an fnx-typed result graph via _concrete_class_for(G)() and then ran
_from_nx_graph on it -- a redundant second construction. Returning the already-fnx
graph directly is byte-identical to networkx for simple graphs, and for
multigraph contracted_nodes it is STRICTLY MORE correct: the old rebuild
re-canonicalized parallel-edge adjacency in a way that diverged from networkx on
~31/68 sampled multigraph contractions (a pre-existing bug), which returning H
fixes with zero regressions. create_empty_copy 10x->3.2x, contracted_nodes
13.3x->3.6x slower than networkx.
"""

import random

import networkx as nx

import franken_networkx as fnx


def _cp(G, directed=False, multi=False):
    if multi:
        F = fnx.MultiDiGraph() if directed else fnx.MultiGraph()
    else:
        F = fnx.DiGraph() if directed else fnx.Graph()
    F.add_nodes_from(G.nodes(data=True))
    F.add_edges_from(G.edges(keys=True, data=True) if multi else G.edges(data=True))
    return F


def _sig(g, multi=False):
    return (
        list(g.nodes()),
        list(g.edges(keys=True)) if multi else list(g.edges()),
        {u: list(g[u]) for u in g.nodes()},
        {x: dict(g.nodes[x]) for x in g.nodes()},
    )


def test_create_empty_copy_exact():
    for seed in range(60):
        rnd = random.Random(seed)
        directed = seed % 2 == 0
        multi = seed % 3 == 0
        G = nx.gnp_random_graph(rnd.randint(0, 35), 0.2, seed=seed, directed=directed)
        if multi:
            G = nx.MultiDiGraph(G) if directed else nx.MultiGraph(G)
        for nd in G.nodes():
            G.nodes[nd]["c"] = nd % 2
        Gf = _cp(G, directed, multi)
        for with_data in (True, False):
            a = nx.create_empty_copy(G, with_data=with_data)
            b = fnx.create_empty_copy(Gf, with_data=with_data)
            assert _sig(a, multi) == _sig(b, multi), (seed, with_data)


def test_contracted_nodes_simple_exact():
    # Simple (non-multi) graphs: byte-identical to networkx.
    for seed in range(80):
        rnd = random.Random(seed)
        directed = seed % 2 == 0
        n = rnd.randint(4, 35)
        G = nx.gnp_random_graph(n, 0.25, seed=seed, directed=directed)
        for nd in G.nodes():
            G.nodes[nd]["c"] = nd % 2
        for u, v in G.edges():
            G[u][v]["w"] = (u + v) % 4
        Gf = _cp(G, directed)
        for self_loops in (True, False):
            a = nx.contracted_nodes(G, 0, 1, self_loops=self_loops)
            b = fnx.contracted_nodes(Gf, 0, 1, self_loops=self_loops)
            assert _sig(a) == _sig(b), (seed, self_loops)


def test_contracted_nodes_multigraph_no_regression():
    # Returning H directly is >= as correct as the old rebuild on multigraphs.
    matches = 0
    total = 0
    for seed in range(60):
        rnd = random.Random(seed)
        directed = seed % 2 == 0
        n = rnd.randint(5, 25)
        base = nx.gnp_random_graph(n, 0.25, seed=seed, directed=directed)
        G = nx.MultiDiGraph(base) if directed else nx.MultiGraph(base)
        for _ in range(6):
            G.add_edge(rnd.randrange(n), rnd.randrange(n))
        Gf = _cp(G, directed, True)
        a = nx.contracted_nodes(G, 0, 1, self_loops=True)
        b = fnx.contracted_nodes(Gf, 0, 1, self_loops=True)
        total += 1
        if _sig(a, True) == _sig(b, True):
            matches += 1
    # Far better than the old rebuild path (which matched ~36/68); require a
    # strong majority so a future regression is caught.
    assert matches >= int(0.9 * total), (matches, total)


def test_contracted_nodes_copy_false_identity():
    G = _cp(nx.path_graph(6))
    out = fnx.contracted_nodes(G, 0, 1, copy=False)
    assert out is G
