"""Adjacency-matrix walk-counting identities (algebra <-> combinatorics).

Powers of the adjacency matrix count walks: (A^k)[i][j] is the number of length-k
walks from i to j. This yields identities cross-checking adjacency_matrix,
triangles, degree, and number_of_edges:
  - sum(A) = 2|E|; A is symmetric (undirected);
  - trace(A^2) = sum of degrees = 2|E|;
  - A^2[i][i] = degree(i) (2-walks returning to i);
  - trace(A^3) = 6 * (number of triangles);
  - A^3[i][i] / 2 = number of triangles through node i.
All are oracle-free (combinatorial theorems), independent of networkx.

Every identity below indexes row i against node i, which holds only because the
random graphs are labelled range(n) and inserted in order. Two things that
assumption rests on are pinned separately: the row order is g.nodes() order (not
sorted-label order), and `nodelist` permutes it. The identities also assume an
UNWEIGHTED matrix — adjacency_matrix reads the weight attribute by default, and
sum(A) = 2|E| is false on a weighted graph — so that boundary is pinned too.

No mocks: real fnx (numpy for the matrix powers).
"""

from __future__ import annotations

import random

import numpy as np
import pytest
import franken_networkx as fnx


def _graph(seed):
    r = random.Random(seed)
    n = r.randint(5, 10)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.4]
    g = fnx.Graph(); g.add_nodes_from(range(n)); g.add_edges_from(edges)
    return g, n


@pytest.mark.parametrize("seed", range(40))
def test_a_squared_identities(seed):
    g, n = _graph(seed)
    A = fnx.adjacency_matrix(g).toarray().astype(float)
    assert np.allclose(A, A.T)                                   # symmetric
    assert abs(A.sum() - 2 * g.number_of_edges()) < 1e-9        # sum(A) = 2|E|
    A2 = A @ A
    assert abs(np.trace(A2) - 2 * g.number_of_edges()) < 1e-9   # trace(A^2) = 2|E|
    degs = dict(g.degree())
    for i in range(n):
        assert abs(A2[i][i] - degs[i]) < 1e-9                    # A^2 diag = degree


@pytest.mark.parametrize("seed", range(40))
def test_a_cubed_counts_triangles(seed):
    g, n = _graph(seed)
    A = fnx.adjacency_matrix(g).toarray().astype(float)
    A3 = A @ A @ A
    # Each triangle is counted once per corner, so the sum must divide by 3
    # exactly — assert that rather than letting // silently truncate.
    assert sum(fnx.triangles(g).values()) % 3 == 0
    num_triangles = sum(fnx.triangles(g).values()) // 3
    # trace(A^3) = 6 * number of triangles.
    assert abs(np.trace(A3) - 6 * num_triangles) < 1e-6
    # Per-node: A^3[i][i] / 2 = triangles through node i.
    tri = fnx.triangles(g)
    for i in range(n):
        assert abs(A3[i][i] / 2 - tri[i]) < 1e-6


def _labelled_path():
    """A 3-path whose labels are neither range(n) nor in sorted order."""
    g = fnx.Graph()
    g.add_nodes_from(["c", "a", "b"])
    g.add_edges_from([("a", "b"), ("b", "c")])
    return g


def test_rows_follow_node_order_not_sorted_labels():
    """The i-th row is the i-th node of g.nodes(), which need not be sorted."""
    g = _labelled_path()
    assert list(g.nodes()) == ["c", "a", "b"]          # insertion order, unsorted
    A = fnx.adjacency_matrix(g).toarray().astype(float)
    index = {v: i for i, v in enumerate(g.nodes())}
    degrees = dict(g.degree())

    a2 = A @ A
    assert all(abs(a2[index[v]][index[v]] - degrees[v]) < 1e-9 for v in g.nodes())
    # Discriminating: the diagonal matches node order, NOT sorted-label order.
    assert [a2[i][i] for i in range(3)] == [degrees[v] for v in ["c", "a", "b"]]
    assert [a2[i][i] for i in range(3)] != [degrees[v] for v in ["a", "b", "c"]]


def test_nodelist_permutes_the_matrix():
    """nodelist reorders rows and columns; the identities follow the new order."""
    g = _labelled_path()
    default = fnx.adjacency_matrix(g).toarray()
    reordered = fnx.adjacency_matrix(g, nodelist=["a", "b", "c"]).toarray()
    assert not np.array_equal(default, reordered)      # a genuine permutation

    degrees = dict(g.degree())
    a2 = (reordered.astype(float)) @ (reordered.astype(float))
    for i, v in enumerate(["a", "b", "c"]):
        assert abs(a2[i][i] - degrees[v]) < 1e-9
    # Permuting cannot change a trace.
    assert abs(np.trace(a2) - np.trace(default.astype(float) @ default.astype(float))) < 1e-9


def test_identities_assume_an_unweighted_matrix():
    """adjacency_matrix reads `weight` by default, which breaks sum(A) = 2|E|."""
    g = fnx.Graph(); g.add_edge(0, 1, weight=5); g.add_edge(1, 2, weight=2)

    weighted = fnx.adjacency_matrix(g).toarray().astype(float)
    assert weighted.sum() == 14                        # 2*(5+2), not 2*|E|
    assert weighted.sum() != 2 * g.number_of_edges()

    unweighted = fnx.adjacency_matrix(g, weight=None).toarray().astype(float)
    assert unweighted.sum() == 2 * g.number_of_edges()
    assert abs(np.trace(unweighted @ unweighted) - 2 * g.number_of_edges()) < 1e-9


def test_complete_graph_triangle_count_via_trace():
    # K_n has C(n,3) triangles; trace(A^3) must be 6 * C(n,3).
    import math
    for n in (4, 5, 6):
        A = fnx.adjacency_matrix(fnx.complete_graph(n)).toarray().astype(float)
        assert abs(np.trace(A @ A @ A) - 6 * math.comb(n, 3)) < 1e-6
