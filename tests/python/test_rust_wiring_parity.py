"""Parity tests for Python functions wired to Rust bindings.

Verifies that the Rust-backed implementations match NetworkX behavior
for the functions OliveShore wired in the 2026-03-31/04-01 session.
"""
import pytest

try:
    import networkx as nx
    HAS_NX = True
except ImportError:
    HAS_NX = False

import franken_networkx as fnx

needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


def _make_identical_graphs():
    """Build identical undirected graph in both FNX and NX."""
    edges = [(0, 1), (1, 2), (2, 3), (3, 4), (4, 0), (0, 2), (1, 3)]
    G_fnx = fnx.Graph()
    G_nx = nx.Graph()
    for u, v in edges:
        G_fnx.add_edge(u, v)
        G_nx.add_edge(u, v)
    return G_fnx, G_nx


def _make_identical_digraphs():
    """Build identical directed graph in both FNX and NX."""
    edges = [(0, 1), (1, 2), (2, 3), (3, 0), (0, 3)]
    D_fnx = fnx.DiGraph()
    D_nx = nx.DiGraph()
    for u, v in edges:
        D_fnx.add_edge(u, v)
        D_nx.add_edge(u, v)
    return D_fnx, D_nx


def _make_empty_graphs():
    return fnx.Graph(), nx.Graph()


def _make_directed_single_edge_graphs():
    fnx_graph = fnx.DiGraph()
    nx_graph = nx.DiGraph()
    fnx_graph.add_edge(0, 1)
    nx_graph.add_edge(0, 1)
    return fnx_graph, nx_graph


def _make_weighted_single_edge_graphs():
    fnx_graph = fnx.Graph()
    nx_graph = nx.Graph()
    fnx_graph.add_edge(0, 1, capacity=1)
    nx_graph.add_edge(0, 1, capacity=1)
    return fnx_graph, nx_graph


# ---------------------------------------------------------------------------
# Triadic analysis
# ---------------------------------------------------------------------------

@needs_nx
class TestTriadicParity:
    def test_triadic_census_matches(self):
        D_fnx, D_nx = _make_identical_digraphs()
        assert fnx.triadic_census(D_fnx) == nx.triadic_census(D_nx)

    def test_triad_type_all_16(self):
        for t in ['003', '012', '102', '021D', '021U', '021C', '111D', '111U',
                   '030T', '030C', '201', '120D', '120U', '120C', '210', '300']:
            G = fnx.triad_graph(t)
            assert fnx.triad_type(G) == t, f"triad_type mismatch for {t}"


# ---------------------------------------------------------------------------
# Self-loop functions
# ---------------------------------------------------------------------------

class TestSelfLoopParity:
    def test_number_of_selfloops(self):
        G = fnx.Graph()
        G.add_edge(0, 0)
        G.add_edge(1, 2)
        assert fnx.number_of_selfloops(G) == 1

    def test_nodes_with_selfloops(self):
        G = fnx.Graph()
        G.add_edge(0, 0)
        G.add_edge(1, 1)
        G.add_edge(2, 3)
        assert set(fnx.nodes_with_selfloops(G)) == {0, 1}

    def test_selfloop_edges(self):
        G = fnx.Graph()
        G.add_edge(0, 0)
        G.add_edge(1, 2)
        loops = list(fnx.selfloop_edges(G))
        assert len(loops) == 1
        assert loops[0][0] == loops[0][1]


# ---------------------------------------------------------------------------
# Graph operations
# ---------------------------------------------------------------------------

@needs_nx
class TestGraphOpsParity:
    def test_power_path_graph(self):
        G_fnx = fnx.path_graph(5)
        result = fnx.power(G_fnx, 2)
        # In G^2, nodes within distance ≤ 2 are connected
        assert result.has_edge(0, 2)
        assert result.has_edge(1, 3)
        assert result.has_edge(2, 4)
        # Nodes 0 and 3 are distance 3 apart, NOT connected in G^2
        assert not result.has_edge(0, 3)

    def test_to_dict_of_lists(self):
        G = fnx.path_graph(3)
        d = fnx.to_dict_of_lists(G)
        assert set(d[0]) == {1}
        assert set(d[1]) == {0, 2}
        assert set(d[2]) == {1}


