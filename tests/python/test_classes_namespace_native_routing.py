"""``franken_networkx.classes`` exposes fnx-native graph types + helpers.

``from networkx.classes import *`` left the core graph TYPES
(Graph/DiGraph/MultiGraph/MultiDiGraph) and ~42 helper functions bound to
networkx's objects, so ``from franken_networkx.classes import Graph``
returned ``nx.Graph`` (a serious drop-in bug) and ``fnx.classes.degree``
etc. resolved to nx's helpers. Types now alias the fnx natives; functions
route via call-time wrappers.

br-r37-c1-2qsqf
"""

from __future__ import annotations

import importlib.util
import inspect
import sys
from functools import lru_cache
from pathlib import Path

import franken_networkx as fnx
import networkx as nx
import pytest
from franken_networkx import classes as fnx_classes

_TYPES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]
_GRAPH_PREDICATES = ("is_directed", "is_multigraph")
_FUNCS = [
    "add_cycle", "add_path", "all_neighbors", "create_empty_copy", "degree",
    "degree_histogram", "density", "edges", "induced_subgraph", "is_directed",
    "neighbors", "nodes", "non_edges", "number_of_edges", "number_of_nodes",
    "number_of_selfloops", "selfloop_edges", "subgraph", "to_directed",
    "to_undirected",
]


@lru_cache(maxsize=1)
def _legacy_networkx():
    module_name = "franken_networkx_legacy_networkx_classes_function"
    legacy_init = (
        Path(__file__).resolve().parents[2]
        / "legacy_networkx_code"
        / "networkx"
        / "networkx"
        / "__init__.py"
    )
    spec = importlib.util.spec_from_file_location(module_name, legacy_init)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("name", _TYPES)
def test_graph_type_is_fnx_native(name):
    cls = getattr(fnx_classes, name)
    assert cls is getattr(fnx, name)
    assert cls is not getattr(nx, name)


@pytest.mark.parametrize("name", _FUNCS)
def test_helper_fn_is_not_networkx_version(name):
    fn = getattr(fnx_classes, name)
    if hasattr(nx, name):
        assert fn is not getattr(nx, name)


def test_imported_graph_type_instantiates_fnx_native():
    from franken_networkx.classes import Graph, DiGraph

    g = Graph([(0, 1), (1, 2)])
    assert type(g).__module__.startswith("franken_networkx")
    assert isinstance(g, fnx.Graph)
    assert fnx_classes.number_of_edges(g) == 2
    dg = DiGraph([(0, 1)])
    assert isinstance(dg, fnx.DiGraph)


@pytest.mark.parametrize("graph_type", _TYPES)
@pytest.mark.parametrize("predicate", _GRAPH_PREDICATES)
def test_native_graph_predicate_signatures_and_errors_match_legacy_oracle(
    graph_type, predicate
):
    legacy = _legacy_networkx()
    actual_class = getattr(fnx_classes, graph_type)
    expected_class = getattr(legacy.classes, graph_type)
    actual_predicate = getattr(actual_class, predicate)
    expected_predicate = getattr(expected_class, predicate)

    assert str(inspect.signature(actual_predicate)) == str(
        inspect.signature(expected_predicate)
    )
    assert actual_predicate(actual_class()) is expected_predicate(expected_class())

    with pytest.raises(TypeError):
        actual_predicate(actual_class(), "unexpected")


def test_helper_function_values_match_networkx():
    g = fnx.complete_graph(4)
    ng = nx.complete_graph(4)
    assert fnx_classes.degree_histogram(g) == nx.degree_histogram(ng)
    assert fnx_classes.density(g) == pytest.approx(nx.density(ng))
    assert fnx_classes.number_of_nodes(g) == nx.number_of_nodes(ng)


def test_classes_functional_view_argument_contract_matches_legacy_oracle():
    legacy = _legacy_networkx()
    legacy_graph = legacy.Graph([("a", "b")])
    graph = fnx.Graph([("a", "b")])

    with pytest.raises(TypeError) as legacy_error:
        legacy.classes.nodes(legacy_graph, ["a"])
    with pytest.raises(type(legacy_error.value)):
        fnx_classes.nodes(graph, ["a"])

    assert list(fnx_classes.edges(graph, nbunch=["a"])) == list(
        legacy.classes.edges(legacy_graph, nbunch=["a"])
    )
    assert list(fnx_classes.degree(graph, nbunch=["a"], weight=None)) == list(
        legacy.classes.degree(legacy_graph, nbunch=["a"], weight=None)
    )


