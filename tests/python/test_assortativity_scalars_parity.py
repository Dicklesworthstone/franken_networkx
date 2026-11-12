"""Differential parity for assortativity scalars and numeric domains.

Covers ``average_degree_connectivity``, ``average_neighbor_degree`` and
``degree_pearson_correlation_coefficient``. Weighted sums preserve row order,
numeric types, self-loop grouping and observable provider behavior.

br-r37-c1-3v25j
"""

from __future__ import annotations

import math
import random
from decimal import Decimal
from fractions import Fraction

import pytest
import networkx as nx
import franken_networkx as fnx


def _pair(seed, directed=False, weighted=False, p=0.4):
    rng = random.Random(seed)
    n = rng.randint(6, 12)
    fnx_cls, nx_cls = (fnx.DiGraph, nx.DiGraph) if directed else (fnx.Graph, nx.Graph)
    fg = fnx_cls()
    ng = nx_cls()
    fg.add_nodes_from(range(n))
    ng.add_nodes_from(range(n))
    for u in range(n):
        for v in range(n):
            if u == v:
                continue
            if (directed or u < v) and rng.random() < p:
                if weighted:
                    w = round(rng.uniform(1, 4), 2)
                    fg.add_edge(u, v, weight=w)
                    ng.add_edge(u, v, weight=w)
                else:
                    fg.add_edge(u, v)
                    ng.add_edge(u, v)
    return fg, ng


def _dict_close(a, b, tol=1e-9):
    assert set(a) == set(b)
    for k in b:
        assert a[k] == pytest.approx(b[k], abs=tol)


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("weighted", [False, True])
@pytest.mark.parametrize("seed", range(25))
def test_average_degree_connectivity_matches_networkx(directed, weighted, seed):
    fg, ng = _pair(seed, directed=directed, weighted=weighted)
    kwargs = {"weight": "weight"} if weighted else {}
    _dict_close(
        fnx.average_degree_connectivity(fg, **kwargs),
        nx.average_degree_connectivity(ng, **kwargs),
    )


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("seed", range(25))
def test_average_neighbor_degree_matches_networkx(directed, seed):
    fg, ng = _pair(seed, directed=directed)
    _dict_close(fnx.average_neighbor_degree(fg), nx.average_neighbor_degree(ng))


@pytest.mark.parametrize("weighted", [False, True])
@pytest.mark.parametrize("seed", range(30))
def test_degree_pearson_correlation_matches_networkx(weighted, seed):
    fg, ng = _pair(seed, weighted=weighted)
    kwargs = {"weight": "weight"} if weighted else {}
    fr = fnx.degree_pearson_correlation_coefficient(fg, **kwargs)
    nr = nx.degree_pearson_correlation_coefficient(ng, **kwargs)
    if math.isnan(nr):
        assert math.isnan(fr)
    else:
        assert fr == pytest.approx(nr, abs=1e-7)


def test_average_degree_connectivity_golden():
    # Path 0-1-2-3: degree-1 nodes neighbour degree-2 nodes and vice versa.
    p4 = fnx.path_graph(4)
    assert fnx.average_degree_connectivity(p4) == {1: 2.0, 2: 1.5}
    assert fnx.average_degree_connectivity(p4) == nx.average_degree_connectivity(
        nx.path_graph(4)
    )


def test_directed_source_target_params_match_networkx():
    dg = fnx.DiGraph([(0, 1), (1, 2), (2, 0), (0, 2)])
    ndg = nx.DiGraph([(0, 1), (1, 2), (2, 0), (0, 2)])
    _dict_close(
        fnx.average_degree_connectivity(dg, source="in", target="out"),
        nx.average_degree_connectivity(ndg, source="in", target="out"),
    )


_DIRECTIONS = [("in+out", "in+out")] + [
    (source, target)
    for source in ("in", "out", "in+out")
    for target in ("in", "out", "in+out")
    if (source, target) != ("in+out", "in+out")
]


def _numeric_connectivity_graph(module, class_name, value):
    graph = getattr(module, class_name)()
    graph.add_nodes_from(["c", "a", "b", "isolated"])
    graph.add_edge("b", "a", cost=value)
    graph.add_edge("c", "a", cost=value * 2)
    graph.add_edge("a", "a", cost=value * 3)
    graph.add_edge("a", "c")  # A missing attribute has weight one.
    if graph.is_multigraph():
        graph.add_edge("b", "a", key="parallel", cost=value * 4)
    return graph


