"""Gallai's identity: matching number + edge cover number = n.

For a graph with no isolated vertices, Gallai's theorem states
  nu(G) + rho(G) = |V|,
where nu is the maximum matching size and rho is the minimum edge cover size.
This cross-checks two independent algorithms (max_weight_matching and
min_edge_cover) against each other AND the node count — a strong oracle-free
invariant. Cardinality parity with networkx and edge-cover validity are also
checked.

No mocks: real fnx and real networkx.
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _no_isolates_graph(seed):
    r = random.Random(seed)
    n = r.randint(4, 8)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.5]
    fg = fnx.Graph(); fg.add_nodes_from(range(n)); fg.add_edges_from(edges)
    ng = nx.Graph(); ng.add_nodes_from(range(n)); ng.add_edges_from(edges)
    return fg, ng, n


@pytest.mark.parametrize("seed", range(40))
def test_gallai_matching_plus_edge_cover_equals_n(seed):
    fg, ng, n = _no_isolates_graph(seed)
    if any(d == 0 for _, d in fg.degree()):
        pytest.skip("has isolated vertex (identity needs none)")

    nu = len(fnx.max_weight_matching(fg))    # maximum matching cardinality
    rho = len(fnx.min_edge_cover(fg))         # minimum edge cover cardinality
    # Gallai: nu + rho == n.
    assert nu + rho == n
    # Both cardinalities match networkx.
    assert len(nx.max_weight_matching(ng)) == nu
    assert len(nx.min_edge_cover(ng)) == rho


@pytest.mark.parametrize("seed", range(40))
def test_min_edge_cover_is_valid(seed):
    fg, ng, n = _no_isolates_graph(seed)
    if any(d == 0 for _, d in fg.degree()):
        pytest.skip("has isolated vertex")
    ec = fnx.min_edge_cover(fg)
    covered = set()
    for u, v in ec:
        covered.add(u)
        covered.add(v)
    # An edge cover must touch every node.
    assert covered == set(range(n))


def test_matching_is_valid_on_named_graphs():
    # A perfect matching on an even cycle covers all nodes in n/2 disjoint edges.
    g = fnx.cycle_graph(6)
    m = fnx.max_weight_matching(g)
    assert len(m) == 3
    seen = set()
    for u, v in m:
        assert u not in seen and v not in seen  # disjoint (a real matching)
        seen.add(u); seen.add(v)
