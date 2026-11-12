"""Conformance tests: centrality algorithms — fnx vs nx oracle."""

from decimal import Decimal
from fractions import Fraction

import pytest
from conftest import assert_dicts_close


@pytest.mark.conformance
class TestCentrality:
    def test_degree_centrality(self, fnx, nx, path_graph):
        G_fnx, G_nx = path_graph
        assert_dicts_close(fnx.degree_centrality(G_fnx), nx.degree_centrality(G_nx),
                           label="degree_centrality")

    def test_closeness_centrality(self, fnx, nx, path_graph):
        G_fnx, G_nx = path_graph
        assert_dicts_close(fnx.closeness_centrality(G_fnx), nx.closeness_centrality(G_nx),
                           label="closeness_centrality")

    def test_harmonic_centrality(self, fnx, nx, path_graph):
        G_fnx, G_nx = path_graph
        assert_dicts_close(fnx.harmonic_centrality(G_fnx), nx.harmonic_centrality(G_nx),
                           label="harmonic_centrality")

    def test_betweenness_centrality(self, fnx, nx, path_graph):
        G_fnx, G_nx = path_graph
        assert_dicts_close(fnx.betweenness_centrality(G_fnx), nx.betweenness_centrality(G_nx),
                           label="betweenness_centrality")

    def test_eigenvector_centrality(self, fnx, nx, complete_graph):
        G_fnx, G_nx = complete_graph
        # K5 all nodes have equal eigenvector centrality
        fnx_ec = fnx.eigenvector_centrality(G_fnx)
        nx_ec = nx.eigenvector_centrality(G_nx)
        assert_dicts_close(fnx_ec, nx_ec, atol=1e-3, label="eigenvector_centrality")

    def test_pagerank(self, fnx, nx, complete_graph):
        G_fnx, G_nx = complete_graph
        fnx_pr = fnx.pagerank(G_fnx)
        nx_pr = nx.pagerank(G_nx)
        assert_dicts_close(fnx_pr, nx_pr, atol=1e-3, label="pagerank")

    def test_pagerank_sum_to_one(self, fnx, path_graph):
        G_fnx, _ = path_graph
        pr = fnx.pagerank(G_fnx)
        assert abs(sum(pr.values()) - 1.0) < 0.01

    def test_pagerank_dangling(self, fnx, nx):
        G_fnx = fnx.DiGraph()
        G_nx = nx.DiGraph()
        G_fnx.add_edge(0, 1)
        G_nx.add_edge(0, 1)
        G_fnx.add_node(2)
        G_nx.add_node(2)
        dangling = {0: 0.0, 1: 0.5, 2: 0.5}

        assert_dicts_close(
            fnx.pagerank(G_fnx, dangling=dangling),
            nx.pagerank(G_nx, dangling=dangling),
            atol=1e-6,
            label="pagerank_dangling",
        )

    def test_katz_centrality(self, fnx, nx, path_graph):
        G_fnx, G_nx = path_graph
        fnx_kc = fnx.katz_centrality(G_fnx)
        nx_kc = nx.katz_centrality(G_nx)
        assert_dicts_close(fnx_kc, nx_kc, atol=1e-3, label="katz_centrality")

    def test_katz_centrality_many(self, fnx, nx):
        G_fnx = fnx.DiGraph()
        G_nx = nx.DiGraph()
        edges = [
            (0, 1, 0.5),
            (1, 2, 1.25),
            (2, 0, 0.75),
            (2, 3, 1.5),
            (3, 1, 0.25),
        ]
        G_fnx.add_weighted_edges_from(edges)
        G_nx.add_weighted_edges_from(edges)
        betas = [
            1.0,
            {node: 0.5 + node / 10 for node in G_nx},
            {node: 1.5 - node / 10 for node in G_nx},
        ]
        kwargs = {
            "alpha": 0.05,
            "max_iter": 1000,
            "tol": 1.0e-10,
            "normalized": True,
            "weight": "weight",
        }

        actual = fnx.katz_centrality_many(G_fnx, betas, workers=2, **kwargs)
        expected = [nx.katz_centrality(G_nx, beta=beta, **kwargs) for beta in betas]
        single = [fnx.katz_centrality(G_fnx, beta=beta, **kwargs) for beta in betas]
        serial = fnx.katz_centrality_many(G_fnx, betas, workers=1, **kwargs)

        assert len(actual) == len(betas)
        for index, (actual_vector, expected_vector, serial_vector) in enumerate(
            zip(actual, expected, serial)
        ):
            assert_dicts_close(
                actual_vector,
                expected_vector,
                atol=1e-12,
                label=f"katz_centrality_many[{index}]",
            )
            assert actual_vector == single[index]
            assert actual_vector == serial_vector

    def test_katz_centrality_many_preserves_first_convergence(self, fnx):
        graph = fnx.DiGraph([(0, 1), (1, 2), (2, 0), (2, 3), (3, 1)])
        betas = [
            1.0e-3,
            1.0e3,
            {node: 0.25 + node for node in graph},
            {node: 4.0 - node / 2 for node in graph},
        ]
        kwargs = {
            "alpha": 0.05,
            "max_iter": 1000,
            "tol": 1.0e-10,
            "normalized": False,
            "weight": None,
        }
        expected = [
            fnx.katz_centrality(graph, beta=beta, **kwargs) for beta in betas
        ]

        assert fnx.katz_centrality_many(
            graph, betas, workers=4, **kwargs
        ) == expected

    def test_katz_centrality_many_edges(self, fnx):
        assert fnx.katz_centrality_many(fnx.Graph(), [1.0, 2.0]) == [{}, {}]
        assert fnx.katz_centrality_many(fnx.path_graph(3), []) == []
        with pytest.raises(ValueError, match="workers must be greater than 0"):
            fnx.katz_centrality_many(fnx.path_graph(3), [1.0], workers=0)
        with pytest.raises(
            fnx.NetworkXError,
            match="beta dictionary must have a value for every node",
        ):
            fnx.katz_centrality_many(fnx.path_graph(3), [{0: 1.0}], workers=1)
        with pytest.raises(fnx.NetworkXNotImplemented):
            fnx.katz_centrality_many(fnx.MultiGraph([(0, 1)]), [1.0])

    def test_edge_betweenness_centrality(self, fnx, nx, path_graph):
        G_fnx, G_nx = path_graph
        fnx_ebc = fnx.edge_betweenness_centrality(G_fnx)
        nx_ebc = nx.edge_betweenness_centrality(G_nx)
        # Normalize edge keys for comparison
        fnx_norm = {tuple(sorted((str(u), str(v)))): s for (u, v), s in fnx_ebc.items()}
        nx_norm = {tuple(sorted((str(u), str(v)))): s for (u, v), s in nx_ebc.items()}
        for key in nx_norm:
            assert abs(fnx_norm[key] - nx_norm[key]) < 1e-6, f"edge_betweenness[{key}]"

    def test_voterank(self, fnx, nx, path_graph):
        G_fnx, G_nx = path_graph
        fnx_vr = fnx.voterank(G_fnx)
        nx_vr = nx.voterank(G_nx)
        # Voterank order should match
        assert [str(x) for x in fnx_vr] == [str(x) for x in nx_vr]

    def test_degree_assortativity(self, fnx, nx, path_graph):
        G_fnx, G_nx = path_graph
        fnx_dac = fnx.degree_assortativity_coefficient(G_fnx)
        nx_dac = nx.degree_assortativity_coefficient(G_nx)
        assert abs(fnx_dac - nx_dac) < 1e-6


