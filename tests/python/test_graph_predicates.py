"""Tests for graph predicate algorithm bindings.

Tests cover:
- is_graphical, is_digraphical, is_multigraphical, is_pseudographical
- is_regular, is_k_regular
- is_tournament
- is_weighted, is_negatively_weighted
- is_path
- is_distance_regular
"""

import importlib.util

import networkx as nx
import pytest
import franken_networkx as fnx
from copy import deepcopy


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def triangle():
    g = fnx.Graph()
    g.add_edge("a", "b")
    g.add_edge("b", "c")
    g.add_edge("c", "a")
    return g


@pytest.fixture
def path3():
    """Path a-b-c."""
    g = fnx.Graph()
    g.add_edge("a", "b")
    g.add_edge("b", "c")
    return g


# ---------------------------------------------------------------------------
# Degree sequence predicates
# ---------------------------------------------------------------------------

class TestIsGraphical:
    def test_triangle(self):
        assert fnx.is_graphical([2, 2, 2]) is True

    def test_single_edge(self):
        assert fnx.is_graphical([1, 1]) is True

    def test_empty(self):
        assert fnx.is_graphical([]) is True

    def test_odd_sum(self):
        assert fnx.is_graphical([1]) is False

    def test_degree_too_high(self):
        assert fnx.is_graphical([3, 1, 1]) is False

    def test_star(self):
        assert fnx.is_graphical([3, 1, 1, 1]) is True

    @pytest.mark.parametrize(
        ("sequence", "method"),
        [
            ([], "eg"),
            ([], "hh"),
            ([0], "eg"),
            ([1], "eg"),
            ([2, -1], "eg"),
            ([-1, -1], "hh"),
            ([1.0, 1.0], "eg"),
            ([1.5, 1.5], "eg"),
            (["1", 1], "hh"),
            ([1, 1], "bogus"),
        ],
    )
    def test_matches_networkx_without_fallback(self, monkeypatch, sequence, method):
        expected_sequence = deepcopy(sequence)
        try:
            expected = nx.is_graphical(expected_sequence, method=method)
        except Exception as exc:
            expected = exc

        monkeypatch.setattr(
            nx,
            "is_graphical",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("NetworkX is_graphical fallback should not be used")
            ),
        )

        actual_sequence = deepcopy(sequence)
        if isinstance(expected, Exception):
            with pytest.raises(Exception) as fnx_exc:
                fnx.is_graphical(actual_sequence, method=method)
            assert type(fnx_exc.value).__name__ == type(expected).__name__
            assert str(fnx_exc.value) == str(expected)
        else:
            assert fnx.is_graphical(actual_sequence, method=method) is expected


class TestIsDigraphical:
    def test_mutual(self):
        assert fnx.is_digraphical([1, 1], [1, 1]) is True

    def test_one_way(self):
        assert fnx.is_digraphical([1, 0], [0, 1]) is True

    def test_empty(self):
        assert fnx.is_digraphical([], []) is True

    def test_unbalanced(self):
        assert fnx.is_digraphical([2, 0], [0, 1]) is False

    @pytest.mark.parametrize(
        ("in_sequence", "out_sequence"),
        [
            ([], []),
            ([1, 1], [1, 1]),
            ([1, 0], [0, 1]),
            ([2, 0], [0, 1]),
            ([-1], [1]),
            ([1.0], [1.0]),
            ([1.5], [1]),
            (["1"], [1]),
            ([1], [1, 0]),
        ],
    )
    def test_matches_networkx_without_fallback(
        self, monkeypatch, in_sequence, out_sequence
    ):
        expected = nx.is_digraphical(
            deepcopy(in_sequence),
            deepcopy(out_sequence),
        )

        monkeypatch.setattr(
            nx,
            "is_digraphical",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("NetworkX is_digraphical fallback should not be used")
            ),
        )

        assert (
            fnx.is_digraphical(
                deepcopy(in_sequence),
                deepcopy(out_sequence),
            )
            is expected
        )


class TestIsMultigraphical:
    def test_valid(self):
        assert fnx.is_multigraphical([2, 2, 2]) is True

    def test_high_degree(self):
        assert fnx.is_multigraphical([4, 2, 2]) is True

    def test_odd_sum(self):
        assert fnx.is_multigraphical([1]) is False

    @pytest.mark.parametrize(
        "sequence",
        [
            [],
            [0],
            [1],
            [2, -1],
            [1.0, 1.0],
            [1.5, 1.5],
            ["1", 1],
        ],
    )
    def test_matches_networkx_without_fallback(self, monkeypatch, sequence):
        expected = nx.is_multigraphical(deepcopy(sequence))
        monkeypatch.setattr(
            nx,
            "is_multigraphical",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError(
                    "NetworkX is_multigraphical fallback should not be used"
                )
            ),
        )
        assert fnx.is_multigraphical(deepcopy(sequence)) is expected


