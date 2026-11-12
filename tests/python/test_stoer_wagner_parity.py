"""br-r37-c1-35oum: stoer_wagner must return nx's EXACT min-cut
partition, not just an equal cut value. Kernel mirrors nx's phases
(per-phase lazy-deletion heap with insertion-counter tie-breaks,
copy-order arbitrary_element, row-order contraction merges); the
set-order-dependent recovery tail runs in Python with real CPython
sets."""

import random

import networkx as nx
import pytest

import fnx_backend_info
import franken_networkx as fnx
from franken_networkx.backend import BackendInterface, get_backend_info


def _cmp(gn, gf):
    a, b = fnx.stoer_wagner(gf), nx.stoer_wagner(gn)
    assert (a[0], [repr(x) for x in a[1][0]], [repr(x) for x in a[1][1]]) == (
        b[0],
        [repr(x) for x in b[1][0]],
        [repr(x) for x in b[1][1]],
    )


def test_reaudit_repro_partition_exact():
    rnd = random.Random(7)
    gn, gf = nx.Graph(), fnx.Graph()
    for _ in range(40):
        u, v = rnd.randrange(12), rnd.randrange(12)
        if u != v:
            gn.add_edge(u, v, weight=1 + (u + v) % 3)
            gf.add_edge(u, v, weight=1 + (u + v) % 3)
    _cmp(gn, gf)


def test_docstring_example():
    gn, gf = nx.Graph(), fnx.Graph()
    for g in (gn, gf):
        g.add_edge("x", "a", weight=3)
        g.add_edge("x", "b", weight=1)
        g.add_edge("a", "c", weight=3)
        g.add_edge("b", "c", weight=5)
        g.add_edge("b", "d", weight=4)
        g.add_edge("d", "e", weight=2)
        g.add_edge("c", "y", weight=2)
        g.add_edge("e", "y", weight=3)
    _cmp(gn, gf)


@pytest.mark.parametrize("mode", range(4))
def test_tie_rich_corpus(mode):
    rnd = random.Random(41 + mode)
    done = 0
    for _ in range(40):
        gn, gf = nx.Graph(), fnx.Graph()
        n = rnd.randrange(4, 13)
        for i in range(rnd.randrange(n, n * 3)):
            u, v = rnd.randrange(n), rnd.randrange(n)
            if u == v:
                continue
            kw = {}
            if mode == 1:
                kw = {"weight": rnd.randrange(1, 4)}
            elif mode == 2:
                kw = {"weight": rnd.choice([0, 1, 1, 2])}
            elif mode == 3 and i % 2:
                kw = {"weight": 2}
            gn.add_edge(u, v, **kw)
            gf.add_edge(u, v, **kw)
        if gn.number_of_nodes() < 2 or not nx.is_connected(gn):
            continue
        _cmp(gn, gf)
        done += 1
    assert done > 5


def test_integral_cut_value_type():
    gn, gf = nx.Graph([(0, 1), (1, 2), (0, 2)]), fnx.Graph([(0, 1), (1, 2), (0, 2)])
    tn, tf = nx.stoer_wagner(gn)[0], fnx.stoer_wagner(gf)[0]
    assert type(tn) is type(tf) and tn == tf


def test_error_contracts():
    with pytest.raises(fnx.NetworkXError, match="negative-weighted"):
        fnx.stoer_wagner(fnx.Graph([(1, 2, {"weight": -1})]))
    with pytest.raises(fnx.NetworkXError, match="not connected"):
        fnx.stoer_wagner(fnx.Graph([(1, 2), (3, 4)]))


def _provider_graph(module, kind, second_read):
    reads = []

    class WeightProvider(dict):
        def get(self, key, default=None):
            if key == "weight":
                reads.append(key)
                if len(reads) > 1:
                    if second_read == "raise":
                        raise RuntimeError("weight provider consumed twice")
                    return second_read
            return super().get(key, default)

    reference = nx.Graph(
        [(0, 1, {"weight": 1}), (1, 2, {"weight": 2}), (0, 2, {"weight": 2})]
    )
    attrs = WeightProvider(weight=1)
    reference._adj[0][1] = reference._adj[1][0] = attrs
    if kind == "foreign":
        graph = reference
    else:
        graph = module.Graph(reference)
        # Assigned adjacency is authoritative even when its dictionaries have
        # observable reads. Both directions share the same attribute object.
        graph._adj = reference._adj
        if kind == "view":
            graph = graph.subgraph([0, 1, 2])
    return graph, reads


