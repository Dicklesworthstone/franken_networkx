"""Multigraph edge endpoints remain logical nodes after storage-slot reuse."""

from copy import copy

import networkx as nx
import pytest

import franken_networkx as fnx


def _edge_views_match(graph, reference):
    for options in (
        {},
        {"keys": True},
        {"data": True},
        {"keys": True, "data": True},
        {"data": "weight", "default": -1},
        {"keys": True, "data": "weight", "default": -1},
    ):
        assert list(graph.edges(**options)) == list(reference.edges(**options))
    for u, v, key, attrs in graph.edges(keys=True, data=True):
        assert attrs is graph[u][v][key]


@pytest.mark.parametrize("batch", [False, True])
@pytest.mark.parametrize("reinsert", [False, True])
@pytest.mark.parametrize("cloning", ["original", "copy", "shallow_copy"])
def test_edge_views_preserve_endpoints_keys_and_live_attrs_after_compaction(
    batch, reinsert, cloning
):
    nodes = [("node", index) for index in range(5)]
    parallel_key = object()
    payload = {"items": ["shared"]}
    graphs = []
    for lib in (fnx, nx):
        graph = lib.MultiGraph()
        graph.add_nodes_from(nodes)
        graph.add_edge(nodes[3], nodes[4], key=7, weight=3, payload=payload)
        graph.add_edge(nodes[3], nodes[4], key=parallel_key, weight=5)
        graph.add_edge(nodes[3], nodes[3], key="source-loop", weight=11)
        graph.add_edge(nodes[4], nodes[4], key="target-loop", weight=13)
        # Exercise a warmed native node/edge cache before mutation too.
        list(graph.edges(keys=True, data=True))
        if batch:
            graph.remove_nodes_from(nodes[:3])
        else:
            for node in nodes[:3]:
                graph.remove_node(node)
        if reinsert:
            graph.add_nodes_from(reversed(nodes[:3]))
            graph.add_edge(nodes[4], nodes[2], key="reused-target", weight=17)
            graph.add_edge(nodes[0], nodes[3], key="reused-source", weight=19)
            graph.add_edge(nodes[1], nodes[1], key="reused-loop", weight=23)
        if cloning == "copy":
            graph = graph.copy()
        elif cloning == "shallow_copy":
            graph = copy(graph)
        graphs.append(graph)

    graph, reference = graphs
    _edge_views_match(graph, reference)
    _edge_views_match(graph, reference)
    for current in graphs:
        current[nodes[3]][nodes[4]][parallel_key]["weight"] = 101
    _edge_views_match(graph, reference)
    assert graph[nodes[3]][nodes[4]][7]["payload"] is payload
    assert any(key is parallel_key for _, _, key in graph.edges(keys=True))


@pytest.mark.parametrize("batch", [False, True])
def test_compacted_single_node_self_loop_can_be_iterated(batch):
    graph = fnx.MultiGraph()
    graph.add_nodes_from(range(3))
    graph.add_edge(2, 2, key="loop", weight=9)
    if batch:
        graph.remove_nodes_from([0, 1])
    else:
        graph.remove_node(0)
        graph.remove_node(1)
    assert list(graph.edges()) == [(2, 2)]
    assert list(graph.edges(keys=True, data=True)) == [(2, 2, "loop", {"weight": 9})]


@pytest.mark.parametrize("copy_graph", [False, True])
def test_repeated_contractions_preserve_laplacians_and_spanning_tree_counts(copy_graph):
    np = pytest.importorskip("numpy")
    pytest.importorskip("scipy")
    edges = [(0, 1), (1, 2), (2, 0), (2, 3), (3, 4), (4, 1)]
    graph = fnx.MultiGraph(edges)
    reference = nx.MultiGraph(edges)
    for node in (1, 2, 3):
        graph = fnx.contracted_nodes(
            graph, 0, node, self_loops=False, copy=copy_graph
        )
        reference = nx.contracted_nodes(
            reference, 0, node, self_loops=False, copy=copy_graph
        )
        _edge_views_match(graph, reference)
        np.testing.assert_array_equal(
            fnx.laplacian_matrix(graph, weight=None).toarray(),
            nx.laplacian_matrix(reference, weight=None).toarray(),
        )
        assert fnx.number_of_spanning_trees(graph) == pytest.approx(
            nx.number_of_spanning_trees(reference)
        )
