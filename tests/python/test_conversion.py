"""Tests for conversion utilities: relabel_nodes, convert_node_labels_to_integers,
to/from_dict_of_dicts, to/from_dict_of_lists, to/from_edgelist,
to/from_numpy_array, to/from_scipy_sparse_array, to/from_pandas_edgelist."""

import copy
import importlib
import importlib.util
import inspect
import json
import sys
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path

import networkx as nx
import pytest

import franken_networkx as fnx


@lru_cache(maxsize=1)
def _legacy_networkx():
    module_name = "franken_networkx_legacy_networkx_convert_surface"
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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def triangle():
    G = fnx.Graph()
    G.add_edge("a", "b", weight=1.0)
    G.add_edge("b", "c", weight=2.0)
    G.add_edge("a", "c", weight=3.0)
    return G


@pytest.fixture
def small_digraph():
    D = fnx.DiGraph()
    D.add_edge(0, 1)
    D.add_edge(1, 2)
    D.add_edge(0, 2)
    return D


def _normalize_mapping(value):
    if isinstance(value, Mapping):
        return tuple(sorted((repr(key), _normalize_mapping(item)) for key, item in value.items()))
    return repr(value)


def _canonical_edge_nodes(graph, u, v):
    if graph.is_directed():
        return repr(u), repr(v)
    return tuple(sorted((repr(u), repr(v))))


def _graph_signature(graph):
    graph_attrs = tuple(sorted((repr(key), _normalize_mapping(value)) for key, value in graph.graph.items()))
    nodes = sorted(
        (repr(node), tuple(sorted((repr(key), _normalize_mapping(value)) for key, value in dict(attrs).items())))
        for node, attrs in graph.nodes(data=True)
    )
    if graph.is_multigraph():
        edges = sorted(
            (
                *_canonical_edge_nodes(graph, u, v),
                repr(key),
                tuple(sorted((repr(attr), _normalize_mapping(value)) for attr, value in dict(data).items())),
            )
            for u, v, key, data in graph.edges(keys=True, data=True)
        )
    else:
        edges = sorted(
            (
                *_canonical_edge_nodes(graph, u, v),
                tuple(sorted((repr(attr), _normalize_mapping(value)) for attr, value in dict(data).items())),
            )
            for u, v, data in graph.edges(data=True)
        )
    return graph_attrs, nodes, edges


def _label_graph_pair(fnx_cls, nx_cls):
    graph = fnx_cls()
    expected = nx_cls()
    graph.graph["name"] = "labels"
    expected.graph["name"] = "labels"
    for node, color in [("b", "blue"), ("a", "red"), ("c", "green")]:
        graph.add_node(node, color=color)
        expected.add_node(node, color=color)
    if graph.is_multigraph():
        graph.add_edge("b", "a", key=7, weight=2)
        graph.add_edge("a", "c", key=3, weight=4)
        expected.add_edge("b", "a", key=7, weight=2)
        expected.add_edge("a", "c", key=3, weight=4)
    else:
        graph.add_edge("b", "a", weight=2)
        graph.add_edge("a", "c", weight=4)
        expected.add_edge("b", "a", weight=2)
        expected.add_edge("a", "c", weight=4)
    return graph, expected


def _block_networkx_conversion(monkeypatch, *names):
    def fail_networkx(*args, **kwargs):
        raise AssertionError("NetworkX conversion fallback should not be used")

    for name in names:
        monkeypatch.setattr(nx, name, fail_networkx)


# ---------------------------------------------------------------------------
# relabel_nodes
# ---------------------------------------------------------------------------


class TestRelabelNodes:
    def test_dict_mapping(self, triangle):
        mapping = {"a": 0, "b": 1, "c": 2}
        H = fnx.relabel_nodes(triangle, mapping)
        assert H.number_of_nodes() == 3
        assert H.has_edge(0, 1)
        assert H.has_edge(1, 2)
        assert H.has_edge(0, 2)

    def test_callable_mapping(self, triangle):
        H = fnx.relabel_nodes(triangle, str.upper)
        assert H.has_node("A")
        assert H.has_node("B")
        assert H.has_node("C")
        assert H.has_edge("A", "B")

    def test_copy_true(self, triangle):
        H = fnx.relabel_nodes(triangle, {"a": "x"}, copy=True)
        assert H.has_node("x")
        assert triangle.has_node("a")  # original unchanged

    def test_copy_false(self):
        G = fnx.Graph()
        G.add_edge(0, 1)
        fnx.relabel_nodes(G, {0: 10, 1: 11}, copy=False)
        assert G.has_node(10)
        assert G.has_node(11)
        assert not G.has_node(0)

    def test_partial_mapping(self):
        G = fnx.Graph()
        G.add_edge(0, 1)
        G.add_edge(1, 2)
        H = fnx.relabel_nodes(G, {0: 10})
        assert H.has_node(10)
        assert H.has_node(1)
        assert H.has_node(2)

    def test_copy_true_plain_graph_empty_attrs_order_matches_networkx(self, monkeypatch):
        graph = fnx.Graph()
        expected = nx.Graph()
        graph.graph["name"] = "empty-attr-relabel"
        expected.graph["name"] = "empty-attr-relabel"
        graph.add_nodes_from(range(30))
        expected.add_nodes_from(range(30))
        edges = [((i * 37 + 11) % i, i) for i in range(1, 30)]
        edges.extend(
            (i, (i * 97 + 53) % 30) for i in range(30) if i != (i * 97 + 53) % 30
        )
        graph.add_edges_from(edges)
        expected.add_edges_from(edges)
        mapping = {i: i + 1 for i in range(0, 30, 5)}
        expected_result = nx.relabel_nodes(expected, mapping, copy=True)

        _block_networkx_conversion(monkeypatch, "relabel_nodes")

        result = fnx.relabel_nodes(graph, mapping, copy=True)

        assert result.graph == expected_result.graph
        assert list(result.nodes(data=True)) == list(expected_result.nodes(data=True))
        assert list(result.edges(data=True)) == list(expected_result.edges(data=True))

    def test_preserves_edge_attrs(self, triangle):
        H = fnx.relabel_nodes(triangle, {"a": 0, "b": 1, "c": 2})
        edge_data = H.edges[0, 1]
        assert edge_data.get("weight") == 1.0

    @pytest.mark.parametrize(
        ("fnx_cls", "nx_cls"),
        [
            (fnx.Graph, nx.Graph),
            (fnx.DiGraph, nx.DiGraph),
            (fnx.MultiGraph, nx.MultiGraph),
            (fnx.MultiDiGraph, nx.MultiDiGraph),
        ],
    )
    @pytest.mark.parametrize(
        "mapping",
        [
            {"a": "x"},
            lambda node: node.upper(),
        ],
    )
    def test_matches_networkx_without_fallback(self, monkeypatch, fnx_cls, nx_cls, mapping):
        graph, expected = _label_graph_pair(fnx_cls, nx_cls)
        expected_result = nx.relabel_nodes(expected, mapping, copy=True)
        expected_signature = _graph_signature(expected_result)

        _block_networkx_conversion(monkeypatch, "relabel_nodes")

        result = fnx.relabel_nodes(graph, mapping, copy=True)

        assert result.is_directed() == expected_result.is_directed()
        assert result.is_multigraph() == expected_result.is_multigraph()
        assert _graph_signature(result) == expected_signature

    @pytest.mark.parametrize(
        ("fnx_cls", "nx_cls"),
        [
            (fnx.MultiGraph, nx.MultiGraph),
            (fnx.MultiDiGraph, nx.MultiDiGraph),
        ],
    )
    def test_copy_true_multigraph_key_collisions_match_networkx_without_fallback(
        self, monkeypatch, fnx_cls, nx_cls
    ):
        graph = fnx_cls()
        expected = nx_cls()
        for current in (graph, expected):
            current.add_edge(0, 2, key=0, label="left")
            current.add_edge(1, 2, key=0, label="right")

        expected_result = nx.relabel_nodes(expected, {0: 1}, copy=True)

        _block_networkx_conversion(monkeypatch, "relabel_nodes")

        result = fnx.relabel_nodes(graph, {0: 1}, copy=True)
        result_edges = sorted(
            (u, v, key, dict(data))
            for u, v, key, data in result.edges(keys=True, data=True)
        )
        expected_edges = sorted(
            (u, v, key, dict(data))
            for u, v, key, data in expected_result.edges(keys=True, data=True)
        )

        assert result.number_of_edges(1, 2) == expected_result.number_of_edges(1, 2)
        assert result_edges == expected_edges

    @pytest.mark.parametrize(
        ("fnx_cls", "nx_cls"),
        [
            (fnx.Graph, nx.Graph),
            (fnx.DiGraph, nx.DiGraph),
            (fnx.MultiGraph, nx.MultiGraph),
            (fnx.MultiDiGraph, nx.MultiDiGraph),
        ],
    )
    def test_copy_false_collision_matches_networkx_without_fallback(self, monkeypatch, fnx_cls, nx_cls):
        graph, expected = _label_graph_pair(fnx_cls, nx_cls)
        expected_result = nx.relabel_nodes(expected, {"a": "b"}, copy=False)
        expected_signature = _graph_signature(expected_result)

        _block_networkx_conversion(monkeypatch, "relabel_nodes")

        result = fnx.relabel_nodes(graph, {"a": "b"}, copy=False)

        assert result is graph
        assert _graph_signature(graph) == expected_signature

    @pytest.mark.parametrize(
        ("fnx_cls", "nx_cls"),
        [
            (fnx.Graph, nx.Graph),
            (fnx.DiGraph, nx.DiGraph),
            (fnx.MultiGraph, nx.MultiGraph),
            (fnx.MultiDiGraph, nx.MultiDiGraph),
        ],
    )
    @pytest.mark.parametrize(
        "mapping",
        [
            {"a": "b", "b": "c", "c": "a"},
            {"x": "y", "y": "x"},
        ],
    )
    def test_copy_false_cyclic_overlap_raises_like_networkx_without_fallback(
        self, monkeypatch, fnx_cls, nx_cls, mapping
    ):
        graph, expected = _label_graph_pair(fnx_cls, nx_cls)

        with pytest.raises(Exception) as nx_exc:
            nx.relabel_nodes(expected, mapping, copy=False)

        _block_networkx_conversion(monkeypatch, "relabel_nodes")

        with pytest.raises(Exception) as fnx_exc:
            fnx.relabel_nodes(graph, mapping, copy=False)

        assert type(fnx_exc.value).__name__ == type(nx_exc.value).__name__
        assert str(fnx_exc.value) == str(nx_exc.value)


