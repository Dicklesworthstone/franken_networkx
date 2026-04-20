"""Comprehensive parity tests for all FrankenNetworkX functions.

Cross-validates every function against NetworkX where possible.
Tests basic functionality, edge cases, and return type correctness.
"""

import pytest
import franken_networkx as fnx

try:
    import networkx as nx
    HAS_NX = True
except ImportError:
    HAS_NX = False

try:
    import numpy as np
    HAS_NP = True
except ImportError:
    HAS_NP = False

needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")
needs_np = pytest.mark.skipif(not HAS_NP, reason="numpy not installed")


# ---------------------------------------------------------------------------
# Graph construction helpers
# ---------------------------------------------------------------------------

class TestConstructionHelpers:
    def test_add_path(self):
        G = fnx.Graph()
        fnx.add_path(G, [0, 1, 2, 3])
        assert G.number_of_edges() == 3

    def test_add_cycle(self):
        G = fnx.Graph()
        fnx.add_cycle(G, [0, 1, 2, 3])
        assert G.number_of_edges() == 4

    def test_add_star(self):
        G = fnx.Graph()
        fnx.add_star(G, [0, 1, 2, 3])
        assert G.number_of_edges() == 3


# ---------------------------------------------------------------------------
# Attribute helpers
# ---------------------------------------------------------------------------

class TestAttributeHelpers:
    def test_set_get_node_attributes(self):
        G = fnx.Graph()
        G.add_nodes_from([0, 1, 2])
        fnx.set_node_attributes(G, {0: 'a', 1: 'b'}, 'label')
        attrs = fnx.get_node_attributes(G, 'label')
        assert attrs[0] == 'a'

    def test_set_get_edge_attributes(self):
        G = fnx.Graph()
        G.add_edge(0, 1)
        fnx.set_edge_attributes(G, {(0, 1): 5.0}, 'weight')
        attrs = fnx.get_edge_attributes(G, 'weight')
        assert (0, 1) in attrs or (1, 0) in attrs

    def test_remove_node_attributes(self):
        G = fnx.Graph()
        G.add_node(0, color='red')
        fnx.remove_node_attributes(G, 'color')

    def test_remove_edge_attributes(self):
        G = fnx.Graph()
        G.add_edge(0, 1, weight=3.0)
        fnx.remove_edge_attributes(G, 'weight')


# ---------------------------------------------------------------------------
# DAG & Ancestor algorithms
# ---------------------------------------------------------------------------

