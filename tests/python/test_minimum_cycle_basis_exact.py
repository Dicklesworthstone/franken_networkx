"""Minimum-cycle bases with optional dependencies and exact Python weights."""

import builtins
from decimal import Decimal
from fractions import Fraction

import networkx as nx
import pytest

import franken_networkx as fnx


def _as_fnx(graph):
    result = fnx.Graph()
    result.add_nodes_from(graph)
    result.add_edges_from((u, v, dict(data)) for u, v, data in graph.edges(data=True))
    return result


def _reject_call(*args, **kwargs):
    raise AssertionError("unexpected delegated or accelerated cycle-basis search")


@pytest.fixture
def owned_without_scipy(monkeypatch):
    """Exercise the fallback even when a native single-cycle kernel is present."""
    namespace = fnx.minimum_cycle_basis.__globals__
    monkeypatch.setitem(namespace, "_raw_minimum_cycle_basis", None)
    original_import = builtins.__import__

    def import_without_scipy(name, *args, **kwargs):
        if name == "scipy" or name.startswith("scipy."):
            raise ModuleNotFoundError("SciPy is optional")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", import_without_scipy)


def _independent_basis_weight(graph, cycles, weight=None):
    """Check simple cycles and GF(2) independence, returning their total cost."""
    edge_bits = {
        frozenset((u, v)): 1 << position
        for position, (u, v) in enumerate(graph.edges)
    }
    pivots = {}
    total = 0
    for cycle in cycles:
        assert cycle and len(cycle) == len(set(cycle))
        vector = 0
        for u, v in zip(cycle, cycle[1:] + cycle[:1]):
            assert graph.has_edge(u, v), (cycle, u, v)
            vector ^= edge_bits[frozenset((u, v))]
            total += graph[u][v].get(weight, 1)
        while vector:
            pivot = vector.bit_length() - 1
            if pivot not in pivots:
                pivots[pivot] = vector
                break
            vector ^= pivots[pivot]
        assert vector, "returned cycles are linearly dependent"
    dimension = graph.number_of_edges() - len(graph) + nx.number_connected_components(graph)
    assert len(pivots) == dimension
    return total


def _minimum_basis_weight_by_enumeration(graph, weight=None):
    """Independent small-graph oracle: greedy basis of all simple cycles."""
    edge_bits = {
        frozenset((u, v)): 1 << position
        for position, (u, v) in enumerate(graph.edges)
    }
    candidates = []
    for cycle in nx.simple_cycles(graph):
        vector = 0
        cost = 0
        for u, v in zip(cycle, cycle[1:] + cycle[:1]):
            vector ^= edge_bits[frozenset((u, v))]
            cost += graph[u][v].get(weight, 1)
        candidates.append((cost, vector))
    pivots = {}
    total = 0
    for cost, vector in sorted(candidates):
        while vector:
            pivot = vector.bit_length() - 1
            if pivot not in pivots:
                pivots[pivot] = vector
                total += cost
                break
            vector ^= pivots[pivot]
    return total


@pytest.mark.parametrize("seed", range(8))
@pytest.mark.parametrize("weight", [None, "cost"])
def test_cycle_basis_without_scipy_preserves_exact_order(
    owned_without_scipy, monkeypatch, seed, weight
):
    reference = nx.gnp_random_graph(8, 0.35, seed=seed)
    for index, (u, v) in enumerate(reference.edges):
        reference[u][v]["cost"] = (index * 7 + seed) % 11
    expected = nx.minimum_cycle_basis(reference, weight=weight)
    graph = _as_fnx(reference)
    monkeypatch.setattr(nx, "minimum_cycle_basis", _reject_call)
    monkeypatch.setattr(nx.algorithms.cycles, "_min_cycle", _reject_call)

    actual = fnx.minimum_cycle_basis(graph, weight=weight)

    assert actual == expected
    assert _independent_basis_weight(reference, actual, weight) == (
        _minimum_basis_weight_by_enumeration(reference, weight)
    )


@pytest.mark.parametrize(
    "make_weight",
    [
        pytest.param(lambda n: 2**53 + n, id="integers-above-float-precision"),
        pytest.param(lambda n: 10**400 + n, id="integers-above-float-range"),
        pytest.param(lambda n: Fraction(2**53 * 10 + n, 10), id="fractions"),
        pytest.param(lambda n: Decimal(2**53) + Decimal(n) / 10, id="decimals"),
    ],
)
def test_cycle_basis_preserves_exact_weight_domain(owned_without_scipy, make_weight):
    reference = nx.complete_graph(4)
    for (u, v), offset in zip(reference.edges, (1, 3, 4, 2, 6, 5)):
        reference[u][v]["cost"] = make_weight(offset)

    actual = fnx.minimum_cycle_basis(_as_fnx(reference), weight="cost")

    assert actual == nx.minimum_cycle_basis(reference, weight="cost")
    assert _independent_basis_weight(reference, actual, "cost") == (
        _minimum_basis_weight_by_enumeration(reference, "cost")
    )


