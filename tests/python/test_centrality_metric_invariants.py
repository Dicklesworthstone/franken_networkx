"""Metamorphic tests for centrality / metric / structural algebraic invariants.

Sixth metamorphic-equivalence module pairing with:
- test_mst_algorithm_equivalence.py
- test_shortest_path_algorithm_equivalence.py
- test_dag_closure_reduction_equivalence.py
- test_graph_operator_involutions.py
- test_connectivity_metamorphic_invariants.py

Covers algebraic invariants on centrality / clustering / metric
properties that catch a class of bug invisible to per-function unit
tests:

1. **PageRank distribution**: pagerank scores sum to 1 (probability
   distribution invariant when power iteration converges).
2. **Degree centrality range**: ``degree_centrality(v) ∈ [0, 1]``
   for every node v.
3. **Triangle sum invariant**: sum of per-node triangle counts equals
   3 * (total triangles in G), since each triangle contributes once
   to each of its three vertices.
4. **Density formula**: ``density(G) = 2|E| / (|V|(|V|-1))`` for
   simple undirected graphs.
5. **Bipartite no odd cycles**: when ``is_bipartite(G)`` is true,
   no cycle in ``cycle_basis(G)`` has odd length.
6. **Self-degree-centrality on regular graphs**: every node of a
   d-regular graph has the same degree centrality (since they all
   have the same degree).
7. **Closeness centrality range**: ``closeness_centrality(v) ∈ [0, 1]``
   for every node on a connected graph.
"""

from __future__ import annotations

import pytest

import franken_networkx as fnx


CONNECTED_FIXTURES = [
    ("path_5", lambda: fnx.path_graph(5)),
    ("cycle_5", lambda: fnx.cycle_graph(5)),
    ("complete_4", lambda: fnx.complete_graph(4)),
    ("complete_5", lambda: fnx.complete_graph(5)),
    ("balanced_tree_2_2", lambda: fnx.balanced_tree(2, 2)),
    ("karate", lambda: fnx.karate_club_graph()),
]

REGULAR_FIXTURES = [
    # (name, builder, expected_degree)
    ("cycle_5", lambda: fnx.cycle_graph(5), 2),
    ("complete_5", lambda: fnx.complete_graph(5), 4),
    ("complete_4", lambda: fnx.complete_graph(4), 3),
]

BIPARTITE_FIXTURES = [
    ("complete_bipartite_3_3", lambda: fnx.complete_bipartite_graph(3, 3)),
    ("complete_bipartite_2_4", lambda: fnx.complete_bipartite_graph(2, 4)),
    ("path_5", lambda: fnx.path_graph(5)),
    ("balanced_tree_2_2", lambda: fnx.balanced_tree(2, 2)),
]


# -----------------------------------------------------------------------------
# PageRank
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "builder"), CONNECTED_FIXTURES)
def test_pagerank_sums_to_one(name, builder):
    g = builder()
    pr = fnx.pagerank(g)
    total = sum(pr.values())
    assert abs(total - 1.0) < 1.0e-6, (
        f"{name}: pagerank sum {total} != 1.0 — probability distribution invariant"
    )


# -----------------------------------------------------------------------------
# Degree centrality range
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "builder"), CONNECTED_FIXTURES)
def test_degree_centrality_in_unit_range(name, builder):
    g = builder()
    dc = fnx.degree_centrality(g)
    for v, c in dc.items():
        assert 0.0 - 1e-9 <= c <= 1.0 + 1e-9, (
            f"{name}: degree_centrality[{v}] = {c} outside [0, 1]"
        )


# -----------------------------------------------------------------------------
# Closeness centrality range
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "builder"), CONNECTED_FIXTURES)
def test_closeness_centrality_in_unit_range(name, builder):
    g = builder()
    cc = fnx.closeness_centrality(g)
    for v, c in cc.items():
        assert 0.0 - 1e-9 <= c <= 1.0 + 1e-9, (
            f"{name}: closeness_centrality[{v}] = {c} outside [0, 1]"
        )


# -----------------------------------------------------------------------------
# Triangle sum invariant
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "builder"), CONNECTED_FIXTURES)
def test_triangle_sum_divisible_by_three(name, builder):
    """Each triangle contributes once to each of its 3 vertices, so
    the sum of per-node triangle counts is always divisible by 3."""
    g = builder()
    triangles = fnx.triangles(g)
    total = sum(triangles.values())
    assert total % 3 == 0, (
        f"{name}: triangle-count sum {total} not divisible by 3 "
        f"(each triangle contributes once per vertex)"
    )


# -----------------------------------------------------------------------------
# Density formula
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "builder"), CONNECTED_FIXTURES)
def test_density_matches_formula(name, builder):
    g = builder()
    n = g.number_of_nodes()
    m = g.number_of_edges()
    if n < 2:
        return
    expected = 2 * m / (n * (n - 1))
    actual = fnx.density(g)
    assert abs(actual - expected) < 1e-9, (
        f"{name}: density {actual} != 2|E|/(|V|(|V|-1)) = {expected}"
    )


# -----------------------------------------------------------------------------
# Bipartite no odd cycles
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "builder"), BIPARTITE_FIXTURES)
def test_bipartite_graphs_have_no_odd_cycles(name, builder):
    g = builder()
    if not fnx.is_bipartite(g):
        return  # only meaningful for bipartite inputs
    basis = list(fnx.cycle_basis(g))
    for cycle in basis:
        assert len(cycle) % 2 == 0, (
            f"{name}: bipartite graph has odd-length cycle {cycle} "
            f"(length {len(cycle)}) in its cycle basis"
        )


# -----------------------------------------------------------------------------
# Regular graph: all nodes have the same degree centrality
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "builder", "expected_deg"), REGULAR_FIXTURES)
def test_regular_graph_uniform_degree_centrality(name, builder, expected_deg):
    g = builder()
    # First confirm the fixture really is regular.
    degs = [g.degree(v) for v in g.nodes()]
    if not all(d == expected_deg for d in degs):
        return
    dc = fnx.degree_centrality(g)
    values = list(dc.values())
    if not values:
        return
    base = values[0]
    for v, c in dc.items():
        assert abs(c - base) < 1e-9, (
            f"{name}: regular graph has uneven degree centrality "
            f"({base} vs {c} on node {v})"
        )
