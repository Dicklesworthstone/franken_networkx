"""Tests for reciprocity, kemeny_constant, wiener_index,
average_degree_connectivity, rich_club_coefficient, and s_metric."""

import math
import inspect
import networkx as nx
import pytest

import franken_networkx as fnx


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def triangle():
    G = fnx.Graph()
    G.add_edge(0, 1)
    G.add_edge(1, 2)
    G.add_edge(0, 2)
    return G


@pytest.fixture
def path4():
    G = fnx.Graph()
    G.add_edge(0, 1)
    G.add_edge(1, 2)
    G.add_edge(2, 3)
    return G


@pytest.fixture
def mutual_digraph():
    """DiGraph where all edges are reciprocated."""
    D = fnx.DiGraph()
    D.add_edge(0, 1)
    D.add_edge(1, 0)
    D.add_edge(1, 2)
    D.add_edge(2, 1)
    return D


@pytest.fixture
def one_way_digraph():
    """DiGraph with no reciprocated edges."""
    D = fnx.DiGraph()
    D.add_edge(0, 1)
    D.add_edge(1, 2)
    D.add_edge(2, 3)
    return D


# ---------------------------------------------------------------------------
# overall_reciprocity
# ---------------------------------------------------------------------------


class TestOverallReciprocity:
    def test_fully_reciprocal(self, mutual_digraph):
        r = fnx.overall_reciprocity(mutual_digraph)
        assert abs(r - 1.0) < 1e-9

    def test_no_reciprocity(self, one_way_digraph):
        r = fnx.overall_reciprocity(one_way_digraph)
        assert abs(r - 0.0) < 1e-9

    def test_partial_reciprocity(self):
        D = fnx.DiGraph()
        D.add_edge(0, 1)
        D.add_edge(1, 0)
        D.add_edge(1, 2)
        # 2 of 3 edges are reciprocated (0->1 and 1->0)
        r = fnx.overall_reciprocity(D)
        assert 0.0 < r < 1.0


# ---------------------------------------------------------------------------
# reciprocity
# ---------------------------------------------------------------------------


class TestReciprocity:
    def test_fully_reciprocal(self, mutual_digraph):
        r = fnx.reciprocity(mutual_digraph)
        # Should return a dict or float depending on implementation
        if isinstance(r, dict):
            for v in r.values():
                assert abs(v - 1.0) < 1e-9
        else:
            assert abs(r - 1.0) < 1e-9


def _build_reciprocity_case(graph, case_name):
    if case_name == "empty":
        return
    if case_name == "triangle":
        graph.add_edges_from([(0, 1), (1, 2), (2, 0)])
        return
    if case_name == "mutual_digraph":
        graph.add_edges_from([(0, 1), (1, 0), (1, 2), (2, 1)])
        return
    if case_name == "one_way_digraph":
        graph.add_edges_from([(0, 1), (1, 2), (2, 3)])
        return
    if case_name == "isolated_only":
        graph.add_node(1)
        return
    if case_name == "single_directed_edge":
        graph.add_edge(0, 1)
        return
    if case_name == "multidigraph_mutual":
        graph.add_edge(0, 1)
        graph.add_edge(1, 0)
        return
    raise ValueError(f"unknown reciprocity case {case_name}")


class TestReciprocityParity:
    def test_overall_reciprocity_backend_keyword_surface_matches_networkx(self):
        graph = fnx.DiGraph([(0, 1), (1, 0), (1, 2)])
        expected = nx.DiGraph([(0, 1), (1, 0), (1, 2)])

        assert str(inspect.signature(fnx.overall_reciprocity)) == str(
            inspect.signature(nx.overall_reciprocity)
        )

        for backend in (None, "networkx"):
            assert fnx.overall_reciprocity(graph, backend=backend) == nx.overall_reciprocity(
                expected, backend=backend
            )

        with pytest.raises(ImportError, match="'parallel' backend is not installed"):
            fnx.overall_reciprocity(graph, backend="parallel")
        with pytest.raises(ImportError, match="'parallel' backend is not installed"):
            nx.overall_reciprocity(expected, backend="parallel")

        with pytest.raises(TypeError, match="unexpected keyword argument 'backend_kwargs'"):
            fnx.overall_reciprocity(graph, backend_kwargs={"x": 1})
        with pytest.raises(TypeError, match="unexpected keyword argument 'backend_kwargs'"):
            nx.overall_reciprocity(expected, backend_kwargs={"x": 1})

    def test_reciprocity_backend_keyword_surface_matches_networkx(self):
        graph = fnx.DiGraph([(0, 1), (1, 0), (1, 2), (2, 1)])
        expected = nx.DiGraph([(0, 1), (1, 0), (1, 2), (2, 1)])

        assert str(inspect.signature(fnx.reciprocity)) == str(
            inspect.signature(nx.reciprocity)
        )

        for backend in (None, "networkx"):
            assert fnx.reciprocity(graph, backend=backend) == nx.reciprocity(
                expected, backend=backend
            )
            assert fnx.reciprocity(graph, [0, 1, 2], backend=backend) == nx.reciprocity(
                expected, [0, 1, 2], backend=backend
            )

        with pytest.raises(ImportError, match="'parallel' backend is not installed"):
            fnx.reciprocity(graph, backend="parallel")
        with pytest.raises(ImportError, match="'parallel' backend is not installed"):
            nx.reciprocity(expected, backend="parallel")

        with pytest.raises(TypeError, match="unexpected keyword argument 'backend_kwargs'"):
            fnx.reciprocity(graph, backend_kwargs={"x": 1})
        with pytest.raises(TypeError, match="unexpected keyword argument 'backend_kwargs'"):
            nx.reciprocity(expected, backend_kwargs={"x": 1})

    @pytest.mark.parametrize(
        ("function_name", "fnx_cls", "nx_cls", "case_name", "args"),
        [
            ("overall_reciprocity", fnx.Graph, nx.Graph, "triangle", ()),
            ("overall_reciprocity", fnx.DiGraph, nx.DiGraph, "mutual_digraph", ()),
            ("overall_reciprocity", fnx.DiGraph, nx.DiGraph, "one_way_digraph", ()),
            ("overall_reciprocity", fnx.MultiDiGraph, nx.MultiDiGraph, "multidigraph_mutual", ()),
            ("reciprocity", fnx.Graph, nx.Graph, "triangle", ()),
            ("reciprocity", fnx.DiGraph, nx.DiGraph, "mutual_digraph", ()),
            ("reciprocity", fnx.MultiDiGraph, nx.MultiDiGraph, "multidigraph_mutual", ()),
            ("reciprocity", fnx.DiGraph, nx.DiGraph, "mutual_digraph", (0,)),
            ("reciprocity", fnx.DiGraph, nx.DiGraph, "mutual_digraph", ([0, 1, 2],)),
            ("reciprocity", fnx.DiGraph, nx.DiGraph, "isolated_only", ([1],)),
            ("reciprocity", fnx.DiGraph, nx.DiGraph, "single_directed_edge", ([0, 2],)),
        ],
    )
    def test_matches_networkx_without_fallback(
        self, monkeypatch, function_name, fnx_cls, nx_cls, case_name, args
    ):
        graph = fnx_cls()
        expected = nx_cls()
        _build_reciprocity_case(graph, case_name)
        _build_reciprocity_case(expected, case_name)

        expected_result = getattr(nx, function_name)(expected, *args)

        monkeypatch.setattr(
            nx,
            function_name,
            lambda *call_args, **call_kwargs: (_ for _ in ()).throw(
                AssertionError(
                    f"NetworkX {function_name} fallback should not be used"
                )
            ),
        )

        actual_result = getattr(fnx, function_name)(graph, *args)
        assert actual_result == expected_result

    @pytest.mark.parametrize(
        ("function_name", "fnx_cls", "nx_cls", "case_name", "args"),
        [
            ("overall_reciprocity", fnx.Graph, nx.Graph, "empty", ()),
            ("overall_reciprocity", fnx.DiGraph, nx.DiGraph, "empty", ()),
            ("overall_reciprocity", fnx.MultiGraph, nx.MultiGraph, "empty", ()),
            ("overall_reciprocity", fnx.MultiGraph, nx.MultiGraph, "triangle", ()),
            ("reciprocity", fnx.Graph, nx.Graph, "empty", ()),
            ("reciprocity", fnx.MultiGraph, nx.MultiGraph, "triangle", ()),
            ("reciprocity", fnx.DiGraph, nx.DiGraph, "isolated_only", (1,)),
            ("reciprocity", fnx.Graph, nx.Graph, "triangle", (0,)),
            ("reciprocity", fnx.Graph, nx.Graph, "triangle", ([0, 1],)),
            ("reciprocity", fnx.DiGraph, nx.DiGraph, "single_directed_edge", (2,)),
        ],
    )
    def test_error_contract_matches_networkx_without_fallback(
        self, monkeypatch, function_name, fnx_cls, nx_cls, case_name, args
    ):
        graph = fnx_cls()
        expected = nx_cls()
        _build_reciprocity_case(graph, case_name)
        _build_reciprocity_case(expected, case_name)

        try:
            getattr(nx, function_name)(expected, *args)
        except Exception as exc:
            expected_type = type(exc).__name__
            expected_message = str(exc)

        monkeypatch.setattr(
            nx,
            function_name,
            lambda *call_args, **call_kwargs: (_ for _ in ()).throw(
                AssertionError(
                    f"NetworkX {function_name} fallback should not be used"
                )
            ),
        )

        with pytest.raises(Exception) as fnx_exc:
            getattr(fnx, function_name)(graph, *args)

        assert type(fnx_exc.value).__name__ == expected_type
        assert str(fnx_exc.value) == expected_message