@pytest.mark.parametrize("weight", [None, "cost"])
def test_cycle_basis_lift_does_not_collide_with_tuple_labels(owned_without_scipy, weight):
    reference = nx.complete_graph([0, (0, 1), ((0, 1), 1), 2])
    for index, (u, v) in enumerate(reference.edges):
        reference[u][v]["cost"] = index + 1

    actual = fnx.minimum_cycle_basis(_as_fnx(reference), weight=weight)

    # NetworkX 3.6's lifted (node, 1) labels collide on this input. Compare
    # against the cycle-space/minimum-cost invariants, not that invalid basis.
    assert _independent_basis_weight(reference, actual, weight) == (
        _minimum_basis_weight_by_enumeration(reference, weight)
    )


def test_cycle_basis_empty_forest_loops_and_disconnected_views(owned_without_scipy):
    for reference in (nx.Graph(), nx.path_graph(5)):
        assert fnx.minimum_cycle_basis(_as_fnx(reference)) == []

    reference, graph = nx.Graph(), fnx.Graph()
    for current in (reference, graph):
        current.add_nodes_from(["hidden", "b", "a", "c", "isolate", "loop", "x", "y", "z"])
        current.add_edges_from(
            [("b", "a"), ("a", "c"), ("c", "b"), ("loop", "loop"),
             ("x", "y"), ("y", "z"), ("z", "x"), ("hidden", "b")]
        )
    visible = set(reference) - {"hidden"}
    graph_view = graph.subgraph(visible)
    reference_view = reference.subgraph(visible)
    assert fnx.minimum_cycle_basis(graph_view) == nx.minimum_cycle_basis(reference_view)


def test_cycle_basis_uses_assigned_logical_storage(owned_without_scipy):
    reference = nx.Graph()
    reference.add_edges_from([(10, 11), (11, 12), (12, 10), (20, 21), (21, 22), (22, 20)])
    graph = fnx.Graph()
    graph.add_edge("stale", "native")
    graph._node = reference._node
    graph._adj = reference._adj

    assert fnx.minimum_cycle_basis(graph) == nx.minimum_cycle_basis(reference)


@pytest.mark.parametrize("weight", [None, 5, ("edge", "cost")])
def test_cycle_basis_nonstring_attribute_keys(owned_without_scipy, weight):
    reference = nx.complete_graph(4)
    for (u, v), value in zip(reference.edges, (9, 2, 1, 8, 3, 7)):
        reference[u][v][None] = value
        reference[u][v][5] = 11 - value
        reference[u][v][("edge", "cost")] = value

    graph = _as_fnx(reference)
    graph.add_edge("hidden", 0, cost=-100)
    filtered = graph.subgraph(reference)
    actual = fnx.minimum_cycle_basis(filtered, weight=weight)

    assert actual == nx.minimum_cycle_basis(reference, weight=weight)
    assert _independent_basis_weight(reference, actual, weight) == (
        _minimum_basis_weight_by_enumeration(reference, weight)
    )


@pytest.mark.parametrize(
    "edges",
    [
        [(0, 1, 1e308), (1, 2, 1e308), (2, 0, 1e308)],
        [(0, 1, 1e308), (1, 2, 1e308), (2, 3, 1e308), (3, 0, 1e308), (0, 2, 1e308)],
        [(0, 1, 1e308), (1, 2, 1e308), (2, 0, 1e308), (3, 4, 1), (4, 5, 1), (5, 3, 1)],
        [(0, 1, 1), (1, 2, 1), (2, 0, 1), (2, 3, 1e308), (3, 4, 1e308), (4, 2, 1e308)],
        [(0, 1, 1e308), (1, 2, 1), (2, 3, 1), (1, 3, 1)],
    ],
    ids=["triangle", "two-cycles", "disconnected", "mixed-cycles", "large-bridge"],
)
def test_public_cycle_basis_keeps_cycles_at_infinite_distance(owned_without_scipy, edges):
    reference = nx.Graph()
    reference.add_weighted_edges_from(edges, weight="cost")
    reference.add_node("isolate")

    actual = fnx.minimum_cycle_basis(_as_fnx(reference), weight="cost")

    assert actual == nx.minimum_cycle_basis(reference, weight="cost")
    _independent_basis_weight(reference, actual, "cost")