@pytest.mark.parametrize("kind", ["foreign", "private", "view"])
@pytest.mark.parametrize("second_read", [100, -100, "raise"])
def test_weight_provider_is_consumed_once(kind, second_read):
    expected_graph, expected_reads = _provider_graph(nx, kind, second_read)
    actual_graph, actual_reads = _provider_graph(fnx, kind, second_read)

    expected = nx.stoer_wagner(expected_graph)
    actual = fnx.stoer_wagner(actual_graph)

    assert actual == expected
    assert actual[0] == 3
    assert actual_reads == expected_reads == ["weight"]


@pytest.mark.parametrize("kind", ["foreign", "private", "view"])
def test_negative_weight_provider_keeps_error_and_read_order(kind):
    outcomes = []
    for module in (nx, fnx):
        graph, reads = _provider_graph(module, kind, "raise")
        graph[0][1]["weight"] = -1
        with pytest.raises(nx.NetworkXError) as error:
            module.stoer_wagner(graph)
        outcomes.append((type(error.value), error.value.args, reads))
    assert outcomes[0] == outcomes[1]
    assert outcomes[0][1] == ("graph has a negative-weighted edge.",)
    assert outcomes[0][2] == ["weight"]


def _backend_stoer_weight(domain, value):
    from decimal import Decimal
    from fractions import Fraction

    if domain == "huge-int":
        return (1 << 60) + value
    if domain == "fraction":
        return Fraction(value, 7)
    if domain == "decimal":
        return Decimal(value) / Decimal(10)
    return value


def _backend_stoer_graph(module=nx, domain="int", weight="weight"):
    graph = module.Graph()
    graph.add_nodes_from(["tail", 7, "b", "a"])
    for u, v, value in [
        ("a", "b", 1), ("b", 7, 2), (7, "a", 3),
        (7, "tail", 4), ("tail", "a", 5),
    ]:
        graph.add_edge(u, v)
        graph[u][v][weight] = _backend_stoer_weight(domain, value)
    return graph


def _stoer_result_contract(result):
    value, partition = result
    return type(value), value, type(partition), [(type(side), list(side)) for side in partition]


def _prime_stoer_backend_cache(graph, monkeypatch):
    monkeypatch.setattr(nx.config, "cache_converted_graphs", True)
    nx.relabel_nodes(graph, {}, backend="franken_networkx")
    assert graph.__networkx_cache__["backends"]["franken_networkx"]


def test_stoer_wagner_backend_is_advertised_and_bindable():
    assert "stoer_wagner" in get_backend_info()["functions"]
    assert "stoer_wagner" in fnx_backend_info.get_backend_info()["functions"]
    graph = _backend_stoer_graph()
    assert BackendInterface.can_run("stoer_wagner", (graph,), {})
    assert BackendInterface.can_run("stoer_wagner", (), {"G": graph, "weight": "weight"})
    assert not BackendInterface.can_run("stoer_wagner", (), {})


@pytest.mark.parametrize("domain", ["int", "huge-int", "fraction", "decimal"])
@pytest.mark.parametrize("input_kind", ["networkx", "cached-networkx", "native"])
def test_stoer_wagner_backend_preserves_exact_numeric_results(domain, input_kind, monkeypatch):
    source = _backend_stoer_graph(fnx if input_kind == "native" else nx, domain)
    expected_source = _backend_stoer_graph(nx, domain)
    if input_kind == "cached-networkx":
        _prime_stoer_backend_cache(source, monkeypatch)
    expected = nx.stoer_wagner(expected_source, backend="networkx")
    actual = nx.stoer_wagner(source, backend="franken_networkx")
    assert _stoer_result_contract(actual) == _stoer_result_contract(expected)
    assert sum(source[u][v]["weight"] for u, v in source.edges() if (u in actual[1][0]) != (v in actual[1][0])) == actual[0]