# ---------------------------------------------------------------------------
# kemeny_constant
# ---------------------------------------------------------------------------


def _build_kemeny_case(graph, case_name):
    if case_name == "empty":
        return
    if case_name == "path4":
        graph.add_edges_from([(0, 1), (1, 2), (2, 3)])
        return
    if case_name == "digraph_edge":
        graph.add_edge(0, 1)
        return
    if case_name == "multigraph_edge":
        graph.add_edge(0, 1)
        return
    raise ValueError(f"unknown kemeny case {case_name}")


class TestKemenyConstantParity:
    @pytest.mark.parametrize(
        ("fnx_cls", "nx_cls", "case_name"),
        [
            (fnx.Graph, nx.Graph, "path4"),
            (fnx.MultiGraph, nx.MultiGraph, "multigraph_edge"),
        ],
    )
    def test_matches_networkx_without_fallback(
        self, monkeypatch, fnx_cls, nx_cls, case_name
    ):
        graph = fnx_cls()
        expected = nx_cls()
        _build_kemeny_case(graph, case_name)
        _build_kemeny_case(expected, case_name)

        expected_result = nx.kemeny_constant(expected)

        monkeypatch.setattr(
            nx,
            "kemeny_constant",
            lambda *call_args, **call_kwargs: (_ for _ in ()).throw(
                AssertionError(
                    "NetworkX kemeny_constant fallback should not be used"
                )
            ),
        )

        actual_result = fnx.kemeny_constant(graph)
        assert actual_result == pytest.approx(expected_result)

    @pytest.mark.parametrize(
        ("fnx_cls", "nx_cls", "case_name"),
        [
            (fnx.Graph, nx.Graph, "empty"),
            (fnx.DiGraph, nx.DiGraph, "digraph_edge"),
        ],
    )
    def test_error_contract_matches_networkx_without_fallback(
        self, monkeypatch, fnx_cls, nx_cls, case_name
    ):
        graph = fnx_cls()
        expected = nx_cls()
        _build_kemeny_case(graph, case_name)
        _build_kemeny_case(expected, case_name)

        try:
            nx.kemeny_constant(expected)
        except Exception as exc:
            expected_type = type(exc).__name__
            expected_message = str(exc)

        monkeypatch.setattr(
            nx,
            "kemeny_constant",
            lambda *call_args, **call_kwargs: (_ for _ in ()).throw(
                AssertionError(
                    "NetworkX kemeny_constant fallback should not be used"
                )
            ),
        )

        with pytest.raises(Exception) as fnx_exc:
            fnx.kemeny_constant(graph)

        assert type(fnx_exc.value).__name__ == expected_type
        assert str(fnx_exc.value) == expected_message


# ---------------------------------------------------------------------------
# wiener_index
# ---------------------------------------------------------------------------


class TestWienerIndex:
    def test_triangle(self, triangle):
        # Triangle: all pairwise distances are 1, so W = 3 * 1 = 3
        w = fnx.wiener_index(triangle)
        assert abs(w - 3.0) < 1e-9

    def test_path4(self, path4):
        # Path 0-1-2-3: distances are 1+2+3+1+2+1 = 10
        w = fnx.wiener_index(path4)
        assert abs(w - 10.0) < 1e-9

    def test_single_node(self):
        G = fnx.Graph()
        G.add_node(0)
        w = fnx.wiener_index(G)
        assert abs(w - 0.0) < 1e-9


def _build_wiener_case(graph, case_name):
    if case_name == "empty":
        return
    if case_name == "graph_edge":
        graph.add_edge(0, 1)
        return
    if case_name == "graph_with_isolate":
        graph.add_edge(0, 1)
        graph.add_node(2)
        return
    if case_name == "digraph_edge":
        graph.add_edge(0, 1)
        return
    if case_name == "digraph_mutual":
        graph.add_edge(0, 1)
        graph.add_edge(1, 0)
        return
    if case_name == "multigraph_edge":
        graph.add_edge(0, 1)
        return
    if case_name == "path3_weighted":
        graph.add_edges_from([(0, 1), (1, 2)])
        for u, v in graph.edges():
            graph[u][v]["weight"] = 2
        return
    raise ValueError(f"unknown wiener case {case_name}")


