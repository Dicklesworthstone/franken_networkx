"""NetworkX conformance for the maximum-flow algorithm family.

Existing ``test_flow.py`` and ``test_flow_conformance_matrix.py`` cover
``edmonds_karp`` and the high-level ``maximum_flow`` /
``minimum_cut`` entry points. The other four algorithms
(``shortest_augmenting_path``, ``preflow_push``, ``dinitz``,
``boykov_kolmogorov``) had no broad differential coverage.

This harness asserts:

- All five algorithms produce the same maximum flow VALUE on every
  fixture (max-flow is unique even when the flow assignment differs).
- All five produce the same minimum cut VALUE.
- ``maximum_flow_value(G, s, t, flow_func=algo)`` agrees with
  ``algo(G, s, t).graph['flow_value']``.
- The cut partition is valid: ``s`` ∈ S-side, ``t`` ∈ T-side.
- Unreachable target raises ``NetworkXUnbounded`` (or returns 0)
  consistently across both libraries.
- Multigraph and DiGraph dispatch is identical.
- Edge cases: source == target, no path, infinite-capacity path.
"""

from __future__ import annotations

import itertools
import warnings
from decimal import Decimal
from fractions import Fraction

import pytest
import networkx as nx
from networkx.algorithms import flow as nx_flow

import franken_networkx as fnx
import franken_networkx.backend as fnx_backend


ALGORITHMS = [
    "edmonds_karp",
    "shortest_augmenting_path",
    "preflow_push",
    "dinitz",
    "boykov_kolmogorov",
]


def _pair_directed(edges_with_cap, capacity_attr="capacity"):
    fg = fnx.DiGraph()
    ng = nx.DiGraph()
    for tup in edges_with_cap:
        if len(tup) == 3:
            u, v, c = tup
            fg.add_edge(u, v, **{capacity_attr: c})
            ng.add_edge(u, v, **{capacity_attr: c})
        else:
            u, v = tup
            fg.add_edge(u, v)
            ng.add_edge(u, v)
    return fg, ng


# ---------------------------------------------------------------------------
# Fixtures — each is (name, edges_with_cap, source, target)
# ---------------------------------------------------------------------------


def _structured_fixtures():
    out = []
    out.append(("diamond",
                [("s", "a", 3), ("s", "b", 4),
                 ("a", "t", 3), ("b", "t", 4)],
                "s", "t"))
    out.append(("path_chain",
                [("s", "a", 5), ("a", "b", 3), ("b", "t", 4)],
                "s", "t"))
    out.append(("two_disjoint_paths",
                [("s", "a", 10), ("a", "t", 10),
                 ("s", "b", 5), ("b", "t", 5)],
                "s", "t"))
    out.append(("classic_demo",
                [("s", "a", 10), ("s", "b", 10), ("a", "b", 2),
                 ("a", "c", 4), ("a", "d", 8), ("b", "d", 9),
                 ("c", "t", 10), ("d", "c", 6), ("d", "t", 10)],
                "s", "t"))
    out.append(("ford_fulkerson_classic",
                [("s", "a", 16), ("s", "c", 13), ("a", "b", 12),
                 ("c", "a", 4), ("c", "d", 14), ("b", "c", 9),
                 ("b", "t", 20), ("d", "b", 7), ("d", "t", 4)],
                "s", "t"))
    out.append(("bottleneck",
                [("s", "a", 100), ("a", "b", 1), ("b", "t", 100)],
                "s", "t"))
    out.append(("multi_bottleneck",
                [("s", "a", 100), ("s", "b", 100),
                 ("a", "x", 1), ("b", "x", 1),
                 ("x", "t", 100)],
                "s", "t"))
    out.append(("complete_K_5_directed",
                [(u, v, float(u + v + 1))
                 for u in range(5) for v in range(5) if u != v],
                0, 4))
    out.append(("layered",
                [("s", "a", 7), ("s", "b", 4), ("a", "c", 5),
                 ("a", "d", 3), ("b", "c", 3), ("b", "d", 2),
                 ("c", "t", 8), ("d", "t", 5)],
                "s", "t"))
    return out


def _random_fixtures():
    out = []
    for n, p, seed in [(8, 0.3, 1), (10, 0.3, 2), (12, 0.25, 3),
                       (15, 0.2, 4)]:
        gnp = nx.gnp_random_graph(n, p, seed=seed, directed=True)
        # Add capacities derived from edge endpoints
        edges = [
            (u, v, float((u * 7 + v * 11 + seed) % 13 + 1))
            for u, v in gnp.edges()
        ]
        if not edges:
            continue
        nodes = list(range(n))
        # Pick source = 0, target = max node
        out.append((f"dir_gnp_n{n}_p{p}_s{seed}",
                    edges, 0, n - 1))
    return out


STRUCTURED = _structured_fixtures()
RANDOM = _random_fixtures()
ALL_FIXTURES = STRUCTURED + RANDOM


# ---------------------------------------------------------------------------
# Algorithm-by-algorithm flow value parity
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("algorithm", ALGORITHMS)
@pytest.mark.parametrize("name,edges,source,target", ALL_FIXTURES,
                         ids=[fx[0] for fx in ALL_FIXTURES])
def test_maximum_flow_value_per_algorithm_matches_networkx(
    name, edges, source, target, algorithm,
):
    fg, ng = _pair_directed(edges)
    fnx_fn = getattr(fnx.flow, algorithm)
    nx_fn = getattr(nx_flow, algorithm)
    try:
        nr = nx.maximum_flow_value(ng, source, target, flow_func=nx_fn)
    except nx.NetworkXUnbounded:
        with pytest.raises(fnx.NetworkXUnbounded):
            fnx.maximum_flow_value(fg, source, target, flow_func=fnx_fn)
        return
    fr = fnx.maximum_flow_value(fg, source, target, flow_func=fnx_fn)
    assert fr == nr, f"{name} {algorithm}: fnx={fr} nx={nr}"


@pytest.mark.parametrize("algorithm", ALGORITHMS)
@pytest.mark.parametrize("name,edges,source,target", ALL_FIXTURES,
                         ids=[fx[0] for fx in ALL_FIXTURES])