class TestIsPseudographical:
    def test_self_loop(self):
        assert fnx.is_pseudographical([2]) is True

    def test_odd_sum(self):
        assert fnx.is_pseudographical([1]) is False

    @pytest.mark.parametrize(
        "sequence",
        [
            [],
            [0],
            [1],
            [2],
            [2, -1],
            [1.0, 1.0],
            [1.5, 1.5],
            ["1", 1],
        ],
    )
    def test_matches_networkx_without_fallback(self, monkeypatch, sequence):
        expected_sequence = deepcopy(sequence)
        try:
            expected = nx.is_pseudographical(expected_sequence)
        except Exception as exc:
            expected = exc

        monkeypatch.setattr(
            nx,
            "is_pseudographical",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError(
                    "NetworkX is_pseudographical fallback should not be used"
                )
            ),
        )

        actual_sequence = deepcopy(sequence)
        if isinstance(expected, Exception):
            with pytest.raises(Exception) as fnx_exc:
                fnx.is_pseudographical(actual_sequence)
            assert type(fnx_exc.value).__name__ == type(expected).__name__
            assert str(fnx_exc.value) == str(expected)
        else:
            assert fnx.is_pseudographical(actual_sequence) is expected


class TestValidDegreeSequenceAlgorithms:
    @pytest.mark.parametrize(
        ("function_name", "sequence"),
        [
            ("is_valid_degree_sequence_erdos_gallai", []),
            ("is_valid_degree_sequence_erdos_gallai", [3, 3, 2, 2, 2]),
            ("is_valid_degree_sequence_erdos_gallai", [4, 1, 1]),
            ("is_valid_degree_sequence_erdos_gallai", [1.0, 1.0]),
            ("is_valid_degree_sequence_erdos_gallai", [1.5, 1.5]),
            ("is_valid_degree_sequence_erdos_gallai", ["1", 1]),
            ("is_valid_degree_sequence_havel_hakimi", []),
            ("is_valid_degree_sequence_havel_hakimi", [3, 3, 2, 2, 2]),
            ("is_valid_degree_sequence_havel_hakimi", [4, 1, 1]),
            ("is_valid_degree_sequence_havel_hakimi", [1.0, 1.0]),
            ("is_valid_degree_sequence_havel_hakimi", [1.5, 1.5]),
            ("is_valid_degree_sequence_havel_hakimi", ["1", 1]),
        ],
    )
    def test_matches_networkx_without_fallback(
        self, monkeypatch, function_name, sequence
    ):
        expected_sequence = deepcopy(sequence)
        nx_function = getattr(nx, function_name)
        fnx_function = getattr(fnx, function_name)

        try:
            expected = nx_function(expected_sequence)
        except Exception as exc:
            expected = exc

        monkeypatch.setattr(
            nx,
            function_name,
            lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError(f"NetworkX {function_name} fallback should not be used")
            ),
        )

        actual_sequence = deepcopy(sequence)
        if isinstance(expected, Exception):
            with pytest.raises(Exception) as fnx_exc:
                fnx_function(actual_sequence)
            assert type(fnx_exc.value).__name__ == type(expected).__name__
            assert str(fnx_exc.value) == str(expected)
        else:
            assert fnx_function(actual_sequence) is expected


# ---------------------------------------------------------------------------
# Graph regularity
# ---------------------------------------------------------------------------

class TestIsRegular:
    def test_triangle(self, triangle):
        assert fnx.is_regular(triangle) is True

    def test_path(self, path3):
        assert fnx.is_regular(path3) is False

    def test_single_node(self):
        g = fnx.Graph()
        g.add_node("a")
        assert fnx.is_regular(g) is True

    @pytest.mark.parametrize(
        ("fnx_cls", "nx_cls"),
        [
            (fnx.Graph, nx.Graph),
            (fnx.DiGraph, nx.DiGraph),
            (fnx.MultiGraph, nx.MultiGraph),
            (fnx.MultiDiGraph, nx.MultiDiGraph),
        ],
    )
    @pytest.mark.parametrize(
        "builder",
        [
            lambda graph: None,
            lambda graph: graph.add_node("a"),
            lambda graph: graph.add_edge("a", "b"),
            lambda graph: graph.add_edges_from([("a", "b"), ("b", "c"), ("c", "a")]),
        ],
    )
    def test_matches_networkx_without_fallback(
        self, monkeypatch, fnx_cls, nx_cls, builder
    ):
        graph = fnx_cls()
        expected = nx_cls()
        builder(graph)
        builder(expected)

        try:
            expected_result = nx.is_regular(expected)
        except Exception as exc:
            expected_result = exc

        monkeypatch.setattr(
            nx,
            "is_regular",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("NetworkX is_regular fallback should not be used")
            ),
        )

        if isinstance(expected_result, Exception):
            with pytest.raises(Exception) as fnx_exc:
                fnx.is_regular(graph)
            assert type(fnx_exc.value).__name__ == type(expected_result).__name__
            assert str(fnx_exc.value) == str(expected_result)
        else:
            assert fnx.is_regular(graph) is expected_result


class TestIsKRegular:
    def test_triangle_2regular(self, triangle):
        assert fnx.is_k_regular(triangle, 2) is True
        assert fnx.is_k_regular(triangle, 1) is False

    def test_empty_0regular(self):
        g = fnx.Graph()
        g.add_node("a")
        g.add_node("b")
        assert fnx.is_k_regular(g, 0) is True


# ---------------------------------------------------------------------------
# Tournament
# ---------------------------------------------------------------------------

