"""Conformance tests: centrality algorithms — fnx vs nx oracle."""

from decimal import Decimal
from fractions import Fraction

import pytest
from conftest import assert_dicts_close


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph"])
@pytest.mark.parametrize(
    "algorithm", ["harmonic_centrality", "betweenness_centrality", "edge_betweenness_centrality"]
)
@pytest.mark.parametrize("shape", ["subclass", "object", "tuple"])
@pytest.mark.parametrize("warm", [False, True])
@pytest.mark.parametrize("weighted", [False, True])
@pytest.mark.parametrize("action", ["add-edge", "remove-edge", "raise"])
def test_path_centrality_node_callbacks_keep_live_scores(
    fnx, nx, graph_type, algorithm, shape, warm, weighted, action
):
    def outcome(module):
        graph = getattr(module, graph_type)()
        armed = changed = False

        def callback():
            nonlocal changed
            if armed and not changed:
                changed = True
                if action == "raise":
                    raise LookupError("path centrality node callback")
                if action == "add-edge":
                    graph.add_edge(labels[0], labels[2], weight=0.5)
                else:
                    graph.remove_edge(labels[1], labels[2])

        class IntKey(int):
            def __hash__(self):
                callback()
                return int.__hash__(self)

        class ObjectKey:
            def __init__(self, value):
                self.value = value

            def __hash__(self):
                callback()
                return hash(self.value)

            def __eq__(self, other):
                return isinstance(other, ObjectKey) and self.value == other.value

        labels = [
            ObjectKey(i) if shape == "object" else (IntKey(i),) if shape == "tuple" else IntKey(i)
            for i in range(4)
        ]
        graph.add_weighted_edges_from(
            (labels[i], labels[i + 1], 1.0 + i) for i in range(3)
        )
        if warm:
            list(graph)
            list(graph.nodes)
        kwargs = {}
        if weighted:
            kwargs["distance" if algorithm == "harmonic_centrality" else "weight"] = "weight"
        armed = True
        try:
            result, failure = getattr(module, algorithm)(graph, **kwargs), None
        except Exception as exc:
            result, failure = None, (type(exc).__name__, exc.args)
        finally:
            armed = False

        def plain(node):
            if isinstance(node, ObjectKey):
                return node.value
            return int(node[0] if shape == "tuple" else node)

        values = None
        if result is not None:
            values = {
                tuple(plain(node) for node in key)
                if algorithm == "edge_betweenness_centrality" else plain(key): value
                for key, value in result.items()
            }
        topology = (
            [plain(node) for node in graph],
            [(plain(u), plain(v)) for u, v in graph.edges()],
        )
        return values, failure, changed, topology

    expected = outcome(nx)
    actual = outcome(fnx)
    assert expected[2], "the reference must exercise the node callback"
    assert actual[1:] == expected[1:]
    if action == "raise":
        assert expected[1] == ("LookupError", ("path centrality node callback",))
        assert actual[0] is None
    else:
        assert expected[1] is None
        assert list(actual[0]) == list(expected[0])
        assert actual[0] == pytest.approx(expected[0], rel=1e-12, abs=1e-12)


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph"])
@pytest.mark.parametrize("shape", ["integer", "tuple", "frozenset"])
@pytest.mark.parametrize(
    "algorithm, native_name",
    [
        ("harmonic_centrality", "_raw_harmonic_centrality"),
        ("betweenness_centrality", "_raw_betweenness_centrality"),
        ("edge_betweenness_centrality", "_raw_edge_betweenness_centrality"),
    ],
)
def test_path_centrality_stable_labels_keep_native_route(
    fnx, nx, monkeypatch, graph_type, shape, algorithm, native_name
):
    labels = [
        i if shape == "integer" else (i, "node") if shape == "tuple" else frozenset((i,))
        for i in range(4)
    ]
    graph = getattr(fnx, graph_type)()
    reference = getattr(nx, graph_type)()
    graph.add_edges_from(zip(labels, labels[1:]))
    reference.add_edges_from(zip(labels, labels[1:]))
    native = getattr(fnx, native_name)
    calls = []

    def recording_native(*args, **kwargs):
        calls.append(args[0])
        return native(*args, **kwargs)

    monkeypatch.setattr(fnx, native_name, recording_native)
    actual = getattr(fnx, algorithm)(graph)
    expected = getattr(nx, algorithm)(reference)
    assert calls == [graph]
    assert list(actual) == list(expected)
    assert actual == pytest.approx(expected, rel=1e-12, abs=1e-12)


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph"])
@pytest.mark.parametrize("shape", ["subclass", "object", "tuple"])
@pytest.mark.parametrize("warm", [False, True])
@pytest.mark.parametrize("action", ["current-edge", "later-edge", "add-node", "remove-node", "raise"])
def test_degree_centrality_node_callbacks_keep_live_scores(
    fnx, nx, graph_type, shape, warm, action
):
    def outcome(module):
        armed = changed = False
        graph = getattr(module, graph_type)()

        def callback():
            nonlocal changed
            if armed and not changed:
                changed = True
                if action == "raise":
                    raise LookupError("degree centrality node callback")
                if action == "current-edge":
                    graph.add_edge(labels[0], labels[2])
                elif action == "later-edge":
                    graph.add_edge(labels[1], labels[3])
                elif action == "add-node":
                    graph.add_node(9)
                else:
                    graph.remove_node(labels[3])

        class IntKey(int):
            def __hash__(self):
                callback()
                return int.__hash__(self)

        class ObjectKey:
            def __init__(self, value):
                self.value = value

            def __hash__(self):
                callback()
                return hash(self.value)

            def __eq__(self, other):
                return isinstance(other, ObjectKey) and self.value == other.value

        labels = [
            ObjectKey(i) if shape == "object" else (IntKey(i),) if shape == "tuple" else IntKey(i)
            for i in range(4)
        ]
        graph.add_edges_from(zip(labels, labels[1:]))
        if warm:
            list(graph)
            list(graph.degree())
        armed = True
        try:
            result, failure = module.degree_centrality(graph), None
        except Exception as exc:
            result, failure = None, (type(exc), exc.args)
        armed = False

        def plain(node):
            if isinstance(node, ObjectKey):
                return node.value
            return int(node[0] if isinstance(node, tuple) else node)

        values = None if result is None else [(plain(node), score) for node, score in result.items()]
        return values, failure, changed, [plain(node) for node in graph], [
            (plain(u), plain(v)) for u, v in graph.edges()
        ]

    expected = outcome(nx)
    actual = outcome(fnx)
    assert expected[2], "the reference must exercise the node callback"
    assert actual == expected


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


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
def test_voterank_backend_keeps_changed_view_membership(fnx, nx, graph_type, monkeypatch):
    graph = getattr(nx, graph_type)()
    graph.add_edges_from((node, node + 1) for node in range(6))
    visible = set(graph)
    view = nx.subgraph_view(graph, filter_node=visible.__contains__)
    monkeypatch.setattr(nx.config, "cache_converted_graphs", True)
    assert nx.is_tree(view, backend="franken_networkx")
    assert view.__networkx_cache__["backends"]["franken_networkx"]
    visible.remove(1)

    expected = nx.voterank(view)
    actual = nx.voterank(view, backend="franken_networkx")

    assert actual == expected
    assert all(node in visible for node in actual)


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("graph_module", ["native", "networkx"])
def test_voterank_reads_topology_after_degree_provider(fnx, nx, graph_type, graph_module):
    def make_graph(module):
        graph = getattr(module, graph_type)()
        graph.add_edges_from((node, node + 1) for node in range(5))
        name = "out_degree" if graph.is_directed() else "degree"
        degree = getattr(graph, name)

        def change_topology():
            graph.remove_edge(1, 2)
            graph.add_edges_from([(0, 3), (0, 4), (0, 5)])
            return degree()

        setattr(graph, name, change_topology)
        return graph

    expected = nx.voterank(make_graph(nx))
    actual = fnx.voterank(make_graph(fnx if graph_module == "native" else nx))

    assert expected[0] == 0
    assert actual == expected


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("route", ["native", "foreign", "backend-cold", "backend-warm"])
def test_voterank_observes_edge_provider_between_elections(
    fnx, nx, graph_type, route, monkeypatch
):
    def make_graph(module, warm=False):
        graph = getattr(module, graph_type)()
        graph.add_edges_from((node, node + 1) for node in range(6))
        if warm:
            monkeypatch.setattr(nx.config, "cache_converted_graphs", True)
            assert nx.is_tree(graph, backend="franken_networkx")
            assert graph.__networkx_cache__["backends"]["franken_networkx"]
        edges = graph.edges
        calls = []
        changed = False

        def live_edges(nbunch=None):
            nonlocal changed
            calls.append(nbunch)
            if nbunch is not None and not changed:
                changed = True
                graph.remove_edge(3, 4)
                graph.add_edges_from([(5, 0), (5, 2), (5, 3)])
            return edges(nbunch)

        graph.edges = live_edges
        return graph, calls

    reference, expected_calls = make_graph(nx)
    expected = nx.voterank(reference)
    actual_graph, actual_calls = make_graph(
        fnx if route == "native" else nx, route == "backend-warm"
    )
    if route.startswith("backend-"):
        actual = nx.voterank(actual_graph, backend="franken_networkx")
    else:
        actual = fnx.voterank(actual_graph)

    assert actual == expected
    assert actual_calls == expected_calls
    assert len([node for node in actual_calls if node is not None]) > 1


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("number_of_nodes", [None, 0, 2, 20])
def test_voterank_keeps_native_snapshot_for_ordinary_graphs(
    fnx, nx, graph_type, number_of_nodes, monkeypatch
):
    edges = [(0, 1), (1, 2), (2, 0), (1, 3), (3, 4), (4, 5), (2, 2)]
    if "Multi" in graph_type:
        edges.extend([(0, 1), (0, 1), (1, 3)])
    graph = getattr(fnx, graph_type)(edges)
    reference = getattr(nx, graph_type)(edges)
    expected = nx.voterank(reference, number_of_nodes=number_of_nodes)

    def unexpected_live_rounds(*args, **kwargs):
        raise AssertionError("ordinary native VoteRank lost its topology snapshot")

    monkeypatch.setattr(fnx, "_voterank_live_rounds", unexpected_live_rounds)
    assert fnx.voterank(graph, number_of_nodes=number_of_nodes) == expected


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
def test_voterank_node_hash_mutation_during_weakening(fnx, nx, graph_type):
    def make_graph(module):
        state = {"active": False, "hashes": 0, "mutated": False}

        class CallbackNode:
            def __hash__(self):
                if state["active"]:
                    state["hashes"] += 1
                    if state["hashes"] == 3:
                        state["mutated"] = True
                        graph.add_edges_from(("pivot", node) for node in "abcd")
                return 17

            def __repr__(self):
                return "callback"

        callback = CallbackNode()
        graph = getattr(module, graph_type)()
        graph.add_nodes_from(["hub", callback, "a", "b", "c", "d", "pivot"])
        graph.add_edges_from([
            ("hub", callback), ("hub", "a"), ("hub", "b"),
            ("a", "c"), ("b", "d"), ("c", "d"),
        ])
        edges = graph.edges

        def live_edges(nbunch=None):
            for edge in list(edges(nbunch)):
                observe = nbunch is not None and edge[1] is callback
                state["active"] = observe
                yield edge
                state["active"] = False

        graph.edges = live_edges
        return graph, state

    reference, expected_state = make_graph(nx)
    expected = nx.voterank(reference)
    graph, actual_state = make_graph(fnx)
    actual = fnx.voterank(graph)

    assert expected_state["mutated"]
    assert expected[:2] == ["hub", "pivot"]
    assert actual_state["mutated"]
    assert [repr(node) for node in actual] == [repr(node) for node in expected]


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
@pytest.mark.parametrize("normalized", [False, True])
def test_katz_beta_key_equality_precedes_live_edge_reads(fnx, nx, graph_type, normalized):
    def outcome(module):
        graph = getattr(module, graph_type)([(0, 1), (1, 2), (2, 0)])
        edge = graph[0][1]
        events = []
        armed = False

        class Key(int):
            __hash__ = int.__hash__

            def __eq__(self, other):
                if armed:
                    events.append(int(self))
                    edge["weight"] = 4.0
                return int.__eq__(self, other)

        beta = {Key(node): float(node + 1) for node in range(3)}
        armed = True
        scores = module.katz_centrality(
            graph, beta=beta, alpha=0.05, weight="weight",
            tol=1e-12, normalized=normalized,
        )
        return scores, events, edge["weight"]

    expected = outcome(nx)
    actual = outcome(fnx)
    # A matrix built before validating beta reads the old unit weight. Keep
    # both the resulting scores and every subsequent beta-key lookup live.
    assert actual == expected
    assert expected[1]
    assert expected[2] == 4.0


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph"])
def test_eigenvector_zero_start_precedes_custom_key_hashing(fnx, nx, graph_type):
    def outcome(module):
        graph = getattr(module, graph_type)([(0, 1), (1, 2), (2, 0)])
        armed = False

        class Key(int):
            def __hash__(self):
                if armed:
                    raise AssertionError("an all-zero start does not hash its keys")
                return int.__hash__(self)

        start = {Key(node): 0.0 for node in range(3)}
        armed = True
        with pytest.raises(module.NetworkXError, match="all zero") as error:
            module.eigenvector_centrality(graph, nstart=start, weight="weight")
        return error.value.args

    assert outcome(fnx) == outcome(nx)


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph"])
@pytest.mark.parametrize("algorithm", ["eigenvector_centrality", "katz_centrality"])
@pytest.mark.parametrize("label_kind", ["integer-subclass", "tuple"])
@pytest.mark.parametrize("warm", [False, True])
@pytest.mark.parametrize("weight", [None, "weight"])
def test_iterative_centrality_node_hash_updates_current_scores(
    fnx, nx, graph_type, algorithm, label_kind, warm, weight
):
    def outcome(module):
        graph = getattr(module, graph_type)()
        armed = changed = False
        plain = list(range(4))
        if label_kind == "tuple":
            plain = [(node, "node") for node in plain]

        class Node(int):
            def __hash__(self):
                nonlocal changed
                if armed and not changed:
                    changed = True
                    graph.add_edge(plain[0], plain[2], weight=0.25)
                return int.__hash__(self)

        labels = [Node(node) for node in range(4)]
        if label_kind == "tuple":
            labels = [(node, "node") for node in labels]
        graph.add_edges_from(
            (labels[node], labels[(node + 1) % 4], {"weight": 0.5})
            for node in range(4)
        )
        if warm:
            assert list(graph) == labels
        armed = True
        result = getattr(module, algorithm)(graph, weight=weight)
        scores = {
            int(node[0] if label_kind == "tuple" else node): value
            for node, value in result.items()
        }
        return scores, changed, graph.has_edge(plain[0], plain[2])

    expected, expected_changed, expected_edge = outcome(nx)
    actual, actual_changed, actual_edge = outcome(fnx)
    assert list(actual) == list(expected)
    assert actual == pytest.approx(expected, rel=1e-12, abs=1e-12)
    assert actual_changed is expected_changed is True
    assert actual_edge is expected_edge is True


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph"])
@pytest.mark.parametrize("algorithm", ["eigenvector_centrality", "katz_centrality"])
@pytest.mark.parametrize("warm", [False, True])
def test_iterative_centrality_node_hash_error_propagates(
    fnx, nx, graph_type, algorithm, warm
):
    def outcome(module):
        armed = False

        class Node(int):
            def __hash__(self):
                if armed:
                    raise LookupError("centrality node callback")
                return int.__hash__(self)

        graph = getattr(module, graph_type)()
        nodes = [Node(node) for node in range(4)]
        graph.add_edges_from(zip(nodes, nodes[1:] + nodes[:1]))
        if warm:
            list(graph)
        armed = True
        with pytest.raises(LookupError) as error:
            getattr(module, algorithm)(graph)
        armed = False
        # A callback failure must release every borrow and leave the graph
        # usable by a later computation.
        graph.add_edge(0, 2)
        result = getattr(module, algorithm)(graph)
        return error.value.args, {int(node): value for node, value in result.items()}

    expected_error, expected = outcome(nx)
    actual_error, actual = outcome(fnx)
    assert actual_error == expected_error == ("centrality node callback",)
    assert actual == pytest.approx(expected, rel=1e-12, abs=1e-12)


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph"])
@pytest.mark.parametrize("algorithm", ["eigenvector_centrality", "katz_centrality"])
@pytest.mark.parametrize("warm", [False, True])
def test_iterative_centrality_hash_resizing_nodes_keeps_iterator_error(
    fnx, nx, graph_type, algorithm, warm
):
    def outcome(module):
        graph = getattr(module, graph_type)()
        armed = changed = False

        class Node(int):
            def __hash__(self):
                nonlocal changed
                if armed and not changed:
                    changed = True
                    graph.add_node(99)
                return int.__hash__(self)

        nodes = [Node(node) for node in range(4)]
        graph.add_edges_from(zip(nodes, nodes[1:] + nodes[:1]))
        if warm:
            list(graph)
        armed = True
        with pytest.raises(RuntimeError) as error:
            getattr(module, algorithm)(graph)
        return error.value.args, changed, [int(node) for node in graph]

    actual = outcome(fnx)
    expected = outcome(nx)
    assert actual == expected
    assert actual[0] == ("dictionary changed size during iteration",)
    assert actual[1] is True
    assert actual[2] == [0, 1, 2, 3, 99]


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph"])
def test_eigenvector_zero_start_does_not_hash_graph_labels(fnx, nx, graph_type):
    def outcome(module):
        armed = False

        class Node(int):
            def __hash__(self):
                if armed:
                    raise AssertionError("zero-start validation precedes graph hashing")
                return int.__hash__(self)

        graph = getattr(module, graph_type)()
        nodes = [Node(node) for node in range(3)]
        graph.add_edges_from(zip(nodes, nodes[1:] + nodes[:1]))
        armed = True
        with pytest.raises(module.NetworkXError, match="all zero") as error:
            module.eigenvector_centrality(graph, nstart={0: 0, 1: 0, 2: 0})
        return error.value.args

    assert outcome(fnx) == outcome(nx)


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph"])
@pytest.mark.parametrize("algorithm", ["eigenvector_centrality", "katz_centrality"])
@pytest.mark.parametrize("max_iter", [None, 0], ids=["defaults", "zero-iterations"])
def test_iterative_centrality_keeps_class_node_iterator_overrides(
    fnx, nx, monkeypatch, graph_type, algorithm, max_iter
):
    def outcome(module):
        graph_class = getattr(module, graph_type)
        graph = graph_class([(0, 1), (1, 2), (2, 3), (3, 0)])
        original_iter = graph_class.__iter__
        events = []

        def changed_iter(current):
            if current is graph:
                events.append("iter")
                current.add_edge(0, 2)
            return original_iter(current)

        # Restore each module's class independently: graph construction and
        # the oracle must not inherit another call's iterator replacement.
        with monkeypatch.context() as patch:
            patch.setattr(graph_class, "__iter__", changed_iter)
            if max_iter == 0:
                with pytest.raises(module.PowerIterationFailedConvergence) as error:
                    getattr(module, algorithm)(graph, max_iter=max_iter)
                result = str(error.value)
            else:
                result = getattr(module, algorithm)(graph)
        return result, events, graph.has_edge(0, 2)

    expected, expected_events, expected_edge = outcome(nx)
    actual, actual_events, actual_edge = outcome(fnx)
    if max_iter == 0:
        assert actual == expected
    else:
        assert list(actual) == list(expected)
        assert actual == pytest.approx(expected, rel=1e-12, abs=1e-12)
    assert actual_events == expected_events == ["iter"] * (
        1 if algorithm == "eigenvector_centrality" else 2
    )
    assert actual_edge is expected_edge is True


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph"])
@pytest.mark.parametrize("algorithm", ["eigenvector_centrality", "katz_centrality"])
def test_iterative_centrality_builtin_labels_keep_native_route(
    fnx, nx, monkeypatch, graph_type, algorithm
):
    nodes = [0, "node", ("tuple", 1), frozenset({"left", "right"})]
    actual_graph = getattr(fnx, graph_type)()
    expected_graph = getattr(nx, graph_type)()
    for graph in (actual_graph, expected_graph):
        graph.add_edges_from(zip(nodes, nodes[1:] + nodes[:1]))
    raw_name = f"_raw_{algorithm}"
    native_solver = getattr(fnx, raw_name)
    calls = []

    def tracked_raw(graph, *args, **kwargs):
        calls.append(graph)
        return native_solver(graph, *args, **kwargs)

    monkeypatch.setattr(fnx, raw_name, tracked_raw)
    actual = getattr(fnx, algorithm)(actual_graph)
    expected = getattr(nx, algorithm)(expected_graph)
    assert actual == pytest.approx(expected, rel=1e-12, abs=1e-12)
    assert calls == [actual_graph]


