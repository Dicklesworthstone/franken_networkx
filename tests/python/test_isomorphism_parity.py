import networkx as nx
import pytest
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


def test_vf2pp_all_isomorphisms_uses_rust_without_labels(monkeypatch):
    g1 = fnx.path_graph(3)
    g2 = fnx.relabel_nodes(g1, {0: "a", 1: "b", 2: "c"})
    called = {"rust": False}

    def fake_rust(left, right):
        called["rust"] = True
        assert left is g1
        assert right is g2
        return [{0: "a", 1: "b", 2: "c"}]

    def fail_networkx(*args, **kwargs):
        raise AssertionError("unexpected NetworkX fallback")

    monkeypatch.setattr(fnx, "_vf2pp_all_isomorphisms_rust", fake_rust)
    monkeypatch.setattr(nx, "vf2pp_all_isomorphisms", fail_networkx)

    assert list(fnx.vf2pp_all_isomorphisms(g1, g2)) == [{0: "a", 1: "b", 2: "c"}]
    assert called["rust"] is True


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


def test_vf2pp_isomorphism_directed_matches_networkx():
    g1 = fnx.DiGraph([(0, 1), (1, 2)])
    g2 = fnx.DiGraph([("a", "b"), ("b", "c")])

    assert fnx.vf2pp_isomorphism(g1, g2) == nx.vf2pp_isomorphism(_to_nx(g1), _to_nx(g2))


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
