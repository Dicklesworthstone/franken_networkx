"""Tests for conversion and serialization compatibility wrappers."""

import networkx as nx
import pytest

import franken_networkx as fnx


def _node_key(node):
    return (type(node).__name__, repr(node))


def _value_key(value):
    if isinstance(value, dict):
        return tuple(
            sorted(((type(key).__name__, repr(key)), _value_key(inner)) for key, inner in value.items())
        )
    if isinstance(value, (list, tuple)):
        return tuple(_value_key(item) for item in value)
    if isinstance(value, set):
        return tuple(sorted(_value_key(item) for item in value))
    return (type(value).__name__, repr(value))


def _mapping_key(mapping):
    return tuple(
        sorted(((type(key).__name__, repr(key)), _value_key(value)) for key, value in mapping.items())
    )


def _graph_data_signature(graph):
    nodes = [(_node_key(node), _mapping_key(attrs)) for node, attrs in graph.nodes(data=True)]
    if graph.is_multigraph():
        edges = sorted(
            (
                *(
                    tuple(sorted((_node_key(u), _node_key(v))))
                    if not graph.is_directed()
                    else (_node_key(u), _node_key(v))
                ),
                (type(key).__name__, repr(key)),
                _mapping_key(attrs),
            )
            for u, v, key, attrs in graph.edges(keys=True, data=True)
        )
    else:
        edges = sorted(
            (
                *(
                    tuple(sorted((_node_key(u), _node_key(v))))
                    if not graph.is_directed()
                    else (_node_key(u), _node_key(v))
                ),
                _mapping_key(attrs),
            )
            for u, v, attrs in graph.edges(data=True)
        )
    return (
        graph.is_directed(),
        graph.is_multigraph(),
        _mapping_key(graph.graph),
        nodes,
        edges,
    )


def test_pandas_adjacency_round_trip():
    pd = pytest.importorskip("pandas")

    graph = fnx.Graph()
    graph.add_edge("a", "b", weight=2.5)
    graph.add_edge("b", "c", weight=1.5)

    frame = fnx.to_pandas_adjacency(graph, dtype=float)
    restored = fnx.from_pandas_adjacency(frame)

    assert isinstance(frame, pd.DataFrame)
    assert restored["a"]["b"]["weight"] == 2.5
    assert restored["b"]["c"]["weight"] == 1.5


def test_prufer_sequence_round_trip():
    tree = fnx.path_graph(5)

    sequence = fnx.to_prufer_sequence(tree)
    restored = fnx.from_prufer_sequence(sequence)

    assert len(sequence) == 3
    assert restored.number_of_nodes() == 5
    assert restored.number_of_edges() == 4


def test_nested_tuple_round_trip():
    tree = fnx.balanced_tree(2, 2)

    nested = fnx.to_nested_tuple(tree, root=0)
    restored = fnx.from_nested_tuple(nested, sensible_relabeling=True)

    assert nested == (((), ()), ((), ()))
    assert restored.number_of_nodes() == tree.number_of_nodes()
    assert restored.number_of_edges() == tree.number_of_edges()


def test_cytoscape_and_generic_graph_conversion():
    graph = fnx.Graph()
    graph.add_edge("x", "y", weight=4)

    data = fnx.cytoscape_data(graph)
    restored = fnx.cytoscape_graph(data)
    generic = fnx.to_networkx_graph({"x": {"y": {"weight": 7}}})

    assert "elements" in data
    assert restored["x"]["y"]["weight"] == 4
    assert generic["x"]["y"]["weight"] == 7


def test_attr_sparse_matrix_returns_sparse_and_ordering():
    scipy = pytest.importorskip("scipy")

    graph = fnx.Graph()
    graph.add_node("a", color=0)
    graph.add_node("b", color=1)
    graph.add_edge("a", "b", weight=3)

    matrix, ordering = fnx.attr_sparse_matrix(graph, edge_attr="weight", node_attr="color")

    assert isinstance(matrix, scipy.sparse.sparray)
    assert ordering == [0, 1]


