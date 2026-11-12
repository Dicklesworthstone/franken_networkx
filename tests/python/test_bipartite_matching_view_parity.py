"""Parity for the one-shot-nx-view bipartite matching overrides (br-r37-c1-bipmatch).

fnx.bipartite re-exported networkx's matching functions verbatim, so calling them on
an fnx graph ran nx's algorithm over the fnx substrate (3-6x slower; Hopcroft-Karp /
Eppstein sweep the adjacency many times). They now convert once to a plain nx graph
(node + edge order preserved) and delegate, so the matching is byte-identical to
networkx while ~2-2.5x faster than before.
"""

import random
import sys

import networkx as nx
import networkx.algorithms.bipartite as nxb
import pytest

import fnx_backend_info
import franken_networkx as fnx
from franken_networkx.backend import BackendInterface, get_backend_info

FUNCS = ["hopcroft_karp_matching", "maximum_matching", "eppstein_matching"]


def _cp(G):
    F = fnx.Graph()
    F.add_nodes_from(G.nodes(data=True))
    F.add_edges_from(G.edges())
    return F


def test_matching_parity_top_and_none():
    for seed in range(200):
        rnd = random.Random(seed)
        a, b = rnd.randint(5, 45), rnd.randint(5, 45)
        g = nx.bipartite.random_graph(a, b, rnd.uniform(0.12, 0.5), seed=seed)
        top = [n for n, d in g.nodes(data=True) if d["bipartite"] == 0]
        f = _cp(g)
        for name in FUNCS:
            ffn = getattr(fnx.bipartite, name)
            nfn = getattr(nxb, name)
            for tn in (top, None):
                try:
                    expected = nfn(g, tn)
                    err = None
                except Exception as e:  # noqa: BLE001
                    expected, err = None, type(e)
                if err is not None:
                    try:
                        ffn(f, tn)
                    except err:
                        continue
                    raise AssertionError((name, seed, "expected", err))
                assert ffn(f, tn) == expected, (name, seed)


def test_nx_typed_input_passthrough():
    g = nx.bipartite.random_graph(20, 20, 0.2, seed=1)
    top = [n for n, d in g.nodes(data=True) if d["bipartite"] == 0]
    for name in FUNCS:
        assert getattr(fnx.bipartite, name)(g, top) == getattr(nxb, name)(g, top)


def test_string_node_labels():
    g = nx.bipartite.random_graph(15, 15, 0.25, seed=3)
    g = nx.relabel_nodes(g, {n: f"v{n}" for n in g})
    top = [n for n in g if int(n[1:]) < 15]
    f = _cp(g)
    assert fnx.bipartite.hopcroft_karp_matching(f, top) == nxb.hopcroft_karp_matching(
        g, top
    )


_BACKEND_MATCHING = FUNCS + ["to_vertex_cover", "minimum_weight_full_matching"]


def _matching_graph(module, class_name="Graph"):
    graph = getattr(module, class_name)()
    graph.add_nodes_from([2, 0, 1, 5, 3, 4])
    graph.add_weighted_edges_from(
        [(0, 3, 6), (0, 4, 1), (1, 4, 5), (1, 5, 2), (2, 3, 3), (2, 5, 7)]
    )
    return graph


def _matching_kwargs(name, graph, top_nodes):
    kwargs = {"top_nodes": top_nodes}
    if name == "to_vertex_cover":
        kwargs["matching"] = {0: 4, 1: 5, 2: 3, 4: 0, 5: 1, 3: 2}
    return kwargs


def _ordered_matching(result):
    return list(result.items()) if isinstance(result, dict) else list(result)


def _prime_matching_cache(graph, monkeypatch):
    monkeypatch.setattr(nx.config, "cache_converted_graphs", True)
    nx.relabel_nodes(graph, {}, backend="franken_networkx")
    assert graph.__networkx_cache__["backends"]["franken_networkx"]


