"""Conformance tests: clustering algorithms — fnx vs nx oracle."""

import pytest
from conftest import assert_dicts_close


@pytest.mark.conformance
class TestClustering:
    def test_clustering(self, fnx, nx, triangle_graph):
        G_fnx, G_nx = triangle_graph
        assert_dicts_close(fnx.clustering(G_fnx), nx.clustering(G_nx),
                           label="clustering")

    def test_average_clustering(self, fnx, nx, triangle_graph):
        G_fnx, G_nx = triangle_graph
        assert abs(fnx.average_clustering(G_fnx) - nx.average_clustering(G_nx)) < 1e-9

    def test_transitivity(self, fnx, nx, triangle_graph):
        G_fnx, G_nx = triangle_graph
        assert abs(fnx.transitivity(G_fnx) - nx.transitivity(G_nx)) < 1e-9

    def test_triangles(self, fnx, nx, triangle_graph):
        G_fnx, G_nx = triangle_graph
        fnx_tri = fnx.triangles(G_fnx)
        nx_tri = nx.triangles(G_nx)
        for node in nx_tri:
            assert fnx_tri[node] == nx_tri[node], f"triangles[{node}]"

    def test_square_clustering(self, fnx, nx, complete_graph):
        G_fnx, G_nx = complete_graph
        assert_dicts_close(fnx.square_clustering(G_fnx), nx.square_clustering(G_nx),
                           label="square_clustering")

    def test_find_cliques(self, fnx, nx, complete_graph):
        G_fnx, G_nx = complete_graph
        # br-bulkgen: fnx.find_cliques now returns a generator matching nx.
        fnx_cliques = list(fnx.find_cliques(G_fnx))
        nx_cliques = list(nx.find_cliques(G_nx))
        # K5 should have exactly one maximal clique of size 5
        assert len(fnx_cliques) == len(nx_cliques)
        fnx_sorted = sorted([sorted(str(n) for n in c) for c in fnx_cliques])
        nx_sorted = sorted([sorted(str(n) for n in c) for c in nx_cliques])
        assert fnx_sorted == nx_sorted

    def test_graph_clique_number(self, fnx, complete_graph):
        G_fnx, _ = complete_graph
        # nx.graph_clique_number was removed in NetworkX 3.4;
        # verify our implementation against known value (K5 clique number = 5)
        assert fnx.graph_clique_number(G_fnx) == 5

    def test_clustering_path_graph(self, fnx, nx, path_graph):
        G_fnx, G_nx = path_graph
        # Path graph has 0 clustering everywhere
        assert abs(fnx.transitivity(G_fnx) - nx.transitivity(G_nx)) < 1e-9


def _build_clustering_case(graph, case_name):
    if case_name == "empty":
        return
    if case_name == "triangle_tail":
        graph.add_edges_from([(0, 1), (1, 2), (2, 0), (2, 3)])
        return
    if case_name == "bidirectional_triangle":
        graph.add_edges_from([(0, 1), (1, 0), (1, 2), (2, 1), (2, 0), (0, 2)])
        return
    if case_name == "selfloop":
        graph.add_edge(0, 0)
        return
    if case_name == "weighted_triangle_tail":
        graph.add_edge(0, 1, weight=2)
        graph.add_edge(1, 2, weight=4)
        graph.add_edge(2, 0, weight=8)
        graph.add_edge(2, 3, weight=16)
        return
    if case_name == "negative_weight_triangle":
        graph.add_edge(0, 1, weight=-2)
        graph.add_edge(1, 2, weight=4)
        graph.add_edge(2, 0, weight=8)
        return
    raise ValueError(f"unknown clustering case {case_name}")


