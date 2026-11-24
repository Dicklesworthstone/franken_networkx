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

    def test_graph_clique_number_absent(self, fnx, nx):
        # nx.graph_clique_number was removed upstream; fnx mirrors that
        # public surface instead of keeping a compatibility shim.
        assert not hasattr(nx, "graph_clique_number")
        assert not hasattr(fnx, "graph_clique_number")

    def test_clustering_path_graph(self, fnx, nx, path_graph):
        G_fnx, G_nx = path_graph
        # Path graph has 0 clustering everywhere
        assert abs(fnx.transitivity(G_fnx) - nx.transitivity(G_nx)) < 1e-9

    def test_triangle_census_reused_by_clustering_family(
        self, monkeypatch, fnx, nx
    ):
        edges = [(0, 1), (1, 2), (2, 0), (2, 3), (3, 4), (4, 2)]
        G_fnx = fnx.Graph()
        G_nx = nx.Graph()
        G_fnx.add_edges_from(edges)
        G_nx.add_edges_from(edges)
        G_fnx.add_edge(4, 4)
        G_nx.add_edge(4, 4)

        raw_triangles = fnx._raw_triangles
        calls = 0

        def counted_triangles(graph):
            nonlocal calls
            calls += 1
            return raw_triangles(graph)

        def duplicate_census(*_args, **_kwargs):
            raise AssertionError("triangle census should be reused")

        monkeypatch.setattr(fnx, "_raw_triangles", counted_triangles)
        monkeypatch.setattr(fnx, "_raw_clustering", duplicate_census)
        monkeypatch.setattr(fnx, "_raw_transitivity", duplicate_census)

        triangle_result = fnx.triangles(G_fnx)
        assert triangle_result == nx.triangles(G_nx)
        triangle_result[0] = 999
        assert fnx.average_clustering(G_fnx) == nx.average_clustering(G_nx)
        assert fnx.transitivity(G_fnx) == nx.transitivity(G_nx)
        clustering_result = fnx.clustering(G_fnx)
        assert clustering_result == nx.clustering(G_nx)
        clustering_result[0] = 999
        assert fnx.triangles(G_fnx) == nx.triangles(G_nx)
        assert fnx.clustering(G_fnx) == nx.clustering(G_nx)
        assert calls == 1

        # A topology mutation invalidates the snapshot and exactly one new
        # census repopulates the whole family.
        G_fnx.add_edge(0, 4)
        G_nx.add_edge(0, 4)
        assert fnx.triangles(G_fnx) == nx.triangles(G_nx)
        assert fnx.average_clustering(G_fnx) == nx.average_clustering(G_nx)
        assert fnx.transitivity(G_fnx) == nx.transitivity(G_nx)
        assert fnx.clustering(G_fnx) == nx.clustering(G_nx)
        assert calls == 2


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


def _clustering_live_view(module, kind):
    graph = module.DiGraph()
    graph.add_weighted_edges_from(
        [
            (0, 1, 1), (1, 0, 10), (1, 2, 2),
            (2, 1, 20), (2, 0, 3), (0, 2, 30),
            (2, 3, 4), (3, 2, 5),
        ]
    )
    if kind == "undirected":
        return graph.to_undirected(as_view=True)
    if kind == "filtered_undirected":
        return module.subgraph_view(
            graph.to_undirected(as_view=True), filter_node=lambda node: node != 3
        )
    if kind == "reverse":
        return graph.reverse(copy=False)
    return module.subgraph_view(
        graph, filter_edge=lambda left, right: (left, right) != (1, 0)
    )


def _clustering_nodes(mode):
    if mode == "all":
        return None
    if mode == "scalar":
        return 0
    if mode == "subset":
        return [0, 2, 99]
    return iter([0, 2, 99])


