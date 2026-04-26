"""Tests for clustering and clique algorithm bindings.

Tests cover:
- all_triangles
- node_clique_number
- enumerate_all_cliques
- find_cliques_recursive
- chordal_graph_cliques
- make_max_clique_graph
- ring_of_cliques
"""

import networkx as nx
import pytest
import franken_networkx as fnx


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
def k4():
    g = fnx.Graph()
    for u, v in [("a", "b"), ("a", "c"), ("a", "d"), ("b", "c"), ("b", "d"), ("c", "d")]:
        g.add_edge(u, v)
    return g


@pytest.fixture
def path3():
    g = fnx.Graph()
    g.add_edge("a", "b")
    g.add_edge("b", "c")
    return g


@pytest.fixture
def diamond():
    """Diamond graph: a-b, a-c, b-c, b-d, c-d (two triangles sharing edge b-c)."""
    g = fnx.Graph()
    g.add_edge("a", "b")
    g.add_edge("a", "c")
    g.add_edge("b", "c")
    g.add_edge("b", "d")
    g.add_edge("c", "d")
    return g


# ---------------------------------------------------------------------------
# all_triangles
# ---------------------------------------------------------------------------

class TestAllTriangles:
    def test_triangle(self, triangle):
        tris = list(fnx.all_triangles(triangle))
        assert len(tris) == 1
        # The triangle should contain all three nodes
        tri_set = set(tris[0])
        assert tri_set == {"a", "b", "c"}

    def test_k4(self, k4):
        tris = list(fnx.all_triangles(k4))
        # K4 has C(4,3) = 4 triangles
        assert len(tris) == 4

    def test_path_no_triangles(self, path3):
        tris = list(fnx.all_triangles(path3))
        assert tris == []

    def test_diamond(self, diamond):
        tris = list(fnx.all_triangles(diamond))
        # Diamond has 2 triangles: (a,b,c) and (b,c,d)
        assert len(tris) == 2

    def test_empty_graph(self):
        g = fnx.Graph()
        assert list(fnx.all_triangles(g)) == []

    def test_single_node(self):
        g = fnx.Graph()
        g.add_node("x")
        assert list(fnx.all_triangles(g)) == []


def _build_all_triangles_case(graph, case_name):
    if case_name == "triangle":
        graph.add_edges_from([(0, 1), (1, 2), (2, 0)])
        return
    if case_name == "two_triangles":
        graph.add_edges_from([(0, 1), (1, 2), (2, 0), (2, 3), (3, 4), (4, 2)])
        return
    if case_name == "parallel_triangle":
        graph.add_edge(0, 1)
        graph.add_edge(0, 1)
        graph.add_edge(1, 2)
        graph.add_edge(2, 0)
        graph.add_edge(2, 2)
        return
    if case_name == "empty":
        return
    raise ValueError(f"unknown all_triangles case {case_name}")


def _build_number_of_cliques_case(graph, case_name):
    if case_name == "triangle_tail":
        graph.add_edges_from([(0, 1), (1, 2), (2, 0), (2, 3)])
        return
    if case_name == "empty":
        return
    raise ValueError(f"unknown number_of_cliques case {case_name}")


class TestAllTrianglesParity:
    @pytest.mark.parametrize(
        ("fnx_cls", "nx_cls", "case_name", "kwargs"),
        [
            (fnx.Graph, nx.Graph, "two_triangles", {}),
            (fnx.Graph, nx.Graph, "two_triangles", {"nbunch": 2}),
            (fnx.Graph, nx.Graph, "two_triangles", {"nbunch": [2, 3, 99]}),
            (fnx.Graph, nx.Graph, "empty", {"nbunch": []}),
            (fnx.MultiGraph, nx.MultiGraph, "parallel_triangle", {}),
            (fnx.MultiGraph, nx.MultiGraph, "parallel_triangle", {"nbunch": [0, 99]}),
        ],
    )
    def test_matches_networkx_without_fallback(
        self, monkeypatch, fnx_cls, nx_cls, case_name, kwargs
    ):
        graph = fnx_cls()
        expected = nx_cls()
        _build_all_triangles_case(graph, case_name)
        _build_all_triangles_case(expected, case_name)

        expected_result = list(nx.all_triangles(expected, **kwargs))

        monkeypatch.setattr(
            nx,
            "all_triangles",
            lambda *call_args, **call_kwargs: (_ for _ in ()).throw(
                AssertionError("NetworkX all_triangles fallback should not be used")
            ),
        )

        actual_result = list(fnx.all_triangles(graph, **kwargs))
        assert actual_result == expected_result

    @pytest.mark.parametrize(
        ("fnx_cls", "nx_cls", "case_name", "kwargs"),
        [
            (fnx.DiGraph, nx.DiGraph, "triangle", {}),
            (fnx.DiGraph, nx.DiGraph, "triangle", {"nbunch": [0]}),
            (fnx.Graph, nx.Graph, "triangle", {"nbunch": 9}),
            (fnx.Graph, nx.Graph, "triangle", {"nbunch": [[0]]}),
        ],
    )
    def test_error_contract_matches_networkx_without_fallback(
        self, monkeypatch, fnx_cls, nx_cls, case_name, kwargs
    ):
        graph = fnx_cls()
        expected = nx_cls()
        _build_all_triangles_case(graph, case_name)
        _build_all_triangles_case(expected, case_name)

        try:
            list(nx.all_triangles(expected, **kwargs))
        except Exception as exc:
            expected_type = type(exc).__name__
            expected_message = str(exc)

        monkeypatch.setattr(
            nx,
            "all_triangles",
            lambda *call_args, **call_kwargs: (_ for _ in ()).throw(
                AssertionError("NetworkX all_triangles fallback should not be used")
            ),
        )

        with pytest.raises(Exception) as fnx_exc:
            list(fnx.all_triangles(graph, **kwargs))

        assert type(fnx_exc.value).__name__ == expected_type
        assert str(fnx_exc.value) == expected_message


