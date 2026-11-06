"""Metric closure must preserve the public Dijkstra weight-domain contract."""

from fractions import Fraction
import math

import networkx as nx
import pytest

import franken_networkx as fnx


def _graph_pair(edges, weight):
    graphs = nx.Graph(), fnx.Graph()
    for graph in graphs:
        graph.add_edges_from((u, v, {weight: value}) for u, v, value in edges)
    return graphs


def _closure(module, graph, weight):
    kwargs = {"backend": "networkx"} if module is nx else {}
    with pytest.warns(DeprecationWarning, match="metric_closure"):
        return module.approximation.metric_closure(graph, weight=weight, **kwargs)


def _assert_closure_equal(actual, expected):
    assert set(actual) == set(expected)
    assert actual.number_of_edges() == expected.number_of_edges()
    for u, v, expected_attrs in expected.edges(data=True):
        actual_attrs = actual[u][v]
        assert actual_attrs["path"] == expected_attrs["path"]
        actual_distance = actual_attrs["distance"]
        expected_distance = expected_attrs["distance"]
        assert type(actual_distance) is type(expected_distance)
        if isinstance(expected_distance, float) and math.isnan(expected_distance):
            assert math.isnan(actual_distance)
        else:
            assert actual_distance == expected_distance


def _reject_packed_dijkstra(monkeypatch):
    def unexpected_packed_call(*args, **kwargs):
        pytest.fail("unsupported metric-closure weights entered the packed f64 kernel")

    monkeypatch.setattr(fnx, "_raw_all_pairs_dijkstra", unexpected_packed_call)


@pytest.mark.parametrize("weight", ["weight", "cost"])
@pytest.mark.parametrize(
    "value", [float("inf"), float("nan"), Fraction(1, 3)],
    ids=["infinity", "nan", "fraction"],
)
def test_metric_closure_preserves_nonfinite_and_exact_weights(value, weight, monkeypatch):
    gnx, gfx = _graph_pair([("s", "a", value), ("a", "t", 1)], weight)
    expected = _closure(nx, gnx, weight)
    assert fnx._should_delegate_dijkstra_to_networkx(gfx, weight) is True
    _reject_packed_dijkstra(monkeypatch)
    _assert_closure_equal(_closure(fnx, gfx, weight), expected)


@pytest.mark.parametrize("weight", ["weight", "cost"])
def test_metric_closure_large_integer_weights_choose_the_exact_path(weight, monkeypatch):
    # Rounding the direct edge down to 2**53 makes it tie and incorrectly win.
    gnx, gfx = _graph_pair([
        ("s", "a", 2**53), ("s", "t", 2**53 + 1), ("a", "t", 0),
    ], weight)
    expected = _closure(nx, gnx, weight)
    assert expected["s"]["t"]["distance"] == 2**53
    assert expected["s"]["t"]["path"] == ["s", "a", "t"]
    _reject_packed_dijkstra(monkeypatch)
    _assert_closure_equal(_closure(fnx, gfx, weight), expected)


@pytest.mark.parametrize("weight", ["weight", "cost"])
@pytest.mark.parametrize(
    "value", [None, -1.0, "not-a-number"],
    ids=["hidden-edge", "negative-edge", "nonnumeric-edge"],
)
def test_metric_closure_preserves_weight_errors(value, weight, monkeypatch):
    gnx, gfx = _graph_pair([("s", "a", value), ("a", "t", 1)], weight)
    with pytest.raises(Exception) as expected:
        _closure(nx, gnx, weight)
    _reject_packed_dijkstra(monkeypatch)
    with pytest.raises(Exception) as actual:
        _closure(fnx, gfx, weight)
    assert type(actual.value).__name__ == type(expected.value).__name__
    assert actual.value.args == expected.value.args


@pytest.mark.parametrize(
    "weights", [(3, 4), (2.5, 0.25), (1e308, 1e308, 1.0)],
    ids=["integers", "floats", "accumulated-infinity"],
)
def test_metric_closure_supported_weights_keep_the_packed_route(weights, monkeypatch):
    nodes = ["s", "a", "b", "t"][:len(weights) + 1]
    gnx, gfx = _graph_pair(list(zip(nodes, nodes[1:], weights)), "weight")
    expected = _closure(nx, gnx, "weight")
    raw = fnx._raw_all_pairs_dijkstra
    packed_calls = []

    def packed_dijkstra(*args, **kwargs):
        packed_calls.append(True)
        return raw(*args, **kwargs)

    def unexpected_public_call(*args, **kwargs):
        pytest.fail("supported metric-closure weights bypassed the packed kernel")

    monkeypatch.setattr(fnx, "_raw_all_pairs_dijkstra", packed_dijkstra)
    monkeypatch.setattr(fnx, "all_pairs_dijkstra", unexpected_public_call)
    _assert_closure_equal(_closure(fnx, gfx, "weight"), expected)
    assert packed_calls == [True]
