"""Differential + golden parity for single-set cuts metrics.

Covers ``volume`` (sum of node degrees in a set, weighted or not),
``node_expansion`` (|N(S)| / |S|) and ``boundary_expansion``
(|node_boundary(S)| / |S|). None had a dedicated test file.

Locks fnx to upstream networkx across random undirected and directed
graphs (weighted ``volume`` too), hand-computed goldens, and the
empty-set ``ZeroDivisionError`` contract.

br-r37-c1-gbgld
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _pair(seed, directed=False, weighted=False, p=0.4):
    rng = random.Random(seed)
    n = rng.randint(5, 11)
    fnx_cls, nx_cls = (fnx.DiGraph, nx.DiGraph) if directed else (fnx.Graph, nx.Graph)
    fg = fnx_cls()
    ng = nx_cls()
    fg.add_nodes_from(range(n))
    ng.add_nodes_from(range(n))
    for u in range(n):
        for v in range(n):
            if u == v:
                continue
            if (directed or u < v) and rng.random() < p:
                if weighted:
                    w = round(rng.uniform(1, 4), 2)
                    fg.add_edge(u, v, weight=w)
                    ng.add_edge(u, v, weight=w)
                else:
                    fg.add_edge(u, v)
                    ng.add_edge(u, v)
    return fg, ng, n


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("weighted", [False, True])
@pytest.mark.parametrize("seed", range(40))
def test_volume_matches_networkx(directed, weighted, seed):
    fg, ng, n = _pair(seed, directed=directed, weighted=weighted)
    rng = random.Random(seed * 13 + 1)
    s = set(rng.sample(range(n), rng.randint(1, n)))
    kwargs = {"weight": "weight"} if weighted else {}
    assert fnx.volume(fg, s, **kwargs) == pytest.approx(nx.volume(ng, s, **kwargs))


@pytest.mark.parametrize("fn", ["node_expansion", "boundary_expansion"])
@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("seed", range(40))
def test_expansion_matches_networkx(fn, directed, seed):
    fg, ng, n = _pair(seed, directed=directed)
    rng = random.Random(seed * 17 + 3)
    s = set(rng.sample(range(n), rng.randint(1, n)))
    assert getattr(fnx, fn)(fg, s) == pytest.approx(getattr(nx, fn)(ng, s))


def test_single_set_cuts_goldens():
    g = fnx.path_graph(4)  # 0-1-2-3, all degree 1 or 2
    assert fnx.volume(g, {1, 2}) == 4          # deg(1) + deg(2) = 2 + 2
    assert fnx.node_expansion(g, {1}) == pytest.approx(2.0)   # N({1})={0,2}
    assert fnx.boundary_expansion(g, {0, 1}) == pytest.approx(0.5)  # boundary {2}


def test_directed_volume_golden():
    # Directed volume uses out-degree.
    dg = fnx.DiGraph([(0, 1), (1, 2), (0, 2)])
    ndg = nx.DiGraph([(0, 1), (1, 2), (0, 2)])
    assert fnx.volume(dg, {0}) == 2
    assert fnx.volume(dg, {0}) == nx.volume(ndg, {0})


@pytest.mark.parametrize("fn", ["node_expansion", "boundary_expansion"])
def test_empty_set_raises_like_networkx(fn):
    g = fnx.path_graph(4)
    ng = nx.path_graph(4)
    with pytest.raises(ZeroDivisionError):
        getattr(fnx, fn)(g, set())
    with pytest.raises(ZeroDivisionError):
        getattr(nx, fn)(ng, set())