class TestWienerIndexParity:
    def test_backend_keyword_surface_matches_networkx(self):
        graph = fnx.path_graph(3)
        expected = nx.path_graph(3)

        assert str(inspect.signature(fnx.wiener_index)) == str(inspect.signature(nx.wiener_index))

        for backend in (None, "networkx"):
            assert fnx.wiener_index(graph, backend=backend) == nx.wiener_index(
                expected, backend=backend
            )

        with pytest.raises(ImportError, match="'parallel' backend is not installed"):
            fnx.wiener_index(graph, backend="parallel")
        with pytest.raises(ImportError, match="'parallel' backend is not installed"):
            nx.wiener_index(expected, backend="parallel")

        with pytest.raises(TypeError, match="unexpected keyword argument 'backend_kwargs'"):
            fnx.wiener_index(graph, backend_kwargs={"x": 1})
        with pytest.raises(TypeError, match="unexpected keyword argument 'backend_kwargs'"):
            nx.wiener_index(expected, backend_kwargs={"x": 1})

    @pytest.mark.parametrize(
        ("fnx_cls", "nx_cls", "case_name"),
        [
            (fnx.Graph, nx.Graph, "graph_edge"),
            (fnx.Graph, nx.Graph, "graph_with_isolate"),
            (fnx.DiGraph, nx.DiGraph, "digraph_edge"),
            (fnx.DiGraph, nx.DiGraph, "digraph_mutual"),
            (fnx.MultiGraph, nx.MultiGraph, "multigraph_edge"),
        ],
    )
    def test_matches_networkx_without_fallback(
        self, monkeypatch, fnx_cls, nx_cls, case_name
    ):
        graph = fnx_cls()
        expected = nx_cls()
        _build_wiener_case(graph, case_name)
        _build_wiener_case(expected, case_name)

        expected_result = nx.wiener_index(expected)

        monkeypatch.setattr(
            nx,
            "wiener_index",
            lambda *call_args, **call_kwargs: (_ for _ in ()).throw(
                AssertionError("NetworkX wiener_index fallback should not be used")
            ),
        )

        actual_result = fnx.wiener_index(graph)
        assert actual_result == expected_result

    def test_weighted_matches_networkx_without_fallback(self, monkeypatch):
        graph = fnx.Graph()
        expected = nx.Graph()
        _build_wiener_case(graph, "path3_weighted")
        _build_wiener_case(expected, "path3_weighted")

        expected_result = nx.wiener_index(expected, weight="weight")

        monkeypatch.setattr(
            nx,
            "wiener_index",
            lambda *call_args, **call_kwargs: (_ for _ in ()).throw(
                AssertionError("NetworkX wiener_index fallback should not be used")
            ),
        )

        actual_result = fnx.wiener_index(graph, weight="weight")
        assert actual_result == expected_result

    @pytest.mark.parametrize(
        ("fnx_cls", "nx_cls", "case_name"),
        [
            (fnx.Graph, nx.Graph, "empty"),
            (fnx.DiGraph, nx.DiGraph, "empty"),
        ],
    )
    def test_error_contract_matches_networkx_without_fallback(
        self, monkeypatch, fnx_cls, nx_cls, case_name
    ):
        graph = fnx_cls()
        expected = nx_cls()
        _build_wiener_case(graph, case_name)
        _build_wiener_case(expected, case_name)

        try:
            nx.wiener_index(expected)
        except Exception as exc:
            expected_type = type(exc).__name__
            expected_message = str(exc)

        monkeypatch.setattr(
            nx,
            "wiener_index",
            lambda *call_args, **call_kwargs: (_ for _ in ()).throw(
                AssertionError("NetworkX wiener_index fallback should not be used")
            ),
        )

        with pytest.raises(Exception) as fnx_exc:
            fnx.wiener_index(graph)

        assert type(fnx_exc.value).__name__ == expected_type
        assert str(fnx_exc.value) == expected_message


# ---------------------------------------------------------------------------
# closeness_vitality
# ---------------------------------------------------------------------------


def _build_closeness_vitality_case(graph, case_name):
    if case_name == "empty":
        return
    if case_name == "single_node":
        graph.add_node(0)
        return
    if case_name == "path3":
        graph.add_edges_from([(0, 1), (1, 2)])
        return
    if case_name == "path3_weighted":
        graph.add_edges_from([(0, 1), (1, 2)])
        for u, v in graph.edges():
            graph[u][v]["weight"] = 2
        return
    if case_name == "digraph_edge":
        graph.add_edge(0, 1)
        return
    if case_name == "digraph_cycle":
        graph.add_edges_from([(0, 1), (1, 2), (2, 0)])
        return
    if case_name == "multigraph_edge":
        graph.add_edge(0, 1)
        return
    raise ValueError(f"unknown closeness vitality case {case_name}")


class TestClosenessVitalityParity:
    def test_backend_keyword_surface_matches_networkx(self):
        graph = fnx.path_graph(3)
        expected = nx.path_graph(3)

        assert str(inspect.signature(fnx.closeness_vitality)) == str(
            inspect.signature(nx.closeness_vitality)
        )

        for backend in (None, "networkx"):
            assert fnx.closeness_vitality(graph, backend=backend) == nx.closeness_vitality(
                expected, backend=backend
            )

        with pytest.raises(ImportError, match="'parallel' backend is not installed"):
            fnx.closeness_vitality(graph, backend="parallel")
        with pytest.raises(ImportError, match="'parallel' backend is not installed"):
            nx.closeness_vitality(expected, backend="parallel")

        with pytest.raises(TypeError, match="unexpected keyword argument 'backend_kwargs'"):
            fnx.closeness_vitality(graph, backend_kwargs={"x": 1})
        with pytest.raises(TypeError, match="unexpected keyword argument 'backend_kwargs'"):
            nx.closeness_vitality(expected, backend_kwargs={"x": 1})

    @pytest.mark.parametrize(
        ("fnx_cls", "nx_cls", "case_name", "kwargs"),
        [
            (fnx.Graph, nx.Graph, "path3", {}),
            (fnx.Graph, nx.Graph, "path3_weighted", {"weight": "weight"}),
            (fnx.DiGraph, nx.DiGraph, "digraph_edge", {}),
            (fnx.DiGraph, nx.DiGraph, "digraph_cycle", {}),
            (fnx.MultiGraph, nx.MultiGraph, "multigraph_edge", {}),
            (fnx.Graph, nx.Graph, "path3", {"node": 99}),
        ],
    )
    def test_matches_networkx_without_fallback(
        self, monkeypatch, fnx_cls, nx_cls, case_name, kwargs
    ):
        graph = fnx_cls()
        expected = nx_cls()
        _build_closeness_vitality_case(graph, case_name)
        _build_closeness_vitality_case(expected, case_name)

        expected_result = nx.closeness_vitality(expected, **kwargs)

        monkeypatch.setattr(
            nx,
            "closeness_vitality",
            lambda *call_args, **call_kwargs: (_ for _ in ()).throw(
                AssertionError(
                    "NetworkX closeness_vitality fallback should not be used"
                )
            ),
        )

        actual_result = fnx.closeness_vitality(graph, **kwargs)
        assert actual_result == expected_result

    @pytest.mark.parametrize(
        ("fnx_cls", "nx_cls", "case_name", "kwargs"),
        [
            (fnx.Graph, nx.Graph, "empty", {}),
            (fnx.Graph, nx.Graph, "single_node", {}),
            (fnx.Graph, nx.Graph, "single_node", {"node": 0}),
        ],
    )
    def test_error_contract_matches_networkx_without_fallback(
        self, monkeypatch, fnx_cls, nx_cls, case_name, kwargs
    ):
        graph = fnx_cls()
        expected = nx_cls()
        _build_closeness_vitality_case(graph, case_name)
        _build_closeness_vitality_case(expected, case_name)

        try:
            nx.closeness_vitality(expected, **kwargs)
        except Exception as exc:
            expected_type = type(exc).__name__
            expected_message = str(exc)

        monkeypatch.setattr(
            nx,
            "closeness_vitality",
            lambda *call_args, **call_kwargs: (_ for _ in ()).throw(
                AssertionError(
                    "NetworkX closeness_vitality fallback should not be used"
                )
            ),
        )

        with pytest.raises(Exception) as fnx_exc:
            fnx.closeness_vitality(graph, **kwargs)

        assert type(fnx_exc.value).__name__ == expected_type
        assert str(fnx_exc.value) == expected_message


# ---------------------------------------------------------------------------
# structural hole metrics
# ---------------------------------------------------------------------------


def _build_structural_hole_case(graph, case_name):
    if case_name == "empty":
        return
    if case_name == "single_node":
        graph.add_node(0)
        return
    if case_name == "two_isolates":
        graph.add_nodes_from([0, 1])
        return
    if case_name == "path3":
        graph.add_edges_from([(0, 1), (1, 2)])
        return
    raise ValueError(f"unknown structural-hole case {case_name}")


