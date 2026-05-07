"""Tests for graph metric and expansion bindings.

Cross-validates franken_networkx against NetworkX reference for:
- volume, boundary_expansion, conductance, edge_expansion,
  node_expansion, mixing_expansion
- non_edges, average_node_connectivity, is_k_edge_connected,
  global_node_connectivity
- all_pairs_dijkstra, number_of_spanning_arborescences
"""

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
def path5():
    return fnx.path_graph(5)


@pytest.fixture
def k4():
    return fnx.complete_graph(4)


@pytest.fixture
def star5():
    return fnx.star_graph(4)  # star with 5 nodes (center + 4 leaves)


@pytest.fixture
def weighted_path():
    G = fnx.path_graph(4)
    G.add_edge(0, 1, weight=2.0)
    G.add_edge(1, 2, weight=3.0)
    G.add_edge(2, 3, weight=1.0)
    return G


@pytest.fixture
def simple_digraph():
    D = fnx.DiGraph()
    D.add_edge(0, 1)
    D.add_edge(0, 2)
    D.add_edge(1, 2)
    return D


# ---------------------------------------------------------------------------
# volume
# ---------------------------------------------------------------------------


class TestVolume:
    def test_volume_path(self, path5):
        # nodes 0,1 in path 0-1-2-3-4: deg(0)=1, deg(1)=2 => vol=3
        assert fnx.volume(path5, [0, 1]) == 3

    def test_volume_single_node(self, path5):
        assert fnx.volume(path5, [2]) == 2  # degree of middle node

    def test_volume_all_nodes(self, k4):
        # K4: each node has degree 3, total volume = 12
        assert fnx.volume(k4, [0, 1, 2, 3]) == 12

    def test_volume_empty_set(self, path5):
        assert fnx.volume(path5, []) == 0

    @needs_nx
    def test_volume_matches_nx(self, path5):
        G_nx = nx.path_graph(5)
        nodes = [1, 2, 3]
        expected = nx.volume(G_nx, nodes)
        actual = fnx.volume(path5, nodes)
        assert actual == expected


# ---------------------------------------------------------------------------
# boundary_expansion
# ---------------------------------------------------------------------------


class TestBoundaryExpansion:
    def test_boundary_expansion_path(self, path5):
        # S={0,1}: boundary edges crossing to {2,3,4} = edge (1,2) = 1
        # boundary_expansion = 1/2 = 0.5
        assert fnx.boundary_expansion(path5, [0, 1]) == pytest.approx(0.5)

    def test_boundary_expansion_complete(self, k4):
        # S={0}: boundary edges = 3, |S|=1 => 3.0
        assert fnx.boundary_expansion(k4, [0]) == pytest.approx(3.0)

    def test_boundary_expansion_empty_raises_like_networkx(self, path5):
        """Upstream nx.boundary_expansion divides by len(S) without a
        guard, so an empty S raises ZeroDivisionError. Match that
        contract instead of silently returning 0.0.
        """
        with pytest.raises(ZeroDivisionError):
            fnx.boundary_expansion(path5, [])


# ---------------------------------------------------------------------------
# conductance
# ---------------------------------------------------------------------------


class TestConductance:
    def test_conductance_path(self, path5):
        result = fnx.conductance(path5, [0, 1])
        assert result > 0

    def test_conductance_balanced_split_complete(self, k4):
        # S={0,1}, complement={2,3}
        # boundary edges: 0-2, 0-3, 1-2, 1-3 = 4
        # vol(S) = 6, vol(complement) = 6, min_vol = 6
        # conductance = 4/6
        assert fnx.conductance(k4, [0, 1]) == pytest.approx(4.0 / 6.0)

    @needs_nx
    def test_conductance_matches_nx(self, k4):
        G_nx = nx.complete_graph(4)
        expected = nx.conductance(G_nx, [0, 1])
        actual = fnx.conductance(k4, [0, 1])
        assert actual == pytest.approx(expected)


# ---------------------------------------------------------------------------
# edge_expansion
# ---------------------------------------------------------------------------