@pytest.mark.parametrize("algorithm", ["eigenvector_centrality", "katz_centrality"])
@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph"])
@pytest.mark.parametrize("weight", [None, "weight"])
def test_iterative_centrality_reads_assigned_node_count_live(
    fnx, nx, algorithm, graph_type, weight
):
    def outcome(module):
        graph = getattr(module, graph_type)()
        graph.add_weighted_edges_from(
            [(0, 1, 0.5), (1, 2, 0.25), (2, 3, 0.75), (3, 0, 0.5)]
        )
        events = []

        def node_count():
            events.append("number_of_nodes")
            graph.add_edge(0, 2, weight=0.125)
            return len(graph)

        graph.number_of_nodes = node_count
        result = getattr(module, algorithm)(graph, weight=weight)
        return result, events, graph.has_edge(0, 2)

    expected, expected_events, expected_edge = outcome(nx)
    actual, actual_events, actual_edge = outcome(fnx)
    assert list(actual) == list(expected)
    assert actual == pytest.approx(expected, rel=1e-12, abs=1e-12)
    assert actual_events == expected_events == ["number_of_nodes"]
    assert actual_edge is expected_edge is True


@pytest.mark.parametrize("algorithm", ["eigenvector_centrality", "katz_centrality"])
@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph"])
@pytest.mark.parametrize("reader", ["number_of_nodes", "__getitem__"])
@pytest.mark.parametrize("action", ["edge", "error"])
@pytest.mark.parametrize("weight", [None, "weight"])
@pytest.mark.parametrize("warm", [False, True])
def test_iterative_centrality_class_readers_keep_live_effects(
    fnx, nx, monkeypatch, algorithm, graph_type, reader, action, weight, warm
):
    def outcome(module):
        graph_class = getattr(module, graph_type)
        graph = graph_class()
        graph.add_weighted_edges_from(
            [(0, 1, 0.5), (1, 2, 0.25), (2, 3, 0.75), (3, 0, 0.5)]
        )
        if warm:
            getattr(module, algorithm)(graph, weight=weight)
        original = getattr(graph_class, reader)
        events = []

        def provider(current, *args):
            if current is graph:
                events.append((reader, args))
                if len(events) == 1:
                    if action == "error":
                        raise LookupError("class centrality provider")
                    current.add_edge(0, 2, weight=0.125)
            return original(current, *args)

        with monkeypatch.context() as patch:
            patch.setattr(graph_class, reader, provider)
            if module is fnx:
                fnx._spectral_centrality_can_snapshot(graph, None, weight)
                assert events == []
                assert not graph.has_edge(0, 2)
            if action == "error":
                with pytest.raises(LookupError) as error:
                    getattr(module, algorithm)(graph, weight=weight)
                result = error.value.args
            else:
                result = getattr(module, algorithm)(graph, weight=weight)
        return result, events, graph.has_edge(0, 2)

    expected, expected_events, expected_edge = outcome(nx)
    actual, actual_events, actual_edge = outcome(fnx)
    if action == "error":
        assert actual == expected == ("class centrality provider",)
    else:
        assert list(actual) == list(expected)
        assert actual == pytest.approx(expected, rel=1e-12, abs=1e-12)
    assert actual_events == expected_events
    assert expected_events
    assert actual_edge is expected_edge is (action == "edge")


