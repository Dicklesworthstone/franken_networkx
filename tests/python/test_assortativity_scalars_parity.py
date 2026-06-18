"""Differential parity for order-invariant assortativity scalars.

Covers ``average_degree_connectivity``, ``average_neighbor_degree`` and
``degree_pearson_correlation_coefficient`` — all order-invariant
scalars/dicts (unlike ``degree_mixing_matrix``, which depends on
set-iteration order and is excluded). None had a dedicated test file.

br-r37-c1-3v25j
"""

from __future__ import annotations

import math
import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _pair(seed, directed=False, weighted=False, p=0.4):
    rng = random.Random(seed)
    n = rng.randint(6, 12)
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
    return fg, ng


def _dict_close(a, b, tol=1e-9):
    assert set(a) == set(b)
    for k in b:
        assert a[k] == pytest.approx(b[k], abs=tol)


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("weighted", [False, True])
@pytest.mark.parametrize("seed", range(25))
def test_average_degree_connectivity_matches_networkx(directed, weighted, seed):
    fg, ng = _pair(seed, directed=directed, weighted=weighted)
    kwargs = {"weight": "weight"} if weighted else {}
    _dict_close(
        fnx.average_degree_connectivity(fg, **kwargs),
        nx.average_degree_connectivity(ng, **kwargs),
    )


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("seed", range(25))
def test_average_neighbor_degree_matches_networkx(directed, seed):
    fg, ng = _pair(seed, directed=directed)
    _dict_close(fnx.average_neighbor_degree(fg), nx.average_neighbor_degree(ng))


@pytest.mark.parametrize("weighted", [False, True])
@pytest.mark.parametrize("seed", range(30))
def test_degree_pearson_correlation_matches_networkx(weighted, seed):
    fg, ng = _pair(seed, weighted=weighted)
    kwargs = {"weight": "weight"} if weighted else {}
    fr = fnx.degree_pearson_correlation_coefficient(fg, **kwargs)
    nr = nx.degree_pearson_correlation_coefficient(ng, **kwargs)
    if math.isnan(nr):
        assert math.isnan(fr)
    else:
        assert fr == pytest.approx(nr, abs=1e-7)


def test_average_degree_connectivity_golden():
    # Path 0-1-2-3: degree-1 nodes neighbour degree-2 nodes and vice versa.
    p4 = fnx.path_graph(4)
    assert fnx.average_degree_connectivity(p4) == {1: 2.0, 2: 1.5}
    assert fnx.average_degree_connectivity(p4) == nx.average_degree_connectivity(
        nx.path_graph(4)
    )


def test_directed_source_target_params_match_networkx():
    dg = fnx.DiGraph([(0, 1), (1, 2), (2, 0), (0, 2)])
    ndg = nx.DiGraph([(0, 1), (1, 2), (2, 0), (0, 2)])
    _dict_close(
        fnx.average_degree_connectivity(dg, source="in", target="out"),
        nx.average_degree_connectivity(ndg, source="in", target="out"),
    )
