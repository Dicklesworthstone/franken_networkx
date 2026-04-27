"""Tests verifying algorithm dispatch works correctly on MultiGraph and MultiDiGraph.

Algorithms should transparently accept multigraph inputs by converting them to
simple graphs internally (collapsing parallel edges). Results should match
NetworkX behavior on equivalent simple-graph projections.
"""

import pytest

import franken_networkx as fnx

try:
    import networkx as nx

    HAS_NX = True
except ImportError:
    HAS_NX = False

needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


def _normalized_matching(matching):
    return {frozenset(edge) for edge in matching}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mg_triangle():
    """MultiGraph triangle with parallel edges on one side."""
    G = fnx.MultiGraph()
    G.add_edge(0, 1, weight=1.0)
    G.add_edge(0, 1, weight=5.0)  # parallel
    G.add_edge(1, 2, weight=2.0)
    G.add_edge(0, 2, weight=3.0)
    return G


@pytest.fixture
def mg_path():
    """MultiGraph path with a parallel edge."""
    G = fnx.MultiGraph()
    G.add_edge(0, 1)
    G.add_edge(0, 1)  # parallel
    G.add_edge(1, 2)
    G.add_edge(2, 3)
    return G


@pytest.fixture
def mdg_cycle():
    """MultiDiGraph 3-cycle with a parallel edge."""
    D = fnx.MultiDiGraph()
    D.add_edge("a", "b")
    D.add_edge("a", "b")  # parallel
    D.add_edge("b", "c")
    D.add_edge("c", "a")
    return D


@pytest.fixture
def mdg_dag():
    """MultiDiGraph DAG."""
    D = fnx.MultiDiGraph()
    D.add_edge(0, 1)
    D.add_edge(0, 2)
    D.add_edge(1, 3)
    D.add_edge(2, 3)
    return D


# ---------------------------------------------------------------------------
# Connectivity on MultiGraph
# ---------------------------------------------------------------------------


class TestMultiGraphConnectivity:
    def test_is_connected(self, mg_triangle):
        assert fnx.is_connected(mg_triangle)

    def test_connected_components(self, mg_triangle):
        comps = list(fnx.connected_components(mg_triangle))
        assert len(comps) == 1

    def test_number_connected_components(self, mg_path):
        assert fnx.number_connected_components(mg_path) == 1

    def test_disconnected_multigraph(self):
        G = fnx.MultiGraph()
        G.add_edge(0, 1)
        G.add_edge(2, 3)
        assert not fnx.is_connected(G)
        assert fnx.number_connected_components(G) == 2

    def test_bridges(self, mg_path):
        # br-zzcm9: parallel edges are not bridges (removing one leaves
        # the other intact). mg_path has parallel (0, 1) + simple (1, 2),
        # (2, 3). Only the two simple edges are bridges, matching nx.
        b = sorted(fnx.bridges(mg_path))
        assert b == [(1, 2), (2, 3)]


# ---------------------------------------------------------------------------
# Shortest path on MultiGraph
# ---------------------------------------------------------------------------


class TestMultiGraphShortestPath:
    def test_shortest_path(self, mg_path):
        path = fnx.shortest_path(mg_path, 0, 3)
        assert path == [0, 1, 2, 3]

    def test_has_path(self, mg_path):
        assert fnx.has_path(mg_path, 0, 3)

    def test_shortest_path_length(self, mg_path):
        length = fnx.shortest_path_length(mg_path, 0, 3)
        assert length == 3

    def test_dijkstra_path(self, mg_triangle):
        path = fnx.dijkstra_path(mg_triangle, 0, 2, weight="weight")
        assert path is not None
        assert path[0] == 0
        assert path[-1] == 2


# ---------------------------------------------------------------------------
# Centrality on MultiGraph
# ---------------------------------------------------------------------------


class TestMultiGraphCentrality:
    def test_degree_centrality(self, mg_triangle):
        # br-zzcm9: degree_centrality on MultiGraph counts parallel
        # edges in the degree (matches nx). mg_triangle has parallel
        # (0, 1) so nodes 0 and 1 have degree 3 in a 3-node graph and
        # their centrality is 3 / (3-1) = 1.5 — legitimately >1.0 for
        # multigraphs. Compare directly against nx.
        import networkx as nx

        MGn = nx.MultiGraph()
        MGn.add_edge(0, 1, weight=1.0)
        MGn.add_edge(0, 1, weight=5.0)
        MGn.add_edge(1, 2, weight=2.0)
        MGn.add_edge(0, 2, weight=3.0)
        assert fnx.degree_centrality(mg_triangle) == nx.degree_centrality(MGn)

    def test_betweenness_centrality(self, mg_triangle):
        bc = fnx.betweenness_centrality(mg_triangle)
        assert len(bc) == 3

    def test_pagerank(self, mg_triangle):
        pr = fnx.pagerank(mg_triangle)
        assert len(pr) == 3
        assert abs(sum(pr.values()) - 1.0) < 1e-6

    def test_closeness_centrality(self, mg_triangle):
        cc = fnx.closeness_centrality(mg_triangle)
        assert len(cc) == 3


