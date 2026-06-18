"""Differential + golden parity for efficiency / reaching metrics.

Covers ``global_efficiency``, ``local_efficiency`` and
``global_reaching_centrality``. None had a dedicated test file.

Locks fnx to upstream networkx across random graphs (including
disconnected ones, where some pairs have infinite distance), hand-
computed goldens, and the directed ``NetworkXNotImplemented`` contract
for the efficiency functions.

br-r37-c1-xtiuz
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _pair(seed, p=0.4):
    rng = random.Random(seed)
    n = rng.randint(5, 11)
    fg = fnx.Graph()
    ng = nx.Graph()
    fg.add_nodes_from(range(n))
    ng.add_nodes_from(range(n))
    for u in range(n):
        for v in range(u + 1, n):
            if rng.random() < p:
                fg.add_edge(u, v)
                ng.add_edge(u, v)
    return fg, ng, n


# ---------------------------------------------------------------------------
# Differential parity (random graphs, possibly disconnected).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fn", ["global_efficiency", "local_efficiency"])
@pytest.mark.parametrize("seed", range(40))
def test_efficiency_matches_networkx(fn, seed):
    fg, ng, _ = _pair(seed)
    assert getattr(fnx, fn)(fg) == pytest.approx(getattr(nx, fn)(ng))


@pytest.mark.parametrize("seed", range(40))
def test_global_reaching_centrality_matches_networkx(seed):
    fg, ng, _ = _pair(seed)
    assert fnx.global_reaching_centrality(fg) == pytest.approx(
        nx.global_reaching_centrality(ng)
    )


# ---------------------------------------------------------------------------
# Hand-computed goldens.
# ---------------------------------------------------------------------------


def test_complete_graph_efficiency_is_one():
    k5 = fnx.complete_graph(5)
    assert fnx.global_efficiency(k5) == pytest.approx(1.0)
    assert fnx.local_efficiency(k5) == pytest.approx(1.0)


def test_path_graph_global_efficiency_golden():
    # P3 (0-1-2): pairs (0,1)=1, (1,2)=1, (0,2)=1/2 -> mean = (1+1+0.5)/3.
    p3 = fnx.path_graph(3)
    assert fnx.global_efficiency(p3) == pytest.approx((1 + 1 + 0.5) / 3)
    assert fnx.global_efficiency(p3) == pytest.approx(nx.global_efficiency(nx.path_graph(3)))


def test_trivial_graphs_efficiency_zero():
    for builder in (fnx.Graph(), _single_node()):
        assert fnx.global_efficiency(builder) == 0


def _single_node():
    g = fnx.Graph()
    g.add_node(0)
    return g


def test_disconnected_graph_matches_networkx():
    fg = fnx.Graph([(0, 1), (2, 3), (3, 4)])
    ng = nx.Graph([(0, 1), (2, 3), (3, 4)])
    assert fnx.global_efficiency(fg) == pytest.approx(nx.global_efficiency(ng))
    assert fnx.local_efficiency(fg) == pytest.approx(nx.local_efficiency(ng))


# ---------------------------------------------------------------------------
# Error contract.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fn", ["global_efficiency", "local_efficiency"])
def test_efficiency_rejects_directed_like_networkx(fn):
    with pytest.raises(nx.NetworkXNotImplemented):
        getattr(fnx, fn)(fnx.DiGraph([(0, 1)]))
    with pytest.raises(nx.NetworkXNotImplemented):
        getattr(nx, fn)(nx.DiGraph([(0, 1)]))
