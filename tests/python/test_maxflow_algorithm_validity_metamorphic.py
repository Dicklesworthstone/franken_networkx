"""Oracle-free max-flow validity across EVERY flow algorithm (br-r37-c1-324jn).

``test_maxflow_validity_metamorphic.py`` already checks capacity, conservation,
value-equals-source-outflow, the min-cut theorem and the complete-digraph closed
form — but only for the DEFAULT ``flow_func``. ``maximum_flow`` takes five
interchangeable implementations, so four of them were validated by nothing here,
and a flow algorithm is exactly the kind of code where one variant can be wrong
while its siblings are right.

This file adds what that leaves out, all of it oracle-free — every assertion is
a property of a correct flow, not a comparison against networkx:

* every algorithm, on the same graphs;
* the cut PARTITION's real capacity, summed edge by edge, equals the value it
  reported. The existing check only asserts that s and t land on opposite
  sides, which a partition can satisfy while misplacing every interior node;
* value equals net SINK inflow as well as net source outflow — a flow that
  leaked in the middle can satisfy one and fail the other;
* float capacities, where an integer-only accumulator would show up;
* the value-only entry points agreeing with the full ones.

The algorithms must also agree with EACH OTHER: max flow is unique in value
even though the flow assignment is not, so any two disagreeing is a bug in one
of them without needing to know which.
"""

from __future__ import annotations

import random

import pytest

import franken_networkx as fnx

ALGORITHMS = [
    "edmonds_karp",
    "shortest_augmenting_path",
    "preflow_push",
    "dinitz",
    "boykov_kolmogorov",
]
TOL = 1e-9


def _flow_func(name):
    return getattr(fnx.algorithms.flow, name)


def _random_capacitated_digraph(seed, *, float_caps=False):
    rng = random.Random(seed)
    n = rng.randint(4, 9)
    graph = fnx.DiGraph()
    graph.add_nodes_from(range(n))
    for u in range(n):
        for v in range(n):
            if u != v and rng.random() < 0.4:
                cap = rng.uniform(0.5, 9.0) if float_caps else rng.randint(1, 9)
                graph.add_edge(u, v, capacity=cap)
    return graph, n


def _violations(graph, flow, value, source, sink):
    """Every way a flow dict can fail to be a flow. Empty list == valid."""
    bad = []
    for u, nbrs in flow.items():
        for v, f in nbrs.items():
            cap = graph[u][v].get("capacity", float("inf"))
            if f < -TOL:
                bad.append(f"negative flow {u}->{v} = {f}")
            if f > cap + TOL:
                bad.append(f"flow {u}->{v} = {f} exceeds capacity {cap}")
    for node in graph:
        if node in (source, sink):
            continue
        out = sum(flow.get(node, {}).values())
        inn = sum(flow.get(u, {}).get(node, 0) for u in graph)
        if abs(out - inn) > TOL:
            bad.append(f"conservation violated at {node}: in {inn} out {out}")
    src_out = sum(flow.get(source, {}).values()) - sum(
        flow.get(u, {}).get(source, 0) for u in graph
    )
    snk_in = sum(flow.get(u, {}).get(sink, 0) for u in graph) - sum(
        flow.get(sink, {}).values()
    )
    if abs(value - src_out) > TOL:
        bad.append(f"value {value} != net source outflow {src_out}")
    if abs(value - snk_in) > TOL:
        bad.append(f"value {value} != net sink inflow {snk_in}")
    return bad


def _cut_violations(graph, value, cut_value, partition, source, sink):
    reachable, non_reachable = partition
    bad = []
    if abs(cut_value - value) > TOL:
        bad.append(f"min-cut {cut_value} != max-flow {value}")
    if source not in reachable:
        bad.append("source is not on the reachable side")
    if sink not in non_reachable:
        bad.append("sink is not on the non-reachable side")
    if set(reachable) | set(non_reachable) != set(graph):
        bad.append("partition does not cover every node")
    if set(reachable) & set(non_reachable):
        bad.append("partition sides overlap")
    # The capacity actually crossing the cut, summed edge by edge.
    crossing = sum(
        graph[u][v].get("capacity", float("inf"))
        for u in reachable
        if u in graph
        for v in graph[u]
        if v in non_reachable
    )
    if abs(crossing - cut_value) > TOL:
        bad.append(f"edges crossing the cut sum to {crossing}, reported {cut_value}")
    return bad


@pytest.mark.parametrize("algorithm", ALGORITHMS)
@pytest.mark.parametrize("seed", range(12))
@pytest.mark.parametrize("float_caps", [False, True], ids=["int", "float"])
def test_every_algorithm_produces_a_valid_flow(algorithm, seed, float_caps):
    graph, n = _random_capacitated_digraph(seed, float_caps=float_caps)
    source, sink = 0, n - 1
    if not fnx.has_path(graph, source, sink):
        pytest.skip("no s-t path")
    flow_func = _flow_func(algorithm)
    value, flow = fnx.maximum_flow(graph, source, sink, flow_func=flow_func)
    assert _violations(graph, flow, value, source, sink) == []


