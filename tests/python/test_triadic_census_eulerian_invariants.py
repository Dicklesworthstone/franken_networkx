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