# ---------------------------------------------------------------------------
# number_of_cliques
# ---------------------------------------------------------------------------

class TestNumberOfCliquesParity:
    @pytest.mark.parametrize(
        ("fnx_cls", "nx_cls", "case_name", "kwargs"),
        [
            (fnx.Graph, nx.Graph, "triangle_tail", {}),
            (fnx.Graph, nx.Graph, "triangle_tail", {"nodes": 0}),
            (fnx.Graph, nx.Graph, "triangle_tail", {"nodes": [0, 2, 9]}),
            (fnx.Graph, nx.Graph, "triangle_tail", {"nodes": 9}),
            (
                fnx.Graph,
                nx.Graph,
                "triangle_tail",
                {"cliques": [[0, 1, 2], [2, 3]]},
            ),
            (
                fnx.Graph,
                nx.Graph,
                "triangle_tail",
                {"nodes": [0, 2, 9], "cliques": [[0, 1, 2], [2, 3]]},
            ),
            (fnx.MultiGraph, nx.MultiGraph, "triangle_tail", {}),
            (
                fnx.DiGraph,
                nx.DiGraph,
                "triangle_tail",
                {"cliques": [[0, 1, 2], [2, 3]]},
            ),
            (
                fnx.DiGraph,
                nx.DiGraph,
                "triangle_tail",
                {"nodes": 0, "cliques": [[0, 1, 2], [2, 3]]},
            ),
        ],
    )
    def test_matches_networkx_without_fallback(
        self, monkeypatch, fnx_cls, nx_cls, case_name, kwargs
    ):
        graph = fnx_cls()
        expected = nx_cls()
        _build_number_of_cliques_case(graph, case_name)
        _build_number_of_cliques_case(expected, case_name)

        expected_result = nx.number_of_cliques(expected, **kwargs)

        monkeypatch.setattr(
            nx,
            "number_of_cliques",
            lambda *call_args, **call_kwargs: (_ for _ in ()).throw(
                AssertionError("NetworkX number_of_cliques fallback should not be used")
            ),
        )

        actual_result = fnx.number_of_cliques(graph, **kwargs)
        assert actual_result == expected_result

    @pytest.mark.parametrize(
        ("fnx_cls", "nx_cls", "case_name", "kwargs"),
        [
            (fnx.DiGraph, nx.DiGraph, "triangle_tail", {}),
            (fnx.DiGraph, nx.DiGraph, "triangle_tail", {"nodes": 0}),
            (fnx.DiGraph, nx.DiGraph, "triangle_tail", {"nodes": [0, 2, 9]}),
            (fnx.Graph, nx.Graph, "triangle_tail", {"nodes": [[0]]}),
        ],
    )
    def test_error_contract_matches_networkx_without_fallback(
        self, monkeypatch, fnx_cls, nx_cls, case_name, kwargs
    ):
        graph = fnx_cls()
        expected = nx_cls()
        _build_number_of_cliques_case(graph, case_name)
        _build_number_of_cliques_case(expected, case_name)

        try:
            nx.number_of_cliques(expected, **kwargs)
        except Exception as exc:
            expected_type = type(exc).__name__
            expected_message = str(exc)

        monkeypatch.setattr(
            nx,
            "number_of_cliques",
            lambda *call_args, **call_kwargs: (_ for _ in ()).throw(
                AssertionError("NetworkX number_of_cliques fallback should not be used")
            ),
        )

        with pytest.raises(Exception) as fnx_exc:
            fnx.number_of_cliques(graph, **kwargs)

        assert type(fnx_exc.value).__name__ == expected_type
        assert str(fnx_exc.value) == expected_message


