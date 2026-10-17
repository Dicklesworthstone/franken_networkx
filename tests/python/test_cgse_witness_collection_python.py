"""``franken_networkx._fnx.cgse.collect_witnesses`` drains CGSE witnesses from Python.

Before this binding the witness ledger was reachable only from Rust integration
tests; the README promised a reproducibility receipt per execution that Python
could not observe. ``collect_witnesses(func)`` runs ``func()`` with the
thread-local ledger armed and returns ``(result, [ComplexityWitness, ...])``.

Only instrumented kernels emit. From the public Python surface that includes
connected components, BFS/DFS edges and trees, Kruskal MST, indexed Prim
spanning trees/edges on simple graphs, Bellman-Ford,
SCC enumeration/count for DiGraph/MultiDiGraph, simple-graph and exact-domain
undirected MultiGraph bidirectional Dijkstra,
and unweighted bidirectional BFS on all four graph classes.
Unit-weight dijkstra_path also emits on the four concrete classes; Python-only
weights, private rows, subclasses and the None target sentinel retain Python.
Other parameter/graph-kind routes and reference algorithms still reach sibling
kernels that are not instrumented and yield an empty list;
the planted negative below pins that an un-instrumented call reports nothing
rather than a fabricated witness.
"""

import hashlib
import json
import math
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import franken_networkx as fnx
import networkx as nx
import pytest
from franken_networkx._fnx import cgse


def _log_public_case(case_id, oracle, expected, actual, witness, started, contract_passed):
    """Live public-route evidence, including the extension this process loaded."""
    # Start a new line so pytest's progress dots cannot prefix the JSON record.
    print("\n" + json.dumps({
        "ts": datetime.now(timezone.utc).isoformat(),
        "case_id": case_id,
        "input_sha256": hashlib.sha256(json.dumps(nx.node_link_data(oracle), default=str, sort_keys=True).encode()).hexdigest(),
        "fnx_version": fnx.__version__,
        "nx_version": nx.__version__,
        "so_sha256": hashlib.sha256(Path(fnx._fnx.__file__).read_bytes()).hexdigest(),
        "graph_class": type(oracle).__name__,
        "construction_path": "independent-native-and-networkx-public-constructors",
        "expected": expected,
        "actual": actual,
        "pass": actual == expected and contract_passed,
        "duration_ms": (time.perf_counter() - started) * 1000,
        "policy": witness.policy.id() if witness else None,
        "observed_count": witness.observed_count if witness else None,
        "decision_path_hash": witness.decision_path_hash if witness else None,
    }, default=str, sort_keys=True), flush=True)
    if actual != expected or not contract_passed:
        print("REPRODUCER " + json.dumps({
            "case_id": case_id,
            "graph": nx.node_link_data(oracle),
            "expected": expected,
            "actual": actual,
        }, default=str, sort_keys=True), flush=True)


def _graph():
    G = fnx.Graph()
    G.add_edges_from([(0, 1), (1, 2), (2, 3), (3, 0), (4, 5)])
    G.add_edge(1, 3, weight=2.5)
    G.add_edge(0, 2, weight=0.5)
    return G


@pytest.mark.parametrize("failure", [None, "output", "contract", "missing_witness"])
def test_public_case_logging_reports_failures_before_assertions(capsys, failure):
    graph = _graph()
    oracle = nx.Graph([(0, 1), (1, 2), (2, 3), (3, 0), (4, 5)])
    oracle.add_edge(1, 3, weight=2.5)
    oracle.add_edge(0, 2, weight=0.5)
    result, witnesses = cgse.collect_witnesses(lambda: list(fnx.bfs_edges(graph, 0)))
    expected = [] if failure == "output" else list(nx.bfs_edges(oracle, 0))
    witness = None if failure == "missing_witness" else witnesses[0]
    _log_public_case("logging/bfs", oracle, expected, result, witness,
                     time.perf_counter(), failure not in ("contract", "missing_witness"))
    lines = capsys.readouterr().out.strip().splitlines()
    record = json.loads(lines[0])
    assert record["pass"] == (failure is None), record
    assert record["so_sha256"] == hashlib.sha256(Path(fnx._fnx.__file__).read_bytes()).hexdigest()
    assert len(lines) == (1 if failure is None else 2)
    if failure is not None:
        assert lines[1].startswith("REPRODUCER ")
        reproducer = json.loads(lines[1].removeprefix("REPRODUCER "))
        assert reproducer["case_id"] == "logging/bfs"
        assert reproducer["graph"] == nx.node_link_data(oracle)


def test_result_passes_through_unchanged():
    G = _graph()
    result, witnesses = cgse.collect_witnesses(lambda: list(fnx.bfs_edges(G, 0)))
    assert result == list(fnx.bfs_edges(G, 0))
    assert len(witnesses) == 1


@pytest.mark.parametrize(
    ("call", "policy_id", "dominant_term"),
    [
        (lambda G: list(fnx.connected_components(G)), "lex_min", "n_plus_m"),
        (lambda G: fnx.number_connected_components(G), "lex_min", "n_plus_m"),
        (lambda G: list(fnx.bfs_edges(G, 0)), "insertion_order", "n_plus_m"),
        (lambda G: list(fnx.dfs_edges(G, 0)), "insertion_order", "n_plus_m"),
        (lambda G: fnx.minimum_spanning_tree(G), "weight_then_lex", "m_log_m"),
    ],
)
def test_reference_kernels_emit_one_witness_with_the_registered_policy(
    call, policy_id, dominant_term
):
    G = _graph()
    _, witnesses = cgse.collect_witnesses(lambda: call(G))
    assert len(witnesses) == 1, witnesses
    w = witnesses[0]
    assert isinstance(w, cgse.ComplexityWitness)
    assert (w.n, w.m) == (G.number_of_nodes(), G.number_of_edges())
    assert w.policy.id() == policy_id
    assert w.dominant_term == dominant_term
    assert w.observed_count > 0
    assert len(w.decision_path_hash) == 64  # blake3 hex
    assert int(w.decision_path_hash, 16) != 0


def test_witnesses_are_reproducible_and_input_sensitive():
    G = _graph()
    _, first = cgse.collect_witnesses(lambda: list(fnx.connected_components(G)))
    _, second = cgse.collect_witnesses(lambda: list(fnx.connected_components(G)))
    assert [w.decision_path_hash for w in first] == [w.decision_path_hash for w in second]

    H = _graph()
    H.add_edge(5, 6)
    _, other = cgse.collect_witnesses(lambda: list(fnx.connected_components(H)))
    assert other[0].n == first[0].n + 1
    assert other[0].decision_path_hash != first[0].decision_path_hash


def test_several_calls_inside_one_scope_are_all_collected_in_order():
    G = _graph()

    def workload():
        list(fnx.bfs_edges(G, 0))
        fnx.minimum_spanning_tree(G)
        list(fnx.connected_components(G))
        return "done"

    result, witnesses = cgse.collect_witnesses(workload)
    assert result == "done"
    assert [w.policy.id() for w in witnesses] == [
        "insertion_order",
        "weight_then_lex",
        "lex_min",
    ]


def test_uninstrumented_kernels_emit_nothing():
    """Planted negative: a non-reference algorithm must not fabricate a witness."""
    G = _graph()
    result, witnesses = cgse.collect_witnesses(lambda: fnx.degree_centrality(G))
    assert result == fnx.degree_centrality(G)
    assert witnesses == []


@pytest.mark.parametrize("route", [
    "minimum_spanning_tree", "maximum_spanning_tree",
    "minimum_spanning_edges", "maximum_spanning_edges",
])
@pytest.mark.parametrize("case", [
    "empty", "singleton", "ties", "weighted", "forest", "removed",
    "positive_zero_first", "negative_zero_first",
])
def test_public_prim_witness_and_live_oracle(route, case):
    """The indexed public Prim kernel must report its real FIFO tie policy."""
    graph, oracle = fnx.Graph(), nx.Graph()
    n = 0 if case == "empty" else 1 if case == "singleton" else 6
    edges = [] if n < 2 else [
        (0, 2, {"weight": 1}), (0, 1, {"weight": 1}),
        (2, 3, {"weight": 1}), (1, 3, {"weight": 1}),
        (4, 5, {"weight": 1}), (0, 0, {"weight": -5}),
    ]
    if case == "weighted":
        edges = [(u, v, {"weight": index + 0.5})
                 for index, (u, v, _) in enumerate(edges)]
    elif case in ("positive_zero_first", "negative_zero_first"):
        negative_index = 1 if case == "positive_zero_first" else 0
        edges = [(u, v, {"weight": -0.0 if index == negative_index else 0.0})
                 for index, (u, v, _) in enumerate(edges)]
    elif case == "forest":
        edges = edges[:2]
    for target in (graph, oracle):
        target.add_nodes_from(range(n))
        target.add_edges_from(edges)
        if case == "removed":
            target.remove_node(1)

    def call(module, target):
        result = getattr(module, route)(target, algorithm="prim")
        if route.endswith("tree"):
            return (list(result.nodes(data=True)), list(result.edges(data=True)))
        return list(result)

    expected = call(nx, oracle)
    started = time.perf_counter()
    result, witnesses = cgse.collect_witnesses(lambda: call(fnx, graph))
    uncollected = call(fnx, graph)
    _, repeated = cgse.collect_witnesses(lambda: call(fnx, graph))
    witness = witnesses[0] if len(witnesses) == 1 else None
    # The reference registry still describes the separate lexical Prim kernel.
    # Do not mislabel the public kernel or use that mismatch to weaken its gate.
    contract_passed = (
        witness is not None and len(repeated) == 1 and result == uncollected
        and json.dumps(result) == json.dumps(expected)
        and witness.policy.id() == "weight_then_insertion_order"
        and witness.dominant_term == "m_log_n"
        and (witness.n, witness.m) == (graph.number_of_nodes(), graph.number_of_edges())
        # These cases end on an isolated/tree component, so every queued edge
        # is popped, including stale cycle entries. Self-loops are never queued.
        and witness.observed_count == 2 * sum(u != v for u, v in oracle.edges())
        and witness.verify_complexity_bound()["within_bounds"]
        and witness.decision_path_hash == repeated[0].decision_path_hash
    )
    _log_public_case(f"Graph/{route}/prim/{case}", oracle, expected, result,
                     witness, started, contract_passed)
    assert result == expected
    assert json.dumps(result) == json.dumps(expected)  # retain signed attribute zeros
    assert result == uncollected
    assert len(witnesses) == len(repeated) == 1, witnesses
    assert contract_passed


