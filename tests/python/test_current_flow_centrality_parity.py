"""Differential parity for current-flow (electrical) centralities.

Covers ``current_flow_closeness_centrality`` (== ``information_centrality``),
``current_flow_betweenness_centrality`` and
``edge_current_flow_betweenness_centrality``. None had a dedicated test
file. All require a connected undirected graph.

br-r37-c1-ckk8d
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _connected(seed, p=0.5):
    rng = random.Random(seed)
    n = rng.randint(5, 9)
    p_cur = p
    for _ in range(60):
        fg = fnx.Graph()
        ng = nx.Graph()
        fg.add_nodes_from(range(n))
        ng.add_nodes_from(range(n))
        for u in range(n):
            for v in range(u + 1, n):
                if rng.random() < p_cur:
                    fg.add_edge(u, v)
                    ng.add_edge(u, v)
        if nx.is_connected(ng):
            return fg, ng, n
        p_cur = min(0.9, p_cur + 0.05)
    return None


def _close_dict(a, b, tol=1e-6):
    assert set(a) == set(b)
    for k in b:
        assert a[k] == pytest.approx(b[k], abs=tol, rel=1e-6)


@pytest.mark.parametrize("fn", [
    "current_flow_closeness_centrality",
    "current_flow_betweenness_centrality",
])
@pytest.mark.parametrize("seed", range(25))
def test_node_current_flow_matches_networkx(fn, seed):
    pair = _connected(seed)
    if pair is None:
        pytest.skip("no connected graph")
    fg, ng, _ = pair
    _close_dict(getattr(fnx, fn)(fg), getattr(nx, fn)(ng))


@pytest.mark.parametrize("seed", range(25))
def test_edge_current_flow_betweenness_matches_networkx(seed):
    pair = _connected(seed)
    if pair is None:
        pytest.skip("no connected graph")
    fg, ng, _ = pair
    fe = {tuple(sorted(k)): v for k, v in
          fnx.edge_current_flow_betweenness_centrality(fg).items()}
    ne = {tuple(sorted(k)): v for k, v in
          nx.edge_current_flow_betweenness_centrality(ng).items()}
    _close_dict(fe, ne)


@pytest.mark.parametrize("seed", range(15))
def test_information_centrality_is_current_flow_closeness(seed):
    pair = _connected(seed)
    if pair is None:
        pytest.skip("no connected graph")
    fg, ng, _ = pair
    # information_centrality is an alias of current_flow_closeness_centrality.
    _close_dict(fnx.information_centrality(fg), fnx.current_flow_closeness_centrality(fg))
    _close_dict(fnx.information_centrality(fg), nx.information_centrality(ng))


def test_disconnected_raises_like_networkx():
    fg = fnx.Graph([(0, 1), (2, 3)])
    ng = nx.Graph([(0, 1), (2, 3)])
    with pytest.raises(nx.NetworkXError):
        fnx.current_flow_closeness_centrality(fg)
    with pytest.raises(nx.NetworkXError):
        nx.current_flow_closeness_centrality(ng)
