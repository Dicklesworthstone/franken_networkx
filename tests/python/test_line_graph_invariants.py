"""Line graph L(G) structural invariants (line_graph <-> degree).

The line graph has one node per edge of G, with two such nodes adjacent iff the
edges share an endpoint. This gives exact structural identities cross-checking
line_graph against the degree sequence:
  - |V(L(G))| = |E(G)|;
  - |E(L(G))| = sum_v C(deg(v), 2)  (each node of degree d contributes C(d,2)
    adjacent edge-pairs);
  - the line-graph node for edge {u, v} has degree deg(u) + deg(v) - 2.
Oracle-free, independent of networkx.

No mocks: real fnx.
"""

from __future__ import annotations

import random

import pytest
import franken_networkx as fnx


def _graph(seed):
    r = random.Random(seed)
    n = r.randint(4, 9)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.4]
    g = fnx.Graph(); g.add_nodes_from(range(n)); g.add_edges_from(edges)
    return g


@pytest.mark.parametrize("seed", range(40))
def test_line_graph_node_and_edge_counts(seed):
    g = _graph(seed)
    if g.number_of_edges() == 0:
        pytest.skip("no edges")
    L = fnx.line_graph(g)
    deg = dict(g.degree())

    # One node per edge.
    assert L.number_of_nodes() == g.number_of_edges()
    # Edge count = sum of C(deg, 2) over original nodes.
    assert L.number_of_edges() == sum(deg[v] * (deg[v] - 1) // 2 for v in g)


@pytest.mark.parametrize("seed", range(40))
def test_line_graph_node_degrees(seed):
    g = _graph(seed)
    if g.number_of_edges() == 0:
        pytest.skip("no edges")
    L = fnx.line_graph(g)
    deg = dict(g.degree())
    for ln in L.nodes():
        u, v = tuple(ln)
        # An edge {u,v} is adjacent to all other edges at u and at v.
        assert L.degree(ln) == deg[u] + deg[v] - 2


def test_line_graph_of_path_and_cycle():
    # L(P_n) is P_{n-1}: the path on n nodes has n-1 edges -> n-1 line nodes.
    L = fnx.line_graph(fnx.path_graph(5))
    assert L.number_of_nodes() == 4
    assert L.number_of_edges() == 3            # consecutive edges share a node
    # L(C_n) is C_n: a cycle's line graph is a cycle of the same length.
    Lc = fnx.line_graph(fnx.cycle_graph(6))
    assert Lc.number_of_nodes() == 6
    assert Lc.number_of_edges() == 6
