"""Conformance tests verifying fnx algorithm outputs match NetworkX exactly.

These tests systematically compare fnx and nx outputs across algorithms,
edge cases, and graph types. They serve as regression guards against
parity drift.

br-r37-c1-y5y7i follow-up: added after scipy.sparse pagerank optimization.
"""

import math
import random

import networkx as nx
import pytest

import franken_networkx as fnx


class TestCentralityParity:
    """Verify centrality algorithm outputs match NetworkX."""

    def test_pagerank_undirected(self):
        G = fnx.barabasi_albert_graph(100, 5, seed=42)
        nxG = nx.barabasi_albert_graph(100, 5, seed=42)
        fnx_pr = fnx.pagerank(G, alpha=0.85)
        nx_pr = nx.pagerank(nxG, alpha=0.85)
        max_diff = max(abs(fnx_pr[n] - nx_pr[n]) for n in fnx_pr)
        assert max_diff < 1e-10

    def test_pagerank_directed(self):
        DG = fnx.DiGraph()
        DG.add_edges_from([(0, 1), (1, 2), (2, 0), (2, 3), (3, 1)])
        nxDG = nx.DiGraph()
        nxDG.add_edges_from([(0, 1), (1, 2), (2, 0), (2, 3), (3, 1)])
        fnx_pr = fnx.pagerank(DG)
        nx_pr = nx.pagerank(nxDG)
        max_diff = max(abs(fnx_pr[n] - nx_pr[n]) for n in fnx_pr)
        assert max_diff < 1e-10

    def test_pagerank_dangling_nodes(self):
        DG = fnx.DiGraph()
        DG.add_edges_from([(0, 1), (1, 2)])
        DG.add_node(3)  # dangling - no outgoing
        nxDG = nx.DiGraph()
        nxDG.add_edges_from([(0, 1), (1, 2)])
        nxDG.add_node(3)
        fnx_pr = fnx.pagerank(DG)
        nx_pr = nx.pagerank(nxDG)
        max_diff = max(abs(fnx_pr[n] - nx_pr[n]) for n in fnx_pr)
        assert max_diff < 1e-10

    def test_pagerank_weighted(self):
        random.seed(42)
        G = fnx.DiGraph()
        for i in range(10):
            for j in range(10):
                if i != j and random.random() < 0.3:
                    G.add_edge(i, j, weight=random.uniform(0.5, 2.0))
        nxG = nx.DiGraph()
        for u, v, d in G.edges(data=True):
            nxG.add_edge(u, v, weight=d["weight"])
        fnx_pr = fnx.pagerank(G, weight="weight")
        nx_pr = nx.pagerank(nxG, weight="weight")
        max_diff = max(abs(fnx_pr[n] - nx_pr[n]) for n in fnx_pr)
        assert max_diff < 1e-10

    def test_pagerank_empty(self):
        assert fnx.pagerank(fnx.Graph()) == {}
        assert nx.pagerank(nx.Graph()) == {}

    def test_betweenness_centrality_large(self):
        G = fnx.barabasi_albert_graph(200, 5, seed=42)
        nxG = nx.barabasi_albert_graph(200, 5, seed=42)
        fnx_bc = fnx.betweenness_centrality(G)
        nx_bc = nx.betweenness_centrality(nxG)
        max_diff = max(abs(fnx_bc[n] - nx_bc[n]) for n in fnx_bc)
        assert max_diff < 1e-10

    def test_closeness_centrality(self):
        G = fnx.cycle_graph(20)
        nxG = nx.cycle_graph(20)
        fnx_cc = fnx.closeness_centrality(G)
        nx_cc = nx.closeness_centrality(nxG)
        max_diff = max(abs(fnx_cc[n] - nx_cc[n]) for n in fnx_cc)
        assert max_diff < 1e-10

    def test_clustering_coefficient(self):
        G = fnx.barabasi_albert_graph(100, 5, seed=42)
        nxG = nx.barabasi_albert_graph(100, 5, seed=42)
        fnx_cl = fnx.clustering(G)
        nx_cl = nx.clustering(nxG)
        max_diff = max(abs(fnx_cl[n] - nx_cl[n]) for n in fnx_cl)
        assert max_diff < 1e-10


class TestShortestPathParity:
    """Verify shortest path algorithm outputs match NetworkX."""

    def test_single_source_shortest_path_length(self):
        G = fnx.barabasi_albert_graph(100, 5, seed=42)
        nxG = nx.barabasi_albert_graph(100, 5, seed=42)
        fnx_sp = dict(fnx.single_source_shortest_path_length(G, 0))
        nx_sp = dict(nx.single_source_shortest_path_length(nxG, 0))
        assert fnx_sp == nx_sp

    def test_all_pairs_shortest_path_length(self):
        G = fnx.path_graph(10)
        nxG = nx.path_graph(10)
        fnx_apsp = dict(fnx.all_pairs_shortest_path_length(G))
        nx_apsp = dict(nx.all_pairs_shortest_path_length(nxG))
        assert fnx_apsp == nx_apsp

    def test_dijkstra_directed(self):
        DG = fnx.gnm_random_graph(50, 200, directed=True, seed=42)
        nxDG = nx.gnm_random_graph(50, 200, directed=True, seed=42)
        fnx_sp = dict(fnx.single_source_dijkstra_path_length(DG, 0))
        nx_sp = dict(nx.single_source_dijkstra_path_length(nxDG, 0))
        assert fnx_sp == nx_sp


class TestComponentsParity:
    """Verify component algorithm outputs match NetworkX."""

    def test_connected_components(self):
        G = fnx.Graph()
        G.add_edges_from([(0, 1), (2, 3), (4, 5), (5, 6)])
        nxG = nx.Graph()
        nxG.add_edges_from([(0, 1), (2, 3), (4, 5), (5, 6)])
        fnx_cc = sorted([tuple(sorted(c)) for c in fnx.connected_components(G)])
        nx_cc = sorted([tuple(sorted(c)) for c in nx.connected_components(nxG)])
        assert fnx_cc == nx_cc

    def test_strongly_connected_components(self):
        DG = fnx.gnm_random_graph(50, 200, directed=True, seed=42)
        nxDG = nx.gnm_random_graph(50, 200, directed=True, seed=42)
        fnx_scc = sorted([tuple(sorted(c)) for c in fnx.strongly_connected_components(DG)])
        nx_scc = sorted([tuple(sorted(c)) for c in nx.strongly_connected_components(nxDG)])
        assert fnx_scc == nx_scc

    def test_number_connected_components(self):
        G = fnx.Graph()
        G.add_edges_from([(0, 1), (2, 3)])
        G.add_node(99)  # isolated
        nxG = nx.Graph()
        nxG.add_edges_from([(0, 1), (2, 3)])
        nxG.add_node(99)
        assert fnx.number_connected_components(G) == nx.number_connected_components(nxG)


class TestMatchingParity:
    """Verify matching algorithm outputs match NetworkX."""

    def test_max_weight_matching(self):
        G = fnx.Graph()
        G.add_edge(0, 1, weight=1)
        G.add_edge(1, 2, weight=5)
        G.add_edge(2, 3, weight=1)
        G.add_edge(0, 3, weight=5)
        nxG = nx.Graph()
        for u, v, d in G.edges(data=True):
            nxG.add_edge(u, v, **d)
        fnx_match = set(tuple(sorted(e)) for e in fnx.max_weight_matching(G))
        nx_match = set(tuple(sorted(e)) for e in nx.max_weight_matching(nxG))
        assert fnx_match == nx_match


class TestMultiGraphParity:
    """Verify MultiGraph/MultiDiGraph behaviors match NetworkX."""

    def test_multigraph_pagerank_weighted(self):
        MG = fnx.MultiGraph()
        MG.add_edge(0, 1, weight=1.0)
        MG.add_edge(0, 1, weight=2.0)  # parallel edge
        MG.add_edge(1, 2, weight=1.0)
        nxMG = nx.MultiGraph()
        nxMG.add_edge(0, 1, weight=1.0)
        nxMG.add_edge(0, 1, weight=2.0)
        nxMG.add_edge(1, 2, weight=1.0)
        fnx_pr = fnx.pagerank(MG, weight="weight")
        nx_pr = nx.pagerank(nxMG, weight="weight")
        max_diff = max(abs(fnx_pr[n] - nx_pr[n]) for n in fnx_pr)
        assert max_diff < 1e-10

    def test_multigraph_weighted_degree(self):
        MG = fnx.MultiGraph()
        MG.add_edge(0, 1, weight=1.0)
        MG.add_edge(0, 1, weight=2.0)
        nxMG = nx.MultiGraph()
        nxMG.add_edge(0, 1, weight=1.0)
        nxMG.add_edge(0, 1, weight=2.0)
        assert dict(MG.degree(weight="weight")) == dict(nxMG.degree(weight="weight"))

    def test_multigraph_selfloops(self):
        MG = fnx.MultiGraph()
        MG.add_edge(0, 0)
        MG.add_edge(0, 0)
        MG.add_edge(0, 1)
        nxMG = nx.MultiGraph()
        nxMG.add_edge(0, 0)
        nxMG.add_edge(0, 0)
        nxMG.add_edge(0, 1)
        assert fnx.number_of_selfloops(MG) == nx.number_of_selfloops(nxMG)


