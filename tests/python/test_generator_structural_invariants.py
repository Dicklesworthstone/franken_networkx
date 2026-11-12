"""Metamorphic tests for classic-graph-generator structural identities.

Tenth metamorphic-equivalence module pairing with the nine already in
place. Asserts the closed-form structural properties of the textbook
graph generators — every fixture (n) must produce a graph with the
exact node count, edge count, degree sequence, and topological
identities that the generator promises.

Generator-specific identities:

1. **complete_graph(n)**:
   - ``|V| = n``, ``|E| = n*(n-1)/2``
   - All nodes have degree ``n-1`` (regular)
   - Density == 1 (when n ≥ 2)

2. **cycle_graph(n)**:
   - ``|V| = n``, ``|E| = n`` (for n ≥ 3)
   - All nodes have degree 2

3. **path_graph(n)**:
   - ``|V| = n``, ``|E| = max(0, n-1)``
   - Exactly 2 nodes have degree 1 (the endpoints) for n ≥ 2;
     all interior nodes have degree 2

4. **star_graph(spokes)**:
   - ``|V| = spokes + 1``, ``|E| = spokes``
   - Center has degree ``spokes``; ``spokes`` rim nodes have degree 1

5. **complete_bipartite_graph(m, n)**:
   - ``|V| = m + n``, ``|E| = m * n``
   - is_bipartite == True
   - The two parts have sizes ``m`` and ``n`` (or ``n`` and ``m``;
     the classification can name either side first)

6. **balanced_tree(r, h)**:
   - ``|V| = (r^(h+1) - 1) / (r - 1)`` for r ≥ 2
   - is_tree == True (acyclic + connected)
"""

from __future__ import annotations

import pytest

import franken_networkx as fnx


# -----------------------------------------------------------------------------
# complete_graph
# -----------------------------------------------------------------------------


@pytest.mark.parametrize("n", [0, 1, 2, 3, 4, 5, 10])
def test_complete_graph_invariants(n):
    g = fnx.complete_graph(n)
    assert g.number_of_nodes() == n
    expected_edges = n * (n - 1) // 2
    assert g.number_of_edges() == expected_edges
    if n >= 1:
        # Every node has degree n-1; the graph is (n-1)-regular.
        for v, deg_v in g.degree():
            assert deg_v == n - 1, (
                f"complete_graph({n}): node {v} has degree {deg_v}, "
                f"expected {n - 1}"
            )


# -----------------------------------------------------------------------------
# cycle_graph
# -----------------------------------------------------------------------------


@pytest.mark.parametrize("n", [3, 4, 5, 6, 10])
def test_cycle_graph_invariants(n):
    g = fnx.cycle_graph(n)
    assert g.number_of_nodes() == n
    assert g.number_of_edges() == n
    # All nodes have degree 2 (regular).
    for v, deg_v in g.degree():
        assert deg_v == 2, (
            f"cycle_graph({n}): node {v} has degree {deg_v}, expected 2"
        )


# -----------------------------------------------------------------------------
# path_graph
# -----------------------------------------------------------------------------


@pytest.mark.parametrize("n", [2, 3, 4, 5, 6, 10])
def test_path_graph_invariants(n):
    g = fnx.path_graph(n)
    assert g.number_of_nodes() == n
    assert g.number_of_edges() == n - 1
    degree_counts = {1: 0, 2: 0}
    for _, deg_v in g.degree():
        degree_counts[deg_v] = degree_counts.get(deg_v, 0) + 1
    if n >= 2:
        assert degree_counts.get(1, 0) == 2, (
            f"path_graph({n}): expected 2 endpoints (degree 1), got "
            f"{degree_counts}"
        )
        assert degree_counts.get(2, 0) == n - 2, (
            f"path_graph({n}): expected n-2={n - 2} interior nodes "
            f"(degree 2), got {degree_counts}"
        )


# -----------------------------------------------------------------------------
# star_graph
# -----------------------------------------------------------------------------