@pytest.mark.conformance
class TestClusteringParity:
    @pytest.mark.parametrize(
        ("fnx_cls_name", "nx_cls_name", "case_name", "kwargs"),
        [
            ("Graph", "Graph", "triangle_tail", {}),
            ("Graph", "Graph", "triangle_tail", {"nodes": 0}),
            ("Graph", "Graph", "triangle_tail", {"nodes": [0, 2, 9]}),
            ("Graph", "Graph", "weighted_triangle_tail", {"weight": "weight"}),
            ("Graph", "Graph", "weighted_triangle_tail", {"nodes": 0, "weight": "weight"}),
            ("Graph", "Graph", "negative_weight_triangle", {"weight": "weight"}),
            ("DiGraph", "DiGraph", "triangle_tail", {}),
            ("DiGraph", "DiGraph", "triangle_tail", {"nodes": 0}),
            ("DiGraph", "DiGraph", "triangle_tail", {"nodes": [0, 2, 9]}),
            ("DiGraph", "DiGraph", "weighted_triangle_tail", {"weight": "weight"}),
        ],
    )
    def test_matches_networkx_without_fallback(
        self, monkeypatch, fnx, nx, fnx_cls_name, nx_cls_name, case_name, kwargs
    ):
        G_fnx = getattr(fnx, fnx_cls_name)()
        G_nx = getattr(nx, nx_cls_name)()
        _build_clustering_case(G_fnx, case_name)
        _build_clustering_case(G_nx, case_name)

        expected = nx.clustering(G_nx, **kwargs)

        monkeypatch.setattr(
            nx,
            "clustering",
            lambda *call_args, **call_kwargs: (_ for _ in ()).throw(
                AssertionError("NetworkX clustering fallback should not be used")
            ),
        )

        actual = fnx.clustering(G_fnx, **kwargs)

        if isinstance(expected, dict):
            assert_dicts_close(actual, expected, label="clustering")
        else:
            assert abs(actual - expected) < 1e-9

    @pytest.mark.parametrize(
        ("fnx_cls_name", "nx_cls_name", "case_name", "kwargs"),
        [
            ("Graph", "Graph", "triangle_tail", {"nodes": 9}),
            ("Graph", "Graph", "triangle_tail", {"nodes": [[0]]}),
            ("Graph", "Graph", "triangle_tail", {"nodes": object()}),
            ("MultiGraph", "MultiGraph", "triangle_tail", {}),
            ("MultiGraph", "MultiGraph", "triangle_tail", {"nodes": 0}),
            ("MultiDiGraph", "MultiDiGraph", "triangle_tail", {}),
            ("MultiDiGraph", "MultiDiGraph", "triangle_tail", {"nodes": [[0]]}),
        ],
    )
    def test_error_contract_matches_networkx_without_fallback(
        self, monkeypatch, fnx, nx, fnx_cls_name, nx_cls_name, case_name, kwargs
    ):
        G_fnx = getattr(fnx, fnx_cls_name)()
        G_nx = getattr(nx, nx_cls_name)()
        _build_clustering_case(G_fnx, case_name)
        _build_clustering_case(G_nx, case_name)

        try:
            nx.clustering(G_nx, **kwargs)
        except Exception as exc:
            expected_type = type(exc).__name__
            expected_message = str(exc)

        monkeypatch.setattr(
            nx,
            "clustering",
            lambda *call_args, **call_kwargs: (_ for _ in ()).throw(
                AssertionError("NetworkX clustering fallback should not be used")
            ),
        )

        with pytest.raises(Exception) as fnx_exc:
            fnx.clustering(G_fnx, **kwargs)

        assert type(fnx_exc.value).__name__ == expected_type
        assert str(fnx_exc.value) == expected_message


