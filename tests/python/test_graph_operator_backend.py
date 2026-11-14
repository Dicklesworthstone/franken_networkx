"""Graph-combination workflows through NetworkX's real backend dispatcher."""

import gc
import weakref

import networkx as nx
import pytest

import franken_networkx as fnx
from franken_networkx import backend as fnx_backend


_SEQUENCE_OPERATORS = (
    "compose_all", "union_all", "intersection_all", "disjoint_union_all",
)
_BINARY_OPERATORS = (
    "compose", "union", "intersection", "difference", "symmetric_difference",
    "disjoint_union", "cartesian_product", "tensor_product",
    "lexicographic_product", "strong_product",
)
_GRAPH_CLASSES = ("Graph", "DiGraph", "MultiGraph", "MultiDiGraph")


def _inputs(libraries, cls_name):
    graphs = []
    for index, library in enumerate(libraries):
        graph = getattr(library, cls_name)()
        graph.graph.update(source=index, nested=[index])
        graph.add_nodes_from([
            ("a", {"source": index, "nested": [index]}),
            ("b", {"source": index}),
            ("isolated", {}),
        ])
        graph.nodes["a"][17] = "non-string node attribute"
        if graph.is_multigraph():
            graph.add_edge("a", "b", key="shared", weight=index + 1)
            graph.add_edge("a", "b", key=("parallel", index), weight=4)
        else:
            graph.add_edge("a", "b", weight=index + 1)
        if index:
            graph.add_edge("b", "b", weight=7)
        graphs.append(graph)
    return graphs


def _snapshot(graph):
    edges = (
        [(u, v, key, dict(data)) for u, v, key, data in graph.edges(keys=True, data=True)]
        if graph.is_multigraph()
        else [(u, v, dict(data)) for u, v, data in graph.edges(data=True)]
    )
    return (
        graph.is_directed(), graph.is_multigraph(), dict(graph.graph),
        [(node, dict(data)) for node, data in graph.nodes(data=True)], edges,
        [(node, list(neighbors)) for node, neighbors in graph.adjacency()],
    )


def _warm(graph):
    if getattr(graph, "__networkx_backend__", "networkx") == "networkx":
        nx.convert_node_labels_to_integers(graph, backend="franken_networkx")
        assert graph.__networkx_cache__["backends"]["franken_networkx"]


def _call(name, graphs, backend, *, keyword=False):
    options = {"backend": backend}
    if name in {"union", "union_all"}:
        options["rename"] = ("left-", "right-")
    if name in _SEQUENCE_OPERATORS:
        if keyword:
            return getattr(nx, name)(graphs=graphs, **options)
        return getattr(nx, name)(graphs, **options)
    if keyword:
        return getattr(nx, name)(G=graphs[0], H=graphs[1], **options)
    return getattr(nx, name)(*graphs, **options)


@pytest.mark.parametrize("name", _SEQUENCE_OPERATORS + _BINARY_OPERATORS)
@pytest.mark.parametrize("cls_name", _GRAPH_CLASSES)
@pytest.mark.parametrize("route", ("cold", "warm", "native", "mixed"))
def test_graph_combinations_match_networkx_through_backend(name, cls_name, route):
    expected = _call(name, _inputs((nx, nx), cls_name), "networkx")
    libraries = (fnx, fnx) if route == "native" else (nx, fnx) if route == "mixed" else (nx, nx)
    graphs = _inputs(libraries, cls_name)
    if route in {"warm", "mixed"}:
        for graph in graphs:
            _warm(graph)
    before = [_snapshot(graph) for graph in graphs]
    actual = _call(name, graphs, "franken_networkx", keyword=route == "warm")
    assert isinstance(actual, getattr(fnx, cls_name))
    assert _snapshot(actual) == _snapshot(expected)
    assert [_snapshot(graph) for graph in graphs] == before


@pytest.mark.parametrize("name", _SEQUENCE_OPERATORS)
@pytest.mark.parametrize("warm", (False, True))
def test_graph_sequence_dispatch_preserves_updated_sources_and_repeated_graphs(name, warm):
    graphs = _inputs((nx, nx), "MultiDiGraph")
    if warm:
        for graph in graphs:
            _warm(graph)
    graphs[0].nodes["a"]["source"] = "updated after conversion"
    graphs[0]["a"]["b"]["shared"]["weight"] = 99
    graphs[0].graph["new metadata"] = [1, 2]
    sequence = [graphs[0], graphs[1], graphs[0]]
    options = {"rename": ("first-", "second-", "third-")} if name == "union_all" else {}
    expected = getattr(nx, name)(sequence, backend="networkx", **options)
    actual = getattr(nx, name)(graphs=iter(sequence), backend="franken_networkx", **options)
    assert _snapshot(actual) == _snapshot(expected)
    for graph in graphs:
        assert not graph.__networkx_cache__.get("backends")


