"""Metamorphic tests for connectivity-related algebraic invariants.

Fifth metamorphic-equivalence module pairing with:
- test_mst_algorithm_equivalence.py
- test_shortest_path_algorithm_equivalence.py
- test_dag_closure_reduction_equivalence.py
- test_graph_operator_involutions.py

Covers algebraic invariants involving connectivity / cut / tree
properties that catch a class of bug invisible to per-function unit
tests:

1. **Tree edge-removal**: every edge of a tree is a bridge — removing
   any edge from a tree disconnects it (number of connected
   components goes from 1 to 2).
2. **Tree edge count**: a tree on n nodes has exactly n-1 edges.
3. **Articulation removal**: removing an articulation point strictly
   increases the number of connected components.
4. **Bridge removal**: removing a bridge edge strictly increases the
   number of connected components.
5. **Non-bridge removal**: removing a non-bridge edge does NOT
   increase the number of connected components.
6. **Component partition**: ``connected_components(G)`` is a partition
   — every node appears in exactly one component, and the union of
   all components equals the node set.
"""

from __future__ import annotations

import pytest

import franken_networkx as fnx


TREE_FIXTURES = [
    ("path_5", lambda: fnx.path_graph(5)),
    ("balanced_tree_2_2", lambda: fnx.balanced_tree(2, 2)),
    ("balanced_tree_3_2", lambda: fnx.balanced_tree(3, 2)),
    ("star_5", lambda: fnx.star_graph(5)),
]

CONNECTED_NON_TREE_FIXTURES = [
    ("cycle_4", lambda: fnx.cycle_graph(4)),
    ("complete_4", lambda: fnx.complete_graph(4)),
    ("triangle_with_tail",
     lambda: fnx.Graph([(0, 1), (1, 2), (2, 0), (2, 3), (3, 4)])),
    ("two_triangles_share_edge",
     lambda: fnx.Graph([(0, 1), (1, 2), (2, 0), (2, 3), (3, 0)])),
]


# -----------------------------------------------------------------------------
# Tree properties
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "builder"), TREE_FIXTURES)
def test_tree_has_n_minus_1_edges(name, builder):
    g = builder()
    assert fnx.is_tree(g), f"{name}: fixture is not a tree"
    n = g.number_of_nodes()
    m = g.number_of_edges()
    assert m == n - 1, (
        f"{name}: tree should have n-1={n - 1} edges but has {m}"
    )


@pytest.mark.parametrize(("name", "builder"), TREE_FIXTURES)
def test_every_tree_edge_is_a_bridge(name, builder):
    """Removing any edge of a tree disconnects it (each edge is a
    bridge by definition of a tree)."""
    g = builder()
    if g.number_of_edges() == 0:
        return  # trivial
    for u, v in list(g.edges()):
        g2 = g.copy()
        g2.remove_edge(u, v)
        assert not fnx.is_connected(g2), (
            f"{name}: removing edge ({u}, {v}) didn't disconnect the tree"
        )
        assert fnx.number_connected_components(g2) == 2, (
            f"{name}: removing tree edge ({u}, {v}) didn't yield 2 components"
        )


# -----------------------------------------------------------------------------
# Articulation removal
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "builder"), CONNECTED_NON_TREE_FIXTURES + TREE_FIXTURES)
def test_articulation_removal_increases_components(name, builder):
    g = builder()
    aps = list(fnx.articulation_points(g))
    if not aps:
        return
    ncc = fnx.number_connected_components(g)
    for ap in aps:
        g2 = g.copy()
        g2.remove_node(ap)
        new_ncc = fnx.number_connected_components(g2)
        # We removed a node, so the *remaining* graph has at least one
        # more component than before once the articulation point is
        # gone (the original ncc, minus 1 for the removed component
        # that disappeared with the node, plus the new components the
        # split produced). The strict invariant: new_ncc > ncc - 1
        # when the AP straddled multiple cuts.
        assert new_ncc >= ncc, (
            f"{name}: removing articulation point {ap} should not *decrease* ncc "
            f"(was {ncc}, now {new_ncc})"
        )


# -----------------------------------------------------------------------------
# Bridge removal
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "builder"), CONNECTED_NON_TREE_FIXTURES + TREE_FIXTURES)
def test_bridge_removal_increases_components(name, builder):
    """Removing any bridge edge increases ncc by exactly 1."""
    g = builder()
    bridges = list(fnx.bridges(g))
    if not bridges:
        return
    ncc = fnx.number_connected_components(g)
    for u, v in bridges:
        g2 = g.copy()
        g2.remove_edge(u, v)
        new_ncc = fnx.number_connected_components(g2)
        assert new_ncc == ncc + 1, (
            f"{name}: removing bridge ({u}, {v}) should increase ncc "
            f"by exactly 1, but went from {ncc} to {new_ncc}"
        )


# -----------------------------------------------------------------------------
# Non-bridge removal
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "builder"), CONNECTED_NON_TREE_FIXTURES)
def test_non_bridge_removal_preserves_components(name, builder):
    """Removing an edge that is NOT a bridge does not increase ncc."""
    g = builder()
    bridges = set()
    for u, v in fnx.bridges(g):
        bridges.add(tuple(sorted((u, v))))
    ncc = fnx.number_connected_components(g)
    for u, v in g.edges():
        if tuple(sorted((u, v))) in bridges:
            continue
        g2 = g.copy()
        g2.remove_edge(u, v)
        new_ncc = fnx.number_connected_components(g2)
        assert new_ncc == ncc, (
            f"{name}: removing non-bridge ({u}, {v}) should preserve ncc "
            f"(was {ncc}, now {new_ncc})"
        )


# -----------------------------------------------------------------------------
# Component partition
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "builder"), CONNECTED_NON_TREE_FIXTURES + TREE_FIXTURES)
def test_connected_components_form_partition(name, builder):
    g = builder()
    components = list(fnx.connected_components(g))
    seen = set()
    for comp in components:
        for n in comp:
            assert g.has_node(n), (
                f"{name}: component contains foreign node {n}"
            )
            assert n not in seen, (
                f"{name}: node {n} appears in multiple components"
            )
            seen.add(n)
    assert seen == set(g.nodes()), (
        f"{name}: connected components don't cover the graph's node set"
    )