class TestEdgeCaseParity:
    """Verify edge case behaviors match NetworkX."""

    def test_k_core_isolated_nodes(self):
        G = fnx.Graph()
        G.add_edges_from([(0, 1), (1, 2), (2, 0), (0, 3), (1, 3)])
        G.add_node(99)  # isolated
        nxG = nx.Graph()
        nxG.add_edges_from([(0, 1), (1, 2), (2, 0), (0, 3), (1, 3)])
        nxG.add_node(99)
        assert set(fnx.k_core(G, k=2).nodes()) == set(nx.k_core(nxG, k=2).nodes())

    def test_density_various_graphs(self):
        # Empty
        assert fnx.density(fnx.Graph()) == nx.density(nx.Graph())
        # Single node
        g1 = fnx.Graph()
        g1.add_node(0)
        ng1 = nx.Graph()
        ng1.add_node(0)
        assert fnx.density(g1) == nx.density(ng1)
        # Path
        assert fnx.density(fnx.path_graph(5)) == nx.density(nx.path_graph(5))

    def test_is_bipartite_edge_cases(self):
        # Empty
        assert fnx.is_bipartite(fnx.Graph()) == nx.is_bipartite(nx.Graph())
        # Single node
        g1 = fnx.Graph()
        g1.add_node(0)
        ng1 = nx.Graph()
        ng1.add_node(0)
        assert fnx.is_bipartite(g1) == nx.is_bipartite(ng1)
        # Triangle (not bipartite)
        assert fnx.is_bipartite(fnx.cycle_graph(3)) == nx.is_bipartite(nx.cycle_graph(3))
        # Square (bipartite)
        assert fnx.is_bipartite(fnx.cycle_graph(4)) == nx.is_bipartite(nx.cycle_graph(4))

    def test_triangles(self):
        G = fnx.Graph()
        G.add_edges_from([(0, 1), (1, 2), (2, 0), (2, 3), (3, 4)])
        nxG = nx.Graph()
        nxG.add_edges_from([(0, 1), (1, 2), (2, 0), (2, 3), (3, 4)])
        assert fnx.triangles(G) == nx.triangles(nxG)

    def test_transitivity(self):
        G = fnx.barabasi_albert_graph(50, 3, seed=42)
        nxG = nx.barabasi_albert_graph(50, 3, seed=42)
        assert abs(fnx.transitivity(G) - nx.transitivity(nxG)) < 1e-10


class TestCommunityParity:
    """Verify community detection outputs match NetworkX."""

    def test_louvain_communities(self):
        G = fnx.barabasi_albert_graph(50, 3, seed=42)
        nxG = nx.barabasi_albert_graph(50, 3, seed=42)
        fnx_louvain = list(fnx.community.louvain_communities(G, seed=42))
        nx_louvain = list(nx.community.louvain_communities(nxG, seed=42))
        fnx_sets = set(frozenset(c) for c in fnx_louvain)
        nx_sets = set(frozenset(c) for c in nx_louvain)
        assert fnx_sets == nx_sets

    def test_greedy_modularity_communities(self):
        G = fnx.barabasi_albert_graph(50, 3, seed=42)
        nxG = nx.barabasi_albert_graph(50, 3, seed=42)
        fnx_greedy = list(fnx.community.greedy_modularity_communities(G))
        nx_greedy = list(nx.community.greedy_modularity_communities(nxG))
        fnx_sets = set(frozenset(c) for c in fnx_greedy)
        nx_sets = set(frozenset(c) for c in nx_greedy)
        assert fnx_sets == nx_sets


class TestLinkAnalysisParity:
    """Verify link analysis algorithm outputs match NetworkX."""

    def test_eigenvector_centrality(self):
        G = fnx.barabasi_albert_graph(50, 3, seed=42)
        nxG = nx.barabasi_albert_graph(50, 3, seed=42)
        fnx_ec = fnx.eigenvector_centrality(G, max_iter=1000)
        nx_ec = nx.eigenvector_centrality(nxG, max_iter=1000)
        max_diff = max(abs(fnx_ec[n] - nx_ec[n]) for n in fnx_ec)
        assert max_diff < 1e-6

    def test_hits(self):
        G = fnx.barabasi_albert_graph(50, 3, seed=42)
        nxG = nx.barabasi_albert_graph(50, 3, seed=42)
        fnx_hubs, fnx_auth = fnx.hits(G, max_iter=1000)
        nx_hubs, nx_auth = nx.hits(nxG, max_iter=1000)
        max_hub_diff = max(abs(fnx_hubs[n] - nx_hubs[n]) for n in fnx_hubs)
        max_auth_diff = max(abs(fnx_auth[n] - nx_auth[n]) for n in fnx_auth)
        assert max_hub_diff < 1e-6
        assert max_auth_diff < 1e-6


class TestIsomorphismParity:
    """Verify isomorphism algorithm outputs match NetworkX."""

    def test_is_isomorphic_same(self):
        G1 = fnx.cycle_graph(5)
        G2 = fnx.cycle_graph(5)
        nxG1 = nx.cycle_graph(5)
        nxG2 = nx.cycle_graph(5)
        assert fnx.is_isomorphic(G1, G2) == nx.is_isomorphic(nxG1, nxG2)

    def test_is_isomorphic_different(self):
        G1 = fnx.cycle_graph(5)
        G2 = fnx.path_graph(5)
        nxG1 = nx.cycle_graph(5)
        nxG2 = nx.path_graph(5)
        assert fnx.is_isomorphic(G1, G2) == nx.is_isomorphic(nxG1, nxG2)

    def test_graph_edit_distance(self):
        G1 = fnx.path_graph(4)
        G2 = fnx.cycle_graph(4)
        nxG1 = nx.path_graph(4)
        nxG2 = nx.cycle_graph(4)
        assert fnx.graph_edit_distance(G1, G2) == nx.graph_edit_distance(nxG1, nxG2)

    def test_tree_isomorphism(self):
        t1 = fnx.path_graph(5)
        t2 = fnx.path_graph(5)
        nxt1 = nx.path_graph(5)
        nxt2 = nx.path_graph(5)
        fnx_result = fnx.isomorphism.tree_isomorphism(t1, t2)
        nx_result = nx.algorithms.isomorphism.tree_isomorphism(nxt1, nxt2)
        assert set(fnx_result) == set(nx_result)

    def test_tree_isomorphism_non_isomorphic(self):
        t1 = fnx.path_graph(5)
        t2 = fnx.star_graph(4)
        fnx_result = fnx.isomorphism.tree_isomorphism(t1, t2)
        assert fnx_result == []

    def test_rooted_tree_isomorphism(self):
        t1 = fnx.path_graph(5)
        t2 = fnx.path_graph(5)
        nxt1 = nx.path_graph(5)
        nxt2 = nx.path_graph(5)
        fnx_result = fnx.isomorphism.rooted_tree_isomorphism(t1, 0, t2, 0)
        nx_result = nx.algorithms.isomorphism.rooted_tree_isomorphism(nxt1, 0, nxt2, 0)
        assert set(fnx_result) == set(nx_result)


class TestGraphOperationsParity:
    """Verify graph operations match NetworkX."""

    def test_cartesian_product(self):
        G1 = fnx.path_graph(3)
        G2 = fnx.path_graph(2)
        nxG1 = nx.path_graph(3)
        nxG2 = nx.path_graph(2)
        fnx_cart = fnx.cartesian_product(G1, G2)
        nx_cart = nx.cartesian_product(nxG1, nxG2)
        assert sorted(fnx_cart.nodes()) == sorted(nx_cart.nodes())
        assert fnx_cart.number_of_edges() == nx_cart.number_of_edges()

    def test_compose(self):
        G1 = fnx.Graph()
        G1.add_edges_from([(0, 1), (1, 2)])
        G2 = fnx.Graph()
        G2.add_edges_from([(1, 2), (2, 3)])
        nxG1 = nx.Graph()
        nxG1.add_edges_from([(0, 1), (1, 2)])
        nxG2 = nx.Graph()
        nxG2.add_edges_from([(1, 2), (2, 3)])
        fnx_comp = fnx.compose(G1, G2)
        nx_comp = nx.compose(nxG1, nxG2)
        assert sorted(fnx_comp.edges()) == sorted(nx_comp.edges())

    def test_line_graph(self):
        G = fnx.path_graph(4)
        nxG = nx.path_graph(4)
        fnx_line = fnx.line_graph(G)
        nx_line = nx.line_graph(nxG)
        assert sorted(fnx_line.nodes()) == sorted(nx_line.nodes())
        assert sorted(fnx_line.edges()) == sorted(nx_line.edges())

    def test_power_graph(self):
        G = fnx.path_graph(5)
        nxG = nx.path_graph(5)
        fnx_pow = fnx.power(G, 2)
        nx_pow = nx.power(nxG, 2)
        assert sorted(fnx_pow.edges()) == sorted(nx_pow.edges())


class TestDAGParity:
    """Verify DAG algorithm outputs match NetworkX."""

    def test_dag_longest_path(self):
        DG = fnx.DiGraph()
        DG.add_weighted_edges_from([(0, 1, 1), (0, 2, 2), (1, 3, 3), (2, 3, 1)])
        nxDG = nx.DiGraph()
        nxDG.add_weighted_edges_from([(0, 1, 1), (0, 2, 2), (1, 3, 3), (2, 3, 1)])
        fnx_path = fnx.dag_longest_path(DG, weight="weight")
        nx_path = nx.dag_longest_path(nxDG, weight="weight")
        assert fnx_path == nx_path

    def test_dag_longest_path_length(self):
        DG = fnx.DiGraph()
        DG.add_weighted_edges_from([(0, 1, 1), (0, 2, 2), (1, 3, 3), (2, 3, 1)])
        nxDG = nx.DiGraph()
        nxDG.add_weighted_edges_from([(0, 1, 1), (0, 2, 2), (1, 3, 3), (2, 3, 1)])
        fnx_length = fnx.dag_longest_path_length(DG, weight="weight")
        nx_length = nx.dag_longest_path_length(nxDG, weight="weight")
        assert fnx_length == nx_length

    def test_ancestors_descendants(self):
        DG = fnx.DiGraph()
        DG.add_edges_from([(0, 1), (0, 2), (1, 3), (2, 3)])
        nxDG = nx.DiGraph()
        nxDG.add_edges_from([(0, 1), (0, 2), (1, 3), (2, 3)])
        assert fnx.ancestors(DG, 3) == nx.ancestors(nxDG, 3)
        assert fnx.descendants(DG, 0) == nx.descendants(nxDG, 0)

    def test_transitive_closure(self):
        DG = fnx.DiGraph()
        DG.add_edges_from([(0, 1), (1, 2), (2, 3)])
        nxDG = nx.DiGraph()
        nxDG.add_edges_from([(0, 1), (1, 2), (2, 3)])
        fnx_tc = fnx.transitive_closure(DG)
        nx_tc = nx.transitive_closure(nxDG)
        assert sorted(fnx_tc.edges()) == sorted(nx_tc.edges())


