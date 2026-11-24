"""Directed node-connectivity divergence locks.

NetworkX 3.6.1 can over-report global node connectivity on some
strongly connected digraphs.  FrankenNetworkX returns the smaller value
also witnessed by NetworkX's own pairwise local-connectivity primitive.

br-r37-c1-npdzs
"""

from __future__ import annotations

from itertools import permutations

from networkx.algorithms.connectivity import local_node_connectivity
import networkx as nx
import pytest

import franken_networkx as fnx
from franken_networkx import _fnx

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


REROUTING_EDGES = [
    ("s", "a"),
    ("s", "d"),
    ("a", "b"),
    ("a", "c"),
    ("d", "b"),
    ("b", "t"),
    ("c", "t"),
]


def _rerouting_graph(module, graph_type):
    graph = getattr(module, graph_type)()
    graph.add_nodes_from(["s", "a", "b", "c", "d", "t"])
    graph.add_edges_from(REROUTING_EDGES)
    return graph


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph"])
def test_native_local_connectivity_can_reroute_an_earlier_path(graph_type):
    actual = _rerouting_graph(fnx, graph_type)
    reference = _rerouting_graph(nx, graph_type)
    # Greedily keeping s-a-b-t consumes both internal vertices required by
    # the optimum. Residual rerouting instead finds s-a-c-t and s-d-b-t.
    assert local_node_connectivity(reference, "s", "t") == 2
    assert _fnx.node_connectivity(actual, "s", "t") == 2
    assert fnx.node_connectivity(actual, "s", "t") == 2

    # A direct edge contributes one additional path, without excluding any
    # internal vertex. It must neither vanish nor have infinite capacity.
    actual.add_edge("s", "t")
    reference.add_edge("s", "t")
    assert local_node_connectivity(reference, "s", "t") == 3
    assert _fnx.node_connectivity(actual, "s", "t") == 3
    assert fnx.node_connectivity(actual, "s", "t") == 3


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph"])
def test_native_average_connectivity_uses_exact_independent_pair_flows(graph_type):
    actual = _rerouting_graph(fnx, graph_type)
    reference = _rerouting_graph(nx, graph_type)
    for add_direct_edge in (False, True):
        if add_direct_edge:
            actual.add_edge("s", "t")
            reference.add_edge("s", "t")
        expected = nx.average_node_connectivity(reference)
        assert _fnx.average_node_connectivity(actual) == expected
        assert fnx.average_node_connectivity(actual) == expected
        # Repeated queries must not retain residual capacities from an
        # earlier pair or an earlier call.
        assert _fnx.average_node_connectivity(actual) == expected


@pytest.mark.parametrize("graph_type", ["Graph", "MultiGraph"])
@pytest.mark.parametrize("selected", [("t", "s"), ("t", "s", "a")])
def test_exact_pair_matrix_agrees_with_small_subset_queries(graph_type, selected):
    actual = _rerouting_graph(fnx, graph_type)
    reference = _rerouting_graph(nx, graph_type)
    for add_direct_edge in (False, True):
        if add_direct_edge:
            actual.add_edge("s", "t")
            reference.add_edge("s", "t")
        expected = nx.all_pairs_node_connectivity(reference)
        complete = fnx.all_pairs_node_connectivity(actual)
        assert complete == expected
        assert complete["s"]["t"] == (3 if add_direct_edge else 2)
        # The small Graph subset selects a different native entry point.
        # Both routes must compute exact flows, including when a generator
        # yields repeated nodes or reverses the graph's insertion order.
        subset = fnx.all_pairs_node_connectivity(
            actual, nbunch=(node for node in (*selected, selected[0]))
        )
        assert subset == {
            source: {
                target: expected[source][target]
                for target in selected
                if source != target
            }
            for source in selected
        }


def test_both_native_directed_global_entry_points_are_exact():
    actual = _rerouting_graph(fnx, "DiGraph")
    reference = _rerouting_graph(nx, "DiGraph")
    for graph in (actual, reference):
        graph.add_edges_from((right, left) for left, right in REROUTING_EDGES)
    expected = min(
        local_node_connectivity(reference, source, target)
        for source, target in permutations(reference, 2)
    )
    assert expected == 2
    assert _fnx.node_connectivity(actual) == expected
    assert _fnx.global_node_connectivity(actual) == expected
    assert fnx.node_connectivity(actual) == expected


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph"])
def test_native_global_connectivity_ignores_self_loops(graph_type):
    graph = getattr(fnx, graph_type)()
    graph.add_nodes_from(range(4))
    graph.add_edges_from(permutations(range(4), 2))
    assert _fnx.node_connectivity(graph) == 3
    assert _fnx.global_node_connectivity(graph) == 3
    graph.add_edges_from((node, node) for node in range(4))
    assert _fnx.node_connectivity(graph) == 3
    assert _fnx.global_node_connectivity(graph) == 3