def test_minimum_cut_value_per_algorithm_matches_networkx(
    name, edges, source, target, algorithm,
):
    fg, ng = _pair_directed(edges)
    fnx_fn = getattr(fnx.flow, algorithm)
    nx_fn = getattr(nx_flow, algorithm)
    try:
        nr_val, _ = nx.minimum_cut(ng, source, target, flow_func=nx_fn)
    except nx.NetworkXUnbounded:
        with pytest.raises(fnx.NetworkXUnbounded):
            fnx.minimum_cut(fg, source, target, flow_func=fnx_fn)
        return
    fr_val, _ = fnx.minimum_cut(fg, source, target, flow_func=fnx_fn)
    assert fr_val == nr_val, f"{name} {algorithm}: fnx={fr_val} nx={nr_val}"


# ---------------------------------------------------------------------------
# Cross-algorithm consistency: all 5 give the same flow value
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,edges,source,target", ALL_FIXTURES,
                         ids=[fx[0] for fx in ALL_FIXTURES])
def test_all_algorithms_produce_same_max_flow_value(
    name, edges, source, target,
):
    """Maximum flow is unique even if the flow assignment differs;
    every algorithm must report the same value."""
    fg, _ = _pair_directed(edges)
    values = {}
    for algorithm in ALGORITHMS:
        fnx_fn = getattr(fnx.flow, algorithm)
        try:
            v = fnx.maximum_flow_value(fg, source, target, flow_func=fnx_fn)
        except (fnx.NetworkXUnbounded, nx.NetworkXUnbounded):
            return
        values[algorithm] = v
    distinct_values = set(values.values())
    assert len(distinct_values) == 1, (
        f"{name}: algorithms disagree on max flow value: {values}"
    )


# ---------------------------------------------------------------------------
# Direct algorithm call: residual graph has flow_value annotation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("algorithm", ALGORITHMS)
@pytest.mark.parametrize(
    "name,edges,source,target",
    [fx for fx in STRUCTURED if fx[0] != "complete_K_5_directed"],
    ids=[fx[0] for fx in STRUCTURED if fx[0] != "complete_K_5_directed"],
)
def test_algorithm_residual_flow_value_matches_maximum_flow_value(
    name, edges, source, target, algorithm,
):
    """The residual returned by ``algo(G, s, t)`` carries a
    ``flow_value`` attribute equal to ``maximum_flow_value(...,
    flow_func=algo)``."""
    fg, _ = _pair_directed(edges)
    fnx_fn = getattr(fnx.flow, algorithm)
    residual = fnx_fn(fg, source, target)
    flow_value = residual.graph["flow_value"]
    expected = fnx.maximum_flow_value(fg, source, target, flow_func=fnx_fn)
    assert flow_value == expected, (
        f"{name} {algorithm}: residual.flow_value={flow_value}, "
        f"maximum_flow_value={expected}"
    )


def test_edmonds_karp_integral_residual_value_types_match_networkx():
    fg, ng = _pair_directed([("s", "a", 3), ("a", "t", 3)])

    fr = fnx.flow.edmonds_karp(fg, "s", "t")
    nr = nx_flow.edmonds_karp(ng, "s", "t")

    assert fr.graph["flow_value"] == nr.graph["flow_value"]
    assert isinstance(fr.graph["flow_value"], int)
    assert fr.graph["inf"] == nr.graph["inf"]
    assert isinstance(fr.graph["inf"], int)

    for u, v in nr.edges():
        fattrs = fr[u][v]
        nattrs = nr[u][v]
        assert fattrs["capacity"] == nattrs["capacity"]
        assert isinstance(fattrs["capacity"], int)
        assert fattrs["flow"] == nattrs["flow"]
        assert isinstance(fattrs["flow"], int)


def test_high_level_flow_with_fnx_edmonds_karp_preserves_integral_types():
    fg, ng = _pair_directed([("s", "a", 3), ("a", "t", 3)])

    fnx_value = fnx.maximum_flow_value(fg, "s", "t", flow_func=fnx.flow.edmonds_karp)
    nx_value = nx.maximum_flow_value(ng, "s", "t", flow_func=nx_flow.edmonds_karp)
    assert fnx_value == nx_value
    assert isinstance(fnx_value, int)

    fnx_cut = fnx.minimum_cut_value(fg, "s", "t", flow_func=fnx.flow.edmonds_karp)
    nx_cut = nx.minimum_cut_value(ng, "s", "t", flow_func=nx_flow.edmonds_karp)
    assert fnx_cut == nx_cut
    assert isinstance(fnx_cut, int)


@pytest.mark.parametrize("capacity", [None, "bad"])
def test_edmonds_karp_malformed_capacity_raises_like_networkx(capacity):
    fg, ng = _pair_directed([("s", "t", capacity)])
    with pytest.raises(Exception) as nx_exc:
        nx_flow.edmonds_karp(ng, "s", "t")
    with pytest.raises(type(nx_exc.value)) as fnx_exc:
        fnx.flow.edmonds_karp(fg, "s", "t")
    assert str(fnx_exc.value) == str(nx_exc.value)


# ---------------------------------------------------------------------------
# Min-cut partition validity
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("algorithm", ALGORITHMS)
@pytest.mark.parametrize(
    "name,edges,source,target",
    [fx for fx in STRUCTURED if fx[0] != "complete_K_5_directed"],
    ids=[fx[0] for fx in STRUCTURED if fx[0] != "complete_K_5_directed"],
)
def test_minimum_cut_partition_separates_source_and_target(
    name, edges, source, target, algorithm,
):
    """The returned partition must place ``source`` in the S-side and
    ``target`` in the T-side. Together S and T must cover every node
    in the graph and be disjoint."""
    fg, _ = _pair_directed(edges)
    fnx_fn = getattr(fnx.flow, algorithm)
    cut_value, (S, T) = fnx.minimum_cut(fg, source, target, flow_func=fnx_fn)
    assert source in S, f"{name} {algorithm}: source not in S-side"
    assert target in T, f"{name} {algorithm}: target not in T-side"
    assert S.isdisjoint(T), f"{name} {algorithm}: S and T overlap"
    assert S | T == set(fg.nodes()), (
        f"{name} {algorithm}: S ∪ T does not cover all nodes"
    )