@pytest.mark.conformance
@pytest.mark.parametrize("algorithm", ["eigenvector_centrality", "katz_centrality"])
@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph"])
class TestCentralityStartVectors:
    @staticmethod
    def _graphs(fnx, nx, graph_type, shape="cycle"):
        edges = {
            "cycle": [(0, 1, 2), (1, 2, 3), (2, 0, 1)],
            "component": [(0, 1, 2), (1, 0, 2)],
            "isolates": [],
        }[shape]
        graphs = [getattr(module, graph_type)() for module in (fnx, nx)]
        for graph in graphs:
            graph.add_nodes_from(range(3))
            graph.add_weighted_edges_from(edges)
        return graphs

    @pytest.mark.parametrize("reverse_start", [False, True])
    @pytest.mark.parametrize("weight", [None, "weight"])
    def test_complete_start_preserves_order_and_sparse_route(
        self, fnx, nx, monkeypatch, algorithm, graph_type, reverse_start, weight
    ):
        actual_graph, expected_graph = self._graphs(fnx, nx, graph_type)
        nodes = list(expected_graph)[::-1] if reverse_start else list(expected_graph)
        start = {node: node + 1.0 for node in nodes}
        original_items = list(start.items())
        kwargs = {"max_iter": 1000, "tol": 1e-10, "weight": weight}
        expected = getattr(nx, algorithm)(expected_graph, nstart=start, **kwargs)
        calls = []
        for suffix in ("scipy", "inproc"):
            name = f"_{algorithm}_{suffix}"
            original = getattr(fnx, name)

            def recording(*args, _name=name, _original=original, **kw):
                calls.append(_name)
                return _original(*args, **kw)

            monkeypatch.setattr(fnx, name, recording)

        actual = getattr(fnx, algorithm)(actual_graph, nstart=start, **kwargs)
        assert list(actual) == list(expected) == nodes
        assert actual == pytest.approx(expected, rel=1e-12, abs=1e-12)
        assert list(start.items()) == original_items
        assert calls == [f"_{algorithm}_scipy"]

    @pytest.mark.parametrize(
        ("shape", "start_items"),
        [
            pytest.param("cycle", [(0, 1.0)], id="missing-connected-node"),
            pytest.param(
                "cycle", [(0, 1.0), (1, 2.0), (2, 3.0), (99, 4.0)],
                id="extra-node",
            ),
            pytest.param(
                "cycle", [(0, 1.0), (1, 2.0), (99, 3.0)],
                id="same-size-wrong-domain",
            ),
            pytest.param("cycle", [], id="empty-start"),
            pytest.param(
                "component", [(1, 2.0), (0, 1.0)],
                id="complete-component-subset",
            ),
            pytest.param(
                "isolates", [(2, 3.0), (0, 1.0)], id="isolated-node-subset",
            ),
        ],
    )
    def test_start_domain_matches_networkx(
        self, fnx, nx, algorithm, graph_type, shape, start_items
    ):
        actual_graph, expected_graph = self._graphs(fnx, nx, graph_type, shape)
        actual_start = dict(start_items)
        expected_start = dict(start_items)
        kwargs = {"max_iter": 1000, "tol": 1e-10, "weight": "weight"}
        try:
            expected = getattr(nx, algorithm)(
                expected_graph, nstart=expected_start, **kwargs
            )
        except Exception as expected_error:
            error_type = getattr(fnx, type(expected_error).__name__, type(expected_error))
            with pytest.raises(error_type) as actual_error:
                getattr(fnx, algorithm)(actual_graph, nstart=actual_start, **kwargs)
            assert actual_error.value.args == expected_error.args
        else:
            actual = getattr(fnx, algorithm)(actual_graph, nstart=actual_start, **kwargs)
            assert list(actual) == list(expected)
            assert actual == pytest.approx(expected, rel=1e-12, abs=1e-12)
        assert list(actual_start.items()) == list(expected_start.items()) == start_items

    def test_start_mapping_methods_are_not_replaced_by_get(
        self, fnx, nx, algorithm, graph_type
    ):
        class Start(dict):
            def get(self, *args):
                raise AssertionError("the centrality iteration does not use get")

        actual_graph, expected_graph = self._graphs(fnx, nx, graph_type)
        start = Start([(2, 3.0), (0, 1.0), (1, 2.0)])
        original_items = list(start.items())
        kwargs = {"max_iter": 1000, "tol": 1e-10, "weight": "weight"}
        expected = getattr(nx, algorithm)(expected_graph, nstart=start, **kwargs)
        actual = getattr(fnx, algorithm)(actual_graph, nstart=start, **kwargs)
        assert list(actual) == list(expected) == list(start)
        assert actual == pytest.approx(expected, rel=1e-12, abs=1e-12)
        assert list(start.items()) == original_items


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph"])
@pytest.mark.parametrize(
    "values",
    [(1, -1, 0), (10 ** 400, 2 * 10 ** 400, 3 * 10 ** 400)],
    ids=["signed-zero-sum", "huge-integer-scale"],
)
def test_eigenvector_start_normalizes_before_float_conversion(fnx, nx, graph_type, values):
    actual_graph, expected_graph = TestCentralityStartVectors._graphs(fnx, nx, graph_type)
    start = {node: values[node] for node in (2, 0, 1)}
    original_items = list(start.items())
    kwargs = {"nstart": start, "max_iter": 1000, "tol": 1e-10, "weight": "weight"}
    try:
        expected = nx.eigenvector_centrality(expected_graph, **kwargs)
    except ZeroDivisionError as expected_error:
        with pytest.raises(ZeroDivisionError) as actual_error:
            fnx.eigenvector_centrality(actual_graph, **kwargs)
        assert actual_error.value.args == expected_error.args
    else:
        actual = fnx.eigenvector_centrality(actual_graph, **kwargs)
        assert list(actual) == list(expected) == list(start)
        assert actual == pytest.approx(expected, rel=1e-12, abs=1e-12)
    assert list(start.items()) == original_items


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph"])
@pytest.mark.parametrize("algorithm", ["eigenvector_centrality", "katz_centrality"])
@pytest.mark.parametrize("weight", [None, "", 0, ("centrality", "weight")])
def test_iterative_centrality_weight_selectors(fnx, nx, graph_type, algorithm, weight):
    graphs = [getattr(module, graph_type)() for module in (fnx, nx)]
    for graph in graphs:
        for u, v, value in [(0, 1, 1.0), (1, 2, 4.0), (2, 0, 2.0)]:
            graph.add_edge(u, v)
            graph[u][v][weight] = value
    kwargs = {"weight": weight, "max_iter": 1000}
    expected = getattr(nx, algorithm)(graphs[1], **kwargs)
    actual = getattr(fnx, algorithm)(graphs[0], **kwargs)
    assert actual == pytest.approx(expected, rel=1e-12, abs=1e-12)
    if weight is None and algorithm == "katz_centrality":
        # The native default must also honor the literal None key.
        assert fnx.katz_centrality(graphs[0]) == pytest.approx(
            nx.katz_centrality(graphs[1]), rel=1e-12, abs=1e-12
        )


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph"])
@pytest.mark.parametrize("number", [Decimal, Fraction])
def test_katz_retains_exact_python_arithmetic(fnx, nx, graph_type, number):
    graphs = [getattr(module, graph_type)() for module in (fnx, nx)]
    for graph in graphs:
        for u, v in [(0, 1), (1, 2), (2, 0)]:
            graph.add_edge(u, v)
            graph[u][v]["weight"] = number("0.5")
    kwargs = {
        "alpha": number("0.1"),
        "beta": {0: number(1), 1: number(2), 2: number(3)},
        "normalized": False,
        "weight": "weight",
    }
    expected = nx.katz_centrality(graphs[1], **kwargs)
    actual = fnx.katz_centrality(graphs[0], **kwargs)
    assert actual == expected
    assert all(type(score) is number for score in actual.values())


