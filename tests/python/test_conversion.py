"""Tests for conversion utilities: relabel_nodes, convert_node_labels_to_integers,
to/from_dict_of_dicts, to/from_dict_of_lists, to/from_edgelist,
to/from_numpy_array, to/from_scipy_sparse_array, to/from_pandas_edgelist."""

from collections.abc import Mapping

import networkx as nx
import pytest

import franken_networkx as fnx


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
        el = fnx.to_edgelist(G)
        assert len(el) == 2
        # Each element is (u, v, data_dict)
        assert len(el[0]) == 3

        H = fnx.from_edgelist([(u, v) for u, v, _ in el])
        assert H.number_of_edges() == 2

    def test_nodelist_filter(self):
        G = fnx.Graph()
        G.add_edge(0, 1)
        G.add_edge(1, 2)
        el = fnx.to_edgelist(G, nodelist=[0, 1])
        assert len(el) == 1

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
