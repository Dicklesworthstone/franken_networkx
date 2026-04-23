"""Tests for recently added parity functions.

Covers: girvan_newman, k_clique_communities, bipartite helpers,
random generators, GML I/O, isomorphism.
"""

import os
import tempfile

import pytest

import franken_networkx as fnx

try:
    import networkx as nx

    HAS_NX = True
except ImportError:
    HAS_NX = False

needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


# ---------------------------------------------------------------------------
# Community detection
# ---------------------------------------------------------------------------


class TestGirvanNewman:
    def test_two_cliques_with_bridge(self):
        G = fnx.Graph()
        G.add_edges_from([(0, 1), (1, 2), (0, 2), (3, 4), (4, 5), (3, 5), (2, 3)])
        partitions = list(fnx.girvan_newman(G))
        assert len(partitions) >= 1
        # First split should separate the two triangles
        first = partitions[0]
        assert len(first) == 2
        sizes = sorted(len(c) for c in first)
        assert sizes == [3, 3]

    def test_single_node(self):
        """Upstream nx.community.girvan_newman on a single-node graph
        yields one partition with one community — the node itself.
        fnx matches the contract (community shape is ``list`` on fnx,
        ``set`` on nx; compare by frozenset to stay stable).
        """
        G = fnx.Graph()
        G.add_node(0)
        partitions = list(fnx.girvan_newman(G))
        assert [[frozenset(c) for c in p] for p in partitions] == [[frozenset({0})]]

    def test_empty_graph(self):
        G = fnx.Graph()
        partitions = list(fnx.girvan_newman(G))
        assert partitions == [()]

    def test_disconnected_graph(self):
        G = fnx.Graph()
        G.add_edge(0, 1)
        G.add_edge(2, 3)
        # Already disconnected — first yield should have 2 components
        partitions = list(fnx.girvan_newman(G))
        assert len(partitions) >= 1


class TestKCliqueCommunities:
    def test_two_overlapping_triangles(self):
        G = fnx.Graph()
        G.add_edges_from([(0, 1), (0, 2), (1, 2), (2, 3), (2, 4), (3, 4)])
        comms = list(fnx.k_clique_communities(G, 3))
        assert len(comms) == 2
        # Node 2 should be in both communities
        all_nodes = set()
        for c in comms:
            all_nodes.update(c)
        assert 2 in all_nodes

    def test_k_too_large(self):
        G = fnx.path_graph(3)
        comms = list(fnx.k_clique_communities(G, 3))
        assert comms == []

    def test_k_equals_2(self):
        G = fnx.path_graph(4)
        comms = list(fnx.k_clique_communities(G, 2))
        # Each edge is a 2-clique, and they're all adjacent
        assert len(comms) >= 1

    def test_k_less_than_2_raises(self):
        G = fnx.Graph()
        with pytest.raises(ValueError):
            list(fnx.k_clique_communities(G, 1))


# ---------------------------------------------------------------------------
# Bipartite helpers
# ---------------------------------------------------------------------------


class TestBipartiteHelpers:
    def test_is_bipartite_node_set_valid(self):
        B = fnx.Graph()
        B.add_edges_from([(1, "a"), (1, "b"), (2, "b"), (2, "c")])
        top, _ = fnx.bipartite_sets(B)
        assert fnx.is_bipartite_node_set(B, top)

    def test_is_bipartite_node_set_invalid(self):
        B = fnx.Graph()
        B.add_edges_from([(1, "a"), (2, "b")])
        assert not fnx.is_bipartite_node_set(B, [1, "a"])

    def test_projected_graph(self):
        B = fnx.Graph()
        B.add_edges_from([(1, "a"), (1, "b"), (2, "b"), (2, "c"), (3, "c")])
        P = fnx.projected_graph(B, [1, 2, 3])
        assert P.number_of_nodes() == 3
        # 1 and 2 share neighbor "b"
        assert P.has_edge(1, 2)
        # 2 and 3 share neighbor "c"
        assert P.has_edge(2, 3)

    def test_bipartite_density(self):
        B = fnx.complete_bipartite_graph(3, 3)
        top, _ = fnx.bipartite_sets(B)
        d = fnx.bipartite_density(B, top)
        assert d == pytest.approx(1.0)

    def test_bipartite_density_sparse(self):
        B = fnx.Graph()
        B.add_edge(0, "a")
        d = fnx.bipartite_density(B, [0])
        assert d == pytest.approx(1.0)

    def test_hopcroft_karp_matching(self):
        B = fnx.Graph()
        B.add_edges_from([(1, "a"), (1, "b"), (2, "b"), (3, "c")])
        m = fnx.hopcroft_karp_matching(B)
        # Should match at least 2 pairs
        assert len(m) >= 4  # Each match creates 2 entries (u->v and v->u)