class TestStructuralHoleParity:
    @pytest.mark.parametrize(
        ("function_name", "fnx_cls", "nx_cls", "case_name", "kwargs"),
        [
            ("constraint", fnx.Graph, nx.Graph, "path3", {}),
            ("constraint", fnx.Graph, nx.Graph, "path3", {"nodes": [0, 2]}),
            ("effective_size", fnx.Graph, nx.Graph, "path3", {}),
            ("effective_size", fnx.Graph, nx.Graph, "path3", {"nodes": [0, 2]}),
        ],
    )
    def test_matches_networkx_without_fallback(
        self, monkeypatch, function_name, fnx_cls, nx_cls, case_name, kwargs
    ):
        graph = fnx_cls()
        expected = nx_cls()
        _build_structural_hole_case(graph, case_name)
        _build_structural_hole_case(expected, case_name)

        expected_result = getattr(nx, function_name)(expected, **kwargs)

        monkeypatch.setattr(
            nx,
            function_name,
            lambda *call_args, **call_kwargs: (_ for _ in ()).throw(
                AssertionError(
                    f"NetworkX {function_name} fallback should not be used"
                )
            ),
        )

        actual_result = getattr(fnx, function_name)(graph, **kwargs)
        assert actual_result == expected_result

    @pytest.mark.parametrize(
        ("function_name", "fnx_cls", "nx_cls", "case_name", "kwargs"),
        [
            ("constraint", fnx.Graph, nx.Graph, "empty", {}),
            ("constraint", fnx.Graph, nx.Graph, "single_node", {}),
            ("constraint", fnx.Graph, nx.Graph, "two_isolates", {}),
            ("constraint", fnx.Graph, nx.Graph, "path3", {"nodes": [99]}),
            ("effective_size", fnx.Graph, nx.Graph, "empty", {}),
            ("effective_size", fnx.Graph, nx.Graph, "single_node", {}),
            ("effective_size", fnx.Graph, nx.Graph, "two_isolates", {}),
            ("effective_size", fnx.Graph, nx.Graph, "path3", {"nodes": [99]}),
        ],
    )
    def test_edge_contract_matches_networkx_without_fallback(
        self, monkeypatch, function_name, fnx_cls, nx_cls, case_name, kwargs
    ):
        graph = fnx_cls()
        expected = nx_cls()
        _build_structural_hole_case(graph, case_name)
        _build_structural_hole_case(expected, case_name)

        try:
            expected_result = getattr(nx, function_name)(expected, **kwargs)
        except Exception as exc:
            expected_type = type(exc).__name__
            expected_message = str(exc)
        else:
            expected_type = None
            expected_message = None

        monkeypatch.setattr(
            nx,
            function_name,
            lambda *call_args, **call_kwargs: (_ for _ in ()).throw(
                AssertionError(
                    f"NetworkX {function_name} fallback should not be used"
                )
            ),
        )

        if expected_type is None:
            actual_result = getattr(fnx, function_name)(graph, **kwargs)
            assert actual_result.keys() == expected_result.keys()
            for node in expected_result:
                if math.isnan(expected_result[node]):
                    assert math.isnan(actual_result[node])
                else:
                    assert actual_result[node] == expected_result[node]
            return

        with pytest.raises(Exception) as fnx_exc:
            getattr(fnx, function_name)(graph, **kwargs)

        assert type(fnx_exc.value).__name__ == expected_type
        assert str(fnx_exc.value) == expected_message


# ---------------------------------------------------------------------------
# graph indices
# ---------------------------------------------------------------------------


def _build_graph_index_case(graph, case_name):
    if case_name == "empty":
        return
    if case_name == "single_node":
        graph.add_node(0)
        return
    if case_name == "graph_edge":
        graph.add_edge(0, 1)
        return
    if case_name == "graph_with_isolate":
        graph.add_edge(0, 1)
        graph.add_node(2)
        return
    if case_name == "digraph_edge":
        graph.add_edge(0, 1)
        return
    if case_name == "multigraph_edge":
        graph.add_edge(0, 1)
        return
    if case_name == "weighted_path3":
        graph.add_edges_from([(0, 1), (1, 2)])
        for u, v in graph.edges():
            graph[u][v]["weight"] = 2
        return
    raise ValueError(f"unknown graph index case {case_name}")


class TestGraphIndexParity:
    @pytest.mark.parametrize("function_name", ["schultz_index", "gutman_index"])
    def test_backend_keyword_surface_matches_networkx(self, function_name):
        graph = fnx.path_graph(3)
        expected = nx.path_graph(3)

        assert str(inspect.signature(getattr(fnx, function_name))) == str(
            inspect.signature(getattr(nx, function_name))
        )

        for backend in (None, "networkx"):
            assert getattr(fnx, function_name)(graph, backend=backend) == getattr(
                nx, function_name
            )(expected, backend=backend)

        with pytest.raises(ImportError, match="'parallel' backend is not installed"):
            getattr(fnx, function_name)(graph, backend="parallel")
        with pytest.raises(ImportError, match="'parallel' backend is not installed"):
            getattr(nx, function_name)(expected, backend="parallel")

        with pytest.raises(TypeError, match="unexpected keyword argument 'backend_kwargs'"):
            getattr(fnx, function_name)(graph, backend_kwargs={"x": 1})
        with pytest.raises(TypeError, match="unexpected keyword argument 'backend_kwargs'"):
            getattr(nx, function_name)(expected, backend_kwargs={"x": 1})

    @pytest.mark.parametrize(
        ("function_name", "fnx_cls", "nx_cls", "case_name", "kwargs"),
        [
            ("schultz_index", fnx.Graph, nx.Graph, "single_node", {}),
            ("schultz_index", fnx.Graph, nx.Graph, "graph_edge", {}),
            ("schultz_index", fnx.Graph, nx.Graph, "graph_with_isolate", {}),
            ("schultz_index", fnx.Graph, nx.Graph, "weighted_path3", {"weight": "weight"}),
            ("gutman_index", fnx.Graph, nx.Graph, "single_node", {}),
            ("gutman_index", fnx.Graph, nx.Graph, "graph_edge", {}),
            ("gutman_index", fnx.Graph, nx.Graph, "graph_with_isolate", {}),
            ("gutman_index", fnx.Graph, nx.Graph, "weighted_path3", {"weight": "weight"}),
        ],
    )
    def test_matches_networkx_without_fallback(
        self, monkeypatch, function_name, fnx_cls, nx_cls, case_name, kwargs
    ):
        graph = fnx_cls()
        expected = nx_cls()
        _build_graph_index_case(graph, case_name)
        _build_graph_index_case(expected, case_name)

        expected_result = getattr(nx, function_name)(expected, **kwargs)

        monkeypatch.setattr(
            nx,
            function_name,
            lambda *call_args, **call_kwargs: (_ for _ in ()).throw(
                AssertionError(
                    f"NetworkX {function_name} fallback should not be used"
                )
            ),
        )

        actual_result = getattr(fnx, function_name)(graph, **kwargs)
        assert actual_result == expected_result

    @pytest.mark.parametrize(
        ("function_name", "fnx_cls", "nx_cls", "case_name"),
        [
            ("schultz_index", fnx.Graph, nx.Graph, "empty"),
            ("schultz_index", fnx.DiGraph, nx.DiGraph, "digraph_edge"),
            ("schultz_index", fnx.MultiGraph, nx.MultiGraph, "multigraph_edge"),
            ("gutman_index", fnx.Graph, nx.Graph, "empty"),
            ("gutman_index", fnx.DiGraph, nx.DiGraph, "digraph_edge"),
            ("gutman_index", fnx.MultiGraph, nx.MultiGraph, "multigraph_edge"),
        ],
    )
    def test_error_contract_matches_networkx_without_fallback(
        self, monkeypatch, function_name, fnx_cls, nx_cls, case_name
    ):
        graph = fnx_cls()
        expected = nx_cls()
        _build_graph_index_case(graph, case_name)
        _build_graph_index_case(expected, case_name)

        try:
            getattr(nx, function_name)(expected)
        except Exception as exc:
            expected_type = type(exc).__name__
            expected_message = str(exc)

        monkeypatch.setattr(
            nx,
            function_name,
            lambda *call_args, **call_kwargs: (_ for _ in ()).throw(
                AssertionError(
                    f"NetworkX {function_name} fallback should not be used"
                )
            ),
        )

        with pytest.raises(Exception) as fnx_exc:
            getattr(fnx, function_name)(graph)

        assert type(fnx_exc.value).__name__ == expected_type
        assert str(fnx_exc.value) == expected_message