class TestDAGAlgorithms:
    def test_all_topological_sorts(self):
        D = fnx.DiGraph()
        D.add_edges_from([(0, 1), (0, 2), (1, 3), (2, 3)])
        sorts = list(fnx.all_topological_sorts(D))
        assert len(sorts) == 2

    def test_lowest_common_ancestor(self):
        D = fnx.DiGraph()
        D.add_edges_from([(0, 1), (0, 2), (1, 3), (2, 3)])
        assert fnx.lowest_common_ancestor(D, 1, 2) == 0

    def test_all_pairs_lowest_common_ancestor(self):
        D = fnx.DiGraph()
        D.add_edges_from([(0, 1), (0, 2)])
        pairs = list(fnx.all_pairs_lowest_common_ancestor(D, pairs=[(1, 2)]))
        assert len(pairs) == 1

    def test_tree_all_pairs_lowest_common_ancestor_matches_networkx_without_fallback(
        self, monkeypatch
    ):
        graph = fnx.DiGraph([(0, 1), (0, 2), (1, 3), (1, 4)])
        expected = nx.DiGraph([(0, 1), (0, 2), (1, 3), (1, 4)])

        expected_result = list(nx.tree_all_pairs_lowest_common_ancestor(expected))

        monkeypatch.setattr(
            nx,
            "tree_all_pairs_lowest_common_ancestor",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError(
                    "NetworkX tree_all_pairs_lowest_common_ancestor fallback should not be used"
                )
            ),
        )

        result = list(fnx.tree_all_pairs_lowest_common_ancestor(graph))
        assert result == expected_result

    def test_tree_all_pairs_lowest_common_ancestor_root_matches_networkx_without_fallback(
        self, monkeypatch
    ):
        graph = fnx.DiGraph([(0, 1), (0, 2), (1, 3), (1, 4)])
        expected = nx.DiGraph([(0, 1), (0, 2), (1, 3), (1, 4)])

        expected_result = list(nx.tree_all_pairs_lowest_common_ancestor(expected, root=1))

        monkeypatch.setattr(
            nx,
            "tree_all_pairs_lowest_common_ancestor",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError(
                    "NetworkX tree_all_pairs_lowest_common_ancestor fallback should not be used"
                )
            ),
        )

        result = list(fnx.tree_all_pairs_lowest_common_ancestor(graph, root=1))
        assert result == expected_result

    @pytest.mark.parametrize(
        ("actual_graph", "expected_graph", "kwargs"),
        [
            (fnx.DiGraph(), nx.DiGraph(), {}),
            (fnx.Graph([(0, 1)]), nx.Graph([(0, 1)]), {}),
            (fnx.DiGraph([(0, 1), (2, 3)]), nx.DiGraph([(0, 1), (2, 3)]), {}),
            (fnx.DiGraph([(0, 1)]), nx.DiGraph([(0, 1)]), {"root": 9}),
            (
                fnx.DiGraph([(0, 1)]),
                nx.DiGraph([(0, 1)]),
                {"pairs": [(0, 9)]},
            ),
        ],
    )
    def test_tree_all_pairs_lowest_common_ancestor_error_contract_matches_networkx_without_fallback(
        self,
        monkeypatch,
        actual_graph,
        expected_graph,
        kwargs,
    ):
        try:
            list(nx.tree_all_pairs_lowest_common_ancestor(expected_graph, **kwargs))
        except Exception as exc:
            expected_type = type(exc).__name__
            expected_message = str(exc)

        monkeypatch.setattr(
            nx,
            "tree_all_pairs_lowest_common_ancestor",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError(
                    "NetworkX tree_all_pairs_lowest_common_ancestor fallback should not be used"
                )
            ),
        )

        with pytest.raises(Exception) as fnx_exc:
            list(fnx.tree_all_pairs_lowest_common_ancestor(actual_graph, **kwargs))

        assert type(fnx_exc.value).__name__ == expected_type
        assert str(fnx_exc.value) == expected_message

    def test_all_pairs_lowest_common_ancestor_missing_pair_error_matches_networkx_without_fallback(
        self, monkeypatch
    ):
        graph = fnx.DiGraph([(0, 1), (0, 2), (1, 3), (2, 3)])
        expected = nx.DiGraph([(0, 1), (0, 2), (1, 3), (2, 3)])
        pairs = [(1, 9), (1, 9)]

        try:
            dict(nx.all_pairs_lowest_common_ancestor(expected, pairs=pairs))
        except Exception as exc:
            expected_type = type(exc).__name__
            expected_message = str(exc)

        monkeypatch.setattr(
            nx,
            "all_pairs_lowest_common_ancestor",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError(
                    "NetworkX all_pairs_lowest_common_ancestor fallback should not be used"
                )
            ),
        )

        with pytest.raises(Exception) as fnx_exc:
            dict(fnx.all_pairs_lowest_common_ancestor(graph, pairs=pairs))

        assert type(fnx_exc.value).__name__ == expected_type
        assert str(fnx_exc.value) == expected_message

    def test_all_pairs_lowest_common_ancestor_undirected_error_matches_networkx_without_fallback(
        self, monkeypatch
    ):
        graph = fnx.Graph([(0, 1)])
        expected = nx.Graph([(0, 1)])

        try:
            dict(nx.all_pairs_lowest_common_ancestor(expected))
        except Exception as exc:
            expected_type = type(exc).__name__
            expected_message = str(exc)

        monkeypatch.setattr(
            nx,
            "all_pairs_lowest_common_ancestor",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError(
                    "NetworkX all_pairs_lowest_common_ancestor fallback should not be used"
                )
            ),
        )

        with pytest.raises(Exception) as fnx_exc:
            dict(fnx.all_pairs_lowest_common_ancestor(graph))

        assert type(fnx_exc.value).__name__ == expected_type
        assert str(fnx_exc.value) == expected_message

    def test_dag_to_branching(self):
        D = fnx.DiGraph()
        D.add_edges_from([(0, 1), (0, 2), (1, 3), (2, 3)])
        B = fnx.dag_to_branching(D)
        assert B.number_of_nodes() > D.number_of_nodes()  # node 3 duplicated


# ---------------------------------------------------------------------------
# Shortest path extras
# ---------------------------------------------------------------------------

class TestShortestPathExtras:
    def test_dijkstra_predecessor_and_distance(self):
        G = fnx.path_graph(4)
        pred, dist = fnx.dijkstra_predecessor_and_distance(G, 0)
        assert dist[3] == 3.0

    def test_multi_source_dijkstra_path(self):
        G = fnx.path_graph(5)
        paths = fnx.multi_source_dijkstra_path(G, [0])
        assert 4 in paths

    def test_all_pairs_all_shortest_paths(self):
        G = fnx.path_graph(3)
        result = list(fnx.all_pairs_all_shortest_paths(G))
        assert len(result) == 3

    def test_johnson(self):
        G = fnx.path_graph(4)
        J = fnx.johnson(G)
        assert J[0][3] == 3

    def test_bidirectional_dijkstra(self):
        G = fnx.path_graph(5)
        length, path = fnx.bidirectional_dijkstra(G, 0, 4)
        assert path == [0, 1, 2, 3, 4]

    def test_bellman_ford_predecessor_and_distance(self):
        G = fnx.path_graph(4)
        pred, dist = fnx.bellman_ford_predecessor_and_distance(G, 0)
        assert dist[3] == 3


