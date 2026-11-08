"""Native fast paths must admit the graph represented by public mappings."""

import copy

import networkx as nx
import pytest

import franken_networkx as fnx


_GRAPH_TYPES = [nx.Graph, nx.DiGraph, nx.MultiGraph, nx.MultiDiGraph]
_INPUT_MODES = ["assigned", "deepcopy", "view"]


def _install_logical_stores(graph, logical):
    if logical.is_directed():
        nodes, successors, predecessors = copy.deepcopy(
            (logical._node, logical._succ, logical._pred)
        )
        graph._node = nodes
        graph._adj = successors
        graph._pred = predecessors
    else:
        graph._node, graph._adj = copy.deepcopy((logical._node, logical._adj))


def _graph_input(logical, mode):
    graph = getattr(fnx, type(logical).__name__)()
    if mode == "assigned":
        # A real native triangle deliberately disagrees with the logical rows.
        graph.add_edges_from([(90, 91), (91, 92), (92, 90)])
        _install_logical_stores(graph, logical)
        return graph

    graph.add_nodes_from(logical.nodes(data=True))
    if logical.is_multigraph():
        graph.add_edges_from(logical.edges(keys=True, data=True))
    else:
        graph.add_edges_from(logical.edges(data=True))
    if mode == "deepcopy":
        graph.graph["nested"] = []
        return copy.deepcopy(graph)
    graph.add_edge(90, 91)
    return fnx.subgraph_view(graph, filter_node=lambda node: node not in (90, 91))


@pytest.mark.parametrize("ncls", _GRAPH_TYPES)
@pytest.mark.parametrize("mode", _INPUT_MODES)
@pytest.mark.parametrize("edges", [[], [(0, 1), (1, 2)], [(0, 1), (1, 2), (2, 0)]])
def test_predicates_use_logical_rows(ncls, mode, edges):
    logical = ncls()
    logical.add_nodes_from([0, 1, 2])
    logical.add_edges_from(edges)
    graph = _graph_input(logical, mode)
    assert fnx.is_empty(graph) == nx.is_empty(logical)
    assert fnx.is_regular(graph) == nx.is_regular(logical)


@pytest.mark.parametrize("ncls", _GRAPH_TYPES)
def test_empty_logical_graph_retains_predicate_errors(ncls):
    graph = _graph_input(ncls(), "assigned")
    assert fnx.is_empty(graph)
    with pytest.raises(nx.NetworkXPointlessConcept):
        fnx.is_regular(graph)


@pytest.mark.parametrize("mode", _INPUT_MODES)
def test_planarity_reads_the_logical_petersen_graph(mode):
    logical = nx.petersen_graph()
    graph = _graph_input(logical, mode)
    assert fnx.is_planar(graph) == nx.is_planar(logical) is False


@pytest.mark.parametrize("mode", _INPUT_MODES)
@pytest.mark.parametrize("selected", [False, True])
def test_generalized_degree_reads_logical_triangles(mode, selected):
    logical = nx.Graph()
    logical.add_nodes_from(range(40))
    logical.add_edges_from([(0, 1), (1, 2), (2, 0), (0, 3), (1, 3)])
    graph = _graph_input(logical, mode)
    nodes = list(logical) if selected else None
    assert fnx.generalized_degree(graph, nodes) == nx.generalized_degree(logical, nodes)


@pytest.mark.parametrize("ncls", _GRAPH_TYPES)
@pytest.mark.parametrize("mode", _INPUT_MODES)
@pytest.mark.parametrize("weight", [None, "weight"])
@pytest.mark.parametrize("name", ["to_numpy_array", "laplacian_matrix", "normalized_laplacian_matrix"])
def test_matrix_families_use_logical_rows(ncls, mode, weight, name):
    np = pytest.importorskip("numpy")
    if name != "to_numpy_array":
        pytest.importorskip("scipy")
    logical = ncls()
    logical.add_nodes_from([3, 1, 0, 2])
    logical.add_weighted_edges_from([(0, 1, 2), (1, 2, 3), (1, 1, 4)])
    if logical.is_multigraph():
        logical.add_edge(0, 1, weight=5)
    graph = _graph_input(logical, mode)
    options = {"nodelist": [2, 0, 3, 1], "weight": weight}
    actual = getattr(fnx, name)(graph, **options)
    expected = getattr(nx, name)(logical, **options)
    if name != "to_numpy_array":
        actual, expected = actual.toarray(), expected.toarray()
    np.testing.assert_allclose(actual, expected, atol=1e-14)


@pytest.mark.parametrize("mode", _INPUT_MODES)
@pytest.mark.parametrize("name", ["laplacian_spectrum", "normalized_laplacian_spectrum", "adjacency_spectrum"])
def test_spectra_use_logical_rows(mode, name):
    np = pytest.importorskip("numpy")
    pytest.importorskip("scipy")
    logical = nx.Graph()
    logical.add_weighted_edges_from([(0, 1, 2), (1, 2, 3), (2, 0, 4), (2, 3, 5)])
    logical.add_node(4)
    graph = _graph_input(logical, mode)
    actual = getattr(fnx, name)(graph)
    expected = getattr(nx, name)(logical)
    np.testing.assert_allclose(np.sort(actual), np.sort(expected), atol=1e-12)