# ---------------------------------------------------------------------------
# sigma
# ---------------------------------------------------------------------------


def _build_sigma_case(graph, case_name):
    if case_name == "empty":
        return
    if case_name == "path4":
        graph.add_edges_from([(0, 1), (1, 2), (2, 3)])
        return
    if case_name == "cycle4":
        graph.add_edges_from([(0, 1), (1, 2), (2, 3), (3, 0)])
        return
    if case_name == "complete4":
        graph.add_edges_from(
            [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)]
        )
        return
    if case_name == "disconnected4":
        graph.add_edges_from([(0, 1), (2, 3)])
        return
    if case_name == "digraph_edge":
        graph.add_edge(0, 1)
        return
    if case_name == "multigraph_edge":
        graph.add_edge(0, 1)
        return
    raise ValueError(f"unknown sigma case {case_name}")


class TestSigmaParity:
    @pytest.mark.parametrize(
        ("fnx_cls", "nx_cls", "case_name"),
        [
            (fnx.Graph, nx.Graph, "path4"),
            (fnx.Graph, nx.Graph, "cycle4"),
            (fnx.Graph, nx.Graph, "complete4"),
        ],
    )
    def test_matches_networkx_without_fallback(
        self, monkeypatch, fnx_cls, nx_cls, case_name
    ):
        graph = fnx_cls()
        expected = nx_cls()
        _build_sigma_case(graph, case_name)
        _build_sigma_case(expected, case_name)

        expected_result = nx.sigma(expected, niter=2, nrand=2, seed=123)

        monkeypatch.setattr(
            nx,
            "sigma",
            lambda *call_args, **call_kwargs: (_ for _ in ()).throw(
                AssertionError("NetworkX sigma fallback should not be used")
            ),
        )

        actual_result = fnx.sigma(graph, niter=2, nrand=2, seed=123)
        if math.isnan(expected_result):
            assert math.isnan(actual_result)
        else:
            assert actual_result == expected_result

    @pytest.mark.parametrize(
        ("fnx_cls", "nx_cls", "case_name"),
        [
            (fnx.Graph, nx.Graph, "empty"),
            (fnx.Graph, nx.Graph, "disconnected4"),
            (fnx.DiGraph, nx.DiGraph, "digraph_edge"),
            (fnx.MultiGraph, nx.MultiGraph, "multigraph_edge"),
        ],
    )
    def test_error_contract_matches_networkx_without_fallback(
        self, monkeypatch, fnx_cls, nx_cls, case_name
    ):
        graph = fnx_cls()
        expected = nx_cls()
        _build_sigma_case(graph, case_name)
        _build_sigma_case(expected, case_name)

        try:
            nx.sigma(expected, niter=2, nrand=2, seed=123)
        except Exception as exc:
            expected_type = type(exc).__name__
            expected_message = str(exc)

        monkeypatch.setattr(
            nx,
            "sigma",
            lambda *call_args, **call_kwargs: (_ for _ in ()).throw(
                AssertionError("NetworkX sigma fallback should not be used")
            ),
        )

        with pytest.raises(Exception) as fnx_exc:
            fnx.sigma(graph, niter=2, nrand=2, seed=123)

        assert type(fnx_exc.value).__name__ == expected_type
        assert str(fnx_exc.value) == expected_message


# ---------------------------------------------------------------------------
# omega
# ---------------------------------------------------------------------------


def _build_omega_case(graph, case_name):
    if case_name == "empty":
        return
    if case_name == "path3":
        graph.add_edges_from([(0, 1), (1, 2)])
        return
    if case_name == "path4":
        graph.add_edges_from([(0, 1), (1, 2), (2, 3)])
        return
    if case_name == "cycle4":
        graph.add_edges_from([(0, 1), (1, 2), (2, 3), (3, 0)])
        return
    if case_name == "complete4":
        graph.add_edges_from(
            [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)]
        )
        return
    if case_name == "disconnected4":
        graph.add_edges_from([(0, 1), (2, 3)])
        return
    if case_name == "digraph_edge":
        graph.add_edge(0, 1)
        return
    if case_name == "multigraph_edge":
        graph.add_edge(0, 1)
        return
    raise ValueError(f"unknown omega case {case_name}")


class TestOmegaParity:
    @pytest.mark.parametrize(
        ("fnx_cls", "nx_cls", "case_name"),
        [
            (fnx.Graph, nx.Graph, "complete4"),
        ],
    )
    def test_matches_networkx_without_fallback(
        self, monkeypatch, fnx_cls, nx_cls, case_name
    ):
        graph = fnx_cls()
        expected = nx_cls()
        _build_omega_case(graph, case_name)
        _build_omega_case(expected, case_name)

        expected_result = nx.omega(expected, niter=2, nrand=2, seed=123)

        monkeypatch.setattr(
            nx,
            "omega",
            lambda *call_args, **call_kwargs: (_ for _ in ()).throw(
                AssertionError("NetworkX omega fallback should not be used")
            ),
        )

        actual_result = fnx.omega(graph, niter=2, nrand=2, seed=123)
        assert actual_result == expected_result

    @pytest.mark.parametrize(
        ("fnx_cls", "nx_cls", "case_name"),
        [
            (fnx.Graph, nx.Graph, "empty"),
            (fnx.Graph, nx.Graph, "path3"),
            (fnx.Graph, nx.Graph, "path4"),
            (fnx.Graph, nx.Graph, "cycle4"),
            (fnx.Graph, nx.Graph, "disconnected4"),
            (fnx.DiGraph, nx.DiGraph, "digraph_edge"),
            (fnx.MultiGraph, nx.MultiGraph, "multigraph_edge"),
        ],
    )
    def test_error_contract_matches_networkx_without_fallback(
        self, monkeypatch, fnx_cls, nx_cls, case_name
    ):
        graph = fnx_cls()
        expected = nx_cls()
        _build_omega_case(graph, case_name)
        _build_omega_case(expected, case_name)

        try:
            nx.omega(expected, niter=2, nrand=2, seed=123)
        except Exception as exc:
            expected_type = type(exc).__name__
            expected_message = str(exc)

        monkeypatch.setattr(
            nx,
            "omega",
            lambda *call_args, **call_kwargs: (_ for _ in ()).throw(
                AssertionError("NetworkX omega fallback should not be used")
            ),
        )

        with pytest.raises(Exception) as fnx_exc:
            fnx.omega(graph, niter=2, nrand=2, seed=123)

        assert type(fnx_exc.value).__name__ == expected_type
        assert str(fnx_exc.value) == expected_message


# ---------------------------------------------------------------------------
# number_of_walks
# ---------------------------------------------------------------------------


def _build_number_of_walks_case(graph, case_name):
    if case_name == "empty":
        return
    if case_name == "path2":
        graph.add_edge(0, 1)
        return
    if case_name == "path3":
        graph.add_edges_from([(0, 1), (1, 2)])
        return
    if case_name == "digraph_path3":
        graph.add_edges_from([(0, 1), (1, 2)])
        return
    raise ValueError(f"unknown number_of_walks case {case_name}")