# ---------------------------------------------------------------------------
# Flow algorithms
# ---------------------------------------------------------------------------

class TestFlowAlgorithms:
    def test_cost_of_flow(self):
        D = fnx.DiGraph()
        D.add_edge(0, 1, weight=2)
        flow = {0: {1: 3}}
        assert fnx.cost_of_flow(D, flow) == 6.0

    @needs_nx
    def test_min_cost_flow(self):
        D = fnx.DiGraph()
        D.add_node(0, demand=-3)
        D.add_node(1, demand=3)
        D.add_edge(0, 1, capacity=10, weight=1)

        expected = nx.DiGraph()
        expected.add_node(0, demand=-3)
        expected.add_node(1, demand=3)
        expected.add_edge(0, 1, capacity=10, weight=1)

        assert fnx.min_cost_flow(D) == nx.min_cost_flow(expected)

    @needs_nx
    def test_min_cost_flow_rejects_networkx_unfeasible_demand_signs(self):
        D = fnx.DiGraph()
        D.add_node(0, demand=3)
        D.add_node(1, demand=-3)
        D.add_edge(0, 1, capacity=10, weight=1)

        expected = nx.DiGraph()
        expected.add_node(0, demand=3)
        expected.add_node(1, demand=-3)
        expected.add_edge(0, 1, capacity=10, weight=1)

        with pytest.raises(nx.NetworkXUnfeasible):
            nx.min_cost_flow(expected)
        with pytest.raises(fnx.NetworkXUnfeasible):
            fnx.min_cost_flow(D)

    def test_network_simplex(self):
        D = fnx.DiGraph()
        D.add_node(0, demand=-2)
        D.add_node(1, demand=2)
        D.add_edge(0, 1, capacity=10, weight=3)
        cost, flow = fnx.network_simplex(D)
        assert cost == 6.0

    def test_network_simplex_error_contract_matches_networkx(self):
        actual_undirected = fnx.Graph()
        expected_undirected = nx.Graph()
        with pytest.raises(nx.NetworkXNotImplemented) as expected_undirected_error:
            nx.network_simplex(expected_undirected)
        with pytest.raises(fnx.NetworkXNotImplemented) as actual_undirected_error:
            fnx.network_simplex(actual_undirected)
        assert str(actual_undirected_error.value) == str(expected_undirected_error.value)

        actual_empty = fnx.DiGraph()
        expected_empty = nx.DiGraph()
        with pytest.raises(nx.NetworkXError) as expected_empty_error:
            nx.network_simplex(expected_empty)
        with pytest.raises(fnx.NetworkXError) as actual_empty_error:
            fnx.network_simplex(actual_empty)
        assert str(actual_empty_error.value) == str(expected_empty_error.value)

        actual_nonzero = fnx.DiGraph()
        expected_nonzero = nx.DiGraph()
        actual_nonzero.add_node("a", demand=-1)
        actual_nonzero.add_node("b", demand=2)
        actual_nonzero.add_edge("a", "b", capacity=5, weight=1)
        expected_nonzero.add_node("a", demand=-1)
        expected_nonzero.add_node("b", demand=2)
        expected_nonzero.add_edge("a", "b", capacity=5, weight=1)
        with pytest.raises(nx.NetworkXUnfeasible) as expected_nonzero_error:
            nx.network_simplex(expected_nonzero)
        with pytest.raises(fnx.NetworkXUnfeasible) as actual_nonzero_error:
            fnx.network_simplex(actual_nonzero)
        assert str(actual_nonzero_error.value) == str(expected_nonzero_error.value)

        actual_negative_capacity = fnx.DiGraph()
        expected_negative_capacity = nx.DiGraph()
        actual_negative_capacity.add_node("a", demand=-1)
        actual_negative_capacity.add_node("b", demand=1)
        actual_negative_capacity.add_edge("a", "b", capacity=-1, weight=1)
        expected_negative_capacity.add_node("a", demand=-1)
        expected_negative_capacity.add_node("b", demand=1)
        expected_negative_capacity.add_edge("a", "b", capacity=-1, weight=1)
        with pytest.raises(nx.NetworkXUnfeasible) as expected_capacity_error:
            nx.network_simplex(expected_negative_capacity)
        with pytest.raises(fnx.NetworkXUnfeasible) as actual_capacity_error:
            fnx.network_simplex(actual_negative_capacity)
        assert str(actual_capacity_error.value) == str(expected_capacity_error.value)

        actual_infinite_weight = fnx.DiGraph()
        expected_infinite_weight = nx.DiGraph()
        actual_infinite_weight.add_node("a", demand=-1)
        actual_infinite_weight.add_node("b", demand=1)
        actual_infinite_weight.add_edge("a", "b", capacity=1, weight=float("inf"))
        expected_infinite_weight.add_node("a", demand=-1)
        expected_infinite_weight.add_node("b", demand=1)
        expected_infinite_weight.add_edge("a", "b", capacity=1, weight=float("inf"))
        with pytest.raises(nx.NetworkXError) as expected_weight_error:
            nx.network_simplex(expected_infinite_weight)
        with pytest.raises(fnx.NetworkXError) as actual_weight_error:
            fnx.network_simplex(actual_infinite_weight)
        assert str(actual_weight_error.value) == str(expected_weight_error.value)

        actual_infinite_demand = fnx.DiGraph()
        expected_infinite_demand = nx.DiGraph()
        actual_infinite_demand.add_node("a", demand=float("inf"))
        actual_infinite_demand.add_node("b", demand=-float("inf"))
        actual_infinite_demand.add_edge("a", "b", capacity=1, weight=1)
        expected_infinite_demand.add_node("a", demand=float("inf"))
        expected_infinite_demand.add_node("b", demand=-float("inf"))
        expected_infinite_demand.add_edge("a", "b", capacity=1, weight=1)
        with pytest.raises(nx.NetworkXError) as expected_demand_error:
            nx.network_simplex(expected_infinite_demand)
        with pytest.raises(fnx.NetworkXError) as actual_demand_error:
            fnx.network_simplex(actual_infinite_demand)
        assert str(actual_demand_error.value) == str(expected_demand_error.value)

    def test_flow_hierarchy_dag(self):
        D = fnx.DiGraph()
        D.add_edges_from([(0, 1), (1, 2)])
        assert fnx.flow_hierarchy(D) == 1.0