@pytest.mark.parametrize("algorithm", ALGORITHMS)
@pytest.mark.parametrize("seed", range(12))
def test_every_algorithm_cut_partition_really_costs_what_it_says(algorithm, seed):
    """The check the existing coverage stops short of.

    Asserting only that s and t land on opposite sides passes for a partition
    that misplaces every node in between; summing the crossing edges does not.
    """
    graph, n = _random_capacitated_digraph(seed)
    source, sink = 0, n - 1
    if not fnx.has_path(graph, source, sink):
        pytest.skip("no s-t path")
    flow_func = _flow_func(algorithm)
    value, _flow = fnx.maximum_flow(graph, source, sink, flow_func=flow_func)
    cut_value, partition = fnx.minimum_cut(graph, source, sink, flow_func=flow_func)
    assert _cut_violations(graph, value, cut_value, partition, source, sink) == []


@pytest.mark.parametrize("seed", range(20))
def test_all_algorithms_agree_on_the_value(seed):
    """Max-flow VALUE is unique even though the assignment is not.

    Needs no reference implementation: if two of the five disagree, one of them
    is wrong.
    """
    graph, n = _random_capacitated_digraph(seed)
    source, sink = 0, n - 1
    if not fnx.has_path(graph, source, sink):
        pytest.skip("no s-t path")
    values = {
        algorithm: fnx.maximum_flow_value(
            graph, source, sink, flow_func=_flow_func(algorithm)
        )
        for algorithm in ALGORITHMS
    }
    assert len(set(round(v, 9) for v in values.values())) == 1, values


@pytest.mark.parametrize("algorithm", ALGORITHMS)
@pytest.mark.parametrize("seed", range(8))
def test_value_only_entry_points_agree_with_the_full_ones(algorithm, seed):
    graph, n = _random_capacitated_digraph(seed)
    source, sink = 0, n - 1
    if not fnx.has_path(graph, source, sink):
        pytest.skip("no s-t path")
    flow_func = _flow_func(algorithm)
    value, _flow = fnx.maximum_flow(graph, source, sink, flow_func=flow_func)
    assert fnx.maximum_flow_value(graph, source, sink, flow_func=flow_func) == value
    cut_value, _partition = fnx.minimum_cut(graph, source, sink, flow_func=flow_func)
    assert fnx.minimum_cut_value(graph, source, sink, flow_func=flow_func) == cut_value


@pytest.mark.parametrize("algorithm", ALGORITHMS)
def test_no_path_means_zero_flow_and_a_trivial_cut(algorithm):
    """A disconnected s,t is a valid instance, not an error."""
    graph = fnx.DiGraph()
    graph.add_edge("s", "x", capacity=5)
    graph.add_edge("y", "t", capacity=5)
    flow_func = _flow_func(algorithm)
    value, flow = fnx.maximum_flow(graph, "s", "t", flow_func=flow_func)
    assert value == 0
    assert _violations(graph, flow, value, "s", "t") == []
    cut_value, partition = fnx.minimum_cut(graph, "s", "t", flow_func=flow_func)
    assert cut_value == 0
    assert _cut_violations(graph, value, cut_value, partition, "s", "t") == []


@pytest.mark.parametrize("algorithm", ALGORITHMS)
@pytest.mark.parametrize("n", [4, 5, 6])
def test_complete_digraph_closed_form_for_every_algorithm(algorithm, n):
    """Unit-capacity complete digraph: max flow s->t is exactly n-1.

    The direct edge, plus one length-2 detour through each of the other n-2
    nodes. Ground truth, no reference implementation involved.
    """
    graph = fnx.DiGraph()
    graph.add_nodes_from(range(n))
    for u in range(n):
        for v in range(n):
            if u != v:
                graph.add_edge(u, v, capacity=1)
    value, flow = fnx.maximum_flow(
        graph, 0, n - 1, flow_func=_flow_func(algorithm)
    )
    assert value == n - 1
    assert _violations(graph, flow, value, 0, n - 1) == []


@pytest.mark.parametrize("algorithm", ALGORITHMS)
def test_scaling_every_capacity_scales_the_value(algorithm):
    """Metamorphic: multiply every capacity by k and the value multiplies by k."""
    base, n = _random_capacitated_digraph(3)
    source, sink = 0, n - 1
    if not fnx.has_path(base, source, sink):
        pytest.skip("no s-t path")
    flow_func = _flow_func(algorithm)
    value = fnx.maximum_flow_value(base, source, sink, flow_func=flow_func)
    for k in (2, 5):
        scaled = fnx.DiGraph()
        scaled.add_nodes_from(base)
        for u, v, data in base.edges(data=True):
            scaled.add_edge(u, v, capacity=data["capacity"] * k)
        scaled_value = fnx.maximum_flow_value(
            scaled, source, sink, flow_func=flow_func
        )
        assert abs(scaled_value - value * k) < TOL, (algorithm, k)
