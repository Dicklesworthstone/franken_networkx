"""Metamorphic tests for adjacency-matrix algebraic invariants.

Fourteenth metamorphic-equivalence module pairing with the thirteen
already in place. Covers textbook spectral / matrix-algebra identities
that follow from the definition of the adjacency matrix.

Adjacency matrix invariants:

1. **Symmetry on undirected**: ``A == A.T`` for every undirected graph.
2. **Zero diagonal on simple graph**: ``A[i, i] == 0`` for every i
   (simple graphs have no self-loops).
3. **Row sum equals degree**: ``sum(A[i, :]) == deg(node_i)`` for
   every node.
4. **A² diagonal = degree**: ``A²[i, i] == deg(node_i)`` (the number
   of length-2 walks from i back to i equals the number of distinct
   neighbors).
5. **Triangle count via trace(A³)**: ``trace(A³) == 6 * |triangles|``
   on undirected graphs (each triangle u-v-w-u contributes 6 closed
   walks of length 3 — once per ordered (u,v,w) permutation).

Pairs with the linalg subpackage path that landed earlier
(``franken_networkx.linalg.adjacency_matrix``) and verifies the
adjacency matrix it builds satisfies these algebraic identities.
"""

from __future__ import annotations

import numpy as np
import pytest

import franken_networkx as fnx


CONNECTED_FIXTURES = [
    ("path_5", lambda: fnx.path_graph(5)),
    ("cycle_6", lambda: fnx.cycle_graph(6)),
    ("complete_4", lambda: fnx.complete_graph(4)),
    ("complete_5", lambda: fnx.complete_graph(5)),
    ("complete_bipartite_3_3", lambda: fnx.complete_bipartite_graph(3, 3)),
    ("balanced_tree_2_2", lambda: fnx.balanced_tree(2, 2)),
    ("karate", lambda: fnx.karate_club_graph()),
]


def _adj_matrix(g):
    """Return the binary 0/1 adjacency matrix as a dense numpy array
    using a deterministic node ordering. Forces ``weight=None`` so
    edge attributes never inflate counts (the karate fixture carries
    real weights)."""
    nodelist = sorted(g.nodes(), key=str)
    sparse = fnx.linalg.adjacency_matrix(g, nodelist=nodelist, weight=None)
    return np.array(sparse.todense()), nodelist


# -----------------------------------------------------------------------------
# Symmetry on undirected
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "builder"), CONNECTED_FIXTURES)
def test_adjacency_matrix_is_symmetric_on_undirected(name, builder):
    g = builder()
    A, _ = _adj_matrix(g)
    assert np.array_equal(A, A.T), (
        f"{name}: adjacency matrix on undirected graph is not symmetric"
    )


# -----------------------------------------------------------------------------
# Zero diagonal on simple graph
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "builder"), CONNECTED_FIXTURES)
def test_adjacency_matrix_has_zero_diagonal(name, builder):
    g = builder()
    A, _ = _adj_matrix(g)
    diag = np.diag(A)
    assert np.all(diag == 0), (
        f"{name}: adjacency matrix has non-zero diagonal {diag} "
        f"(simple graph should have no self-loops)"
    )


# -----------------------------------------------------------------------------
# Row sum equals degree
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "builder"), CONNECTED_FIXTURES)
def test_row_sum_equals_degree(name, builder):
    g = builder()
    A, nodelist = _adj_matrix(g)
    for i, node in enumerate(nodelist):
        row_sum = int(A[i, :].sum())
        deg_node = g.degree(node)
        assert row_sum == deg_node, (
            f"{name}: A row sum {row_sum} != deg({node}) = {deg_node}"
        )


# -----------------------------------------------------------------------------
# A² diagonal == degree
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "builder"), CONNECTED_FIXTURES)
def test_a_squared_diagonal_equals_degree(name, builder):
    g = builder()
    A, nodelist = _adj_matrix(g)
    A2 = A @ A
    for i, node in enumerate(nodelist):
        diag_i = int(A2[i, i])
        deg_node = g.degree(node)
        assert diag_i == deg_node, (
            f"{name}: A²[{i}, {i}] = {diag_i} != deg({node}) = {deg_node} "
            f"(closed-walk-of-length-2 count should equal degree)"
        )


# -----------------------------------------------------------------------------
# trace(A³) = 6 * |triangles|
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "builder"), CONNECTED_FIXTURES)
def test_trace_a_cubed_equals_six_times_triangles(name, builder):
    g = builder()
    A, _ = _adj_matrix(g)
    A3 = A @ A @ A
    trace = int(np.trace(A3))
    triangle_counts = fnx.triangles(g)
    total_triangles = sum(triangle_counts.values()) // 3
    assert trace == 6 * total_triangles, (
        f"{name}: trace(A³) = {trace} != 6 * |triangles| = "
        f"{6 * total_triangles}"
    )


# -----------------------------------------------------------------------------
# A² is symmetric (follows from A symmetric on undirected)
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "builder"), CONNECTED_FIXTURES)
def test_a_squared_is_symmetric_on_undirected(name, builder):
    g = builder()
    A, _ = _adj_matrix(g)
    A2 = A @ A
    assert np.array_equal(A2, A2.T), (
        f"{name}: A² is not symmetric (impossible since A is symmetric)"
    )


# -----------------------------------------------------------------------------
# Total entries of A == 2 * |E|
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "builder"), CONNECTED_FIXTURES)
def test_adjacency_matrix_total_equals_twice_edges(name, builder):
    g = builder()
    A, _ = _adj_matrix(g)
    total = int(A.sum())
    expected = 2 * g.number_of_edges()
    assert total == expected, (
        f"{name}: sum(A) = {total} != 2|E| = {expected} "
        f"(handshaking lemma in matrix form)"
    )
