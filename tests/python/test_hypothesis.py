"""Hypothesis property-based tests for FrankenNetworkX Python bindings.

Uses Hypothesis to generate random graphs and verify structural invariants
and cross-validation against NetworkX oracle.

Run with: python -m pytest tests/python/test_hypothesis.py -v --hypothesis-seed=0
"""

import logging
import math

import pytest
from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st

log = logging.getLogger("fnx_hypothesis")

try:
    import franken_networkx as fnx
except ImportError:
    pytest.skip("franken_networkx not installed", allow_module_level=True)

try:
    import networkx as nx
except ImportError:
    pytest.skip("networkx not installed", allow_module_level=True)


# ---------------------------------------------------------------------------
# Hypothesis strategies for graph generation
# ---------------------------------------------------------------------------

@st.composite
def small_connected_graph(draw, min_nodes=3, max_nodes=30):
    """Generate a small connected graph (both fnx and nx versions).

    Builds a random tree first (guarantees connectivity), then adds
    random extra edges up to a drawn density.
    """
    n = draw(st.integers(min_value=min_nodes, max_value=max_nodes))
    # Density of extra edges (0.0 = tree, 1.0 = complete)
    extra_density = draw(st.floats(min_value=0.0, max_value=0.6))

    G_fnx = fnx.Graph()
    G_nx = nx.Graph()

    nodes = list(range(n))
    for node in nodes:
        G_fnx.add_node(node)
        G_nx.add_node(node)

    # Build a random spanning tree via random permutation
    perm = draw(st.permutations(nodes))
    for i in range(1, n):
        u, v = perm[i - 1], perm[i]
        G_fnx.add_edge(u, v)
        G_nx.add_edge(u, v)

    # Add random extra edges
    possible_extra = []
    for i in range(n):
        for j in range(i + 1, n):
            if not G_nx.has_edge(i, j):
                possible_extra.append((i, j))

    if possible_extra:
        num_extra = int(len(possible_extra) * extra_density)
        if num_extra > 0:
            indices = draw(
                st.lists(
                    st.integers(min_value=0, max_value=len(possible_extra) - 1),
                    min_size=num_extra,
                    max_size=num_extra,
                    unique=True,
                )
            )
            for idx in indices:
                u, v = possible_extra[idx]
                G_fnx.add_edge(u, v)
                G_nx.add_edge(u, v)

    return G_fnx, G_nx, n


@st.composite
def small_weighted_connected_graph(draw, min_nodes=3, max_nodes=20):
    """Generate a small connected weighted graph."""
    G_fnx, G_nx, n = draw(small_connected_graph(min_nodes=min_nodes, max_nodes=max_nodes))

    # Assign random weights to all edges
    for u, v in list(G_nx.edges()):
        w = draw(st.floats(min_value=0.1, max_value=100.0, allow_nan=False, allow_infinity=False))
        G_fnx.add_edge(u, v, weight=w)
        G_nx[u][v]["weight"] = w

    return G_fnx, G_nx, n


@st.composite
def general_graph(draw, min_nodes=2, max_nodes=25):
    """Generate a general graph (possibly disconnected)."""
    n = draw(st.integers(min_value=min_nodes, max_value=max_nodes))
    density = draw(st.floats(min_value=0.0, max_value=0.5))

    G_fnx = fnx.Graph()
    G_nx = nx.Graph()

    for i in range(n):
        G_fnx.add_node(i)
        G_nx.add_node(i)

    for i in range(n):
        for j in range(i + 1, n):
            if draw(st.floats(min_value=0.0, max_value=1.0)) < density:
                G_fnx.add_edge(i, j)
                G_nx.add_edge(i, j)

    return G_fnx, G_nx, n


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

FAST = settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
MODERATE = settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])


# ---------------------------------------------------------------------------
# Structural invariant tests
# ---------------------------------------------------------------------------

class TestConnectivityInvariants:
    """Properties that must hold for connectivity algorithms."""

    @given(data=small_connected_graph())
    @settings(MODERATE)
    def test_connected_graph_is_connected(self, data):
        """A graph built from a spanning tree must be connected."""
        G_fnx, G_nx, n = data
        assert fnx.is_connected(G_fnx)

    @given(data=small_connected_graph())
    @settings(MODERATE)
    def test_single_connected_component(self, data):
        """A connected graph has exactly one connected component."""
        G_fnx, G_nx, n = data
        comps = fnx.connected_components(G_fnx)
        assert len(comps) == 1
        assert len(comps[0]) == n

    @given(data=small_connected_graph())
    @settings(FAST)
    def test_components_partition_all_nodes(self, data):
        """Connected components must partition all nodes."""
        G_fnx, G_nx, n = data
        comps = fnx.connected_components(G_fnx)
        all_nodes = set()
        for comp in comps:
            comp_set = set(comp)
            # No overlap with previously seen nodes
            assert not (all_nodes & comp_set), "Components overlap"
            all_nodes |= comp_set
        assert len(all_nodes) == n

    @given(data=general_graph())
    @settings(FAST)
    def test_number_connected_components_matches(self, data):
        """fnx and nx agree on number of connected components."""
        G_fnx, G_nx, n = data
        fnx_count = fnx.number_connected_components(G_fnx)
        nx_count = nx.number_connected_components(G_nx)
        assert fnx_count == nx_count