def test_json_graph_constructors_match_networkx_without_fallback(monkeypatch):
    adjacency_source = nx.MultiDiGraph()
    adjacency_source.graph["name"] = "demo"
    adjacency_source.add_node("a", color="red")
    adjacency_source.add_node("b")
    adjacency_source.add_edge("a", "b", key=7, weight=2)
    adjacency_payload = nx.adjacency_data(adjacency_source, attrs={"id": "name", "key": "ekey"})
    expected_adjacency = nx.adjacency_graph(adjacency_payload, attrs={"id": "name", "key": "ekey"})

    node_link_source = nx.MultiDiGraph()
    node_link_source.graph["name"] = "demo"
    node_link_source.add_node("a", color="red")
    node_link_source.add_node("b")
    node_link_source.add_edge("a", "b", key=7, weight=2)
    node_link_payload = nx.node_link_data(
        node_link_source,
        edges="links",
        nodes="verts",
        source="src",
        target="dst",
        name="name",
        key="ekey",
    )
    expected_node_link = nx.node_link_graph(
        node_link_payload,
        edges="links",
        nodes="verts",
        source="src",
        target="dst",
        name="name",
        key="ekey",
    )

    cytoscape_source = nx.MultiDiGraph()
    cytoscape_source.graph["name"] = "demo"
    cytoscape_source.add_node("a", label="A")
    cytoscape_source.add_node("b", label="B")
    cytoscape_source.add_edge("a", "b", key=7, weight=2)
    cytoscape_payload = nx.cytoscape_data(cytoscape_source, name="label", ident="value")
    expected_cytoscape = nx.cytoscape_graph(cytoscape_payload, name="label", ident="value")

    def fail(*args, **kwargs):
        raise AssertionError("unexpected NetworkX fallback")

    monkeypatch.setattr(nx, "adjacency_graph", fail)
    monkeypatch.setattr(nx, "node_link_graph", fail)
    monkeypatch.setattr(nx, "cytoscape_graph", fail)

    actual_adjacency = fnx.adjacency_graph(adjacency_payload, attrs={"id": "name", "key": "ekey"})
    actual_node_link = fnx.node_link_graph(
        node_link_payload,
        edges="links",
        nodes="verts",
        source="src",
        target="dst",
        name="name",
        key="ekey",
    )
    actual_cytoscape = fnx.cytoscape_graph(cytoscape_payload, name="label", ident="value")

    assert _graph_data_signature(actual_adjacency) == _graph_data_signature(expected_adjacency)
    assert _graph_data_signature(actual_node_link) == _graph_data_signature(expected_node_link)
    assert _graph_data_signature(actual_cytoscape) == _graph_data_signature(expected_cytoscape)


def test_node_link_graph_converts_list_nodes_to_tuples_without_fallback(monkeypatch):
    payload = {
        "graph": {"name": "demo"},
        "nodes": [{"id": ["a", "b"]}, {"id": "c"}],
        "edges": [{"source": ["a", "b"], "target": "c", "weight": 2}],
    }
    expected = nx.node_link_graph(payload)

    def fail(*args, **kwargs):
        raise AssertionError("unexpected NetworkX fallback")

    monkeypatch.setattr(nx, "node_link_graph", fail)

    actual = fnx.node_link_graph(payload)

    assert _graph_data_signature(actual) == _graph_data_signature(expected)


def test_json_graph_constructors_preserve_existing_non_integer_key_contract_without_fallback(
    monkeypatch,
):
    adjacency_source = nx.MultiDiGraph()
    adjacency_source.add_edge("a", "b", key=("left", "right"), weight=2)
    adjacency_payload = nx.adjacency_data(adjacency_source, attrs={"id": "name", "key": "ekey"})
    expected_adjacency = fnx.readwrite._from_nx_graph(
        nx.adjacency_graph(adjacency_payload, attrs={"id": "name", "key": "ekey"})
    )

    node_link_source = nx.MultiDiGraph()
    node_link_source.add_edge("a", "b", key=("left", "right"), weight=2)
    node_link_payload = nx.node_link_data(
        node_link_source,
        edges="links",
        nodes="verts",
        source="src",
        target="dst",
        name="name",
        key="ekey",
    )
    expected_node_link = fnx.readwrite._from_nx_graph(
        nx.node_link_graph(
            node_link_payload,
            edges="links",
            nodes="verts",
            source="src",
            target="dst",
            name="name",
            key="ekey",
        )
    )

    def fail(*args, **kwargs):
        raise AssertionError("unexpected NetworkX fallback")

    monkeypatch.setattr(nx, "adjacency_graph", fail)
    monkeypatch.setattr(nx, "node_link_graph", fail)

    actual_adjacency = fnx.adjacency_graph(adjacency_payload, attrs={"id": "name", "key": "ekey"})
    actual_node_link = fnx.node_link_graph(
        node_link_payload,
        edges="links",
        nodes="verts",
        source="src",
        target="dst",
        name="name",
        key="ekey",
    )

    assert _graph_data_signature(actual_adjacency) == _graph_data_signature(expected_adjacency)
    assert _graph_data_signature(actual_node_link) == _graph_data_signature(expected_node_link)


