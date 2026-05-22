"""Regression coverage for ``max_weight_clique`` node-weight totals."""

from __future__ import annotations

import franken_networkx as fnx
import networkx as nx


def test_max_weight_clique_sums_live_node_weights_like_networkx():
    fnx_graph = fnx.complete_graph(5)
    nx_graph = nx.complete_graph(5)
    for node in range(5):
        fnx_graph.nodes[node]["weight"] = node + 1
        nx_graph.nodes[node]["weight"] = node + 1

    assert fnx.max_weight_clique(fnx_graph) == nx.max_weight_clique(nx_graph)


def test_max_weight_clique_custom_weight_attribute_matches_networkx():
    fnx_graph = fnx.Graph()
    nx_graph = nx.Graph()
    edges = [(0, 1), (1, 2), (2, 0), (2, 3)]
    fnx_graph.add_edges_from(edges)
    nx_graph.add_edges_from(edges)
    weights = {0: 2, 1: 4, 2: 8, 3: 100}
    for node, value in weights.items():
        fnx_graph.nodes[node]["score"] = value
        nx_graph.nodes[node]["score"] = value

    assert fnx.max_weight_clique(fnx_graph, weight="score") == nx.max_weight_clique(
        nx_graph, weight="score"
    )
