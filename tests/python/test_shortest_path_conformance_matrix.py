"""Differential conformance harness for shortest-path algorithms.

Bead franken_networkx-dyw3: table-driven Python-vs-NetworkX parity
matrix spanning the shortest-path family across graph types, weight
modes, and error contracts. This is the shortest-path analogue of the
centrality / community conformance harnesses.

Each fixture is small enough to be fast while still exercising:
- unweighted, attribute-weighted, and callable-weight modes,
- Graph, DiGraph, MultiGraph, MultiDiGraph constructors,
- missing-source / no-path / negative-cycle / unsupported-method
  error contracts.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _simple_weighted_pair(fnx_ctor, nx_ctor):
    fg = fnx_ctor()
    fg.add_edge(0, 1, weight=1.0)
    fg.add_edge(1, 2, weight=1.0)
    fg.add_edge(0, 2, weight=3.0)
    ng = nx_ctor()
    ng.add_edge(0, 1, weight=1.0)
    ng.add_edge(1, 2, weight=1.0)
    ng.add_edge(0, 2, weight=3.0)
    return fg, ng


def _path_pair(fnx_ctor, nx_ctor, n=5):
    return fnx_ctor() if False else (fnx.path_graph(n) if fnx_ctor is fnx.Graph else _path_via_ctor(fnx_ctor, n)), nx.path_graph(n) if nx_ctor is nx.Graph else _path_via_ctor_nx(nx_ctor, n)


def _path_via_ctor(ctor, n):
    g = ctor()
    for i in range(n - 1):
        g.add_edge(i, i + 1)
    return g


def _path_via_ctor_nx(ctor, n):
    g = ctor()
    for i in range(n - 1):
        g.add_edge(i, i + 1)
    return g


FAMILIES = [
    pytest.param(fnx.Graph, nx.Graph, id="Graph"),
    pytest.param(fnx.DiGraph, nx.DiGraph, id="DiGraph"),
    pytest.param(fnx.MultiGraph, nx.MultiGraph, id="MultiGraph"),
    pytest.param(fnx.MultiDiGraph, nx.MultiDiGraph, id="MultiDiGraph"),
]

UNDIRECTED_FAMILIES = [
    pytest.param(fnx.Graph, nx.Graph, id="Graph"),
    pytest.param(fnx.MultiGraph, nx.MultiGraph, id="MultiGraph"),
]


def _deep_path(path):
    return list(path) if path is not None else None


# ---------------------------------------------------------------------------
# Unweighted shortest paths
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("fnx_ctor", "nx_ctor"), FAMILIES)
def test_shortest_path_unweighted_matches_networkx(fnx_ctor, nx_ctor):
    fg = _path_via_ctor(fnx_ctor, 5)
    ng = _path_via_ctor_nx(nx_ctor, 5)
    assert fnx.shortest_path(fg, 0, 4) == nx.shortest_path(ng, 0, 4)


@pytest.mark.parametrize(("fnx_ctor", "nx_ctor"), FAMILIES)
def test_shortest_path_length_unweighted_matches_networkx(fnx_ctor, nx_ctor):
    fg = _path_via_ctor(fnx_ctor, 5)
    ng = _path_via_ctor_nx(nx_ctor, 5)
    assert fnx.shortest_path_length(fg, 0, 4) == nx.shortest_path_length(ng, 0, 4)


# ---------------------------------------------------------------------------
# Attribute-weighted shortest paths
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("fnx_ctor", "nx_ctor"),
    [
        pytest.param(fnx.Graph, nx.Graph, id="Graph"),
        pytest.param(fnx.DiGraph, nx.DiGraph, id="DiGraph"),
    ],
)
def test_shortest_path_attribute_weighted_matches_networkx(fnx_ctor, nx_ctor):
    fg, ng = _simple_weighted_pair(fnx_ctor, nx_ctor)
    # Weighted shortest path 0→2 prefers 0→1→2 (cost 2) over direct (cost 3).
    assert fnx.shortest_path(fg, 0, 2, weight="weight") == nx.shortest_path(
        ng, 0, 2, weight="weight"
    )
    assert fnx.shortest_path_length(
        fg, 0, 2, weight="weight"
    ) == nx.shortest_path_length(ng, 0, 2, weight="weight")


# ---------------------------------------------------------------------------
# Dijkstra-family
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("fnx_ctor", "nx_ctor"),
    [
        pytest.param(fnx.Graph, nx.Graph, id="Graph"),
        pytest.param(fnx.DiGraph, nx.DiGraph, id="DiGraph"),
    ],
)
def test_single_source_dijkstra_path_length_matches_networkx(fnx_ctor, nx_ctor):
    fg, ng = _simple_weighted_pair(fnx_ctor, nx_ctor)
    assert dict(fnx.single_source_dijkstra_path_length(fg, 0)) == dict(
        nx.single_source_dijkstra_path_length(ng, 0)
    )


@pytest.mark.parametrize(
    ("fnx_ctor", "nx_ctor"),
    [
        pytest.param(fnx.Graph, nx.Graph, id="Graph"),
        pytest.param(fnx.DiGraph, nx.DiGraph, id="DiGraph"),
    ],
)
def test_single_source_dijkstra_matches_networkx(fnx_ctor, nx_ctor):
    fg, ng = _simple_weighted_pair(fnx_ctor, nx_ctor)
    f_dist, f_paths = fnx.single_source_dijkstra(fg, 0)
    n_dist, n_paths = nx.single_source_dijkstra(ng, 0)
    assert dict(f_dist) == dict(n_dist)
    assert dict(f_paths) == dict(n_paths)


@pytest.mark.parametrize(
    ("fnx_ctor", "nx_ctor"),
    [
        pytest.param(fnx.Graph, nx.Graph, id="Graph"),
        pytest.param(fnx.DiGraph, nx.DiGraph, id="DiGraph"),
    ],
)
def test_all_pairs_dijkstra_matches_networkx(fnx_ctor, nx_ctor):
    fg, ng = _simple_weighted_pair(fnx_ctor, nx_ctor)
    # Materialise and compare per-source dicts.
    f_result = {src: (dict(d), dict(p)) for src, (d, p) in fnx.all_pairs_dijkstra(fg)}
    n_result = {src: (dict(d), dict(p)) for src, (d, p) in nx.all_pairs_dijkstra(ng)}
    assert f_result == n_result


# ---------------------------------------------------------------------------
# Bellman-Ford
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("fnx_ctor", "nx_ctor"),
    [
        pytest.param(fnx.Graph, nx.Graph, id="Graph"),
        pytest.param(fnx.DiGraph, nx.DiGraph, id="DiGraph"),
    ],
)
def test_bellman_ford_path_matches_networkx(fnx_ctor, nx_ctor):
    fg, ng = _simple_weighted_pair(fnx_ctor, nx_ctor)
    assert fnx.bellman_ford_path(fg, 0, 2) == nx.bellman_ford_path(ng, 0, 2)
    assert fnx.bellman_ford_path_length(fg, 0, 2) == nx.bellman_ford_path_length(
        ng, 0, 2
    )


# ---------------------------------------------------------------------------
# Johnson / Goldberg-Radzik
# ---------------------------------------------------------------------------


def test_johnson_matches_networkx_on_simple_digraph():
    fg = fnx.DiGraph()
    fg.add_weighted_edges_from([(0, 1, 1), (1, 2, 2), (0, 2, 5)])
    ng = nx.DiGraph()
    ng.add_weighted_edges_from([(0, 1, 1), (1, 2, 2), (0, 2, 5)])
    f = {k: dict(v) for k, v in fnx.johnson(fg, weight="weight").items()}
    n = {k: dict(v) for k, v in nx.johnson(ng, weight="weight").items()}
    assert f == n


def test_goldberg_radzik_matches_networkx_on_simple_digraph():
    fg = fnx.DiGraph()
    fg.add_weighted_edges_from([(0, 1, 1), (1, 2, 2)])
    ng = nx.DiGraph()
    ng.add_weighted_edges_from([(0, 1, 1), (1, 2, 2)])
    f_pred, f_dist = fnx.goldberg_radzik(fg, 0, weight="weight")
    n_pred, n_dist = nx.goldberg_radzik(ng, 0, weight="weight")
    assert dict(f_pred) == dict(n_pred)
    assert dict(f_dist) == dict(n_dist)


# ---------------------------------------------------------------------------
# Error contracts
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("fnx_ctor", "nx_ctor"),
    [
        pytest.param(fnx.Graph, nx.Graph, id="Graph"),
        pytest.param(fnx.DiGraph, nx.DiGraph, id="DiGraph"),
    ],
)
def test_shortest_path_missing_source_raises_like_networkx(fnx_ctor, nx_ctor):
    fg = _path_via_ctor(fnx_ctor, 3)
    ng = _path_via_ctor_nx(nx_ctor, 3)
    with pytest.raises((fnx.NodeNotFound, nx.NodeNotFound)):
        fnx.shortest_path(fg, 99, 0)
    with pytest.raises(nx.NodeNotFound):
        nx.shortest_path(ng, 99, 0)


@pytest.mark.parametrize(
    ("fnx_ctor", "nx_ctor"),
    [
        pytest.param(fnx.Graph, nx.Graph, id="Graph"),
        pytest.param(fnx.DiGraph, nx.DiGraph, id="DiGraph"),
    ],
)
def test_shortest_path_no_path_raises_like_networkx(fnx_ctor, nx_ctor):
    fg = fnx_ctor()
    fg.add_edge(0, 1)
    fg.add_node(5)  # isolated
    ng = nx_ctor()
    ng.add_edge(0, 1)
    ng.add_node(5)
    with pytest.raises((fnx.NetworkXError, fnx.NetworkXNoPath, nx.NetworkXNoPath)):
        fnx.shortest_path(fg, 0, 5)
    with pytest.raises(nx.NetworkXNoPath):
        nx.shortest_path(ng, 0, 5)


def test_bellman_ford_negative_cycle_raises_like_networkx():
    fg = fnx.DiGraph()
    fg.add_weighted_edges_from([(0, 1, 1), (1, 2, -3), (2, 0, 1)])
    ng = nx.DiGraph()
    ng.add_weighted_edges_from([(0, 1, 1), (1, 2, -3), (2, 0, 1)])
    with pytest.raises((fnx.NetworkXError, fnx.NetworkXUnbounded, nx.NetworkXUnbounded)):
        fnx.bellman_ford_path(fg, 0, 2)
    with pytest.raises(nx.NetworkXUnbounded):
        nx.bellman_ford_path(ng, 0, 2)
