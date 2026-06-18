"""Estrada index closed form (trace of the adjacency matrix exponential).

The Estrada index is the sum of e^lambda over the adjacency eigenvalues, i.e.
the trace of exp(A):
  estrada_index(G) = sum_i e^{lambda_i}.
This cross-checks estrada_index against the adjacency spectrum (existing tests
cover nx parity / numerical precision, not the eigenvalue definition):
  - random graphs: estrada == sum of e^lambda over eigvalsh(A);
  - K_n: estrada == (n-1)*e^{-1} + e^{n-1} (spectrum is {-1}^(n-1), {n-1});
  - empty graph: estrada == n (all eigenvalues 0 -> e^0 = 1 each).
Oracle-free, independent of networkx.

No mocks: real fnx (numpy for the spectrum).
"""

from __future__ import annotations

import math
import random

import numpy as np
import pytest
import franken_networkx as fnx


@pytest.mark.parametrize("seed", range(25))
def test_estrada_equals_sum_exp_eigenvalues(seed):
    r = random.Random(seed)
    n = r.randint(4, 8)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.45]
    g = fnx.Graph(); g.add_nodes_from(range(n)); g.add_edges_from(edges)
    A = fnx.adjacency_matrix(g).toarray().astype(float)
    expected = sum(math.exp(e) for e in np.linalg.eigvalsh(A))
    assert fnx.estrada_index(g) == pytest.approx(expected, abs=1e-4)


@pytest.mark.parametrize("n", [3, 4, 5, 6])
def test_complete_graph_estrada_closed_form(n):
    # K_n adjacency spectrum: -1 with multiplicity n-1, and n-1 once.
    expected = (n - 1) * math.exp(-1) + math.exp(n - 1)
    assert fnx.estrada_index(fnx.complete_graph(n)) == pytest.approx(expected, abs=1e-3)


@pytest.mark.parametrize("n", [3, 4, 5])
def test_empty_graph_estrada_is_n(n):
    # No edges -> all eigenvalues 0 -> e^0 summed n times.
    assert fnx.estrada_index(fnx.empty_graph(n)) == pytest.approx(n, abs=1e-6)
