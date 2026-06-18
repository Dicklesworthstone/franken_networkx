"""Node-label parity for ``maximum_spanning_tree`` (br-r37-c1-7t11e).

Sibling of br-r37-c1-esr5k: on graphs built via ``add_nodes_from(range(n))``
the native maximum-spanning-tree kernel emitted canonical string node keys
instead of the original ints. The wrapper now rebuilds the tree from G's
actual nodes when the kernel returns foreign-typed nodes.
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _signature(G):
    return (sorted(G.nodes()), sorted(tuple(sorted(e)) for e in G.edges()))


def test_range_built_graph_preserves_int_node_labels():
    g = fnx.Graph()
    g.add_nodes_from(range(6))
    for u, v, w in [(0, 1, 3), (1, 2, 1), (2, 0, 2), (2, 3, 4), (3, 4, 1), (0, 5, 2)]:
        g.add_edge(u, v, weight=w)
    mst = fnx.maximum_spanning_tree(g, weight="weight")
    assert all(isinstance(n, int) for n in mst.nodes())


@pytest.mark.parametrize("seed", range(50))
def test_unique_max_spanning_tree_exact_parity_with_networkx(seed):
    rng = random.Random(seed)
    n = rng.randint(5, 10)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if rng.random() < 0.45]
    weights = random.Random(seed + 1000).sample(range(1, 2000), len(edges))
    fg = fnx.Graph()
    ng = nx.Graph()
    fg.add_nodes_from(range(n))
    ng.add_nodes_from(range(n))
    for (u, v), w in zip(edges, weights):
        fg.add_edge(u, v, weight=w)
        ng.add_edge(u, v, weight=w)
    assert _signature(fnx.maximum_spanning_tree(fg, weight="weight")) == _signature(
        nx.maximum_spanning_tree(ng, weight="weight")
    )


def test_node_and_graph_attrs_preserved():
    fg = fnx.Graph()
    ng = nx.Graph()
    for g in (fg, ng):
        g.graph["name"] = "demo"
        g.add_node(0, color="red")
        g.add_node(1)
        g.add_node(2, color="blue")
        g.add_edge(0, 1, weight=1)
        g.add_edge(1, 2, weight=2)
    fmst = fnx.maximum_spanning_tree(fg, weight="weight")
    nmst = nx.maximum_spanning_tree(ng, weight="weight")
    assert dict(fmst.nodes(data=True)) == dict(nmst.nodes(data=True))
    assert fmst.graph == nmst.graph