def test_katz_can_return_integral_scores(fnx, nx):
    kwargs = {"alpha": 0, "beta": {0: 2, 1: 3}, "normalized": False}
    expected = nx.katz_centrality(nx.path_graph(2), **kwargs)
    actual = fnx.katz_centrality(fnx.path_graph(2), **kwargs)
    assert actual == expected
    assert all(type(score) is int for score in actual.values())


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph"])
def test_eigenvector_preserves_unsupported_decimal_arithmetic(fnx, nx, graph_type):
    graphs = [getattr(module, graph_type)() for module in (fnx, nx)]
    for graph in graphs:
        graph.add_edge(0, 1)
        graph[0][1]["weight"] = Decimal("0.5")
    with pytest.raises(TypeError) as expected:
        nx.eigenvector_centrality(graphs[1], weight="weight")
    with pytest.raises(TypeError) as actual:
        fnx.eigenvector_centrality(graphs[0], weight="weight")
    assert actual.value.args == expected.value.args


@pytest.mark.parametrize("algorithm", ["eigenvector_centrality", "katz_centrality"])
def test_spectral_admission_does_not_call_numeric_conversion(fnx, nx, algorithm):
    class Weight(float):
        def __float__(self):
            raise AssertionError("power iteration must use this value's arithmetic")

    graphs = [module.DiGraph([(0, 1), (1, 2), (2, 0)]) for module in (fnx, nx)]
    for graph in graphs:
        for u, v in graph.edges():
            graph[u][v]["weight"] = Weight(0.5)
    kwargs = {"weight": "weight", "max_iter": 1000}
    expected = getattr(nx, algorithm)(graphs[1], **kwargs)
    actual = getattr(fnx, algorithm)(graphs[0], **kwargs)
    assert actual == expected


