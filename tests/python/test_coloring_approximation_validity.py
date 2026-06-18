"""Coloring + approximation: validity invariants + networkx parity.

A graph coloring is *proper* iff no edge is monochromatic; a vertex cover must
touch every edge; an independent set must contain no edge; a dominating set
must dominate every node. These validity invariants hold regardless of any
reference implementation. greedy_color's deterministic strategies additionally
match networkx exactly.

No mocks: real fnx and real networkx on random graphs.
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx

_STRATEGIES = [
    "largest_first", "smallest_last", "independent_set", "DSATUR",
    "connected_sequential_bfs", "connected_sequential_dfs",
    "saturation_largest_first",
]


def _graph(seed):
    r = random.Random(seed)
    n = r.randint(6, 12)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.4]
    fg = fnx.Graph(); fg.add_nodes_from(range(n)); fg.add_edges_from(edges)
    ng = nx.Graph(); ng.add_nodes_from(range(n)); ng.add_edges_from(edges)
    return fg, ng, n, edges


@pytest.mark.parametrize("strategy", _STRATEGIES)
@pytest.mark.parametrize("seed", range(20))
def test_greedy_color_parity_and_validity(strategy, seed):
    fg, ng, n, edges = _graph(seed)
    coloring = fnx.greedy_color(fg, strategy=strategy)
    assert coloring == nx.greedy_color(ng, strategy=strategy)
    # Proper coloring: no edge is monochromatic.
    assert all(coloring[u] != coloring[v] for u, v in edges)


@pytest.mark.parametrize("seed", range(40))
def test_approximation_outputs_are_valid(seed):
    fg, ng, n, edges = _graph(seed)
    adj = {i: set() for i in range(n)}
    for u, v in edges:
        adj[u].add(v)
        adj[v].add(u)

    # Vertex cover touches every edge.
    vc = fnx.approximation.min_weighted_vertex_cover(fg)
    assert all(u in vc or v in vc for u, v in edges)

    # Independent set contains no edge.
    mis = fnx.approximation.maximum_independent_set(fg)
    assert all(not (u in mis and v in mis) for u, v in edges)

    # Dominating set dominates every node.
    ds = fnx.approximation.min_weighted_dominating_set(fg)
    assert all(node in ds or (adj[node] & ds) for node in range(n))
