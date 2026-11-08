"""Capacity scaling is an owned algorithm with its own heap/flow contract."""

from copy import deepcopy
from importlib import import_module
import random

import networkx as nx
import pytest

import franken_networkx as fnx


def _graph(module, graph_type, seed):
    rng = random.Random(seed)
    graph = getattr(module, graph_type)()
    graph.add_nodes_from(range(5))
    graph.nodes[0]["demand"] = -3
    graph.nodes[4]["demand"] = 3
    for source in graph:
        for target in graph:
            if source != target and rng.random() < 0.5:
                graph.add_edge(
                    source, target, capacity=rng.randrange(1, 5),
                    weight=rng.randrange(-1, 4),
                )
    if graph.is_multigraph():
        graph.add_edge(0, 4, key=("extra", seed), capacity=2, weight=3)
    return graph


def _outcome(function, graph, **kwargs):
    try:
        cost, flow = function(graph, **kwargs)
        return type(cost), cost, flow
    except nx.NetworkXException as exc:
        return type(exc), str(exc)


@pytest.mark.parametrize("graph_type", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("input_kind", ["native", "networkx", "view"])
@pytest.mark.parametrize("seed", range(20))
def test_capacity_scaling_matches_exact_flow_assignment(graph_type, input_kind, seed):
    original = _graph(nx, graph_type, seed)
    graph = _graph(nx if input_kind == "networkx" else fnx, graph_type, seed)
    if input_kind == "view":
        graph = graph.subgraph(list(graph))
    before = deepcopy(dict(graph.nodes(data=True)))
    edges_before = list(graph.edges(data=True, keys=True)) if graph.is_multigraph() else list(graph.edges(data=True))
    assert _outcome(fnx.capacity_scaling, graph) == _outcome(nx.capacity_scaling, original)
    assert dict(graph.nodes(data=True)) == before
    assert (list(graph.edges(data=True, keys=True)) if graph.is_multigraph() else list(graph.edges(data=True))) == edges_before


@pytest.mark.parametrize("spelling", ["capacity_scaling", "flow.capacity_scaling", "algorithms.capacity_scaling"])
def test_capacity_scaling_uses_requested_heap_and_original_labels(spelling):
    def run(module):
        events = []

        class ObservedHeap(nx.utils.BinaryHeap):
            def __init__(self):
                events.append(("new",))
                super().__init__()

            def insert(self, key, value, allow_increase=False):
                events.append(("insert", key, value))
                return super().insert(key, value, allow_increase)

            def pop(self):
                item = super().pop()
                events.append(("pop", *item))
                return item

        graph = module.MultiDiGraph()
        graph.add_node(("source", 0), demand=-5)
        graph.add_node("sink", demand=5)
        graph.add_edge(("source", 0), "middle", key="cheap", capacity=3, weight=1)
        graph.add_edge(("source", 0), "middle", key="other", capacity=4, weight=4)
        graph.add_edge("middle", "sink", key=("out", 0), capacity=5, weight=2)
        function = module
        for part in spelling.split("."):
            function = getattr(function, part)
        return function(graph, heap=ObservedHeap), events

    expected, events = run(nx)
    assert events and any(row[0] == "insert" and row[1] == ("source", 0) for row in events)
    assert run(fnx) == (expected, events)


def test_capacity_scaling_propagates_heap_errors():
    class BrokenHeap:
        def __init__(self):
            raise LookupError("requested capacity-scaling heap")

    graph = fnx.DiGraph()
    graph.add_node("s", demand=-1)
    graph.add_node("t", demand=1)
    graph.add_edge("s", "t", capacity=1)
    with pytest.raises(LookupError, match="requested capacity-scaling heap"):
        fnx.capacity_scaling(graph, heap=BrokenHeap)


@pytest.mark.parametrize("graph_type", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("case", ["empty", "imbalance", "infeasible", "infinite-cycle", "infinite-loop", "nonpositive", "finite-loop"])
def test_capacity_scaling_validation_and_residual_contract(graph_type, case):
    def build(module):
        graph = getattr(module, graph_type)()
        if case == "imbalance":
            graph.add_node("s", demand=-1)
        elif case == "infeasible":
            graph.add_node("s", demand=-3)
            graph.add_node("t", demand=3)
            graph.add_edge("s", "t", capacity=2)
        elif case == "infinite-cycle":
            graph.add_edge("s", "t", weight=-2)
            graph.add_edge("t", "s", weight=1)
        elif case == "infinite-loop":
            graph.add_edge("s", "s", weight=-1)
        elif case == "nonpositive":
            graph.add_edge("s", "t", capacity=-2, weight=-4)
            graph.add_edge("t", "t", capacity=0, weight=-5)
        elif case == "finite-loop":
            graph.add_edge("s", "s", capacity=3, weight=-2)
            graph.add_edge("s", "t", capacity=0, weight=1.5)
        return graph

    assert _outcome(fnx.capacity_scaling, build(fnx)) == _outcome(nx.capacity_scaling, build(nx))


@pytest.mark.parametrize("graph_type", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("amount", [5, 2**62 + 3, 10**400])
def test_capacity_scaling_keeps_exact_arithmetic_and_attribute_names(graph_type, amount):
    def build(module):
        graph = getattr(module, graph_type)()
        graph.add_node("s", balance=-amount)
        graph.add_node("t", balance=amount)
        graph.add_edge("s", "a", units=amount, cost=2)
        graph.add_edge("a", "t", cost=3)
        return graph

    kwargs = {"demand": "balance", "capacity": "units", "weight": "cost"}
    assert _outcome(fnx.capacity_scaling, build(fnx), **kwargs) == _outcome(nx.capacity_scaling, build(nx), **kwargs)


def test_capacity_scaling_is_independent_of_simplex_and_upstream(monkeypatch):
    graph = _graph(fnx, "MultiDiGraph", 0)
    expected = nx.capacity_scaling(_graph(nx, "MultiDiGraph", 0))

    def forbidden(*args, **kwargs):
        raise AssertionError("capacity scaling substituted a different solver")

    monkeypatch.setattr(fnx, "min_cost_flow", forbidden)
    monkeypatch.setitem(fnx.capacity_scaling.__globals__, "min_cost_flow", forbidden)
    monkeypatch.setattr(nx, "capacity_scaling", forbidden)
    monkeypatch.setattr(nx, "network_simplex", forbidden)
    monkeypatch.setattr(import_module("networkx.algorithms.flow.capacityscaling"), "capacity_scaling", forbidden)
    assert fnx.capacity_scaling(graph) == expected


@pytest.mark.parametrize("graph_type", ["DiGraph", "MultiDiGraph"])
def test_capacity_scaling_pairing_heap(graph_type):
    assert _outcome(fnx.capacity_scaling, _graph(fnx, graph_type, 0), heap=fnx.utils.PairingHeap) == _outcome(
        nx.capacity_scaling, _graph(nx, graph_type, 0), heap=nx.utils.PairingHeap
    )


@pytest.mark.parametrize("weight,cycle_size", [(-float("inf"), 2), (-1e308, 8), (-1, 8)])
def test_capacity_scaling_infinite_cycle_detection_survives_distance_overflow(weight, cycle_size):
    def build(module):
        graph = module.DiGraph()
        graph.add_nodes_from(range(8))
        for node in range(cycle_size):
            graph.add_edge(node, (node + 1) % cycle_size, weight=weight if node == 0 else 0)
        return graph

    expected = _outcome(nx.capacity_scaling, build(nx))
    assert expected[0] is nx.NetworkXUnbounded
    assert _outcome(fnx.capacity_scaling, build(fnx)) == expected


def test_capacity_scaling_does_not_relax_acyclic_infinite_arcs(monkeypatch):
    solver = import_module("franken_networkx._capacity_scaling")
    graph = fnx.DiGraph()
    graph.add_nodes_from(reversed(range(1024)))
    graph.add_edges_from((node, node + 1, {"weight": -1}) for node in range(1023))
    oracle = nx.DiGraph()
    oracle.add_nodes_from(graph)
    oracle.add_edges_from(graph.edges(data=True))
    expected = nx.capacity_scaling(oracle)

    def unexpected_cycle_proof(*args, **kwargs):
        raise AssertionError("acyclic infinite-capacity network entered cycle relaxation")

    monkeypatch.setattr(solver, "_negative_cycle", unexpected_cycle_proof)
    assert fnx.capacity_scaling(graph) == expected


def test_capacity_scaling_detects_negative_cycle_before_a_whole_component_overflows():
    def build(module):
        graph = module.DiGraph()
        for node in range(1, 8):
            graph.add_edge(0, node, weight=-1e308 if node == 1 else 0)
            graph.add_edge(node, 0, weight=0)
        return graph

    expected = _outcome(nx.capacity_scaling, build(nx))
    assert expected[0] is nx.NetworkXUnbounded
    assert _outcome(fnx.capacity_scaling, build(fnx)) == expected
