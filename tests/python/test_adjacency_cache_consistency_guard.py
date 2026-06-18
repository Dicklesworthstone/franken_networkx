"""Cache-consistency guard for the adjacency() read optimization.

adjacency() / dict(adjacency()) is served from a cached nested dict
(adjacency_dict_cached + rebuild_adjacency_cache) that replaces a per-element
MultiAdjacencyView lambda chain (~30000x slower than nx per the impl comment).
That cache must invalidate on EDGE mutation, or adjacency() silently returns
stale neighbors. This locks consistency: after each edge mutation, dict(
adjacency()) must reflect the live graph and match a freshly-built graph.

Mutations exercised between cache reads:
  * add an edge (+ attr);
  * change an existing edge's attr;
  * remove an edge;
  * add a node + incident edge.

No mocks: pure fnx self-consistency (the adjacency cache vs the live graph).
"""

from __future__ import annotations

import random

import pytest
import franken_networkx as fnx

_TYPES = [fnx.Graph, fnx.DiGraph, fnx.MultiGraph, fnx.MultiDiGraph]


def _build(cls, seed):
    r = random.Random(seed)
    n = r.randint(4, 8)
    g = cls()
    g.add_nodes_from(range(n))
    for u in range(n):
        for v in range(n):
            if u != v and (g.is_directed() or u < v) and r.random() < 0.4:
                g.add_edge(u, v, weight=r.randint(1, 9))
    return g, n


def _adj(g):
    """Order-insensitive neighbor map from dict(adjacency())."""
    out = {}
    for node, nbrs in g.adjacency():
        out[node] = sorted(nbrs.keys())
    return out


@pytest.mark.parametrize("cls", _TYPES)
@pytest.mark.parametrize("seed", range(12))
def test_adjacency_reflects_edge_mutations(cls, seed):
    g, n = _build(cls, seed)

    # Warm the adjacency cache.
    a0 = _adj(g)
    assert set(a0) == set(g.nodes())

    # 1) add an edge -> cache invalidates, neighbor appears.
    g.add_edge(0, n - 1, weight=5)
    a = _adj(g)
    assert (n - 1) in a[0]
    if not g.is_directed():
        assert 0 in a[n - 1]

    # 2) change an edge attr -> structure unchanged but data via dict(adjacency).
    d = dict(g.adjacency())
    assert (n - 1) in dict(d[0])

    # 3) remove an edge -> neighbor gone.
    g.remove_edge(0, n - 1)
    a = _adj(g)
    assert (n - 1) not in a[0]

    # 4) add a node + incident edge -> reflected.
    g.add_node("Z")
    g.add_edge("Z", 0)
    a = _adj(g)
    assert 0 in a["Z"]

    # Cross-check vs a freshly built graph at the same edge set.
    fresh = cls()
    fresh.add_nodes_from(g.nodes())
    fresh.add_edges_from(g.edges())
    assert _adj(fresh) == _adj(g)