class TestIsTournament:
    def test_complete_oriented(self):
        g = fnx.DiGraph()
        g.add_edge("a", "b")
        g.add_edge("b", "c")
        g.add_edge("a", "c")
        assert fnx.is_tournament(g) is True

    def test_missing_edge(self):
        g = fnx.DiGraph()
        g.add_edge("a", "b")
        g.add_edge("b", "c")
        assert fnx.is_tournament(g) is False

    def test_raises_on_undirected(self, triangle):
        with pytest.raises(fnx.NetworkXNotImplemented):
            fnx.is_tournament(triangle)

    @pytest.mark.parametrize(
        ("fnx_cls", "nx_cls", "builder"),
        [
            (fnx.Graph, nx.Graph, lambda graph: None),
            (fnx.MultiGraph, nx.MultiGraph, lambda graph: None),
            (fnx.MultiDiGraph, nx.MultiDiGraph, lambda graph: None),
            (
                fnx.DiGraph,
                nx.DiGraph,
                lambda graph: graph.add_edges_from([("a", "b"), ("b", "c"), ("a", "c")]),
            ),
            (
                fnx.DiGraph,
                nx.DiGraph,
                lambda graph: graph.add_edges_from([("a", "b"), ("b", "c")]),
            ),
            (
                fnx.DiGraph,
                nx.DiGraph,
                lambda graph: graph.add_edge("a", "a"),
            ),
        ],
    )
    def test_matches_networkx_without_fallback(
        self, monkeypatch, fnx_cls, nx_cls, builder
    ):
        graph = fnx_cls()
        expected = nx_cls()
        builder(graph)
        builder(expected)

        try:
            expected_result = nx.is_tournament(expected)
        except Exception as exc:
            expected_result = exc

        monkeypatch.setattr(
            nx,
            "is_tournament",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("NetworkX is_tournament fallback should not be used")
            ),
        )

        if isinstance(expected_result, Exception):
            with pytest.raises(Exception) as fnx_exc:
                fnx.is_tournament(graph)
            assert type(fnx_exc.value).__name__ == type(expected_result).__name__
            assert str(fnx_exc.value) == str(expected_result)
        else:
            assert fnx.is_tournament(graph) is expected_result


class TestTournamentScoreSequence:
    def test_complete_oriented_scores(self):
        graph = fnx.DiGraph()
        graph.add_edges_from([(1, 0), (1, 3), (0, 2), (0, 3), (2, 1), (3, 2)])
        assert fnx.score_sequence(graph) == [1, 1, 2, 2]

    @pytest.mark.parametrize(
        ("fnx_cls", "nx_cls", "builder"),
        [
            (
                fnx.DiGraph,
                nx.DiGraph,
                lambda graph: graph.add_edges_from(
                    [(1, 0), (1, 3), (0, 2), (0, 3), (2, 1), (3, 2)]
                ),
            ),
            (fnx.Graph, nx.Graph, lambda graph: graph.add_edge("a", "b")),
            (fnx.MultiGraph, nx.MultiGraph, lambda graph: graph.add_edge("a", "b")),
            (fnx.MultiDiGraph, nx.MultiDiGraph, lambda graph: graph.add_edge("a", "b")),
        ],
    )
    def test_matches_networkx_without_fallback(
        self, monkeypatch, fnx_cls, nx_cls, builder
    ):
        graph = fnx_cls()
        expected = nx_cls()
        builder(graph)
        builder(expected)

        try:
            expected_result = nx.tournament.score_sequence(expected)
        except Exception as exc:
            expected_result = exc

        monkeypatch.setattr(
            nx.tournament,
            "score_sequence",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError(
                    "NetworkX tournament.score_sequence fallback should not be used"
                )
            ),
        )

        if isinstance(expected_result, Exception):
            with pytest.raises(Exception) as fnx_exc:
                fnx.score_sequence(graph)
            assert type(fnx_exc.value).__name__ == type(expected_result).__name__
            assert str(fnx_exc.value) == str(expected_result)
        else:
            assert fnx.score_sequence(graph) == expected_result


class TestTournamentIsReachable:
    """Tests for is_reachable tournament algorithm."""

    def test_direct_edge_reachable(self):
        """Direct edge should be reachable."""
        g = fnx.DiGraph()
        g.add_edge("a", "b")
        g.add_edge("b", "c")
        g.add_edge("a", "c")
        assert fnx.is_reachable(g, "a", "b") is True
        assert fnx.is_reachable(g, "a", "c") is True

    def test_transitive_reachable(self):
        """Transitive path should be reachable."""
        g = fnx.DiGraph()
        g.add_edge("a", "b")
        g.add_edge("b", "c")
        g.add_edge("a", "c")
        assert fnx.is_reachable(g, "a", "c") is True

    def test_not_reachable(self):
        """Reverse direction should not be reachable in tournament."""
        g = fnx.DiGraph()
        g.add_edge("a", "b")
        g.add_edge("b", "c")
        g.add_edge("a", "c")
        assert fnx.is_reachable(g, "c", "a") is False
        assert fnx.is_reachable(g, "b", "a") is False

    def test_parity_with_networkx(self):
        """is_reachable should match NetworkX behavior."""
        # Build a complete tournament (all edges go one direction)
        g_fnx = fnx.DiGraph()
        g_nx = nx.DiGraph()
        for g in [g_fnx, g_nx]:
            g.add_edge(0, 1)
            g.add_edge(0, 2)
            g.add_edge(1, 2)

        from networkx.algorithms.tournament import is_reachable as nx_is_reachable

        for s, t in [(0, 1), (0, 2), (1, 2), (1, 0), (2, 0), (2, 1)]:
            fnx_result = fnx.is_reachable(g_fnx, s, t)
            nx_result = nx_is_reachable(g_nx, s, t)
            assert fnx_result == nx_result, f"Mismatch for ({s}, {t})"

    def test_fnx_tuple_labeled_tournament_matches_networkx(self):
        """FrankenNetworkX DiGraph inputs should preserve parity for non-int labels."""
        mapping = {node: ("tour", node) for node in range(4)}
        base_edges = [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)]
        g_fnx = fnx.relabel_nodes(fnx.DiGraph(base_edges), mapping)
        g_nx = nx.relabel_nodes(nx.DiGraph(base_edges), mapping)

        from networkx.algorithms.tournament import is_reachable as nx_is_reachable

        for source in mapping.values():
            for target in mapping.values():
                fnx_result = fnx.is_reachable(g_fnx, source, target)
                nx_result = nx_is_reachable(g_nx, source, target)
                assert fnx_result == nx_result, f"Mismatch for ({source!r}, {target!r})"