# ---------------------------------------------------------------------------
# convert_node_labels_to_integers
# ---------------------------------------------------------------------------


class TestConvertNodeLabelsToIntegers:
    def test_basic(self, triangle):
        H = fnx.convert_node_labels_to_integers(triangle)
        assert H.number_of_nodes() == 3
        assert all(isinstance(n, int) for n in H.nodes())

    def test_first_label(self, triangle):
        H = fnx.convert_node_labels_to_integers(triangle, first_label=10)
        nodes = list(H.nodes())
        assert min(nodes) >= 10
        assert max(nodes) <= 12

    def test_label_attribute(self, triangle):
        H = fnx.convert_node_labels_to_integers(
            triangle, label_attribute="old_label"
        )
        for n in H.nodes():
            assert "old_label" in H.nodes[n]

    def test_preserves_edges(self, triangle):
        H = fnx.convert_node_labels_to_integers(triangle)
        assert H.number_of_edges() == 3

    @pytest.mark.parametrize(
        ("fnx_cls", "nx_cls"),
        [
            (fnx.Graph, nx.Graph),
            (fnx.DiGraph, nx.DiGraph),
            (fnx.MultiGraph, nx.MultiGraph),
            (fnx.MultiDiGraph, nx.MultiDiGraph),
        ],
    )
    @pytest.mark.parametrize(
        "ordering",
        ["default", "sorted", "increasing degree", "decreasing degree"],
    )
    def test_orderings_match_networkx_without_fallback(
        self,
        monkeypatch,
        fnx_cls,
        nx_cls,
        ordering,
    ):
        graph, expected = _label_graph_pair(fnx_cls, nx_cls)
        expected_result = nx.convert_node_labels_to_integers(
            expected,
            first_label=10,
            ordering=ordering,
            label_attribute="old",
        )
        expected_signature = _graph_signature(expected_result)

        _block_networkx_conversion(monkeypatch, "convert_node_labels_to_integers")

        result = fnx.convert_node_labels_to_integers(
            graph,
            first_label=10,
            ordering=ordering,
            label_attribute="old",
        )

        assert result.is_directed() == expected_result.is_directed()
        assert result.is_multigraph() == expected_result.is_multigraph()
        assert _graph_signature(result) == expected_signature


# ---------------------------------------------------------------------------
# to/from_dict_of_dicts
# ---------------------------------------------------------------------------


