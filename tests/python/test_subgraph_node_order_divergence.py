"""Behavior lock for subgraph/edge_subgraph node order.

NetworkX's ``G.subgraph(nbunch)`` / ``edge_subgraph`` return a view whose node
iteration order is produced by ``FilterAtlas.__iter__``. That iterator has a
size-based optimization: when ``2 * len(induced_nodes) < len(G)`` it iterates
the *induced node set* (a Python ``set`` — CPython hash-table slot order)
instead of the original graph's insertion order. So on a large graph the
node order of a small induced subgraph is whatever CPython's ``set`` iteration
happens to be (e.g. ``list({8,3,1,5}) == [8, 1, 3, 5]``); on a small graph
(``2*|sub| >= |G|``) it falls back to original-graph order.

franken_networkx mirrors that size-adaptive order: parent insertion order for
large induced sets, and CPython set iteration for small induced sets. This is
both parity-critical and performance-critical because small subgraph views can
iterate the selected node set instead of scanning every parent node.
"""

import networkx as nx
import franken_networkx as fnx

import pytest


def _build(mod, n_extra):
    g = mod.Graph()
    # Deliberately non-monotonic insertion order.
    g.add_nodes_from([5, 3, 8, 1] + list(range(100, 100 + n_extra)))
    g.add_edges_from([(5, 3), (3, 8), (8, 1), (3, 1)])
    return g


SUBSET = [8, 3, 1, 5]
SUBSET_SET = {8, 3, 1, 5}


def _original_order(g):
    return [n for n in g.nodes() if n in SUBSET_SET]


@pytest.mark.parametrize("n_extra", [0, 1, 2, 3])  # 2*4 >= total -> nx uses original order
def test_subgraph_order_matches_nx_when_no_set_shortcut(n_extra):
    gn = _build(nx, n_extra)
    gf = _build(fnx, n_extra)
    assert list(gn.subgraph(SUBSET).nodes()) == list(gf.subgraph(SUBSET).nodes())
    # ...and it is the stable original-graph order.
    assert list(gf.subgraph(SUBSET).nodes()) == _original_order(gf)


@pytest.mark.parametrize("n_extra", [0, 1, 2, 3])
def test_fnx_subgraph_order_uses_original_order_without_set_shortcut(n_extra):
    gf = _build(fnx, n_extra)
    expected = _original_order(gf)
    assert list(gf.subgraph(SUBSET).nodes()) == expected
    assert list(gf.subgraph([1, 5, 8, 3]).nodes()) == expected  # nbunch order irrelevant
    assert list(gf.edge_subgraph([(5, 3), (3, 8), (8, 1)]).nodes()) == expected


def test_set_shortcut_regime_matches_networkx():
    # In the shortcut regime (2*|sub| < |G|) nx iterates the induced set in
    # CPython hash order. fnx deliberately mirrors that behavior because it is
    # observable through list(view.nodes()) and avoids O(parent) scans.
    gn = _build(nx, 8)   # total 12, subset 4 -> 8 < 12 -> shortcut on
    gf = _build(fnx, 8)
    nx_order = list(gn.subgraph(SUBSET).nodes())
    fnx_order = list(gf.subgraph(SUBSET).nodes())
    assert set(nx_order) == set(fnx_order) == SUBSET_SET
    assert fnx_order == nx_order == list(SUBSET_SET)
    assert list(gf.subgraph(SUBSET).copy().nodes()) == list(
        gn.subgraph(SUBSET).copy().nodes()
    )
    assert fnx_order != _original_order(gf)


def test_edge_subgraph_set_shortcut_regime_matches_networkx():
    gn = _build(nx, 8)
    gf = _build(fnx, 8)
    edges = [(5, 3), (3, 8), (8, 1)]
    assert list(gf.edge_subgraph(edges).nodes()) == list(
        gn.edge_subgraph(edges).nodes()
    )


def test_subgraph_set_shortcut_still_tracks_parent_mutations():
    gn = _build(nx, 8)
    gf = _build(fnx, 8)
    sn = gn.subgraph(SUBSET)
    sf = gf.subgraph(SUBSET)
    gn.remove_node(8)
    gf.remove_node(8)
    assert list(sf.nodes()) == list(sn.nodes())
    gn.add_node(8)
    gf.add_node(8)
    assert list(sf.nodes()) == list(sn.nodes())
    gn.add_node(999)
    gf.add_node(999)
    assert list(sf.nodes()) == list(sn.nodes())


def test_custom_subgraph_view_node_set_and_lambda_order_match_nx():
    gn = _build(nx, 8)
    gf = _build(fnx, 8)

    class NodeSetFilter:
        def __init__(self, nodes):
            self.nodes = set(nodes)

        def __call__(self, node):
            return node in self.nodes

    node_filter_nx = NodeSetFilter(SUBSET)
    node_filter_fnx = NodeSetFilter(SUBSET)
    assert list(fnx.subgraph_view(gf, filter_node=node_filter_fnx).nodes()) == list(
        nx.subgraph_view(gn, filter_node=node_filter_nx).nodes()
    )

    lambda_nx = lambda node: node in SUBSET_SET
    lambda_fnx = lambda node: node in SUBSET_SET
    assert list(fnx.subgraph_view(gf, filter_node=lambda_fnx).nodes()) == list(
        nx.subgraph_view(gn, filter_node=lambda_nx).nodes()
    )
    assert list(fnx.subgraph_view(gf, filter_node=lambda_fnx).nodes()) == _original_order(gf)