class TestConnectivityParity:
    """Verify connectivity algorithm outputs match NetworkX."""

    def test_node_connectivity(self):
        G = fnx.barabasi_albert_graph(50, 3, seed=42)
        nxG = nx.barabasi_albert_graph(50, 3, seed=42)
        assert fnx.node_connectivity(G) == nx.node_connectivity(nxG)

    def test_edge_connectivity(self):
        G = fnx.barabasi_albert_graph(50, 3, seed=42)
        nxG = nx.barabasi_albert_graph(50, 3, seed=42)
        assert fnx.edge_connectivity(G) == nx.edge_connectivity(nxG)

    def test_articulation_points(self):
        G = fnx.Graph()
        G.add_edges_from([(0, 1), (1, 2), (2, 3), (3, 1), (3, 4)])
        nxG = nx.Graph()
        nxG.add_edges_from([(0, 1), (1, 2), (2, 3), (3, 1), (3, 4)])
        assert set(fnx.articulation_points(G)) == set(nx.articulation_points(nxG))

    def test_bridges(self):
        G = fnx.Graph()
        G.add_edges_from([(0, 1), (1, 2), (2, 3), (3, 1), (3, 4)])
        nxG = nx.Graph()
        nxG.add_edges_from([(0, 1), (1, 2), (2, 3), (3, 1), (3, 4)])
        assert set(fnx.bridges(G)) == set(nx.bridges(nxG))


class TestSpanningTreeParity:
    """Verify spanning tree algorithm outputs match NetworkX."""

    def test_minimum_spanning_tree_kruskal(self):
        G = fnx.Graph()
        G.add_weighted_edges_from([(0, 1, 1), (1, 2, 2), (0, 2, 3), (2, 3, 1)])
        nxG = nx.Graph()
        nxG.add_weighted_edges_from([(0, 1, 1), (1, 2, 2), (0, 2, 3), (2, 3, 1)])
        fnx_mst = fnx.minimum_spanning_tree(G, algorithm="kruskal")
        nx_mst = nx.minimum_spanning_tree(nxG, algorithm="kruskal")
        fnx_edges = sorted(tuple(sorted(e)) for e in fnx_mst.edges())
        nx_edges = sorted(tuple(sorted(e)) for e in nx_mst.edges())
        assert fnx_edges == nx_edges

    def test_minimum_spanning_tree_prim(self):
        G = fnx.Graph()
        G.add_weighted_edges_from([(0, 1, 1), (1, 2, 2), (0, 2, 3), (2, 3, 1)])
        nxG = nx.Graph()
        nxG.add_weighted_edges_from([(0, 1, 1), (1, 2, 2), (0, 2, 3), (2, 3, 1)])
        fnx_mst = fnx.minimum_spanning_tree(G, algorithm="prim")
        nx_mst = nx.minimum_spanning_tree(nxG, algorithm="prim")
        fnx_edges = sorted(tuple(sorted(e)) for e in fnx_mst.edges())
        nx_edges = sorted(tuple(sorted(e)) for e in nx_mst.edges())
        assert fnx_edges == nx_edges

    def test_maximum_spanning_tree(self):
        G = fnx.Graph()
        G.add_weighted_edges_from([(0, 1, 1), (1, 2, 2), (0, 2, 3), (2, 3, 1)])
        nxG = nx.Graph()
        nxG.add_weighted_edges_from([(0, 1, 1), (1, 2, 2), (0, 2, 3), (2, 3, 1)])
        fnx_mst = fnx.maximum_spanning_tree(G)
        nx_mst = nx.maximum_spanning_tree(nxG)
        fnx_edges = sorted(tuple(sorted(e)) for e in fnx_mst.edges())
        nx_edges = sorted(tuple(sorted(e)) for e in nx_mst.edges())
        assert fnx_edges == nx_edges


class TestMetricsParity:
    """Verify graph metrics match NetworkX."""

    def test_average_clustering(self):
        G = fnx.barabasi_albert_graph(100, 3, seed=42)
        nxG = nx.barabasi_albert_graph(100, 3, seed=42)
        assert abs(fnx.average_clustering(G) - nx.average_clustering(nxG)) < 1e-10

    def test_average_shortest_path_length(self):
        G = fnx.path_graph(10)
        nxG = nx.path_graph(10)
        fnx_aspl = fnx.average_shortest_path_length(G)
        nx_aspl = nx.average_shortest_path_length(nxG)
        assert abs(fnx_aspl - nx_aspl) < 1e-10

    def test_wiener_index(self):
        G = fnx.path_graph(10)
        nxG = nx.path_graph(10)
        assert fnx.wiener_index(G) == nx.wiener_index(nxG)

    def test_global_efficiency(self):
        G = fnx.barabasi_albert_graph(50, 3, seed=42)
        nxG = nx.barabasi_albert_graph(50, 3, seed=42)
        assert abs(fnx.global_efficiency(G) - nx.global_efficiency(nxG)) < 1e-10

    def test_local_efficiency(self):
        G = fnx.barabasi_albert_graph(50, 3, seed=42)
        nxG = nx.barabasi_albert_graph(50, 3, seed=42)
        assert abs(fnx.local_efficiency(G) - nx.local_efficiency(nxG)) < 1e-10


class TestTriadsParity:
    """Verify triad algorithm outputs match NetworkX."""

    def test_triadic_census(self):
        DG = fnx.DiGraph()
        DG.add_edges_from([(0, 1), (1, 2), (2, 0), (0, 2)])
        nxDG = nx.DiGraph()
        nxDG.add_edges_from([(0, 1), (1, 2), (2, 0), (0, 2)])
        assert fnx.triadic_census(DG) == nx.triadic_census(nxDG)

    def test_transitivity_digraph(self):
        DG = fnx.DiGraph()
        DG.add_edges_from([(0, 1), (1, 2), (0, 2), (2, 3)])
        nxDG = nx.DiGraph()
        nxDG.add_edges_from([(0, 1), (1, 2), (0, 2), (2, 3)])
        assert abs(fnx.transitivity(DG) - nx.transitivity(nxDG)) < 1e-10


class TestTreeAlgorithmsParity:
    """Verify tree algorithm outputs match NetworkX."""

    def test_is_tree(self):
        T = fnx.path_graph(5)
        nxT = nx.path_graph(5)
        assert fnx.is_tree(T) == nx.is_tree(nxT)

    def test_is_forest(self):
        F = fnx.Graph()
        F.add_edges_from([(0, 1), (2, 3)])
        nxF = nx.Graph()
        nxF.add_edges_from([(0, 1), (2, 3)])
        assert fnx.is_forest(F) == nx.is_forest(nxF)

    def test_to_prufer_sequence(self):
        T = fnx.random_labeled_tree(10, seed=42)
        nxT = nx.random_labeled_tree(10, seed=42)
        assert fnx.to_prufer_sequence(T) == nx.to_prufer_sequence(nxT)

    def test_from_prufer_sequence(self):
        seq = [1, 0, 4, 3, 3, 2, 1, 8]
        fnx_tree = fnx.from_prufer_sequence(seq)
        nx_tree = nx.from_prufer_sequence(seq)
        fnx_edges = sorted(tuple(sorted(e)) for e in fnx_tree.edges())
        nx_edges = sorted(tuple(sorted(e)) for e in nx_tree.edges())
        assert fnx_edges == nx_edges


class TestFlowParity:
    """Verify flow algorithm outputs match NetworkX."""

    def test_maximum_flow(self):
        DG = fnx.DiGraph()
        DG.add_edge(0, 1, capacity=10)
        DG.add_edge(0, 2, capacity=10)
        DG.add_edge(1, 3, capacity=4)
        DG.add_edge(2, 3, capacity=8)
        DG.add_edge(3, 4, capacity=10)
        nxDG = nx.DiGraph()
        nxDG.add_edge(0, 1, capacity=10)
        nxDG.add_edge(0, 2, capacity=10)
        nxDG.add_edge(1, 3, capacity=4)
        nxDG.add_edge(2, 3, capacity=8)
        nxDG.add_edge(3, 4, capacity=10)
        fnx_flow, _ = fnx.maximum_flow(DG, 0, 4)
        nx_flow, _ = nx.maximum_flow(nxDG, 0, 4)
        assert fnx_flow == nx_flow

    def test_minimum_cut(self):
        DG = fnx.DiGraph()
        DG.add_edge(0, 1, capacity=10)
        DG.add_edge(0, 2, capacity=10)
        DG.add_edge(1, 3, capacity=4)
        DG.add_edge(2, 3, capacity=8)
        DG.add_edge(3, 4, capacity=10)
        nxDG = nx.DiGraph()
        nxDG.add_edge(0, 1, capacity=10)
        nxDG.add_edge(0, 2, capacity=10)
        nxDG.add_edge(1, 3, capacity=4)
        nxDG.add_edge(2, 3, capacity=8)
        nxDG.add_edge(3, 4, capacity=10)
        fnx_cut, _ = fnx.minimum_cut(DG, 0, 4)
        nx_cut, _ = nx.minimum_cut(nxDG, 0, 4)
        assert fnx_cut == nx_cut


class TestLinkPredictionParity:
    """Verify link prediction algorithm outputs match NetworkX."""

    def test_jaccard_coefficient(self):
        G = fnx.Graph()
        G.add_edges_from([(0, 1), (0, 2), (1, 2), (1, 3), (2, 3)])
        nxG = nx.Graph()
        nxG.add_edges_from([(0, 1), (0, 2), (1, 2), (1, 3), (2, 3)])
        fnx_jc = list(fnx.jaccard_coefficient(G, [(0, 3)]))
        nx_jc = list(nx.jaccard_coefficient(nxG, [(0, 3)]))
        assert fnx_jc == nx_jc

    def test_adamic_adar_index(self):
        G = fnx.Graph()
        G.add_edges_from([(0, 1), (0, 2), (1, 2), (1, 3), (2, 3)])
        nxG = nx.Graph()
        nxG.add_edges_from([(0, 1), (0, 2), (1, 2), (1, 3), (2, 3)])
        fnx_aa = list(fnx.adamic_adar_index(G, [(0, 3)]))
        nx_aa = list(nx.adamic_adar_index(nxG, [(0, 3)]))
        assert abs(fnx_aa[0][2] - nx_aa[0][2]) < 1e-10