class TestShortestPathInvariants:
    """Properties of shortest paths."""

    @given(data=small_connected_graph(min_nodes=4, max_nodes=25))
    @settings(FAST)
    def test_shortest_path_endpoints(self, data):
        """Shortest path starts at source and ends at target."""
        G_fnx, G_nx, n = data
        source, target = 0, n - 1
        path = fnx.shortest_path(G_fnx, source, target)
        assert path[0] == source
        assert path[-1] == target

    @given(data=small_connected_graph(min_nodes=4, max_nodes=25))
    @settings(FAST)
    def test_shortest_path_all_edges_exist(self, data):
        """Every consecutive pair in the path must be an edge."""
        G_fnx, G_nx, n = data
        path = fnx.shortest_path(G_fnx, 0, n - 1)
        for i in range(len(path) - 1):
            assert G_fnx.has_edge(path[i], path[i + 1]), (
                f"Edge ({path[i]}, {path[i+1]}) not in graph"
            )

    @given(data=small_connected_graph(min_nodes=4, max_nodes=25))
    @settings(FAST)
    def test_shortest_path_length_matches_nx(self, data):
        """fnx and nx agree on shortest path length."""
        G_fnx, G_nx, n = data
        fnx_len = fnx.shortest_path_length(G_fnx, 0, n - 1)
        nx_len = nx.shortest_path_length(G_nx, 0, n - 1)
        assert fnx_len == nx_len

    @given(data=small_weighted_connected_graph(min_nodes=4, max_nodes=15))
    @settings(FAST)
    def test_weighted_shortest_path_length_matches_nx(self, data):
        """fnx and nx agree on weighted shortest path length."""
        G_fnx, G_nx, n = data
        fnx_len = fnx.shortest_path_length(G_fnx, 0, n - 1, weight="weight")
        nx_len = nx.shortest_path_length(G_nx, 0, n - 1, weight="weight")
        assert abs(fnx_len - nx_len) < 1e-6

    @given(data=small_connected_graph(min_nodes=4, max_nodes=20))
    @settings(FAST)
    def test_has_path_is_consistent(self, data):
        """has_path should be True for any pair in a connected graph."""
        G_fnx, G_nx, n = data
        assert fnx.has_path(G_fnx, 0, n - 1)


