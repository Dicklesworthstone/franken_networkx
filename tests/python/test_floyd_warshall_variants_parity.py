"""Differential parity for Floyd-Warshall variants.

Covers ``floyd_warshall_numpy`` (dense distance matrix) and
``floyd_warshall_predecessor_and_distance`` (predecessor + distance
dicts). Neither had a dedicated test file.

Graphs are oriented low->high index so they stay acyclic (no negative
cycle), keeping the all-pairs distances well-defined even with negative
edge weights.

br-r37-c1-hykcx
"""

from __future__ import annotations

import random

import numpy as np
import pytest
import networkx as nx
import franken_networkx as fnx
import franken_networkx.algorithms as fnx_algorithms


def _valid_pair(seed, negatives=True):
    rng = random.Random(seed)
    n = rng.randint(4, 8)
    fg = fnx.DiGraph()
    ng = nx.DiGraph()
    fg.add_nodes_from(range(n))
    ng.add_nodes_from(range(n))
    for u in range(n):
        for v in range(u + 1, n):  # acyclic -> no negative cycle
            if rng.random() < 0.5:
                w = rng.randint(-3, 9) if negatives else rng.randint(1, 9)
                fg.add_edge(u, v, weight=w)
                ng.add_edge(u, v, weight=w)
    return fg, ng, n


@pytest.mark.parametrize("seed", range(50))
def test_floyd_warshall_numpy_matches_networkx(seed):
    fg, ng, _ = _valid_pair(seed)
    assert np.allclose(
        np.asarray(fnx.floyd_warshall_numpy(fg)),
        np.asarray(nx.floyd_warshall_numpy(ng)),
        equal_nan=True,
    )


@pytest.mark.parametrize("seed", range(50))
def test_floyd_warshall_predecessor_and_distance_matches_networkx(seed):
    fg, ng, _ = _valid_pair(seed)
    _, fdist = fnx.floyd_warshall_predecessor_and_distance(fg)
    _, ndist = nx.floyd_warshall_predecessor_and_distance(ng)
    # Distances are the well-defined invariant; predecessor choices are not
    # unique when multiple shortest paths tie, so only distances are compared.
    assert {u: dict(d) for u, d in fdist.items()} == {
        u: dict(d) for u, d in ndist.items()
    }


def test_floyd_warshall_goldens():
    g = fnx.DiGraph()
    ng = nx.DiGraph()
    for u, v, w in [(0, 1, 1), (1, 2, 2), (0, 2, 5)]:
        g.add_edge(u, v, weight=w)
        ng.add_edge(u, v, weight=w)
    _, dist = fnx.floyd_warshall_predecessor_and_distance(g)
    # 0->1->2 (cost 3) beats the direct 0->2 (cost 5).
    assert dist[0][2] == 3
    assert {u: dict(d) for u, d in dist.items()} == {
        u: dict(d) for u, d in nx.floyd_warshall_predecessor_and_distance(ng)[1].items()
    }


def _parallel_pair(seed, cls):
    rng = random.Random(seed)
    n = rng.randint(4, 8)
    graphs = (getattr(fnx, cls)(), getattr(nx, cls)())
    for graph in graphs:
        graph.add_nodes_from(range(n))
    for _ in range(3 * n):
        u, v = sorted(rng.sample(range(n), 2))
        w = rng.randint(1, 9)
        for graph in graphs:
            graph.add_edge(u, v, weight=w)
    return graphs


