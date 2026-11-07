import inspect
import networkx as nx
import operator
import pytest
import random
import re
from builtins import ValueError as BuiltinValueError

import franken_networkx as fnx

from franken_networkx.backend import _fnx_to_nx as _to_nx


def _mapping_signature(mapping):
    return tuple(
        sorted(
            (
                type(left).__name__,
                repr(left),
                type(right).__name__,
                repr(right),
            )
            for left, right in mapping.items()
        )
    )


def _block_networkx_graph_edit(monkeypatch):
    def fail_networkx(*args, **kwargs):
        raise AssertionError("NetworkX graph-edit fallback should not be used")

    monkeypatch.setattr(nx, "graph_edit_distance", fail_networkx)
    monkeypatch.setattr(nx, "optimal_edit_paths", fail_networkx)
    monkeypatch.setattr(nx, "optimize_edit_paths", fail_networkx)
    monkeypatch.setattr(nx, "optimize_graph_edit_distance", fail_networkx)


_ISOMORPHISM_MATCH_HELPERS = [
    "categorical_node_match",
    "categorical_edge_match",
    "categorical_multiedge_match",
    "numerical_node_match",
    "numerical_edge_match",
    "numerical_multiedge_match",
    "generic_node_match",
    "generic_edge_match",
    "generic_multiedge_match",
]


@pytest.mark.parametrize("helper_name", _ISOMORPHISM_MATCH_HELPERS)
def test_isomorphism_match_helper_signatures_match_networkx(helper_name):
    # br-r37-c1-iso-removed: matchers live at fnx.algorithms.isomorphism
    assert inspect.signature(getattr(fnx.algorithms.isomorphism, helper_name)) == inspect.signature(
        getattr(nx.algorithms.isomorphism, helper_name)
    )


@pytest.mark.parametrize(
    ("helper_name", "factory_args", "matching_attrs", "mismatching_attrs"),
    [
        (
            "categorical_node_match",
            ("color", "red"),
            ({"color": "red"}, {"color": "red"}),
            ({"color": "red"}, {"color": "blue"}),
        ),
        (
            "categorical_edge_match",
            ("relation", "friend"),
            ({"relation": "friend"}, {"relation": "friend"}),
            ({"relation": "friend"}, {"relation": "blocked"}),
        ),
        (
            "categorical_multiedge_match",
            ("color", "red"),
            (
                {0: {"color": "red"}, 1: {"color": "blue"}},
                {0: {"color": "blue"}, 1: {"color": "red"}},
            ),
            ({0: {"color": "red"}}, {0: {"color": "blue"}}),
        ),
        (
            "numerical_node_match",
            ("weight", 1.0),
            ({"weight": 1.0}, {"weight": 1.000000001}),
            ({"weight": 1.0}, {"weight": 1.1}),
        ),
        (
            "numerical_edge_match",
            ("weight", 1.0),
            ({"weight": 3.0}, {"weight": 3.000000001}),
            ({"weight": 3.0}, {"weight": 4.0}),
        ),
        (
            "numerical_multiedge_match",
            ("weight", 1.0),
            (
                {0: {"weight": 1.0}, 1: {"weight": 2.0}},
                {0: {"weight": 2.0}, 1: {"weight": 1.0}},
            ),
            ({0: {"weight": 1.0}}, {0: {"weight": 2.0}}),
        ),
        (
            "generic_node_match",
            ("color", "red", operator.eq),
            ({"color": "red"}, {"color": "red"}),
            ({"color": "red"}, {"color": "blue"}),
        ),
        (
            "generic_edge_match",
            ("weight", 1, operator.eq),
            ({"weight": 2}, {"weight": 2}),
            ({"weight": 2}, {"weight": 3}),
        ),
        (
            "generic_multiedge_match",
            ("weight", 1, operator.eq),
            (
                {0: {"weight": 1}, 1: {"weight": 2}},
                {0: {"weight": 2}, 1: {"weight": 1}},
            ),
            ({0: {"weight": 1}}, {0: {"weight": 2}}),
        ),
    ],
)
def test_isomorphism_match_helpers_match_networkx(
    helper_name,
    factory_args,
    matching_attrs,
    mismatching_attrs,
):
    # br-r37-c1-iso-removed: matchers live at fnx.algorithms.isomorphism
    matcher = getattr(fnx.algorithms.isomorphism, helper_name)(*factory_args)
    expected = getattr(nx.algorithms.isomorphism, helper_name)(*factory_args)

    assert matcher(*matching_attrs) == expected(*matching_attrs)
    assert matcher(*mismatching_attrs) == expected(*mismatching_attrs)


def test_ismags_signature_and_full_isomorphism_match_networkx():
    assert inspect.signature(fnx.ISMAGS) == inspect.signature(
        nx.algorithms.isomorphism.ISMAGS
    )

    graph = fnx.Graph()
    graph.add_node(0, color="red")
    graph.add_node(1, color="blue")
    graph.add_node(2, color="green")
    graph.add_edge(0, 1, weight=2)
    graph.add_edge(1, 2, weight=3)

    target = fnx.Graph()
    target.add_node("a", color="red")
    target.add_node("b", color="blue")
    target.add_node("c", color="green")
    target.add_edge("a", "b", weight=2)
    target.add_edge("b", "c", weight=3)

    def node_match(left, right):
        return left == right

    def edge_match(left, right):
        return left == right

    matcher = fnx.ISMAGS(
        graph,
        target,
        node_match=node_match,
        edge_match=edge_match,
    )
    expected = nx.algorithms.isomorphism.ISMAGS(
        _to_nx(graph),
        _to_nx(target),
        node_match=node_match,
        edge_match=edge_match,
    )

    assert isinstance(matcher, nx.algorithms.isomorphism.ISMAGS)
    for symmetry in (False, True):
        assert matcher.is_isomorphic(symmetry=symmetry) == expected.is_isomorphic(
            symmetry=symmetry
        )
    assert _mapping_signatures(matcher.isomorphisms_iter()) == _mapping_signatures(
        expected.isomorphisms_iter()
    )


def test_ismags_subgraph_methods_match_networkx():
    graph = fnx.path_graph(3)
    subgraph = fnx.path_graph(2)

    matcher = fnx.ISMAGS(graph, subgraph)
    expected = nx.algorithms.isomorphism.ISMAGS(_to_nx(graph), _to_nx(subgraph))

    assert matcher.subgraph_is_isomorphic() == expected.subgraph_is_isomorphic()
    assert _mapping_signatures(matcher.subgraph_isomorphisms_iter()) == _mapping_signatures(
        expected.subgraph_isomorphisms_iter()
    )
    assert _mapping_signatures(matcher.largest_common_subgraph()) == _mapping_signatures(
        expected.largest_common_subgraph()
    )


@pytest.mark.parametrize(
    ("fnx_graph_cls", "nx_graph_cls", "fnx_matcher_cls", "nx_matcher_cls"),
    [
        (
            fnx.Graph,
            nx.Graph,
            fnx.TimeRespectingGraphMatcher,
            nx.algorithms.isomorphism.TimeRespectingGraphMatcher,
        ),
        (
            fnx.DiGraph,
            nx.DiGraph,
            fnx.TimeRespectingDiGraphMatcher,
            nx.algorithms.isomorphism.TimeRespectingDiGraphMatcher,
        ),
    ],
)
def test_time_respecting_matchers_match_networkx(
    fnx_graph_cls,
    nx_graph_cls,
    fnx_matcher_cls,
    nx_matcher_cls,
):
    assert inspect.signature(fnx_matcher_cls) == inspect.signature(nx_matcher_cls)

    graph = fnx_graph_cls()
    graph.add_edge(0, 1, date=1)
    graph.add_edge(1, 2, date=2)

    target = fnx_graph_cls()
    target.add_edge("a", "b", date=1)
    target.add_edge("b", "c", date=2)

    expected_graph = nx_graph_cls()
    expected_graph.add_edge(0, 1, date=1)
    expected_graph.add_edge(1, 2, date=2)

    expected_target = nx_graph_cls()
    expected_target.add_edge("a", "b", date=1)
    expected_target.add_edge("b", "c", date=2)

    matcher = fnx_matcher_cls(graph, target, "date", 1)
    expected = nx_matcher_cls(expected_graph, expected_target, "date", 1)

    assert isinstance(matcher, nx_matcher_cls)
    assert matcher.is_isomorphic() == expected.is_isomorphic()
    assert _mapping_signatures(matcher.isomorphisms_iter()) == _mapping_signatures(
        expected.isomorphisms_iter()
    )
    assert matcher.subgraph_is_isomorphic() == expected.subgraph_is_isomorphic()
    assert _mapping_signatures(matcher.subgraph_isomorphisms_iter()) == _mapping_signatures(
        expected.subgraph_isomorphisms_iter()
    )


