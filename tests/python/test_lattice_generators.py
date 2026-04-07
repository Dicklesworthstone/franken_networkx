"""Tests for lattice and structured graph generator wrappers."""

import networkx as nx

import franken_networkx as fnx
from franken_networkx.drawing.layout import _to_nx


def test_hexagonal_and_triangular_lattice_match_networkx():
    hex_graph = fnx.hexagonal_lattice_graph(2, 3)
    hex_nx = nx.hexagonal_lattice_graph(2, 3)

    tri_graph = fnx.triangular_lattice_graph(2, 3)
    tri_nx = nx.triangular_lattice_graph(2, 3)

    assert sorted(_to_nx(hex_graph).edges()) == sorted(hex_nx.edges())
    assert sorted(_to_nx(tri_graph).edges()) == sorted(tri_nx.edges())
    assert "pos" in hex_graph.nodes[next(iter(hex_graph.nodes()))]
    assert "pos" in tri_graph.nodes[next(iter(tri_graph.nodes()))]


def test_grid_graph_matches_networkx():
    graph = fnx.grid_graph([2, 3], periodic=False)
    graph_nx = nx.grid_graph([2, 3], periodic=False)

    assert sorted(_to_nx(graph).edges()) == sorted(graph_nx.edges())
    assert graph.number_of_nodes() == 6


def test_lattice_reference_preserves_degree_sequence_and_matches_networkx():
    base = fnx.cycle_graph(8)
    rewired = fnx.lattice_reference(base, niter=2, seed=5)
    rewired_nx = nx.lattice_reference(nx.cycle_graph(8), niter=2, seed=5)

    assert sorted(rewired.degree[node] for node in rewired.nodes()) == sorted(
        base.degree[node] for node in base.nodes()
    )
    assert sorted(_to_nx(rewired).edges()) == sorted(rewired_nx.edges())


def test_lattice_reference_does_not_delegate_to_networkx(monkeypatch):
    expected = nx.lattice_reference(nx.cycle_graph(8), niter=2, seed=5)

    def fail(*args, **kwargs):
        raise AssertionError("networkx fallback was used")

    monkeypatch.setattr(nx, "lattice_reference", fail)

    actual = fnx.lattice_reference(fnx.cycle_graph(8), niter=2, seed=5)
    assert sorted(_to_nx(actual).edges()) == sorted(expected.edges())


def test_margulis_and_sudoku_graph_match_networkx():
    margulis = fnx.margulis_gabber_galil_graph(3)
    margulis_nx = nx.margulis_gabber_galil_graph(3)

    sudoku = fnx.sudoku_graph()
    sudoku_nx = nx.sudoku_graph()

    assert sorted(_to_nx(margulis).edges()) == sorted(margulis_nx.edges())
    assert sorted(_to_nx(sudoku).edges()) == sorted(sudoku_nx.edges())
    assert set(sudoku.degree[node] for node in sudoku.nodes()) == {20}