@pytest.mark.parametrize("tol", [100.0, 1e-6])
def test_eigenvector_signed_cancellation_preserves_convergence(fnx, nx, tol):
    graphs = [module.DiGraph() for module in (fnx, nx)]
    for graph in graphs:
        graph.add_nodes_from(range(3))
        graph.add_weighted_edges_from([(0, 2, 1e16), (1, 2, -1e16)])
    kwargs = {
        "nstart": {0: 1.0, 1: 1.0, 2: 1.0},
        "weight": "weight",
        "max_iter": 1000,
        "tol": tol,
    }
    if tol == 1e-6:
        with pytest.raises(nx.PowerIterationFailedConvergence):
            nx.eigenvector_centrality(graphs[1], **kwargs)
        with pytest.raises(fnx.PowerIterationFailedConvergence):
            fnx.eigenvector_centrality(graphs[0], **kwargs)
    else:
        assert fnx.eigenvector_centrality(graphs[0], **kwargs) == (
            nx.eigenvector_centrality(graphs[1], **kwargs)
        )


@pytest.mark.parametrize("algorithm", ["eigenvector_centrality", "katz_centrality"])
@pytest.mark.parametrize("provider", ["native", "networkx", "filtered", "reverse", "private"])
def test_iterative_centrality_vectors_mutate_the_live_graph(fnx, nx, algorithm, provider):
    def run(module):
        root = module.DiGraph([(0, 1), (1, 2), (2, 0)])
        graph = root
        if provider == "networkx":
            root = graph = nx.DiGraph(root.edges())
        elif provider == "filtered":
            graph = module.subgraph_view(root, filter_node=lambda node: True)
        elif provider == "reverse":
            graph = root.reverse(copy=False)
        elif provider == "private":
            root = nx.DiGraph(root.edges())
            graph._adj = root._adj
            graph._succ = root._succ
            graph._pred = root._pred

        class Start(dict):
            def values(self):
                root.add_edge(0, 2)
                return super().values()

        class Beta(dict):
            def __iter__(self):
                root.add_edge(0, 2)
                return super().__iter__()

        kwargs = {"max_iter": 1000, "tol": 1e-10}
        if algorithm == "eigenvector_centrality":
            kwargs["nstart"] = Start({0: 1.0, 1: 1.0, 2: 1.0})
        else:
            kwargs["beta"] = Beta({0: 1.0, 1: 2.0, 2: 3.0})
        scores = getattr(module, algorithm)(graph, **kwargs)
        return scores, list(graph.edges())

    expected, expected_edges = run(nx)
    actual, actual_edges = run(fnx)
    assert actual == pytest.approx(expected, rel=1e-12, abs=1e-12)
    assert actual_edges == expected_edges


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph"])
@pytest.mark.parametrize("number", [Decimal, Fraction])
@pytest.mark.parametrize("workers", [1, 3])
def test_katz_many_retains_exact_python_arithmetic(fnx, nx, graph_type, number, workers):
    graphs = [getattr(module, graph_type)() for module in (fnx, nx)]
    for graph in graphs:
        for u, v in [(0, 1), (1, 2), (2, 0)]:
            graph.add_edge(u, v)
            graph[u][v]["weight"] = number("0.5")
    betas = [{node: number(node + offset) for node in range(3)} for offset in (1, 2)]
    kwargs = {"alpha": number("0.1"), "normalized": False, "weight": "weight"}
    expected = [nx.katz_centrality(graphs[1], beta=beta, **kwargs) for beta in betas]
    actual = fnx.katz_centrality_many(graphs[0], betas, workers=workers, **kwargs)
    assert actual == expected
    assert all(type(value) is number for vector in actual for value in vector.values())


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph"])
@pytest.mark.parametrize("workers", [1, 3])
def test_katz_many_can_return_integral_scores(fnx, nx, graph_type, workers):
    betas = [{0: 2, 1: 3}, {0: 4, 1: 5}]
    kwargs = {"alpha": 0, "normalized": False}
    expected = [
        nx.katz_centrality(getattr(nx, graph_type)([(0, 1)]), beta=beta, **kwargs)
        for beta in betas
    ]
    actual = fnx.katz_centrality_many(
        getattr(fnx, graph_type)([(0, 1)]), betas, workers=workers, **kwargs
    )
    assert actual == expected
    assert all(type(value) is int for vector in actual for value in vector.values())


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph"])
@pytest.mark.parametrize("weight", [None, 0, ""])
@pytest.mark.parametrize("workers", [1, 3])
def test_katz_many_preserves_literal_weight_keys(fnx, nx, graph_type, weight, workers):
    graphs = [getattr(module, graph_type)([(0, 1), (1, 2), (2, 0)]) for module in (fnx, nx)]
    for graph in graphs:
        for u, v in graph.edges():
            graph[u][v][weight] = 3.0
    betas = [1.0, {0: 1.0, 1: 2.0, 2: 3.0}]
    kwargs = {"alpha": 0.05, "weight": weight, "tol": 1e-10}
    expected = [nx.katz_centrality(graphs[1], beta=beta, **kwargs) for beta in betas]
    actual = fnx.katz_centrality_many(graphs[0], betas, workers=workers, **kwargs)
    for got, want in zip(actual, expected):
        assert list(got) == list(want)
        assert got == pytest.approx(want, rel=1e-12, abs=1e-12)


