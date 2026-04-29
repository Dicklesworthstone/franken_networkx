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

import pytest
import networkx as nx
from networkx.algorithms import flow as nx_flow

import franken_networkx as fnx


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
    fnx_fn = getattr(fnx, algorithm)
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
    fnx_fn = getattr(fnx, algorithm)
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
        fnx_fn = getattr(fnx, algorithm)
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
    fnx_fn = getattr(fnx, algorithm)
    residual = fnx_fn(fg, source, target)
    flow_value = residual.graph["flow_value"]
    expected = fnx.maximum_flow_value(fg, source, target, flow_func=fnx_fn)
    assert flow_value == expected, (
        f"{name} {algorithm}: residual.flow_value={flow_value}, "
        f"maximum_flow_value={expected}"
    )


@pytest.mark.parametrize("capacity", [None, "bad"])
def test_edmonds_karp_malformed_capacity_raises_like_networkx(capacity):
    fg, ng = _pair_directed([("s", "t", capacity)])
    with pytest.raises(Exception) as nx_exc:
        nx_flow.edmonds_karp(ng, "s", "t")
    with pytest.raises(type(nx_exc.value)) as fnx_exc:
        fnx.edmonds_karp(fg, "s", "t")
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
    fnx_fn = getattr(fnx, algorithm)
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
    fnx_fn = getattr(fnx, algorithm)
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
    fnx_fn = getattr(fnx, algorithm)
    nx_fn = getattr(nx_flow, algorithm)
    with pytest.raises(nx.NetworkXUnbounded):
        nx.maximum_flow_value(ng, "s", "t", flow_func=nx_fn)
    with pytest.raises(fnx.NetworkXUnbounded):
        fnx.maximum_flow_value(fg, "s", "t", flow_func=fnx_fn)


@pytest.mark.parametrize("algorithm", ALGORITHMS)
def test_source_equals_target_raises_or_zero(algorithm):
    """``s == t`` is degenerate — both libraries must mirror exactly
    (NX raises NetworkXError)."""
    fg = fnx.DiGraph()
    ng = nx.DiGraph()
    fg.add_edge(0, 1, capacity=5)
    ng.add_edge(0, 1, capacity=5)
    fnx_fn = getattr(fnx, algorithm)
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
    fnx_fn = getattr(fnx, algorithm)
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
    fnx_fn = getattr(fnx, algorithm)
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
