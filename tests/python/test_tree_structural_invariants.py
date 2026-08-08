"""Tree-specific structural invariants.

Trees have characteristic properties beyond "connected and acyclic":
  - exactly n-1 edges, connected, is_tree;
  - the center consists of exactly 1 or 2 nodes (a tree's center is a vertex or
    an edge);
  - between any two nodes there is a UNIQUE simple path;
  - diameter and radius satisfy 2*radius - 1 <= diameter <= 2*radius;
  - every edge is a bridge (removing it disconnects the tree).
Trees are generated from random Prufer sequences. Oracle-free, cross-checking
center/radius/diameter/all_simple_paths/is_tree.

No mocks: real fnx.
"""

from __future__ import annotations

import itertools
import random

import pytest
import franken_networkx as fnx


def _random_tree(seed):
    r = random.Random(seed)
    n = r.randint(4, 14)
    seq = [r.randrange(n) for _ in range(n - 2)]
    return fnx.from_prufer_sequence(seq), n, r


@pytest.mark.parametrize("seed", range(40))
def test_basic_tree_structure(seed):
    t, n, r = _random_tree(seed)
    assert t.number_of_edges() == n - 1
    assert fnx.is_connected(t)
    assert fnx.is_tree(t)
    # Every edge of a tree is a bridge.
    e = next(iter(t.edges()))
    h = t.copy()
    h.remove_edge(*e)
    assert not fnx.is_connected(h)


@pytest.mark.parametrize("seed", range(40))
def test_center_and_unique_paths(seed):
    t, n, r = _random_tree(seed)
    # A tree's center is one node or two adjacent nodes.
    assert len(fnx.center(t)) in (1, 2)
    # Unique simple path between any two nodes.
    a, b = r.sample(list(t.nodes()), 2)
    assert len(list(fnx.all_simple_paths(t, a, b))) == 1


@pytest.mark.parametrize("seed", range(40))
def test_diameter_radius_relationship(seed):
    t, n, r = _random_tree(seed)
    diam = fnx.diameter(t)
    rad = fnx.radius(t)
    # For a tree, diameter is 2*radius or 2*radius - 1.
    assert 2 * rad - 1 <= diam <= 2 * rad


# br-r37-c1-0jqz4: the two invariants above are UNIVERSAL — "every edge is a
# bridge", "between ANY two nodes there is a unique simple path" — but each was
# checked on a single sample: `next(iter(t.edges()))` is one edge of n-1, and
# `r.sample(nodes, 2)` is one pair of n*(n-1)/2. A defect affecting some edges
# or some pairs and not the sampled one passes unnoticed. Quantifying costs
# nothing at these sizes: 337 edges and 1789 pairs across the same 40 seeds,
# against 40 and 40 before. All verified to hold before being asserted.
@pytest.mark.parametrize("seed", range(40))
def test_every_edge_is_a_bridge(seed):
    t, n, _ = _random_tree(seed)
    for edge in list(t.edges()):
        h = t.copy()
        h.remove_edge(*edge)
        assert not fnx.is_connected(h), edge


@pytest.mark.parametrize("seed", range(40))
def test_every_pair_has_exactly_one_simple_path(seed):
    t, n, _ = _random_tree(seed)
    for a, b in itertools.combinations(list(t.nodes()), 2):
        assert len(list(fnx.all_simple_paths(t, a, b))) == 1, (a, b)


@pytest.mark.parametrize("seed", range(40))
def test_center_is_a_node_or_an_adjacent_pair(seed):
    """The module docstring states the center is "a vertex or an edge", but the
    assertion above only counts it. A two-node center that was NOT adjacent
    would satisfy the count and violate the property (br-r37-c1-0jqz4).
    """
    t, _, _ = _random_tree(seed)
    center = fnx.center(t)
    assert set(center) <= set(t.nodes())
    assert len(center) in (1, 2)
    if len(center) == 2:
        assert t.has_edge(center[0], center[1]), center


def test_path_graph_center_and_diameter():
    # Path P_5: center is the single middle node, diameter 4, radius 2.
    p = fnx.path_graph(5)
    assert sorted(fnx.center(p)) == [2]
    assert fnx.diameter(p) == 4
    assert fnx.radius(p) == 2
    # Path P_4 (even): center is the two middle nodes.
    assert sorted(fnx.center(fnx.path_graph(4))) == [1, 2]
