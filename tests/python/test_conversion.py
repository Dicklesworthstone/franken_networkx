"""Tests for conversion utilities: relabel_nodes, convert_node_labels_to_integers,
to/from_dict_of_dicts, to/from_dict_of_lists, to/from_edgelist,
to/from_numpy_array, to/from_scipy_sparse_array, to/from_pandas_edgelist."""

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