# ---------------------------------------------------------------------------
# Flow & connectivity
# ---------------------------------------------------------------------------

@needs_nx
class TestFlowParity:
    def test_flow_hierarchy_dag(self):
        D_fnx = fnx.DiGraph()
        D_fnx.add_edges_from([(0, 1), (1, 2)])
        assert fnx.flow_hierarchy(D_fnx) == 1.0

    def test_flow_hierarchy_cycle(self):
        D_fnx = fnx.DiGraph()
        D_fnx.add_edges_from([(0, 1), (1, 2), (2, 0)])
        assert fnx.flow_hierarchy(D_fnx) == 0.0

    def test_gomory_hu_tree_basic(self):
        G = fnx.Graph()
        G.add_edge(0, 1, weight=3)
        G.add_edge(1, 2, weight=5)
        T = fnx.gomory_hu_tree(G, capacity='weight')
        assert T.number_of_nodes() == 3

    @pytest.mark.parametrize(
        "flow_func",
        [nx.algorithms.flow.edmonds_karp, nx.algorithms.flow.shortest_augmenting_path],
    )
    def test_gomory_hu_tree_flow_func_matches_networkx_without_fallback(
        self, monkeypatch, flow_func
    ):
        G_fnx = fnx.Graph()
        G_nx = nx.Graph()
        for u, v, capacity in [
            (0, 1, 3),
            (1, 2, 5),
            (2, 3, 4),
            (0, 3, 2),
            (0, 2, 1),
        ]:
            G_fnx.add_edge(u, v, capacity=capacity)
            G_nx.add_edge(u, v, capacity=capacity)

        expected = nx.gomory_hu_tree(G_nx, flow_func=flow_func)

        def fail(*args, **kwargs):
            raise AssertionError("unexpected NetworkX gomory_hu_tree fallback")

        monkeypatch.setattr(nx, "gomory_hu_tree", fail)

        actual = fnx.gomory_hu_tree(G_fnx, flow_func=flow_func)
        expected_edges = sorted(
            (min(u, v), max(u, v), data["weight"]) for u, v, data in expected.edges(data=True)
        )
        actual_edges = sorted(
            (min(u, v), max(u, v), data["weight"]) for u, v, data in actual.edges(data=True)
        )
        assert actual_edges == expected_edges

    @pytest.mark.parametrize(
        ("graph_factory", "flow_func"),
        [
            (_make_empty_graphs, None),
            (_make_directed_single_edge_graphs, nx.algorithms.flow.edmonds_karp),
            (_make_weighted_single_edge_graphs, 1),
        ],
    )
    def test_gomory_hu_tree_error_contract_matches_networkx_without_fallback(
        self, monkeypatch, graph_factory, flow_func
    ):
        G_fnx, G_nx = graph_factory()

        try:
            if flow_func is None:
                nx.gomory_hu_tree(G_nx)
            else:
                nx.gomory_hu_tree(G_nx, flow_func=flow_func)
        except Exception as exc:
            expected = exc
        else:
            raise AssertionError("expected NetworkX gomory_hu_tree to fail for this case")

        def fail(*args, **kwargs):
            raise AssertionError("unexpected NetworkX gomory_hu_tree fallback")

        monkeypatch.setattr(nx, "gomory_hu_tree", fail)

        fnx_exc_type = getattr(fnx, type(expected).__name__)
        with pytest.raises(fnx_exc_type, match=str(expected)):
            if flow_func is None:
                fnx.gomory_hu_tree(G_fnx)
            else:
                fnx.gomory_hu_tree(G_fnx, flow_func=flow_func)

    def test_edge_disjoint_paths(self):
        G = fnx.Graph()
        G.add_edges_from([(0, 1), (0, 2), (1, 3), (2, 3)])
        paths = list(fnx.edge_disjoint_paths(G, 0, 3))
        assert len(paths) == 2

    def test_node_disjoint_paths(self):
        G = fnx.Graph()
        G.add_edges_from([(0, 1), (0, 2), (1, 3), (2, 3)])
        paths = list(fnx.node_disjoint_paths(G, 0, 3))
        assert len(paths) == 2

    def test_all_pairs_node_connectivity_path(self):
        G_fnx, G_nx = _make_identical_graphs()
        fnx_result = fnx.all_pairs_node_connectivity(G_fnx)
        nx_result = nx.all_pairs_node_connectivity(G_nx)
        for u in nx_result:
            for v in nx_result[u]:
                assert fnx_result[u][v] == nx_result[u][v], f"mismatch at ({u},{v})"