class TestDictOfDicts:
    def test_round_trip(self):
        G = fnx.Graph()
        G.add_edge(0, 1, weight=1.5)
        G.add_edge(1, 2, weight=2.5)
        d = fnx.to_dict_of_dicts(G)
        H = fnx.from_dict_of_dicts(d)
        assert H.number_of_nodes() == 3
        assert H.number_of_edges() == 2

    def test_nodelist_filter(self):
        G = fnx.Graph()
        G.add_edge(0, 1)
        G.add_edge(1, 2)
        d = fnx.to_dict_of_dicts(G, nodelist=[0, 1])
        assert 2 not in d

    def test_edge_data_override(self):
        G = fnx.Graph()
        G.add_edge(0, 1, weight=5.0)
        d = fnx.to_dict_of_dicts(G, edge_data=1)
        assert d[0][1] == 1

    def test_directed_default_preserves_successor_order_and_live_attrs(self):
        graph = fnx.DiGraph()
        expected = nx.DiGraph()
        for target, weight in (("b", 1), ("c", 2)):
            graph.add_edge("a", target, weight=weight)
            expected.add_edge("a", target, weight=weight)
        graph.add_edge("b", "a", weight=3)
        expected.add_edge("b", "a", weight=3)

        result = fnx.to_dict_of_dicts(graph)
        expected_result = nx.to_dict_of_dicts(expected)

        assert list(result) == list(expected_result)
        assert list(result["a"]) == list(expected_result["a"])
        assert result == expected_result
        assert result["a"]["b"] is graph["a"]["b"]
        assert result["b"]["a"] is graph["b"]["a"]
        assert "a" not in result["c"]

    def test_generated_graph_default_uses_live_cached_edge_attrs(self):
        graph = fnx.gnp_random_graph(6, 1.0, seed=7)
        first = fnx.to_dict_of_dicts(graph)
        u, v = next(iter(graph.edges()))

        assert list(first) == list(graph.nodes())
        assert list(first[u]) == list(graph[u])
        assert first[u][v] is graph[u][v]
        assert first[v][u] is graph[u][v]

        first[u][v]["marker"] = 11
        second = fnx.to_dict_of_dicts(graph)

        assert second is not first
        assert second[u] is not first[u]
        assert second[u][v] is graph[u][v]
        assert second[v][u] is graph[u][v]
        assert second[u][v]["marker"] == 11

        graph.add_edge("new", "node")
        third = fnx.to_dict_of_dicts(graph)

        assert "new" in third
        assert "node" in third["new"]
        assert third["new"]["node"] is graph["new"]["node"]

    @pytest.mark.parametrize(
        ("fnx_cls", "nx_cls"),
        [(fnx.MultiGraph, nx.MultiGraph), (fnx.MultiDiGraph, nx.MultiDiGraph)],
    )
    def test_multigraph_edge_key_mapping_is_plain_dict(self, fnx_cls, nx_cls):
        graph = fnx_cls()
        expected = nx_cls()
        graph.add_edge("a", "b", key="k0", weight=3)
        expected.add_edge("a", "b", key="k0", weight=3)

        result = fnx.to_dict_of_dicts(graph)
        expected_result = nx.to_dict_of_dicts(expected)

        assert result == expected_result
        assert isinstance(result["a"]["b"], dict)
        assert result["a"]["b"].copy() == expected_result["a"]["b"]

    @pytest.mark.parametrize(
        ("fnx_cls", "nx_cls"),
        [
            (fnx.Graph, nx.Graph),
            (fnx.DiGraph, nx.DiGraph),
            (fnx.MultiGraph, nx.MultiGraph),
            (fnx.MultiDiGraph, nx.MultiDiGraph),
        ],
    )
    def test_nodelist_tracks_mutations_like_networkx_without_fallback(
        self, monkeypatch, fnx_cls, nx_cls
    ):
        graph = fnx_cls()
        expected = nx_cls()
        if graph.is_multigraph():
            graph.add_edge("a", "b", key="k1", weight=1)
            expected.add_edge("a", "b", key="k1", weight=1)
        else:
            graph.add_edge("a", "b", weight=1)
            expected.add_edge("a", "b", weight=1)

        expected_result = nx.to_dict_of_dicts(expected, nodelist=["a", "b"])
        monkeypatch.setattr(
            nx,
            "to_dict_of_dicts",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("NetworkX to_dict_of_dicts fallback should not be used")
            ),
        )
        result = fnx.to_dict_of_dicts(graph, nodelist=["a", "b"])

        if graph.is_multigraph():
            graph.add_edge("a", "b", key="k2", weight=2)
            expected.add_edge("a", "b", key="k2", weight=2)
        else:
            graph["a"]["b"]["weight"] = 9
            expected["a"]["b"]["weight"] = 9

        assert _normalize_mapping(result) == _normalize_mapping(expected_result)

    def test_from_empty(self):
        G = fnx.from_dict_of_dicts({})
        assert G.number_of_nodes() == 0

    @pytest.mark.parametrize("cls", ["MultiGraph", "MultiDiGraph"])
    @pytest.mark.parametrize("nodelist", [None, [0, 1, 2]], ids=["all", "nodelist"])
    @pytest.mark.parametrize(
        "op_name,op",
        [
            ("setitem", lambda v: v.__setitem__("k", {"c": 3})),
            ("delitem", lambda v: v.__delitem__(0)),
            ("pop", lambda v: v.pop(0, None)),
            ("popitem", lambda v: v.popitem()),
            ("setdefault", lambda v: v.setdefault("k", {"c": 3})),
            ("update", lambda v: v.update({"k": {"c": 3}})),
            ("ior", lambda v: v.__ior__({"k": {"c": 3}})),
        ],
    )
    def test_multigraph_value_writes_match_networkx(self, cls, nodelist, op_name, op):
        """br-r37-c1-5cqna: with no nodelist networkx's d[u][v] on a multigraph
        IS the graph's keydict, so a write through it adds or removes that edge;
        with a nodelist it is the read-only G[u][v] view, and the write raises.
        fnx's value was a read-only view on both paths. Compare the error, the
        resulting graph and the returned mapping with networkx."""
        states = []
        for lib in (nx, fnx):
            graph = getattr(lib, cls)([(0, 1, {"w": 1}), (0, 1, {"w": 2}), (1, 2, {"w": 5})])
            d = lib.to_dict_of_dicts(graph, nodelist=nodelist)
            try:
                op(d[0][1])
                error = None
            except (TypeError, AttributeError) as exc:
                error = type(exc).__name__
            states.append(
                (
                    error,
                    sorted(map(repr, graph.edges(keys=True, data=True))),
                    json.dumps(d, default=lambda view: dict(view)),
                )
            )
        assert states[1] == states[0]

    @pytest.mark.parametrize("cls", ["MultiGraph", "MultiDiGraph"])
    def test_multigraph_values_are_the_graphs_keydicts(self, cls):
        """br-r37-c1-5cqna: json and every other reader of the dict storage saw
        {} for fnx's multigraph d[u][v]; networkx's value is the keydict itself,
        live, and shared by d[u][v] and d[v][u] on an undirected graph."""
        graphs = [getattr(lib, cls)() for lib in (nx, fnx)]
        results = []
        for graph, lib in zip(graphs, (nx, fnx)):
            graph.add_edge(0, 1, weight=1.0)
            graph.add_edge(0, 1, key="k", c=2)
            graph.add_edge(2, 1)
            d = lib.to_dict_of_dicts(graph)
            before = json.dumps(d)
            graph.add_edge(0, 1, key="late", c=9)
            results.append(
                (
                    before,
                    json.dumps(d),
                    d[0][1] is graph.get_edge_data(0, 1),
                    d[1].get(0) is d[0][1],
                    isinstance(d[0][1], dict),
                )
            )
        assert results[1] == results[0]

    @pytest.mark.parametrize("nodelist", [None, [0, 1]], ids=["all", "nodelist"])
    @pytest.mark.parametrize("copier", ["pickle", "deepcopy"])
    def test_multigraph_value_round_trips_like_networkx(self, nodelist, copier):
        """br-r37-c1-lmev-pickle: pickle.loads on to_dict_of_dicts(MG) output
        once crashed. It must round-trip, and come back as the same kind of
        mapping networkx's does - a plain dict from the keydict path, the view
        type from the nodelist path."""
        import copy
        import pickle

        restored = []
        for lib in (nx, fnx):
            M = lib.MultiGraph([(0, 1, {"w": 1}), (0, 1, {"w": 2})])
            out = lib.to_dict_of_dicts(M, nodelist=nodelist)
            if copier == "pickle":
                again = pickle.loads(pickle.dumps(out))  # nosec B301  # ubs:ignore - trusted round trip
            else:
                again = copy.deepcopy(out)
            value = again[0][1]
            restored.append((type(value).__name__, isinstance(value, dict), dict(value)))
        assert restored[1] == restored[0]
        assert restored[1][2] == {0: {"w": 1}, 1: {"w": 2}}

    def test_preserves_isolated_nodes(self):
        # Node 5 has no neighbors but should still be in the graph.
        d = {0: {1: {"weight": 1.0}}, 1: {0: {"weight": 1.0}}, 5: {}}
        G = fnx.from_dict_of_dicts(d)
        assert G.number_of_nodes() == 3
        assert G.has_node(5)
        assert G.number_of_edges() == 1


# ---------------------------------------------------------------------------
# to/from_dict_of_lists
# ---------------------------------------------------------------------------


