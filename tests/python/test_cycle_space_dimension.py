"""Cycle-space dimension (circuit rank / first Betti number) invariants.

The cycle space of a graph has dimension E - V + C (edges minus nodes plus
connected components) — the circuit rank, a.k.a. the first Betti number. So
``cycle_basis`` must return exactly that many independent cycles, each a real
cycle, and the graph is a forest iff the circuit rank is 0. These are
topological invariants, independent of networkx (the existing cycle_basis tests
cover DFS-order parity, not the dimension).

Counting the cycles and checking each one is genuinely a cycle does not make the
result a *basis*: a routine that returned the same cycle ``rank`` times would
satisfy both. The defining property is linear independence over GF(2), which is
asserted here directly. Independence plus a cardinality equal to the dimension
is what makes the returned set a basis, so no separate spanning check is needed.

No mocks: real fnx.
"""

from __future__ import annotations

import random

import pytest
import franken_networkx as fnx


def _edge_index(g):
    """Map each undirected edge to a distinct bit position (self-loops included)."""
    return {frozenset((u, v)): i for i, (u, v) in enumerate(g.edges())}


def _cycle_vector(cycle, index):
    """The cycle's edge-indicator vector in GF(2)^E, as a bitmask."""
    k = len(cycle)
    vec = 0
    for i in range(k):
        vec ^= 1 << index[frozenset((cycle[i], cycle[(i + 1) % k]))]
    return vec


def _gf2_rank(vectors):
    """Rank over GF(2) by xor elimination — computed without consulting fnx."""
    basis = []
    for vec in vectors:
        for b in basis:
            vec = min(vec, vec ^ b)
        if vec:
            basis.append(vec)
            basis.sort(reverse=True)
    return len(basis)


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


@pytest.mark.parametrize("seed", range(40))
def test_basis_cycles_are_linearly_independent(seed):
    """The property that makes it a *basis* and not just a bag of cycles."""
    r = random.Random(seed)
    n = r.randint(5, 12)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.4]
    g = fnx.Graph(); g.add_nodes_from(range(n)); g.add_edges_from(edges)

    index = _edge_index(g)
    cb = fnx.cycle_basis(g)
    vectors = [_cycle_vector(cyc, index) for cyc in cb]
    # No cycle is a GF(2) sum of the others — duplicates or dependent cycles
    # would drop the rank below the returned count.
    assert _gf2_rank(vectors) == len(cb)
    # And the count is the dimension, so the independent set spans: a basis.
    E, V, C = g.number_of_edges(), g.number_of_nodes(), fnx.number_connected_components(g)
    assert len(cb) == E - V + C


def test_self_loops_are_length_one_cycles():
    """A self-loop is a cycle-space element of its own; E - V + C still holds."""
    g = fnx.Graph(); g.add_edges_from([(0, 1), (1, 2)]); g.add_edge(0, 0); g.add_edge(2, 2)

    E, V, C = g.number_of_edges(), g.number_of_nodes(), fnx.number_connected_components(g)
    assert (E, V, C) == (4, 3, 1)
    cb = fnx.cycle_basis(g)
    assert len(cb) == E - V + C == 2
    # Each loop shows up as a one-node cycle on a node that carries a self-loop.
    assert sorted(cyc[0] for cyc in cb) == [0, 2]
    assert all(len(cyc) == 1 and g.has_edge(cyc[0], cyc[0]) for cyc in cb)
    assert fnx.is_forest(g) is False
    assert _gf2_rank([_cycle_vector(c, _edge_index(g)) for c in cb]) == 2


def test_disconnected_union_pins_the_component_term():
    """C > 1 with known per-component ranks, so the +C term carries real weight."""
    g = fnx.Graph()
    g.add_edges_from([(("a", i), ("a", (i + 1) % 3)) for i in range(3)])   # C_3  -> 1
    g.add_edges_from([(("b", i), ("b", (i + 1) % 4)) for i in range(4)])   # C_4  -> 1
    g.add_edges_from([(("c", i), ("c", j))                                 # K_4  -> 3
                      for i in range(4) for j in range(i + 1, 4)])
    g.add_edges_from([(("d", 0), ("d", 1)), (("d", 1), ("d", 2))])         # path -> 0
    g.add_nodes_from([("e", 0), ("e", 1)])                                 # isolates -> 0

    E, V, C = g.number_of_edges(), g.number_of_nodes(), fnx.number_connected_components(g)
    assert C == 6                                    # 4 edge components + 2 isolates
    assert E - V + C == 1 + 1 + 3                    # ranks add over components
    cb = fnx.cycle_basis(g)
    assert len(cb) == 5
    assert _gf2_rank([_cycle_vector(c, _edge_index(g)) for c in cb]) == 5
    # Every basis cycle lives inside a single component — cycles cannot cross.
    assert all(len({node[0] for node in cyc}) == 1 for cyc in cb)


def test_known_cycle_ranks():
    assert len(fnx.cycle_basis(fnx.path_graph(6))) == 0          # tree: rank 0
    assert len(fnx.cycle_basis(fnx.cycle_graph(7))) == 1         # one cycle
    # K_n: rank = C(n,2) - n + 1.
    for n in (4, 5, 6):
        k = fnx.complete_graph(n)
        expected = k.number_of_edges() - n + 1
        assert len(fnx.cycle_basis(k)) == expected