@pytest.mark.parametrize("provider", ["native", "networkx", "filtered", "reverse"])
@pytest.mark.parametrize("workers", [1, 3])
def test_katz_many_reads_beta_providers_in_query_order(fnx, nx, provider, workers):
    def outcome(module, batched):
        root = module.DiGraph([(0, 1), (1, 2), (2, 0)])
        graph = root
        if provider == "networkx":
            root = graph = nx.DiGraph(root.edges())
        elif provider == "filtered":
            graph = module.subgraph_view(root, filter_node=lambda node: True)
        elif provider == "reverse":
            graph = root.reverse(copy=False)
        events = []

        class Beta(dict):
            def __iter__(self):
                events.append("beta")
                root.add_edge(0, 2)
                return super().__iter__()

        betas = [1.0, Beta({0: 1.0, 1: 2.0, 2: 3.0}), 2.0]
        kwargs = {"alpha": 0.05, "normalized": False, "tol": 1e-10}
        if batched:
            vectors = module.katz_centrality_many(graph, betas, workers=workers, **kwargs)
        else:
            vectors = [module.katz_centrality(graph, beta=beta, **kwargs) for beta in betas]
        return vectors, list(graph.edges()), events

    actual = outcome(fnx, True)
    expected = outcome(nx, False)
    assert actual[1:] == expected[1:]
    for got, want in zip(actual[0], expected[0]):
        assert got == pytest.approx(want, rel=1e-12, abs=1e-12)