@pytest.mark.skipif(
    not importlib.util.find_spec("numpy"), reason="numpy required for tournament_matrix"
)
@pytest.mark.skipif(
    not importlib.util.find_spec("scipy"), reason="scipy required for tournament_matrix"
)
class TestTournamentMatrix:
    """Tests for tournament_matrix algorithm."""

    def test_complete_tournament_matrix(self):
        """Complete tournament should produce proper sparse matrix."""
        import scipy.sparse as sp

        g = fnx.DiGraph()
        g.add_edge(0, 1)
        g.add_edge(0, 2)
        g.add_edge(1, 2)

        mat = fnx.tournament_matrix(g)
        assert sp.issparse(mat)
        assert mat.shape == (3, 3)
        # Convert to dense for easier assertions
        dense = mat.toarray()
        # Row 0: edges to 1 and 2
        assert dense[0, 1] == 1
        assert dense[0, 2] == 1
        # Row 1: edge to 2
        assert dense[1, 2] == 1
        # No self-loops
        assert dense[0, 0] == 0
        assert dense[1, 1] == 0
        assert dense[2, 2] == 0

    def test_parity_with_networkx(self):
        """tournament_matrix should match NetworkX."""
        import numpy as np
        from networkx.algorithms.tournament import tournament_matrix as nx_tournament_matrix

        g_fnx = fnx.DiGraph()
        g_nx = nx.DiGraph()
        for g in [g_fnx, g_nx]:
            g.add_edge(0, 1)
            g.add_edge(0, 2)
            g.add_edge(1, 2)

        fnx_mat = fnx.tournament_matrix(g_fnx)
        nx_mat = nx_tournament_matrix(g_nx)
        # Compare as dense arrays
        np.testing.assert_array_equal(fnx_mat.toarray(), nx_mat.toarray())


# ---------------------------------------------------------------------------
# Directed component predicates
# ---------------------------------------------------------------------------


def _build_semiconnected_case(graph, case_name):
    if case_name == "empty":
        return
    if case_name == "path":
        graph.add_edges_from([("a", "b"), ("b", "c")])
        return
    if case_name == "fork":
        graph.add_edges_from([("a", "b"), ("c", "b")])
        return
    if case_name == "cycle":
        graph.add_edges_from([("a", "b"), ("b", "c"), ("c", "a")])
        return
    raise ValueError(f"unknown semiconnected case {case_name}")


def _build_attracting_case(graph, case_name):
    if case_name == "empty":
        return
    if case_name == "path":
        graph.add_edges_from([("a", "b"), ("b", "c")])
        return
    if case_name == "cycle":
        graph.add_edges_from([("a", "b"), ("b", "c"), ("c", "a")])
        return
    if case_name == "two_sinks":
        graph.add_edges_from([("a", "b"), ("b", "a"), ("c", "d"), ("d", "c")])
        return
    raise ValueError(f"unknown attracting-components case {case_name}")


def _normalize_components(components):
    return sorted(
        (tuple(sorted(component)) for component in components),
        key=lambda component: (len(component), component),
    )


class TestIsSemiconnected:
    @pytest.mark.parametrize(
        ("fnx_cls", "nx_cls"),
        [
            (fnx.DiGraph, nx.DiGraph),
            (fnx.MultiDiGraph, nx.MultiDiGraph),
            (fnx.Graph, nx.Graph),
            (fnx.MultiGraph, nx.MultiGraph),
        ],
    )
    @pytest.mark.parametrize("case_name", ["empty", "path", "fork", "cycle"])
    def test_matches_networkx_without_fallback(
        self, monkeypatch, fnx_cls, nx_cls, case_name
    ):
        graph = fnx_cls()
        expected = nx_cls()
        _build_semiconnected_case(graph, case_name)
        _build_semiconnected_case(expected, case_name)

        try:
            expected_result = nx.is_semiconnected(expected)
        except Exception as exc:
            expected_result = exc

        monkeypatch.setattr(
            nx,
            "is_semiconnected",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("NetworkX is_semiconnected fallback should not be used")
            ),
        )

        if isinstance(expected_result, Exception):
            with pytest.raises(Exception) as fnx_exc:
                fnx.is_semiconnected(graph)
            assert type(fnx_exc.value).__name__ == type(expected_result).__name__
            assert str(fnx_exc.value) == str(expected_result)
        else:
            assert fnx.is_semiconnected(graph) is expected_result


