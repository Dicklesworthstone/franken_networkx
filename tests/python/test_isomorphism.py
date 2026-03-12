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
