"""Weight-argument handling parity across modes.

networkx accepts the ``weight`` argument in several forms — a string key, a
callable ``f(u, v, data)``, ``None`` (unit weights), a missing key (defaults to
1), and graphs where only some edges carry the attribute. Each is a distinct
code path that fnx must reproduce. This pins fnx == networkx across all of them.

No mocks: real fnx and real networkx on identically-built graphs.
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _weighted(seed, attr="weight"):
    r = random.Random(seed)
    n = r.randint(6, 9)
    fg = fnx.Graph(); fg.add_nodes_from(range(n))
    ng = nx.Graph(); ng.add_nodes_from(range(n))
    for u in range(n):
        for v in range(u + 1, n):
            if r.random() < 0.5:
                w = r.randint(1, 9)
                fg.add_edge(u, v, **{attr: w}, cost=w * 2)
                ng.add_edge(u, v, **{attr: w}, cost=w * 2)
    return fg, ng, n


@pytest.mark.parametrize("seed", range(30))
def test_callable_weight(seed):
    fg, ng, n = _weighted(seed)
    if not fnx.is_connected(fg):
        pytest.skip("disconnected")
    wf = lambda u, v, d: d.get("cost", 1)  # noqa: E731
    assert fnx.betweenness_centrality(fg, weight=wf) == (
        nx.betweenness_centrality(ng, weight=wf)
    )
    assert sorted(fnx.minimum_spanning_tree(fg, weight=wf).edges()) == (
        sorted(nx.minimum_spanning_tree(ng, weight=wf).edges())
    )
    r = random.Random(seed + 1)
    s, t = r.sample(range(n), 2)
    assert fnx.dijkstra_path_length(fg, s, t, weight=wf) == (
        nx.dijkstra_path_length(ng, s, t, weight=wf)
    )


@pytest.mark.parametrize("seed", range(30))
def test_weight_none_and_missing_key(seed):
    fg, ng, n = _weighted(seed)
    if not fnx.is_connected(fg):
        pytest.skip("disconnected")
    r = random.Random(seed + 2)
    s, t = r.sample(range(n), 2)
    # weight=None → unit weights (hop count).
    assert fnx.shortest_path_length(fg, s, t, weight=None) == (
        nx.shortest_path_length(ng, s, t, weight=None)
    )
    # Missing key → networkx defaults to 1 for every edge.
    assert fnx.dijkstra_path_length(fg, s, t, weight="absent") == (
        nx.dijkstra_path_length(ng, s, t, weight="absent")
    )


@pytest.mark.parametrize("seed", range(30))
def test_partial_weight_attribute(seed):
    """Only some edges carry 'weight'; networkx defaults the rest to 1."""
    r = random.Random(seed + 100)
    n = r.randint(6, 9)
    fg = fnx.Graph(); fg.add_nodes_from(range(n))
    ng = nx.Graph(); ng.add_nodes_from(range(n))
    for u in range(n):
        for v in range(u + 1, n):
            if r.random() < 0.5:
                if r.random() < 0.5:
                    w = r.randint(1, 9)
                    fg.add_edge(u, v, weight=w); ng.add_edge(u, v, weight=w)
                else:
                    fg.add_edge(u, v); ng.add_edge(u, v)
    if not fnx.is_connected(fg):
        pytest.skip("disconnected")
    assert dict(fnx.all_pairs_dijkstra_path_length(fg, weight="weight")) == (
        dict(nx.all_pairs_dijkstra_path_length(ng, weight="weight"))
    )
    assert dict(fg.degree(weight="weight")) == dict(ng.degree(weight="weight"))
