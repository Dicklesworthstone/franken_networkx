"""node/edge_disjoint_paths parity with networkx: the paths, their order, and
the exception contract.

When s and t are disconnected, networkx's disjoint-path generators raise
``NetworkXNoPath`` on iteration; the Rust fast path used to yield an empty
generator instead (silent divergence). The degenerate ``s == t`` case for
``node_disjoint_paths`` (nx yields the cycles through s) was also wrong.

Found via the Menger disjoint-paths cross-check (the same metamorphic method
that surfaced the two P1 node_connectivity bugs). br-r37-c1-xn2ho

br-r37-c1-r6ce1: the native kernel used to find *a* maximum set of disjoint
paths over hash-set adjacency, so the paths - not just their order - moved
from run to run and differed from networkx's. It is now networkx's algorithm
step for step (auxiliary digraph, residual network, bidirectional-BFS
Edmonds-Karp, flow-dict rebuild), so every row here compares the whole list,
exceptions by type and args.
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import networkx.algorithms.connectivity.disjoint_paths as nx_disjoint
from networkx.exception import NetworkXNoPath
import franken_networkx as fnx
import franken_networkx.backend as fnx_backend
import franken_networkx.connectivity as fnx_connectivity
import franken_networkx.flow as fnx_flow


def _outcome(fn, *args, **kwargs):
    try:
        return ("ok", list(fn(*args, **kwargs)))
    except Exception as exc:  # noqa: BLE001 — exception parity is the point
        return ("err", type(exc).__name__, exc.args)


_PAIRS = [
    (fnx.node_disjoint_paths, nx.node_disjoint_paths),
    (fnx.edge_disjoint_paths, nx.edge_disjoint_paths),
]

_CLASSES = [
    (fnx.Graph, nx.Graph),
    (fnx.DiGraph, nx.DiGraph),
    (fnx.MultiGraph, nx.MultiGraph),
    (fnx.MultiDiGraph, nx.MultiDiGraph),
]


def _assert_same(G, NG, s, t):
    for ff, nf in _PAIRS:
        assert _outcome(ff, G, s, t) == _outcome(nf, NG, s, t), (
            nf.__name__, s, t, list(NG.edges()),
        )


def test_disconnected_raises_networkx_no_path():
    g = fnx.Graph([(0, 1), (2, 3)])
    with pytest.raises(NetworkXNoPath):
        list(fnx.node_disjoint_paths(g, 0, 3))
    with pytest.raises(NetworkXNoPath):
        list(fnx.edge_disjoint_paths(g, 0, 3))


def test_directed_disconnected_raises():
    d = fnx.DiGraph([(0, 1), (1, 0), (2, 3)])
    with pytest.raises(NetworkXNoPath):
        list(fnx.node_disjoint_paths(d, 0, 3))
    with pytest.raises(NetworkXNoPath):
        list(fnx.edge_disjoint_paths(d, 0, 3))


def test_node_disjoint_same_source_sink_matches_networkx():
    g = fnx.Graph([(0, 1), (1, 2)])
    ng = nx.Graph([(0, 1), (1, 2)])
    assert _outcome(fnx.node_disjoint_paths, g, 0, 0) == _outcome(
        nx.node_disjoint_paths, ng, 0, 0
    )


@pytest.mark.parametrize("fcls,ncls", _CLASSES)
def test_same_source_sink_and_self_loops_match_networkx(fcls, ncls):
    # s == t: node_disjoint_paths yields the cycles through s (each node
    # once); edge_disjoint_paths raises NetworkXNoPath for a node without
    # edges and "source and sink are the same node" otherwise - networkx's
    # order of checks, which fnx used to invert (it raised the same-node
    # error first, even for a node that is not in the graph).
    edges = [(0, 1), (1, 2), (2, 0), (2, 3), (3, 0)]
    G, NG = fcls(edges), ncls(edges)
    G.add_node(9)
    NG.add_node(9)
    for s in (0, 2, 9):
        _assert_same(G, NG, s, s)
    # A self-loop is one auxiliary arc: counted in the degrees that bound
    # the paths, dropped from the edge residual, a B -> A arc in the
    # node-split graph (so node_disjoint_paths(G, s, s) yields [s]).
    G.add_edge(0, 0)
    NG.add_edge(0, 0)
    for s, t in [(0, 0), (0, 2), (2, 0), (3, 3)]:
        _assert_same(G, NG, s, t)
    for ff, nf in _PAIRS:
        assert _outcome(ff, G, 7, 7) == _outcome(nf, NG, 7, 7)
        assert _outcome(ff, G, 0, 7) == _outcome(nf, NG, 0, 7)


@pytest.mark.parametrize("seed", range(70))
def test_paths_and_order_are_networkxs(seed):
    r = random.Random(seed)
    n = r.randint(5, 9)
    directed = r.random() < 0.5
    G = fnx.DiGraph() if directed else fnx.Graph()
    NG = nx.DiGraph() if directed else nx.Graph()
    G.add_nodes_from(range(n))
    NG.add_nodes_from(range(n))
    for u in range(n):
        for v in range(n):
            if u != v and (directed or u < v) and r.random() < 0.45:
                G.add_edge(u, v)
                NG.add_edge(u, v)
    for _ in range(3):
        s, t = r.sample(range(n), 2)
        _assert_same(G, NG, s, t)


@pytest.mark.parametrize("seed", range(12))
@pytest.mark.parametrize("fcls,ncls", _CLASSES)
def test_larger_graphs_every_class(seed, fcls, ncls):
    # Edges in a shuffled insertion order with string labels, parallel
    # edges on the multigraphs, self-loops, and nodes removed afterwards so
    # the storage slots no longer line up with node positions.
    r = random.Random(1000 + seed)
    n = r.randint(20, 45)
    labels = [f"v{r.randrange(10**6)}" for _ in range(n)]
    labels = list(dict.fromkeys(labels))
    edges = [
        (r.choice(labels), r.choice(labels))
        for _ in range(r.randint(2 * n, 5 * n))
    ]
    G, NG = fcls(), ncls()
    G.add_nodes_from(labels)
    NG.add_nodes_from(labels)
    G.add_edges_from(edges)
    NG.add_edges_from(edges)
    for node in r.sample(labels, 3):
        G.remove_node(node)
        NG.remove_node(node)
    nodes = list(NG)
    for _ in range(6):
        s, t = r.choice(nodes), r.choice(nodes)
        _assert_same(G, NG, s, t)


def test_mixed_label_types_keep_networkx_order():
    edges = [(0, "a"), ("a", 2.5), (2.5, (1, 2)), ((1, 2), 0), (0, 2.5),
             ("a", (1, 2)), (True, 0), (True, (1, 2))]
    for fcls, ncls in _CLASSES:
        G, NG = fcls(edges), ncls(edges)
        for s in NG:
            for t in NG:
                _assert_same(G, NG, s, t)


_DISJOINT_APIS = ["edge_disjoint_paths", "node_disjoint_paths"]
_DISJOINT_GRAPH_TYPES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]
_DISJOINT_FLOW_SOLVERS = [
    "edmonds_karp", "shortest_augmenting_path", "preflow_push",
    "dinitz", "boykov_kolmogorov",
]


def _optional_disjoint_pair(graph_type):
    source = ("source",)
    edges = [
        (source, "a"), (source, 3), (source, ("middle",)), (source, "sink"),
        ("a", "sink"), (3, "sink"), (("middle",), "sink"),
        ("a", 3), (3, "a"), (("middle",), "a"), ("a", "a"),
        (source, "dead"), ("dead", "stuck"),
    ]
    graphs = (getattr(fnx, graph_type)(), getattr(nx, graph_type)())
    for graph in graphs:
        graph.add_nodes_from([
            source, "a", 3, ("middle",), "sink", "isolated", "dead", "stuck",
        ])
        graph.add_edges_from(edges)
        if graph.is_multigraph():
            graph.add_edges_from([(source, "a"), (3, "sink")])
    return graphs


def _forbid_disjoint_delegation(*args, **kwargs):
    raise AssertionError("optional disjoint paths must use owned auxiliary flow")


def _block_disjoint_delegation(monkeypatch):
    monkeypatch.setattr(fnx_backend, "_fnx_to_nx", _forbid_disjoint_delegation)
    for name in _DISJOINT_APIS:
        monkeypatch.setattr(nx, name, _forbid_disjoint_delegation)
        monkeypatch.setattr(nx_disjoint, name, _forbid_disjoint_delegation)


@pytest.mark.parametrize("name", _DISJOINT_APIS)
@pytest.mark.parametrize("graph_type", _DISJOINT_GRAPH_TYPES)
@pytest.mark.parametrize("solver_name", _DISJOINT_FLOW_SOLVERS)
@pytest.mark.parametrize("cutoff", [None, 1, 2.5])
def test_owned_disjoint_paths_keep_solver_specific_path_sequence(
    monkeypatch, name, graph_type, solver_name, cutoff
):
    actual, reference = _optional_disjoint_pair(graph_type)
    expected = _outcome(
        getattr(nx, name), reference, ("source",), "sink", cutoff=cutoff,
        flow_func=getattr(nx.algorithms.flow, solver_name),
    )
    _block_disjoint_delegation(monkeypatch)
    assert _outcome(
        getattr(fnx, name), actual, ("source",), "sink", cutoff=cutoff,
        flow_func=getattr(fnx_flow, solver_name),
    ) == expected


@pytest.mark.parametrize("name", _DISJOINT_APIS)
@pytest.mark.parametrize("graph_type", ["DiGraph", "MultiGraph"])
@pytest.mark.parametrize("cutoff", [-1, 0, 0.5, 2.5, 20, float("inf"), float("nan"), "2"])
def test_owned_disjoint_default_cutoff_outcomes(
    monkeypatch, name, graph_type, cutoff
):
    actual, reference = _optional_disjoint_pair(graph_type)
    expected = _outcome(
        getattr(nx, name), reference, ("source",), "sink", cutoff=cutoff
    )
    _block_disjoint_delegation(monkeypatch)
    assert _outcome(
        getattr(fnx, name), actual, ("source",), "sink", cutoff=cutoff
    ) == expected


@pytest.mark.parametrize("name", _DISJOINT_APIS)
@pytest.mark.parametrize("graph_type", _DISJOINT_GRAPH_TYPES)
@pytest.mark.parametrize("callback_name", ["custom", "preflow_push", "shortest_augmenting_path"])
def test_owned_disjoint_callbacks_reuse_auxiliary_residual_and_exact_options(
    monkeypatch, name, graph_type, callback_name
):
    actual, reference = _optional_disjoint_pair(graph_type)
    builder = (
        "build_auxiliary_node_connectivity" if name == "node_disjoint_paths"
        else "build_auxiliary_edge_connectivity"
    )
    auxiliary = getattr(fnx_connectivity, builder)(actual)
    oracle_auxiliary = getattr(nx.algorithms.connectivity, builder)(reference)
    residual = fnx_flow.build_residual_network(auxiliary, "capacity")
    oracle_residual = nx.algorithms.flow.build_residual_network(
        oracle_auxiliary, "capacity"
    )
    marker = object()
    residual.graph["caller_marker"] = marker
    edge_order = list(residual.edges())
    edge = edge_order[0]
    held_attrs = residual[edge[0]][edge[1]]
    actual_calls, expected_calls = [], []

    def actual_solver(graph, source, target, **kwargs):
        actual_calls.append((graph, source, target, dict(kwargs)))
        return fnx_flow.edmonds_karp(graph, source, target, **kwargs)

    def oracle_solver(graph, source, target, **kwargs):
        expected_calls.append((graph, source, target, dict(kwargs)))
        return nx.algorithms.flow.edmonds_karp(graph, source, target, **kwargs)

    actual_solver.__name__ = oracle_solver.__name__ = callback_name
    pairs = [(("source",), "sink"), ("a", "sink"), (3, "sink")]
    expected = [
        _outcome(
            getattr(nx, name), reference, source, target, flow_func=oracle_solver,
            cutoff=2, auxiliary=oracle_auxiliary, residual=oracle_residual,
        )
        for source, target in pairs
    ]
    _block_disjoint_delegation(monkeypatch)
    for (source, target), expected_paths in zip(pairs, expected):
        before = len(actual_calls)
        result = getattr(fnx, name)(
            actual, source, target, flow_func=actual_solver, cutoff=2,
            auxiliary=auxiliary, residual=residual,
        )
        assert len(actual_calls) == before
        assert _outcome(lambda: result) == expected_paths
        assert len(actual_calls) == before + 1
    assert len(actual_calls) == len(expected_calls) == len(pairs)
    for actual_call, expected_call in zip(actual_calls, expected_calls):
        assert actual_call[0] is auxiliary
        assert actual_call[1:3] == expected_call[1:3]
        assert actual_call[3]["residual"] is residual
        assert {k: v for k, v in actual_call[3].items() if k != "residual"} == {
            k: v for k, v in expected_call[3].items() if k != "residual"
        }
    assert residual.graph["caller_marker"] is marker
    assert list(residual.edges()) == edge_order
    assert residual[edge[0]][edge[1]] is held_attrs


@pytest.mark.parametrize("name", _DISJOINT_APIS)
@pytest.mark.parametrize("graph_type", _DISJOINT_GRAPH_TYPES)
@pytest.mark.parametrize("source,target", [
    (("source",), ("source",)), ("isolated", "isolated"),
    (("source",), "isolated"), ("outside", "sink"), (("source",), "outside"),
])
def test_owned_disjoint_optional_endpoint_errors_remain_lazy(
    monkeypatch, name, graph_type, source, target
):
    actual, reference = _optional_disjoint_pair(graph_type)
    expected = _outcome(
        getattr(nx, name), reference, source, target, cutoff=1
    )
    _block_disjoint_delegation(monkeypatch)
    paths = getattr(fnx, name)(actual, source, target, cutoff=1)
    assert iter(paths) is paths
    assert _outcome(lambda: paths) == expected


@pytest.mark.parametrize("damage", ["absent", "none", "empty", "missing_split_node", "missing_id"])
def test_owned_node_disjoint_rejects_invalid_auxiliary_like_oracle(monkeypatch, damage):
    actual, reference = _optional_disjoint_pair("DiGraph")
    auxiliary = fnx_connectivity.build_auxiliary_node_connectivity(actual)
    oracle_auxiliary = nx.algorithms.connectivity.build_auxiliary_node_connectivity(reference)
    for graph in (auxiliary, oracle_auxiliary):
        if damage == "absent":
            del graph.graph["mapping"]
        elif damage == "none":
            graph.graph["mapping"] = None
        elif damage == "empty":
            graph.graph["mapping"] = {}
        elif damage == "missing_split_node":
            graph.graph["mapping"][("source",)] = "missing"
        else:
            index = graph.graph["mapping"][("source",)]
            del graph.nodes[f"{index}B"]["id"]
    expected = _outcome(
        nx.node_disjoint_paths, reference, ("source",), "sink", auxiliary=oracle_auxiliary
    )
    _block_disjoint_delegation(monkeypatch)
    assert _outcome(
        fnx.node_disjoint_paths, actual, ("source",), "sink", auxiliary=auxiliary
    ) == expected


def test_owned_edge_disjoint_custom_residual_cycle_through_source(monkeypatch):
    edges = [
        ("s", "a"), ("a", "b"), ("b", "s"),
        ("s", "t"), ("s", "u"), ("u", "t"),
    ]
    actual, reference = fnx.DiGraph(edges), nx.DiGraph(edges)
    auxiliary = fnx_connectivity.build_auxiliary_edge_connectivity(actual)
    oracle_auxiliary = nx.algorithms.connectivity.build_auxiliary_edge_connectivity(reference)
    residual = fnx_flow.build_residual_network(auxiliary, "capacity")
    oracle_residual = nx.algorithms.flow.build_residual_network(oracle_auxiliary, "capacity")
    for graph in (residual, oracle_residual):
        for _, _, attrs in graph.edges(data=True):
            attrs["flow"] = 0
        for source, target in edges:
            graph[source][target]["flow"] = 1
            graph[target][source]["flow"] = -1
        graph.graph["flow_value"] = 2

    def circulation(graph, source, target, **kwargs):
        return kwargs["residual"]

    expected = _outcome(
        nx.edge_disjoint_paths, reference, "s", "t", flow_func=circulation,
        auxiliary=oracle_auxiliary, residual=oracle_residual,
    )
    assert expected[0] == "ok"
    assert len(expected[1]) == 2
    assert any(path.count("s") > 1 for path in expected[1])
    _block_disjoint_delegation(monkeypatch)
    assert _outcome(
        fnx.edge_disjoint_paths, actual, "s", "t", flow_func=circulation,
        auxiliary=auxiliary, residual=residual,
    ) == expected


