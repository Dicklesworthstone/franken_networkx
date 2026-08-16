"""Adjacency spectrum validated from the EIGENVALUE side, via trace identities.

br-r37-c1-8mqpt. `trace(A^k)` counts closed walks of length k, and it also
equals the k-th power sum of the eigenvalues. That gives three ground-truth
identities that need no reference implementation:

    sum lambda      = trace(A)   = 0            (no self-loops: zero diagonal)
    sum lambda^2    = trace(A^2) = 2|E|         (each edge traversed both ways)
    sum lambda^3    = trace(A^3) = 6 * triangles(G)
                                  (each triangle: 3 starting points x 2 directions)

br-r37-c1-imp6j already checks these against the matrix A directly. This checks
them from `adjacency_spectrum`, so the two together pin the eigenvalues and the
matrix against each other — a spectrum computed from a subtly wrong matrix
passes the matrix-side test and fails here.

The third identity is the sharp one: it is the only one of the three that
depends on the eigenvalue SIGNS, so a routine returning absolute values or a
sorted-magnitude ordering satisfies the first two and fails this.
"""

import math

import numpy as np
import pytest

import franken_networkx as fnx

GRAPHS = {
    "path_6": lambda: fnx.path_graph(6),
    "path_9": lambda: fnx.path_graph(9),
    "cycle_6": lambda: fnx.cycle_graph(6),
    "cycle_7": lambda: fnx.cycle_graph(7),
    "complete_5": lambda: fnx.complete_graph(5),
    "complete_7": lambda: fnx.complete_graph(7),
    "star_6": lambda: fnx.star_graph(6),
    "bipartite_3_4": lambda: fnx.complete_bipartite_graph(3, 4),
    "petersen": lambda: fnx.petersen_graph(),
    "erdos_12_p3": lambda: fnx.erdos_renyi_graph(12, 0.3, seed=11),
    "erdos_14_p5": lambda: fnx.erdos_renyi_graph(14, 0.5, seed=12),
}


def _spectrum(graph):
    return np.array(fnx.adjacency_spectrum(graph)).real


def _triangle_count(graph):
    return sum(fnx.triangles(graph).values()) // 3


@pytest.mark.parametrize("name", sorted(GRAPHS))
def test_first_moment_is_zero(name):
    """trace(A) = 0 because a simple graph has a zero diagonal."""
    assert _spectrum(GRAPHS[name]()).sum() == pytest.approx(0.0, abs=1e-8)


@pytest.mark.parametrize("name", sorted(GRAPHS))
def test_second_moment_is_twice_the_edge_count(name):
    graph = GRAPHS[name]()
    assert (_spectrum(graph) ** 2).sum() == pytest.approx(
        2 * graph.number_of_edges(), rel=1e-9
    )


@pytest.mark.parametrize("name", sorted(GRAPHS))
def test_third_moment_is_six_times_the_triangle_count(name):
    """The sign-sensitive identity: absolute values pass moments 1-2, not this."""
    graph = GRAPHS[name]()
    assert (_spectrum(graph) ** 3).sum() == pytest.approx(
        6 * _triangle_count(graph), abs=1e-6
    )


@pytest.mark.parametrize("n", [2, 3, 4, 5, 6, 7, 8])
def test_complete_graph_spectrum_is_the_known_pair(n):
    """K_n has eigenvalue n-1 once and -1 with multiplicity n-1."""
    eigenvalues = sorted(_spectrum(fnx.complete_graph(n)))
    assert eigenvalues[-1] == pytest.approx(n - 1)
    for value in eigenvalues[:-1]:
        assert value == pytest.approx(-1.0)


@pytest.mark.parametrize("name", sorted(GRAPHS))
def test_spectrum_has_one_eigenvalue_per_node(name):
    """Guards against a truncated or padded spectrum silently passing the sums."""
    graph = GRAPHS[name]()
    assert len(_spectrum(graph)) == graph.number_of_nodes()


@pytest.mark.parametrize("m,n", [(2, 3), (3, 4), (1, 5), (4, 4)])
def test_complete_bipartite_third_moment_vanishes(m, n):
    """A bipartite graph is triangle-free, so trace(A^3) must be exactly 0.

    Independent of the triangle counter — the expectation comes from
    bipartiteness, so this also fails if `triangles` and the spectrum ever
    disagree.
    """
    spectrum = _spectrum(fnx.complete_bipartite_graph(m, n))
    assert (spectrum**3).sum() == pytest.approx(0.0, abs=1e-6)
    assert (spectrum**2).sum() == pytest.approx(2 * m * n, rel=1e-9)
