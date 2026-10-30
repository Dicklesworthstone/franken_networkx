"""Differential parity for Floyd-Warshall variants.

Covers ``floyd_warshall_numpy`` (dense distance matrix) and
``floyd_warshall_predecessor_and_distance`` (predecessor + distance
dicts). Neither had a dedicated test file.

Graphs are oriented low->high index so they stay acyclic (no negative
cycle), keeping the all-pairs distances well-defined even with negative
edge weights.

br-r37-c1-hykcx
"""

from __future__ import annotations

import random

import numpy as np
import pytest
import networkx as nx
import franken_networkx as fnx
import franken_networkx.algorithms as fnx_algorithms


def _valid_pair(seed, negatives=True):
    rng = random.Random(seed)
    n = rng.randint(4, 8)
    fg = fnx.DiGraph()
    ng = nx.DiGraph()
    fg.add_nodes_from(range(n))
    ng.add_nodes_from(range(n))
    for u in range(n):
        for v in range(u + 1, n):  # acyclic -> no negative cycle
            if rng.random() < 0.5:
                w = rng.randint(-3, 9) if negatives else rng.randint(1, 9)
                fg.add_edge(u, v, weight=w)
                ng.add_edge(u, v, weight=w)
    return fg, ng, n


@pytest.mark.parametrize("seed", range(50))
def test_floyd_warshall_numpy_matches_networkx(seed):
    fg, ng, _ = _valid_pair(seed)
    assert np.allclose(
        np.asarray(fnx.floyd_warshall_numpy(fg)),
        np.asarray(nx.floyd_warshall_numpy(ng)),
        equal_nan=True,
    )


@pytest.mark.parametrize("seed", range(50))
def test_floyd_warshall_predecessor_and_distance_matches_networkx(seed):
    fg, ng, _ = _valid_pair(seed)
    _, fdist = fnx.floyd_warshall_predecessor_and_distance(fg)
    _, ndist = nx.floyd_warshall_predecessor_and_distance(ng)
    # Distances are the well-defined invariant; predecessor choices are not
    # unique when multiple shortest paths tie, so only distances are compared.
    assert {u: dict(d) for u, d in fdist.items()} == {
        u: dict(d) for u, d in ndist.items()
    }


def test_floyd_warshall_goldens():
    g = fnx.DiGraph()
    ng = nx.DiGraph()
    for u, v, w in [(0, 1, 1), (1, 2, 2), (0, 2, 5)]:
        g.add_edge(u, v, weight=w)
        ng.add_edge(u, v, weight=w)
    _, dist = fnx.floyd_warshall_predecessor_and_distance(g)
    # 0->1->2 (cost 3) beats the direct 0->2 (cost 5).
    assert dist[0][2] == 3
    assert {u: dict(d) for u, d in dist.items()} == {
        u: dict(d) for u, d in nx.floyd_warshall_predecessor_and_distance(ng)[1].items()
    }


def _parallel_pair(seed, cls):
    rng = random.Random(seed)
    n = rng.randint(4, 8)
    graphs = (getattr(fnx, cls)(), getattr(nx, cls)())
    for graph in graphs:
        graph.add_nodes_from(range(n))
    for _ in range(3 * n):
        u, v = sorted(rng.sample(range(n), 2))
        w = rng.randint(1, 9)
        for graph in graphs:
            graph.add_edge(u, v, weight=w)
    return graphs


