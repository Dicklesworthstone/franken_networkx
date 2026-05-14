"""br-r37-c1-8cqeh: regression — the +inf gating function
_has_positive_infinity_edge_weight_for_dijkstra must use the native
``graph_has_nonfinite_edge_weight`` Rust helper for fast short-circuit
on finite-weight graphs (the common case).

Before this fix, the gate iterated every edge in Python on every
dijkstra/astar call, adding ~50 ms of overhead on BA5000-sized
inputs. After: the native helper returns False fast for finite-only
graphs and we skip the Python scan.
"""

from __future__ import annotations

import time

import pytest

import franken_networkx as fnx


def _time_fn(fn, n=5):
    times = []
    for _ in range(n):
        t0 = time.perf_counter()
        fn()
        times.append(time.perf_counter() - t0)
    return min(times)


def test_inf_gate_native_short_circuits_on_finite_graph():
    """On a 500-node graph with no inf weights, the gate should return
    False quickly via the native nonfinite-scan helper."""
    g = fnx.gnp_random_graph(500, 0.1, seed=42)
    # Warm up
    for _ in range(2):
        fnx._has_positive_infinity_edge_weight_for_dijkstra(g, "weight")
    t = _time_fn(lambda: fnx._has_positive_infinity_edge_weight_for_dijkstra(g, "weight"))
    # Native scan: ~10-20 ms on typical hardware. Python scan was ~50 ms.
    # Allow a generous bound (~35 ms) so the test isn't flaky on slow CI.
    assert t < 0.035, f"+inf gate took {t*1000:.1f}ms — native fast path likely not engaged"


def test_inf_gate_detects_positive_infinity():
    """When a +inf weight is present, the gate must still detect it
    (i.e., the native short-circuit doesn't mask correctness)."""
    g = fnx.gnp_random_graph(50, 0.3, seed=42)
    edges = list(g.edges())
    g[edges[0][0]][edges[0][1]]["weight"] = float("inf")
    assert fnx._has_positive_infinity_edge_weight_for_dijkstra(g, "weight") is True


def test_inf_gate_ignores_negative_infinity():
    """``-inf`` is handled by the negative-weight gate, not this one.
    Even though native helper returns True for -inf (it's non-finite),
    this gate should not classify -inf as positive infinity."""
    g = fnx.Graph()
    g.add_edge(0, 1, weight=float("-inf"))
    g.add_edge(1, 2, weight=2.0)
    assert fnx._has_positive_infinity_edge_weight_for_dijkstra(g, "weight") is False


def test_inf_gate_ignores_nan():
    """NaN is non-finite but is not positive infinity. Don't flag it."""
    g = fnx.Graph()
    g.add_edge(0, 1, weight=float("nan"))
    g.add_edge(1, 2, weight=2.0)
    assert fnx._has_positive_infinity_edge_weight_for_dijkstra(g, "weight") is False


def test_inf_gate_finite_only_returns_false():
    g = fnx.gnp_random_graph(50, 0.3, seed=42)
    for u, v in g.edges():
        g[u][v]["weight"] = float(u + v + 1)
    assert fnx._has_positive_infinity_edge_weight_for_dijkstra(g, "weight") is False


def test_inf_gate_correctness_on_dijkstra_call():
    """Top-level: dijkstra_path on a +inf-containing graph still
    routes around the inf edge after the perf optimization."""
    g = fnx.Graph()
    g.add_edge(0, 1, weight=float("inf"))
    g.add_edge(0, 2, weight=1.0)
    g.add_edge(2, 1, weight=1.0)
    assert fnx.dijkstra_path(g, 0, 1, weight="weight") == [0, 2, 1]
