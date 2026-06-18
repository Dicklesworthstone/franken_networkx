"""Max-flow integrality theorem + unit-capacity Menger equality.

Two classic flow theorems, distinct from the flow-validity checks in
br-r37-c1-324jn:
  - **Integral Flow Theorem**: with integer capacities, a maximum flow has an
    integer value AND an integer flow on every edge;
  - **Menger (edge form)**: with unit capacities, the maximum s-t flow equals the
    local edge connectivity (the number of edge-disjoint s-t paths).
Oracle-free, independent of networkx.

No mocks: real fnx (networkx used only to decide reachability for the skip).
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx
import franken_networkx.algorithms.connectivity as fc


def _capacitated(seed):
    r = random.Random(seed)
    n = r.randint(4, 8)
    g = fnx.DiGraph()
    g.add_nodes_from(range(n))
    for u in range(n):
        for v in range(n):
            if u != v and r.random() < 0.35:
                g.add_edge(u, v, capacity=r.randint(1, 9))
    return g, n


def _has_path(g, s, t, n):
    ng = nx.DiGraph()
    ng.add_nodes_from(range(n))
    ng.add_edges_from((u, v) for u, v in g.edges())
    return nx.has_path(ng, s, t)


@pytest.mark.parametrize("seed", range(40))
def test_integer_capacities_give_integer_flow(seed):
    g, n = _capacitated(seed)
    s, t = 0, n - 1
    if not _has_path(g, s, t, n):
        pytest.skip("no s-t path")
    value, flow = fnx.maximum_flow(g, s, t)
    # Integral flow theorem: integer value and integer edge flows.
    assert value == int(value)
    for u in flow:
        for v, f in flow[u].items():
            assert abs(f - round(f)) < 1e-9


@pytest.mark.parametrize("seed", range(40))
def test_unit_capacity_flow_equals_edge_connectivity(seed):
    g, n = _capacitated(seed)
    s, t = 0, n - 1
    if not _has_path(g, s, t, n):
        pytest.skip("no s-t path")
    # Replace all capacities with 1.
    gu = fnx.DiGraph()
    gu.add_nodes_from(range(n))
    for u, v in g.edges():
        gu.add_edge(u, v, capacity=1)
    # Menger (edge form): unit-capacity max flow == local edge connectivity.
    assert fnx.maximum_flow_value(gu, s, t) == fc.local_edge_connectivity(gu, s, t)


def test_complete_unit_digraph_flow_is_n_minus_1():
    # Complete unit-capacity digraph: n-1 edge-disjoint s-t paths.
    for n in (4, 5, 6):
        g = fnx.DiGraph()
        g.add_nodes_from(range(n))
        for u in range(n):
            for v in range(n):
                if u != v:
                    g.add_edge(u, v, capacity=1)
        assert fnx.maximum_flow_value(g, 0, n - 1) == n - 1
