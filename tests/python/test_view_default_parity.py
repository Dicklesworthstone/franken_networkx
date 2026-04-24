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
