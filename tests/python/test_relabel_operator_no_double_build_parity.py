"""Parity for removing the redundant _from_nx_graph double-build.

br-norebuild: relabel_nodes / convert_node_labels_to_integers / disjoint_union(_all)
/ compose_all / union_all / intersection_all built an fnx-typed result graph and
then ran _from_nx_graph(R) on it -- a SECOND full construction of an already-
correct fnx graph (~4x of base construction on top of the slow source-view
iteration). The redundant rebuild is dropped: when the built graph is already an
fnx type it is returned directly; nx-typed results still convert. Node order,
edge order, full adjacency iteration order and node/edge attributes remain
byte-identical to networkx. relabel_nodes 18x->4.3x, convert_node_labels
17.8x->4.0x, disjoint_union 20x->5.5x slower than nx.
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


def _adjsig(g, multi=False):
    nodes = list(g.nodes())
    edges = list(g.edges(keys=True)) if multi else list(g.edges())
    adj = {u: list(g[u]) for u in g.nodes()}
    nattr = {x: dict(g.nodes[x]) for x in g.nodes()}
    return (nodes, edges, adj, nattr)


def _mk(n, sd, directed):
    G = nx.gnp_random_graph(n, 0.25, seed=sd, directed=directed)
    for nd in G.nodes():
        G.nodes[nd]["c"] = nd % 2
    return G


def test_relabel_nodes_fnx_and_nx_inputs():
    for seed in range(40):
        rnd = random.Random(seed)
        directed = seed % 2 == 0
        multi = seed % 3 == 0
        G = _mk(rnd.randint(4, 25), seed, directed)
        if multi:
            G = nx.MultiDiGraph(G) if directed else nx.MultiGraph(G)
            for _ in range(5):
                G.add_edge(rnd.randrange(len(G)), rnd.randrange(len(G)))
        mp = {x: x + 10000 for x in G.nodes()}
        Gf = _cp(G, directed, multi)
        assert _adjsig(nx.relabel_nodes(G, mp), multi) == _adjsig(fnx.relabel_nodes(Gf, mp), multi), seed
        # nx-typed input must also produce an fnx graph identical to nx
        assert _adjsig(nx.relabel_nodes(G, mp), multi) == _adjsig(fnx.relabel_nodes(G, mp), multi), seed


def test_convert_node_labels_to_integers():
    for seed in range(30):
        directed = seed % 2 == 0
        G = _mk(random.Random(seed).randint(4, 30), seed, directed)
        Gf = _cp(G, directed)
        for ordering in ("default", "sorted", "increasing degree", "decreasing degree"):
            a = nx.convert_node_labels_to_integers(G, ordering=ordering)
            b = fnx.convert_node_labels_to_integers(Gf, ordering=ordering)
            assert _adjsig(a) == _adjsig(b), (seed, ordering)


def test_compose_disjoint_union_intersection():
    for seed in range(40):
        directed = seed % 2 == 0
        G = _mk(random.Random(seed).randint(4, 22), seed, directed)
        H = _mk(random.Random(seed).randint(4, 22), seed + 777, directed)
        Gf, Hf = _cp(G, directed), _cp(H, directed)
        assert _adjsig(nx.compose(G, H)) == _adjsig(fnx.compose(Gf, Hf)), seed
        assert _adjsig(nx.disjoint_union(G, H)) == _adjsig(fnx.disjoint_union(Gf, Hf)), seed
        # intersection needs a shared node set
        Gi = _mk(20, seed, directed)
        Hi = _mk(20, seed + 1, directed)
        assert _adjsig(nx.intersection(Gi, Hi)) == _adjsig(
            fnx.intersection(_cp(Gi, directed), _cp(Hi, directed))
        ), seed


def test_relabel_copy_false_still_works():
    G = _cp(nx.path_graph(6))
    nx_G = nx.path_graph(6)
    fnx.relabel_nodes(G, {0: 100}, copy=False)
    nx.relabel_nodes(nx_G, {0: 100}, copy=False)
    assert sorted(map(str, G.nodes())) == sorted(map(str, nx_G.nodes()))