class TestCentralityInvariants:
    """Properties of centrality measures."""

    @given(data=small_connected_graph(min_nodes=3, max_nodes=20))
    @settings(FAST)
    def test_pagerank_sums_to_one(self, data):
        """PageRank values must sum to 1.0."""
        G_fnx, G_nx, n = data
        pr = fnx.pagerank(G_fnx)
        total = sum(pr.values())
        assert abs(total - 1.0) < 0.01, f"PageRank sum = {total}"

    @given(data=small_connected_graph(min_nodes=3, max_nodes=20))
    @settings(FAST)
    def test_pagerank_all_positive(self, data):
        """All PageRank values must be positive."""
        G_fnx, G_nx, n = data
        pr = fnx.pagerank(G_fnx)
        assert all(v > 0 for v in pr.values())

    @given(data=small_connected_graph(min_nodes=3, max_nodes=20))
    @settings(FAST)
    def test_pagerank_matches_nx(self, data):
        """fnx PageRank should be close to nx PageRank."""
        G_fnx, G_nx, n = data
        pr_fnx = fnx.pagerank(G_fnx)
        pr_nx = nx.pagerank(G_nx)
        for node in pr_nx:
            fnx_val = pr_fnx.get(node, pr_fnx.get(str(node)))
            assert fnx_val is not None, f"Node {node} missing from fnx result"
            assert abs(fnx_val - pr_nx[node]) < 1e-4, (
                f"PageRank[{node}]: fnx={fnx_val}, nx={pr_nx[node]}"
            )

    @given(data=small_connected_graph(min_nodes=3, max_nodes=20))
    @settings(FAST)
    def test_degree_centrality_in_range(self, data):
        """Degree centrality values must be in [0, 1]."""
        G_fnx, G_nx, n = data
        dc = fnx.degree_centrality(G_fnx)
        assert all(0 <= v <= 1 for v in dc.values())

    @given(data=small_connected_graph(min_nodes=3, max_nodes=20))
    @settings(FAST)
    def test_degree_centrality_matches_nx(self, data):
        """fnx and nx agree on degree centrality."""
        G_fnx, G_nx, n = data
        dc_fnx = fnx.degree_centrality(G_fnx)
        dc_nx = nx.degree_centrality(G_nx)
        for node in dc_nx:
            fnx_val = dc_fnx.get(node, dc_fnx.get(str(node)))
            assert fnx_val is not None, f"Node {node} missing from fnx"
            assert abs(fnx_val - dc_nx[node]) < 1e-10, (
                f"DegreeCentrality[{node}]: fnx={fnx_val}, nx={dc_nx[node]}"
            )

    @given(data=small_connected_graph(min_nodes=3, max_nodes=15))
    @settings(FAST)
    def test_betweenness_centrality_in_range(self, data):
        """Betweenness centrality values must be in [0, 1]."""
        G_fnx, G_nx, n = data
        bc = fnx.betweenness_centrality(G_fnx)
        assert all(0 <= v <= 1 for v in bc.values())

    @given(data=small_connected_graph(min_nodes=3, max_nodes=15))
    @settings(FAST)
    def test_betweenness_centrality_matches_nx(self, data):
        """fnx and nx agree on betweenness centrality."""
        G_fnx, G_nx, n = data
        bc_fnx = fnx.betweenness_centrality(G_fnx)
        bc_nx = nx.betweenness_centrality(G_nx)
        for node in bc_nx:
            fnx_val = bc_fnx.get(node, bc_fnx.get(str(node)))
            assert fnx_val is not None, f"Node {node} missing"
            assert abs(fnx_val - bc_nx[node]) < 1e-6, (
                f"Betweenness[{node}]: fnx={fnx_val}, nx={bc_nx[node]}"
            )

    @given(data=small_connected_graph(min_nodes=3, max_nodes=20))
    @settings(FAST)
    def test_closeness_centrality_matches_nx(self, data):
        """fnx and nx agree on closeness centrality."""
        G_fnx, G_nx, n = data
        cc_fnx = fnx.closeness_centrality(G_fnx)
        cc_nx = nx.closeness_centrality(G_nx)
        for node in cc_nx:
            fnx_val = cc_fnx.get(node, cc_fnx.get(str(node)))
            assert fnx_val is not None
            assert abs(fnx_val - cc_nx[node]) < 1e-6


class TestClusteringInvariants:
    """Properties of clustering measures."""

    @given(data=small_connected_graph(min_nodes=3, max_nodes=20))
    @settings(FAST)
    def test_clustering_coefficient_in_range(self, data):
        """Clustering coefficient must be in [0, 1]."""
        G_fnx, G_nx, n = data
        cc = fnx.clustering(G_fnx)
        assert all(0 <= v <= 1 for v in cc.values())

    @given(data=small_connected_graph(min_nodes=3, max_nodes=20))
    @settings(FAST)
    def test_clustering_matches_nx(self, data):
        """fnx and nx agree on clustering coefficients."""
        G_fnx, G_nx, n = data
        cc_fnx = fnx.clustering(G_fnx)
        cc_nx = nx.clustering(G_nx)
        for node in cc_nx:
            fnx_val = cc_fnx.get(node, cc_fnx.get(str(node)))
            assert fnx_val is not None
            assert abs(fnx_val - cc_nx[node]) < 1e-6

    @given(data=small_connected_graph(min_nodes=3, max_nodes=20))
    @settings(FAST)
    def test_transitivity_in_range(self, data):
        """Transitivity must be in [0, 1]."""
        G_fnx, G_nx, n = data
        t = fnx.transitivity(G_fnx)
        assert 0 <= t <= 1

    @given(data=small_connected_graph(min_nodes=3, max_nodes=20))
    @settings(FAST)
    def test_transitivity_matches_nx(self, data):
        """fnx and nx agree on transitivity."""
        G_fnx, G_nx, n = data
        t_fnx = fnx.transitivity(G_fnx)
        t_nx = nx.transitivity(G_nx)
        assert abs(t_fnx - t_nx) < 1e-6

    @given(data=small_connected_graph(min_nodes=3, max_nodes=20))
    @settings(FAST)
    def test_triangles_non_negative(self, data):
        """Triangle counts must be non-negative integers."""
        G_fnx, G_nx, n = data
        tri = fnx.triangles(G_fnx)
        assert all(v >= 0 for v in tri.values())

    @given(data=small_connected_graph(min_nodes=3, max_nodes=20))
    @settings(FAST)
    def test_triangles_match_nx(self, data):
        """fnx and nx agree on triangle counts."""
        G_fnx, G_nx, n = data
        tri_fnx = fnx.triangles(G_fnx)
        tri_nx = nx.triangles(G_nx)
        for node in tri_nx:
            fnx_val = tri_fnx.get(node, tri_fnx.get(str(node)))
            assert fnx_val is not None
            assert fnx_val == tri_nx[node]

    @given(data=small_connected_graph(min_nodes=3, max_nodes=20))
    @settings(FAST)
    def test_average_clustering_matches_nx(self, data):
        """fnx and nx agree on average clustering."""
        G_fnx, G_nx, n = data
        ac_fnx = fnx.average_clustering(G_fnx)
        ac_nx = nx.average_clustering(G_nx)
        assert abs(ac_fnx - ac_nx) < 1e-6


