"""Oracle-free output-validity for minimum cut and Eulerian circuit.

* ``minimum_cut`` returns a partition (S, T) with the source in S, the sink
  in T, disjoint and covering, and its value equals the total capacity of
  the S->T crossing edges
* ``eulerian_circuit`` traverses every edge exactly once, consecutive edges
  share an endpoint, and the walk is closed

br-r37-c1-ey1h1
"""

from __future__ import annotations

import random
from collections import Counter

import pytest
import networkx as nx
import franken_networkx as fnx


def _capacitated_digraph(seed, p=0.4):
    rng = random.Random(seed)
    n = rng.randint(4, 8)
    g = fnx.DiGraph()
    g.add_nodes_from(range(n))
    for u in range(n):
        for v in range(n):
            if u != v and rng.random() < p:
                g.add_edge(u, v, capacity=rng.randint(1, 9))
    return g, n


@pytest.mark.parametrize("seed", range(40))
def test_minimum_cut_partition_is_valid(seed):
    g, n = _capacitated_digraph(seed)
    for s in range(min(2, n)):
        for t in range(n):
            if s == t:
                continue
            value, (S, T) = fnx.minimum_cut(g, s, t)
            assert s in S and t in T
            assert not (S & T)
            assert (S | T) == set(range(n))
            crossing = sum(
                g[u][v]["capacity"]
                for u in S for v in g.successors(u) if v in T
            )
            assert crossing == pytest.approx(value)


def _make_eulerian(seed):
    rng = random.Random(seed)
    n = rng.randint(4, 8)
    g = fnx.cycle_graph(n)
    for _ in range(rng.randint(0, 2)):
        cyc = rng.sample(range(n), rng.randint(3, n))
        for i in range(len(cyc)):
            g.add_edge(cyc[i], cyc[(i + 1) % len(cyc)])
    return g


@pytest.mark.parametrize("seed", range(60))
def test_eulerian_circuit_is_valid(seed):
    g = _make_eulerian(seed)
    if not fnx.is_eulerian(g):
        pytest.skip("not eulerian")
    circuit = list(fnx.eulerian_circuit(g))
    # Uses every edge exactly once (multiplicity-aware).
    used = Counter(tuple(sorted(e[:2])) for e in circuit)
    available = Counter(tuple(sorted(e)) for e in g.edges())
    assert used == available
    # Consecutive edges share an endpoint, and the walk closes.
    assert all(circuit[i][1] == circuit[i + 1][0] for i in range(len(circuit) - 1))
    if circuit:
        assert circuit[-1][1] == circuit[0][0]
