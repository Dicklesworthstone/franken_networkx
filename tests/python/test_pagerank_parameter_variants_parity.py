"""Differential parity for pagerank's parameter combinations.

Default pagerank is covered elsewhere; this pins the complex knobs whose
semantics are easy to get subtly wrong: ``personalization``, ``dangling``,
``nstart``, ``weight``/``alpha`` and their combination.

br-r37-c1-ktky5
"""

from __future__ import annotations

import random

import franken_networkx as fnx
import networkx as nx
import pytest


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


@pytest.mark.parametrize("workers", [None, 1, 4])
@pytest.mark.parametrize("weight", [None, "weight"])
def test_pagerank_many_is_byte_identical_to_separate_networkx_calls(
    workers, weight
):
    fg, ng, n, _ = _weighted_digraph(917, p=0.55)
    rng = random.Random(1229)
    personalizations = [
        {node: rng.random() + 0.01 for node in rng.sample(range(n), 3)}
        for _ in range(8)
    ]

    actual = fnx.pagerank_many(
        fg,
        personalizations,
        alpha=0.9,
        max_iter=250,
        tol=1.0e-9,
        weight=weight,
        workers=workers,
    )
    expected = [
        nx.pagerank(
            ng,
            personalization=personalization,
            alpha=0.9,
            max_iter=250,
            tol=1.0e-9,
            weight=weight,
        )
        for personalization in personalizations
    ]
    assert actual == expected


def test_pagerank_many_preserves_query_order_and_degenerate_shapes():
    fg, ng, n, _ = _weighted_digraph(41)
    personalizations = [{node: 1.0} for node in range(n)]
    actual = fnx.pagerank_many(fg, personalizations, weight=None, workers=3)
    expected = [
        nx.pagerank(ng, personalization=p, weight=None)
        for p in personalizations
    ]
    assert actual == expected
    assert fnx.pagerank_many(fg, [], workers=3) == []
    assert fnx.pagerank_many(fnx.DiGraph(), [None, {}], workers=2) == [{}, {}]


def test_pagerank_many_rejects_zero_sum_personalization_and_bad_workers():
    graph = fnx.path_graph(4, create_using=fnx.DiGraph)
    with pytest.raises(ZeroDivisionError):
        fnx.pagerank_many(graph, [{0: 0.0}], workers=1)
    with pytest.raises(ValueError, match="workers must be greater than 0"):
        fnx.pagerank_many(graph, [{0: 1.0}], workers=0)