# ---------------------------------------------------------------------------
# Edge cases — source == target, no path, infinite capacity
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("algorithm", ALGORITHMS)
def test_no_path_returns_zero_or_raises(algorithm):
    """Disconnected source/target — different algorithms handle this
    differently, but fnx must mirror NX exactly."""
    fg = fnx.DiGraph()
    ng = nx.DiGraph()
    for u, v in [("s", "a"), ("b", "t")]:
        fg.add_edge(u, v, capacity=10)
        ng.add_edge(u, v, capacity=10)
    fnx_fn = getattr(fnx.flow, algorithm)
    nx_fn = getattr(nx_flow, algorithm)
    try:
        nr = nx.maximum_flow_value(ng, "s", "t", flow_func=nx_fn)
    except Exception as nx_exc:
        with pytest.raises(type(nx_exc)):
            fnx.maximum_flow_value(fg, "s", "t", flow_func=fnx_fn)
        return
    fr = fnx.maximum_flow_value(fg, "s", "t", flow_func=fnx_fn)
    assert fr == nr


@pytest.mark.parametrize("algorithm", ALGORITHMS)
def test_infinite_capacity_path_raises_unbounded(algorithm):
    """A path with no capacity attribute (default = inf) makes max flow
    unbounded; both libraries raise ``NetworkXUnbounded``."""
    fg = fnx.DiGraph()
    ng = nx.DiGraph()
    for u, v in [("s", "a"), ("a", "t")]:  # no capacity → infinite
        fg.add_edge(u, v)
        ng.add_edge(u, v)
    fnx_fn = getattr(fnx.flow, algorithm)
    nx_fn = getattr(nx_flow, algorithm)
    with pytest.raises(nx.NetworkXUnbounded):
        nx.maximum_flow_value(ng, "s", "t", flow_func=nx_fn)
    with pytest.raises(fnx.NetworkXUnbounded):
        fnx.maximum_flow_value(fg, "s", "t", flow_func=fnx_fn)


def test_high_level_flow_treats_negative_capacity_like_networkx():
    fg, ng = _pair_directed([("s", "t", -1)])

    assert fnx.maximum_flow_value(fg, "s", "t") == nx.maximum_flow_value(
        ng, "s", "t"
    )
    assert fnx.maximum_flow(fg, "s", "t") == nx.maximum_flow(ng, "s", "t")
    assert fnx.minimum_cut_value(fg, "s", "t") == nx.minimum_cut_value(
        ng, "s", "t"
    )
    assert fnx.minimum_cut(fg, "s", "t") == nx.minimum_cut(ng, "s", "t")


@pytest.mark.parametrize(
    "function",
    [nx.maximum_flow, nx.maximum_flow_value, nx.minimum_cut, nx.minimum_cut_value],
)
def test_high_level_flow_rejects_numeric_string_capacity_like_networkx(function):
    fg, ng = _pair_directed([("s", "t", "3")])

    with pytest.raises(TypeError) as nx_exc:
        function(ng, "s", "t")
    with pytest.raises(TypeError) as fnx_exc:
        getattr(fnx, function.__name__)(fg, "s", "t")
    assert str(fnx_exc.value) == str(nx_exc.value)


@pytest.mark.parametrize("capacity,expected", [(True, 1), (False, 0)])
def test_high_level_flow_boolean_capacity_preserves_networkx_int_type(
    capacity, expected,
):
    fg, ng = _pair_directed([("s", "t", capacity)])

    fnx_value = fnx.maximum_flow_value(fg, "s", "t")
    nx_value = nx.maximum_flow_value(ng, "s", "t")
    assert fnx_value == nx_value == expected
    assert isinstance(fnx_value, int)

    fnx_cut_value = fnx.minimum_cut_value(fg, "s", "t")
    nx_cut_value = nx.minimum_cut_value(ng, "s", "t")
    assert fnx_cut_value == nx_cut_value == expected
    assert isinstance(fnx_cut_value, int)


@pytest.mark.parametrize("graph_cls", [fnx.Graph, fnx.DiGraph])
@pytest.mark.parametrize("function_name", ["maximum_flow_value", "minimum_cut_value"])
@pytest.mark.parametrize(
    "edges",
    [
        [("s", "x", 0.0), ("x", "t", 0.0)],
        [("s", "x", 1.0), ("x", "q", 1.0), ("y", "t", 1.0)],
    ],
    ids=["zero_float_path", "disconnected_float_path"],
)
def test_high_level_flow_zero_float_result_preserves_networkx_int_type(
    graph_cls, function_name, edges,
):
    fnx_graph = graph_cls()
    nx_graph = nx.DiGraph() if graph_cls is fnx.DiGraph else nx.Graph()
    for u, v, capacity in edges:
        fnx_graph.add_edge(u, v, capacity=capacity)
        nx_graph.add_edge(u, v, capacity=capacity)

    actual = getattr(fnx, function_name)(fnx_graph, "s", "t")
    expected = getattr(nx, function_name)(nx_graph, "s", "t")
    assert actual == expected == 0
    assert type(actual) is type(expected) is int


@pytest.mark.parametrize("algorithm", ALGORITHMS)
def test_source_equals_target_raises_or_zero(algorithm):
    """``s == t`` is degenerate — both libraries must mirror exactly
    (NX raises NetworkXError)."""
    fg = fnx.DiGraph()
    ng = nx.DiGraph()
    fg.add_edge(0, 1, capacity=5)
    ng.add_edge(0, 1, capacity=5)
    fnx_fn = getattr(fnx.flow, algorithm)
    nx_fn = getattr(nx_flow, algorithm)
    with pytest.raises(nx.NetworkXError) as nx_exc:
        nx.maximum_flow_value(ng, 0, 0, flow_func=nx_fn)
    with pytest.raises(fnx.NetworkXError) as fnx_exc:
        fnx.maximum_flow_value(fg, 0, 0, flow_func=fnx_fn)
    assert str(fnx_exc.value) == str(nx_exc.value)


