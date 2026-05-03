"""Tests for I/O functions: read/write_edgelist, read/write_adjlist,
read/write_graphml, node_link_data/graph."""

import io
import os
import tempfile

import pytest

import franken_networkx as fnx


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def triangle():
    G = fnx.Graph()
    G.add_edge(0, 1)
    G.add_edge(1, 2)
    G.add_edge(0, 2)
    return G


@pytest.fixture
def weighted_graph():
    G = fnx.Graph()
    G.add_edge(0, 1, weight=1.5)
    G.add_edge(1, 2, weight=2.5)
    return G


@pytest.fixture
def small_digraph():
    D = fnx.DiGraph()
    D.add_edge(0, 1)
    D.add_edge(1, 2)
    return D


# ---------------------------------------------------------------------------
# node_link_data / node_link_graph
# ---------------------------------------------------------------------------


class TestNodeLinkFormat:
    def test_round_trip(self, triangle):
        data = fnx.node_link_data(triangle)
        assert "nodes" in data
        assert "edges" in data
        assert len(data["nodes"]) == 3
        assert len(data["edges"]) == 3

        H = fnx.node_link_graph(data)
        assert H.number_of_nodes() == 3
        assert H.number_of_edges() == 3

    def test_with_attrs(self, weighted_graph):
        data = fnx.node_link_data(weighted_graph)
        H = fnx.node_link_graph(data)
        assert H.number_of_edges() == 2

    def test_digraph_round_trip(self, small_digraph):
        data = fnx.node_link_data(small_digraph)
        assert "nodes" in data
        assert "edges" in data
        H = fnx.node_link_graph(data)
        assert H.number_of_nodes() == 3
        assert H.number_of_edges() == 2


# ---------------------------------------------------------------------------
# read/write_edgelist
# ---------------------------------------------------------------------------


class TestEdgelistIO:
    def test_round_trip(self, triangle):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".edgelist", delete=False
        ) as f:
            path = f.name

        try:
            fnx.write_edgelist(triangle, path)
            H = fnx.read_edgelist(path)
            assert H.number_of_edges() == 3
        finally:
            os.unlink(path)

    def test_digraph(self, small_digraph):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".edgelist", delete=False
        ) as f:
            path = f.name

        try:
            fnx.write_edgelist(small_digraph, path)
            assert os.path.exists(path)
            assert os.path.getsize(path) > 0
        finally:
            os.unlink(path)

    def test_binary_file_like_round_trip(self, triangle):
        buffer = io.BytesIO()
        fnx.write_edgelist(triangle, buffer)
        buffer.seek(0)
        H = fnx.read_edgelist(buffer)
        assert H.number_of_nodes() == 3
        assert H.number_of_edges() == 3


# ---------------------------------------------------------------------------
# read/write_adjlist
# ---------------------------------------------------------------------------


class TestAdjlistIO:
    def test_round_trip(self, triangle):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".adjlist", delete=False
        ) as f:
            path = f.name

        try:
            fnx.write_adjlist(triangle, path)
            H = fnx.read_adjlist(path)
            assert H.number_of_nodes() == 3
        finally:
            os.unlink(path)

    def test_digraph_round_trip(self, small_digraph):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".adjlist", delete=False
        ) as f:
            path = f.name

        try:
            fnx.write_adjlist(small_digraph, path)
            H = fnx.read_adjlist(path)
            # adjlist doesn't preserve direction; result is undirected Graph
            assert H.number_of_nodes() == 3
        finally:
            os.unlink(path)

    def test_large_graph(self):
        G = fnx.path_graph(100)
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".adjlist", delete=False
        ) as f:
            path = f.name

        try:
            fnx.write_adjlist(G, path)
            H = fnx.read_adjlist(path)
            assert H.number_of_nodes() == 100
        finally:
            os.unlink(path)

    def test_binary_file_like_round_trip(self, triangle):
        buffer = io.BytesIO()
        fnx.write_adjlist(triangle, buffer)
        buffer.seek(0)
        H = fnx.read_adjlist(buffer)
        assert H.number_of_nodes() == 3
        assert H.number_of_edges() == 3

    def test_write_adjlist_default_uses_rust_fast_path(self, monkeypatch, triangle):
        def fail_delegate(*args, **kwargs):
            raise AssertionError("default write_adjlist should use Rust fast path")

        monkeypatch.setattr(fnx, "_write_adjlist_via_nx", fail_delegate)
        buffer = io.BytesIO()
        fnx.write_adjlist(triangle, buffer)
        buffer.seek(0)
        H = fnx.read_adjlist(buffer)
        assert H.number_of_nodes() == 3
        assert H.number_of_edges() == 3

    def test_write_adjlist_non_default_kwargs_stay_delegated(self, monkeypatch, triangle):
        observed = {}

        def fake_delegate(G, path, *, comments="#", delimiter=" ", encoding="utf-8"):
            observed.update(
                {
                    "graph": G,
                    "comments": comments,
                    "delimiter": delimiter,
                    "encoding": encoding,
                }
            )
            path.write(b"delegated\n")

        monkeypatch.setattr(fnx, "_write_adjlist_via_nx", fake_delegate)
        buffer = io.BytesIO()
        fnx.write_adjlist(triangle, buffer, delimiter="|")
        assert buffer.getvalue() == b"delegated\n"
        assert observed == {
            "graph": triangle,
            "comments": "#",
            "delimiter": "|",
            "encoding": "utf-8",
        }


