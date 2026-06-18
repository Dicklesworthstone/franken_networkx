"""Graph predicate cross-consistency (the is_X family must agree).

The boolean graph predicates are tied together by their definitions, so they
cross-check each other:
  - is_tree(G)  <=>  is_connected(G) and is_forest(G);
  - is_tree(G)  <=>  is_connected(G) and |E| == |V| - 1  (|V| > 0);
  - is_forest(G)  <=>  |E| == |V| - (number of components)   (acyclic);
  - is_regular(G)  <=>  all node degrees are equal;
  - is_connected(G)  <=>  number_connected_components(G) == 1  (|V| > 0);
  - is_empty(G)  <=>  the graph has no edges;
  - is_bipartite(G)  <=>  the bipartite node sets are a valid 2-colouring.
Oracle-free, independent of networkx.

No mocks: real fnx.
"""

from __future__ import annotations

import random

import pytest
import franken_networkx as fnx


def _graph(seed):
    r = random.Random(seed)
    n = r.randint(4, 10)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.35]
    g = fnx.Graph(); g.add_nodes_from(range(n)); g.add_edges_from(edges)
    return g, n


@pytest.mark.parametrize("seed", range(50))
def test_tree_forest_connected_predicates(seed):
    g, n = _graph(seed)
    E = g.number_of_edges()
    C = fnx.number_connected_components(g)

    assert fnx.is_tree(g) == (fnx.is_connected(g) and fnx.is_forest(g))
    assert fnx.is_tree(g) == (fnx.is_connected(g) and E == n - 1 and n > 0)
    assert fnx.is_forest(g) == (E == n - C)          # acyclic
    assert fnx.is_connected(g) == (C == 1)
    assert fnx.is_empty(g) == (E == 0)


@pytest.mark.parametrize("seed", range(50))
def test_regular_predicate(seed):
    g, n = _graph(seed)
    degrees = {d for _, d in g.degree()}
    assert fnx.is_regular(g) == (len(degrees) == 1)


@pytest.mark.parametrize("seed", range(50))
def test_bipartite_sets_are_valid_two_colouring(seed):
    g, n = _graph(seed)
    if not fnx.is_bipartite(g) or not fnx.is_connected(g):
        # bipartite.sets raises AmbiguousSolution on disconnected graphs (the
        # bipartition is not unique) — in both fnx and networkx.
        pytest.skip("not connected bipartite")
    left, right = fnx.bipartite.sets(g)
    # The two sides partition the nodes...
    assert left | right == set(g.nodes())
    assert not (left & right)
    # ...and no edge lies within a side (a valid 2-colouring).
    for u, v in g.edges():
        assert (u in left) != (v in left)
