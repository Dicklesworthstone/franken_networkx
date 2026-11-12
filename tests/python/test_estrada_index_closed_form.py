"""Estrada index against its eigenvalue definition and closed forms.

br-r37-c1-byf5b. Existing coverage is parity/precision against networkx. This
asserts the spectral definition instead:

    EE(G) = sum over eigenvalues lambda of A of exp(lambda) = trace(exp(A))

with two consequences used as ground truth:

    complete   EE(K_n) = (n-1) e^{-1} + e^{n-1}
               K_n has eigenvalues n-1 (once) and -1 (n-1 times)
    empty      EE(E_n) = n     all eigenvalues are 0, so every term is e^0 = 1

The trace identity is the useful one to keep in view: because trace(exp(A)) is
also the sum over k of trace(A^k)/k!, and trace(A^k) counts closed walks of
length k, EE is a weighted count of closed walks. That is why the empty-graph
case is n and not 0 — a subtle enough result that an implementation returning 0
looks plausible.
"""

import math

import numpy as np
import pytest

import franken_networkx as fnx

SIZES = [2, 3, 4, 5, 6, 7, 8]


def _from_spectrum(graph):
    """EE recomputed from the adjacency spectrum, independent of estrada_index."""
    eigenvalues = np.array(fnx.adjacency_spectrum(graph)).real
    return float(np.exp(eigenvalues).sum())


@pytest.mark.parametrize("n", SIZES)
def test_complete_graph_estrada_closed_form(n):
    expected = (n - 1) * math.exp(-1) + math.exp(n - 1)
    assert fnx.estrada_index(fnx.complete_graph(n)) == pytest.approx(expected, rel=1e-9)


@pytest.mark.parametrize("n", [1, 2, 3, 5, 8])
def test_empty_graph_estrada_index_is_the_node_count(n):
    """Every eigenvalue is 0, so EE = n * e^0 = n — NOT 0."""
    graph = fnx.Graph()
    graph.add_nodes_from(range(n))
    assert fnx.estrada_index(graph) == pytest.approx(n)


@pytest.mark.parametrize(
    "builder",
    [
        lambda: fnx.path_graph(6),
        lambda: fnx.cycle_graph(7),
        lambda: fnx.star_graph(5),
        lambda: fnx.complete_bipartite_graph(3, 4),
        lambda: fnx.petersen_graph(),
        lambda: fnx.erdos_renyi_graph(12, 0.3, seed=5),
        lambda: fnx.erdos_renyi_graph(12, 0.5, seed=6),
    ],
)
def test_estrada_index_matches_the_adjacency_spectrum(builder):
    graph = builder()
    assert fnx.estrada_index(graph) == pytest.approx(_from_spectrum(graph), rel=1e-8)


@pytest.mark.parametrize("n", [3, 4, 5, 6])
def test_estrada_index_is_at_least_the_node_count(n):
    """Structural bound: EE >= n for any graph, with equality only when empty.

    By AM-GM on exp over a spectrum summing to 0 (no self-loops). An
    implementation that dropped a term or summed the wrong axis violates this
    while still producing a plausible-looking number.
    """
    for graph in (fnx.path_graph(n), fnx.cycle_graph(n), fnx.complete_graph(n)):
        assert fnx.estrada_index(graph) >= n - 1e-9

    empty = fnx.Graph()
    empty.add_nodes_from(range(n))
    assert fnx.estrada_index(empty) == pytest.approx(n)


@pytest.mark.parametrize("n", [4, 5, 6, 7])
def test_adding_an_edge_strictly_increases_the_estrada_index(n):
    """Monotonicity — more closed walks means a larger weighted count."""
    graph = fnx.path_graph(n)
    before = fnx.estrada_index(graph)
    graph.add_edge(0, n - 1)  # close the path into a cycle
    assert fnx.estrada_index(graph) > before