# ---------------------------------------------------------------------------
# read/write_graphml
# ---------------------------------------------------------------------------


class TestGraphMLIO:
    def test_round_trip(self, triangle):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".graphml", delete=False
        ) as f:
            path = f.name

        try:
            fnx.write_graphml(triangle, path)
            H = fnx.read_graphml(path)
            assert H.number_of_nodes() == 3
            assert H.number_of_edges() == 3
        finally:
            os.unlink(path)

    def test_weighted(self, weighted_graph):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".graphml", delete=False
        ) as f:
            path = f.name

        try:
            fnx.write_graphml(weighted_graph, path)
            H = fnx.read_graphml(path)
            assert H.number_of_edges() == 2
            # Weights are preserved as strings in GraphML by default in our implementation
            w1 = H["0"]["1"]["weight"]
            assert float(w1) == 1.5
        finally:
            os.unlink(path)

    def test_directed_graphml(self):
        D = fnx.DiGraph()
        D.add_edge("a", "b")
        D.add_edge("b", "a")
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".graphml", delete=False
        ) as f:
            path = f.name

        try:
            fnx.write_graphml(D, path)
            H = fnx.read_graphml(path)
            assert isinstance(H, fnx.DiGraph)
            assert H.has_edge("a", "b")
            assert H.has_edge("b", "a")
            assert H.number_of_nodes() == 2
            assert H.number_of_edges() == 2
        finally:
            os.unlink(path)

    def test_node_attrs_preserved(self):
        G = fnx.Graph()
        G.add_node("a", color="red")
        G.add_node("b", color="blue")
        G.add_edge("a", "b")
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".graphml", delete=False
        ) as f:
            path = f.name

        try:
            fnx.write_graphml(G, path)
            H = fnx.read_graphml(path)
            assert H.nodes["a"]["color"] == "red"
            assert H.nodes["b"]["color"] == "blue"
        finally:
            os.unlink(path)

    def test_edge_attrs_preserved(self):
        G = fnx.Graph()
        G.add_edge("a", "b", weight="1.0", label="edge1")
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".graphml", delete=False
        ) as f:
            path = f.name

        try:
            fnx.write_graphml(G, path)
            H = fnx.read_graphml(path)
            data = H.get_edge_data("a", "b")
            assert data["weight"] == "1.0"
            assert data["label"] == "edge1"
        finally:
            os.unlink(path)

    def test_binary_file_like_round_trip(self, triangle):
        buffer = io.BytesIO()
        fnx.write_graphml(triangle, buffer)
        buffer.seek(0)
        H = fnx.read_graphml(buffer)
        assert H.number_of_nodes() == 3
        assert H.number_of_edges() == 3


# ---------------------------------------------------------------------------
# Regression: write_edgelist / read_edgelist cross-compatibility with nx
# (franken_networkx-wredge, -rdedge)
# ---------------------------------------------------------------------------


