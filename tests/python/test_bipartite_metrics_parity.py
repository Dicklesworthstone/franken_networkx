"""Differential parity for bipartite-specific metrics.

Covers ``node_redundancy``, ``clustering`` (Latapy),
``robins_alexander_clustering`` and ``minimum_weight_full_matching`` from
``networkx.algorithms.bipartite``. None had a dedicated test file.

br-r37-c1-ahnrn
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx
from franken_networkx.algorithms import bipartite as fnx_bip
from networkx.algorithms import bipartite as nx_bip


def _bipartite_pair(seed, p=0.5):
    rng = random.Random(seed)
    a = rng.randint(3, 5)
    b = rng.randint(3, 5)
    fg = fnx.Graph()
    ng = nx.Graph()
    top = list(range(a))
    bot = list(range(a, a + b))
    for g in (fg, ng):
        g.add_nodes_from(top, bipartite=0)
        g.add_nodes_from(bot, bipartite=1)
    for u in top:
        for v in bot:
            if rng.random() < p:
                fg.add_edge(u, v)
                ng.add_edge(u, v)
    return fg, ng


def _dict_close(a, b, tol=1e-9):
    assert set(a) == set(b)
    for k in b:
        assert a[k] == pytest.approx(b[k], abs=tol)


@pytest.mark.parametrize("seed", range(40))
def test_latapy_clustering_matches_networkx(seed):
    fg, ng = _bipartite_pair(seed)
    _dict_close(fnx_bip.clustering(fg), nx_bip.clustering(ng))


@pytest.mark.parametrize("seed", range(40))
def test_robins_alexander_clustering_matches_networkx(seed):
    fg, ng = _bipartite_pair(seed)
    assert fnx_bip.robins_alexander_clustering(fg) == pytest.approx(
        nx_bip.robins_alexander_clustering(ng), abs=1e-9
    )


@pytest.mark.parametrize("seed", range(40))
def test_node_redundancy_matches_networkx(seed):
    fg, ng = _bipartite_pair(seed)
    if any(d < 2 for _, d in ng.degree()):
        pytest.skip("node_redundancy requires every node degree >= 2")
    _dict_close(fnx_bip.node_redundancy(fg), nx_bip.node_redundancy(ng))


@pytest.mark.parametrize("seed", range(30))
def test_minimum_weight_full_matching_total_weight_matches_networkx(seed):
    rng = random.Random(seed + 7)
    k = rng.randint(2, 4)
    fg = fnx.Graph()
    ng = nx.Graph()
    for u in range(k):
        fg.add_node(u, bipartite=0)
        ng.add_node(u, bipartite=0)
    for v in range(k, 2 * k):
        fg.add_node(v, bipartite=1)
        ng.add_node(v, bipartite=1)
    for u in range(k):
        for v in range(k, 2 * k):
            w = rng.randint(1, 9)
            fg.add_edge(u, v, weight=w)
            ng.add_edge(u, v, weight=w)
    fmm = fnx_bip.minimum_weight_full_matching(fg)
    nmm = nx_bip.minimum_weight_full_matching(ng)
    fw = sum(fg[u][v]["weight"] for u, v in fmm.items() if u < v)
    nw = sum(ng[u][v]["weight"] for u, v in nmm.items() if u < v)
    assert fw == nw


def test_complete_bipartite_goldens():
    g = fnx.complete_bipartite_graph(2, 2)
    ng = nx.complete_bipartite_graph(2, 2)
    # K_{2,2} is a 4-cycle: robins-alexander clustering is 1.0.
    assert fnx_bip.robins_alexander_clustering(g) == pytest.approx(1.0)
    _dict_close(fnx_bip.clustering(g), nx_bip.clustering(ng))