class TestAttractingComponents:
    @pytest.mark.parametrize(
        ("fnx_cls", "nx_cls"),
        [
            (fnx.DiGraph, nx.DiGraph),
            (fnx.MultiDiGraph, nx.MultiDiGraph),
            (fnx.Graph, nx.Graph),
            (fnx.MultiGraph, nx.MultiGraph),
        ],
    )
    @pytest.mark.parametrize("case_name", ["empty", "path", "cycle", "two_sinks"])
    def test_matches_networkx_without_fallback(
        self, monkeypatch, fnx_cls, nx_cls, case_name
    ):
        graph = fnx_cls()
        expected = nx_cls()
        _build_attracting_case(graph, case_name)
        _build_attracting_case(expected, case_name)

        try:
            expected_result = list(nx.attracting_components(expected))
        except Exception as exc:
            expected_result = exc

        monkeypatch.setattr(
            nx,
            "attracting_components",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError(
                    "NetworkX attracting_components fallback should not be used"
                )
            ),
        )

        if isinstance(expected_result, Exception):
            with pytest.raises(Exception) as fnx_exc:
                fnx.attracting_components(graph)
            assert type(fnx_exc.value).__name__ == type(expected_result).__name__
            assert str(fnx_exc.value) == str(expected_result)
        else:
            actual_result = fnx.attracting_components(graph)
            assert not isinstance(actual_result, list)
            assert _normalize_components(actual_result) == _normalize_components(
                expected_result
            )


class TestAttractingComponentHelpers:
    @pytest.mark.parametrize(
        "function_name",
        ["number_attracting_components", "is_attracting_component"],
    )
    @pytest.mark.parametrize(
        ("fnx_cls", "nx_cls"),
        [
            (fnx.DiGraph, nx.DiGraph),
            (fnx.MultiDiGraph, nx.MultiDiGraph),
            (fnx.Graph, nx.Graph),
            (fnx.MultiGraph, nx.MultiGraph),
        ],
    )
    @pytest.mark.parametrize("case_name", ["empty", "path", "cycle", "two_sinks"])
    def test_matches_networkx_without_fallback(
        self, monkeypatch, function_name, fnx_cls, nx_cls, case_name
    ):
        graph = fnx_cls()
        expected = nx_cls()
        _build_attracting_case(graph, case_name)
        _build_attracting_case(expected, case_name)

        nx_function = getattr(nx, function_name)
        try:
            expected_result = nx_function(expected)
        except Exception as exc:
            expected_result = exc

        monkeypatch.setattr(
            nx,
            function_name,
            lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError(
                    f"NetworkX {function_name} fallback should not be used"
                )
            ),
        )

        fnx_function = getattr(fnx, function_name)
        if isinstance(expected_result, Exception):
            with pytest.raises(Exception) as fnx_exc:
                fnx_function(graph)
            assert type(fnx_exc.value).__name__ == type(expected_result).__name__
            assert str(fnx_exc.value) == str(expected_result)
        else:
            assert fnx_function(graph) == expected_result


# ---------------------------------------------------------------------------
# Non-randomness
# ---------------------------------------------------------------------------


def _build_non_randomness_case(graph, case_name):
    if case_name == "path4":
        graph.add_edges_from([(0, 1), (1, 2), (2, 3)])
        return
    if case_name == "cycle4_weighted":
        graph.add_edge(0, 1, weight=1.0)
        graph.add_edge(1, 2, weight=2.0)
        graph.add_edge(2, 3, weight=3.0)
        graph.add_edge(3, 0, weight=4.0)
        return
    if case_name == "empty":
        graph.add_nodes_from([0, 1, 2])
        return
    if case_name == "disconnected":
        graph.add_edges_from([(0, 1), (2, 3)])
        return
    if case_name == "self_loop":
        graph.add_edge(0, 1)
        graph.add_edge(1, 1)
        return
    raise ValueError(f"unknown non_randomness case {case_name}")


