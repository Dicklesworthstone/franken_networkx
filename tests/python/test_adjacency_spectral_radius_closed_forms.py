"""Largest adjacency eigenvalue against closed forms and the degree bounds.

br-r37-c1-zu3o7. The spectral radius rho(G) is the largest eigenvalue of A. It
has exact values on several families and a universal bound that holds for every
graph:

    complete            rho(K_n)      = n - 1
    cycle               rho(C_n)      = 2
    complete bipartite  rho(K_{m,n})  = sqrt(m * n)
    d-regular           rho           = d          (Petersen: 3)
    universal           average degree <= rho <= maximum degree

This is distinct from br-r37-c1-5dkg5, which is Laplacian: the two spectra
coincide only on regular graphs, so a routine that silently returned Laplacian
eigenvalues would pass every regular-family assertion here and fail the star and
bipartite cases.

The universal bound is the load-bearing assertion, because it applies to
arbitrary random graphs where no closed form is available — it is what makes
this more than a table of five memorised numbers.
"""

import math

import numpy as np
import pytest

import franken_networkx as fnx


def _spectral_radius(graph):
    return float(max(np.array(fnx.adjacency_spectrum(graph)).real))


@pytest.mark.parametrize("n", [2, 3, 4, 5, 6, 7, 8, 10])
def test_complete_graph_spectral_radius_is_n_minus_one(n):
    assert _spectral_radius(fnx.complete_graph(n)) == pytest.approx(n - 1)


@pytest.mark.parametrize("n", [3, 4, 5, 6, 7, 8, 9, 12])
def test_cycle_graph_spectral_radius_is_two(n):
    assert _spectral_radius(fnx.cycle_graph(n)) == pytest.approx(2.0)


@pytest.mark.parametrize("m,n", [(1, 1), (1, 4), (2, 3), (3, 3), (3, 5), (4, 6)])
def test_complete_bipartite_spectral_radius_is_sqrt_mn(m, n):
    """Non-regular unless m == n, so this separates A from L."""
    assert _spectral_radius(fnx.complete_bipartite_graph(m, n)) == pytest.approx(
        math.sqrt(m * n)
    )


@pytest.mark.parametrize(
    "builder,degree",
    [
        (fnx.petersen_graph, 3),
        (lambda: fnx.cycle_graph(9), 2),
        (lambda: fnx.complete_graph(6), 5),
        (lambda: fnx.hypercube_graph(3), 3),
        (lambda: fnx.hypercube_graph(4), 4),
    ],
)
def test_regular_graph_spectral_radius_equals_its_degree(builder, degree):
    graph = builder()
    assert {d for _, d in graph.degree()} == {degree}, "fixture is not d-regular"
    assert _spectral_radius(graph) == pytest.approx(float(degree))


@pytest.mark.parametrize("seed", [1, 2, 3, 4, 5, 6, 7])
@pytest.mark.parametrize("probability", [0.2, 0.5])
def test_spectral_radius_lies_between_average_and_maximum_degree(seed, probability):
    """The universal bound, on graphs with no closed form available."""
    graph = fnx.erdos_renyi_graph(16, probability, seed=seed)
    degrees = [d for _, d in graph.degree()]
    if not degrees:
        pytest.skip("empty graph has no degree bounds to check")
    average = sum(degrees) / len(degrees)
    radius = _spectral_radius(graph)
    assert radius >= average - 1e-8, f"rho {radius} below average degree {average}"
    assert radius <= max(degrees) + 1e-8, f"rho {radius} above max degree {max(degrees)}"


@pytest.mark.parametrize("leaves", [2, 3, 4, 6, 9])
def test_star_graph_spectral_radius_is_sqrt_of_leaf_count(leaves):
    """S_n is K_{1,n}, so rho = sqrt(n) — NOT the degree n of its centre.

    The case most likely to catch a routine that returns a maximum degree, or a
    Laplacian eigenvalue, instead of the adjacency spectral radius.
    """
    assert _spectral_radius(fnx.star_graph(leaves)) == pytest.approx(
        math.sqrt(leaves)
    )


def test_empty_and_single_node_graphs():
    single = fnx.Graph()
    single.add_node(0)
    assert _spectral_radius(single) == pytest.approx(0.0, abs=1e-9)

    isolated = fnx.Graph()
    isolated.add_nodes_from(range(4))
    assert _spectral_radius(isolated) == pytest.approx(0.0, abs=1e-9)
