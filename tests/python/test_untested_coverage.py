"""Coverage tests for previously-untested FrankenNetworkX functions.

Ensures basic smoke-test coverage: function is callable, returns the
expected type, and doesn't crash on simple inputs.
"""
import pytest

try:
    import networkx as nx  # noqa: F401
    HAS_NX = True
except ImportError:
    HAS_NX = False

try:
    import numpy as np  # noqa: F401
    HAS_NP = True
except ImportError:
    HAS_NP = False

import franken_networkx as fnx

needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")
needs_np = pytest.mark.skipif(not HAS_NP, reason="numpy not installed")


def _path5():
    return fnx.path_graph(5)


def _cycle5():
    return fnx.cycle_graph(5)


def _k4():
    return fnx.complete_graph(4)


def _digraph():
    D = fnx.DiGraph()
    D.add_edges_from([(0, 1), (1, 2), (2, 3), (3, 0), (0, 2)])
    return D


# ---------------------------------------------------------------------------
# Connectivity & cuts
# ---------------------------------------------------------------------------

class TestConnectivityCoverage:
    def test_all_neighbors(self):
        G = _path5()
        nbrs = fnx.all_neighbors(G, 2)
        assert set(nbrs) == {1, 3}

    def test_all_neighbors_directed(self):
        D = _digraph()
        nbrs = fnx.all_neighbors(D, 0)
        assert 1 in nbrs  # successor
        assert 3 in nbrs  # predecessor

    def test_has_bridges(self):
        G = _path5()
        assert fnx.has_bridges(G) is True

    def test_has_bridges_cycle(self):
        G = _cycle5()
        assert fnx.has_bridges(G) is False

    def test_minimum_edge_cut(self):
        G = _k4()
        cut = fnx.minimum_edge_cut(G)
        assert len(cut) == 3  # K4 has edge connectivity 3

    def test_k_edge_subgraphs(self):
        G = _path5()
        comps = list(fnx.k_edge_subgraphs(G, 2))
        # Path graph has edge connectivity 1, so each node is its own 2-edge component
        assert len(comps) == 5

    def test_k_core(self):
        G = _k4()
        core = fnx.k_core(G)
        assert core.number_of_nodes() == 4  # K4 is 3-core

    def test_k_shell(self):
        G = _k4()
        shell = fnx.k_shell(G)
        assert shell.number_of_nodes() == 4


# ---------------------------------------------------------------------------
# Shortest paths & distance
# ---------------------------------------------------------------------------

class TestDistanceCoverage:
    def test_all_simple_edge_paths(self):
        G = fnx.Graph()
        G.add_edges_from([(0, 1), (1, 2), (0, 2)])
        paths = list(fnx.all_simple_edge_paths(G, 0, 2))
        assert len(paths) == 2

    def test_single_source_all_shortest_paths(self):
        G = _path5()
        results = list(fnx.single_source_all_shortest_paths(G, 0))
        assert len(results) > 0

    def test_minimum_cycle_basis(self):
        G = fnx.Graph()
        G.add_edges_from([(0, 1), (1, 2), (2, 0)])
        basis = fnx.minimum_cycle_basis(G)
        assert len(basis) == 1


# ---------------------------------------------------------------------------
# Centrality extras
# ---------------------------------------------------------------------------

class TestCentralityExtras:
    def test_edge_current_flow_betweenness(self):
        G = _path5()
        ebc = fnx.edge_current_flow_betweenness_centrality(G)
        assert len(ebc) > 0

    def test_approximate_current_flow_betweenness(self):
        G = _path5()
        abc = fnx.approximate_current_flow_betweenness_centrality(G)
        assert len(abc) == 5

    def test_closeness_vitality(self):
        G = _path5()
        cv = fnx.closeness_vitality(G)
        assert len(cv) == 5

    def test_subgraph_centrality(self):
        G = _k4()
        sc = fnx.subgraph_centrality(G)
        assert len(sc) == 4
        assert all(v > 0 for v in sc.values())

    def test_subgraph_centrality_exp(self):
        G = _k4()
        sc = fnx.subgraph_centrality_exp(G)
        assert len(sc) == 4

    def test_effective_size(self):
        G = _k4()
        es = fnx.effective_size(G)
        assert len(es) == 4

    def test_local_constraint(self):
        G = _k4()
        lc = fnx.local_constraint(G, 0, 1)
        assert isinstance(lc, float)

    def test_information_centrality(self):
        G = _k4()
        ic = fnx.information_centrality(G)
        assert len(ic) == 4

    def test_common_neighbor_centrality(self):
        G = _k4()
        cnc = list(fnx.common_neighbor_centrality(G, [(0, 1)]))
        assert len(cnc) == 1


