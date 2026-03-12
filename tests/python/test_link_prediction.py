"""Tests for link prediction functions."""

import pytest

import franken_networkx as fnx


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def triangle_plus():
    """Triangle (0-1-2-0) with pendant node 3 on node 0."""
    G = fnx.Graph()
    G.add_edge(0, 1)
    G.add_edge(1, 2)
    G.add_edge(2, 0)
    G.add_edge(0, 3)
    return G


@pytest.fixture
def star5():
    """Star graph with center 0 and leaves 1-4."""
    G = fnx.Graph()
    for i in range(1, 5):
        G.add_edge(0, i)
    return G


# ---------------------------------------------------------------------------
# common_neighbors
# ---------------------------------------------------------------------------


class TestCommonNeighbors:
    def test_basic(self, triangle_plus):
        cn = list(fnx.common_neighbors(triangle_plus, 1, 2))
        assert set(cn) == {0}

    def test_shared_via_center(self, triangle_plus):
        # Nodes 1 and 3 share neighbor 0
        cn = list(fnx.common_neighbors(triangle_plus, 1, 3))
        assert set(cn) == {0}

    def test_star_leaves(self, star5):
        cn = list(fnx.common_neighbors(star5, 1, 2))
        assert set(cn) == {0}

    def test_adjacent_nodes(self, triangle_plus):
        # Nodes 0 and 1 share neighbor 2
        cn = list(fnx.common_neighbors(triangle_plus, 0, 1))
        assert 2 in cn


# ---------------------------------------------------------------------------
# jaccard_coefficient
# ---------------------------------------------------------------------------


class TestJaccardCoefficient:
    def test_basic(self, triangle_plus):
        result = list(fnx.jaccard_coefficient(triangle_plus, [(1, 2)]))
        assert len(result) == 1
        u, v, p = result[0]
        assert u == 1 and v == 2
        # common = {0}, union = {0,2} | {0,1} = {0,1,2} => 1/3
        assert abs(p - 1.0 / 3.0) < 1e-9

    def test_no_common_neighbors(self, star5):
        # Leaves 1,2 share only center 0; |union| = {0} (they have 1 neighbor each)
        result = list(fnx.jaccard_coefficient(star5, [(1, 2)]))
        u, v, p = result[0]
        # common = {0}, union = {0} => 1/1 = 1.0 (both leaves only have center)
        assert abs(p - 1.0) < 1e-9

    def test_all_pairs(self, triangle_plus):
        # When ebunch=None, should return predictions for all non-edge pairs
        result = list(fnx.jaccard_coefficient(triangle_plus))
        assert len(result) > 0
        for u, v, p in result:
            assert 0.0 <= p <= 1.0


# ---------------------------------------------------------------------------
# adamic_adar_index
# ---------------------------------------------------------------------------


class TestAdamicAdarIndex:
    def test_basic(self, triangle_plus):
        result = list(fnx.adamic_adar_index(triangle_plus, [(1, 2)]))
        assert len(result) == 1
        u, v, p = result[0]
        assert u == 1 and v == 2
        # Common neighbor is 0 with degree 3 => 1/log(3)
        import math
        assert abs(p - 1.0 / math.log(3)) < 1e-9

    def test_all_pairs(self, triangle_plus):
        result = list(fnx.adamic_adar_index(triangle_plus))
        assert len(result) > 0
        for u, v, p in result:
            assert p >= 0.0


# ---------------------------------------------------------------------------
# preferential_attachment
# ---------------------------------------------------------------------------


class TestPreferentialAttachment:
    def test_basic(self, triangle_plus):
        result = list(fnx.preferential_attachment(triangle_plus, [(1, 2)]))
        assert len(result) == 1
        u, v, p = result[0]
        assert u == 1 and v == 2
        # deg(1)=2, deg(2)=2 => 2*2 = 4
        assert abs(p - 4.0) < 1e-9

    def test_star_leaves(self, star5):
        result = list(fnx.preferential_attachment(star5, [(1, 2)]))
        u, v, p = result[0]
        # deg(1)=1, deg(2)=1 => 1*1 = 1
        assert abs(p - 1.0) < 1e-9

    def test_all_pairs(self, triangle_plus):
        result = list(fnx.preferential_attachment(triangle_plus))
        assert len(result) > 0
        for u, v, p in result:
            assert p >= 0.0


# ---------------------------------------------------------------------------
# resource_allocation_index
# ---------------------------------------------------------------------------


class TestResourceAllocationIndex:
    def test_basic(self, triangle_plus):
        result = list(fnx.resource_allocation_index(triangle_plus, [(1, 2)]))
        assert len(result) == 1
        u, v, p = result[0]
        assert u == 1 and v == 2
        # Common neighbor is 0 with degree 3 => 1/3
        assert abs(p - 1.0 / 3.0) < 1e-9

    def test_all_pairs(self, triangle_plus):
        result = list(fnx.resource_allocation_index(triangle_plus))
        assert len(result) > 0
        for u, v, p in result:
            assert p >= 0.0
