"""Parity tests for functions natively replaced by MaroonLotus.

Verifies that native Python implementations match NetworkX output exactly.
"""

import pytest
import franken_networkx as fnx

try:
    import networkx as nx

    HAS_NX = True
except ImportError:
    HAS_NX = False

needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx required")


@needs_nx
class TestEulerize:
    def test_eulerize_null_graph_error_matches_networkx(self):
        fnx_graph = fnx.Graph()
        nx_graph = nx.Graph()

        with pytest.raises(fnx.NetworkXPointlessConcept, match=r"^Cannot Eulerize null graph$") as fnx_exc:
            fnx.eulerize(fnx_graph)
        with pytest.raises(nx.NetworkXPointlessConcept, match=r"^Cannot Eulerize null graph$") as nx_exc:
            nx.eulerize(nx_graph)

        assert str(fnx_exc.value) == str(nx_exc.value)

    def test_eulerize_makes_graph_eulerian(self):
        G = fnx.Graph()
        G.add_edges_from([(0, 1), (1, 2), (2, 3)])
        H = fnx.eulerize(G)
        assert fnx.is_eulerian(H)

    def test_eulerize_already_eulerian_unchanged(self):
        G = fnx.cycle_graph(5)
        H = fnx.eulerize(G)
        assert fnx.is_eulerian(H)
        assert H.number_of_edges() == G.number_of_edges()

    def test_eulerize_preserves_nodes(self):
        G = fnx.path_graph(5)
        H = fnx.eulerize(G)
        assert set(H.nodes()) == set(G.nodes())


@needs_nx
class TestMoralGraph:
    def test_moral_graph_marries_co_parents(self):
        D = fnx.DiGraph()
        D.add_edges_from([(1, 3), (2, 3)])
        M = fnx.moral_graph(D)
        assert M.has_edge(1, 2), "co-parents should be married"

    def test_moral_graph_matches_nx(self):
        D_fnx = fnx.DiGraph()
        D_fnx.add_edges_from([(1, 3), (2, 3), (3, 4), (1, 4), (2, 4)])
        D_nx = nx.DiGraph()
        D_nx.add_edges_from([(1, 3), (2, 3), (3, 4), (1, 4), (2, 4)])

        M_fnx = fnx.moral_graph(D_fnx)
        M_nx = nx.moral_graph(D_nx)

        assert {frozenset(e) for e in M_fnx.edges()} == {
            frozenset(e) for e in M_nx.edges()
        }


@needs_nx
class TestProjectedGraph:
    def test_projected_graph_basic(self):
        B = fnx.Graph()
        B.add_edges_from([("a", 1), ("a", 2), ("b", 1)])
        P = fnx.projected_graph(B, [1, 2])
        assert P.has_edge(1, 2)

    def test_projected_graph_multigraph_matches_nx(self):
        B_fnx = fnx.complete_bipartite_graph(2, 3)
        B_nx = nx.complete_bipartite_graph(2, 3)

        P_fnx = fnx.projected_graph(B_fnx, [0, 1], multigraph=True)
        P_nx = nx.projected_graph(B_nx, [0, 1], multigraph=True)

        assert isinstance(P_fnx, fnx.MultiGraph)
        assert sorted(P_fnx.edges(keys=True)) == sorted(P_nx.edges(keys=True))

    def test_projected_graph_is_native_not_nx_delegate(self):
        """Bead franken_networkx-y76g: confirm fnx.projected_graph runs
        the fnx-native implementation rather than delegating into nx.
        """
        from unittest import mock

        B_fnx = fnx.complete_bipartite_graph(2, 3)
        B_nx = nx.complete_bipartite_graph(2, 3)
        expected = nx.projected_graph(B_nx, [0, 1])

        with mock.patch(
            "networkx.projected_graph",
            side_effect=AssertionError("fnx must not delegate to networkx"),
        ):
            actual = fnx.projected_graph(B_fnx, [0, 1])

        assert isinstance(actual, fnx.Graph)
        assert sorted(actual.edges) == sorted(expected.edges)