class TestApproximationParity:
    """Verify approximation algorithm outputs match NetworkX."""

    def test_large_clique_size(self):
        G = fnx.barabasi_albert_graph(50, 3, seed=42)
        nxG = nx.barabasi_albert_graph(50, 3, seed=42)
        assert fnx.approximation.large_clique_size(G) == nx.approximation.large_clique_size(nxG)

    def test_average_clustering_approx(self):
        G = fnx.barabasi_albert_graph(50, 3, seed=42)
        nxG = nx.barabasi_albert_graph(50, 3, seed=42)
        fnx_ac = fnx.approximation.average_clustering(G, seed=42)
        nx_ac = nx.approximation.average_clustering(nxG, seed=42)
        assert abs(fnx_ac - nx_ac) < 1e-10

    def test_min_weighted_vertex_cover(self):
        G = fnx.Graph()
        G.add_edges_from([(0, 1), (1, 2), (2, 3), (0, 3)])
        nxG = nx.Graph()
        nxG.add_edges_from([(0, 1), (1, 2), (2, 3), (0, 3)])
        fnx_cover = fnx.approximation.min_weighted_vertex_cover(G)
        nx_cover = nx.approximation.min_weighted_vertex_cover(nxG)
        assert fnx_cover == nx_cover


class TestCutsParity:
    """Verify cut algorithm outputs match NetworkX."""

    def test_minimum_node_cut(self):
        G = fnx.Graph()
        G.add_edges_from([(0, 1), (1, 2), (2, 3), (0, 3), (0, 2)])
        nxG = nx.Graph()
        nxG.add_edges_from([(0, 1), (1, 2), (2, 3), (0, 3), (0, 2)])
        assert fnx.minimum_node_cut(G) == nx.minimum_node_cut(nxG)

    def test_minimum_edge_cut(self):
        G = fnx.Graph()
        G.add_edges_from([(0, 1), (1, 2), (2, 3), (0, 3), (0, 2)])
        nxG = nx.Graph()
        nxG.add_edges_from([(0, 1), (1, 2), (2, 3), (0, 3), (0, 2)])
        fnx_cut = {tuple(sorted(e)) for e in fnx.minimum_edge_cut(G)}
        nx_cut = {tuple(sorted(e)) for e in nx.minimum_edge_cut(nxG)}
        assert len(fnx_cut) == len(nx_cut)


class TestCyclesParity:
    """Verify cycle algorithm outputs match NetworkX."""

    def test_simple_cycles(self):
        DG = fnx.DiGraph()
        DG.add_edges_from([(0, 1), (1, 2), (2, 0), (2, 3), (3, 1)])
        nxDG = nx.DiGraph()
        nxDG.add_edges_from([(0, 1), (1, 2), (2, 0), (2, 3), (3, 1)])
        fnx_cycles = sorted([tuple(c) for c in fnx.simple_cycles(DG)])
        nx_cycles = sorted([tuple(c) for c in nx.simple_cycles(nxDG)])
        assert fnx_cycles == nx_cycles

    def test_find_cycle(self):
        G = fnx.cycle_graph(5)
        nxG = nx.cycle_graph(5)
        fnx_cycle = fnx.find_cycle(G)
        nx_cycle = nx.find_cycle(nxG)
        assert len(fnx_cycle) == len(nx_cycle)


class TestBipartiteParity:
    """Verify bipartite algorithm outputs match NetworkX."""

    def test_is_bipartite(self):
        G = fnx.complete_bipartite_graph(3, 4)
        nxG = nx.complete_bipartite_graph(3, 4)
        assert fnx.is_bipartite(G) == nx.is_bipartite(nxG) == True

        # triangle is not bipartite
        G2 = fnx.cycle_graph(3)
        nxG2 = nx.cycle_graph(3)
        assert fnx.is_bipartite(G2) == nx.is_bipartite(nxG2) == False

    def test_bipartite_sets(self):
        G = fnx.complete_bipartite_graph(3, 4)
        nxG = nx.complete_bipartite_graph(3, 4)
        fnx_top, fnx_bottom = fnx.bipartite.sets(G)
        nx_top, nx_bottom = nx.bipartite.sets(nxG)
        assert len(fnx_top) == len(nx_top)
        assert len(fnx_bottom) == len(nx_bottom)

    def test_bipartite_density(self):
        G = fnx.complete_bipartite_graph(3, 4)
        nxG = nx.complete_bipartite_graph(3, 4)
        fnx_top, _ = fnx.bipartite.sets(G)
        nx_top, _ = nx.bipartite.sets(nxG)
        fnx_d = fnx.bipartite.density(G, fnx_top)
        nx_d = nx.bipartite.density(nxG, nx_top)
        assert abs(fnx_d - nx_d) < 1e-10

    def test_bipartite_clustering(self):
        G = fnx.complete_bipartite_graph(3, 4)
        nxG = nx.complete_bipartite_graph(3, 4)
        fnx_c = fnx.bipartite.clustering(G)
        nx_c = nx.bipartite.clustering(nxG)
        for n in fnx_c:
            assert abs(fnx_c[n] - nx_c[n]) < 1e-10


class TestTraversalParity:
    """Verify traversal algorithm outputs match NetworkX."""

    def test_bfs_edges(self):
        G = fnx.balanced_tree(2, 3)
        nxG = nx.balanced_tree(2, 3)
        fnx_edges = list(fnx.bfs_edges(G, 0))
        nx_edges = list(nx.bfs_edges(nxG, 0))
        assert fnx_edges == nx_edges

    def test_bfs_tree(self):
        G = fnx.barabasi_albert_graph(20, 2, seed=42)
        nxG = nx.barabasi_albert_graph(20, 2, seed=42)
        fnx_tree = fnx.bfs_tree(G, 0)
        nx_tree = nx.bfs_tree(nxG, 0)
        assert set(fnx_tree.edges()) == set(nx_tree.edges())

    def test_dfs_edges(self):
        G = fnx.balanced_tree(2, 3)
        nxG = nx.balanced_tree(2, 3)
        fnx_edges = list(fnx.dfs_edges(G, 0))
        nx_edges = list(nx.dfs_edges(nxG, 0))
        assert fnx_edges == nx_edges

    def test_dfs_preorder_nodes(self):
        G = fnx.balanced_tree(2, 3)
        nxG = nx.balanced_tree(2, 3)
        fnx_nodes = list(fnx.dfs_preorder_nodes(G, 0))
        nx_nodes = list(nx.dfs_preorder_nodes(nxG, 0))
        assert fnx_nodes == nx_nodes

    def test_dfs_postorder_nodes(self):
        G = fnx.balanced_tree(2, 3)
        nxG = nx.balanced_tree(2, 3)
        fnx_nodes = list(fnx.dfs_postorder_nodes(G, 0))
        nx_nodes = list(nx.dfs_postorder_nodes(nxG, 0))
        assert fnx_nodes == nx_nodes


class TestColoringParity:
    """Verify graph coloring outputs match NetworkX."""

    def test_greedy_color_petersen(self):
        G = fnx.petersen_graph()
        nxG = nx.petersen_graph()
        fnx_col = fnx.greedy_color(G)
        nx_col = nx.greedy_color(nxG)
        assert max(fnx_col.values()) + 1 == max(nx_col.values()) + 1

    def test_greedy_color_cycle(self):
        G = fnx.cycle_graph(6)
        nxG = nx.cycle_graph(6)
        fnx_col = fnx.greedy_color(G)
        nx_col = nx.greedy_color(nxG)
        fnx_num_colors = len(set(fnx_col.values()))
        nx_num_colors = len(set(nx_col.values()))
        assert fnx_num_colors == nx_num_colors

    def test_equitable_color(self):
        G = fnx.complete_graph(4)
        nxG = nx.complete_graph(4)
        fnx_col = fnx.equitable_color(G, 4)
        nx_col = nx.equitable_color(nxG, 4)
        assert len(set(fnx_col.values())) == len(set(nx_col.values()))


class TestPlanarityParity:
    """Verify planarity algorithm outputs match NetworkX."""

    def test_is_planar_k4(self):
        G = fnx.complete_graph(4)
        nxG = nx.complete_graph(4)
        assert fnx.is_planar(G) == nx.is_planar(nxG) == True

    def test_is_planar_k5(self):
        G = fnx.complete_graph(5)
        nxG = nx.complete_graph(5)
        assert fnx.is_planar(G) == nx.is_planar(nxG) == False

    def test_is_planar_k33(self):
        G = fnx.complete_bipartite_graph(3, 3)
        nxG = nx.complete_bipartite_graph(3, 3)
        assert fnx.is_planar(G) == nx.is_planar(nxG) == False

    def test_check_planarity_petersen(self):
        G = fnx.petersen_graph()
        nxG = nx.petersen_graph()
        fnx_planar, _ = fnx.check_planarity(G)
        nx_planar, _ = nx.check_planarity(nxG)
        assert fnx_planar == nx_planar == False


class TestDominanceParity:
    """Verify dominance algorithm outputs match NetworkX."""

    def test_dominating_set(self):
        G = fnx.path_graph(10)
        nxG = nx.path_graph(10)
        fnx_ds = fnx.dominating_set(G)
        nx_ds = nx.dominating_set(nxG)
        # verify both are valid dominating sets (not necessarily same)
        assert fnx.is_dominating_set(G, fnx_ds)
        assert nx.is_dominating_set(nxG, nx_ds)

    def test_is_dominating_set(self):
        G = fnx.path_graph(5)
        nxG = nx.path_graph(5)
        dom = {1, 3}
        assert fnx.is_dominating_set(G, dom) == nx.is_dominating_set(nxG, dom)
        non_dom = {0}
        assert fnx.is_dominating_set(G, non_dom) == nx.is_dominating_set(nxG, non_dom)

    def test_immediate_dominators(self):
        DG = fnx.DiGraph()
        DG.add_edges_from([(0, 1), (0, 2), (1, 3), (2, 3), (3, 4)])
        nxDG = nx.DiGraph()
        nxDG.add_edges_from([(0, 1), (0, 2), (1, 3), (2, 3), (3, 4)])
        fnx_idom = fnx.immediate_dominators(DG, 0)
        nx_idom = nx.immediate_dominators(nxDG, 0)
        assert fnx_idom == nx_idom