class TestNonRandomness:
    @pytest.mark.parametrize(
        ("case_name", "kwargs"),
        [
            ("path4", {"k": 1}),
            ("path4", {}),
            ("cycle4_weighted", {"k": 1, "weight": "weight"}),
            ("cycle4_weighted", {"k": 1, "weight": None}),
        ],
    )
    def test_matches_networkx_without_fallback(self, monkeypatch, case_name, kwargs):
        graph = fnx.Graph()
        expected = nx.Graph()
        _build_non_randomness_case(graph, case_name)
        _build_non_randomness_case(expected, case_name)

        expected_result = nx.non_randomness(expected, **kwargs)

        monkeypatch.setattr(
            nx,
            "non_randomness",
            lambda *args, **other_kwargs: (_ for _ in ()).throw(
                AssertionError("NetworkX non_randomness fallback should not be used")
            ),
        )

        actual_result = fnx.non_randomness(graph, **kwargs)
        assert actual_result == pytest.approx(expected_result)

    @pytest.mark.parametrize(
        ("fnx_cls", "nx_cls"),
        [
            (fnx.DiGraph, nx.DiGraph),
            (fnx.MultiGraph, nx.MultiGraph),
            (fnx.MultiDiGraph, nx.MultiDiGraph),
        ],
    )
    def test_unsupported_graph_types_match_networkx_without_fallback(
        self, monkeypatch, fnx_cls, nx_cls
    ):
        graph = fnx_cls()
        expected = nx_cls()
        graph.add_edge(0, 1)
        expected.add_edge(0, 1)

        try:
            nx.non_randomness(expected)
        except Exception as exc:
            expected_type = type(exc).__name__
            expected_message = str(exc)

        monkeypatch.setattr(
            nx,
            "non_randomness",
            lambda *args, **other_kwargs: (_ for _ in ()).throw(
                AssertionError("NetworkX non_randomness fallback should not be used")
            ),
        )

        with pytest.raises(Exception) as fnx_exc:
            fnx.non_randomness(graph)

        assert type(fnx_exc.value).__name__ == expected_type
        assert str(fnx_exc.value) == expected_message

    @pytest.mark.parametrize(
        ("case_name", "kwargs"),
        [
            ("empty", {}),
            ("disconnected", {}),
            ("self_loop", {}),
            ("path4", {"k": 2}),
            ("path4", {"k": 3}),
        ],
    )
    def test_error_contract_matches_networkx_without_fallback(
        self, monkeypatch, case_name, kwargs
    ):
        graph = fnx.Graph()
        expected = nx.Graph()
        _build_non_randomness_case(graph, case_name)
        _build_non_randomness_case(expected, case_name)

        try:
            nx.non_randomness(expected, **kwargs)
        except Exception as exc:
            expected_type = type(exc).__name__
            expected_message = str(exc)

        monkeypatch.setattr(
            nx,
            "non_randomness",
            lambda *args, **other_kwargs: (_ for _ in ()).throw(
                AssertionError("NetworkX non_randomness fallback should not be used")
            ),
        )

        with pytest.raises(Exception) as fnx_exc:
            fnx.non_randomness(graph, **kwargs)

        assert type(fnx_exc.value).__name__ == expected_type
        assert str(fnx_exc.value) == expected_message


# ---------------------------------------------------------------------------
# Weighted predicates
# ---------------------------------------------------------------------------

class TestIsWeighted:
    def test_weighted(self):
        g = fnx.Graph()
        g.add_edge("a", "b", weight=1.0)
        assert fnx.is_weighted(g) is True

    def test_not_weighted(self, path3):
        assert fnx.is_weighted(path3) is False

    def test_custom_attr(self):
        g = fnx.Graph()
        g.add_edge("a", "b", cost=5.0)
        assert fnx.is_weighted(g, weight="cost") is True
        assert fnx.is_weighted(g) is False

    @pytest.mark.parametrize(
        ("fnx_cls", "nx_cls"),
        [
            (fnx.Graph, nx.Graph),
            (fnx.DiGraph, nx.DiGraph),
            (fnx.MultiGraph, nx.MultiGraph),
            (fnx.MultiDiGraph, nx.MultiDiGraph),
        ],
    )
    def test_matches_networkx_without_fallback(self, monkeypatch, fnx_cls, nx_cls):
        graph = fnx_cls()
        expected = nx_cls()
        graph.add_nodes_from(["a", "b", "c", "d"])
        expected.add_nodes_from(["a", "b", "c", "d"])

        if graph.is_multigraph():
            graph.add_edge("a", "b", key="k1", weight=2)
            graph.add_edge("a", "b", key="k2")
            graph.add_edge("b", "c", key="k3")
            expected.add_edge("a", "b", key="k1", weight=2)
            expected.add_edge("a", "b", key="k2")
            expected.add_edge("b", "c", key="k3")
        else:
            graph.add_edge("a", "b", weight=2)
            graph.add_edge("b", "c")
            expected.add_edge("a", "b", weight=2)
            expected.add_edge("b", "c")

        expected_graph = nx.is_weighted(expected)
        expected_ab = nx.is_weighted(expected, ("a", "b"))
        expected_bc = nx.is_weighted(expected, ("b", "c"))
        try:
            nx.is_weighted(expected, ("a", "d"))
        except Exception as exc:
            expected_missing_type = type(exc).__name__
            expected_missing_message = str(exc)

        monkeypatch.setattr(
            nx,
            "is_weighted",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("NetworkX is_weighted fallback should not be used")
            ),
        )

        assert fnx.is_weighted(graph) is expected_graph
        assert fnx.is_weighted(graph, ("a", "b")) is expected_ab
        assert fnx.is_weighted(graph, ("b", "c")) is expected_bc

        with pytest.raises(Exception) as fnx_exc:
            fnx.is_weighted(graph, ("a", "d"))

        assert type(fnx_exc.value).__name__ == expected_missing_type
        assert str(fnx_exc.value) == expected_missing_message


