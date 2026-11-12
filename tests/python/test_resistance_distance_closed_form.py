"""Resistance distance closed form (pseudo-inverse of the Laplacian).

The effective resistance between u and v is a quadratic form in the Moore-Penrose
pseudo-inverse L^+ of the graph Laplacian:
  resistance(u, v) = L^+[u,u] + L^+[v,v] - 2 L^+[u,v].
This cross-checks resistance_distance against that definition and against known
closed forms (no dedicated invariant test exists):
  - random connected graphs: matches the L^+ quadratic form, and is symmetric;
  - tree: resistance == number of edges on the unique u-v path;
  - K_n: resistance == 2/n for every pair.
Oracle-free, independent of networkx.

No mocks: real fnx (numpy for the pseudo-inverse ground truth).
"""

from __future__ import annotations

import random

import pytest
import franken_networkx as fnx

np = pytest.importorskip("numpy")


@pytest.mark.parametrize("seed", range(20))
def test_resistance_matches_laplacian_pinv(seed):
    r = random.Random(seed)
    n = r.randint(4, 7)
    g = fnx.Graph(); g.add_nodes_from(range(n))
    for u in range(n):
        for v in range(u + 1, n):
            if r.random() < 0.55:
                g.add_edge(u, v)
    if not fnx.is_connected(g):
        pytest.skip("not connected")

    L = fnx.laplacian_matrix(g).toarray().astype(float)
    Lp = np.linalg.pinv(L)
    for u in range(n):
        for v in range(u + 1, n):
            expected = Lp[u, u] + Lp[v, v] - 2 * Lp[u, v]
            assert fnx.resistance_distance(g, u, v) == pytest.approx(expected, abs=1e-5)
            # Symmetric.
            assert fnx.resistance_distance(g, u, v) == pytest.approx(
                fnx.resistance_distance(g, v, u), abs=1e-9
            )


def test_tree_resistance_equals_path_length():
    # On a tree the effective resistance is the number of edges on the unique path.
    t = fnx.path_graph(6)
    for u in range(6):
        for v in range(u + 1, 6):
            assert fnx.resistance_distance(t, u, v) == pytest.approx(abs(u - v))


@pytest.mark.parametrize("n", [3, 4, 5, 6])
def test_complete_graph_resistance(n):
    # Every pair in K_n has effective resistance 2/n.
    k = fnx.complete_graph(n)
    for u in range(n):
        for v in range(u + 1, n):
            assert fnx.resistance_distance(k, u, v) == pytest.approx(2 / n)
