"""Parity coverage for the ``franken_networkx.matching`` module."""

from __future__ import annotations

import importlib
import inspect

import franken_networkx as fnx
import networkx as nx
import pytest


PUBLIC_FUNCTIONS = (
    "is_matching",
    "is_maximal_matching",
    "is_perfect_matching",
    "max_weight_matching",
    "min_weight_matching",
    "maximal_matching",
)


def _build_pair():
    weighted_edges = [
        (0, 1, 5),
        (1, 2, 6),
        (2, 3, 5),
        (0, 3, 1),
    ]
    fnx_graph = fnx.Graph()
    nx_graph = nx.Graph()
    for u, v, weight in weighted_edges:
        fnx_graph.add_edge(u, v, weight=weight)
        nx_graph.add_edge(u, v, weight=weight)
    return fnx_graph, nx_graph


def _normalized_edges(edges):
    return {frozenset(edge) for edge in edges}


def test_direct_matching_module_import_exposes_wrappers():
    module = importlib.import_module("franken_networkx.matching")

    for name in PUBLIC_FUNCTIONS:
        assert callable(getattr(module, name))


def test_algorithms_matching_import_routes_to_same_module():
    direct = importlib.import_module("franken_networkx.matching")
    via_algorithms = importlib.import_module("franken_networkx.algorithms.matching")

    assert via_algorithms is direct
    assert fnx.algorithms.matching is direct


def test_matching_module_public_surface_matches_networkx():
    module = importlib.import_module("franken_networkx.matching")
    expected = importlib.import_module("networkx.algorithms.matching")

    assert set(module.__all__) == set(expected.__all__)


def test_matching_function_signatures_match_networkx():
    module = importlib.import_module("franken_networkx.matching")
    expected = importlib.import_module("networkx.algorithms.matching")

    for name in PUBLIC_FUNCTIONS:
        actual_repr = str(inspect.signature(getattr(module, name)))
        expected_repr = str(inspect.signature(getattr(expected, name)))
        if actual_repr != expected_repr:
            raise AssertionError(
                f"{name} signature mismatch: "
                f"{actual_repr} != {expected_repr}"
            )


def test_matching_predicates_match_networkx():
    module = importlib.import_module("franken_networkx.matching")
    fnx_graph, nx_graph = _build_pair()
    matching = {(0, 1), (2, 3)}

    assert module.is_matching(fnx_graph, matching) == nx.is_matching(
        nx_graph, matching
    )
    assert module.is_maximal_matching(fnx_graph, matching) == nx.is_maximal_matching(
        nx_graph, matching
    )
    assert module.is_perfect_matching(fnx_graph, matching) == nx.is_perfect_matching(
        nx_graph, matching
    )


def test_matching_constructors_match_networkx():
    module = importlib.import_module("franken_networkx.matching")
    fnx_graph, nx_graph = _build_pair()

    assert _normalized_edges(module.max_weight_matching(fnx_graph)) == _normalized_edges(
        nx.max_weight_matching(nx_graph)
    )
    assert _normalized_edges(module.min_weight_matching(fnx_graph)) == _normalized_edges(
        nx.min_weight_matching(nx_graph)
    )
    assert _normalized_edges(module.maximal_matching(fnx_graph)) == _normalized_edges(
        nx.maximal_matching(nx_graph)
    )


def test_weighted_matching_small_graphs_bypass_top_level_conversion(monkeypatch):
    module = importlib.import_module("franken_networkx.matching")
    fnx_graph, nx_graph = _build_pair()

    def fail_top_level(*args, **kwargs):
        raise AssertionError("top-level weighted matching delegation was used")

    monkeypatch.setattr(fnx, "max_weight_matching", fail_top_level)
    monkeypatch.setattr(fnx, "min_weight_matching", fail_top_level)

    assert module.max_weight_matching(
        fnx_graph,
        maxcardinality=True,
    ) == nx.max_weight_matching(nx_graph, maxcardinality=True)
    assert module.min_weight_matching(fnx_graph) == nx.min_weight_matching(nx_graph)


def test_max_weight_matching_large_graph_keeps_existing_route(monkeypatch):
    module = importlib.import_module("franken_networkx.matching")
    graph = fnx.path_graph(13)
    sentinel = {("existing", "route")}

    monkeypatch.setattr(fnx, "max_weight_matching", lambda *args, **kwargs: sentinel)

    assert module.max_weight_matching(graph) is sentinel


def test_matching_rejects_backend_kwargs_like_networkx_dispatch():
    module = importlib.import_module("franken_networkx.matching")
    fnx_graph, _ = _build_pair()

    with pytest.raises(TypeError):
        module.maximal_matching(fnx_graph, unsupported=True)


# Weighted matching must preserve the caller's edge readers before choosing
# a native snapshot, including after NetworkX has cached a backend graph.
_WEIGHTED_APIS = ("max_weight_matching", "min_weight_matching")
_WEIGHTED_ROUTES = (
    "native-input", "networkx-input", "matching-module",
    "backend-cold", "backend-warm",
)