@pytest.mark.parametrize("graph_type", ("Graph", "DiGraph", "MultiGraph", "MultiDiGraph"))
def test_classes_functional_views_match_legacy_oracle_and_remain_live(graph_type):
    legacy = _legacy_networkx()
    legacy_graph = getattr(legacy, graph_type)()
    graph = getattr(fnx, graph_type)()
    for candidate in (legacy_graph, graph):
        candidate.add_edge("a", "b", weight=2)
        candidate.add_edge("a", "a", weight=3)
        candidate.add_node("isolated")

    legacy_edges = legacy.classes.edges(legacy_graph, ["a"])
    edges = fnx_classes.edges(graph, ["a"])
    legacy_degree = legacy.classes.degree(legacy_graph, ["a"], weight="weight")
    degree = fnx_classes.degree(graph, ["a"], weight="weight")

    assert list(edges) == list(legacy_edges)
    assert list(degree) == list(legacy_degree)
    assert list(fnx_classes.nodes(graph)) == list(legacy.classes.nodes(legacy_graph))

    legacy_graph.add_edge("a", "late", weight=5)
    graph.add_edge("a", "late", weight=5)
    assert list(edges) == list(legacy_edges)
    assert degree["a"] == legacy_degree["a"]


def test_high_use_classes_functional_helpers_match_legacy_oracle():
    legacy = _legacy_networkx()
    legacy_graph = legacy.Graph()
    graph = fnx.Graph()

    for helper, nodes in (
        (legacy.classes.add_path, ["a", "b", "c"]),
        (fnx_classes.add_path, ["a", "b", "c"]),
    ):
        helper(legacy_graph if helper is legacy.classes.add_path else graph, nodes, weight=2)
    legacy.classes.add_cycle(legacy_graph, ["c", "d", "e"], color="blue")
    fnx_classes.add_cycle(graph, ["c", "d", "e"], color="blue")

    assert list(fnx_classes.neighbors(graph, "c")) == list(
        legacy.classes.neighbors(legacy_graph, "c")
    )
    assert fnx_classes.number_of_nodes(graph) == legacy.classes.number_of_nodes(
        legacy_graph
    )
    assert fnx_classes.number_of_edges(graph) == legacy.classes.number_of_edges(
        legacy_graph
    )
    assert fnx_classes.density(graph) == legacy.classes.density(legacy_graph)

    legacy_subgraph = legacy.classes.subgraph(legacy_graph, ["a", "b", "c"])
    subgraph = fnx_classes.subgraph(graph, ["a", "b", "c"])
    assert list(subgraph.nodes) == list(legacy_subgraph.nodes)
    assert list(subgraph.edges) == list(legacy_subgraph.edges)

    legacy_edge_subgraph = legacy.classes.edge_subgraph(legacy_graph, [("a", "b")])
    edge_subgraph = fnx_classes.edge_subgraph(graph, [("a", "b")])
    assert list(edge_subgraph.edges) == list(legacy_edge_subgraph.edges)
    assert fnx_classes.is_directed(graph) is legacy.classes.is_directed(legacy_graph)

    legacy_directed = legacy.classes.to_directed(legacy_graph)
    directed = fnx_classes.to_directed(graph)
    assert list(directed.edges) == list(legacy_directed.edges)
    assert not fnx_classes.to_undirected(directed).is_directed()


def test_classes_live_view_helpers_match_legacy_oracle():
    legacy = _legacy_networkx()
    legacy_graph = legacy.DiGraph([("a", "b"), ("b", "c"), ("c", "a")])
    graph = fnx.DiGraph([("a", "b"), ("b", "c"), ("c", "a")])

    legacy_induced = legacy.classes.induced_subgraph(legacy_graph, ["a", "b"])
    induced = fnx_classes.induced_subgraph(graph, ["a", "b"])
    assert list(induced.edges) == list(legacy_induced.edges)

    legacy_filtered = legacy.classes.subgraph_view(
        legacy_graph,
        filter_node=lambda node: node != "c",
        filter_edge=lambda source, target: source != "b",
    )
    filtered = fnx_classes.subgraph_view(
        graph,
        filter_node=lambda node: node != "c",
        filter_edge=lambda source, target: source != "b",
    )
    assert list(filtered.edges) == list(legacy_filtered.edges)

    legacy_restricted = legacy.classes.restricted_view(
        legacy_graph, ["c"], [("a", "b")]
    )
    restricted = fnx_classes.restricted_view(graph, ["c"], [("a", "b")])
    assert list(restricted.edges) == list(legacy_restricted.edges)

    legacy_reversed = legacy.classes.reverse_view(legacy_graph)
    reversed_view = fnx_classes.reverse_view(graph)
    assert list(reversed_view.edges) == list(legacy_reversed.edges)

    legacy_graph.add_edge("b", "late")
    graph.add_edge("b", "late")
    assert list(reversed_view.edges) == list(legacy_reversed.edges)

    with pytest.raises(legacy.NetworkXNotImplemented):
        legacy.classes.reverse_view(legacy.Graph())
    with pytest.raises(fnx.NetworkXNotImplemented):
        fnx_classes.reverse_view(fnx.Graph())


