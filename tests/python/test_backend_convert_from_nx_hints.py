"""BackendInterface.convert_from_nx honours networkx's attribute hints (sfq4w.2).

networkx tells a backend which attributes a dispatched algorithm reads
(``edge_attrs`` / ``node_attrs`` as {name: default}) or that it keeps all of
them (``preserve_*_attrs``). fnx copied every attribute dict regardless, and
walked the adjacency in Python; that was most of the backend-mode conversion
toll. The conversion must still keep node order and every node's neighbor
order exactly, since algorithms break ties by them.
"""

import copy
import gc
import pickle
import random
import weakref
from decimal import Decimal
from fractions import Fraction

import networkx as nx
import pytest

import franken_networkx as fnx
from franken_networkx._fnx import nx_adjacency_edge_batch
from franken_networkx.backend import (
    BackendInterface,
    _nx_to_fnx_for_dispatch,
    _topo_emit_edges_by_adj,
)
from franken_networkx.readwrite import _from_nx_graph

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]


def _churned(cls, seed):
    """A graph whose adjacency order is NOT its edge-list order: edges added in
    random orientation, some removed and re-added, self-loops, attributes."""
    rng = random.Random(seed)
    g = getattr(nx, cls)()
    g.graph["name"] = f"g{seed}"
    n = rng.randint(1, 30)
    for i in rng.sample(range(n), n):
        g.add_node(i, color=rng.choice(["r", "g"]), size=i)
    for _ in range(rng.randint(0, 4 * n)):
        u, v = rng.randrange(n), rng.randrange(n)
        data = {}
        if rng.random() < 0.7:
            data["weight"] = rng.randint(1, 9)
        if rng.random() < 0.3:
            data["label"] = "x"
        g.add_edge(u, v, **data)
    for u, v in rng.sample(list(g.edges()), len(g.edges()) // 4):
        if g.has_edge(u, v):
            g.remove_edge(u, v)
    for _ in range(n // 2):
        u, v = rng.randrange(n), rng.randrange(n)
        g.add_edge(v, u, weight=1)
    return g


def _shape(g):
    adj = [(repr(u), [repr(v) for v in g.adj[u]]) for u in g]
    if g.is_multigraph():
        edges = [(repr(u), repr(v), repr(k), sorted(d.items())) for u, v, k, d in g.edges(keys=True, data=True)]
    else:
        edges = [(repr(u), repr(v), sorted(d.items())) for u, v, d in g.edges(data=True)]
    nodes = [(repr(n), sorted(d.items())) for n, d in g.nodes(data=True)]
    pred = [(repr(u), [repr(v) for v in g.pred[u]]) for u in g] if g.is_directed() else None
    return type(g).__name__, dict(g.graph), nodes, adj, edges, pred


def _convert_preserving_attrs(graph, converter):
    if converter == "readwrite":
        return _from_nx_graph(graph)
    return BackendInterface.convert_from_nx(graph, preserve_all_attrs=True)


@pytest.mark.parametrize("cls", ["Graph", "DiGraph"])
def test_native_edge_order_equals_the_python_helper(cls):
    for seed in range(200):
        g = _churned(cls, seed)
        native = [(u, v) for u, v, *_ in nx_adjacency_edge_batch(g._adj, g.is_directed())]
        assert native == list(_topo_emit_edges_by_adj(g)), seed


@pytest.mark.parametrize("cls", CLASSES)
def test_preserving_everything_equals_the_full_converter(cls):
    for seed in range(120):
        g = _churned(cls, seed)
        hinted = _nx_to_fnx_for_dispatch(
            g,
            edge_attrs=None,
            node_attrs=None,
            preserve_edge_attrs=True,
            preserve_node_attrs=True,
            preserve_graph_attrs=True,
        )
        # Compare with the actual source as well: both converters previously
        # lost the same predecessor/multigraph-neighbor ordering.
        assert _shape(hinted) == _shape(g), seed
        assert _shape(_from_nx_graph(g)) == _shape(g), seed


@pytest.mark.parametrize("converter", ["backend", "readwrite"])
@pytest.mark.parametrize("cls", ["DiGraph", "MultiDiGraph"])
def test_conversion_preserves_reverse_traversal_and_shortest_path_ties(cls, converter):
    graph = getattr(nx, cls)()
    graph.add_nodes_from([0, 1, 2, 5])
    graph.add_edges_from([(5, 2), (0, 2), (1, 0), (1, 5)])
    converted = _convert_preserving_attrs(graph, converter)

    assert list(graph.pred[2]) == [5, 0]
    assert list(converted.pred[2]) == [5, 0]
    assert list(fnx.bfs_edges(converted, 2, reverse=True)) == list(
        nx.bfs_edges(graph, 2, reverse=True)
    )
    expected = nx.bidirectional_shortest_path(graph, 1, 2)
    assert expected == [1, 5, 2]
    assert fnx.bidirectional_shortest_path(converted, 1, 2) == expected
    assert fnx.shortest_path(converted, 1, 2) == expected


@pytest.mark.parametrize("cls", ["DiGraph", "MultiDiGraph"])
def test_dispatched_reverse_traversal_and_shortest_path_keep_source_order(cls):
    graph = getattr(nx, cls)()
    graph.add_nodes_from([0, 1, 2, 5])
    graph.add_edges_from([(5, 2), (0, 2), (1, 0), (1, 5)])
    assert nx.bidirectional_shortest_path(
        graph, 1, 2, backend="franken_networkx"
    ) == nx.bidirectional_shortest_path(graph, 1, 2)
    assert list(nx.bfs_edges(graph, 2, reverse=True, backend="franken_networkx")) == list(
        nx.bfs_edges(graph, 2, reverse=True)
    )


@pytest.mark.parametrize("converter", ["backend", "readwrite"])
@pytest.mark.parametrize("cls", CLASSES)
def test_conversion_keeps_shallow_attributes_and_parallel_edge_keys(cls, converter):
    graph = getattr(nx, cls)()
    graph_payload, node_payload, edge_payload = [], [], []
    graph.graph["payload"] = graph_payload
    graph.add_nodes_from(["a", "b", "c", "d", "isolated"])
    graph.nodes["d"]["payload"] = node_payload
    key_one = tuple(["parallel", 1])
    key_two = tuple(["parallel", 2])
    edges = [("c", "d"), ("a", "d"), ("b", "d"), ("d", "d")]
    for u, v in edges:
        attrs = {"weight": 3, "payload": edge_payload}
        if graph.is_multigraph():
            graph.add_edge(u, v, key=key_one, **attrs)
            graph.add_edge(u, v, key=key_two, **attrs)
        else:
            graph.add_edge(u, v, **attrs)

    converted = _convert_preserving_attrs(graph, converter)
    assert _shape(converted) == _shape(graph)
    assert converted.graph is not graph.graph
    assert converted.graph["payload"] is graph_payload
    assert converted.nodes["d"] is not graph.nodes["d"]
    assert converted.nodes["d"]["payload"] is node_payload
    for u, v in edges:
        if graph.is_multigraph():
            keys = list(converted[u][v])
            assert len(keys) == 2
            assert keys[0] is key_one
            assert keys[1] is key_two
            original_attrs, converted_attrs = graph[u][v][key_one], converted[u][v][key_one]
        else:
            original_attrs, converted_attrs = graph[u][v], converted[u][v]
        assert converted_attrs is not original_attrs
        assert converted_attrs["payload"] is edge_payload
        converted_attrs["changed"] = True
        assert "changed" not in original_attrs
    if not graph.is_directed():
        assert list(fnx.bfs_edges(converted, "d")) == list(nx.bfs_edges(graph, "d"))


@pytest.mark.parametrize("converter", ["backend", "readwrite"])
@pytest.mark.parametrize("cls", CLASSES)
def test_conversion_preserves_empty_and_isolated_graphs(cls, converter):
    graph = getattr(nx, cls)()
    assert _shape(_convert_preserving_attrs(graph, converter)) == _shape(graph)
    graph.add_nodes_from(["second", "first"])
    assert _shape(_convert_preserving_attrs(graph, converter)) == _shape(graph)


@pytest.mark.parametrize("cls", CLASSES)
def test_hints_carry_only_what_networkx_asks_for(cls):
    g = _churned(cls, 7)
    assert any(d for *_, d in g.edges(data=True)) and any(d for _, d in g.nodes(data=True))
    full = _shape(_from_nx_graph(g))

    bare = BackendInterface.convert_from_nx(g)
    shape = _shape(bare)
    assert shape[3] == full[3]  # every node's neighbor order is kept
    assert all(not d for *_, d in shape[4]) and all(not d for _, d in shape[2])
    assert shape[1] == {}
    # the old converter carried everything: the hint is what drops it
    assert any(d for *_, d in full[4])

    weighted = BackendInterface.convert_from_nx(g, edge_attrs={"weight": 1})
    for *_, d in weighted.edges(data=True):
        assert set(d) == {"weight"}  # missing weights filled with the default
    present = BackendInterface.convert_from_nx(g, edge_attrs={"weight": None})
    for u, v, *rest in present.edges(data=True, keys=True) if g.is_multigraph() else present.edges(data=True):
        assert set(rest[-1]) <= {"weight"}
    assert sum("weight" in d for *_, d in present.edges(data=True)) == sum(
        "weight" in d for *_, d in g.edges(data=True)
    )

    colored = BackendInterface.convert_from_nx(g, node_attrs={"color": None}, preserve_graph_attrs=True)
    assert [d for _, d in colored.nodes(data=True)] == [{"color": d["color"]} for _, d in g.nodes(data=True)]
    assert dict(colored.graph) == dict(g.graph)


def test_views_and_subclasses_keep_the_full_conversion():
    g = _churned("Graph", 3)

    class Sub(nx.Graph):
        pass

    sub = Sub(g)
    view = g.subgraph(list(g)[: len(g) // 2])
    for graph in (sub, view):
        converted = _nx_to_fnx_for_dispatch(
            graph,
            edge_attrs=None,
            node_attrs=None,
            preserve_edge_attrs=True,
            preserve_node_attrs=True,
            preserve_graph_attrs=True,
        )
        assert _shape(converted)[2:] == _shape(_from_nx_graph(graph))[2:]


@pytest.mark.parametrize("cls", ["Graph", "DiGraph"])
def test_dispatched_results_still_equal_networkx(cls):
    for seed in range(20):
        g = _churned(cls, seed)
        source = next(iter(g))
        assert nx.single_source_shortest_path_length(
            g, source, backend="franken_networkx"
        ) == nx.single_source_shortest_path_length(g, source)
        assert nx.single_source_dijkstra_path_length(
            g, source, backend="franken_networkx"
        ) == nx.single_source_dijkstra_path_length(g, source)
        assert list(nx.bfs_edges(g, source, backend="franken_networkx")) == list(nx.bfs_edges(g, source))


# should_run's ski rental (sfq4w.2 part 2): a cheap kernel's first calls on a
# graph run in networkx (a cold conversion costs more than networkx's own
# run); the call that brings the graph's accumulated share of a conversion to
# one converts, and the cached conversion serves every later call.

from franken_networkx.backend import _CONVERT_AFTER_USES, _RENT_KEY


def _fresh():
    return nx.barabasi_albert_graph(200, 3, seed=5)


def test_a_cheap_kernel_declines_until_its_calls_pay_for_a_conversion():
    g = _fresh()
    k = _CONVERT_AFTER_USES["bfs_tree"]
    verdicts = [BackendInterface.should_run("bfs_tree", (g, 0), {}) for _ in range(k)]
    assert all(isinstance(v, str) for v in verdicts[:-1]), verdicts
    assert verdicts[-1] is True
    g.add_edge(0, 199)  # networkx clears the cache, and the running total with it
    assert _RENT_KEY not in g.__networkx_cache__
    assert isinstance(BackendInterface.should_run("bfs_tree", (g, 0), {}), str)


def test_calls_of_different_kernels_share_the_graph_s_total():
    g = _fresh()
    pagerank, core = 1 / _CONVERT_AFTER_USES["pagerank"], 1 / _CONVERT_AFTER_USES["core_number"]
    assert 2 * pagerank < 1.0 <= 2 * pagerank + core  # two pageranks, then core_number pays
    assert isinstance(BackendInterface.should_run("pagerank", (g,), {}), str)
    assert isinstance(BackendInterface.should_run("pagerank", (g,), {}), str)
    assert BackendInterface.should_run("core_number", (g,), {}) is True


def test_kernels_that_never_pay_and_heavy_kernels():
    g = _fresh()
    assert all(isinstance(BackendInterface.should_run("has_path", (g, 0, 1), {}), str) for _ in range(50))
    assert "betweenness_centrality" not in _CONVERT_AFTER_USES
    assert BackendInterface.should_run("betweenness_centrality", (g,), {}) is True


def test_a_cached_conversion_means_run_and_no_caching_means_decline():
    g = _fresh()
    nx.bfs_tree(g, 0, backend="franken_networkx")  # an explicit backend converts and caches
    assert g.__networkx_cache__["backends"]["franken_networkx"]
    assert BackendInterface.should_run("connected_components", (g,), {}) is True
    h = _fresh()
    h.__networkx_cache__ = None
    assert isinstance(BackendInterface.should_run("bfs_tree", (h, 0), {}), str)


def test_backend_priority_runs_networkx_until_the_conversion_pays():
    g = _fresh()
    saved = list(nx.config.backend_priority.algos)
    nx.config.backend_priority.algos = ["franken_networkx"]
    try:
        # core_number returns a dict, so networkx takes it from the algos list
        # (graph-returning functions use backend_priority.generators).
        k = _CONVERT_AFTER_USES["core_number"]
        for i in range(k - 1):
            assert nx.core_number(g) == nx.core_number(g, backend="networkx")
            assert not g.__networkx_cache__.get("backends", {}).get("franken_networkx"), i
        assert nx.core_number(g) == nx.core_number(g, backend="networkx")
        assert g.__networkx_cache__["backends"]["franken_networkx"]
    finally:
        nx.config.backend_priority.algos = saved


def test_every_threshold_names_a_function_fnx_dispatches():
    from franken_networkx.backend import _SUPPORTED_ALGORITHMS

    assert set(_CONVERT_AFTER_USES) <= set(_SUPPORTED_ALGORITHMS)
    assert all(k is None or (isinstance(k, int) and k >= 2) for k in _CONVERT_AFTER_USES.values())


def test_a_declined_pagerank_does_not_convert_through_its_nested_dispatch():
    # networkx's pagerank dispatches to_scipy_sparse_array itself; before that
    # entry existed, the nested call converted the graph on the first pagerank.
    g = _fresh()
    saved = list(nx.config.backend_priority.algos)
    nx.config.backend_priority.algos = ["franken_networkx"]
    try:
        assert nx.pagerank(g) == nx.pagerank(g, backend="networkx")
        assert not g.__networkx_cache__.get("backends", {}).get("franken_networkx")
    finally:
        nx.config.backend_priority.algos = saved


def _warm_live_input_cache(graph, monkeypatch):
    """Prime a reusable attribute-preserving conversion through public dispatch."""
    monkeypatch.setattr(nx.config, "cache_converted_graphs", True)
    assert set(nx.relabel_nodes(graph, {}, backend="franken_networkx")) == set(graph)
    assert graph.__networkx_cache__["backends"]["franken_networkx"]
    convert_from_nx = BackendInterface.convert_from_nx

    def unexpected_conversion(*args, **kwargs):
        pytest.fail("the already cached compatible graph must be reused")

    monkeypatch.setattr(BackendInterface, "convert_from_nx", unexpected_conversion)
    return convert_from_nx


def _degree_connectivity_backend_graph(cls_name="Graph"):
    graph = getattr(nx, cls_name)()
    graph.add_nodes_from(range(4))
    graph.add_edge(0, 1, cost=1)
    graph.add_edge(1, 2, cost=10)
    graph.add_edge(2, 3, cost=1)
    return graph


def _group_centrality_backend_graph(cls_name):
    graph = getattr(nx, cls_name)()
    for u, v, cost in [(0, 1, 2), (1, 2, 3), (2, 3, 1), (3, 4, 4), (4, 0, 5), (0, 2, 8)]:
        if graph.is_multigraph():
            key = graph.add_edge(u, v, cost=cost)
            graph[u][v][key][None] = cost
        else:
            graph.add_edge(u, v, cost=cost)
            graph[u][v][None] = cost
    if graph.is_multigraph():
        graph.add_edge(0, 1, key="parallel", cost=7)
        graph[0][1]["parallel"][None] = 7
    return graph


@pytest.mark.parametrize("cached", [False, True])
@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("weight", [None, "cost"])
@pytest.mark.parametrize("algorithm", ["group_betweenness_centrality", "group_closeness_centrality"])
def test_backend_group_centrality_reads_original_weights(
    cached, cls_name, weight, algorithm, monkeypatch
):
    graph = _group_centrality_backend_graph(cls_name)
    if cached:
        _warm_live_input_cache(graph, monkeypatch)
    attrs = graph[1][2][0] if graph.is_multigraph() else graph[1][2]
    attrs["cost"] = attrs[None] = 13
    function = getattr(nx, algorithm)
    expected = function(graph, [1, 3], weight=weight, backend="networkx")
    actual = function(graph, [1, 3], weight=weight, backend="franken_networkx")
    assert actual == pytest.approx(expected, rel=1e-12, abs=1e-12)
    assert not graph.__networkx_cache__.get("backends")


@pytest.mark.parametrize("cached", [False, True])
@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("filtered", [False, True])
@pytest.mark.parametrize("algorithm", ["group_betweenness_centrality", "group_closeness_centrality"])
def test_backend_group_centrality_keeps_callback_dictionaries(
    cached, cls_name, filtered, algorithm, monkeypatch
):
    def run(backend):
        graph = _group_centrality_backend_graph(cls_name)
        work = graph.subgraph(list(graph)) if filtered else graph
        if cached and backend == "franken_networkx":
            _warm_live_input_cache(work, monkeypatch)
        events = []

        def weight(u, v, data):
            later = graph[1][2][0] if graph.is_multigraph() else graph[1][2]
            later["cost"] = 1
            attributes = list(data.values()) if graph.is_multigraph() else [data]
            for attrs in attributes:
                attrs["reads"] = attrs.get("reads", 0) + 1
            values = tuple(attrs["cost"] for attrs in attributes)
            events.append((u, v, values))
            return min(values)

        value = getattr(nx, algorithm)(work, [1, 3], weight=weight, backend=backend)
        if backend == "franken_networkx":
            assert not work.__networkx_cache__.get("backends")
        if graph.is_multigraph():
            attrs = [(u, v, k, dict(data)) for u, v, k, data in graph.edges(keys=True, data=True)]
        else:
            attrs = [(u, v, dict(data)) for u, v, data in graph.edges(data=True)]
        return value, events, attrs

    expected = run("networkx")
    actual = run("franken_networkx")
    assert actual[0] == pytest.approx(expected[0], rel=1e-12, abs=1e-12)
    assert actual[1:] == expected[1:]


@pytest.mark.parametrize("cached", [False, True])
@pytest.mark.parametrize("algorithm", ["group_betweenness_centrality", "group_closeness_centrality"])
def test_backend_group_centrality_clears_cache_after_callback_error(
    cached, algorithm, monkeypatch
):
    graph = _group_centrality_backend_graph("Graph")
    if cached:
        _warm_live_input_cache(graph, monkeypatch)

    def failing_weight(u, v, data):
        graph[1][2]["cost"] = 19
        raise RuntimeError("group weight failed")

    with pytest.raises(RuntimeError, match="group weight failed"):
        getattr(nx, algorithm)(
            graph, [1, 3], weight=failing_weight, backend="franken_networkx"
        )
    assert graph[1][2]["cost"] == 19
    assert not graph.__networkx_cache__.get("backends")


@pytest.mark.parametrize("cached", [False, True])
@pytest.mark.parametrize("algorithm", ["group_betweenness_centrality", "group_closeness_centrality"])
def test_backend_group_centrality_preserves_group_iteration(cached, algorithm, monkeypatch):
    def run(backend):
        graph = _group_centrality_backend_graph("Graph")
        if cached and backend == "franken_networkx":
            _warm_live_input_cache(graph, monkeypatch)
        events = []

        class Group:
            def __iter__(self):
                events.append("select")
                graph.add_edge(1, 4, cost=1)
                yield 1
                yield 3

        result = getattr(nx, algorithm)(graph, Group(), backend=backend)
        if backend == "franken_networkx":
            assert not graph.__networkx_cache__.get("backends")
        return result, events, list(graph.edges())

    expected = run("networkx")
    actual = run("franken_networkx")
    assert actual[0] == pytest.approx(expected[0], rel=1e-12, abs=1e-12)
    assert actual[1:] == expected[1:]


@pytest.mark.parametrize("cached", [False, True])
@pytest.mark.parametrize("view_kind", ["undirected", "filtered", "reverse"])
@pytest.mark.parametrize("algorithm", ["average_degree_connectivity", "average_neighbor_degree"])
def test_backend_degree_connectivity_keeps_live_view_rows(cached, view_kind, algorithm, monkeypatch):
    root = nx.DiGraph()
    for u, v, cost in [(0, 1, 2), (1, 0, 10), (0, 2, 1), (2, 0, 1), (1, 3, 1), (1, 4, 1)]:
        root.add_edge(u, v, cost=cost)
    if view_kind == "reverse":
        graph = root.reverse(copy=False)
    else:
        graph = root.to_undirected(as_view=True)
        if view_kind == "filtered":
            graph = graph.subgraph([0, 1, 2, 3])
    if cached:
        _warm_live_input_cache(graph, monkeypatch)
    root[1][0]["cost"] = 13
    function = getattr(nx, algorithm)
    expected = function(graph, weight="cost", backend="networkx")
    actual = function(graph, weight="cost", backend="franken_networkx")
    assert list(actual.items()) == list(expected.items())


@pytest.mark.parametrize("cached", [False, True])
@pytest.mark.parametrize("cls_name", ["Graph", "DiGraph"])
@pytest.mark.parametrize("value", [Decimal("1.5"), Fraction(3, 2), 10**400])
@pytest.mark.parametrize("nodes", [None, 1])
def test_backend_degree_connectivity_keeps_exact_numeric_domains(cached, cls_name, value, nodes, monkeypatch):
    graph = _degree_connectivity_backend_graph(cls_name)
    graph[0][1]["cost"] = value
    graph[1][2]["cost"] = value * 2
    if cached:
        _warm_live_input_cache(graph, monkeypatch)
    expected = nx.average_degree_connectivity(graph, nodes=nodes, weight="cost", backend="networkx")
    actual = nx.average_degree_connectivity(graph, nodes=nodes, weight="cost", backend="franken_networkx")
    assert list(actual.items()) == list(expected.items())
    assert [type(value) for value in actual.values()] == [type(value) for value in expected.values()]


@pytest.mark.parametrize("cached", [False, True])
@pytest.mark.parametrize("cls_name", ["Graph", "DiGraph"])
def test_backend_degree_connectivity_observes_numeric_mutations(cached, cls_name, monkeypatch):
    def run(backend):
        graph = _degree_connectivity_backend_graph(cls_name)
        if cached and backend == "franken_networkx":
            _warm_live_input_cache(graph, monkeypatch)
        events = []

        class MutatingWeight:
            def __mul__(self, degree):
                events.append(degree)
                graph[1][2]["cost"] = 2
                return degree

            def __radd__(self, value):
                return value + 1

        graph[0][1]["cost"] = MutatingWeight()
        result = nx.average_degree_connectivity(
            graph, "in+out", "in+out", None, "cost", backend=backend
        )
        if backend == "franken_networkx":
            assert not graph.__networkx_cache__.get("backends")
        return list(result.items()), events, graph[1][2]["cost"]

    expected = run("networkx")
    assert run("franken_networkx") == expected


@pytest.mark.parametrize("cached", [False, True])
@pytest.mark.parametrize("weighted", [False, True])
@pytest.mark.parametrize("algorithm", ["average_degree_connectivity", "average_neighbor_degree"])
def test_backend_degree_connectivity_observes_selector_mutations(cached, weighted, algorithm, monkeypatch):
    def run(backend):
        graph = _degree_connectivity_backend_graph()
        if cached and backend == "franken_networkx":
            _warm_live_input_cache(graph, monkeypatch)
        events = []

        class Nodes:
            def __iter__(self):
                events.append("select")
                if weighted:
                    graph[1][2]["cost"] = 2
                else:
                    graph.add_edge(0, 2)
                yield 0
                yield 1
                yield 2

        result = getattr(nx, algorithm)(
            graph, nodes=Nodes(), weight="cost" if weighted else None, backend=backend
        )
        if backend == "franken_networkx":
            assert not graph.__networkx_cache__.get("backends")
        return list(result.items()), events

    expected = run("networkx")
    assert expected[1] == ["select"]
    assert run("franken_networkx") == expected


@pytest.mark.parametrize("cached", [False, True])
@pytest.mark.parametrize("provider", ["degree", "neighbors", "attributes"])
def test_backend_degree_connectivity_keeps_graph_providers(cached, provider, monkeypatch):
    def run(backend):
        graph = _degree_connectivity_backend_graph()
        if cached and backend == "franken_networkx":
            _warm_live_input_cache(graph, monkeypatch)
        events = []
        if provider == "degree":
            original = graph.degree

            def degree(nbunch=None, weight=None):
                events.append((type(nbunch).__name__, weight))
                graph[1][2]["cost"] = 2
                return original(nbunch, weight=weight)

            graph.degree = degree
        elif provider == "neighbors":
            original = graph.neighbors

            def neighbors(node):
                events.append(node)
                graph[1][2]["cost"] = 2
                return original(node)

            graph.neighbors = neighbors
        else:
            class Attributes(dict):
                def get(self, key, default=None):
                    events.append(key)
                    graph[1][2]["cost"] = 2
                    return super().get(key, default)

            graph._adj[0][1] = graph._adj[1][0] = Attributes(cost=1)
        result = nx.average_degree_connectivity(graph, weight="cost", backend=backend)
        return list(result.items()), events

    expected = run("networkx")
    assert expected[1]
    assert run("franken_networkx") == expected


@pytest.mark.parametrize("cached", [False, True])
@pytest.mark.parametrize("cls_name", ["Graph", "DiGraph"])
@pytest.mark.parametrize("weight", [None, "cost"])
@pytest.mark.parametrize("nodes", [None, [0, 1, 2]])
@pytest.mark.parametrize("algorithm", ["average_degree_connectivity", "average_neighbor_degree"])
def test_backend_degree_connectivity_reuses_plain_native_input(cached, cls_name, weight, nodes, algorithm, monkeypatch):
    from functools import wraps
    from franken_networkx import backend as backend_module

    monkeypatch.setattr(nx.config, "cache_converted_graphs", True)
    graph = _degree_connectivity_backend_graph(cls_name)
    kwargs = dict(nodes=nodes, weight=weight)
    expected = getattr(nx, algorithm)(graph, **kwargs, backend="networkx")
    # Ordinary cached public views must still qualify for native conversion.
    list(graph.degree)
    list(graph.nodes)
    list(graph.adj)
    if graph.is_directed():
        list(graph.in_degree)
        list(graph.out_degree)
        list(graph.pred)
        list(graph.succ)
    if cached:
        _warm_live_input_cache(graph, monkeypatch)
    function = backend_module._SUPPORTED_ALGORITHMS[algorithm]
    received = []

    @wraps(function)
    def record_input(*args, **options):
        received.append(args[0] if args else options["G"])
        return function(*args, **options)

    monkeypatch.setitem(backend_module._SUPPORTED_ALGORITHMS, algorithm, record_input)
    for _ in range(2):
        assert list(getattr(nx, algorithm)(graph, **kwargs, backend="franken_networkx").items()) == list(expected.items())
    assert type(received[0]) is getattr(fnx, cls_name)
    assert received[0] is received[1]
    assert graph.__networkx_cache__["backends"]["franken_networkx"]


@pytest.mark.parametrize("cached", [False, True])
@pytest.mark.parametrize("cls_name", ["Graph", "DiGraph"])
def test_backend_neighbor_degree_keeps_mutating_attribute_readers(cached, cls_name, monkeypatch):
    def run(backend):
        graph = _degree_connectivity_backend_graph(cls_name)
        if cached and backend == "franken_networkx":
            _warm_live_input_cache(graph, monkeypatch)
        events = []

        class Attributes(dict):
            def get(self, key, default=None):
                events.append(key)
                graph[1][2]["cost"] = 2
                return super().get(key, default)

        attrs = Attributes(cost=1)
        graph._adj[0][1] = attrs
        if graph.is_directed():
            graph._pred[1][0] = attrs
        else:
            graph._adj[1][0] = attrs
        result = nx.average_neighbor_degree(graph, weight="cost", backend=backend)
        if backend == "franken_networkx":
            assert not graph.__networkx_cache__.get("backends")
        return list(result.items()), events, graph[1][2]["cost"]

    expected = run("networkx")
    assert expected[1] and expected[2] == 2
    assert run("franken_networkx") == expected


@pytest.mark.parametrize("cached", [False, True])
def test_backend_neighbor_degree_discards_mutated_conversions_on_error(cached, monkeypatch):
    monkeypatch.setattr(nx.config, "cache_converted_graphs", True)
    graph = nx.Graph()
    graph.add_edge(0, 1, weight=2)
    if cached:
        nx.relabel_nodes(graph, {}, backend="franken_networkx")

    class Nodes:
        def __iter__(self):
            assert nx.dijkstra_path_length(graph, 0, 1, backend="franken_networkx") == 2
            assert graph.__networkx_cache__["backends"]["franken_networkx"]
            graph[0][1]["weight"] = 9
            raise RuntimeError("node selector stopped after a live write")

    with pytest.raises(RuntimeError, match="node selector stopped after a live write"):
        nx.average_neighbor_degree(
            graph, nodes=Nodes(), weight="weight", backend="franken_networkx"
        )
    assert not graph.__networkx_cache__.get("backends")
    assert nx.dijkstra_path_length(graph, 0, 1, backend="franken_networkx") == 9


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("cached", [False, True])
@pytest.mark.parametrize("call_style", ["keyword", "positional", "automatic"])
def test_backend_greedy_color_preserves_strategy_graph_and_feedback(
    cls_name, cached, call_style, monkeypatch
):
    monkeypatch.setattr(nx.config, "cache_converted_graphs", True)

    def run(backend):
        graph = getattr(nx, cls_name)()
        graph.add_nodes_from([2, 0, 1])
        graph.add_edge(1, 0, label="original")
        graph.graph["label"] = "caller"
        graph.nodes[0]["priority"] = 7
        edge = graph[1][0][0] if graph.is_multigraph() else graph[1][0]
        trace = []
        feedback = []
        if cached and backend == "franken_networkx":
            _warm_live_input_cache(graph, monkeypatch)

        def strategy(current, colors):
            assert current is graph
            assert current.graph is graph.graph
            assert current.nodes[0] is graph.nodes[0]
            assert (current[1][0][0] if current.is_multigraph() else current[1][0]) is edge
            feedback.append(colors)
            trace.append(("start", current.graph["label"], current.nodes[0]["priority"]))
            yield 0
            trace.append(("first", list(colors.items())))
            current.add_edges_from([(2, 0), (2, 1)])
            yield 1
            trace.append(("second", list(colors.items())))
            yield 2
            trace.append(("finished", list(colors.items())))

        if call_style == "automatic" and backend == "franken_networkx":
            monkeypatch.setattr(nx.config.backend_priority, "algos", [backend])
            result = nx.greedy_color(graph, strategy=strategy)
        elif call_style == "positional":
            result = nx.greedy_color(graph, strategy, backend=backend)
        else:
            result = nx.greedy_color(graph, strategy=strategy, backend=backend)
        assert result is feedback[0]
        if backend == "franken_networkx":
            assert not graph.__networkx_cache__.get("backends")
        return list(result.items()), trace, list(graph.edges())

    expected = run("networkx")
    assert expected[0] == [(0, 0), (1, 1), (2, 2)]
    assert run("franken_networkx") == expected


@pytest.mark.parametrize("cls_name", ["Graph", "DiGraph"])
@pytest.mark.parametrize("cached", [False, True])
def test_backend_greedy_color_keeps_custom_degree_reads(cls_name, cached, monkeypatch):
    monkeypatch.setattr(nx.config, "cache_converted_graphs", True)

    def run(backend):
        graph = getattr(nx, cls_name)([(0, 1), (1, 2), (2, 3), (3, 0)])
        if cached and backend == "franken_networkx":
            _warm_live_input_cache(graph, monkeypatch)
        reads = []
        priority = {0: 1, 1: 3, 2: 2, 3: 4}

        def degree(node):
            reads.append(node)
            return priority[node]

        graph.degree = degree
        result = nx.greedy_color(graph, backend=backend)
        return list(result.items()), reads

    assert run("franken_networkx") == run("networkx")


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("cached", [False, True])
def test_backend_greedy_color_keeps_live_view_filters(cls_name, cached, monkeypatch):
    graph = getattr(nx, cls_name)([(0, 1), (1, 2), (2, 3), (3, 0)])
    visible = {0, 1, 2, 3}
    view = nx.subgraph_view(graph, filter_node=visible.__contains__)
    if cached:
        _warm_live_input_cache(view, monkeypatch)
    visible.remove(3)
    expected = nx.greedy_color(view, backend="networkx")
    assert list(nx.greedy_color(view, backend="franken_networkx").items()) == list(expected.items())
    assert set(expected) == {0, 1, 2}


@pytest.mark.parametrize("cached", [False, True])
def test_backend_greedy_color_preserves_named_strategy_override(cached, monkeypatch):
    graph = nx.Graph([(0, 1), (1, 2)])
    graph.graph["order"] = [2, 1, 0]
    seen = []
    if cached:
        _warm_live_input_cache(graph, monkeypatch)

    def strategy(current, colors):
        assert current is graph
        seen.append(colors)
        return current.graph["order"]

    expected = nx.greedy_color(graph, strategy=strategy, backend="networkx")
    monkeypatch.setitem(fnx.coloring.STRATEGIES, "largest_first", strategy)
    actual = nx.greedy_color(graph, backend="franken_networkx")
    assert list(actual.items()) == list(expected.items())
    assert actual is seen[-1]


@pytest.mark.parametrize("cls_name", ["Graph", "DiGraph"])
@pytest.mark.parametrize("cached", [False, True])
def test_backend_greedy_color_reuses_plain_native_default(cls_name, cached, monkeypatch):
    from functools import wraps
    from franken_networkx import backend as backend_module

    monkeypatch.setattr(nx.config, "cache_converted_graphs", True)
    graph = getattr(nx, cls_name)([(3, 1), (1, 4), (4, 2), (2, 3), (3, 4)])
    expected = nx.greedy_color(graph, backend="networkx")
    # Cached ordinary report views must not be mistaken for custom providers.
    list(graph.degree)
    list(graph.adj)
    if cached:
        _warm_live_input_cache(graph, monkeypatch)
    function = backend_module._SUPPORTED_ALGORITHMS["greedy_color"]
    received = []

    @wraps(function)
    def record_input(*args, **kwargs):
        received.append(args[0] if args else kwargs["G"])
        return function(*args, **kwargs)

    monkeypatch.setitem(backend_module._SUPPORTED_ALGORITHMS, "greedy_color", record_input)
    for _ in range(2):
        assert nx.greedy_color(graph, backend="franken_networkx") == expected
    assert len(received) == 2
    assert received[0] is received[1]
    assert type(received[0]) is getattr(fnx, cls_name)
    assert graph.__networkx_cache__["backends"]["franken_networkx"]


@pytest.mark.parametrize("cls_name", CLASSES)
def test_backend_greedy_color_keeps_independent_native_graph(cls_name, monkeypatch):
    monkeypatch.setattr(nx.config, "cache_converted_graphs", True)
    graph = getattr(nx, cls_name)([(1, 0)])
    nx.degree_centrality(graph, backend="franken_networkx")
    converted = next(iter(graph.__networkx_cache__["backends"]["franken_networkx"].values()))
    converted.add_edge(2, 1)

    def strategy(current, colors):
        assert current is converted
        return [0, 1, 2]

    result = nx.greedy_color(converted, strategy=strategy, backend="franken_networkx")
    assert result == {0: 0, 1: 1, 2: 0}
    assert list(graph) == [1, 0]


@pytest.mark.parametrize("cached", [False, True])
def test_backend_greedy_color_discards_callback_conversions_on_error(cached, monkeypatch):
    monkeypatch.setattr(nx.config, "cache_converted_graphs", True)
    graph = nx.Graph()
    graph.add_edge(0, 1, weight=2)
    if cached:
        nx.relabel_nodes(graph, {}, backend="franken_networkx")

    def strategy(current, colors):
        assert current is graph
        assert nx.dijkstra_path_length(current, 0, 1, backend="franken_networkx") == 2
        assert current.__networkx_cache__["backends"]["franken_networkx"]
        current[0][1]["weight"] = 9
        raise RuntimeError("strategy stopped after a live write")

    with pytest.raises(RuntimeError, match="strategy stopped after a live write"):
        nx.greedy_color(graph, strategy=strategy, backend="franken_networkx")
    assert not graph.__networkx_cache__.get("backends")
    assert nx.dijkstra_path_length(graph, 0, 1, backend="franken_networkx") == 9


@pytest.mark.parametrize("cached", [False, True])
@pytest.mark.parametrize(
    "algorithm", ["closeness_centrality", "harmonic_centrality", "wiener_index", "closeness_vitality"]
)
def test_backend_weighted_analytics_keep_asymmetric_view_rows(algorithm, cached, monkeypatch):
    graph = nx.DiGraph()
    graph.add_weighted_edges_from(
        [(0, 1, 1), (1, 0, 7), (1, 2, 2), (2, 1, 9), (2, 0, 4), (0, 2, 11)]
    )
    view = graph.to_undirected(as_view=True).subgraph([0, 1, 2])
    parameter = "distance" if algorithm.endswith("centrality") else "weight"
    kwargs = {parameter: "weight"}
    expected = getattr(nx, algorithm)(view, **kwargs, backend="networkx")
    if cached:
        _warm_live_input_cache(view, monkeypatch)
    actual = getattr(nx, algorithm)(view, **kwargs, backend="franken_networkx")
    assert actual == pytest.approx(expected)


@pytest.mark.parametrize("cached", [False, True])
@pytest.mark.parametrize("cls_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize(
    "algorithm", ["closeness_centrality", "harmonic_centrality", "wiener_index", "closeness_vitality"]
)
def test_backend_weighted_analytics_preserve_callback_trace(algorithm, cls_name, cached, monkeypatch):
    monkeypatch.setattr(nx.config, "cache_converted_graphs", True)

    def run(backend):
        graph = getattr(nx, cls_name)()
        graph.add_weighted_edges_from(
            [(0, 1, 1), (1, 2, 10), (2, 0, 7), (1, 0, 2), (2, 1, 3), (0, 2, 8)]
        )
        trace = []

        def weight(u, v, data):
            selected = data[0] if graph.is_multigraph() else data
            original = graph._adj[u][v]
            original = original[0] if graph.is_multigraph() else original
            trace.append((u, v, selected is original))
            if (u, v) == (0, 1):
                changed = graph[1][2][0] if graph.is_multigraph() else graph[1][2]
                changed["weight"] = 1
            return min(attrs["weight"] for attrs in data.values()) if graph.is_multigraph() else selected["weight"]

        if cached and backend == "franken_networkx":
            nx.relabel_nodes(graph, {}, backend=backend)
            assert graph.__networkx_cache__["backends"][backend]
        parameter = "distance" if algorithm.endswith("centrality") else "weight"
        answer = getattr(nx, algorithm)(graph, **{parameter: weight}, backend=backend)
        if backend == "franken_networkx":
            assert not graph.__networkx_cache__.get("backends")
        return answer, trace, list(graph.edges(data=True))

    expected, expected_trace, expected_edges = run("networkx")
    actual, actual_trace, actual_edges = run("franken_networkx")
    assert actual == pytest.approx(expected)
    assert actual_trace == expected_trace
    assert actual_edges == expected_edges


@pytest.mark.parametrize("cached", [False, True])
@pytest.mark.parametrize("algorithm", ["eigenvector_centrality", "katz_centrality"])
def test_backend_spectral_vectors_mutate_the_original_graph(algorithm, cached, monkeypatch):
    monkeypatch.setattr(nx.config, "cache_converted_graphs", True)

    def run(backend):
        graph = nx.DiGraph([(0, 1), (1, 2), (2, 0)])

        class Start(dict):
            def values(self):
                graph.add_edge(0, 2)
                return super().values()

        class Beta(dict):
            def __iter__(self):
                graph.add_edge(0, 2)
                return super().__iter__()

        kwargs = {"max_iter": 1000, "tol": 1e-10}
        if algorithm == "eigenvector_centrality":
            kwargs["nstart"] = Start({0: 1.0, 1: 1.0, 2: 1.0})
        else:
            kwargs["beta"] = Beta({0: 1.0, 1: 2.0, 2: 3.0})
        if cached and backend == "franken_networkx":
            nx.relabel_nodes(graph, {}, backend=backend)
            assert graph.__networkx_cache__["backends"][backend]
        answer = getattr(nx, algorithm)(graph, **kwargs, backend=backend)
        if backend == "franken_networkx":
            assert not graph.__networkx_cache__.get("backends")
        return answer, list(graph.edges())

    expected, expected_edges = run("networkx")
    actual, actual_edges = run("franken_networkx")
    assert actual == pytest.approx(expected, rel=1e-12, abs=1e-12)
    assert actual_edges == expected_edges


@pytest.mark.parametrize("cached", [False, True])
def test_backend_katz_retains_literal_none_weights(cached, monkeypatch):
    graph = nx.Graph([(0, 1), (1, 2), (2, 0)])
    for (u, v), weight in zip(graph.edges(), [1, 4, 2]):
        graph[u][v][None] = weight
    expected = nx.katz_centrality(graph, normalized=False, backend="networkx")
    if cached:
        _warm_live_input_cache(graph, monkeypatch)
    assert nx.katz_centrality(
        graph, normalized=False, backend="franken_networkx"
    ) == pytest.approx(expected)


@pytest.mark.parametrize("cached", [False, True])
@pytest.mark.parametrize("algorithm", ["eigenvector_centrality", "katz_centrality"])
@pytest.mark.parametrize("provider", ["number", "attribute_key"])
def test_backend_spectral_admission_preserves_numeric_and_key_protocols(
    algorithm, provider, cached, monkeypatch
):
    monkeypatch.setattr(nx.config, "cache_converted_graphs", True)

    def run(backend):
        graph = nx.DiGraph([(0, 1), (1, 2), (2, 0)])
        trace = []
        if cached and backend == "franken_networkx":
            nx.relabel_nodes(graph, {}, backend=backend)

        class Weight:
            def __float__(self):
                trace.append("float")
                return 1.0

            def __rmul__(self, other):
                trace.append("multiply")
                return other

        class Key:
            def __hash__(self):
                return hash("weight")

            def __eq__(self, other):
                trace.append("equal")
                return False

        for _, _, attrs in graph.edges(data=True):
            if provider == "number":
                attrs["weight"] = Weight()
            else:
                attrs[Key()] = 1
        trace.clear()
        answer = getattr(nx, algorithm)(
            graph, weight="weight", max_iter=1000, backend=backend
        )
        if backend == "franken_networkx":
            assert not graph.__networkx_cache__.get("backends")
        return answer, trace

    expected, expected_trace = run("networkx")
    actual, actual_trace = run("franken_networkx")
    assert actual == pytest.approx(expected)
    assert actual_trace == expected_trace
    assert "float" not in actual_trace


@pytest.mark.parametrize("cached", [False, True])
@pytest.mark.parametrize("cls_name", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("heap_kind", ["default", "observed", "pairing"])
def test_backend_capacity_scaling_preserves_heap_and_flow(cls_name, heap_kind, cached, monkeypatch):
    monkeypatch.setattr(nx.config, "cache_converted_graphs", True)

    def run(backend):
        graph = getattr(nx, cls_name)()
        graph.add_node(("source", 0), demand=-3)
        graph.add_node("sink", demand=3)
        graph.add_edge(("source", 0), "middle", capacity=3, weight=1)
        graph.add_edge("middle", "sink", capacity=3, weight=2)
        events = []

        class ObservedHeap(nx.utils.BinaryHeap):
            def __init__(self):
                events.append(("new",))
                data = graph[("source", 0)]["middle"]
                (data[0] if graph.is_multigraph() else data)["weight"] = 7
                super().__init__()

            def insert(self, key, value, allow_increase=False):
                events.append(("insert", key, value))
                return super().insert(key, value, allow_increase)

            def pop(self):
                result = super().pop()
                events.append(("pop", *result))
                return result

        kwargs = {}
        if heap_kind != "default":
            kwargs["heap"] = ObservedHeap if heap_kind == "observed" else nx.utils.PairingHeap
        if cached and backend == "franken_networkx":
            nx.relabel_nodes(graph, {}, backend=backend)
            assert graph.__networkx_cache__["backends"][backend]
        answer = nx.capacity_scaling(graph, **kwargs, backend=backend)
        if backend == "franken_networkx":
            assert not graph.__networkx_cache__.get("backends")
        return answer, events, list(graph.edges(data=True))

    assert run("franken_networkx") == run("networkx")


@pytest.mark.parametrize("cached", [False, True])
@pytest.mark.parametrize("cls_name", ["DiGraph", "MultiDiGraph"])
def test_backend_capacity_scaling_reads_live_cost_after_capacity(cls_name, cached, monkeypatch):
    monkeypatch.setattr(nx.config, "cache_converted_graphs", True)

    def run(backend):
        graph = getattr(nx, cls_name)()
        graph.add_node("s", demand=-2)
        graph.add_node("t", demand=2)
        graph.add_edge("s", "t", capacity=2, weight=1)
        if cached and backend == "franken_networkx":
            nx.relabel_nodes(graph, {}, backend=backend)
        trace = []

        class Edge(dict):
            def get(self, key, default=None):
                trace.append(key)
                if key == "capacity" and trace.count("capacity") == 2:
                    self["weight"] = 7
                return super().get(key, default)

        attrs = Edge(capacity=2, weight=1)
        if graph.is_multigraph():
            graph._adj["s"]["t"][0] = attrs
            graph._pred["t"]["s"][0] = attrs
        else:
            graph._adj["s"]["t"] = attrs
            graph._pred["t"]["s"] = attrs
        answer = nx.capacity_scaling(graph, backend=backend)
        return answer, trace, dict(attrs)

    expected = run("networkx")
    assert expected[0][0] == 14
    assert run("franken_networkx") == expected


@pytest.mark.parametrize("cached", [False, True])
@pytest.mark.parametrize("cls_name", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("shape", ["parallel", "cancellation", "reverse", "custom_size"])
def test_backend_flow_hierarchy_preserves_graph_protocols(cls_name, shape, cached, monkeypatch):
    monkeypatch.setattr(nx.config, "cache_converted_graphs", True)

    def run(backend):
        graph = getattr(nx, cls_name)()
        trace = []
        weight = None
        if shape in ("cancellation", "reverse"):
            graph.add_weighted_edges_from([(0, 1, 1e16), (1, 0, 1), (1, 2, 1), (2, 1, -1e16)])
            weight = "weight"
            if shape == "reverse":
                graph = graph.reverse(copy=False).subgraph([0, 1, 2])
        else:
            graph.add_edges_from([(0, 1), (1, 0)] + [(1, 2)] * 10)
        if shape == "custom_size":
            original_size = graph.size

            def size(weight=None):
                trace.append(weight)
                return original_size(weight=weight) / 2

            graph.size = size
        if cached and backend == "franken_networkx":
            nx.relabel_nodes(graph, {}, backend=backend)
            trace.clear()
        answer = nx.flow_hierarchy(graph, weight=weight, backend=backend)
        if backend == "franken_networkx":
            assert not graph.__networkx_cache__.get("backends")
        return answer, trace

    assert run("franken_networkx") == run("networkx")


@pytest.mark.parametrize("algorithm", ["min_cost_flow", "min_cost_flow_cost", "network_simplex"])
@pytest.mark.parametrize("cls_name", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("cached", [False, True])
@pytest.mark.parametrize("domain", ["integer", "wide_integer", "fraction", "decimal"])
def test_backend_minimum_cost_flow_preserves_numeric_domains(
    algorithm, cls_name, cached, domain, monkeypatch
):
    from decimal import Decimal
    from fractions import Fraction

    amount, cost = {
        "integer": (3, 2),
        "wide_integer": (10**40, 2**80 + 1),
        "fraction": (Fraction(3, 2), Fraction(2, 3)),
        "decimal": (Decimal("1.5"), Decimal("0.75")),
    }[domain]
    graph = getattr(nx, cls_name)()
    graph.add_node(("source", 0), balance=-amount)
    graph.add_node("sink", balance=amount)
    graph.add_edge(("source", 0), "middle", units=amount, cost=cost)
    graph.add_edge("middle", "sink", units=amount, cost=cost)
    graph.add_edge(("source", 0), "sink", units=amount, cost=4 * cost)
    if graph.is_multigraph():
        graph.add_edge(("source", 0), "middle", key=("other", 1), units=amount, cost=5 * cost)
    kwargs = {"demand": "balance", "capacity": "units", "weight": "cost"}
    expected = getattr(nx, algorithm)(graph, **kwargs, backend="networkx")
    if cached:
        _warm_live_input_cache(graph, monkeypatch)
    actual = getattr(nx, algorithm)(graph, **kwargs, backend="franken_networkx")
    assert actual == expected
    if algorithm == "min_cost_flow_cost":
        assert type(actual) is type(expected)
    elif algorithm == "network_simplex":
        assert type(actual[0]) is type(expected[0])


@pytest.mark.parametrize("algorithm", ["min_cost_flow", "min_cost_flow_cost", "network_simplex"])
@pytest.mark.parametrize("cls_name", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("cached", [False, True])
@pytest.mark.parametrize("provider", ["demand", "capacity"])
def test_backend_minimum_cost_flow_preserves_live_providers(
    algorithm, cls_name, cached, provider, monkeypatch
):
    monkeypatch.setattr(nx.config, "cache_converted_graphs", True)

    def run(backend):
        graph = getattr(nx, cls_name)()
        graph.add_node("s", demand=-2)
        graph.add_node("t", demand=2)
        graph.add_edge("s", "t", capacity=2, weight=1)
        if cached and backend == "franken_networkx":
            nx.relabel_nodes(graph, {}, backend=backend)
        trace = []
        edge = graph["s"]["t"][0] if graph.is_multigraph() else graph["s"]["t"]

        class Provider(dict):
            def get(self, key, default=None):
                trace.append(key)
                if key == provider:
                    edge["weight"] = 7
                return super().get(key, default)

        if provider == "demand":
            graph._node["s"] = Provider(demand=-2)
        else:
            edge = Provider(capacity=2, weight=1)
            if graph.is_multigraph():
                graph._adj["s"]["t"][0] = edge
                graph._pred["t"]["s"][0] = edge
            else:
                graph._adj["s"]["t"] = edge
                graph._pred["t"]["s"] = edge
        answer = getattr(nx, algorithm)(graph, backend=backend)
        if backend == "franken_networkx":
            assert not graph.__networkx_cache__.get("backends")
        return answer, trace, dict(edge)

    assert run("franken_networkx") == run("networkx")


@pytest.mark.parametrize("algorithm", ["min_cost_flow", "min_cost_flow_cost", "network_simplex"])
@pytest.mark.parametrize("case", ["unbalanced", "infeasible", "unbounded"])
def test_backend_minimum_cost_flow_preserves_solver_errors(algorithm, case):
    graph = nx.DiGraph()
    if case == "unbounded":
        graph.add_edge(0, 0, weight=-1)
    else:
        graph.add_node(0, demand=-2)
        graph.add_node(1, demand=1 if case == "unbalanced" else 2)
        graph.add_edge(0, 1, capacity=1)
    outcomes = []
    for backend in ("networkx", "franken_networkx"):
        try:
            getattr(nx, algorithm)(graph, backend=backend)
        except nx.NetworkXException as exc:
            outcomes.append((type(exc), exc.args))
    assert len(outcomes) == 2
    assert outcomes[0] == outcomes[1]


@pytest.mark.parametrize("algorithm", ["min_cost_flow", "min_cost_flow_cost", "network_simplex"])
@pytest.mark.parametrize("cls_name", ["DiGraph", "MultiDiGraph"])
def test_backend_minimum_cost_flow_automatic_selection(algorithm, cls_name, monkeypatch):
    graph = getattr(nx, cls_name)()
    graph.add_node("s", demand=-2)
    graph.add_node("t", demand=2)
    graph.add_edge("s", "t", capacity=2, weight=3)
    expected = getattr(nx, algorithm)(graph, backend="networkx")
    monkeypatch.setattr(nx.config.backend_priority, "algos", ["franken_networkx"])
    assert getattr(nx, algorithm)(graph) == expected


@pytest.mark.parametrize("cached", [False, True])
@pytest.mark.parametrize("cls", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize(
    "algorithm",
    [
        "bfs_edges", "bfs_predecessors", "bfs_successors", "bfs_layers",
        "dfs_edges", "dfs_preorder_nodes", "dfs_postorder_nodes",
        "edge_bfs", "edge_dfs",
    ],
)
def test_backend_traversal_keeps_input_live_before_first_yield(
    algorithm, cls, cached, monkeypatch
):
    graph = getattr(nx, cls)()
    graph.add_nodes_from(range(4))
    graph.add_edges_from([(0, 1), (1, 2)])
    if cached:
        _warm_live_input_cache(graph, monkeypatch)
    iterator = getattr(nx, algorithm)(graph, 0, backend="franken_networkx")
    graph.add_edge(2, 3)
    assert list(iterator) == list(getattr(nx, algorithm)(graph, 0, backend="networkx"))


@pytest.mark.parametrize("cached", [False, True])
@pytest.mark.parametrize(
    "algorithm, directed, args, kwargs, added_edge",
    [
        ("find_cliques", False, (), {}, (2, 0)),
        ("enumerate_all_cliques", False, (), {}, (2, 0)),
        ("all_triangles", False, (), {}, (2, 0)),
        ("bridges", False, (), {}, (2, 0)),
        ("local_bridges", False, (), {"with_span": False}, (2, 0)),
        ("local_bridges", False, (), {"with_span": True}, (2, 0)),
        ("simple_cycles", True, (), {}, (2, 0)),
        ("antichains", True, (), {}, (0, 2)),
        ("all_simple_edge_paths", True, (0, 2), {}, (0, 2)),
    ],
)
def test_backend_structural_iterators_read_input_at_first_advance(
    algorithm, directed, args, kwargs, added_edge, cached, monkeypatch
):
    graph = nx.DiGraph() if directed else nx.Graph()
    graph.add_nodes_from(range(3))
    graph.add_edge(0, 1)
    if algorithm != "antichains":
        graph.add_edge(1, 2)
    if cached:
        _warm_live_input_cache(graph, monkeypatch)
    iterator = getattr(nx, algorithm)(graph, *args, backend="franken_networkx", **kwargs)
    graph.add_edge(*added_edge)
    assert list(iterator) == list(
        getattr(nx, algorithm)(graph, *args, backend="networkx", **kwargs)
    )


@pytest.mark.parametrize("cached", [False, True])
@pytest.mark.parametrize(
    "algorithm, kwargs, error_type",
    [
        ("find_cliques", {"nodes": [9]}, ValueError),
        ("bridges", {"root": 9}, nx.NodeNotFound),
        ("simple_cycles", {"length_bound": -1}, ValueError),
        ("all_simple_edge_paths", {"source": 9, "target": 1}, nx.NodeNotFound),
    ],
)
def test_backend_structural_iterator_errors_remain_deferred(
    algorithm, kwargs, error_type, cached, monkeypatch
):
    graph = nx.Graph([(0, 1), (1, 2)])
    if cached:
        _warm_live_input_cache(graph, monkeypatch)
    actual = getattr(nx, algorithm)(graph, backend="franken_networkx", **kwargs)
    expected = getattr(nx, algorithm)(graph, backend="networkx", **kwargs)
    with pytest.raises(error_type) as wanted:
        next(expected)
    with pytest.raises(error_type) as observed:
        next(actual)
    assert str(observed.value) == str(wanted.value)


@pytest.mark.parametrize("cached", [False, True])
def test_backend_local_bridge_callback_clears_conversions_between_advances(cached, monkeypatch):
    graph = nx.cycle_graph(4)
    nx.set_edge_attributes(graph, 1, "weight")
    convert_from_nx = BackendInterface.convert_from_nx
    if cached:
        convert_from_nx = _warm_live_input_cache(graph, monkeypatch)

    def weight(u, v, data):
        assert data is graph._adj[u][v]
        if (u, v) == (0, 3):
            graph[3][2]["weight"] = 7
        return data["weight"]

    iterator = nx.local_bridges(graph, weight=weight, backend="franken_networkx")
    monkeypatch.setattr(BackendInterface, "convert_from_nx", staticmethod(convert_from_nx))
    assert next(iterator) == (0, 1, 9)
    assert nx.dijkstra_path_length(graph, 2, 3, backend="franken_networkx") == (
        nx.dijkstra_path_length(graph, 2, 3, backend="networkx")
    )
    iterator.close()


@pytest.mark.parametrize("cached", [False, True])
@pytest.mark.parametrize(
    "algorithm",
    [
        "all_pairs_shortest_path", "all_pairs_shortest_path_length",
        "all_pairs_dijkstra_path", "all_pairs_dijkstra_path_length",
        "all_pairs_bellman_ford_path", "all_pairs_bellman_ford_path_length",
    ],
)
def test_backend_all_pairs_reads_mutations_between_sources(algorithm, cached, monkeypatch):
    graph = nx.DiGraph()
    graph.add_nodes_from(range(4))
    graph.add_weighted_edges_from([(0, 1, 1), (1, 2, 7), (2, 3, 5)])
    if cached:
        _warm_live_input_cache(graph, monkeypatch)
    iterator = getattr(nx, algorithm)(graph, backend="franken_networkx")
    assert next(iterator)[0] == 0
    # In-place attribute writes do not clear NetworkX's cache. The next source
    # must nevertheless read the graph at that yield, as the oracle does.
    graph[1][2]["weight"] = 2
    graph.add_edge(1, 3, weight=1)
    expected = dict(getattr(nx, algorithm)(graph, backend="networkx"))[1]
    assert next(iterator) == (1, expected)


@pytest.mark.parametrize("entrypoint", ["direct", "cold", "warm"])
@pytest.mark.parametrize("algorithm", ["shortest_path", "shortest_path_length"])
@pytest.mark.parametrize("weight", [None, "weight"])
@pytest.mark.parametrize("method", ["dijkstra", "bellman-ford"])
def test_backend_generic_all_pairs_keeps_live_input(
    algorithm, weight, method, entrypoint, monkeypatch
):
    graph = nx.DiGraph()
    graph.add_nodes_from(range(4))
    graph.add_weighted_edges_from([(0, 1, 1), (1, 2, 7), (2, 3, 5)])
    if entrypoint == "warm":
        _warm_live_input_cache(graph, monkeypatch)
    kwargs = {"weight": weight, "method": method}
    if entrypoint == "direct":
        iterator = getattr(fnx, algorithm)(graph, **kwargs)
    else:
        iterator = getattr(nx, algorithm)(graph, backend="franken_networkx", **kwargs)
    assert next(iterator)[0] == 0
    graph[1][2]["weight"] = 2
    graph.add_edge(1, 3, weight=1)
    expected = dict(getattr(nx, algorithm)(graph, backend="networkx", **kwargs))[1]
    assert next(iterator) == (1, expected)


@pytest.mark.parametrize("cached", [False, True])
@pytest.mark.parametrize(
    "algorithm",
    ["topological_sort", "topological_generations", "lexicographical_topological_sort"],
)
def test_backend_topology_detects_mutation_after_cached_conversion(
    algorithm, cached, monkeypatch
):
    graph = nx.DiGraph([(0, 1), (1, 2)])
    if cached:
        _warm_live_input_cache(graph, monkeypatch)
    iterator = getattr(nx, algorithm)(graph, backend="franken_networkx")
    assert next(iterator) == ([0] if algorithm == "topological_generations" else 0)
    graph.remove_node(1)
    with pytest.raises(RuntimeError):
        next(iterator)


@pytest.mark.parametrize("cached", [False, True])
@pytest.mark.parametrize("cls", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("algorithm", ["dijkstra_path_length", "bellman_ford_path_length"])
def test_backend_weight_callback_uses_original_dicts_and_observes_writes(
    algorithm, cls, cached, monkeypatch
):
    graph = getattr(nx, cls)()
    graph.add_weighted_edges_from([(0, 1, 1), (1, 2, 10)])
    convert_from_nx = BackendInterface.convert_from_nx
    if cached:
        convert_from_nx = _warm_live_input_cache(graph, monkeypatch)

    def weight(u, v, data):
        assert data is graph._adj[u][v]
        if (u, v) == (0, 1):
            changed = graph._adj[1][2]
            (changed[0] if graph.is_multigraph() else changed)["weight"] = 2
        return (data[0] if graph.is_multigraph() else data)["weight"]

    assert getattr(nx, algorithm)(graph, 0, 2, weight, backend="franken_networkx") == 3
    # Callback writes bypass NetworkX's graph mutators, so a later eager call
    # must not reuse a pre-callback snapshot with the old weight of ten.
    monkeypatch.setattr(BackendInterface, "convert_from_nx", staticmethod(convert_from_nx))
    assert nx.dijkstra_path_length(graph, 0, 2, "weight", backend="franken_networkx") == 3


@pytest.mark.parametrize("cached", [False, True])
@pytest.mark.parametrize("method", ["dijkstra", "bellman-ford"])
def test_backend_all_shortest_paths_callback_preserves_call_time_predecessors(
    method, cached, monkeypatch
):
    graph = nx.DiGraph()
    graph.add_weighted_edges_from([(0, 1, 1), (1, 2, 10), (0, 2, 5)])
    if cached:
        _warm_live_input_cache(graph, monkeypatch)

    def weight(u, v, data):
        assert data is graph._adj[u][v]
        if (u, v) == (0, 1):
            graph[1][2]["weight"] = 2
        return data["weight"]

    paths = nx.all_shortest_paths(
        graph, 0, 2, weight=weight, method=method, backend="franken_networkx"
    )
    graph[0][2]["weight"] = 0
    assert list(paths) == [[0, 1, 2]]


@pytest.mark.parametrize(
    "algorithm", ["eccentricity", "diameter", "radius", "center", "periphery", "barycenter"]
)
def test_backend_distance_measure_callbacks_receive_original_dicts(algorithm, monkeypatch):
    graph = nx.Graph([(0, 1), (1, 2)])
    _warm_live_input_cache(graph, monkeypatch)
    seen = []

    def weight(u, v, data):
        assert data is graph._adj[u][v]
        seen.append((u, v))
        return 1

    assert getattr(nx, algorithm)(graph, weight=weight, backend="franken_networkx") == getattr(
        nx, algorithm
    )(graph, weight=None, backend="networkx")
    assert seen


@pytest.mark.parametrize("algorithm", ["bfs_tree", "dfs_tree"])
def test_backend_eager_traversal_observes_sort_callback_mutations(algorithm, monkeypatch):
    graph = nx.DiGraph()
    graph.add_nodes_from(range(4))
    graph.add_edges_from([(0, 1), (1, 2)])
    _warm_live_input_cache(graph, monkeypatch)

    def sort_neighbors(neighbors):
        graph.add_edge(2, 3)
        return sorted(neighbors)

    tree = getattr(nx, algorithm)(
        graph, 0, sort_neighbors=sort_neighbors, backend="franken_networkx"
    )
    assert list(tree.edges()) == [(0, 1), (1, 2), (2, 3)]


def test_backend_astar_observes_heuristic_callback_mutations(monkeypatch):
    graph = nx.DiGraph()
    graph.add_weighted_edges_from([(0, 1, 1), (1, 2, 10)])
    _warm_live_input_cache(graph, monkeypatch)

    def heuristic(node, target):
        graph[1][2]["weight"] = 2
        return 0

    assert nx.astar_path_length(
        graph, 0, 2, heuristic, backend="franken_networkx"
    ) == 3


def test_backend_layers_observe_changes_after_a_yield(monkeypatch):
    graph = nx.DiGraph([(0, 1), (1, 2)])
    graph.add_node(3)
    _warm_live_input_cache(graph, monkeypatch)
    layers = nx.bfs_layers(graph, 0, backend="franken_networkx")
    assert next(layers) == [0]
    graph.add_edge(0, 3)
    assert list(layers) == [[1, 3], [2]]


@pytest.mark.parametrize("algorithm", ["all_simple_paths", "shortest_simple_paths"])
def test_backend_simple_paths_keep_the_source_graph(monkeypatch, algorithm):
    graph = nx.DiGraph([(0, 1), (1, 2)])
    _warm_live_input_cache(graph, monkeypatch)
    paths = getattr(nx, algorithm)(graph, 0, 2, backend="franken_networkx")
    graph.add_edge(0, 2)
    assert list(paths) == list(getattr(nx, algorithm)(graph, 0, 2, backend="networkx"))


def test_backend_live_dispatch_does_not_cache_the_networkx_source(monkeypatch):
    from franken_networkx import backend as backend_module

    monkeypatch.setattr(nx.config, "cache_converted_graphs", True)
    graph = nx.DiGraph([(0, 1), (1, 2)])
    assert list(nx.topological_sort(graph, backend="franken_networkx")) == [0, 1, 2]
    conversions = graph.__networkx_cache__["backends"]["franken_networkx"]
    assert conversions and all(isinstance(value, fnx.DiGraph) for value in conversions.values())
    kernel = backend_module._SUPPORTED_ALGORITHMS["degree_centrality"]
    seen = []

    def record_input(G):
        seen.append(G)
        return kernel(G)

    monkeypatch.setitem(backend_module._SUPPORTED_ALGORITHMS, "degree_centrality", record_input)
    assert nx.degree_centrality(graph, backend="franken_networkx") == nx.degree_centrality(
        graph, backend="networkx"
    )
    assert len(seen) == 1 and isinstance(seen[0], fnx.DiGraph)


def test_backend_source_lifetime_follows_the_live_iterator(monkeypatch):
    monkeypatch.setattr(nx.config, "cache_converted_graphs", True)
    graph = nx.Graph([(0, 1), (1, 2)])
    source_ref = weakref.ref(graph)
    iterator = nx.bfs_layers(graph, 0, backend="franken_networkx")
    converted = next(iter(graph.__networkx_cache__["backends"]["franken_networkx"].values()))
    del graph
    gc.collect()
    assert source_ref() is not None
    assert list(iterator) == [[0], [1], [2]]
    del iterator
    gc.collect()
    assert source_ref() is None
    # A surviving native conversion remains a usable independent snapshot.
    assert list(BackendInterface().bfs_layers(converted, 0)) == [[0], [1], [2]]


@pytest.mark.parametrize("cached", [False, True])
def test_backend_explicit_native_conversion_keeps_its_own_mutations(cached, monkeypatch):
    graph = nx.Graph([(0, 1)])
    if cached:
        monkeypatch.setattr(nx.config, "cache_converted_graphs", True)
        nx.degree_centrality(graph, backend="franken_networkx")
        converted = next(iter(graph.__networkx_cache__["backends"]["franken_networkx"].values()))
    else:
        converted = BackendInterface.convert_from_nx(graph)
    converted.add_edge(1, 2)
    assert list(nx.bfs_layers(converted, 0, backend="franken_networkx")) == [[0], [1], [2]]
    assert list(graph) == [0, 1]


@pytest.mark.parametrize("roundtrip", [copy.deepcopy, lambda graph: pickle.loads(pickle.dumps(graph))])
def test_backend_copied_conversion_cache_recovers_its_new_source(roundtrip, monkeypatch):
    graph = nx.Graph([(0, 1)])
    graph.add_node(2)
    _warm_live_input_cache(graph, monkeypatch)
    restored = roundtrip(graph)
    layers = nx.bfs_layers(restored, 0, backend="franken_networkx")
    restored.add_edge(1, 2)
    assert list(layers) == [[0], [1], [2]]
    assert list(graph.edges()) == [(0, 1)]


def test_backend_lazy_callback_invalidates_caches_between_yields(monkeypatch):
    graph = nx.DiGraph()
    graph.add_weighted_edges_from([(0, 1, 1), (1, 2, 10)])
    convert_from_nx = _warm_live_input_cache(graph, monkeypatch)
    calls = []

    def weight(u, v, data):
        calls.append((u, v))
        graph[1][2]["weight"] = 2 if len(calls) < 3 else 4
        return data["weight"]

    iterator = nx.all_pairs_dijkstra_path_length(graph, weight=weight, backend="franken_networkx")
    assert next(iterator) == (0, {0: 0, 1: 1, 2: 3})
    monkeypatch.setattr(BackendInterface, "convert_from_nx", staticmethod(convert_from_nx))
    assert nx.dijkstra_path_length(graph, 0, 2, backend="franken_networkx") == 3
    assert next(iterator) == (1, {1: 0, 2: 4})
    assert nx.dijkstra_path_length(graph, 0, 2, backend="franken_networkx") == 5


def test_backend_convert_from_nx_e2e_jsonl_emission():
    import hashlib
    import json
    import time
    from datetime import datetime, timezone
    from pathlib import Path
    import franken_networkx._fnx as _fnx_ext

    repo_root = Path(__file__).resolve().parents[2]
    out_path = repo_root / "artifacts" / "conformance" / "latest" / "backend_convert_from_nx_e2e.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    so_sha256 = hashlib.sha256(Path(_fnx_ext.__file__).read_bytes()).hexdigest()

    records = []
    for cls in CLASSES:
        g = _churned(cls, 19)
        full_ref = _from_nx_graph(g)
        input_sha256 = hashlib.sha256(repr(_shape(g)).encode("utf-8")).hexdigest()
        t0 = time.perf_counter()
        conv = BackendInterface.convert_from_nx(g, edge_attrs={"weight": 1})
        elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 4)
        exp_adj = _shape(full_ref)[3]
        act_adj = _shape(conv)[3]
        weights_ok = all(set(d) == {"weight"} for *_, d in conv.edges(data=True))
        passed = (exp_adj == act_adj) and weights_ok
        assert passed, f"Conversion mismatch on {cls}"
        records.append(
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "case_id": f"convert_from_nx_hinted_{cls}",
                "input_sha256": input_sha256,
                "fnx_version": getattr(fnx, "__version__", "0.2.3"),
                "nx_version": nx.__version__,
                "so_sha256": so_sha256,
                "graph_class": cls,
                "construction_path": "BackendInterface.convert_from_nx(edge_attrs={'weight': 1})",
                "expected": len(exp_adj),
                "actual": len(act_adj),
                "pass": passed,
                "duration_ms": elapsed_ms,
            }
        )

    out_path.write_text(
        "\n".join(json.dumps(r, sort_keys=True) for r in records) + "\n",
        encoding="utf-8",
    )
    assert len(records) == 4