@pytest.mark.parametrize("name", _SEQUENCE_OPERATORS)
def test_graph_sequence_keeps_explicit_native_conversion_independent(name):
    source = nx.Graph()
    source.add_edge("a", "b", weight=1)
    _warm(source)
    native = next(iter(source.__networkx_cache__["backends"]["franken_networkx"].values()))
    native.add_node("native-only")
    source.nodes["a"]["source-only"] = True
    expected_native = fnx_backend.backend_interface.convert_to_nx(native)
    options = {"rename": ("source-", "native-")} if name == "union_all" else {}
    expected = getattr(nx, name)([source, expected_native], backend="networkx", **options)
    actual = getattr(nx, name)([source, native], backend="franken_networkx", **options)
    assert _snapshot(actual) == _snapshot(expected)


@pytest.mark.parametrize("name", _SEQUENCE_OPERATORS)
def test_sequence_can_run_does_not_consume_a_graph_generator(name):
    observed = []

    def graphs():
        observed.append("consumed")
        yield nx.Graph()

    iterator = graphs()
    assert fnx_backend.backend_interface.can_run(name, (iterator,), {}) is True
    assert observed == []


@pytest.mark.parametrize("name", _SEQUENCE_OPERATORS)
def test_stale_sequence_probe_does_not_replace_a_standalone_call(name):
    probed = _inputs((nx, nx), "Graph")
    assert fnx_backend.backend_interface.can_run(name, (probed,), {}) is True
    call = getattr(fnx_backend.backend_interface, name)
    actual_inputs = _inputs((nx, nx), "Graph")
    actual_inputs[0].add_node("unrelated invocation")
    options = {"rename": ("first-", "second-")} if name == "union_all" else {}
    expected = getattr(nx, name)(actual_inputs, backend="networkx", **options)
    actual = call(actual_inputs, **options)
    assert _snapshot(actual) == _snapshot(expected)


@pytest.mark.parametrize("name", _SEQUENCE_OPERATORS)
def test_unused_sequence_probe_does_not_retain_graphs(name):
    graph = nx.Graph()
    reference = weakref.ref(graph)
    assert fnx_backend.backend_interface.can_run(name, ([graph],), {}) is True
    call = getattr(fnx_backend.backend_interface, name)
    del graph
    gc.collect()
    assert reference() is None
    assert callable(call)


@pytest.mark.parametrize("name", _SEQUENCE_OPERATORS)
def test_empty_sequence_backend_errors_match_networkx(name):
    with pytest.raises(ValueError) as expected:
        getattr(nx, name)([], backend="networkx")
    with pytest.raises(ValueError) as actual:
        getattr(nx, name)([], backend="franken_networkx")
    assert str(actual.value) == str(expected.value)


@pytest.mark.parametrize("name", _SEQUENCE_OPERATORS + _BINARY_OPERATORS[:6])
def test_incompatible_graphs_fail_and_discard_conversions(name):
    graphs = [nx.Graph([(0, 1)]), nx.MultiGraph([(0, 1)])]
    for graph in graphs:
        _warm(graph)
    with pytest.raises(nx.NetworkXError) as expected:
        _call(name, graphs, "networkx")
    with pytest.raises(nx.NetworkXError) as actual:
        _call(name, graphs, "franken_networkx")
    assert str(actual.value) == str(expected.value)
    for graph in graphs:
        assert not graph.__networkx_cache__.get("backends")


@pytest.mark.parametrize("name", ("compose_all", "union_all", "disjoint_union_all"))
def test_sequence_backend_copies_attributes_before_reading_later_graphs(name):
    def query(backend):
        first, second = _inputs((nx, nx), "Graph")
        if backend == "franken_networkx":
            _warm(first)
            _warm(second)
        first.nodes["a"]["early"] = 0
        first["a"]["b"]["early"] = 0
        nodes = second.nodes

        class Nodes:
            def _mutate(self):
                first.nodes["a"]["early"] = 99
                first["a"]["b"]["early"] = 99

            def __call__(self, data=False):
                self._mutate()
                return nodes(data=data)

            def items(self):
                self._mutate()
                return nodes.items()

            def __iter__(self):
                return iter(nodes)

            def __getitem__(self, key):
                return nodes[key]

        second.nodes = Nodes()
        result = _call(name, [first, second], backend)
        return _snapshot(result)

    assert query("franken_networkx") == query("networkx")


@pytest.mark.parametrize("name", _SEQUENCE_OPERATORS)
def test_sequence_backend_invalidates_caches_created_by_a_failing_provider(name):
    graphs = _inputs((nx, nx), "Graph")
    for graph in graphs:
        _warm(graph)

    class FailingNodes:
        def _fail(self):
            for graph in graphs:
                graph.__networkx_cache__["backends"] = {"other_backend": {"stale": object()}}
            raise ValueError("node provider failed")

        def __iter__(self):
            self._fail()

        def __call__(self, *args, **kwargs):
            self._fail()

        def items(self):
            self._fail()

    graphs[1].nodes = FailingNodes()
    with pytest.raises(ValueError, match="node provider failed"):
        getattr(nx, name)(graphs, backend="franken_networkx")
    for graph in graphs:
        assert not graph.__networkx_cache__.get("backends")
