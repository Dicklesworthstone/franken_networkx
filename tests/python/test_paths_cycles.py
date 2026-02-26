"""Conformance tests: paths and cycles algorithms — fnx vs nx oracle."""

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