@pytest.mark.parametrize("algorithm", ["eigenvector_centrality", "katz_centrality"])
@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph"])
def test_iterative_centrality_does_not_probe_class_edge_descriptors(
    fnx, nx, monkeypatch, algorithm, graph_type
):
    def outcome(module):
        graph_class = getattr(module, graph_type)
        graph = graph_class()
        graph.add_weighted_edges_from(
            [(0, 1, 0.5), (1, 2, 0.25), (2, 3, 0.75), (3, 0, 0.5)]
        )

        def edges(current):
            raise AssertionError("power iteration does not read the edges descriptor")

        with monkeypatch.context() as patch:
            patch.setattr(graph_class, "edges", property(edges))
            if module is fnx:
                fnx._spectral_centrality_can_snapshot(graph, None, "weight")
            return getattr(module, algorithm)(graph, weight="weight")

    assert outcome(fnx) == pytest.approx(outcome(nx), rel=1e-12, abs=1e-12)


@pytest.mark.parametrize("algorithm", ["eigenvector_centrality", "katz_centrality"])
@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph"])
def test_iterative_centrality_does_not_read_assigned_edge_provider(
    fnx, nx, algorithm, graph_type
):
    def outcome(module):
        graph = getattr(module, graph_type)()
        graph.add_weighted_edges_from(
            [(0, 1, 0.5), (1, 2, 0.25), (2, 3, 0.75), (3, 0, 0.5)]
        )

        def edges(*args, **kwargs):
            raise AssertionError("power iteration reads adjacency, not edges")

        graph.edges = edges
        return getattr(module, algorithm)(graph, weight="weight")

    expected = outcome(nx)
    actual = outcome(fnx)
    assert list(actual) == list(expected)
    assert actual == pytest.approx(expected, rel=1e-12, abs=1e-12)