class TestDictOfLists:
    def test_convert_module_signature_and_value_match_legacy_oracle(self):
        module = importlib.import_module("franken_networkx.convert")
        legacy = _legacy_networkx()
        graph = fnx.DiGraph([("a", "b"), ("b", "c")])
        legacy_graph = legacy.DiGraph([("a", "b"), ("b", "c")])

        assert inspect.signature(module.to_dict_of_lists).parameters == inspect.signature(
            legacy.to_dict_of_lists
        ).parameters
        assert module.to_dict_of_lists(
            graph, nodelist=["a", "b"], backend="networkx"
        ) == legacy.to_dict_of_lists(
            legacy_graph, nodelist=["a", "b"], backend="networkx"
        )
        with pytest.raises(ImportError):
            module.to_dict_of_lists(graph, backend="missing")
        with pytest.raises(TypeError):
            module.to_dict_of_lists(graph, unexpected=True)

    def test_round_trip(self):
        G = fnx.Graph()
        G.add_edge(0, 1)
        G.add_edge(1, 2)
        d = fnx.to_dict_of_lists(G)
        assert 1 in d[0]
        H = fnx.from_dict_of_lists(d)
        assert H.number_of_edges() == 2

    def test_nodelist_filter(self):
        G = fnx.Graph()
        G.add_edge(0, 1)
        G.add_edge(1, 2)
        d = fnx.to_dict_of_lists(G, nodelist=[0, 1])
        assert 2 not in d

    @pytest.mark.parametrize(
        ("fnx_cls", "nx_cls"),
        [
            (fnx.DiGraph, nx.DiGraph),
            (fnx.MultiDiGraph, nx.MultiDiGraph),
        ],
    )
    def test_directed_parity_without_fallback(self, monkeypatch, fnx_cls, nx_cls):
        graph = fnx_cls()
        expected = nx_cls()
        if graph.is_multigraph():
            graph.add_edge("a", "b", key="k1")
            graph.add_edge("a", "b", key="k2")
            graph.add_edge("b", "c", key="j")
            expected.add_edge("a", "b", key="k1")
            expected.add_edge("a", "b", key="k2")
            expected.add_edge("b", "c", key="j")
        else:
            graph.add_edge("a", "b")
            graph.add_edge("b", "c")
            expected.add_edge("a", "b")
            expected.add_edge("b", "c")

        expected_all = nx.to_dict_of_lists(expected)
        expected_filtered = nx.to_dict_of_lists(expected, nodelist=["a", "b"])

        monkeypatch.setattr(
            nx,
            "to_dict_of_lists",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("NetworkX to_dict_of_lists fallback should not be used")
            ),
        )

        assert fnx.to_dict_of_lists(graph) == expected_all
        assert fnx.to_dict_of_lists(graph, nodelist=["a", "b"]) == expected_filtered

    def test_from_empty(self):
        G = fnx.from_dict_of_lists({})
        assert G.number_of_nodes() == 0

    def test_create_using_graph_class(self):
        G = fnx.from_dict_of_lists({0: [1], 1: [0]}, create_using=fnx.DiGraph)
        assert isinstance(G, fnx.DiGraph)
        assert G.has_edge(0, 1)

    def test_create_using_instance_is_cleared(self):
        G = fnx.Graph()
        G.add_edge("stale", "edge")
        H = fnx.from_dict_of_lists({0: [1], 1: [0]}, create_using=G)
        assert H is G
        assert not H.has_node("stale")
        assert H.number_of_edges() == 1

    def test_multigraph_symmetric_adjacency_deduplicates_parallel_edges(self):
        adjacency = {0: [1, 2], 1: [0, 2, 3], 2: [0, 1, 4], 3: [1], 4: [2]}

        actual = fnx.from_dict_of_lists(adjacency, create_using=fnx.MultiGraph())
        expected = nx.from_dict_of_lists(adjacency, create_using=nx.MultiGraph())

        assert actual.number_of_edges() == expected.number_of_edges() == 5
        assert sorted(actual.edges(keys=True)) == sorted(expected.edges(keys=True))


# ---------------------------------------------------------------------------
# to/from_edgelist
# ---------------------------------------------------------------------------


class TestEdgelist:
    def test_round_trip(self):
        G = fnx.Graph()
        G.add_edge(0, 1, weight=1.0)
        G.add_edge(1, 2, weight=2.0)
        # br-r37-c1-rsvst: to_edgelist now returns G.edges(data=True)
        # directly (an EdgeDataView, matching nx). Materialize via
        # list() before subscripting.
        el = list(fnx.to_edgelist(G))
        assert len(el) == 2
        assert len(el[0]) == 3

        H = fnx.from_edgelist([(u, v) for u, v, _ in el])
        assert H.number_of_edges() == 2

    def test_nodelist_filter(self):
        G = fnx.Graph()
        G.add_edge(0, 1)
        G.add_edge(1, 2)
        # br-r37-c1-rsvst: nodelist semantics now match nx — edges
        # incident to ANY node in nodelist, not just edges fully within
        # nodelist. Passing nodelist=[0, 1] therefore includes (1, 2)
        # too because 1 ∈ nodelist.
        el = list(fnx.to_edgelist(G, nodelist=[0, 1]))
        assert len(el) == 2
        edge_set = {(u, v) for u, v, _ in el}
        assert (0, 1) in edge_set
        assert (1, 2) in edge_set

    def test_to_edgelist_preserves_directed_order_and_live_attrs(self):
        G = fnx.DiGraph()
        G.add_edge("a", "b", weight=1)
        G.add_edge("a", "c", weight=2)

        el = list(fnx.to_edgelist(G))

        if [(u, v) for u, v, _ in el] != [("a", "b"), ("a", "c")]:
            raise AssertionError("to_edgelist changed directed edge order")
        if el[0][2] is not G["a"]["b"]:
            raise AssertionError("to_edgelist did not preserve live edge attrs")
        el[0][2]["seen"] = True
        if not G["a"]["b"]["seen"]:
            raise AssertionError("to_edgelist attr dict is detached from graph storage")

    def test_from_edgelist_with_data(self):
        edges = [(0, 1, {"weight": 1.0}), (1, 2, {"weight": 2.0})]
        G = fnx.from_edgelist(edges)
        assert G.number_of_edges() == 2

    def test_from_edgelist_create_using_graph_class(self):
        G = fnx.from_edgelist([(0, 1)], create_using=fnx.DiGraph)
        assert isinstance(G, fnx.DiGraph)
        assert G.has_edge(0, 1)


# ---------------------------------------------------------------------------
# to/from_numpy_array
# ---------------------------------------------------------------------------


class TestNumpyArray:
    @pytest.fixture(autouse=True)
    def _skip_no_numpy(self):
        pytest.importorskip("numpy")

    def test_round_trip(self):

        G = fnx.Graph()
        G.add_edge(0, 1, weight=2.0)
        G.add_edge(1, 2, weight=3.0)
        A = fnx.to_numpy_array(G)
        assert A.shape == (3, 3)
        assert A[0, 1] == 2.0
        assert A[1, 0] == 2.0  # undirected symmetry
        assert A[0, 2] == 0.0  # no edge

        H = fnx.from_numpy_array(A)
        assert H.number_of_nodes() == 3
        assert H.number_of_edges() == 2

    def test_nonedge_value(self):

        G = fnx.Graph()
        G.add_node(0)
        G.add_node(1)
        A = fnx.to_numpy_array(G, nonedge=-1.0)
        assert A[0, 1] == -1.0

    def test_weight_none(self):
        G = fnx.Graph()
        G.add_edge(0, 1)
        A = fnx.to_numpy_array(G, weight=None)
        assert A[0, 1] == 1.0


# ---------------------------------------------------------------------------
# to/from_scipy_sparse_array
# ---------------------------------------------------------------------------


class TestScipySparseArray:
    @pytest.fixture(autouse=True)
    def _skip_no_scipy(self):
        pytest.importorskip("scipy")

    def test_round_trip(self):
        G = fnx.Graph()
        G.add_edge(0, 1, weight=2.0)
        G.add_edge(1, 2, weight=3.0)
        S = fnx.to_scipy_sparse_array(G)
        assert S.shape == (3, 3)

        H = fnx.from_scipy_sparse_array(S)
        assert H.number_of_nodes() == 3
        assert H.number_of_edges() == 2

    def test_format(self):
        G = fnx.Graph()
        G.add_edge(0, 1)
        for fmt in ("csr", "csc", "coo"):
            S = fnx.to_scipy_sparse_array(G, format=fmt)
            assert S.format == fmt


# ---------------------------------------------------------------------------
# to/from_pandas_edgelist
# ---------------------------------------------------------------------------


class TestPandasEdgelist:
    @pytest.fixture(autouse=True)
    def _skip_no_pandas(self):
        pytest.importorskip("pandas")

    def test_round_trip(self):
        import pandas as pd

        G = fnx.Graph()
        G.add_edge("a", "b", weight=1.0)
        G.add_edge("b", "c", weight=2.0)
        df = fnx.to_pandas_edgelist(G)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2
        assert "source" in df.columns
        assert "target" in df.columns

        H = fnx.from_pandas_edgelist(df, edge_attr=True)
        assert H.number_of_edges() == 2

    def test_custom_columns(self):

        G = fnx.Graph()
        G.add_edge(0, 1)
        df = fnx.to_pandas_edgelist(G, source="src", target="dst")
        assert "src" in df.columns
        assert "dst" in df.columns

        H = fnx.from_pandas_edgelist(df, source="src", target="dst")
        assert H.has_edge(0, 1)

    def test_from_pandas_edgelist_signature_matches_networkx_backend_surface(self):
        assert str(inspect.signature(fnx.from_pandas_edgelist)) == str(
            inspect.signature(nx.from_pandas_edgelist)
        )

    @pytest.mark.parametrize("backend", [None, "networkx"])
    def test_from_pandas_edgelist_accepts_supported_backend_keyword(self, backend):
        import pandas as pd

        df = pd.DataFrame([{"source": "a", "target": "b"}])
        G = fnx.from_pandas_edgelist(df, backend=backend)
        assert sorted(G.edges()) == [("a", "b")]

    def test_from_pandas_edgelist_backend_error_wording_matches_networkx(self):
        import pandas as pd

        df = pd.DataFrame([{"source": "a", "target": "b"}])

        with pytest.raises(ImportError) as actual_backend:
            fnx.from_pandas_edgelist(df, backend="missing")
        with pytest.raises(ImportError) as expected_backend:
            nx.from_pandas_edgelist(df, backend="missing")
        assert str(actual_backend.value) == str(expected_backend.value)

        with pytest.raises(TypeError) as actual_literal:
            fnx.from_pandas_edgelist(df, backend_kwargs={"x": 1})
        with pytest.raises(TypeError) as expected_literal:
            nx.from_pandas_edgelist(df, backend_kwargs={"x": 1})
        assert str(actual_literal.value) == str(expected_literal.value)

        with pytest.raises(TypeError) as actual_unknown:
            fnx.from_pandas_edgelist(df, bogus=1)
        with pytest.raises(TypeError) as expected_unknown:
            nx.from_pandas_edgelist(df, bogus=1)
        assert str(actual_unknown.value) == str(expected_unknown.value)


