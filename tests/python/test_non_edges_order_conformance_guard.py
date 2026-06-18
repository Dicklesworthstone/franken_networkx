"""Order-exact conformance guard for non_edges (default-ebunch substrate).

non_edges underpins the default-ebunch link-prediction path; the swarm optimized
it to a native node-key-snapshot + raw-neighbor-row substrate (ledger 9143), whose
keep criterion is "preserving NetworkX set-pop pair semantics". This pins that:
non_edges(G) yields exactly nx's pairs in nx's order, for Graph and DiGraph,
including isolated nodes and near-complete graphs.

No dedicated non_edges test existed. No mocks: real fnx vs real networkx 3.x.
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


@pytest.mark.parametrize("cls,ncls", [(fnx.Graph, nx.Graph), (fnx.DiGraph, nx.DiGraph)])
@pytest.mark.parametrize("seed", range(20))
def test_non_edges_order_exact(cls, ncls, seed):
    r = random.Random(seed)
    n = r.randint(5, 12)
    directed = cls is fnx.DiGraph
    edges = [(u, v) for u in range(n) for v in range(n)
             if u != v and (directed or u < v) and r.random() < 0.4]
    fg = cls(list(edges)); fg.add_nodes_from(range(n))
    ng = ncls(list(edges)); ng.add_nodes_from(range(n))
    # nx's non_edges order is deterministic (set-pop over the adjacency) — match it.
    assert list(fnx.non_edges(fg)) == list(nx.non_edges(ng))


@pytest.mark.parametrize("cls,ncls", [(fnx.Graph, nx.Graph), (fnx.DiGraph, nx.DiGraph)])
def test_non_edges_edge_shapes(cls, ncls):
    # complete graph -> no non-edges; empty graph with isolated nodes -> all pairs.
    k = cls(); nk = ncls()
    k.add_nodes_from(range(4)); nk.add_nodes_from(range(4))
    directed = cls is fnx.DiGraph
    for u in range(4):
        for v in range(4):
            if u != v and (directed or u < v):
                k.add_edge(u, v); nk.add_edge(u, v)
    assert list(fnx.non_edges(k)) == list(nx.non_edges(nk))   # complete -> []

    iso = cls(); niso = ncls()
    iso.add_nodes_from(range(4)); niso.add_nodes_from(range(4))
    assert list(fnx.non_edges(iso)) == list(nx.non_edges(niso))  # all pairs
