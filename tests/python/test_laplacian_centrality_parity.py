"""Differential + golden parity for ``laplacian_centrality``.

The drop in Laplacian energy when a node is removed, optionally weighted
and normalized. No dedicated test file existed.

Locks fnx to upstream networkx across random connected undirected and
directed graphs (weighted / normalized / unweighted), a symmetric
golden, and the no-edge ``ZeroDivisionError`` contract.

br-r37-c1-2csye
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _connected(seed, directed=False, weighted=False, p=0.45):
    rng = random.Random(seed)
    n = rng.randint(5, 10)
    fnx_cls, nx_cls = (fnx.DiGraph, nx.DiGraph) if directed else (fnx.Graph, nx.Graph)
    p_cur = p
    for _ in range(60):
        fg = fnx_cls()
        ng = nx_cls()
        fg.add_nodes_from(range(n))
        ng.add_nodes_from(range(n))
        for u in range(n):
            for v in range(n):
                if u == v:
                    continue
                if (directed or u < v) and rng.random() < p_cur:
                    if weighted:
                        w = round(rng.uniform(1, 4), 2)
                        fg.add_edge(u, v, weight=w)
                        ng.add_edge(u, v, weight=w)
                    else:
                        fg.add_edge(u, v)
                        ng.add_edge(u, v)
        ok = nx.is_strongly_connected(ng) if directed else nx.is_connected(ng)
        if ok:
            return fg, ng, n
        p_cur = min(0.9, p_cur + 0.05)
    return None


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("weighted", [False, True])
@pytest.mark.parametrize("normalized", [True, False])
@pytest.mark.parametrize("seed", range(20))
def test_laplacian_centrality_matches_networkx(directed, weighted, normalized, seed):
    pair = _connected(seed, directed=directed, weighted=weighted)
    if pair is None:
        pytest.skip("no connected graph")
    fg, ng, _ = pair
    kwargs = {"normalized": normalized, "weight": "weight" if weighted else None}
    fr = fnx.laplacian_centrality(fg, **kwargs)
    nr = nx.laplacian_centrality(ng, **kwargs)
    assert set(fr) == set(nr)
    for k in nr:
        assert fr[k] == pytest.approx(nr[k], abs=1e-9)


def test_complete_graph_symmetric_golden():
    k3 = fnx.complete_graph(3)
    result = fnx.laplacian_centrality(k3)
    # By symmetry every node has the same Laplacian centrality.
    assert len(set(round(v, 12) for v in result.values())) == 1
    assert result == nx.laplacian_centrality(nx.complete_graph(3))


def test_no_edge_graph_raises_like_networkx():
    with pytest.raises(ZeroDivisionError):
        fnx.laplacian_centrality(fnx.empty_graph(3))
    with pytest.raises(ZeroDivisionError):
        nx.laplacian_centrality(nx.empty_graph(3))


@pytest.mark.parametrize("cls", ["Graph", "MultiGraph"])
@pytest.mark.parametrize("normalized", [True, False])
@pytest.mark.parametrize("seed", range(15))
def test_negative_weighted_degree_matches_networkx(cls, normalized, seed):
    # br-r37-c1-p1uop: the vectorised closed form used diag**2 where networkx's
    # delete-and-re-sum loop gives diag*|diag|; they differ only for a node whose
    # weighted degree is negative. (Directed graphs are left out: a random walk
    # over negative weights has no well-defined stationary distribution, and
    # directed_laplacian_matrix itself is not stable there in networkx.)
    rng = random.Random(seed)
    n = rng.randint(4, 9)
    fg, ng = getattr(fnx, cls)(), getattr(nx, cls)()
    for graph in (fg, ng):
        graph.add_nodes_from(range(n))
    for _ in range(2 * n):
        u, v = rng.sample(range(n), 2)
        w = rng.choice([rng.randint(-8, 8), rng.uniform(-3, 5)])
        fg.add_edge(u, v, weight=w)
        ng.add_edge(u, v, weight=w)
    for nodelist in (None, [0, 1]):
        try:
            expected = nx.laplacian_centrality(ng, normalized=normalized, nodelist=nodelist)
        except ZeroDivisionError:
            with pytest.raises(ZeroDivisionError):
                fnx.laplacian_centrality(fg, normalized=normalized, nodelist=nodelist)
            continue
        actual = fnx.laplacian_centrality(fg, normalized=normalized, nodelist=nodelist)
        assert actual.keys() == expected.keys()
        for node, value in expected.items():
            assert actual[node] == pytest.approx(value, rel=1e-9, abs=1e-12), node