# ---------------------------------------------------------------------------
# node_clique_number
# ---------------------------------------------------------------------------

class TestNodeCliqueNumberParity:
    @pytest.mark.parametrize(
        ("fnx_cls", "nx_cls", "case_name", "kwargs"),
        [
            (fnx.Graph, nx.Graph, "triangle_tail", {}),
            (fnx.Graph, nx.Graph, "triangle_tail", {"nodes": 0}),
            (fnx.Graph, nx.Graph, "triangle_tail", {"nodes": [0, 2]}),
            (
                fnx.Graph,
                nx.Graph,
                "triangle_tail",
                {"cliques": [[0, 1, 2], [2, 3]]},
            ),
            (
                fnx.Graph,
                nx.Graph,
                "triangle_tail",
                {"nodes": [0, 2, 9], "cliques": [[0, 1, 2], [2, 3]]},
            ),
            (fnx.MultiGraph, nx.MultiGraph, "triangle_tail", {}),
            (fnx.MultiGraph, nx.MultiGraph, "triangle_tail", {"nodes": 0}),
            (
                fnx.DiGraph,
                nx.DiGraph,
                "triangle_tail",
                {"cliques": [[0, 1, 2], [2, 3]]},
            ),
            (
                fnx.MultiDiGraph,
                nx.MultiDiGraph,
                "triangle_tail",
                {"nodes": [0, 2, 9], "cliques": [[0, 1, 2], [2, 3]]},
            ),
        ],
    )
    def test_matches_networkx_without_fallback(
        self, monkeypatch, fnx_cls, nx_cls, case_name, kwargs
    ):
        graph = fnx_cls()
        expected = nx_cls()
        _build_number_of_cliques_case(graph, case_name)
        _build_number_of_cliques_case(expected, case_name)

        expected_result = nx.node_clique_number(expected, **kwargs)

        monkeypatch.setattr(
            nx,
            "node_clique_number",
            lambda *call_args, **call_kwargs: (_ for _ in ()).throw(
                AssertionError("NetworkX node_clique_number fallback should not be used")
            ),
        )

        actual_result = fnx.node_clique_number(graph, **kwargs)
        assert actual_result == expected_result

    @pytest.mark.parametrize(
        ("fnx_cls", "nx_cls", "case_name", "kwargs"),
        [
            (fnx.Graph, nx.Graph, "triangle_tail", {"nodes": 9}),
            (fnx.Graph, nx.Graph, "triangle_tail", {"nodes": [[0]]}),
            (
                fnx.Graph,
                nx.Graph,
                "triangle_tail",
                {"nodes": 9, "cliques": [[0, 1, 2], [2, 3]]},
            ),
            (
                fnx.Graph,
                nx.Graph,
                "triangle_tail",
                {"nodes": [[0]], "cliques": [[0, 1, 2], [2, 3]]},
            ),
            (fnx.DiGraph, nx.DiGraph, "triangle_tail", {}),
            (fnx.DiGraph, nx.DiGraph, "triangle_tail", {"nodes": 0}),
            (fnx.DiGraph, nx.DiGraph, "triangle_tail", {"nodes": [0, 2, 9]}),
        ],
    )
    def test_error_contract_matches_networkx_without_fallback(
        self, monkeypatch, fnx_cls, nx_cls, case_name, kwargs
    ):
        graph = fnx_cls()
        expected = nx_cls()
        _build_number_of_cliques_case(graph, case_name)
        _build_number_of_cliques_case(expected, case_name)

        try:
            nx.node_clique_number(expected, **kwargs)
        except Exception as exc:
            expected_type = type(exc).__name__
            expected_message = str(exc)

        monkeypatch.setattr(
            nx,
            "node_clique_number",
            lambda *call_args, **call_kwargs: (_ for _ in ()).throw(
                AssertionError("NetworkX node_clique_number fallback should not be used")
            ),
        )

        with pytest.raises(Exception) as fnx_exc:
            fnx.node_clique_number(graph, **kwargs)

        assert type(fnx_exc.value).__name__ == expected_type
        assert str(fnx_exc.value) == expected_message