class TestTreeInvariants:
    """Properties of tree and forest detection."""

    @given(data=small_connected_graph(min_nodes=3, max_nodes=20))
    @settings(FAST)
    def test_tree_iff_connected_and_n_minus_1_edges(self, data):
        """is_tree should be True iff graph is connected with exactly n-1 edges."""
        G_fnx, G_nx, n = data
        is_t = fnx.is_tree(G_fnx)
        num_edges = G_fnx.number_of_edges()
        expected = (num_edges == n - 1)  # We know it's connected
        assert is_t == expected, (
            f"is_tree={is_t}, n={n}, edges={num_edges}, expected={expected}"
        )

    @given(data=general_graph(min_nodes=2, max_nodes=15))
    @settings(FAST)
    def test_is_forest_matches_nx(self, data):
        """fnx and nx agree on is_forest."""
        G_fnx, G_nx, n = data
        assert fnx.is_forest(G_fnx) == nx.is_forest(G_nx)

    @given(data=general_graph(min_nodes=2, max_nodes=15))
    @settings(FAST)
    def test_is_tree_matches_nx(self, data):
        """fnx and nx agree on is_tree."""
        G_fnx, G_nx, n = data
        assert fnx.is_tree(G_fnx) == nx.is_tree(G_nx)


class TestMatchingInvariants:
    """Properties of matching algorithms."""

    @given(data=small_connected_graph(min_nodes=4, max_nodes=20))
    @settings(FAST)
    def test_maximal_matching_edges_are_disjoint(self, data):
        """In a matching, no two edges share a node."""
        G_fnx, G_nx, n = data
        matching = fnx.maximal_matching(G_fnx)
        nodes_seen = set()
        for u, v in matching:
            assert u not in nodes_seen, f"Node {u} appears in multiple matching edges"
            assert v not in nodes_seen, f"Node {v} appears in multiple matching edges"
            nodes_seen.add(u)
            nodes_seen.add(v)

    @given(data=small_connected_graph(min_nodes=4, max_nodes=20))
    @settings(FAST)
    def test_maximal_matching_edges_exist(self, data):
        """All edges in the matching must exist in the graph."""
        G_fnx, G_nx, n = data
        matching = fnx.maximal_matching(G_fnx)
        for u, v in matching:
            assert G_fnx.has_edge(u, v) or G_fnx.has_edge(v, u), (
                f"Matching edge ({u}, {v}) not in graph"
            )

    @given(data=small_connected_graph(min_nodes=4, max_nodes=20))
    @settings(FAST)
    def test_maximal_matching_is_maximal(self, data):
        """A maximal matching can't be extended — every unmatched edge
        has at least one endpoint in the matching."""
        G_fnx, G_nx, n = data
        matching = fnx.maximal_matching(G_fnx)
        matched_nodes = set()
        for u, v in matching:
            matched_nodes.add(u)
            matched_nodes.add(v)
        # Every edge must touch at least one matched node
        for u, v in G_nx.edges():
            if u not in matched_nodes and v not in matched_nodes:
                pytest.fail(
                    f"Edge ({u}, {v}) has both endpoints unmatched — "
                    f"matching is not maximal"
                )