@pytest.mark.parametrize("source", ["native", "networkx"])
@pytest.mark.parametrize(
    "kind", ["undirected", "filtered_undirected", "reverse", "filtered_directed"]
)
@pytest.mark.parametrize("mode", ["all", "scalar", "subset", "iterator"])
def test_weighted_clustering_reads_each_view_endpoint(fnx, nx, source, kind, mode):
    actual_graph = _clustering_live_view(fnx if source == "native" else nx, kind)
    expected_graph = _clustering_live_view(nx, kind)
    expected = nx.clustering(
        expected_graph, nodes=_clustering_nodes(mode), weight="weight"
    )
    actual = fnx.clustering(
        actual_graph, nodes=_clustering_nodes(mode), weight="weight"
    )
    assert actual == expected


@pytest.mark.parametrize("source", ["native", "networkx"])
@pytest.mark.parametrize(
    "kind", ["undirected", "filtered_undirected", "reverse", "filtered_directed"]
)
@pytest.mark.parametrize("mode", ["all", "subset", "iterator"])
def test_weighted_average_clustering_reads_each_view_endpoint(
    fnx, nx, source, kind, mode
):
    actual_graph = _clustering_live_view(fnx if source == "native" else nx, kind)
    expected_graph = _clustering_live_view(nx, kind)
    expected = nx.average_clustering(
        expected_graph, nodes=_clustering_nodes(mode), weight="weight"
    )
    actual = fnx.average_clustering(
        actual_graph, nodes=_clustering_nodes(mode), weight="weight"
    )
    assert actual == expected


@pytest.mark.parametrize("name", ["clustering", "average_clustering"])
@pytest.mark.parametrize("weight", [None, "weight"])
@pytest.mark.parametrize("asymmetric_topology", [False, True])
def test_clustering_keeps_assigned_adjacency_rows(
    fnx, nx, name, weight, asymmetric_topology
):
    def make(module):
        graph = module.Graph([(0, 1), (1, 2), (2, 0)])
        # A native triangle census is already cached before logical rows
        # change, without any native topology revision.
        module.triangles(graph)
        graph._adj = {
            0: {1: {"weight": 1}, 2: {"weight": 30}},
            1: {0: {"weight": 10}, 2: {"weight": 2}},
            2: {0: {"weight": 3}, 1: {"weight": 20}},
        }
        if asymmetric_topology:
            del graph._adj[0][2]
        return graph

    assert getattr(fnx, name)(make(fnx), weight=weight) == getattr(nx, name)(
        make(nx), weight=weight
    )


@pytest.mark.parametrize("graph_class", ["Graph", "DiGraph"])
@pytest.mark.parametrize("name", ["clustering", "average_clustering"])
@pytest.mark.parametrize("weighted", [False, True])
def test_clustering_consumes_mutating_nbunch_between_rows(
    fnx, nx, graph_class, name, weighted
):
    def run(module):
        graph = getattr(module, graph_class)()
        graph.add_weighted_edges_from(
            [(0, 1, 2), (1, 2, 4), (2, 0, 8), (0, 2, 8)]
        )

        def selected_nodes():
            yield 0
            graph[1][2]["weight"] = 16
            graph.add_edge(2, 3, weight=1)
            yield 1
            yield 2

        result = getattr(module, name)(
            graph, nodes=selected_nodes(), weight="weight" if weighted else None
        )
        return result, graph[1][2]["weight"], list(graph.edges)

    assert run(fnx) == run(nx)


@pytest.mark.parametrize("graph_class", ["Graph", "DiGraph"])
@pytest.mark.parametrize("name", ["clustering", "average_clustering"])
def test_clustering_observes_weight_arithmetic_mutation(fnx, nx, graph_class, name):
    def run(module):
        graph = getattr(module, graph_class)()
        events = []

        class Weight(float):
            def __truediv__(self, other):
                events.append((float(self), float(other)))
                if len(events) == 1:
                    graph[1][2]["weight"] = Weight(13)
                return float(self) / float(other)

        graph.add_weighted_edges_from(
            [
                (0, 1, Weight(2)), (1, 2, Weight(4)),
                (2, 0, Weight(8)), (0, 2, Weight(8)),
            ]
        )
        result = getattr(module, name)(graph, weight="weight")
        return result, events, graph[1][2]["weight"]

    assert run(fnx) == run(nx)


