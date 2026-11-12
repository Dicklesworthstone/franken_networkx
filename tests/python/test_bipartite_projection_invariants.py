"""Bipartite projection: differential parity + output validity.

``projected_graph`` and ``weighted_projected_graph`` collapse a bipartite
graph onto one side. Combines parity vs networkx with the defining
metamorphic relation: two same-side nodes are adjacent in the projection
iff they share a neighbour on the other side, and the weighted projection's
edge weight is the number of shared neighbours.

br-r37-c1-v3aoo
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx
from franken_networkx.algorithms import bipartite as fnx_bip
from networkx.algorithms import bipartite as nx_bip


def _bipartite_pair(seed, p=0.5):
    rng = random.Random(seed)
    a = rng.randint(3, 5)
    b = rng.randint(3, 5)
    fg = fnx.Graph()
    ng = nx.Graph()
    top = list(range(a))
    bot = list(range(a, a + b))
    for g in (fg, ng):
        g.add_nodes_from(top, bipartite=0)
        g.add_nodes_from(bot, bipartite=1)
    for u in top:
        for v in bot:
            if rng.random() < p:
                fg.add_edge(u, v)
                ng.add_edge(u, v)
    return fg, ng, top


def _edge_set(g):
    return sorted(tuple(sorted(e)) for e in g.edges())


@pytest.mark.parametrize("seed", range(40))
def test_projected_graph_matches_networkx(seed):
    fg, ng, top = _bipartite_pair(seed)
    fp = fnx_bip.projected_graph(fg, top)
    np_ = nx_bip.projected_graph(ng, top)
    assert sorted(fp.nodes()) == sorted(np_.nodes())
    assert _edge_set(fp) == _edge_set(np_)


@pytest.mark.parametrize("seed", range(40))
def test_projection_connects_iff_shared_neighbor(seed):
    fg, _, top = _bipartite_pair(seed)
    proj = fnx_bip.projected_graph(fg, top)
    adj = {x: set(fg.neighbors(x)) for x in fg}
    for u in top:
        for v in top:
            if u < v:
                assert proj.has_edge(u, v) == bool(adj[u] & adj[v])


@pytest.mark.parametrize("seed", range(40))
def test_weighted_projection_weight_is_shared_neighbor_count(seed):
    fg, ng, top = _bipartite_pair(seed)
    fw = fnx_bip.weighted_projected_graph(fg, top)
    nw = nx_bip.weighted_projected_graph(ng, top)
    fw_edges = {tuple(sorted(e)): fw[e[0]][e[1]]["weight"] for e in fw.edges()}
    nw_edges = {tuple(sorted(e)): nw[e[0]][e[1]]["weight"] for e in nw.edges()}
    assert fw_edges == nw_edges
    # The weight counts shared neighbours.
    adj = {x: set(fg.neighbors(x)) for x in fg}
    for (u, v), w in fw_edges.items():
        assert w == len(adj[u] & adj[v])
