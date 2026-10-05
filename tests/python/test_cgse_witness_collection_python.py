"""``franken_networkx._fnx.cgse.collect_witnesses`` drains CGSE witnesses from Python.

Before this binding the witness ledger was reachable only from Rust integration
tests; the README promised a reproducibility receipt per execution that Python
could not observe. ``collect_witnesses(func)`` runs ``func()`` with the
thread-local ledger armed and returns ``(result, [ComplexityWitness, ...])``.

Only instrumented kernels emit. From the public Python surface that includes
connected components, BFS/DFS edges and trees, Kruskal MST, Bellman-Ford,
SCC enumeration/count for DiGraph/MultiDiGraph, simple-graph and exact-domain
undirected MultiGraph bidirectional Dijkstra,
and unweighted bidirectional BFS on all four graph classes.
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
])
def test_public_witness_hash_is_stable_across_python_hash_seeds(graph_name, route):
    program = """
import json, sys
import franken_networkx as fnx
from franken_networkx._fnx import cgse
graph = getattr(fnx, sys.argv[1])()
graph.add_edges_from([("z", "b", {"weight": 1}), ("z", "a", {"weight": 1}),
                      ("b", "t", {"weight": 1}), ("a", "t", {"weight": 1}),
                      ("t", "z", {"weight": 1})])
route = sys.argv[2]
if route == "strongly_connected_components":
    call = lambda: list(fnx.strongly_connected_components(graph))
else:
    call = lambda: getattr(fnx, route)(graph, "z", "t")
_, witnesses = cgse.collect_witnesses(call)
assert len(witnesses) == 1, witnesses
witness = witnesses[0]
print(json.dumps([witness.n, witness.m, witness.policy.id(), witness.dominant_term,
                  witness.observed_count, witness.decision_path_hash]))
"""
    results = []
    for seed in ("0", "1", "42"):
        env = dict(os.environ, PYTHONHASHSEED=seed)
        completed = subprocess.run(
            [sys.executable, "-c", program, graph_name, route],
            env=env, capture_output=True, text=True, timeout=30, check=False,
        )
        assert completed.returncode == 0, (completed.stdout, completed.stderr)
        results.append(json.loads(completed.stdout))
    assert results[0] == results[1] == results[2]
