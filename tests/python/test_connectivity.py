"""Conformance tests: connectivity algorithms — fnx vs nx oracle."""

import pytest
from conftest import assert_sets_equal


@pytest.mark.conformance
class TestConnectivity:
    def test_is_connected_true(self, fnx, nx, path_graph):
        G_fnx, G_nx = path_graph
        assert fnx.is_connected(G_fnx) == nx.is_connected(G_nx)

    def test_is_connected_false(self, fnx, nx, disconnected_graph):
        G_fnx, G_nx = disconnected_graph
        assert fnx.is_connected(G_fnx) == nx.is_connected(G_nx)

    def test_number_connected_components(self, fnx, nx, disconnected_graph):
        G_fnx, G_nx = disconnected_graph
        assert fnx.number_connected_components(G_fnx) == nx.number_connected_components(G_nx)

    def test_connected_components_count(self, fnx, nx, disconnected_graph):
        G_fnx, G_nx = disconnected_graph
        fnx_comps = fnx.connected_components(G_fnx)
        nx_comps = list(nx.connected_components(G_nx))
        assert len(fnx_comps) == len(nx_comps)

    def test_connected_components_content(self, fnx, nx, path_graph):
        G_fnx, G_nx = path_graph
        fnx_comps = fnx.connected_components(G_fnx)
        nx_comps = list(nx.connected_components(G_nx))
        # Both should have one component with all nodes
        assert len(fnx_comps) == 1
        assert_sets_equal(fnx_comps[0], nx_comps[0])

    def test_node_connectivity(self, fnx, nx, complete_graph):
        G_fnx, G_nx = complete_graph
        assert fnx.node_connectivity(G_fnx) == nx.node_connectivity(G_nx)

    def test_node_connectivity_directed(self, fnx, nx):
        D_fnx = fnx.DiGraph()
        D_fnx.add_edge(0, 1)

        D_nx = nx.DiGraph()
        D_nx.add_edge(0, 1)

        assert fnx.node_connectivity(D_fnx) == nx.node_connectivity(D_nx)

    def test_node_connectivity_directed_cycle_tiebreak(self, fnx, nx):
        D_fnx = fnx.DiGraph()
        D_fnx.add_edge(0, 1)
        D_fnx.add_edge(1, 0)

        D_nx = nx.DiGraph()
        D_nx.add_edge(0, 1)
        D_nx.add_edge(1, 0)

        assert fnx.node_connectivity(D_fnx) == nx.node_connectivity(D_nx)

    def test_minimum_node_cut_directed(self, fnx, nx):
        D_fnx = fnx.DiGraph()
        D_fnx.add_edge(0, 1)

        D_nx = nx.DiGraph()
        D_nx.add_edge(0, 1)

        assert_sets_equal(fnx.minimum_node_cut(D_fnx), nx.minimum_node_cut(D_nx))

    def test_minimum_node_cut_directed_cycle_tiebreak(self, fnx, nx):
        D_fnx = fnx.DiGraph()
        D_fnx.add_edge(0, 1)
        D_fnx.add_edge(1, 0)

        D_nx = nx.DiGraph()
        D_nx.add_edge(0, 1)
        D_nx.add_edge(1, 0)

        assert_sets_equal(fnx.minimum_node_cut(D_fnx), nx.minimum_node_cut(D_nx))

    def test_minimum_node_cut_directed_two_node_cycle(self, fnx, nx):
        D_fnx = fnx.DiGraph()
        D_fnx.add_edge("a", "b")
        D_fnx.add_edge("b", "a")

        D_nx = nx.DiGraph()
        D_nx.add_edge("a", "b")
        D_nx.add_edge("b", "a")

        assert_sets_equal(fnx.minimum_node_cut(D_fnx), nx.minimum_node_cut(D_nx))

    def test_minimum_node_cut_directed_three_cycle(self, fnx, nx):
        D_fnx = fnx.DiGraph()
        D_fnx.add_edge("a", "b")
        D_fnx.add_edge("b", "c")
        D_fnx.add_edge("c", "a")

        D_nx = nx.DiGraph()
        D_nx.add_edge("a", "b")
        D_nx.add_edge("b", "c")
        D_nx.add_edge("c", "a")

        assert_sets_equal(fnx.minimum_node_cut(D_fnx), nx.minimum_node_cut(D_nx))

    def test_minimum_node_cut_disconnected_raises(self, fnx, nx):
        G_fnx = fnx.Graph()
        G_fnx.add_node(0)
        G_fnx.add_node(1)

        G_nx = nx.Graph()
        G_nx.add_node(0)
        G_nx.add_node(1)

        with pytest.raises(nx.NetworkXError):
            nx.minimum_node_cut(G_nx)
        with pytest.raises(fnx.NetworkXError):
            fnx.minimum_node_cut(G_fnx)

    def test_minimum_node_cut_directed_disconnected_raises(self, fnx, nx):
        D_fnx = fnx.DiGraph()
        D_fnx.add_edge(0, 1)
        D_fnx.add_node(2)

        D_nx = nx.DiGraph()
        D_nx.add_edge(0, 1)
        D_nx.add_node(2)

        with pytest.raises(nx.NetworkXError):
            nx.minimum_node_cut(D_nx)
        with pytest.raises(fnx.NetworkXError):
            fnx.minimum_node_cut(D_fnx)

    def test_all_node_cuts_cycle_graph_matches_nx(self, fnx, nx):
        G_fnx = fnx.cycle_graph(5)
        G_nx = nx.cycle_graph(5)

        actual = {frozenset(cut) for cut in fnx.all_node_cuts(G_fnx)}
        expected = {frozenset(cut) for cut in nx.all_node_cuts(G_nx)}

        assert actual == expected

    def test_all_node_cuts_respects_explicit_k(self, fnx, nx):
        G_fnx = fnx.cycle_graph(5)
        G_nx = nx.cycle_graph(5)

        actual = list(fnx.all_node_cuts(G_fnx, k=3))
        expected = list(nx.all_node_cuts(G_nx, k=3))

        assert actual == expected == []

    def test_all_node_cuts_negative_k_matches_nx(self, fnx, nx):
        G_fnx = fnx.cycle_graph(5)
        G_nx = nx.cycle_graph(5)

        actual = {frozenset(cut) for cut in fnx.all_node_cuts(G_fnx, k=-1)}
        expected = {frozenset(cut) for cut in nx.all_node_cuts(G_nx, k=-1)}

        assert actual == expected

    def test_all_node_cuts_directed_raises(self, fnx, nx):
        D_fnx = fnx.DiGraph()
        D_fnx.add_edges_from([(0, 1), (1, 2), (2, 0)])

        with pytest.raises(nx.NetworkXNotImplemented):
            list(nx.all_node_cuts(nx.DiGraph([(0, 1), (1, 2), (2, 0)])))
        with pytest.raises(fnx.NetworkXNotImplemented):
            list(fnx.all_node_cuts(D_fnx))

    def test_all_node_cuts_disconnected_raises(self, fnx, nx):
        G_fnx = fnx.Graph()
        G_fnx.add_nodes_from([0, 1])

        G_nx = nx.Graph()
        G_nx.add_nodes_from([0, 1])

        with pytest.raises(nx.NetworkXError):
            next(nx.all_node_cuts(G_nx))
        with pytest.raises(fnx.NetworkXError):
            next(fnx.all_node_cuts(G_fnx))

    def test_all_node_cuts_with_flow_func_matches_nx(self, fnx, nx):
        G_fnx = fnx.cycle_graph(5)
        G_nx = nx.cycle_graph(5)

        actual = {frozenset(cut) for cut in fnx.all_node_cuts(
            G_fnx,
            flow_func=nx.algorithms.flow.shortest_augmenting_path,
        )}
        expected = {frozenset(cut) for cut in nx.all_node_cuts(
            G_nx,
            flow_func=nx.algorithms.flow.shortest_augmenting_path,
        )}

        assert actual == expected

    def test_edge_connectivity_directed(self, fnx, nx):
        D_fnx = fnx.DiGraph()
        D_fnx.add_edge(0, 1)
        D_fnx.add_edge(1, 0)

        D_nx = nx.DiGraph()
        D_nx.add_edge(0, 1)
        D_nx.add_edge(1, 0)

        assert fnx.edge_connectivity(D_fnx) == nx.edge_connectivity(D_nx)

    def test_articulation_points(self, fnx, nx, path_graph):
        G_fnx, G_nx = path_graph
        fnx_ap = set(str(x) for x in fnx.articulation_points(G_fnx))
        nx_ap = set(str(x) for x in nx.articulation_points(G_nx))
        assert fnx_ap == nx_ap

    def test_bridges(self, fnx, nx, path_graph):
        G_fnx, G_nx = path_graph
        fnx_br = set(tuple(sorted((str(u), str(v)))) for u, v in fnx.bridges(G_fnx))
        nx_br = set(tuple(sorted((str(u), str(v)))) for u, v in nx.bridges(G_nx))
        assert fnx_br == nx_br