@pytest.mark.parametrize("cls", ["MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("seed", range(20))
def test_floyd_warshall_numpy_takes_the_lightest_parallel_edge(seed, cls):
    # br-r37-c1-545ld: networkx builds the matrix with multigraph_weight=min;
    # fnx summed parallel edges (dist 1.5 came back 5.5 on a doubled pair)
    fg, ng = _parallel_pair(seed, cls)
    assert np.array_equal(fnx.floyd_warshall_numpy(fg), nx.floyd_warshall_numpy(ng))
    nodelist = list(reversed(list(ng)))
    assert np.array_equal(
        fnx.floyd_warshall_numpy(fg, nodelist=nodelist),
        nx.floyd_warshall_numpy(ng, nodelist=nodelist),
    )


def _floyd_distance_state(distances):
    # Preserve ordering, scalar types, signed infinities, and NaNs without
    # treating NaN's intentionally unequal comparison as a parity failure.
    return [
        (
            source,
            [
                (target, type(value), value.hex() if type(value) is float else value)
                for target, value in row.items()
            ],
        )
        for source, row in distances.items()
    ]


@pytest.mark.parametrize("kind", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("mode", ["strict", "hardened"])
@pytest.mark.parametrize("namespace", [fnx, fnx_algorithms])
@pytest.mark.parametrize(
    "edges",
    [
        pytest.param([(0, 0, -2), (0, 1, 3), (1, 2, 1)], id="negative-self-loop-int"),
        pytest.param([(0, 0, -2.0), (0, 1, 3.0), (1, 2, 1.0)], id="negative-self-loop-float"),
        pytest.param([(0, 1, -2), (1, 0, 1), (1, 2, 3)], id="negative-cycle-int"),
        pytest.param([(0, 1, -2.0), (1, 0, 1.0), (1, 2, 3.0)], id="negative-cycle-float"),
        pytest.param([(0, 1, -float("inf")), (1, 2, 1.0)], id="negative-infinity"),
        pytest.param([(0, 1, float("nan")), (1, 2, 1.0)], id="nan-edge"),
        pytest.param([(0, 1, float("inf")), (1, 2, 1.0)], id="positive-infinity"),
        pytest.param([(0, 1, -2.0), (1, 2, 3.0), (0, 2, 4.0)], id="finite-weights"),
        pytest.param([(0, 2, -1e308), (2, 1, -1e308)], id="finite-underflow"),
    ],
)
def test_floyd_warshall_dictionary_numeric_contract(kind, mode, namespace, edges):
    graphs = [getattr(module, kind)() for module in (fnx, nx)]
    for graph in graphs:
        # The isolated node exposes NaNs propagated into unreachable rows.
        graph.add_nodes_from(range(4))
        for source, target, value in edges:
            graph.add_edge(source, target, cost=value)
    expected = nx.floyd_warshall(graphs[1], weight="cost")
    with fnx.compatibility_mode(mode):
        actual = namespace.floyd_warshall(graphs[0], weight="cost")
    assert _floyd_distance_state(actual) == _floyd_distance_state(expected)


@pytest.mark.parametrize("scalar", [int, float])
def test_floyd_warshall_finite_negative_dag_keeps_matrix_route(monkeypatch, scalar):
    graphs = [module.DiGraph() for module in (fnx, nx)]
    for graph in graphs:
        graph.add_nodes_from(range(4))
        for source, target, value in [(0, 1, -2), (1, 2, 3), (0, 2, 4)]:
            graph.add_edge(source, target, cost=scalar(value))
    namespace = fnx.floyd_warshall.__globals__
    matrix_solver = namespace["_floyd_warshall_numpy"]
    calls = []

    def record_matrix(graph, weight):
        calls.append(graph)
        return matrix_solver(graph, weight)

    def reject_fallback(*args, **kwargs):
        raise AssertionError("Finite negative DAG unnecessarily left the matrix route")

    monkeypatch.setitem(namespace, "_floyd_warshall_numpy", record_matrix)
    monkeypatch.setitem(
        namespace, "_floyd_warshall_predecessor_and_distance_inproc", reject_fallback
    )
    actual = fnx.floyd_warshall(graphs[0], weight="cost")
    expected = nx.floyd_warshall(graphs[1], weight="cost")
    assert calls == [graphs[0]]
    assert _floyd_distance_state(actual) == _floyd_distance_state(expected)