class TestEulerianParity:
    """Verify Eulerian algorithm outputs match NetworkX."""

    def test_is_eulerian(self):
        G = fnx.cycle_graph(5)
        nxG = nx.cycle_graph(5)
        assert fnx.is_eulerian(G) == nx.is_eulerian(nxG) == True

        # Complete graph K4 is not Eulerian (odd degree vertices)
        G2 = fnx.complete_graph(4)
        nxG2 = nx.complete_graph(4)
        assert fnx.is_eulerian(G2) == nx.is_eulerian(nxG2) == False

    def test_has_eulerian_path(self):
        G = fnx.path_graph(5)
        nxG = nx.path_graph(5)
        assert fnx.has_eulerian_path(G) == nx.has_eulerian_path(nxG) == True

    def test_is_semieulerian(self):
        G = fnx.path_graph(5)
        nxG = nx.path_graph(5)
        assert fnx.is_semieulerian(G) == nx.is_semieulerian(nxG) == True

    def test_eulerian_circuit(self):
        G = fnx.cycle_graph(6)
        nxG = nx.cycle_graph(6)
        fnx_circuit = list(fnx.eulerian_circuit(G))
        nx_circuit = list(nx.eulerian_circuit(nxG))
        assert len(fnx_circuit) == len(nx_circuit) == 6


class TestCliqueParity:
    """Verify clique algorithm outputs match NetworkX."""

    def test_enumerate_all_cliques(self):
        G = fnx.complete_graph(4)
        nxG = nx.complete_graph(4)
        fnx_cliques = sorted([tuple(sorted(c)) for c in fnx.enumerate_all_cliques(G)])
        nx_cliques = sorted([tuple(sorted(c)) for c in nx.enumerate_all_cliques(nxG)])
        assert fnx_cliques == nx_cliques

    def test_find_cliques(self):
        G = fnx.Graph()
        G.add_edges_from([(0, 1), (0, 2), (1, 2), (2, 3)])
        nxG = nx.Graph()
        nxG.add_edges_from([(0, 1), (0, 2), (1, 2), (2, 3)])
        fnx_cliques = sorted([tuple(sorted(c)) for c in fnx.find_cliques(G)])
        nx_cliques = sorted([tuple(sorted(c)) for c in nx.find_cliques(nxG)])
        assert fnx_cliques == nx_cliques

    def test_node_clique_number(self):
        G = fnx.complete_graph(5)
        nxG = nx.complete_graph(5)
        fnx_cn = fnx.node_clique_number(G)
        nx_cn = nx.node_clique_number(nxG)
        assert fnx_cn == nx_cn


class TestChordalParity:
    """Verify chordal algorithm outputs match NetworkX."""

    def test_is_chordal_cycle(self):
        G = fnx.cycle_graph(5)
        nxG = nx.cycle_graph(5)
        assert fnx.is_chordal(G) == nx.is_chordal(nxG) == False

    def test_is_chordal_complete(self):
        G = fnx.complete_graph(5)
        nxG = nx.complete_graph(5)
        assert fnx.is_chordal(G) == nx.is_chordal(nxG) == True

    def test_chordal_graph_cliques(self):
        G = fnx.complete_graph(4)
        nxG = nx.complete_graph(4)
        fnx_cliques = list(fnx.chordal_graph_cliques(G))
        nx_cliques = list(nx.chordal_graph_cliques(nxG))
        assert len(fnx_cliques) == len(nx_cliques)


class TestDegreeParity:
    """Verify degree-related algorithm outputs match NetworkX."""

    def test_degree_histogram(self):
        G = fnx.barabasi_albert_graph(50, 3, seed=42)
        nxG = nx.barabasi_albert_graph(50, 3, seed=42)
        fnx_hist = fnx.degree_histogram(G)
        nx_hist = nx.degree_histogram(nxG)
        assert fnx_hist == nx_hist

    def test_is_regular(self):
        G = fnx.cycle_graph(6)
        nxG = nx.cycle_graph(6)
        assert fnx.is_regular(G) == nx.is_regular(nxG) == True

        G2 = fnx.path_graph(5)
        nxG2 = nx.path_graph(5)
        assert fnx.is_regular(G2) == nx.is_regular(nxG2) == False

    def test_is_k_regular(self):
        G = fnx.cycle_graph(6)
        nxG = nx.cycle_graph(6)
        assert fnx.is_k_regular(G, 2) == nx.is_k_regular(nxG, 2) == True
        assert fnx.is_k_regular(G, 3) == nx.is_k_regular(nxG, 3) == False

    def test_degree_centrality(self):
        G = fnx.complete_graph(5)
        nxG = nx.complete_graph(5)
        fnx_dc = fnx.degree_centrality(G)
        nx_dc = nx.degree_centrality(nxG)
        for n in fnx_dc:
            assert abs(fnx_dc[n] - nx_dc[n]) < 1e-10

    def test_average_neighbor_degree(self):
        G = fnx.barabasi_albert_graph(30, 2, seed=42)
        nxG = nx.barabasi_albert_graph(30, 2, seed=42)
        fnx_and = fnx.average_neighbor_degree(G)
        nx_and = nx.average_neighbor_degree(nxG)
        for n in fnx_and:
            assert abs(fnx_and[n] - nx_and[n]) < 1e-10


class TestBoundaryParity:
    """Verify boundary algorithm outputs match NetworkX."""

    def test_node_boundary(self):
        G = fnx.complete_bipartite_graph(3, 4)
        nxG = nx.complete_bipartite_graph(3, 4)
        fnx_nb = set(fnx.node_boundary(G, [0, 1, 2]))
        nx_nb = set(nx.node_boundary(nxG, [0, 1, 2]))
        assert fnx_nb == nx_nb

    def test_edge_boundary(self):
        G = fnx.complete_bipartite_graph(3, 4)
        nxG = nx.complete_bipartite_graph(3, 4)
        fnx_eb = set(fnx.edge_boundary(G, [0, 1, 2]))
        nx_eb = set(nx.edge_boundary(nxG, [0, 1, 2]))
        assert fnx_eb == nx_eb


class TestWienerParity:
    """Verify Wiener index outputs match NetworkX."""

    def test_wiener_index_path(self):
        G = fnx.path_graph(10)
        nxG = nx.path_graph(10)
        fnx_wi = fnx.wiener_index(G)
        nx_wi = nx.wiener_index(nxG)
        assert fnx_wi == nx_wi

    def test_wiener_index_cycle(self):
        G = fnx.cycle_graph(10)
        nxG = nx.cycle_graph(10)
        fnx_wi = fnx.wiener_index(G)
        nx_wi = nx.wiener_index(nxG)
        assert fnx_wi == nx_wi


class TestReciprocityParity:
    """Verify reciprocity outputs match NetworkX."""

    def test_overall_reciprocity(self):
        DG = fnx.DiGraph()
        DG.add_edges_from([(0, 1), (1, 0), (1, 2), (2, 3), (3, 2)])
        nxDG = nx.DiGraph()
        nxDG.add_edges_from([(0, 1), (1, 0), (1, 2), (2, 3), (3, 2)])
        fnx_r = fnx.overall_reciprocity(DG)
        nx_r = nx.overall_reciprocity(nxDG)
        assert abs(fnx_r - nx_r) < 1e-10

    def test_reciprocity(self):
        DG = fnx.DiGraph()
        DG.add_edges_from([(0, 1), (1, 0), (1, 2), (2, 3), (3, 2)])
        nxDG = nx.DiGraph()
        nxDG.add_edges_from([(0, 1), (1, 0), (1, 2), (2, 3), (3, 2)])
        fnx_r = fnx.reciprocity(DG, [0, 1])
        nx_r = nx.reciprocity(nxDG, [0, 1])
        assert fnx_r == nx_r


class TestCoreParity:
    """Verify k-core outputs match NetworkX."""

    def test_core_number(self):
        G = fnx.barabasi_albert_graph(30, 3, seed=42)
        nxG = nx.barabasi_albert_graph(30, 3, seed=42)
        fnx_cn = fnx.core_number(G)
        nx_cn = nx.core_number(nxG)
        assert fnx_cn == nx_cn

    def test_k_core(self):
        G = fnx.barabasi_albert_graph(30, 3, seed=42)
        nxG = nx.barabasi_albert_graph(30, 3, seed=42)
        fnx_kc = fnx.k_core(G, k=2)
        nx_kc = nx.k_core(nxG, k=2)
        assert set(fnx_kc.nodes()) == set(nx_kc.nodes())


class TestBridgeParity:
    """Verify bridge algorithm outputs match NetworkX."""

    def test_bridges(self):
        G = fnx.path_graph(5)
        nxG = nx.path_graph(5)
        fnx_bridges = set(fnx.bridges(G))
        nx_bridges = set(nx.bridges(nxG))
        assert fnx_bridges == nx_bridges

    def test_has_bridges(self):
        G = fnx.path_graph(5)
        nxG = nx.path_graph(5)
        assert fnx.has_bridges(G) == nx.has_bridges(nxG) == True

        G2 = fnx.cycle_graph(5)
        nxG2 = nx.cycle_graph(5)
        assert fnx.has_bridges(G2) == nx.has_bridges(nxG2) == False

    def test_local_bridges(self):
        G = fnx.ladder_graph(5)
        nxG = nx.ladder_graph(5)
        fnx_lb = list(fnx.local_bridges(G))
        nx_lb = list(nx.local_bridges(nxG))
        # Just verify counts match since order may differ
        assert len(fnx_lb) == len(nx_lb)


class TestArticulationParity:
    """Verify articulation point outputs match NetworkX."""

    def test_articulation_points_path(self):
        G = fnx.path_graph(5)
        nxG = nx.path_graph(5)
        fnx_ap = set(fnx.articulation_points(G))
        nx_ap = set(nx.articulation_points(nxG))
        assert fnx_ap == nx_ap

    def test_articulation_points_ladder(self):
        G = fnx.ladder_graph(5)
        nxG = nx.ladder_graph(5)
        fnx_ap = set(fnx.articulation_points(G))
        nx_ap = set(nx.articulation_points(nxG))
        assert fnx_ap == nx_ap