@pytest.mark.parametrize("algorithm", ["eigenvector_centrality", "katz_centrality"])
@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph"])
def test_iterative_centrality_retains_overridden_edge_reads(
    fnx, nx, monkeypatch, algorithm, graph_type
):
    expected_reads = []
    actual_reads = []

    class EdgeAttrs(dict):
        __slots__ = ()

        def get(self, key, default=None):
            expected_reads.append(key)
            return dict.get(self, key, default)

    expected_graph = getattr(nx, graph_type)()
    expected_graph.edge_attr_dict_factory = EdgeAttrs
    actual_graph = getattr(fnx, graph_type)()
    for graph in (expected_graph, actual_graph):
        graph.add_weighted_edges_from(
            [(0, 1, 0.5), (1, 2, 0.25), (2, 3, 0.75), (3, 0, 0.5)]
        )
    rows = [data for _, _, data in actual_graph.edges(data=True)]

    def tracked_get(data, key, default=None):
        actual_reads.append(key)
        return dict.get(data, key, default)

    for cls in {type(row) for row in rows}:
        monkeypatch.setattr(cls, "get", tracked_get)

    expected = getattr(nx, algorithm)(expected_graph, weight="weight")
    actual = getattr(fnx, algorithm)(actual_graph, weight="weight")
    assert actual == expected
    assert actual_reads == expected_reads
    assert expected_reads


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
def test_katz_many_does_not_probe_assigned_edge_provider(fnx, nx, workers):
    def outcome(module, batched):
        graph = module.DiGraph([(0, 1), (1, 2), (2, 0)])
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
            result = module.katz_centrality_many(graph, betas, workers=workers, **kwargs)
        else:
            result = [module.katz_centrality(graph, beta=beta, **kwargs) for beta in betas]
        return result, events[:]

    expected = outcome(fnx, False)
    reference = outcome(nx, False)
    assert expected[1] == reference[1] == []
    for actual, wanted in zip(expected[0], reference[0]):
        assert actual == pytest.approx(wanted, rel=1e-12, abs=1e-12)
    assert outcome(fnx, True) == expected


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph"])
@pytest.mark.parametrize("workers", [1, 3])
@pytest.mark.parametrize("warm", [False, True])
def test_katz_many_node_hash_mutations_reach_current_query(
    fnx, nx, graph_type, workers, warm
):
    def outcome(module, batched):
        graph = getattr(module, graph_type)()
        armed = changed = False

        class Node(int):
            def __hash__(self):
                nonlocal changed
                if armed and not changed:
                    changed = True
                    graph.add_edge(0, 2, weight=0.25)
                return int.__hash__(self)

        nodes = [Node(node) for node in range(4)]
        graph.add_edges_from(
            (nodes[node], nodes[(node + 1) % 4], {"weight": 0.5})
            for node in range(4)
        )
        if warm:
            list(graph)
        armed = True
        betas = [1.0, 2.0]
        kwargs = {"alpha": 0.05, "weight": "weight", "normalized": False}
        if batched:
            vectors = module.katz_centrality_many(graph, betas, workers=workers, **kwargs)
        else:
            vectors = [module.katz_centrality(graph, beta=beta, **kwargs) for beta in betas]
        scores = [{int(node): value for node, value in vector.items()} for vector in vectors]
        return scores, changed

    actual, changed = outcome(fnx, True)
    expected, reference_changed = outcome(nx, False)
    assert changed is reference_changed is True
    assert len(actual) == len(expected) == 2
    for result, wanted in zip(actual, expected):
        assert list(result) == list(wanted)
        assert result == pytest.approx(wanted, rel=1e-12, abs=1e-12)


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


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph"])
@pytest.mark.parametrize("algorithm", ["eigenvector_centrality", "katz_centrality"])
@pytest.mark.parametrize("mutation", ["edge", "error", "resize"])
@pytest.mark.parametrize("instance_shadow", [False, True])
def test_iterative_centrality_inherited_iterator_keeps_node_callbacks(
    fnx, nx, graph_type, algorithm, mutation, instance_shadow
):
    def outcome(module):
        base = getattr(module, graph_type)

        class ParentGraph(base):
            def _fnx_unhashed_node_iter(self):
                raise AssertionError("private helpers do not override public iteration")

        class InheritedGraph(ParentGraph):
            pass

        graph = InheritedGraph()
        armed = fired = False

        class Node(int):
            def __hash__(self):
                nonlocal fired
                if armed and not fired:
                    fired = True
                    if mutation == "error":
                        raise LookupError("inherited centrality node callback")
                    if mutation == "resize":
                        graph.add_node(99)
                    else:
                        graph.add_edge(0, 2)
                return int.__hash__(self)

        nodes = [Node(node) for node in range(4)]
        graph.add_edges_from(zip(nodes, nodes[1:] + nodes[:1]))
        if instance_shadow:
            def instance_iterator():
                raise AssertionError("iter(G) ignores instance-only __iter__")

            graph.__iter__ = instance_iterator
        armed = True
        scores = failure = None
        try:
            result = getattr(module, algorithm)(graph)
            scores = {int(node): score for node, score in result.items()}
        except (LookupError, RuntimeError) as error:
            failure = (type(error).__name__, error.args)
        finally:
            armed = False
        return scores, failure, fired, list(map(int, graph)), graph.has_edge(0, 2)

    expected = outcome(nx)
    actual = outcome(fnx)
    assert actual[1:] == expected[1:]
    assert expected[2] is True
    if mutation == "edge":
        assert actual[1] is None
        assert list(actual[0]) == list(expected[0])
        assert actual[0] == pytest.approx(expected[0], rel=1e-12, abs=1e-12)
        assert actual[4] is True
    elif mutation == "error":
        assert actual[1] == (
            "LookupError", ("inherited centrality node callback",)
        )
    else:
        assert actual[1] == (
            "RuntimeError", ("dictionary changed size during iteration",)
        )
        assert actual[3] == [0, 1, 2, 3, 99]


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph"])
@pytest.mark.parametrize("algorithm", ["eigenvector_centrality", "katz_centrality"])
def test_iterative_centrality_preserves_subclass_iterator_descriptor(
    fnx, nx, graph_type, algorithm
):
    def outcome(module):
        base = getattr(module, graph_type)
        original_iter = base.__iter__
        events = []

        class PublicIterator:
            def __get__(self, instance, owner=None):
                if instance is None:
                    raise AssertionError("admission must not bind an iterator descriptor")

                def iterate():
                    events.append("iter")
                    instance.add_edge(0, 2)
                    return original_iter(instance)

                return iterate

        class GraphSubclass(base):
            __iter__ = PublicIterator()

        graph = GraphSubclass()
        graph.add_edges_from([(0, 1), (1, 2), (2, 3), (3, 0)])
        result = getattr(module, algorithm)(graph)
        return result, events, graph.has_edge(0, 2)

    expected, expected_events, expected_edge = outcome(nx)
    actual, actual_events, actual_edge = outcome(fnx)
    assert list(actual) == list(expected)
    assert actual == pytest.approx(expected, rel=1e-12, abs=1e-12)
    assert actual_events == expected_events
    assert expected_events
    assert actual_edge is expected_edge is True


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph"])
@pytest.mark.parametrize("algorithm", ["eigenvector_centrality", "katz_centrality"])
def test_iterative_centrality_subclass_uses_assigned_node_storage(
    fnx, nx, graph_type, algorithm
):
    def outcome(module):
        base = getattr(module, graph_type)

        class GraphSubclass(base):
            pass

        graph = GraphSubclass([(0, 1), (1, 2), (2, 3), (3, 0)])
        # Preserve adjacency but reorder the logical node store. Native keys
        # retain the old order and must not replace this assigned reader.
        graph._node = {node: {} for node in (3, 2, 1, 0)}
        return getattr(module, algorithm)(graph)

    expected = outcome(nx)
    actual = outcome(fnx)
    assert list(actual) == list(expected) == [3, 2, 1, 0]
    assert actual == pytest.approx(expected, rel=1e-12, abs=1e-12)


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph"])
@pytest.mark.parametrize("reader", ["getattribute", "dict-property"])
def test_spectral_node_iteration_does_not_probe_subclass_storage(
    fnx, nx, graph_type, reader
):
    import inspect

    for module in (nx, fnx):
        base = getattr(module, graph_type)
        native_dict = inspect.getattr_static(base, "__dict__")
        armed = False
        events = []

        if reader == "getattribute":
            class GraphSubclass(base):
                def __getattribute__(self, name):
                    if armed and name == "__dict__":
                        events.append("dict")
                        raise AssertionError("iteration must not probe subclass storage")
                    return super().__getattribute__(name)
        else:
            class GraphSubclass(base):
                @property
                def __dict__(self):
                    if armed:
                        events.append("dict")
                        raise AssertionError("iteration must not probe subclass storage")
                    return native_dict.__get__(self, type(self))

        graph = GraphSubclass()
        graph.add_nodes_from([0, 1, 2])
        armed = True
        iterator = (
            module._spectral_centrality_nodes(graph)
            if module is fnx else iter(graph)
        )
        assert list(iterator) == [0, 1, 2]
        assert events == []
