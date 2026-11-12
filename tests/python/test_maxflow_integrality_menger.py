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
    # Zero is an integer, so integrality alone is satisfied by a flow of nothing:
    # an s-t path exists and every capacity is >= 1, so the max flow is positive.
    assert value > 0
    # The scalar and the dict are separate return values and nothing above ties
    # them together — the value must be the net flow leaving the source.
    out_of_s = sum(flow[s].values())
    into_s = sum(row.get(s, 0) for row in flow.values())
    assert out_of_s - into_s == value
    # maximum_flow_value is a second code path to the same number.
    assert fnx.maximum_flow_value(g, s, t) == value


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


@pytest.mark.parametrize("seed", range(40))
def test_menger_holds_for_every_reachable_pair(seed):
    """The test above checks a single (0, n-1) pair and skips 13 of its 40 seeds.

    Menger is a statement about every pair, and the graph almost always has many
    reachable ones, so sweeping them costs nothing and multiplies the coverage.
    """
    g, n = _capacitated(seed)
    gu = fnx.DiGraph()
    gu.add_nodes_from(range(n))
    for u, v in g.edges():
        gu.add_edge(u, v, capacity=1)

    checked = 0
    for s in range(n):
        for t in range(n):
            if s == t or not _has_path(g, s, t, n):
                continue
            checked += 1
            flow = fnx.maximum_flow_value(gu, s, t)
            assert flow == fc.local_edge_connectivity(gu, s, t)
            # Edge-disjoint s-t paths must leave s and enter t on distinct edges.
            assert flow <= min(gu.out_degree(s), gu.in_degree(t))
    assert checked > 0, "seed produced no reachable pair — the sweep would be vacuous"


@pytest.mark.parametrize("seed", range(40))
def test_scaling_integer_capacities_scales_the_value(seed):
    """Integrality is metamorphic: k * integer capacities gives exactly k * value."""
    g, n = _capacitated(seed)
    s, t = 0, n - 1
    if not _has_path(g, s, t, n):
        pytest.skip("no s-t path")
    base = fnx.maximum_flow_value(g, s, t)

    for k in (2, 3):
        scaled = fnx.DiGraph()
        scaled.add_nodes_from(range(n))
        for u, v, data in g.edges(data=True):
            scaled.add_edge(u, v, capacity=data["capacity"] * k)
        assert fnx.maximum_flow_value(scaled, s, t) == base * k


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