class TestRichClubParity:
    """Verify rich club coefficient outputs match NetworkX."""

    def test_rich_club_coefficient(self):
        G = fnx.barabasi_albert_graph(30, 2, seed=42)
        nxG = nx.barabasi_albert_graph(30, 2, seed=42)
        fnx_rc = fnx.rich_club_coefficient(G, normalized=False)
        nx_rc = nx.rich_club_coefficient(nxG, normalized=False)
        for k in fnx_rc:
            if k in nx_rc:
                assert abs(fnx_rc[k] - nx_rc[k]) < 1e-10


class TestSMetricParity:
    """Verify s-metric outputs match NetworkX."""

    def test_s_metric(self):
        G = fnx.barabasi_albert_graph(30, 2, seed=42)
        nxG = nx.barabasi_albert_graph(30, 2, seed=42)
        fnx_s = fnx.s_metric(G)
        nx_s = nx.s_metric(nxG)
        assert abs(fnx_s - nx_s) < 1e-10


class TestTournamentParity:
    """Verify tournament algorithm outputs match NetworkX."""

    def test_is_tournament(self):
        # A tournament: complete digraph with no symmetric edges
        DG = fnx.DiGraph()
        DG.add_edges_from([(0, 1), (0, 2), (1, 2)])
        nxDG = nx.DiGraph()
        nxDG.add_edges_from([(0, 1), (0, 2), (1, 2)])
        assert fnx.is_tournament(DG) == nx.is_tournament(nxDG) == True

        # Not a tournament
        DG2 = fnx.DiGraph()
        DG2.add_edges_from([(0, 1), (0, 2)])
        nxDG2 = nx.DiGraph()
        nxDG2.add_edges_from([(0, 1), (0, 2)])
        assert fnx.is_tournament(DG2) == nx.is_tournament(nxDG2) == False


class TestAssortativityParity:
    """Verify assortativity outputs match NetworkX."""

    def test_degree_assortativity_coefficient(self):
        G = fnx.barabasi_albert_graph(50, 3, seed=42)
        nxG = nx.barabasi_albert_graph(50, 3, seed=42)
        fnx_ac = fnx.degree_assortativity_coefficient(G)
        nx_ac = nx.degree_assortativity_coefficient(nxG)
        assert abs(fnx_ac - nx_ac) < 1e-10

    def test_attribute_assortativity_coefficient(self):
        G = fnx.Graph()
        G.add_nodes_from([(0, {"color": "red"}), (1, {"color": "blue"}),
                          (2, {"color": "red"}), (3, {"color": "blue"})])
        G.add_edges_from([(0, 2), (1, 3), (0, 1)])
        nxG = nx.Graph()
        nxG.add_nodes_from([(0, {"color": "red"}), (1, {"color": "blue"}),
                            (2, {"color": "red"}), (3, {"color": "blue"})])
        nxG.add_edges_from([(0, 2), (1, 3), (0, 1)])
        fnx_ac = fnx.attribute_assortativity_coefficient(G, "color")
        nx_ac = nx.attribute_assortativity_coefficient(nxG, "color")
        assert abs(fnx_ac - nx_ac) < 1e-10


class TestVitalityParity:
    """Verify vitality algorithm outputs match NetworkX."""

    def test_closeness_vitality(self):
        G = fnx.cycle_graph(6)
        nxG = nx.cycle_graph(6)
        fnx_cv = fnx.closeness_vitality(G)
        nx_cv = nx.closeness_vitality(nxG)
        for n in fnx_cv:
            if math.isfinite(fnx_cv[n]) and math.isfinite(nx_cv[n]):
                assert abs(fnx_cv[n] - nx_cv[n]) < 1e-10
            else:
                assert fnx_cv[n] == nx_cv[n]


class TestVoronoiParity:
    """Verify Voronoi algorithm outputs match NetworkX."""

    def test_voronoi_cells(self):
        G = fnx.cycle_graph(10)
        nxG = nx.cycle_graph(10)
        fnx_vc = fnx.voronoi_cells(G, {0, 5})
        nx_vc = nx.voronoi_cells(nxG, {0, 5})
        for center in fnx_vc:
            assert fnx_vc[center] == nx_vc[center]


class TestEffectiveSizeParity:
    """Verify effective size outputs match NetworkX."""

    def test_effective_size(self):
        G = fnx.barabasi_albert_graph(20, 2, seed=42)
        nxG = nx.barabasi_albert_graph(20, 2, seed=42)
        fnx_es = fnx.effective_size(G)
        nx_es = nx.effective_size(nxG)
        for n in fnx_es:
            assert abs(fnx_es[n] - nx_es[n]) < 1e-10


class TestDistanceMeasuresParity:
    """Verify distance measure outputs match NetworkX."""

    def test_eccentricity(self):
        G = fnx.path_graph(10)
        nxG = nx.path_graph(10)
        fnx_e = fnx.eccentricity(G)
        nx_e = nx.eccentricity(nxG)
        assert fnx_e == nx_e

    def test_diameter(self):
        G = fnx.path_graph(10)
        nxG = nx.path_graph(10)
        assert fnx.diameter(G) == nx.diameter(nxG)

    def test_radius(self):
        G = fnx.path_graph(10)
        nxG = nx.path_graph(10)
        assert fnx.radius(G) == nx.radius(nxG)

    def test_center(self):
        G = fnx.path_graph(10)
        nxG = nx.path_graph(10)
        fnx_c = fnx.center(G)
        nx_c = nx.center(nxG)
        assert fnx_c == nx_c

    def test_periphery(self):
        G = fnx.path_graph(10)
        nxG = nx.path_graph(10)
        fnx_p = fnx.periphery(G)
        nx_p = nx.periphery(nxG)
        assert fnx_p == nx_p


class TestResistanceDistanceParity:
    """Verify resistance distance outputs match NetworkX."""

    def test_resistance_distance(self):
        G = fnx.cycle_graph(6)
        nxG = nx.cycle_graph(6)
        fnx_rd = fnx.resistance_distance(G, 0, 3)
        nx_rd = nx.resistance_distance(nxG, 0, 3)
        assert abs(fnx_rd - nx_rd) < 1e-10


class TestAncestorsParity:
    """Verify ancestor algorithm outputs match NetworkX."""

    def test_ancestors(self):
        DG = fnx.DiGraph()
        DG.add_edges_from([(0, 1), (0, 2), (1, 3), (2, 3), (3, 4)])
        nxDG = nx.DiGraph()
        nxDG.add_edges_from([(0, 1), (0, 2), (1, 3), (2, 3), (3, 4)])
        fnx_anc = fnx.ancestors(DG, 4)
        nx_anc = nx.ancestors(nxDG, 4)
        assert fnx_anc == nx_anc

    def test_descendants(self):
        DG = fnx.DiGraph()
        DG.add_edges_from([(0, 1), (0, 2), (1, 3), (2, 3), (3, 4)])
        nxDG = nx.DiGraph()
        nxDG.add_edges_from([(0, 1), (0, 2), (1, 3), (2, 3), (3, 4)])
        fnx_desc = fnx.descendants(DG, 0)
        nx_desc = nx.descendants(nxDG, 0)
        assert fnx_desc == nx_desc


class TestComplementParity:
    """Verify complement outputs match NetworkX."""

    def test_complement(self):
        G = fnx.path_graph(5)
        nxG = nx.path_graph(5)
        fnx_c = fnx.complement(G)
        nx_c = nx.complement(nxG)
        assert set(fnx_c.edges()) == set(nx_c.edges())


class TestUnionIntersectionParity:
    """Verify union and intersection outputs match NetworkX."""

    def test_union(self):
        G1 = fnx.path_graph(3)
        G2 = fnx.path_graph(3)
        nxG1 = nx.path_graph(3)
        nxG2 = nx.path_graph(3)
        fnx_u = fnx.union(G1, G2, rename=("G1", "G2"))
        nx_u = nx.union(nxG1, nxG2, rename=("G1", "G2"))
        assert set(fnx_u.nodes()) == set(nx_u.nodes())
        assert set(fnx_u.edges()) == set(nx_u.edges())

    def test_intersection(self):
        G1 = fnx.complete_graph(5)
        G2 = fnx.cycle_graph(5)
        nxG1 = nx.complete_graph(5)
        nxG2 = nx.cycle_graph(5)
        fnx_i = fnx.intersection(G1, G2)
        nx_i = nx.intersection(nxG1, nxG2)
        assert set(fnx_i.nodes()) == set(nx_i.nodes())
        assert set(fnx_i.edges()) == set(nx_i.edges())

    def test_disjoint_union(self):
        G1 = fnx.path_graph(3)
        G2 = fnx.path_graph(3)
        nxG1 = nx.path_graph(3)
        nxG2 = nx.path_graph(3)
        fnx_du = fnx.disjoint_union(G1, G2)
        nx_du = nx.disjoint_union(nxG1, nxG2)
        assert fnx_du.number_of_nodes() == nx_du.number_of_nodes()
        assert fnx_du.number_of_edges() == nx_du.number_of_edges()


class TestMoralGraphParity:
    """Verify moral graph outputs match NetworkX."""

    def test_moral_graph(self):
        DG = fnx.DiGraph()
        DG.add_edges_from([(0, 2), (1, 2), (2, 3)])
        nxDG = nx.DiGraph()
        nxDG.add_edges_from([(0, 2), (1, 2), (2, 3)])
        fnx_mg = fnx.moral_graph(DG)
        nx_mg = nx.moral_graph(nxDG)
        fnx_edges = set(tuple(sorted(e)) for e in fnx_mg.edges())
        nx_edges = set(tuple(sorted(e)) for e in nx_mg.edges())
        assert fnx_edges == nx_edges


class TestBiconnectedParity:
    """Verify biconnected algorithm outputs match NetworkX."""

    def test_is_biconnected_cycle(self):
        G = fnx.cycle_graph(5)
        nxG = nx.cycle_graph(5)
        assert fnx.is_biconnected(G) == nx.is_biconnected(nxG) == True

    def test_is_biconnected_path(self):
        G = fnx.path_graph(5)
        nxG = nx.path_graph(5)
        assert fnx.is_biconnected(G) == nx.is_biconnected(nxG) == False

    def test_biconnected_components(self):
        G = fnx.cycle_graph(5)
        nxG = nx.cycle_graph(5)
        fnx_bc = list(fnx.biconnected_components(G))
        nx_bc = list(nx.biconnected_components(nxG))
        assert len(fnx_bc) == len(nx_bc)


