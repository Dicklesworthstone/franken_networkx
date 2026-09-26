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


def _build_undirected_flow(spec, lib, cls="Graph"):
    n, edges = spec
    g = getattr(lib, cls)()
    g.add_nodes_from(range(n))
    for u, v, w, c in edges:
        g.add_edge(u, v, weight=w, capacity=c)
    return g


def _ordered(flow):
    return [(u, list(row.items())) for u, row in flow.items()]


@pytest.mark.parametrize("seed", range(30))
def test_max_flow_min_cost_undirected_matches_networkx(seed):
    # br-r37-c1-b4n6b: networkx runs min_cost_flow on DiGraph(G), so an undirected
    # G works (two arcs per edge); fnx copied G and min_cost_flow refused it.
    spec = _flow_spec(seed)
    n = spec[0]
    ff = fnx.max_flow_min_cost(_build_undirected_flow(spec, fnx), 0, n - 1)
    nf = nx.max_flow_min_cost(_build_undirected_flow(spec, nx), 0, n - 1)
    assert _ordered(ff) == _ordered(nf)


# br-r37-c1-33ctq: networkx's capacity_scaling adds flow * weight to the int 0
# only where flow moves (plus negative selfloops' saturation), so an edge that
# carries no flow never makes the cost a float; fnx scored every edge with
# cost_of_flow, and 0 * 2.5 is 0.0. 2 == 2.0, so compare (value, type).
_SCALING_CASES = {
    "no_demand_float_weights": ([(0, 0), (1, 0)], [(0, 1, 1.5, 4)]),
    "flow_on_int_edge_only": (
        [("s", -2), ("a", 0), ("t", 2)],
        [("s", "t", 1, 5), ("s", "a", 2.5, 5), ("a", "t", 2.5, 5)],
    ),
    "flow_on_float_edge": ([("s", -2), ("t", 2)], [("s", "t", 1.5, 5)]),
    "int_weights": ([("s", -3), ("a", 0), ("t", 3)], [("s", "a", 2, 2), ("a", "t", 1, 5), ("s", "t", 4, 5)]),
    "negative_selfloop": (
        [("s", -1), ("a", 0), ("t", 1)],
        [("s", "a", 1, 5), ("a", "t", 1, 5), ("a", "a", -1.5, 2)],
    ),
}


def _scaling_graph(lib, cls, case):
    nodes, edges = _SCALING_CASES[case]
    g = getattr(lib, cls)()
    for node, demand in nodes:
        g.add_node(node, demand=demand)
    for u, v, w, c in edges:
        g.add_edge(u, v, weight=w, capacity=c)
    return g


@pytest.mark.parametrize("spelling", ["capacity_scaling", "flow.capacity_scaling", "algorithms.capacity_scaling"])
@pytest.mark.parametrize("cls", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("case", sorted(_SCALING_CASES))
def test_capacity_scaling_cost_type_matches_networkx(spelling, cls, case):
    fn = fnx
    for part in spelling.split("."):
        fn = getattr(fn, part)
    n_cost, n_flow = nx.capacity_scaling(_scaling_graph(nx, cls, case))
    f_cost, f_flow = fn(_scaling_graph(fnx, cls, case))
    assert (f_cost, type(f_cost).__name__) == (n_cost, type(n_cost).__name__)
    assert f_flow == n_flow


@pytest.mark.parametrize("cls", ["MultiGraph", "MultiDiGraph"])
def test_max_flow_min_cost_multigraph_still_raises_like_networkx(cls):
    spec = _flow_spec(3)
    n = spec[0]
    with pytest.raises(nx.NetworkXError) as nx_exc:
        nx.max_flow_min_cost(_build_undirected_flow(spec, nx, cls), 0, n - 1)
    with pytest.raises(nx.NetworkXError) as fnx_exc:
        fnx.max_flow_min_cost(_build_undirected_flow(spec, fnx, cls), 0, n - 1)
    assert str(fnx_exc.value) == str(nx_exc.value)
