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
