import pytest

import franken_networkx as fnx


GRAPH_CASES = (
    (fnx.Graph, False),
    (fnx.DiGraph, False),
    (fnx.MultiGraph, True),
    (fnx.MultiDiGraph, True),
)


def _weighted_graph(graph_cls, is_multi):
    graph = graph_cls()
    if is_multi:
        graph.add_edge("a", "b", key=0, weight=10)
        graph.add_edge("b", "c", key=0, weight=10)
        graph.add_edge("a", "c", key=0, weight=5)
    else:
        graph.add_edge("a", "b", weight=10)
        graph.add_edge("b", "c", weight=10)
        graph.add_edge("a", "c", weight=5)
    return graph


def _set_ab_bc_to_short_path(graph, is_multi, edge_attrs):
    if is_multi:
        edge_attrs("a", "b", 0)["weight"] = 1
        edge_attrs("b", "c", 0)["weight"] = 1
    else:
        edge_attrs("a", "b")["weight"] = 1
        edge_attrs("b", "c")["weight"] = 1


def _assert_weighted_kernel_sees_mutation(graph):
    assert fnx.shortest_path_length(graph, "a", "c", weight="weight") == 2


@pytest.mark.parametrize(("graph_cls", "is_multi"), GRAPH_CASES)
def test_weight_mutation_via_getitem_syncs_to_weighted_kernel(graph_cls, is_multi):
    graph = _weighted_graph(graph_cls, is_multi)
    _set_ab_bc_to_short_path(graph, is_multi, lambda u, v, key=None: graph[u][v][key] if is_multi else graph[u][v])

    _assert_weighted_kernel_sees_mutation(graph)


@pytest.mark.parametrize(("graph_cls", "is_multi"), GRAPH_CASES)
def test_weight_mutation_via_edges_data_syncs_to_weighted_kernel(graph_cls, is_multi):
    graph = _weighted_graph(graph_cls, is_multi)
    if is_multi:
        for u, v, key, attrs in graph.edges(keys=True, data=True):
            if (u, v, key) in {("a", "b", 0), ("b", "c", 0)}:
                attrs["weight"] = 1
    else:
        for u, v, attrs in graph.edges(data=True):
            if (u, v) in {("a", "b"), ("b", "c")}:
                attrs["weight"] = 1

    _assert_weighted_kernel_sees_mutation(graph)


@pytest.mark.parametrize(("graph_cls", "is_multi"), GRAPH_CASES)
def test_weight_mutation_via_adjacency_syncs_to_weighted_kernel(graph_cls, is_multi):
    graph = _weighted_graph(graph_cls, is_multi)
    _set_ab_bc_to_short_path(graph, is_multi, lambda u, v, key=None: graph.adj[u][v][key] if is_multi else graph.adj[u][v])

    _assert_weighted_kernel_sees_mutation(graph)


@pytest.mark.parametrize(("graph_cls", "is_multi"), GRAPH_CASES)
def test_weight_mutation_via_get_edge_data_syncs_to_weighted_kernel(graph_cls, is_multi):
    graph = _weighted_graph(graph_cls, is_multi)
    _set_ab_bc_to_short_path(
        graph,
        is_multi,
        lambda u, v, key=None: graph.get_edge_data(u, v, key=key) if is_multi else graph.get_edge_data(u, v),
    )

    _assert_weighted_kernel_sees_mutation(graph)


@pytest.mark.parametrize(("graph_cls", "is_multi"), ((fnx.DiGraph, False), (fnx.MultiDiGraph, True)))
def test_weight_mutation_via_predecessor_adjacency_syncs_to_weighted_kernel(graph_cls, is_multi):
    graph = _weighted_graph(graph_cls, is_multi)
    _set_ab_bc_to_short_path(graph, is_multi, lambda u, v, key=None: graph.pred[v][u][key] if is_multi else graph.pred[v][u])

    _assert_weighted_kernel_sees_mutation(graph)