class TestEdgeExpansion:
    def test_edge_expansion_path(self, path5):
        # S={0,1}, complement={2,3,4}
        # boundary edges = 1, min(|S|, |complement|) = 2
        # edge_expansion = 1/2 = 0.5
        assert fnx.edge_expansion(path5, [0, 1]) == pytest.approx(0.5)

    def test_edge_expansion_complete(self, k4):
        # S={0}, complement={1,2,3}
        # boundary edges = 3, min(1,3) = 1
        # edge_expansion = 3/1 = 3.0
        assert fnx.edge_expansion(k4, [0]) == pytest.approx(3.0)


# ---------------------------------------------------------------------------
# node_expansion
# ---------------------------------------------------------------------------


class TestNodeExpansion:
    def test_node_expansion_path(self, path5):
        # Upstream nx.node_expansion yields 1.5 on path5 with S=[0,1];
        # fnx matches. (Upstream's formula averages outside-neighbor
        # counts over S, not the single-boundary count the old docstring
        # assumed.)
        assert fnx.node_expansion(path5, [0, 1]) == pytest.approx(1.5)

    def test_node_expansion_complete(self, k4):
        # S={0}: node boundary = {1,2,3} => 3/1 = 3.0
        assert fnx.node_expansion(k4, [0]) == pytest.approx(3.0)

    def test_node_expansion_empty_raises_like_networkx(self, path5):
        """Upstream divides by len(S) without a guard on empty S."""
        with pytest.raises(ZeroDivisionError):
            fnx.node_expansion(path5, [])


# ---------------------------------------------------------------------------
# mixing_expansion
# ---------------------------------------------------------------------------


class TestMixingExpansion:
    def test_mixing_expansion_path(self, path5):
        """Upstream formula is edges(S, T) / (2 * |E|) — on a 4-edge
        path_graph(5) with S=[0,1] that's 1 / 8 = 0.125 on both sides.
        """
        assert fnx.mixing_expansion(path5, [0, 1]) == pytest.approx(
            nx.mixing_expansion(nx.path_graph(5), [0, 1])
        ) if HAS_NX else True

    def test_mixing_expansion_complete_balanced(self, k4):
        """S={0,1}, complement={2,3} in K4: edges(S,T)=4, 2|E|=12,
        mixing_expansion = 4/12 = 1/3 on both sides.
        """
        assert fnx.mixing_expansion(k4, [0, 1]) == pytest.approx(
            nx.mixing_expansion(nx.complete_graph(4), [0, 1])
        ) if HAS_NX else True


# ---------------------------------------------------------------------------
# non_edges
# ---------------------------------------------------------------------------


class TestNonEdges:
    def test_non_edges_complete(self, k4):
        # non_edges returns a generator — materialise first.
        assert list(fnx.non_edges(k4)) == []

    def test_non_edges_path(self, path5):
        result = list(fnx.non_edges(path5))
        # path 0-1-2-3-4 has edges: 01,12,23,34
        # non-edges: 02,03,04,13,14,24 = 6
        assert len(result) == 6

    def test_non_edges_sparse(self):
        G = fnx.Graph()
        G.add_node(0)
        G.add_node(1)
        G.add_node(2)
        result = list(fnx.non_edges(G))
        # No edges at all => 3 non-edges: (0,1), (0,2), (1,2)
        assert len(result) == 3

    @needs_nx
    def test_non_edges_directed_matches_nx(self):
        D = fnx.DiGraph()
        D.add_edge(0, 1)
        D.add_node(2)

        D_nx = nx.DiGraph()
        D_nx.add_edge(0, 1)
        D_nx.add_node(2)

        assert list(fnx.non_edges(D)) == list(nx.non_edges(D_nx))


# ---------------------------------------------------------------------------
# average_node_connectivity
# ---------------------------------------------------------------------------