@pytest.mark.conformance
class TestAverageClusteringParity:
    @pytest.mark.parametrize(
        ("fnx_cls_name", "nx_cls_name", "case_name", "kwargs"),
        [
            ("Graph", "Graph", "triangle_tail", {}),
            ("Graph", "Graph", "triangle_tail", {"nodes": [0, 2, 9]}),
            ("Graph", "Graph", "triangle_tail", {"count_zeros": False}),
            ("Graph", "Graph", "weighted_triangle_tail", {"weight": "weight"}),
            (
                "Graph",
                "Graph",
                "weighted_triangle_tail",
                {"nodes": [0, 2, 9], "weight": "weight"},
            ),
            ("DiGraph", "DiGraph", "triangle_tail", {}),
            ("DiGraph", "DiGraph", "triangle_tail", {"nodes": [0, 2, 9]}),
            ("DiGraph", "DiGraph", "triangle_tail", {"count_zeros": False}),
            ("DiGraph", "DiGraph", "weighted_triangle_tail", {"weight": "weight"}),
        ],
    )
    def test_matches_networkx_without_fallback(
        self, monkeypatch, fnx, nx, fnx_cls_name, nx_cls_name, case_name, kwargs
    ):
        G_fnx = getattr(fnx, fnx_cls_name)()
        G_nx = getattr(nx, nx_cls_name)()
        _build_clustering_case(G_fnx, case_name)
        _build_clustering_case(G_nx, case_name)

        expected = nx.average_clustering(G_nx, **kwargs)

        monkeypatch.setattr(
            nx,
            "average_clustering",
            lambda *call_args, **call_kwargs: (_ for _ in ()).throw(
                AssertionError(
                    "NetworkX average_clustering fallback should not be used"
                )
            ),
        )

        actual = fnx.average_clustering(G_fnx, **kwargs)
        assert abs(actual - expected) < 1e-9

    @pytest.mark.parametrize(
        ("fnx_cls_name", "nx_cls_name", "case_name", "kwargs"),
        [
            ("Graph", "Graph", "triangle_tail", {"nodes": 0}),
            ("Graph", "Graph", "triangle_tail", {"nodes": [[0]]}),
            ("MultiGraph", "MultiGraph", "triangle_tail", {}),
            ("MultiGraph", "MultiGraph", "triangle_tail", {"count_zeros": False}),
            ("MultiDiGraph", "MultiDiGraph", "triangle_tail", {"weight": "weight"}),
        ],
    )
    def test_error_contract_matches_networkx_without_fallback(
        self, monkeypatch, fnx, nx, fnx_cls_name, nx_cls_name, case_name, kwargs
    ):
        G_fnx = getattr(fnx, fnx_cls_name)()
        G_nx = getattr(nx, nx_cls_name)()
        _build_clustering_case(G_fnx, case_name)
        _build_clustering_case(G_nx, case_name)

        try:
            nx.average_clustering(G_nx, **kwargs)
        except Exception as exc:
            expected_type = type(exc).__name__
            expected_message = str(exc)

        monkeypatch.setattr(
            nx,
            "average_clustering",
            lambda *call_args, **call_kwargs: (_ for _ in ()).throw(
                AssertionError(
                    "NetworkX average_clustering fallback should not be used"
                )
            ),
        )

        with pytest.raises(Exception) as fnx_exc:
            fnx.average_clustering(G_fnx, **kwargs)

        assert type(fnx_exc.value).__name__ == expected_type
        assert str(fnx_exc.value) == expected_message