@pytest.mark.parametrize("route", ["minimum_spanning_edges", "maximum_spanning_edges"])
@pytest.mark.parametrize("ignore_nan", [False, True])
@pytest.mark.parametrize("after_edge", [False, True])
def test_public_prim_nan_witness_preserves_live_exception(route, ignore_nan, after_edge):
    graph, oracle = fnx.Graph(), nx.Graph()
    for target in (graph, oracle):
        target.add_nodes_from(range(3))
        target.add_edge(0, 1, weight=2 if after_edge else float("nan"))
        target.add_edge(1, 2, weight=float("nan") if after_edge else 2)

    def call(module, target):
        try:
            return ("result", list(getattr(module, route)(
                target, algorithm="prim", ignore_nan=ignore_nan)))
        except ValueError as error:
            return ("error", type(error).__name__, str(error))

    expected = call(nx, oracle)
    result, witnesses = cgse.collect_witnesses(lambda: call(fnx, graph))
    assert result == expected
    assert len(witnesses) == 1, witnesses
    witness = witnesses[0]
    assert witness.policy.id() == "weight_then_insertion_order"
    assert witness.dominant_term == "m_log_n"
    assert (witness.n, witness.m) == (3, 2)
    assert witness.observed_count == (2 if ignore_nan or after_edge else 0)
    assert witness.verify_complexity_bound()["within_bounds"]


def test_witnesses_outside_a_scope_are_not_carried_into_the_next_one():
    G = _graph()
    list(fnx.bfs_edges(G, 0))  # outside any scope: not recorded
    _, witnesses = cgse.collect_witnesses(lambda: None)
    assert witnesses == []


def test_exceptions_propagate_unchanged():
    def boom():
        raise ValueError("boom")

    with pytest.raises(ValueError, match="boom"):
        cgse.collect_witnesses(boom)


def test_python_receipt_roundtrip_uses_the_native_bound_checker():
    graph = _graph()
    _, witnesses = cgse.collect_witnesses(lambda: list(fnx.bfs_edges(graph, 0)))
    witness = witnesses[0]
    receipt = witness.to_json()
    restored = cgse.ComplexityWitness.from_json(receipt)
    assert restored.to_json() == receipt
    assert restored.decision_path_hash == witness.decision_path_hash
    expected = {
        "within_bounds": True,
        "observed_count": witness.observed_count,
        "upper_bound": 2 * (witness.n + witness.m),
        "dominant_term": "n_plus_m",
        "formula": f"2 * f({witness.n}, {witness.m})",
    }
    assert restored.verify_complexity_bound() == expected
    assert witness.verify_complexity_bound() == expected

    # A replayed receipt is data, not evidence that a kernel executed. Check
    # the real Rust predicate on a deliberately inflated receipt from Python.
    planted = json.loads(receipt)
    planted["observed_count"] = 2**64 - 1
    inflated = cgse.ComplexityWitness.from_json(json.dumps(planted))
    report = inflated.verify_complexity_bound()
    assert report["within_bounds"] is False, report
    assert report["observed_count"] == 2**64 - 1
    assert report["upper_bound"] == expected["upper_bound"]
    assert witness.verify_complexity_bound() == expected  # no mutation


def test_python_bound_checker_rejects_unknown_complexity_terms():
    _, witnesses = cgse.collect_witnesses(lambda: list(fnx.bfs_edges(_graph(), 0)))
    receipt = json.loads(witnesses[0].to_json())
    receipt["dominant_term"] = "unregistered_term"
    restored = cgse.ComplexityWitness.from_json(json.dumps(receipt))
    with pytest.raises(ValueError, match="unknown complexity term: unregistered_term"):
        restored.verify_complexity_bound()


@pytest.mark.parametrize("corruption", ["syntax", "negative_count", "overflow", "hash_length", "policy"])
def test_python_receipt_decoder_rejects_malformed_witnesses(corruption):
    _, witnesses = cgse.collect_witnesses(lambda: list(fnx.bfs_edges(_graph(), 0)))
    receipt = json.loads(witnesses[0].to_json())
    if corruption == "syntax":
        text = "{"
    else:
        if corruption == "negative_count":
            receipt["observed_count"] = -1
        elif corruption == "overflow":
            receipt["observed_count"] = 2**64
        elif corruption == "hash_length":
            receipt["decision_path_blake3"] = [0] * 31
        elif corruption == "policy":
            receipt["policy"] = "unregistered_policy"
        text = json.dumps(receipt)
    with pytest.raises(ValueError):
        cgse.ComplexityWitness.from_json(text)