def test_top_level_isomorphism_module_exports_franken_wrappers():
    import franken_networkx.isomorphism as fnx_iso

    expected_exports = (
        "GraphMatcher",
        "DiGraphMatcher",
        "MultiGraphMatcher",
        "MultiDiGraphMatcher",
        "ISMAGS",
        "TimeRespectingGraphMatcher",
        "TimeRespectingDiGraphMatcher",
        "categorical_node_match",
        "numerical_edge_match",
        "generic_multiedge_match",
        "is_isomorphic",
        "vf2pp_is_isomorphic",
        "tree_isomorphism",
        "rooted_tree_isomorphism",
    )

    assert fnx_iso is fnx.isomorphism
    # br-r37-c1-iso-removed: matchers live only at
    # fnx.algorithms.isomorphism (which is the nx submodule).  They
    # are not in fnx top-level nor fnx.isomorphism (the local
    # franken submodule).  Verify they are reachable via
    # fnx.algorithms.isomorphism for the matcher names; verify the
    # other names (matchers + Graph types) live in fnx.isomorphism.
    # br-r37-c1-rhwwa: tree_isomorphism / rooted_tree_isomorphism were
    # also hidden from fnx top-level (br-r37-c1-dm5jl); they live at
    # fnx.algorithms.isomorphism via the auto-bound nx submodule.
    _MATCHERS_AT_ALGO_ONLY = {
        "categorical_node_match", "numerical_edge_match", "generic_multiedge_match",
        "tree_isomorphism", "rooted_tree_isomorphism",
    }
    for export_name in expected_exports:
        if export_name in _MATCHERS_AT_ALGO_ONLY:
            assert hasattr(fnx.algorithms.isomorphism, export_name)
            continue
        assert export_name in fnx_iso.__all__
        assert getattr(fnx_iso, export_name) is getattr(fnx, export_name)

    graph = fnx.path_graph(3)
    target = fnx.relabel_nodes(graph, {0: "a", 1: "b", 2: "c"})
    matcher = fnx_iso.GraphMatcher(graph, target)
    expected = nx.algorithms.isomorphism.GraphMatcher(_to_nx(graph), _to_nx(target))

    assert isinstance(matcher, nx.algorithms.isomorphism.GraphMatcher)
    assert matcher.is_isomorphic() == expected.is_isomorphic()
    assert _mapping_signatures(matcher.isomorphisms_iter()) == _mapping_signatures(
        expected.isomorphisms_iter()
    )


@pytest.mark.parametrize(
    ("fnx_graph_cls", "nx_graph_cls", "fnx_matcher_cls", "nx_matcher_cls"),
    [
        (fnx.Graph, nx.Graph, fnx.GraphMatcher, nx.algorithms.isomorphism.GraphMatcher),
        (
            fnx.DiGraph,
            nx.DiGraph,
            fnx.DiGraphMatcher,
            nx.algorithms.isomorphism.DiGraphMatcher,
        ),
        (
            fnx.MultiGraph,
            nx.MultiGraph,
            fnx.MultiGraphMatcher,
            nx.algorithms.isomorphism.MultiGraphMatcher,
        ),
        (
            fnx.MultiDiGraph,
            nx.MultiDiGraph,
            fnx.MultiDiGraphMatcher,
            nx.algorithms.isomorphism.MultiDiGraphMatcher,
        ),
    ],
)
def test_vf2_matcher_classes_match_networkx_api(
    fnx_graph_cls,
    nx_graph_cls,
    fnx_matcher_cls,
    nx_matcher_cls,
):
    graph = fnx_graph_cls()
    graph.add_edges_from([(0, 1), (1, 2)])
    graph.nodes[0]["color"] = "red"
    graph.nodes[1]["color"] = "blue"
    graph.nodes[2]["color"] = "green"

    expected_graph = nx_graph_cls()
    expected_graph.add_edges_from([(0, 1), (1, 2)])
    expected_graph.nodes[0]["color"] = "red"
    expected_graph.nodes[1]["color"] = "blue"
    expected_graph.nodes[2]["color"] = "green"

    target = fnx_graph_cls()
    target.add_edges_from([("a", "b"), ("b", "c")])
    target.nodes["a"]["color"] = "red"
    target.nodes["b"]["color"] = "blue"
    target.nodes["c"]["color"] = "green"

    expected_target = nx_graph_cls()
    expected_target.add_edges_from([("a", "b"), ("b", "c")])
    expected_target.nodes["a"]["color"] = "red"
    expected_target.nodes["b"]["color"] = "blue"
    expected_target.nodes["c"]["color"] = "green"

    def node_match(left, right):
        return left == right

    matcher = fnx_matcher_cls(graph, target, node_match=node_match)
    expected = nx_matcher_cls(expected_graph, expected_target, node_match=node_match)

    assert isinstance(matcher, nx_matcher_cls)
    assert matcher.is_isomorphic() == expected.is_isomorphic()
    assert {_mapping_signature(mapping) for mapping in matcher.isomorphisms_iter()} == {
        _mapping_signature(mapping) for mapping in expected.isomorphisms_iter()
    }
    assert matcher.subgraph_is_isomorphic() == expected.subgraph_is_isomorphic()
    assert {
        _mapping_signature(mapping) for mapping in matcher.subgraph_isomorphisms_iter()
    } == {
        _mapping_signature(mapping) for mapping in expected.subgraph_isomorphisms_iter()
    }
    for method_name in (
        "match",
        "candidate_pairs_iter",
        "semantic_feasibility",
        "syntactic_feasibility",
        "initialize",
    ):
        assert callable(getattr(matcher, method_name))


def test_is_isomorphic_uses_rust_when_no_callbacks(monkeypatch):
    g1 = fnx.path_graph(4)
    g2 = fnx.path_graph(4)
    called = {"rust": False}

    def fake_rust(left, right):
        called["rust"] = True
        assert left is g1
        assert right is g2
        return True

    def fail_networkx(*args, **kwargs):
        raise AssertionError("unexpected NetworkX fallback")

    monkeypatch.setattr(fnx, "_is_isomorphic_rust", fake_rust)
    monkeypatch.setattr(nx, "is_isomorphic", fail_networkx)

    assert fnx.is_isomorphic(g1, g2) is True
    assert called["rust"] is True


def test_is_isomorphic_with_callbacks_avoids_networkx(monkeypatch):
    g1 = fnx.Graph()
    g1.add_node(1, color="red")
    g1.add_node(2, color="blue")
    g1.add_edge(1, 2)

    g2 = fnx.Graph()
    g2.add_node("a", color="red")
    g2.add_node("b", color="green")
    g2.add_edge("a", "b")

    def fail_rust(*args, **kwargs):
        raise AssertionError("Rust fast path should not be used with callbacks")

    def node_match(left, right):
        return left == right

    expected = nx.is_isomorphic(
        _to_nx(g1),
        _to_nx(g2),
        node_match=node_match,
    )

    def fail_networkx(*args, **kwargs):
        raise AssertionError("unexpected NetworkX fallback")

    monkeypatch.setattr(fnx, "_is_isomorphic_rust", fail_rust)
    monkeypatch.setattr(nx, "is_isomorphic", fail_networkx)

    assert fnx.is_isomorphic(g1, g2, node_match=node_match) == expected


def test_could_be_isomorphic_properties_matches_networkx_without_fallback(monkeypatch):
    g1 = fnx.Graph()
    g1.add_edges_from(
        [(0, 1), (0, 2), (0, 3), (0, 4), (1, 2), (3, 4), (4, 5), (4, 6), (0, 7)]
    )
    g2 = fnx.Graph()
    g2.add_edges_from(
        [(0, 1), (0, 2), (0, 3), (0, 4), (1, 2), (3, 4), (4, 5), (4, 6), (4, 7)]
    )

    expected = {
        properties: nx.could_be_isomorphic(_to_nx(g1), _to_nx(g2), properties=properties)
        for properties in ("d", "t", "dt", "c", "dtc", "x")
    }

    def fail_networkx(*args, **kwargs):
        raise AssertionError("unexpected NetworkX fallback")

    monkeypatch.setattr(nx, "could_be_isomorphic", fail_networkx)

    actual = {
        properties: fnx.could_be_isomorphic(g1, g2, properties=properties)
        for properties in ("d", "t", "dt", "c", "dtc", "x")
    }

    assert actual == expected


