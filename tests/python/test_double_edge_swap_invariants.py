"""double_edge_swap / connected_double_edge_swap degree-preservation invariants.

The double-edge-swap rewiring functions are randomized (and fnx's RNG diverges
from networkx's, so they cannot be parity-tested), but they have exact defining
invariants:
  - a double edge swap removes two edges and adds two, so it PRESERVES every
    node's degree (hence the whole degree sequence) and the edge count;
  - connected_double_edge_swap additionally PRESERVES connectivity.
These hold for whatever random rewiring is performed.

No mocks: real fnx.
"""

from __future__ import annotations

import random

import pytest
import franken_networkx as fnx


def _graph(seed):
    r = random.Random(seed)
    n = r.randint(8, 14)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.4]
    g = fnx.Graph(); g.add_nodes_from(range(n)); g.add_edges_from(edges)
    return g


@pytest.mark.parametrize("seed", range(40))
def test_double_edge_swap_preserves_degree_sequence(seed):
    g = _graph(seed)
    if g.number_of_edges() < 2:
        pytest.skip("too few edges to swap")
    deg_before = sorted(d for _, d in g.degree())
    edges_before = g.number_of_edges()

    h = g.copy()
    fnx.double_edge_swap(h, nswap=5, max_tries=200, seed=seed)

    assert sorted(d for _, d in h.degree()) == deg_before   # degree sequence kept
    assert h.number_of_edges() == edges_before               # edge count kept


@pytest.mark.parametrize("seed", range(40))
def test_connected_swap_preserves_degree_and_connectivity(seed):
    g = _graph(seed)
    if g.number_of_edges() < 2 or not fnx.is_connected(g):
        pytest.skip("not connected / too few edges")
    deg_before = sorted(d for _, d in g.degree())
    edges_before = g.number_of_edges()

    h = g.copy()
    fnx.connected_double_edge_swap(h, nswap=5, seed=seed)

    assert sorted(d for _, d in h.degree()) == deg_before
    assert h.number_of_edges() == edges_before
    assert fnx.is_connected(h)                                # connectivity kept


def test_swap_keeps_no_self_loops_or_multi_edges():
    # A simple graph stays simple after swaps (no self-loops, no parallel edges).
    g = fnx.gnm_random_graph(12, 24, seed=3)
    h = g.copy()
    fnx.double_edge_swap(h, nswap=10, max_tries=500, seed=3)
    assert fnx.number_of_selfloops(h) == 0
    assert not h.is_multigraph()
    assert h.number_of_edges() == g.number_of_edges()
