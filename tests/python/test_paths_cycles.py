"""Conformance tests: paths and cycles algorithms — fnx vs nx oracle."""

import inspect

import pytest


@pytest.mark.conformance
class TestPathsCycles:
    def test_all_simple_paths(self, fnx, nx, path_graph):
        G_fnx, G_nx = path_graph
        fnx_paths = fnx.all_simple_paths(G_fnx, "a", "e")
        nx_paths = list(nx.all_simple_paths(G_nx, "a", "e"))
        # Sort paths for comparison
        fnx_sorted = sorted([list(map(str, p)) for p in fnx_paths])
        nx_sorted = sorted([list(map(str, p)) for p in nx_paths])
        assert fnx_sorted == nx_sorted

    def test_all_simple_paths_with_cutoff(self, fnx, nx, complete_graph):
        G_fnx, G_nx = complete_graph
        fnx_paths = fnx.all_simple_paths(G_fnx, "a", "e", cutoff=2)
        nx_paths = list(nx.all_simple_paths(G_nx, "a", "e", cutoff=2))
        fnx_sorted = sorted([list(map(str, p)) for p in fnx_paths])
        nx_sorted = sorted([list(map(str, p)) for p in nx_paths])
        assert fnx_sorted == nx_sorted

    def test_all_simple_paths_preserves_multigraph_multiplicity(self, fnx, nx):
        G_fnx = fnx.MultiGraph()
        G_nx = nx.MultiGraph()
        for graph in (G_fnx, G_nx):
            graph.add_edge("a", "b", key="k1")
            graph.add_edge("a", "b", key="k2")
            graph.add_edge("b", "c", key="k3")

        assert list(fnx.all_simple_paths(G_fnx, "a", "c")) == list(
            nx.all_simple_paths(G_nx, "a", "c")
        )
        assert list(fnx.all_simple_paths(G_fnx, "a", "c", cutoff=2)) == list(
            nx.all_simple_paths(G_nx, "a", "c", cutoff=2)
        )

    def test_all_simple_paths_signature_matches_networkx(self, fnx, nx):
        assert str(inspect.signature(fnx.all_simple_paths)) == str(
            inspect.signature(nx.all_simple_paths)
        )

    def test_all_simple_paths_backend_keyword_contract(self, fnx, nx, path_graph):
        G_fnx, G_nx = path_graph

        assert list(fnx.all_simple_paths(G_fnx, "a", "e", backend="networkx")) == list(
            nx.all_simple_paths(G_nx, "a", "e")
        )
        with pytest.raises(ImportError):
            list(fnx.all_simple_paths(G_fnx, "a", "e", backend="missing"))
        with pytest.raises(TypeError):
            list(fnx.all_simple_paths(G_fnx, "a", "e", unexpected=True))

    def test_all_simple_paths_iterable_targets_match_networkx(self, fnx, nx):
        G_fnx = fnx.complete_graph(4)
        G_nx = nx.complete_graph(4)

        assert list(fnx.all_simple_paths(G_fnx, 0, [3, 2])) == list(
            nx.all_simple_paths(G_nx, 0, [3, 2])
        )
        assert list(fnx.all_simple_paths(G_fnx, 0, [0, 1, 2])) == list(
            nx.all_simple_paths(G_nx, 0, [0, 1, 2])
        )
        assert list(fnx.all_simple_paths(G_fnx, 0, "x")) == list(
            nx.all_simple_paths(G_nx, 0, "x")
        )
        with pytest.raises(Exception) as expected_error:
            list(nx.all_simple_paths(G_nx, 0, 9))
        with pytest.raises(Exception) as actual_error:
            list(fnx.all_simple_paths(G_fnx, 0, 9))
        assert type(actual_error.value).__name__ == type(expected_error.value).__name__
        assert str(actual_error.value) == str(expected_error.value)

    def test_all_simple_edge_paths_preserve_multigraph_keys(self, fnx, nx):
        for graph_type in ("MultiGraph", "MultiDiGraph"):
            G_fnx = getattr(fnx, graph_type)()
            G_nx = getattr(nx, graph_type)()
            for graph in (G_fnx, G_nx):
                graph.add_edge("a", "b", key="k1")
                graph.add_edge("a", "b", key="k2")
                graph.add_edge("b", "c", key="k3")

            assert list(fnx.all_simple_edge_paths(G_fnx, "a", "c")) == list(
                nx.all_simple_edge_paths(G_nx, "a", "c")
            )
            assert list(fnx.all_simple_edge_paths(G_fnx, "a", "c", cutoff=2)) == list(
                nx.all_simple_edge_paths(G_nx, "a", "c", cutoff=2)
            )

    def test_all_simple_edge_paths_signature_matches_networkx(self, fnx, nx):
        assert str(inspect.signature(fnx.all_simple_edge_paths)) == str(
            inspect.signature(nx.all_simple_edge_paths)
        )

    def test_all_simple_edge_paths_backend_keyword_contract(self, fnx, nx, path_graph):
        G_fnx, G_nx = path_graph

        assert list(
            fnx.all_simple_edge_paths(G_fnx, "a", "e", backend="networkx")
        ) == list(nx.all_simple_edge_paths(G_nx, "a", "e"))
        with pytest.raises(ImportError):
            list(fnx.all_simple_edge_paths(G_fnx, "a", "e", backend="missing"))
        with pytest.raises(TypeError):
            list(fnx.all_simple_edge_paths(G_fnx, "a", "e", unexpected=True))

    def test_all_simple_edge_paths_iterable_targets_match_networkx(self, fnx, nx):
        G_fnx = fnx.complete_graph(4)
        G_nx = nx.complete_graph(4)

        assert list(fnx.all_simple_edge_paths(G_fnx, 0, [3, 2])) == list(
            nx.all_simple_edge_paths(G_nx, 0, [3, 2])
        )
        assert list(fnx.all_simple_edge_paths(G_fnx, 0, ("x", "y"))) == list(
            nx.all_simple_edge_paths(G_nx, 0, ("x", "y"))
        )
        with pytest.raises(Exception) as expected_error:
            list(nx.all_simple_edge_paths(G_nx, 0, 9))
        with pytest.raises(Exception) as actual_error:
            list(fnx.all_simple_edge_paths(G_fnx, 0, 9))
        assert type(actual_error.value).__name__ == type(expected_error.value).__name__
        assert str(actual_error.value) == str(expected_error.value)

    def test_cycle_basis_count(self, fnx, nx, cycle_graph):
        G_fnx, G_nx = cycle_graph
        fnx_cycles = fnx.cycle_basis(G_fnx)
        nx_cycles = nx.cycle_basis(G_nx)
        assert len(fnx_cycles) == len(nx_cycles)

    def test_cycle_basis_tree_empty(self, fnx, nx, path_graph):
        G_fnx, G_nx = path_graph
        fnx_cycles = fnx.cycle_basis(G_fnx)
        nx_cycles = nx.cycle_basis(G_nx)
        assert len(fnx_cycles) == 0
        assert len(nx_cycles) == 0


