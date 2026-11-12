"""Laplacian spectrum validated from the EIGENVALUE side, via degree identities.

br-r37-c1-sdxgk. For L = D - A the trace identities tie the spectrum directly to
the degree sequence, with no reference implementation involved:

    sum mu    = trace(L)   = sum of degrees = 2|E|
    sum mu^2  = trace(L^2) = sum of d_i^2 + 2|E|
                             (diagonal d_i^2 terms, plus one 1 per ordered
                              adjacent pair from the off-diagonal -1 entries)

plus two structural facts: L is positive semidefinite, so every mu >= 0, and the
all-ones vector is always in the kernel, so the smallest eigenvalue is exactly 0.

br-r37-c1-5dkg5 covers the zero-multiplicity = component-count result. This
covers the moment/degree identities, which are independent of it: a spectrum
that got the connectivity structure right can still be wrong about magnitudes.

The second moment is the discriminating one — it is the only assertion here that
would notice A being dropped from L (leaving just D), since trace(D) = trace(L).
"""

import math

import numpy as np
import pytest

import franken_networkx as fnx

GRAPHS = {
    "path_6": lambda: fnx.path_graph(6),
    "path_10": lambda: fnx.path_graph(10),
    "cycle_6": lambda: fnx.cycle_graph(6),
    "cycle_9": lambda: fnx.cycle_graph(9),
    "complete_5": lambda: fnx.complete_graph(5),
    "complete_8": lambda: fnx.complete_graph(8),
    "star_7": lambda: fnx.star_graph(7),
    "bipartite_3_4": lambda: fnx.complete_bipartite_graph(3, 4),
    "petersen": lambda: fnx.petersen_graph(),
    "erdos_12_p3": lambda: fnx.erdos_renyi_graph(12, 0.3, seed=21),
    "erdos_15_p4": lambda: fnx.erdos_renyi_graph(15, 0.4, seed=22),
}


def _spectrum(graph):
    return np.array(fnx.laplacian_spectrum(graph)).real


def _degrees(graph):
    return [degree for _, degree in graph.degree()]


@pytest.mark.parametrize("name", sorted(GRAPHS))
def test_first_moment_is_twice_the_edge_count(name):
    graph = GRAPHS[name]()
    assert _spectrum(graph).sum() == pytest.approx(
        2 * graph.number_of_edges(), rel=1e-9
    )
    assert _spectrum(graph).sum() == pytest.approx(sum(_degrees(graph)), rel=1e-9)


@pytest.mark.parametrize("name", sorted(GRAPHS))
def test_second_moment_is_sum_of_squared_degrees_plus_twice_edges(name):
    """The identity that notices A being dropped from L = D - A."""
    graph = GRAPHS[name]()
    expected = sum(d * d for d in _degrees(graph)) + 2 * graph.number_of_edges()
    assert (_spectrum(graph) ** 2).sum() == pytest.approx(expected, rel=1e-8)


@pytest.mark.parametrize("name", sorted(GRAPHS))
def test_laplacian_is_positive_semidefinite_with_a_zero_eigenvalue(name):
    spectrum = sorted(_spectrum(GRAPHS[name]()))
    assert spectrum[0] == pytest.approx(0.0, abs=1e-8)
    assert min(spectrum) >= -1e-8, "L is PSD; no eigenvalue may be negative"


@pytest.mark.parametrize("n", [2, 3, 4, 5, 6, 7, 8])
def test_complete_graph_laplacian_spectrum_is_the_known_pair(n):
    """L(K_n) has eigenvalue 0 once and n with multiplicity n-1."""
    spectrum = sorted(_spectrum(fnx.complete_graph(n)))
    assert spectrum[0] == pytest.approx(0.0, abs=1e-8)
    for value in spectrum[1:]:
        assert value == pytest.approx(float(n))


@pytest.mark.parametrize("leaves", [2, 3, 4, 5, 7])
def test_star_graph_laplacian_spectrum_is_zero_ones_and_n_plus_one(leaves):
    """S_n: eigenvalues 0, 1 (multiplicity n-1) and n+1 — a non-regular check.

    Every other closed form here is on a regular or near-regular graph, where a
    routine confusing L with D would be harder to catch.
    """
    spectrum = sorted(_spectrum(fnx.star_graph(leaves)))
    assert spectrum[0] == pytest.approx(0.0, abs=1e-8)
    assert spectrum[-1] == pytest.approx(float(leaves + 1))
    for value in spectrum[1:-1]:
        assert value == pytest.approx(1.0)


@pytest.mark.parametrize("name", sorted(GRAPHS))
def test_spectrum_has_one_eigenvalue_per_node(name):
    graph = GRAPHS[name]()
    assert len(_spectrum(graph)) == graph.number_of_nodes()