class TestMSTInvariants:
    """Properties of minimum spanning tree."""

    @given(data=small_weighted_connected_graph(min_nodes=3, max_nodes=15))
    @settings(FAST)
    def test_mst_has_n_minus_1_edges(self, data):
        """MST of a connected graph with n nodes has exactly n-1 edges."""
        G_fnx, G_nx, n = data
        mst = fnx.minimum_spanning_tree(G_fnx)
        assert mst.number_of_edges() == n - 1

    @given(data=small_weighted_connected_graph(min_nodes=3, max_nodes=15))
    @settings(FAST)
    def test_mst_is_connected(self, data):
        """MST must be a connected subgraph."""
        G_fnx, G_nx, n = data
        mst = fnx.minimum_spanning_tree(G_fnx)
        assert fnx.is_connected(mst)

    @given(data=small_weighted_connected_graph(min_nodes=3, max_nodes=15))
    @settings(FAST)
    def test_mst_weight_matches_nx(self, data):
        """fnx MST total weight should match nx MST total weight."""
        G_fnx, G_nx, n = data
        mst_fnx = fnx.minimum_spanning_tree(G_fnx)
        mst_nx = nx.minimum_spanning_tree(G_nx)

        fnx_weight = mst_fnx.size(weight="weight")
        nx_weight = mst_nx.size(weight="weight")
        assert abs(fnx_weight - nx_weight) < 1e-6, (
            f"MST weight: fnx={fnx_weight}, nx={nx_weight}"
        )

    @given(data=small_weighted_connected_graph(min_nodes=3, max_nodes=15))
    @settings(FAST)
    def test_mst_is_tree(self, data):
        """MST must be a tree."""
        G_fnx, G_nx, n = data
        mst = fnx.minimum_spanning_tree(G_fnx)
        assert fnx.is_tree(mst)


class TestDistanceMeasureInvariants:
    """Properties of distance measures."""

    @given(data=small_connected_graph(min_nodes=3, max_nodes=15))
    @settings(FAST)
    def test_diameter_matches_nx(self, data):
        """fnx and nx agree on diameter."""
        G_fnx, G_nx, n = data
        assert fnx.diameter(G_fnx) == nx.diameter(G_nx)

    @given(data=small_connected_graph(min_nodes=3, max_nodes=15))
    @settings(FAST)
    def test_radius_matches_nx(self, data):
        """fnx and nx agree on radius."""
        G_fnx, G_nx, n = data
        assert fnx.radius(G_fnx) == nx.radius(G_nx)

    @given(data=small_connected_graph(min_nodes=3, max_nodes=15))
    @settings(FAST)
    def test_radius_leq_diameter(self, data):
        """Radius <= Diameter always."""
        G_fnx, G_nx, n = data
        assert fnx.radius(G_fnx) <= fnx.diameter(G_fnx)

    @given(data=small_connected_graph(min_nodes=3, max_nodes=15))
    @settings(FAST)
    def test_center_nodes_have_minimum_eccentricity(self, data):
        """Center nodes must have eccentricity equal to radius."""
        G_fnx, G_nx, n = data
        r = fnx.radius(G_fnx)
        center_nodes = fnx.center(G_fnx)
        ecc = fnx.eccentricity(G_fnx)
        for node in center_nodes:
            node_ecc = ecc.get(node, ecc.get(str(node)))
            assert node_ecc == r, f"Center node {node} ecc={node_ecc}, radius={r}"

    @given(data=small_connected_graph(min_nodes=3, max_nodes=15))
    @settings(FAST)
    def test_periphery_nodes_have_maximum_eccentricity(self, data):
        """Periphery nodes must have eccentricity equal to diameter."""
        G_fnx, G_nx, n = data
        d = fnx.diameter(G_fnx)
        periphery_nodes = fnx.periphery(G_fnx)
        ecc = fnx.eccentricity(G_fnx)
        for node in periphery_nodes:
            node_ecc = ecc.get(node, ecc.get(str(node)))
            assert node_ecc == d, (
                f"Periphery node {node} ecc={node_ecc}, diameter={d}"
            )

    @given(data=small_connected_graph(min_nodes=3, max_nodes=15))
    @settings(FAST)
    def test_density_matches_nx(self, data):
        """fnx and nx agree on graph density."""
        G_fnx, G_nx, n = data
        d_fnx = fnx.density(G_fnx)
        d_nx = nx.density(G_nx)
        assert abs(d_fnx - d_nx) < 1e-10


class TestBipartiteInvariants:
    """Properties of bipartite detection."""

    @given(data=general_graph(min_nodes=2, max_nodes=20))
    @settings(FAST)
    def test_is_bipartite_matches_nx(self, data):
        """fnx and nx agree on bipartite detection."""
        G_fnx, G_nx, n = data
        assert fnx.is_bipartite(G_fnx) == nx.is_bipartite(G_nx)

    @given(data=small_connected_graph(min_nodes=3, max_nodes=15))
    @settings(FAST)
    def test_bipartite_sets_are_valid_partition(self, data):
        """If bipartite, the two sets must partition all nodes with
        no intra-set edges."""
        G_fnx, G_nx, n = data
        if not fnx.is_bipartite(G_fnx):
            return  # Skip non-bipartite graphs

        set_a, set_b = fnx.bipartite_sets(G_fnx)
        all_nodes = set(set_a) | set(set_b)
        assert len(all_nodes) == n, "Bipartite sets don't cover all nodes"
        assert not (set(set_a) & set(set_b)), "Bipartite sets overlap"

        # No edge within set_a
        set_a_s = set(set_a)
        set_b_s = set(set_b)
        for u, v in G_nx.edges():
            assert not (u in set_a_s and v in set_a_s), (
                f"Intra-set edge ({u}, {v}) in set A"
            )
            assert not (u in set_b_s and v in set_b_s), (
                f"Intra-set edge ({u}, {v}) in set B"
            )