class TestNumberOfWalksParity:
    def test_backend_keyword_surface_matches_networkx(self):
        graph = fnx.path_graph(3)
        expected = nx.path_graph(3)

        assert str(inspect.signature(fnx.number_of_walks)) == str(
            inspect.signature(nx.number_of_walks)
        )

        for backend in (None, "networkx"):
            assert fnx.number_of_walks(graph, 2, backend=backend) == nx.number_of_walks(
                expected, 2, backend=backend
            )

        with pytest.raises(ImportError, match="'parallel' backend is not installed"):
            fnx.number_of_walks(graph, 2, backend="parallel")
        with pytest.raises(ImportError, match="'parallel' backend is not installed"):
            nx.number_of_walks(expected, 2, backend="parallel")

        with pytest.raises(TypeError, match="unexpected keyword argument 'backend_kwargs'"):
            fnx.number_of_walks(graph, 2, backend_kwargs={"x": 1})
        with pytest.raises(TypeError, match="unexpected keyword argument 'backend_kwargs'"):
            nx.number_of_walks(expected, 2, backend_kwargs={"x": 1})

    @pytest.mark.parametrize(
        ("fnx_cls", "nx_cls", "case_name", "walk_length"),
        [
            (fnx.Graph, nx.Graph, "path2", 0),
            (fnx.Graph, nx.Graph, "path3", 2),
            (fnx.DiGraph, nx.DiGraph, "digraph_path3", 2),
            (fnx.Graph, nx.Graph, "path2", True),
        ],
    )
    def test_matches_networkx_without_fallback(
        self, monkeypatch, fnx_cls, nx_cls, case_name, walk_length
    ):
        graph = fnx_cls()
        expected = nx_cls()
        _build_number_of_walks_case(graph, case_name)
        _build_number_of_walks_case(expected, case_name)

        expected_result = nx.number_of_walks(expected, walk_length)

        monkeypatch.setattr(
            nx,
            "number_of_walks",
            lambda *call_args, **call_kwargs: (_ for _ in ()).throw(
                AssertionError(
                    "NetworkX number_of_walks fallback should not be used"
                )
            ),
        )

        actual_result = fnx.number_of_walks(graph, walk_length)
        assert actual_result == expected_result

    @pytest.mark.parametrize(
        ("fnx_cls", "nx_cls", "case_name", "walk_length"),
        [
            (fnx.Graph, nx.Graph, "empty", 1),
            (fnx.Graph, nx.Graph, "path3", -1),
            (fnx.Graph, nx.Graph, "path3", 1.5),
            (fnx.Graph, nx.Graph, "path3", "1"),
            (fnx.Graph, nx.Graph, "path3", None),
        ],
    )
    def test_error_contract_matches_networkx_without_fallback(
        self, monkeypatch, fnx_cls, nx_cls, case_name, walk_length
    ):
        graph = fnx_cls()
        expected = nx_cls()
        _build_number_of_walks_case(graph, case_name)
        _build_number_of_walks_case(expected, case_name)

        try:
            nx.number_of_walks(expected, walk_length)
        except Exception as exc:
            expected_type = type(exc).__name__
            expected_message = str(exc)

        monkeypatch.setattr(
            nx,
            "number_of_walks",
            lambda *call_args, **call_kwargs: (_ for _ in ()).throw(
                AssertionError(
                    "NetworkX number_of_walks fallback should not be used"
                )
            ),
        )

        with pytest.raises(Exception) as fnx_exc:
            fnx.number_of_walks(graph, walk_length)

        assert type(fnx_exc.value).__name__ == expected_type
        assert str(fnx_exc.value) == expected_message


# ---------------------------------------------------------------------------
# average_degree_connectivity
# ---------------------------------------------------------------------------


class TestAverageDegreeConnectivity:
    def test_triangle(self, triangle):
        adc = fnx.average_degree_connectivity(triangle)
        # All nodes have degree 2, so adc[2] should be 2.0
        assert isinstance(adc, dict)
        assert 2 in adc
        assert abs(adc[2] - 2.0) < 1e-9

    def test_star(self):
        G = fnx.Graph()
        for i in range(1, 5):
            G.add_edge(0, i)
        adc = fnx.average_degree_connectivity(G)
        assert isinstance(adc, dict)
        # Leaves (degree 1) connect to hub (degree 4)
        assert 1 in adc
        assert abs(adc[1] - 4.0) < 1e-9


def _build_average_degree_connectivity_case(graph, case_name):
    if case_name == "empty":
        return
    if case_name == "path4":
        graph.add_edges_from([(0, 1), (1, 2), (2, 3)])
        return
    if case_name == "digraph":
        graph.add_edges_from([(0, 1), (1, 2)])
        return
    if case_name == "multigraph_parallel":
        graph.add_edge(0, 1)
        graph.add_edge(0, 1)
        return
    if case_name == "weighted_path3":
        graph.add_edge(0, 1, weight=2)
        graph.add_edge(1, 2, weight=4)
        return
    raise ValueError(f"unknown average_degree_connectivity case {case_name}")


class TestAverageDegreeConnectivityParity:
    def test_backend_keyword_surface_matches_networkx(self):
        graph = fnx.path_graph(4)
        expected = nx.path_graph(4)

        assert str(inspect.signature(fnx.average_degree_connectivity)) == str(
            inspect.signature(nx.average_degree_connectivity)
        )

        for backend in (None, "networkx"):
            assert fnx.average_degree_connectivity(graph, backend=backend) == (
                nx.average_degree_connectivity(expected, backend=backend)
            )

        with pytest.raises(ImportError, match="'parallel' backend is not installed"):
            fnx.average_degree_connectivity(graph, backend="parallel")
        with pytest.raises(ImportError, match="'parallel' backend is not installed"):
            nx.average_degree_connectivity(expected, backend="parallel")

        with pytest.raises(TypeError, match="unexpected keyword argument 'backend_kwargs'"):
            fnx.average_degree_connectivity(graph, backend_kwargs={"x": 1})
        with pytest.raises(TypeError, match="unexpected keyword argument 'backend_kwargs'"):
            nx.average_degree_connectivity(expected, backend_kwargs={"x": 1})

    @pytest.mark.parametrize(
        ("fnx_cls", "nx_cls", "case_name", "kwargs"),
        [
            (fnx.Graph, nx.Graph, "empty", {}),
            (fnx.Graph, nx.Graph, "path4", {}),
            (fnx.Graph, nx.Graph, "path4", {"nodes": 1}),
            (fnx.Graph, nx.Graph, "path4", {"nodes": [1, 2]}),
            (fnx.Graph, nx.Graph, "weighted_path3", {"weight": "weight"}),
            (fnx.DiGraph, nx.DiGraph, "digraph", {}),
            (
                fnx.DiGraph,
                nx.DiGraph,
                "digraph",
                {"source": "out", "target": "in"},
            ),
            (fnx.MultiGraph, nx.MultiGraph, "multigraph_parallel", {}),
        ],
    )
    def test_matches_networkx_without_fallback(
        self, monkeypatch, fnx_cls, nx_cls, case_name, kwargs
    ):
        graph = fnx_cls()
        expected = nx_cls()
        _build_average_degree_connectivity_case(graph, case_name)
        _build_average_degree_connectivity_case(expected, case_name)

        expected_result = nx.average_degree_connectivity(expected, **kwargs)

        monkeypatch.setattr(
            nx,
            "average_degree_connectivity",
            lambda *call_args, **call_kwargs: (_ for _ in ()).throw(
                AssertionError(
                    "NetworkX average_degree_connectivity fallback should not be used"
                )
            ),
        )

        actual_result = fnx.average_degree_connectivity(graph, **kwargs)
        assert actual_result == expected_result

    @pytest.mark.parametrize(
        ("fnx_cls", "nx_cls", "case_name", "kwargs"),
        [
            (fnx.Graph, nx.Graph, "path4", {"source": "out"}),
            (fnx.DiGraph, nx.DiGraph, "digraph", {"source": "bad"}),
            (fnx.DiGraph, nx.DiGraph, "digraph", {"target": "bad"}),
        ],
    )
    def test_error_contract_matches_networkx_without_fallback(
        self, monkeypatch, fnx_cls, nx_cls, case_name, kwargs
    ):
        graph = fnx_cls()
        expected = nx_cls()
        _build_average_degree_connectivity_case(graph, case_name)
        _build_average_degree_connectivity_case(expected, case_name)

        try:
            nx.average_degree_connectivity(expected, **kwargs)
        except Exception as exc:
            expected_type = type(exc).__name__
            expected_message = str(exc)

        monkeypatch.setattr(
            nx,
            "average_degree_connectivity",
            lambda *call_args, **call_kwargs: (_ for _ in ()).throw(
                AssertionError(
                    "NetworkX average_degree_connectivity fallback should not be used"
                )
            ),
        )

        with pytest.raises(Exception) as fnx_exc:
            fnx.average_degree_connectivity(graph, **kwargs)

        assert type(fnx_exc.value).__name__ == expected_type
        assert str(fnx_exc.value) == expected_message


