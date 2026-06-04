"""Parity for the one-shot-nx-view bipartite matching overrides (br-r37-c1-bipmatch).

fnx.bipartite re-exported networkx's matching functions verbatim, so calling them on
an fnx graph ran nx's algorithm over the fnx substrate (3-6x slower; Hopcroft-Karp /
Eppstein sweep the adjacency many times). They now convert once to a plain nx graph
(node + edge order preserved) and delegate, so the matching is byte-identical to
networkx while ~2-2.5x faster than before.
"""

import random

import networkx as nx
import networkx.algorithms.bipartite as nxb

import franken_networkx as fnx

FUNCS = ["hopcroft_karp_matching", "maximum_matching", "eppstein_matching"]


def _cp(G):
    F = fnx.Graph()
    F.add_nodes_from(G.nodes(data=True))
    F.add_edges_from(G.edges())
    return F


def test_matching_parity_top_and_none():
    for seed in range(200):
        rnd = random.Random(seed)
        a, b = rnd.randint(5, 45), rnd.randint(5, 45)
        g = nx.bipartite.random_graph(a, b, rnd.uniform(0.12, 0.5), seed=seed)
        top = [n for n, d in g.nodes(data=True) if d["bipartite"] == 0]
        f = _cp(g)
        for name in FUNCS:
            ffn = getattr(fnx.bipartite, name)
            nfn = getattr(nxb, name)
            for tn in (top, None):
                try:
                    expected = nfn(g, tn)
                    err = None
                except Exception as e:  # noqa: BLE001
                    expected, err = None, type(e)
                if err is not None:
                    try:
                        ffn(f, tn)
                    except err:
                        continue
                    raise AssertionError((name, seed, "expected", err))
                assert ffn(f, tn) == expected, (name, seed)


def test_nx_typed_input_passthrough():
    g = nx.bipartite.random_graph(20, 20, 0.2, seed=1)
    top = [n for n, d in g.nodes(data=True) if d["bipartite"] == 0]
    for name in FUNCS:
        assert getattr(fnx.bipartite, name)(g, top) == getattr(nxb, name)(g, top)


def test_string_node_labels():
    g = nx.bipartite.random_graph(15, 15, 0.25, seed=3)
    g = nx.relabel_nodes(g, {n: f"v{n}" for n in g})
    top = [n for n in g if int(n[1:]) < 15]
    f = _cp(g)
    assert fnx.bipartite.hopcroft_karp_matching(f, top) == nxb.hopcroft_karp_matching(
        g, top
    )