# ---------------------------------------------------------------------------
# Clustering on MultiGraph
# ---------------------------------------------------------------------------


class TestMultiGraphClustering:
    def test_clustering(self, mg_triangle):
        # Upstream nx.clustering raises NetworkXNotImplemented for
        # multigraphs; fnx matches.
        with pytest.raises(fnx.NetworkXNotImplemented):
            fnx.clustering(mg_triangle)

    def test_transitivity(self, mg_triangle):
        # Upstream nx.transitivity raises NetworkXNotImplemented for
        # multigraphs; fnx matches.
        with pytest.raises(fnx.NetworkXNotImplemented):
            fnx.transitivity(mg_triangle)

    def test_triangles(self, mg_triangle):
        tri = fnx.triangles(mg_triangle)
        assert all(v == 1 for v in tri.values())


# ---------------------------------------------------------------------------
# Matching on MultiGraph
# ---------------------------------------------------------------------------


class TestMultiGraphMatching:
    def test_max_weight_matching(self, mg_path):
        m = fnx.max_weight_matching(mg_path)
        assert len(m) == 2  # path of 4 nodes -> 2 edges in matching

    def test_maximal_matching(self, mg_triangle):
        # br-r37-c1-2dwen: fnx now matches nx's
        # @not_implemented_for('multigraph') decorator and raises
        # NetworkXNotImplemented on MultiGraph input. Previously the
        # Rust-direct re-export silently accepted MultiGraph and
        # returned a matching from the simple-graph projection.
        import pytest as _pytest
        with _pytest.raises(fnx.NetworkXNotImplemented):
            fnx.maximal_matching(mg_triangle)

    @needs_nx
    def test_max_weight_matching_maxcardinality_matches_networkx(self):
        graph = fnx.Graph()
        graph.add_edge(1, 2, weight=2)
        graph.add_edge(1, 3, weight=-2)
        graph.add_edge(2, 3, weight=1)
        graph.add_edge(2, 4, weight=-1)
        graph.add_edge(3, 4, weight=-6)

        expected = nx.Graph()
        expected.add_edge(1, 2, weight=2)
        expected.add_edge(1, 3, weight=-2)
        expected.add_edge(2, 3, weight=1)
        expected.add_edge(2, 4, weight=-1)
        expected.add_edge(3, 4, weight=-6)

        default_matching = _normalized_matching(fnx.max_weight_matching(graph))
        default_expected = _normalized_matching(nx.max_weight_matching(expected))
        maxcard_matching = _normalized_matching(
            fnx.max_weight_matching(graph, maxcardinality=True)
        )
        maxcard_expected = _normalized_matching(
            nx.max_weight_matching(expected, maxcardinality=True)
        )

        assert default_matching == default_expected == {frozenset((1, 2))}
        assert maxcard_matching == maxcard_expected == {
            frozenset((1, 3)),
            frozenset((2, 4)),
        }


# ---------------------------------------------------------------------------
# Tree / MST on MultiGraph
# ---------------------------------------------------------------------------


class TestMultiGraphTree:
    def test_is_tree_path(self, mg_path):
        # br-zzcm9: mg_path has a parallel edge on (0, 1), which
        # creates a cycle — so it is NOT a tree. This matches nx.
        assert not fnx.is_tree(mg_path)

    def test_minimum_spanning_tree(self, mg_triangle):
        mst = fnx.minimum_spanning_tree(mg_triangle)
        assert mst.number_of_nodes() == 3
        assert mst.number_of_edges() == 2  # tree has n-1 edges


# ---------------------------------------------------------------------------
# Graph operators on MultiGraph
# ---------------------------------------------------------------------------


class TestMultiGraphOperators:
    def test_density(self, mg_triangle):
        d = fnx.density(mg_triangle)
        assert d == pytest.approx(4 / 3)