class TestIsNegativelyWeighted:
    def test_negative(self):
        g = fnx.Graph()
        g.add_edge("a", "b", weight=-1.0)
        assert fnx.is_negatively_weighted(g) is True

    def test_positive(self):
        g = fnx.Graph()
        g.add_edge("a", "b", weight=1.0)
        assert fnx.is_negatively_weighted(g) is False

    @pytest.mark.parametrize(
        ("fnx_cls", "nx_cls"),
        [
            (fnx.Graph, nx.Graph),
            (fnx.DiGraph, nx.DiGraph),
            (fnx.MultiGraph, nx.MultiGraph),
            (fnx.MultiDiGraph, nx.MultiDiGraph),
        ],
    )
    def test_matches_networkx_without_fallback(self, monkeypatch, fnx_cls, nx_cls):
        graph = fnx_cls()
        expected = nx_cls()
        graph.add_nodes_from(["a", "b", "c", "d"])
        expected.add_nodes_from(["a", "b", "c", "d"])

        if graph.is_multigraph():
            graph.add_edge("a", "b", key="k1", weight=2)
            graph.add_edge("a", "b", key="k2")
            graph.add_edge("b", "c", key="k3", weight=-1)
            expected.add_edge("a", "b", key="k1", weight=2)
            expected.add_edge("a", "b", key="k2")
            expected.add_edge("b", "c", key="k3", weight=-1)
        else:
            graph.add_edge("a", "b", weight=2)
            graph.add_edge("b", "c", weight=-1)
            expected.add_edge("a", "b", weight=2)
            expected.add_edge("b", "c", weight=-1)

        expected_graph = nx.is_negatively_weighted(expected)
        expected_ab = nx.is_negatively_weighted(expected, ("a", "b"))
        expected_bc = nx.is_negatively_weighted(expected, ("b", "c"))
        try:
            nx.is_negatively_weighted(expected, ("a", "d"))
        except Exception as exc:
            expected_missing_type = type(exc).__name__
            expected_missing_message = str(exc)

        monkeypatch.setattr(
            nx,
            "is_negatively_weighted",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError(
                    "NetworkX is_negatively_weighted fallback should not be used"
                )
            ),
        )

        assert fnx.is_negatively_weighted(graph) is expected_graph
        assert fnx.is_negatively_weighted(graph, ("a", "b")) is expected_ab
        assert fnx.is_negatively_weighted(graph, ("b", "c")) is expected_bc

        with pytest.raises(Exception) as fnx_exc:
            fnx.is_negatively_weighted(graph, ("a", "d"))

        assert type(fnx_exc.value).__name__ == expected_missing_type
        assert str(fnx_exc.value) == expected_missing_message


# ---------------------------------------------------------------------------
# Path validation
# ---------------------------------------------------------------------------

class TestIsPath:
    @pytest.mark.parametrize(
        ("fnx_cls", "nx_cls"),
        [
            (fnx.Graph, nx.Graph),
            (fnx.DiGraph, nx.DiGraph),
            (fnx.MultiGraph, nx.MultiGraph),
            (fnx.MultiDiGraph, nx.MultiDiGraph),
        ],
    )
    @pytest.mark.parametrize(
        "path",
        [
            ["a", "b", "c"],
            ["a", "c"],
            [],
            ["missing"],
            ["a", "missing"],
            ["a", "b", "a"],
            ["a", ["b"]],
            "abc",
            None,
        ],
    )
    def test_matches_networkx_without_fallback(self, monkeypatch, fnx_cls, nx_cls, path):
        graph = fnx_cls()
        expected = nx_cls()
        if graph.is_multigraph():
            graph.add_edge("a", "b", key="k")
            graph.add_edge("b", "c", key="j")
            expected.add_edge("a", "b", key="k")
            expected.add_edge("b", "c", key="j")
        else:
            graph.add_edge("a", "b")
            graph.add_edge("b", "c")
            expected.add_edge("a", "b")
            expected.add_edge("b", "c")

        expected_result = nx.is_path(expected, path)
        monkeypatch.setattr(
            nx,
            "is_path",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("NetworkX is_path fallback should not be used")
            ),
        )

        assert fnx.is_path(graph, path) is expected_result


# ---------------------------------------------------------------------------
# Distance-regular
# ---------------------------------------------------------------------------