# ---------------------------------------------------------------------------
# Structural properties
# ---------------------------------------------------------------------------

class TestStructuralParity:
    def test_is_strongly_regular_petersen(self):
        G = fnx.petersen_graph()
        assert fnx.is_strongly_regular(G) is True

    def test_is_strongly_regular_path(self):
        G = fnx.path_graph(4)
        assert fnx.is_strongly_regular(G) is False

    def test_is_at_free_path(self):
        G = fnx.path_graph(5)
        assert fnx.is_at_free(G) is True

    def test_find_asteroidal_triple_cycle(self):
        G = fnx.cycle_graph(6)
        result = fnx.find_asteroidal_triple(G)
        assert result is not None


# ---------------------------------------------------------------------------
# Distance indices
# ---------------------------------------------------------------------------

@needs_nx
class TestDistanceIndicesParity:
    def test_gutman_index(self):
        G_fnx, G_nx = _make_identical_graphs()
        assert abs(fnx.gutman_index(G_fnx) - nx.gutman_index(G_nx)) < 1e-10

    def test_schultz_index(self):
        G_fnx, G_nx = _make_identical_graphs()
        assert abs(fnx.schultz_index(G_fnx) - nx.schultz_index(G_nx)) < 1e-10

    def test_hyper_wiener_index(self):
        G_fnx = fnx.path_graph(4)
        G_nx = nx.path_graph(4)
        assert abs(fnx.hyper_wiener_index(G_fnx) - nx.hyper_wiener_index(G_nx)) < 1e-10

    def test_harmonic_diameter(self):
        G = fnx.path_graph(4)
        hd = fnx.harmonic_diameter(G)
        assert hd > 0


# ---------------------------------------------------------------------------
# Centrality
# ---------------------------------------------------------------------------

@needs_nx
class TestCentralityParity:
    def test_second_order_centrality(self):
        G_fnx, G_nx = _make_identical_graphs()
        soc_fnx = fnx.second_order_centrality(G_fnx)
        soc_nx = nx.second_order_centrality(G_nx)
        for n in soc_nx:
            assert abs(soc_fnx[n] - soc_nx[n]) < 1e-6, f"node {n}: {soc_fnx[n]} vs {soc_nx[n]}"

    def test_group_betweenness(self):
        G_fnx, G_nx = _make_identical_graphs()
        gb_fnx = fnx.group_betweenness_centrality(G_fnx, [0, 1])
        gb_nx = nx.group_betweenness_centrality(G_nx, [0, 1])
        assert abs(gb_fnx - gb_nx) < 1e-6

    def test_group_closeness(self):
        G_fnx, G_nx = _make_identical_graphs()
        gc_fnx = fnx.group_closeness_centrality(G_fnx, [0, 1])
        gc_nx = nx.group_closeness_centrality(G_nx, [0, 1])
        assert abs(gc_fnx - gc_nx) < 1e-6

    def test_communicability_betweenness(self):
        G = fnx.path_graph(4)
        cbc = fnx.communicability_betweenness_centrality(G)
        assert len(cbc) == 4
        # Interior nodes should have higher centrality
        assert cbc[1] > cbc[0]
        assert cbc[2] > cbc[3]

    def test_current_flow_betweenness(self):
        G = fnx.path_graph(4)
        cfb = fnx.current_flow_betweenness_centrality(G)
        assert len(cfb) == 4
        # Interior nodes have higher current-flow betweenness
        assert cfb[1] >= cfb[0]


# ---------------------------------------------------------------------------
# Community & similarity
# ---------------------------------------------------------------------------

class TestCommunityParity:
    def test_k_clique_communities(self):
        G = fnx.complete_graph(5)
        comms = list(fnx.k_clique_communities(G, 3))
        # Complete graph K5 has one 3-clique community containing all 5 nodes
        assert len(comms) == 1
        assert len(comms[0]) == 5

    def test_k_clique_communities_disconnected(self):
        G = fnx.Graph()
        G.add_edges_from([(0, 1), (1, 2), (2, 0)])
        G.add_edges_from([(3, 4), (4, 5), (5, 3)])
        comms = sorted(fnx.k_clique_communities(G, 3), key=min)
        assert len(comms) == 2

    def test_simrank_similarity_self(self):
        G = fnx.path_graph(3)
        sim = fnx.simrank_similarity(G, 0, 0)
        assert abs(sim - 1.0) < 1e-6


