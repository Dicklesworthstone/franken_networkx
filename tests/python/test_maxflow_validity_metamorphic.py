"""Oracle-free validity tests for maximum_flow / minimum_cut.

A flow dict is *valid* iff it satisfies the definitional properties — these
hold regardless of any reference implementation, so they catch correctness
bugs that exact-parity testing can miss:

- **Capacity**: 0 <= flow[u][v] <= capacity[u][v] on every edge.
- **Conservation**: at every node except source/sink, inflow == outflow.
- **Value**: the returned flow value equals net outflow from the source.
- **Max-flow / min-cut theorem**: max flow value == min cut value.

No mocks: real fnx on randomly generated capacitated digraphs.

br-r37-c1-324jn
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _random_capacitated_digraph(seed):
    r = random.Random(seed)
    n = r.randint(4, 8)
    g = fnx.DiGraph()
    g.add_nodes_from(range(n))
    for u in range(n):
        for v in range(n):
            if u != v and r.random() < 0.35:
                g.add_edge(u, v, capacity=r.randint(1, 9))
    return g, n


def _has_st_path(g, s, t, n):
    ng = nx.DiGraph()
    ng.add_nodes_from(range(n))
    ng.add_edges_from((u, v) for u, v in g.edges())
    return nx.has_path(ng, s, t)


@pytest.mark.parametrize("seed", range(80))
def test_flow_is_valid_and_equals_min_cut(seed):
    g, n = _random_capacitated_digraph(seed)
    s, t = 0, n - 1
    if not _has_st_path(g, s, t, n):
        pytest.skip("no s-t path")

    value, flow = fnx.maximum_flow(g, s, t)

    # Capacity constraints.
    for u in flow:
        for v, f in flow[u].items():
            assert -1e-9 <= f <= g[u][v]["capacity"] + 1e-9

    # Conservation at internal nodes.
    for node in range(n):
        if node in (s, t):
            continue
        inflow = sum(flow[u].get(node, 0) for u in flow)
        outflow = sum(flow[node].values()) if node in flow else 0
        assert abs(inflow - outflow) < 1e-9

    # Value == net source outflow.
    src_out = sum(flow[s].values()) - sum(flow[u].get(s, 0) for u in flow)
    assert abs(value - src_out) < 1e-9

    # Max-flow / min-cut theorem.
    cut_value, (reachable, non_reachable) = fnx.minimum_cut(g, s, t)
    assert abs(value - cut_value) < 1e-9
    # The cut partition separates s from t.
    assert s in reachable and t in non_reachable


def test_maxflow_complete_digraph_closed_form():
    # In a complete digraph with unit capacities, max flow s->t equals the
    # number of edge-disjoint paths = (n-1): the direct edge plus n-2 length-2
    # detours through each other node.
    for n in (4, 5, 6):
        g = fnx.DiGraph()
        g.add_nodes_from(range(n))
        for u in range(n):
            for v in range(n):
                if u != v:
                    g.add_edge(u, v, capacity=1)
        value, _ = fnx.maximum_flow(g, 0, n - 1)
        assert value == n - 1