@pytest.mark.parametrize("invalid", [-1, "cost", None])
def test_cycle_basis_invalid_or_hidden_weights_match_reference(owned_without_scipy, invalid):
    reference = nx.cycle_graph(3)
    nx.set_edge_attributes(reference, invalid, "cost")
    with pytest.raises(Exception) as expected:
        nx.minimum_cycle_basis(reference, weight="cost")
    with pytest.raises(type(expected.value)) as actual:
        fnx.minimum_cycle_basis(_as_fnx(reference), weight="cost")
    assert actual.value.args == expected.value.args


@pytest.mark.parametrize("kind", ["DiGraph", "MultiGraph", "MultiDiGraph"])
def test_cycle_basis_rejection_precedence_matches_reference(kind):
    with pytest.raises(nx.NetworkXNotImplemented) as expected:
        nx.minimum_cycle_basis(getattr(nx, kind)())
    with pytest.raises(fnx.NetworkXNotImplemented) as actual:
        fnx.minimum_cycle_basis(getattr(fnx, kind)())
    assert actual.value.args == expected.value.args


@pytest.mark.parametrize("loop", [False, True])
@pytest.mark.parametrize("cost", [0, 3])
@pytest.mark.parametrize("strings", [False, True])
def test_cycle_basis_native_single_chord_keeps_order(monkeypatch, loop, cost, strings):
    from franken_networkx import _minimum_cycle_basis as implementation

    namespace = fnx.minimum_cycle_basis.__globals__
    raw = namespace.get("_raw_minimum_cycle_basis")
    if raw is None:
        pytest.skip("native cycle-basis kernel unavailable")
    reference = nx.path_graph(5)
    reference.add_edge(1, 1) if loop else reference.add_edge(1, 4)
    if strings:
        reference = nx.relabel_nodes(reference, lambda node: f"node-{node}")
    nx.set_edge_attributes(reference, cost, "cost")
    calls = []

    def record_native(graph, **kwargs):
        calls.append(graph)
        return raw(graph, **kwargs)

    monkeypatch.setitem(namespace, "_raw_minimum_cycle_basis", record_native)
    monkeypatch.setattr(implementation, "_minimum_cycle_basis_orthogonal_cycle", _reject_call)

    assert fnx.minimum_cycle_basis(_as_fnx(reference), weight="cost") == (
        nx.minimum_cycle_basis(reference, weight="cost")
    )
    assert len(calls) == 1


@pytest.mark.parametrize("cost", [2**53 + 1, Fraction(3, 2), Decimal("1.25")])
def test_cycle_basis_exact_single_chord_avoids_native(monkeypatch, cost):
    namespace = fnx.minimum_cycle_basis.__globals__
    monkeypatch.setitem(namespace, "_raw_minimum_cycle_basis", _reject_call)
    reference = nx.cycle_graph(3)
    nx.set_edge_attributes(reference, cost, "cost")
    assert fnx.minimum_cycle_basis(_as_fnx(reference), weight="cost") == (
        nx.minimum_cycle_basis(reference, weight="cost")
    )


def test_cycle_basis_multiple_chords_avoid_native_order_changes(monkeypatch):
    namespace = fnx.minimum_cycle_basis.__globals__
    monkeypatch.setitem(namespace, "_raw_minimum_cycle_basis", _reject_call)
    reference = nx.gnp_random_graph(8, 0.35, seed=1)
    assert fnx.minimum_cycle_basis(_as_fnx(reference)) == nx.minimum_cycle_basis(reference)


def test_cycle_basis_optional_scipy_batches_keep_zero_cost_ties(monkeypatch):
    pytest.importorskip("scipy")
    namespace = fnx.minimum_cycle_basis.__globals__
    monkeypatch.setitem(namespace, "_raw_minimum_cycle_basis", None)
    reference = nx.cycle_graph(67)
    nx.set_edge_attributes(reference, 0, "cost")
    expected = nx.minimum_cycle_basis(reference, weight="cost")

    # Every start, including starts on both sides of a batch boundary, ties.
    # A zero in a sparse matrix must remain an edge, not disappear as padding.
    assert fnx.minimum_cycle_basis(_as_fnx(reference), weight="cost") == expected
