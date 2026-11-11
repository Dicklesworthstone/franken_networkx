"""Regression coverage for backend-dispatch re-entry (br-parityrec).

When a user sets ``nx.config.backend_priority = ["franken_networkx"]``
to transparently accelerate nx calls, and then calls an algorithm that
fnx implements via the _call_networkx_for_parity fallback (because fnx
can't honour some argument, e.g. ``flow_func=``), the fallback must
bypass the backend dispatcher — otherwise ``getattr(nx, name)(...)``
re-enters the dispatcher and bounces right back into fnx, producing an
infinite RecursionError before the user ever sees a result.

Fix: _call_networkx_for_parity and _call_networkx_submodule_for_parity
both call nx with ``backend="networkx"`` to force the pure-Python nx
path.
"""

from __future__ import annotations

import warnings
from decimal import Decimal
from fractions import Fraction

import franken_networkx as fnx
import networkx as nx
import pytest


@pytest.fixture(autouse=True)
def _clear_backend_priority():
    prior_algos = list(nx.config.backend_priority.algos)
    yield
    nx.config.backend_priority.algos = prior_algos


def test_maximum_flow_value_with_flow_func_does_not_recurse():
    """flow_func triggers the parity fallback; recursion used to blow up."""
    nx.config.backend_priority.algos = ["franken_networkx"]

    G = nx.DiGraph()
    G.add_edge("s", "a", capacity=3)
    G.add_edge("s", "t", capacity=2)
    G.add_edge("a", "t", capacity=2)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        val = nx.maximum_flow_value(
            G,
            "s",
            "t",
            flow_func=nx.algorithms.flow.shortest_augmenting_path,
        )
    assert val == 4


def test_maximum_flow_default_still_uses_backend():
    """Regression-check that the dispatch-bypass patch did not break the
    ordinary dispatch path that reaches fnx's native implementation."""
    nx.config.backend_priority.algos = ["franken_networkx"]

    G = nx.DiGraph()
    G.add_edge("s", "a", capacity=3)
    G.add_edge("s", "t", capacity=2)
    G.add_edge("a", "t", capacity=2)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        val = nx.maximum_flow_value(G, "s", "t")
    assert val == 4


def test_average_shortest_path_length_with_method_does_not_recurse():
    """Explicit methods dispatch to the owned average-distance routes."""
    nx.config.backend_priority.algos = ["franken_networkx"]
    G = nx.path_graph(5)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        val = nx.average_shortest_path_length(G, method="dijkstra")
    assert val == pytest.approx(2.0)


_AVERAGE_METHODS = [
    None, "unweighted", "dijkstra", "bellman-ford",
    "floyd-warshall", "floyd-warshall-numpy",
]


def _average_outcome(call):
    try:
        value = call()
    except Exception as error:
        return "raise", type(error).__name__, str(error)
    return "return", type(value).__name__, repr(value)


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("method", _AVERAGE_METHODS)
@pytest.mark.parametrize("value", [2, Fraction(1, 3), Decimal("0.1"), 2**55 + 1])
def test_average_methods_dispatch_preserves_numeric_domains(graph_type, method, value):
    graph = getattr(nx, graph_type)([(0, 1), (1, 2), (2, 0)])
    for _, _, attrs in graph.edges(data=True):
        attrs["cost"] = value
    expected = _average_outcome(
        lambda: nx.average_shortest_path_length(
            graph, weight="cost", method=method, backend="networkx"
        )
    )
    assert _average_outcome(
        lambda: nx.average_shortest_path_length(
            graph, weight="cost", method=method, backend="franken_networkx"
        )
    ) == expected
    native = getattr(fnx, graph_type)()
    native.add_nodes_from(graph)
    native.add_edges_from(graph.edges(data=True))
    assert _average_outcome(
        lambda: fnx.average_shortest_path_length(native, weight="cost", method=method)
    ) == expected


@pytest.mark.parametrize("method", _AVERAGE_METHODS)
@pytest.mark.parametrize("weight", [None, 17, ("edge", "cost")])
def test_average_explicit_methods_keep_literal_weight_keys(method, weight):
    graph = nx.path_graph(3)
    for _, _, attrs in graph.edges(data=True):
        attrs[weight] = Fraction(1, 3)
    expected = _average_outcome(
        lambda: nx.average_shortest_path_length(
            graph, weight=weight, method=method, backend="networkx"
        )
    )
    assert _average_outcome(
        lambda: nx.average_shortest_path_length(
            graph, weight=weight, method=method, backend="franken_networkx"
        )
    ) == expected
    native = fnx.Graph(graph.edges(data=True))
    assert _average_outcome(
        lambda: fnx.average_shortest_path_length(native, weight=weight, method=method)
    ) == expected