def _assert_exact_scalar_mapping(actual, expected):
    assert list(actual) == list(expected)
    for key, value in expected.items():
        assert type(actual[key]) is type(value)
        if isinstance(value, float) and math.isnan(value):
            assert math.isnan(actual[key])
        else:
            assert actual[key] == value


@pytest.mark.parametrize("class_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("value", [Decimal("1.5"), Fraction(3, 2), 10**400],
                         ids=["decimal", "fraction", "large-int"])
@pytest.mark.parametrize("selected", [None, ["b", "a", "isolated", "b"]])
def test_degree_connectivity_preserves_numeric_arithmetic(class_name, value, selected):
    """Weights must reach Python arithmetic without a float-zero coercion."""
    actual_graph = _numeric_connectivity_graph(fnx, class_name, value)
    expected_graph = _numeric_connectivity_graph(nx, class_name, value)
    directions = _DIRECTIONS if actual_graph.is_directed() else _DIRECTIONS[:1]
    for source, target in directions:
        kwargs = dict(source=source, target=target, nodes=selected, weight="cost")
        _assert_exact_scalar_mapping(
            fnx.average_degree_connectivity(actual_graph, **kwargs),
            nx.average_degree_connectivity(expected_graph, **kwargs),
        )


@pytest.mark.parametrize("class_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("selected", [99, 1.5, [[1]]])
def test_degree_connectivity_keeps_node_selection_errors(class_name, selected):
    outcomes = []
    for module in (nx, fnx):
        graph = _numeric_connectivity_graph(module, class_name, 2)
        try:
            result = module.average_degree_connectivity(graph, nodes=selected)
        except Exception as exc:
            outcomes.append((type(exc).__name__, exc.args))
        else:
            outcomes.append(("result", result))
    assert outcomes[0][0] == "NetworkXError"
    assert outcomes[1] == outcomes[0]


@pytest.mark.parametrize("class_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("selected", ["missing", "a", [], ["missing"], ["b", "missing", "b"]])
def test_degree_connectivity_keeps_node_selection_semantics(class_name, selected):
    actual_graph = _numeric_connectivity_graph(fnx, class_name, 2)
    expected_graph = _numeric_connectivity_graph(nx, class_name, 2)
    _assert_exact_scalar_mapping(
        fnx.average_degree_connectivity(actual_graph, nodes=selected, weight="cost"),
        nx.average_degree_connectivity(expected_graph, nodes=selected, weight="cost"),
    )


@pytest.mark.parametrize("class_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("selected", [None, ["n"]])
@pytest.mark.parametrize("with_loop", [False, True])
def test_degree_connectivity_preserves_float_reduction_grouping(class_name, selected, with_loop):
    graphs = []
    for module in (nx, fnx):
        graph = getattr(module, class_name)()
        graph.add_nodes_from(["n", "a", "b", "c", "d", "isolated"])
        graph.add_edge("n", "a", cost=1e16)
        if with_loop:
            graph.add_edge("n", "n", cost=1.5)
        else:
            graph.add_edge("n", "b", cost=3.0)
            graph.add_edge("b", "d", cost=1.0)
        graph.add_edge("n", "c", cost=-1e16)
        graphs.append(graph)
    expected_graph, actual_graph = graphs
    directions = _DIRECTIONS if actual_graph.is_directed() else _DIRECTIONS[:1]
    for source, target in directions:
        kwargs = dict(source=source, target=target, nodes=selected, weight="cost")
        _assert_exact_scalar_mapping(
            fnx.average_degree_connectivity(actual_graph, **kwargs),
            nx.average_degree_connectivity(expected_graph, **kwargs),
        )


@pytest.mark.parametrize("class_name", ["MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("selected", [None, ["n"]])
def test_degree_connectivity_sums_parallel_weights_before_neighbor_grouping(class_name, selected):
    outcomes = []
    for module in (nx, fnx):
        graph = getattr(module, class_name)()
        graph.add_edge("n", "a", cost=1e16)
        graph.add_edge("n", "a", cost=3.0)
        graph.add_edge("n", "b", cost=-1e16)
        kwargs = dict(nodes=selected, weight="cost")
        if graph.is_directed():
            kwargs.update(source="out", target="in")
        outcomes.append(module.average_degree_connectivity(graph, **kwargs))
    _assert_exact_scalar_mapping(outcomes[1], outcomes[0])


@pytest.mark.parametrize("selected", [None, ["n"]])
def test_degree_connectivity_keeps_predecessor_sum_order(selected):
    outcomes = []
    for module in (nx, fnx):
        graph = module.DiGraph()
        graph.add_nodes_from(["n", "a", "b", "c"])
        graph.add_edge("c", "n", cost=1e308)
        graph.add_edge("b", "n", cost=1e308)
        graph.add_edge("a", "n", cost=-1e308)
        outcomes.append(module.average_degree_connectivity(
            graph, source="in", target="out", nodes=selected, weight="cost"
        ))
    assert math.isnan(outcomes[0][3])
    _assert_exact_scalar_mapping(outcomes[1], outcomes[0])


@pytest.mark.parametrize("view_kind", ["undirected", "filtered", "reverse"])
@pytest.mark.parametrize("value", [1.0, Decimal("1.5"), Fraction(3, 2)])
def test_degree_connectivity_reads_logical_view_weights(view_kind, value):
    outcomes = []
    for module in (nx, fnx):
        root = module.DiGraph()
        for u, v, factor in [(0, 1, 2), (1, 0, 10), (0, 2, 1), (2, 0, 1), (1, 3, 1), (1, 4, 1)]:
            root.add_edge(u, v, cost=value * factor)
        if view_kind == "reverse":
            graph = root.reverse(copy=False)
        else:
            graph = root.to_undirected(as_view=True)
            if view_kind == "filtered":
                graph = graph.subgraph([0, 1, 2, 3])
        outcomes.append(module.average_degree_connectivity(graph, weight="cost"))
    _assert_exact_scalar_mapping(outcomes[1], outcomes[0])


def test_degree_connectivity_observes_numeric_callback_graph_mutations():
    class MutatingWeight:
        def __init__(self, graph):
            self.graph = graph

        def __mul__(self, value):
            self.graph.add_edge("b", "c", cost=1)
            return value

        def __radd__(self, value):
            return value + 1

    outcomes = []
    for module in (nx, fnx):
        graph = module.Graph()
        graph.add_nodes_from(["a", "b", "c", "d"])
        graph.add_edge("a", "b", cost=MutatingWeight(graph))
        graph.add_edge("c", "d", cost=1)
        outcomes.append(module.average_degree_connectivity(graph, weight="cost"))
    assert outcomes[0] == {1: 1.5, 2: 1.5}
    _assert_exact_scalar_mapping(outcomes[1], outcomes[0])


@pytest.mark.parametrize("mutation", ["remove_neighbor", "add_node"])
def test_degree_connectivity_keeps_callback_iteration_failures(mutation):
    outcomes = []
    for module in (nx, fnx):
        graph = module.Graph()
        graph.add_nodes_from(["a", "b", "c", "d"])
        events = []

        class MutatingWeight:
            def __mul__(self, value):
                events.append("multiply")
                if mutation == "remove_neighbor":
                    graph.remove_edge("a", "c")
                else:
                    graph.add_node("new")
                return value

            def __radd__(self, value):
                return value + 1

        graph.add_edge("a", "b", cost=MutatingWeight())
        graph.add_edge("a", "c", cost=1)
        graph.add_edge("c", "d", cost=1)
        try:
            result = module.average_degree_connectivity(graph, weight="cost")
        except Exception as exc:
            outcomes.append((type(exc).__name__, exc.args, events))
        else:
            outcomes.append(("result", result, events))
    assert outcomes[0][0] == ("KeyError" if mutation == "remove_neighbor" else "RuntimeError")
    assert outcomes[1] == outcomes[0]


@pytest.mark.parametrize("class_name", ["Graph", "DiGraph"])
def test_degree_connectivity_keeps_plain_weighted_native_rows(monkeypatch, class_name):
    graph = _numeric_connectivity_graph(fnx, class_name, 2.0)
    expected_graph = _numeric_connectivity_graph(nx, class_name, 2.0)
    list(graph.degree)
    list(graph.nodes)
    list(graph.adj)
    if graph.is_directed():
        list(graph.in_degree)
        list(graph.out_degree)
        list(graph.pred)
        list(graph.succ)
    calls = []
    original = getattr(fnx, class_name)._native_adjacency_dict

    def tracked(self):
        calls.append(self)
        return original(self)

    monkeypatch.setattr(getattr(fnx, class_name), "_native_adjacency_dict", tracked)
    for _ in range(2):
        _assert_exact_scalar_mapping(
            fnx.average_degree_connectivity(graph, weight="cost"),
            nx.average_degree_connectivity(expected_graph, weight="cost"),
        )
    assert calls == [graph, graph]
