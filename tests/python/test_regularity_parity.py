"""Differential + golden parity for regularity / distance-regularity.

Covers ``is_regular``, ``degree_histogram``, ``is_distance_regular`` and
``intersection_array``. None had a dedicated test file.

br-r37-c1-zrht0
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _pair(seed, directed=False, p=0.4):
    rng = random.Random(seed)
    n = rng.randint(4, 9)
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
                fg.add_edge(u, v)
                ng.add_edge(u, v)
    return fg, ng


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("seed", range(50))
def test_is_regular_and_degree_histogram_match_networkx(directed, seed):
    fg, ng = _pair(seed, directed=directed)
    assert fnx.is_regular(fg) == nx.is_regular(ng)
    assert fnx.degree_histogram(fg) == nx.degree_histogram(ng)


@pytest.mark.parametrize("k", [0, 2, 3])
@pytest.mark.parametrize("seed", range(30))
def test_is_k_regular_matches_networkx(k, seed):
    fg, ng = _pair(seed)
    assert fnx.is_k_regular(fg, k) == nx.is_k_regular(ng, k)


@pytest.mark.parametrize("builder", [
    lambda lib: lib.petersen_graph(),
    lambda lib: lib.cycle_graph(6),
    lambda lib: lib.complete_graph(5),
    lambda lib: lib.path_graph(5),
])
def test_distance_regularity_matches_networkx(builder):
    fg = builder(fnx)
    ng = builder(nx)
    assert fnx.is_distance_regular(fg) == nx.is_distance_regular(ng)
    if nx.is_distance_regular(ng):
        assert fnx.intersection_array(fg) == nx.intersection_array(ng)


def test_regularity_goldens():
    assert fnx.is_regular(fnx.complete_graph(4))       # 3-regular
    assert fnx.is_k_regular(fnx.cycle_graph(5), 2)
    assert not fnx.is_regular(fnx.path_graph(4))
    assert fnx.degree_histogram(fnx.complete_graph(4)) == [0, 0, 0, 4]


def test_intersection_array_non_distance_regular_raises_like_networkx():
    with pytest.raises(nx.NetworkXError):
        fnx.intersection_array(fnx.path_graph(5))
    with pytest.raises(nx.NetworkXError):
        nx.intersection_array(nx.path_graph(5))