@pytest.mark.parametrize("provider", ["native", "networkx", "filtered"])
@pytest.mark.parametrize("workers", [1, 3])
def test_katz_many_advances_beta_iterators_between_queries(fnx, nx, provider, workers):
    def outcome(module, batched):
        root = module.DiGraph([(0, 1), (1, 2), (2, 0)])
        graph = root
        if provider == "networkx":
            root = graph = nx.DiGraph(root.edges())
        elif provider == "filtered":
            graph = module.subgraph_view(root, filter_node=lambda node: True)

        def betas():
            yield 1.0
            root.add_edge(2, 3)
            yield 2.0

        kwargs = {"alpha": 0.05, "normalized": False, "tol": 1e-10}
        if batched:
            return module.katz_centrality_many(graph, betas(), workers=workers, **kwargs)
        return [module.katz_centrality(graph, beta=beta, **kwargs) for beta in betas()]

    actual = outcome(fnx, True)
    expected = outcome(nx, False)
    assert list(actual[0]) == list(expected[0]) == [0, 1, 2]
    assert list(actual[1]) == list(expected[1]) == [0, 1, 2, 3]
    for got, want in zip(actual, expected):
        assert got == pytest.approx(want, rel=1e-12, abs=1e-12)


@pytest.mark.parametrize("max_iter", [0, 1])
@pytest.mark.parametrize("workers", [1, 3])
def test_katz_many_stops_consuming_queries_on_failure(fnx, nx, max_iter, workers):
    def outcome(module, batched):
        graph = module.DiGraph([(0, 1), (1, 2), (2, 0)])
        events = []

        def betas():
            events.append("first")
            yield 1.0
            events.append("second")
            yield 2.0

        with pytest.raises(module.PowerIterationFailedConvergence) as error:
            if batched:
                module.katz_centrality_many(
                    graph, betas(), workers=workers, max_iter=max_iter, tol=1e-30
                )
            else:
                [module.katz_centrality(graph, beta=beta, max_iter=max_iter, tol=1e-30)
                 for beta in betas()]
        return events, str(error.value)

    assert outcome(fnx, True) == outcome(nx, False)


