"""Conformance tests: flow algorithms — fnx vs nx oracle."""

import pytest


def _directed_flow_pair(fnx, nx, edges):
    g_fnx = fnx.DiGraph()
    g_nx = nx.DiGraph()
    for u, v, capacity in edges:
        g_fnx.add_edge(u, v, capacity=capacity)
        g_nx.add_edge(u, v, capacity=capacity)
    return g_fnx, g_nx


@pytest.mark.conformance
class TestFlow:
    def test_maximum_flow_value(self, fnx, nx, weighted_graph):
        G_fnx, G_nx = weighted_graph
        fnx_val = fnx.maximum_flow_value(G_fnx, "a", "d", capacity="weight")
        nx_val = nx.maximum_flow_value(G_nx, "a", "d", capacity="weight")
        assert abs(fnx_val - nx_val) < 1e-9

    def test_minimum_cut(self, fnx, nx, weighted_graph):
        G_fnx, G_nx = weighted_graph
        fnx_val, fnx_partition = fnx.minimum_cut(G_fnx, "a", "d", capacity="weight")
        nx_val, nx_partition = nx.minimum_cut(G_nx, "a", "d", capacity="weight")
        assert abs(fnx_val - nx_val) < 1e-9
        assert fnx_partition[0] == nx_partition[0]
        assert fnx_partition[1] == nx_partition[1]

    def test_minimum_cut_value(self, fnx, nx, weighted_graph):
        G_fnx, G_nx = weighted_graph
        fnx_val = fnx.minimum_cut_value(G_fnx, "a", "d", capacity="weight")
        nx_val = nx.minimum_cut_value(G_nx, "a", "d", capacity="weight")
        assert abs(fnx_val - nx_val) < 1e-9

    def test_max_flow_min_cut_theorem(self, fnx, weighted_graph):
        G_fnx, _ = weighted_graph
        mf = fnx.maximum_flow_value(G_fnx, "a", "d", capacity="weight")
        mc = fnx.minimum_cut_value(G_fnx, "a", "d", capacity="weight")
        # Max-flow min-cut theorem
        assert abs(mf - mc) < 1e-9

    def test_flow_bindings_support_directed_graphs(self, fnx, nx):
        DG_fnx, DG_nx = _directed_flow_pair(
            fnx,
            nx,
            [
                ("s", "a", 3.0),
                ("s", "b", 2.0),
                ("a", "b", 1.0),
                ("a", "t", 2.0),
                ("b", "t", 3.0),
            ],
        )

        fnx_val = fnx.maximum_flow_value(DG_fnx, "s", "t")
        nx_val = nx.maximum_flow_value(DG_nx, "s", "t")
        assert abs(fnx_val - nx_val) < 1e-9

        fnx_cut_value, fnx_partition = fnx.minimum_cut(DG_fnx, "s", "t")
        nx_cut_value, nx_partition = nx.minimum_cut(DG_nx, "s", "t")
        assert abs(fnx_cut_value - nx_cut_value) < 1e-9
        assert fnx_partition[0] == nx_partition[0]
        assert fnx_partition[1] == nx_partition[1]

        fnx_cut_val = fnx.minimum_cut_value(DG_fnx, "s", "t")
        nx_cut_val = nx.minimum_cut_value(DG_nx, "s", "t")
        assert abs(fnx_cut_val - nx_cut_val) < 1e-9

    def test_flow_bindings_respect_edge_direction(self, fnx, nx):
        DG_fnx, DG_nx = _directed_flow_pair(
            fnx,
            nx,
            [
                ("a", "s", 5.0),
                ("a", "t", 5.0),
            ],
        )

        fnx_val = fnx.maximum_flow_value(DG_fnx, "s", "t")
        nx_val = nx.maximum_flow_value(DG_nx, "s", "t")
        assert abs(fnx_val - nx_val) < 1e-9

        fnx_cut_value, fnx_partition = fnx.minimum_cut(DG_fnx, "s", "t")
        nx_cut_value, nx_partition = nx.minimum_cut(DG_nx, "s", "t")
        assert abs(fnx_cut_value - nx_cut_value) < 1e-9
        assert fnx_partition[0] == nx_partition[0]
        assert fnx_partition[1] == nx_partition[1]

        fnx_cut_val = fnx.minimum_cut_value(DG_fnx, "s", "t")
        nx_cut_val = nx.minimum_cut_value(DG_nx, "s", "t")
        assert abs(fnx_cut_val - nx_cut_val) < 1e-9