@needs_nx
class TestMycielskian:
    def test_mycielskian_node_edge_count_matches_nx(self):
        for n in [2, 3, 4]:
            G_fnx = fnx.complete_graph(n)
            G_nx = nx.complete_graph(n)
            M_fnx = fnx.mycielskian(G_fnx)
            M_nx = nx.mycielskian(G_nx)
            assert M_fnx.number_of_nodes() == M_nx.number_of_nodes()
            assert M_fnx.number_of_edges() == M_nx.number_of_edges()


@needs_nx
class TestWLHash:
    def test_wl_hash_identical_graphs_equal(self):
        G1 = fnx.path_graph(5)
        G2 = fnx.path_graph(5)
        assert fnx.weisfeiler_lehman_graph_hash(G1) == fnx.weisfeiler_lehman_graph_hash(G2)

    def test_wl_hash_different_graphs_differ(self):
        G1 = fnx.path_graph(5)
        G2 = fnx.cycle_graph(5)
        assert fnx.weisfeiler_lehman_graph_hash(G1) != fnx.weisfeiler_lehman_graph_hash(G2)

    def test_wl_subgraph_hashes_have_correct_length(self):
        G = fnx.path_graph(5)
        sh = fnx.weisfeiler_lehman_subgraph_hashes(G, iterations=3)
        assert len(sh) == 5
        for v in sh.values():
            assert len(v) == 4  # init + 3 iterations


@needs_nx
class TestGoldbergRadzik:
    def test_directed_matches_nx(self):
        D_fnx = fnx.DiGraph()
        D_fnx.add_edge("a", "b", weight=3)
        D_fnx.add_edge("b", "c", weight=-1)
        D_fnx.add_edge("a", "c", weight=5)

        D_nx = nx.DiGraph()
        D_nx.add_edge("a", "b", weight=3)
        D_nx.add_edge("b", "c", weight=-1)
        D_nx.add_edge("a", "c", weight=5)

        pred_fnx, dist_fnx = fnx.goldberg_radzik(D_fnx, "a")
        pred_nx, dist_nx = nx.goldberg_radzik(D_nx, "a")

        assert dist_fnx == dist_nx
        assert pred_fnx == pred_nx


@needs_nx
class TestIsPerfectGraph:
    def test_complete_graph_is_perfect(self):
        assert fnx.is_perfect_graph(fnx.complete_graph(5))

    def test_bipartite_graph_is_perfect(self):
        assert fnx.is_perfect_graph(fnx.complete_bipartite_graph(3, 3))

    def test_c5_is_not_perfect(self):
        assert not fnx.is_perfect_graph(fnx.cycle_graph(5))

    def test_c4_is_perfect(self):
        assert fnx.is_perfect_graph(fnx.cycle_graph(4))

    def test_c7_is_not_perfect(self):
        assert not fnx.is_perfect_graph(fnx.cycle_graph(7))

    def test_c11_is_not_perfect(self):
        assert not fnx.is_perfect_graph(fnx.cycle_graph(11))

    def test_large_graph_matches_nx_without_networkx_fallback(self, monkeypatch):
        large_nx = nx.cycle_graph(11)
        large_fnx = fnx.cycle_graph(11)
        for node in range(11, 21):
            large_nx.add_node(node)
            large_fnx.add_node(node)

        expected = nx.is_perfect_graph(large_nx)

        def fail(*args, **kwargs):
            raise AssertionError("networkx.is_perfect_graph fallback should not be used")

        monkeypatch.setattr(nx, "is_perfect_graph", fail)

        assert large_fnx.number_of_nodes() > 20
        assert fnx.is_perfect_graph(large_fnx) == expected


@needs_nx
class TestKFactor:
    def test_k_factor_produces_k_regular(self):
        G = fnx.complete_graph(6)
        H = fnx.k_factor(G, 2)
        for n in H.nodes():
            assert H.degree[n] == 2

    def test_k_factor_zero_is_empty(self):
        G = fnx.complete_graph(4)
        H = fnx.k_factor(G, 0)
        assert H.number_of_edges() == 0
        assert H.number_of_nodes() == 4