@pytest.mark.conformance
class TestTransitivityParity:
    @pytest.mark.parametrize(
        ("fnx_cls_name", "nx_cls_name", "case_name"),
        [
            ("Graph", "Graph", "empty"),
            ("Graph", "Graph", "triangle_tail"),
            ("Graph", "Graph", "bidirectional_triangle"),
            ("DiGraph", "DiGraph", "empty"),
            ("DiGraph", "DiGraph", "triangle_tail"),
            ("DiGraph", "DiGraph", "bidirectional_triangle"),
        ],
    )
    def test_matches_networkx_without_fallback(
        self, monkeypatch, fnx, nx, fnx_cls_name, nx_cls_name, case_name
    ):
        G_fnx = getattr(fnx, fnx_cls_name)()
        G_nx = getattr(nx, nx_cls_name)()
        _build_clustering_case(G_fnx, case_name)
        _build_clustering_case(G_nx, case_name)

        expected = nx.transitivity(G_nx)

        monkeypatch.setattr(
            nx,
            "transitivity",
            lambda *call_args, **call_kwargs: (_ for _ in ()).throw(
                AssertionError("NetworkX transitivity fallback should not be used")
            ),
        )

        actual = fnx.transitivity(G_fnx)
        assert abs(actual - expected) < 1e-9

    @pytest.mark.parametrize(
        ("fnx_cls_name", "nx_cls_name", "case_name"),
        [
            ("MultiGraph", "MultiGraph", "empty"),
            ("MultiGraph", "MultiGraph", "triangle_tail"),
            ("MultiDiGraph", "MultiDiGraph", "bidirectional_triangle"),
        ],
    )
    def test_error_contract_matches_networkx_without_fallback(
        self, monkeypatch, fnx, nx, fnx_cls_name, nx_cls_name, case_name
    ):
        G_fnx = getattr(fnx, fnx_cls_name)()
        G_nx = getattr(nx, nx_cls_name)()
        _build_clustering_case(G_fnx, case_name)
        _build_clustering_case(G_nx, case_name)

        try:
            nx.transitivity(G_nx)
        except Exception as exc:
            expected_type = type(exc).__name__
            expected_message = str(exc)

        monkeypatch.setattr(
            nx,
            "transitivity",
            lambda *call_args, **call_kwargs: (_ for _ in ()).throw(
                AssertionError("NetworkX transitivity fallback should not be used")
            ),
        )

        with pytest.raises(Exception) as fnx_exc:
            fnx.transitivity(G_fnx)

        assert type(fnx_exc.value).__name__ == expected_type
        assert str(fnx_exc.value) == expected_message


@pytest.mark.conformance
class TestGeneralizedDegreeParity:
    @pytest.mark.parametrize(
        ("fnx_cls_name", "nx_cls_name", "case_name", "kwargs"),
        [
            ("Graph", "Graph", "empty", {}),
            ("Graph", "Graph", "triangle_tail", {}),
            ("Graph", "Graph", "triangle_tail", {"nodes": 0}),
            ("Graph", "Graph", "triangle_tail", {"nodes": [0, 2, 9]}),
            ("Graph", "Graph", "selfloop", {}),
        ],
    )
    def test_matches_networkx_without_fallback(
        self, monkeypatch, fnx, nx, fnx_cls_name, nx_cls_name, case_name, kwargs
    ):
        G_fnx = getattr(fnx, fnx_cls_name)()
        G_nx = getattr(nx, nx_cls_name)()
        _build_clustering_case(G_fnx, case_name)
        _build_clustering_case(G_nx, case_name)

        expected = nx.generalized_degree(G_nx, **kwargs)

        monkeypatch.setattr(
            nx,
            "generalized_degree",
            lambda *call_args, **call_kwargs: (_ for _ in ()).throw(
                AssertionError(
                    "NetworkX generalized_degree fallback should not be used"
                )
            ),
        )

        actual = fnx.generalized_degree(G_fnx, **kwargs)
        assert actual == expected

    @pytest.mark.parametrize(
        ("fnx_cls_name", "nx_cls_name", "case_name", "kwargs"),
        [
            ("Graph", "Graph", "triangle_tail", {"nodes": 9}),
            ("Graph", "Graph", "triangle_tail", {"nodes": [[0]]}),
            ("DiGraph", "DiGraph", "triangle_tail", {}),
            ("MultiGraph", "MultiGraph", "triangle_tail", {}),
            ("MultiDiGraph", "MultiDiGraph", "triangle_tail", {}),
        ],
    )
    def test_error_contract_matches_networkx_without_fallback(
        self, monkeypatch, fnx, nx, fnx_cls_name, nx_cls_name, case_name, kwargs
    ):
        G_fnx = getattr(fnx, fnx_cls_name)()
        G_nx = getattr(nx, nx_cls_name)()
        _build_clustering_case(G_fnx, case_name)
        _build_clustering_case(G_nx, case_name)

        try:
            nx.generalized_degree(G_nx, **kwargs)
        except Exception as exc:
            expected_type = type(exc).__name__
            expected_message = str(exc)

        monkeypatch.setattr(
            nx,
            "generalized_degree",
            lambda *call_args, **call_kwargs: (_ for _ in ()).throw(
                AssertionError(
                    "NetworkX generalized_degree fallback should not be used"
                )
            ),
        )

        with pytest.raises(Exception) as fnx_exc:
            fnx.generalized_degree(G_fnx, **kwargs)

        assert type(fnx_exc.value).__name__ == expected_type
        assert str(fnx_exc.value) == expected_message


