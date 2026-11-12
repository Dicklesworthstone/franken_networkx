"""Parity for the conversion-free link-prediction path (br-r37-c1-lpconv).

jaccard_coefficient / adamic_adar_index / resource_allocation_index /
preferential_attachment delegated to networkx, which did a full fnx->nx graph
conversion (O(V+E)) on every call -- so a small ebunch on a large graph cost
thousands of times more than networkx. They now compute directly on the fnx graph
(no conversion) reproducing networkx's exact algorithm: nx's non_edges order,
common neighbours in G.neighbors(u) order, builtin sum (same compensated
summation), int 0 for empty scores.

This locks EXACT tuple-list equality (f == n), including the pair order, value
bits, and int/float types, across default + explicit ebunch on int / string /
self-loop graphs -- and that an explicit ebunch no longer materializes the graph.
"""

import random

import networkx as nx
import pytest

import franken_networkx as fnx

FUNCS = [
    "jaccard_coefficient",
    "adamic_adar_index",
    "resource_allocation_index",
    "preferential_attachment",
]


def _cp(G, multi=False, directed=False):
    if multi:
        F = fnx.MultiGraph()
    elif directed:
        F = fnx.DiGraph()
    else:
        F = fnx.Graph()
    F.add_nodes_from(G.nodes())
    F.add_edges_from(G.edges())
    return F


@pytest.mark.parametrize("name", FUNCS)
def test_exact_equality_default_ebunch(name):
    for seed in range(120):
        rnd = random.Random(seed)
        n = rnd.randint(4, 55)
        G = nx.gnp_random_graph(n, rnd.uniform(0.08, 0.5), seed=seed)
        if seed % 4 == 0:
            G = nx.relabel_nodes(G, {i: f"x{i}" for i in G})
        if seed % 5 == 0:
            for _ in range(rnd.randint(1, 2)):
                x = rnd.choice(list(G))
                G.add_edge(x, x)
        F = _cp(G)
        assert list(getattr(nx, name)(G)) == list(getattr(fnx, name)(F)), seed


@pytest.mark.parametrize("name", FUNCS)
def test_exact_equality_explicit_ebunch(name):
    for seed in range(80):
        rnd = random.Random(1000 + seed)
        n = rnd.randint(6, 50)
        G = nx.gnp_random_graph(n, rnd.uniform(0.1, 0.4), seed=seed)
        F = _cp(G)
        eb = [e for e in nx.non_edges(G)][:10]
        assert list(getattr(nx, name)(G, eb)) == list(getattr(fnx, name)(F, eb)), seed


def test_str_fixture_exact():
    g = nx.Graph()
    g.add_edges_from([("c", "d"), ("a", "b"), ("b", "c"), ("d", "e")])
    gf = _cp(g)
    for name in FUNCS:
        assert list(getattr(nx, name)(g)) == list(getattr(fnx, name)(gf)), name


def test_zero_scores_are_int_not_float():
    g = nx.Graph()
    g.add_edges_from([("c", "d"), ("a", "b"), ("b", "c"), ("d", "e")])
    gf = _cp(g)
    for name in ("adamic_adar_index", "resource_allocation_index"):
        for _u, _v, score in getattr(fnx, name)(gf):
            if score == 0:
                assert type(score) is int, (name, score)


def test_missing_ebunch_node_raises_node_not_found():
    F = _cp(nx.path_graph(5))
    for name in FUNCS:
        with pytest.raises(nx.NodeNotFound):
            list(getattr(fnx, name)(F, [(0, 99)]))


def test_directed_and_multigraph_raise():
    for name in FUNCS:
        with pytest.raises(nx.NetworkXNotImplemented):
            list(getattr(fnx, name)(_cp(nx.path_graph(4), directed=True)))
        with pytest.raises(nx.NetworkXNotImplemented):
            list(getattr(fnx, name)(_cp(nx.path_graph(4), multi=True)))


def test_explicit_ebunch_does_not_materialize_whole_graph():
    # A 2000-node graph scored on 5 pairs must be fast (no fnx->nx conversion).
    import time

    G = nx.gnp_random_graph(2000, 0.02, seed=1)
    F = _cp(G)
    eb = [e for e in nx.non_edges(G)][:5]
    fnx.resource_allocation_index(F, eb)  # warm
    t0 = time.perf_counter()
    list(fnx.resource_allocation_index(F, eb))
    dt = time.perf_counter() - t0
    assert dt < 0.01, f"explicit ebunch took {dt * 1000:.1f}ms (whole-graph cost?)"
