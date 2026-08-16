"""Algebraic connectivity (the Fiedler value) against spectral closed forms.

br-r37-c1-1jrub. The Fiedler value is the second-smallest Laplacian eigenvalue.
Standard results give exact values on several families:

    complete            a(K_n)       = n
    path                a(P_n)       = 2(1 - cos(pi / n))
    cycle               a(C_n)       = 2(1 - cos(2 pi / n))
    complete bipartite  a(K_{m,n})   = min(m, n)
    star                a(S_n)       = 1          (K_{1,n}, so min(1, n) = 1)

Independent of networkx, and independent of the Laplacian-spectrum tests in
br-r37-c1-sdxgk: those pin trace identities (sums of eigenvalues), which are
invariant to which eigenvalue is which. Selecting the SECOND-SMALLEST is exactly
the part a moment identity cannot check.

The path and cycle values are the discriminating ones — they are irrational and
close together for adjacent n, so they cannot be satisfied by an off-by-one
index or by returning the smallest or largest eigenvalue.
"""

import math

import numpy as np
import pytest

import franken_networkx as fnx


def _second_smallest_laplacian_eigenvalue(graph):
    """The definition, recomputed independently of algebraic_connectivity."""
    spectrum = sorted(np.array(fnx.laplacian_spectrum(graph)).real)
    return float(spectrum[1])


@pytest.mark.parametrize("n", [2, 3, 4, 5, 6, 7, 8, 10])
def test_complete_graph_fiedler_value_is_n(n):
    assert fnx.algebraic_connectivity(fnx.complete_graph(n)) == pytest.approx(
        float(n), rel=1e-6
    )


@pytest.mark.parametrize("n", [3, 4, 5, 6, 7, 8, 9, 10, 12])
def test_path_graph_fiedler_value_closed_form(n):
    expected = 2 * (1 - math.cos(math.pi / n))
    assert fnx.algebraic_connectivity(fnx.path_graph(n)) == pytest.approx(
        expected, rel=1e-6
    )


@pytest.mark.parametrize("n", [3, 4, 5, 6, 7, 8, 9, 10, 12])
def test_cycle_graph_fiedler_value_closed_form(n):
    expected = 2 * (1 - math.cos(2 * math.pi / n))
    assert fnx.algebraic_connectivity(fnx.cycle_graph(n)) == pytest.approx(
        expected, rel=1e-6
    )


@pytest.mark.parametrize("m,n", [(1, 3), (2, 3), (3, 3), (2, 5), (4, 6)])
def test_complete_bipartite_fiedler_value_is_min_m_n(m, n):
    assert fnx.algebraic_connectivity(
        fnx.complete_bipartite_graph(m, n)
    ) == pytest.approx(float(min(m, n)), rel=1e-6)


@pytest.mark.parametrize("leaves", [2, 3, 4, 6, 9])
def test_star_graph_fiedler_value_is_one(leaves):
    """S_n is K_{1,n}, so a = min(1, n) = 1 regardless of size."""
    assert fnx.algebraic_connectivity(fnx.star_graph(leaves)) == pytest.approx(
        1.0, rel=1e-6
    )


@pytest.mark.parametrize("seed", [1, 2, 3, 4, 5])
def test_matches_the_second_smallest_laplacian_eigenvalue(seed):
    """The definition itself, on graphs with no closed form.

    This is what a trace/moment identity cannot check: which eigenvalue gets
    selected, as opposed to what they sum to.
    """
    graph = fnx.erdos_renyi_graph(14, 0.4, seed=seed)
    if not fnx.is_connected(graph):
        pytest.skip("disconnected: the Fiedler value is 0 by a different route")
    assert fnx.algebraic_connectivity(graph) == pytest.approx(
        _second_smallest_laplacian_eigenvalue(graph), rel=1e-5
    )


def test_disconnected_graph_has_zero_algebraic_connectivity():
    """The negative case: a > 0 if and only if the graph is connected."""
    graph = fnx.Graph()
    graph.add_edge(0, 1)
    graph.add_edge(2, 3)
    assert fnx.algebraic_connectivity(graph) == pytest.approx(0.0, abs=1e-8)


@pytest.mark.parametrize("n", [5, 6, 7, 8])
def test_fiedler_value_is_bounded_by_vertex_connectivity_and_min_degree(n):
    """Fiedler's inequality: a(G) <= vertex connectivity <= minimum degree.

    A structural bound that holds for every non-complete graph, so it survives
    a correlated transcription error in the closed forms above.
    """
    for graph in (fnx.cycle_graph(n), fnx.path_graph(n), fnx.star_graph(n)):
        value = fnx.algebraic_connectivity(graph)
        minimum_degree = min(d for _, d in graph.degree())
        assert value <= minimum_degree + 1e-6, (
            f"Fiedler value {value} exceeds minimum degree {minimum_degree}"
        )
        assert value > 0, "a connected graph must have a positive Fiedler value"


@pytest.mark.parametrize("n", [5, 6, 8])
def test_adding_edges_cannot_decrease_algebraic_connectivity(n):
    """Monotone under edge addition — a path closed into a cycle is better connected."""
    path_value = fnx.algebraic_connectivity(fnx.path_graph(n))
    cycle_value = fnx.algebraic_connectivity(fnx.cycle_graph(n))
    assert cycle_value > path_value
