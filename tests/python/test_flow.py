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
    def test_edmonds_karp_residual_matches_networkx(self, fnx, nx):
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

        fnx_residual = fnx.edmonds_karp(DG_fnx, "s", "t")
        nx_residual = nx.algorithms.flow.edmonds_karp(DG_nx, "s", "t")

        assert fnx_residual.graph["algorithm"] == nx_residual.graph["algorithm"]
        assert abs(fnx_residual.graph["flow_value"] - nx_residual.graph["flow_value"]) < 1e-9
        assert abs(fnx_residual.graph["inf"] - nx_residual.graph["inf"]) < 1e-9

        fnx_edges = sorted(
            (u, v, attrs["capacity"], attrs["flow"])
            for u, v, attrs in fnx_residual.edges(data=True)
        )
        nx_edges = sorted(
            (u, v, attrs["capacity"], attrs["flow"])
            for u, v, attrs in nx_residual.edges(data=True)
        )
        assert fnx_edges == nx_edges

    def test_edmonds_karp_infinite_capacity_path_matches_networkx(self, fnx, nx):
        DG_fnx = fnx.DiGraph()
        DG_nx = nx.DiGraph()
        DG_fnx.add_edge("s", "a")
        DG_fnx.add_edge("a", "t")
        DG_nx.add_edge("s", "a")
        DG_nx.add_edge("a", "t")

        message = "Infinite capacity path, flow unbounded above."
        with pytest.raises(fnx.NetworkXUnbounded, match=message):
            fnx.edmonds_karp(DG_fnx, "s", "t")
        with pytest.raises(nx.NetworkXUnbounded, match=message):
            nx.algorithms.flow.edmonds_karp(DG_nx, "s", "t")

    def test_edmonds_karp_cutoff_matches_networkx(self, fnx, nx):
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

        fnx_residual = fnx.edmonds_karp(DG_fnx, "s", "t", cutoff=3.0)
        nx_residual = nx.algorithms.flow.edmonds_karp(DG_nx, "s", "t", cutoff=3.0)

        assert abs(fnx_residual.graph["flow_value"] - nx_residual.graph["flow_value"]) < 1e-9
        fnx_edges = sorted(
            (u, v, attrs["capacity"], attrs["flow"])
            for u, v, attrs in fnx_residual.edges(data=True)
        )
        nx_edges = sorted(
            (u, v, attrs["capacity"], attrs["flow"])
            for u, v, attrs in nx_residual.edges(data=True)
        )
        assert fnx_edges == nx_edges

    def test_maximum_flow(self, fnx, nx, weighted_graph):
        G_fnx, G_nx = weighted_graph
        fnx_val, fnx_flow = fnx.maximum_flow(G_fnx, "a", "d", capacity="weight")
        nx_val, nx_flow = nx.maximum_flow(G_nx, "a", "d", capacity="weight")
        assert abs(fnx_val - nx_val) < 1e-9
        assert fnx_flow == nx_flow

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

        fnx_flow_value, fnx_flow = fnx.maximum_flow(DG_fnx, "s", "t")
        nx_flow_value, nx_flow = nx.maximum_flow(DG_nx, "s", "t")
        assert abs(fnx_flow_value - nx_flow_value) < 1e-9
        assert fnx_flow == nx_flow

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

        fnx_flow_value, fnx_flow = fnx.maximum_flow(DG_fnx, "s", "t")
        nx_flow_value, nx_flow = nx.maximum_flow(DG_nx, "s", "t")
        assert abs(fnx_flow_value - nx_flow_value) < 1e-9
        assert fnx_flow == nx_flow

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

    def test_flow_bindings_reject_same_source_and_sink(self, fnx, nx):
        DG_fnx, DG_nx = _directed_flow_pair(
            fnx,
            nx,
            [
                ("s", "a", 3.0),
                ("a", "t", 2.0),
            ],
        )

        for name in (
            "maximum_flow",
            "maximum_flow_value",
            "minimum_cut",
            "minimum_cut_value",
        ):
            fnx_flow_fn = getattr(fnx, name)
            nx_flow_fn = getattr(nx, name)

            with pytest.raises(fnx.NetworkXError, match="source and sink are the same node"):
                fnx_flow_fn(DG_fnx, "s", "s")

            with pytest.raises(nx.NetworkXError, match="source and sink are the same node"):
                nx_flow_fn(DG_nx, "s", "s")

    def test_flow_bindings_reject_missing_endpoints(self, fnx, nx):
        DG_fnx, DG_nx = _directed_flow_pair(
            fnx,
            nx,
            [
                ("a", "b", 1.0),
            ],
        )

        cases = (
            ("s", "b", "node s not in graph"),
            ("a", "t", "node t not in graph"),
            ("s", "t", "node s not in graph"),
        )

        for source, sink, message in cases:
            for name in (
                "maximum_flow",
                "maximum_flow_value",
                "minimum_cut",
                "minimum_cut_value",
            ):
                fnx_flow_fn = getattr(fnx, name)
                nx_flow_fn = getattr(nx, name)

                with pytest.raises(fnx.NetworkXError, match=message):
                    fnx_flow_fn(DG_fnx, source, sink)

                with pytest.raises(nx.NetworkXError, match=message):
                    nx_flow_fn(DG_nx, source, sink)
