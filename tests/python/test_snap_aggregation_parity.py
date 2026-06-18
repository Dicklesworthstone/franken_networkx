"""Differential parity for ``snap_aggregation``.

SNAP summarization groups nodes that share the chosen node attributes and
have matching edge-type participation, producing a "supergraph". Supernode
names are auto-generated, so this compares the order/name-invariant set of
member groups plus the supernode/superedge counts.

br-r37-c1-5vzei
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _build(seed, lib, colors=("A", "B"), rels=("rel1", "rel2")):
    rng = random.Random(seed)
    n = rng.randint(5, 9)
    g = lib.Graph()
    for i in range(n):
        g.add_node(i, color=rng.choice(colors))
    for u in range(n):
        for v in range(u + 1, n):
            if rng.random() < 0.4:
                g.add_edge(u, v, type=rng.choice(rels))
    return g


def _member_groups(summary):
    return sorted(tuple(sorted(d["group"])) for _, d in summary.nodes(data=True))


@pytest.mark.parametrize("seed", range(40))
def test_snap_aggregation_member_groups_match_networkx(seed):
    fg = _build(seed, fnx)
    ng = _build(seed, nx)
    fr = fnx.snap_aggregation(fg, node_attributes=["color"], edge_attributes=["type"])
    nr = nx.snap_aggregation(ng, node_attributes=["color"], edge_attributes=["type"])
    assert _member_groups(fr) == _member_groups(nr)
    assert fr.number_of_nodes() == nr.number_of_nodes()
    assert fr.number_of_edges() == nr.number_of_edges()


def test_snap_aggregation_golden():
    # Two color classes, each an internal clique, joined by one edge.
    edges_same = [(0, 1), (1, 2), (0, 2)]   # color A clique
    edges_same2 = [(3, 4), (4, 5), (3, 5)]  # color B clique
    fg = fnx.Graph()
    ng = nx.Graph()
    for g in (fg, ng):
        for node in (0, 1, 2):
            g.add_node(node, color="A")
        for node in (3, 4, 5):
            g.add_node(node, color="B")
        for u, v in edges_same + edges_same2 + [(2, 3)]:
            g.add_edge(u, v, type="r")
    fr = fnx.snap_aggregation(fg, node_attributes=["color"], edge_attributes=["type"])
    nr = nx.snap_aggregation(ng, node_attributes=["color"], edge_attributes=["type"])
    assert _member_groups(fr) == _member_groups(nr)
