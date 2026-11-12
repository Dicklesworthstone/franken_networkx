"""Triadic census partition invariant + Eulerian degree characterization.

Two theorem-anchored checks:
  - **Triadic census**: every unordered triple of nodes is exactly one of the
    16 directed triad types, so the census values must sum to C(n, 3) and span
    all 16 type keys.
  - **Eulerian characterization**: a connected undirected graph (with edges) has
    an Eulerian circuit iff every vertex has even degree.
Both are oracle-free; networkx parity is also checked.

No mocks: real fnx and real networkx.
"""

from __future__ import annotations

import itertools
import math
import random

import pytest
import networkx as nx
import franken_networkx as fnx


@pytest.mark.parametrize("seed", range(30))
def test_triadic_census_partition_and_parity(seed):
    r = random.Random(seed)
    n = r.randint(4, 8)
    edges = [(u, v) for u in range(n) for v in range(n) if u != v and r.random() < 0.35]
    fg = fnx.DiGraph(edges); fg.add_nodes_from(range(n))
    ng = nx.DiGraph(edges); ng.add_nodes_from(range(n))

    census = fnx.triadic_census(fg)
    assert census == nx.triadic_census(ng)
    # Partition invariant: the 16 triad types cover every triple exactly once.
    assert sum(census.values()) == math.comb(n, 3)
    assert len(census) == 16


@pytest.mark.parametrize("seed", range(30))
def test_eulerian_degree_characterization(seed):
    r = random.Random(seed)
    n = r.randint(4, 8)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.5]
    fg = fnx.Graph(); fg.add_nodes_from(range(n)); fg.add_edges_from(edges)
    ng = nx.Graph(); ng.add_nodes_from(range(n)); ng.add_edges_from(edges)

    is_eul = fnx.is_eulerian(fg)
    assert is_eul == nx.is_eulerian(ng)
    if fg.number_of_edges() > 0:
        # Euler's characterization: connected + all-even-degree iff Eulerian.
        char = fnx.is_connected(fg) and all(d % 2 == 0 for _, d in fg.degree())
        assert is_eul == char


def test_eulerian_circuit_uses_every_edge_once():
    # A graph with an Eulerian circuit: the circuit traverses each edge exactly once.
    g = fnx.cycle_graph(6)  # all even degree, connected
    assert fnx.is_eulerian(g)
    circuit = list(fnx.eulerian_circuit(g))
    assert len(circuit) == g.number_of_edges()
    used = sorted(tuple(sorted(e)) for e in circuit)
    assert used == sorted(tuple(sorted(e)) for e in g.edges())


def _is_closed_walk(circuit):
    """Consecutive edges chain end-to-start, and the last returns to the first."""
    for (_, head), (tail, _) in zip(circuit, circuit[1:]):
        if head != tail:
            return False
    return bool(circuit) and circuit[0][0] == circuit[-1][1]


@pytest.mark.parametrize(
    "builder",
    [lambda: fnx.cycle_graph(n) for n in (4, 5, 6, 7, 8, 9, 10)]
    + [lambda n=n: fnx.complete_graph(n) for n in (5, 7, 9)],
)
def test_eulerian_circuit_is_a_closed_walk(builder):
    """An edge MULTISET says nothing about the order.

    The named C_6 check compares the circuit's edges against the graph's; a
    randomly shuffled copy of the same circuit satisfies that and is not a walk
    at all. Only 1 of the 30 random draws above is Eulerian, so this uses a
    family built to be Eulerian: cycles, and complete graphs on an odd number
    of nodes (every degree n-1 is even).
    """
    g = builder()
    assert fnx.is_eulerian(g)

    circuit = list(fnx.eulerian_circuit(g))
    # Every edge exactly once...
    assert sorted(tuple(sorted(e)) for e in circuit) == sorted(
        tuple(sorted(e)) for e in g.edges()
    )
    # ...traversed as one closed walk, which the multiset cannot show.
    assert _is_closed_walk(circuit)


def _count_empty_triples(digraph):
    """Triples with no arc among them — an independent census of type '003'."""
    nodes = sorted(digraph.nodes())
    return sum(
        1
        for a, b, c in itertools.combinations(nodes, 3)
        if not any(
            digraph.has_edge(x, y)
            for x, y in ((a, b), (b, a), (a, c), (c, a), (b, c), (c, b))
        )
    )


@pytest.mark.parametrize("seed", range(30))
def test_triadic_census_empty_type_against_an_independent_count(seed):
    """The per-type counts are parity-only; the totals are the oracle-free part.

    Counting one type independently checks a VALUE rather than the sum. '003'
    is the type a direct count can produce unambiguously.
    """
    r = random.Random(seed)
    n = r.randint(4, 8)
    edges = [(u, v) for u in range(n) for v in range(n) if u != v and r.random() < 0.35]
    fg = fnx.DiGraph(edges); fg.add_nodes_from(range(n))

    assert fnx.triadic_census(fg)["003"] == _count_empty_triples(fg)


def test_empty_triple_count_is_usually_nonzero():
    """Guards the check above: 0 == 0 would hold for any implementation."""
    nonzero = 0
    for seed in range(30):
        r = random.Random(seed)
        n = r.randint(4, 8)
        edges = [(u, v) for u in range(n) for v in range(n) if u != v and r.random() < 0.35]
        fg = fnx.DiGraph(edges); fg.add_nodes_from(range(n))
        if _count_empty_triples(fg):
            nonzero += 1
    # Measured 20 of 30.
    assert nonzero >= 10, f"only {nonzero} of 30 draws contain an empty triple"
