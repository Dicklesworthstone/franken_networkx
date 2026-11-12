"""Parity for the lazily-memoized Soundarajan-Hopcroft link predictors (br-r37-c1-shlazy).

cn_soundarajan_hopcroft / ra_index_soundarajan_hopcroft snapshotted the whole
adjacency on every call -- the whole-graph cost for any ebunch, ~340-500x slower
than networkx on a small ebunch. They now lazily memoize neighbour sets / degrees /
community values (small ebunch touches only its endpoints), and ra sums common
neighbours in G.neighbors(u) order with the builtin sum so it is byte-exact with
networkx (up from ~72%).
"""

import random

import networkx as nx
import pytest

import franken_networkx as fnx

FUNCS = ["cn_soundarajan_hopcroft", "ra_index_soundarajan_hopcroft"]


def _cp(G):
    F = fnx.Graph()
    F.add_nodes_from(G.nodes())
    F.add_edges_from(G.edges())
    for n in G:
        F.nodes[n]["community"] = G.nodes[n]["community"]
    return F


@pytest.mark.parametrize("name", FUNCS)
def test_exact_equality(name):
    for seed in range(150):
        rnd = random.Random(seed)
        n = rnd.randint(4, 55)
        G = nx.gnp_random_graph(n, rnd.uniform(0.08, 0.5), seed=seed)
        if seed % 4 == 0:
            G = nx.relabel_nodes(G, {i: f"x{i}" for i in G})
        if seed % 6 == 0:
            for _ in range(rnd.randint(1, 2)):
                x = rnd.choice(list(G))
                G.add_edge(x, x)
        for nd in G:
            G.nodes[nd]["community"] = rnd.randint(0, 2)
        F = _cp(G)
        assert list(getattr(nx, name)(G)) == list(getattr(fnx, name)(F)), seed
        eb = [e for e in nx.non_edges(G)][:8]
        assert list(getattr(nx, name)(G, eb)) == list(getattr(fnx, name)(F, eb)), seed


@pytest.mark.parametrize("name", FUNCS)
def test_missing_community_raises(name):
    G = nx.path_graph(5)  # no community attribute
    F = fnx.Graph()
    F.add_nodes_from(G.nodes())
    F.add_edges_from(G.edges())
    with pytest.raises(nx.NetworkXAlgorithmError):
        list(getattr(fnx, name)(F, [(0, 4)]))


@pytest.mark.parametrize("name", FUNCS)
def test_directed_multigraph_raise(name):
    for ctor in (fnx.DiGraph, fnx.MultiGraph):
        F = ctor()
        F.add_edges_from([(0, 1), (1, 2)])
        with pytest.raises(nx.NetworkXNotImplemented):
            list(getattr(fnx, name)(F))


def test_explicit_ebunch_does_not_materialize_whole_graph():
    import time

    G = nx.gnp_random_graph(2000, 0.02, seed=1)
    for i, nd in enumerate(G):
        G.nodes[nd]["community"] = i % 2
    F = _cp(G)
    eb = [e for e in nx.non_edges(G)][:5]
    list(fnx.ra_index_soundarajan_hopcroft(F, eb))  # warm
    t0 = time.perf_counter()
    list(fnx.ra_index_soundarajan_hopcroft(F, eb))
    assert time.perf_counter() - t0 < 0.01
