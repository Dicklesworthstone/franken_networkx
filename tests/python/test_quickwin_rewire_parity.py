"""Parity tests for quick-win FNX rewires."""

import networkx as nx
import pytest

import franken_networkx as fnx


def test_minimum_edge_cut_matches_nx_for_specific_terminals():
    graph = fnx.Graph()
    graph.add_edges_from([("s", "a"), ("s", "b"), ("a", "t"), ("b", "t")])
    expected = nx.Graph()
    expected.add_edges_from([("s", "a"), ("s", "b"), ("a", "t"), ("b", "t")])

    cut = fnx.minimum_edge_cut(graph, "s", "t")
    cut_nx = nx.minimum_edge_cut(expected, "s", "t")

    assert len(cut) == len(cut_nx)
    augmented = graph.copy()
    augmented.remove_edges_from(list(cut))
    assert not fnx.has_path(augmented, "s", "t")


def test_minimum_st_node_cut_matches_nx():
    graph = fnx.Graph()
    graph.add_edges_from([("s", "a"), ("a", "b"), ("b", "t"), ("a", "t")])
    expected = nx.Graph()
    expected.add_edges_from([("s", "a"), ("a", "b"), ("b", "t"), ("a", "t")])

    assert fnx.minimum_st_node_cut(graph, "s", "t") == nx.minimum_node_cut(expected, "s", "t")


def test_ego_graph_matches_nx():
    graph = fnx.path_graph(5)
    expected = nx.path_graph(5)

    ego = fnx.ego_graph(graph, 2, radius=1)
    ego_nx = nx.ego_graph(expected, 2, radius=1)
    assert sorted(ego.nodes(data=True)) == sorted(ego_nx.nodes(data=True))
    assert sorted(ego.edges(data=True)) == sorted(ego_nx.edges(data=True))

    ego_no_center = fnx.ego_graph(graph, 2, radius=2, center=False)
    ego_no_center_nx = nx.ego_graph(expected, 2, radius=2, center=False)
    assert sorted(ego_no_center.nodes(data=True)) == sorted(ego_no_center_nx.nodes(data=True))
    assert sorted(ego_no_center.edges(data=True)) == sorted(ego_no_center_nx.edges(data=True))


def _populate_empty_copy_graph(graph):
    graph.graph["name"] = "base"
    graph.add_node("a", color="red")
    graph.add_node("b", seen=True)
    if graph.is_multigraph():
        graph.add_edge("a", "b", key=4, weight=2)
    else:
        graph.add_edge("a", "b", weight=2)


def _node_snapshot(graph):
    return sorted((node, dict(attrs)) for node, attrs in graph.nodes(data=True))


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
    ids=["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"],
)
def test_create_empty_copy_matches_nx_without_fallback(monkeypatch, fnx_cls, nx_cls):
    graph = fnx_cls()
    expected = nx_cls()
    _populate_empty_copy_graph(graph)
    _populate_empty_copy_graph(expected)

    copy_with_data_nx = nx.create_empty_copy(expected, with_data=True)
    copy_without_data_nx = nx.create_empty_copy(expected, with_data=False)

    def blocked_create_empty_copy(*args, **kwargs):
        raise AssertionError("NetworkX create_empty_copy fallback used")

    monkeypatch.setattr(nx, "create_empty_copy", blocked_create_empty_copy)

    copy_with_data = fnx.create_empty_copy(graph, with_data=True)
    assert type(copy_with_data).__name__ == type(copy_with_data_nx).__name__
    assert dict(copy_with_data.graph) == dict(copy_with_data_nx.graph)
    assert _node_snapshot(copy_with_data) == _node_snapshot(copy_with_data_nx)
    assert copy_with_data.number_of_edges() == copy_with_data_nx.number_of_edges() == 0

    copy_without_data = fnx.create_empty_copy(graph, with_data=False)
    assert type(copy_without_data).__name__ == type(copy_without_data_nx).__name__
    assert dict(copy_without_data.graph) == dict(copy_without_data_nx.graph) == {}
    assert _node_snapshot(copy_without_data) == _node_snapshot(copy_without_data_nx)
    assert copy_without_data.number_of_edges() == copy_without_data_nx.number_of_edges() == 0


def test_node_degree_xy_matches_nx():
    graph = fnx.DiGraph()
    graph.add_edges_from([("a", "b"), ("a", "c"), ("b", "c")])
    expected = nx.DiGraph()
    expected.add_edges_from([("a", "b"), ("a", "c"), ("b", "c")])

    assert sorted(fnx.node_degree_xy(graph, x="out", y="in")) == sorted(
        nx.node_degree_xy(expected, x="out", y="in")
    )


def test_all_pairs_node_connectivity_matches_nx():
    graph = fnx.cycle_graph(4)
    expected = nx.cycle_graph(4)

    assert fnx.all_pairs_node_connectivity(graph) == nx.all_pairs_node_connectivity(expected)
    assert fnx.all_pairs_node_connectivity(graph, nbunch=[0, 2]) == nx.all_pairs_node_connectivity(
        expected,
        nbunch=[0, 2],
    )


def test_all_pairs_node_connectivity_validates_flow_func():
    graph = fnx.path_graph(4)
    expected = nx.path_graph(4)

    with pytest.raises(nx.NetworkXError) as expected_error:
        nx.all_pairs_node_connectivity(expected, flow_func=1)
    with pytest.raises(fnx.NetworkXError) as actual_error:
        fnx.all_pairs_node_connectivity(graph, flow_func=1)

    assert str(actual_error.value) == str(expected_error.value)
