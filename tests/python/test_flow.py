"""Conformance tests: flow algorithms — fnx vs nx oracle."""

import pytest


@pytest.mark.conformance
class TestFlow:
    def test_maximum_flow_value(self, fnx, nx, weighted_graph):
        G_fnx, G_nx = weighted_graph
        fnx_val = fnx.maximum_flow_value(G_fnx, "a", "d", capacity="weight")
        nx_val = nx.maximum_flow_value(G_nx, "a", "d", capacity="weight")
        assert abs(fnx_val - nx_val) < 1e-9

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
