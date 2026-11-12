"""Goldberg-Radzik live reads and negative-weight predecessor dispatch.

networkx validates the source at the top of ``goldberg_radzik`` with
``NodeNotFound("Node {source} is not found in the graph")``. fnx
previously surfaced the internal bellman-ford wording
``Source x not in G``. This locks fnx to nx's exact message across
directed and undirected graphs. br-r37-c1-tnzt9
"""

from __future__ import annotations

from decimal import Decimal
from fractions import Fraction

import pytest
import networkx as nx
import franken_networkx as fnx


@pytest.mark.parametrize(
    "fnx_cls,nx_cls", [(fnx.Graph, nx.Graph), (fnx.DiGraph, nx.DiGraph)],
    ids=["undirected", "directed"],
)
@pytest.mark.parametrize("missing", ["x", 99])
def test_goldberg_radzik_missing_source_matches_networkx(fnx_cls, nx_cls, missing):
    fg = fnx_cls([(0, 1), (1, 2)])
    ng = nx_cls([(0, 1), (1, 2)])
    with pytest.raises(nx.NodeNotFound) as fnx_exc:
        fnx.goldberg_radzik(fg, missing)
    with pytest.raises(nx.NodeNotFound) as nx_exc:
        nx.goldberg_radzik(ng, missing)
    assert str(fnx_exc.value) == str(nx_exc.value)


def test_goldberg_radzik_message_exact_wording():
    fg = fnx.DiGraph([(0, 1), (1, 2)])
    with pytest.raises(nx.NodeNotFound) as exc:
        fnx.goldberg_radzik(fg, "x")
    assert str(exc.value) == "Node x is not found in the graph"


def test_goldberg_radzik_valid_query_unaffected():
    fg = fnx.DiGraph([(0, 1), (1, 2)])
    ng = nx.DiGraph([(0, 1), (1, 2)])
    assert fnx.goldberg_radzik(fg, 0) == nx.goldberg_radzik(ng, 0)


def _install_edge_data(graph, u, v, data):
    graph._adj[u][v] = data
    if graph.is_directed():
        graph._pred[v][u] = data
    else:
        graph._adj[v][u] = data


def _observed_weight_graph(class_name, *, private=False, view=False):
    graph = getattr(nx, class_name)()
    graph.add_weighted_edges_from([(0, 1, 1), (1, 2, 10)])
    events = []

    class ReweightedData(dict):
        def get(self, key, default=None):
            value = super().get(key, default)
            if key == "weight":
                events.append(value)
                self["weight"] = 1
            return value

    _install_edge_data(graph, 1, 2, ReweightedData(graph[1][2]))
    if private:
        native = getattr(fnx, class_name)()
        native._node = graph._node
        native._adj = graph._adj
        if graph.is_directed():
            native._pred = graph._pred
        graph = native
    if view:
        graph = graph.subgraph([0, 1, 2])
    return graph, events


@pytest.mark.parametrize("class_name", ["Graph", "DiGraph"])
@pytest.mark.parametrize("kind", ["networkx", "private", "networkx_view", "private_view"])
def test_goldberg_radzik_revisits_live_weight_dictionaries(class_name, kind):
    graph, events = _observed_weight_graph(
        class_name, private=kind.startswith("private"), view=kind.endswith("view")
    )
    reference, expected_events = _observed_weight_graph(class_name, view=kind.endswith("view"))
    expected = nx.goldberg_radzik(reference, 0)
    assert expected[1][2] == 2
    assert fnx.goldberg_radzik(graph, 0) == expected
    assert events == expected_events


@pytest.mark.parametrize("class_name", ["Graph", "DiGraph"])
def test_goldberg_radzik_does_not_read_unreachable_edge_providers(class_name):
    class Unreadable(dict):
        def get(self, key, default=None):
            raise AssertionError("unreachable edge weight was read")

    for algorithm in (nx.goldberg_radzik, fnx.goldberg_radzik):
        graph = getattr(nx, class_name)()
        graph.add_weighted_edges_from([(0, 1, 2), (8, 9, 3)])
        _install_edge_data(graph, 8, 9, Unreadable(weight=3))
        assert algorithm(graph, 0) == ({0: None, 1: 0}, {0: 0, 1: 2})


@pytest.mark.parametrize("graph_module", [nx, fnx], ids=["networkx", "native"])
def test_goldberg_radzik_numeric_provider_changes_later_weight(graph_module):
    def run(module, algorithm):
        graph = module.DiGraph()
        graph.add_weighted_edges_from([(0, 1, 1), (1, 2, 10)])

        class ReweightOnAdd(int):
            def __radd__(self, other):
                graph[1][2]["weight"] = 1
                return other + int(self)

        graph[0][1]["weight"] = ReweightOnAdd(1)
        return algorithm(graph, 0)

    expected = run(nx, nx.goldberg_radzik)
    assert expected[1][2] == 2
    assert run(graph_module, fnx.goldberg_radzik) == expected