@pytest.mark.conformance
class TestEfficiency:
    def test_efficiency(self, fnx, nx, path_graph):
        G_fnx, G_nx = path_graph
        assert abs(fnx.efficiency(G_fnx, "a", "c") - nx.efficiency(G_nx, "a", "c")) < 1e-6
        assert abs(fnx.efficiency(G_fnx, "a", "b") - 1.0) < 1e-6

    def test_efficiency_disconnected_nodes(self, fnx, nx, disconnected_graph):
        G_fnx, G_nx = disconnected_graph
        assert fnx.efficiency(G_fnx, "a", "d") == nx.efficiency(G_nx, "a", "d") == 0

    def test_efficiency_same_node_raises(self, fnx, path_graph):
        G_fnx, _ = path_graph
        with pytest.raises(ZeroDivisionError, match="division by zero"):
            fnx.efficiency(G_fnx, "a", "a")

    def test_efficiency_missing_node_raises(self, fnx, path_graph):
        G_fnx, _ = path_graph
        with pytest.raises(fnx.NodeNotFound):
            fnx.efficiency(G_fnx, "missing", "a")

    def test_global_efficiency(self, fnx, nx, path_graph):
        G_fnx, G_nx = path_graph
        assert abs(fnx.global_efficiency(G_fnx) - nx.global_efficiency(G_nx)) < 1e-6

    def test_local_efficiency(self, fnx, nx, complete_graph):
        G_fnx, G_nx = complete_graph
        assert abs(fnx.local_efficiency(G_fnx) - nx.local_efficiency(G_nx)) < 1e-6

    def test_global_efficiency_complete(self, fnx, nx, complete_graph):
        G_fnx, G_nx = complete_graph
        # Complete graph has global efficiency 1.0
        assert abs(fnx.global_efficiency(G_fnx) - 1.0) < 1e-6
