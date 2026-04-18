import networkx as nx

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


def test_graph_edit_distance_with_callbacks_delegates_to_networkx(monkeypatch):
    g1 = fnx.Graph()
    g1.add_node(1, color="red")
    g2 = fnx.Graph()
    g2.add_node(2, color="blue")
    called = {"networkx": False}

    def fail_rust(*args, **kwargs):
        raise AssertionError("native common-case path should not be used")

    real_graph_edit_distance = nx.graph_edit_distance

    def wrapped_networkx(*args, **kwargs):
        called["networkx"] = True
        return real_graph_edit_distance(*args, **kwargs)

    monkeypatch.setattr(fnx, "_graph_edit_distance_common_rust", fail_rust)
    monkeypatch.setattr(nx, "graph_edit_distance", wrapped_networkx)

    assert (
        fnx.graph_edit_distance(
            g1,
            g2,
            node_match=lambda left, right: left == right,
        )
        == 1.0
    )
    assert called["networkx"] is True
