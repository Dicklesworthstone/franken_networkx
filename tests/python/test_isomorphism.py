"""Tests for graph isomorphism: is_isomorphic, could_be_isomorphic,
fast_could_be_isomorphic."""

import pytest

import franken_networkx as fnx


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def k4():
    return fnx.complete_graph(4)


@pytest.fixture
def c4():
    return fnx.cycle_graph(4)


@pytest.fixture
def p4():
    return fnx.path_graph(4)


# ---------------------------------------------------------------------------
# is_isomorphic
# ---------------------------------------------------------------------------


class TestIsIsomorphic:
    def test_same_graph(self, k4):
        assert fnx.is_isomorphic(k4, k4)

    def test_identical_structure(self):
        G1 = fnx.Graph()
        G1.add_edge(0, 1)
        G1.add_edge(1, 2)
        G2 = fnx.Graph()
        G2.add_edge("a", "b")
        G2.add_edge("b", "c")
        assert fnx.is_isomorphic(G1, G2)

    def test_complete_not_iso_cycle(self, k4, c4):
        assert not fnx.is_isomorphic(k4, c4)

    def test_empty_graphs(self):
        G1 = fnx.Graph()
        G2 = fnx.Graph()
        assert fnx.is_isomorphic(G1, G2)

    def test_single_node(self):
        G1 = fnx.Graph()
        G1.add_node(0)
        G2 = fnx.Graph()
        G2.add_node("x")
        assert fnx.is_isomorphic(G1, G2)

    def test_different_sizes(self):
        G1 = fnx.complete_graph(3)
        G2 = fnx.complete_graph(4)
        assert not fnx.is_isomorphic(G1, G2)

    def test_same_nodes_different_edges(self):
        G1 = fnx.Graph()
        G1.add_edge(0, 1)
        G1.add_edge(1, 2)
        G2 = fnx.Graph()
        G2.add_edge(0, 1)
        G2.add_edge(0, 2)
        # Both are paths of 3 nodes, so they ARE isomorphic.
        assert fnx.is_isomorphic(G1, G2)

    def test_cycle_iso_relabeled_cycle(self):
        G1 = fnx.cycle_graph(5)
        G2 = fnx.Graph()
        G2.add_edge(10, 11)
        G2.add_edge(11, 12)
        G2.add_edge(12, 13)
        G2.add_edge(13, 14)
        G2.add_edge(14, 10)
        assert fnx.is_isomorphic(G1, G2)

    def test_path_not_iso_star(self):
        path = fnx.path_graph(4)
        star = fnx.star_graph(3)  # 4 nodes: hub + 3 leaves
        # Path: degree seq [1,2,2,1]; Star: degree seq [3,1,1,1]
        assert not fnx.is_isomorphic(path, star)

    def test_directed_relabeled_path_isomorphic(self):
        g1 = fnx.DiGraph()
        g1.add_edge(0, 1)
        g1.add_edge(1, 2)
        g2 = fnx.DiGraph()
        g2.add_edge("a", "b")
        g2.add_edge("b", "c")
        assert fnx.is_isomorphic(g1, g2)

    def test_directed_orientation_changes_non_isomorphic(self):
        g1 = fnx.DiGraph()
        g1.add_edge(0, 1)
        g1.add_edge(1, 2)
        g2 = fnx.DiGraph()
        g2.add_edge("a", "b")
        g2.add_edge("c", "b")
        assert not fnx.is_isomorphic(g1, g2)

    def test_mixed_graph_types_raise(self):
        graph = fnx.Graph()
        graph.add_edge(0, 1)
        digraph = fnx.DiGraph()
        digraph.add_edge(0, 1)
        with pytest.raises(fnx.NetworkXError, match="not of the same type"):
            fnx.is_isomorphic(graph, digraph)

    def test_graph_and_single_edge_multigraph_are_isomorphic(self):
        graph = fnx.Graph()
        graph.add_edge(0, 1)
        multigraph = fnx.MultiGraph()
        multigraph.add_edge("a", "b", key=0)
        assert fnx.is_isomorphic(graph, multigraph)

    def test_graph_and_parallel_edge_multigraph_are_not_isomorphic(self):
        graph = fnx.Graph()
        graph.add_edge(0, 1)
        multigraph = fnx.MultiGraph()
        multigraph.add_edge("a", "b", key=0)
        multigraph.add_edge("a", "b", key=1)
        assert not fnx.is_isomorphic(graph, multigraph)


# ---------------------------------------------------------------------------
# could_be_isomorphic
# ---------------------------------------------------------------------------