@pytest.mark.parametrize("method", [*_AVERAGE_METHODS, "unsupported", []])
@pytest.mark.parametrize("shape", ["empty", "singleton", "disconnected", "not_strong"])
def test_average_method_validation_and_graph_errors_precede_weight_reads(method, shape):
    graph = nx.DiGraph() if shape == "not_strong" else nx.Graph()
    if shape == "singleton":
        graph.add_edge(0, 0, weight=-1)
    elif shape == "disconnected":
        graph.add_nodes_from([0, 1])
    elif shape == "not_strong":
        graph.add_edge(0, 1)

    def unexpected_weight(*args):
        raise AssertionError("weight evaluated before the graph boundary")

    expected = _average_outcome(
        lambda: nx.average_shortest_path_length(
            graph, weight=unexpected_weight, method=method, backend="networkx"
        )
    )
    assert _average_outcome(
        lambda: nx.average_shortest_path_length(
            graph, weight=unexpected_weight, method=method, backend="franken_networkx"
        )
    ) == expected
    assert _average_outcome(
        lambda: fnx.average_shortest_path_length(graph, weight=unexpected_weight, method=method)
    ) == expected


@pytest.mark.parametrize("method", ["dijkstra", "bellman-ford"])
@pytest.mark.parametrize("route", ["native", "foreign", "backend", "cached_backend"])
def test_average_weighted_source_validation_precedes_its_weight_resolution(method, route, monkeypatch):
    def run(reference):
        events = []
        module = fnx if not reference and route == "native" else nx

        class ObservedGraph(module.Graph):
            def __contains__(self, node):
                events.append(("contains", node))
                return super().__contains__(node)

            def is_multigraph(self):
                events.append("weight-function")
                return super().is_multigraph()

        graph = ObservedGraph([(0, 1)])
        graph[0][1][None] = 2
        if module is fnx:
            attrs = {None: 2}
            graph._adj = {0: {1: attrs}, 1: {0: attrs}}
        if not reference and route == "cached_backend":
            monkeypatch.setattr(nx.config, "cache_converted_graphs", True)
            nx.relabel_nodes(graph, {}, backend="franken_networkx")
        events.clear()
        if reference:
            result = nx.average_shortest_path_length(
                graph, weight=None, method=method, backend="networkx"
            )
        elif route in ("backend", "cached_backend"):
            result = nx.average_shortest_path_length(
                graph, weight=None, method=method, backend="franken_networkx"
            )
        else:
            result = fnx.average_shortest_path_length(graph, weight=None, method=method)
        return result, events

    assert run(False) == run(True)


@pytest.mark.parametrize("method", [None, "unweighted", "dijkstra", "bellman-ford"])
def test_average_plain_methods_keep_native_kernel(method, monkeypatch):
    namespace = fnx.average_shortest_path_length.__globals__
    native = namespace["_raw_average_shortest_path_length"]
    calls = []

    def record(graph, **kwargs):
        calls.append(type(graph))
        return native(graph, **kwargs)

    monkeypatch.setitem(namespace, "_raw_average_shortest_path_length", record)
    graph = nx.path_graph(3)
    nx.set_edge_attributes(graph, 2, "cost")
    expected = nx.average_shortest_path_length(graph, weight="cost", method=method, backend="networkx")
    assert nx.average_shortest_path_length(
        graph, weight="cost", method=method, backend="franken_networkx"
    ) == expected
    assert calls == [fnx.Graph]


