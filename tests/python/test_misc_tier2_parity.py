import networkx as nx
import pytest

import franken_networkx as fnx


def normalize_cycles(cycles):
    return sorted(sorted(cycle) for cycle in cycles)


def test_chordless_cycles_returns_iterator_and_matches_networkx():
    graph = fnx.cycle_graph(4)
    expected = nx.cycle_graph(4)

    cycles = fnx.chordless_cycles(graph)

    assert iter(cycles) is cycles
    assert normalize_cycles(cycles) == normalize_cycles(nx.chordless_cycles(expected))


def test_chromatic_polynomial_matches_networkx_expression():
    graph = fnx.complete_graph(4)
    expected = nx.complete_graph(4)

    try:
        import sympy  # noqa: F401
    except ModuleNotFoundError:
        try:
            nx.chromatic_polynomial(expected)
        except ModuleNotFoundError as exc:
            with pytest.raises(ModuleNotFoundError, match=str(exc)):
                fnx.chromatic_polynomial(graph)
        else:
            pytest.fail("expected NetworkX chromatic_polynomial to require sympy")
    else:
        assert str(fnx.chromatic_polynomial(graph)) == str(nx.chromatic_polynomial(expected))


def test_minimum_cycle_basis_matches_networkx_on_triangle():
    graph = fnx.Graph()
    graph.add_edges_from([(0, 1), (1, 2), (2, 0)])
    expected = nx.Graph()
    expected.add_edges_from([(0, 1), (1, 2), (2, 0)])

    assert normalize_cycles(fnx.minimum_cycle_basis(graph)) == normalize_cycles(
        nx.minimum_cycle_basis(expected)
    )


def test_equitable_color_matches_networkx_on_cycle():
    graph = fnx.cycle_graph(4)
    expected = nx.cycle_graph(4)

    assert fnx.equitable_color(graph, 3) == nx.equitable_color(expected, 3)
