"""Tests for reciprocity, wiener_index, average_degree_connectivity,
rich_club_coefficient, and s_metric."""

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
def path4():
    G = fnx.Graph()
    G.add_edge(0, 1)
    G.add_edge(1, 2)
    G.add_edge(2, 3)
    return G


@pytest.fixture
def mutual_digraph():
    """DiGraph where all edges are reciprocated."""
    D = fnx.DiGraph()
    D.add_edge(0, 1)
    D.add_edge(1, 0)
    D.add_edge(1, 2)
    D.add_edge(2, 1)
    return D


@pytest.fixture
def one_way_digraph():
    """DiGraph with no reciprocated edges."""
    D = fnx.DiGraph()
    D.add_edge(0, 1)
    D.add_edge(1, 2)
    D.add_edge(2, 3)
    return D


# ---------------------------------------------------------------------------
# overall_reciprocity
# ---------------------------------------------------------------------------


class TestOverallReciprocity:
    def test_fully_reciprocal(self, mutual_digraph):
        r = fnx.overall_reciprocity(mutual_digraph)
        assert abs(r - 1.0) < 1e-9

    def test_no_reciprocity(self, one_way_digraph):
        r = fnx.overall_reciprocity(one_way_digraph)
        assert abs(r - 0.0) < 1e-9

    def test_partial_reciprocity(self):
        D = fnx.DiGraph()
        D.add_edge(0, 1)
        D.add_edge(1, 0)
        D.add_edge(1, 2)
        # 2 of 3 edges are reciprocated (0->1 and 1->0)
        r = fnx.overall_reciprocity(D)
        assert 0.0 < r < 1.0


# ---------------------------------------------------------------------------
# reciprocity
# ---------------------------------------------------------------------------


class TestReciprocity:
    def test_fully_reciprocal(self, mutual_digraph):
        r = fnx.reciprocity(mutual_digraph)
        # Should return a dict or float depending on implementation
        if isinstance(r, dict):
            for v in r.values():
                assert abs(v - 1.0) < 1e-9
        else:
            assert abs(r - 1.0) < 1e-9


# ---------------------------------------------------------------------------
# wiener_index
# ---------------------------------------------------------------------------


class TestWienerIndex:
    def test_triangle(self, triangle):
        # Triangle: all pairwise distances are 1, so W = 3 * 1 = 3
        w = fnx.wiener_index(triangle)
        assert abs(w - 3.0) < 1e-9

    def test_path4(self, path4):
        # Path 0-1-2-3: distances are 1+2+3+1+2+1 = 10
        w = fnx.wiener_index(path4)
        assert abs(w - 10.0) < 1e-9

    def test_single_node(self):
        G = fnx.Graph()
        G.add_node(0)
        w = fnx.wiener_index(G)
        assert abs(w - 0.0) < 1e-9


# ---------------------------------------------------------------------------
# average_degree_connectivity
# ---------------------------------------------------------------------------


class TestAverageDegreeConnectivity:
    def test_triangle(self, triangle):
        adc = fnx.average_degree_connectivity(triangle)
        # All nodes have degree 2, so adc[2] should be 2.0
        assert isinstance(adc, dict)
        assert 2 in adc
        assert abs(adc[2] - 2.0) < 1e-9

    def test_star(self):
        G = fnx.Graph()
        for i in range(1, 5):
            G.add_edge(0, i)
        adc = fnx.average_degree_connectivity(G)
        assert isinstance(adc, dict)
        # Leaves (degree 1) connect to hub (degree 4)
        assert 1 in adc
        assert abs(adc[1] - 4.0) < 1e-9


# ---------------------------------------------------------------------------
# rich_club_coefficient
# ---------------------------------------------------------------------------


class TestRichClubCoefficient:
    def test_complete_graph(self):
        G = fnx.complete_graph(5)
        rcc = fnx.rich_club_coefficient(G)
        assert isinstance(rcc, dict)
        # Rich club coefficients are between 0 and 1
        for k, v in rcc.items():
            assert 0.0 <= v <= 1.0 + 1e-9

    def test_returns_dict(self, triangle):
        rcc = fnx.rich_club_coefficient(triangle)
        assert isinstance(rcc, dict)


# ---------------------------------------------------------------------------
# s_metric
# ---------------------------------------------------------------------------


class TestSMetric:
    def test_triangle(self, triangle):
        s = fnx.s_metric(triangle)
        # s_metric = sum(d(u)*d(v)) for all edges
        # Triangle: all degrees are 2, so s = 3 * (2*2) = 12
        assert abs(s - 12.0) < 1e-9

    def test_star(self):
        G = fnx.Graph()
        for i in range(1, 5):
            G.add_edge(0, i)
        s = fnx.s_metric(G)
        # Hub degree 4, leaves degree 1
        # s = 4 * (4*1) = 16
        assert abs(s - 16.0) < 1e-9

    def test_single_edge(self):
        G = fnx.Graph()
        G.add_edge(0, 1)
        s = fnx.s_metric(G)
        # deg(0)=1, deg(1)=1 => s = 1*1 = 1
        assert abs(s - 1.0) < 1e-9
