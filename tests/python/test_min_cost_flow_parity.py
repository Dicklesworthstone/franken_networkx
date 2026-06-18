"""Differential + golden parity for the min-cost-flow family.

Covers ``min_cost_flow_cost`` (and ``min_cost_flow``), ``network_simplex``
and ``max_flow_min_cost``. None had a dedicated test file. Graphs are
built from a single shared spec so fnx and nx see identical networks.

br-r37-c1-b9nfx
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _demand_spec(seed):
    rng = random.Random(seed)
    n = rng.randint(4, 7)
    demand = [0] * n
    amount = rng.randint(1, 5)
    demand[0] = -amount
    demand[n - 1] = amount
    edges = [
        (u, v, rng.randint(1, 9), rng.randint(3, 10))
        for u in range(n)
        for v in range(n)
        if u != v and rng.random() < 0.5
    ]
    return n, demand, edges


def _build_demand(spec, lib):
    n, demand, edges = spec
    g = lib.DiGraph()
    for i in range(n):
        g.add_node(i, demand=demand[i])
    for u, v, w, c in edges:
        g.add_edge(u, v, weight=w, capacity=c)
    return g


def _flow_spec(seed):
    rng = random.Random(seed)
    n = rng.randint(4, 7)
    edges = [
        (u, v, rng.randint(1, 5), rng.randint(1, 8))
        for u in range(n)
        for v in range(n)
        if u != v and rng.random() < 0.5
    ]
    return n, edges


def _build_flow(spec, lib):
    n, edges = spec
    g = lib.DiGraph()
    g.add_nodes_from(range(n))
    for u, v, w, c in edges:
        g.add_edge(u, v, weight=w, capacity=c)
    return g


@pytest.mark.parametrize("seed", range(60))
def test_min_cost_flow_cost_matches_networkx(seed):
    spec = _demand_spec(seed)
    fg = _build_demand(spec, fnx)
    ng = _build_demand(spec, nx)
    try:
        nc = nx.min_cost_flow_cost(ng)
    except nx.NetworkXUnfeasible:
        with pytest.raises(nx.NetworkXUnfeasible):
            fnx.min_cost_flow_cost(fg)
        return
    assert fnx.min_cost_flow_cost(fg) == nc
    # network_simplex returns the same optimal cost.
    assert fnx.network_simplex(fg)[0] == nx.network_simplex(ng)[0]


@pytest.mark.parametrize("seed", range(60))
def test_max_flow_min_cost_matches_networkx(seed):
    spec = _flow_spec(seed)
    fg = _build_flow(spec, fnx)
    ng = _build_flow(spec, nx)
    n = spec[0]
    ff = fnx.max_flow_min_cost(fg, 0, n - 1)
    nf = nx.max_flow_min_cost(ng, 0, n - 1)
    # Flow dicts may differ; the optimal cost is the invariant.
    assert fnx.cost_of_flow(fg, ff) == nx.cost_of_flow(ng, nf)


def test_min_cost_flow_golden():
    spec_edges = [(0, 1, 2, 10), (1, 2, 3, 10)]
    fg = fnx.DiGraph()
    ng = nx.DiGraph()
    for g in (fg, ng):
        g.add_node(0, demand=-5)
        g.add_node(1, demand=0)
        g.add_node(2, demand=5)
        for u, v, w, c in spec_edges:
            g.add_edge(u, v, weight=w, capacity=c)
    # 5 units over edges costing 2 then 3 -> 5*(2+3) = 25.
    assert fnx.min_cost_flow_cost(fg) == 25
    assert fnx.min_cost_flow(fg) == nx.min_cost_flow(ng)


def test_infeasible_raises_like_networkx():
    fg = fnx.DiGraph()
    ng = nx.DiGraph()
    for g in (fg, ng):
        g.add_node(0, demand=-10)
        g.add_node(1, demand=10)
        g.add_edge(0, 1, weight=1, capacity=3)  # capacity < demand
    with pytest.raises(nx.NetworkXUnfeasible):
        fnx.min_cost_flow_cost(fg)
    with pytest.raises(nx.NetworkXUnfeasible):
        nx.min_cost_flow_cost(ng)