class TestCrossClassConstructor:
    """Regression for franken_networkx-xmginit: fnx.Graph(MultiGraph)
    used to drop all edges because the Rust __new__ copies nodes for
    cross-class instantiations but not edges.
    """

    def test_graph_from_multigraph_collapses_parallel_edges(self):
        MG = fnx.MultiGraph()
        MG.add_edges_from([(0, 1), (0, 1), (1, 2)])
        G = fnx.Graph(MG)
        assert sorted(G.edges()) == [(0, 1), (1, 2)]

    def test_graph_from_multigraph_last_attr_wins(self):
        MG = fnx.MultiGraph()
        MG.add_edge(0, 1, key="a", w=1.0)
        MG.add_edge(0, 1, key="b", w=2.0)
        G = fnx.Graph(MG)
        assert dict(G.edges[0, 1]) == {"w": 2.0}

    def test_digraph_from_multidigraph_collapses(self):
        MD = fnx.MultiDiGraph()
        MD.add_edges_from([(0, 1), (0, 1), (1, 2)])
        D = fnx.DiGraph(MD)
        assert sorted(D.edges()) == [(0, 1), (1, 2)]

    def test_multigraph_from_multigraph_preserves_keys(self):
        src = fnx.MultiGraph()
        src.add_edge(0, 1, key="a", w=1.0)
        src.add_edge(0, 1, key="b", w=2.0)
        dst = fnx.MultiGraph(src)
        # Ordering of parallel edges isn't fixed by nx's contract — compare
        # as a set so either emission order is acceptable.
        actual = {
            (frozenset((u, v)), k, tuple(sorted(d.items())))
            for u, v, k, d in dst.edges(keys=True, data=True)
        }
        assert actual == {
            (frozenset((0, 1)), "a", (("w", 1.0),)),
            (frozenset((0, 1)), "b", (("w", 2.0),)),
        }

    def test_multigraph_from_simple_graph(self):
        src = fnx.Graph()
        src.add_edges_from([(0, 1), (1, 2)])
        dst = fnx.MultiGraph(src)
        assert dst.number_of_edges() == 2
        assert list(dst.edges(keys=True)) == [(0, 1, 0), (1, 2, 0)]

    def test_graph_from_non_parallel_multigraph(self):
        MG = fnx.MultiGraph()
        MG.add_edges_from([(0, 1), (1, 2)])
        G = fnx.Graph(MG)
        assert sorted(G.edges()) == [(0, 1), (1, 2)]

    def test_graph_from_graph_unchanged(self):
        src = fnx.Graph()
        src.add_edges_from([(0, 1), (1, 2)])
        dst = fnx.Graph(src)
        assert list(dst.edges()) == [(0, 1), (1, 2)]


class TestCrossLibraryConstructor:
    """Regression for franken_networkx-nxgraph: fnx.Graph(nx.path_graph(3))
    silently returned an empty graph because the Rust __new__ only copies
    nodes for foreign (nx) graph instances, not edges.
    """

    def test_fnx_graph_from_nx_graph(self):
        import networkx as nx
        r = fnx.Graph(nx.path_graph(3))
        assert sorted(r.edges()) == [(0, 1), (1, 2)]

    def test_fnx_digraph_from_nx_digraph(self):
        import networkx as nx
        r = fnx.DiGraph(nx.DiGraph([(0, 1), (1, 2)]))
        assert sorted(r.edges()) == [(0, 1), (1, 2)]

    def test_fnx_multigraph_from_nx_multigraph_preserves_parallels(self):
        import networkx as nx
        r = fnx.MultiGraph(nx.MultiGraph([(0, 1), (0, 1), (1, 2)]))
        assert r.number_of_edges() == 3

    def test_fnx_graph_from_nx_multigraph_collapses(self):
        import networkx as nx
        r = fnx.Graph(nx.MultiGraph([(0, 1), (0, 1), (1, 2)]))
        assert sorted(r.edges()) == [(0, 1), (1, 2)]

    def test_fnx_multigraph_from_nx_graph(self):
        import networkx as nx
        r = fnx.MultiGraph(nx.path_graph(3))
        assert r.number_of_edges() == 2

    def test_nx_internals_work_on_fnx(self):
        """nx.to_dict_of_dicts uses AtlasView.copy() — br-atlascp adds it."""
        import networkx as nx
        assert nx.to_dict_of_dicts(fnx.path_graph(3)) == {
            0: {1: {}}, 1: {0: {}, 2: {}}, 2: {1: {}},
        }


_LIVE_DOD_CASES = [
    (graph_class, private, kind)
    for graph_class in ("Graph", "DiGraph", "MultiGraph", "MultiDiGraph")
    for private in (False, True)
    for kind in (
        ["plain", "filtered", "restricted", "edge", "conversion"]
        + (["reverse"] if graph_class in ("DiGraph", "MultiDiGraph") else [])
    )
]


def _live_dod_graph(lib, graph_class, private):
    graph = getattr(lib, graph_class)()
    graph.add_nodes_from([3, 0, 4, 1, 2])
    for u, v in [(0, 1), (1, 2), (2, 0), (3, 2), (3, 4), (1, 0), (0, 0)]:
        attrs = {"weight": 3.5, "side": f"{u}->{v}"}
        if graph.is_multigraph():
            graph.add_edge(u, v, key=7, **attrs)
            graph.add_edge(u, v, key=9, weight=4.5)
        else:
            graph.add_edge(u, v, **attrs)
    if private:
        succ = {u: {} for u in graph}
        pred = {u: {} for u in graph}
        for u, v in [(0, 2), (2, 1), (3, 1), (2, 0), (0, 0)]:
            attrs = {"weight": 5.5, "side": f"{u}->{v}"}
            data = {7: attrs, 9: {"weight": 6.5}} if graph.is_multigraph() else attrs
            succ[u][v] = data
            (pred if graph.is_directed() else succ)[v][u] = data
        if graph.is_directed():
            graph._succ, graph._pred = succ, pred
        graph._adj = succ
    return graph


def _live_dod_view(lib, graph, kind):
    if kind == "plain":
        return graph
    if kind == "filtered":
        return graph.subgraph([0, 1, 2, 3])
    if kind == "restricted":
        return lib.restricted_view(graph, [4], [])
    if kind == "edge":
        edges = [(0, 0, 7), (2, 0, 7)] if graph.is_multigraph() else [(0, 0), (2, 0)]
        return graph.edge_subgraph(edges)
    if kind == "conversion":
        if graph.is_directed():
            return graph.to_undirected(as_view=True)
        return graph.to_directed(as_view=True)
    assert kind == "reverse"
    return graph.reverse(copy=False)


def _live_dod_signature(value):
    """Preserve every mapping layer's insertion order, without sorting."""
    if isinstance(value, Mapping):
        return [(key, _live_dod_signature(item)) for key, item in value.items()]
    return value


