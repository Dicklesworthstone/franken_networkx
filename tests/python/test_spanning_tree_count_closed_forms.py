"""Spanning-tree counts against Cayley's formula and the Matrix-Tree theorem.

br-r37-c1-fp5tx. Two independent ground truths, neither of which consults
networkx:

    Cayley       tau(K_n) = n^(n-2)
    cycle        tau(C_n) = n            deleting any one of the n edges leaves a tree
    any tree     tau(T)   = 1            it is its own only spanning tree
    Matrix-Tree  tau(G)   = det of ANY first principal minor of the Laplacian
                            (delete one row and the matching column)

Cayley and Matrix-Tree are the interesting pair: Cayley is a closed form for one
family, while Matrix-Tree is a general theorem that applies to every connected
graph, including random ones where no formula exists. A routine that special-cased
complete graphs would satisfy the first and fail the second.

The Matrix-Tree check also pins a subtler property: the determinant is the same
whichever row/column you delete. That is a real theorem, not an implementation
detail, so it is asserted across several deletion choices.
"""

import math

import numpy as np
import pytest

import franken_networkx as fnx


def _matrix_tree_count(graph, deleted_index=0):
    """tau(G) via the Matrix-Tree theorem, computed independently."""
    nodes = list(graph)
    size = len(nodes)
    laplacian = np.zeros((size, size), dtype=float)
    index = {node: i for i, node in enumerate(nodes)}
    for node in nodes:
        laplacian[index[node], index[node]] = graph.degree(node)
    for u, v in graph.edges():
        laplacian[index[u], index[v]] -= 1
        laplacian[index[v], index[u]] -= 1
    keep = [i for i in range(size) if i != deleted_index]
    minor = laplacian[np.ix_(keep, keep)]
    return float(np.linalg.det(minor))


@pytest.mark.parametrize("n", [2, 3, 4, 5, 6, 7, 8])
def test_complete_graph_matches_cayleys_formula(n):
    assert fnx.number_of_spanning_trees(fnx.complete_graph(n)) == pytest.approx(
        float(n ** (n - 2)), rel=1e-7
    )


@pytest.mark.parametrize("n", [3, 4, 5, 6, 7, 8, 10, 12])
def test_cycle_graph_has_exactly_n_spanning_trees(n):
    """Deleting any single edge of C_n leaves a spanning tree, and only that."""
    assert fnx.number_of_spanning_trees(fnx.cycle_graph(n)) == pytest.approx(
        float(n), rel=1e-9
    )


@pytest.mark.parametrize(
    "builder",
    [
        lambda: fnx.path_graph(6),
        lambda: fnx.path_graph(11),
        lambda: fnx.star_graph(5),
        lambda: fnx.star_graph(9),
        lambda: fnx.balanced_tree(2, 3),
    ],
)
def test_a_tree_has_exactly_one_spanning_tree(builder):
    assert fnx.number_of_spanning_trees(builder()) == pytest.approx(1.0, rel=1e-7)


@pytest.mark.parametrize(
    "builder",
    [
        lambda: fnx.complete_graph(5),
        lambda: fnx.complete_graph(7),
        lambda: fnx.cycle_graph(8),
        lambda: fnx.path_graph(7),
        lambda: fnx.star_graph(6),
        lambda: fnx.complete_bipartite_graph(3, 4),
        lambda: fnx.petersen_graph(),
        lambda: fnx.erdos_renyi_graph(11, 0.5, seed=3),
        lambda: fnx.erdos_renyi_graph(12, 0.6, seed=4),
    ],
)
def test_matrix_tree_theorem_on_arbitrary_connected_graphs(builder):
    """The general theorem — covers graphs with no closed form available."""
    graph = builder()
    if not fnx.is_connected(graph):
        pytest.skip("fixture is disconnected; tau would be 0 by a different route")
    assert fnx.number_of_spanning_trees(graph) == pytest.approx(
        _matrix_tree_count(graph), rel=1e-6
    )


@pytest.mark.parametrize("deleted_index", [0, 1, 2, 3])
def test_matrix_tree_minor_is_independent_of_which_row_is_deleted(deleted_index):
    """A real theorem, not an implementation detail — so it is asserted."""
    graph = fnx.erdos_renyi_graph(10, 0.6, seed=9)
    if not fnx.is_connected(graph):
        pytest.skip("fixture is disconnected")
    reference = _matrix_tree_count(graph, deleted_index=0)
    assert _matrix_tree_count(graph, deleted_index=deleted_index) == pytest.approx(
        reference, rel=1e-6
    )
    assert fnx.number_of_spanning_trees(graph) == pytest.approx(reference, rel=1e-6)


@pytest.mark.parametrize("m,n", [(2, 2), (2, 3), (3, 3), (3, 4)])
def test_complete_bipartite_spanning_tree_closed_form(m, n):
    """tau(K_{m,n}) = m^(n-1) * n^(m-1) — a second independent closed form."""
    expected = float(m ** (n - 1) * n ** (m - 1))
    assert fnx.number_of_spanning_trees(
        fnx.complete_bipartite_graph(m, n)
    ) == pytest.approx(expected, rel=1e-7)


def test_disconnected_graph_has_no_spanning_tree():
    """The negative case: tau = 0 when the graph cannot be spanned by a tree."""
    graph = fnx.Graph()
    graph.add_edge(0, 1)
    graph.add_edge(2, 3)
    assert fnx.number_of_spanning_trees(graph) == pytest.approx(0.0, abs=1e-9)