class TestCouldBeIsomorphic:
    def test_true_for_isomorphic(self, k4):
        assert fnx.could_be_isomorphic(k4, k4)

    def test_false_for_different_degree_seq(self, k4, c4):
        # K4 all degree 3; C4 all degree 2.
        assert not fnx.could_be_isomorphic(k4, c4)

    def test_true_for_same_degree_seq(self):
        # Two different graphs with same degree sequence.
        G1 = fnx.Graph()
        G1.add_edge(0, 1)
        G1.add_edge(1, 2)
        G1.add_edge(2, 3)
        G2 = fnx.Graph()
        G2.add_edge(0, 1)
        G2.add_edge(2, 3)
        G2.add_edge(1, 2)
        assert fnx.could_be_isomorphic(G1, G2)

    def test_empty(self):
        assert fnx.could_be_isomorphic(fnx.Graph(), fnx.Graph())

    def test_directed_graphs_not_supported(self):
        g1 = fnx.DiGraph()
        g1.add_edge(0, 1)
        g2 = fnx.DiGraph()
        g2.add_edge("a", "b")
        with pytest.raises(fnx.NetworkXNotImplemented, match="directed type"):
            fnx.could_be_isomorphic(g1, g2)

    def test_graph_and_parallel_edge_multigraph_return_false(self):
        graph = fnx.Graph()
        graph.add_edge(0, 1)
        multigraph = fnx.MultiGraph()
        multigraph.add_edge("a", "b", key=0)
        multigraph.add_edge("a", "b", key=1)
        assert not fnx.could_be_isomorphic(graph, multigraph)

    def test_digraph_and_single_edge_multidigraph_raise_not_implemented(self):
        digraph = fnx.DiGraph()
        digraph.add_edge(0, 1)
        multidigraph = fnx.MultiDiGraph()
        multidigraph.add_edge("a", "b", key=0)
        with pytest.raises(fnx.NetworkXNotImplemented, match="directed type"):
            fnx.could_be_isomorphic(digraph, multidigraph)


# ---------------------------------------------------------------------------
# fast_could_be_isomorphic
# ---------------------------------------------------------------------------


class TestFastCouldBeIsomorphic:
    def test_true_for_isomorphic(self, k4):
        assert fnx.fast_could_be_isomorphic(k4, k4)

    def test_false_for_different_sizes(self):
        G1 = fnx.complete_graph(3)
        G2 = fnx.complete_graph(4)
        assert not fnx.fast_could_be_isomorphic(G1, G2)

    def test_false_for_different_edges(self):
        G1 = fnx.complete_graph(4)
        G2 = fnx.cycle_graph(4)
        assert not fnx.fast_could_be_isomorphic(G1, G2)

    def test_empty(self):
        assert fnx.fast_could_be_isomorphic(fnx.Graph(), fnx.Graph())

    def test_directed_graphs_not_supported(self):
        g1 = fnx.DiGraph()
        g1.add_edge(0, 1)
        g2 = fnx.DiGraph()
        g2.add_edge("a", "b")
        with pytest.raises(fnx.NetworkXNotImplemented, match="directed type"):
            fnx.fast_could_be_isomorphic(g1, g2)

    def test_graph_and_parallel_edge_multigraph_return_false(self):
        graph = fnx.Graph()
        graph.add_edge(0, 1)
        multigraph = fnx.MultiGraph()
        multigraph.add_edge("a", "b", key=0)
        multigraph.add_edge("a", "b", key=1)
        assert not fnx.fast_could_be_isomorphic(graph, multigraph)

    def test_digraph_and_single_edge_multidigraph_raise_not_implemented(self):
        digraph = fnx.DiGraph()
        digraph.add_edge(0, 1)
        multidigraph = fnx.MultiDiGraph()
        multidigraph.add_edge("a", "b", key=0)
        with pytest.raises(fnx.NetworkXNotImplemented, match="directed type"):
            fnx.fast_could_be_isomorphic(digraph, multidigraph)


class TestFasterCouldBeIsomorphic:
    def test_directed_graphs_use_total_degree_sequence(self):
        g1 = fnx.DiGraph()
        g1.add_edge(0, 1)
        g1.add_edge(1, 2)
        g2 = fnx.DiGraph()
        g2.add_edge("a", "b")
        g2.add_edge("b", "c")
        assert fnx.faster_could_be_isomorphic(g1, g2)

    def test_directed_total_degree_mismatch_returns_false(self):
        g1 = fnx.DiGraph()
        g1.add_edge(0, 1)
        g2 = fnx.DiGraph()
        g2.add_edge("a", "b")
        g2.add_edge("b", "a")
        assert not fnx.faster_could_be_isomorphic(g1, g2)

    def test_mixed_graph_and_digraph_can_match(self):
        graph = fnx.Graph()
        graph.add_edge(0, 1)
        digraph = fnx.DiGraph()
        digraph.add_edge("a", "b")
        assert fnx.faster_could_be_isomorphic(graph, digraph)

    def test_mixed_graph_and_reciprocal_digraph_do_not_match(self):
        graph = fnx.Graph()
        graph.add_edge(0, 1)
        digraph = fnx.DiGraph()
        digraph.add_edge("a", "b")
        digraph.add_edge("b", "a")
        assert not fnx.faster_could_be_isomorphic(graph, digraph)

    def test_graph_and_parallel_edge_multigraph_do_not_match(self):
        graph = fnx.Graph()
        graph.add_edge(0, 1)
        multigraph = fnx.MultiGraph()
        multigraph.add_edge("a", "b", key=0)
        multigraph.add_edge("a", "b", key=1)
        assert not fnx.faster_could_be_isomorphic(graph, multigraph)

    def test_digraph_and_single_edge_multidigraph_can_match(self):
        digraph = fnx.DiGraph()
        digraph.add_edge(0, 1)
        multidigraph = fnx.MultiDiGraph()
        multidigraph.add_edge("a", "b", key=0)
        assert fnx.faster_could_be_isomorphic(digraph, multidigraph)