class TestTransitivityParity:
    """Verify transitivity outputs match NetworkX."""

    def test_transitivity(self):
        G = fnx.complete_graph(5)
        nxG = nx.complete_graph(5)
        fnx_t = fnx.transitivity(G)
        nx_t = nx.transitivity(nxG)
        assert abs(fnx_t - nx_t) < 1e-10

    def test_transitive_closure(self):
        DG = fnx.DiGraph()
        DG.add_edges_from([(0, 1), (1, 2), (2, 3)])
        nxDG = nx.DiGraph()
        nxDG.add_edges_from([(0, 1), (1, 2), (2, 3)])
        fnx_tc = fnx.transitive_closure(DG)
        nx_tc = nx.transitive_closure(nxDG)
        assert set(fnx_tc.edges()) == set(nx_tc.edges())


class TestDensityParity:
    """Verify density outputs match NetworkX."""

    def test_density_complete(self):
        G = fnx.complete_graph(10)
        nxG = nx.complete_graph(10)
        assert abs(fnx.density(G) - nx.density(nxG)) < 1e-10

    def test_density_path(self):
        G = fnx.path_graph(10)
        nxG = nx.path_graph(10)
        assert abs(fnx.density(G) - nx.density(nxG)) < 1e-10


class TestSimplePathsParity:
    """Verify simple paths outputs match NetworkX."""

    def test_is_simple_path(self):
        G = fnx.path_graph(5)
        nxG = nx.path_graph(5)
        assert fnx.is_simple_path(G, [0, 1, 2]) == nx.is_simple_path(nxG, [0, 1, 2]) == True
        assert fnx.is_simple_path(G, [0, 1, 0]) == nx.is_simple_path(nxG, [0, 1, 0]) == False

    def test_all_simple_paths(self):
        G = fnx.complete_graph(4)
        nxG = nx.complete_graph(4)
        fnx_paths = sorted([tuple(p) for p in fnx.all_simple_paths(G, 0, 3)])
        nx_paths = sorted([tuple(p) for p in nx.all_simple_paths(nxG, 0, 3)])
        assert fnx_paths == nx_paths

    def test_shortest_simple_paths(self):
        G = fnx.complete_graph(4)
        nxG = nx.complete_graph(4)
        fnx_ssp = [tuple(p) for p in fnx.shortest_simple_paths(G, 0, 3)]
        nx_ssp = [tuple(p) for p in nx.shortest_simple_paths(nxG, 0, 3)]
        assert fnx_ssp[:3] == nx_ssp[:3]


class TestIsolatesParity:
    """Verify isolate detection outputs match NetworkX."""

    def test_isolates(self):
        G = fnx.Graph()
        G.add_nodes_from([0, 1, 2, 3])
        G.add_edge(0, 1)
        nxG = nx.Graph()
        nxG.add_nodes_from([0, 1, 2, 3])
        nxG.add_edge(0, 1)
        fnx_iso = list(fnx.isolates(G))
        nx_iso = list(nx.isolates(nxG))
        assert set(fnx_iso) == set(nx_iso)

    def test_is_isolate(self):
        G = fnx.Graph()
        G.add_nodes_from([0, 1, 2])
        G.add_edge(0, 1)
        nxG = nx.Graph()
        nxG.add_nodes_from([0, 1, 2])
        nxG.add_edge(0, 1)
        assert fnx.is_isolate(G, 2) == nx.is_isolate(nxG, 2) == True
        assert fnx.is_isolate(G, 0) == nx.is_isolate(nxG, 0) == False

    def test_number_of_isolates(self):
        G = fnx.Graph()
        G.add_nodes_from([0, 1, 2, 3, 4])
        G.add_edge(0, 1)
        nxG = nx.Graph()
        nxG.add_nodes_from([0, 1, 2, 3, 4])
        nxG.add_edge(0, 1)
        assert fnx.number_of_isolates(G) == nx.number_of_isolates(nxG) == 3


class TestAverageShortestPathParity:
    """Verify average shortest path length outputs match NetworkX."""

    def test_average_shortest_path_length(self):
        G = fnx.complete_graph(10)
        nxG = nx.complete_graph(10)
        fnx_aspl = fnx.average_shortest_path_length(G)
        nx_aspl = nx.average_shortest_path_length(nxG)
        assert abs(fnx_aspl - nx_aspl) < 1e-10


class TestReverseParity:
    """Verify reverse graph outputs match NetworkX."""

    def test_reverse(self):
        DG = fnx.DiGraph()
        DG.add_edges_from([(0, 1), (1, 2), (2, 3)])
        nxDG = nx.DiGraph()
        nxDG.add_edges_from([(0, 1), (1, 2), (2, 3)])
        fnx_r = fnx.reverse(DG)
        nx_r = nx.reverse(nxDG)
        assert set(fnx_r.edges()) == set(nx_r.edges())


class TestLineGraphParity:
    """Verify line graph outputs match NetworkX."""

    def test_line_graph(self):
        G = fnx.cycle_graph(5)
        nxG = nx.cycle_graph(5)
        fnx_lg = fnx.line_graph(G)
        nx_lg = nx.line_graph(nxG)
        assert fnx_lg.number_of_nodes() == nx_lg.number_of_nodes()
        assert fnx_lg.number_of_edges() == nx_lg.number_of_edges()


class TestSquareClusteringParity:
    """Verify square clustering outputs match NetworkX."""

    def test_square_clustering(self):
        G = fnx.complete_graph(5)
        nxG = nx.complete_graph(5)
        fnx_sc = fnx.square_clustering(G)
        nx_sc = nx.square_clustering(nxG)
        for n in fnx_sc:
            assert abs(fnx_sc[n] - nx_sc[n]) < 1e-10


class TestProductParity:
    """Verify graph product outputs match NetworkX."""

    def test_cartesian_product(self):
        G1 = fnx.path_graph(3)
        G2 = fnx.path_graph(2)
        nxG1 = nx.path_graph(3)
        nxG2 = nx.path_graph(2)
        fnx_cp = fnx.cartesian_product(G1, G2)
        nx_cp = nx.cartesian_product(nxG1, nxG2)
        assert fnx_cp.number_of_nodes() == nx_cp.number_of_nodes()
        assert fnx_cp.number_of_edges() == nx_cp.number_of_edges()

    def test_tensor_product(self):
        G1 = fnx.cycle_graph(3)
        G2 = fnx.cycle_graph(3)
        nxG1 = nx.cycle_graph(3)
        nxG2 = nx.cycle_graph(3)
        fnx_tp = fnx.tensor_product(G1, G2)
        nx_tp = nx.tensor_product(nxG1, nxG2)
        assert fnx_tp.number_of_nodes() == nx_tp.number_of_nodes()
        assert fnx_tp.number_of_edges() == nx_tp.number_of_edges()

    def test_strong_product(self):
        G1 = fnx.path_graph(3)
        G2 = fnx.path_graph(2)
        nxG1 = nx.path_graph(3)
        nxG2 = nx.path_graph(2)
        fnx_sp = fnx.strong_product(G1, G2)
        nx_sp = nx.strong_product(nxG1, nxG2)
        assert fnx_sp.number_of_nodes() == nx_sp.number_of_nodes()
        assert fnx_sp.number_of_edges() == nx_sp.number_of_edges()


class TestPowerParity:
    """Verify power graph outputs match NetworkX."""

    def test_power(self):
        G = fnx.path_graph(5)
        nxG = nx.path_graph(5)
        fnx_p = fnx.power(G, 2)
        nx_p = nx.power(nxG, 2)
        assert fnx_p.number_of_nodes() == nx_p.number_of_nodes()
        assert fnx_p.number_of_edges() == nx_p.number_of_edges()


class TestGraphGeneratorsParity:
    """Verify graph generator outputs match NetworkX."""

    def test_complete_graph(self):
        G = fnx.complete_graph(10)
        nxG = nx.complete_graph(10)
        assert G.number_of_nodes() == nxG.number_of_nodes()
        assert G.number_of_edges() == nxG.number_of_edges()

    def test_cycle_graph(self):
        G = fnx.cycle_graph(10)
        nxG = nx.cycle_graph(10)
        assert G.number_of_nodes() == nxG.number_of_nodes()
        assert G.number_of_edges() == nxG.number_of_edges()

    def test_path_graph(self):
        G = fnx.path_graph(10)
        nxG = nx.path_graph(10)
        assert G.number_of_nodes() == nxG.number_of_nodes()
        assert G.number_of_edges() == nxG.number_of_edges()

    def test_star_graph(self):
        G = fnx.star_graph(10)
        nxG = nx.star_graph(10)
        assert G.number_of_nodes() == nxG.number_of_nodes()
        assert G.number_of_edges() == nxG.number_of_edges()

    def test_wheel_graph(self):
        G = fnx.wheel_graph(10)
        nxG = nx.wheel_graph(10)
        assert G.number_of_nodes() == nxG.number_of_nodes()
        assert G.number_of_edges() == nxG.number_of_edges()

    def test_ladder_graph(self):
        G = fnx.ladder_graph(10)
        nxG = nx.ladder_graph(10)
        assert G.number_of_nodes() == nxG.number_of_nodes()
        assert G.number_of_edges() == nxG.number_of_edges()

    def test_grid_2d_graph(self):
        G = fnx.grid_2d_graph(5, 5)
        nxG = nx.grid_2d_graph(5, 5)
        assert G.number_of_nodes() == nxG.number_of_nodes()
        assert G.number_of_edges() == nxG.number_of_edges()

    def test_petersen_graph(self):
        G = fnx.petersen_graph()
        nxG = nx.petersen_graph()
        assert G.number_of_nodes() == nxG.number_of_nodes()
        assert G.number_of_edges() == nxG.number_of_edges()

    def test_tutte_graph(self):
        G = fnx.tutte_graph()
        nxG = nx.tutte_graph()
        assert G.number_of_nodes() == nxG.number_of_nodes()
        assert G.number_of_edges() == nxG.number_of_edges()

    def test_balanced_tree(self):
        G = fnx.balanced_tree(2, 4)
        nxG = nx.balanced_tree(2, 4)
        assert G.number_of_nodes() == nxG.number_of_nodes()
        assert G.number_of_edges() == nxG.number_of_edges()


