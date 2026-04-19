"""Tests for lattice and structured graph generator wrappers."""

import networkx as nx
import pytest

import franken_networkx as fnx
from franken_networkx.backend import _fnx_to_nx as _to_nx


def test_hexagonal_and_triangular_lattice_match_networkx():
    hex_graph = fnx.hexagonal_lattice_graph(2, 3)
    hex_nx = nx.hexagonal_lattice_graph(2, 3)

    tri_graph = fnx.triangular_lattice_graph(2, 3)
    tri_nx = nx.triangular_lattice_graph(2, 3)

    assert sorted(_to_nx(hex_graph).edges()) == sorted(hex_nx.edges())
    assert sorted(_to_nx(tri_graph).edges()) == sorted(tri_nx.edges())
    assert "pos" in hex_graph.nodes[next(iter(hex_graph.nodes()))]
    assert "pos" in tri_graph.nodes[next(iter(tri_graph.nodes()))]


def test_hexagonal_lattice_graph_does_not_delegate_to_networkx(monkeypatch):
    def undirected_edges(graph):
        return sorted(tuple(sorted(edge)) for edge in graph.edges())

    cases = [
        (2, 3, False, True),
        (2, 3, False, False),
        (2, 2, True, True),
    ]
    expected = [
        (
            m,
            n,
            periodic,
            with_positions,
            nx.hexagonal_lattice_graph(
                m,
                n,
                periodic=periodic,
                with_positions=with_positions,
            ),
        )
        for m, n, periodic, with_positions in cases
    ]

    def fail(*args, **kwargs):
        raise AssertionError("networkx hexagonal_lattice_graph fallback was used")

    monkeypatch.setattr(nx, "hexagonal_lattice_graph", fail)

    for m, n, periodic, with_positions, expected_graph in expected:
        actual = _to_nx(
            fnx.hexagonal_lattice_graph(
                m,
                n,
                periodic=periodic,
                with_positions=with_positions,
            )
        )
        assert sorted(actual.nodes()) == sorted(expected_graph.nodes())
        assert undirected_edges(actual) == undirected_edges(expected_graph)
        assert nx.get_node_attributes(actual, "pos") == nx.get_node_attributes(
            expected_graph,
            "pos",
        )


def test_triangular_lattice_graph_does_not_delegate_to_networkx(monkeypatch):
    def undirected_edges(graph):
        return sorted(tuple(sorted(edge)) for edge in graph.edges())

    cases = [
        (3, 4, False, True),
        (3, 5, False, False),
        (3, 5, True, True),
    ]
    expected = [
        (
            m,
            n,
            periodic,
            with_positions,
            nx.triangular_lattice_graph(
                m,
                n,
                periodic=periodic,
                with_positions=with_positions,
            ),
        )
        for m, n, periodic, with_positions in cases
    ]

    def fail(*args, **kwargs):
        raise AssertionError("networkx triangular_lattice_graph fallback was used")

    monkeypatch.setattr(nx, "triangular_lattice_graph", fail)

    for m, n, periodic, with_positions, expected_graph in expected:
        actual = _to_nx(
            fnx.triangular_lattice_graph(
                m,
                n,
                periodic=periodic,
                with_positions=with_positions,
            )
        )
        assert sorted(actual.nodes()) == sorted(expected_graph.nodes())
        assert undirected_edges(actual) == undirected_edges(expected_graph)
        assert nx.get_node_attributes(actual, "pos") == nx.get_node_attributes(
            expected_graph,
            "pos",
        )


def test_grid_graph_matches_networkx():
    graph = fnx.grid_graph([2, 3], periodic=False)
    graph_nx = nx.grid_graph([2, 3], periodic=False)

    assert sorted(_to_nx(graph).edges()) == sorted(graph_nx.edges())
    assert graph.number_of_nodes() == 6


def test_grid_graph_periodic_and_iterable_dimensions_without_networkx_fallback(monkeypatch):
    cases = [
        ([2, 3], [True, False]),
        ([range(7, 9), range(3, 6)], False),
        ([1], True),
        ([[1, 1, 2]], True),
    ]
    expected = [
        (dim, periodic, nx.grid_graph(dim, periodic=periodic))
        for dim, periodic in cases
    ]

    def fail(*args, **kwargs):
        raise AssertionError("networkx grid_graph fallback was used")

    monkeypatch.setattr(nx, "grid_graph", fail)

    for dim, periodic, expected_graph in expected:
        actual = _to_nx(fnx.grid_graph(dim, periodic=periodic))
        assert sorted(actual.nodes()) == sorted(expected_graph.nodes())
        assert sorted(actual.edges()) == sorted(expected_graph.edges())


def test_lattice_reference_preserves_degree_sequence_and_matches_networkx():
    base = fnx.cycle_graph(8)
    rewired = fnx.lattice_reference(base, niter=2, seed=5)
    rewired_nx = nx.lattice_reference(nx.cycle_graph(8), niter=2, seed=5)

    assert sorted(rewired.degree[node] for node in rewired.nodes()) == sorted(
        base.degree[node] for node in base.nodes()
    )
    assert sorted(_to_nx(rewired).edges()) == sorted(rewired_nx.edges())