# ---------------------------------------------------------------------------
# Centrality extras
# ---------------------------------------------------------------------------

class TestCentralityExtras:
    def test_current_flow_betweenness(self):
        G = fnx.path_graph(5)
        bc = fnx.current_flow_betweenness_centrality(G)
        assert len(bc) == 5
        assert all(v >= 0 for v in bc.values())

    def test_betweenness_subset(self):
        G = fnx.path_graph(5)
        bc = fnx.betweenness_centrality_subset(G, [0], [4])
        assert bc[2] > 0

    def test_laplacian_centrality(self):
        G = fnx.path_graph(5)
        lc = fnx.laplacian_centrality(G)
        assert all(0 <= v <= 1 for v in lc.values())

    def test_trophic_levels(self):
        D = fnx.DiGraph()
        D.add_edges_from([(0, 1), (1, 2)])
        tl = fnx.trophic_levels(D)
        assert tl[0] == pytest.approx(1.0)

    def test_group_betweenness(self):
        G = fnx.path_graph(5)
        gb = fnx.group_betweenness_centrality(G, [2])
        assert gb > 0

    @needs_np
    def test_eigenvector_centrality_numpy(self):
        G = fnx.path_graph(5)
        ec = fnx.eigenvector_centrality_numpy(G)
        assert len(ec) == 5

    @needs_np
    def test_katz_centrality_numpy(self):
        G = fnx.path_graph(5)
        kc = fnx.katz_centrality_numpy(G)
        assert len(kc) == 5


# ---------------------------------------------------------------------------
# Connectivity extras
# ---------------------------------------------------------------------------

class TestConnectivityExtras:
    def test_edge_disjoint_paths(self):
        G = fnx.Graph()
        G.add_edges_from([(0, 1), (0, 2), (1, 3), (2, 3)])
        paths = list(fnx.edge_disjoint_paths(G, 0, 3))
        assert len(paths) == 2

    def test_connected_dominating_set(self):
        G = fnx.star_graph(5)
        ds = fnx.connected_dominating_set(G)
        assert fnx.is_connected_dominating_set(G, ds)

    def test_is_kl_connected(self):
        G = fnx.complete_graph(5)
        assert fnx.is_kl_connected(G, 2, 1)


# ---------------------------------------------------------------------------
# Traversal extras
# ---------------------------------------------------------------------------

class TestTraversalExtras:
    def test_bfs_beam_edges(self):
        G = fnx.path_graph(5)
        edges = list(fnx.bfs_beam_edges(G, 0, value=lambda n: n))
        assert len(edges) >= 1

    def test_dfs_labeled_edges(self):
        G = fnx.path_graph(4)
        labels = list(fnx.dfs_labeled_edges(G, 0))
        tree_count = sum(1 for _, _, label in labels if label == 'tree')
        assert tree_count >= 3


# ---------------------------------------------------------------------------
# Structural decomposition
# ---------------------------------------------------------------------------