# ---------------------------------------------------------------------------
# DAG operations
# ---------------------------------------------------------------------------

@needs_nx
class TestDAGParity:
    def test_all_topological_sorts_diamond(self):
        D = fnx.DiGraph()
        D.add_edges_from([(0, 1), (0, 2), (1, 3), (2, 3)])
        sorts = list(fnx.all_topological_sorts(D))
        # Diamond DAG has exactly 2 topological sorts
        assert len(sorts) == 2
        for s in sorts:
            assert s[0] == 0 and s[-1] == 3

    def test_all_topological_sorts_cycle_raises(self):
        D = fnx.DiGraph()
        D.add_edges_from([(0, 1), (1, 0)])
        with pytest.raises(fnx.NetworkXUnfeasible):
            list(fnx.all_topological_sorts(D))


# ---------------------------------------------------------------------------
# Traversal
# ---------------------------------------------------------------------------

class TestTraversalParity:
    def test_bfs_labeled_edges_forward(self):
        G = fnx.path_graph(4)
        assert list(fnx.bfs_labeled_edges(G, 0)) == [
            (0, 1, "tree"),
            (1, 2, "tree"),
            (2, 3, "tree"),
        ]

    def test_generic_bfs_edges_depth_limit(self):
        G = fnx.path_graph(10)
        edges = list(fnx.generic_bfs_edges(G, 0, depth_limit=2))
        reached = {0} | {v for _, v in edges}
        assert max(reached) <= 2

    @needs_nx
    def test_generic_bfs_edges_rejects_sort_neighbors_matches_networkx(self):
        G_fnx = fnx.path_graph(4)
        G_nx = nx.path_graph(4)

        for call_f, call_n in (
            (
                lambda: fnx.generic_bfs_edges(G_fnx, 0, sort_neighbors=sorted),
                lambda: nx.generic_bfs_edges(G_nx, 0, sort_neighbors=sorted),
            ),
            (
                lambda: fnx.generic_bfs_edges(
                    G_fnx, 0, neighbors=G_fnx.neighbors, sort_neighbors=sorted
                ),
                lambda: nx.generic_bfs_edges(
                    G_nx, 0, neighbors=G_nx.neighbors, sort_neighbors=sorted
                ),
            ),
        ):
            with pytest.raises(TypeError) as fnx_exc:
                list(call_f())
            with pytest.raises(TypeError) as nx_exc:
                list(call_n())
            assert str(fnx_exc.value) == str(nx_exc.value)

    @needs_nx
    def test_bfs_labeled_edges_matches_networkx(self):
        G_fnx = fnx.Graph()
        G_nx = nx.Graph()
        for G in (G_fnx, G_nx):
            G.add_edge("a", "b")
            G.add_edge("b", "c")
            G.add_edge("c", "a")
            G.add_edge("c", "d")
        assert list(fnx.bfs_labeled_edges(G_fnx, "a")) == list(
            nx.bfs_labeled_edges(G_nx, "a")
        )

    @needs_nx
    def test_bfs_labeled_edges_digraph_matches_networkx(self):
        D_fnx = fnx.DiGraph()
        D_nx = nx.DiGraph()
        for D in (D_fnx, D_nx):
            D.add_edge("a", "b")
            D.add_edge("a", "c")
            D.add_edge("b", "c")
            D.add_edge("c", "d")
        assert list(fnx.bfs_labeled_edges(D_fnx, "a")) == list(
            nx.bfs_labeled_edges(D_nx, "a")
        )

    @needs_nx
    def test_dfs_labeled_edges_matches_networkx(self):
        G_fnx = fnx.Graph()
        G_nx = nx.Graph()
        for G in (G_fnx, G_nx):
            G.add_edge(0, 1)
            G.add_edge(0, 2)
            G.add_edge(1, 3)
            G.add_edge(2, 3)
        assert list(fnx.dfs_labeled_edges(G_fnx, 0)) == list(
            nx.dfs_labeled_edges(G_nx, 0)
        )

    @needs_nx
    def test_dfs_labeled_edges_digraph_matches_networkx(self):
        D_fnx = fnx.DiGraph()
        D_nx = nx.DiGraph()
        for D in (D_fnx, D_nx):
            D.add_edge("a", "b")
            D.add_edge("a", "c")
            D.add_edge("b", "d")
            D.add_edge("c", "d")
        assert list(fnx.dfs_labeled_edges(D_fnx, "a")) == list(
            nx.dfs_labeled_edges(D_nx, "a")
        )

    def test_global_parameters_petersen(self):
        """global_parameters now takes (b, c) matching upstream.
        Drive it with the Petersen intersection array and compare
        against upstream on the same arrays.
        """
        G = fnx.petersen_graph()
        b, c = fnx.intersection_array(G)
        assert list(fnx.global_parameters(b, c)) == list(nx.global_parameters(b, c))

    def test_intersection_array_matches_networkx(self):
        for fnx_graph, nx_graph in [
            (fnx.cycle_graph(4), nx.cycle_graph(4)),
            (fnx.petersen_graph(), nx.petersen_graph()),
        ]:
            assert fnx.intersection_array(fnx_graph) == nx.intersection_array(nx_graph)

        fnx_graph = fnx.path_graph(4)
        nx_graph = nx.path_graph(4)
        with pytest.raises(fnx.NetworkXError, match=r"^Graph is not distance regular\.$") as fnx_exc:
            fnx.intersection_array(fnx_graph)
        with pytest.raises(nx.NetworkXError, match=r"^Graph is not distance regular\.$") as nx_exc:
            nx.intersection_array(nx_graph)
        assert str(fnx_exc.value) == str(nx_exc.value)