class TestColoringInvariants:
    """Properties of graph coloring."""

    @given(data=small_connected_graph(min_nodes=3, max_nodes=20))
    @settings(FAST)
    def test_greedy_color_is_valid(self, data):
        """Greedy coloring must be proper — no two adjacent nodes share a color."""
        G_fnx, G_nx, n = data
        coloring = fnx.greedy_color(G_fnx)
        for u, v in G_nx.edges():
            cu = coloring.get(u, coloring.get(str(u)))
            cv = coloring.get(v, coloring.get(str(v)))
            assert cu != cv, f"Adjacent nodes {u} and {v} share color {cu}"

    @given(data=small_connected_graph(min_nodes=3, max_nodes=20))
    @settings(FAST)
    def test_greedy_color_all_nodes_colored(self, data):
        """Every node must receive a color."""
        G_fnx, G_nx, n = data
        coloring = fnx.greedy_color(G_fnx)
        assert len(coloring) == n


class TestCoreNumberInvariants:
    """Properties of k-core decomposition."""

    @given(data=small_connected_graph(min_nodes=3, max_nodes=20))
    @settings(FAST)
    def test_core_number_matches_nx(self, data):
        """fnx and nx agree on core numbers."""
        G_fnx, G_nx, n = data
        cn_fnx = fnx.core_number(G_fnx)
        cn_nx = nx.core_number(G_nx)
        for node in cn_nx:
            fnx_val = cn_fnx.get(node, cn_fnx.get(str(node)))
            assert fnx_val is not None
            assert fnx_val == cn_nx[node]

    @given(data=small_connected_graph(min_nodes=3, max_nodes=20))
    @settings(FAST)
    def test_core_number_non_negative(self, data):
        """Core numbers must be non-negative."""
        G_fnx, G_nx, n = data
        cn = fnx.core_number(G_fnx)
        assert all(v >= 0 for v in cn.values())


class TestEfficiencyInvariants:
    """Properties of efficiency measures."""

    @given(data=small_connected_graph(min_nodes=3, max_nodes=12))
    @settings(FAST)
    def test_efficiency_matches_nx(self, data):
        """Pairwise efficiency matches NetworkX for a deterministic node pair."""
        G_fnx, G_nx, _n = data
        nodes = sorted(G_nx.nodes())
        source = nodes[0]
        target = nodes[-1]
        eff_fnx = fnx.efficiency(G_fnx, source, target)
        eff_nx = nx.efficiency(G_nx, source, target)
        assert abs(eff_fnx - eff_nx) < 1e-6

    @given(data=small_connected_graph(min_nodes=3, max_nodes=15))
    @settings(FAST)
    def test_global_efficiency_in_range(self, data):
        """Global efficiency must be in [0, 1]."""
        G_fnx, G_nx, n = data
        eff = fnx.global_efficiency(G_fnx)
        assert 0 <= eff <= 1 + 1e-10

    @given(data=small_connected_graph(min_nodes=3, max_nodes=12))
    @settings(FAST)
    def test_global_efficiency_matches_nx(self, data):
        """fnx and nx agree on global efficiency."""
        G_fnx, G_nx, n = data
        eff_fnx = fnx.global_efficiency(G_fnx)
        eff_nx = nx.global_efficiency(G_nx)
        assert abs(eff_fnx - eff_nx) < 1e-6

    @given(data=small_connected_graph(min_nodes=3, max_nodes=10))
    @settings(FAST)
    def test_local_efficiency_in_range(self, data):
        """Local efficiency must be in [0, 1]."""
        G_fnx, G_nx, n = data
        eff = fnx.local_efficiency(G_fnx)
        assert 0 <= eff <= 1 + 1e-10


class TestGraphMeasures:
    """Properties of basic graph measures."""

    @given(data=small_connected_graph(min_nodes=3, max_nodes=20))
    @settings(FAST)
    def test_density_in_range(self, data):
        """Density must be in [0, 1]."""
        G_fnx, G_nx, n = data
        d = fnx.density(G_fnx)
        assert 0 <= d <= 1

    @given(data=small_connected_graph(min_nodes=3, max_nodes=20))
    @settings(FAST)
    def test_density_formula(self, data):
        """Density = 2*m / (n*(n-1)) for undirected graph."""
        G_fnx, G_nx, n = data
        d = fnx.density(G_fnx)
        m = G_fnx.number_of_edges()
        expected = 2 * m / (n * (n - 1)) if n > 1 else 0
        assert abs(d - expected) < 1e-10

    @given(data=small_connected_graph(min_nodes=3, max_nodes=15))
    @settings(FAST)
    def test_average_shortest_path_length_matches_nx(self, data):
        """fnx and nx agree on average shortest path length."""
        G_fnx, G_nx, n = data
        aspl_fnx = fnx.average_shortest_path_length(G_fnx)
        aspl_nx = nx.average_shortest_path_length(G_nx)
        assert abs(aspl_fnx - aspl_nx) < 1e-6


