"""Cycle-space dimension (circuit rank / first Betti number) invariants.

The cycle space of a graph has dimension E - V + C (edges minus nodes plus
connected components) — the circuit rank, a.k.a. the first Betti number. So
``cycle_basis`` must return exactly that many independent cycles, each a real
cycle, and the graph is a forest iff the circuit rank is 0. These are
topological invariants, independent of networkx (the existing cycle_basis tests
cover DFS-order parity, not the dimension).

No mocks: real fnx.
"""

from __future__ import annotations

import random

import pytest
import franken_networkx as fnx


@pytest.mark.parametrize("seed", range(40))
def test_cycle_basis_dimension_is_circuit_rank(seed):
    r = random.Random(seed)
    n = r.randint(5, 10)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.4]
    g = fnx.Graph(); g.add_nodes_from(range(n)); g.add_edges_from(edges)

    E, V, C = g.number_of_edges(), g.number_of_nodes(), fnx.number_connected_components(g)
    rank = E - V + C
    cb = fnx.cycle_basis(g)
    # Cycle space dimension = circuit rank.
    assert len(cb) == rank
    # The graph is a forest iff the circuit rank is 0.
    assert fnx.is_forest(g) == (rank == 0)


@pytest.mark.parametrize("seed", range(40))
def test_each_basis_cycle_is_a_real_cycle(seed):
    r = random.Random(seed)
    n = r.randint(5, 10)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.45]
    g = fnx.Graph(); g.add_nodes_from(range(n)); g.add_edges_from(edges)
    for cyc in fnx.cycle_basis(g):
        k = len(cyc)
        assert k >= 3                                  # simple cycles have >= 3 nodes
        # Consecutive nodes (wrapping) are adjacent — it's a genuine cycle.
        assert all(g.has_edge(cyc[i], cyc[(i + 1) % k]) for i in range(k))
        assert len(set(cyc)) == k                       # no repeated node


def test_known_cycle_ranks():
    assert len(fnx.cycle_basis(fnx.path_graph(6))) == 0          # tree: rank 0
    assert len(fnx.cycle_basis(fnx.cycle_graph(7))) == 1         # one cycle
    # K_n: rank = C(n,2) - n + 1.
    for n in (4, 5, 6):
        k = fnx.complete_graph(n)
        expected = k.number_of_edges() - n + 1
        assert len(fnx.cycle_basis(k)) == expected