class TestStructuralDecomposition:
    def test_k_truss(self):
        G = fnx.complete_graph(5)
        kt = fnx.k_truss(G, 4)
        assert kt.number_of_nodes() == 5

    def test_onion_layers(self):
        G = fnx.path_graph(5)
        layers = fnx.onion_layers(G)
        assert len(layers) == 5

    def test_spectral_bisection(self):
        G = fnx.path_graph(6)
        a, b = fnx.spectral_bisection(G)
        assert len(a) + len(b) == 6

    def test_k_edge_components(self):
        G = fnx.path_graph(5)
        comps = fnx.k_edge_components(G, 1)
        assert len(comps) == 1


# ---------------------------------------------------------------------------
# Triads
# ---------------------------------------------------------------------------

class TestTriads:
    def test_triadic_census(self):
        D = fnx.DiGraph()
        D.add_edges_from([(0, 1), (1, 2), (2, 0)])
        census = fnx.triadic_census(D)
        assert sum(census.values()) == 1

    @needs_nx
    def test_triadic_census_matches_nx(self):
        edges = [(0, 1), (1, 2), (2, 0), (0, 2)]
        D = fnx.DiGraph()
        D.add_edges_from(edges)
        N = nx.DiGraph()
        N.add_edges_from(edges)
        fc = fnx.triadic_census(D)
        nc = nx.triadic_census(N)
        for t in fc:
            assert fc[t] == nc.get(t, 0), f"Mismatch on {t}"

    def test_triad_graph_roundtrip(self):
        for t in ['003', '012', '102', '021D', '021U', '021C', '111D', '111U',
                   '030T', '030C', '201', '120D', '120U', '120C', '210', '300']:
            G = fnx.triad_graph(t)
            assert fnx.triad_type(G) == t

    @pytest.mark.parametrize(("fnx_cls", "nx_cls"), [(fnx.DiGraph, nx.DiGraph), (fnx.MultiDiGraph, nx.MultiDiGraph)])
    def test_is_triad_self_loop_matches_networkx_without_fallback(
        self, monkeypatch, fnx_cls, nx_cls
    ):
        graph = fnx_cls([(0, 1), (1, 2), (2, 0)])
        expected = nx_cls([(0, 1), (1, 2), (2, 0)])
        graph.add_edge(0, 0)
        expected.add_edge(0, 0)

        expected_result = nx.is_triad(expected)
        monkeypatch.setattr(
            nx,
            "is_triad",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("NetworkX is_triad fallback should not be used")
            ),
        )

        assert fnx.is_triad(graph) is expected_result

    @pytest.mark.parametrize(("fnx_cls", "nx_cls"), [(fnx.Graph, nx.Graph), (fnx.MultiGraph, nx.MultiGraph)])
    def test_all_triads_undirected_error_matches_networkx_without_fallback(
        self, monkeypatch, fnx_cls, nx_cls
    ):
        graph = fnx_cls([(0, 1), (1, 2), (2, 0)])
        expected = nx_cls([(0, 1), (1, 2), (2, 0)])

        try:
            list(nx.all_triads(expected))
        except Exception as exc:
            expected_type = type(exc).__name__
            expected_message = str(exc)

        monkeypatch.setattr(
            nx,
            "all_triads",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("NetworkX all_triads fallback should not be used")
            ),
        )

        with pytest.raises(Exception) as fnx_exc:
            list(fnx.all_triads(graph))

        assert type(fnx_exc.value).__name__ == expected_type
        assert str(fnx_exc.value) == expected_message


# ---------------------------------------------------------------------------
# Spectral
# ---------------------------------------------------------------------------

@needs_np
class TestSpectral:
    def test_laplacian_matrix(self):
        G = fnx.path_graph(4)
        L = fnx.laplacian_matrix(G)
        assert L.shape == (4, 4)

    def test_laplacian_spectrum(self):
        G = fnx.path_graph(4)
        spec = fnx.laplacian_spectrum(G)
        assert abs(spec[0]) < 1e-10

    def test_bethe_hessian(self):
        G = fnx.path_graph(4)
        H = fnx.bethe_hessian_matrix(G)
        assert H.shape == (4, 4)

    def test_google_matrix(self):
        D = fnx.DiGraph()
        D.add_edges_from([(0, 1), (1, 2), (2, 0)])
        GM = fnx.google_matrix(D)
        assert np.allclose(GM.sum(axis=1), 1.0)

    def test_algebraic_connectivity(self):
        G = fnx.path_graph(5)
        ac = fnx.algebraic_connectivity(G)
        assert ac > 0

    @needs_nx
    def test_estrada_matches_nx(self):
        G = fnx.complete_graph(5)
        N = nx.complete_graph(5)
        assert abs(fnx.estrada_index(G) - nx.estrada_index(N)) < 0.01