@pytest.mark.parametrize("weight", [None, "", ("edge", "cost")])
@pytest.mark.parametrize("cached", [False, True])
def test_stoer_wagner_backend_preserves_literal_weight_keys(weight, cached, monkeypatch):
    source = _backend_stoer_graph(weight=weight)
    expected_source = _backend_stoer_graph(weight=weight)
    if cached:
        _prime_stoer_backend_cache(source, monkeypatch)
    expected = nx.stoer_wagner(expected_source, weight=weight, backend="networkx")
    actual = nx.stoer_wagner(source, weight=weight, backend="franken_networkx")
    assert _stoer_result_contract(actual) == _stoer_result_contract(expected)
    assert actual[0] == 3


@pytest.mark.parametrize("second_read", [100, -100, "raise"])
@pytest.mark.parametrize("cached", [False, True])
def test_stoer_wagner_backend_consumes_live_weight_provider_once(second_read, cached, monkeypatch):
    source, actual_reads = _provider_graph(nx, "foreign", second_read)
    expected_source, expected_reads = _provider_graph(nx, "foreign", second_read)
    if cached:
        _prime_stoer_backend_cache(source, monkeypatch)
    assert actual_reads == expected_reads == []
    expected = nx.stoer_wagner(expected_source, backend="networkx")
    actual = nx.stoer_wagner(source, backend="franken_networkx")
    assert _stoer_result_contract(actual) == _stoer_result_contract(expected)
    assert actual_reads == expected_reads == ["weight"]


def _stoer_error_graph(module, kind):
    if kind in ("DiGraph", "MultiGraph", "MultiDiGraph"):
        return getattr(module, kind)([(0, 1), (1, 2), (0, 2)])
    graph = module.Graph()
    if kind == "singleton":
        graph.add_node(0)
    elif kind == "disconnected":
        graph.add_edges_from([(0, 1), (2, 3)])
    elif kind == "negative":
        graph.add_edge(0, 1, weight=-1)
    return graph


@pytest.mark.parametrize("kind", ["DiGraph", "MultiGraph", "MultiDiGraph", "empty", "singleton", "disconnected", "negative"])
@pytest.mark.parametrize("native", [False, True])
def test_stoer_wagner_backend_preserves_graph_errors(kind, native):
    expected_source = _stoer_error_graph(nx, kind)
    source = _stoer_error_graph(fnx if native else nx, kind)
    with pytest.raises(Exception) as expected:
        nx.stoer_wagner(expected_source, backend="networkx")
    with pytest.raises(type(expected.value)) as actual:
        nx.stoer_wagner(source, backend="franken_networkx")
    assert actual.value.args == expected.value.args


@pytest.mark.parametrize("cached", [False, True])
@pytest.mark.parametrize("dispatch", ["explicit", "automatic"])
def test_stoer_wagner_backend_heap_mutates_source_after_snapshot(cached, dispatch, monkeypatch):
    graphs, calls, heaps = [], [], []
    for _ in range(2):
        graph = nx.Graph()
        graph.add_weighted_edges_from([(0, 1, 1), (1, 2, 2), (0, 2, 3)])
        events = []

        class HeapFactory:
            def __call__(self, graph=graph, events=events):
                events.append("heap")
                if len(events) == 1:
                    # In-place attribute edits do not invalidate NetworkX's
                    # conversion cache. They occur after the algorithm copied
                    # its weighted working graph and must affect the NEXT cut.
                    graph[1][2]["weight"] = 100
                return nx.utils.BinaryHeap()

        graphs.append(graph)
        calls.append(events)
        heaps.append(HeapFactory())
    if cached:
        _prime_stoer_backend_cache(graphs[0], monkeypatch)
    expected = nx.stoer_wagner(graphs[1], heap=heaps[1], backend="networkx")
    if dispatch == "automatic":
        monkeypatch.setattr(nx.config.backend_priority, "algos", ["franken_networkx"])
        actual = nx.stoer_wagner(graphs[0], heap=heaps[0])
    else:
        actual = nx.stoer_wagner(graphs[0], heap=heaps[0], backend="franken_networkx")
    assert _stoer_result_contract(actual) == _stoer_result_contract(expected)
    assert actual[0] == 3
    assert calls[0] == calls[1] and calls[0]
    assert graphs[0][1][2]["weight"] == 100
    assert not graphs[0].__networkx_cache__.get("backends")
    after = nx.stoer_wagner(graphs[0], backend="franken_networkx")
    assert after[0] == 4