@pytest.mark.parametrize("graph_cls", [nx.MultiGraph, nx.MultiDiGraph])
@pytest.mark.parametrize(
    "function",
    [nx.maximum_flow, nx.maximum_flow_value, nx.minimum_cut, nx.minimum_cut_value],
)
def test_high_level_flow_rejects_multigraphs_like_networkx(graph_cls, function):
    fnx_graph_cls = getattr(fnx, graph_cls.__name__)
    fg = fnx_graph_cls()
    ng = graph_cls()
    fg.add_edge("s", "t", capacity=1)
    ng.add_edge("s", "t", capacity=1)

    with pytest.raises(nx.NetworkXError) as nx_exc:
        function(ng, "s", "t")
    with pytest.raises(fnx.NetworkXError) as fnx_exc:
        getattr(fnx, function.__name__)(fg, "s", "t")
    assert str(fnx_exc.value) == str(nx_exc.value)


# ---------------------------------------------------------------------------
# minimum_cut_value — high-level entry point
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("algorithm", ALGORITHMS)
@pytest.mark.parametrize("name,edges,source,target", ALL_FIXTURES,
                         ids=[fx[0] for fx in ALL_FIXTURES])
def test_minimum_cut_value_high_level_matches_networkx(
    name, edges, source, target, algorithm,
):
    fg, ng = _pair_directed(edges)
    fnx_fn = getattr(fnx.flow, algorithm)
    nx_fn = getattr(nx_flow, algorithm)
    try:
        nr = nx.minimum_cut_value(ng, source, target, flow_func=nx_fn)
    except nx.NetworkXUnbounded:
        with pytest.raises(fnx.NetworkXUnbounded):
            fnx.minimum_cut_value(fg, source, target, flow_func=fnx_fn)
        return
    fr = fnx.minimum_cut_value(fg, source, target, flow_func=fnx_fn)
    assert fr == nr


# ---------------------------------------------------------------------------
# Custom capacity attribute name
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("algorithm", ALGORITHMS)
def test_custom_capacity_attribute_name(algorithm):
    edges = [("s", "a", 3), ("s", "b", 4), ("a", "t", 3), ("b", "t", 4)]
    fg, ng = _pair_directed(edges, capacity_attr="weight")
    fnx_fn = getattr(fnx.flow, algorithm)
    nx_fn = getattr(nx_flow, algorithm)
    fr = fnx.maximum_flow_value(fg, "s", "t", capacity="weight",
                                 flow_func=fnx_fn)
    nr = nx.maximum_flow_value(ng, "s", "t", capacity="weight",
                                flow_func=nx_fn)
    assert fr == nr


def test_minimum_cut_uses_custom_flow_func_and_forwards_kwargs():
    fg, ng = _pair_directed([("s", "a", 3), ("a", "t", 3)])
    calls = []

    def sentinel(G, s, t, capacity="capacity", residual=None, value_only=False, **kwargs):
        calls.append((s, t, capacity, kwargs.get("marker")))
        return nx_flow.edmonds_karp(
            G,
            s,
            t,
            capacity=capacity,
            residual=residual,
            value_only=value_only,
        )

    fr = fnx.minimum_cut(fg, "s", "t", flow_func=sentinel, marker="fnx")
    assert calls == [("s", "t", "capacity", "fnx")]

    calls.clear()
    nr = nx.minimum_cut(ng, "s", "t", flow_func=sentinel, marker="nx")
    assert calls == [("s", "t", "capacity", "nx")]
    assert fr == nr


def test_minimum_cut_value_uses_custom_flow_func_and_forwards_kwargs():
    fg, ng = _pair_directed([("s", "a", 3), ("a", "t", 3)])
    calls = []

    def sentinel(G, s, t, capacity="capacity", residual=None, value_only=False, **kwargs):
        calls.append((s, t, capacity, kwargs.get("marker")))
        return nx_flow.edmonds_karp(
            G,
            s,
            t,
            capacity=capacity,
            residual=residual,
            value_only=value_only,
        )

    fr = fnx.minimum_cut_value(fg, "s", "t", flow_func=sentinel, marker="fnx")
    assert calls == [("s", "t", "capacity", "fnx")]

    calls.clear()
    nr = nx.minimum_cut_value(ng, "s", "t", flow_func=sentinel, marker="nx")
    assert calls == [("s", "t", "capacity", "nx")]
    assert fr == nr


def _int_keyed_flow_graph(module):
    # networkx's test_mincost.py::test_digraph3: attribute keys 0 and 1.
    G = module.DiGraph()
    for u, v, cap, cost in [
        ("s", "a", 2, 4), ("s", "b", 2, 1), ("a", "b", 5, 2),
        ("a", "t", 1, 5), ("b", "a", 1, 3), ("b", "t", 3, 2),
    ]:
        G.add_edge(u, v)
        G[u][v].update({0: cap, 1: cost})
    return G


def test_non_string_attribute_keys_reach_networkx_results():
    # nro4w.7: networkx accepts any hashable attribute key; the native
    # max-flow kernels take capacity by string name, so capacity=0 raised
    # TypeError before any flow was computed.
    fg, ng = _int_keyed_flow_graph(fnx), _int_keyed_flow_graph(nx)
    fsol = fnx.max_flow_min_cost(fg, "s", "t", capacity=0, weight=1)
    nsol = nx.max_flow_min_cost(ng, "s", "t", capacity=0, weight=1)
    assert fsol == nsol
    assert fnx.cost_of_flow(fg, fsol, weight=1) == nx.cost_of_flow(ng, nsol, weight=1) == 23
    for name in ("maximum_flow", "maximum_flow_value", "minimum_cut", "minimum_cut_value"):
        assert getattr(fnx, name)(fg, "s", "t", capacity=0) == getattr(nx, name)(
            ng, "s", "t", capacity=0
        ), name


_HIGH_LEVEL_FLOW_APIS = (
    "maximum_flow", "maximum_flow_value", "minimum_cut", "minimum_cut_value"
)


def _forbid_networkx_flow(*args, **kwargs):
    raise AssertionError("owned flow must not convert to or execute through NetworkX")