@pytest.mark.parametrize("name", _BACKEND_MATCHING)
def test_matching_backend_advertises_canonical_dispatch_names(name):
    dispatch_name = "hopcroft_karp_matching" if name == "maximum_matching" else name
    assert dispatch_name in get_backend_info()["functions"]
    assert dispatch_name in fnx_backend_info.get_backend_info()["functions"]
    graph = _matching_graph(nx)
    assert BackendInterface.can_run(dispatch_name, (graph,), _matching_kwargs(name, graph, [0, 1, 2]))


@pytest.mark.parametrize("name", _BACKEND_MATCHING)
@pytest.mark.parametrize("class_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("input_kind", ["networkx", "cached-networkx", "native", "view", "private"])
def test_matching_backend_preserves_exact_results(name, class_name, input_kind, monkeypatch):
    source = _matching_graph(fnx if input_kind == "native" else nx, class_name)
    expected_source = _matching_graph(nx, class_name)
    if input_kind == "view":
        source = nx.subgraph_view(source, filter_node=lambda node: node != 2)
        expected_source = nx.subgraph_view(expected_source, filter_node=lambda node: node != 2)
        top_nodes = [0, 1]
    else:
        top_nodes = [0, 1, 2]
    if input_kind == "private":
        # User-assigned row mappings are live inputs, even when the graph class
        # itself is one of NetworkX's ordinary concrete classes.
        class Rows(dict):
            pass

        source._adj = Rows(source._adj)
        expected_source._adj = Rows(expected_source._adj)
    if input_kind == "cached-networkx":
        _prime_matching_cache(source, monkeypatch)
    kwargs = _matching_kwargs(name, expected_source, top_nodes)
    if name == "to_vertex_cover":
        kwargs["matching"] = nxb.hopcroft_karp_matching(
            expected_source, top_nodes, backend="networkx"
        )
    expected = getattr(nxb, name)(expected_source, backend="networkx", **kwargs)
    actual = getattr(nxb, name)(source, backend="franken_networkx", **kwargs)
    assert _ordered_matching(actual) == _ordered_matching(expected)


@pytest.mark.parametrize("name", ["hopcroft_karp_matching", "maximum_matching"])
@pytest.mark.parametrize("cached", [False, True])
def test_matching_backend_keeps_plain_native_kernel(name, cached, monkeypatch):
    graph = _matching_graph(nx)
    if cached:
        _prime_matching_cache(graph, monkeypatch)
    expected = getattr(nxb, name)(graph, [0, 1, 2], backend="networkx")
    native_calls = []
    kernel = fnx._fnx.bipartite_hopcroft_karp_matching

    def observe(frame, event, function):
        if event == "c_call" and function is kernel:
            native_calls.append(function)

    previous = sys.getprofile()
    try:
        sys.setprofile(observe)
        actual = getattr(nxb, name)(graph, [0, 1, 2], backend="franken_networkx")
    finally:
        sys.setprofile(previous)
    assert list(actual.items()) == list(expected.items())
    assert native_calls == [kernel]


@pytest.mark.parametrize("name", FUNCS + ["minimum_weight_full_matching"])
@pytest.mark.parametrize("input_kind", ["networkx", "cached-networkx", "native", "view"])
def test_matching_partition_iterable_mutates_original_graph_once(name, input_kind, monkeypatch):
    sources, roots, calls, partitions = [], [], [], []
    for module in (fnx if input_kind == "native" else nx, nx):
        root = module.Graph()
        root.add_weighted_edges_from([(0, 2, 1), (0, 3, 5), (1, 3, 1)])
        graph = root.subgraph([0, 1, 2, 3]) if input_kind == "view" else root
        events = []

        def partition(root=root, events=events):
            events.append("start")
            root.remove_edge(0, 2)
            root.add_edge(1, 2, weight=1)
            yield 0
            yield 1

        roots.append(root)
        sources.append(graph)
        calls.append(events)
        partitions.append(partition())
    if input_kind == "cached-networkx":
        _prime_matching_cache(sources[0], monkeypatch)
    expected = getattr(nxb, name)(sources[1], partitions[1], backend="networkx")
    if input_kind == "native":
        actual = getattr(fnx.bipartite, name)(sources[0], partitions[0])
    else:
        actual = getattr(nxb, name)(sources[0], partitions[0], backend="franken_networkx")
    assert list(actual.items()) == list(expected.items())
    assert calls == [["start"], ["start"]]
    assert list(roots[0].edges()) == list(roots[1].edges())
    assert actual[0] == 3 and actual[1] == 2


@pytest.mark.parametrize("name", ["hopcroft_karp_matching", "maximum_matching"])
@pytest.mark.parametrize("top_nodes", [[0, 1, 2], [999], [0, []]])
@pytest.mark.parametrize("input_kind", ["networkx", "cached-networkx", "native"])
def test_matching_invalid_partitions_keep_oracle_errors(name, top_nodes, input_kind, monkeypatch):
    source = (fnx if input_kind == "native" else nx).Graph([(0, 2), (0, 3), (1, 2)])
    expected_source = nx.Graph([(0, 2), (0, 3), (1, 2)])
    if input_kind == "cached-networkx":
        _prime_matching_cache(source, monkeypatch)
    with pytest.raises(Exception) as expected:
        getattr(nxb, name)(expected_source, top_nodes, backend="networkx")
    with pytest.raises(type(expected.value)) as actual:
        if input_kind == "native":
            getattr(fnx.bipartite, name)(source, top_nodes)
        else:
            getattr(nxb, name)(source, top_nodes, backend="franken_networkx")
    assert actual.value.args == expected.value.args


@pytest.mark.parametrize("name", _BACKEND_MATCHING)
@pytest.mark.parametrize("input_kind", ["networkx", "native"])
def test_matching_backend_preserves_ambiguous_disconnected_partition(name, input_kind):
    source = (fnx if input_kind == "native" else nx).Graph([(0, 2), (1, 3)])
    expected_source = nx.Graph([(0, 2), (1, 3)])
    kwargs = _matching_kwargs(name, expected_source, None)
    with pytest.raises(nx.AmbiguousSolution) as expected:
        getattr(nxb, name)(expected_source, backend="networkx", **kwargs)
    with pytest.raises(nx.AmbiguousSolution) as actual:
        getattr(nxb, name)(source, backend="franken_networkx", **kwargs)
    assert actual.value.args == expected.value.args


@pytest.mark.parametrize("name", _BACKEND_MATCHING)
def test_matching_runs_under_automatic_backend_priority(name, monkeypatch):
    source = _matching_graph(nx)
    kwargs = _matching_kwargs(name, source, [0, 1, 2])
    expected = getattr(nxb, name)(source, backend="networkx", **kwargs)
    monkeypatch.setattr(nx.config.backend_priority, "algos", ["franken_networkx"])
    actual = getattr(nxb, name)(source, **kwargs)
    assert _ordered_matching(actual) == _ordered_matching(expected)


@pytest.mark.parametrize("cached", [False, True])
def test_vertex_cover_backend_reads_live_matching_mapping(cached, monkeypatch):
    graphs, matchings, calls = [], [], []
    for _ in range(2):
        graph = nx.Graph([(0, 3), (1, 3), (1, 4), (2, 4)])
        events = []

        class Matching(dict):
            def __iter__(self, graph=graph, events=events):
                events.append("iterate")
                graph.remove_edge(2, 4)
                return super().__iter__()

        graphs.append(graph)
        calls.append(events)
        matchings.append(Matching({0: 3, 3: 0, 1: 4, 4: 1}))
    if cached:
        _prime_matching_cache(graphs[0], monkeypatch)
    expected = nxb.to_vertex_cover(graphs[1], matchings[1], [0, 1, 2], backend="networkx")
    actual = nxb.to_vertex_cover(graphs[0], matchings[0], [0, 1, 2], backend="franken_networkx")
    assert actual == expected == {0, 1}
    assert calls == [["iterate"], ["iterate"]]
    assert not graphs[0].has_edge(2, 4)


@pytest.mark.parametrize("cached", [False, True])
def test_full_matching_backend_reads_live_weight_providers(cached, monkeypatch):
    graphs, calls = [], []
    for _ in range(2):
        graph = nx.Graph()
        graph.add_weighted_edges_from(
            [(0, 2, 1), (0, 3, 2), (1, 2, 1), (1, 3, 1)], weight="cost"
        )
        events = []

        class Weight(dict):
            def get(self, key, default=None, graph=graph, events=events):
                events.append(key)
                graph[1][3]["cost"] = 100
                return super().get(key, default)

        graph._adj[0][2] = graph._adj[2][0] = Weight({"cost": 1})
        graphs.append(graph)
        calls.append(events)
    if cached:
        _prime_matching_cache(graphs[0], monkeypatch)
    assert calls == [[], []]
    expected = nxb.minimum_weight_full_matching(
        graphs[1], [0, 1], weight="cost", backend="networkx"
    )
    actual = nxb.minimum_weight_full_matching(
        graphs[0], [0, 1], weight="cost", backend="franken_networkx"
    )
    assert list(actual.items()) == list(expected.items())
    assert actual[0] == 3 and actual[1] == 2
    assert calls == [["cost"], ["cost"]]
    assert graphs[0][1][3]["cost"] == 100
    assert not graphs[0].__networkx_cache__.get("backends")


@pytest.mark.parametrize("name", ["hopcroft_karp_matching", "maximum_matching"])
def test_native_matching_uses_assigned_adjacency(name):
    actual_graph = fnx.Graph([(0, 2), (1, 3)])
    expected_graph = nx.Graph([(0, 2), (1, 3)])
    for graph in (actual_graph, expected_graph):
        left, right = {}, {}
        graph._adj = {0: {3: left}, 1: {2: right}, 2: {1: right}, 3: {0: left}}
    expected = getattr(nxb, name)(expected_graph, [0, 1], backend="networkx")
    actual = getattr(fnx.bipartite, name)(actual_graph, [0, 1])
    assert list(actual.items()) == list(expected.items())
    assert actual[0] == 3 and actual[1] == 2


@pytest.mark.parametrize("name", ["hopcroft_karp_matching", "maximum_matching"])
@pytest.mark.parametrize("input_kind", ["networkx", "cached-networkx", "native"])
@pytest.mark.parametrize("aliases", ["partition", "neighbors", "signed-zero"])
def test_matching_preserves_numeric_label_representatives(name, input_kind, aliases, monkeypatch):
    graphs = []
    for module in (fnx if input_kind == "native" else nx, nx):
        graph = module.Graph()
        graph.add_nodes_from([0, 1, 2, 3])
        edges = (
            [(0, 2.0), (1, 3.0), (0, 3), (1, 2)]
            if aliases == "neighbors"
            else [(0, 2), (1, 3), (0, 3), (1, 2)]
        )
        graph.add_edges_from(edges)
        graphs.append(graph)
    if input_kind == "cached-networkx":
        _prime_matching_cache(graphs[0], monkeypatch)
    top_nodes = [False, 1.0] if aliases == "partition" else [-0.0, 1] if aliases == "signed-zero" else [0, 1]
    expected = getattr(nxb, name)(graphs[1], top_nodes, backend="networkx")
    if input_kind == "native":
        actual = getattr(fnx.bipartite, name)(graphs[0], top_nodes)
    else:
        actual = getattr(nxb, name)(graphs[0], top_nodes, backend="franken_networkx")

    def label(node):
        return type(node), node.hex() if type(node) is float else node

    assert [(label(u), label(v)) for u, v in actual.items()] == [
        (label(u), label(v)) for u, v in expected.items()
    ]


@pytest.mark.parametrize("cached", [False, True])
def test_hopcroft_karp_backend_does_not_read_unneeded_edges_provider(cached, monkeypatch):
    source = _matching_graph(nx)
    expected = nxb.hopcroft_karp_matching(source, [0, 1, 2], backend="networkx")
    if cached:
        _prime_matching_cache(source, monkeypatch)

    def unexpected_edges(*args, **kwargs):
        pytest.fail("Hopcroft-Karp must read adjacency without invoking the edges provider")

    source.edges = unexpected_edges
    actual = nxb.hopcroft_karp_matching(source, [0, 1, 2], backend="franken_networkx")
    assert list(actual.items()) == list(expected.items())