@pytest.mark.parametrize("graph_class", ["MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("name", ["clustering", "average_clustering"])
def test_clustering_live_multigraph_still_rejects(fnx, nx, graph_class, name):
    expected_graph = getattr(nx, graph_class)([(0, 1), (1, 2), (2, 0)])
    actual_graph = getattr(fnx, graph_class)([(0, 1), (1, 2), (2, 0)])
    with pytest.raises(nx.NetworkXNotImplemented) as expected:
        getattr(nx, name)(expected_graph.copy(as_view=True), weight="weight")
    with pytest.raises(fnx.NetworkXNotImplemented) as actual:
        getattr(fnx, name)(actual_graph.copy(as_view=True), weight="weight")
    assert actual.value.args == expected.value.args


@pytest.mark.parametrize("source", ["native", "networkx"])
@pytest.mark.parametrize("name", ["clustering", "average_clustering"])
def test_clustering_preserves_edge_count_provider(fnx, nx, source, name):
    def make(module):
        graph = module.Graph()
        graph.add_weighted_edges_from([(0, 1, 2), (1, 2, 4), (2, 0, 8)])
        graph.number_of_edges = lambda: 0
        return graph

    assert getattr(fnx, name)(
        make(fnx if source == "native" else nx), weight="weight"
    ) == getattr(nx, name)(make(nx), weight="weight")


@pytest.mark.parametrize("source", ["native", "networkx"])
@pytest.mark.parametrize("view", [False, True])
def test_triangles_consume_mutating_nbunch_between_counts(fnx, nx, source, view):
    def run(algorithm, graph_module):
        owner = graph_module.Graph([(0, 1), (1, 2), (2, 0)])
        graph = owner.copy(as_view=True) if view else owner

        def selected_nodes():
            yield 0
            owner.remove_edge(1, 2)
            yield 1
            yield 2

        result = algorithm.triangles(graph, nodes=selected_nodes())
        return result, owner.has_edge(1, 2)

    expected = run(nx, nx)
    assert expected == ({0: 1, 1: 0, 2: 0}, False)
    assert run(fnx, fnx if source == "native" else nx) == expected


@pytest.mark.parametrize("graph_class", ["Graph", "MultiGraph"])
@pytest.mark.parametrize("warm_cache", [False, True])
def test_triangles_keep_stored_node_mutation_live(fnx, nx, graph_class, warm_cache):
    def run(module):
        graph = getattr(module, graph_class)()

        class Node:
            value = 0
            armed = False

            def __hash__(self):
                if self.armed:
                    self.armed = False
                    graph.remove_edge(1, 2)
                return 0

        node = Node()
        graph.add_edges_from([(node, 1), (1, 2), (2, node)])
        if warm_cache:
            module.triangles(graph)
        node.armed = True
        result = module.triangles(graph)
        values = [(getattr(key, "value", key), value) for key, value in result.items()]
        return values, graph.has_edge(1, 2)

    expected = run(nx)
    assert expected == ([(0, 0), (1, 0), (2, 0)], False)
    assert run(fnx) == expected


@pytest.mark.parametrize("selection", ["scalar", "list", "iterator"])
@pytest.mark.parametrize("warm_cache", [False, True])
def test_triangles_selected_rows_keep_neighbor_mutation_live(
    fnx, nx, selection, warm_cache
):
    def run(module):
        graph = module.Graph()

        class Node:
            armed = False

            def __hash__(self):
                if self.armed:
                    self.armed = False
                    graph.remove_edge(1, self)
                return 2

        node = Node()
        graph.add_edges_from([(0, 1), (1, node), (node, 0)])
        if warm_cache:
            module.triangles(graph)
        node.armed = True
        selected = 0 if selection == "scalar" else [0]
        if selection == "iterator":
            selected = iter(selected)
        result = module.triangles(graph, nodes=selected)
        return result, graph.has_edge(1, node)

    expected = run(nx)
    assert expected == (0 if selection == "scalar" else {0: 0}, False)
    assert run(fnx) == expected


@pytest.mark.parametrize("source", ["native", "networkx"])
@pytest.mark.parametrize("provider", ["instance", "class"])
def test_triangles_keep_original_adjacency_provider(
    fnx, nx, source, provider, monkeypatch
):
    def run(algorithm, graph_module):
        graph = graph_module.Graph([(0, 1), (1, 2), (2, 0)])
        algorithm.triangles(graph)
        reads = []

        def adjacency(*_args):
            reads.append("adjacency")
            yield 0, {1: {}, 2: {}}
            yield 1, {0: {}}
            yield 2, {0: {}}

        with monkeypatch.context() as patch:
            patch.setattr(graph if provider == "instance" else type(graph), "adjacency", adjacency)
            result = algorithm.triangles(graph)
        return result, reads

    expected = run(nx, nx)
    assert expected == ({0: 0, 1: 0, 2: 0}, ["adjacency"])
    assert run(fnx, fnx if source == "native" else nx) == expected


@pytest.mark.parametrize("mutation", ["node_domain", "neighbor_row"])
def test_triangles_preserve_live_dictionary_size_errors(fnx, nx, mutation):
    def run(module):
        graph = module.Graph()

        class Node:
            armed = False

            def __hash__(self):
                if self.armed:
                    self.armed = False
                    if mutation == "node_domain":
                        graph.add_node(3)
                    else:
                        graph.add_edge(0, 3)
                return 2

        node = Node()
        graph.add_edges_from([(0, node), (node, 1), (1, 0)])
        node.armed = True
        with pytest.raises(RuntimeError) as error:
            module.triangles(graph)
        return error.value.args

    assert run(fnx) == run(nx) == ("dictionary changed size during iteration",)


@pytest.mark.parametrize("selection", ["scalar", "list", "iterator"])
def test_triangles_local_queries_do_not_touch_unrelated_labels(
    fnx, nx, selection, monkeypatch
):
    def run(module):
        graph = module.Graph([(0, 1), (1, 2), (2, 0)])

        class Unrelated:
            armed = False

            def __hash__(self):
                if self.armed:
                    raise AssertionError("unrelated node was hashed")
                return 42

        node = Unrelated()
        graph.add_node(node)
        node.armed = True
        selected = 0 if selection == "scalar" else [0]
        if selection == "iterator":
            selected = iter(selected)
        return module.triangles(graph, nodes=selected)

    def reject_global_admission(*_args):
        raise AssertionError("local query scanned all node labels")

    monkeypatch.setattr(fnx, "_view_root_node_keys_are_stable", reject_global_admission)
    assert run(fnx) == run(nx) == (1 if selection == "scalar" else {0: 1})


def test_triangles_multigraph_does_not_read_parallel_edge_keys(fnx, nx, monkeypatch):
    raw_triangles = fnx._raw_triangles
    calls = []

    def counted(graph):
        calls.append(graph)
        return raw_triangles(graph)

    def run(module):
        graph = module.MultiGraph([(0, 1), (1, 2), (2, 0)])

        class EdgeKey:
            armed = False

            def __hash__(self):
                if self.armed:
                    raise AssertionError("parallel edge key was hashed")
                return 42

        key = EdgeKey()
        graph.add_edge(0, 1, key=key)
        key.armed = True
        return module.triangles(graph)

    monkeypatch.setattr(fnx, "_raw_triangles", counted)
    assert run(fnx) == run(nx) == {0: 1, 1: 1, 2: 1}
    assert len(calls) == 1


@pytest.mark.parametrize("graph_class", ["Graph", "MultiGraph", "DiGraph", "MultiDiGraph"])
def test_triangles_preserve_membership_and_graph_type_error_order(fnx, nx, graph_class):
    def run(module):
        graph = getattr(module, graph_class)([(0, 1)])
        events = []

        class Selector:
            def __hash__(self):
                events.append("membership")
                raise RuntimeError("selector membership")

        try:
            module.triangles(graph, nodes=Selector())
        except Exception as error:
            return type(error).__name__, error.args, events
        raise AssertionError("expected selector or graph-type error")

    expected = run(nx)
    assert expected[2] == ([] if "DiGraph" in graph_class else ["membership"])
    assert run(fnx) == expected