@pytest.mark.parametrize("name", _HIGH_LEVEL_FLOW_APIS)
@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("capacity", [10**100, Fraction(2, 3), Decimal("0.7")])
def test_general_capacity_flow_runs_without_networkx(
    monkeypatch, name, directed, capacity
):
    nx_graph = nx.DiGraph() if directed else nx.Graph()
    nx_graph.add_edge("s", "a", capacity=capacity)
    nx_graph.add_edge("a", "t", capacity=capacity)
    nx_graph.add_edge("s", "dead", capacity=capacity * 2)
    nx_graph.add_node("isolated")
    fnx_graph = fnx.DiGraph() if directed else fnx.Graph()
    fnx_graph.add_nodes_from(nx_graph)
    fnx_graph.add_edges_from(nx_graph.edges(data=True))
    expected = getattr(nx, name)(nx_graph, "s", "t")

    monkeypatch.setattr(fnx_backend, "_fnx_to_nx", _forbid_networkx_flow)
    for entrypoint in _HIGH_LEVEL_FLOW_APIS:
        monkeypatch.setattr(nx_flow.maxflow, entrypoint, _forbid_networkx_flow)
    actual = getattr(fnx, name)(fnx_graph, "s", "t")
    assert actual == expected
    actual_value = actual[0] if isinstance(actual, tuple) else actual
    expected_value = expected[0] if isinstance(expected, tuple) else expected
    assert type(actual_value) is type(expected_value)


@pytest.mark.parametrize("name", _HIGH_LEVEL_FLOW_APIS)
@pytest.mark.parametrize("algorithm", ALGORITHMS)
def test_flow_callback_reuses_original_graph_and_residual(monkeypatch, name, algorithm):
    edges = [
        ("s", "a", 8), ("a", "t", 2), ("s", "b", 4),
        ("b", "t", 3), ("s", "dead", 7), ("a", "b", 1),
    ]
    fg, ng = _pair_directed(edges, capacity_attr="budget")
    fg.add_node("isolated")
    ng.add_node("isolated")
    nx_solver = getattr(nx_flow, algorithm)
    fnx_solver = getattr(fnx.flow, algorithm)
    expected = getattr(nx, name)(
        ng, "s", "t", capacity="budget", flow_func=nx_solver
    )
    residual = fnx.flow.build_residual_network(fg, "budget")
    held_attrs = {(u, v): attrs for u, v, attrs in residual.edges(data=True)}
    edge_order = list(residual.edges())
    marker = object()
    residual.graph["caller_marker"] = marker
    calls = []

    def solver(graph, source, target, *, capacity, value_only, residual, marker):
        calls.append((graph, source, target, capacity, value_only, residual, marker))
        result = fnx_solver(
            graph, source, target, capacity=capacity,
            value_only=value_only, residual=residual,
        )
        assert result is residual
        return result

    monkeypatch.setattr(fnx_backend, "_fnx_to_nx", _forbid_networkx_flow)
    for entrypoint in _HIGH_LEVEL_FLOW_APIS:
        monkeypatch.setattr(nx_flow.maxflow, entrypoint, _forbid_networkx_flow)
    actual = getattr(fnx, name)(
        fg, "s", "t", capacity="budget", flow_func=solver,
        residual=residual, marker=marker,
    )
    assert actual == expected
    assert len(calls) == 1
    graph, source, target, capacity, value_only, used_residual, received_marker = calls[0]
    assert graph is fg
    assert (source, target, capacity) == ("s", "t", "budget")
    assert value_only is (name != "maximum_flow")
    assert used_residual is residual
    assert received_marker is marker
    assert residual.graph["caller_marker"] is marker
    assert list(residual.edges()) == edge_order
    for (u, v), attrs in held_attrs.items():
        assert residual[u][v] is attrs


@pytest.mark.parametrize("name", ["minimum_cut", "minimum_cut_value"])
def test_cut_rejects_preflow_cutoff_before_invoking_solver(name):
    fg, ng = _pair_directed([("s", "a", 4), ("a", "t", 3)])
    with pytest.raises(nx.NetworkXError) as expected:
        getattr(nx, name)(ng, "s", "t", flow_func=nx_flow.preflow_push, cutoff=1)
    for solver in (nx_flow.preflow_push, fnx.flow.preflow_push):
        with pytest.raises(fnx.NetworkXError) as actual:
            getattr(fnx, name)(fg, "s", "t", flow_func=solver, cutoff=1)
        assert str(actual.value) == str(expected.value)


@pytest.mark.parametrize("name", _HIGH_LEVEL_FLOW_APIS)
def test_explicit_augmenting_flow_retains_cutoff_behavior(name):
    fg, ng = _pair_directed([
        ("s", "a", 3), ("a", "t", 3),
        ("s", "b", 5), ("b", "t", 5),
    ])
    expected = getattr(nx, name)(
        ng, "s", "t", flow_func=nx_flow.edmonds_karp, cutoff=2
    )
    actual = getattr(fnx, name)(
        fg, "s", "t", flow_func=fnx.flow.edmonds_karp, cutoff=2
    )
    assert actual == expected


def _custom_flow_input(module, kind):
    """Return graph shapes whose storage must stay live across a callback."""
    graph_module = nx if kind == "networkx" else module
    root = graph_module.DiGraph()
    root.add_nodes_from(["s", "a", "t"])
    edges = [("s", "a", 5), ("a", "t", 2)]
    if kind == "reverse":
        edges = [(v, u, capacity) for u, v, capacity in edges]
    for u, v, capacity in edges:
        root.add_edge(u, v, budget=capacity)
    if kind == "subgraph":
        root.add_edge("s", "hidden", budget=20)
        root.add_edge("hidden", "t", budget=20)
        return root.subgraph(["s", "a", "t"])
    if kind == "reverse":
        return root.reverse(copy=False)
    if kind == "shared_copy":
        from copy import copy

        return copy(root)
    if kind == "assigned":
        graph = module.DiGraph()
        nodes = {node: dict(attrs) for node, attrs in root.nodes(data=True)}
        successors = {node: {} for node in root}
        predecessors = {node: {} for node in root}
        for u, v, attrs in root.edges(data=True):
            data = dict(attrs)
            successors[u][v] = data
            predecessors[v][u] = data
        graph._node = nodes
        graph._succ = successors
        graph._pred = predecessors
        return graph
    return root