def _build_triangles_case(graph, case_name):
    if case_name == "triangle_tail":
        graph.add_edges_from([(0, 1), (1, 2), (2, 0), (2, 3)])
        return
    if case_name == "empty":
        return
    raise ValueError(f"unknown triangles case {case_name}")


@pytest.mark.conformance
class TestTrianglesParity:
    @pytest.mark.parametrize(
        ("fnx_cls_name", "nx_cls_name", "case_name", "nodes"),
        [
            ("Graph", "Graph", "triangle_tail", None),
            ("Graph", "Graph", "triangle_tail", 0),
            ("Graph", "Graph", "triangle_tail", [0, 2, 3]),
            ("Graph", "Graph", "triangle_tail", [9]),
            ("MultiGraph", "MultiGraph", "triangle_tail", None),
        ],
    )
    def test_matches_networkx_without_fallback(
        self, monkeypatch, fnx, nx, fnx_cls_name, nx_cls_name, case_name, nodes
    ):
        G_fnx = getattr(fnx, fnx_cls_name)()
        G_nx = getattr(nx, nx_cls_name)()
        _build_triangles_case(G_fnx, case_name)
        _build_triangles_case(G_nx, case_name)

        if nodes is None:
            expected = nx.triangles(G_nx)
        else:
            expected = nx.triangles(G_nx, nodes)

        monkeypatch.setattr(
            nx,
            "triangles",
            lambda *call_args, **call_kwargs: (_ for _ in ()).throw(
                AssertionError("NetworkX triangles fallback should not be used")
            ),
        )

        if nodes is None:
            actual = fnx.triangles(G_fnx)
        else:
            actual = fnx.triangles(G_fnx, nodes)

        assert actual == expected

    @pytest.mark.parametrize(
        ("fnx_cls_name", "nx_cls_name", "case_name", "nodes"),
        [
            ("Graph", "Graph", "triangle_tail", 9),
            ("Graph", "Graph", "triangle_tail", [[0]]),
            ("DiGraph", "DiGraph", "triangle_tail", None),
            ("DiGraph", "DiGraph", "triangle_tail", 0),
            ("MultiGraph", "MultiGraph", "triangle_tail", 0),
            ("MultiDiGraph", "MultiDiGraph", "triangle_tail", None),
            ("MultiDiGraph", "MultiDiGraph", "triangle_tail", 0),
        ],
    )
    def test_error_contract_matches_networkx_without_fallback(
        self, monkeypatch, fnx, nx, fnx_cls_name, nx_cls_name, case_name, nodes
    ):
        G_fnx = getattr(fnx, fnx_cls_name)()
        G_nx = getattr(nx, nx_cls_name)()
        _build_triangles_case(G_fnx, case_name)
        _build_triangles_case(G_nx, case_name)

        try:
            if nodes is None:
                nx.triangles(G_nx)
            else:
                nx.triangles(G_nx, nodes)
        except Exception as exc:
            expected_type = type(exc).__name__
            expected_message = str(exc)

        monkeypatch.setattr(
            nx,
            "triangles",
            lambda *call_args, **call_kwargs: (_ for _ in ()).throw(
                AssertionError("NetworkX triangles fallback should not be used")
            ),
        )

        with pytest.raises(Exception) as fnx_exc:
            if nodes is None:
                fnx.triangles(G_fnx)
            else:
                fnx.triangles(G_fnx, nodes)

        assert type(fnx_exc.value).__name__ == expected_type
        assert str(fnx_exc.value) == expected_message