# ---------------------------------------------------------------------------
# cut / expansion helpers
# ---------------------------------------------------------------------------


def _build_cut_metric_case(graph, case_name):
    if case_name == "empty":
        return
    if case_name == "path4":
        graph.add_edges_from([(0, 1), (1, 2), (2, 3)])
        return
    if case_name == "weighted_path4":
        graph.add_edge(0, 1, weight=2)
        graph.add_edge(1, 2, weight=4)
        graph.add_edge(2, 3, weight=8)
        return
    if case_name == "digraph":
        graph.add_edges_from([(0, 1), (1, 2)])
        return
    if case_name == "multigraph_parallel":
        graph.add_edge(0, 1)
        graph.add_edge(0, 1)
        return
    raise ValueError(f"unknown cut metric case {case_name}")


class TestCutExpansionParity:
    @pytest.mark.parametrize(
        ("function_name", "fnx_cls", "nx_cls", "case_name", "kwargs"),
        [
            ("volume", fnx.Graph, nx.Graph, "empty", {"S": []}),
            ("volume", fnx.Graph, nx.Graph, "path4", {"S": [0, 1]}),
            ("volume", fnx.Graph, nx.Graph, "weighted_path4", {"S": [0, 1], "weight": "weight"}),
            ("volume", fnx.MultiGraph, nx.MultiGraph, "multigraph_parallel", {"S": [0, 1]}),
            ("edge_expansion", fnx.Graph, nx.Graph, "path4", {"S": [0, 1]}),
            ("mixing_expansion", fnx.Graph, nx.Graph, "path4", {"S": [0, 1]}),
            ("node_expansion", fnx.Graph, nx.Graph, "path4", {"S": [0, 1]}),
            ("node_expansion", fnx.DiGraph, nx.DiGraph, "digraph", {"S": [0, 1]}),
            ("boundary_expansion", fnx.Graph, nx.Graph, "path4", {"S": [0, 1]}),
            ("conductance", fnx.Graph, nx.Graph, "path4", {"S": [0, 1]}),
            ("conductance", fnx.Graph, nx.Graph, "weighted_path4", {"S": [0, 1], "weight": "weight"}),
        ],
    )
    def test_matches_networkx_without_fallback(
        self, monkeypatch, function_name, fnx_cls, nx_cls, case_name, kwargs
    ):
        graph = fnx_cls()
        expected = nx_cls()
        _build_cut_metric_case(graph, case_name)
        _build_cut_metric_case(expected, case_name)

        expected_result = getattr(nx, function_name)(expected, **kwargs)

        monkeypatch.setattr(
            nx,
            function_name,
            lambda *call_args, **call_kwargs: (_ for _ in ()).throw(
                AssertionError(
                    f"NetworkX {function_name} fallback should not be used"
                )
            ),
        )

        actual_result = getattr(fnx, function_name)(graph, **kwargs)
        assert actual_result == expected_result

    @pytest.mark.parametrize(
        ("function_name", "fnx_cls", "nx_cls", "case_name", "kwargs"),
        [
            ("edge_expansion", fnx.Graph, nx.Graph, "path4", {"S": []}),
            ("node_expansion", fnx.Graph, nx.Graph, "path4", {"S": []}),
            ("boundary_expansion", fnx.Graph, nx.Graph, "path4", {"S": []}),
            ("conductance", fnx.Graph, nx.Graph, "path4", {"S": []}),
        ],
    )
    def test_error_contract_matches_networkx_without_fallback(
        self, monkeypatch, function_name, fnx_cls, nx_cls, case_name, kwargs
    ):
        graph = fnx_cls()
        expected = nx_cls()
        _build_cut_metric_case(graph, case_name)
        _build_cut_metric_case(expected, case_name)

        try:
            getattr(nx, function_name)(expected, **kwargs)
        except Exception as exc:
            expected_type = type(exc).__name__
            expected_message = str(exc)

        monkeypatch.setattr(
            nx,
            function_name,
            lambda *call_args, **call_kwargs: (_ for _ in ()).throw(
                AssertionError(
                    f"NetworkX {function_name} fallback should not be used"
                )
            ),
        )

        with pytest.raises(Exception) as fnx_exc:
            getattr(fnx, function_name)(graph, **kwargs)

        assert type(fnx_exc.value).__name__ == expected_type
        assert str(fnx_exc.value) == expected_message


# ---------------------------------------------------------------------------
# rich_club_coefficient
# ---------------------------------------------------------------------------


class TestRichClubCoefficient:
    def test_complete_graph(self):
        G = fnx.complete_graph(5)
        rcc = fnx.rich_club_coefficient(G, normalized=False)
        assert isinstance(rcc, dict)
        # Rich club coefficients are between 0 and 1
        for k, v in rcc.items():
            assert 0.0 <= v <= 1.0 + 1e-9

    def test_returns_dict(self, triangle):
        rcc = fnx.rich_club_coefficient(triangle, normalized=False)
        assert isinstance(rcc, dict)


# ---------------------------------------------------------------------------
# rich_club_coefficient parity
# ---------------------------------------------------------------------------


def _build_rich_club_case(graph, case_name):
    if case_name == "empty":
        return
    if case_name == "path4":
        graph.add_edges_from([(0, 1), (1, 2), (2, 3)])
        return
    if case_name == "cycle4":
        graph.add_edges_from([(0, 1), (1, 2), (2, 3), (3, 0)])
        return
    if case_name == "complete5":
        graph.add_edges_from(
            [
                (0, 1),
                (0, 2),
                (0, 3),
                (0, 4),
                (1, 2),
                (1, 3),
                (1, 4),
                (2, 3),
                (2, 4),
                (3, 4),
            ]
        )
        return
    if case_name == "digraph":
        graph.add_edges_from([(0, 1), (1, 2)])
        return
    if case_name == "multigraph":
        graph.add_edge(0, 1)
        graph.add_edge(0, 1)
        return
    if case_name == "selfloop":
        graph.add_edge(0, 0)
        graph.add_edge(0, 1)
        graph.add_edge(1, 2)
        graph.add_edge(2, 3)
        return
    raise ValueError(f"unknown rich-club case {case_name}")