@pytest.mark.parametrize("name", ["laplacian_spectrum", "normalized_laplacian_spectrum", "adjacency_spectrum"])
@pytest.mark.parametrize("native_shape", ["star", "complete", "bipartite"])
def test_spectral_shape_shortcuts_ignore_hidden_native_graph(name, native_shape):
    np = pytest.importorskip("numpy")
    pytest.importorskip("scipy")
    if native_shape == "star":
        graph = fnx.star_graph(4)
    elif native_shape == "complete":
        graph = fnx.complete_graph(5)
    else:
        graph = fnx.complete_bipartite_graph(2, 3)
    logical = nx.path_graph(5)
    _install_logical_stores(graph, logical)
    actual = getattr(fnx, name)(graph)
    expected = getattr(nx, name)(logical)
    np.testing.assert_allclose(np.sort(actual), np.sort(expected), atol=1e-12)


@pytest.mark.parametrize("mode", _INPUT_MODES)
@pytest.mark.parametrize("edge_attr", [None, "weight", "other"])
def test_attr_matrix_uses_logical_rows(mode, edge_attr):
    np = pytest.importorskip("numpy")
    logical = nx.Graph()
    logical.add_edge(0, 1, weight=3, other=7)
    logical.add_edge(1, 2, weight=5, other=11)
    graph = _graph_input(logical, mode)
    options = {"edge_attr": edge_attr, "rc_order": [2, 0, 1]}
    np.testing.assert_allclose(fnx.attr_matrix(graph, **options), nx.attr_matrix(logical, **options))


def test_attr_matrix_callback_keeps_live_graph():
    np = pytest.importorskip("numpy")
    logical = nx.Graph()
    logical.add_edges_from([(0, 1), (1, 2)])
    graph = _graph_input(logical, "assigned")
    seen = []

    def weight(left, right):
        seen.append((left, right))
        graph[left][right]["called"] = True
        return 2

    actual = fnx.attr_matrix(graph, edge_attr=weight, rc_order=[0, 1, 2])
    np.testing.assert_array_equal(actual, [[0, 2, 0], [2, 0, 2], [0, 2, 0]])
    assert seen == [(0, 1), (1, 2)]
    assert all(data["called"] for _, _, data in graph.edges(data=True))


@pytest.mark.parametrize("ncls", [nx.DiGraph, nx.MultiDiGraph])
@pytest.mark.parametrize("mode", _INPUT_MODES)
@pytest.mark.parametrize("name", ["min_cost_flow", "min_cost_flow_cost", "network_simplex", "capacity_scaling"])
def test_min_cost_flow_families_use_logical_rows(ncls, mode, name):
    logical = ncls()
    logical.add_node(0, demand=-3)
    logical.add_node(3, demand=3)
    logical.add_edges_from([
        (0, 1, {"capacity": 2, "weight": 1}),
        (1, 3, {"capacity": 2, "weight": 1}),
        (0, 2, {"capacity": 3, "weight": 5}),
        (2, 3, {"capacity": 3, "weight": 1}),
    ])
    graph = _graph_input(logical, mode)
    assert getattr(fnx, name)(graph) == getattr(nx, name)(logical)


@pytest.mark.parametrize("mode", _INPUT_MODES)
def test_min_cost_flow_rejects_negative_logical_capacity(mode):
    logical = nx.DiGraph()
    logical.add_edge(0, 1, limit=-1)
    graph = _graph_input(logical, mode)
    with pytest.raises(nx.NetworkXUnfeasible, match="negative capacity"):
        fnx.min_cost_flow(graph, capacity="limit")


def test_min_cost_flow_uses_subclass_edge_provider():
    class PublicEdges(fnx.DiGraph):
        def edges(self, data=False):
            return [(0, 1, {"capacity": 2, "weight": 3})]

    graph = PublicEdges()
    graph.add_node(0, demand=-1)
    graph.add_node(1, demand=1)
    graph.add_edge(0, 1, capacity=0, weight=99)
    assert fnx.min_cost_flow(graph) == {0: {1: 1}, 1: {}}


@pytest.mark.parametrize("mode", _INPUT_MODES)
def test_johnson_uses_negative_logical_weights(mode):
    logical = nx.DiGraph()
    logical.add_weighted_edges_from([(0, 1, 2), (0, 2, 5), (2, 1, -7), (1, 3, 1)])
    graph = _graph_input(logical, mode)
    assert fnx.johnson(graph) == nx.johnson(logical)
    graph[2][1]["weight"] = 1
    logical[2][1]["weight"] = 1
    assert fnx.johnson(graph) == nx.johnson(logical)


def test_ordinary_native_predicate_and_matrix_routes_remain_available(monkeypatch):
    pytest.importorskip("numpy")
    graph = fnx.Graph()
    graph.add_edge(0, 1, weight=3)
    calls = []
    for name in ("_raw_is_empty", "_raw_is_regular", "_native_adjacency_arrays"):
        original = getattr(fnx, name)

        def recorded(*args, _name=name, _original=original, **kwargs):
            calls.append(_name)
            return _original(*args, **kwargs)

        monkeypatch.setattr(fnx, name, recorded)
    assert not fnx.is_empty(graph)
    assert fnx.is_regular(graph)
    assert fnx.to_numpy_array(graph)[0, 1] == 3
    assert calls == ["_raw_is_empty", "_raw_is_regular", "_native_adjacency_arrays"]


def test_ordinary_min_cost_snapshot_keeps_native_bulk_reader(monkeypatch):
    from franken_networkx._network_simplex_native import _FastG

    graph = fnx.DiGraph()
    graph.add_edge(0, 1, capacity=2, weight=3)
    original = fnx.DiGraph._native_edges_with_data
    calls = []

    def recorded(self):
        calls.append(self)
        return original(self)

    monkeypatch.setattr(fnx.DiGraph, "_native_edges_with_data", recorded)
    assert list(_FastG(graph).edges(data=True)) == list(graph.edges(data=True))
    assert calls and all(candidate is graph for candidate in calls)