def _build_square_clustering_case(graph, case_name):
    if case_name == "square_with_diagonal":
        graph.add_edges_from([(0, 1), (1, 2), (2, 3), (3, 0), (0, 2)])
        return
    if case_name == "empty":
        return
    raise ValueError(f"unknown square_clustering case {case_name}")


@pytest.mark.conformance
class TestSquareClusteringParity:
    @pytest.mark.parametrize(
        ("fnx_cls_name", "nx_cls_name", "case_name", "nodes"),
        [
            ("Graph", "Graph", "square_with_diagonal", None),
            ("Graph", "Graph", "square_with_diagonal", 0),
            ("Graph", "Graph", "square_with_diagonal", [0, 2, 9]),
            ("DiGraph", "DiGraph", "square_with_diagonal", None),
            ("DiGraph", "DiGraph", "square_with_diagonal", 0),
            ("DiGraph", "DiGraph", "square_with_diagonal", [0, 2, 9]),
            ("MultiGraph", "MultiGraph", "square_with_diagonal", None),
            ("MultiDiGraph", "MultiDiGraph", "square_with_diagonal", None),
        ],
    )
    def test_matches_networkx_without_fallback(
        self, monkeypatch, fnx, nx, fnx_cls_name, nx_cls_name, case_name, nodes
    ):
        G_fnx = getattr(fnx, fnx_cls_name)()
        G_nx = getattr(nx, nx_cls_name)()
        _build_square_clustering_case(G_fnx, case_name)
        _build_square_clustering_case(G_nx, case_name)

        if nodes is None:
            expected = nx.square_clustering(G_nx)
        else:
            expected = nx.square_clustering(G_nx, nodes)

        monkeypatch.setattr(
            nx,
            "square_clustering",
            lambda *call_args, **call_kwargs: (_ for _ in ()).throw(
                AssertionError(
                    "NetworkX square_clustering fallback should not be used"
                )
            ),
        )

        if nodes is None:
            actual = fnx.square_clustering(G_fnx)
        else:
            actual = fnx.square_clustering(G_fnx, nodes)

        if isinstance(expected, dict):
            assert_dicts_close(actual, expected, label="square_clustering")
        else:
            assert abs(actual - expected) < 1e-9

    @pytest.mark.parametrize(
        ("fnx_cls_name", "nx_cls_name", "case_name", "nodes"),
        [
            ("Graph", "Graph", "square_with_diagonal", 9),
            ("Graph", "Graph", "square_with_diagonal", [[0]]),
            ("Graph", "Graph", "square_with_diagonal", object()),
            ("DiGraph", "DiGraph", "square_with_diagonal", 9),
            ("MultiGraph", "MultiGraph", "square_with_diagonal", [[0]]),
        ],
    )
    def test_error_contract_matches_networkx_without_fallback(
        self, monkeypatch, fnx, nx, fnx_cls_name, nx_cls_name, case_name, nodes
    ):
        G_fnx = getattr(fnx, fnx_cls_name)()
        G_nx = getattr(nx, nx_cls_name)()
        _build_square_clustering_case(G_fnx, case_name)
        _build_square_clustering_case(G_nx, case_name)

        try:
            nx.square_clustering(G_nx, nodes)
        except Exception as exc:
            expected_type = type(exc).__name__
            expected_message = str(exc)

        monkeypatch.setattr(
            nx,
            "square_clustering",
            lambda *call_args, **call_kwargs: (_ for _ in ()).throw(
                AssertionError(
                    "NetworkX square_clustering fallback should not be used"
                )
            ),
        )

        with pytest.raises(Exception) as fnx_exc:
            fnx.square_clustering(G_fnx, nodes)

        assert type(fnx_exc.value).__name__ == expected_type
        assert str(fnx_exc.value) == expected_message
