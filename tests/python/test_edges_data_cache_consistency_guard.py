"""Cache-consistency guard for the edges(data=...) read optimization.

edges(data=True) is served from edges_with_data_cache, keyed by
(nodes_seq, edges_seq). The subtle risk: an edge ATTR mutation
(g[u][v]['weight'] = X) is not a structural change — if it does not invalidate
the cache, edges(data=True) serves STALE attribute data. This locks consistency
vs the live graph (and a freshly-built graph) after each mutation kind:

  * add an edge;
  * change an existing edge's attr (the staleness-prone case);
  * remove an edge;
  * add a node + incident edge.

Completes the read-cache invalidation triple (node_data_mirror, adjacency,
edges_with_data). No mocks: pure fnx self-consistency.
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


def _edata(g):
    """Order-insensitive (endpoints, sorted-attrs) multiset of edges(data=True).

    The undirected orientation sort uses ``key=str`` so it is robust to mixed
    node-key types; original endpoint values are preserved in the tuple.
    """
    def key(u, v):
        return (u, v) if g.is_directed() else tuple(sorted((u, v), key=str))
    return sorted(
        (key(u, v), tuple(sorted(d.items()))) for u, v, d in g.edges(data=True)
    )


@pytest.mark.parametrize("cls", _TYPES)
@pytest.mark.parametrize("seed", range(12))
def test_edges_data_reflects_mutations(cls, seed):
    g, n = _build(cls, seed)

    # Warm the edges(data) cache.
    _ = _edata(g)

    # 1) add an edge.
    g.add_edge(0, n - 1, weight=42)
    assert ((0, n - 1) if g.is_directed() else tuple(sorted((0, n - 1))),
            (("weight", 42),)) in _edata(g)

    # 2) change an existing edge's attr -> MUST be reflected (staleness-prone).
    #    Only for simple graphs, where g[u][v] IS the edge attr dict.
    if not g.is_multigraph():
        some = next(iter(g.edges()))
        u, v = some[0], some[1]
        g[u][v]["weight"] = 777
        assert any(attrs == (("weight", 777),) for _, attrs in _edata(g))

    # 3) remove an edge.
    g.remove_edge(0, n - 1)
    ek = (0, n - 1) if g.is_directed() else tuple(sorted((0, n - 1)))
    assert all(not (k == ek and attrs == (("weight", 42),)) for k, attrs in _edata(g))

    # 4) add node + incident edge (int node -> no mixed-type key sort).
    znode = n + 100
    g.add_node(znode)
    g.add_edge(znode, 0, weight=1)

    # Cross-check vs a freshly built graph with the same edges+data.
    fresh = cls()
    fresh.add_nodes_from(g.nodes())
    fresh.add_edges_from(g.edges(data=True))
    assert _edata(fresh) == _edata(g)