class TestEdgelistNxCrossCompat:
    """The Rust-native write_edgelist emitted `u v -` for empty attrs and
    `u v key=val` for attr edges, neither of which round-tripped through
    networkx.read_edgelist. read_edgelist silently dropped most of the
    nx kwargs (nodetype, create_using, data, delimiter, ...). Both paths
    now go through Python wrappers that delegate the format to nx.
    """

    def test_empty_attr_round_trips_through_networkx(self):
        import networkx as nx

        G = fnx.Graph()
        G.add_edges_from([(0, 1), (1, 2)])
        buf = io.BytesIO()
        fnx.write_edgelist(G, buf)
        # Must be nx-readable: this used to raise
        # TypeError: Failed to convert edge data (['-']) to dictionary.
        nx_graph = nx.read_edgelist(io.BytesIO(buf.getvalue()))
        assert sorted(map(tuple, map(sorted, nx_graph.edges()))) == [("0", "1"), ("1", "2")]

    def test_attr_round_trips_as_python_dict_repr(self):
        import networkx as nx

        G = fnx.Graph()
        G.add_edge(0, 1, weight=2.5)
        buf = io.BytesIO()
        fnx.write_edgelist(G, buf)
        # Output uses Python-dict repr rather than the legacy `key=val`.
        assert b"{'weight': 2.5}" in buf.getvalue()
        nx_graph = nx.read_edgelist(io.BytesIO(buf.getvalue()))
        data = nx_graph.get_edge_data("0", "1")
        assert data == {"weight": 2.5}

    def test_read_edgelist_honours_nodetype_int(self):
        import networkx as nx

        G_nx = nx.Graph()
        G_nx.add_edges_from([(0, 1), (1, 2)])
        nx_bytes_buf = io.BytesIO()
        nx.write_edgelist(G_nx, nx_bytes_buf, data=False)

        G = fnx.read_edgelist(io.BytesIO(nx_bytes_buf.getvalue()), nodetype=int)
        assert sorted(G.nodes()) == [0, 1, 2]
        assert all(isinstance(n, int) for n in G.nodes())

    def test_read_edgelist_honours_create_using_digraph(self):
        import networkx as nx

        buf = io.BytesIO(b"0 1\n1 2\n")
        G = fnx.read_edgelist(buf, create_using=fnx.DiGraph)
        assert G.is_directed()
        assert sorted(G.edges()) == [("0", "1"), ("1", "2")]

    def test_read_edgelist_signature_matches_networkx_backend_surface(self):
        import inspect
        import networkx as nx

        assert str(inspect.signature(fnx.read_edgelist)) == str(
            inspect.signature(nx.read_edgelist)
        )

    @pytest.mark.parametrize("backend", [None, "networkx"])
    def test_read_edgelist_accepts_supported_backend_keyword(self, backend):
        G = fnx.read_edgelist(io.BytesIO(b"0 1\n"), backend=backend)
        assert sorted(G.edges()) == [("0", "1")]

    def test_read_edgelist_backend_error_wording_matches_networkx(self):
        import networkx as nx

        with pytest.raises(ImportError) as actual_backend:
            fnx.read_edgelist(io.BytesIO(b"0 1\n"), backend="missing")
        with pytest.raises(ImportError) as expected_backend:
            nx.read_edgelist(io.BytesIO(b"0 1\n"), backend="missing")
        assert str(actual_backend.value) == str(expected_backend.value)

        with pytest.raises(TypeError) as actual_literal:
            fnx.read_edgelist(io.BytesIO(b"0 1\n"), backend_kwargs={"x": 1})
        with pytest.raises(TypeError) as expected_literal:
            nx.read_edgelist(io.BytesIO(b"0 1\n"), backend_kwargs={"x": 1})
        assert str(actual_literal.value) == str(expected_literal.value)

        with pytest.raises(TypeError) as actual_unknown:
            fnx.read_edgelist(io.BytesIO(b"0 1\n"), bogus=1)
        with pytest.raises(TypeError) as expected_unknown:
            nx.read_edgelist(io.BytesIO(b"0 1\n"), bogus=1)
        assert str(actual_unknown.value) == str(expected_unknown.value)

    def test_read_adjlist_honours_nodetype(self):
        G = fnx.read_adjlist(io.BytesIO(b"0 1\n1 2\n"), nodetype=int)
        assert sorted(G.nodes()) == [0, 1, 2]
        assert all(isinstance(n, int) for n in G.nodes())

    def test_write_edgelist_data_false(self):
        G = fnx.Graph()
        G.add_edge(0, 1, weight=2.5)
        buf = io.BytesIO()
        fnx.write_edgelist(G, buf, data=False)
        assert buf.getvalue() == b"0 1\n"

    def test_write_edgelist_delimiter_override(self):
        G = fnx.Graph()
        G.add_edges_from([(0, 1), (1, 2)])
        buf = io.BytesIO()
        fnx.write_edgelist(G, buf, delimiter="|")
        text = buf.getvalue().decode()
        for line in text.splitlines():
            parts = line.split("|")
            assert len(parts) == 3