@pytest.mark.parametrize("cls", ["MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("seed", range(20))
def test_floyd_warshall_numpy_takes_the_lightest_parallel_edge(seed, cls):
    # br-r37-c1-545ld: networkx builds the matrix with multigraph_weight=min;
    # fnx summed parallel edges (dist 1.5 came back 5.5 on a doubled pair)
    fg, ng = _parallel_pair(seed, cls)
    assert np.array_equal(fnx.floyd_warshall_numpy(fg), nx.floyd_warshall_numpy(ng))
    nodelist = list(reversed(list(ng)))
    assert np.array_equal(
        fnx.floyd_warshall_numpy(fg, nodelist=nodelist),
        nx.floyd_warshall_numpy(ng, nodelist=nodelist),
    )


def _floyd_distance_state(distances):
    # Preserve ordering, scalar types, signed infinities, and NaNs without
    # treating NaN's intentionally unequal comparison as a parity failure.
    return [
        (
            source,
            [
                (target, type(value), value.hex() if type(value) is float else value)
                for target, value in row.items()
            ],
        )
        for source, row in distances.items()
    ]


@pytest.mark.parametrize("kind", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("mode", ["strict", "hardened"])
@pytest.mark.parametrize("namespace", [fnx, fnx_algorithms])
@pytest.mark.parametrize(
    "edges",
    [
        pytest.param([(0, 0, -2), (0, 1, 3), (1, 2, 1)], id="negative-self-loop-int"),
        pytest.param([(0, 0, -2.0), (0, 1, 3.0), (1, 2, 1.0)], id="negative-self-loop-float"),
        pytest.param([(0, 1, -2), (1, 0, 1), (1, 2, 3)], id="negative-cycle-int"),
        pytest.param([(0, 1, -2.0), (1, 0, 1.0), (1, 2, 3.0)], id="negative-cycle-float"),
        pytest.param([(0, 1, -float("inf")), (1, 2, 1.0)], id="negative-infinity"),
        pytest.param([(0, 1, float("nan")), (1, 2, 1.0)], id="nan-edge"),
        pytest.param([(0, 1, float("inf")), (1, 2, 1.0)], id="positive-infinity"),
        pytest.param([(0, 1, -2.0), (1, 2, 3.0), (0, 2, 4.0)], id="finite-weights"),
        pytest.param([(0, 2, -1e308), (2, 1, -1e308)], id="finite-underflow"),
    ],
)
def test_floyd_warshall_dictionary_numeric_contract(kind, mode, namespace, edges):
    graphs = [getattr(module, kind)() for module in (fnx, nx)]
    for graph in graphs:
        # The isolated node exposes NaNs propagated into unreachable rows.
        graph.add_nodes_from(range(4))
        for source, target, value in edges:
            graph.add_edge(source, target, cost=value)
    expected = nx.floyd_warshall(graphs[1], weight="cost")
    with fnx.compatibility_mode(mode):
        actual = namespace.floyd_warshall(graphs[0], weight="cost")
    assert _floyd_distance_state(actual) == _floyd_distance_state(expected)


@pytest.mark.parametrize("scalar", [int, float])
@pytest.mark.parametrize("graph_module", [fnx, nx])
def test_floyd_warshall_finite_negative_dag_keeps_matrix_route(monkeypatch, scalar, graph_module):
    graphs = [module.DiGraph() for module in (graph_module, nx)]
    for graph in graphs:
        graph.add_nodes_from(range(4))
        for source, target, value in [(0, 1, -2), (1, 2, 3), (0, 2, 4)]:
            graph.add_edge(source, target, cost=scalar(value))
        # Ordinary cached views must remain eligible for acceleration.
        list(graph.nodes)
        list(graph.edges)
    namespace = fnx.floyd_warshall.__globals__
    matrix_solver = namespace["_floyd_warshall_numpy"]
    calls = []

    def record_matrix(graph, weight):
        calls.append(graph)
        return matrix_solver(graph, weight)

    def reject_fallback(*args, **kwargs):
        raise AssertionError("Finite negative DAG unnecessarily left the matrix route")

    monkeypatch.setitem(namespace, "_floyd_warshall_numpy", record_matrix)
    monkeypatch.setitem(
        namespace, "_floyd_warshall_predecessor_and_distance_inproc", reject_fallback
    )
    actual = fnx.floyd_warshall(graphs[0], weight="cost")
    expected = nx.floyd_warshall(graphs[1], weight="cost")
    assert calls == [graphs[0]]
    assert _floyd_distance_state(actual) == _floyd_distance_state(expected)


@pytest.mark.parametrize("base", [int, float])
@pytest.mark.parametrize("kind", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("namespace", [fnx, fnx_algorithms])
def test_floyd_warshall_preserves_numeric_subclass_arithmetic(base, kind, namespace):
    class OffsetWeight(base):
        def __add__(self, other):
            return base(self) + other + 100

        def __radd__(self, other):
            return other + base(self) + 100

    graphs = [getattr(module, kind)() for module in (fnx, nx)]
    for graph in graphs:
        graph.add_edge("source", "middle", cost=OffsetWeight(2))
        graph.add_edge("middle", "target", cost=OffsetWeight(2))
        graph.add_edge("source", "target", cost=base(5))

    expected = nx.floyd_warshall(graphs[1], weight="cost")
    actual = namespace.floyd_warshall(graphs[0], weight="cost")
    # Float coercion would choose the two-edge route (4), while the caller's
    # addition makes the direct edge (5) shorter. Direct distances also retain
    # their original scalar subclass, not only their numeric equality.
    assert expected["source"]["target"] == 5
    assert _floyd_distance_state(actual) == _floyd_distance_state(expected)


@pytest.mark.parametrize("base", [int, float])
@pytest.mark.parametrize("namespace", [fnx, fnx_algorithms])
def test_floyd_warshall_preserves_numeric_subclass_errors(base, namespace):
    class InvalidWeight(base):
        def __add__(self, other):
            raise ArithmeticError("custom edge-weight addition")

        def __radd__(self, other):
            raise ArithmeticError("custom edge-weight addition")

    for module, algorithms in ((nx, nx), (fnx, namespace)):
        graph = module.DiGraph()
        graph.add_edge(0, 1, cost=InvalidWeight(2))
        with pytest.raises(ArithmeticError, match="custom edge-weight addition"):
            algorithms.floyd_warshall(graph, weight="cost")


@pytest.mark.parametrize("namespace", [fnx, fnx_algorithms])
@pytest.mark.parametrize("kind", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("algorithm", ["floyd_warshall", "floyd_warshall_predecessor_and_distance"])
def test_floyd_warshall_uses_original_public_weight_provider(namespace, kind, algorithm):
    outcomes = []
    for algorithms in (nx, namespace):
        reads = []

        class WeightData(dict):
            def get(self, key, default=None):
                reads.append((key, default))
                return super().get(key, default) + 10

        class PublicGraph(getattr(nx, kind)):
            edge_attr_dict_factory = WeightData

            @property
            def nodes(self):
                raise AssertionError("Floyd-Warshall exported input node attributes")

        graph = PublicGraph()
        graph.add_edge(0, 1, cost=2)
        graph.add_edge(1, 2, cost=3)
        result = getattr(algorithms, algorithm)(graph, weight="cost")
        if algorithm == "floyd_warshall_predecessor_and_distance":
            predecessors, distances = result
        else:
            predecessors, distances = None, result
        outcomes.append((predecessors, _floyd_distance_state(distances), reads))
        assert distances[0][2] == 25
    assert outcomes[0] == outcomes[1]


@pytest.mark.parametrize("namespace", [fnx, fnx_algorithms])
@pytest.mark.parametrize("algorithm", ["floyd_warshall", "floyd_warshall_predecessor_and_distance"])
def test_floyd_warshall_admission_does_not_call_weight_read_descriptors(namespace, algorithm):
    outcomes = []
    for algorithms in (nx, namespace):
        reads = []

        class WeightGetter:
            def __get__(self, instance, owner):
                if instance is None:
                    raise AssertionError("admission invoked a user descriptor")

                def read(key, default=None):
                    reads.append((key, default))
                    return dict.get(instance, key, default) + 10

                return read

        class WeightData(dict):
            __slots__ = ()
            get = WeightGetter()

        graph = nx.DiGraph()
        graph.add_edge(0, 1, cost=2)
        graph.add_edge(1, 2, cost=3)
        for source, target in graph.edges:
            attrs = WeightData(graph._succ[source][target])
            graph._succ[source][target] = attrs
            graph._pred[target][source] = attrs
        result = getattr(algorithms, algorithm)(graph, weight="cost")
        distances = result[1] if algorithm == "floyd_warshall_predecessor_and_distance" else result
        outcomes.append((_floyd_distance_state(distances), reads))
        assert distances[0][2] == 25
    assert outcomes[0] == outcomes[1]


@pytest.mark.parametrize("namespace", [fnx, fnx_algorithms])
@pytest.mark.parametrize("inherited", [False, True])
@pytest.mark.parametrize("algorithm", ["floyd_warshall", "floyd_warshall_predecessor_and_distance"])
def test_floyd_warshall_retains_instance_weight_read_overrides(namespace, inherited, algorithm):
    class WeightData(dict):
        pass

    class SlottedChild(WeightData):
        __slots__ = ()

    attr_class = SlottedChild if inherited else WeightData
    outcomes = []
    for algorithms in (nx, namespace):
        reads = []
        graph = nx.DiGraph()
        graph.add_edge(0, 1, cost=2)
        graph.add_edge(1, 2, cost=3)
        for source, target in graph.edges:
            attrs = attr_class(graph._succ[source][target])

            def read(key, default=None, data=attrs):
                reads.append((key, default))
                return dict.get(data, key, default) + 10

            attrs.get = read
            graph._succ[source][target] = attrs
            graph._pred[target][source] = attrs
        result = getattr(algorithms, algorithm)(graph, weight="cost")
        distances = result[1] if algorithm == "floyd_warshall_predecessor_and_distance" else result
        outcomes.append((_floyd_distance_state(distances), reads))
        assert distances[0][2] == 25
    assert outcomes[0] == outcomes[1]


@pytest.mark.parametrize("namespace", [fnx, fnx_algorithms])
@pytest.mark.parametrize("kind", ["Graph", "DiGraph"])
@pytest.mark.parametrize("shadow", ["edges", "nodes", "is_directed"])
@pytest.mark.parametrize("algorithm", ["floyd_warshall", "floyd_warshall_predecessor_and_distance"])
def test_floyd_warshall_keeps_exact_graph_instance_providers(namespace, kind, shadow, algorithm):
    outcomes = []
    for algorithms in (nx, namespace):
        graph = getattr(nx, kind)()
        graph.add_edge(0, 1, cost=2)
        graph.add_edge(1, 2, cost=3)
        reads = []
        if shadow == "edges":
            original_edges = graph.edges

            def edges(*args, **kwargs):
                reads.append(("edges", args, kwargs))
                if len(reads) > 1:
                    raise AssertionError("the edge provider was consumed more than once")
                return original_edges(*args, **kwargs)

            graph.edges = edges
        elif shadow == "is_directed":
            original_is_directed = graph.is_directed

            def is_directed():
                reads.append("is_directed")
                return original_is_directed()

            graph.is_directed = is_directed
        else:
            # The dictionary API iterates the graph, never its node view.
            graph.nodes = object()
        result = getattr(algorithms, algorithm)(graph, weight="cost")
        distances = result[1] if algorithm == "floyd_warshall_predecessor_and_distance" else result
        outcomes.append((_floyd_distance_state(distances), reads))
        assert distances[0][2] == 5
    assert outcomes[0] == outcomes[1]


@pytest.mark.parametrize("cached", [False, True])
@pytest.mark.parametrize("kind", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("algorithm", ["floyd_warshall", "floyd_warshall_predecessor_and_distance"])
def test_floyd_warshall_backend_retains_public_weight_provider(cached, kind, algorithm, monkeypatch):
    monkeypatch.setattr(nx.config, "cache_converted_graphs", True)
    outcomes = []
    for backend in ("networkx", "franken_networkx"):
        reads = []

        class WeightData(dict):
            def get(self, key, default=None):
                reads.append((key, default))
                return super().get(key, default) + 10

        class PublicGraph(getattr(nx, kind)):
            edge_attr_dict_factory = WeightData

        graph = PublicGraph()
        graph.add_edge(0, 1, cost=2)
        graph.add_edge(1, 2, cost=3)
        if cached and backend == "franken_networkx":
            nx.relabel_nodes(graph, {}, backend=backend)
            assert graph.__networkx_cache__["backends"][backend]
        reads.clear()
        result = getattr(nx, algorithm)(graph, weight="cost", backend=backend)
        distances = result[1] if algorithm == "floyd_warshall_predecessor_and_distance" else result
        outcomes.append((_floyd_distance_state(distances), reads))
        assert distances[0][2] == 25
    assert outcomes[0] == outcomes[1]


@pytest.mark.parametrize("kind", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize(
    "edges",
    [
        pytest.param([(0, 1, 0.0), (1, 2, 3.0)], id="zero-weight"),
        pytest.param([(0, 1, -0.0), (1, 2, 0.0)], id="signed-zero"),
        pytest.param([(0, 1, -2), (1, 2, 3)], id="negative-edge"),
        pytest.param([(0, 1, -2), (1, 0, 1)], id="negative-cycle"),
        pytest.param([(0, 0, -2), (0, 1, 3)], id="negative-self-loop"),
        pytest.param([(0, 1, float("nan"))], id="nan-edge"),
        pytest.param([(0, 1, float("inf"))], id="positive-infinity"),
        pytest.param([(0, 1, -float("inf"))], id="negative-infinity"),
        pytest.param([(0, 1, 1e308), (1, 2, 1e308)], id="finite-overflow"),
        pytest.param([(0, 1, -1e308), (1, 2, -1e308)], id="finite-underflow"),
    ],
)
def test_dense_floyd_warshall_numpy_numeric_contract(kind, edges):
    graphs = [getattr(module, kind)() for module in (fnx, nx)]
    for graph in graphs:
        graph.add_nodes_from(range(4))
        graph.add_weighted_edges_from(edges, weight="cost")
    with np.errstate(over="ignore", invalid="ignore"):
        actual = fnx.floyd_warshall_numpy(graphs[0], weight="cost")
        expected = nx.floyd_warshall_numpy(graphs[1], weight="cost")
    np.testing.assert_array_equal(actual, expected)
    zero_cells = expected == 0
    np.testing.assert_array_equal(np.signbit(actual[zero_cells]), np.signbit(expected[zero_cells]))


@pytest.mark.parametrize("kind", ["Graph", "DiGraph"])
@pytest.mark.parametrize("value", [float("nan"), -float("inf"), 1e308])
def test_dense_floyd_warshall_obeys_numpy_error_policy(kind, value):
    outcomes = []
    for module in (fnx, nx):
        graph = getattr(module, kind)()
        graph.add_nodes_from(range(4))
        graph.add_weighted_edges_from([(0, 1, value), (1, 2, value)])
        with np.errstate(over="raise", invalid="raise"):
            try:
                matrix = module.floyd_warshall_numpy(graph)
            except FloatingPointError as exc:
                outcomes.append((type(exc), str(exc)))
            else:
                outcomes.append(("matrix", matrix.tolist()))
    # NaN inputs need not raise, but must propagate to the same cells.
    if outcomes[0][0] == "matrix":
        assert outcomes[1][0] == "matrix"
        np.testing.assert_array_equal(outcomes[0][1], outcomes[1][1])
    else:
        assert outcomes[0] == outcomes[1]


@pytest.mark.parametrize("kind", ["Graph", "DiGraph"])
@pytest.mark.parametrize("algorithm", ["to_numpy_array", "floyd_warshall_numpy"])
@pytest.mark.parametrize("shadow", ["edges", "nodes", "is_directed", "is_multigraph"])
def test_dense_matrices_preserve_exact_graph_providers(kind, algorithm, shadow):
    outcomes = []
    for module in (fnx, nx):
        graph = getattr(module, kind)()
        graph.add_weighted_edges_from([(0, 1, 2), (1, 2, 3)])
        reads = []
        if shadow == "edges":
            original_edges = graph.edges

            def edges(*args, **kwargs):
                reads.append((args, kwargs))
                return original_edges(*args, **kwargs)

            graph.edges = edges
        elif shadow == "nodes":
            # Both dense APIs iterate G, not its assignable node view.
            graph.nodes = object()
        else:
            original_graph_kind = getattr(graph, shadow)

            def graph_kind():
                reads.append(shadow)
                return original_graph_kind()

            setattr(graph, shadow, graph_kind)
        result = getattr(module, algorithm)(graph)
        outcomes.append((result, reads))
    np.testing.assert_array_equal(outcomes[0][0], outcomes[1][0])
    assert outcomes[0][1] == outcomes[1][1]


@pytest.mark.parametrize("algorithm", ["to_numpy_array", "floyd_warshall_numpy"])
@pytest.mark.parametrize("kind", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
def test_dense_matrices_read_original_edge_attribute_protocol(kind, algorithm):
    outcomes = []
    for implementation in (fnx, nx):
        reads = []

        class WeightData(dict):
            def get(self, key, default=None):
                reads.append((key, default))
                return super().get(key, default) + 10

        class PublicGraph(getattr(nx, kind)):
            edge_attr_dict_factory = WeightData

        graph = PublicGraph()
        graph.add_edge(0, 1, cost=2)
        graph.add_edge(1, 2, cost=3)
        result = getattr(implementation, algorithm)(graph, weight="cost")
        outcomes.append((result, reads))
    np.testing.assert_array_equal(outcomes[0][0], outcomes[1][0])
    assert outcomes[0][1] == outcomes[1][1]


@pytest.mark.parametrize("kind", ["Graph", "DiGraph"])
def test_dense_floyd_warshall_reads_self_loop_values_before_zeroing_diagonal(kind):
    for module in (fnx, nx):
        graph = getattr(module, kind)()
        graph.add_edge(0, 0, weight="not numeric")
        with pytest.raises(ValueError, match="could not convert string to float"):
            module.floyd_warshall_numpy(graph)


@pytest.mark.parametrize("kind", ["Graph", "DiGraph"])
def test_dense_floyd_warshall_plain_weights_retain_native_kernel(kind, monkeypatch):
    graph = getattr(fnx, kind)()
    graph.add_weighted_edges_from([(0, 1, 2.0), (1, 2, 3.0), (0, 2, 7.0)])
    list(graph.nodes)
    list(graph.edges)
    native = fnx._fnx.floyd_warshall_dense
    calls = []

    def record_native(*args):
        calls.append(args)
        return native(*args)

    monkeypatch.setattr(fnx._fnx, "floyd_warshall_dense", record_native)
    result = fnx.floyd_warshall_numpy(graph)
    assert result[0, 2] == 5.0
    assert calls == [(graph, "weight")]


@pytest.mark.parametrize("cached", [False, True])
@pytest.mark.parametrize("kind", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("weight", ["cost", None, 7])
def test_dense_floyd_warshall_backend_preserves_weights_and_node_order(cached, kind, weight, monkeypatch):
    monkeypatch.setattr(nx.config, "cache_converted_graphs", True)
    graph = getattr(nx, kind)()
    graph.add_nodes_from(["last", "middle", "first", "isolated"])
    graph.add_edges_from([("first", "middle"), ("middle", "last"), ("first", "last")])
    for (u, v), value in zip(graph.edges(), (2, 7, 3)):
        if graph.is_multigraph():
            graph[u][v][0][weight] = value
        else:
            graph[u][v][weight] = value
    if cached:
        nx.relabel_nodes(graph, {}, backend="franken_networkx")
        assert graph.__networkx_cache__["backends"]["franken_networkx"]
    # Direct dictionary mutation does not clear NetworkX's conversion cache.
    attrs = graph["first"]["last"][0] if graph.is_multigraph() else graph["first"]["last"]
    attrs[weight] = 100
    order = list(graph)[::-1]
    expected = nx.floyd_warshall_numpy(graph, nodelist=order, weight=weight, backend="networkx")
    actual = nx.floyd_warshall_numpy(graph, nodelist=order, weight=weight, backend="franken_networkx")
    np.testing.assert_array_equal(actual, expected)


@pytest.mark.parametrize("algorithm", ["to_numpy_array", "floyd_warshall_numpy"])
@pytest.mark.parametrize("kind", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("weight", [None, 7, ("cost", 2), "cost"])
def test_dense_matrices_preserve_literal_attribute_keys(algorithm, kind, weight):
    results = []
    for module in (nx, fnx):
        graph = getattr(module, kind)()
        graph.add_edges_from([(0, 1, {weight: 2}), (1, 2, {weight: 3})])
        results.append(getattr(module, algorithm)(graph, weight=weight))
    np.testing.assert_array_equal(results[1], results[0])


def _floyd_hash_callback_graph(module, kind, label_shape, action):
    graph = getattr(module, kind)()
    armed = changed = False
    events = []

    class Label(int):
        def __hash__(self):
            nonlocal changed
            if armed and not changed:
                changed = True
                events.append(int(self))
                if action == "raise":
                    raise ArithmeticError(f"node hash {int(self)}")
                graph.add_edge(labels[0], labels[2], cost=1)
            return int.__hash__(self)

    labels = [Label(index) for index in range(4)]
    if label_shape == "tuple":
        labels = [(label,) for label in labels]
    graph.add_nodes_from(labels)
    graph.add_edges_from(
        (left, right, {"cost": 3}) for left, right in zip(labels, labels[1:])
    )

    def arm():
        nonlocal armed
        armed = True

    return graph, labels, events, arm


@pytest.mark.parametrize("kind", ["Graph", "DiGraph"])
@pytest.mark.parametrize("graph_module", [fnx, nx])
@pytest.mark.parametrize("namespace", [fnx, fnx_algorithms])
@pytest.mark.parametrize("label_shape", ["scalar", "tuple"])
def test_floyd_warshall_node_hash_mutation_precedes_edge_reads(
    kind, graph_module, namespace, label_shape, monkeypatch
):
    def reject_matrix(*args, **kwargs):
        pytest.fail("Callback-sensitive node labels reached the matrix solver")

    monkeypatch.setitem(fnx.floyd_warshall.__globals__, "_floyd_warshall_numpy", reject_matrix)
    outcomes = []
    for module, algorithms in ((nx, nx), (graph_module, namespace)):
        graph, labels, events, arm = _floyd_hash_callback_graph(
            module, kind, label_shape, "mutate"
        )
        arm()
        distances = algorithms.floyd_warshall(graph, weight="cost")
        assert distances[labels[0]][labels[3]] == 4
        assert events == [0]
        outcomes.append(_floyd_distance_state(distances))
    assert outcomes[0] == outcomes[1]


@pytest.mark.parametrize("kind", ["Graph", "DiGraph"])
@pytest.mark.parametrize("graph_module", [fnx, nx])
@pytest.mark.parametrize("namespace", [fnx, fnx_algorithms])
@pytest.mark.parametrize("label_shape", ["scalar", "tuple"])
def test_floyd_warshall_node_hash_exception_retains_reference_boundary(
    kind, graph_module, namespace, label_shape
):
    for module, algorithms in ((nx, nx), (graph_module, namespace)):
        graph, _, events, arm = _floyd_hash_callback_graph(
            module, kind, label_shape, "raise"
        )
        arm()
        with pytest.raises(ArithmeticError, match="^node hash 0$"):
            algorithms.floyd_warshall(graph, weight="cost")
        assert events == [0]


@pytest.mark.parametrize("kind", ["Graph", "DiGraph"])
@pytest.mark.parametrize("cached", [False, True])
@pytest.mark.parametrize("label_shape", ["scalar", "tuple"])
def test_floyd_warshall_backend_keeps_live_node_hash_callbacks(
    kind, cached, label_shape, monkeypatch
):
    monkeypatch.setattr(nx.config, "cache_converted_graphs", True)
    outcomes = []
    for backend in ("networkx", "franken_networkx"):
        graph, labels, events, arm = _floyd_hash_callback_graph(
            nx, kind, label_shape, "mutate"
        )
        if cached and backend == "franken_networkx":
            nx.relabel_nodes(graph, {}, backend=backend)
            assert graph.__networkx_cache__["backends"][backend]
        arm()
        distances = nx.floyd_warshall(graph, weight="cost", backend=backend)
        assert distances[labels[0]][labels[3]] == 4
        assert events == [0]
        outcomes.append(_floyd_distance_state(distances))
    assert outcomes[0] == outcomes[1]


@pytest.mark.parametrize("kind", ["Graph", "DiGraph"])
@pytest.mark.parametrize("graph_module", [fnx, nx])
@pytest.mark.parametrize("label_shape", ["int", "str", "tuple", "frozenset"])
def test_floyd_warshall_plain_node_labels_keep_matrix_route(
    kind, graph_module, label_shape, monkeypatch
):
    labels = {
        "int": [0, 1, 2],
        "str": ["zero", "one", "two"],
        "tuple": [("node", index) for index in range(3)],
        "frozenset": [frozenset((index,)) for index in range(3)],
    }[label_shape]
    graph = getattr(graph_module, kind)()
    graph.add_weighted_edges_from(
        [(labels[0], labels[1], 2), (labels[1], labels[2], 3)], weight="cost"
    )
    namespace = fnx.floyd_warshall.__globals__
    solver = namespace["_floyd_warshall_numpy"]
    calls = []

    def record_matrix(*args, **kwargs):
        calls.append(args[0])
        return solver(*args, **kwargs)

    def reject_fallback(*args, **kwargs):
        pytest.fail("Plain node labels unnecessarily left the matrix route")

    monkeypatch.setitem(namespace, "_floyd_warshall_numpy", record_matrix)
    monkeypatch.setitem(
        namespace, "_floyd_warshall_predecessor_and_distance_inproc", reject_fallback
    )
    distances = fnx.floyd_warshall(graph, weight="cost")
    assert distances[labels[0]][labels[2]] == 5
    assert calls == [graph]
