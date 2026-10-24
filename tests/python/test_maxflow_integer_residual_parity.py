"""Parity for the integer-relabeled Edmonds-Karp residual hot loop.

br-flowint: compute_max_flow_residual (the Edmonds-Karp core behind maximum_flow,
minimum_cut, edge_connectivity and node_connectivity) used a String-keyed residual
``HashMap<String, HashMap<String, f64>>`` and re-sorted the neighbor list
(``neighbors.sort_unstable()``) on EVERY BFS visit -- String hashing, cloning and
an O(deg log deg) re-sort per node per augmenting path. The hot loop now relabels
nodes to integers in lexicographic (string) order -- so ascending-index neighbor
iteration reproduces the original traversal order EXACTLY -- and runs the BFS on
flat ``Vec<bool>`` / ``Vec<usize>`` arrays with an ordered ``BTreeMap`` residual,
re-materializing the string residual only once at the end. Augmenting paths,
flow values, residual and min-cut are byte-identical; maximum_flow_value is now
faster than networkx and edge_connectivity's gap roughly halves.
"""

import random
from decimal import Decimal
from fractions import Fraction

import networkx as nx
import pytest

import franken_networkx as fnx


def _cp(Gx, directed=False):
    Gf = fnx.DiGraph() if directed else fnx.Graph()
    Gf.add_nodes_from(Gx.nodes())
    Gf.add_edges_from(Gx.edges(data=True))
    return Gf


def test_maxflow_and_mincut_value_match_networkx():
    for seed in range(80):
        rnd = random.Random(seed)
        n = rnd.randint(4, 32)
        directed = seed % 2 == 0
        Gx = nx.gnp_random_graph(n, rnd.uniform(0.1, 0.4), seed=seed, directed=directed)
        for u, v in Gx.edges():
            Gx[u][v]["capacity"] = rnd.randint(1, 15)
        if Gx.number_of_nodes() < 2:
            continue
        Gf = _cp(Gx, directed=directed)
        nodes = list(Gx.nodes())
        s, t = nodes[0], nodes[-1]
        assert nx.maximum_flow_value(Gx, s, t) == fnx.maximum_flow_value(Gf, s, t), seed
        assert nx.minimum_cut_value(Gx, s, t) == fnx.minimum_cut_value(Gf, s, t), seed


def test_maxflow_value_conservation():
    rnd = random.Random(11)
    Gx = nx.gnp_random_graph(40, 0.1, seed=11, directed=True)
    for u, v in Gx.edges():
        Gx[u][v]["capacity"] = rnd.randint(1, 10)
    Gf = _cp(Gx, directed=True)
    val, flow = fnx.maximum_flow(Gf, 0, 39)
    assert (val, flow) == nx.maximum_flow(Gx, 0, 39)
    # A valid flow can circulate back into the source: this fixture has
    # outgoing flow 25 and incoming flow 4 in NetworkX, for net flow 21.
    # Check net source/sink balance and conservation at every other node.
    terminal_balances = {0: val, 39: -val}
    for node, outgoing in flow.items():
        incoming = sum(row.get(node, 0) for row in flow.values())
        assert sum(outgoing.values()) - incoming == terminal_balances.get(node, 0), node
        for neighbor, amount in outgoing.items():
            assert 0 <= amount <= Gx[node][neighbor]["capacity"]


def test_edge_connectivity_matches_networkx():
    for seed in range(60):
        G = nx.gnp_random_graph(random.Random(seed).randint(5, 45), 0.12, seed=seed)
        F = _cp(G)
        assert nx.edge_connectivity(G) == fnx.edge_connectivity(F), seed


def test_node_connectivity_matches_networkx():
    for seed in range(40):
        G = nx.gnp_random_graph(random.Random(seed).randint(5, 40), 0.12, seed=seed)
        F = _cp(G)
        assert nx.node_connectivity(G) == fnx.node_connectivity(F), seed


def test_local_st_edge_connectivity():
    G = nx.gnp_random_graph(30, 0.2, seed=2)
    F = _cp(G)
    assert nx.edge_connectivity(G, 0, 15) == fnx.edge_connectivity(F, 0, 15)


def test_disconnected_edge_connectivity_zero():
    G = fnx.Graph([(0, 1), (2, 3)])
    assert fnx.edge_connectivity(G) == 0


_FLOW_APIS = {
    "maximum_flow": ("_raw_maximum_flow", "_maximum_flow_inproc"),
    "maximum_flow_value": ("_raw_maximum_flow_value", "_maximum_flow_value_inproc"),
    "minimum_cut": ("_minimum_cut_raw", "_minimum_cut_inproc"),
    "minimum_cut_value": ("_minimum_cut_value_raw", "_minimum_cut_value_inproc"),
}


def _forbid_flow_route(*args, **kwargs):
    raise AssertionError("flow used the wrong numeric-domain route")