@pytest.mark.parametrize("name", _HIGH_LEVEL_FLOW_APIS)
@pytest.mark.parametrize(
    "kind", ["native", "networkx", "subgraph", "reverse", "assigned", "shared_copy"]
)
def test_custom_flow_solver_receives_live_caller_graph(name, kind):
    outcomes = []
    for module in (fnx, nx):
        graph = _custom_flow_input(module, kind)
        marker = object()
        calls = []

        def solver(received, source, target, *, capacity, value_only, marker):
            calls.append((received, source, target, capacity, value_only))
            # Update through the caller's reference after the high-level call
            # has begun. A converted snapshot would still see capacity 2.
            graph["a"]["t"]["budget"] = 4
            received.graph["solver_marker"] = marker
            return nx_flow.edmonds_karp(
                received, source, target,
                capacity=capacity, value_only=value_only,
            )

        result = getattr(module, name)(
            graph, "s", "t", capacity="budget", flow_func=solver, marker=marker
        )
        value = result[0] if isinstance(result, tuple) else result
        assert value == 4
        assert len(calls) == 1
        received, source, target, capacity, value_only = calls[0]
        assert received is graph
        assert (source, target, capacity) == ("s", "t", "budget")
        assert value_only is (name != "maximum_flow")
        assert graph.graph["solver_marker"] is marker
        assert graph["a"]["t"]["budget"] == 4
        outcomes.append(result)
    assert outcomes[0] == outcomes[1]


@pytest.mark.parametrize("name", _HIGH_LEVEL_FLOW_APIS)
@pytest.mark.parametrize("kind", ["missing_endpoints", "multigraph"])
def test_custom_flow_solver_owns_input_validation(name, kind):
    for module in (fnx, nx):
        graph = module.MultiDiGraph() if kind == "multigraph" else module.DiGraph()
        if kind == "multigraph":
            graph.add_edge("s", "t", capacity=3)
        calls = []

        def solver(received, source, target, **kwargs):
            calls.append(received)
            raise LookupError("custom solver input validation")

        with pytest.raises(LookupError, match="custom solver input validation"):
            getattr(module, name)(graph, "s", "t", flow_func=solver)
        assert len(calls) == 1
        assert calls[0] is graph


@pytest.mark.parametrize("name", _HIGH_LEVEL_FLOW_APIS)
@pytest.mark.parametrize("prewarm", [False, True])
@pytest.mark.parametrize("keyword_arguments", [False, True])
@pytest.mark.parametrize("kind", ["networkx", "subgraph"])
def test_backend_custom_flow_preserves_graph_residual_and_mutations(
    name, prewarm, keyword_arguments, kind
):
    def run(backend_name):
        graph = _custom_flow_input(nx, kind)
        if prewarm and backend_name == "franken_networkx":
            assert nx.maximum_flow_value(
                graph, "s", "t", capacity="budget", backend=backend_name
            ) == 2
        residual = nx_flow.build_residual_network(graph, "budget", backend="networkx")
        held_attrs = {(u, v): attrs for u, v, attrs in residual.edges(data=True)}
        marker = object()
        calls = []

        def solver(received, source, target, *, capacity, value_only, residual, marker):
            calls.append((received, source, target, capacity, value_only, residual, marker))
            # The second invocation reuses the residual left by the first.
            # Reading through received also catches a detached backend copy.
            graph["a"]["t"]["budget"] = 5 - len(calls)
            residual["a"]["t"]["capacity"] = received["a"]["t"][capacity]
            received.graph["solver_marker"] = marker
            return nx_flow.edmonds_karp(
                received, source, target, capacity=capacity,
                value_only=value_only, residual=residual, backend="networkx",
            )

        results = []
        for expected_capacity in (4, 3):
            options = {
                "residual": residual, "marker": marker, "backend": backend_name,
            }
            if keyword_arguments:
                result = getattr(nx, name)(
                    flowG=graph, _s="s", _t="t", capacity="budget",
                    flow_func=solver, **options,
                )
            else:
                result = getattr(nx, name)(graph, "s", "t", "budget", solver, **options)
            value = result[0] if isinstance(result, tuple) else result
            assert value == expected_capacity
            received, source, target, capacity, value_only, supplied, token = calls[-1]
            assert received is graph
            assert supplied is residual
            assert token is marker
            assert (source, target, capacity) == ("s", "t", "budget")
            assert value_only is (name != "maximum_flow")
            assert graph.graph["solver_marker"] is marker
            assert graph["a"]["t"]["budget"] == expected_capacity
            if backend_name == "franken_networkx":
                assert all(residual[u][v] is attrs for (u, v), attrs in held_attrs.items())
                # Direct attribute writes do not clear NetworkX's conversion
                # cache. A later native query must still see the callback's write.
                assert nx.maximum_flow_value(
                    graph, "s", "t", capacity="budget", backend=backend_name
                ) == expected_capacity
            results.append(result)
        assert len(calls) == 2
        return results

    assert run("franken_networkx") == run("networkx")


@pytest.mark.parametrize("name", _HIGH_LEVEL_FLOW_APIS)
@pytest.mark.parametrize("keyword_arguments", [False, True])
def test_backend_custom_flow_keeps_explicit_native_graph(name, keyword_arguments):
    original = _custom_flow_input(nx, "networkx")
    graph = fnx_backend.BackendInterface.convert_from_nx(
        original, edge_attrs={"budget": 1}, name=name,
    )
    graph["a"]["t"]["budget"] = 4
    calls = []

    def solver(received, source, target, *, capacity, value_only):
        calls.append(received)
        assert received is graph
        received.graph["solver_visited"] = True
        return nx_flow.edmonds_karp(
            received, source, target, capacity=capacity,
            value_only=value_only, backend="networkx",
        )

    if keyword_arguments:
        result = getattr(nx, name)(
            flowG=graph, _s="s", _t="t", capacity="budget",
            flow_func=solver, backend="franken_networkx",
        )
    else:
        result = getattr(nx, name)(
            graph, "s", "t", "budget", solver, backend="franken_networkx"
        )
    value = result[0] if isinstance(result, tuple) else result
    assert value == 4
    assert calls == [graph]
    assert graph.graph["solver_visited"] is True
    assert original["a"]["t"]["budget"] == 2
    assert "solver_visited" not in original.graph


