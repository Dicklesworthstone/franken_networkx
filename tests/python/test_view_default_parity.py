"""Parity tests for view default parameter (bead kg11)."""
import franken_networkx as fnx
import networkx as nx
import pytest


class TestNodeViewDefault:
    def test_nodes_data_attr_with_default(self):
        G = fnx.Graph()
        G.add_node(0, color="red")
        G.add_node(1)
        G.add_node(2, color="blue")
        nG = nx.Graph()
        nG.add_node(0, color="red")
        nG.add_node(1)
        nG.add_node(2, color="blue")
        result = list(G.nodes(data="color", default="gray"))
        nresult = list(nG.nodes(data="color", default="gray"))
        assert result == nresult

    def test_nodes_data_attr_without_default(self):
        G = fnx.Graph()
        G.add_node(0, color="red")
        G.add_node(1)
        result = list(G.nodes(data="color"))
        assert result[0] == (0, "red")
        assert result[1][1] is None  # no default means None

    def test_digraph_nodes_default(self):
        D = fnx.DiGraph()
        D.add_node(0, tag="A")
        D.add_node(1)
        nD = nx.DiGraph()
        nD.add_node(0, tag="A")
        nD.add_node(1)
        assert list(D.nodes(data="tag", default="X")) == list(
            nD.nodes(data="tag", default="X")
        )


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [(fnx.Graph, nx.Graph), (fnx.DiGraph, nx.DiGraph)],
)
def test_nodes_iteration_detects_node_set_mutation(fnx_cls, nx_cls):
    graph = fnx_cls()
    expected = nx_cls()
    for candidate in (graph, expected):
        candidate.add_nodes_from(["a", "b"])

    fnx_iter = iter(graph.nodes())
    nx_iter = iter(expected.nodes())

    assert next(fnx_iter) == next(nx_iter) == "a"

    graph.add_node("c")
    expected.add_node("c")

    with pytest.raises(RuntimeError) as fnx_exc:
        next(fnx_iter)
    with pytest.raises(RuntimeError) as nx_exc:
        next(nx_iter)

    assert str(fnx_exc.value) == str(nx_exc.value)


class TestEdgeViewDefault:
    def test_edges_data_attr_with_default(self):
        G = fnx.Graph()
        G.add_edge(0, 1, weight=3.0)
        G.add_edge(1, 2)
        nG = nx.Graph()
        nG.add_edge(0, 1, weight=3.0)
        nG.add_edge(1, 2)
        result = list(G.edges(data="weight", default=1.0))
        nresult = list(nG.edges(data="weight", default=1.0))
        assert result == nresult

    def test_edges_data_attr_no_default(self):
        G = fnx.Graph()
        G.add_edge(0, 1, weight=3.0)
        G.add_edge(1, 2)
        nG = nx.Graph()
        nG.add_edge(0, 1, weight=3.0)
        nG.add_edge(1, 2)
        result = list(G.edges(data="weight"))
        nresult = list(nG.edges(data="weight"))
        assert result == nresult

    def test_edges_nbunch_with_default(self):
        G = fnx.Graph()
        G.add_edge(0, 1, weight=5.0)
        G.add_edge(1, 2)
        G.add_edge(2, 3, weight=2.0)
        result = list(G.edges(data="weight", nbunch=[1], default=0.0))
        # Should include edges from node 1 with weight default
        assert any(w == 0.0 for _, _, w in result)

    def test_digraph_edges_default(self):
        D = fnx.DiGraph()
        D.add_edge(0, 1, capacity=10)
        D.add_edge(1, 2)
        nD = nx.DiGraph()
        nD.add_edge(0, 1, capacity=10)
        nD.add_edge(1, 2)
        result = sorted(D.edges(data="capacity", default=0))
        nresult = sorted(nD.edges(data="capacity", default=0))
        assert result == nresult


# ---------------------------------------------------------------------------
# br-r37-c1-msf5j: G.edges() must return a LIVE view (matches nx) for all
# graph classes, not a frozen list snapshot. Subsequent edge mutations
# should be visible when the captured view is iterated again.
# ---------------------------------------------------------------------------