@pytest.mark.parametrize("workers", [1, 3])
def test_katz_many_preserves_first_query_failure(fnx, nx, workers):
    graph = fnx.DiGraph([(0, 1), (1, 2), (2, 0)])
    with pytest.raises(nx.PowerIterationFailedConvergence):
        fnx.katz_centrality_many(
            graph, [1.0, {0: 1.0}], workers=workers, max_iter=1, tol=1e-30
        )


@pytest.mark.parametrize("missing", ["numpy", "scipy"])
@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph"])
def test_katz_many_works_without_matrix_accelerators(fnx, nx, monkeypatch, missing, graph_type):
    import builtins

    graphs = [getattr(module, graph_type)([(0, 1), (1, 2), (2, 0)]) for module in (fnx, nx)]
    betas = [1.0, {0: 1.0, 1: 2.0, 2: 3.0}]
    kwargs = {"alpha": 0.05, "tol": 1e-10, "normalized": False}
    expected = [nx.katz_centrality(graphs[1], beta=beta, **kwargs) for beta in betas]
    original_import = builtins.__import__

    def limited_import(name, *args, **kwargs):
        if name == missing or name.startswith(missing + "."):
            raise ModuleNotFoundError(f"No module named '{missing}'", name=missing)
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", limited_import)
    actual = fnx.katz_centrality_many(graphs[0], betas, workers=2, **kwargs)
    assert actual == expected


@pytest.mark.parametrize("workers", [1, 3])
def test_katz_many_plain_batches_share_one_matrix(fnx, nx, monkeypatch, workers):
    edges = [(0, 1), (1, 2), (2, 0), (0, 2)]
    betas = [1.0, {0: 1.0, 1: 2.0, 2: 3.0}]
    kwargs = {"alpha": 0.05, "tol": 1e-10, "normalized": False}
    expected = [nx.katz_centrality(nx.DiGraph(edges), beta=beta, **kwargs) for beta in betas]
    original = fnx.to_scipy_sparse_array
    calls = []

    def matrix(*args, **kwargs):
        calls.append(None)
        return original(*args, **kwargs)

    monkeypatch.setattr(fnx, "to_scipy_sparse_array", matrix)
    actual = fnx.katz_centrality_many(fnx.DiGraph(edges), betas, workers=workers, **kwargs)
    assert len(calls) == 1
    for got, want in zip(actual, expected):
        assert got == pytest.approx(want, rel=1e-12, abs=1e-12)


@pytest.mark.parametrize("workers", [1, 3])
def test_katz_many_resolves_iteration_limits_per_query(fnx, nx, workers):
    def outcome(module, batched):
        graph = module.DiGraph([(0, 1), (1, 2), (2, 0)])
        events = []

        class Iterations:
            calls = 0

            def __index__(self):
                self.calls += 1
                events.append("index")
                if self.calls == 1:
                    graph.add_edge(0, 2)
                else:
                    graph.remove_edge(0, 2)
                return 1000

        class Beta(dict):
            def __iter__(self):
                events.append("beta")
                return super().__iter__()

        betas = [Beta({0: 1.0, 1: 2.0, 2: 3.0}) for _ in range(2)]
        kwargs = {"max_iter": Iterations(), "alpha": 0.05, "normalized": False}
        if batched:
            result = module.katz_centrality_many(graph, betas, workers=workers, **kwargs)
        else:
            result = [module.katz_centrality(graph, beta=beta, **kwargs) for beta in betas]
        return result, events, list(graph.edges())

    assert outcome(fnx, True) == outcome(nx, False)


@pytest.mark.parametrize("iterator", [False, True])
def test_katz_many_empty_batch_does_not_resolve_iteration_limit(fnx, iterator):
    class Iterations:
        def __index__(self):
            raise AssertionError("an empty batch has no iteration limit to consume")

    betas = iter(()) if iterator else []
    assert fnx.katz_centrality_many(fnx.Graph(), betas, max_iter=Iterations()) == []