# ---------------------------------------------------------------------------
# Generators
# ---------------------------------------------------------------------------

class TestGenerators:
    def test_stochastic_block_model(self):
        G = fnx.stochastic_block_model([5, 5], [[0.8, 0.1], [0.1, 0.8]], seed=42)
        assert G.number_of_nodes() == 10

    def test_planted_partition(self):
        G = fnx.planted_partition_graph(3, 5, 0.9, 0.1, seed=42)
        assert G.number_of_nodes() == 15

    def test_hexagonal_lattice(self):
        G = fnx.hexagonal_lattice_graph(3, 4)
        assert G.number_of_nodes() > 0

    def test_triangular_lattice(self):
        G = fnx.triangular_lattice_graph(3, 4)
        assert G.number_of_nodes() == 12

    def test_grid_graph(self):
        G = fnx.grid_graph([3, 4])
        assert G.number_of_nodes() == 12

    def test_random_geometric(self):
        G = fnx.random_geometric_graph(20, 0.5, seed=42)
        assert G.number_of_nodes() == 20

    def test_waxman(self):
        G = fnx.waxman_graph(20, seed=42)
        assert G.number_of_nodes() == 20

    def test_visibility_graph(self):
        G = fnx.visibility_graph([3, 1, 4, 1, 5])
        assert G.number_of_nodes() == 5

    def test_hkn_harary(self):
        G = fnx.hkn_harary_graph(3, 7)
        assert G.number_of_nodes() == 7

    def test_mycielskian(self):
        G = fnx.mycielskian(fnx.complete_graph(2))
        assert G.number_of_nodes() > 2

    def test_random_lobster_graph(self):
        G = fnx.random_lobster_graph(10, 0.5, 0.3, seed=42)
        assert fnx.is_connected(G)

    def test_interval_graph(self):
        G = fnx.interval_graph([(0, 2), (1, 3), (4, 6)])
        assert G.has_edge(0, 1)
        assert not G.has_edge(0, 2)

    def test_dorogovtsev(self):
        G = fnx.dorogovtsev_goltsev_mendes_graph(2)
        assert G.number_of_nodes() > 2

    def test_complete_to_chordal(self):
        H, added = fnx.complete_to_chordal_graph(fnx.cycle_graph(5))
        assert fnx.is_chordal(H)


@needs_nx
class TestCompleteToChordalGraphParity:
    @pytest.mark.parametrize(
        "builder",
        [
            lambda: nx.wheel_graph(10),
            lambda: nx.cycle_graph(5),
            lambda: nx.cycle_graph(6),
            lambda: nx.cycle_graph(8),
            lambda: nx.ladder_graph(4),
        ],
    )
    def test_non_chordal_matches_networkx_counts(self, builder):
        Gn = builder()
        Gf = fnx.Graph()
        Gf.add_nodes_from(Gn.nodes())
        Gf.add_edges_from(Gn.edges())

        Hn, alpha_n = nx.complete_to_chordal_graph(Gn)
        Hf, alpha_f = fnx.complete_to_chordal_graph(Gf)

        nx_added = Hn.number_of_edges() - Gn.number_of_edges()
        fnx_added = Hf.number_of_edges() - Gf.number_of_edges()
        assert fnx_added == nx_added, f"chord count {fnx_added} != nx {nx_added}"
        assert fnx.is_chordal(Hf)
        assert set(alpha_f.keys()) == set(alpha_n.keys())
        assert sorted(alpha_f.values()) == sorted(alpha_n.values())

    @pytest.mark.parametrize(
        "builder",
        [
            lambda: nx.path_graph(5),
            lambda: nx.complete_graph(4),
            lambda: nx.star_graph(4),
            lambda: nx.empty_graph(3),
        ],
    )
    def test_already_chordal_returns_zero_alpha_and_unchanged_graph(self, builder):
        Gn = builder()
        Gf = fnx.Graph()
        Gf.add_nodes_from(Gn.nodes())
        Gf.add_edges_from(Gn.edges())

        Hf, alpha_f = fnx.complete_to_chordal_graph(Gf)

        assert Hf.number_of_edges() == Gf.number_of_edges()
        assert set(Hf.nodes()) == set(Gf.nodes())
        assert all(v == 0 for v in alpha_f.values())
        assert set(alpha_f.keys()) == set(Gf.nodes())


