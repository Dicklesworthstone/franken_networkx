"""Exact numeric domains and solver hooks for global cuts and cut trees."""

from decimal import Decimal
from fractions import Fraction
from itertools import combinations

import networkx as nx
import pytest

import franken_networkx as fnx
from franken_networkx import _fnx


EXACT_CAPACITIES = [
    2**53 + 1,
    2**63 + 7,
    10**400,
    Fraction(1, 3),
    Decimal("0.3"),
    2.0**-500,
]


def _graphs(edges, key):
    reference, actual = nx.Graph(), fnx.Graph()
    for graph in (reference, actual):
        for u, v, value in edges:
            graph.add_edge(u, v)
            graph[u][v][key] = value
    return reference, actual


def _tree_weights(tree):
    return {
        frozenset((u, v)): data["weight"]
        for u, v, data in tree.edges(data=True)
    }


@pytest.mark.parametrize("capacity", EXACT_CAPACITIES)
def test_single_edge_cut_values_keep_exact_type(capacity):
    reference, actual = _graphs([("left", "right", capacity)], "amount")
    expected_cut = nx.stoer_wagner(reference, weight="amount")
    actual_cut = fnx.stoer_wagner(actual, weight="amount")
    assert actual_cut == expected_cut
    assert type(actual_cut[0]) is type(expected_cut[0])

    expected_tree = nx.gomory_hu_tree(reference, capacity="amount")
    actual_tree = fnx.gomory_hu_tree(actual, capacity="amount")
    assert _tree_weights(actual_tree) == _tree_weights(expected_tree)
    assert type(actual_tree["left"]["right"]["weight"]) is type(
        expected_tree["left"]["right"]["weight"]
    )


@pytest.mark.parametrize("scale", [2**53 + 1, Fraction(1, 7), Decimal("0.125")])
def test_cut_tree_encodes_every_pairwise_minimum_cut(scale):
    edges = [
        ("root", 1, 3 * scale),
        (1, ("leaf",), 5 * scale),
        (("leaf",), "end", 4 * scale),
        ("root", "end", 2 * scale),
        ("root", ("leaf",), scale),
    ]
    reference, actual = _graphs(edges, "capacity")
    expected = nx.gomory_hu_tree(reference)
    tree = fnx.gomory_hu_tree(actual)
    assert _tree_weights(tree) == _tree_weights(expected)
    assert list(tree) == list(reference)
    for source, target in combinations(reference, 2):
        path = nx.shortest_path(expected, source, target)
        represented = min(
            tree[u][v]["weight"] for u, v in zip(path, path[1:])
        )
        assert represented == nx.minimum_cut_value(reference, source, target)


@pytest.mark.parametrize("key", [0, ("capacity",)])
def test_non_string_attribute_keys_keep_exact_values(key):
    reference, actual = _graphs([(0, 1, 2**53 + 1), (1, 2, 2**53 + 3)], key)
    assert fnx.stoer_wagner(actual, weight=key) == nx.stoer_wagner(
        reference, weight=key
    )
    assert _tree_weights(fnx.gomory_hu_tree(actual, capacity=key)) == _tree_weights(
        nx.gomory_hu_tree(reference, capacity=key)
    )


def test_custom_flow_solver_is_called_with_one_reused_residual(monkeypatch):
    reference, actual = _graphs(
        [(0, 1, 3), (1, 2, 5), (2, 3, 4), (0, 3, 2), (0, 2, 1)],
        "capacity",
    )
    expected = nx.gomory_hu_tree(reference)
    calls = []

    def flow_solver(graph, source, target, capacity, residual=None, **kwargs):
        calls.append((source, target, residual))
        return nx.algorithms.flow.edmonds_karp(
            graph,
            source,
            target,
            capacity=capacity,
            residual=residual,
            **kwargs,
        )

    def reject_whole_algorithm(*args, **kwargs):
        raise AssertionError("cut-tree construction must remain local")

    monkeypatch.setattr(nx, "gomory_hu_tree", reject_whole_algorithm)
    tree = fnx.gomory_hu_tree(actual, flow_func=flow_solver)
    assert _tree_weights(tree) == _tree_weights(expected)
    assert len(calls) == len(actual) - 1
    assert calls[0][2] is not None
    assert all(residual is calls[0][2] for _, _, residual in calls)