@pytest.mark.parametrize("name", _HIGH_LEVEL_FLOW_APIS)
def test_backend_custom_flow_clears_cache_after_solver_exception(name):
    graph = _custom_flow_input(nx, "networkx")
    assert nx.maximum_flow_value(
        graph, "s", "t", capacity="budget", backend="franken_networkx"
    ) == 2

    def solver(received, source, target, **kwargs):
        assert received is graph
        received["a"]["t"]["budget"] = 4
        raise LookupError("solver stopped after updating capacity")

    with pytest.raises(LookupError, match="solver stopped after updating capacity"):
        getattr(nx, name)(
            graph, "s", "t", capacity="budget", flow_func=solver,
            backend="franken_networkx",
        )
    assert nx.maximum_flow_value(
        graph, "s", "t", capacity="budget", backend="franken_networkx"
    ) == 4


class _ResidualOnlyInput(nx.DiGraph):
    """An input whose topology is unnecessary once its residual is supplied."""

    forbid_topology = False

    def __getattribute__(self, name):
        if name in ("edges", "adj", "_adj", "succ", "pred", "nodes"):
            if object.__getattribute__(self, "forbid_topology"):
                raise AssertionError("input topology read despite supplied residual")
        return super().__getattribute__(name)


@pytest.mark.parametrize("algorithm", ALGORITHMS)
@pytest.mark.parametrize("residual_module", [nx, fnx], ids=["networkx", "franken_networkx"])
def test_supplied_residual_avoids_reading_input_topology(algorithm, residual_module):
    outcomes = []
    for flow_module in (nx_flow, fnx.flow):
        graph = _ResidualOnlyInput()
        graph.add_weighted_edges_from(
            [("s", "a", 4), ("a", "t", 3), ("s", "t", 2)], weight="capacity"
        )
        residual = residual_module.flow.build_residual_network(graph, "capacity")
        held_attributes = {(u, v): data for u, v, data in residual.edges(data=True)}
        graph.forbid_topology = True
        options = {"backend": "networkx"} if flow_module is nx_flow else {}

        result = getattr(flow_module, algorithm)(
            graph, "s", "t", residual=residual, **options
        )

        assert result is residual
        assert result.graph["flow_value"] == 5
        assert all(result[u][v] is attrs for (u, v), attrs in held_attributes.items())
        outcomes.append([
            (u, v, dict(attrs)) for u, v, attrs in result.edges(data=True)
        ])
    assert outcomes[0] == outcomes[1]


@pytest.mark.parametrize("algorithm", ALGORITHMS)
@pytest.mark.parametrize("endpoints", [("missing", "t"), ("s", "missing"), ("s", "s")])
def test_flow_endpoint_validation_precedes_input_topology(algorithm, endpoints):
    outcomes = []
    for flow_module in (nx_flow, fnx.flow):
        graph = _ResidualOnlyInput()
        graph.add_edge("s", "t", capacity=3)
        graph.forbid_topology = True
        options = {"backend": "networkx"} if flow_module is nx_flow else {}
        with pytest.raises(Exception) as error:
            getattr(flow_module, algorithm)(graph, *endpoints, **options)
        outcomes.append((type(error.value).__name__, str(error.value)))
    assert outcomes[0] == outcomes[1]
    assert outcomes[0][0] == "NetworkXError"


@pytest.mark.parametrize("directed", [False, True])
def test_residual_builder_reads_public_graph_without_node_attribute_export(directed):
    graph_type = nx.DiGraph if directed else nx.Graph

    class PublicGraph(graph_type):
        @property
        def nodes(self):
            raise AssertionError("residual construction exported input node attributes")

    graph = PublicGraph()
    graph.add_edge("s", "a", capacity=Fraction(7, 2))
    graph.add_edge("a", "t", capacity=Fraction(5, 2))
    graph.add_edge("s", "t", capacity=0)
    graph.add_edge("t", "t", capacity=100)
    graph.add_node("isolated", payload=object())
    expected = nx_flow.build_residual_network(graph, "capacity", backend="networkx")
    actual = fnx.flow.build_residual_network(graph, "capacity")

    assert list(actual) == list(expected)
    assert list(actual.nodes(data=True)) == list(expected.nodes(data=True))
    assert list(actual.edges(data=True)) == list(expected.edges(data=True))
    assert actual.graph == expected.graph
    assert isinstance(actual, fnx.DiGraph)


@pytest.mark.parametrize("algorithm", ALGORITHMS)
def test_flow_solver_keeps_live_public_edge_capacity_provider(algorithm):
    outcomes = []
    for flow_module in (nx_flow, fnx.flow):
        reads = []

        class Capacity(dict):
            def get(self, key, default=None):
                reads.append(("get", key))
                return super().get(key, default)

            def __getitem__(self, key):
                reads.append(("getitem", key))
                return super().__getitem__(key)

        class PublicGraph(nx.DiGraph):
            edge_attr_dict_factory = Capacity

            @property
            def nodes(self):
                raise AssertionError("solver exported input node attributes")

        graph = PublicGraph()
        graph.add_edge("s", "a", capacity=4)
        graph.add_edge("a", "t", capacity=3)
        graph.add_edge("s", "t", capacity=2)
        options = {"backend": "networkx"} if flow_module is nx_flow else {}
        result = getattr(flow_module, algorithm)(graph, "s", "t", **options)
        outcomes.append((result.graph["flow_value"], reads))
    assert outcomes[0] == outcomes[1]
    assert outcomes[0][0] == 5