def test_classes_scalar_topology_helpers_match_legacy_oracle():
    legacy = _legacy_networkx()
    legacy_graph = legacy.Graph()
    graph = fnx.Graph()
    legacy.classes.add_star(legacy_graph, ["hub", "a", "b"], weight=3)
    fnx_classes.add_star(graph, ["hub", "a", "b"], weight=3)
    for candidate in (legacy_graph, graph):
        candidate.add_edge("a", "a", weight=5)
        candidate.add_node("isolated")

    assert list(fnx_classes.all_neighbors(graph, "hub")) == list(
        legacy.classes.all_neighbors(legacy_graph, "hub")
    )
    assert list(fnx_classes.common_neighbors(graph, "a", "b")) == list(
        legacy.classes.common_neighbors(legacy_graph, "a", "b")
    )
    assert fnx_classes.degree_histogram(graph) == legacy.classes.degree_histogram(
        legacy_graph
    )
    assert fnx_classes.is_path(graph, ["a", "hub", "b"]) is legacy.classes.is_path(
        legacy_graph, ["a", "hub", "b"]
    )
    assert fnx_classes.is_path(graph, ["a", "isolated"]) is legacy.classes.is_path(
        legacy_graph, ["a", "isolated"]
    )
    assert list(fnx_classes.nodes_with_selfloops(graph)) == list(
        legacy.classes.nodes_with_selfloops(legacy_graph)
    )
    assert list(fnx_classes.non_edges(graph)) == list(legacy.classes.non_edges(legacy_graph))
    assert list(fnx_classes.non_neighbors(graph, "hub")) == list(
        legacy.classes.non_neighbors(legacy_graph, "hub")
    )
    assert fnx_classes.path_weight(graph, ["a", "hub", "b"], "weight") == (
        legacy.classes.path_weight(legacy_graph, ["a", "hub", "b"], "weight")
    )
    assert list(fnx_classes.selfloop_edges(graph, data=True, default=None)) == list(
        legacy.classes.selfloop_edges(legacy_graph, data=True, default=None)
    )


@pytest.mark.parametrize("with_data", (True, False))
def test_classes_lifecycle_helpers_match_legacy_oracle(with_data):
    legacy = _legacy_networkx()
    legacy_graph = legacy.Graph(graph_label="legacy")
    graph = fnx.Graph(graph_label="legacy")
    for candidate in (legacy_graph, graph):
        candidate.add_node("node", label="kept")
        candidate.add_edge("node", "other", weight=4)

    legacy_copy = legacy.classes.create_empty_copy(legacy_graph, with_data=with_data)
    copied = fnx_classes.create_empty_copy(graph, with_data=with_data)
    assert list(copied.nodes(data=True)) == list(legacy_copy.nodes(data=True))
    assert copied.graph == legacy_copy.graph
    assert list(copied.edges(data=True)) == list(legacy_copy.edges(data=True))

    assert fnx_classes.is_frozen(graph) is legacy.classes.is_frozen(legacy_graph)
    assert fnx_classes.freeze(graph) is graph
    assert legacy.classes.freeze(legacy_graph) is legacy_graph
    assert fnx_classes.is_frozen(graph) is legacy.classes.is_frozen(legacy_graph)
    with pytest.raises(legacy.NetworkXError):
        legacy_graph.add_node("blocked")
    with pytest.raises(fnx.NetworkXError):
        graph.add_node("blocked")