class TestNodeCliqueNumber:
    def test_triangle(self, triangle):
        result = fnx.node_clique_number(triangle)
        # All nodes are in a 3-clique
        assert result["a"] == 3
        assert result["b"] == 3
        assert result["c"] == 3

    def test_k4(self, k4):
        result = fnx.node_clique_number(k4)
        for node in ["a", "b", "c", "d"]:
            assert result[node] == 4

    def test_path(self, path3):
        result = fnx.node_clique_number(path3)
        # Path nodes are in at most a 2-clique (edge)
        for node in ["a", "b", "c"]:
            assert result[node] == 2

    def test_isolated_node(self):
        g = fnx.Graph()
        g.add_node("x")
        result = fnx.node_clique_number(g)
        assert result["x"] == 1

    def test_diamond(self, diamond):
        result = fnx.node_clique_number(diamond)
        # a is in triangle (a,b,c) → clique number 3
        assert result["a"] == 3
        # d is in triangle (b,c,d) → clique number 3
        assert result["d"] == 3


# ---------------------------------------------------------------------------
# enumerate_all_cliques
# ---------------------------------------------------------------------------

class TestEnumerateAllCliques:
    # br-bulkgen: nx.enumerate_all_cliques returns a generator; fnx
    # matches. Tests list()-materialize before asserting list semantics.
    def test_triangle(self, triangle):
        cliques = list(fnx.enumerate_all_cliques(triangle))
        # 3 single-node cliques + 3 edge cliques + 1 triangle = 7
        assert len(cliques) == 7
        sizes = [len(c) for c in cliques]
        assert sizes.count(1) == 3
        assert sizes.count(2) == 3
        assert sizes.count(3) == 1

    def test_path(self, path3):
        cliques = list(fnx.enumerate_all_cliques(path3))
        # 3 single nodes + 2 edges = 5
        assert len(cliques) == 5

    def test_k4(self, k4):
        cliques = list(fnx.enumerate_all_cliques(k4))
        # C(4,1) + C(4,2) + C(4,3) + C(4,4) = 4 + 6 + 4 + 1 = 15
        assert len(cliques) == 15

    def test_empty_graph(self):
        g = fnx.Graph()
        assert list(fnx.enumerate_all_cliques(g)) == []

    def test_single_node(self):
        g = fnx.Graph()
        g.add_node("x")
        cliques = list(fnx.enumerate_all_cliques(g))
        assert len(cliques) == 1
        assert cliques[0] == ["x"]


# ---------------------------------------------------------------------------
# find_cliques
# ---------------------------------------------------------------------------

def _build_find_cliques_case(graph, case_name):
    if case_name == "triangle_tail":
        graph.add_edges_from([(0, 1), (1, 2), (2, 0), (2, 3)])
        return
    if case_name == "path3":
        graph.add_edges_from([(0, 1), (1, 2)])
        return
    if case_name == "empty":
        return
    raise ValueError(f"unknown find_cliques case {case_name}")


def _normalize_graph_with_attrs(graph):
    nodes = sorted(
        ((repr(node), dict(attrs)) for node, attrs in graph.nodes(data=True)),
        key=lambda item: item[0],
    )
    if graph.is_directed():
        edges = sorted(
            ((repr(u), repr(v), dict(attrs)) for u, v, attrs in graph.edges(data=True)),
            key=lambda item: (item[0], item[1]),
        )
    else:
        edges = sorted(
            (
                tuple(sorted((repr(u), repr(v)))),
                dict(attrs),
            )
            for u, v, attrs in graph.edges(data=True)
        )
    return type(graph).__name__, nodes, edges


