"""Tests for approximation algorithms and related parity gaps."""

import pytest

import franken_networkx as fnx

try:
    import networkx as nx
    HAS_NX = True
except ImportError:
    HAS_NX = False

needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


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


def assert_valid_spanner(original, candidate, stretch, weight=None):
    assert set(original.nodes()) == set(candidate.nodes())
    for u, v in candidate.edges():
        assert original.has_edge(u, v)
        if weight is not None:
            assert candidate[u][v][weight] == original[u][v][weight]

    for u in original.nodes():
        for v in original.nodes():
            try:
                original_length = fnx.shortest_path_length(original, u, v, weight=weight)
            except Exception:
                continue
            candidate_length = fnx.shortest_path_length(candidate, u, v, weight=weight)
            assert candidate_length <= stretch * original_length + 1e-9


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
# maximal_independent_set
# ---------------------------------------------------------------------------


class TestMaximalIndependentSet:
    def test_seeded_empty_graph_matches_reference_order(self):
        G = fnx.empty_graph(5)
        assert fnx.maximal_independent_set(G, seed=1) == [1, 0, 3, 2, 4]

    def test_seeded_path_with_required_node(self):
        G = fnx.path_graph(5)
        assert fnx.maximal_independent_set(G, [1], seed=1) == [1, 3]

    def test_invalid_seed_nodes_raise(self, triangle):
        with pytest.raises(fnx.NetworkXUnfeasible):
            fnx.maximal_independent_set(triangle, [0, 1])

    def test_single_self_loop_raises(self):
        G = fnx.Graph()
        G.add_edge("a", "a")
        with pytest.raises(fnx.NetworkXUnfeasible):
            fnx.maximal_independent_set(G)

    def test_directed_not_implemented(self):
        G = fnx.DiGraph()
        G.add_edge(0, 1)
        with pytest.raises(fnx.NetworkXNotImplemented):
            fnx.maximal_independent_set(G)


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


# ---------------------------------------------------------------------------
# chordal_graph_treewidth
# ---------------------------------------------------------------------------


class TestChordalGraphTreewidth:
    def test_trees_have_treewidth_one(self):
        assert fnx.chordal_graph_treewidth(fnx.path_graph(5)) == 1
        assert fnx.chordal_graph_treewidth(fnx.star_graph(6)) == 1

    def test_largest_clique_drives_treewidth(self):
        G = fnx.star_graph(10)
        for left in "abcde":
            G.add_node(left)
        clique = list("abcde")
        for i, left in enumerate(clique):
            for right in clique[i + 1 :]:
                G.add_edge(left, right)
        G.add_edge(5, "a")
        assert fnx.chordal_graph_treewidth(G) == 4

    def test_non_chordal_graph_raises(self):
        with pytest.raises(fnx.NetworkXError):
            fnx.chordal_graph_treewidth(fnx.cycle_graph(5))

    def test_empty_graph_matches_current_networkx_contract(self):
        assert fnx.chordal_graph_treewidth(fnx.Graph()) == -2


@needs_nx
class TestChordalGraphTreewidthParity:
    @pytest.mark.parametrize(
        "graph_builder",
        [
            lambda mod: mod.Graph(),
            lambda mod: mod.path_graph(5),
            lambda mod: mod.barbell_graph(4, 6),
        ],
    )
    def test_matches_networkx_without_fallback(self, monkeypatch, graph_builder):
        graph = graph_builder(fnx)
        expected = graph_builder(nx)

        expected_value = nx.chordal_graph_treewidth(expected)

        monkeypatch.setattr(
            nx,
            "chordal_graph_treewidth",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError(
                    "NetworkX chordal_graph_treewidth fallback should not be used"
                )
            ),
        )

        assert fnx.chordal_graph_treewidth(graph) == expected_value

    @pytest.mark.parametrize(
        ("fnx_builder", "nx_builder"),
        [
            (lambda: fnx.cycle_graph(5), lambda: nx.cycle_graph(5)),
            (lambda: fnx.DiGraph([(0, 1)]), lambda: nx.DiGraph([(0, 1)])),
            (lambda: fnx.MultiGraph([(0, 1)]), lambda: nx.MultiGraph([(0, 1)])),
            (lambda: fnx.MultiDiGraph([(0, 1)]), lambda: nx.MultiDiGraph([(0, 1)])),
        ],
    )
    def test_error_contract_matches_networkx_without_fallback(
        self, monkeypatch, fnx_builder, nx_builder
    ):
        graph = fnx_builder()
        expected = nx_builder()

        with pytest.raises(Exception) as nx_exc:
            nx.chordal_graph_treewidth(expected)

        monkeypatch.setattr(
            nx,
            "chordal_graph_treewidth",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError(
                    "NetworkX chordal_graph_treewidth fallback should not be used"
                )
            ),
        )

        with pytest.raises(Exception) as fnx_exc:
            fnx.chordal_graph_treewidth(graph)

        assert type(fnx_exc.value).__name__ == type(nx_exc.value).__name__
        assert str(fnx_exc.value) == str(nx_exc.value)