@pytest.mark.parametrize("properties", ["d", "x", "t", "dtc"])
def test_could_be_isomorphic_directed_properties_match_networkx_without_fallback(
    monkeypatch, properties
):
    g1 = fnx.DiGraph()
    g1.add_edges_from([(0, 1), (1, 2)])
    g2 = fnx.DiGraph()
    g2.add_edges_from([("a", "b"), ("b", "c")])

    try:
        expected = nx.could_be_isomorphic(_to_nx(g1), _to_nx(g2), properties=properties)
    except Exception as exc:
        expected = exc

    def fail_networkx(*args, **kwargs):
        raise AssertionError("unexpected NetworkX fallback")

    monkeypatch.setattr(nx, "could_be_isomorphic", fail_networkx)

    if isinstance(expected, Exception):
        with pytest.raises(getattr(fnx, type(expected).__name__), match=str(expected)):
            fnx.could_be_isomorphic(g1, g2, properties=properties)
    else:
        assert fnx.could_be_isomorphic(g1, g2, properties=properties) == expected


def test_vf2pp_is_isomorphic_matches_networkx():
    g1 = fnx.path_graph(4)
    g2 = fnx.relabel_nodes(g1, {0: "a", 1: "b", 2: "c", 3: "d"})
    g2.nodes["a"]["color"] = "red"
    g2.nodes["b"]["color"] = "blue"
    g2.nodes["c"]["color"] = "blue"
    g2.nodes["d"]["color"] = "red"
    g1.nodes[0]["color"] = "red"
    g1.nodes[1]["color"] = "blue"
    g1.nodes[2]["color"] = "blue"
    g1.nodes[3]["color"] = "red"

    assert fnx.vf2pp_is_isomorphic(g1, g2, node_label="color") == nx.vf2pp_is_isomorphic(
        _to_nx(g1),
        _to_nx(g2),
        node_label="color",
    )


def test_vf2pp_is_isomorphic_with_labels_avoids_networkx(monkeypatch):
    g1 = fnx.path_graph(4)
    g2 = fnx.relabel_nodes(g1, {0: "a", 1: "b", 2: "c", 3: "d"})
    g1.nodes[0]["color"] = "red"
    g1.nodes[1]["color"] = "blue"
    g1.nodes[2]["color"] = "blue"
    g1.nodes[3]["color"] = "red"
    g2.nodes["a"]["color"] = "red"
    g2.nodes["b"]["color"] = "blue"
    g2.nodes["c"]["color"] = "blue"
    g2.nodes["d"]["color"] = "red"

    expected = nx.vf2pp_is_isomorphic(_to_nx(g1), _to_nx(g2), node_label="color")

    def fail_networkx(*args, **kwargs):
        raise AssertionError("unexpected NetworkX fallback")

    monkeypatch.setattr(nx, "vf2pp_is_isomorphic", fail_networkx)
    monkeypatch.setattr(nx, "vf2pp_isomorphism", fail_networkx)
    monkeypatch.setattr(nx, "vf2pp_all_isomorphisms", fail_networkx)

    assert fnx.vf2pp_is_isomorphic(g1, g2, node_label="color") == expected


def test_vf2pp_is_isomorphic_with_default_label_avoids_networkx(monkeypatch):
    g1 = fnx.path_graph(3)
    g2 = fnx.relabel_nodes(g1, {0: "a", 1: "b", 2: "c"})
    g1.nodes[0]["color"] = "red"
    g1.nodes[2]["color"] = "blue"
    g2.nodes["a"]["color"] = "red"
    g2.nodes["b"]["color"] = "blue"

    expected = nx.vf2pp_is_isomorphic(
        _to_nx(g1),
        _to_nx(g2),
        node_label="color",
        default_label="blue",
    )

    def fail_networkx(*args, **kwargs):
        raise AssertionError("unexpected NetworkX fallback")

    monkeypatch.setattr(nx, "vf2pp_is_isomorphic", fail_networkx)
    monkeypatch.setattr(nx, "vf2pp_isomorphism", fail_networkx)
    monkeypatch.setattr(nx, "vf2pp_all_isomorphisms", fail_networkx)

    assert (
        fnx.vf2pp_is_isomorphic(
            g1,
            g2,
            node_label="color",
            default_label="blue",
        )
        == expected
    )


def test_vf2pp_isomorphism_mapping_preserves_edges():
    g1 = fnx.cycle_graph(4)
    g2 = fnx.Graph()
    g2.add_edges_from([("a", "b"), ("b", "c"), ("c", "d"), ("d", "a")])

    mapping = fnx.vf2pp_isomorphism(g1, g2)

    assert set(mapping) == set(g1.nodes())
    assert set(mapping.values()) == set(g2.nodes())
    mapped_edges = {
        frozenset((mapping[u], mapping[v]))
        for u, v in g1.edges()
    }
    expected_edges = {frozenset(edge) for edge in g2.edges()}
    assert mapped_edges == expected_edges


def test_vf2pp_isomorphism_uses_rust_without_labels(monkeypatch):
    g1 = fnx.path_graph(3)
    g2 = fnx.relabel_nodes(g1, {0: "a", 1: "b", 2: "c"})
    called = {"rust": False}

    def fake_rust(left, right):
        called["rust"] = True
        assert left is g1
        assert right is g2
        return {0: "a", 1: "b", 2: "c"}

    def fail_networkx(*args, **kwargs):
        raise AssertionError("unexpected NetworkX fallback")

    monkeypatch.setattr(fnx, "_vf2pp_isomorphism_rust", fake_rust)
    monkeypatch.setattr(nx, "vf2pp_isomorphism", fail_networkx)

    assert fnx.vf2pp_isomorphism(g1, g2) == {0: "a", 1: "b", 2: "c"}
    assert called["rust"] is True


def test_vf2pp_isomorphism_with_labels_avoids_networkx(monkeypatch):
    g1 = fnx.path_graph(4)
    g2 = fnx.relabel_nodes(g1, {0: "a", 1: "b", 2: "c", 3: "d"})
    g1.nodes[0]["color"] = "red"
    g1.nodes[1]["color"] = "blue"
    g1.nodes[2]["color"] = "blue"
    g1.nodes[3]["color"] = "red"
    g2.nodes["a"]["color"] = "red"
    g2.nodes["b"]["color"] = "blue"
    g2.nodes["c"]["color"] = "blue"
    g2.nodes["d"]["color"] = "red"

    expected_mappings = list(
        nx.vf2pp_all_isomorphisms(_to_nx(g1), _to_nx(g2), node_label="color")
    )

    def fail_networkx(*args, **kwargs):
        raise AssertionError("unexpected NetworkX fallback")

    monkeypatch.setattr(nx, "vf2pp_is_isomorphic", fail_networkx)
    monkeypatch.setattr(nx, "vf2pp_isomorphism", fail_networkx)
    monkeypatch.setattr(nx, "vf2pp_all_isomorphisms", fail_networkx)

    actual = fnx.vf2pp_isomorphism(g1, g2, node_label="color")
    assert actual in expected_mappings


def test_vf2pp_all_isomorphisms_count_matches_networkx():
    g1 = fnx.cycle_graph(4)
    g2 = fnx.cycle_graph(4)

    assert len(list(fnx.vf2pp_all_isomorphisms(g1, g2))) == len(
        list(nx.vf2pp_all_isomorphisms(_to_nx(g1), _to_nx(g2)))
    )


