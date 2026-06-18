"""Differential parity for WEIGHTED centrality / path variants.

Weight handling (which keyword, how distances vs. influence weights are
interpreted, directed vs. undirected) is a recurring source of subtle
divergence. This pins fnx == networkx for the weighted forms across both
undirected and directed random graphs.

No mocks: real fnx and real networkx on identically-constructed weighted graphs.
"""

from __future__ import annotations

import math
import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _norm(x):
    if isinstance(x, dict):
        return {k: _norm(v) for k, v in x.items()}
    if isinstance(x, float):
        return round(x, 5) if math.isfinite(x) else repr(x)
    if isinstance(x, (list, tuple)):
        return type(x)(_norm(v) for v in x)
    return x


def _weighted_undirected(seed):
    r = random.Random(seed)
    n = r.randint(5, 9)
    g = fnx.Graph(); g.add_nodes_from(range(n))
    ng = nx.Graph(); ng.add_nodes_from(range(n))
    for u in range(n):
        for v in range(u + 1, n):
            if r.random() < 0.5:
                w = r.randint(1, 9)
                g.add_edge(u, v, weight=w)
                ng.add_edge(u, v, weight=w)
    return g, ng


def _weighted_directed(seed):
    r = random.Random(seed)
    n = r.randint(5, 9)
    g = fnx.DiGraph(); g.add_nodes_from(range(n))
    ng = nx.DiGraph(); ng.add_nodes_from(range(n))
    for u in range(n):
        for v in range(n):
            if u != v and r.random() < 0.4:
                w = r.randint(1, 9)
                g.add_edge(u, v, weight=w)
                ng.add_edge(u, v, weight=w)
    return g, ng


@pytest.mark.parametrize("seed", range(40))
def test_weighted_undirected_centralities_match(seed):
    g, ng = _weighted_undirected(seed)
    if not nx.is_connected(ng):
        pytest.skip("disconnected")
    assert _norm(fnx.betweenness_centrality(g, weight="weight")) == _norm(
        nx.betweenness_centrality(ng, weight="weight")
    )
    assert _norm(fnx.closeness_centrality(g, distance="weight")) == _norm(
        nx.closeness_centrality(ng, distance="weight")
    )
    assert _norm(fnx.pagerank(g, weight="weight")) == _norm(
        nx.pagerank(ng, weight="weight")
    )
    assert _norm(fnx.clustering(g, weight="weight")) == _norm(
        nx.clustering(ng, weight="weight")
    )
    assert _norm(fnx.average_shortest_path_length(g, weight="weight")) == _norm(
        nx.average_shortest_path_length(ng, weight="weight")
    )


@pytest.mark.parametrize("seed", range(50))
def test_weighted_directed_centralities_match(seed):
    g, ng = _weighted_directed(seed)
    assert _norm(fnx.pagerank(g, weight="weight")) == _norm(
        nx.pagerank(ng, weight="weight")
    )
    assert _norm(fnx.betweenness_centrality(g, weight="weight")) == _norm(
        nx.betweenness_centrality(ng, weight="weight")
    )
    assert _norm(dict(fnx.all_pairs_dijkstra_path_length(g, weight="weight"))) == (
        _norm(dict(nx.all_pairs_dijkstra_path_length(ng, weight="weight")))
    )
    assert round(fnx.overall_reciprocity(g), 5) == round(
        nx.overall_reciprocity(ng), 5
    )