# ---------------------------------------------------------------------------
# Assortativity
# ---------------------------------------------------------------------------

@needs_nx
class TestAssortativityParity:
    def test_degree_mixing_dict(self):
        G_fnx, G_nx = _make_identical_graphs()
        d_fnx = fnx.degree_mixing_dict(G_fnx)
        d_nx = nx.degree_mixing_dict(G_nx)
        for d1 in d_nx:
            for d2 in d_nx[d1]:
                assert d_fnx.get(d1, {}).get(d2, 0) == d_nx[d1][d2], f"mismatch at ({d1},{d2})"

    def test_degree_mixing_dict_nodes_filter(self):
        G_fnx, G_nx = _make_identical_graphs()
        assert fnx.degree_mixing_dict(G_fnx, nodes=[0, 1, -1]) == nx.degree_mixing_dict(
            G_nx,
            nodes=[0, 1, -1],
        )

    def test_degree_mixing_dict_weighted(self):
        G_fnx = fnx.Graph()
        G_fnx.add_edge(0, 1, weight=7)
        G_fnx.add_edge(1, 2, weight=10)

        G_nx = nx.Graph()
        G_nx.add_edge(0, 1, weight=7)
        G_nx.add_edge(1, 2, weight=10)

        assert fnx.degree_mixing_dict(G_fnx, weight="weight") == nx.degree_mixing_dict(
            G_nx,
            weight="weight",
        )

    def test_attribute_assortativity_matches_nx(self):
        G_fnx = fnx.Graph()
        G_fnx.add_node(0, color='red')
        G_fnx.add_node(1, color='red')
        G_fnx.add_node(2, color='blue')
        G_fnx.add_node(3, color='blue')
        G_fnx.add_edges_from([(0, 1), (2, 3)])

        G_nx = nx.Graph()
        G_nx.add_node(0, color='red')
        G_nx.add_node(1, color='red')
        G_nx.add_node(2, color='blue')
        G_nx.add_node(3, color='blue')
        G_nx.add_edges_from([(0, 1), (2, 3)])

        assert abs(fnx.attribute_assortativity_coefficient(G_fnx, 'color') -
                    nx.attribute_assortativity_coefficient(G_nx, 'color')) < 1e-10

    def test_numeric_assortativity_missing_attr_raises(self):
        G = fnx.Graph()
        G.add_edge(0, 1)
        with pytest.raises(KeyError):
            fnx.numeric_assortativity_coefficient(G, 'missing')