class TestHarmonicCentralityParity:
    """Verify harmonic centrality outputs match NetworkX."""

    def test_harmonic_centrality(self):
        G = fnx.barabasi_albert_graph(30, 2, seed=42)
        nxG = nx.barabasi_albert_graph(30, 2, seed=42)
        fnx_hc = fnx.harmonic_centrality(G)
        nx_hc = nx.harmonic_centrality(nxG)
        for n in fnx_hc:
            assert abs(fnx_hc[n] - nx_hc[n]) < 1e-10


class TestClassicGeneratorsParity:
    """Verify classic graph generators match NetworkX."""

    def test_barbell_graph(self):
        G = fnx.barbell_graph(5, 3)
        nxG = nx.barbell_graph(5, 3)
        assert G.number_of_nodes() == nxG.number_of_nodes()
        assert G.number_of_edges() == nxG.number_of_edges()

    def test_bull_graph(self):
        G = fnx.bull_graph()
        nxG = nx.bull_graph()
        assert G.number_of_nodes() == nxG.number_of_nodes()
        assert G.number_of_edges() == nxG.number_of_edges()

    def test_chvatal_graph(self):
        G = fnx.chvatal_graph()
        nxG = nx.chvatal_graph()
        assert G.number_of_nodes() == nxG.number_of_nodes()
        assert G.number_of_edges() == nxG.number_of_edges()

    def test_cubical_graph(self):
        G = fnx.cubical_graph()
        nxG = nx.cubical_graph()
        assert G.number_of_nodes() == nxG.number_of_nodes()
        assert G.number_of_edges() == nxG.number_of_edges()

    def test_desargues_graph(self):
        G = fnx.desargues_graph()
        nxG = nx.desargues_graph()
        assert G.number_of_nodes() == nxG.number_of_nodes()
        assert G.number_of_edges() == nxG.number_of_edges()

    def test_dodecahedral_graph(self):
        G = fnx.dodecahedral_graph()
        nxG = nx.dodecahedral_graph()
        assert G.number_of_nodes() == nxG.number_of_nodes()
        assert G.number_of_edges() == nxG.number_of_edges()

    def test_heawood_graph(self):
        G = fnx.heawood_graph()
        nxG = nx.heawood_graph()
        assert G.number_of_nodes() == nxG.number_of_nodes()
        assert G.number_of_edges() == nxG.number_of_edges()

    def test_icosahedral_graph(self):
        G = fnx.icosahedral_graph()
        nxG = nx.icosahedral_graph()
        assert G.number_of_nodes() == nxG.number_of_nodes()
        assert G.number_of_edges() == nxG.number_of_edges()

    def test_moebius_kantor_graph(self):
        G = fnx.moebius_kantor_graph()
        nxG = nx.moebius_kantor_graph()
        assert G.number_of_nodes() == nxG.number_of_nodes()
        assert G.number_of_edges() == nxG.number_of_edges()

    def test_octahedral_graph(self):
        G = fnx.octahedral_graph()
        nxG = nx.octahedral_graph()
        assert G.number_of_nodes() == nxG.number_of_nodes()
        assert G.number_of_edges() == nxG.number_of_edges()


class TestCurrentFlowCentralityParity:
    """Verify current flow centrality outputs match NetworkX."""

    def test_current_flow_closeness_centrality(self):
        G = fnx.cycle_graph(6)
        nxG = nx.cycle_graph(6)
        fnx_cfc = fnx.current_flow_closeness_centrality(G)
        nx_cfc = nx.current_flow_closeness_centrality(nxG)
        for n in fnx_cfc:
            assert abs(fnx_cfc[n] - nx_cfc[n]) < 1e-10


class TestKatzCentralityParity:
    """Verify Katz centrality outputs match NetworkX."""

    def test_katz_centrality(self):
        G = fnx.barabasi_albert_graph(20, 2, seed=42)
        nxG = nx.barabasi_albert_graph(20, 2, seed=42)
        fnx_kc = fnx.katz_centrality(G, alpha=0.1)
        nx_kc = nx.katz_centrality(nxG, alpha=0.1)
        for n in fnx_kc:
            assert abs(fnx_kc[n] - nx_kc[n]) < 1e-8


class TestLoadCentralityParity:
    """Verify load centrality outputs match NetworkX."""

    def test_load_centrality(self):
        G = fnx.barabasi_albert_graph(30, 2, seed=42)
        nxG = nx.barabasi_albert_graph(30, 2, seed=42)
        fnx_lc = fnx.load_centrality(G)
        nx_lc = nx.load_centrality(nxG)
        for n in fnx_lc:
            assert abs(fnx_lc[n] - nx_lc[n]) < 1e-10


class TestEfficiencyParity:
    """Verify efficiency outputs match NetworkX."""

    def test_global_efficiency(self):
        G = fnx.barabasi_albert_graph(20, 2, seed=42)
        nxG = nx.barabasi_albert_graph(20, 2, seed=42)
        fnx_ge = fnx.global_efficiency(G)
        nx_ge = nx.global_efficiency(nxG)
        assert abs(fnx_ge - nx_ge) < 1e-10

    def test_local_efficiency(self):
        G = fnx.barabasi_albert_graph(20, 2, seed=42)
        nxG = nx.barabasi_albert_graph(20, 2, seed=42)
        fnx_le = fnx.local_efficiency(G)
        nx_le = nx.local_efficiency(nxG)
        assert abs(fnx_le - nx_le) < 1e-10

    def test_efficiency(self):
        G = fnx.complete_graph(10)
        nxG = nx.complete_graph(10)
        fnx_e = fnx.efficiency(G, 0, 5)
        nx_e = nx.efficiency(nxG, 0, 5)
        assert abs(fnx_e - nx_e) < 1e-10


class TestInformationCentralityParity:
    """Verify information centrality outputs match NetworkX."""

    def test_information_centrality(self):
        G = fnx.cycle_graph(8)
        nxG = nx.cycle_graph(8)
        fnx_ic = fnx.information_centrality(G)
        nx_ic = nx.information_centrality(nxG)
        for n in fnx_ic:
            assert abs(fnx_ic[n] - nx_ic[n]) < 1e-10


class TestSubgraphParity:
    """Verify subgraph operations match NetworkX."""

    def test_subgraph(self):
        G = fnx.complete_graph(10)
        nxG = nx.complete_graph(10)
        fnx_sg = fnx.subgraph(G, [0, 1, 2, 3])
        nx_sg = nx.subgraph(nxG, [0, 1, 2, 3])
        assert fnx_sg.number_of_nodes() == nx_sg.number_of_nodes()
        assert fnx_sg.number_of_edges() == nx_sg.number_of_edges()

    def test_induced_subgraph(self):
        G = fnx.complete_graph(10)
        nxG = nx.complete_graph(10)
        fnx_sg = fnx.induced_subgraph(G, [0, 1, 2, 3])
        nx_sg = nx.induced_subgraph(nxG, [0, 1, 2, 3])
        assert fnx_sg.number_of_nodes() == nx_sg.number_of_nodes()
        assert fnx_sg.number_of_edges() == nx_sg.number_of_edges()

    def test_subgraph_centrality(self):
        G = fnx.cycle_graph(8)
        nxG = nx.cycle_graph(8)
        fnx_sc = fnx.subgraph_centrality(G)
        nx_sc = nx.subgraph_centrality(nxG)
        for n in fnx_sc:
            assert abs(fnx_sc[n] - nx_sc[n]) < 1e-8


class TestRelabelParity:
    """Verify relabel operations match NetworkX."""

    def test_relabel_nodes(self):
        G = fnx.path_graph(5)
        nxG = nx.path_graph(5)
        mapping = {0: "a", 1: "b", 2: "c", 3: "d", 4: "e"}
        fnx_rel = fnx.relabel_nodes(G, mapping)
        nx_rel = nx.relabel_nodes(nxG, mapping)
        assert set(fnx_rel.nodes()) == set(nx_rel.nodes())
        assert fnx_rel.number_of_edges() == nx_rel.number_of_edges()


class TestSelfLoopParity:
    """Verify self-loop detection matches NetworkX."""

    def test_number_of_selfloops(self):
        G = fnx.Graph()
        G.add_edges_from([(0, 1), (1, 2), (0, 0), (2, 2)])
        nxG = nx.Graph()
        nxG.add_edges_from([(0, 1), (1, 2), (0, 0), (2, 2)])
        assert fnx.number_of_selfloops(G) == nx.number_of_selfloops(nxG) == 2

    def test_nodes_with_selfloops(self):
        G = fnx.Graph()
        G.add_edges_from([(0, 1), (1, 2), (0, 0), (2, 2)])
        nxG = nx.Graph()
        nxG.add_edges_from([(0, 1), (1, 2), (0, 0), (2, 2)])
        fnx_nwsl = set(fnx.nodes_with_selfloops(G))
        nx_nwsl = set(nx.nodes_with_selfloops(nxG))
        assert fnx_nwsl == nx_nwsl


class TestCopyParity:
    """Verify graph copy operations match NetworkX."""

    def test_to_undirected(self):
        DG = fnx.DiGraph()
        DG.add_edges_from([(0, 1), (1, 2), (2, 0)])
        nxDG = nx.DiGraph()
        nxDG.add_edges_from([(0, 1), (1, 2), (2, 0)])
        fnx_ud = DG.to_undirected()
        nx_ud = nxDG.to_undirected()
        assert fnx_ud.number_of_nodes() == nx_ud.number_of_nodes()
        assert fnx_ud.number_of_edges() == nx_ud.number_of_edges()

    def test_to_directed(self):
        G = fnx.cycle_graph(5)
        nxG = nx.cycle_graph(5)
        fnx_dir = G.to_directed()
        nx_dir = nxG.to_directed()
        assert fnx_dir.number_of_nodes() == nx_dir.number_of_nodes()
        assert fnx_dir.number_of_edges() == nx_dir.number_of_edges()