def test_classes_attribute_helpers_match_legacy_oracle_and_backend_contract():
    legacy = _legacy_networkx()
    legacy_graph = legacy.Graph([("a", "b"), ("b", "c")])
    graph = fnx.Graph([("a", "b"), ("b", "c")])

    legacy.classes.set_node_attributes(
        legacy_graph, {"a": 1, "b": 2}, "tier", backend="networkx"
    )
    fnx_classes.set_node_attributes(
        graph, {"a": 1, "b": 2}, "tier", backend="networkx"
    )
    legacy.classes.set_edge_attributes(
        legacy_graph, {("a", "b"): 4}, "cost", backend="networkx"
    )
    fnx_classes.set_edge_attributes(
        graph, {("a", "b"): 4}, "cost", backend="networkx"
    )

    assert fnx_classes.get_node_attributes(graph, "tier", default=0) == (
        legacy.classes.get_node_attributes(legacy_graph, "tier", default=0)
    )
    assert fnx_classes.get_edge_attributes(graph, "cost", default=0) == (
        legacy.classes.get_edge_attributes(legacy_graph, "cost", default=0)
    )

    with pytest.raises(ImportError):
        legacy.classes.get_node_attributes(legacy_graph, "tier", backend="missing")
    with pytest.raises(ImportError):
        fnx_classes.get_node_attributes(graph, "tier", backend="missing")
    with pytest.raises(TypeError) as legacy_error:
        legacy.classes.set_edge_attributes(legacy_graph, {}, unexpected=True)
    with pytest.raises(type(legacy_error.value)):
        fnx_classes.set_edge_attributes(graph, {}, unexpected=True)


def test_classes_edge_property_helpers_match_legacy_oracle_and_errors():
    legacy = _legacy_networkx()
    legacy_graph = legacy.Graph([("a", "a", {"weight": -2}), ("a", "b", {"weight": 3})])
    graph = fnx.Graph([("a", "a", {"weight": -2}), ("a", "b", {"weight": 3})])

    for helper in (
        "number_of_selfloops",
        "is_weighted",
        "is_negatively_weighted",
    ):
        legacy_helper = getattr(legacy.classes, helper)
        fnx_helper = getattr(fnx_classes, helper)
        assert fnx_helper(graph, backend="networkx") == legacy_helper(
            legacy_graph, backend="networkx"
        )

    assert fnx_classes.is_weighted(graph, edge=("a", "b")) is legacy.classes.is_weighted(
        legacy_graph, edge=("a", "b")
    )
    assert fnx_classes.is_negatively_weighted(
        graph, edge=("a", "a")
    ) is legacy.classes.is_negatively_weighted(legacy_graph, edge=("a", "a"))

    with pytest.raises(legacy.NetworkXError) as legacy_error:
        legacy.classes.is_weighted(legacy_graph, edge=("missing", "edge"))
    with pytest.raises(fnx.NetworkXError) as fnx_error:
        fnx_classes.is_weighted(graph, edge=("missing", "edge"))
    assert str(fnx_error.value) == str(legacy_error.value)


def test_remaining_classes_helpers_match_legacy_oracle(capsys):
    legacy = _legacy_networkx()
    legacy_graph = legacy.Graph(name="described")
    graph = fnx.Graph(name="described")
    for candidate in (legacy_graph, graph):
        candidate.add_edge("a", "b", cost=7, label="remove")
        candidate.add_node("a", tier=1, label="remove")
        candidate.add_node("b", tier=2, label="remove")

    legacy.classes.describe(legacy_graph, describe_hook=lambda G: {"Hook": len(G)})
    legacy_output = capsys.readouterr().out
    fnx_classes.describe(graph, describe_hook=lambda G: {"Hook": len(G)})
    assert capsys.readouterr().out == legacy_output

    assert fnx_classes.is_empty(fnx.Graph(), backend="networkx") is legacy.classes.is_empty(
        legacy.Graph(), backend="networkx"
    )
    assert fnx_classes.is_empty(graph) is legacy.classes.is_empty(legacy_graph)

    legacy.classes.remove_node_attributes(
        legacy_graph, "label", nbunch=["a", "missing"], backend="networkx"
    )
    fnx_classes.remove_node_attributes(
        graph, "label", nbunch=["a", "missing"], backend="networkx"
    )
    legacy.classes.remove_edge_attributes(
        legacy_graph, "label", ebunch=[("a", "b")], backend="networkx"
    )
    fnx_classes.remove_edge_attributes(
        graph, "label", ebunch=[("a", "b")], backend="networkx"
    )
    assert list(graph.nodes(data=True)) == list(legacy_graph.nodes(data=True))
    assert list(graph.edges(data=True)) == list(legacy_graph.edges(data=True))

    assert fnx_classes.remove_node_attributes(graph) is legacy.classes.remove_node_attributes(
        legacy_graph
    )
    assert fnx_classes.remove_edge_attributes(graph) is legacy.classes.remove_edge_attributes(
        legacy_graph
    )