@pytest.mark.parametrize("workers", [1, 3])
def test_katz_many_does_not_reenter_query_iterator(fnx, nx, workers):
    def outcome(module, batched):
        graph = module.DiGraph([(0, 1), (1, 2), (2, 0)])
        events = []

        class Betas:
            entered = False
            position = 0

            def __iter__(self):
                assert not self.entered, "query iterator must not be entered twice"
                self.entered = True
                events.append("iter")
                graph.add_edge(0, 2)
                return self

            def __next__(self):
                events.append(self.position)
                if self.position == 2:
                    raise StopIteration
                self.position += 1
                return float(self.position)

        kwargs = {"alpha": 0.05, "normalized": False}
        if batched:
            vectors = module.katz_centrality_many(graph, Betas(), workers=workers, **kwargs)
        else:
            vectors = [module.katz_centrality(graph, beta=beta, **kwargs) for beta in Betas()]
        return vectors, events

    actual, actual_events = outcome(fnx, True)
    expected, expected_events = outcome(nx, False)
    assert actual_events == expected_events
    for got, want in zip(actual, expected):
        assert got == pytest.approx(want, rel=1e-12, abs=1e-12)


@pytest.mark.parametrize("workers", [1, 3])
def test_katz_many_does_not_probe_assigned_edge_provider(fnx, workers):
    def outcome(batched):
        graph = fnx.DiGraph([(0, 1), (1, 2), (2, 0)])
        edges = graph.edges
        events = []

        def provider(*args, **kwargs):
            events.append("edges")
            graph[0][1]["weight"] = 1.0 + len(events) / 10
            return edges(*args, **kwargs)

        graph.edges = provider
        betas = [1.0, {0: 1.0, 1: 2.0, 2: 3.0}]
        kwargs = {"alpha": 0.05, "weight": "weight", "normalized": False}
        if batched:
            result = fnx.katz_centrality_many(graph, betas, workers=workers, **kwargs)
        else:
            result = [fnx.katz_centrality(graph, beta=beta, **kwargs) for beta in betas]
        return result, events[:]

    expected = outcome(False)
    assert expected[1]
    assert outcome(True) == expected


@pytest.mark.parametrize("key_location", ["nodes", "beta"])
@pytest.mark.parametrize("workers", [1, 3])
def test_katz_many_does_not_probe_custom_keys(fnx, key_location, workers):
    def outcome(batched):
        events = []
        armed = False

        class Label(int):
            def __new__(cls, value, tag):
                result = int.__new__(cls, value)
                result.tag = tag
                return result

            def __hash__(self):
                if armed:
                    events.append(("hash", self.tag, int(self)))
                return int.__hash__(self)

            def __eq__(self, other):
                if armed:
                    events.append(("eq", self.tag, int(self)))
                return int.__eq__(self, other)

        nodes = [Label(node, "node") for node in range(3)] if key_location == "nodes" else list(range(3))
        graph = fnx.DiGraph([(nodes[0], nodes[1]), (nodes[1], nodes[2]), (nodes[2], nodes[0])])
        betas = [1.0, 2.0] if key_location == "nodes" else [
            {Label(node, f"beta{offset}"): float(node + offset) for node in range(3)}
            for offset in (1, 2)
        ]
        armed = True
        kwargs = {"alpha": 0.05, "normalized": False}
        if batched:
            result = fnx.katz_centrality_many(graph, betas, workers=workers, **kwargs)
        else:
            result = [fnx.katz_centrality(graph, beta=beta, **kwargs) for beta in betas]
        return result, events[:]

    expected = outcome(False)
    assert expected[1]
    assert outcome(True) == expected


@pytest.mark.parametrize("workers", [1, 3])
def test_katz_many_does_not_probe_observable_edge_keys(fnx, workers):
    def outcome(batched):
        graph = fnx.DiGraph([(0, 1), (1, 2), (2, 0)])
        events = []

        class Key:
            def __hash__(self):
                return hash(None)

            def __eq__(self, other):
                events.append(other is None)
                return self is other

        graph[0][1][Key()] = 7
        events.clear()
        betas = [1.0, {0: 1.0, 1: 2.0, 2: 3.0}]
        kwargs = {"alpha": 0.05, "normalized": False}
        if batched:
            result = fnx.katz_centrality_many(graph, betas, workers=workers, **kwargs)
        else:
            result = [fnx.katz_centrality(graph, beta=beta, **kwargs) for beta in betas]
        return result, events[:]

    expected = outcome(False)
    assert expected[1]
    assert outcome(True) == expected