class TestAverageNodeConnectivity:
    def test_complete_graph(self, k4):
        # K4: node connectivity between any pair = 3
        assert fnx.average_node_connectivity(k4) == pytest.approx(3.0)

    def test_path_graph(self, path5):
        # Path graph: connectivity between any pair = 1
        assert fnx.average_node_connectivity(path5) == pytest.approx(1.0)

    def test_single_node(self):
        G = fnx.Graph()
        G.add_node(0)
        assert fnx.average_node_connectivity(G) == pytest.approx(0.0)

    def test_empty_graph(self):
        G = fnx.Graph()
        assert fnx.average_node_connectivity(G) == pytest.approx(0.0)

    @needs_nx
    def test_directed_matches_nx(self):
        D = fnx.DiGraph()
        D.add_edge(0, 1)
        D.add_node(2)

        D_nx = nx.DiGraph()
        D_nx.add_edge(0, 1)
        D_nx.add_node(2)

        assert fnx.average_node_connectivity(D) == pytest.approx(
            nx.average_node_connectivity(D_nx)
        )


# ---------------------------------------------------------------------------
# is_k_edge_connected
# ---------------------------------------------------------------------------


class TestIsKEdgeConnected:
    def test_k0_raises_value_error(self, path5):
        """br-ikeck0: nx.is_k_edge_connected validates k>=1; fnx
        matches that contract. (Earlier fnx vacuously returned True
        for k=0, which the original test_k0_always_true asserted.)"""
        with pytest.raises(ValueError, match="k must be positive"):
            fnx.is_k_edge_connected(path5, 0)

    def test_k1_connected(self, path5):
        assert fnx.is_k_edge_connected(path5, 1)

    def test_k2_path_false(self, path5):
        # Path graph has edge connectivity 1, not 2.
        assert not fnx.is_k_edge_connected(path5, 2)

    @needs_nx
    def test_positive_float_k_matches_nx(self):
        """br-r37-c1-nyh42: nx accepts comparison-compatible
        positive float ``k`` values; fnx previously sent them into
        the PyO3 integer binding and raised TypeError."""
        G = fnx.path_graph(5)
        H = nx.path_graph(5)
        for k in (1.0, 2.0, 2.5):
            assert fnx.is_k_edge_connected(G, k) == nx.is_k_edge_connected(H, k)

    def test_k3_complete(self, k4):
        # K4 has edge connectivity 3.
        assert fnx.is_k_edge_connected(k4, 3)

    def test_k4_complete_false(self, k4):
        assert not fnx.is_k_edge_connected(k4, 4)

    def test_disconnected_false(self):
        G = fnx.Graph()
        G.add_node(0)
        G.add_node(1)
        assert not fnx.is_k_edge_connected(G, 1)

    def test_directed_raises(self):
        D = fnx.DiGraph()
        D.add_edge(0, 1)
        with pytest.raises(fnx.NetworkXNotImplemented):
            fnx.is_k_edge_connected(D, 1)

    def test_multigraph_raises_like_nx(self):
        """br-r37-c1-nyh42: nx rejects multigraph inputs; the raw
        fnx binding collapsed the parallel-edge surface and returned
        a boolean."""
        G = fnx.MultiGraph()
        G.add_edge(0, 1)
        with pytest.raises(fnx.NetworkXNotImplemented):
            fnx.is_k_edge_connected(G, 1)


# ---------------------------------------------------------------------------
# global_node_connectivity
# ---------------------------------------------------------------------------


class TestGlobalNodeConnectivity:
    def test_complete(self, k4):
        assert fnx.global_node_connectivity(k4) == 3

    def test_path(self, path5):
        assert fnx.global_node_connectivity(path5) == 1

    def test_single_node(self):
        G = fnx.Graph()
        G.add_node(0)
        assert fnx.global_node_connectivity(G) == 0

    def test_directed_orders_pairs(self):
        D = fnx.DiGraph()
        D.add_edge(0, 1)
        D.add_edge(0, 2)
        assert fnx.global_node_connectivity(D) == 0


class TestHyperWienerIndex:
    def test_path_graph_matches_networkx(self):
        path_fnx = fnx.path_graph(4)
        path_nx = nx.path_graph(4)
        assert fnx.hyper_wiener_index(path_fnx) == nx.hyper_wiener_index(path_nx)

    def test_cycle_graph_matches_networkx(self):
        cycle_fnx = fnx.cycle_graph(4)
        cycle_nx = nx.cycle_graph(4)
        assert fnx.hyper_wiener_index(cycle_fnx) == nx.hyper_wiener_index(cycle_nx)


