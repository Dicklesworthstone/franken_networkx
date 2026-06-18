"""number_of_spanning_trees: Cayley + Matrix-Tree theorem + nx parity.

The spanning-tree count has strong closed-form / algebraic oracles:
  - **Cayley's formula**: K_n has n^(n-2) spanning trees.
  - **Cycle**: C_n has exactly n spanning trees; a tree has exactly 1.
  - **Matrix-Tree theorem (Kirchhoff)**: the count equals any (n-1)x(n-1)
    cofactor of the Laplacian (here det of the first principal minor).
These are independent of networkx; parity with networkx is also checked.

No mocks: real fnx and real networkx.
"""

from __future__ import annotations

import random

import numpy as np
import pytest
import networkx as nx
import franken_networkx as fnx


@pytest.mark.parametrize("n", [3, 4, 5, 6, 7])
def test_cayley_formula_complete_graph(n):
    # K_n has exactly n^(n-2) spanning trees.
    assert round(fnx.number_of_spanning_trees(fnx.complete_graph(n))) == n ** (n - 2)


@pytest.mark.parametrize("n", [3, 4, 5, 7])
def test_cycle_and_tree_counts(n):
    assert round(fnx.number_of_spanning_trees(fnx.cycle_graph(n))) == n
    assert round(fnx.number_of_spanning_trees(fnx.path_graph(n))) == 1
    assert round(fnx.number_of_spanning_trees(fnx.star_graph(n))) == 1


@pytest.mark.parametrize("seed", range(30))
def test_matrix_tree_theorem_and_nx_parity(seed):
    r = random.Random(seed)
    n = r.randint(4, 8)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.5]
    fg = fnx.Graph(); fg.add_nodes_from(range(n)); fg.add_edges_from(edges)
    ng = nx.Graph(); ng.add_nodes_from(range(n)); ng.add_edges_from(edges)
    if not fnx.is_connected(fg):
        pytest.skip("disconnected (0 spanning trees)")

    count = fnx.number_of_spanning_trees(fg)
    assert abs(count - nx.number_of_spanning_trees(ng)) < 1e-3

    # Matrix-Tree theorem: count == det of a first principal minor of the Laplacian.
    L = nx.laplacian_matrix(ng).toarray().astype(float)
    minor = np.delete(np.delete(L, 0, 0), 0, 1)
    assert abs(count - round(np.linalg.det(minor))) < 0.5