def test_custom_stoer_wagner_heap_is_used():
    reference, actual = _graphs([(0, 1, 3), (1, 2, 5), (0, 2, 2)], "weight")
    calls = []

    class RecordingHeap(nx.utils.BinaryHeap):
        def __init__(self, *args, **kwargs):
            calls.append(True)
            super().__init__(*args, **kwargs)

    result = fnx.stoer_wagner(actual, heap=RecordingHeap)
    assert result == nx.stoer_wagner(reference)
    assert calls


@pytest.mark.parametrize("algorithm", ["stoer_wagner", "gomory_hu_tree"])
def test_live_capacity_mutations_are_visible(algorithm):
    reference, actual = _graphs([(0, 1, 3), (1, 2, 5), (0, 2, 2)], "amount")
    keyword = "weight" if algorithm == "stoer_wagner" else "capacity"
    operation = getattr(fnx, algorithm)
    oracle = getattr(nx, algorithm)
    operation(actual, **{keyword: "amount"})
    for graph in (reference, actual):
        graph[0][1]["amount"] = 11
        graph[0][2]["amount"] = 13
    result = operation(actual, **{keyword: "amount"})
    expected = oracle(reference, **{keyword: "amount"})
    if algorithm == "gomory_hu_tree":
        assert _tree_weights(result) == _tree_weights(expected)
    else:
        assert result == expected


def test_native_cut_paths_remain_available_for_small_integers(monkeypatch):
    _, actual = _graphs([(0, 1, 3), (1, 2, 5), (0, 2, 2)], "amount")
    import franken_networkx.backend as backend

    def reject_conversion(*args, **kwargs):
        raise AssertionError("bounded integral cuts must stay native")

    monkeypatch.setattr(backend, "_fnx_to_nx", reject_conversion)
    assert fnx.stoer_wagner(actual, weight="amount")[0] == 5
    tree = fnx.gomory_hu_tree(actual, capacity="amount")
    assert sorted(data["weight"] for _, _, data in tree.edges(data=True)) == [5, 7]


def test_large_integer_domains_do_not_enter_float_cut_kernels(monkeypatch):
    _, actual = _graphs([(0, 1, 2**53 + 1)], "amount")

    def reject_float_kernel(*args, **kwargs):
        raise AssertionError("exact capacities reached an f64 cut kernel")

    monkeypatch.setattr(_fnx, "stoer_wagner_phases", reject_float_kernel)
    monkeypatch.setattr(fnx, "_minimum_cut_raw", reject_float_kernel)
    assert fnx.stoer_wagner(actual, weight="amount")[0] == 2**53 + 1
    assert fnx.gomory_hu_tree(actual, capacity="amount")[0][1]["weight"] == 2**53 + 1


def test_mixed_weights_preserve_an_integral_winning_cut():
    reference, actual = _graphs([(0, 1, 2), (1, 2, 100.0), (1, 3, 100.0)], "weight")
    expected = nx.stoer_wagner(reference)
    result = fnx.stoer_wagner(actual)
    assert result == expected
    assert type(result[0]) is type(expected[0]) is int


def test_self_loop_weights_do_not_change_cut_or_result_type():
    reference, actual = _graphs([(0, 1, 3), (1, 2, 5), (0, 2, 2)], "weight")
    for graph in (reference, actual):
        graph.add_edge(1, 1, weight=Fraction(-1, 3))
    expected = nx.stoer_wagner(reference)
    result = fnx.stoer_wagner(actual)
    assert result == expected
    assert type(result[0]) is type(expected[0]) is int