# ---------------------------------------------------------------------------
# all_pairs_dijkstra
# ---------------------------------------------------------------------------


class TestAllPairsDijkstra:
    def test_basic(self, weighted_path):
        # all_pairs_dijkstra yields (source, (dists, paths)); materialise
        # to a dict for direct indexing / length checks.
        result = dict(fnx.all_pairs_dijkstra(weighted_path, weight="weight"))
        # Should have entries for all 4 nodes
        assert len(result) == 4
        # Check that distances and paths exist for each source
        for source in range(4):
            dists, paths = result[source]
            assert source in dists
            assert dists[source] == pytest.approx(0.0)
            assert source in paths
            assert paths[source] == [source]

    def test_distances_correct(self, weighted_path):
        result = dict(fnx.all_pairs_dijkstra(weighted_path, weight="weight"))
        dists_from_0, _ = result[0]
        assert dists_from_0[0] == pytest.approx(0.0)
        assert dists_from_0[1] == pytest.approx(2.0)
        assert dists_from_0[2] == pytest.approx(5.0)  # 2+3
        assert dists_from_0[3] == pytest.approx(6.0)  # 2+3+1

    @needs_nx
    def test_matches_nx(self, weighted_path):
        G_nx = nx.path_graph(4)
        G_nx[0][1]["weight"] = 2.0
        G_nx[1][2]["weight"] = 3.0
        G_nx[2][3]["weight"] = 1.0
        nx_result = dict(nx.all_pairs_dijkstra(G_nx, weight="weight"))
        fnx_result = dict(fnx.all_pairs_dijkstra(weighted_path, weight="weight"))
        for node in range(4):
            nx_dists, nx_paths = nx_result[node]
            fnx_dists, fnx_paths = fnx_result[node]
            for target in range(4):
                assert fnx_dists[target] == pytest.approx(nx_dists[target])

    @needs_nx
    def test_directed_matches_nx(self):
        D = fnx.DiGraph()
        D.add_edge(0, 1, weight=1.0)
        D.add_edge(0, 2, weight=1.0)
        D.add_edge(1, 2, weight=1.0)

        D_nx = nx.DiGraph()
        D_nx.add_edge(0, 1, weight=1.0)
        D_nx.add_edge(0, 2, weight=1.0)
        D_nx.add_edge(1, 2, weight=1.0)

        assert dict(fnx.all_pairs_dijkstra(D, weight="weight")) == dict(
            nx.all_pairs_dijkstra(D_nx, weight="weight")
        )


# ---------------------------------------------------------------------------
# number_of_spanning_arborescences
# ---------------------------------------------------------------------------


class TestNumberOfSpanningArborescences:
    def test_simple_digraph(self, simple_digraph):
        # D: 0->1, 0->2, 1->2
        # From root 0: arborescences are {0->1, 0->2} and {0->1, 1->2}
        result = fnx.number_of_spanning_arborescences(simple_digraph, 0)
        assert result == pytest.approx(2.0)

    def test_single_node(self):
        D = fnx.DiGraph()
        D.add_node(0)
        assert fnx.number_of_spanning_arborescences(D, 0) == pytest.approx(1.0)

    def test_undirected_raises(self, k4):
        with pytest.raises(Exception):
            fnx.number_of_spanning_arborescences(k4, 0)

    def test_disconnected_zero(self):
        D = fnx.DiGraph()
        D.add_node(0)
        D.add_node(1)
        assert fnx.number_of_spanning_arborescences(D, 0) == pytest.approx(0.0)

    def test_chain_digraph(self):
        # Linear chain 0->1->2->3: only one spanning arborescence from root 0
        D = fnx.DiGraph()
        D.add_edge(0, 1)
        D.add_edge(1, 2)
        D.add_edge(2, 3)
        assert fnx.number_of_spanning_arborescences(D, 0) == pytest.approx(1.0)