class TestFindCliquesParity:
    @pytest.mark.parametrize(
        ("fnx_cls", "nx_cls", "case_name", "kwargs"),
        [
            # br-r37-c1-g71v3: the nodes=None path now legitimately
            # delegates to nx for iteration-order parity, so empty-
            # kwargs cases moved to the
            # tests/python/test_find_cliques_iteration_order_parity.py
            # parametrisation. The nodes= branch still runs the
            # local pure-Python algorithm and keeps the no-fallback
            # contract here.
            (fnx.Graph, nx.Graph, "triangle_tail", {"nodes": [0, 2]}),
            (fnx.Graph, nx.Graph, "path3", {"nodes": [0, 1]}),
            (fnx.MultiGraph, nx.MultiGraph, "triangle_tail", {"nodes": [0, 2]}),
        ],
    )
    def test_matches_networkx_without_fallback(
        self, monkeypatch, fnx_cls, nx_cls, case_name, kwargs
    ):
        graph = fnx_cls()
        expected = nx_cls()
        _build_find_cliques_case(graph, case_name)
        _build_find_cliques_case(expected, case_name)

        expected_result = list(nx.find_cliques(expected, **kwargs))

        monkeypatch.setattr(
            nx,
            "find_cliques",
            lambda *call_args, **call_kwargs: (_ for _ in ()).throw(
                AssertionError("NetworkX find_cliques fallback should not be used")
            ),
        )

        actual_result = list(fnx.find_cliques(graph, **kwargs))
        normalize = lambda cliques: sorted(tuple(sorted(clique)) for clique in cliques)
        assert normalize(actual_result) == normalize(expected_result)

    @pytest.mark.parametrize(
        ("fnx_cls", "nx_cls", "case_name", "kwargs"),
        [
            (fnx.DiGraph, nx.DiGraph, "triangle_tail", {}),
            (fnx.DiGraph, nx.DiGraph, "triangle_tail", {"nodes": [0, 2]}),
            (fnx.Graph, nx.Graph, "triangle_tail", {"nodes": 0}),
            (fnx.Graph, nx.Graph, "triangle_tail", {"nodes": [0, 9]}),
            (fnx.Graph, nx.Graph, "triangle_tail", {"nodes": [[0]]}),
            (fnx.Graph, nx.Graph, "path3", {"nodes": [0, 2]}),
        ],
    )
    def test_error_contract_matches_networkx_without_fallback(
        self, monkeypatch, fnx_cls, nx_cls, case_name, kwargs
    ):
        graph = fnx_cls()
        expected = nx_cls()
        _build_find_cliques_case(graph, case_name)
        _build_find_cliques_case(expected, case_name)

        try:
            list(nx.find_cliques(expected, **kwargs))
        except Exception as exc:
            expected_type = type(exc).__name__
            expected_message = str(exc)

        monkeypatch.setattr(
            nx,
            "find_cliques",
            lambda *call_args, **call_kwargs: (_ for _ in ()).throw(
                AssertionError("NetworkX find_cliques fallback should not be used")
            ),
        )

        with pytest.raises(Exception) as fnx_exc:
            list(fnx.find_cliques(graph, **kwargs))

        assert type(fnx_exc.value).__name__ == expected_type
        assert str(fnx_exc.value) == expected_message


# ---------------------------------------------------------------------------
# find_cliques_recursive
# ---------------------------------------------------------------------------

class TestFindCliquesRecursive:
    # br-bulkgen: list()-materialize before len()/indexing since nx
    # returns a generator from find_cliques_recursive.
    def test_triangle(self, triangle):
        cliques = list(fnx.find_cliques_recursive(triangle))
        assert len(cliques) == 1
        assert set(cliques[0]) == {"a", "b", "c"}

    def test_k4(self, k4):
        cliques = list(fnx.find_cliques_recursive(k4))
        assert len(cliques) == 1
        assert set(cliques[0]) == {"a", "b", "c", "d"}

    def test_matches_find_cliques(self, diamond):
        rec = list(fnx.find_cliques_recursive(diamond))
        iterative = list(fnx.find_cliques(diamond))
        # Both should return same cliques (sorted)
        assert sorted([sorted(c) for c in rec]) == sorted([sorted(c) for c in iterative])

    def test_path(self, path3):
        cliques = list(fnx.find_cliques_recursive(path3))
        # Two maximal cliques: {a,b} and {b,c}
        assert len(cliques) == 2

    def test_empty_graph(self):
        g = fnx.Graph()
        assert list(fnx.find_cliques_recursive(g)) == []


