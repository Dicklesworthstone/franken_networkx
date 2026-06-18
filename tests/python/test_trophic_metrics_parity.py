"""Differential + golden parity for trophic (food-web) metrics.

Covers ``trophic_differences`` (per-edge difference of trophic levels)
and ``trophic_incoherence_parameter`` (std of those differences).
Neither had a dedicated test file. Both require a directed graph with at
least one basal node (in-degree 0).

br-r37-c1-2o891
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _dag_with_basal(seed):
    rng = random.Random(seed)
    n = rng.randint(5, 9)
    fg = fnx.DiGraph()
    ng = nx.DiGraph()
    fg.add_nodes_from(range(n))
    ng.add_nodes_from(range(n))
    # Spanning forest oriented low->high guarantees node 0 is basal and the
    # graph is acyclic with a defined trophic structure.
    for v in range(1, n):
        u = rng.randint(0, v - 1)
        fg.add_edge(u, v)
        ng.add_edge(u, v)
    for _ in range(rng.randint(0, n)):
        u = rng.randint(0, n - 1)
        v = rng.randint(0, n - 1)
        if u < v:
            fg.add_edge(u, v)
            ng.add_edge(u, v)
    return fg, ng, n


@pytest.mark.parametrize("seed", range(40))
def test_trophic_differences_matches_networkx(seed):
    fg, ng, _ = _dag_with_basal(seed)
    fr = fnx.trophic_differences(fg)
    nr = nx.trophic_differences(ng)
    assert set(fr) == set(nr)
    for edge in nr:
        assert fr[edge] == pytest.approx(nr[edge], abs=1e-9)


@pytest.mark.parametrize("seed", range(40))
def test_trophic_incoherence_parameter_matches_networkx(seed):
    fg, ng, _ = _dag_with_basal(seed)
    assert fnx.trophic_incoherence_parameter(fg) == pytest.approx(
        nx.trophic_incoherence_parameter(ng), abs=1e-9
    )


def test_chain_goldens():
    # 0->1->2->3: trophic levels 1,2,3,4; every edge difference is 1, so the
    # incoherence parameter (std of differences) is 0.
    g = fnx.DiGraph([(0, 1), (1, 2), (2, 3)])
    ng = nx.DiGraph([(0, 1), (1, 2), (2, 3)])
    assert all(d == pytest.approx(1.0) for d in fnx.trophic_differences(g).values())
    assert fnx.trophic_incoherence_parameter(g) == pytest.approx(0.0)
    assert fnx.trophic_differences(g) == nx.trophic_differences(ng)


def test_no_basal_node_raises_like_networkx():
    fg = fnx.DiGraph([(0, 1), (1, 0)])  # cycle, no basal node
    ng = nx.DiGraph([(0, 1), (1, 0)])
    with pytest.raises(nx.NetworkXError):
        fnx.trophic_levels(fg)
    with pytest.raises(nx.NetworkXError):
        nx.trophic_levels(ng)
