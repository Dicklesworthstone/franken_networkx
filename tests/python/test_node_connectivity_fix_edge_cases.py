"""Edge-case regression guard for the node_connectivity P1 fixes.

br-r37-c1-cqlms (undirected adjacent returned 0) and br-r37-c1-ebd8d
(directed local undercounted) are covered for random graphs elsewhere;
this pins the special-structure cases the random tests rarely hit:
directed 2-/3-cycles and self-loops, multigraph adjacent pairs (the
delegated path), and complete/star adjacency.

br-r37-c1-bpyoc
"""

from __future__ import annotations

import pytest
import networkx as nx
import franken_networkx as fnx


_DIRECTED_SPECS = [
    [(0, 1)],
    [(0, 1), (1, 0)],
    [(0, 1), (1, 2), (2, 0)],
    [(0, 0), (0, 1)],
    [(0, 1), (1, 2), (2, 3), (3, 0)],
]


@pytest.mark.parametrize("spec", _DIRECTED_SPECS)
def test_directed_local_special_structures(spec):
    g = fnx.DiGraph(spec)
    ng = nx.DiGraph(spec)
    for s in list(g):
        for t in list(g):
            if s == t:
                continue
            assert fnx.node_connectivity(g, s, t) == nx.node_connectivity(ng, s, t)


@pytest.mark.parametrize("spec", [
    [(0, 1), (0, 1)],
    [(0, 1), (0, 1), (1, 2)],
    [(0, 1), (0, 1), (0, 1), (1, 2), (1, 2)],
])
def test_multigraph_adjacent_pairs(spec):
    g = fnx.MultiGraph(spec)
    ng = nx.MultiGraph(spec)
    for s in list(g):
        for t in list(g):
            if s >= t:
                continue
            assert fnx.node_connectivity(g, s, t) == nx.node_connectivity(ng, s, t)


@pytest.mark.parametrize("builder", [
    lambda lib: lib.complete_graph(5),
    lambda lib: lib.star_graph(4),
    lambda lib: lib.complete_bipartite_graph(3, 3),
])
def test_structured_adjacent_pairs(builder):
    g = builder(fnx)
    ng = builder(nx)
    for s in list(g):
        for t in list(g):
            if s == t:
                continue
            assert fnx.node_connectivity(g, s, t) == nx.node_connectivity(ng, s, t)