# ---------------------------------------------------------------------------
# Random generators
# ---------------------------------------------------------------------------


class TestRandomGenerators:
    def test_erdos_renyi_graph(self):
        G = fnx.erdos_renyi_graph(30, 0.3, seed=42)
        assert G.number_of_nodes() == 30
        assert G.number_of_edges() > 0

    def test_random_regular_graph(self):
        G = fnx.random_regular_graph(3, 20, seed=42)
        assert G.number_of_nodes() == 20
        assert G.number_of_edges() == 30  # n*d/2
        for _, deg in G.degree:
            assert deg == 3

    def test_powerlaw_cluster_graph(self):
        G = fnx.powerlaw_cluster_graph(30, 2, 0.5, seed=42)
        assert G.number_of_nodes() == 30
        assert G.number_of_edges() > 0
        assert fnx.is_connected(G)


# ---------------------------------------------------------------------------
# GML I/O
# ---------------------------------------------------------------------------


class TestGmlIO:
    def test_undirected_round_trip(self):
        G = fnx.path_graph(4)
        with tempfile.NamedTemporaryFile(suffix=".gml", delete=False) as f:
            path = f.name
        try:
            fnx.write_gml(G, path)
            H = fnx.read_gml(path)
            assert H.number_of_nodes() == 4
            assert H.number_of_edges() == 3
        finally:
            os.unlink(path)

    def test_directed_round_trip(self):
        D = fnx.DiGraph()
        D.add_edge("a", "b")
        D.add_edge("b", "c")
        with tempfile.NamedTemporaryFile(suffix=".gml", delete=False) as f:
            path = f.name
        try:
            fnx.write_gml(D, path)
            H = fnx.read_gml(path)
            assert isinstance(H, fnx.DiGraph)
            assert H.number_of_nodes() == 3
            assert H.number_of_edges() == 2
        finally:
            os.unlink(path)

    def test_weighted_round_trip(self):
        G = fnx.Graph()
        G.add_edge(0, 1, weight="2.5")
        with tempfile.NamedTemporaryFile(suffix=".gml", delete=False) as f:
            path = f.name
        try:
            fnx.write_gml(G, path)
            H = fnx.read_gml(path)
            assert H.number_of_edges() == 1
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# Isomorphism
# ---------------------------------------------------------------------------


class TestIsomorphism:
    def test_faster_could_be_isomorphic(self):
        G1 = fnx.path_graph(5)
        G2 = fnx.path_graph(5)
        assert fnx.faster_could_be_isomorphic(G1, G2)

    def test_faster_not_isomorphic(self):
        G1 = fnx.path_graph(5)
        G2 = fnx.complete_graph(5)
        assert not fnx.faster_could_be_isomorphic(G1, G2)


class TestChordal:
    def test_complete_is_chordal(self):
        assert fnx.is_chordal(fnx.complete_graph(5))

    def test_cycle_not_chordal(self):
        assert not fnx.is_chordal(fnx.cycle_graph(5))

    def test_tree_is_chordal(self):
        assert fnx.is_chordal(fnx.path_graph(5))
        assert fnx.is_chordal(fnx.star_graph(4))

    @needs_nx
    def test_matches_nx(self):
        for g_fn, args in [(fnx.complete_graph, (6,)), (fnx.cycle_graph, (6,)), (fnx.path_graph, (4,))]:
            g_fnx = g_fn(*args)
            g_nx = getattr(nx, g_fn.__name__)(*args)
            assert fnx.is_chordal(g_fnx) == nx.is_chordal(g_nx)