@pytest.mark.parametrize("domain", ["int", "huge-int", "fraction", "decimal"])
def test_stoer_wagner_backend_runs_with_automatic_priority(domain, monkeypatch):
    source = _backend_stoer_graph(domain=domain)
    expected = nx.stoer_wagner(source, backend="networkx")
    monkeypatch.setattr(nx.config.backend_priority, "algos", ["franken_networkx"])
    actual = nx.stoer_wagner(source)
    assert _stoer_result_contract(actual) == _stoer_result_contract(expected)


@pytest.mark.parametrize("cached", [False, True])
def test_stoer_wagner_backend_preserves_heap_provider_error(cached, monkeypatch):
    source = _backend_stoer_graph()
    expected_source = _backend_stoer_graph()
    if cached:
        _prime_stoer_backend_cache(source, monkeypatch)

    def failed_heap():
        raise RuntimeError("heap provider failed")

    with pytest.raises(RuntimeError) as expected:
        nx.stoer_wagner(expected_source, heap=failed_heap, backend="networkx")
    with pytest.raises(RuntimeError) as actual:
        nx.stoer_wagner(source, heap=failed_heap, backend="franken_networkx")
    assert actual.value.args == expected.value.args
    assert not source.__networkx_cache__.get("backends")


@pytest.mark.parametrize("kind", ["valid", "negative", "disconnected"])
@pytest.mark.parametrize("cached", [False, True])
def test_stoer_wagner_explicit_none_heap_preserves_validation_order(kind, cached, monkeypatch):
    source = _backend_stoer_graph() if kind == "valid" else _stoer_error_graph(nx, kind)
    expected_source = _backend_stoer_graph() if kind == "valid" else _stoer_error_graph(nx, kind)
    if cached:
        _prime_stoer_backend_cache(source, monkeypatch)
    with pytest.raises(Exception) as expected:
        nx.stoer_wagner(expected_source, heap=None, backend="networkx")
    with pytest.raises(type(expected.value)) as dispatched:
        nx.stoer_wagner(source, heap=None, backend="franken_networkx")
    with pytest.raises(type(expected.value)) as direct:
        fnx.stoer_wagner(source, heap=None)
    assert dispatched.value.args == direct.value.args == expected.value.args


def _install_stoer_connectivity_provider(graph, provider):
    reads = []
    if provider == "unused-nodes":
        def unused_nodes(*args, **kwargs):
            reads.append("nodes")
            raise RuntimeError("unused nodes provider consumed")

        graph.nodes = unused_nodes
    else:
        class LiveAdjacency(dict):
            def __getitem__(self, node):
                reads.append(node)
                if len(reads) > 1:
                    raise RuntimeError("connectivity read an unnecessary adjacency row")
                row = super().__getitem__(node)
                # The first row reaches every node. Its live mutation must be
                # visible to the later weight snapshot without reading another
                # adjacency row merely to establish connectivity.
                row[1]["weight"] = 5
                return row

        graph._adj = LiveAdjacency(graph._adj)
    return reads


@pytest.mark.parametrize("provider", ["unused-nodes", "live-adjacency"])
@pytest.mark.parametrize("route", ["direct", "backend-cold", "backend-warm", "private"])
def test_stoer_wagner_connectivity_keeps_live_source_protocols(provider, route, monkeypatch):
    expected_source = nx.Graph()
    expected_source.add_weighted_edges_from([(0, 1, 1), (1, 2, 2), (0, 2, 2)])
    source_reference = nx.Graph(expected_source)
    if route == "private":
        source = fnx.Graph(source_reference)
        source._adj = source_reference._adj
    else:
        source = source_reference
    if route == "backend-warm":
        _prime_stoer_backend_cache(source, monkeypatch)

    expected_reads = _install_stoer_connectivity_provider(expected_source, provider)
    actual_reads = _install_stoer_connectivity_provider(source, provider)
    expected = nx.stoer_wagner(expected_source, backend="networkx")
    if route in ("direct", "private"):
        actual = fnx.stoer_wagner(source)
    else:
        actual = nx.stoer_wagner(source, backend="franken_networkx")

    assert _stoer_result_contract(actual) == _stoer_result_contract(expected)
    assert actual[0] == (3 if provider == "unused-nodes" else 4)
    assert actual_reads == expected_reads == ([] if provider == "unused-nodes" else [0])
