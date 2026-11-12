"""complete_to_chordal_graph correctness invariants.

The chordal completion adds fill-in edges to make a graph chordal. Its output
must satisfy the defining properties (the existing test covers nx parity; this
pins the output's correctness independent of nx):
  - the result IS chordal;
  - the result is a supergraph of the input (every original edge survives) on
    the same node set;
  - an already-chordal graph is returned unchanged (no fill edges);
  - a chordless cycle C_n (n >= 4) becomes chordal after completion.
Oracle-free.

No mocks: real fnx.
"""

from __future__ import annotations

import random

import pytest
import franken_networkx as fnx


def _edge_set(g):
    return {tuple(sorted((u, v))) for u, v in g.edges()}


def _graph(seed):
    r = random.Random(seed)
    n = r.randint(5, 10)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.35]
    g = fnx.Graph(); g.add_nodes_from(range(n)); g.add_edges_from(edges)
    return g


@pytest.mark.parametrize("seed", range(40))
def test_completion_is_chordal_supergraph(seed):
    g = _graph(seed)
    h, _alpha = fnx.complete_to_chordal_graph(g)
    # The completion is chordal.
    assert fnx.is_chordal(h)
    # It is a supergraph on the same node set.
    assert _edge_set(g) <= _edge_set(h)
    assert set(h.nodes()) == set(g.nodes())


@pytest.mark.parametrize("seed", range(40))
def test_already_chordal_is_unchanged(seed):
    g = _graph(seed)
    if not fnx.is_chordal(g):
        pytest.skip("not already chordal")
    h, _alpha = fnx.complete_to_chordal_graph(g)
    # A chordal graph needs no fill-in edges.
    assert _edge_set(h) == _edge_set(g)


@pytest.mark.parametrize("n", [4, 5, 6, 7])
def test_chordless_cycle_becomes_chordal(n):
    c = fnx.cycle_graph(n)
    assert not fnx.is_chordal(c)               # C_n (n>=4) has no chord
    h, _alpha = fnx.complete_to_chordal_graph(c)
    assert fnx.is_chordal(h)
    assert _edge_set(c) <= _edge_set(h)