@pytest.mark.parametrize("class_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
def test_vf2pp_all_isomorphisms_without_labels_yields_a_bounded_prefix(monkeypatch, class_name):
    # The former native-route assertion required a complete Vec of mappings.
    # Consuming one mapping of K12 must not enumerate its 12! automorphisms.
    left = nx.complete_graph(12, create_using=getattr(nx, class_name))
    right = nx.relabel_nodes(left, {i: f"node-{i}" for i in left})
    fleft, fright = getattr(fnx, class_name)(left), getattr(fnx, class_name)(right)

    def reject_eager_enumeration(*args, **kwargs):
        raise AssertionError("prefix query used eager native or NetworkX enumeration")

    monkeypatch.setattr(fnx, "_vf2pp_all_isomorphisms_rust", reject_eager_enumeration)
    for name in ("vf2pp_all_isomorphisms", "vf2pp_isomorphism", "vf2pp_is_isomorphic"):
        monkeypatch.setattr(nx, name, reject_eager_enumeration)
    iterator = fnx.vf2pp_all_isomorphisms(fleft, fright)
    mapping = next(iterator)
    assert set(mapping) == set(left)
    assert set(mapping.values()) == set(right)
    iterator.close()


def test_vf2pp_all_isomorphisms_with_labels_avoids_networkx(monkeypatch):
    g1 = fnx.cycle_graph(4)
    g2 = fnx.relabel_nodes(g1, {0: "a", 1: "b", 2: "c", 3: "d"})
    g1.nodes[0]["color"] = "red"
    g1.nodes[1]["color"] = "blue"
    g1.nodes[2]["color"] = "red"
    g1.nodes[3]["color"] = "blue"
    g2.nodes["a"]["color"] = "blue"
    g2.nodes["b"]["color"] = "red"
    g2.nodes["c"]["color"] = "blue"
    g2.nodes["d"]["color"] = "red"

    expected = list(nx.vf2pp_all_isomorphisms(_to_nx(g1), _to_nx(g2), node_label="color"))

    def fail_networkx(*args, **kwargs):
        raise AssertionError("unexpected NetworkX fallback")

    monkeypatch.setattr(nx, "vf2pp_is_isomorphic", fail_networkx)
    monkeypatch.setattr(nx, "vf2pp_isomorphism", fail_networkx)
    monkeypatch.setattr(nx, "vf2pp_all_isomorphisms", fail_networkx)

    actual = list(fnx.vf2pp_all_isomorphisms(g1, g2, node_label="color"))
    assert {_mapping_signature(mapping) for mapping in actual} == {
        _mapping_signature(mapping) for mapping in expected
    }


@pytest.mark.parametrize("class_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("seed", range(12))
def test_labeled_vf2pp_preserves_complete_mapping_sets(class_name, seed):
    rng = random.Random(seed)
    left = getattr(nx, class_name)()
    left.add_nodes_from((i, {"color": i % 2}) for i in range(5))
    for u in left:
        for v in left:
            if not left.is_directed() and v < u:
                continue
            if rng.random() < 0.25:
                left.add_edge(u, v)
                if left.is_multigraph() and rng.random() < 0.5:
                    left.add_edge(u, v)
    right = nx.relabel_nodes(left, {i: f"node-{4 - i}" for i in left})
    if seed % 3 == 1:
        right.nodes["node-4"]["color"] = "different"
    elif seed % 3 == 2:
        right.remove_edges_from(list(right.edges())[::2])
    expected = list(nx.vf2pp_all_isomorphisms(left, right, node_label="color"))
    fleft, fright = getattr(fnx, class_name)(left), getattr(fnx, class_name)(right)
    actual = list(fnx.vf2pp_all_isomorphisms(fleft, fright, node_label="color"))
    assert _mapping_signatures(actual) == _mapping_signatures(expected)
    assert fnx.vf2pp_is_isomorphic(fleft, fright, node_label="color") == bool(expected)
    first = fnx.vf2pp_isomorphism(fleft, fright, node_label="color")
    assert first in expected if expected else first is None


@pytest.mark.parametrize("class_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("distinct_labels", [False, True])
@pytest.mark.parametrize("operation", ["vf2pp_is_isomorphic", "vf2pp_isomorphism", "vf2pp_all_isomorphisms"])
def test_labeled_vf2pp_short_circuits_symmetric_search(
    monkeypatch, class_name, distinct_labels, operation
):
    # A complete 12-node graph has 12! structural automorphisms. Neither a
    # boolean query nor the first iterator result may construct that list.
    left = nx.complete_graph(12, create_using=getattr(nx, class_name))
    nx.set_node_attributes(left, {i: i if distinct_labels else "same" for i in left}, "color")
    right = nx.relabel_nodes(left, {i: f"node-{i}" for i in left})
    fleft, fright = getattr(fnx, class_name)(left), getattr(fnx, class_name)(right)

    def reject_enumeration(*args, **kwargs):
        raise AssertionError("labeled search enumerated unfiltered automorphisms")

    monkeypatch.setattr(fnx, "_vf2pp_all_isomorphisms_rust", reject_enumeration)
    for name in ("vf2pp_is_isomorphic", "vf2pp_isomorphism", "vf2pp_all_isomorphisms"):
        monkeypatch.setattr(nx, name, reject_enumeration)
    result = getattr(fnx, operation)(fleft, fright, node_label="color")
    if operation == "vf2pp_is_isomorphic":
        assert result is True
    else:
        mapping = next(result) if operation == "vf2pp_all_isomorphisms" else result
        assert mapping == {i: f"node-{i}" for i in left}
        if operation == "vf2pp_all_isomorphisms":
            result.close()


def test_labeled_vf2pp_iterator_resumes_with_independent_results():
    left, right = fnx.complete_graph(4), fnx.complete_graph(4)
    iterator = fnx.vf2pp_all_isomorphisms(left, right, node_label="missing")
    first = next(iterator)
    saved = first.copy()
    second = next(iterator)
    assert first == saved and first is not second
    first.clear()
    remaining = list(iterator)
    assert len(remaining) == 22
    assert all(len(mapping) == 4 for mapping in [second, *remaining])
    expected = nx.vf2pp_all_isomorphisms(nx.complete_graph(4), nx.complete_graph(4), node_label="missing")
    assert _mapping_signatures([saved, second, *remaining]) == _mapping_signatures(expected)


def test_labeled_vf2pp_rejects_constrained_core_before_isolate_permutations():
    left, right = fnx.Graph(), fnx.Graph()
    for graph in (left, right):
        graph.add_nodes_from(range(46))
    left.add_edges_from((40 + i, 40 + (i + 1) % 6) for i in range(6))
    right.add_edges_from([(40, 41), (41, 42), (42, 40), (43, 44), (44, 45), (45, 43)])
    # Equal degree/label histograms, but C6 is not two triangles. Mapping the
    # 40 isolates first would repeat the impossible core search 40! times.
    assert not fnx.vf2pp_is_isomorphic(left, right, node_label="missing")


@pytest.mark.parametrize("class_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
def test_labeled_vf2pp_handles_long_sparse_graph_without_recursion(class_name):
    size = 1200
    left = getattr(fnx, class_name)()
    right = getattr(fnx, class_name)()
    left.add_nodes_from((i, {"color": i}) for i in range(size))
    right.add_nodes_from((f"node-{i}", {"color": i}) for i in range(size))
    left.add_edges_from((i, i + 1) for i in range(size - 1))
    right.add_edges_from((f"node-{i}", f"node-{i + 1}") for i in range(size - 1))
    assert fnx.vf2pp_isomorphism(left, right, node_label="color") == {
        i: f"node-{i}" for i in range(size)
    }


@pytest.mark.parametrize("class_name", ["MultiGraph", "MultiDiGraph"])
def test_labeled_vf2pp_rejects_changed_parallel_multiplicity(class_name):
    # The same complete simple projection and total edge count hide different
    # multiplicities. Unique labels make the only allowed bijection explicit.
    graphs = []
    for counts in ((3, 1, 1), (1, 3, 1)):
        graph = getattr(nx, class_name)()
        graph.add_nodes_from((i, {"color": i}) for i in range(3))
        for (u, v), count in zip(((0, 1), (1, 2), (2, 0)), counts):
            for _ in range(count):
                graph.add_edge(u, v)
        graphs.append(graph)
    assert not nx.vf2pp_is_isomorphic(*graphs, node_label="color")
    fgraphs = [getattr(fnx, class_name)(graph) for graph in graphs]
    assert not fnx.vf2pp_is_isomorphic(*fgraphs, node_label="color")
    assert list(fnx.vf2pp_all_isomorphisms(*fgraphs, node_label="color")) == []


@pytest.mark.parametrize("class_names", [("Graph", "MultiGraph"), ("DiGraph", "MultiDiGraph")])
def test_labeled_vf2pp_accepts_equal_simple_and_multigraphs(class_names):
    graphs = [getattr(nx, name)([(0, 1), (1, 2)]) for name in class_names]
    for graph in graphs:
        nx.set_node_attributes(graph, {i: i for i in graph}, "color")
    expected = list(nx.vf2pp_all_isomorphisms(*graphs, node_label="color"))
    actual = list(fnx.vf2pp_all_isomorphisms(
        *(getattr(fnx, name)(graph) for name, graph in zip(class_names, graphs)),
        node_label="color",
    ))
    assert _mapping_signatures(actual) == _mapping_signatures(expected)


@pytest.mark.parametrize("label", [[], {"unhashable": True}])
def test_labeled_vf2pp_rejects_unhashable_labels(label):
    for module in (nx, fnx):
        left, right = module.path_graph(2), module.path_graph(2)
        left.nodes[0]["color"] = label
        right.nodes[0]["color"] = label
        with pytest.raises(TypeError, match="unhashable"):
            module.vf2pp_is_isomorphic(left, right, node_label="color")


def test_labeled_vf2pp_shared_nonreflexive_label_matches_oracle():
    label = float("nan")
    outcomes = []
    for module in (nx, fnx):
        left, right = module.path_graph(2), module.path_graph(2)
        for graph in (left, right):
            for node in graph:
                graph.nodes[node]["color"] = label
        outcomes.append(_mapping_signatures(module.vf2pp_all_isomorphisms(left, right, node_label="color")))
    assert outcomes[0] == outcomes[1]


@pytest.mark.parametrize("class_name", ["MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize(
    "operation", ["is_isomorphic", "vf2pp_is_isomorphic", "vf2pp_isomorphism", "vf2pp_all_isomorphisms"]
)
def test_unlabeled_multigraph_isomorphism_checks_multiplicities(class_name, operation):
    directed = class_name == "MultiDiGraph"
    base = nx.complete_graph(4, create_using=nx.DiGraph if directed else nx.Graph)
    left, right = getattr(nx, class_name)(), getattr(nx, class_name)()
    for graph in (left, right):
        graph.add_nodes_from(base)
        for u, v in base.edges():
            graph.add_edge(u, v, key="base")
    for u, v in ((0, 1), (2, 3)):
        pairs = ((u, v), (v, u)) if directed else ((u, v),)
        for source, target in pairs:
            for repetition in range(2):
                left.add_edge(source, target, key=("matching", repetition))
    for u, v in ((0, 1), (1, 2), (2, 3), (3, 0)):
        pairs = ((u, v), (v, u)) if directed else ((u, v),)
        for source, target in pairs:
            right.add_edge(source, target, key="cycle")

    # Equal order, size, degrees and complete simple projections hide a
    # triple matching on the left versus doubled cycle edges on the right.
    assert left.number_of_edges() == right.number_of_edges()
    assert sorted(dict(left.degree()).values()) == sorted(dict(right.degree()).values())
    assert set(left.edges()) == set(right.edges())
    expected = getattr(nx, operation)(left, right)
    actual = getattr(fnx, operation)(getattr(fnx, class_name)(left), getattr(fnx, class_name)(right))
    if operation == "vf2pp_all_isomorphisms":
        expected, actual = list(expected), list(actual)
    assert actual == expected
    assert not expected


@pytest.mark.parametrize("class_name", ["MultiGraph", "MultiDiGraph"])
def test_unlabeled_multigraph_isomorphism_preserves_loops_and_ignores_edge_keys(class_name):
    left, right = getattr(nx, class_name)(), getattr(nx, class_name)()
    left.add_nodes_from(range(4))
    renamed = {i: f"node-{3 - i}" for i in left}
    right.add_nodes_from(renamed.values())
    edges = [(0, 0), (0, 0), (0, 1), (0, 1), (1, 2), (2, 2), (2, 3), (2, 3)]
    for i, (u, v) in enumerate(edges):
        left.add_edge(u, v, key=("left", i))
        right.add_edge(renamed[u], renamed[v], key=("right", -i))
    expected = list(nx.vf2pp_all_isomorphisms(left, right))
    assert expected
    fleft, fright = getattr(fnx, class_name)(left), getattr(fnx, class_name)(right)
    assert fnx.is_isomorphic(fleft, fright)
    assert fnx.vf2pp_is_isomorphic(fleft, fright)
    assert fnx.vf2pp_isomorphism(fleft, fright) in expected
    assert _mapping_signatures(fnx.vf2pp_all_isomorphisms(fleft, fright)) == _mapping_signatures(expected)


@pytest.mark.parametrize("class_names", [("Graph", "MultiGraph"), ("DiGraph", "MultiDiGraph")])
@pytest.mark.parametrize("reverse", [False, True])
def test_unlabeled_vf2pp_accepts_equal_simple_and_multigraphs(class_names, reverse):
    if reverse:
        class_names = class_names[::-1]
    left, right = (nx.path_graph(4, create_using=getattr(nx, name)) for name in class_names)
    expected = list(nx.vf2pp_all_isomorphisms(left, right))
    fleft, fright = (getattr(fnx, name)(graph) for name, graph in zip(class_names, (left, right)))
    assert fnx.is_isomorphic(fleft, fright)
    assert fnx.vf2pp_is_isomorphic(fleft, fright)
    assert fnx.vf2pp_isomorphism(fleft, fright) in expected
    assert _mapping_signatures(fnx.vf2pp_all_isomorphisms(fleft, fright)) == _mapping_signatures(expected)


@pytest.mark.parametrize("class_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("explicit_none", [False, True])
def test_vf2pp_none_attribute_key_is_a_real_label(class_name, explicit_none):
    left, right = getattr(nx, class_name)(), getattr(nx, class_name)()
    for graph in (left, right):
        graph.add_nodes_from([0, 1])
        graph.nodes[0][None] = "red"
    left.nodes[1][None] = "blue"
    right.nodes[1][None] = "red"
    fleft, fright = getattr(fnx, class_name)(left), getattr(fnx, class_name)(right)
    kwargs = {"node_label": None} if explicit_none else {}
    assert fnx.vf2pp_is_isomorphic(fleft, fright, **kwargs) == nx.vf2pp_is_isomorphic(left, right, **kwargs)
    assert fnx.vf2pp_isomorphism(fleft, fright, **kwargs) == nx.vf2pp_isomorphism(left, right, **kwargs)
    assert list(fnx.vf2pp_all_isomorphisms(fleft, fright, **kwargs)) == list(
        nx.vf2pp_all_isomorphisms(left, right, **kwargs)
    ) == []


@pytest.mark.parametrize("class_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("node_label", [None, "color"])
@pytest.mark.parametrize("operation", ["vf2pp_is_isomorphic", "vf2pp_isomorphism", "vf2pp_all_isomorphisms"])
def test_vf2pp_unhashable_default_label_matches_oracle(class_name, node_label, operation):
    for module in (nx, fnx):
        left, right = getattr(module, class_name)([(0, 1), (1, 2)]), getattr(module, class_name)([(0, 1), (1, 2)])
        with pytest.raises(TypeError, match="unhashable type: 'list'"):
            result = getattr(module, operation)(left, right, node_label=node_label, default_label=[])
            if operation == "vf2pp_all_isomorphisms":
                list(result)


@pytest.mark.parametrize("class_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("node_label", [None, "color"])
def test_vf2pp_unhashable_default_is_unused_when_labels_exist(class_name, node_label):
    left = nx.path_graph(3, create_using=getattr(nx, class_name))
    right = left.copy()
    for graph in (left, right):
        for node in graph:
            graph.nodes[node][node_label] = node
    expected = list(nx.vf2pp_all_isomorphisms(left, right, node_label=node_label, default_label=[]))
    assert expected
    fleft, fright = getattr(fnx, class_name)(left), getattr(fnx, class_name)(right)
    assert fnx.vf2pp_is_isomorphic(fleft, fright, node_label=node_label, default_label=[])
    assert fnx.vf2pp_isomorphism(fleft, fright, node_label=node_label, default_label=[]) in expected
    assert _mapping_signatures(fnx.vf2pp_all_isomorphisms(
        fleft, fright, node_label=node_label, default_label=[]
    )) == _mapping_signatures(expected)


@pytest.mark.parametrize("class_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("node_label", [None, "color"])
@pytest.mark.parametrize("case", ["empty", "order", "degree"])
def test_vf2pp_shape_checks_precede_unhashable_defaults(class_name, node_label, case):
    if case == "empty":
        left, right = nx.Graph(), nx.Graph()
    elif case == "order":
        left, right = nx.path_graph(3), nx.path_graph(4)
    else:
        left, right = nx.path_graph(4), nx.star_graph(3)
    left, right = getattr(nx, class_name)(left), getattr(nx, class_name)(right)
    fleft, fright = getattr(fnx, class_name)(left), getattr(fnx, class_name)(right)
    kwargs = {"node_label": node_label, "default_label": []}
    assert fnx.vf2pp_is_isomorphic(fleft, fright, **kwargs) == nx.vf2pp_is_isomorphic(left, right, **kwargs) is False
    assert fnx.vf2pp_isomorphism(fleft, fright, **kwargs) == nx.vf2pp_isomorphism(left, right, **kwargs) is None
    assert list(fnx.vf2pp_all_isomorphisms(fleft, fright, **kwargs)) == list(
        nx.vf2pp_all_isomorphisms(left, right, **kwargs)
    ) == []


@pytest.mark.parametrize("class_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
def test_is_isomorphic_ignores_implicit_labels_and_short_circuits_callbacks(monkeypatch, class_name):
    left = nx.complete_graph(12, create_using=getattr(nx, class_name))
    right = left.copy()
    for node in left:
        left.nodes[node][None] = []
        right.nodes[node][None] = {"different": True}
        left.nodes[node]["color"] = node
        right.nodes[node]["color"] = 11 - node
    fleft, fright = getattr(fnx, class_name)(left), getattr(fnx, class_name)(right)
    assert fnx.is_isomorphic(fleft, fright) == nx.is_isomorphic(left, right) is True

    def reject_enumeration(*args, **kwargs):
        raise AssertionError("callback search enumerated structural automorphisms")

    monkeypatch.setattr(fnx, "_vf2pp_all_isomorphisms_rust", reject_enumeration)
    calls = 0

    def node_match(a, b):
        nonlocal calls
        calls += 1
        assert calls <= 12 * 12, "node labels were checked only after constructing full bijections"
        return a["color"] == b["color"]

    assert fnx.is_isomorphic(fleft, fright, node_match=node_match)
    assert 12 <= calls <= 12 * 12


@pytest.mark.parametrize("class_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
def test_is_isomorphic_edge_callbacks_prune_before_full_bijections(monkeypatch, class_name):
    left = nx.complete_graph(12, create_using=getattr(nx, class_name))
    right = getattr(nx, class_name)()
    right.add_nodes_from(left)
    for u, v in left.edges():
        color = (u, v)
        if left.is_multigraph():
            left[u][v][0]["color"] = color
        else:
            left[u][v]["color"] = color
        right.add_edge(11 - u, 11 - v, color=color)

    def same_colors(a, b):
        if left.is_multigraph():
            return sorted(data["color"] for data in a.values()) == sorted(
                data["color"] for data in b.values()
            )
        return a["color"] == b["color"]

    assert nx.is_isomorphic(left, right, edge_match=same_colors)
    fleft, fright = getattr(fnx, class_name)(left), getattr(fnx, class_name)(right)

    def reject_enumeration(*args, **kwargs):
        raise AssertionError("edge callback search enumerated structural automorphisms")

    monkeypatch.setattr(fnx, "_vf2pp_all_isomorphisms_rust", reject_enumeration)
    calls = 0

    def edge_match(a, b):
        nonlocal calls
        calls += 1
        assert calls <= 12 ** 3, "edge attributes were checked only after constructing full bijections"
        return same_colors(a, b)

    assert fnx.is_isomorphic(fleft, fright, edge_match=edge_match)
    assert 0 < calls <= 12 ** 3


@pytest.mark.parametrize("class_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
def test_is_isomorphic_empty_graphs_do_not_invoke_callbacks(class_name):
    def reject_callback(*args):
        raise AssertionError("empty bijections have no node or edge attributes to compare")

    for module in (nx, fnx):
        left, right = getattr(module, class_name)(), getattr(module, class_name)()
        assert module.is_isomorphic(left, right, node_match=reject_callback, edge_match=reject_callback)
        assert not module.vf2pp_is_isomorphic(left, right)
        assert module.vf2pp_isomorphism(left, right) is None
        assert list(module.vf2pp_all_isomorphisms(left, right)) == []


def test_vf2pp_isomorphism_directed_matches_networkx():
    g1 = fnx.DiGraph([(0, 1), (1, 2)])
    g2 = fnx.DiGraph([("a", "b"), ("b", "c")])

    assert fnx.vf2pp_isomorphism(g1, g2) == nx.vf2pp_isomorphism(_to_nx(g1), _to_nx(g2))


def _mapping_signatures(mappings):
    return {_mapping_signature(mapping) for mapping in mappings}


@pytest.mark.parametrize(
    ("fnx_matcher", "nx_matcher", "left", "right"),
    [
        (
            fnx.GraphMatcher,
            nx.algorithms.isomorphism.GraphMatcher,
            fnx.path_graph(3),
            fnx.relabel_nodes(fnx.path_graph(3), {0: "a", 1: "b", 2: "c"}),
        ),
        (
            fnx.DiGraphMatcher,
            nx.algorithms.isomorphism.DiGraphMatcher,
            fnx.DiGraph([(0, 1), (1, 2)]),
            fnx.DiGraph([("a", "b"), ("b", "c")]),
        ),
        (
            fnx.MultiGraphMatcher,
            nx.algorithms.isomorphism.MultiGraphMatcher,
            fnx.MultiGraph([(0, 1), (0, 1), (1, 2)]),
            fnx.MultiGraph([("a", "b"), ("a", "b"), ("b", "c")]),
        ),
        (
            fnx.MultiDiGraphMatcher,
            nx.algorithms.isomorphism.MultiDiGraphMatcher,
            fnx.MultiDiGraph([(0, 1), (0, 1), (1, 2)]),
            fnx.MultiDiGraph([("a", "b"), ("a", "b"), ("b", "c")]),
        ),
    ],
)
def test_vf2_matcher_wrappers_match_networkx(fnx_matcher, nx_matcher, left, right):
    matcher = fnx_matcher(left, right)
    expected = nx_matcher(_to_nx(left), _to_nx(right))

    assert matcher.is_isomorphic() == expected.is_isomorphic()
    assert _mapping_signatures(matcher.isomorphisms_iter()) == _mapping_signatures(
        expected.isomorphisms_iter()
    )
    assert _mapping_signatures(fnx_matcher(left, right).match()) == _mapping_signatures(
        nx_matcher(_to_nx(left), _to_nx(right)).match()
    )

    matcher.initialize()
    expected.initialize()
    actual_pair = next(matcher.candidate_pairs_iter())
    expected_pair = next(expected.candidate_pairs_iter())
    assert actual_pair == expected_pair
    assert matcher.semantic_feasibility(*actual_pair) == expected.semantic_feasibility(
        *expected_pair
    )
    assert matcher.syntactic_feasibility(*actual_pair) == expected.syntactic_feasibility(
        *expected_pair
    )


def test_vf2_graph_matcher_callbacks_and_subgraph_api_match_networkx():
    left = fnx.Graph()
    left.add_node(0, color="red")
    left.add_node(1, color="blue")
    left.add_node(2, color="red")
    left.add_node(3, color="blue")
    left.add_edge(0, 1, weight=2)
    left.add_edge(1, 2, weight=3)
    left.add_edge(2, 3, weight=2)

    right = fnx.Graph()
    right.add_node("a", color="red")
    right.add_node("b", color="blue")
    right.add_node("c", color="red")
    right.add_edge("a", "b", weight=2)
    right.add_edge("b", "c", weight=3)

    def node_match(left_attrs, right_attrs):
        return left_attrs == right_attrs

    def edge_match(left_attrs, right_attrs):
        return left_attrs == right_attrs

    matcher = fnx.GraphMatcher(
        left,
        right,
        node_match=node_match,
        edge_match=edge_match,
    )
    expected = nx.algorithms.isomorphism.GraphMatcher(
        _to_nx(left),
        _to_nx(right),
        node_match=node_match,
        edge_match=edge_match,
    )

    assert matcher.subgraph_is_isomorphic() == expected.subgraph_is_isomorphic()
    assert matcher.subgraph_is_monomorphic() == expected.subgraph_is_monomorphic()
    assert _mapping_signatures(matcher.subgraph_isomorphisms_iter()) == _mapping_signatures(
        expected.subgraph_isomorphisms_iter()
    )
    assert _mapping_signatures(matcher.subgraph_monomorphisms_iter()) == _mapping_signatures(
        expected.subgraph_monomorphisms_iter()
    )


def test_graph_edit_distance_matches_networkx_on_small_graphs():
    g1 = fnx.path_graph(3)
    g2 = fnx.path_graph(4)

    assert fnx.graph_edit_distance(g1, g2) == nx.graph_edit_distance(
        _to_nx(g1),
        _to_nx(g2),
    )


def test_graph_edit_distance_uses_native_common_case(monkeypatch):
    g1 = fnx.path_graph(3)
    g2 = fnx.path_graph(4)
    called = {"rust": False}

    def fake_rust(left, right, upper_bound=None):
        called["rust"] = True
        assert left is g1
        assert right is g2
        assert upper_bound is None
        return ([{0: 0, 1: 1, 2: 2}], 2.0)

    def fail_networkx(*args, **kwargs):
        raise AssertionError("unexpected NetworkX fallback")

    monkeypatch.setattr(fnx, "_graph_edit_distance_common_rust", fake_rust)
    monkeypatch.setattr(nx, "graph_edit_distance", fail_networkx)

    assert fnx.graph_edit_distance(g1, g2) == 2.0
    assert called["rust"] is True


def test_edit_path_helpers_use_native_common_case(monkeypatch):
    g1 = fnx.path_graph(3)
    g2 = fnx.path_graph(4)
    called = {"rust": 0}

    def fake_rust(left, right, upper_bound=None):
        called["rust"] += 1
        return ([{0: 0, 1: 1, 2: 2}, {2: 0, 1: 1, 0: 2}], 2.0)

    def fail_networkx(*args, **kwargs):
        raise AssertionError("unexpected NetworkX fallback")

    monkeypatch.setattr(fnx, "_graph_edit_distance_common_rust", fake_rust)
    monkeypatch.setattr(nx, "optimal_edit_paths", fail_networkx)
    monkeypatch.setattr(nx, "optimize_edit_paths", fail_networkx)
    monkeypatch.setattr(nx, "optimize_graph_edit_distance", fail_networkx)

    optimal_paths, cost = fnx.optimal_edit_paths(g1, g2)
    assert cost == 2.0
    assert optimal_paths[0][0] == [(0, 0), (1, 1), (2, 2), (None, 3)]
    assert list(fnx.optimize_graph_edit_distance(g1, g2)) == [2.0]
    assert list(fnx.optimize_edit_paths(g1, g2, strictly_decreasing=False)) == [
        (
            [(0, 0), (1, 1), (2, 2), (None, 3)],
            [((0, 1), (0, 1)), ((1, 2), (1, 2)), (None, (2, 3))],
            2.0,
        ),
        (
            [(2, 0), (1, 1), (0, 2), (None, 3)],
            [((0, 1), (2, 1)), ((1, 2), (1, 0)), (None, (2, 3))],
            2.0,
        ),
    ]
    assert called["rust"] == 3


def test_edit_optimizers_route_through_local_wrappers(monkeypatch):
    g1 = fnx.path_graph(2)
    g2 = fnx.path_graph(3)

    def fail_networkx(*args, **kwargs):
        raise AssertionError("optimizer NetworkX fallback should not be used")

    monkeypatch.setattr(nx, "optimize_edit_paths", fail_networkx)
    monkeypatch.setattr(nx, "optimize_graph_edit_distance", fail_networkx)
    monkeypatch.setattr(
        fnx,
        "optimal_edit_paths",
        lambda *args, **kwargs: (
            [
                (
                    [(0, 0), (1, 1), (None, 2)],
                    [((0, 1), (0, 1)), (None, (1, 2))],
                )
            ],
            2.0,
        ),
    )
    monkeypatch.setattr(fnx, "graph_edit_distance", lambda *args, **kwargs: 2.0)

    assert list(fnx.optimize_graph_edit_distance(g1, g2)) == [2.0]
    assert list(fnx.optimize_edit_paths(g1, g2)) == [
        (
            [(0, 0), (1, 1), (None, 2)],
            [((0, 1), (0, 1)), (None, (1, 2))],
            2.0,
        )
    ]


def test_graph_edit_distance_with_callbacks_uses_local_optimal_paths(monkeypatch):
    g1 = fnx.Graph()
    g1.add_node(1, color="red")
    g2 = fnx.Graph()
    g2.add_node(2, color="blue")

    def fail_rust(*args, **kwargs):
        raise AssertionError("native common-case path should not be used")

    def fail_networkx(*args, **kwargs):
        raise AssertionError("NetworkX edit-distance fallback should not be used")

    monkeypatch.setattr(fnx, "_graph_edit_distance_common_rust", fail_rust)
    monkeypatch.setattr(nx, "graph_edit_distance", fail_networkx)
    monkeypatch.setattr(nx, "optimal_edit_paths", fail_networkx)

    assert (
        fnx.graph_edit_distance(
            g1,
            g2,
            node_match=lambda left, right: left == right,
        )
        == 1.0
    )


def test_optimal_edit_paths_with_callbacks_matches_networkx_without_fallback(monkeypatch):
    g1 = fnx.Graph()
    g1.add_node(1, color="red")
    g2 = fnx.Graph()
    g2.add_node(2, color="blue")
    node_match = lambda left, right: left == right

    expected_paths, expected_cost = nx.optimal_edit_paths(
        _to_nx(g1),
        _to_nx(g2),
        node_match=node_match,
    )

    def fail_networkx(*args, **kwargs):
        raise AssertionError("NetworkX optimal_edit_paths fallback should not be used")

    monkeypatch.setattr(nx, "optimal_edit_paths", fail_networkx)
    paths, cost = fnx.optimal_edit_paths(g1, g2, node_match=node_match)

    assert cost == expected_cost
    assert paths == expected_paths


def test_optimal_edit_paths_callback_costs_match_networkx_without_fallback(monkeypatch):
    g1 = fnx.Graph()
    g1.add_node("a", size=1)
    g1.add_node("b", size=3)
    g1.add_edge("a", "b", weight=4)

    g2 = fnx.Graph()
    g2.add_node("x", size=2)
    g2.add_node("y", size=5)
    g2.add_edge("x", "y", weight=7)

    kwargs = {
        "node_subst_cost": lambda left, right: abs(left.get("size", 0) - right.get("size", 0)),
        "node_del_cost": lambda attrs: attrs.get("size", 1),
        "node_ins_cost": lambda attrs: attrs.get("size", 1),
        "edge_subst_cost": lambda left, right: abs(left.get("weight", 0) - right.get("weight", 0)),
        "edge_del_cost": lambda attrs: attrs.get("weight", 1),
        "edge_ins_cost": lambda attrs: attrs.get("weight", 1),
    }
    expected_paths, expected_cost = nx.optimal_edit_paths(_to_nx(g1), _to_nx(g2), **kwargs)

    monkeypatch.setattr(
        fnx,
        "_graph_edit_distance_common_rust",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("native common-case path should not be used with callbacks")
        ),
    )
    _block_networkx_graph_edit(monkeypatch)

    paths, cost = fnx.optimal_edit_paths(g1, g2, **kwargs)

    assert cost == expected_cost
    assert [edge_path for _, edge_path in paths] == [
        edge_path for _, edge_path in expected_paths
    ]
    assert fnx.graph_edit_distance(g1, g2, **kwargs) == expected_cost
    assert list(fnx.optimize_graph_edit_distance(g1, g2, **kwargs)) == [expected_cost]
    assert [item[2] for item in fnx.optimize_edit_paths(g1, g2, **kwargs)] == [
        expected_cost
    ]


def test_directed_graph_edit_respects_edge_direction_without_fallback(monkeypatch):
    g1 = fnx.DiGraph()
    g1.add_node("a", color="red")
    g1.add_node("b", color="blue")
    g1.add_edge("a", "b")

    g2 = fnx.DiGraph()
    g2.add_node("x", color="red")
    g2.add_node("y", color="blue")
    g2.add_edge("y", "x")

    kwargs = {
        "node_subst_cost": lambda left, right: 0
        if left.get("color") == right.get("color")
        else 10,
    }
    expected_paths, expected_cost = nx.optimal_edit_paths(_to_nx(g1), _to_nx(g2), **kwargs)

    monkeypatch.setattr(
        fnx,
        "_graph_edit_distance_common_rust",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("native common-case path should not be used with callbacks")
        ),
    )
    _block_networkx_graph_edit(monkeypatch)

    paths, cost = fnx.optimal_edit_paths(g1, g2, **kwargs)

    assert cost == expected_cost
    assert cost == pytest.approx(2.0)
    assert {tuple(edge_path) for _, edge_path in paths} == {
        tuple(edge_path) for _, edge_path in expected_paths
    }
    assert fnx.graph_edit_distance(g1, g2, **kwargs) == expected_cost


def test_directed_graph_edit_edge_match_without_fallback(monkeypatch):
    g1 = fnx.DiGraph()
    g1.add_node("a", color="red")
    g1.add_node("b", color="blue")
    g1.add_edge("a", "b", kind="uses")

    g2 = fnx.DiGraph()
    g2.add_node("x", color="red")
    g2.add_node("y", color="blue")
    g2.add_edge("x", "y", kind="blocks")

    kwargs = {
        "node_match": lambda left, right: left == right,
        "edge_match": lambda left, right: left == right,
    }
    expected_paths, expected_cost = nx.optimal_edit_paths(_to_nx(g1), _to_nx(g2), **kwargs)

    monkeypatch.setattr(
        fnx,
        "_graph_edit_distance_common_rust",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("native common-case path should not be used with callbacks")
        ),
    )
    _block_networkx_graph_edit(monkeypatch)

    paths, cost = fnx.optimal_edit_paths(g1, g2, **kwargs)

    assert cost == expected_cost
    assert cost == pytest.approx(1.0)
    assert [edge_path for _, edge_path in paths] == [
        edge_path for _, edge_path in expected_paths
    ]
    assert fnx.graph_edit_distance(g1, g2, **kwargs) == expected_cost


def test_graph_edit_self_loop_costs_match_networkx_without_fallback(monkeypatch):
    g1 = fnx.Graph()
    g1.add_node("a", color="red")
    g1.add_edge("a", "a", weight=3)

    g2 = fnx.Graph()
    g2.add_node("x", color="red")

    kwargs = {
        "node_match": lambda left, right: left == right,
        "edge_del_cost": lambda attrs: attrs.get("weight", 1),
    }
    expected_paths, expected_cost = nx.optimal_edit_paths(_to_nx(g1), _to_nx(g2), **kwargs)

    monkeypatch.setattr(
        fnx,
        "_graph_edit_distance_common_rust",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("native common-case path should not be used with callbacks")
        ),
    )
    _block_networkx_graph_edit(monkeypatch)

    paths, cost = fnx.optimal_edit_paths(g1, g2, **kwargs)

    assert cost == expected_cost
    assert cost == pytest.approx(3.0)
    assert paths == expected_paths
    assert fnx.graph_edit_distance(g1, g2, **kwargs) == expected_cost


def test_graph_edit_weighted_edge_costs_match_networkx_without_fallback(monkeypatch):
    g1 = fnx.DiGraph()
    g1.add_node("a", color="red")
    g1.add_node("b", color="blue")
    g1.add_edge("a", "b", weight=2)

    g2 = fnx.DiGraph()
    g2.add_node("x", color="red")
    g2.add_node("y", color="blue")
    g2.add_edge("y", "x", weight=5)

    kwargs = {
        "node_subst_cost": lambda left, right: 0
        if left.get("color") == right.get("color")
        else 10,
        "edge_del_cost": lambda attrs: attrs.get("weight", 1),
        "edge_ins_cost": lambda attrs: attrs.get("weight", 1),
    }
    expected_paths, expected_cost = nx.optimal_edit_paths(_to_nx(g1), _to_nx(g2), **kwargs)

    monkeypatch.setattr(
        fnx,
        "_graph_edit_distance_common_rust",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("native common-case path should not be used with callbacks")
        ),
    )
    _block_networkx_graph_edit(monkeypatch)

    paths, cost = fnx.optimal_edit_paths(g1, g2, **kwargs)

    assert cost == expected_cost
    assert cost == pytest.approx(7.0)
    assert {tuple(edge_path) for _, edge_path in paths} == {
        tuple(edge_path) for _, edge_path in expected_paths
    }
    assert fnx.graph_edit_distance(g1, g2, **kwargs) == expected_cost


def test_graph_edit_upper_bound_matches_networkx_without_fallback(monkeypatch):
    g1 = fnx.Graph()
    g1.add_node(1, color="red")
    g2 = fnx.Graph()
    g2.add_node(2, color="blue")
    kwargs = {
        "node_match": lambda left, right: left == right,
        "upper_bound": 0,
    }
    expected_paths, expected_cost = nx.optimal_edit_paths(_to_nx(g1), _to_nx(g2), **kwargs)

    _block_networkx_graph_edit(monkeypatch)

    assert fnx.optimal_edit_paths(g1, g2, **kwargs) == (expected_paths, expected_cost)
    assert fnx.graph_edit_distance(g1, g2, **kwargs) == expected_cost
    assert list(fnx.optimize_graph_edit_distance(g1, g2, **kwargs)) == []
    assert list(fnx.optimize_edit_paths(g1, g2, **kwargs)) == []


def test_graph_edit_directed_mismatch_and_unsupported_modes_do_not_fallback(monkeypatch):
    _block_networkx_graph_edit(monkeypatch)

    with pytest.raises(fnx.NetworkXError):
        fnx.graph_edit_distance(fnx.Graph(), fnx.DiGraph())

    multigraph = fnx.MultiGraph()
    multigraph.add_edge(1, 2)
    with pytest.raises(fnx.NetworkXNotImplemented):
        fnx.optimal_edit_paths(multigraph, fnx.Graph())

    with pytest.raises(fnx.NetworkXNotImplemented):
        list(fnx.optimize_edit_paths(fnx.path_graph(2), fnx.path_graph(2), timeout=1))

    with pytest.raises(fnx.NetworkXNotImplemented):
        fnx.graph_edit_distance(fnx.path_graph(2), fnx.path_graph(2), timeout=1)


def test_graph_edit_distance_roots_matches_networkx_without_fallback(monkeypatch):
    expected_cost = nx.graph_edit_distance(nx.path_graph(3), nx.path_graph(3), roots=(1, 0))
    expected_paths = list(nx.optimize_edit_paths(nx.path_graph(3), nx.path_graph(3), roots=(1, 0)))

    _block_networkx_graph_edit(monkeypatch)

    assert fnx.graph_edit_distance(fnx.path_graph(3), fnx.path_graph(3), roots=(1, 0)) == expected_cost
    assert list(fnx.optimize_edit_paths(fnx.path_graph(3), fnx.path_graph(3), roots=(1, 0))) == expected_paths


@pytest.mark.parametrize("roots", [("x", "x"), (), (0,)])
def test_graph_edit_distance_roots_error_contract_matches_networkx_without_fallback(
    monkeypatch, roots
):
    try:
        nx.graph_edit_distance(nx.path_graph(3), nx.path_graph(3), roots=roots)
    except Exception as exc:
        expected = exc
    else:
        raise AssertionError("expected NetworkX graph_edit_distance to fail for invalid roots")

    _block_networkx_graph_edit(monkeypatch)

    fnx_exc_type = getattr(fnx, type(expected).__name__, BuiltinValueError)
    with pytest.raises(fnx_exc_type, match=re.escape(str(expected))):
        fnx.graph_edit_distance(fnx.path_graph(3), fnx.path_graph(3), roots=roots)

    with pytest.raises(fnx_exc_type, match=re.escape(str(expected))):
        list(fnx.optimize_edit_paths(fnx.path_graph(3), fnx.path_graph(3), roots=roots))


def test_mixed_directedness_raises_before_the_degree_precheck():
    # nro4w.7: networkx's test_is_isomorphic. The degree-histogram pre-reject
    # answered False for P4 vs its directed copy before the type check ran.
    G = fnx.path_graph(4)
    with pytest.raises(fnx.NetworkXError, match="Graphs G1 and G2 are not of the same type."):
        fnx.is_isomorphic(G.to_directed(), G)
    with pytest.raises(nx.NetworkXError, match="Graphs G1 and G2 are not of the same type."):
        nx.is_isomorphic(nx.path_graph(4).to_directed(), nx.path_graph(4))


def test_multigraph_edge_match_receives_keydicts_like_networkx():
    # nro4w.7: networkx hands edge_match the two keydicts of each mapped node
    # pair; categorical_multiedge_match reads them. fnx paired datadicts and
    # the helper crashed on a bare attribute value.
    edge_match = nx.algorithms.isomorphism.categorical_multiedge_match("c", 0)
    edges = [(0, 1, {"c": 1}), (0, 1, {"c": 2}), (1, 2, {"c": 1})]
    other = [(5, 4, {"c": 2}), (5, 4, {"c": 1}), (4, 3, {"c": 1})]
    for cls_name in ("MultiGraph", "MultiDiGraph"):
        expected = nx.is_isomorphic(
            getattr(nx, cls_name)(edges), getattr(nx, cls_name)(other), edge_match=edge_match
        )
        actual = fnx.is_isomorphic(
            getattr(fnx, cls_name)(edges), getattr(fnx, cls_name)(other), edge_match=edge_match
        )
        assert actual == expected


def _isomorphic_outcome(module, c1, c2, n, e1, e2, edge_match):
    a = getattr(module, c1)()
    a.add_nodes_from(range(n))
    a.add_edges_from(e1)
    b = getattr(module, c2)()
    b.add_nodes_from(range(n))
    b.add_edges_from(e2)
    try:
        if edge_match is None:
            return module.is_isomorphic(a, b)
        return module.is_isomorphic(a, b, edge_match=edge_match)
    except Exception as exc:  # the error contract is part of the parity
        return type(exc).__name__, str(exc)


@pytest.mark.parametrize("seed", range(4))
def test_random_class_pairs_match_networkx(seed):
    """Every class pairing, with and without edge_match, parallel edges and
    self-loops included. Before nro4w.7 about a quarter of these differed:
    mixed multigraph / simple pairs, multiplicity mismatches, and mixed
    directedness hidden behind the degree pre-reject."""
    iso = nx.algorithms.isomorphism
    classes = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]
    rng = random.Random(seed)
    for _ in range(150):
        n = rng.randint(1, 5)
        e1 = [(rng.randrange(n), rng.randrange(n), {"c": rng.randint(0, 1)})
              for _ in range(rng.randint(0, 6))]
        perm = list(range(n))
        rng.shuffle(perm)
        if rng.random() < 0.7:
            e2 = [(perm[u], perm[v], dict(d)) for u, v, d in e1]
        else:
            e2 = [(rng.randrange(n), rng.randrange(n), {"c": rng.randint(0, 1)})
                  for _ in range(len(e1))]
        c1 = rng.choice(classes)
        c2 = c1 if rng.random() < 0.6 else rng.choice(classes)
        multi = c1.startswith("Multi") and c2.startswith("Multi")
        simple = not c1.startswith("Multi") and not c2.startswith("Multi")
        edge_match = rng.choice(
            [None, lambda a, b: True]
            + ([iso.categorical_multiedge_match("c", 0)] if multi else [])
            + ([iso.categorical_edge_match("c", 0)] if simple else [])
        )
        expected = _isomorphic_outcome(nx, c1, c2, n, e1, e2, edge_match)
        actual = _isomorphic_outcome(fnx, c1, c2, n, e1, e2, edge_match)
        assert actual == expected, (c1, c2, edge_match is not None, e1, e2)
