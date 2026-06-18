"""Differential parity for scalar graph metrics.

Covers ``s_metric`` (sum of degree products over edges),
``flow_hierarchy`` (fraction of edges not in a cycle), ``reciprocity``
(overall / single-node / node-iterable forms) and ``overall_reciprocity``.
None had a dedicated test file.

Locks fnx to upstream networkx across random graphs, hand-computed
goldens, and the isolated-node / empty-graph ``NetworkXError`` contracts.

br-r37-c1-ixuhi
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _connected(seed, directed=False, p=0.4):
    rng = random.Random(seed)
    n = rng.randint(5, 11)
    fnx_cls, nx_cls = (fnx.DiGraph, nx.DiGraph) if directed else (fnx.Graph, nx.Graph)
    p_cur = p
    for _ in range(60):
        fg = fnx_cls()
        ng = nx_cls()
        fg.add_nodes_from(range(n))
        ng.add_nodes_from(range(n))
        for u in range(n):
            for v in range(n):
                if u == v:
                    continue
                if (directed or u < v) and rng.random() < p_cur:
                    fg.add_edge(u, v)
                    ng.add_edge(u, v)
        connected = nx.is_strongly_connected(ng) if directed else nx.is_connected(ng)
        if connected:
            return fg, ng, n
        p_cur = min(0.9, p_cur + 0.05)
    return None


# ---------------------------------------------------------------------------
# Differential parity.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("seed", range(40))
def test_s_metric_matches_networkx(seed):
    pair = _connected(seed)
    if pair is None:
        pytest.skip("no connected graph")
    fg, ng, _ = pair
    assert fnx.s_metric(fg) == pytest.approx(nx.s_metric(ng))


@pytest.mark.parametrize("seed", range(40))
def test_flow_hierarchy_matches_networkx(seed):
    pair = _connected(seed, directed=True)
    if pair is None:
        pytest.skip("no strongly-connected digraph")
    fg, ng, _ = pair
    assert fnx.flow_hierarchy(fg) == pytest.approx(nx.flow_hierarchy(ng))


@pytest.mark.parametrize("seed", range(40))
def test_reciprocity_matches_networkx(seed):
    pair = _connected(seed, directed=True)
    if pair is None:
        pytest.skip("no strongly-connected digraph")
    fg, ng, n = pair
    # overall form
    assert fnx.reciprocity(fg) == pytest.approx(nx.reciprocity(ng))
    assert fnx.overall_reciprocity(fg) == pytest.approx(nx.overall_reciprocity(ng))
    # single-node form
    for node in range(n):
        assert fnx.reciprocity(fg, node) == pytest.approx(nx.reciprocity(ng, node))
    # node-iterable form -> dict
    fr = fnx.reciprocity(fg, list(range(n)))
    nr = nx.reciprocity(ng, list(range(n)))
    assert set(fr) == set(nr)
    for k in nr:
        assert fr[k] == pytest.approx(nr[k])


# ---------------------------------------------------------------------------
# Hand-computed goldens.
# ---------------------------------------------------------------------------


def test_s_metric_golden():
    # star_graph(3): center 0 (deg 3), leaves deg 1; 3 edges each 3*1 -> 9.
    assert fnx.s_metric(fnx.star_graph(3)) == 9
    # path 0-1-2: degrees 1,2,1; edges (0,1)=1*2 + (1,2)=2*1 = 4.
    assert fnx.s_metric(fnx.path_graph(3)) == 4


def test_reciprocity_golden():
    # 0<->1 reciprocal, 1->2 one-way: overall reciprocity = 2/3.
    g = fnx.DiGraph([(0, 1), (1, 0), (1, 2)])
    assert fnx.overall_reciprocity(g) == pytest.approx(2 / 3)


# ---------------------------------------------------------------------------
# Error contracts.
# ---------------------------------------------------------------------------


def test_reciprocity_isolated_node_raises_like_networkx():
    fg = fnx.DiGraph()
    fg.add_node(0)
    ng = nx.DiGraph()
    ng.add_node(0)
    with pytest.raises(nx.NetworkXError):
        fnx.reciprocity(fg, 0)
    with pytest.raises(nx.NetworkXError):
        nx.reciprocity(ng, 0)


def test_overall_reciprocity_empty_raises_like_networkx():
    with pytest.raises(nx.NetworkXError):
        fnx.overall_reciprocity(fnx.DiGraph())
    with pytest.raises(nx.NetworkXError):
        nx.overall_reciprocity(nx.DiGraph())
