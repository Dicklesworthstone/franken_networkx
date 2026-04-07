import pytest

import franken_networkx as fnx

nx = pytest.importorskip("networkx")


def _edge_records(G):
    def normalize_endpoints(u, v):
        if G.is_directed():
            return u, v
        return tuple(sorted((u, v)))

    if G.is_multigraph():
        return sorted(
            (
                *normalize_endpoints(u, v),
                key,
                data,
            )
            for u, v, key, data in G.edges(keys=True, data=True)
        )
    return sorted(
        (
            *normalize_endpoints(u, v),
            data,
        )
        for u, v, data in G.edges(data=True)
    )


def test_line_graph_matches_networkx_for_simple_path():
    graph = fnx.path_graph(4)

    result = fnx.line_graph(graph)
    expected = nx.line_graph(nx.path_graph(4))

    assert type(result).__name__ == type(expected).__name__
    assert sorted(result.nodes(data=True)) == sorted(expected.nodes(data=True))
    assert _edge_records(result) == _edge_records(expected)


def test_line_graph_matches_networkx_for_multigraph_and_create_using():
    graph = fnx.MultiGraph()
    graph.add_edge("a", "b", key=5, capacity=2)
    graph.add_edge("b", "c", key=9, capacity=3)

    result = fnx.line_graph(graph, create_using=fnx.MultiGraph())

    expected_input = nx.MultiGraph()
    expected_input.add_edge("a", "b", key=5, capacity=2)
    expected_input.add_edge("b", "c", key=9, capacity=3)
    expected = nx.line_graph(expected_input, create_using=nx.MultiGraph())

    assert result.is_multigraph()
    assert sorted(result.nodes(data=True)) == sorted(expected.nodes(data=True))
    assert _edge_records(result) == _edge_records(expected)


def test_power_matches_networkx():
    graph = fnx.cycle_graph(5)

    result = fnx.power(graph, 2)
    expected = nx.power(nx.cycle_graph(5), 2)

    assert dict(result.graph) == expected.graph
    assert sorted(result.nodes(data=True)) == sorted(expected.nodes(data=True))
    assert sorted(result.edges(data=True)) == sorted(expected.edges(data=True))


def test_stochastic_graph_matches_networkx_copy_and_in_place():
    graph = fnx.MultiDiGraph()
    graph.graph["name"] = "weighted"
    graph.add_node("z", color="blue")
    graph.add_edge("a", "b", key=1, w=2.0)
    graph.add_edge("a", "c", key=4, w=6.0)
    graph.add_edge("b", "c", key=7)

    expected_input = nx.MultiDiGraph()
    expected_input.graph["name"] = "weighted"
    expected_input.add_node("z", color="blue")
    expected_input.add_edge("a", "b", key=1, w=2.0)
    expected_input.add_edge("a", "c", key=4, w=6.0)
    expected_input.add_edge("b", "c", key=7)

    copy_result = fnx.stochastic_graph(graph, copy=True, weight="w")
    expected_copy = nx.stochastic_graph(expected_input, copy=True, weight="w")
    assert copy_result is not graph
    assert dict(copy_result.graph) == expected_copy.graph
    assert sorted(copy_result.nodes(data=True)) == sorted(expected_copy.nodes(data=True))
    assert _edge_records(copy_result) == _edge_records(expected_copy)

    inplace_graph = fnx.MultiDiGraph()
    inplace_graph.graph["name"] = "weighted"
    inplace_graph.add_edge("a", "b", key=1, w=2.0)
    inplace_graph.add_edge("a", "c", key=4, w=6.0)
    inplace_graph.add_edge("b", "c", key=7)

    expected_inplace = nx.MultiDiGraph()
    expected_inplace.graph["name"] = "weighted"
    expected_inplace.add_edge("a", "b", key=1, w=2.0)
    expected_inplace.add_edge("a", "c", key=4, w=6.0)
    expected_inplace.add_edge("b", "c", key=7)

    same_object = fnx.stochastic_graph(inplace_graph, copy=False, weight="w")
    expected_same_object = nx.stochastic_graph(expected_inplace, copy=False, weight="w")
    assert same_object is inplace_graph
    assert _edge_records(same_object) == _edge_records(expected_same_object)


def test_disjoint_union_matches_networkx_for_multigraphs():
    left = fnx.MultiGraph()
    left.graph["side"] = "left"
    left.add_node("a", color="red")
    left.add_edge("a", "b", key=7, weight=2)

    right = fnx.MultiGraph()
    right.graph["side"] = "right"
    right.add_node("x", size=3)
    right.add_edge("x", "y", key=11, weight=5)

    result = fnx.disjoint_union(left, right)

    expected_left = nx.MultiGraph()
    expected_left.graph["side"] = "left"
    expected_left.add_node("a", color="red")
    expected_left.add_edge("a", "b", key=7, weight=2)
    expected_right = nx.MultiGraph()
    expected_right.graph["side"] = "right"
    expected_right.add_node("x", size=3)
    expected_right.add_edge("x", "y", key=11, weight=5)
    expected = nx.disjoint_union(expected_left, expected_right)

    assert dict(result.graph) == expected.graph
    assert sorted(result.nodes(data=True)) == sorted(expected.nodes(data=True))
    assert _edge_records(result) == _edge_records(expected)


def test_disjoint_union_all_matches_networkx_and_rejects_mixed_types():
    graphs = [fnx.path_graph(3), fnx.path_graph(2), fnx.empty_graph(1)]
    expected_graphs = [nx.path_graph(3), nx.path_graph(2), nx.empty_graph(1)]

    result = fnx.disjoint_union_all(graphs)
    expected = nx.disjoint_union_all(expected_graphs)

    assert dict(result.graph) == expected.graph
    assert sorted(result.nodes(data=True)) == sorted(expected.nodes(data=True))
    assert sorted(result.edges(data=True)) == sorted(expected.edges(data=True))

    with pytest.raises(fnx.NetworkXError, match="All graphs must be directed or undirected."):
        fnx.disjoint_union_all([fnx.Graph(), fnx.DiGraph()])


def test_make_max_clique_graph_create_using_matches_networkx():
    graph = fnx.Graph()
    graph.add_edges_from([(0, 1), (1, 2), (2, 0), (2, 3)])

    result = fnx.make_max_clique_graph(graph, create_using=fnx.MultiGraph())

    expected_input = nx.Graph()
    expected_input.add_edges_from([(0, 1), (1, 2), (2, 0), (2, 3)])
    expected = nx.make_max_clique_graph(expected_input, create_using=nx.MultiGraph())

    assert result.is_multigraph()
    assert sorted(result.nodes(data=True)) == sorted(expected.nodes(data=True))
    assert _edge_records(result) == _edge_records(expected)
