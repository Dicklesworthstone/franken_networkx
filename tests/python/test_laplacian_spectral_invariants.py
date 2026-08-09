"""Laplacian spectral invariants (spectral graph theory cross-checks).

The Laplacian and its spectrum obey strong identities that cross-check
laplacian_matrix, adjacency_matrix, laplacian_spectrum, and
number_connected_components:
  - L = D - A (degree diagonal minus adjacency);
  - row sums are zero; trace(L) = sum of degrees = 2|E|;
  - the smallest Laplacian eigenvalue is 0;
  - the multiplicity of eigenvalue 0 equals the number of connected components;
  - the eigenvalues sum to 2|E|;
  - the graph is connected iff the second-smallest eigenvalue (lambda_2) > 0.
All are oracle-free (theorems, not a reference implementation).

A spectrum is permutation-invariant by nature, so the eigenvalue tests cannot
see a row-order regression and are not expected to. The structural test does not
see one either: it derives D from A, so a consistently permuted (L, A) pair still
satisfies L = D - A. The row-to-node correspondence is therefore pinned
separately, against the degrees, along with `nodelist` and the weighted case
(laplacian_matrix reads the weight attribute by default, which breaks
trace(L) = 2|E| while leaving the row sums zero).

No mocks: real fnx (numpy for the eigen-decomposition).
"""

from __future__ import annotations

import random

import numpy as np
import pytest
import franken_networkx as fnx


def _graph(seed):
    r = random.Random(seed)
    n = r.randint(5, 10)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.35]
    g = fnx.Graph(); g.add_nodes_from(range(n)); g.add_edges_from(edges)
    return g, n


@pytest.mark.parametrize("seed", range(40))
def test_laplacian_structure(seed):
    g, n = _graph(seed)
    L = fnx.laplacian_matrix(g).toarray().astype(float)
    A = fnx.adjacency_matrix(g).toarray().astype(float)
    D = np.diag(A.sum(axis=1))
    assert np.allclose(L, D - A)               # L = D - A
    assert np.allclose(L.sum(axis=1), 0)       # row sums zero
    assert abs(np.trace(L) - 2 * g.number_of_edges()) < 1e-9   # trace = 2|E|


@pytest.mark.parametrize("seed", range(40))
def test_laplacian_spectrum_invariants(seed):
    g, n = _graph(seed)
    evals = sorted(np.real(fnx.laplacian_spectrum(g)))

    assert abs(evals[0]) < 1e-8                 # smallest eigenvalue is 0
    assert abs(sum(evals) - 2 * g.number_of_edges()) < 1e-6   # eigsum = 2|E|

    # Multiplicity of eigenvalue 0 == number of connected components.
    mult0 = sum(1 for e in evals if abs(e) < 1e-8)
    assert mult0 == fnx.number_connected_components(g)

    # Connected graph (n>1) has a strictly positive Fiedler value.
    if fnx.is_connected(g) and n > 1:
        assert evals[1] > 1e-8
    else:
        # The other half of the "iff": disconnected means lambda_2 is 0 too.
        # Only the forward direction was asserted, on the 22 connected draws;
        # the 18 disconnected ones fell through without any spectral check.
        assert abs(evals[1]) < 1e-8


def _labelled_path():
    """A 3-path labelled so that node order and sorted order disagree."""
    g = fnx.Graph()
    g.add_nodes_from(["c", "a", "b"])
    g.add_edges_from([("a", "b"), ("b", "c")])
    return g


def test_laplacian_rows_follow_node_order():
    """L = D - A is order-blind because D comes from A; the degrees are not."""
    g = _labelled_path()
    L = fnx.laplacian_matrix(g).toarray().astype(float)
    degrees = dict(g.degree())

    index = {v: i for i, v in enumerate(g.nodes())}
    assert all(abs(L[index[v]][index[v]] - degrees[v]) < 1e-9 for v in g.nodes())
    # Discriminating: the diagonal follows g.nodes(), not sorted labels.
    assert [L[i][i] for i in range(3)] == [degrees[v] for v in ["c", "a", "b"]]
    assert [L[i][i] for i in range(3)] != [degrees[v] for v in ["a", "b", "c"]]
    # Off-diagonal is -1 exactly where an edge exists.
    for u in g.nodes():
        for v in g.nodes():
            if u != v:
                expected = -1.0 if g.has_edge(u, v) else 0.0
                assert L[index[u]][index[v]] == expected


def test_nodelist_permutes_the_laplacian():
    g = _labelled_path()
    default = fnx.laplacian_matrix(g).toarray().astype(float)
    reordered = fnx.laplacian_matrix(g, nodelist=["a", "b", "c"]).toarray().astype(float)
    assert not np.array_equal(default, reordered)          # a genuine permutation

    degrees = dict(g.degree())
    for i, v in enumerate(["a", "b", "c"]):
        assert abs(reordered[i][i] - degrees[v]) < 1e-9
    # Permutation preserves the trace and the row sums.
    assert abs(np.trace(reordered) - np.trace(default)) < 1e-9
    assert np.allclose(reordered.sum(axis=1), 0)


def test_weighted_laplacian_breaks_the_trace_identity():
    """laplacian_matrix reads `weight` by default, so trace(L) is 2*sum(weights)."""
    g = fnx.Graph(); g.add_edge(0, 1, weight=5); g.add_edge(1, 2, weight=2)

    weighted = fnx.laplacian_matrix(g).toarray().astype(float)
    assert np.trace(weighted) == 14                        # 2*(5+2), not 2*|E|
    assert abs(np.trace(weighted) - 2 * g.number_of_edges()) > 1e-9
    # Row sums stay zero regardless of weighting — that invariant is structural.
    assert np.allclose(weighted.sum(axis=1), 0)

    unweighted = fnx.laplacian_matrix(g, weight=None).toarray().astype(float)
    assert abs(np.trace(unweighted) - 2 * g.number_of_edges()) < 1e-9


def test_complete_graph_laplacian_spectrum_closed_form():
    # K_n Laplacian spectrum: 0 once, n with multiplicity n-1.
    for n in (4, 5, 6):
        evals = sorted(round(e, 6) for e in np.real(fnx.laplacian_spectrum(fnx.complete_graph(n))))
        assert evals[0] == 0
        assert all(abs(e - n) < 1e-6 for e in evals[1:])