def _live_dod_observe(lib, graph, options):
    try:
        result = lib.to_dict_of_dicts(graph, **options)
    except Exception as error:
        return ("error", type(error).__name__, error.args)
    try:
        encoded = ("json", json.dumps(result))
    except TypeError as error:
        encoded = ("json-error", error.args)
    return ("result", _live_dod_signature(result), encoded)


@pytest.mark.parametrize("graph_class,private,kind", _LIVE_DOD_CASES)
@pytest.mark.parametrize("option", ["default", "list", "tuple", "iterator", "constant", "constant_list"])
def test_live_dod_actual_mapping_and_view_parity(graph_class, private, kind, option):
    actual = _live_dod_view(fnx, _live_dod_graph(fnx, graph_class, private), kind)
    expected = _live_dod_view(nx, _live_dod_graph(nx, graph_class, private), kind)
    nodes = list(expected)[::-1]
    constant = {"shared": ["payload"]}

    def options():
        if option == "list":
            return {"nodelist": nodes}
        if option == "tuple":
            return {"nodelist": tuple(nodes)}
        if option == "iterator":
            return {"nodelist": iter(nodes)}
        if option == "constant":
            return {"edge_data": constant}
        if option == "constant_list":
            return {"nodelist": nodes[:3], "edge_data": constant}
        return {}

    assert _live_dod_observe(fnx, actual, options()) == _live_dod_observe(nx, expected, options())