class TestFindCliquesRecursiveParity:
    @pytest.mark.parametrize(
        ("graph", "expected_graph", "case_name", "kwargs"),
        [
            # br-r37-c1-g71v3: the nodes=None path now legitimately
            # delegates to nx for iteration-order parity. Empty-kwargs
            # cases moved to test_find_cliques_iteration_order_parity.py.
            (fnx.Graph(), nx.Graph(), "triangle_tail", {"nodes": [0, 2]}),
            (fnx.Graph(), nx.Graph(), "path3", {"nodes": [0, 1]}),
            (fnx.MultiGraph(), nx.MultiGraph(), "triangle_tail", {"nodes": [0, 2]}),
        ],
    )
    def test_matches_networkx_without_fallback(
        self, monkeypatch, graph, expected_graph, case_name, kwargs
    ):
        _build_find_cliques_case(graph, case_name)
        _build_find_cliques_case(expected_graph, case_name)

        expected_result = list(nx.find_cliques_recursive(expected_graph, **kwargs))
        monkeypatch.setattr(
            nx,
            "find_cliques_recursive",
            lambda *args, **inner_kwargs: (_ for _ in ()).throw(
                AssertionError(
                    "NetworkX find_cliques_recursive fallback should not be used"
                )
            ),
        )

        actual_result = list(fnx.find_cliques_recursive(graph, **kwargs))
        normalize = lambda cliques: sorted(tuple(sorted(clique)) for clique in cliques)
        assert normalize(actual_result) == normalize(expected_result)

    @pytest.mark.parametrize(
        ("graph", "expected_graph", "case_name", "kwargs"),
        [
            # br-r37-c1-g71v3: nodes=None on DiGraph now delegates to
            # nx (which raises NetworkXNotImplemented), so the empty-
            # kwargs DiGraph error case is dropped from the no-fallback
            # parametrisation. The nodes= cases keep the contract since
            # they hit the local pure-Python error path.
            (fnx.DiGraph(), nx.DiGraph(), "triangle_tail", {"nodes": [0, 2]}),
            (fnx.Graph(), nx.Graph(), "triangle_tail", {"nodes": 0}),
            (fnx.Graph(), nx.Graph(), "triangle_tail", {"nodes": [0, 9]}),
            (fnx.Graph(), nx.Graph(), "triangle_tail", {"nodes": [[0]]}),
            (fnx.Graph(), nx.Graph(), "path3", {"nodes": [0, 2]}),
        ],
    )
    def test_error_contract_matches_networkx_without_fallback(
        self, monkeypatch, graph, expected_graph, case_name, kwargs
    ):
        _build_find_cliques_case(graph, case_name)
        _build_find_cliques_case(expected_graph, case_name)

        try:
            list(nx.find_cliques_recursive(expected_graph, **kwargs))
        except Exception as exc:
            expected_type = type(exc).__name__
            expected_message = str(exc)

        monkeypatch.setattr(
            nx,
            "find_cliques_recursive",
            lambda *args, **inner_kwargs: (_ for _ in ()).throw(
                AssertionError(
                    "NetworkX find_cliques_recursive fallback should not be used"
                )
            ),
        )

        with pytest.raises(Exception) as fnx_exc:
            list(fnx.find_cliques_recursive(graph, **kwargs))

        assert type(fnx_exc.value).__name__ == expected_type
        assert str(fnx_exc.value) == expected_message


# ---------------------------------------------------------------------------
# make_clique_bipartite
# ---------------------------------------------------------------------------

class TestMakeCliqueBipartiteParity:
    @pytest.mark.parametrize(
        ("fnx_cls", "nx_cls", "case_name"),
        [
            (fnx.Graph, nx.Graph, "triangle_tail"),
            (fnx.MultiGraph, nx.MultiGraph, "triangle_tail"),
            (fnx.Graph, nx.Graph, "empty"),
        ],
    )
    def test_matches_networkx_without_fallback(
        self, monkeypatch, fnx_cls, nx_cls, case_name
    ):
        graph = fnx_cls()
        expected = nx_cls()
        _build_find_cliques_case(graph, case_name)
        _build_find_cliques_case(expected, case_name)

        expected_result = nx.make_clique_bipartite(expected)

        monkeypatch.setattr(
            nx,
            "make_clique_bipartite",
            lambda *call_args, **call_kwargs: (_ for _ in ()).throw(
                AssertionError(
                    "NetworkX make_clique_bipartite fallback should not be used"
                )
            ),
        )

        actual_result = fnx.make_clique_bipartite(graph)
        assert _normalize_graph_with_attrs(actual_result) == _normalize_graph_with_attrs(
            expected_result
        )

    def test_create_using_instance_matches_networkx_without_fallback(self, monkeypatch):
        graph = fnx.Graph()
        expected = nx.Graph()
        _build_find_cliques_case(graph, "triangle_tail")
        _build_find_cliques_case(expected, "triangle_tail")

        fnx_target = fnx.DiGraph()
        fnx_target.add_edge("stale", "edge")
        expected_target = nx.DiGraph()
        expected_target.add_edge("stale", "edge")

        expected_result = nx.make_clique_bipartite(expected, create_using=expected_target)

        monkeypatch.setattr(
            nx,
            "make_clique_bipartite",
            lambda *call_args, **call_kwargs: (_ for _ in ()).throw(
                AssertionError(
                    "NetworkX make_clique_bipartite fallback should not be used"
                )
            ),
        )

        actual_result = fnx.make_clique_bipartite(graph, create_using=fnx_target)
        assert actual_result is fnx_target
        assert _normalize_graph_with_attrs(actual_result) == _normalize_graph_with_attrs(
            expected_result
        )

    @pytest.mark.parametrize(
        ("fnx_cls", "nx_cls", "case_name"),
        [
            (fnx.DiGraph, nx.DiGraph, "triangle_tail"),
            (fnx.MultiDiGraph, nx.MultiDiGraph, "triangle_tail"),
        ],
    )
    def test_error_contract_matches_networkx_without_fallback(
        self, monkeypatch, fnx_cls, nx_cls, case_name
    ):
        graph = fnx_cls()
        expected = nx_cls()
        _build_find_cliques_case(graph, case_name)
        _build_find_cliques_case(expected, case_name)

        try:
            nx.make_clique_bipartite(expected)
        except Exception as exc:
            expected_type = type(exc).__name__
            expected_message = str(exc)

        monkeypatch.setattr(
            nx,
            "make_clique_bipartite",
            lambda *call_args, **call_kwargs: (_ for _ in ()).throw(
                AssertionError(
                    "NetworkX make_clique_bipartite fallback should not be used"
                )
            ),
        )

        with pytest.raises(Exception) as fnx_exc:
            fnx.make_clique_bipartite(graph)

        assert type(fnx_exc.value).__name__ == expected_type
        assert str(fnx_exc.value) == expected_message


