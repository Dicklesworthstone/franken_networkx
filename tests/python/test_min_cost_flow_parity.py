"""Differential + golden parity for the min-cost-flow family.

Covers ``min_cost_flow_cost`` (and ``min_cost_flow``), ``network_simplex``
and ``max_flow_min_cost``. None had a dedicated test file. Graphs are
built from a single shared spec so fnx and nx see identical networks.

br-r37-c1-b9nfx
"""

from __future__ import annotations

import random
from decimal import Decimal
from fractions import Fraction
from importlib import import_module

import pytest
import networkx as nx
import franken_networkx as fnx


def _demand_spec(seed):
    rng = random.Random(seed)
    n = rng.randint(4, 7)
    demand = [0] * n
    amount = rng.randint(1, 5)
    demand[0] = -amount
    demand[n - 1] = amount
    edges = [
        (u, v, rng.randint(1, 9), rng.randint(3, 10))
        for u in range(n)
        for v in range(n)
        if u != v and rng.random() < 0.5
    ]
    return n, demand, edges


def _build_demand(spec, lib):
    n, demand, edges = spec
    g = lib.DiGraph()
    for i in range(n):
        g.add_node(i, demand=demand[i])
    for u, v, w, c in edges:
        g.add_edge(u, v, weight=w, capacity=c)
    return g


def _flow_spec(seed):
    rng = random.Random(seed)
    n = rng.randint(4, 7)
    edges = [
        (u, v, rng.randint(1, 5), rng.randint(1, 8))
        for u in range(n)
        for v in range(n)
        if u != v and rng.random() < 0.5
    ]
    return n, edges


def _build_flow(spec, lib):
    n, edges = spec
    g = lib.DiGraph()
    g.add_nodes_from(range(n))
    for u, v, w, c in edges:
        g.add_edge(u, v, weight=w, capacity=c)
    return g


@pytest.mark.parametrize("seed", range(60))
def test_min_cost_flow_cost_matches_networkx(seed):
    spec = _demand_spec(seed)
    fg = _build_demand(spec, fnx)
    ng = _build_demand(spec, nx)
    try:
        nc = nx.min_cost_flow_cost(ng)
    except nx.NetworkXUnfeasible:
        with pytest.raises(nx.NetworkXUnfeasible):
            fnx.min_cost_flow_cost(fg)
        return
    assert fnx.min_cost_flow_cost(fg) == nc
    # network_simplex returns the same optimal cost.
    assert fnx.network_simplex(fg)[0] == nx.network_simplex(ng)[0]


@pytest.mark.parametrize("seed", range(60))
def test_max_flow_min_cost_matches_networkx(seed):
    spec = _flow_spec(seed)
    fg = _build_flow(spec, fnx)
    ng = _build_flow(spec, nx)
    n = spec[0]
    ff = fnx.max_flow_min_cost(fg, 0, n - 1)
    nf = nx.max_flow_min_cost(ng, 0, n - 1)
    # Flow dicts may differ; the optimal cost is the invariant.
    assert fnx.cost_of_flow(fg, ff) == nx.cost_of_flow(ng, nf)


def test_min_cost_flow_golden():
    spec_edges = [(0, 1, 2, 10), (1, 2, 3, 10)]
    fg = fnx.DiGraph()
    ng = nx.DiGraph()
    for g in (fg, ng):
        g.add_node(0, demand=-5)
        g.add_node(1, demand=0)
        g.add_node(2, demand=5)
        for u, v, w, c in spec_edges:
            g.add_edge(u, v, weight=w, capacity=c)
    # 5 units over edges costing 2 then 3 -> 5*(2+3) = 25.
    assert fnx.min_cost_flow_cost(fg) == 25
    assert fnx.min_cost_flow(fg) == nx.min_cost_flow(ng)