@pytest.mark.parametrize("spokes", [1, 2, 3, 5, 10])
def test_star_graph_invariants(spokes):
    g = fnx.star_graph(spokes)
    assert g.number_of_nodes() == spokes + 1
    assert g.number_of_edges() == spokes
    degree_counts = {}
    for _, deg_v in g.degree():
        degree_counts[deg_v] = degree_counts.get(deg_v, 0) + 1
    # The star with 1 spoke is degenerate: 2 nodes, 1 edge, both have
    # degree 1. The textbook (center, rim) split collapses.
    if spokes == 1:
        assert degree_counts == {1: 2}, (
            f"star_graph(1): expected {{1: 2}}, got {degree_counts}"
        )
        return
    # General case: one center of degree ``spokes``, ``spokes`` rim
    # nodes of degree 1.
    assert degree_counts.get(spokes, 0) == 1, (
        f"star_graph({spokes}): expected 1 center node with degree "
        f"{spokes}, got {degree_counts}"
    )
    assert degree_counts.get(1, 0) == spokes, (
        f"star_graph({spokes}): expected {spokes} rim nodes with "
        f"degree 1, got {degree_counts}"
    )


# -----------------------------------------------------------------------------
# complete_bipartite_graph
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("m", "n"),
    [(1, 1), (1, 5), (2, 3), (3, 3), (4, 5), (3, 7)],
)
def test_complete_bipartite_invariants(m, n):
    g = fnx.complete_bipartite_graph(m, n)
    assert g.number_of_nodes() == m + n
    assert g.number_of_edges() == m * n
    assert fnx.is_bipartite(g), (
        f"complete_bipartite_graph({m}, {n}) reported as non-bipartite"
    )
    # Each part is m-regular or n-regular respectively. We can verify
    # the degree multiset has m nodes of degree n and n nodes of
    # degree m (the two sides each connect to every node on the
    # other side).
    degree_counts = {}
    for _, deg_v in g.degree():
        degree_counts[deg_v] = degree_counts.get(deg_v, 0) + 1
    if m == n:
        # Symmetric: every node has degree m == n; m + n = 2m total.
        assert degree_counts.get(m, 0) == m + n
    else:
        assert degree_counts.get(n, 0) == m, (
            f"complete_bipartite_graph({m}, {n}): expected {m} nodes "
            f"with degree {n}, got {degree_counts}"
        )
        assert degree_counts.get(m, 0) == n, (
            f"complete_bipartite_graph({m}, {n}): expected {n} nodes "
            f"with degree {m}, got {degree_counts}"
        )


# -----------------------------------------------------------------------------
# balanced_tree
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("r", "h"),
    [(2, 1), (2, 2), (2, 3), (3, 2), (3, 3), (4, 2)],
)
def test_balanced_tree_invariants(r, h):
    g = fnx.balanced_tree(r, h)
    expected_n = (r ** (h + 1) - 1) // (r - 1)
    assert g.number_of_nodes() == expected_n, (
        f"balanced_tree({r}, {h}): expected {expected_n} nodes, "
        f"got {g.number_of_nodes()}"
    )
    # A tree has |E| = |V| - 1 and is_tree == True.
    assert g.number_of_edges() == expected_n - 1
    assert fnx.is_tree(g), (
        f"balanced_tree({r}, {h}) is not a tree"
    )


# -----------------------------------------------------------------------------
# Cross-generator: every connected graph is its own connected component
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "builder"),
    [
        ("complete_5", lambda: fnx.complete_graph(5)),
        ("cycle_6", lambda: fnx.cycle_graph(6)),
        ("path_8", lambda: fnx.path_graph(8)),
        ("star_4", lambda: fnx.star_graph(4)),
        ("k_3_3", lambda: fnx.complete_bipartite_graph(3, 3)),
        ("balanced_tree_2_2", lambda: fnx.balanced_tree(2, 2)),
    ],
)
def test_connected_generator_yields_one_component(name, builder):
    g = builder()
    if g.number_of_nodes() == 0:
        return
    components = list(fnx.connected_components(g))
    assert len(components) == 1, (
        f"{name}: expected 1 connected component, got {len(components)}"
    )
    assert len(components[0]) == g.number_of_nodes(), (
        f"{name}: connected component should cover all "
        f"{g.number_of_nodes()} nodes, but only covered "
        f"{len(components[0])}"
    )
