"""Differential parity for current-flow (electrical) centralities.

Covers ``current_flow_closeness_centrality`` (== ``information_centrality``),
``current_flow_betweenness_centrality`` and
``edge_current_flow_betweenness_centrality``. None had a dedicated test
file. All require a connected undirected graph.

br-r37-c1-ckk8d
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _connected(seed, p=0.5):
    rng = random.Random(seed)
    n = rng.randint(5, 9)
    p_cur = p
    for _ in range(60):
        fg = fnx.Graph()
        ng = nx.Graph()
        fg.add_nodes_from(range(n))
        ng.add_nodes_from(range(n))
        for u in range(n):
            for v in range(u + 1, n):
                if rng.random() < p_cur:
                    fg.add_edge(u, v)
                    ng.add_edge(u, v)
        if nx.is_connected(ng):
            return fg, ng, n
        p_cur = min(0.9, p_cur + 0.05)
    return None


def _close_dict(a, b, tol=1e-6):
    assert set(a) == set(b)
    for k in b:
        assert a[k] == pytest.approx(b[k], abs=tol, rel=1e-6)


@pytest.mark.parametrize("fn", [
    "current_flow_closeness_centrality",
    "current_flow_betweenness_centrality",
])
@pytest.mark.parametrize("seed", range(25))
def test_node_current_flow_matches_networkx(fn, seed):
    pair = _connected(seed)
    if pair is None:
        pytest.skip("no connected graph")
    fg, ng, _ = pair
    _close_dict(getattr(fnx, fn)(fg), getattr(nx, fn)(ng))


@pytest.mark.parametrize("seed", range(25))
def test_edge_current_flow_betweenness_matches_networkx(seed):
    pair = _connected(seed)
    if pair is None:
        pytest.skip("no connected graph")
    fg, ng, _ = pair
    fe = {tuple(sorted(k)): v for k, v in
          fnx.edge_current_flow_betweenness_centrality(fg).items()}
    ne = {tuple(sorted(k)): v for k, v in
          nx.edge_current_flow_betweenness_centrality(ng).items()}
    _close_dict(fe, ne)


@pytest.mark.parametrize("seed", range(15))
def test_information_centrality_is_current_flow_closeness(seed):
    pair = _connected(seed)
    if pair is None:
        pytest.skip("no connected graph")
    fg, ng, _ = pair
    # information_centrality is an alias of current_flow_closeness_centrality.
    _close_dict(fnx.information_centrality(fg), fnx.current_flow_closeness_centrality(fg))
    _close_dict(fnx.information_centrality(fg), nx.information_centrality(ng))


def test_disconnected_raises_like_networkx():
    fg = fnx.Graph([(0, 1), (2, 3)])
    ng = nx.Graph([(0, 1), (2, 3)])
    with pytest.raises(nx.NetworkXError):
        fnx.current_flow_closeness_centrality(fg)
    with pytest.raises(nx.NetworkXError):
        nx.current_flow_closeness_centrality(ng)



_NATIVE_CURRENT_FLOW = {
    "current_flow_betweenness_centrality": (
        "current_flow_betweenness_centrality_nx_ordered_rust"
    ),
    "edge_current_flow_betweenness_centrality": (
        "edge_current_flow_betweenness_centrality_nx_ordered_rust"
    ),
}


@pytest.mark.parametrize("name,native_name", _NATIVE_CURRENT_FLOW.items())
@pytest.mark.parametrize("normalized", [True, False])
@pytest.mark.parametrize("loop_nodes", [(0,), (1,), (2,), (0, 1, 2)])
def test_current_flow_self_loops_match_networkx_with_owned_rows(
    name, native_name, normalized, loop_nodes, monkeypatch
):
    graphs = [module.path_graph(3) for module in (fnx, nx)]
    for graph in graphs:
        graph.add_edges_from((node, node) for node in loop_nodes)
    expected = getattr(nx, name)(graphs[1], normalized=normalized)

    def reject_native(*args, **kwargs):
        raise AssertionError("The native kernel omits self-loop flow rows")

    monkeypatch.setattr(fnx._fnx, native_name, reject_native)
    actual = getattr(fnx, name)(graphs[0], normalized=normalized)
    assert list(actual) == list(expected)
    _close_dict(actual, expected)


@pytest.mark.parametrize("name,native_name", _NATIVE_CURRENT_FLOW.items())
@pytest.mark.parametrize("normalized", [True, False])
def test_current_flow_loop_free_graphs_keep_native_route(
    name, native_name, normalized, monkeypatch
):
    graphs = [module.path_graph(5) for module in (fnx, nx)]
    expected = getattr(nx, name)(graphs[1], normalized=normalized)
    native = getattr(fnx._fnx, native_name)
    calls = []

    def record_native(*args):
        calls.append(args[0])
        return native(*args)

    monkeypatch.setattr(fnx._fnx, native_name, record_native)
    actual = getattr(fnx, name)(graphs[0], normalized=normalized)
    assert calls == [graphs[0]]
    assert list(actual) == list(expected)
    _close_dict(actual, expected)


@pytest.mark.parametrize("name", _NATIVE_CURRENT_FLOW)
@pytest.mark.parametrize("normalized", [True, False])
@pytest.mark.parametrize("seed", range(12))
def test_current_flow_looped_connected_graphs_match_networkx(name, normalized, seed):
    rng = random.Random(seed)
    # A path keeps every fixture connected; chords and loops change degree
    # ties, RCM grounding, and the flow rows independently of connectivity.
    edges = [(node, node + 1) for node in range(6)]
    edges.extend(
        (left, right)
        for left in range(7)
        for right in range(left + 2, 7)
        if rng.random() < 0.3
    )
    edges.extend((node, node) for node in range(7) if rng.random() < 0.6)
    actual_graph = fnx.Graph(edges)
    reference_graph = nx.Graph(edges)
    expected = getattr(nx, name)(reference_graph, normalized=normalized)
    actual = getattr(fnx, name)(actual_graph, normalized=normalized)
    assert list(actual) == list(expected)
    _close_dict(actual, expected)


def test_current_flow_rcm_counts_self_loops_in_degree_ties(monkeypatch):
    from networkx.utils.rcm import pseudo_peripheral_node

    edges = [
        (0, 1), (0, 5), (0, 0), (1, 2), (1, 3), (1, 4), (1, 5),
        (2, 4), (2, 5), (3, 3), (4, 5), (4, 4), (5, 5),
    ]
    graphs = [module.Graph() for module in (fnx, nx)]
    for graph in graphs:
        graph.add_nodes_from(range(6))
        graph.add_edges_from(edges)
    assert pseudo_peripheral_node(graphs[1]) == 2

    def reject_native_start(*args, **kwargs):
        raise AssertionError("The native heuristic counts each self-loop once")

    monkeypatch.setattr(
        fnx._fnx, "current_flow_pseudo_peripheral_node_rust", reject_native_start
    )
    assert fnx._current_flow_rcm_ordering(graphs[0]) == list(
        nx.utils.reverse_cuthill_mckee_ordering(graphs[1])
    )
    for name in _NATIVE_CURRENT_FLOW:
        expected = getattr(nx, name)(graphs[1])
        actual = getattr(fnx, name)(graphs[0])
        assert list(actual) == list(expected)
        _close_dict(actual, expected)


@pytest.mark.parametrize(
    "name", ["current_flow_closeness_centrality", "information_centrality"]
)
def test_current_flow_self_loops_do_not_change_laplacian_closeness(name):
    graphs = [module.path_graph(5) for module in (fnx, nx)]
    for graph in graphs:
        graph.add_edges_from((node, node) for node in range(5))
    expected = getattr(nx, name)(graphs[1])
    actual = getattr(fnx, name)(graphs[0])
    assert list(actual) == list(expected)
    _close_dict(actual, expected)



@pytest.mark.parametrize(
    "algorithm",
    [
        "current_flow_closeness_centrality", "information_centrality",
        "current_flow_betweenness_centrality", "edge_current_flow_betweenness_centrality",
        "approximate_current_flow_betweenness_centrality",
    ],
)
@pytest.mark.parametrize("filtered", [False, True])
def test_none_key_current_flow_after_weight_mutation(algorithm, filtered):
    graphs = []
    attrs = []
    for module in (fnx, nx):
        graph = module.cycle_graph(4)
        attrs.append(graph[1][2])
        if filtered:
            graph.add_edge(0, 2)
            graph = module.subgraph_view(graph, filter_edge=lambda u, v: {u, v} != {0, 2})
        graphs.append(graph)
    kwargs = {"seed": 17, "epsilon": 0.75} if algorithm.startswith("approximate") else {}
    for value in (3.0, 0.25):
        for data in attrs:
            data[None] = value
        expected = getattr(nx, algorithm)(graphs[1], weight=None, **kwargs)
        actual = getattr(fnx, algorithm)(graphs[0], weight=None, **kwargs)
        assert list(actual) == list(expected)
        assert actual == pytest.approx(expected, abs=1e-10)


@pytest.mark.parametrize(
    "algorithm",
    [
        "current_flow_closeness_centrality", "current_flow_betweenness_centrality",
        "current_flow_betweenness_centrality_subset",
        "edge_current_flow_betweenness_centrality_subset",
    ],
)
@pytest.mark.parametrize("filtered", [False, True])
def test_none_key_current_flow_preserves_key_protocol(algorithm, filtered):
    def outcome(module):
        graph = module.cycle_graph(4)
        original_graph = graph
        events = []

        class WeightKey:
            def __hash__(self):
                events.append("hash")
                return hash(None)

            def __eq__(self, other):
                events.append("compare")
                if other is None:
                    original_graph.add_node(9)
                    return True
                return self is other

            def __str__(self):
                raise AssertionError("a current-flow calculation coerced an attribute key")

        graph[1][2][WeightKey()] = 3
        if filtered:
            graph.add_edge(0, 2)
            graph = module.subgraph_view(graph, filter_edge=lambda u, v: {u, v} != {0, 2})
        events.clear()
        kwargs = {"sources": [0, 1], "targets": [2, 3]} if algorithm.endswith("_subset") else {}
        return getattr(module, algorithm)(graph, weight=None, **kwargs), events

    expected, expected_events = outcome(nx)
    actual, actual_events = outcome(fnx)
    assert actual_events == expected_events
    assert actual == pytest.approx(expected, abs=1e-10)