@pytest.mark.parametrize("name", _HIGH_LEVEL_FLOW_APIS)
@pytest.mark.parametrize("graph_class", ["Graph", "DiGraph"])
@pytest.mark.parametrize("kind", ["networkx", "subclass", "assigned"])
def test_default_flow_keeps_live_capacity_provider(name, graph_class, kind):
    outcomes = []
    for module in (nx, fnx):
        reads = []

        class Capacity(dict):
            def get(self, key, default=None):
                reads.append(("get", key))
                if key == "capacity":
                    dict.__setitem__(self, key, 7)
                return super().get(key, default)

            def __getitem__(self, key):
                reads.append(("getitem", key))
                return super().__getitem__(key)

        graph_module = nx if kind == "networkx" else module
        base = getattr(graph_module, graph_class)
        if kind == "subclass":
            class InputGraph(base):
                def edges(self, nbunch=None, data=False, default=None):
                    if data:
                        return [("s", "t", self.capacity_provider)]
                    return [("s", "t")]

            graph = InputGraph()
            graph.add_edge("s", "t", capacity=1)
            graph.capacity_provider = Capacity(capacity=1)
        else:
            graph = base()
            attrs = Capacity(capacity=1)
            graph._node = {"s": {}, "t": {}}
            if graph_class == "DiGraph":
                graph._succ = {"s": {"t": attrs}, "t": {}}
                graph._pred = {"s": {}, "t": {"s": attrs}}
            else:
                graph._adj = {"s": {"t": attrs}, "t": {"s": attrs}}
        reads.clear()
        result = getattr(module, name)(graph, "s", "t")
        value = result[0] if isinstance(result, tuple) else result
        assert value == 7
        outcomes.append((result, reads))
    assert outcomes[0] == outcomes[1]


@pytest.mark.parametrize("name", _HIGH_LEVEL_FLOW_APIS)
@pytest.mark.parametrize("graph_class", ["Graph", "DiGraph"])
@pytest.mark.parametrize("prewarm", [False, True])
def test_default_flow_keeps_assigned_public_edge_provider(name, graph_class, prewarm):
    outcomes = []
    for module in (nx, fnx):
        graph = getattr(module, graph_class)()
        graph.add_edge("s", "t", capacity=1)
        if prewarm:
            assert getattr(module, "maximum_flow_value")(graph, "s", "t") == 1
            # Retain the descriptor's cached marker to exercise the identity
            # check as well as ordinary attribute assignment detection.
            graph.edges
        reads = []
        attrs = {"capacity": 7}

        def edges(nbunch=None, data=False, default=None):
            reads.append((nbunch, data, default))
            if data:
                return [("s", "t", attrs)]
            return [("s", "t")]

        vars(graph)["edges"] = edges
        result = getattr(module, name)(graph, "s", "t")
        value = result[0] if isinstance(result, tuple) else result
        assert value == 7
        outcomes.append((result, reads))
    assert outcomes[0] == outcomes[1]


@pytest.mark.parametrize("name", _HIGH_LEVEL_FLOW_APIS)
@pytest.mark.parametrize("kind", ["subgraph", "reverse", "shared_copy"])
def test_default_flow_view_observes_builtin_dict_mutations(name, kind):
    outcomes = []
    for module in (nx, fnx):
        graph = _custom_flow_input(module, kind)
        attrs = graph["a"]["t"]
        results = []
        for capacity in (2, 4, 1):
            # Bypass write-watched dict methods after the first query has
            # warmed any materialized view and native conversion caches.
            dict.__setitem__(attrs, "budget", capacity)
            result = getattr(module, name)(graph, "s", "t", capacity="budget")
            value = result[0] if isinstance(result, tuple) else result
            assert value == capacity
            results.append(result)
        outcomes.append(results)
    assert outcomes[0] == outcomes[1]


@pytest.mark.parametrize("name", _HIGH_LEVEL_FLOW_APIS)
@pytest.mark.parametrize("prewarm", [False, True])
@pytest.mark.parametrize("keyword_arguments", [False, True])
def test_backend_default_flow_keeps_live_capacity_provider(
    name, prewarm, keyword_arguments
):
    outcomes = []
    for backend in ("networkx", "franken_networkx"):
        graph = nx.DiGraph()
        graph.add_edge("s", "t", capacity=1)
        if prewarm:
            assert nx.maximum_flow_value(graph, "s", "t", backend=backend) == 1
        reads = []

        class Capacity(dict):
            def get(self, key, default=None):
                reads.append(("get", key))
                if key == "capacity":
                    dict.__setitem__(self, key, 7)
                return super().get(key, default)

        attrs = Capacity(capacity=1)
        # Replacing an inner row deliberately leaves an existing backend
        # conversion cache warm. The new provider still owns this query.
        graph._succ["s"]["t"] = graph._pred["t"]["s"] = attrs
        if keyword_arguments:
            result = getattr(nx, name)(
                flowG=graph, _s="s", _t="t", backend=backend
            )
        else:
            result = getattr(nx, name)(graph, "s", "t", backend=backend)
        value = result[0] if isinstance(result, tuple) else result
        assert value == 7
        assert dict.__getitem__(attrs, "capacity") == 7
        outcomes.append((result, reads))
    assert outcomes[0] == outcomes[1]


@pytest.mark.parametrize("name", _HIGH_LEVEL_FLOW_APIS)
@pytest.mark.parametrize("graph_module", [nx, fnx], ids=["networkx", "native"])
@pytest.mark.parametrize("graph_class", ["Graph", "DiGraph"])
def test_default_flow_plain_graph_retains_native_route(
    monkeypatch, name, graph_module, graph_class
):
    graph = getattr(graph_module, graph_class)()
    graph.add_edge("s", "t", capacity=3)
    # Normal descriptor caches are admissible; inspecting a graph before a
    # flow query must not disable native execution.
    graph.edges
    graph.nodes
    graph.adj
    if graph_class == "DiGraph":
        graph.succ
        graph.pred

    def forbid_python_residual(*args, **kwargs):
        raise AssertionError("ordinary concrete flow should retain its native route")

    monkeypatch.setattr(fnx, "_flow_residual_inproc", forbid_python_residual)
    result = getattr(fnx, name)(graph, "s", "t")
    value = result[0] if isinstance(result, tuple) else result
    assert value == 3