@needs_nx
class TestWithinInterCluster:
    def test_matches_nx(self):
        G_fnx = fnx.Graph()
        G_fnx.add_edges_from([("a", "b"), ("b", "c"), ("c", "d"), ("a", "d")])
        for n in ("a", "b"):
            G_fnx.nodes[n]["community"] = 0
        for n in ("c", "d"):
            G_fnx.nodes[n]["community"] = 1

        G_nx = nx.Graph()
        G_nx.add_edges_from([("a", "b"), ("b", "c"), ("c", "d"), ("a", "d")])
        for n in ("a", "b"):
            G_nx.nodes[n]["community"] = 0
        for n in ("c", "d"):
            G_nx.nodes[n]["community"] = 1

        fnx_r = list(fnx.within_inter_cluster(G_fnx, ebunch=[("a", "c"), ("b", "d")]))
        nx_r = list(nx.within_inter_cluster(G_nx, ebunch=[("a", "c"), ("b", "d")]))
        assert fnx_r == nx_r


@needs_nx
class TestCompleteToChordal:
    def test_result_has_fill_edges(self):
        G = fnx.cycle_graph(5)
        H, alpha = fnx.complete_to_chordal_graph(G)
        assert H.number_of_edges() >= G.number_of_edges()
        assert len(alpha) == G.number_of_nodes()

    def test_preserves_all_nodes(self):
        G = fnx.cycle_graph(6)
        H, _ = fnx.complete_to_chordal_graph(G)
        assert set(H.nodes()) == set(G.nodes())


@needs_nx
class TestKEdgeComponents:
    def test_k1_matches_connected_components(self):
        G = fnx.Graph()
        G.add_edges_from([(1, 2), (3, 4)])
        comps = fnx.k_edge_components(G, 1)
        assert len(comps) == 2

    def test_k2_matches_nx(self):
        G_fnx = fnx.Graph()
        G_fnx.add_edges_from([(1, 2), (2, 3), (3, 1), (3, 4), (4, 5), (5, 6), (6, 4)])
        G_nx = nx.Graph()
        G_nx.add_edges_from([(1, 2), (2, 3), (3, 1), (3, 4), (4, 5), (5, 6), (6, 4)])

        fnx_comps = sorted([frozenset(c) for c in fnx.k_edge_components(G_fnx, 2)])
        nx_comps = sorted([frozenset(c) for c in nx.k_edge_components(G_nx, 2)])
        assert fnx_comps == nx_comps


@needs_nx
class TestEgoGraph:
    def test_ego_graph_undirected_includes_predecessors(self):
        D = fnx.DiGraph()
        D.add_edges_from([(1, 2), (2, 3), (3, 4)])
        E = fnx.ego_graph(D, 3, radius=1, undirected=True)
        assert 2 in E and 4 in E

    def test_ego_graph_distance_parameter(self):
        G = fnx.Graph()
        G.add_edge(1, 2, weight=1.0)
        G.add_edge(2, 3, weight=1.0)
        G.add_edge(1, 3, weight=10.0)
        E = fnx.ego_graph(G, 1, radius=2.0, distance="weight")
        assert 2 in E
        assert 3 in E  # reachable via 1->2->3 (weight 2.0)


@needs_nx
class TestLocalBridges:
    def test_with_span_matches_nx(self):
        G_fnx = fnx.Graph()
        G_fnx.add_edges_from([(1, 2), (2, 3), (3, 4), (4, 5), (5, 6), (6, 1), (1, 3)])

        G_nx = nx.Graph()
        G_nx.add_edges_from([(1, 2), (2, 3), (3, 4), (4, 5), (5, 6), (6, 1), (1, 3)])

        fnx_lb = {(frozenset((u, v)), s) for u, v, s in fnx.local_bridges(G_fnx, with_span=True)}
        nx_lb = {(frozenset((u, v)), s) for u, v, s in nx.local_bridges(G_nx, with_span=True)}
        assert fnx_lb == nx_lb
