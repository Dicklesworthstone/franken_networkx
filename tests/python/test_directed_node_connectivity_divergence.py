"""Directed node-connectivity divergence locks.

NetworkX 3.6.1 can over-report global node connectivity on some
strongly connected digraphs.  FrankenNetworkX returns the smaller value
also witnessed by NetworkX's own pairwise local-connectivity primitive.

br-r37-c1-npdzs
"""

from __future__ import annotations

from networkx.algorithms.connectivity import local_node_connectivity
import networkx as nx

import franken_networkx as fnx

WITNESS_EDGES = [
    (0, 1),
    (0, 3),
    (1, 0),
    (1, 2),
    (2, 3),
    (2, 5),
    (3, 0),
    (3, 4),
    (3, 5),
    (4, 0),
    (4, 1),
    (5, 1),
    (5, 4),
]


def _digraph(module):
    graph = module.DiGraph()
    graph.add_nodes_from(range(6))
    graph.add_edges_from(WITNESS_EDGES)
    return graph


def test_directed_node_connectivity_keeps_more_correct_value_than_nx():
    fnx_graph = _digraph(fnx)
    nx_graph = _digraph(nx)

    assert fnx.is_strongly_connected(fnx_graph)
    assert nx.is_strongly_connected(nx_graph)

    pairwise_min = min(
        local_node_connectivity(nx_graph, source, target)
        for source in nx_graph
        for target in nx_graph
        if source != target
    )
    assert pairwise_min == 1

    without_one = nx_graph.copy()
    without_one.remove_node(1)
    assert not nx.is_strongly_connected(without_one)

    assert fnx.node_connectivity(fnx_graph) == pairwise_min
    assert nx.node_connectivity(nx_graph) == 2