class TestEulerInvariants:
    """Properties of Eulerian detection."""

    @given(data=small_connected_graph(min_nodes=3, max_nodes=15))
    @settings(FAST)
    def test_is_eulerian_matches_nx(self, data):
        """fnx and nx agree on Eulerian detection."""
        G_fnx, G_nx, n = data
        assert fnx.is_eulerian(G_fnx) == nx.is_eulerian(G_nx)

    @given(data=small_connected_graph(min_nodes=3, max_nodes=15))
    @settings(FAST)
    def test_has_eulerian_path_matches_nx(self, data):
        """fnx and nx agree on Eulerian path detection."""
        G_fnx, G_nx, n = data
        assert fnx.has_eulerian_path(G_fnx) == nx.has_eulerian_path(G_nx)

    @given(data=small_connected_graph(min_nodes=3, max_nodes=15))
    @settings(FAST)
    def test_eulerian_implies_all_even_degree(self, data):
        """If graph is Eulerian, all nodes must have even degree."""
        G_fnx, G_nx, n = data
        if fnx.is_eulerian(G_fnx):
            for node, deg in G_nx.degree():
                assert deg % 2 == 0, f"Eulerian graph has odd degree node {node}"


class TestGraphConstruction:
    """Properties of graph construction and mutation."""

    @given(
        n=st.integers(min_value=0, max_value=50),
        edges=st.lists(
            st.tuples(
                st.integers(min_value=0, max_value=49),
                st.integers(min_value=0, max_value=49),
            ),
            max_size=100,
        ),
    )
    @settings(FAST)
    def test_node_edge_counts_match_nx(self, n, edges):
        """Node and edge counts should match between fnx and nx."""
        G_fnx = fnx.Graph()
        G_nx = nx.Graph()

        for i in range(n):
            G_fnx.add_node(i)
            G_nx.add_node(i)

        for u, v in edges:
            if u != v:  # Skip self-loops (fnx may differ)
                G_fnx.add_edge(u, v)
                G_nx.add_edge(u, v)

        assert G_fnx.number_of_nodes() == G_nx.number_of_nodes()
        assert G_fnx.number_of_edges() == G_nx.number_of_edges()

    @given(
        n=st.integers(min_value=1, max_value=30),
    )
    @settings(FAST)
    def test_generator_path_graph_invariants(self, n):
        """Path graph generator should produce n nodes and n-1 edges."""
        G = fnx.path_graph(n)
        assert G.number_of_nodes() == n
        assert G.number_of_edges() == n - 1
        if n > 1:
            assert fnx.is_connected(G)
            assert fnx.is_tree(G)

    @given(
        n=st.integers(min_value=3, max_value=30),
    )
    @settings(FAST)
    def test_generator_cycle_graph_invariants(self, n):
        """Cycle graph generator should produce n nodes and n edges."""
        G = fnx.cycle_graph(n)
        assert G.number_of_nodes() == n
        assert G.number_of_edges() == n
        assert fnx.is_connected(G)
        assert fnx.is_eulerian(G)  # All degrees are 2

    @given(
        n=st.integers(min_value=1, max_value=30),
    )
    @settings(FAST)
    def test_generator_complete_graph_invariants(self, n):
        """Complete graph K_n should have n*(n-1)/2 edges."""
        G = fnx.complete_graph(n)
        assert G.number_of_nodes() == n
        expected_edges = n * (n - 1) // 2
        assert G.number_of_edges() == expected_edges
        if n > 1:
            assert fnx.is_connected(G)
            assert abs(fnx.density(G) - 1.0) < 1e-10

    @given(
        n=st.integers(min_value=1, max_value=30),
    )
    @settings(FAST)
    def test_generator_star_graph_invariants(self, n):
        """Star graph S_n should have n+1 nodes and n edges."""
        G = fnx.star_graph(n)
        assert G.number_of_nodes() == n + 1
        assert G.number_of_edges() == n
        if n > 0:
            assert fnx.is_connected(G)
            assert fnx.is_tree(G)