@pytest.mark.parametrize("method", ["dijkstra", "bellman-ford", "floyd-warshall"])
@pytest.mark.parametrize("provider", ["is_directed", "is_multigraph"])
@pytest.mark.parametrize("route", ["foreign", "backend", "cached_backend"])
def test_average_graph_method_providers_keep_read_order(method, provider, route, monkeypatch):
    def run(reference):
        graph = nx.Graph()
        graph.add_edge(0, 1, cost=1)
        if not reference and route == "cached_backend":
            monkeypatch.setattr(nx.config, "cache_converted_graphs", True)
            nx.relabel_nodes(graph, {}, backend="franken_networkx")
        events = []

        def observed():
            events.append(provider)
            graph._adj[0][1]["cost"] += 1
            return False

        setattr(graph, provider, observed)
        if reference:
            result = nx.average_shortest_path_length(
                graph, weight="cost", method=method, backend="networkx"
            )
        elif route == "foreign":
            result = fnx.average_shortest_path_length(graph, weight="cost", method=method)
        else:
            result = nx.average_shortest_path_length(
                graph, weight="cost", method=method, backend="franken_networkx"
            )
        return result, events, graph._adj[0][1]["cost"]

    assert run(False) == run(True)


def test_maximum_flow_with_flow_func_does_not_recurse():
    nx.config.backend_priority.algos = ["franken_networkx"]
    G = nx.DiGraph()
    G.add_edge("s", "a", capacity=3)
    G.add_edge("s", "t", capacity=2)
    G.add_edge("a", "t", capacity=2)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        val, flow_dict = nx.maximum_flow(
            G, "s", "t", flow_func=nx.algorithms.flow.shortest_augmenting_path
        )
    assert val == 4
    assert flow_dict["s"]["a"] == 2
    assert flow_dict["s"]["t"] == 2


def test_minimum_cut_with_flow_func_does_not_recurse():
    nx.config.backend_priority.algos = ["franken_networkx"]
    G = nx.DiGraph()
    G.add_edge("s", "a", capacity=3)
    G.add_edge("s", "t", capacity=2)
    G.add_edge("a", "t", capacity=2)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        cut_val, partition = nx.minimum_cut(
            G, "s", "t", flow_func=nx.algorithms.flow.shortest_augmenting_path
        )
    assert cut_val == 4
    assert "s" in partition[0]
    assert "t" in partition[1]


def test_minimum_cut_value_with_flow_func_does_not_recurse():
    nx.config.backend_priority.algos = ["franken_networkx"]
    G = nx.DiGraph()
    G.add_edge("s", "a", capacity=3)
    G.add_edge("s", "t", capacity=2)
    G.add_edge("a", "t", capacity=2)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        cut_val = nx.minimum_cut_value(
            G, "s", "t", flow_func=nx.algorithms.flow.shortest_augmenting_path
        )
    assert cut_val == 4


def test_k_components_does_not_recurse():
    nx.config.backend_priority.algos = ["franken_networkx"]
    G = nx.cycle_graph(4)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        kc = nx.algorithms.connectivity.kcomponents.k_components(G)
    assert 2 in kc


def test_random_reference_does_not_recurse():
    nx.config.backend_priority.algos = ["franken_networkx"]
    G = nx.cycle_graph(4)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        rr = nx.algorithms.smallworld.random_reference(G, niter=1, seed=42)
    assert len(rr) == 4


def test_check_planarity_does_not_recurse():
    nx.config.backend_priority.algos = ["franken_networkx"]
    G = nx.cycle_graph(4)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        is_planar, _ = nx.check_planarity(G)
    assert is_planar is True


def test_junction_tree_does_not_recurse():
    nx.config.backend_priority.algos = ["franken_networkx"]
    G = nx.cycle_graph(4)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        jt = nx.junction_tree(G)
    assert len(jt) > 0


def test_random_kernel_graph_does_not_recurse():
    nx.config.backend_priority.algos = ["franken_networkx"]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        rkg = nx.random_kernel_graph(
            10,
            lambda u, w, z: z - w,
            lambda u, w, r: r + w,
            seed=42,
        )
    assert len(rkg) == 10


def test_read_edgelist_and_adjlist_do_not_recurse():
    import io
    nx.config.backend_priority.algos = ["franken_networkx"]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        f = io.BytesIO(b"1 2\n2 3\n")
        g = nx.read_edgelist(f)
        assert len(g) == 3
        f2 = io.BytesIO(b"1 2 3\n")
        g2 = nx.read_adjlist(f2)
        assert len(g2) == 3


def test_tutte_polynomial_does_not_recurse():
    pytest.importorskip("sympy")
    nx.config.backend_priority.algos = ["franken_networkx"]
    G = nx.cycle_graph(4)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        tp = nx.algorithms.polynomials.tutte_polynomial(G)
    assert tp is not None