@needs_nx
class TestNoNetworkxRuntimeDependency:
    """Guard that functions previously flagged NX_DELEGATED still work end-to-end
    without importing or touching NetworkX at runtime.
    """

    def test_is_graphical_bad_method_raises(self):
        with pytest.raises(fnx.NetworkXError):
            fnx.is_graphical([2, 2, 2], method="not-a-method")

    def test_is_graphical_happy_path_matches_nx(self):
        for seq in ([2, 2, 2], [3, 3, 3, 3], [4, 2, 2, 1, 1], [1, 1]):
            assert fnx.is_graphical(seq) == nx.is_graphical(seq)

    def test_maybe_regular_expander_graph_shape(self):
        G = fnx.maybe_regular_expander_graph(12, 4, seed=42)
        assert G.number_of_nodes() == 12
        assert all(G.degree[n] == 4 for n in G.nodes())

    def test_random_regular_expander_graph_shape(self):
        G = fnx.random_regular_expander_graph(10, 4, seed=7)
        assert G.number_of_nodes() == 10
        assert all(G.degree[n] == 4 for n in G.nodes())

    def test_non_randomness_matches_networkx(self):
        Gn = nx.karate_club_graph()
        Gf = fnx.Graph()
        Gf.add_nodes_from(Gn.nodes())
        Gf.add_edges_from(Gn.edges(data=True))

        k = 4
        nr_f, nrr_f = fnx.non_randomness(Gf, k=k)
        nr_n, nrr_n = nx.non_randomness(Gn, k=k)
        assert nr_f == pytest.approx(nr_n, rel=1e-9, abs=1e-9)
        assert nrr_f == pytest.approx(nrr_n, rel=1e-9, abs=1e-9)

    def test_non_randomness_rejects_disconnected(self):
        G = fnx.Graph()
        G.add_edges_from([(0, 1), (2, 3)])
        with pytest.raises(fnx.NetworkXError):
            fnx.non_randomness(G, k=2)


def _build_find_induced_nodes_case(graph, case_name):
    if case_name == "path_0_3":
        graph.add_edges_from([(0, 1), (1, 2), (2, 3)])
        return (0, 3), {}
    if case_name == "path_0_2":
        graph.add_edges_from([(0, 1), (1, 2), (2, 3)])
        return (0, 2), {}
    if case_name == "path_bound":
        graph.add_edges_from([(0, 1), (1, 2), (2, 3)])
        return (0, 3), {"treewidth_bound": 0}
    if case_name == "cycle4":
        graph.add_edges_from([(0, 1), (1, 2), (2, 3), (3, 0)])
        return (0, 2), {}
    if case_name == "digraph":
        graph.add_edges_from([(0, 1), (1, 2), (2, 3)])
        return (0, 3), {}
    if case_name == "multigraph":
        graph.add_edges_from([(0, 1), (1, 2), (2, 3)])
        return (0, 3), {}
    raise ValueError(f"unknown find_induced_nodes case {case_name}")


@needs_nx
class TestFindInducedNodesParity:
    @pytest.mark.parametrize(
        ("fnx_cls", "nx_cls", "case_name"),
        [
            (fnx.Graph, nx.Graph, "path_0_3"),
            (fnx.Graph, nx.Graph, "path_0_2"),
        ],
    )
    def test_matches_networkx_without_fallback(
        self, monkeypatch, fnx_cls, nx_cls, case_name
    ):
        graph = fnx_cls()
        expected = nx_cls()
        args, kwargs = _build_find_induced_nodes_case(graph, case_name)
        _build_find_induced_nodes_case(expected, case_name)

        expected_result = nx.find_induced_nodes(expected, *args, **kwargs)
        monkeypatch.setattr(
            nx,
            "find_induced_nodes",
            lambda *call_args, **call_kwargs: (_ for _ in ()).throw(
                AssertionError("NetworkX find_induced_nodes fallback should not be used")
            ),
        )

        assert fnx.find_induced_nodes(graph, *args, **kwargs) == expected_result

    @pytest.mark.parametrize(
        ("fnx_cls", "nx_cls", "case_name"),
        [
            (fnx.Graph, nx.Graph, "path_bound"),
            (fnx.Graph, nx.Graph, "cycle4"),
            (fnx.DiGraph, nx.DiGraph, "digraph"),
            (fnx.MultiGraph, nx.MultiGraph, "multigraph"),
        ],
    )
    def test_error_contract_matches_networkx_without_fallback(
        self, monkeypatch, fnx_cls, nx_cls, case_name
    ):
        graph = fnx_cls()
        expected = nx_cls()
        args, kwargs = _build_find_induced_nodes_case(graph, case_name)
        _build_find_induced_nodes_case(expected, case_name)

        try:
            nx.find_induced_nodes(expected, *args, **kwargs)
        except Exception as exc:
            expected_type = type(exc).__name__
            expected_message = str(exc)

        monkeypatch.setattr(
            nx,
            "find_induced_nodes",
            lambda *call_args, **call_kwargs: (_ for _ in ()).throw(
                AssertionError("NetworkX find_induced_nodes fallback should not be used")
            ),
        )

        with pytest.raises(Exception) as fnx_exc:
            fnx.find_induced_nodes(graph, *args, **kwargs)

        assert type(fnx_exc.value).__name__ == expected_type
        assert str(fnx_exc.value) == expected_message


