"""Node-label parity for ``minimum_spanning_tree`` (br-r37-c1-esr5k).

On graphs built via ``add_nodes_from(range(n))`` (lazy int display keys),
the native MST kernel emitted canonical STRING node keys ('0','1',...)
instead of the original ints — changing the node-label *type* vs nx even
though the edge set and weights matched. The wrapper now rebuilds the
tree from G's actual nodes when the kernel returns foreign-typed nodes.
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _signature(G):
    return (sorted(G.nodes()), sorted(tuple(sorted(e)) for e in G.edges()))


def _multi_signature(G):
    return (
        type(G).__name__,
        G.is_multigraph(),
        list(G.nodes(data=True)),
        list(G.edges(keys=True, data=True)),
        dict(G.graph),
    )


def test_range_built_graph_preserves_int_node_labels():
    g = fnx.Graph()
    g.add_nodes_from(range(6))
    for u, v, w in [(0, 1, 3), (1, 2, 1), (2, 0, 2), (2, 3, 4), (3, 4, 1), (0, 5, 2)]:
        g.add_edge(u, v, weight=w)
    mst = fnx.minimum_spanning_tree(g, weight="weight")
    assert all(isinstance(n, int) for n in mst.nodes())


@pytest.mark.parametrize("seed", range(50))
def test_unique_mst_exact_parity_with_networkx(seed):
    # Distinct weights -> the MST is unique, so node + edge sets must match nx
    # exactly (including node-label type).
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
    assert _signature(fnx.minimum_spanning_tree(fg, weight="weight")) == _signature(
        nx.minimum_spanning_tree(ng, weight="weight")
    )


def test_from_edgelist_graph_unaffected():
    g = fnx.Graph([(0, 1), (1, 2), (2, 3)])
    mst = fnx.minimum_spanning_tree(g)
    assert all(isinstance(n, int) for n in mst.nodes())


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
    fmst = fnx.minimum_spanning_tree(fg, weight="weight")
    nmst = nx.minimum_spanning_tree(ng, weight="weight")
    assert dict(fmst.nodes(data=True)) == dict(nmst.nodes(data=True))
    assert fmst.graph == nmst.graph


def test_multigraph_mst_preserves_keys_type_attrs_and_matches_networkx():
    fg = fnx.MultiGraph()
    ng = nx.MultiGraph()
    for g in (fg, ng):
        g.graph["name"] = "keyed-mst"
        g.add_node(0, color="red")
        g.add_node(1, color="blue")
        g.add_node(2, color="green")
        g.add_node(3, color="yellow")
        g.add_edge(0, 1, key="slow", weight=10.0, tag="drop")
        g.add_edge(0, 1, key="fast", weight=1.0, tag="keep")
        g.add_edge(1, 2, key="mid", weight=2.0, tag="keep")
        g.add_edge(0, 2, key="heavy", weight=3.0, tag="drop")
        g.add_edge(2, 3, weight=1.5, tag="auto")
        g.add_edge(0, 3, key="expensive", weight=99.0, tag="drop")

    assert _multi_signature(fnx.minimum_spanning_tree(fg, weight="weight")) == _multi_signature(
        nx.minimum_spanning_tree(ng, weight="weight")
    )


def test_multigraph_mst_nonnumeric_weight_uses_networkx_error_contract():
    g = fnx.MultiGraph()
    g.add_edge(0, 1, key="a", weight="1")
    g.add_edge(1, 2, key="b", weight="2")
    g.add_edge(0, 2, key="c", weight="3")

    with pytest.raises(TypeError, match="must be real number"):
        fnx.minimum_spanning_tree(g, weight="weight")
