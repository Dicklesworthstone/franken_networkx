"""Differential parity for pagerank's parameter combinations.

Default pagerank is covered elsewhere; this pins the complex knobs whose
semantics are easy to get subtly wrong: ``personalization``, ``dangling``,
``nstart``, ``weight``/``alpha`` and their combination.

br-r37-c1-ktky5
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _weighted_digraph(seed, p=0.4):
    rng = random.Random(seed)
    n = rng.randint(5, 9)
    fg = fnx.DiGraph()
    ng = nx.DiGraph()
    fg.add_nodes_from(range(n))
    ng.add_nodes_from(range(n))
    for u in range(n):
        for v in range(n):
            if u != v and rng.random() < p:
                w = rng.randint(1, 9)
                fg.add_edge(u, v, weight=w)
                ng.add_edge(u, v, weight=w)
    vec = {i: rng.random() + 0.1 for i in range(n)}
    return fg, ng, n, vec


def _close(a, b, tol=1e-6):
    assert set(a) == set(b)
    for k in b:
        assert a[k] == pytest.approx(b[k], abs=tol)


@pytest.mark.parametrize("seed", range(40))
def test_pagerank_personalization(seed):
    fg, ng, _, vec = _weighted_digraph(seed)
    _close(fnx.pagerank(fg, personalization=vec),
           nx.pagerank(ng, personalization=vec))


@pytest.mark.parametrize("seed", range(40))
def test_pagerank_dangling(seed):
    fg, ng, _, vec = _weighted_digraph(seed)
    _close(fnx.pagerank(fg, dangling=vec), nx.pagerank(ng, dangling=vec))


@pytest.mark.parametrize("seed", range(40))
def test_pagerank_nstart(seed):
    fg, ng, _, vec = _weighted_digraph(seed)
    _close(fnx.pagerank(fg, nstart=vec), nx.pagerank(ng, nstart=vec))


@pytest.mark.parametrize("alpha", [0.5, 0.7, 0.95])
@pytest.mark.parametrize("seed", range(15))
def test_pagerank_weight_and_alpha(alpha, seed):
    fg, ng, _, _ = _weighted_digraph(seed)
    _close(fnx.pagerank(fg, weight="weight", alpha=alpha),
           nx.pagerank(ng, weight="weight", alpha=alpha))


@pytest.mark.parametrize("seed", range(40))
def test_pagerank_combined_personalization_dangling_weight(seed):
    fg, ng, _, vec = _weighted_digraph(seed)
    dangling = {k: v + 0.05 for k, v in vec.items()}
    _close(
        fnx.pagerank(fg, personalization=vec, dangling=dangling, weight="weight"),
        nx.pagerank(ng, personalization=vec, dangling=dangling, weight="weight"),
    )