# ---------------------------------------------------------------------------
# MultiDiGraph algorithms
# ---------------------------------------------------------------------------


class TestMultiDiGraphAlgorithms:
    def test_shortest_path(self, mdg_cycle):
        path = fnx.shortest_path(mdg_cycle, "a", "c")
        assert path is not None
        assert path[0] == "a"
        assert path[-1] == "c"

    def test_strongly_connected_components(self, mdg_cycle):
        sccs = list(fnx.strongly_connected_components(mdg_cycle))
        assert len(sccs) == 1  # full cycle -> 1 SCC

    def test_is_strongly_connected(self, mdg_cycle):
        assert fnx.is_strongly_connected(mdg_cycle)

    def test_weakly_connected(self, mdg_cycle):
        assert fnx.is_weakly_connected(mdg_cycle)

    def test_pagerank(self, mdg_cycle):
        pr = fnx.pagerank(mdg_cycle)
        assert len(pr) == 3
        assert abs(sum(pr.values()) - 1.0) < 1e-6

    def test_topological_sort_dag(self, mdg_dag):
        assert fnx.is_directed_acyclic_graph(mdg_dag)
        # br-zzcm7: topological_sort now returns a generator matching nx.
        topo = list(fnx.topological_sort(mdg_dag))
        assert len(topo) == 4
        # 0 must come before 1,2; 1,2 must come before 3
        idx = {n: i for i, n in enumerate(topo)}
        assert idx[0] < idx[1]
        assert idx[0] < idx[2]
        assert idx[1] < idx[3]
        assert idx[2] < idx[3]

    def test_condensation(self, mdg_cycle):
        cond = fnx.condensation(mdg_cycle)
        assert cond is not None

    def test_condensation_honors_supplied_scc(self):
        D = fnx.MultiDiGraph()
        D.add_edge("a", "b")
        D.add_edge("b", "a")
        D.add_edge("b", "c")
        D.add_edge("c", "d")
        D.add_edge("d", "c")

        supplied_scc = [{"c", "d"}, {"a", "b"}]
        cond = fnx.condensation(D, supplied_scc)

        assert cond.number_of_nodes() == 2
        assert set(cond.nodes[0]["members"]) == {"c", "d"}
        assert set(cond.nodes[1]["members"]) == {"a", "b"}
        assert cond.graph["mapping"] == {"c": 0, "d": 0, "a": 1, "b": 1}
        assert list(cond.edges()) == [(1, 0)]

    def test_ancestors_descendants(self, mdg_dag):
        anc = fnx.ancestors(mdg_dag, 3)
        assert 0 in anc
        desc = fnx.descendants(mdg_dag, 0)
        assert 3 in desc


# ---------------------------------------------------------------------------
# Cross-validation with NetworkX
# ---------------------------------------------------------------------------