def _weighted_graph(lib):
    graph = lib.Graph()
    graph.add_weighted_edges_from([
        (0, 1, 1), (2, 3, 1), (0, 3, 10), (1, 2, 10),
    ])
    return graph


def _warm_weighted_input(graph, route):
    if route == "backend-warm":
        nx.convert_node_labels_to_integers(graph, backend="franken_networkx")
        assert graph.__networkx_cache__["backends"]["franken_networkx"]


def _weighted_call(name, graph, route, **kwargs):
    if route.startswith("backend-"):
        return getattr(nx, name)(graph, backend="franken_networkx", **kwargs)
    if route == "matching-module":
        return getattr(fnx.matching, name)(graph, **kwargs)
    return getattr(fnx, name)(graph, **kwargs)


class _MatchingEdgeProvider:
    def __init__(self, graph, events, *, change_weights=True):
        self.graph = graph
        self.original = graph.edges
        self.events = events
        self.change_weights = change_weights

    def __len__(self):
        self.events.append("edge-count")
        return len(self.original)

    def __iter__(self):
        self.events.append("edge-iteration")
        return iter(self.original)

    def __call__(self, *args, **kwargs):
        self.events.append(("edges", args, tuple(kwargs.items())))
        if self.change_weights:
            self.graph[0][1]["weight"] = 20
            self.graph[2][3]["weight"] = 20
        return self.original(*args, **kwargs)


@pytest.mark.parametrize("name", _WEIGHTED_APIS)
@pytest.mark.parametrize("route", _WEIGHTED_ROUTES)
def test_weighted_matching_observes_original_edge_provider(name, route):
    lib = fnx if route in ("native-input", "matching-module") else nx
    actual, expected = _weighted_graph(lib), _weighted_graph(nx)
    _warm_weighted_input(actual, route)
    actual_events, expected_events = [], []
    actual.edges = _MatchingEdgeProvider(actual, actual_events)
    expected.edges = _MatchingEdgeProvider(expected, expected_events)

    want = getattr(nx, name)(expected)
    assert _weighted_call(name, actual, route) == want
    assert actual_events == expected_events
    assert actual[0][1]["weight"] == expected[0][1]["weight"] == 20
    assert actual[2][3]["weight"] == expected[2][3]["weight"] == 20


@pytest.mark.parametrize("name", _WEIGHTED_APIS)
@pytest.mark.parametrize("route", ("networkx-input", "matching-module", "backend-cold", "backend-warm"))
@pytest.mark.parametrize("behavior", ("fraction", "raise", "not-implemented"))
def test_weighted_matching_does_not_preconsume_weight_reader(name, route, behavior):
    from fractions import Fraction

    def build():
        events = []

        class WeightDict(dict):
            def _observe(self, method, key, default=None):
                events.append((method, key, default))
                if behavior == "raise":
                    raise LookupError("selected weight provider")
                if behavior == "not-implemented":
                    raise nx.NetworkXNotImplemented("selected weight provider")

            def get(self, key, default=None):
                self._observe("get", key, default)
                return super().get(key, default)

            def __getitem__(self, key):
                # min_weight_matching reads EdgeDataView-selected weights by
                # subscription; max_weight_matching reads each dict with get.
                self._observe("__getitem__", key)
                return super().__getitem__(key)

        graph = nx.Graph()
        graph.add_weighted_edges_from([
            (0, 1, Fraction(1, 3)), (2, 3, Fraction(1, 3)),
            (0, 3, Fraction(5, 2)), (1, 2, Fraction(5, 2)),
        ])

        def install():
            for u, v, data in list(graph.edges(data=True)):
                graph._adj[u][v] = graph._adj[v][u] = WeightDict(data)

        return graph, events, install

    actual, actual_events, install_actual = build()
    expected, expected_events, install_expected = build()
    _warm_weighted_input(actual, route)
    install_actual()
    install_expected()

    if behavior != "fraction":
        error_type = nx.NetworkXNotImplemented if behavior == "not-implemented" else LookupError
        with pytest.raises(error_type) as want:
            getattr(nx, name)(expected)
        with pytest.raises(error_type) as got:
            _weighted_call(name, actual, route)
        assert got.value.args == want.value.args
    else:
        assert _weighted_call(name, actual, route) == getattr(nx, name)(expected)
    assert actual_events == expected_events
    first_reader = "get" if name == "max_weight_matching" else "__getitem__"
    assert actual_events[0][0] == first_reader