def test_lattice_reference_does_not_delegate_to_networkx(monkeypatch):
    from networkx.algorithms import smallworld as nx_smallworld

    expected = nx.lattice_reference(nx.cycle_graph(8), niter=2, seed=5)

    def fail(*args, **kwargs):
        raise AssertionError("networkx fallback was used")

    monkeypatch.setattr(nx, "lattice_reference", fail)
    monkeypatch.setattr(nx_smallworld, "lattice_reference", fail)

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


def test_margulis_gabber_galil_graph_does_not_delegate_to_networkx(monkeypatch):
    expected = nx.margulis_gabber_galil_graph(3)

    def fail(*args, **kwargs):
        raise AssertionError("networkx margulis_gabber_galil_graph fallback was used")

    monkeypatch.setattr(nx, "margulis_gabber_galil_graph", fail)

    actual = _to_nx(fnx.margulis_gabber_galil_graph(3))

    assert actual.graph["name"] == expected.graph["name"]
    assert sorted(actual.nodes()) == sorted(expected.nodes())
    assert sorted(actual.edges(keys=True)) == sorted(expected.edges(keys=True))


def test_nonisomorphic_trees_does_not_delegate_to_networkx(monkeypatch):
    expected = [sorted(tree.edges()) for tree in nx.nonisomorphic_trees(5)]

    def fail(*args, **kwargs):
        raise AssertionError("networkx nonisomorphic_trees fallback was used")

    monkeypatch.setattr(nx, "nonisomorphic_trees", fail)

    actual = [sorted(_to_nx(tree).edges()) for tree in fnx.nonisomorphic_trees(5)]

    assert actual == expected
    assert fnx.number_of_nonisomorphic_trees(5) == len(expected)


@pytest.mark.parametrize(
    ("function_name", "kwargs"),
    [
        ("maybe_regular_expander_graph", {"n": 4, "d": 2, "seed": 123}),
        ("maybe_regular_expander_graph", {"n": 10, "d": 4, "seed": 123}),
        ("random_regular_expander_graph", {"n": 10, "d": 4, "epsilon": 0.5, "seed": 123}),
    ],
)
def test_expander_generators_match_networkx_without_fallback(
    monkeypatch, function_name, kwargs
):
    expected = getattr(nx, function_name)(**kwargs)

    def fail(*args, **other_kwargs):
        raise AssertionError(f"networkx {function_name} fallback was used")

    monkeypatch.setattr(nx, function_name, fail)

    actual = _to_nx(getattr(fnx, function_name)(**kwargs))

    assert type(actual) is type(expected)
    assert sorted(actual.nodes()) == sorted(expected.nodes())
    assert sorted(actual.edges()) == sorted(expected.edges())


def test_random_regular_expander_graph_small_case_matches_networkx_contract_without_fallback(
    monkeypatch,
):
    kwargs = {"n": 4, "d": 2, "seed": 123}
    expected = nx.random_regular_expander_graph(**kwargs)

    def fail(*args, **other_kwargs):
        raise AssertionError(
            "networkx random_regular_expander_graph fallback was used"
        )

    monkeypatch.setattr(nx, "random_regular_expander_graph", fail)

    actual = _to_nx(fnx.random_regular_expander_graph(**kwargs))

    # Upstream is not exact-edge deterministic for this degenerate case because the
    # spectral acceptance step can accept different labeled 4-cycles on repeated runs.
    assert type(actual) is type(expected)
    assert sorted(actual.nodes()) == sorted(expected.nodes())
    assert nx.is_isomorphic(actual, expected)
    assert sorted(dict(actual.degree()).values()) == sorted(dict(expected.degree()).values())


@pytest.mark.parametrize(
    ("function_name", "kwargs"),
    [
        ("maybe_regular_expander_graph", {"n": 0, "d": 2, "seed": 123}),
        ("maybe_regular_expander_graph", {"n": 2, "d": 1, "seed": 123}),
        ("maybe_regular_expander_graph", {"n": 10, "d": 3, "seed": 123}),
        ("maybe_regular_expander_graph", {"n": 2, "d": 2, "seed": 123}),
        ("maybe_regular_expander_graph", {"n": 4, "d": 2, "max_tries": 1, "seed": 123}),
        ("random_regular_expander_graph", {"n": 0, "d": 2, "seed": 123}),
        ("random_regular_expander_graph", {"n": 10, "d": 3, "seed": 123}),
        ("random_regular_expander_graph", {"n": 4, "d": 2, "max_tries": 1, "seed": 123}),
    ],
)
def test_expander_generators_error_contract_matches_networkx_without_fallback(
    monkeypatch, function_name, kwargs
):
    try:
        getattr(nx, function_name)(**kwargs)
    except Exception as exc:
        expected_type = type(exc).__name__
        expected_message = str(exc)

    def fail(*args, **other_kwargs):
        raise AssertionError(f"networkx {function_name} fallback was used")

    monkeypatch.setattr(nx, function_name, fail)

    with pytest.raises(Exception) as fnx_exc:
        getattr(fnx, function_name)(**kwargs)

    assert type(fnx_exc.value).__name__ == expected_type
    assert str(fnx_exc.value) == expected_message