@needs_nx
class TestMultiGraphNxParity:
    def test_pagerank_sums_to_one(self):
        """PageRank on MultiGraph should sum to 1 (uses simple projection)."""
        G = fnx.MultiGraph()
        G.add_edge(0, 1)
        G.add_edge(0, 1)
        G.add_edge(1, 2)
        G.add_edge(2, 0)

        pr = fnx.pagerank(G)
        assert abs(sum(pr.values()) - 1.0) < 1e-6

    def test_is_connected_matches_nx(self):
        G = fnx.MultiGraph()
        G.add_edge(0, 1)
        G.add_node(2)

        N = nx.MultiGraph()
        N.add_edge(0, 1)
        N.add_node(2)

        assert fnx.is_connected(G) == nx.is_connected(N)

    def test_strongly_connected_multidigraph(self):
        D = fnx.MultiDiGraph()
        D.add_edge(0, 1)
        D.add_edge(1, 0)
        D.add_edge(0, 1)  # parallel

        N = nx.MultiDiGraph()
        N.add_edge(0, 1)
        N.add_edge(1, 0)
        N.add_edge(0, 1)

        assert fnx.is_strongly_connected(D) == nx.is_strongly_connected(N)

    def test_shortest_path_matches_nx(self):
        G = fnx.MultiGraph()
        G.add_edge(0, 1)
        G.add_edge(1, 2)

        N = nx.MultiGraph()
        N.add_edge(0, 1)
        N.add_edge(1, 2)

        assert fnx.shortest_path(G, 0, 2) == nx.shortest_path(N, 0, 2)

    def test_weighted_multigraph_shortest_path_family_uses_min_parallel_edge(self):
        G = fnx.MultiGraph()
        G.add_edge("a", "b", cost=10.0)
        G.add_edge("a", "b", cost=1.0)
        G.add_edge("b", "c", cost=1.0)
        G.add_edge("a", "c", cost=5.0)

        N = nx.MultiGraph()
        N.add_edge("a", "b", cost=10.0)
        N.add_edge("a", "b", cost=1.0)
        N.add_edge("b", "c", cost=1.0)
        N.add_edge("a", "c", cost=5.0)

        assert fnx.shortest_path(G, "a", "c", weight="cost") == nx.shortest_path(
            N, "a", "c", weight="cost"
        )
        assert fnx.shortest_path_length(G, "a", "c", weight="cost") == nx.shortest_path_length(
            N, "a", "c", weight="cost"
        )
        assert fnx.dijkstra_path(G, "a", "c", weight="cost") == nx.dijkstra_path(
            N, "a", "c", weight="cost"
        )
        assert fnx.dijkstra_path_length(
            G, "a", "c", weight="cost"
        ) == nx.dijkstra_path_length(N, "a", "c", weight="cost")
        assert fnx.bellman_ford_path(G, "a", "c", weight="cost") == nx.bellman_ford_path(
            N, "a", "c", weight="cost"
        )
        assert fnx.bellman_ford_path_length(
            G, "a", "c", weight="cost"
        ) == nx.bellman_ford_path_length(N, "a", "c", weight="cost")
        assert fnx.path_weight(G, ["a", "b", "c"], weight="cost") == nx.path_weight(
            N, ["a", "b", "c"], weight="cost"
        )

        fnx_dists, fnx_paths = fnx.single_source_dijkstra(G, "a", weight="cost")
        nx_dists, nx_paths = nx.single_source_dijkstra(N, "a", weight="cost")
        assert fnx_dists == nx_dists
        assert fnx_paths == nx_paths

        fnx_multi_dists, fnx_multi_paths = fnx.multi_source_dijkstra(G, ["a"], weight="cost")
        nx_multi_dists, nx_multi_paths = nx.multi_source_dijkstra(N, ["a"], weight="cost")
        assert fnx_multi_dists == nx_multi_dists
        assert fnx_multi_paths == nx_multi_paths

        # all_pairs_* now match the nx generator contract — materialise
        # both sides for equality.
        assert dict(fnx.all_pairs_dijkstra_path_length(G, weight="cost")) == dict(
            nx.all_pairs_dijkstra_path_length(N, weight="cost")
        )
        assert dict(fnx.all_pairs_dijkstra_path(G, weight="cost")) == dict(
            nx.all_pairs_dijkstra_path(N, weight="cost")
        )
        assert dict(fnx.all_pairs_dijkstra(G, weight="cost")) == dict(
            nx.all_pairs_dijkstra(N, weight="cost")
        )
        assert dict(fnx.all_pairs_bellman_ford_path_length(G, weight="cost")) == dict(
            nx.all_pairs_bellman_ford_path_length(N, weight="cost")
        )
        assert dict(fnx.all_pairs_bellman_ford_path(G, weight="cost")) == dict(
            nx.all_pairs_bellman_ford_path(N, weight="cost")
        )
        assert fnx.floyd_warshall(G, weight="cost") == dict(nx.floyd_warshall(N, weight="cost"))

        fnx_preds, fnx_fw_dists = fnx.floyd_warshall_predecessor_and_distance(G, weight="cost")
        nx_preds, nx_fw_dists = nx.floyd_warshall_predecessor_and_distance(N, weight="cost")
        assert fnx_preds == nx_preds
        assert fnx_fw_dists == nx_fw_dists

    def test_weighted_multidigraph_shortest_path_family_uses_min_parallel_edge(self):
        D = fnx.MultiDiGraph()
        D.add_edge("a", "b", weight=10.0)
        D.add_edge("a", "b", weight=1.0)
        D.add_edge("b", "c", weight=1.0)
        D.add_edge("a", "c", weight=5.0)

        N = nx.MultiDiGraph()
        N.add_edge("a", "b", weight=10.0)
        N.add_edge("a", "b", weight=1.0)
        N.add_edge("b", "c", weight=1.0)
        N.add_edge("a", "c", weight=5.0)

        assert fnx.shortest_path(D, "a", "c", weight="weight") == nx.shortest_path(
            N, "a", "c", weight="weight"
        )
        assert fnx.shortest_path_length(
            D, "a", "c", weight="weight"
        ) == nx.shortest_path_length(N, "a", "c", weight="weight")
        assert fnx.dijkstra_path(D, "a", "c", weight="weight") == nx.dijkstra_path(
            N, "a", "c", weight="weight"
        )
        assert fnx.dijkstra_path_length(
            D, "a", "c", weight="weight"
        ) == nx.dijkstra_path_length(N, "a", "c", weight="weight")
        assert fnx.bellman_ford_path(D, "a", "c", weight="weight") == nx.bellman_ford_path(
            N, "a", "c", weight="weight"
        )
        assert fnx.bellman_ford_path_length(
            D, "a", "c", weight="weight"
        ) == nx.bellman_ford_path_length(N, "a", "c", weight="weight")
        assert fnx.path_weight(D, ["a", "b", "c"], weight="weight") == nx.path_weight(
            N, ["a", "b", "c"], weight="weight"
        )

        fnx_dists, fnx_paths = fnx.multi_source_dijkstra(D, ["a"], weight="weight")
        nx_dists, nx_paths = nx.multi_source_dijkstra(N, ["a"], weight="weight")
        assert fnx_dists == nx_dists
        assert fnx_paths == nx_paths

        assert dict(fnx.all_pairs_dijkstra_path_length(D, weight="weight")) == dict(
            nx.all_pairs_dijkstra_path_length(N, weight="weight")
        )
        assert dict(fnx.all_pairs_dijkstra_path(D, weight="weight")) == dict(
            nx.all_pairs_dijkstra_path(N, weight="weight")
        )
        assert dict(fnx.all_pairs_dijkstra(D, weight="weight")) == dict(
            nx.all_pairs_dijkstra(N, weight="weight")
        )


