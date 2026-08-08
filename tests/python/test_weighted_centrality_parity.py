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


# br-r37-c1-mfqlz: this module is "weighted centrality/PATH differential parity"
# and the only path function used was all_pairs_dijkstra_path_LENGTH. A weighted
# tie-break divergence hides precisely there: two routes of equal total weight
# leave every length identical while the chosen route differs, so a
# length-only comparison cannot see it. The weighted path differs from the
# unweighted one on 12 of 36 connected seeds, so this arm reaches real work.
@pytest.mark.parametrize("seed", range(40))
def test_weighted_undirected_paths_match(seed):
    g, ng = _weighted_undirected(seed)
    if not nx.is_connected(ng):
        pytest.skip("disconnected")
    n = g.number_of_nodes()
    r = random.Random(seed + 9)
    s, t = r.sample(range(n), 2)
    assert fnx.dijkstra_path(g, s, t, weight="weight") == (
        nx.dijkstra_path(ng, s, t, weight="weight")
    )
    assert _norm({k: dict(v) for k, v in fnx.all_pairs_dijkstra_path(g, weight="weight")}) == (
        _norm({k: dict(v) for k, v in nx.all_pairs_dijkstra_path(ng, weight="weight")})
    )


@pytest.mark.parametrize("seed", range(50))
def test_weighted_directed_paths_match(seed):
    g, ng = _weighted_directed(seed)
    assert _norm({k: dict(v) for k, v in fnx.all_pairs_dijkstra_path(g, weight="weight")}) == (
        _norm({k: dict(v) for k, v in nx.all_pairs_dijkstra_path(ng, weight="weight")})
    )


# br-r37-c1-mfqlz: `_norm` returns dicts, and dict equality ignores insertion
# order — so every assertion above is blind to the ORDER of the returned
# node->value map, which is observable. Verified equal for all of these across
# their seeds before being asserted.
@pytest.mark.parametrize("seed", range(40))
def test_weighted_result_key_order_parity(seed):
    g, ng = _weighted_undirected(seed)
    if not nx.is_connected(ng):
        pytest.skip("disconnected")
    for call in (
        lambda L, G: L.betweenness_centrality(G, weight="weight"),
        lambda L, G: L.closeness_centrality(G, distance="weight"),
        lambda L, G: L.pagerank(G, weight="weight"),
        lambda L, G: L.clustering(G, weight="weight"),
    ):
        assert list(call(fnx, g).keys()) == list(call(nx, ng).keys())


@pytest.mark.parametrize("seed", range(50))
def test_weighted_directed_result_key_order_parity(seed):
    g, ng = _weighted_directed(seed)
    for call in (
        lambda L, G: L.pagerank(G, weight="weight"),
        lambda L, G: L.betweenness_centrality(G, weight="weight"),
        lambda L, G: dict(L.all_pairs_dijkstra_path_length(G, weight="weight")),
    ):
        assert list(call(fnx, g).keys()) == list(call(nx, ng).keys())