class TestRichClubCoefficientParity:
    def test_backend_keyword_surface_matches_networkx(self):
        graph = fnx.path_graph(4)
        expected = nx.path_graph(4)

        assert str(inspect.signature(fnx.rich_club_coefficient)) == str(
            inspect.signature(nx.rich_club_coefficient)
        )

        for backend in (None, "networkx"):
            assert fnx.rich_club_coefficient(
                graph, normalized=False, backend=backend
            ) == nx.rich_club_coefficient(expected, normalized=False, backend=backend)

        with pytest.raises(ImportError, match="'parallel' backend is not installed"):
            fnx.rich_club_coefficient(graph, normalized=False, backend="parallel")
        with pytest.raises(ImportError, match="'parallel' backend is not installed"):
            nx.rich_club_coefficient(expected, normalized=False, backend="parallel")

        with pytest.raises(TypeError, match="unexpected keyword argument 'backend_kwargs'"):
            fnx.rich_club_coefficient(
                graph, normalized=False, backend_kwargs={"x": 1}
            )
        with pytest.raises(TypeError, match="unexpected keyword argument 'backend_kwargs'"):
            nx.rich_club_coefficient(
                expected, normalized=False, backend_kwargs={"x": 1}
            )

    @pytest.mark.parametrize(
        ("fnx_cls", "nx_cls", "case_name", "kwargs"),
        [
            (fnx.Graph, nx.Graph, "empty", {"normalized": False}),
            (fnx.Graph, nx.Graph, "path4", {"normalized": False}),
            (fnx.Graph, nx.Graph, "cycle4", {"normalized": False}),
            (fnx.Graph, nx.Graph, "path4", {"normalized": True, "Q": 2, "seed": 123}),
            (fnx.Graph, nx.Graph, "cycle4", {"normalized": True, "Q": 2, "seed": 123}),
        ],
    )
    def test_matches_networkx_without_fallback(
        self, monkeypatch, fnx_cls, nx_cls, case_name, kwargs
    ):
        graph = fnx_cls()
        expected = nx_cls()
        _build_rich_club_case(graph, case_name)
        _build_rich_club_case(expected, case_name)

        expected_result = nx.rich_club_coefficient(expected, **kwargs)

        monkeypatch.setattr(
            nx,
            "rich_club_coefficient",
            lambda *call_args, **call_kwargs: (_ for _ in ()).throw(
                AssertionError(
                    "NetworkX rich_club_coefficient fallback should not be used"
                )
            ),
        )

        actual_result = fnx.rich_club_coefficient(graph, **kwargs)
        assert actual_result == expected_result

    @pytest.mark.parametrize(
        ("fnx_cls", "nx_cls", "case_name", "kwargs"),
        [
            (fnx.DiGraph, nx.DiGraph, "digraph", {"normalized": False}),
            (fnx.MultiGraph, nx.MultiGraph, "multigraph", {"normalized": False}),
            (fnx.Graph, nx.Graph, "selfloop", {"normalized": False}),
            (fnx.Graph, nx.Graph, "empty", {"normalized": True, "Q": 2, "seed": 123}),
            (fnx.Graph, nx.Graph, "complete5", {"normalized": True, "Q": 2, "seed": 123}),
        ],
    )
    def test_error_contract_matches_networkx_without_fallback(
        self, monkeypatch, fnx_cls, nx_cls, case_name, kwargs
    ):
        graph = fnx_cls()
        expected = nx_cls()
        _build_rich_club_case(graph, case_name)
        _build_rich_club_case(expected, case_name)

        try:
            nx.rich_club_coefficient(expected, **kwargs)
        except Exception as exc:
            expected_type = type(exc).__name__
            expected_message = str(exc)

        monkeypatch.setattr(
            nx,
            "rich_club_coefficient",
            lambda *call_args, **call_kwargs: (_ for _ in ()).throw(
                AssertionError(
                    "NetworkX rich_club_coefficient fallback should not be used"
                )
            ),
        )

        with pytest.raises(Exception) as fnx_exc:
            fnx.rich_club_coefficient(graph, **kwargs)

        assert type(fnx_exc.value).__name__ == expected_type
        assert str(fnx_exc.value) == expected_message


# ---------------------------------------------------------------------------
# s_metric
# ---------------------------------------------------------------------------


class TestSMetric:
    def test_triangle(self, triangle):
        s = fnx.s_metric(triangle)
        # s_metric = sum(d(u)*d(v)) for all edges
        # Triangle: all degrees are 2, so s = 3 * (2*2) = 12
        assert abs(s - 12.0) < 1e-9

    def test_star(self):
        G = fnx.Graph()
        for i in range(1, 5):
            G.add_edge(0, i)
        s = fnx.s_metric(G)
        # Hub degree 4, leaves degree 1
        # s = 4 * (4*1) = 16
        assert abs(s - 16.0) < 1e-9

    def test_single_edge(self):
        G = fnx.Graph()
        G.add_edge(0, 1)
        s = fnx.s_metric(G)
        # deg(0)=1, deg(1)=1 => s = 1*1 = 1
        assert abs(s - 1.0) < 1e-9


def _build_s_metric_case(graph, case_name):
    if case_name == "empty":
        return
    if case_name == "single_edge":
        graph.add_edge(0, 1)
        return
    if case_name == "single_node_selfloop":
        graph.add_edge(0, 0)
        return
    if case_name == "path3":
        graph.add_edges_from([(0, 1), (1, 2)])
        return
    if case_name == "multigraph_parallel":
        graph.add_edge(0, 1)
        graph.add_edge(0, 1)
        return
    if case_name == "digraph":
        graph.add_edge(0, 1)
        return
    raise ValueError(f"unknown s_metric case {case_name}")


class TestSMetricParity:
    def test_backend_keyword_surface_matches_networkx(self):
        graph = fnx.path_graph(3)
        expected = nx.path_graph(3)

        assert str(inspect.signature(fnx.s_metric)) == str(inspect.signature(nx.s_metric))

        for backend in (None, "networkx"):
            assert fnx.s_metric(graph, backend=backend) == nx.s_metric(expected, backend=backend)

        with pytest.raises(ImportError, match="'parallel' backend is not installed"):
            fnx.s_metric(graph, backend="parallel")
        with pytest.raises(ImportError, match="'parallel' backend is not installed"):
            nx.s_metric(expected, backend="parallel")

        with pytest.raises(TypeError, match="unexpected keyword argument 'backend_kwargs'"):
            fnx.s_metric(graph, backend_kwargs={"x": 1})
        with pytest.raises(TypeError, match="unexpected keyword argument 'backend_kwargs'"):
            nx.s_metric(expected, backend_kwargs={"x": 1})

    @pytest.mark.parametrize(
        ("fnx_cls", "nx_cls", "case_name"),
        [
            (fnx.Graph, nx.Graph, "empty"),
            (fnx.Graph, nx.Graph, "single_edge"),
            (fnx.Graph, nx.Graph, "single_node_selfloop"),
            (fnx.Graph, nx.Graph, "path3"),
            (fnx.MultiGraph, nx.MultiGraph, "multigraph_parallel"),
            (fnx.DiGraph, nx.DiGraph, "digraph"),
        ],
    )
    def test_matches_networkx_without_fallback(
        self, monkeypatch, fnx_cls, nx_cls, case_name
    ):
        graph = fnx_cls()
        expected = nx_cls()
        _build_s_metric_case(graph, case_name)
        _build_s_metric_case(expected, case_name)

        expected_result = nx.s_metric(expected)

        monkeypatch.setattr(
            nx,
            "s_metric",
            lambda *call_args, **call_kwargs: (_ for _ in ()).throw(
                AssertionError("NetworkX s_metric fallback should not be used")
            ),
        )

        actual_result = fnx.s_metric(graph)
        assert actual_result == expected_result