@pytest.mark.parametrize("graph_class", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("constant", [None, 17])
def test_live_dod_includes_adjacency_only_nodes(graph_class, constant):
    graphs = [_live_dod_graph(lib, graph_class, True) for lib in (fnx, nx)]
    for graph in graphs:
        data = {7: {"foreign": True}} if graph.is_multigraph() else {"foreign": True}
        graph._adj["adjacency-only"] = {0: data}
    options = {"edge_data": constant}
    assert _live_dod_observe(fnx, graphs[0], options) == _live_dod_observe(nx, graphs[1], options)


@pytest.mark.parametrize("graph_class", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("private", [False, True])
def test_live_dod_shallow_copy_keeps_inner_references_and_tracks_new_rows(graph_class, private):
    snapshots = []
    for lib in (fnx, nx):
        graph = _live_dod_graph(lib, graph_class, private)
        u, v = (0, 2) if private else (0, 1)
        first = lib.to_dict_of_dicts(graph)
        held = first[u][v]
        assert held is graph.get_edge_data(u, v)
        second = lib.to_dict_of_dicts(graph)
        assert second is not first and second[u] is not first[u]
        assert second[u][v] is held
        first[u].pop(v)
        assert v in second[u] and graph.has_edge(u, v)
        if graph.is_multigraph():
            held[7]["changed"] = [1, 2]
            graph.add_edge(u, v, key=11, weight=11.5)
            assert list(held) == [7, 9, 11]
            held[13] = {"weight": 13.5}
            assert graph.has_edge(u, v, 13)
            assert graph.get_edge_data(u, v, 13) is held[13]
        else:
            held["changed"] = [1, 2]
            assert graph.get_edge_data(u, v)["changed"] == [1, 2]
        if private:
            # Native shape epochs do not change when assigned rows are edited.
            graph._adj[u][v] = {23: {"replacement": True}} if graph.is_multigraph() else {"replacement": True}
        else:
            graph.add_edge(u, 4)
        snapshots.append(_live_dod_observe(lib, graph, {}))
    assert snapshots[0] == snapshots[1]


@pytest.mark.parametrize("graph_class,private,kind", _LIVE_DOD_CASES)
def test_live_dod_constant_is_shared_not_copied(graph_class, private, kind):
    graph = _live_dod_view(fnx, _live_dod_graph(fnx, graph_class, private), kind)
    constant = {"mutable": []}
    result = fnx.to_dict_of_dicts(graph, edge_data=constant)
    assert any(result.values())
    assert all(value is constant for row in result.values() for value in row.values())


@pytest.mark.parametrize("graph_class", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
def test_live_dod_ordinary_native_route_is_retained(graph_class):
    graph = _live_dod_graph(fnx, graph_class, False)
    calls = []

    def profile(frame, event, arg):
        if event == "c_call":
            calls.append(getattr(arg, "__name__", ""))

    previous = sys.getprofile()
    sys.setprofile(profile)
    try:
        fnx.to_dict_of_dicts(graph)
    finally:
        sys.setprofile(previous)
    required = "_native_to_dict_of_dicts_live" if graph.is_multigraph() else "to_dict_of_dicts_undirected"
    assert required in calls


@pytest.mark.parametrize("graph_class", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("private", [False, True])
def test_live_dod_restricted_view_reads_authoritative_neighbor_keys(graph_class, private):
    actual = _live_dod_view(fnx, _live_dod_graph(fnx, graph_class, private), "restricted")
    expected = _live_dod_view(nx, _live_dod_graph(nx, graph_class, private), "restricted")
    assert [(u, list(actual[u])) for u in actual] == [(u, list(expected[u])) for u in expected]


@pytest.mark.parametrize("graph_class,private,kind", [case for case in _LIVE_DOD_CASES if case[2] in ("conversion", "reverse")])
def test_live_dod_view_copy_depth_and_live_keydict_mutation(graph_class, private, kind):
    observations = []
    for lib in (fnx, nx):
        root = _live_dod_graph(lib, graph_class, private)
        source_attrs = root.get_edge_data(0, 0, 7) if root.is_multigraph() else root.get_edge_data(0, 0)
        source_attrs["nested"] = []
        view = _live_dod_view(lib, root, kind)
        exported = lib.to_dict_of_dicts(view)
        held = exported[0][0]
        attrs = held[7] if view.is_multigraph() else held
        sharing = (attrs is source_attrs, attrs["nested"] is source_attrs["nested"])
        attrs["exported"] = True
        attrs["nested"].append("shared")
        if view.is_multigraph():
            held[13] = {"weight": 13.5}
            root.add_edge(0, 0, key=17, weight=17.5)
        observations.append((sharing, _live_dod_signature(exported), _live_dod_observe(lib, root, {})))
    assert observations[0] == observations[1]


@pytest.mark.parametrize("graph_class", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("private", [False, True, "node_only"])
def test_live_dod_graph_subclass_keeps_inner_dictionary_identity(graph_class, private):
    for lib in (fnx, nx):
        subclass = type("ExportGraph", (getattr(lib, graph_class),), {})
        graph = subclass()
        if graph.is_multigraph():
            graph.add_edge(0, 1, key=7, weight=3.5)
        else:
            graph.add_edge(0, 1, weight=3.5)
        if private == "node_only":
            graph._node = {0: {}, 1: {}, "node-only": {}}
        elif private:
            data = {7: {"weight": 5.5}} if graph.is_multigraph() else {"weight": 5.5}
            graph._adj = {0: {1: data}, 1: {} if graph.is_directed() else {0: data}}
        exported = lib.to_dict_of_dicts(graph)
        assert exported[0][1] is graph.get_edge_data(0, 1)
        if graph.is_multigraph():
            graph.add_edge(0, 1, key=11, weight=11.5)
            assert list(exported[0][1]) == [7, 11]
        else:
            graph.add_edge(0, 1, changed=True)
            assert exported[0][1]["changed"] is True


@pytest.mark.parametrize("graph_class", ["MultiGraph", "MultiDiGraph"])
def test_live_dod_node_only_override_keeps_raw_keydict_and_lookup_errors(graph_class):
    for lib in (fnx, nx):
        graph = getattr(lib, graph_class)()
        graph.add_edge(0, 1, key=7, weight=3.5)
        held = graph.get_edge_data(0, 1)
        graph._node = {"node-only": {}}
        assert graph.get_edge_data(0, 1) is held
        assert graph.get_edge_data(0, 1, 7) is held[7]
        sentinel = object()
        assert graph.get_edge_data(0, 1, 9, sentinel) is sentinel
        assert graph.get_edge_data(8, 9, default=sentinel) is sentinel
        for args in (([], 1), (0, []), (0, 1, [])):
            with pytest.raises(TypeError, match="unhashable type: 'list'"):
                graph.get_edge_data(*args)


@pytest.mark.parametrize("graph_class", ["MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("hub_index", range(3))
@pytest.mark.parametrize("export_first", [False, True], ids=["get", "export"])
@pytest.mark.parametrize("operation", ["remove_node", "remove_nodes_from", "clear_edges", "clear"])
def test_keydict_registry_endpoint_removal_matches_networkx(
    graph_class, hub_index, export_first, operation
):
    """49u7h: both registry indexes must detach every incident held dict.

    Rotating the hub covers both canonical endpoint roles on MultiGraph;
    incoming, outgoing, and self-loop rows exercise both roles on MultiDiGraph.
    Unrelated rows distinguish node removal from clearing the entire registry.
    """
    observations = []
    for lib in (nx, fnx):
        labels = ["a-long-node-label", "m-long-node-label", "z-long-node-label"]
        hub = labels[hub_index]
        left, right = [node for node in labels if node != hub]
        pairs = [(hub, left), (left, hub), (hub, right), (right, hub),
                 (hub, hub), (left, right), ("outside-a", "outside-z")]
        graph = getattr(lib, graph_class)()
        graph.add_nodes_from(labels + ["outside-a", "outside-z"])
        for index, (u, v) in enumerate(pairs):
            graph.add_edge(u, v, key="first", weight=index)
            graph.add_edge(u, v, key="second", weight=index + 10)
        exported = lib.to_dict_of_dicts(graph) if export_first else None
        held = [exported[u][v] if export_first else graph.get_edge_data(u, v)
                for u, v in pairs]
        assert all(isinstance(row, dict) for row in held)
        before = [dict(row) for row in held]
        if operation == "remove_nodes_from":
            graph.remove_nodes_from([hub, "absent-node"])
        elif operation == "remove_node":
            graph.remove_node(hub)
        else:
            getattr(graph, operation)()
        assert [dict(row) for row in held] == before

        def state():
            return (
                list(graph),
                list(graph.edges(keys=True, data=True)),
                [list(row.items()) for row in held],
                [graph.get_edge_data(u, v) is row
                 for (u, v), row in zip(pairs, held)],
                None if exported is None else json.dumps(exported),
                json.dumps(lib.to_dict_of_dicts(graph)),
            )

        trace = [state()]
        # Detached rows are ordinary dictionaries; unrelated registered rows
        # still write through on a node-only removal. Compare both behaviors.
        for index, row in enumerate(held):
            row["held-write"] = {"weight": index + 100}
        trace.append(state())
        graph.add_edge(hub, left, key="new-generation", weight=200)
        trace.append(state())
        observations.append(trace)
    assert observations[1] == observations[0]


@pytest.mark.parametrize("graph_class", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("copy_method", ["copy", "constructor", "deepcopy"])
@pytest.mark.parametrize("copied_weight", [1, 0.5], ids=["integer", "fractional"])
@pytest.mark.parametrize("warm", [False, True], ids=["cold", "warm"])
def test_graph_copy_mutations_do_not_share_revision_caches(
    graph_class, copy_method, copied_weight, warm
):
    """Equal revision numbers must not join two independent copied graphs."""
    observations = []
    for lib in (nx, fnx):
        graph = getattr(lib, graph_class)()
        graph.add_nodes_from([0, 1, 2])
        graph.add_edge(0, 1, weight=1)

        def paths(subject):
            # Numeric equality alone hides an integer/float cache mix-up.
            return [
                (node, [(target, type(distance), distance)
                        for target, distance in distances.items()])
                for node, distances in lib.all_pairs_dijkstra_path_length(subject)
            ]

        warm_paths = paths(graph) if warm else None
        if copy_method == "constructor":
            copied = getattr(lib, graph_class)(graph)
        elif copy_method == "deepcopy":
            copied = copy.deepcopy(graph)
        else:
            copied = graph.copy()
        # Both graphs advance their native revisions by the same amount, but
        # their edge sets differ. Alternate queries to expose a shared memo.
        copied.remove_edge(0, 1)
        copied.add_edge(0, 2, weight=copied_weight)
        graph.remove_edge(0, 1)
        graph.add_edge(1, 2, weight=1)
        trace = [warm_paths]
        for subject in (copied, graph, copied, graph):
            trace.append((list(subject.edges(data=True)), paths(subject)))
        observations.append(trace)
    assert observations[1] == observations[0]


@pytest.mark.parametrize("graph_class,operation", [
    ("MultiGraph", "copy"), ("MultiGraph", "constructor"),
    ("MultiDiGraph", "copy"), ("MultiDiGraph", "constructor"),
    ("MultiDiGraph", "reverse"),
])
@pytest.mark.parametrize("self_loop", [False, True], ids=["pair", "loop"])
@pytest.mark.parametrize("empty_all", [False, True], ids=["mixed", "edgeless"])
def test_keydict_registry_copy_walk_omits_empty_pairs(
    graph_class, operation, self_loop, empty_all
):
    """A native clone must reproduce the incumbent's edge-only copy walk.

    Source ghost adjacency stays live; copying, constructing or reversing
    a new graph does not copy a pair whose keydict has no edges. Unrelated
    real pairs distinguish dropping ghosts from clearing every edge.
    """
    observations = []
    for lib in (nx, fnx):
        graph = getattr(lib, graph_class)()
        graph.add_nodes_from(["before", "u", "v", "after"])
        target = "u" if self_loop else "v"
        graph.add_edge("u", "before", key="before", weight=3)
        graph.add_edge("u", target, key="ghost", weight=1)
        graph.add_edge("u", "after", key="after", weight=4)
        graph.add_edge("before", "v", key="incoming", weight=5)
        exported = lib.to_dict_of_dicts(graph)
        held = exported["u"][target]
        held.clear()
        if empty_all:
            for row in exported.values():
                for keydict in row.values():
                    keydict.clear()
        assert graph.has_edge("u", target) and not held

        def state(subject):
            return (
                list(subject),
                [(node, list(row)) for node, row in subject.adjacency()],
                list(subject.edges(keys=True, data=True)),
                list(subject.degree()), subject.number_of_edges(),
                json.dumps(lib.to_dict_of_dicts(subject)),
            )

        before = state(graph)
        if operation == "copy":
            copied = graph.copy()
        elif operation == "constructor":
            copied = type(graph)(graph)
        else:
            copied = graph.reverse(copy=True)
        trace = [before, state(copied), state(graph)]
        assert state(graph) == before
        assert graph.get_edge_data("u", target) is held
        copied.add_edge("u", target, key="replacement", weight=9)
        trace.extend([state(copied), state(graph), list(held.items())])
        observations.append(trace)
    assert observations[1] == observations[0]


@pytest.mark.parametrize("graph_class", ["MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("key_type", [str, int], ids=["str-subclass", "int-subclass"])
@pytest.mark.parametrize("self_loop", [False, True], ids=["pair", "loop"])
@pytest.mark.parametrize("fail_hash", [False, True], ids=["delete", "hash-error"])
def test_keydict_registry_hash_error_does_not_remove_native_edge(
    graph_class, key_type, self_loop, fail_hash
):
    """A failed dict deletion must not commit a Rust-only edge removal."""
    class EdgeKey(key_type):
        fail = False

        def __hash__(self):
            if self.fail:
                raise RuntimeError("edge-key hash failed")
            return super().__hash__()

    observations = []
    for lib in (nx, fnx):
        graph = getattr(lib, graph_class)()
        target = 0 if self_loop else 1
        key = EdgeKey("controlled" if key_type is str else 7)
        graph.add_edge(0, target, key=0, weight=2)
        graph.add_edge(0, target, key=key, weight=3)
        exported = lib.to_dict_of_dicts(graph)
        held = exported[0][target]

        def state():
            return (
                graph.number_of_edges(), graph.number_of_edges(0, target),
                list(graph.edges(keys=True, data=True)), list(graph.degree()),
                list(graph.degree(weight="weight")), list(held.items()),
                graph.has_edge(0, target, key),
                graph.get_edge_data(0, target) is held, json.dumps(exported),
            )

        trace = [state()]
        key.fail = fail_hash
        try:
            del held[key]
        except RuntimeError as error:
            result = (type(error).__name__, str(error))
        else:
            result = ("deleted", None)
        finally:
            key.fail = False
        trace.extend([result, state()])
        if fail_hash:
            assert result == ("RuntimeError", "edge-key hash failed")
        else:
            assert result == ("deleted", None)
        observations.append(trace)
    assert observations[1] == observations[0]


@pytest.mark.parametrize("graph_class", ["MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("keys,absent", [
    ([7, 2], 99),
    (["first", "second"], "absent"),
    ([("edge", 7), ("edge", 2)], ("absent", 99)),
])
def test_keydict_registry_missing_bulk_key_keeps_parallel_edges(graph_class, keys, absent):
    """An explicit missing key cannot fall back to removing the last key."""
    observations = []
    for lib in (nx, fnx):
        graph = getattr(lib, graph_class)()
        for index, key in enumerate(keys):
            graph.add_edge(0, 1, key=key, weight=index + 1)
        held = graph.get_edge_data(0, 1)

        def state():
            return (list(graph.edges(keys=True, data=True)), list(held.items()),
                    graph.number_of_edges(), graph.get_edge_data(0, 1) is held)

        trace = [state()]
        trace.append(graph.remove_edges_from([(0, 1, absent)]))
        trace.append(state())
        # The valid prefix is removed, but the following missing key must not
        # remove the remaining parallel edge or detach its held dictionary.
        trace.append(graph.remove_edges_from([(0, 1, keys[0]), (0, 1, absent)]))
        trace.append(state())
        trace.append(graph.remove_edges_from([(0, 1, keys[1])]))
        trace.append(state())
        held["detached"] = {"weight": 9}
        trace.append(state())
        graph.add_edge(0, 1, key="new-generation", weight=10)
        trace.append(state())
        observations.append(trace)
    assert observations[1] == observations[0]


@pytest.mark.parametrize("graph_class", ["MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("labels", [[0, 1, 2, 3], ["", "v", "before", "after"],
                                    ["u-long-label", "v-long-label", "before-long", "after-long"]])
@pytest.mark.parametrize("self_loop", [False, True], ids=["pair", "loop"])
@pytest.mark.parametrize("mutation", ["pop", "popitem", "clear", "del"])
@pytest.mark.parametrize("cleanup", ["clear_edges", "clear", "remove_node", "remove_nodes_from"])
def test_keydict_registry_empty_pair_consumers_match_networkx(
    graph_class, labels, self_loop, mutation, cleanup
):
    """5cqna: native and Python consumers must agree on empty adjacency.

    Warm positional lookasides and real neighbor iterators before the deletion;
    preserving only membership or appending a ghost at export time is insufficient.
    Clear every keydict before cleanup so edge_count == 0 cannot hide ghost rows.
    """
    observations = []
    for lib in (nx, fnx):
        u, other, before, after = labels
        v = u if self_loop else other
        graph = getattr(lib, graph_class)()
        graph.add_nodes_from(labels)
        graph.add_edge(u, before, key="before", weight=3)
        graph.add_edge(u, v, key="first", weight=1)
        graph.add_edge(u, v, key="second", weight=2)
        graph.add_edge(u, after, key="after", weight=4)
        graph.add_edge(before, v, key="incoming", weight=5)
        exported = lib.to_dict_of_dicts(graph)
        held = exported[u][v]
        graph.has_edge(u, v)
        graph.has_edge(u, v, "first")
        graph.number_of_edges(u, v)
        neighbor_iterator = graph.neighbors(u)
        predecessor_iterator = graph.predecessors(v) if graph.is_directed() else graph.neighbors(v)
        if mutation == "clear":
            held.clear()
        else:
            while held:
                if mutation == "pop":
                    held.pop(next(iter(held)))
                elif mutation == "popitem":
                    held.popitem()
                else:
                    del held[next(iter(held))]

        def outcome(call):
            try:
                return ("value", call())
            except Exception as error:
                return ("error", type(error).__name__, str(error))

        def state():
            return (
                list(graph), [(n, list(row)) for n, row in graph.adjacency()],
                list(graph.edges(keys=True, data=True)),
                graph.has_edge(u, v), graph.has_edge(u, v, "first"),
                graph.number_of_edges(), graph.number_of_edges(u, v),
                list(graph.degree()), list(graph.degree(weight="weight")),
                graph.get_edge_data(u, v) is held, list(held.items()),
                json.dumps(exported), json.dumps(lib.to_dict_of_dicts(graph)),
                outcome(lambda: list(lib.bfs_edges(graph, u))),
                outcome(lambda: lib.shortest_path(graph, u, v)),
            )

        trace = [state(), outcome(lambda: list(neighbor_iterator)),
                 outcome(lambda: list(predecessor_iterator))]
        trace.append(outcome(lambda: graph.remove_edge(u, v)))
        trace.append(outcome(lambda: graph.remove_edges_from([(u, v), (u, v, "absent")])))
        trace.append(state())
        graph.add_edge(u, v, key="replacement", weight=6)
        assert graph.get_edge_data(u, v) is held
        trace.append(state())
        # Clear all pair dictionaries, including the recreated singleton and
        # self-loop, without changing node or neighbor insertion order.
        for row in lib.to_dict_of_dicts(graph).values():
            for keydict in row.values():
                keydict.clear()
        assert graph.number_of_edges() == 0
        trace.append(state())
        if cleanup == "remove_nodes_from":
            graph.remove_nodes_from([u])
        elif cleanup == "remove_node":
            graph.remove_node(u)
        else:
            getattr(graph, cleanup)()
        trace.append(state())
        held["after-cleanup"] = {"weight": 7}
        trace.append(state())
        graph.add_edge(u, v, key="new-generation", weight=8)
        assert graph.get_edge_data(u, v) is not held
        trace.append(state())
        observations.append(trace)
    assert observations[1] == observations[0]


@pytest.mark.parametrize("graph_class", ["MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("hub_index", range(3))
@pytest.mark.parametrize("self_loop", [False, True], ids=["pair", "loop"])
@pytest.mark.parametrize("export_first", [False, True], ids=["get", "export"])
@pytest.mark.parametrize("remove_through", ["graph", "dict-pop", "dict-clear"])
def test_keydict_registry_ghost_and_pair_recreation_matches_networkx(
    graph_class, hub_index, self_loop, export_first, remove_through
):
    """49u7h: graph-side last-edge removal and dict-side ghosts differ.

    A ghost must reuse its held keydict until the endpoint is removed. A pair
    emptied through the graph must instead get a new keydict immediately.
    """
    observations = []
    for lib in (nx, fnx):
        labels = ["a-long-node-label", "m-long-node-label", "z-long-node-label"]
        u = labels[hub_index]
        v = u if self_loop else labels[(hub_index + 1) % 3]
        graph = getattr(lib, graph_class)()
        graph.add_nodes_from(labels)
        graph.add_edge(u, v, key="first", weight=1)
        graph.add_edge(u, v, key="second", weight=2)
        graph.add_edge(labels[(hub_index + 2) % 3], "outside", key="unrelated", weight=3)
        exported = lib.to_dict_of_dicts(graph) if export_first else None
        held = exported[u][v] if export_first else graph.get_edge_data(u, v)
        if remove_through == "graph":
            graph.remove_edge(u, v, "first")
            graph.remove_edge(u, v, "second")
        elif remove_through == "dict-pop":
            held.pop("first")
            held.pop("second")
        else:
            held.clear()
        assert held == {}

        def state():
            return (
                list(graph), list(graph.edges(keys=True, data=True)),
                graph.has_edge(u, v), graph.number_of_edges(u, v),
                graph.get_edge_data(u, v) is held, list(held.items()),
                None if exported is None else json.dumps(exported),
                json.dumps(lib.to_dict_of_dicts(graph)),
            )

        trace = [state()]
        graph.add_edge(u, v, key="replacement", weight=4)
        assert (graph.get_edge_data(u, v) is held) == (remove_through != "graph")
        trace.append(state())
        graph.remove_node(u)
        trace.append(state())
        held["detached-write"] = {"weight": 5}
        trace.append(state())
        graph.add_edge(u, v, key="after-node-removal", weight=6)
        assert graph.get_edge_data(u, v) is not held
        trace.append(state())
        observations.append(trace)
    assert observations[1] == observations[0]