class TestIsDistanceRegular:
    def test_cycle_5(self):
        g = fnx.Graph()
        g.add_edge("a", "b")
        g.add_edge("b", "c")
        g.add_edge("c", "d")
        g.add_edge("d", "e")
        g.add_edge("e", "a")
        assert fnx.is_distance_regular(g) is True

    def test_path_not_regular(self):
        g = fnx.Graph()
        g.add_edge("a", "b")
        g.add_edge("b", "c")
        g.add_edge("c", "d")
        assert fnx.is_distance_regular(g) is False

    def test_complete_graph(self, triangle):
        assert fnx.is_distance_regular(triangle) is True

    @pytest.mark.parametrize(
        ("fnx_cls", "nx_cls", "builder"),
        [
            (fnx.Graph, nx.Graph, lambda graph: None),
            (fnx.Graph, nx.Graph, lambda graph: graph.add_node("a")),
            (
                fnx.Graph,
                nx.Graph,
                lambda graph: graph.add_edges_from(
                    [("a", "b"), ("b", "c"), ("c", "d"), ("d", "e"), ("e", "a")]
                ),
            ),
            (
                fnx.Graph,
                nx.Graph,
                lambda graph: graph.add_edges_from([("a", "b"), ("b", "c"), ("c", "d")]),
            ),
            (
                fnx.Graph,
                nx.Graph,
                lambda graph: graph.add_edges_from(
                    [
                        ("a", "b"),
                        ("a", "c"),
                        ("a", "d"),
                        ("b", "c"),
                        ("b", "d"),
                        ("c", "d"),
                    ]
                ),
            ),
            (
                fnx.DiGraph,
                nx.DiGraph,
                lambda graph: graph.add_edges_from(
                    [("a", "b"), ("b", "c"), ("c", "d"), ("d", "a")]
                ),
            ),
            (
                fnx.MultiGraph,
                nx.MultiGraph,
                lambda graph: graph.add_edges_from(
                    [("a", "b"), ("b", "c"), ("c", "d"), ("d", "a")]
                ),
            ),
            (
                fnx.MultiDiGraph,
                nx.MultiDiGraph,
                lambda graph: graph.add_edges_from(
                    [("a", "b"), ("b", "c"), ("c", "d"), ("d", "a")]
                ),
            ),
        ],
    )
    def test_matches_networkx_without_fallback(
        self, monkeypatch, fnx_cls, nx_cls, builder
    ):
        graph = fnx_cls()
        expected = nx_cls()
        builder(graph)
        builder(expected)

        try:
            expected_result = nx.is_distance_regular(expected)
        except Exception as exc:
            expected_result = exc

        monkeypatch.setattr(
            nx,
            "is_distance_regular",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError(
                    "NetworkX is_distance_regular fallback should not be used"
                )
            ),
        )

        if isinstance(expected_result, Exception):
            with pytest.raises(Exception) as fnx_exc:
                fnx.is_distance_regular(graph)
            assert type(fnx_exc.value).__name__ == type(expected_result).__name__
            assert str(fnx_exc.value) == str(expected_result)
        else:
            assert fnx.is_distance_regular(graph) is expected_result


class TestIsRegularExpander:
    @pytest.mark.parametrize(
        ("builder", "epsilon"),
        [
            (lambda graph: graph.add_edges_from([("a", "b"), ("b", "c"), ("c", "d"), ("d", "a")]), 0),
            (lambda graph: graph.add_edges_from([("a", "b"), ("b", "c"), ("c", "d"), ("d", "a")]), 0.5),
            (lambda graph: graph.add_edges_from([("a", "b"), ("b", "c"), ("c", "d")]), 0),
            (lambda graph: graph.add_edges_from([("a", "b"), ("a", "c"), ("a", "d"), ("b", "c"), ("b", "d"), ("c", "d")]), 0),
        ],
    )
    def test_matches_networkx_without_fallback(self, monkeypatch, builder, epsilon):
        graph = fnx.Graph()
        expected = nx.Graph()
        builder(graph)
        builder(expected)

        expected_result = nx.is_regular_expander(expected, epsilon=epsilon)
        monkeypatch.setattr(
            nx,
            "is_regular_expander",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("NetworkX is_regular_expander fallback should not be used")
            ),
        )

        assert fnx.is_regular_expander(graph, epsilon=epsilon) is expected_result

    @pytest.mark.parametrize(
        ("fnx_cls", "nx_cls"),
        [
            (fnx.DiGraph, nx.DiGraph),
            (fnx.MultiGraph, nx.MultiGraph),
            (fnx.MultiDiGraph, nx.MultiDiGraph),
        ],
    )
    def test_unsupported_graph_types_match_networkx_without_fallback(
        self, monkeypatch, fnx_cls, nx_cls
    ):
        graph = fnx_cls()
        expected = nx_cls()
        graph.add_nodes_from(["a", "b", "c", "d"])
        expected.add_nodes_from(["a", "b", "c", "d"])

        try:
            nx.is_regular_expander(expected)
        except Exception as exc:
            expected_type = type(exc).__name__
            expected_message = str(exc)

        monkeypatch.setattr(
            nx,
            "is_regular_expander",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("NetworkX is_regular_expander fallback should not be used")
            ),
        )

        with pytest.raises(Exception) as fnx_exc:
            fnx.is_regular_expander(graph)

        assert type(fnx_exc.value).__name__ == expected_type
        assert str(fnx_exc.value) == expected_message

    @pytest.mark.parametrize(
        ("builder", "epsilon"),
        [
            (lambda graph: None, 0),
            (lambda graph: graph.add_edges_from([("a", "b"), ("b", "c"), ("c", "d"), ("d", "a")]), -1),
        ],
    )
    def test_error_contract_matches_networkx_without_fallback(
        self, monkeypatch, builder, epsilon
    ):
        graph = fnx.Graph()
        expected = nx.Graph()
        builder(graph)
        builder(expected)

        try:
            nx.is_regular_expander(expected, epsilon=epsilon)
        except Exception as exc:
            expected_type = type(exc).__name__
            expected_message = str(exc)

        monkeypatch.setattr(
            nx,
            "is_regular_expander",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("NetworkX is_regular_expander fallback should not be used")
            ),
        )

        with pytest.raises(Exception) as fnx_exc:
            fnx.is_regular_expander(graph, epsilon=epsilon)

        assert type(fnx_exc.value).__name__ == expected_type
        assert str(fnx_exc.value) == expected_message
