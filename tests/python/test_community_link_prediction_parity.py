"""Differential parity for community-based link prediction.

``cn_soundarajan_hopcroft``, ``ra_index_soundarajan_hopcroft`` and
``within_inter_cluster`` score node pairs using a ``community`` node
attribute. Each yields a lazy iterator of ``(u, v, score)`` triples.
None had a dedicated test file.

br-r37-c1-pyppi
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx

_FUNCS = [
    "cn_soundarajan_hopcroft",
    "ra_index_soundarajan_hopcroft",
    "within_inter_cluster",
]


def _community_pair(seed, p=0.4, communities=3):
    rng = random.Random(seed)
    n = rng.randint(6, 12)
    fg = fnx.Graph()
    ng = nx.Graph()
    fg.add_nodes_from(range(n))
    ng.add_nodes_from(range(n))
    for u in range(n):
        for v in range(u + 1, n):
            if rng.random() < p:
                fg.add_edge(u, v)
                ng.add_edge(u, v)
    for node in range(n):
        c = rng.randint(0, communities - 1)
        fg.nodes[node]["community"] = c
        ng.nodes[node]["community"] = c
    return fg, ng, n


def _materialize(it):
    return [(u, v, round(s, 9)) for u, v, s in it]


@pytest.mark.parametrize("fn", _FUNCS)
@pytest.mark.parametrize("seed", range(40))
def test_default_ebunch_matches_networkx(fn, seed):
    fg, ng, _ = _community_pair(seed)
    assert _materialize(getattr(fnx, fn)(fg)) == _materialize(getattr(nx, fn)(ng))


@pytest.mark.parametrize("fn", _FUNCS)
@pytest.mark.parametrize("seed", range(30))
def test_explicit_ebunch_matches_networkx(fn, seed):
    fg, ng, n = _community_pair(seed)
    rng = random.Random(seed * 5 + 1)
    pairs = [(u, v) for u in range(n) for v in range(u + 1, n)]
    rng.shuffle(pairs)
    ebunch = pairs[: min(5, len(pairs))]
    assert _materialize(getattr(fnx, fn)(fg, ebunch)) == _materialize(
        getattr(nx, fn)(ng, ebunch)
    )


def test_within_inter_cluster_cached_adjacency_delta_reference():
    fg = fnx.Graph()
    ng = nx.Graph()
    edges = [(0, 1), (0, 2), (0, 3), (1, 4), (2, 4), (3, 4)]
    fg.add_edges_from(edges)
    ng.add_edges_from(edges)
    communities = {0: 0, 1: 1, 2: 0, 3: 0, 4: 0}
    for node, value in communities.items():
        fg.nodes[node]["community"] = value
        ng.nodes[node]["community"] = value

    ebunch = [(0, 4), (1, 2)]
    assert _materialize(fnx.within_inter_cluster(fg, ebunch, delta=0.5)) == _materialize(
        nx.within_inter_cluster(ng, ebunch, delta=0.5)
    )


@pytest.mark.parametrize("fn", _FUNCS)
def test_returns_lazy_iterator(fn):
    fg, _, _ = _community_pair(0)
    it = getattr(fnx, fn)(fg)
    assert iter(it) is iter(it)
    assert not isinstance(it, list)


@pytest.mark.parametrize("fn", _FUNCS)
def test_missing_community_raises_like_networkx(fn):
    fg = fnx.Graph([(0, 1), (1, 2)])
    ng = nx.Graph([(0, 1), (1, 2)])
    with pytest.raises(nx.NetworkXAlgorithmError):
        list(getattr(fnx, fn)(fg))
    with pytest.raises(nx.NetworkXAlgorithmError):
        list(getattr(nx, fn)(ng))
