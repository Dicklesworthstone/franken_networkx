"""Tests for approximation algorithms: min_weighted_vertex_cover,
maximum_independent_set, max_clique, clique_removal, large_clique_size."""

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
def star5():
    """Star with hub 0 and leaves 1..4."""
    G = fnx.Graph()
    for i in range(1, 5):
        G.add_edge(0, i)
    return G


@pytest.fixture
def path4():
    G = fnx.Graph()
    G.add_edge(0, 1)
    G.add_edge(1, 2)
    G.add_edge(2, 3)
    return G


@pytest.fixture
def petersen():
    """Petersen graph — 10 nodes, 15 edges, 3-regular."""
    G = fnx.Graph()
    # Outer cycle
    for i in range(5):
        G.add_edge(i, (i + 1) % 5)
    # Inner star
    for i in range(5):
        G.add_edge(i + 5, ((i + 2) % 5) + 5)
    # Spokes
    for i in range(5):
        G.add_edge(i, i + 5)
    return G


# ---------------------------------------------------------------------------
# min_weighted_vertex_cover
# ---------------------------------------------------------------------------


class TestMinWeightedVertexCover:
    def test_covers_all_edges(self, triangle):
        cover = fnx.min_weighted_vertex_cover(triangle)
        assert isinstance(cover, set)
        # Every edge must have at least one endpoint in the cover.
        for u, v in [(0, 1), (1, 2), (0, 2)]:
            assert u in cover or v in cover

    def test_complete_graph(self):
        G = fnx.complete_graph(5)
        cover = fnx.min_weighted_vertex_cover(G)
        for u in range(5):
            for v in range(u + 1, 5):
                assert u in cover or v in cover

    def test_star(self, star5):
        cover = fnx.min_weighted_vertex_cover(star5)
        # Hub must be in cover (connects to every leaf).
        # The 2-approx may include the hub + some leaves.
        for i in range(1, 5):
            assert 0 in cover or i in cover

    def test_single_edge(self):
        G = fnx.Graph()
        G.add_edge(0, 1)
        cover = fnx.min_weighted_vertex_cover(G)
        assert 0 in cover or 1 in cover

    def test_empty_graph(self):
        G = fnx.Graph()
        G.add_node(0)
        cover = fnx.min_weighted_vertex_cover(G)
        assert len(cover) == 0

    def test_path(self, path4):
        cover = fnx.min_weighted_vertex_cover(path4)
        for u, v in [(0, 1), (1, 2), (2, 3)]:
            assert u in cover or v in cover


# ---------------------------------------------------------------------------
# maximum_independent_set
# ---------------------------------------------------------------------------


class TestMaximumIndependentSet:
    def test_is_independent(self, triangle):
        iset = fnx.maximum_independent_set(triangle)
        assert isinstance(iset, set)
        iset_list = list(iset)
        # No two nodes in the set should be adjacent.
        for i in range(len(iset_list)):
            for j in range(i + 1, len(iset_list)):
                assert not triangle.has_edge(iset_list[i], iset_list[j])

    def test_triangle(self, triangle):
        iset = fnx.maximum_independent_set(triangle)
        # Triangle: max independent set size is 1.
        assert len(iset) >= 1

    def test_path(self, path4):
        iset = fnx.maximum_independent_set(path4)
        # Path 0-1-2-3: optimal independent set has size 2 (e.g., {0,2} or {1,3}).
        assert len(iset) >= 2
        iset_list = list(iset)
        for i in range(len(iset_list)):
            for j in range(i + 1, len(iset_list)):
                assert not path4.has_edge(iset_list[i], iset_list[j])

    def test_star(self, star5):
        iset = fnx.maximum_independent_set(star5)
        # All 4 leaves are independent, so MIS >= 4.
        assert len(iset) >= 4
        iset_list = list(iset)
        for i in range(len(iset_list)):
            for j in range(i + 1, len(iset_list)):
                assert not star5.has_edge(iset_list[i], iset_list[j])

    def test_empty(self):
        G = fnx.Graph()
        assert len(fnx.maximum_independent_set(G)) == 0

    def test_complete_graph(self):
        G = fnx.complete_graph(5)
        iset = fnx.maximum_independent_set(G)
        # In a complete graph, MIS = 1.
        assert len(iset) == 1


# ---------------------------------------------------------------------------
# max_clique
# ---------------------------------------------------------------------------


class TestMaxClique:
    def test_complete_graph(self):
        G = fnx.complete_graph(5)
        clique = fnx.max_clique(G)
        assert isinstance(clique, set)
        assert len(clique) == 5

    def test_is_clique(self, petersen):
        clique = fnx.max_clique(petersen)
        clique_list = list(clique)
        for i in range(len(clique_list)):
            for j in range(i + 1, len(clique_list)):
                assert petersen.has_edge(clique_list[i], clique_list[j])

    def test_triangle(self, triangle):
        clique = fnx.max_clique(triangle)
        # Triangle is itself a clique of size 3.
        assert len(clique) == 3

    def test_star(self, star5):
        clique = fnx.max_clique(star5)
        # Star: max clique = {hub, one leaf} = size 2.
        assert len(clique) == 2
        assert 0 in clique  # hub must be in the clique

    def test_empty(self):
        G = fnx.Graph()
        assert len(fnx.max_clique(G)) == 0

    def test_single_node(self):
        G = fnx.Graph()
        G.add_node(42)
        clique = fnx.max_clique(G)
        assert len(clique) == 1
        assert 42 in clique


# ---------------------------------------------------------------------------
# clique_removal
# ---------------------------------------------------------------------------


class TestCliqueRemoval:
    def test_returns_tuple(self, triangle):
        result = fnx.clique_removal(triangle)
        assert isinstance(result, tuple)
        assert len(result) == 2
        iset, cliques = result
        assert isinstance(iset, set)
        assert isinstance(cliques, list)

    def test_independent_set_valid(self, petersen):
        iset, _ = fnx.clique_removal(petersen)
        iset_list = list(iset)
        for i in range(len(iset_list)):
            for j in range(i + 1, len(iset_list)):
                assert not petersen.has_edge(iset_list[i], iset_list[j])

    def test_cliques_valid(self, petersen):
        _, cliques = fnx.clique_removal(petersen)
        for clique in cliques:
            clique_list = list(clique)
            for i in range(len(clique_list)):
                for j in range(i + 1, len(clique_list)):
                    assert petersen.has_edge(clique_list[i], clique_list[j])

    def test_cliques_cover_all_nodes(self, petersen):
        _, cliques = fnx.clique_removal(petersen)
        all_nodes = set()
        for clique in cliques:
            all_nodes.update(clique)
        assert all_nodes == set(petersen.nodes())

    def test_empty(self):
        G = fnx.Graph()
        iset, cliques = fnx.clique_removal(G)
        assert len(iset) == 0
        assert len(cliques) == 0


# ---------------------------------------------------------------------------
# large_clique_size
# ---------------------------------------------------------------------------


class TestLargeCliqueSize:
    def test_complete_graph(self):
        assert fnx.large_clique_size(fnx.complete_graph(5)) == 5

    def test_triangle(self, triangle):
        assert fnx.large_clique_size(triangle) == 3

    def test_star(self, star5):
        assert fnx.large_clique_size(star5) == 2

    def test_empty(self):
        G = fnx.Graph()
        assert fnx.large_clique_size(G) == 0

    def test_path(self, path4):
        # Path: max clique size is 2 (any edge).
        assert fnx.large_clique_size(path4) == 2