# ---------------------------------------------------------------------------
# treewidth_min_degree parity
# ---------------------------------------------------------------------------


@needs_nx
class TestTreewidthMinDegreeParity:
    @pytest.mark.parametrize(
        "graph_builder",
        [
            lambda mod: mod.path_graph(5),
            lambda mod: mod.cycle_graph(5),
            lambda mod: mod.complete_graph(4),
        ],
    )
    def test_matches_networkx_without_fallback(self, monkeypatch, graph_builder):
        graph = graph_builder(fnx)
        expected = graph_builder(nx)

        expected_width, expected_decomp = nx.approximation.treewidth_min_degree(expected)
        expected_bags = {frozenset(bag) for bag in expected_decomp.nodes()}
        expected_edges = {
            frozenset((frozenset(u), frozenset(v))) for u, v in expected_decomp.edges()
        }

        monkeypatch.setattr(
            nx.approximation,
            "treewidth_min_degree",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError(
                    "NetworkX approximation.treewidth_min_degree fallback should not be used"
                )
            ),
        )

        actual_width, actual_decomp = fnx.approximation.treewidth_min_degree(graph)
        actual_bags = {frozenset(bag) for bag in actual_decomp.nodes()}
        actual_edges = {
            frozenset((frozenset(u), frozenset(v))) for u, v in actual_decomp.edges()
        }

        assert actual_width == expected_width
        assert actual_bags == expected_bags
        assert actual_edges == expected_edges

    @pytest.mark.parametrize(
        ("fnx_builder", "nx_builder"),
        [
            (lambda: fnx.DiGraph([(0, 1)]), lambda: nx.DiGraph([(0, 1)])),
            (lambda: fnx.MultiGraph([(0, 1)]), lambda: nx.MultiGraph([(0, 1)])),
        ],
    )
    def test_error_contract_matches_networkx_without_fallback(
        self, monkeypatch, fnx_builder, nx_builder
    ):
        graph = fnx_builder()
        expected = nx_builder()

        try:
            nx.approximation.treewidth_min_degree(expected)
        except Exception as exc:
            expected_type = type(exc).__name__
            expected_message = str(exc)

        monkeypatch.setattr(
            nx.approximation,
            "treewidth_min_degree",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError(
                    "NetworkX approximation.treewidth_min_degree fallback should not be used"
                )
            ),
        )

        with pytest.raises(Exception) as fnx_exc:
            fnx.approximation.treewidth_min_degree(graph)

        assert type(fnx_exc.value).__name__ == expected_type
        assert str(fnx_exc.value) == expected_message


# ---------------------------------------------------------------------------
# spanner
# ---------------------------------------------------------------------------


class TestSpanner:
    def test_stretch_one_returns_all_edges(self):
        G = fnx.complete_graph(5)
        S = fnx.spanner(G, 1, seed=2)
        assert set(G.nodes()) == set(S.nodes())
        assert set(G.edges()) == set(S.edges())

    def test_unweighted_complete_graph(self):
        G = fnx.complete_graph(8)
        S = fnx.spanner(G, 4, seed=2)
        assert_valid_spanner(G, S, 4)

    def test_weighted_complete_graph_preserves_weights(self):
        G = fnx.Graph()
        for node in range(6):
            G.add_node(node)
        for left in range(6):
            for right in range(left + 1, 6):
                G.add_edge(left, right, weight=left + right + 0.5)

        S = fnx.spanner(G, 4, weight="weight", seed=2)
        assert_valid_spanner(G, S, 4, weight="weight")

    def test_disconnected_graph_keeps_components(self):
        G = fnx.Graph()
        G.add_edge(0, 1)
        G.add_edge(1, 2)
        G.add_edge(3, 4)
        G.add_edge(4, 5)
        S = fnx.spanner(G, 4, seed=2)
        assert set(G.nodes()) == set(S.nodes())
        for u, v in S.edges():
            assert G.has_edge(u, v)

    def test_invalid_stretch_raises(self):
        with pytest.raises(ValueError, match="stretch must be at least 1"):
            fnx.spanner(fnx.Graph(), 0)