@pytest.mark.parametrize("graph_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("route", ["shortest_path", "bidirectional_shortest_path"])
@pytest.mark.parametrize("case", ["diamond", "dense", "self", "disconnected", "removed", "parallel"])
def test_public_unweighted_bidirectional_bfs_witness_and_live_oracle(graph_name, route, case):
    graph = getattr(fnx, graph_name)()
    oracle = getattr(nx, graph_name)()
    n = 18 if case == "dense" else 7
    edges = [(0, 2), (0, 1), (2, 3), (1, 3), (3, 4), (4, 5)]
    if case == "dense":
        edges = [(u, v) for u in range(n - 1) for v in range(n - 1) if u != v]
    elif case == "parallel":
        edges += [(0, 2), (0, 2), (2, 2)]
    for target in (graph, oracle):
        target.add_nodes_from(range(n))
        target.add_edges_from(edges)
        if case == "removed":
            target.remove_node(1)
    destination = 0 if case == "self" else n - 1 if case == "disconnected" else 5

    def call(module, target):
        try:
            return getattr(module, route)(target, 0, destination)
        except nx.NetworkXNoPath as error:
            return type(error), str(error)

    expected = call(nx, oracle)
    started = time.perf_counter()
    result, witnesses = cgse.collect_witnesses(lambda: call(fnx, graph))
    _, repeated = cgse.collect_witnesses(lambda: call(fnx, graph))
    registered = cgse.policy_registry()["bfs"]
    witness = witnesses[0] if len(witnesses) == 1 else None
    contract_passed = (
        witness is not None and len(repeated) == 1
        and witness.policy.id() == registered["policy"]
        and witness.dominant_term == registered["dominant_complexity"]
        and (witness.n, witness.m) == (oracle.number_of_nodes(), oracle.number_of_edges())
        and witness.verify_complexity_bound()["within_bounds"]
        and (case == "self" or witness.observed_count > 0)
        and witness.decision_path_hash == repeated[0].decision_path_hash
    )
    _log_public_case(f"{graph_name}/{route}/{case}", oracle, expected, result, witness, started, contract_passed)
    assert result == expected
    assert len(witnesses) == len(repeated) == 1, witnesses
    assert witness.policy.id() == registered["policy"]
    assert witness.dominant_term == registered["dominant_complexity"]
    assert (witness.n, witness.m) == (oracle.number_of_nodes(), oracle.number_of_edges())
    assert witness.verify_complexity_bound()["within_bounds"]
    if case != "self":
        assert witness.observed_count > 0
    assert witness.decision_path_hash == repeated[0].decision_path_hash


@pytest.mark.parametrize("graph_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("case", ["fifo", "self", "disconnected", "removed", "parallel", "ignored_attrs", "karate"])
def test_public_unweighted_dijkstra_path_witness_and_live_oracle(graph_name, case):
    graph = getattr(fnx, graph_name)()
    oracle = getattr(nx, graph_name)()
    karate_edges = list(nx.karate_club_graph().edges(data=True)) if case == "karate" else None
    for target in (graph, oracle):
        target.add_nodes_from(range(34 if case == "karate" else 6))
        # The target row sees 1 before 2, but the source frontier sees 2 first.
        # Bidirectional BFS picks [0, 1, 3]; unit-weight Dijkstra picks [0, 2, 3].
        target.add_edges_from(karate_edges if case == "karate" else [(0, 2), (0, 1), (1, 3), (2, 3)])
        if case == "removed":
            target.remove_node(1)
        elif case == "parallel":
            target.add_edges_from([(0, 2), (0, 2), (2, 2)])
        elif case == "ignored_attrs":
            for _, _, attrs in target.edges(data=True):
                attrs.update(weight=float("nan"), cost=object())
    destination = 0 if case == "self" else 5 if case == "disconnected" else 33 if case == "karate" else 3

    def call(module, target):
        try:
            return module.dijkstra_path(target, 0, destination, weight=None)
        except nx.NetworkXNoPath as error:
            return type(error), str(error)

    expected = call(nx, oracle)
    if case == "fifo":
        assert expected == [0, 2, 3]
        assert nx.bidirectional_shortest_path(oracle, 0, destination) == [0, 1, 3]
    started = time.perf_counter()
    result, witnesses = cgse.collect_witnesses(lambda: call(fnx, graph))
    _, repeated = cgse.collect_witnesses(lambda: call(fnx, graph))
    registered = cgse.policy_registry()["dijkstra"]
    witness = witnesses[0] if len(witnesses) == 1 else None
    contract_passed = (
        witness is not None and len(repeated) == 1
        and witness.policy.id() == registered["policy"]
        and witness.dominant_term == registered["dominant_complexity"]
        and (witness.n, witness.m) == (oracle.number_of_nodes(), oracle.number_of_edges())
        and witness.verify_complexity_bound()["within_bounds"]
        and (witness.observed_count == 0 if case == "self" else witness.observed_count > 0)
        and witness.decision_path_hash == repeated[0].decision_path_hash
    )
    _log_public_case(f"{graph_name}/dijkstra_path/None/{case}", oracle, expected, result,
                     witness, started, contract_passed)
    assert result == expected
    assert contract_passed, witnesses


@pytest.mark.parametrize("graph_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("none_weight", [10, None, "invalid"])
def test_public_unweighted_dijkstra_path_none_key_preserves_python_weights(graph_name, none_weight):
    graph = getattr(fnx, graph_name)()
    oracle = getattr(nx, graph_name)()
    for target in (graph, oracle):
        target.add_edges_from([(0, 2), (0, 1), (1, 3), (2, 3)])
        attrs = target[0][2][0] if target.is_multigraph() else target[0][2]
        attrs[None] = none_weight

    def call(module, target):
        try:
            return module.dijkstra_path(target, 0, 3, weight=None)
        except (TypeError, nx.NetworkXNoPath) as error:
            return type(error), str(error)

    result, witnesses = cgse.collect_witnesses(lambda: call(fnx, graph))
    assert result == call(nx, oracle)
    assert witnesses == [], "Declined Python-weight routes must not invent a native witness"
    assert cgse.collect_witnesses(lambda: fnx.dijkstra_path(graph, 0, 0, weight=None))[0] == [0]


@pytest.mark.parametrize("graph_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("source,target", [(False, 3.0), (False, 0.0), (99, 3), (0, 99), ([], 3), (0, [])])
def test_public_unweighted_dijkstra_path_endpoint_contract(graph_name, source, target):
    graph = getattr(fnx, graph_name)()
    oracle = getattr(nx, graph_name)()
    for subject in (graph, oracle):
        subject.add_edges_from([(0, 2.0), (2, 3)])

    def call(module, subject):
        try:
            return module.dijkstra_path(subject, source, target, weight=None)
        except (TypeError, nx.NodeNotFound, nx.NetworkXNoPath) as error:
            return type(error), str(error)

    actual = call(fnx, graph)
    expected = call(nx, oracle)
    assert actual == expected
    if isinstance(actual, list):
        assert actual[-1] is target
        if len(actual) > 1:
            assert actual[0] is source
            assert type(actual[1]) is type(expected[1])


_PRIVATE_POINT_QUERY_ROUTES = [
    ("dijkstra_path", None),
    ("dijkstra_path_length", None),
    ("bidirectional_dijkstra", None),
    ("bellman_ford_path", None),
    ("bellman_ford_path_length", None),
    ("shortest_path", "dijkstra"),
    ("shortest_path", "bellman-ford"),
    ("shortest_path_length", "dijkstra"),
    ("shortest_path_length", "bellman-ford"),
]


@pytest.mark.parametrize("graph_name,view", [
    (graph_name, view)
    for graph_name in ("Graph", "DiGraph", "MultiGraph", "MultiDiGraph")
    for view in ("plain", "subgraph", "restricted", "conversion", "edge_subgraph")
] + [("DiGraph", "reverse"), ("MultiDiGraph", "reverse")])
@pytest.mark.parametrize("weight", [None, "weight", "cost"])
@pytest.mark.parametrize("route,method", _PRIVATE_POINT_QUERY_ROUTES)
def test_public_point_query_private_root_rows_before_coercion(graph_name, view, weight, route, method):
    graph = getattr(fnx, graph_name)()
    oracle = getattr(nx, graph_name)()
    for subject in (graph, oracle):
        subject.add_nodes_from(range(4))
        subject.add_edges_from([(0, 1), (1, 3)])  # stale native route
        edge_attrs = {"weight": 2, "cost": 3}
        other_attrs = {"weight": 4, "cost": 5}
        edge = {0: edge_attrs} if subject.is_multigraph() else edge_attrs
        other = {0: other_attrs} if subject.is_multigraph() else other_attrs
        rows = {0: {2: edge}, 1: {}, 2: {3: other}, 3: {}}
        if subject.is_directed():
            subject._succ = rows
            subject._pred = {0: {}, 1: {}, 2: {0: edge}, 3: {2: other}}
        else:
            rows[2][0] = edge
            rows[3][2] = other
        subject._adj = rows
    if view == "subgraph":
        graph, oracle = graph.subgraph(range(4)), oracle.subgraph(range(4))
    elif view == "restricted":
        graph = fnx.restricted_view(graph, [], [])
        oracle = nx.restricted_view(oracle, [], [])
    elif view == "conversion":
        graph = graph.to_undirected(as_view=True) if graph.is_directed() else graph.to_directed(as_view=True)
        oracle = oracle.to_undirected(as_view=True) if oracle.is_directed() else oracle.to_directed(as_view=True)
    elif view == "edge_subgraph":
        selected_edges = [(0, 2, 0), (2, 3, 0)] if graph.is_multigraph() else [(0, 2), (2, 3)]
        graph, oracle = graph.edge_subgraph(selected_edges), oracle.edge_subgraph(selected_edges)
    elif view == "reverse":
        graph, oracle = graph.reverse(copy=False), oracle.reverse(copy=False)
    kwargs = {"weight": weight}
    if method is not None:
        kwargs["method"] = method
    source, target = (3, 0) if view == "reverse" else (0, 3)
    result, witnesses = cgse.collect_witnesses(lambda: getattr(fnx, route)(graph, source, target, **kwargs))
    distance = 2 if weight is None else 6 if weight == "weight" else 8
    expected_path = [3, 2, 0] if view == "reverse" else [0, 2, 3]
    if route in ("dijkstra_path", "shortest_path", "bellman_ford_path"):
        expected = expected_path
    elif route == "bidirectional_dijkstra":
        expected = (distance, expected_path)
    else:
        expected = distance
    assert result == getattr(nx, route)(oracle, source, target, **kwargs) == expected
    if route == "bidirectional_dijkstra":
        assert type(result[0]) is int
    elif route.endswith("length"):
        assert type(result) is int
    assert witnesses == [], "Authoritative Python rows must not be replaced by stale native storage"


@pytest.mark.parametrize("graph_name", ["MultiGraph", "MultiDiGraph"])
def test_public_point_query_private_root_multigraph_edge_subgraph_requires_keys(graph_name):
    errors = []
    for module in (fnx, nx):
        graph = getattr(module, graph_name)()
        graph.add_edges_from([(0, 2), (2, 3)])
        with pytest.raises(ValueError, match=r"\(expected 3, got 2\)") as error:
            graph.edge_subgraph([(0, 2), (2, 3)])
        errors.append(str(error.value))
    assert errors[0] == errors[1]


@pytest.mark.parametrize("graph_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("route,method", _PRIVATE_POINT_QUERY_ROUTES)
@pytest.mark.parametrize("case", [
    "self", "missing_source", "missing_target", "no_path",
    "unhashable_source", "unhashable_target", "callable", "float",
    "invalid", "negative_cycle",
])
def test_public_point_query_private_root_domain_contract(graph_name, route, method, case):
    graph = getattr(fnx, graph_name)()
    oracle = getattr(nx, graph_name)()
    for subject in (graph, oracle):
        subject.add_nodes_from(range(4))
        subject.add_edges_from([(0, 1), (1, 3)])
        edge_attrs = {"weight": 2, "cost": 3}
        other_attrs = {"weight": 4, "cost": 5}
        if case == "float":
            edge_attrs["weight"] = 2.5
        elif case == "invalid":
            edge_attrs["weight"] = "invalid"
        elif case == "negative_cycle":
            other_attrs["weight"] = -4
        edge = {0: edge_attrs} if subject.is_multigraph() else edge_attrs
        other = {0: other_attrs} if subject.is_multigraph() else other_attrs
        rows = {0: {2: edge}, 1: {}, 2: {3: other}, 3: {}}
        if subject.is_directed():
            predecessors = {0: {}, 1: {}, 2: {0: edge}, 3: {2: other}}
            if case == "negative_cycle":
                rows[3][2] = other
                predecessors[2][3] = other
            subject._succ = rows
            subject._pred = predecessors
        else:
            rows[2][0] = edge
            rows[3][2] = other
        subject._adj = rows

    source, target = {
        "self": (0, 0), "missing_source": (99, 3),
        "missing_target": (0, 99), "no_path": (0, 1),
        "unhashable_source": ([], 3), "unhashable_target": (0, []),
    }.get(case, (0, 3))

    def call(module, subject):
        weight = "weight"
        if case == "callable":
            if subject.is_multigraph():
                weight = lambda u, v, data: min(attrs["cost"] for attrs in data.values())
            else:
                weight = lambda u, v, data: data["cost"]
        kwargs = {"weight": weight}
        if method is not None:
            kwargs["method"] = method
        try:
            result = getattr(module, route)(subject, source, target, **kwargs)
        except Exception as error:
            return "error", type(error), str(error)
        result_type = type(result[0]) if route == "bidirectional_dijkstra" else type(result)
        return "ok", result, result_type

    expected = call(nx, oracle)
    result, witnesses = cgse.collect_witnesses(lambda: call(fnx, graph))
    assert result == expected
    assert witnesses == [], "Python row traversal must not fabricate a native receipt"


_PRIVATE_SOURCE_DIJKSTRA_ROUTES = [
    "single_source_dijkstra",
    "single_source_dijkstra_path",
    "single_source_dijkstra_path_length",
]


def _private_source_dijkstra_graph(module, graph_name, first=2, second=4):
    graph = getattr(module, graph_name)()
    graph.add_nodes_from(range(4))
    graph.add_edges_from([(0, 1), (1, 3)])
    first_attrs = {"weight": first, "cost": 3}
    second_attrs = {"weight": second, "cost": 5}
    edge = {0: first_attrs} if graph.is_multigraph() else first_attrs
    other = {0: second_attrs} if graph.is_multigraph() else second_attrs
    rows = {0: {2: edge}, 1: {}, 2: {3: other}, 3: {}}
    if graph.is_directed():
        graph._succ = rows
        graph._pred = {0: {}, 1: {}, 2: {0: edge}, 3: {2: other}}
    else:
        rows[2][0] = edge
        rows[3][2] = other
    graph._adj = rows
    return graph


@pytest.mark.parametrize("graph_name,view", [
    (graph_name, view)
    for graph_name in ("Graph", "DiGraph", "MultiGraph", "MultiDiGraph")
    for view in ("plain", "subgraph", "restricted", "conversion", "edge_subgraph")
] + [("DiGraph", "reverse"), ("MultiDiGraph", "reverse")])
@pytest.mark.parametrize("weight", [None, "weight", "cost"])
@pytest.mark.parametrize("cutoff", [None, 1, 5])
@pytest.mark.parametrize("route", _PRIVATE_SOURCE_DIJKSTRA_ROUTES)
def test_public_source_dijkstra_private_root_before_coercion(graph_name, view, weight, cutoff, route):
    graph = _private_source_dijkstra_graph(fnx, graph_name)
    oracle = _private_source_dijkstra_graph(nx, graph_name)
    if view == "subgraph":
        graph, oracle = graph.subgraph(range(4)), oracle.subgraph(range(4))
    elif view == "restricted":
        graph, oracle = fnx.restricted_view(graph, [], []), nx.restricted_view(oracle, [], [])
    elif view == "conversion":
        graph = graph.to_undirected(as_view=True) if graph.is_directed() else graph.to_directed(as_view=True)
        oracle = oracle.to_undirected(as_view=True) if oracle.is_directed() else oracle.to_directed(as_view=True)
    elif view == "edge_subgraph":
        edges = [(0, 2, 0), (2, 3, 0)] if graph.is_multigraph() else [(0, 2), (2, 3)]
        graph, oracle = graph.edge_subgraph(edges), oracle.edge_subgraph(edges)
    elif view == "reverse":
        graph, oracle = graph.reverse(copy=False), oracle.reverse(copy=False)
    nodes = [3, 2, 0] if view == "reverse" else [0, 2, 3]
    increments = [1, 1] if weight is None else [2, 4] if weight == "weight" else [3, 5]
    if view == "reverse":
        increments.reverse()
    distances = {nodes[0]: 0}
    paths = {nodes[0]: [nodes[0]]}
    for index, distance in enumerate((increments[0], sum(increments)), 1):
        if cutoff is None or distance <= cutoff:
            distances[nodes[index]] = distance
            paths[nodes[index]] = nodes[:index + 1]
    kwargs = {"cutoff": cutoff, "weight": weight}
    actual, witnesses = cgse.collect_witnesses(lambda: getattr(fnx, route)(graph, nodes[0], **kwargs))
    expected = getattr(nx, route)(oracle, nodes[0], **kwargs)
    if route == "single_source_dijkstra":
        assert [list(row.items()) for row in actual] == [list(row.items()) for row in expected]
        assert list(actual[0].items()) == list(distances.items())
        assert list(actual[1].items()) == list(paths.items())
        actual_distances = actual[0]
    else:
        literal = paths if route.endswith("path") else distances
        assert list(actual.items()) == list(expected.items()) == list(literal.items())
        actual_distances = None if route.endswith("path") else actual
    if actual_distances is not None:
        assert all(type(value) is int for value in actual_distances.values())
    assert witnesses == [], "Private rows cannot produce a native-storage witness"


@pytest.mark.parametrize("graph_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("route", _PRIVATE_SOURCE_DIJKSTRA_ROUTES)
@pytest.mark.parametrize("case", [
    "missing_source", "unhashable_source", "float", "exact_int",
    "callable", "hidden", "invalid", "negative_cycle",
])
def test_public_source_dijkstra_private_root_domain_contract(graph_name, route, case):
    first = {"float": 2.5, "exact_int": 10**30, "invalid": "invalid"}.get(case, 2)
    graph = _private_source_dijkstra_graph(fnx, graph_name, first)
    oracle = _private_source_dijkstra_graph(nx, graph_name, first)
    if case == "negative_cycle":
        for subject in (graph, oracle):
            attrs = {"weight": -8}
            edge = {0: attrs} if subject.is_multigraph() else attrs
            subject._adj[3][2] = edge
            if subject.is_directed():
                subject._pred[2][3] = edge
    source = {"missing_source": 99, "unhashable_source": []}.get(case, 0)

    def call(module, subject):
        weight = "weight"
        if case == "callable":
            weight = (lambda u, v, data: min(attrs["cost"] for attrs in data.values())) if subject.is_multigraph() else (lambda u, v, data: data["cost"])
        elif case == "hidden":
            weight = lambda u, v, data: None if v == 3 else 2
        try:
            result = getattr(module, route)(subject, source, weight=weight)
        except Exception as error:
            return "error", type(error), str(error)
        if route == "single_source_dijkstra":
            return "ok", [(key, type(value), value) for key, value in result[0].items()], list(result[1].items())
        return "ok", [(key, type(value), value) for key, value in result.items()]

    actual, witnesses = cgse.collect_witnesses(lambda: call(fnx, graph))
    assert actual == call(nx, oracle)
    assert witnesses == []


@pytest.mark.parametrize("graph_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("target,cutoff", [(3, None), (3, 5), (0, -1), (1, None), (99, None), ([], None), (3.0, None)])
def test_public_source_dijkstra_private_root_target_contract(graph_name, target, cutoff):
    def call(module):
        subject = _private_source_dijkstra_graph(module, graph_name)
        try:
            result = module.single_source_dijkstra(subject, 0, target=target, cutoff=cutoff)
        except Exception as error:
            return "error", type(error), str(error)
        assert result[1][-1] is target
        return "ok", type(result[0]), result

    actual, witnesses = cgse.collect_witnesses(lambda: call(fnx))
    assert actual == call(nx)
    assert witnesses == []


@pytest.mark.parametrize("graph_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("route", _PRIVATE_SOURCE_DIJKSTRA_ROUTES)
def test_public_source_dijkstra_private_root_unhashable_source_also_matches_native_graph(graph_name, route):
    errors = []
    for module in (fnx, nx):
        graph = getattr(module, graph_name)([(0, 1), (1, 3)])
        with pytest.raises(TypeError) as error:
            getattr(module, route)(graph, [])
        errors.append(str(error.value))
    assert errors[0] == errors[1]


_PRIVATE_SOURCE_BELLMAN_ROUTES = [
    "single_source_bellman_ford",
    "single_source_bellman_ford_path",
    "single_source_bellman_ford_path_length",
]


@pytest.mark.parametrize("graph_name,view", [
    (graph_name, view)
    for graph_name in ("Graph", "DiGraph", "MultiGraph", "MultiDiGraph")
    for view in ("plain", "subgraph", "restricted", "conversion", "edge_subgraph")
] + [("DiGraph", "reverse"), ("MultiDiGraph", "reverse")])
@pytest.mark.parametrize("weight", [None, "weight", "cost"])
@pytest.mark.parametrize("route", _PRIVATE_SOURCE_BELLMAN_ROUTES)
def test_public_source_bellman_private_root_before_coercion(graph_name, view, weight, route):
    graph = _private_source_dijkstra_graph(fnx, graph_name)
    oracle = _private_source_dijkstra_graph(nx, graph_name)
    if view == "subgraph":
        graph, oracle = graph.subgraph(range(4)), oracle.subgraph(range(4))
    elif view == "restricted":
        graph, oracle = fnx.restricted_view(graph, [], []), nx.restricted_view(oracle, [], [])
    elif view == "conversion":
        graph = graph.to_undirected(as_view=True) if graph.is_directed() else graph.to_directed(as_view=True)
        oracle = oracle.to_undirected(as_view=True) if oracle.is_directed() else oracle.to_directed(as_view=True)
    elif view == "edge_subgraph":
        edges = [(0, 2, 0), (2, 3, 0)] if graph.is_multigraph() else [(0, 2), (2, 3)]
        graph, oracle = graph.edge_subgraph(edges), oracle.edge_subgraph(edges)
    elif view == "reverse":
        graph, oracle = graph.reverse(copy=False), oracle.reverse(copy=False)
    nodes = [3, 2, 0] if view == "reverse" else [0, 2, 3]
    increments = [1, 1] if weight is None else [2, 4] if weight == "weight" else [3, 5]
    if view == "reverse":
        increments.reverse()
    distances = {nodes[0]: 0, nodes[1]: increments[0], nodes[2]: sum(increments)}
    paths = {node: nodes[:index + 1] for index, node in enumerate(nodes)}
    actual, witnesses = cgse.collect_witnesses(lambda: getattr(fnx, route)(graph, nodes[0], weight=weight))
    expected = getattr(nx, route)(oracle, nodes[0], weight=weight)
    if route == "single_source_bellman_ford":
        assert [list(row.items()) for row in actual] == [list(row.items()) for row in expected]
        assert list(actual[0].items()) == list(distances.items())
        assert list(actual[1].items()) == list(paths.items())
        actual_distances = actual[0]
    else:
        literal = paths if route.endswith("path") else distances
        assert list(actual.items()) == list(expected.items()) == list(literal.items())
        actual_distances = None if route.endswith("path") else actual
    if actual_distances is not None:
        assert all(type(value) is int for value in actual_distances.values())
    assert witnesses == [], "Private rows cannot produce a native-storage witness"


@pytest.mark.parametrize("graph_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("route", _PRIVATE_SOURCE_BELLMAN_ROUTES)
@pytest.mark.parametrize("case", [
    "missing_source", "unhashable_source", "float", "exact_int", "callable",
    "hidden", "invalid", "negative_edge", "negative_cycle", "unreachable_negative_cycle",
])
def test_public_source_bellman_private_root_domain_contract(graph_name, route, case):
    first = {"float": 2.5, "exact_int": 10**30, "invalid": "invalid", "negative_edge": -2}.get(case, 2)
    graph = _private_source_dijkstra_graph(fnx, graph_name, first)
    oracle = _private_source_dijkstra_graph(nx, graph_name, first)
    if case in ("negative_cycle", "unreachable_negative_cycle"):
        u, v = (3, 2) if case == "negative_cycle" else (1, 1)
        for subject in (graph, oracle):
            attrs = {"weight": -8}
            edge = {0: attrs} if subject.is_multigraph() else attrs
            subject._adj[u][v] = edge
            if subject.is_directed():
                subject._pred[v][u] = edge
    source = {"missing_source": 99, "unhashable_source": []}.get(case, 0)

    def call(module, subject):
        weight = "weight"
        if case == "callable":
            weight = (lambda u, v, data: min(attrs["cost"] for attrs in data.values())) if subject.is_multigraph() else (lambda u, v, data: data["cost"])
        elif case == "hidden":
            weight = lambda u, v, data: None if v == 3 else 2
        try:
            result = getattr(module, route)(subject, source, weight=weight)
        except Exception as error:
            return "error", type(error), str(error)
        if route == "single_source_bellman_ford":
            return "ok", [(key, type(value), value) for key, value in result[0].items()], list(result[1].items())
        return "ok", [(key, type(value), value) for key, value in result.items()]

    actual, witnesses = cgse.collect_witnesses(lambda: call(fnx, graph))
    assert actual == call(nx, oracle)
    assert witnesses == []


@pytest.mark.parametrize("graph_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("source,target", [(0, 3), (0, 0), (0, 1), (0, 99), (0, []), (99, 99), ([], []), (0, 3.0)])
def test_public_source_bellman_private_root_target_contract(graph_name, source, target):
    def call(module):
        subject = _private_source_dijkstra_graph(module, graph_name)
        try:
            result = module.single_source_bellman_ford(subject, source, target=target)
        except Exception as error:
            return "error", type(error), str(error)
        # The self-target branch keeps source identity, not target identity.
        if source != target:
            assert result[1][-1] is target
        return "ok", type(result[0]), result

    actual, witnesses = cgse.collect_witnesses(lambda: call(fnx))
    assert actual == call(nx)
    assert witnesses == []


@pytest.mark.parametrize("graph_name,view", [
    (graph_name, view)
    for graph_name in ("Graph", "DiGraph", "MultiGraph", "MultiDiGraph")
    for view in ("plain", "subgraph", "restricted", "conversion", "edge_subgraph")
] + [("DiGraph", "reverse"), ("MultiDiGraph", "reverse")])
@pytest.mark.parametrize("route", ["single_source_shortest_path", "single_source_shortest_path_length"])
@pytest.mark.parametrize("cutoff", [None, -1, 1, 1.5])
def test_public_source_unweighted_private_root_identity_and_cutoff(graph_name, view, route, cutoff):
    graph = _private_source_dijkstra_graph(fnx, graph_name)
    oracle = _private_source_dijkstra_graph(nx, graph_name)
    # Use the same discovery aliases in both real graphs. Native copies
    # canonicalize these equal-to-int objects; authoritative rows must not.
    aliases = [float(node) for node in range(4)]
    for subject in (graph, oracle):
        for node, neighbors in list(subject._adj.items()):
            subject._adj[node] = {aliases[neighbor]: attrs for neighbor, attrs in neighbors.items()}
        if subject.is_directed():
            for node, neighbors in list(subject._pred.items()):
                subject._pred[node] = {aliases[neighbor]: attrs for neighbor, attrs in neighbors.items()}
    if view == "subgraph":
        graph, oracle = graph.subgraph(range(4)), oracle.subgraph(range(4))
    elif view == "restricted":
        graph, oracle = fnx.restricted_view(graph, [], []), nx.restricted_view(oracle, [], [])
    elif view == "conversion":
        graph = graph.to_undirected(as_view=True) if graph.is_directed() else graph.to_directed(as_view=True)
        oracle = oracle.to_undirected(as_view=True) if oracle.is_directed() else oracle.to_directed(as_view=True)
    elif view == "edge_subgraph":
        edges = [(0, 2, 0), (2, 3, 0)] if graph.is_multigraph() else [(0, 2), (2, 3)]
        graph, oracle = graph.edge_subgraph(edges), oracle.edge_subgraph(edges)
    elif view == "reverse":
        graph, oracle = graph.reverse(copy=False), oracle.reverse(copy=False)
    nodes = [3, 2, 0] if view == "reverse" else [0, 2, 3]
    # NetworkX admits a whole BFS level while cutoff > the previous level.
    # Thus cutoff=1.5 admits depth 2; it is not a distance <= cutoff filter.
    reached = [node for depth, node in enumerate(nodes) if depth == 0 or cutoff is None or cutoff > depth - 1]
    literal = {node: nodes[:depth + 1] if route.endswith("path") else depth for depth, node in enumerate(reached)}
    actual, witnesses = cgse.collect_witnesses(lambda: getattr(fnx, route)(graph, nodes[0], cutoff=cutoff))
    expected = getattr(nx, route)(oracle, nodes[0], cutoff=cutoff)
    assert list(actual.items()) == list(expected.items()) == list(literal.items())
    assert all(a is e for a, e in zip(actual, expected))
    if route.endswith("path"):
        for node in expected:
            assert all(a is e for a, e in zip(actual[node], expected[node]))
        assert len({id(path) for path in actual.values()}) == len(actual)
    else:
        assert all(type(length) is int for length in actual.values())
    assert witnesses == [], "Private row traversal cannot fabricate a native witness"


@pytest.mark.parametrize("graph_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("route", ["single_source_shortest_path", "single_source_shortest_path_length"])
@pytest.mark.parametrize("view", ["subgraph", "restricted"])
@pytest.mark.parametrize("case", ["unhashable_source", "invalid_cutoff"])
def test_public_source_unweighted_private_root_error_contract(graph_name, route, view, case):
    def call(module):
        subject = _private_source_dijkstra_graph(module, graph_name)
        subject = subject.subgraph(range(4)) if view == "subgraph" else module.restricted_view(subject, [], [])
        source = [] if case == "unhashable_source" else 0
        cutoff = "invalid" if case == "invalid_cutoff" else None
        try:
            result = getattr(module, route)(subject, source, cutoff=cutoff)
        except Exception as error:
            return "error", type(error), str(error)
        return "ok", list(result.items())

    actual, witnesses = cgse.collect_witnesses(lambda: call(fnx))
    expected = call(nx)
    assert expected[0] == "error"
    assert actual == expected
    assert witnesses == []


@pytest.mark.parametrize("graph_name,view", [
    (graph_name, view)
    for graph_name in ("Graph", "DiGraph", "MultiGraph", "MultiDiGraph")
    for view in ("plain", "subgraph", "restricted", "conversion", "edge_subgraph")
] + [("DiGraph", "reverse"), ("MultiDiGraph", "reverse")])
@pytest.mark.parametrize("route", ["shortest_path", "shortest_path_length"])
@pytest.mark.parametrize("query", ["source", "target"])
@pytest.mark.parametrize("weight", [None, "weight", "cost"])
@pytest.mark.parametrize("method", ["dijkstra", "bellman-ford"])
def test_public_generic_private_root_single_endpoint_before_coercion(graph_name, view, route, query, weight, method):
    graph = _private_source_dijkstra_graph(fnx, graph_name)
    oracle = _private_source_dijkstra_graph(nx, graph_name)
    if view == "subgraph":
        graph, oracle = graph.subgraph(range(4)), oracle.subgraph(range(4))
    elif view == "restricted":
        graph, oracle = fnx.restricted_view(graph, [], []), nx.restricted_view(oracle, [], [])
    elif view == "conversion":
        graph = graph.to_undirected(as_view=True) if graph.is_directed() else graph.to_directed(as_view=True)
        oracle = oracle.to_undirected(as_view=True) if oracle.is_directed() else oracle.to_directed(as_view=True)
    elif view == "edge_subgraph":
        edges = [(0, 2, 0), (2, 3, 0)] if graph.is_multigraph() else [(0, 2), (2, 3)]
        graph, oracle = graph.edge_subgraph(edges), oracle.edge_subgraph(edges)
    elif view == "reverse":
        graph, oracle = graph.reverse(copy=False), oracle.reverse(copy=False)
    nodes = [3, 2, 0] if view == "reverse" else [0, 2, 3]
    increments = [1, 1] if weight is None else [2, 4] if weight == "weight" else [3, 5]
    if view == "reverse":
        increments.reverse()
    endpoint = nodes[0] if query == "source" else nodes[-1]
    if query == "target":
        nodes.reverse()
        increments.reverse()
    distances = {nodes[0]: 0, nodes[1]: increments[0], nodes[2]: sum(increments)}
    paths = {node: nodes[:index + 1] if query == "source" else list(reversed(nodes[:index + 1])) for index, node in enumerate(nodes)}
    kwargs = {query: endpoint, "weight": weight, "method": method}
    actual, witnesses = cgse.collect_witnesses(lambda: getattr(fnx, route)(graph, **kwargs))
    expected = getattr(nx, route)(oracle, **kwargs)
    literal = paths if route == "shortest_path" else distances
    assert list(actual.items()) == list(expected.items()) == list(literal.items())
    if route == "shortest_path_length":
        assert all(type(distance) is int for distance in actual.values())
    assert witnesses == [], "Generic private-row queries must not fabricate a native witness"


@pytest.mark.parametrize("graph_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("route", ["shortest_path", "shortest_path_length"])
@pytest.mark.parametrize("query", ["source", "target"])
@pytest.mark.parametrize("case", ["missing_endpoint", "unhashable_endpoint", "invalid_method"])
def test_public_generic_private_root_single_endpoint_error_precedence(graph_name, route, query, case):
    def call(module):
        subject = _private_source_dijkstra_graph(module, graph_name).subgraph(range(4))
        endpoint = [] if case == "unhashable_endpoint" else 99
        kwargs = {query: endpoint, "weight": "weight", "method": "invalid" if case == "invalid_method" else "dijkstra"}
        try:
            result = getattr(module, route)(subject, **kwargs)
        except Exception as error:
            return "error", type(error), str(error)
        return "ok", list(result.items())

    actual, witnesses = cgse.collect_witnesses(lambda: call(fnx))
    expected = call(nx)
    assert expected[0] == "error"
    assert actual == expected
    assert witnesses == []


@pytest.mark.parametrize("graph_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("reachable", [False, True])
def test_public_unweighted_dijkstra_path_custom_none_key_checks_only_reached_rows(graph_name, reachable):
    class NoneKey:
        def __hash__(self):
            return hash(None)

        def __eq__(self, other):
            if other is None:
                assert reachable, "Admission must not compare keys of unreachable edges"
                return True
            return self is other

    graph = getattr(fnx, graph_name)()
    oracle = getattr(nx, graph_name)()
    for subject in (graph, oracle):
        subject.add_edges_from([(0, 2), (0, 1), (1, 3), (2, 3), (4, 5)])
        u, v = (0, 2) if reachable else (4, 5)
        attrs = subject[u][v][0] if subject.is_multigraph() else subject[u][v]
        attrs[NoneKey()] = 10
    result, witnesses = cgse.collect_witnesses(lambda: fnx.dijkstra_path(graph, 0, 3, weight=None))
    assert result == nx.dijkstra_path(oracle, 0, 3, weight=None)
    assert result == ([0, 1, 3] if reachable else [0, 2, 3])
    assert witnesses == []


@pytest.mark.parametrize("graph_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
def test_public_unweighted_dijkstra_path_none_target_retains_source_wide_result(graph_name):
    graph = getattr(fnx, graph_name)([(0, 2), (0, 1), (1, 3), (2, 3)])
    oracle = getattr(nx, graph_name)([(0, 2), (0, 1), (1, 3), (2, 3)])
    actual, witnesses = cgse.collect_witnesses(lambda: fnx.dijkstra_path(graph, 0, None, weight=None))
    expected = nx.dijkstra_path(oracle, 0, None, weight=None)
    assert list(actual.items()) == list(expected.items())
    assert witnesses == []


@pytest.mark.parametrize("graph_name", ["MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("case", ["empty_reached", "empty_unreached", "held_nonempty"])
def test_public_unweighted_dijkstra_path_live_keydict_contract(graph_name, case):
    graph = getattr(fnx, graph_name)()
    oracle = getattr(nx, graph_name)()
    for subject in (graph, oracle):
        subject.add_edges_from([(0, 2), (0, 1), (1, 3), (2, 3), (4, 5)])
        u, v = (4, 5) if case == "empty_unreached" else (0, 2)
        row = subject.get_edge_data(u, v)
        if case != "held_nonempty":
            row.clear()  # Leaves the pair in adjacency with no parallel keys.

    def call(module, subject):
        try:
            return module.dijkstra_path(subject, 0, 3, weight=None)
        except ValueError as error:
            return type(error), str(error)

    actual, witnesses = cgse.collect_witnesses(lambda: call(fnx, graph))
    assert actual == call(nx, oracle)
    assert len(witnesses) == (1 if case == "held_nonempty" else 0)
    if case == "held_nonempty":
        assert witnesses[0].verify_complexity_bound()["within_bounds"]


@pytest.mark.parametrize("graph_name", ["Graph", "DiGraph"])
@pytest.mark.parametrize("route", ["shortest_path", "bidirectional_dijkstra"])
@pytest.mark.parametrize("weight", ["weight", "cost"])
@pytest.mark.parametrize("case", ["weighted", "equal", "self", "disconnected"])
def test_public_bidirectional_dijkstra_witness_and_live_oracle(graph_name, route, weight, case):
    graph = getattr(fnx, graph_name)()
    oracle = getattr(nx, graph_name)()
    edges = [(0, 2, 1), (0, 1, 1), (2, 3, 1), (1, 3, 1 if case == "equal" else 5)]
    for target in (graph, oracle):
        target.add_nodes_from(range(5))
        target.add_edges_from((u, v, {weight: value}) for u, v, value in edges)
    destination = 0 if case == "self" else 4 if case == "disconnected" else 3

    def call(module, target):
        try:
            return getattr(module, route)(target, 0, destination, weight=weight)
        except nx.NetworkXNoPath as error:
            # Catch inside the collection scope so the failed search's real
            # witness can also be checked; exception type/message stay exact.
            return type(error), str(error)

    expected = call(nx, oracle)
    started = time.perf_counter()
    result, witnesses = cgse.collect_witnesses(lambda: call(fnx, graph))
    registered = cgse.policy_registry()["dijkstra"]
    _, repeated = cgse.collect_witnesses(lambda: call(fnx, graph))
    witness = witnesses[0] if len(witnesses) == 1 else None
    contract_passed = (
        witness is not None and len(repeated) == 1
        and witness.policy.id() == registered["policy"]
        and witness.dominant_term == registered["dominant_complexity"]
        and (witness.n, witness.m) == (5, 4)
        and witness.observed_count <= 2 * (5 + 4 * math.ceil(math.log2(5)))
        and (case == "self" or witness.observed_count > 0)
        and witness.decision_path_hash == repeated[0].decision_path_hash
    )
    _log_public_case(f"{graph_name}/{route}/{weight}/{case}", oracle, expected, result, witness, started, contract_passed)
    assert result == expected
    assert len(witnesses) == 1, witnesses
    witness = witnesses[0]
    assert witness.policy.id() == registered["policy"]
    assert witness.dominant_term == registered["dominant_complexity"]
    assert (witness.n, witness.m) == (5, 4)
    upper = 2 * (witness.n + witness.m * math.ceil(math.log2(witness.n)))
    assert witness.observed_count <= upper
    if case != "self":
        assert witness.observed_count > 0
    assert witness.decision_path_hash == repeated[0].decision_path_hash


@pytest.mark.parametrize("route", ["shortest_path", "bidirectional_dijkstra"])
@pytest.mark.parametrize("weight", ["weight", "cost"])
@pytest.mark.parametrize("case", ["parallel", "equal", "float", "default", "self", "disconnected", "removed", "dense"])
def test_public_multigraph_bidirectional_dijkstra_witness_and_live_oracle(route, weight, case):
    graph = fnx.MultiGraph()
    oracle = nx.MultiGraph()
    n = 18 if case == "dense" else 7
    edges = [(0, 2, 1), (0, 1, 1), (2, 3, 1), (1, 3, 1), (3, 4, 1), (4, 5, 1)]
    if case == "dense":
        edges = [(u, v, 1) for u in range(n - 1) for v in range(u + 1, n - 1)]
    elif case == "float":
        edges[0] = (0, 2, 0.5)
    for target in (graph, oracle):
        target.add_nodes_from(range(n))
        target.add_edges_from((u, v, {} if case == "default" else {weight: value})
                              for u, v, value in edges)
        if case in ("parallel", "dense"):
            target.add_edge(0, 2, **{weight: 9})
            target.add_edge(0, 2, **{weight: 0.5})
            target.add_edge(2, 2, **{weight: 0})
        if case == "removed":
            target.remove_node(1)
    destination = 0 if case == "self" else n - 1 if case == "disconnected" else 5

    def call(module, target):
        try:
            return getattr(module, route)(target, 0, destination, weight=weight)
        except nx.NetworkXNoPath as error:
            return type(error), str(error)

    expected = call(nx, oracle)
    started = time.perf_counter()
    result, witnesses = cgse.collect_witnesses(lambda: call(fnx, graph))
    _, repeated = cgse.collect_witnesses(lambda: call(fnx, graph))
    witness = witnesses[0] if len(witnesses) == 1 else None
    registered = cgse.policy_registry()["dijkstra"]
    contract_passed = (
        witness is not None and len(repeated) == 1
        and witness.policy.id() == registered["policy"]
        and witness.dominant_term == registered["dominant_complexity"]
        and (witness.n, witness.m) == (oracle.number_of_nodes(), oracle.number_of_edges())
        and witness.verify_complexity_bound()["within_bounds"]
        and (witness.observed_count == 0 if case == "self" else witness.observed_count > 0)
        and witness.decision_path_hash == repeated[0].decision_path_hash
    )
    _log_public_case(f"MultiGraph/{route}/{weight}/{case}", oracle, expected, result,
                     witness, started, contract_passed)
    assert result == expected
    if route == "bidirectional_dijkstra" and case != "disconnected":
        assert type(result[0]) is type(expected[0])  # integer/float length is observable
    assert len(witnesses) == len(repeated) == 1, witnesses
    assert witness.policy.id() == registered["policy"]
    assert witness.dominant_term == registered["dominant_complexity"]
    assert (witness.n, witness.m) == (oracle.number_of_nodes(), oracle.number_of_edges())
    assert witness.verify_complexity_bound()["within_bounds"]
    assert witness.observed_count == 0 if case == "self" else witness.observed_count > 0
    assert witness.decision_path_hash == repeated[0].decision_path_hash
    assert call(fnx, graph) == expected  # scratch reuse/collection must not change the path


@pytest.mark.parametrize("native_scan", [True, False])
@pytest.mark.parametrize("route", ["shortest_path", "bidirectional_dijkstra"])
@pytest.mark.parametrize("labels", ["integers", "wide_integers", "strings_and_integers"])
def test_public_multigraph_integer_labels_use_native_witness(route, labels, native_scan, monkeypatch):
    nodes = [0, 1, 2, 3]
    if labels == "wide_integers":
        nodes = [2**100 + i for i in nodes]
    elif labels == "strings_and_integers":
        nodes = ["s", 1, "b", 3]
    graph, oracle = fnx.MultiGraph(), nx.MultiGraph()
    for target in (graph, oracle):
        target.add_nodes_from(nodes)
        for u, v in [(0, 2), (0, 1), (2, 3), (1, 3)]:
            target.add_edge(nodes[u], nodes[v], weight=1)
        target.add_edge(nodes[0], nodes[2], weight=9)
    if not native_scan:
        monkeypatch.setattr(fnx, "_native_check_dijkstra_weights_fast", None)

    def call(module, target):
        return getattr(module, route)(target, nodes[0], nodes[3], weight="weight")

    expected = call(nx, oracle)
    started = time.perf_counter()
    result, witnesses = cgse.collect_witnesses(lambda: call(fnx, graph))
    _, repeated = cgse.collect_witnesses(lambda: call(fnx, graph))
    registered = cgse.policy_registry()["dijkstra"]
    witness = witnesses[0] if len(witnesses) == 1 else None
    valid = (witness is not None and len(repeated) == 1
             and witness.policy.id() == registered["policy"]
             and witness.dominant_term == registered["dominant_complexity"]
             and (witness.n, witness.m) == (4, 5)
             and witness.observed_count > 0
             and witness.verify_complexity_bound()["within_bounds"]
             and witness.decision_path_hash == repeated[0].decision_path_hash)
    _log_public_case(f"MultiGraph/{route}/{labels}/native_scan={native_scan}",
                     oracle, expected, result, witness, started, valid)
    assert result == expected
    actual_path = result[1] if route == "bidirectional_dijkstra" else result
    expected_path = expected[1] if route == "bidirectional_dijkstra" else expected
    assert [type(node) for node in actual_path] == [type(node) for node in expected_path]
    assert valid, witnesses


@pytest.mark.parametrize("native_scan", [True, False])
@pytest.mark.parametrize("route", ["shortest_path", "bidirectional_dijkstra"])
@pytest.mark.parametrize("case", ["large_int", "sum_envelope", "fraction", "decimal",
                                 "negative", "inf", "nan", "nonnumeric", "mixed_rows",
                                 "bool_endpoint", "float_endpoint", "str_subclass_endpoint",
                                 "int_subclass_endpoint", "callable"])
def test_public_multigraph_inexact_domains_keep_python_authority(route, case, native_scan, monkeypatch):
    from decimal import Decimal
    from fractions import Fraction

    class StringNode(str):
        pass

    class IntegerNode(int):
        pass

    graph, oracle = fnx.MultiGraph(), nx.MultiGraph()
    source, target = 0, 2
    value = {"large_int": 2**60 + 1, "sum_envelope": 2**52 + 1,
             "fraction": Fraction(1, 3), "decimal": Decimal("0.1"),
             "negative": -1, "inf": float("inf"), "nan": float("nan"),
             "nonnumeric": "heavy"}.get(case, 1)
    for current in (graph, oracle):
        if case == "mixed_rows":
            # All global node objects are exact ints: only the adjacency-row
            # override reveals that native graph-global rendering is unsafe.
            current.add_nodes_from([0, 1, 2])
            current.add_edge(0, 1.0, weight=1)
            current.add_edge(1, 2, weight=1)
        elif case == "str_subclass_endpoint":
            current.add_edge("s", "m", weight=1)
            current.add_edge("m", "t", weight=1)
        else:
            current.add_edge(0, 1, weight=value)
            current.add_edge(1, 2, weight=value if case == "sum_envelope" else 1)
    if case == "bool_endpoint":
        source = False
    elif case == "float_endpoint":
        source = 0.0
    elif case == "str_subclass_endpoint":
        source, target = StringNode("s"), "t"
    elif case == "int_subclass_endpoint":
        source = IntegerNode(0)
    weight = (lambda u, v, data: min(attrs.get("weight", 1) for attrs in data.values())) if case == "callable" else "weight"
    if not native_scan:
        monkeypatch.setattr(fnx, "_native_check_dijkstra_weights_fast", None)

    def call(module, current):
        try:
            result = getattr(module, route)(current, source, target, weight=weight)
        except (TypeError, ValueError, nx.NetworkXException) as error:
            return "exception", type(error).__qualname__, str(error)
        path = result[1] if route == "bidirectional_dijkstra" else result
        typed_path = [(type(node).__qualname__, repr(node)) for node in path]
        # repr preserves finite floats, arbitrary ints, custom numerics and NaN;
        # unlike ==, it can also compare two independently produced NaN values.
        return (type(result[0]).__qualname__, repr(result[0]), typed_path) if route == "bidirectional_dijkstra" else typed_path

    expected = call(nx, oracle)
    started = time.perf_counter()
    result, witnesses = cgse.collect_witnesses(lambda: call(fnx, graph))
    _log_public_case(f"MultiGraph/{route}/fallback/{case}/native_scan={native_scan}",
                     oracle, expected, result, None, started, not witnesses)
    assert result == expected
    assert witnesses == []  # no native receipt may be fabricated for Python traversal


@pytest.mark.parametrize("graph_name", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("route", ["strongly_connected_components", "number_strongly_connected_components"])
@pytest.mark.parametrize("case", ["empty", "singleton", "cycle", "components", "parallel", "removed", "sparse", "edgeless"])
def test_public_scc_witness_and_live_oracle(graph_name, route, case):
    graph = getattr(fnx, graph_name)()
    oracle = getattr(nx, graph_name)()
    n = 0 if case == "empty" else 1 if case == "singleton" else 6 if case == "cycle" else 40 if case == "sparse" else 12 if case == "edgeless" else 8
    edges = []
    if case == "cycle":
        edges = [(i, (i + 1) % n) for i in range(n)]
    elif case == "sparse":
        edges = [(i, i + 1) for i in range(n - 1)]
    elif case in ("components", "parallel", "removed"):
        edges = [(0, 1), (1, 0), (1, 4), (4, 5), (5, 4), (5, 6), (6, 7), (7, 6)]
        if case == "parallel":
            edges += [(0, 1), (0, 1), (4, 4)]
    for target in (graph, oracle):
        target.add_nodes_from(range(n))
        target.add_edges_from(edges)
        if case == "removed":
            target.remove_nodes_from([2, 3])

    def call(module, target):
        result = getattr(module, route)(target)
        # Preserve component order AND each Python set's iteration order.
        return [list(component) for component in result] if route == "strongly_connected_components" else result

    expected = call(nx, oracle)
    started = time.perf_counter()
    result, witnesses = cgse.collect_witnesses(lambda: call(fnx, graph))
    uncollected = call(fnx, graph)
    registered = cgse.policy_registry()["strongly_connected_components"]
    _, repeated = cgse.collect_witnesses(lambda: call(fnx, graph))
    witness = witnesses[0] if len(witnesses) == 1 else None
    contract_passed = (
        witness is not None and len(repeated) == 1 and result == uncollected
        and witness.policy.id() == registered["policy"]
        and witness.dominant_term == registered["dominant_complexity"]
        and (witness.n, witness.m) == (oracle.number_of_nodes(), oracle.number_of_edges())
        and witness.observed_count <= 2 * (witness.n + witness.m)
        and (witness.observed_count > 0) == (n > 0)
        and witness.decision_path_hash == repeated[0].decision_path_hash
    )
    _log_public_case(f"{graph_name}/{route}/{case}", oracle, expected, result, witness, started, contract_passed)
    assert result == expected
    assert result == uncollected  # collection must not alter the route
    assert len(witnesses) == 1, witnesses
    witness = witnesses[0]
    assert witness.policy.id() == registered["policy"]
    assert witness.dominant_term == registered["dominant_complexity"]
    assert (witness.n, witness.m) == (oracle.number_of_nodes(), oracle.number_of_edges())
    assert witness.observed_count <= 2 * (witness.n + witness.m)
    assert (witness.observed_count > 0) == (n > 0)
    assert witness.decision_path_hash == repeated[0].decision_path_hash


@pytest.mark.parametrize("graph_name,route", [
    ("Graph", "bidirectional_dijkstra"),
    ("DiGraph", "bidirectional_dijkstra"),
    ("MultiGraph", "bidirectional_dijkstra"),
    ("DiGraph", "strongly_connected_components"),
    ("MultiDiGraph", "strongly_connected_components"),
    ("Graph", "bidirectional_shortest_path"),
    ("DiGraph", "bidirectional_shortest_path"),
    ("MultiGraph", "bidirectional_shortest_path"),
    ("MultiDiGraph", "bidirectional_shortest_path"),
    ("Graph", "dijkstra_path"),
    ("DiGraph", "dijkstra_path"),
    ("MultiGraph", "dijkstra_path"),
    ("MultiDiGraph", "dijkstra_path"),
    ("Graph", "minimum_spanning_tree"),
    ("Graph", "maximum_spanning_tree"),
    ("Graph", "minimum_spanning_edges"),
    ("Graph", "maximum_spanning_edges"),
])
def test_public_witness_hash_is_stable_across_python_hash_seeds(graph_name, route):
    program = """
import hashlib, importlib.util, json, sys
from pathlib import Path
library = Path(sys.argv[3]).resolve()
shim = Path(sys.argv[5]).resolve()
sys.path.insert(0, str(shim.parent.parent))
spec = importlib.util.spec_from_file_location('franken_networkx._fnx', library)
native = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = native
spec.loader.exec_module(native)
import franken_networkx as fnx
from franken_networkx._fnx import cgse
assert Path(fnx._fnx.__file__).resolve() == library
assert hashlib.sha256(library.read_bytes()).hexdigest() == sys.argv[4]
assert Path(fnx.__file__).resolve() == shim
assert hashlib.sha256(shim.read_bytes()).hexdigest() == sys.argv[6]
graph = getattr(fnx, sys.argv[1])()
route = sys.argv[2]
if route.endswith(("spanning_tree", "spanning_edges")):
    # CPython's integer set order is hash-seed independent. String-root Prim
    # traces may legitimately differ across seeds to preserve NetworkX order.
    graph.add_edges_from([(0, 2, {"weight": 1}), (0, 1, {"weight": 1}),
                          (2, 3, {"weight": 1}), (1, 3, {"weight": 1})])
    call = lambda: list(getattr(fnx, route)(graph, algorithm="prim"))
else:
    graph.add_edges_from([("z", "b", {"weight": 1}), ("z", "a", {"weight": 1}),
                          ("b", "t", {"weight": 1}), ("a", "t", {"weight": 1}),
                          ("t", "z", {"weight": 1})])
if route == "strongly_connected_components":
    call = lambda: list(fnx.strongly_connected_components(graph))
elif route == "dijkstra_path":
    call = lambda: fnx.dijkstra_path(graph, "z", "t", weight=None)
elif not route.endswith(("spanning_tree", "spanning_edges")):
    call = lambda: getattr(fnx, route)(graph, "z", "t")
_, witnesses = cgse.collect_witnesses(call)
assert len(witnesses) == 1, witnesses
witness = witnesses[0]
print(json.dumps([witness.n, witness.m, witness.policy.id(), witness.dominant_term,
                  witness.observed_count, witness.decision_path_hash]))
assert hashlib.sha256(library.read_bytes()).hexdigest() == sys.argv[4]
assert hashlib.sha256(shim.read_bytes()).hexdigest() == sys.argv[6]
"""
    results = []
    for seed in ("0", "1", "42"):
        env = dict(os.environ, PYTHONHASHSEED=seed)
        completed = subprocess.run(
            [sys.executable, "-c", program, graph_name, route,
             str(Path(fnx._fnx.__file__).resolve()),
             hashlib.sha256(Path(fnx._fnx.__file__).read_bytes()).hexdigest(),
             str(Path(fnx.__file__).resolve()),
             hashlib.sha256(Path(fnx.__file__).read_bytes()).hexdigest()],
            env=env, capture_output=True, text=True, timeout=30, check=False,
        )
        assert completed.returncode == 0, (completed.stdout, completed.stderr)
        results.append(json.loads(completed.stdout))
    assert results[0] == results[1] == results[2]


@pytest.mark.parametrize("route,registry_key", [
    ("max_weight_matching", "max_weight_matching"),
    ("min_weight_matching", "min_weight_matching"),
])
@pytest.mark.parametrize("maxcardinality", [False, True])
def test_public_matching_witness_and_live_oracle(route, registry_key, maxcardinality):
    graph, oracle = fnx.Graph(), nx.Graph()
    edges = [
        (0, 1, {"weight": 4.0}),
        (1, 2, {"weight": 5.0}),
        (2, 3, {"weight": 3.0}),
        (3, 0, {"weight": 2.0}),
        (0, 2, {"weight": 6.0}),
    ]
    for target in (graph, oracle):
        target.add_nodes_from(range(4))
        target.add_edges_from(edges)

    def call(module, target):
        if route == "min_weight_matching":
            return module.min_weight_matching(target, weight="weight")
        return module.max_weight_matching(target, maxcardinality=maxcardinality, weight="weight")

    expected = call(nx, oracle)
    started = time.perf_counter()
    result, witnesses = cgse.collect_witnesses(lambda: call(fnx, graph))
    _, repeated = cgse.collect_witnesses(lambda: call(fnx, graph))
    registered = cgse.policy_registry()[registry_key]
    witness = witnesses[0] if len(witnesses) == 1 else None
    contract_passed = (
        witness is not None
        and len(repeated) == 1
        and result == expected
        and witness.policy.id() == registered["policy"]
        and witness.dominant_term == registered["dominant_complexity"]
        and (witness.n, witness.m) == (oracle.number_of_nodes(), oracle.number_of_edges())
        and witness.observed_count > 0
        and witness.verify_complexity_bound()["within_bounds"]
        and witness.decision_path_hash == repeated[0].decision_path_hash
    )
    _log_public_case(
        f"Graph/{route}/maxcard={maxcardinality}",
        oracle,
        sorted(expected),
        sorted(result),
        witness,
        started,
        contract_passed,
    )
    assert result == expected
    assert contract_passed, witnesses


@pytest.mark.parametrize("graph_name", ["Graph", "DiGraph"])
def test_public_eulerian_circuit_witness_and_live_oracle(graph_name):
    graph = getattr(fnx, graph_name)()
    oracle = getattr(nx, graph_name)()
    edges = [(0, 1), (1, 2), (2, 3), (3, 0), (0, 2), (2, 1), (1, 3), (3, 2), (2, 0)]
    if graph_name == "Graph":
        edges = [(0, 1), (1, 2), (2, 0), (0, 3), (3, 4), (4, 0)]
    for target in (graph, oracle):
        target.add_nodes_from(range(5 if graph_name == "Graph" else 4))
        target.add_edges_from(edges)

    expected = list(nx.eulerian_circuit(oracle, source=0))
    started = time.perf_counter()
    result, witnesses = cgse.collect_witnesses(lambda: list(fnx.eulerian_circuit(graph, source=0)))
    _, repeated = cgse.collect_witnesses(lambda: list(fnx.eulerian_circuit(graph, source=0)))
    registered = cgse.policy_registry()["eulerian_circuit"]
    witness = witnesses[0] if len(witnesses) == 1 else None
    contract_passed = (
        witness is not None
        and len(repeated) == 1
        and result == expected
        and witness.policy.id() == registered["policy"]
        and witness.dominant_term == registered["dominant_complexity"]
        and (witness.n, witness.m) == (oracle.number_of_nodes(), oracle.number_of_edges())
        and witness.observed_count > 0
        and witness.verify_complexity_bound()["within_bounds"]
        and witness.decision_path_hash == repeated[0].decision_path_hash
    )
    _log_public_case(
        f"{graph_name}/eulerian_circuit",
        oracle,
        expected,
        result,
        witness,
        started,
        contract_passed,
    )
    assert result == expected
    assert contract_passed, witnesses


def test_all_12_v1_policy_registry_reference_algorithms_emit_public_witnesses():
    """Every entry in cgse.policy_registry() (all 12 reference algorithms) must emit a
    valid ComplexityWitness from its public Python API surface."""
    registry = cgse.policy_registry()
    assert len(registry) == 12

    g = fnx.Graph()
    g.add_edges_from([
        (0, 1, {"weight": 2.0}),
        (1, 2, {"weight": 3.0}),
        (2, 0, {"weight": 1.5}),
    ])
    dg = fnx.DiGraph()
    dg.add_edges_from([
        (0, 1, {"weight": 2.0}),
        (1, 2, {"weight": 3.0}),
        (2, 0, {"weight": 1.5}),
    ])
    dag = fnx.DiGraph([(0, 1), (1, 2), (0, 2)])

    calls = {
        "dijkstra": lambda: fnx.dijkstra_path(g, 0, 2),
        "bellman_ford": lambda: fnx.bellman_ford_path(g, 0, 2),
        "bfs": lambda: list(fnx.bfs_edges(g, 0)),
        "dfs": lambda: list(fnx.dfs_edges(g, 0)),
        "max_weight_matching": lambda: fnx.max_weight_matching(g),
        "min_weight_matching": lambda: fnx.min_weight_matching(g),
        "connected_components": lambda: list(fnx.connected_components(g)),
        "strongly_connected_components": lambda: list(fnx.strongly_connected_components(dg)),
        "kruskal": lambda: fnx.minimum_spanning_tree(g, algorithm="kruskal"),
        "prim": lambda: fnx.minimum_spanning_tree(g, algorithm="prim"),
        "eulerian_circuit": lambda: list(fnx.eulerian_circuit(dg, source=0)),
        "topological_sort": lambda: list(fnx.topological_sort(dag)),
    }
    assert set(calls) == set(registry)
    for algo_name, fn in calls.items():
        _, witnesses = cgse.collect_witnesses(fn)
        assert len(witnesses) >= 1, f"{algo_name} emitted no witnesses"
        for w in witnesses:
            assert w.verify_complexity_bound()["within_bounds"], (algo_name, w)