def test_from_dict_of_dicts_matches_networkx_without_fallback(monkeypatch):
    payload = {0: {1: {7: {"w": 1}}}, 1: {0: {7: {"w": 1}}}, 5: {}}
    expected = nx.from_dict_of_dicts(
        payload,
        create_using=nx.MultiGraph(),
        multigraph_input=True,
    )

    def fail(*args, **kwargs):
        raise AssertionError("unexpected NetworkX fallback")

    monkeypatch.setattr(nx, "from_dict_of_dicts", fail)

    actual = fnx.from_dict_of_dicts(
        payload,
        create_using=fnx.MultiGraph(),
        multigraph_input=True,
    )

    assert _graph_data_signature(actual) == _graph_data_signature(expected)


def test_from_dict_of_dicts_preserves_existing_non_integer_key_contract_without_fallback(
    monkeypatch,
):
    payload = {0: {1: {"left": {"w": 1}}}, 1: {0: {"left": {"w": 1}}}}
    expected = fnx.readwrite._from_nx_graph(
        nx.from_dict_of_dicts(
            payload,
            create_using=nx.MultiGraph(),
            multigraph_input=True,
        )
    )

    def fail(*args, **kwargs):
        raise AssertionError("unexpected NetworkX fallback")

    monkeypatch.setattr(nx, "from_dict_of_dicts", fail)

    actual = fnx.from_dict_of_dicts(
        payload,
        create_using=fnx.MultiGraph(),
        multigraph_input=True,
    )

    assert _graph_data_signature(actual) == _graph_data_signature(expected)


def test_from_numpy_array_matches_networkx_without_fallback(monkeypatch):
    np = pytest.importorskip("numpy")
    matrix = np.array([[0, 2], [2, 0]], dtype=int)
    expected = nx.from_numpy_array(
        matrix,
        parallel_edges=True,
        create_using=nx.MultiGraph(),
        nodelist=["left", "right"],
    )

    def fail(*args, **kwargs):
        raise AssertionError("unexpected NetworkX fallback")

    monkeypatch.setattr(nx, "from_numpy_array", fail)

    actual = fnx.from_numpy_array(
        matrix,
        parallel_edges=True,
        create_using=fnx.MultiGraph(),
        nodelist=["left", "right"],
    )

    assert _graph_data_signature(actual) == _graph_data_signature(expected)


def test_from_numpy_array_structured_dtype_matches_networkx_without_fallback(monkeypatch):
    np = pytest.importorskip("numpy")
    dtype = np.dtype([("weight", float), ("cost", int)])
    matrix = np.array([[(0.0, 0), (1.5, 2)], [(1.5, 2), (0.0, 0)]], dtype=dtype)
    expected = nx.from_numpy_array(matrix, nodelist=["left", "right"])

    def fail(*args, **kwargs):
        raise AssertionError("unexpected NetworkX fallback")

    monkeypatch.setattr(nx, "from_numpy_array", fail)

    actual = fnx.from_numpy_array(matrix, nodelist=["left", "right"])

    assert _graph_data_signature(actual) == _graph_data_signature(expected)


def test_from_scipy_sparse_array_matches_networkx_without_fallback(monkeypatch):
    np = pytest.importorskip("numpy")
    scipy_sparse = pytest.importorskip("scipy.sparse")
    matrix = scipy_sparse.csr_array(np.array([[0, 2], [2, 0]], dtype=int))
    expected = nx.from_scipy_sparse_array(
        matrix,
        parallel_edges=True,
        create_using=nx.MultiGraph(),
    )

    def fail(*args, **kwargs):
        raise AssertionError("unexpected NetworkX fallback")

    monkeypatch.setattr(nx, "from_scipy_sparse_array", fail)

    actual = fnx.from_scipy_sparse_array(
        matrix,
        parallel_edges=True,
        create_using=fnx.MultiGraph(),
    )

    assert _graph_data_signature(actual) == _graph_data_signature(expected)


def test_from_pandas_edgelist_matches_networkx_without_fallback(monkeypatch):
    pd = pytest.importorskip("pandas")
    frame = pd.DataFrame(
        [
            {"src": "a", "dst": "b", "ek": 7, "weight": 3},
            {"src": "a", "dst": "b", "ek": 8, "weight": 4},
        ]
    )
    expected = nx.from_pandas_edgelist(
        frame,
        source="src",
        target="dst",
        edge_attr="weight",
        create_using=nx.MultiGraph(),
        edge_key="ek",
    )

    def fail(*args, **kwargs):
        raise AssertionError("unexpected NetworkX fallback")

    monkeypatch.setattr(nx, "from_pandas_edgelist", fail)

    actual = fnx.from_pandas_edgelist(
        frame,
        source="src",
        target="dst",
        edge_attr="weight",
        create_using=fnx.MultiGraph(),
        edge_key="ek",
    )

    assert _graph_data_signature(actual) == _graph_data_signature(expected)