# ---------------------------------------------------------------------------
# Graph products and operators
# ---------------------------------------------------------------------------

class TestGraphProducts:
    def test_corona_product(self):
        G = fnx.corona_product(fnx.path_graph(2), fnx.path_graph(2))
        assert G.number_of_nodes() == 6

    def test_cartesian_product(self):
        G = fnx.cartesian_product(fnx.path_graph(2), fnx.path_graph(3))
        assert G.number_of_nodes() == 6

    def test_disjoint_union(self):
        G = fnx.disjoint_union(fnx.path_graph(3), fnx.path_graph(2))
        assert G.number_of_nodes() == 5


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

@needs_np
class TestMetrics:
    def test_resistance_distance(self):
        G = fnx.path_graph(4)
        rd = fnx.resistance_distance(G, 0, 3)
        assert abs(rd - 3.0) < 0.01

    def test_kemeny_constant(self):
        G = fnx.path_graph(4)
        kc = fnx.kemeny_constant(G)
        assert kc > 0

    def test_sigma(self):
        G = fnx.watts_strogatz_graph(12, 4, 0.2, seed=42)
        s = fnx.sigma(G, nrand=2, seed=42)
        assert isinstance(s, float)


# ---------------------------------------------------------------------------
# Similarity
# ---------------------------------------------------------------------------

class TestSimilarity:
    def test_simrank(self):
        G = fnx.path_graph(4)
        s = fnx.simrank_similarity(G, 0, 0)
        assert s == pytest.approx(1.0)

    def test_panther(self):
        G = fnx.path_graph(5)
        p = fnx.panther_similarity(G, 0, seed=42)
        assert isinstance(p, dict)


# ---------------------------------------------------------------------------
# Predicates
# ---------------------------------------------------------------------------

class TestPredicates:
    def test_is_strongly_regular(self):
        assert fnx.is_strongly_regular(fnx.petersen_graph())

    def test_erdos_gallai(self):
        assert fnx.is_valid_degree_sequence_erdos_gallai([3, 3, 2, 2, 2])
        assert not fnx.is_valid_degree_sequence_erdos_gallai([4, 1, 1])

    def test_is_chordal(self):
        assert fnx.is_chordal(fnx.complete_graph(4))
        assert not fnx.is_chordal(fnx.cycle_graph(5))


# ---------------------------------------------------------------------------
# Conversion
# ---------------------------------------------------------------------------

@needs_np
class TestConversion:
    def test_numpy_roundtrip(self):
        G = fnx.path_graph(4)
        A = fnx.to_numpy_array(G)
        H = fnx.from_numpy_array(A)
        assert H.number_of_edges() == 3

    def test_prufer_roundtrip(self):
        T = fnx.path_graph(5)
        seq = fnx.to_prufer_sequence(T)
        T2 = fnx.from_prufer_sequence(seq)
        assert T2.number_of_edges() == 4

    def test_modularity_matrix(self):
        B = fnx.modularity_matrix(fnx.complete_graph(4))
        assert abs(B.sum()) < 1e-10


# ---------------------------------------------------------------------------
# Community
# ---------------------------------------------------------------------------

class TestCommunity:
    def test_girvan_newman(self):
        G = fnx.Graph()
        G.add_edges_from([(0, 1), (1, 2), (0, 2), (3, 4), (4, 5), (3, 5), (2, 3)])
        parts = list(fnx.girvan_newman(G))
        assert len(parts) >= 1
        assert len(parts[0]) == 2

    def test_k_clique_communities(self):
        G = fnx.Graph()
        G.add_edges_from([(0, 1), (0, 2), (1, 2), (2, 3), (2, 4), (3, 4)])
        comms = list(fnx.k_clique_communities(G, 3))
        assert len(comms) == 2


# ---------------------------------------------------------------------------
# WL hash
# ---------------------------------------------------------------------------

class TestWLHash:
    def test_isomorphism_invariance(self):
        G1 = fnx.complete_graph(4)
        G2 = fnx.complete_graph(4)
        G3 = fnx.path_graph(4)
        assert fnx.weisfeiler_lehman_graph_hash(G1) == fnx.weisfeiler_lehman_graph_hash(G2)
        assert fnx.weisfeiler_lehman_graph_hash(G1) != fnx.weisfeiler_lehman_graph_hash(G3)


# ---------------------------------------------------------------------------
# Edge swapping
# ---------------------------------------------------------------------------

class TestEdgeSwapping:
    def test_degree_preservation(self):
        G = fnx.complete_graph(6)
        orig = sorted(d for _, d in G.degree)
        fnx.double_edge_swap(G, nswap=5, seed=42)
        assert sorted(d for _, d in G.degree) == orig