# ---------------------------------------------------------------------------
# DAG & topological
# ---------------------------------------------------------------------------

class TestDAGCoverage:
    def test_lexicographic_topological_sort(self):
        D = fnx.DiGraph()
        D.add_edges_from([(0, 1), (0, 2), (1, 3), (2, 3)])
        result = list(fnx.lexicographic_topological_sort(D))
        assert result[0] == 0
        assert result[-1] == 3

    def test_transitive_closure_dag(self):
        D = fnx.DiGraph()
        D.add_edges_from([(0, 1), (1, 2)])
        tc = fnx.transitive_closure_dag(D)
        assert tc.has_edge(0, 2)


# ---------------------------------------------------------------------------
# Cycles
# ---------------------------------------------------------------------------

class TestCyclesCoverage:
    def test_chordless_cycles(self):
        G = fnx.Graph()
        G.add_edges_from([(0, 1), (1, 2), (2, 3), (3, 0)])
        cycles = list(fnx.chordless_cycles(G))
        assert len(cycles) >= 1

    def test_recursive_simple_cycles(self):
        D = _digraph()
        cycles = list(fnx.recursive_simple_cycles(D))
        assert len(cycles) > 0

    @needs_nx
    def test_recursive_simple_cycles_undirected_error_matches_networkx(self):
        for graph_type in ("Graph", "MultiGraph"):
            G_fnx = getattr(fnx, graph_type)()
            G_nx = getattr(nx, graph_type)()
            for graph in (G_fnx, G_nx):
                graph.add_edge(0, 1)
                graph.add_edge(1, 2)
                graph.add_edge(2, 0)

            with pytest.raises(fnx.NetworkXNotImplemented, match="not implemented for undirected type"):
                fnx.recursive_simple_cycles(G_fnx)
            with pytest.raises(nx.NetworkXNotImplemented, match="not implemented for undirected type"):
                nx.recursive_simple_cycles(G_nx)

    @needs_nx
    def test_recursive_simple_cycles_multidigraph_matches_networkx(self):
        D_fnx = fnx.MultiDiGraph()
        D_nx = nx.MultiDiGraph()
        for graph in (D_fnx, D_nx):
            graph.add_edge(1, 2, key="k1")
            graph.add_edge(2, 1, key="k2")

        assert fnx.recursive_simple_cycles(D_fnx) == nx.recursive_simple_cycles(D_nx)


# ---------------------------------------------------------------------------
# Graph operations
# ---------------------------------------------------------------------------

class TestGraphOpsCoverage:
    def test_contracted_nodes(self):
        G = _path5()
        H = fnx.contracted_nodes(G, 0, 1)
        assert H.number_of_nodes() == 4

    def test_contracted_edge(self):
        G = _path5()
        H = fnx.contracted_edge(G, (1, 2))
        assert H.number_of_nodes() == 4

    def test_induced_subgraph(self):
        G = _k4()
        H = fnx.induced_subgraph(G, [0, 1, 2])
        assert H.number_of_nodes() == 3
        assert H.number_of_edges() == 3

    def test_subgraph_view(self):
        G = _k4()
        H = fnx.subgraph_view(G, filter_node=lambda n: n != 3)
        assert 3 not in H.nodes()

    def test_restricted_view(self):
        G = _k4()
        H = fnx.restricted_view(G, [3], [])
        assert 3 not in H.nodes()

    def test_equivalence_classes(self):
        items = [1, 2, 3, 4, 5, 6]
        classes = list(fnx.equivalence_classes(items, lambda a, b: a % 2 == b % 2))
        assert len(classes) == 2


# ---------------------------------------------------------------------------
# Triadic
# ---------------------------------------------------------------------------

class TestTriadicCoverage:
    def test_all_triads(self):
        D = fnx.DiGraph()
        D.add_edges_from([(0, 1), (1, 2), (2, 0)])
        triads = list(fnx.all_triads(D))
        assert len(triads) >= 1

    def test_is_triad(self):
        D = fnx.DiGraph()
        D.add_edges_from([(0, 1), (1, 2), (2, 0)])
        assert fnx.is_triad(D) is True

    def test_triads_by_type(self):
        D = fnx.DiGraph()
        D.add_edges_from([(0, 1), (1, 2), (2, 0)])
        result = fnx.triads_by_type(D)
        assert '030C' in result