# ---------------------------------------------------------------------------
# Regression: franken_networkx-zzcm9 — MultiGraph structural algorithm parity
# ---------------------------------------------------------------------------


class TestMultiGraphStructuralParity:
    """The Rust native bridges / is_tree / is_forest / degree_centrality /
    complement routines treat MultiGraph inputs as their simple projection,
    which under-counts parallels or rejects the input outright. These
    wrappers restore the nx observable contract.
    """

    def test_is_tree_multigraph_with_parallel_edges_is_false(self):
        import networkx as nx

        MG = fnx.MultiGraph()
        MG.add_edges_from([(0, 1), (0, 1)])
        MGn = nx.MultiGraph()
        MGn.add_edges_from([(0, 1), (0, 1)])
        assert fnx.is_tree(MG) is False
        assert nx.is_tree(MGn) is False

    def test_is_forest_multigraph_with_parallel_edges_is_false(self):
        import networkx as nx

        MG = fnx.MultiGraph()
        MG.add_edges_from([(0, 1), (0, 1)])
        MGn = nx.MultiGraph()
        MGn.add_edges_from([(0, 1), (0, 1)])
        assert fnx.is_forest(MG) is False
        assert nx.is_forest(MGn) is False

    def test_is_tree_multigraph_valid_tree_is_true(self):
        MG = fnx.MultiGraph()
        MG.add_edges_from([(0, 1), (1, 2), (2, 3)])
        assert fnx.is_tree(MG) is True
        assert fnx.is_forest(MG) is True

    def test_bridges_multigraph_excludes_parallel_edges(self):
        MG = fnx.MultiGraph()
        MG.add_edges_from([(0, 1), (0, 1), (1, 2)])
        # (0, 1) is not a bridge because removing one parallel leaves the
        # other. (1, 2) is a bridge.
        assert sorted(fnx.bridges(MG)) == [(1, 2)]

    def test_degree_centrality_multigraph_counts_parallels(self):
        import networkx as nx

        MG = fnx.MultiGraph()
        MG.add_edges_from([(0, 1), (0, 1), (1, 2)])
        MGn = nx.MultiGraph()
        MGn.add_edges_from([(0, 1), (0, 1), (1, 2)])
        assert fnx.degree_centrality(MG) == nx.degree_centrality(MGn)

    def test_complement_multigraph_returns_multigraph(self):
        MG = fnx.MultiGraph()
        MG.add_edges_from([(0, 1), (1, 2)])
        C = fnx.complement(MG)
        assert isinstance(C, fnx.MultiGraph)
        # Complement of path 0-1-2 is the single non-edge (0, 2).
        assert sorted((u, v) for u, v in C.edges()) == [(0, 2), (0, 2)] or \
            sorted((u, v) for u, v in C.edges()) == [(0, 2)]
