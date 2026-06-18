"""Cache-consistency guard for the edges(keys=True) read optimization (multigraphs).

MultiGraph/MultiDiGraph edges(keys=True) is served from edges_with_keys_cache,
keyed by (nodes_seq, edges_seq). It must invalidate on edge mutation or the keyed
view returns stale parallel-edge structure. This locks consistency without
depending on exact key VALUES (which need not survive a rebuild):

  * the keyed view's endpoint multiset == the plain edges() endpoint multiset;
  * len(edges(keys=True)) == number_of_edges();
  these hold after add-parallel-edge / second-parallel / remove / add-node+edge.

Completes the read-cache invalidation quartet (node_data_mirror, adjacency,
edges_with_data, edges_with_keys). No mocks: pure fnx self-consistency.
"""

from __future__ import annotations

import random

import pytest
import franken_networkx as fnx

_TYPES = [fnx.MultiGraph, fnx.MultiDiGraph]


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


def _endpoints(edge_iter, directed):
    def ep(u, v):
        return (u, v) if directed else tuple(sorted((u, v), key=str))
    return sorted(ep(e[0], e[1]) for e in edge_iter)


@pytest.mark.parametrize("cls", _TYPES)
@pytest.mark.parametrize("seed", range(12))
def test_edges_keys_cache_reflects_mutations(cls, seed):
    g, n = _build(cls, seed)
    directed = g.is_directed()

    def check():
        keyed = _endpoints(g.edges(keys=True), directed)
        plain = _endpoints(g.edges(), directed)
        assert keyed == plain                               # keyed view consistent
        assert len(list(g.edges(keys=True))) == g.number_of_edges()

    _ = list(g.edges(keys=True))   # warm the cache
    check()

    g.add_edge(0, 1, weight=1)     # parallel edge
    check()
    g.add_edge(0, 1, weight=2)     # second parallel
    check()
    g.remove_edge(0, 1)            # drop one parallel
    check()
    g.add_node(n + 100)
    g.add_edge(n + 100, 0, weight=3)
    check()