# ---------------------------------------------------------------------------
# Matrix functions
# ---------------------------------------------------------------------------

@needs_np
class TestMatrixCoverage:
    def test_adjacency_matrix(self):
        G = _path5()
        A = fnx.adjacency_matrix(G)
        assert A.shape == (5, 5)

    def test_adjacency_spectrum(self):
        G = _path5()
        spec = fnx.adjacency_spectrum(G)
        assert len(spec) == 5

    def test_degree_mixing_matrix(self):
        G = _k4()
        M = fnx.degree_mixing_matrix(G)
        assert M.shape[0] > 0

    def test_normalized_laplacian_matrix(self):
        G = _path5()
        NL = fnx.normalized_laplacian_matrix(G)
        assert NL.shape == (5, 5)

    def test_incidence_matrix(self):
        G = _path5()
        inc_mat = fnx.incidence_matrix(G)
        assert inc_mat.shape[0] == 5


# ---------------------------------------------------------------------------
# Link prediction
# ---------------------------------------------------------------------------

class TestLinkPredictionCoverage:
    def test_cn_soundarajan_hopcroft(self):
        G = fnx.Graph()
        G.add_node(0, community=0)
        G.add_node(1, community=0)
        G.add_node(2, community=1)
        G.add_edges_from([(0, 1), (1, 2)])
        preds = list(fnx.cn_soundarajan_hopcroft(G, [(0, 2)]))
        assert len(preds) == 1

    def test_node_degree_xy(self):
        G = _path5()
        pairs = list(fnx.node_degree_xy(G))
        assert len(pairs) > 0

    def test_node_degree_xy_nodes_filter_matches_networkx(self):
        import networkx as nx

        G_fnx = _path5()
        G_nx = nx.path_graph(5)
        assert list(fnx.node_degree_xy(G_fnx, nodes=[0, 1, 4])) == list(
            nx.node_degree_xy(G_nx, nodes=[0, 1, 4])
        )


# ---------------------------------------------------------------------------
# Classic named graphs
# ---------------------------------------------------------------------------

class TestNamedGraphCoverage:
    def test_florentine_families(self):
        G = fnx.florentine_families_graph()
        assert G.number_of_nodes() > 0

    def test_les_miserables(self):
        G = fnx.les_miserables_graph()
        assert G.number_of_nodes() > 0

    def test_davis_southern_women(self):
        G = fnx.davis_southern_women_graph()
        assert G.number_of_nodes() > 0

    def test_mycielski(self):
        G = fnx.mycielski_graph(4)
        assert G.number_of_nodes() > 0


# ---------------------------------------------------------------------------
# Edge swap
# ---------------------------------------------------------------------------

class TestEdgeSwapCoverage:
    def test_directed_edge_swap(self):
        D = fnx.DiGraph()
        D.add_edges_from([(0, 1), (1, 2), (2, 3), (3, 0)])
        result = fnx.directed_edge_swap(D, nswap=1, max_tries=100, seed=42)
        assert result.number_of_edges() == 4

    def test_connected_double_edge_swap(self):
        G = _cycle5()
        G.add_edges_from([(0, 2), (1, 3)])
        # connected_double_edge_swap returns the number of swaps performed
        result = fnx.connected_double_edge_swap(G, nswap=1, seed=42)
        assert isinstance(result, int)


# ---------------------------------------------------------------------------
# Misc algorithms
# ---------------------------------------------------------------------------

class TestMiscCoverage:
    def test_dispersion(self):
        G = _k4()
        d = fnx.dispersion(G)
        assert isinstance(d, dict)

    def test_intersection_array(self):
        G = fnx.petersen_graph()
        ia = fnx.intersection_array(G)
        assert ia is not None

    def test_local_bridges(self):
        G = _path5()
        bridges = list(fnx.local_bridges(G))
        assert isinstance(bridges, list)

    def test_is_d_separator(self):
        D = fnx.DiGraph()
        D.add_edges_from([(0, 1), (1, 2)])
        assert fnx.is_d_separator(D, {0}, {2}, {1}) is True

    def test_random_tree(self):
        T = fnx.random_tree(10, seed=42)
        assert T.number_of_nodes() == 10
        assert fnx.is_tree(T)
