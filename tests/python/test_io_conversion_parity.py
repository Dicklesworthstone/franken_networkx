import networkx as nx
import pytest

import franken_networkx as fnx


def normalize_adjacency_payload(payload):
    return {
        **payload,
        "nodes": sorted(payload["nodes"], key=lambda item: repr(item.get("name", item.get("id")))),
        "adjacency": [
            sorted(neighbors, key=lambda item: (repr(item.get("name", item.get("id"))), repr(item.get("key"))))
            for neighbors in payload["adjacency"]
        ],
    }


def test_adjacency_data_matches_networkx_with_custom_attrs():
    graph = fnx.path_graph(3)
    expected = nx.path_graph(3)

    actual = fnx.adjacency_data(graph, attrs={"id": "name", "key": "ekey"})
    wanted = nx.adjacency_data(expected, attrs={"id": "name", "key": "ekey"})

    assert normalize_adjacency_payload(actual) == normalize_adjacency_payload(wanted)


def test_node_link_data_matches_networkx_with_custom_field_names():
    graph = fnx.path_graph(2)
    expected = nx.path_graph(2)

    assert fnx.node_link_data(
        graph,
        edges="links",
        nodes="vertices",
        source="src",
        target="dst",
        name="name",
    ) == nx.node_link_data(
        expected,
        edges="links",
        nodes="vertices",
        source="src",
        target="dst",
        name="name",
    )


def test_tree_data_matches_networkx():
    graph = nx.DiGraph([(0, 1), (0, 2), (2, 3)])
    expected = nx.tree_data(graph, 0, ident="name", children="kids")

    assert fnx.tree_data(graph, 0, ident="name", children="kids") == expected


def test_tree_data_networkx_input_without_weak_connectivity_fallback(monkeypatch):
    graph = nx.DiGraph()
    graph.add_node("root", color="blue")
    graph.add_node("left", color="red")
    graph.add_node("right", weight=2)
    graph.add_edge("root", "left")
    graph.add_edge("root", "right")
    expected = nx.tree_data(graph, "root", ident="name", children="kids")

    def fail(*args, **kwargs):
        raise AssertionError("NetworkX weak-connectivity fallback was used")

    monkeypatch.setattr(nx, "is_weakly_connected", fail)

    assert fnx.tree_data(graph, "root", ident="name", children="kids") == expected


def test_cytoscape_data_matches_networkx():
    graph = fnx.path_graph(2)
    expected = nx.path_graph(2)

    assert fnx.cytoscape_data(graph, name="label", ident="value") == nx.cytoscape_data(
        expected,
        name="label",
        ident="value",
    )


def test_generalized_degree_matches_networkx():
    graph = fnx.Graph()
    graph.add_edges_from([(0, 1), (1, 2), (2, 0), (2, 3)])
    expected = nx.Graph()
    expected.add_edges_from([(0, 1), (1, 2), (2, 0), (2, 3)])

    assert fnx.generalized_degree(graph) == nx.generalized_degree(expected)
    assert fnx.generalized_degree(graph, 2) == nx.generalized_degree(expected, 2)


def test_describe_matches_networkx_output(capsys):
    graph = fnx.path_graph(3)
    expected = nx.path_graph(3)

    assert fnx.describe(graph) is None
    actual_out = capsys.readouterr().out

    nx.describe(expected)
    expected_out = capsys.readouterr().out

    assert actual_out == expected_out


def test_to_numpy_array_matches_networkx_multigraph_contract():
    np = pytest.importorskip("numpy")

    graph = fnx.MultiGraph()
    graph.add_edge("a", "b", key=7, weight=3)
    graph.add_edge("a", "b", key=8, weight=4)
    expected = nx.MultiGraph()
    expected.add_edge("a", "b", key=7, weight=3)
    expected.add_edge("a", "b", key=8, weight=4)

    actual = fnx.to_numpy_array(
        graph,
        nodelist=["a", "b"],
        multigraph_weight=max,
        weight="weight",
    )
    wanted = nx.to_numpy_array(
        expected,
        nodelist=["a", "b"],
        multigraph_weight=max,
        weight="weight",
    )
    assert np.array_equal(actual, wanted)


def test_to_scipy_sparse_array_matches_networkx_multigraph_contract():
    np = pytest.importorskip("numpy")
    pytest.importorskip("scipy")

    graph = fnx.MultiGraph()
    graph.add_edge("a", "b", key=7, weight=3)
    graph.add_edge("a", "b", key=8, weight=4)
    expected = nx.MultiGraph()
    expected.add_edge("a", "b", key=7, weight=3)
    expected.add_edge("a", "b", key=8, weight=4)

    actual = fnx.to_scipy_sparse_array(graph, nodelist=["a", "b"], format="csr")
    wanted = nx.to_scipy_sparse_array(expected, nodelist=["a", "b"], format="csr")

    assert np.array_equal(actual.toarray(), wanted.toarray())


def test_to_pandas_edgelist_matches_networkx_multigraph_contract():
    pytest.importorskip("pandas")

    graph = fnx.MultiGraph()
    graph.add_edge("a", "b", key=7, weight=3)
    graph.add_edge("a", "b", key=8, weight=4)
    expected = nx.MultiGraph()
    expected.add_edge("a", "b", key=7, weight=3)
    expected.add_edge("a", "b", key=8, weight=4)

    actual = fnx.to_pandas_edgelist(graph, source="src", target="dst", edge_key="ek")
    wanted = nx.to_pandas_edgelist(expected, source="src", target="dst", edge_key="ek")

    assert actual.sort_values(["ek"]).reset_index(drop=True).equals(
        wanted.sort_values(["ek"]).reset_index(drop=True)
    )


def test_to_pandas_adjacency_matches_networkx_multigraph_contract():
    pytest.importorskip("pandas")

    graph = fnx.MultiGraph()
    graph.add_edge("a", "b", key=7, weight=3)
    graph.add_edge("a", "b", key=8, weight=4)
    expected = nx.MultiGraph()
    expected.add_edge("a", "b", key=7, weight=3)
    expected.add_edge("a", "b", key=8, weight=4)

    actual = fnx.to_pandas_adjacency(
        graph,
        nodelist=["a", "b"],
        multigraph_weight=max,
        nonedge=-1.0,
    )
    wanted = nx.to_pandas_adjacency(
        expected,
        nodelist=["a", "b"],
        multigraph_weight=max,
        nonedge=-1.0,
    )

    assert actual.equals(wanted)