class TestExpansionMetrics:
    """Properties of graph expansion and connectivity metrics."""

    @given(data=small_connected_graph(min_nodes=4, max_nodes=15))
    @settings(FAST)
    def test_volume_matches_nx(self, data):
        """Volume of a node set should match NetworkX."""
        G_fnx, G_nx, n = data
        nodes = list(range(min(3, n)))
        fnx_vol = fnx.volume(G_fnx, nodes)
        nx_vol = nx.volume(G_nx, nodes)
        assert fnx_vol == nx_vol

    @given(data=small_connected_graph(min_nodes=4, max_nodes=15))
    @settings(FAST)
    def test_volume_all_nodes_equals_twice_edges(self, data):
        """Volume of all nodes = 2 * number of edges (handshaking lemma)."""
        G_fnx, G_nx, n = data
        all_nodes = list(range(n))
        vol = fnx.volume(G_fnx, all_nodes)
        assert vol == 2 * G_fnx.number_of_edges()

    @given(data=small_connected_graph(min_nodes=4, max_nodes=15))
    @settings(FAST)
    def test_conductance_matches_nx(self, data):
        """Conductance should match NetworkX for a node subset."""
        G_fnx, G_nx, n = data
        # Pick a non-trivial subset (not empty, not full)
        k = max(1, n // 3)
        nodes = list(range(k))
        fnx_val = fnx.conductance(G_fnx, nodes)
        nx_val = nx.conductance(G_nx, nodes)
        assert abs(fnx_val - nx_val) < 1e-10

    @given(data=small_connected_graph(min_nodes=4, max_nodes=15))
    @settings(FAST)
    def test_conductance_non_negative(self, data):
        """Conductance should always be non-negative."""
        G_fnx, _, n = data
        k = max(1, n // 3)
        nodes = list(range(k))
        assert fnx.conductance(G_fnx, nodes) >= 0.0

    @given(data=small_connected_graph(min_nodes=4, max_nodes=15))
    @settings(FAST)
    def test_edge_expansion_non_negative(self, data):
        """Edge expansion should be non-negative."""
        G_fnx, _, n = data
        k = max(1, n // 3)
        nodes = list(range(k))
        assert fnx.edge_expansion(G_fnx, nodes) >= 0.0

    @given(data=small_connected_graph(min_nodes=4, max_nodes=15))
    @settings(FAST)
    def test_node_expansion_non_negative(self, data):
        """Node expansion should be non-negative."""
        G_fnx, _, n = data
        k = max(1, n // 3)
        nodes = list(range(k))
        assert fnx.node_expansion(G_fnx, nodes) >= 0.0

    @given(data=small_connected_graph(min_nodes=4, max_nodes=15))
    @settings(FAST)
    def test_boundary_expansion_leq_volume_ratio(self, data):
        """Boundary expansion <= volume / |S| for connected graphs."""
        G_fnx, _, n = data
        k = max(1, n // 3)
        nodes = list(range(k))
        be = fnx.boundary_expansion(G_fnx, nodes)
        vol = fnx.volume(G_fnx, nodes)
        # boundary_expansion = |edge_boundary| / |S|
        # |edge_boundary| <= vol since each boundary edge contributes to vol
        assert be <= vol / k + 1e-10

    @given(data=small_connected_graph(min_nodes=4, max_nodes=15))
    @settings(FAST)
    def test_non_edges_count(self, data):
        """Non-edges + edges = total possible edges for simple graph."""
        G_fnx, _, n = data
        ne = len(fnx.non_edges(G_fnx))
        total_possible = n * (n - 1) // 2
        assert ne + G_fnx.number_of_edges() == total_possible

    @given(data=small_connected_graph(min_nodes=3, max_nodes=12))
    @settings(FAST, deadline=None)
    def test_is_k_edge_connected_monotonic(self, data):
        """If graph is k-edge-connected, it's also (k-1)-edge-connected."""
        G_fnx, _, n = data
        # Find the edge connectivity
        for k in range(1, n):
            if not fnx.is_k_edge_connected(G_fnx, k):
                # All lower values should be True
                for j in range(k):
                    assert fnx.is_k_edge_connected(G_fnx, j)
                break

    @given(data=small_connected_graph(min_nodes=3, max_nodes=10))
    @settings(FAST)
    def test_average_node_connectivity_bounds(self, data):
        """Average node connectivity is between 0 and n-1."""
        G_fnx, _, n = data
        avg = fnx.average_node_connectivity(G_fnx)
        assert avg >= 0.0
        assert avg <= n - 1 + 1e-10

    @given(data=small_connected_graph(min_nodes=3, max_nodes=10))
    @settings(FAST)
    def test_global_node_connectivity_leq_min_degree(self, data):
        """Node connectivity <= minimum degree (Whitney's theorem)."""
        G_fnx, G_nx, n = data
        gnc = fnx.global_node_connectivity(G_fnx)
        min_deg = min(d for _, d in G_nx.degree())
        assert gnc <= min_deg