# ---------------------------------------------------------------------------
# chordal_graph_cliques
# ---------------------------------------------------------------------------

class TestChordalGraphCliques:
    def test_triangle(self, triangle):
        cliques = list(fnx.chordal_graph_cliques(triangle))
        assert len(cliques) == 1
        assert set(cliques[0]) == {"a", "b", "c"}

    def test_path(self, path3):
        cliques = list(fnx.chordal_graph_cliques(path3))
        assert len(cliques) == 2

    def test_k4(self, k4):
        cliques = list(fnx.chordal_graph_cliques(k4))
        # K4 is chordal, one maximal clique
        assert len(cliques) == 1

    def test_self_loop_raises(self):
        g = fnx.Graph()
        g.add_edge("a", "a")
        with pytest.raises(fnx.NetworkXError):
            fnx.chordal_graph_cliques(g)


def _build_chordal_graph_cliques_case(graph, case_name):
    if case_name == "triangle_tail":
        graph.add_edges_from([(0, 1), (1, 2), (2, 0), (2, 3)])
        return
    if case_name == "cycle4":
        graph.add_edges_from([(0, 1), (1, 2), (2, 3), (3, 0)])
        return
    if case_name == "self_loop":
        graph.add_edge(0, 0)
        return
    raise ValueError(f"unknown chordal_graph_cliques case {case_name}")


class TestChordalGraphCliquesParity:
    @pytest.mark.parametrize(
        ("fnx_cls", "nx_cls", "case_name"),
        [
            (fnx.Graph, nx.Graph, "triangle_tail"),
            (fnx.MultiGraph, nx.MultiGraph, "triangle_tail"),
            (fnx.Graph, nx.Graph, "cycle4"),
            (fnx.MultiGraph, nx.MultiGraph, "cycle4"),
        ],
    )
    def test_matches_networkx_without_fallback(
        self, monkeypatch, fnx_cls, nx_cls, case_name
    ):
        graph = fnx_cls()
        expected = nx_cls()
        _build_chordal_graph_cliques_case(graph, case_name)
        _build_chordal_graph_cliques_case(expected, case_name)

        expected_result = [sorted(clique) for clique in nx.chordal_graph_cliques(expected)]

        monkeypatch.setattr(
            nx,
            "chordal_graph_cliques",
            lambda *call_args, **call_kwargs: (_ for _ in ()).throw(
                AssertionError(
                    "NetworkX chordal_graph_cliques fallback should not be used"
                )
            ),
        )

        actual_result = [sorted(clique) for clique in fnx.chordal_graph_cliques(graph)]
        assert actual_result == expected_result

    @pytest.mark.parametrize(
        ("fnx_cls", "nx_cls", "case_name"),
        [
            (fnx.Graph, nx.Graph, "self_loop"),
            (fnx.DiGraph, nx.DiGraph, "triangle_tail"),
        ],
    )
    def test_error_contract_matches_networkx_without_fallback(
        self, monkeypatch, fnx_cls, nx_cls, case_name
    ):
        graph = fnx_cls()
        expected = nx_cls()
        _build_chordal_graph_cliques_case(graph, case_name)
        _build_chordal_graph_cliques_case(expected, case_name)

        try:
            list(nx.chordal_graph_cliques(expected))
        except Exception as exc:
            expected_type = type(exc).__name__
            expected_message = str(exc)

        monkeypatch.setattr(
            nx,
            "chordal_graph_cliques",
            lambda *call_args, **call_kwargs: (_ for _ in ()).throw(
                AssertionError(
                    "NetworkX chordal_graph_cliques fallback should not be used"
                )
            ),
        )

        with pytest.raises(Exception) as fnx_exc:
            list(fnx.chordal_graph_cliques(graph))

        assert type(fnx_exc.value).__name__ == expected_type
        assert str(fnx_exc.value) == expected_message