@pytest.mark.parametrize("route", _WEIGHTED_ROUTES)
def test_weighted_matching_truth_callback_keeps_reference_read_boundary(route):
    lib = fnx if route in ("native-input", "matching-module") else nx
    actual, expected = _weighted_graph(lib), _weighted_graph(nx)
    _warm_weighted_input(actual, route)
    actual_events, expected_events = [], []
    actual.edges = _MatchingEdgeProvider(actual, actual_events, change_weights=False)
    expected.edges = _MatchingEdgeProvider(expected, expected_events, change_weights=False)

    class TruthProvider:
        def __init__(self, events):
            self.events = events

        def __bool__(self):
            self.events.append("maxcardinality")
            raise LookupError("maxcardinality provider")

    with pytest.raises(LookupError) as want:
        nx.max_weight_matching(expected, maxcardinality=TruthProvider(expected_events))
    with pytest.raises(LookupError) as got:
        _weighted_call(
            "max_weight_matching", actual, route,
            maxcardinality=TruthProvider(actual_events),
        )
    assert got.value.args == want.value.args
    assert actual_events == expected_events
    assert any(isinstance(event, tuple) and event[0] == "edges" for event in actual_events)


@pytest.mark.parametrize("route", _WEIGHTED_ROUTES)
def test_plain_weighted_matching_retains_repeated_truth_protocol(route):
    lib = fnx if route in ("native-input", "matching-module") else nx
    actual, expected = _weighted_graph(lib), _weighted_graph(nx)
    _warm_weighted_input(actual, route)

    class TruthProvider:
        def __init__(self):
            self.calls = 0

        def __bool__(self):
            self.calls += 1
            if self.calls > 1:
                raise LookupError("repeated maxcardinality provider")
            return True

    actual_truth, expected_truth = TruthProvider(), TruthProvider()
    with pytest.raises(LookupError) as want:
        nx.max_weight_matching(expected, maxcardinality=expected_truth)
    with pytest.raises(LookupError) as got:
        _weighted_call(
            "max_weight_matching", actual, route, maxcardinality=actual_truth
        )
    assert got.value.args == want.value.args
    assert actual_truth.calls == expected_truth.calls == 2


@pytest.mark.parametrize("name", _WEIGHTED_APIS)
@pytest.mark.parametrize("route", ("networkx-input", "backend-cold", "backend-warm"))
@pytest.mark.parametrize("weight", (None, 0, ("cost", 1)))
def test_weighted_matching_retains_literal_attribute_keys(name, route, weight):
    actual, expected = _weighted_graph(nx), _weighted_graph(nx)
    for graph in (actual, expected):
        for u, v, data in graph.edges(data=True):
            data[weight] = 20 if frozenset((u, v)) in (
                frozenset((0, 1)), frozenset((2, 3))
            ) else 1
    _warm_weighted_input(actual, route)
    want = getattr(nx, name)(expected, weight=weight)
    assert _weighted_call(name, actual, route, weight=weight) == want


@pytest.mark.parametrize("name", _WEIGHTED_APIS)
@pytest.mark.parametrize("mutation", ("filter", "weight"))
def test_weighted_matching_recovers_warm_view_and_live_weights(name, mutation):
    def build():
        root = _weighted_graph(nx)
        visible = {frozenset((0, 1)), frozenset((2, 3))}
        graph = (
            nx.subgraph_view(root, filter_edge=lambda u, v: frozenset((u, v)) in visible)
            if mutation == "filter" else root
        )
        return root, graph, visible

    actual_root, actual, actual_visible = build()
    expected_root, expected, expected_visible = build()
    _warm_weighted_input(actual, "backend-warm")
    if mutation == "filter":
        for visible in (actual_visible, expected_visible):
            visible.clear()
            visible.update((frozenset((0, 3)), frozenset((1, 2))))
    else:
        for root in (actual_root, expected_root):
            root[0][1]["weight"] = 20
            root[2][3]["weight"] = 20

    assert _weighted_call(name, actual, "backend-warm") == getattr(nx, name)(expected)


@pytest.mark.parametrize("route", ("native-input", "networkx-input", "matching-module", "backend-cold"))
def test_min_weight_matching_empty_graph_preserves_edge_reader_order(route):
    lib = fnx if route in ("native-input", "matching-module") else nx
    actual, expected = lib.Graph(), nx.Graph()
    actual_events, expected_events = [], []
    actual.edges = _MatchingEdgeProvider(actual, actual_events, change_weights=False)
    expected.edges = _MatchingEdgeProvider(expected, expected_events, change_weights=False)

    assert _weighted_call("min_weight_matching", actual, route) == nx.min_weight_matching(expected) == set()
    assert actual_events == expected_events


@pytest.mark.parametrize("name", _WEIGHTED_APIS)
@pytest.mark.parametrize("route", ("native-input", "networkx-input", "backend-cold", "backend-warm"))
def test_plain_weighted_matching_keeps_native_blossom(name, route, monkeypatch):
    lib = fnx if route == "native-input" else nx
    actual, expected = _weighted_graph(lib), _weighted_graph(nx)
    _warm_weighted_input(actual, route)
    calls = []
    native = fnx._raw_networkx_max_weight_matching_mate

    def recorded(*args, **kwargs):
        calls.append(True)
        return native(*args, **kwargs)

    monkeypatch.setattr(fnx, "_raw_networkx_max_weight_matching_mate", recorded)
    assert _weighted_call(name, actual, route) == getattr(nx, name)(expected)
    assert calls