def test_infeasible_raises_like_networkx():
    fg = fnx.DiGraph()
    ng = nx.DiGraph()
    for g in (fg, ng):
        g.add_node(0, demand=-10)
        g.add_node(1, demand=10)
        g.add_edge(0, 1, weight=1, capacity=3)  # capacity < demand
    with pytest.raises(nx.NetworkXUnfeasible):
        fnx.min_cost_flow_cost(fg)
    with pytest.raises(nx.NetworkXUnfeasible):
        nx.min_cost_flow_cost(ng)


def _build_undirected_flow(spec, lib, cls="Graph"):
    n, edges = spec
    g = getattr(lib, cls)()
    g.add_nodes_from(range(n))
    for u, v, w, c in edges:
        g.add_edge(u, v, weight=w, capacity=c)
    return g


def _ordered(flow):
    return [(u, list(row.items())) for u, row in flow.items()]


@pytest.mark.parametrize("seed", range(30))
def test_max_flow_min_cost_undirected_matches_networkx(seed):
    # br-r37-c1-b4n6b: networkx runs min_cost_flow on DiGraph(G), so an undirected
    # G works (two arcs per edge); fnx copied G and min_cost_flow refused it.
    spec = _flow_spec(seed)
    n = spec[0]
    ff = fnx.max_flow_min_cost(_build_undirected_flow(spec, fnx), 0, n - 1)
    nf = nx.max_flow_min_cost(_build_undirected_flow(spec, nx), 0, n - 1)
    assert _ordered(ff) == _ordered(nf)


# br-r37-c1-33ctq: networkx's capacity_scaling adds flow * weight to the int 0
# only where flow moves (plus negative selfloops' saturation), so an edge that
# carries no flow never makes the cost a float; fnx scored every edge with
# cost_of_flow, and 0 * 2.5 is 0.0. 2 == 2.0, so compare (value, type).
_SCALING_CASES = {
    "no_demand_float_weights": ([(0, 0), (1, 0)], [(0, 1, 1.5, 4)]),
    "flow_on_int_edge_only": (
        [("s", -2), ("a", 0), ("t", 2)],
        [("s", "t", 1, 5), ("s", "a", 2.5, 5), ("a", "t", 2.5, 5)],
    ),
    "flow_on_float_edge": ([("s", -2), ("t", 2)], [("s", "t", 1.5, 5)]),
    "int_weights": ([("s", -3), ("a", 0), ("t", 3)], [("s", "a", 2, 2), ("a", "t", 1, 5), ("s", "t", 4, 5)]),
    "negative_selfloop": (
        [("s", -1), ("a", 0), ("t", 1)],
        [("s", "a", 1, 5), ("a", "t", 1, 5), ("a", "a", -1.5, 2)],
    ),
}


def _scaling_graph(lib, cls, case):
    nodes, edges = _SCALING_CASES[case]
    g = getattr(lib, cls)()
    for node, demand in nodes:
        g.add_node(node, demand=demand)
    for u, v, w, c in edges:
        g.add_edge(u, v, weight=w, capacity=c)
    return g