# ---------------------------------------------------------------------------
# make_max_clique_graph
# ---------------------------------------------------------------------------

class TestMakeMaxCliqueGraph:
    def test_triangle(self, triangle):
        mcg = fnx.make_max_clique_graph(triangle)
        # Triangle: 1 maximal clique → 1 node
        assert mcg.number_of_nodes() == 1
        assert mcg.number_of_edges() == 0

    def test_diamond(self, diamond):
        mcg = fnx.make_max_clique_graph(diamond)
        # Diamond: 2 maximal cliques sharing nodes → 2 nodes, 1 edge
        assert mcg.number_of_nodes() == 2
        assert mcg.number_of_edges() == 1

    def test_path(self, path3):
        mcg = fnx.make_max_clique_graph(path3)
        # Path a-b-c: 2 maximal cliques {a,b} and {b,c}, sharing b → edge
        assert mcg.number_of_nodes() == 2
        assert mcg.number_of_edges() == 1


def _build_make_max_clique_graph_case(graph, case_name):
    if case_name == "triangle_tail":
        graph.add_edges_from([(0, 1), (1, 2), (2, 0), (2, 3)])
        return
    if case_name == "path3":
        graph.add_edges_from([(0, 1), (1, 2)])
        return
    if case_name == "empty":
        return
    raise ValueError(f"unknown make_max_clique_graph case {case_name}")


class TestMakeMaxCliqueGraphParity:
    @pytest.mark.parametrize(
        ("fnx_cls", "nx_cls", "case_name"),
        [
            (fnx.Graph, nx.Graph, "triangle_tail"),
            (fnx.Graph, nx.Graph, "path3"),
            (fnx.Graph, nx.Graph, "empty"),
            (fnx.MultiGraph, nx.MultiGraph, "triangle_tail"),
        ],
    )
    def test_matches_networkx_without_fallback(
        self, monkeypatch, fnx_cls, nx_cls, case_name
    ):
        graph = fnx_cls()
        expected = nx_cls()
        _build_make_max_clique_graph_case(graph, case_name)
        _build_make_max_clique_graph_case(expected, case_name)

        expected_result = nx.make_max_clique_graph(expected)

        monkeypatch.setattr(
            nx,
            "make_max_clique_graph",
            lambda *call_args, **call_kwargs: (_ for _ in ()).throw(
                AssertionError("NetworkX make_max_clique_graph fallback should not be used")
            ),
        )

        actual_result = fnx.make_max_clique_graph(graph)
        assert type(actual_result).__name__ == type(expected_result).__name__
        assert sorted(actual_result.nodes()) == sorted(expected_result.nodes())
        assert sorted(actual_result.edges()) == sorted(expected_result.edges())

    @pytest.mark.parametrize(
        ("fnx_cls", "nx_cls", "case_name"),
        [
            (fnx.DiGraph, nx.DiGraph, "triangle_tail"),
            (fnx.MultiDiGraph, nx.MultiDiGraph, "triangle_tail"),
        ],
    )
    def test_error_contract_matches_networkx_without_fallback(
        self, monkeypatch, fnx_cls, nx_cls, case_name
    ):
        graph = fnx_cls()
        expected = nx_cls()
        _build_make_max_clique_graph_case(graph, case_name)
        _build_make_max_clique_graph_case(expected, case_name)

        try:
            nx.make_max_clique_graph(expected)
        except Exception as exc:
            expected_type = type(exc).__name__
            expected_message = str(exc)

        monkeypatch.setattr(
            nx,
            "make_max_clique_graph",
            lambda *call_args, **call_kwargs: (_ for _ in ()).throw(
                AssertionError("NetworkX make_max_clique_graph fallback should not be used")
            ),
        )

        with pytest.raises(Exception) as fnx_exc:
            fnx.make_max_clique_graph(graph)

        assert type(fnx_exc.value).__name__ == expected_type
        assert str(fnx_exc.value) == expected_message


# ---------------------------------------------------------------------------
# ring_of_cliques
# ---------------------------------------------------------------------------

class TestRingOfCliques:
    def test_basic(self):
        g = fnx.ring_of_cliques(3, 3)
        assert g.number_of_nodes() == 9
        assert g.number_of_edges() == 12

    def test_two_by_two(self):
        g = fnx.ring_of_cliques(2, 2)
        assert g.number_of_nodes() == 4
        assert g.number_of_edges() == 4

    def test_connected(self):
        g = fnx.ring_of_cliques(4, 3)
        assert fnx.is_connected(g)