def _check_flow_numeric_parity(api, graph):
    expected = getattr(nx, api)(graph, "s", "t")
    actual = getattr(fnx, api)(_cp(graph, directed=graph.is_directed()), "s", "t")
    assert actual == expected
    if api in ("maximum_flow", "minimum_cut"):
        value, expected_value = actual[0], expected[0]
    else:
        value, expected_value = actual, expected
    assert type(value) is type(expected_value)
    if api == "maximum_flow":
        flow = actual[1]
        for node, outgoing in flow.items():
            incoming = sum(row.get(node, 0) for row in flow.values())
            balance = sum(outgoing.values()) - incoming
            expected_balance = value if node == "s" else -value if node == "t" else 0
            assert balance == expected_balance
            for neighbor, amount in outgoing.items():
                assert type(amount) is type(expected[1][node][neighbor])
    return value


@pytest.mark.parametrize("api", _FLOW_APIS)
@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("capacity", [2**53 + 1, 2**60 + 3])
def test_native_large_integer_flow_is_exact(api, directed, capacity, monkeypatch):
    graph = nx.DiGraph() if directed else nx.Graph()
    graph.add_edge("s", "t", capacity=capacity)
    monkeypatch.setattr(fnx, _FLOW_APIS[api][1], _forbid_flow_route)
    assert _check_flow_numeric_parity(api, graph) == capacity


@pytest.mark.parametrize("api", _FLOW_APIS)
@pytest.mark.parametrize("directed", [False, True])
def test_native_flow_sum_retains_integer_precision(api, directed, monkeypatch):
    graph = nx.DiGraph() if directed else nx.Graph()
    # Every input is exactly representable as f64, but their maximum-flow
    # total is not. Checking only the input capacities misses this defect.
    graph.add_edge("s", "t", capacity=2**52)
    graph.add_edge("s", "a", capacity=2**52 + 1)
    graph.add_edge("a", "t", capacity=2**52 + 1)
    monkeypatch.setattr(fnx, _FLOW_APIS[api][1], _forbid_flow_route)
    assert _check_flow_numeric_parity(api, graph) == 2**53 + 1


class _CapacityInt(int):
    pass


@pytest.mark.parametrize("api", _FLOW_APIS)
@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize(
    "capacity",
    [2**63 + 1, 10**100, Fraction(1, 3), Decimal("0.3"), _CapacityInt(2**53 + 1)],
)
def test_exact_numeric_domains_stay_in_python(api, directed, capacity, monkeypatch):
    graph = nx.DiGraph() if directed else nx.Graph()
    graph.add_edge("s", "t", capacity=capacity)
    monkeypatch.setattr(fnx, _FLOW_APIS[api][0], _forbid_flow_route)
    assert _check_flow_numeric_parity(api, graph) == capacity


@pytest.mark.parametrize("api", _FLOW_APIS)
@pytest.mark.parametrize("directed", [False, True])
def test_integral_flow_aggregate_overflow_stays_exact(api, directed, monkeypatch):
    graph = nx.DiGraph() if directed else nx.Graph()
    # Every capacity fits i64, but saturation of source arcs does not.
    for middle in ("a", "b"):
        graph.add_edge("s", middle, capacity=2**62 + 1)
        graph.add_edge(middle, "t", capacity=2**62 + 1)
    monkeypatch.setattr(fnx, _FLOW_APIS[api][0], _forbid_flow_route)
    assert _check_flow_numeric_parity(api, graph) == 2**63 + 2


@pytest.mark.parametrize("api", _FLOW_APIS)
@pytest.mark.parametrize("directed", [False, True])
def test_opposing_capacity_overflow_stays_exact(api, directed, monkeypatch):
    graph = nx.DiGraph() if directed else nx.Graph()
    graph.add_edge("s", "a", capacity=2**62 + 1)
    if directed:
        graph.add_edge("a", "s", capacity=2**62 + 1)
    graph.add_edge("a", "t", capacity=1)
    # Returning the excess to s computes cap - negative_flow on a->s,
    # which can overflow even though the final maximum flow is only one.
    monkeypatch.setattr(fnx, _FLOW_APIS[api][0], _forbid_flow_route)
    assert _check_flow_numeric_parity(api, graph) == 1


@pytest.mark.parametrize("api", _FLOW_APIS)
@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize(
    "capacities", [(True, True), (False, True), (1.5, 2), (2, 3.0), (3, 2.5), (0.0, 1.0)]
)
def test_native_flow_preserves_mixed_numeric_types(api, directed, capacities, monkeypatch):
    graph = nx.DiGraph() if directed else nx.Graph()
    graph.add_edge("s", "a", capacity=capacities[0])
    graph.add_edge("a", "t", capacity=capacities[1])
    monkeypatch.setattr(fnx, _FLOW_APIS[api][1], _forbid_flow_route)
    _check_flow_numeric_parity(api, graph)