@pytest.mark.parametrize("spelling", ["capacity_scaling", "flow.capacity_scaling", "algorithms.capacity_scaling"])
@pytest.mark.parametrize("cls", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("case", sorted(_SCALING_CASES))
def test_capacity_scaling_cost_type_matches_networkx(spelling, cls, case):
    fn = fnx
    for part in spelling.split("."):
        fn = getattr(fn, part)
    n_cost, n_flow = nx.capacity_scaling(_scaling_graph(nx, cls, case))
    f_cost, f_flow = fn(_scaling_graph(fnx, cls, case))
    assert (f_cost, type(f_cost).__name__) == (n_cost, type(n_cost).__name__)
    assert f_flow == n_flow


@pytest.mark.parametrize("cls", ["MultiGraph", "MultiDiGraph"])
def test_max_flow_min_cost_multigraph_still_raises_like_networkx(cls):
    spec = _flow_spec(3)
    n = spec[0]
    with pytest.raises(nx.NetworkXError) as nx_exc:
        nx.max_flow_min_cost(_build_undirected_flow(spec, nx, cls), 0, n - 1)
    with pytest.raises(nx.NetworkXError) as fnx_exc:
        fnx.max_flow_min_cost(_build_undirected_flow(spec, fnx, cls), 0, n - 1)
    assert str(fnx_exc.value) == str(nx_exc.value)


# br-r37-c1-6soms: nx's network_simplex cost is sum(w * x) over the NON-selfloop
# edges from the int 0, plus w * c per negative selfloop; a non-negative
# selfloop adds nothing. fnx scored every edge (cost_of_flow), so selfloops
# alone came to 0.0. min_cost_flow_cost is network_simplex(G)[0] in nx.
_SIMPLEX_EDGES = {
    "selfloops_only": [(0, 0, 1.5), (12, 12, 2.0)],
    "negative_selfloop": [(0, 0, -1.5), (0, 1, 2.0)],
    "idle_float_edge": [(0, 1, 1.5)],
    "int_weights": [(0, 1, 2)],
    "selfloop_among_edges": [(0, 0, 2.5), (0, 1, 1), (1, 2, 2)],
}


@pytest.mark.parametrize("cls", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("case", sorted(_SIMPLEX_EDGES))
@pytest.mark.parametrize("fn", ["network_simplex", "min_cost_flow_cost"])
def test_network_simplex_cost_value_and_type_match_networkx(cls, case, fn):
    def outcome(lib):
        g = getattr(lib, cls)()
        for u, v, w in _SIMPLEX_EDGES[case]:
            g.add_edge(u, v, weight=w, capacity=3)
        result = getattr(lib, fn)(g)
        cost = result[0] if isinstance(result, tuple) else result
        return (cost, type(cost).__name__)

    assert outcome(fnx) == outcome(nx)


_EXACT_MIN_COST_APIS = (
    "min_cost_flow",
    "min_cost_flow_cost",
    "network_simplex",
    "capacity_scaling",
)


def _exact_demand_graph(lib, cls, demands, edges):
    graph = getattr(lib, cls)()
    graph.add_nodes_from((node, {"demand": value}) for node, value in demands)
    graph.add_edges_from(
        (u, v, {"capacity": capacity, "weight": weight})
        for u, v, capacity, weight in edges
    )
    return graph


@pytest.mark.parametrize("api", _EXACT_MIN_COST_APIS)
@pytest.mark.parametrize("cls", ["DiGraph", "MultiDiGraph"])
def test_min_cost_flow_keeps_exact_large_integer_demand_balance(api, cls):
    # The exact sum is zero, but converting these values to floats before
    # adding them produces -1 and used to reject this feasible network.
    amount = 2**54
    demands = [("t", amount), ("a", 1 - amount), ("s", -1)]
    edges = [("a", "t", amount, 1), ("s", "t", 1, 2)]
    expected = getattr(nx, api)(_exact_demand_graph(nx, cls, demands, edges))
    actual = getattr(fnx, api)(_exact_demand_graph(fnx, cls, demands, edges))
    assert actual == expected


@pytest.mark.parametrize("api", _EXACT_MIN_COST_APIS)
@pytest.mark.parametrize("cls", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("large_field", ["demand", "capacity", "weight"])
def test_min_cost_flow_accepts_integers_beyond_float_range(api, cls, large_field):
    huge = 10**400
    amount = huge if large_field == "demand" else 1
    capacity = huge if large_field in ("demand", "capacity") else 1
    weight = huge if large_field == "weight" else 2
    demands = [("s", -amount), ("t", amount)]
    edges = [("s", "t", capacity, weight)]
    expected = getattr(nx, api)(_exact_demand_graph(nx, cls, demands, edges))
    actual = getattr(fnx, api)(_exact_demand_graph(fnx, cls, demands, edges))
    assert actual == expected


@pytest.mark.parametrize("api", _EXACT_MIN_COST_APIS[:-1])
@pytest.mark.parametrize("cls", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("unit", [Fraction(1, 3), Decimal("0.1")])
def test_min_cost_flow_validates_in_the_original_numeric_domain(api, cls, unit):
    amount = 2**54 * unit
    demands = [("t", amount), ("a", unit - amount), ("s", -unit)]
    edges = [("a", "t", amount, 1), ("s", "t", unit, 2)]
    expected = getattr(nx, api)(_exact_demand_graph(nx, cls, demands, edges))
    actual = getattr(fnx, api)(_exact_demand_graph(fnx, cls, demands, edges))
    assert actual == expected


@pytest.mark.parametrize("api", _EXACT_MIN_COST_APIS)
@pytest.mark.parametrize("cls", ["DiGraph", "MultiDiGraph"])
def test_min_cost_flow_rejects_exact_nonzero_large_demand_sum(api, cls):
    amount = 2**54
    demands = [("s", -amount), ("t", amount + 1)]
    edges = [("s", "t", amount + 1, 1)]
    for lib in (nx, fnx):
        with pytest.raises(nx.NetworkXUnfeasible):
            getattr(lib, api)(_exact_demand_graph(lib, cls, demands, edges))


def _forbid_min_cost_numeric_route(*args, **kwargs):
    raise AssertionError("min-cost flow used the wrong numeric-domain route")


@pytest.mark.parametrize("api", _EXACT_MIN_COST_APIS)
@pytest.mark.parametrize("cls", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize(
    "case", ["cost_product", "unbounded_capacity_cost", "capacity_sum", "potentials"]
)
def test_min_cost_flow_avoids_native_intermediate_integer_overflow(api, cls, case, monkeypatch):
    if case in ("cost_product", "unbounded_capacity_cost"):
        amount = 4_000_000_000
        demands = [("s", -amount), ("t", amount)]
        capacity = float("inf") if case == "unbounded_capacity_cost" else amount
        edges = [("s", "t", capacity, amount)]
    elif case == "capacity_sum":
        demands = [("s", -1), ("t", 1)]
        edges = [
            edge
            for middle in range(8)
            for edge in [("s", middle, 2**59, 1), (middle, "t", 2**59, 1)]
        ]
    else:
        demands = [(0, -1), (3, 1)]
        edges = [(node, node + 1, 1, 2**59) for node in range(3)]

    simplex = import_module("franken_networkx._network_simplex_native")
    monkeypatch.setattr(simplex, "_native_ns_int", _forbid_min_cost_numeric_route)
    expected = getattr(nx, api)(_exact_demand_graph(nx, cls, demands, edges))
    actual = getattr(fnx, api)(_exact_demand_graph(fnx, cls, demands, edges))
    assert actual == expected


@pytest.mark.parametrize("api", _EXACT_MIN_COST_APIS)
@pytest.mark.parametrize("cls", ["DiGraph", "MultiDiGraph"])
def test_min_cost_flow_keeps_safe_integer_problem_native(api, cls, monkeypatch):
    simplex = import_module("franken_networkx._network_simplex_native")
    monkeypatch.setattr(
        simplex._DataEssentialsAndFunctions,
        "find_entering_edges",
        _forbid_min_cost_numeric_route,
    )
    demands = [("s", -5), ("t", 5)]
    edges = [("s", "a", 5, 2), ("a", "t", 5, 3)]
    expected = getattr(nx, api)(_exact_demand_graph(nx, cls, demands, edges))
    actual = getattr(fnx, api)(_exact_demand_graph(fnx, cls, demands, edges))
    assert actual == expected


def _parallel_demand_graph(lib, unit=1):
    graph = lib.MultiDiGraph()
    graph.add_node("source", balance=-5 * unit)
    graph.add_node(("middle", 1), balance=0)
    graph.add_node("sink", balance=5 * unit)
    graph.add_node("isolated", balance=0)
    graph.add_edge("source", ("middle", 1), key=("cheap", 0), units=3 * unit, cost=1)
    graph.add_edge("source", ("middle", 1), key="expensive", units=4 * unit, cost=4)
    graph.add_edge(("middle", 1), "sink", key=7, units=5 * unit, cost=2)
    graph.add_edge("source", "sink", key="closed", units=0, cost=-999)
    graph.add_edge(("middle", 1), ("middle", 1), key="profit", units=2 * unit, cost=-3)
    graph.add_edge(("middle", 1), ("middle", 1), key=("idle", 1), units=9 * unit, cost=2)
    return graph


def _forbid_upstream_min_cost_solver(*args, **kwargs):
    raise AssertionError("parallel-edge min-cost flow delegated to NetworkX")


@pytest.mark.parametrize("api", ["min_cost_flow", "min_cost_flow_cost", "network_simplex"])
@pytest.mark.parametrize("unit", [1, Fraction(1, 2), 2**70])
@pytest.mark.parametrize("input_kind", ["native", "networkx", "view"])
def test_parallel_min_cost_flow_is_owned_and_preserves_keys(api, unit, input_kind, monkeypatch):
    options = {"demand": "balance", "capacity": "units", "weight": "cost"}
    expected = getattr(nx, api)(_parallel_demand_graph(nx, unit), **options)
    graph = _parallel_demand_graph(nx if input_kind == "networkx" else fnx, unit)
    if input_kind == "view":
        graph = fnx.subgraph_view(graph)

    monkeypatch.setattr(nx, "network_simplex", _forbid_upstream_min_cost_solver)
    monkeypatch.setattr(
        nx.algorithms.flow.networksimplex,
        "network_simplex",
        _forbid_upstream_min_cost_solver,
    )
    actual = getattr(fnx, api)(graph, **options)
    assert actual == expected
    if api == "min_cost_flow_cost":
        assert actual == 15 * unit
        return

    flow = actual[1] if api == "network_simplex" else actual
    assert flow["isolated"] == {}
    assert flow["source"][("middle", 1)][("cheap", 0)] == 3 * unit
    assert flow["source"][("middle", 1)]["expensive"] == 2 * unit
    assert flow["source"]["sink"]["closed"] == 0
    assert flow[("middle", 1)][("middle", 1)]["profit"] == 2 * unit
    assert flow[("middle", 1)][("middle", 1)][("idle", 1)] == 0
    for node in graph:
        incoming = sum(flow[u][node][key] for u, _, key in graph.in_edges(node, keys=True))
        outgoing = sum(flow[node][v][key] for _, v, key in graph.out_edges(node, keys=True))
        assert incoming - outgoing == graph.nodes[node]["balance"]
    for u, v, key, data in graph.edges(keys=True, data=True):
        assert 0 <= flow[u][v][key] <= data["units"]


@pytest.mark.parametrize("native_kernel", [True, False])
@pytest.mark.parametrize("case", ["infeasible", "unbounded_cycle", "unbounded_selfloop"])
def test_parallel_min_cost_flow_failure_contract_without_upstream(case, native_kernel, monkeypatch):
    graph = fnx.MultiDiGraph()
    if case == "infeasible":
        graph.add_node("s", demand=-4)
        graph.add_node("t", demand=4)
        graph.add_edge("s", "t", key="a", capacity=1, weight=1)
        graph.add_edge("s", "t", key="b", capacity=2, weight=2)
        error, message = nx.NetworkXUnfeasible, "no flow satisfies all node demands"
    else:
        graph.add_edge("s", "t", key="a", weight=-2)
        graph.add_edge("s", "t", key="b", capacity=3, weight=2)
        graph.add_edge("t", "s", key="back", weight=1)
        if case == "unbounded_selfloop":
            graph["s"]["t"]["a"]["capacity"] = 1
            graph.add_edge("t", "t", key=("loop", 0), weight=-1)
        error, message = nx.NetworkXUnbounded, "negative cycle with infinite capacity found"

    if not native_kernel:
        simplex = import_module("franken_networkx._network_simplex_native")
        monkeypatch.setattr(simplex, "_native_ns_int", None)
    monkeypatch.setattr(nx, "network_simplex", _forbid_upstream_min_cost_solver)
    with pytest.raises(error, match=message):
        fnx.min_cost_flow(graph)


@pytest.mark.parametrize("seed", range(12))
def test_parallel_min_cost_flow_matches_simplex_on_circulations(seed, monkeypatch):
    rng = random.Random(seed)
    graph = nx.MultiDiGraph()
    graph.add_nodes_from(range(5))
    for u in graph:
        for v in graph:
            for key in range(rng.randrange(3)):
                graph.add_edge(u, v, key=key, capacity=rng.randrange(5), weight=rng.randrange(-3, 6))
    expected = nx.network_simplex(graph)
    native_graph = fnx.MultiDiGraph(graph)
    monkeypatch.setattr(nx, "network_simplex", _forbid_upstream_min_cost_solver)
    actual = fnx.network_simplex(native_graph)
    assert actual == expected


@pytest.mark.parametrize("cls", ["Graph", "DiGraph"])
@pytest.mark.parametrize("amount", [2**54 + 1, 10**400])
def test_max_flow_min_cost_preserves_exact_flow_demand(cls, amount):
    demands = [("s", 0), ("t", 0)]
    edges = [("s", "t", amount, 2)]
    expected = nx.max_flow_min_cost(
        _exact_demand_graph(nx, cls, demands, edges), "s", "t"
    )
    actual = fnx.max_flow_min_cost(
        _exact_demand_graph(fnx, cls, demands, edges), "s", "t"
    )
    assert actual == expected


def _cost_flow_typed_result(value):
    if isinstance(value, dict):
        return tuple((key, _cost_flow_typed_result(item)) for key, item in value.items())
    if isinstance(value, tuple):
        return tuple(_cost_flow_typed_result(item) for item in value)
    return type(value), value


def _cost_flow_outcome(function, graph, **options):
    try:
        return "return", _cost_flow_typed_result(function(graph, **options))
    except Exception as exc:
        return "raise", type(exc), exc.args


def _cost_flow_input(source, input_kind):
    if input_kind == "networkx":
        return source
    if input_kind == "networkx_view":
        return nx.subgraph_view(source)
    graph_class = getattr(fnx, type(source).__name__)
    graph = graph_class()
    if input_kind == "native":
        graph.add_nodes_from(source.nodes(data=True))
        graph.add_edges_from(
            source.edges(keys=True, data=True) if source.is_multigraph()
            else source.edges(data=True)
        )
    else:
        graph.add_edge("stale", "storage", capacity=7, weight=99)
        graph._node = source._node
        graph._adj = source._adj
        graph._pred = source._pred
    return graph


@pytest.mark.parametrize("api", _EXACT_MIN_COST_APIS[:-1])
@pytest.mark.parametrize("cls", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("input_kind", ["native", "networkx", "assigned", "networkx_view"])
@pytest.mark.parametrize("disabled_weight", [None, "closed", float("inf"), -float("inf"), 1.5])
def test_zero_capacity_edges_do_not_change_simplex_objective(
    api, cls, input_kind, disabled_weight, monkeypatch,
):
    source = getattr(nx, cls)()
    source.add_node("source", balance=-1)
    source.add_node("sink", balance=1)
    source.add_edge("source", "sink", limit=1, price=2)
    source.add_edge("source", "disabled", limit=0, price=disabled_weight)
    if source.is_multigraph():
        source.add_edge("source", "sink", key=("closed", 1), limit=0, price=disabled_weight)
    options = {"demand": "balance", "capacity": "limit", "weight": "price"}
    expected = _cost_flow_outcome(getattr(nx, api), source, **options)
    actual_input = _cost_flow_input(source, input_kind)
    monkeypatch.setattr(nx, "network_simplex", _forbid_upstream_min_cost_solver)
    monkeypatch.setattr(
        nx.algorithms.flow.networksimplex, "network_simplex", _forbid_upstream_min_cost_solver,
    )
    assert _cost_flow_outcome(getattr(fnx, api), actual_input, **options) == expected


@pytest.mark.parametrize("api", _EXACT_MIN_COST_APIS[:-1])
@pytest.mark.parametrize("cls", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("input_kind", ["networkx", "assigned", "networkx_view"])
def test_cost_flow_reads_demand_once_before_observing_edges(api, cls, input_kind):
    def build():
        graph = getattr(nx, cls)()
        graph.add_node("source", balance=-1)
        graph.add_node("sink", balance=1)
        events = []

        class Demand(dict):
            def get(self, key, default=None):
                if key == "balance":
                    events.append(key)
                    if len(events) != 1:
                        raise AssertionError("demand provider was read more than once")
                    graph.add_edge("source", "sink", limit=1, price=7)
                return super().get(key, default)

        graph._node["source"] = Demand(graph._node["source"])
        return graph, events

    options = {"demand": "balance", "capacity": "limit", "weight": "price"}
    source, expected_events = build()
    expected = _cost_flow_outcome(getattr(nx, api), source, **options)
    actual_source, actual_events = build()
    graph = _cost_flow_input(actual_source, input_kind)
    assert _cost_flow_outcome(getattr(fnx, api), graph, **options) == expected
    assert actual_events == expected_events == ["balance"]
    assert list(graph.edges(data=True)) == list(actual_source.edges(data=True))


@pytest.mark.parametrize("api", _EXACT_MIN_COST_APIS[:-1])
@pytest.mark.parametrize("cls", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("input_kind", ["networkx", "assigned", "networkx_view"])
def test_cost_flow_keeps_objective_from_the_solved_attribute_values(api, cls, input_kind):
    def build():
        graph = getattr(nx, cls)()
        graph.add_node("source", demand=-1)
        graph.add_node("sink", demand=1)
        graph.add_edge("source", "sink", capacity=1, weight=2)
        events = []

        class Price(dict):
            def get(self, key, default=None):
                value = super().get(key, default)
                if key == "weight":
                    events.append(value)
                    self["weight"] = 37
                return value

        if graph.is_multigraph():
            data = Price(graph["source"]["sink"][0])
            graph._succ["source"]["sink"][0] = data
        else:
            data = Price(graph["source"]["sink"])
            graph._succ["source"]["sink"] = data
            graph._pred["sink"]["source"] = data
        return graph, events, data

    source, expected_events, expected_data = build()
    expected = _cost_flow_outcome(getattr(nx, api), source)
    actual_source, actual_events, actual_data = build()
    actual = _cost_flow_outcome(getattr(fnx, api), _cost_flow_input(actual_source, input_kind))
    assert actual == expected
    assert actual_events == expected_events == [2]
    assert actual_data == expected_data


@pytest.mark.parametrize("api", _EXACT_MIN_COST_APIS[:-1])
@pytest.mark.parametrize("cls", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("field", ["demand", "capacity", "weight"])
@pytest.mark.parametrize("renamed", [False, True])
def test_cost_flow_observes_topology_changes_from_numeric_protocols(api, cls, field, renamed):
    options = (
        {"demand": "balance", "capacity": "limit", "weight": "price"}
        if renamed else {name: name for name in ("demand", "capacity", "weight")}
    )

    def run(library):
        graph = getattr(library, cls)()
        events = []

        def add_loop(operation):
            events.append(operation)
            graph.add_edge(
                "source", "source", **{options["capacity"]: -1, options["weight"]: 0},
            )

        class Scalar(int):
            def __abs__(self):
                add_loop("abs")
                return abs(int(self))

            def __lt__(self, other):
                add_loop("lt")
                return int(self) < other

        values = {"demand": -1, "capacity": 1, "weight": 2}
        values[field] = Scalar(values[field])
        graph.add_node("source", **{options["demand"]: values["demand"]})
        graph.add_node("sink", **{options["demand"]: 1})
        graph.add_edge(
            "source", "sink",
            **{options["capacity"]: values["capacity"], options["weight"]: values["weight"]},
        )
        return _cost_flow_outcome(getattr(library, api), graph, **options), events

    expected, expected_events = run(nx)
    actual, actual_events = run(fnx)
    assert expected[0] == "raise" and expected[1] is nx.NetworkXUnfeasible
    assert actual == expected
    assert actual_events == expected_events == ["lt" if field == "capacity" else "abs"]


@pytest.mark.parametrize("api", _EXACT_MIN_COST_APIS[:-1])
@pytest.mark.parametrize("cls", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("input_kind", ["native", "assigned"])
@pytest.mark.parametrize(
    "case", ["infinite_demand", "infinite_weight", "unbalanced", "negative_key", "zero_loop"],
)
def test_cost_flow_shares_simplex_validation_order_and_keyed_errors(api, cls, input_kind, case):
    source = getattr(nx, cls)()
    source.add_node("source", demand=float("inf") if case == "infinite_demand" else 0)
    source.add_node("sink", demand=1 if case == "unbalanced" else 0)
    edge_weight = float("inf") if case == "infinite_weight" else 1
    if case == "zero_loop":
        source.add_edge("source", "source", capacity=0, weight=float("inf"))
    elif source.is_multigraph():
        source.add_edge("source", "sink", key=("invalid", 3), capacity=-1, weight=edge_weight)
    else:
        source.add_edge("source", "sink", capacity=-1, weight=edge_weight)
    expected = _cost_flow_outcome(getattr(nx, api), source)
    actual = _cost_flow_outcome(getattr(fnx, api), _cost_flow_input(source, input_kind))
    assert actual == expected


@pytest.mark.parametrize("api", _EXACT_MIN_COST_APIS[:-1])
@pytest.mark.parametrize("cls", ["DiGraph", "MultiDiGraph"])
def test_cost_flow_solves_safe_integer_problem_once(api, cls, monkeypatch):
    simplex = import_module("franken_networkx._network_simplex_native")
    original = simplex._native_ns_int
    calls = []

    def recorded(*args):
        calls.append(args)
        return original(*args)

    monkeypatch.setattr(simplex, "_native_ns_int", recorded)
    graph = getattr(fnx, cls)()
    graph.add_node("source", demand=-3)
    graph.add_node("sink", demand=3)
    graph.add_edge("source", "sink", capacity=4, weight=2)
    result = getattr(fnx, api)(graph)
    assert len(calls) == 1
    if api == "min_cost_flow_cost":
        assert result == 6 and type(result) is int


@pytest.mark.parametrize("cls", ["DiGraph", "MultiDiGraph"])
def test_cost_flow_bulk_adapter_retains_owned_plain_read_attributes(cls):
    simplex = import_module("franken_networkx._network_simplex_native")
    graph = getattr(fnx, cls)()
    graph.add_node("source", demand=-1, payload=object())
    graph.add_node("sink", demand=1)
    graph.add_edge("source", "sink", capacity=1, weight=2, payload=object())
    adapter = simplex._FastG(graph)
    assert adapter._source is None
    assert list(adapter.edges(data=True, keys=graph.is_multigraph())) == list(
        graph.edges(data=True, keys=True) if graph.is_multigraph()
        else graph.edges(data=True)
    )


@pytest.mark.parametrize("api", _EXACT_MIN_COST_APIS[:-1])
@pytest.mark.parametrize("cls", ["DiGraph", "MultiDiGraph"])
def test_cost_flow_respects_patched_owned_attribute_read_protocols(api, cls, monkeypatch):
    graph = getattr(fnx, cls)()
    graph.add_node("source", demand=-1)
    graph.add_node("sink", demand=1)
    graph.add_edge("source", "sink", capacity=1, weight=2)
    expected_graph = getattr(nx, cls)()
    expected_graph.add_node("source", demand=-1)
    expected_graph.add_node("sink", demand=1)
    expected_graph.add_edge("source", "sink", capacity=1, weight=2)
    expected = _cost_flow_outcome(getattr(nx, api), expected_graph)
    attrs = graph["source"]["sink"]
    if graph.is_multigraph():
        attrs = attrs[0]
    events = []

    def observed_get(self, key, default=None):
        value = dict.get(self, key, default)
        if key == "weight":
            events.append(value)
            self["weight"] = 37
        return value

    monkeypatch.setattr(type(attrs), "get", observed_get)
    assert _cost_flow_outcome(getattr(fnx, api), graph) == expected
    assert events == [2]
    assert attrs["weight"] == 37