class TestEdgesCallReturnsLiveView:
    @pytest.mark.parametrize("cls_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
    def test_edges_view_reflects_subsequent_add_edge(self, cls_name):
        fnx_cls = getattr(fnx, cls_name)
        nx_cls = getattr(nx, cls_name)
        G = fnx_cls([(1, 2), (2, 3)])
        Gn = nx_cls([(1, 2), (2, 3)])

        fview = G.edges()
        nview = Gn.edges()

        # Before mutation: same content
        assert sorted(fview) == sorted(nview)

        # Mutate
        G.add_edge(3, 4)
        Gn.add_edge(3, 4)

        # The captured view must see the new edge in BOTH fnx and nx.
        fnx_after = sorted(fview)
        nx_after = sorted(nview)
        assert fnx_after == nx_after, (
            f"{cls_name}: live-view divergence — fnx={fnx_after} nx={nx_after}"
        )
        # Sanity: the new edge is visible.
        if cls_name in ("Graph", "DiGraph"):
            assert (3, 4) in fnx_after
        else:
            # Multi*: list contains 2-tuples (no key), so (3, 4) appears.
            assert (3, 4) in fnx_after

    @pytest.mark.parametrize("cls_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
    def test_edges_view_reflects_remove_edge(self, cls_name):
        fnx_cls = getattr(fnx, cls_name)
        nx_cls = getattr(nx, cls_name)
        G = fnx_cls([(1, 2), (2, 3), (3, 4)])
        Gn = nx_cls([(1, 2), (2, 3), (3, 4)])

        fview = G.edges()
        nview = Gn.edges()

        G.remove_edge(2, 3)
        Gn.remove_edge(2, 3)

        assert sorted(fview) == sorted(nview)
        # The removed edge is no longer visible in either fnx or nx.
        for v in fview:
            assert v[:2] != (2, 3)

    @pytest.mark.parametrize("cls_name", ["MultiGraph", "MultiDiGraph"])
    def test_multi_edges_call_yields_2tuples(self, cls_name):
        """G.edges() (no args) on a multigraph yields 2-tuples,
        matching nx's MultiEdgeDataView default. The MG.edges (no
        parens) view continues to yield 3-tuples (with keys)."""
        fnx_cls = getattr(fnx, cls_name)
        nx_cls = getattr(nx, cls_name)
        G = fnx_cls([(1, 2), (1, 2), (2, 3)])
        Gn = nx_cls([(1, 2), (1, 2), (2, 3)])

        # No-parens: yields 3-tuples
        assert list(G.edges) == list(Gn.edges)
        # With-parens: yields 2-tuples
        assert list(G.edges()) == list(Gn.edges())

    def test_digraph_edges_view_len_matches(self):
        G = fnx.DiGraph([(1, 2), (2, 3)])
        v = G.edges()
        assert len(v) == 2
        G.add_edge(3, 4)
        assert len(v) == 3

    def test_multidigraph_edges_view_contains(self):
        G = fnx.MultiDiGraph([(1, 2), (2, 3)])
        v = G.edges()
        assert (1, 2) in v
        assert (2, 1) not in v  # directed
        G.add_edge(2, 1)
        assert (2, 1) in v


# ---------------------------------------------------------------------------
# br-r37-c1-f8gi1: Multi*.nodes() must return a LIVE NodeView (matches nx),
# not a frozen list. Same class of defect as br-r37-c1-msf5j (edges()) but
# for the Multi* node side. Rust-side MultiGraphNodeView.__call__ /
# MultiDiGraphNodeView.__call__ returned list; the Python wrapper now
# returns ``self`` (the live NodeView) for default args.
# ---------------------------------------------------------------------------


class TestNodesCallReturnsLiveView:
    @pytest.mark.parametrize("cls_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
    def test_nodes_view_reflects_subsequent_add_node(self, cls_name):
        fnx_cls = getattr(fnx, cls_name)
        nx_cls = getattr(nx, cls_name)
        G = fnx_cls([(1, 2), (2, 3)])
        Gn = nx_cls([(1, 2), (2, 3)])

        fview = G.nodes()
        nview = Gn.nodes()

        G.add_node(99)
        Gn.add_node(99)

        fnx_after = list(fview)
        nx_after = list(nview)
        assert fnx_after == nx_after, (
            f"{cls_name}: nodes() live-view divergence — "
            f"fnx={fnx_after} nx={nx_after}"
        )
        assert 99 in fnx_after

    @pytest.mark.parametrize("cls_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
    def test_nodes_view_reflects_remove_node(self, cls_name):
        fnx_cls = getattr(fnx, cls_name)
        nx_cls = getattr(nx, cls_name)
        G = fnx_cls([(1, 2), (2, 3), (3, 4)])
        Gn = nx_cls([(1, 2), (2, 3), (3, 4)])

        fview = G.nodes()
        nview = Gn.nodes()

        G.remove_node(3)
        Gn.remove_node(3)

        assert list(fview) == list(nview)
        assert 3 not in fview

    @pytest.mark.parametrize("cls_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
    def test_nodes_view_len_updates_after_mutation(self, cls_name):
        G = getattr(fnx, cls_name)([(1, 2)])
        v = G.nodes()
        assert len(v) == 2
        G.add_node(3)
        assert len(v) == 3
        G.remove_node(2)
        assert len(v) == 2

    @pytest.mark.parametrize("cls_name", ["MultiGraph", "MultiDiGraph"])
    def test_multi_nodes_call_returns_live_view_type(self, cls_name):
        """The Rust-side return type for the multi node views was list
        pre-fix. After fix the call returns the live NodeView (same
        type as ``G.nodes`` without parens)."""
        G = getattr(fnx, cls_name)([(1, 2)])
        assert type(G.nodes()) is type(G.nodes), (
            f"{cls_name}.nodes() should return same type as G.nodes "
            f"(live view), got {type(G.nodes())} vs {type(G.nodes)}"
        )