@pytest.mark.parametrize("graph_module", [nx, fnx], ids=["networkx", "native"])
def test_goldberg_radzik_admission_never_coerces_an_unreachable_number(graph_module):
    class NoFloat(int):
        def __float__(self):
            raise AssertionError("numeric admission coerced an unreachable weight")

    graph = graph_module.DiGraph()
    graph.add_weighted_edges_from([(0, 1, 2), (8, 9, 3)])
    graph[8][9]["weight"] = NoFloat(3)
    assert fnx.goldberg_radzik(graph, 0) == ({0: None, 1: 0}, {0: 0, 1: 2})


@pytest.mark.parametrize("algorithm", ["bellman_ford_predecessor_and_distance", "goldberg_radzik"])
@pytest.mark.parametrize("class_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("cached", [False, True])
def test_negative_weight_predecessors_are_available_through_backend(
    algorithm, class_name, cached, monkeypatch
):
    monkeypatch.setattr(nx.config, "cache_converted_graphs", True)
    graph = getattr(nx, class_name)()
    graph.add_weighted_edges_from(
        [(0, 1, 4), (1, 2, -2 if graph.is_directed() else 2), (0, 2, 10)]
    )
    graph.add_node("unreachable")
    if graph.is_multigraph():
        graph.add_edge(0, 1, weight=7)
    if cached:
        nx.relabel_nodes(graph, {}, backend="franken_networkx")
        assert graph.__networkx_cache__["backends"]["franken_networkx"]
    options = {"target": 1, "heuristic": True} if algorithm.startswith("bellman") else {}
    expected = getattr(nx, algorithm)(graph, 0, **options, backend="networkx")
    result = getattr(nx, algorithm)(graph, 0, **options, backend="franken_networkx")
    assert [list(part.items()) for part in result] == [list(part.items()) for part in expected]
    assert set(result[1]) == {0, 1, 2}


@pytest.mark.parametrize("cached", [False, True])
@pytest.mark.parametrize("class_name", ["Graph", "DiGraph"])
def test_backend_goldberg_radzik_retains_live_attribute_reads(class_name, cached, monkeypatch):
    monkeypatch.setattr(nx.config, "cache_converted_graphs", True)
    graph, events = _observed_weight_graph(class_name)
    if cached:
        nx.relabel_nodes(graph, {}, backend="franken_networkx")
        assert graph.__networkx_cache__["backends"]["franken_networkx"]
    reference, expected_events = _observed_weight_graph(class_name)
    expected = nx.goldberg_radzik(reference, 0, backend="networkx")
    assert nx.goldberg_radzik(graph, 0, backend="franken_networkx") == expected
    assert events == expected_events
    assert not graph.__networkx_cache__.get("backends")


@pytest.mark.parametrize("algorithm", ["bellman_ford_predecessor_and_distance", "goldberg_radzik"])
@pytest.mark.parametrize("cached", [False, True])
@pytest.mark.parametrize("failure", [False, True])
def test_predecessor_backend_callbacks_keep_identity_and_invalidate_caches(
    algorithm, cached, failure, monkeypatch
):
    monkeypatch.setattr(nx.config, "cache_converted_graphs", True)

    def run(backend):
        graph = nx.DiGraph()
        graph.add_weighted_edges_from([(0, 1, 1), (1, 2, 10)])
        if cached and backend == "franken_networkx":
            nx.relabel_nodes(graph, {}, backend=backend)
        events = []

        def weight(u, v, data):
            assert data is graph._adj[u][v]
            events.append((u, v))
            if (u, v) == (0, 1):
                graph[1][2]["weight"] = 2
                if failure:
                    raise ValueError("weight supplier failed")
            return data["weight"]

        try:
            result = getattr(nx, algorithm)(graph, 0, weight=weight, backend=backend)
        except ValueError as error:
            result = type(error).__name__, error.args
        if backend == "franken_networkx":
            assert not graph.__networkx_cache__.get("backends")
        return result, events, graph[1][2]["weight"]

    assert run("franken_networkx") == run("networkx")


@pytest.mark.parametrize("algorithm", ["bellman_ford_predecessor_and_distance", "goldberg_radzik"])
@pytest.mark.parametrize("source", [0, "missing"])
def test_predecessor_backend_preserves_negative_cycle_and_source_errors(algorithm, source):
    graph = nx.DiGraph()
    graph.add_weighted_edges_from([(0, 1, 1), (1, 2, -3), (2, 0, 1)])
    with pytest.raises(Exception) as expected:
        getattr(nx, algorithm)(graph, source, backend="networkx")
    with pytest.raises(type(expected.value)) as result:
        getattr(nx, algorithm)(graph, source, backend="franken_networkx")
    assert result.value.args == expected.value.args


def _goldberg_outcome(call):
    try:
        pred, dist = call()
    except Exception as error:
        return "raise", type(error).__name__, str(error)
    return (
        "return", list(pred.items()),
        [(node, type(value).__name__, repr(value)) for node, value in dist.items()],
    )


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("route", ["native", "foreign", "backend", "cached_backend"])
def test_goldberg_radzik_preserves_repeated_edge_provider_reads(graph_type, route, monkeypatch):
    def run(reference):
        events = []

        class LiveWeight(dict):
            def get(self, key, default=None):
                if key == "weight":
                    events.append(key)
                    if len(events) == 2:
                        self[key] = 1
                return super().get(key, default)

        module = fnx if not reference and route == "native" else nx
        graph_class = type("LiveGraph", (getattr(module, graph_type),), {
            "edge_attr_dict_factory": LiveWeight,
        })
        graph = graph_class()
        graph.add_edge("s", "t", weight=5)
        if module is fnx:
            # Install the same live reader in logical Python rows. Native
            # graph construction owns its own attribute storage factories.
            attrs = LiveWeight(weight=5)
            edge = {0: attrs} if graph.is_multigraph() else attrs
            rows = {"s": {"t": edge}, "t": {}}
            if graph.is_directed():
                graph._succ = rows
                graph._pred = {"s": {}, "t": {"s": edge}}
            else:
                rows["t"]["s"] = edge
            graph._adj = rows
        if not reference and route == "cached_backend":
            monkeypatch.setattr(nx.config, "cache_converted_graphs", True)
            nx.relabel_nodes(graph, {}, backend="franken_networkx")
            assert graph.__networkx_cache__["backends"]["franken_networkx"]
            events.clear()
        if reference:
            result = _goldberg_outcome(
                lambda: nx.goldberg_radzik(graph, "s", backend="networkx")
            )
        elif route in ("backend", "cached_backend"):
            result = _goldberg_outcome(
                lambda: nx.goldberg_radzik(graph, "s", backend="franken_networkx")
            )
            assert not graph.__networkx_cache__.get("backends")
        else:
            result = _goldberg_outcome(lambda: fnx.goldberg_radzik(graph, "s"))
        attrs = graph._adj["s"]["t"][0] if graph.is_multigraph() else graph._adj["s"]["t"]
        return result, events, attrs["weight"]

    actual, expected = run(False), run(True)
    assert actual == expected
    assert actual[0][0] == "return"
    assert actual[2] == 1


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("value", [Fraction(2, 7), Decimal("0.2"), 10**400])
@pytest.mark.parametrize("weight", ["weight", None, ("edge", "cost")])
def test_backend_goldberg_radzik_keeps_exact_numeric_distances(graph_type, value, weight):
    graph = getattr(nx, graph_type)([(0, 1), (1, 2), (0, 2)])
    for u, v, attrs in graph.edges(data=True):
        attrs[weight] = value * (3 if (u, v) == (0, 2) else 1)
    expected = _goldberg_outcome(
        lambda: nx.goldberg_radzik(graph, 0, weight, backend="networkx")
    )
    actual = _goldberg_outcome(
        lambda: nx.goldberg_radzik(graph, 0, weight, backend="franken_networkx")
    )
    assert actual == expected
    assert actual[0] == "return"


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("cached", [False, True])
@pytest.mark.parametrize("automatic", [False, True])
def test_backend_goldberg_radzik_callback_reads_original_attributes(
    graph_type, cached, automatic, monkeypatch
):
    def run(backend):
        graph = getattr(nx, graph_type)()
        graph.add_weighted_edges_from([(0, 1, 4), (0, 2, 1), (2, 1, 1), (1, 3, 9)])
        if cached and backend == "franken_networkx":
            monkeypatch.setattr(nx.config, "cache_converted_graphs", True)
            nx.relabel_nodes(graph, {}, backend="franken_networkx")
        events = []

        def weight(u, v, attrs):
            assert attrs is graph._adj[u][v]
            events.append((u, v))
            if (u, v) == (0, 2):
                later = graph[1][3][0] if graph.is_multigraph() else graph[1][3]
                later["weight"] = 0
            if graph.is_multigraph():
                return min(data["weight"] for data in attrs.values())
            return attrs["weight"]

        kwargs = {"backend": backend}
        if automatic and backend == "franken_networkx":
            monkeypatch.setattr(nx.config.backend_priority, "algos", [backend])
            kwargs = {}
        result = _goldberg_outcome(lambda: nx.goldberg_radzik(graph, 0, weight, **kwargs))
        return result, events

    expected = run("networkx")
    assert run("franken_networkx") == expected


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("shape", ["negative_loop", "negative_cycle", "unreachable_cycle", "hidden"])
def test_backend_goldberg_radzik_keeps_weight_and_cycle_errors(graph_type, shape):
    graph = getattr(nx, graph_type)()
    graph.add_edge(0, 1, weight=2)
    if shape == "negative_loop":
        graph.add_edge(9, 9, weight=-1)
    elif shape in ("negative_cycle", "unreachable_cycle"):
        u, v = (1, 2) if shape == "negative_cycle" else (8, 9)
        graph.add_edge(u, v, weight=-2)
        if graph.is_directed():
            graph.add_edge(v, u, weight=1)
    weight = (lambda u, v, data: None) if shape == "hidden" else "weight"
    expected = _goldberg_outcome(
        lambda: nx.goldberg_radzik(graph, 0, weight, backend="networkx")
    )
    assert _goldberg_outcome(
        lambda: nx.goldberg_radzik(graph, 0, weight, backend="franken_networkx")
    ) == expected
