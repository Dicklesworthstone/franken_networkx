"""Parity for native and owned ``group_betweenness_centrality`` routes.

Large groups use the owned inclusion-exclusion implementation. Small groups
retain the native unweighted route while its path counts fit, then use the
same owned implementation if combinatorial path multiplicity exceeds that
integer domain. Neither route delegates the centrality calculation upstream.

br-r37-c1-ejuhf
"""

from __future__ import annotations

import math
import random
import struct

import pytest
import networkx as nx
import franken_networkx as fnx


def _connected(seed, directed=False, p=0.4):
    rng = random.Random(seed)
    n = rng.randint(6, 10)
    fnx_cls, nx_cls = (fnx.DiGraph, nx.DiGraph) if directed else (fnx.Graph, nx.Graph)
    p_cur = p
    for _ in range(60):
        fg = fnx_cls()
        ng = nx_cls()
        fg.add_nodes_from(range(n))
        ng.add_nodes_from(range(n))
        for u in range(n):
            for v in range(n):
                if u == v:
                    continue
                if (directed or u < v) and rng.random() < p_cur:
                    fg.add_edge(u, v)
                    ng.add_edge(u, v)
        ok = nx.is_strongly_connected(ng) if directed else nx.is_connected(ng)
        if ok:
            return fg, ng, n
        p_cur = min(0.9, p_cur + 0.05)
    return None


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("group_size", [1, 2, 3, 4])
@pytest.mark.parametrize("normalized", [True, False])
@pytest.mark.parametrize("seed", range(20))
def test_group_betweenness_matches_networkx(directed, group_size, normalized, seed):
    pair = _connected(seed, directed=directed)
    if pair is None or pair[2] < group_size:
        pytest.skip("graph too small")
    fg, ng, n = pair
    rng = random.Random(seed * 7 + group_size)
    group = rng.sample(range(n), group_size)
    fr = fnx.group_betweenness_centrality(fg, group, normalized=normalized)
    nr = nx.group_betweenness_centrality(ng, group, normalized=normalized)
    assert fr == pytest.approx(nr, abs=1e-7)


def test_size3_regression_golden():
    # The original witness: fnx gave 0.5 where nx gives 0.5208333...
    edges = [
        (0, 2), (0, 3), (0, 4), (0, 7), (1, 2), (1, 3), (2, 3),
        (2, 4), (2, 6), (2, 7), (5, 6), (6, 7),
    ]
    fg = fnx.Graph(edges)
    ng = nx.Graph(edges)
    group = [0, 6, 4, 7]
    assert fnx.group_betweenness_centrality(fg, group) == pytest.approx(
        nx.group_betweenness_centrality(ng, group)
    )
    assert fnx.group_betweenness_centrality(fg, group, normalized=False) == pytest.approx(
        nx.group_betweenness_centrality(ng, group, normalized=False)
    )


def test_list_of_groups_matches_networkx():
    pair = _connected(1)
    assert pair is not None
    fg, ng, _ = pair
    groups = [[0, 1, 2], [3, 4]]
    assert fnx.group_betweenness_centrality(fg, groups) == pytest.approx(
        nx.group_betweenness_centrality(ng, groups)
    )


def test_endpoints_and_weight_paths_match_networkx():
    # Use a 7-node graph so a size-3 group still leaves >= 2 outside nodes
    # (avoids nx's own normalize-by-zero on tiny graphs).
    edges = [
        (0, 1, 2), (1, 2, 1), (2, 3, 3), (3, 4, 1), (4, 5, 2),
        (5, 6, 1), (0, 3, 4), (1, 4, 2), (2, 5, 3), (0, 6, 5),
    ]
    fg = fnx.Graph()
    ng = nx.Graph()
    for g in (fg, ng):
        g.add_weighted_edges_from(edges)
    group = [1, 2, 3]
    assert fnx.group_betweenness_centrality(fg, group, weight="weight") == pytest.approx(
        nx.group_betweenness_centrality(ng, group, weight="weight")
    )
    assert fnx.group_betweenness_centrality(fg, group, endpoints=True) == pytest.approx(
        nx.group_betweenness_centrality(ng, group, endpoints=True)
    )


def _layered_pair(width, levels):
    layers = [["s"]]
    layers.extend([[f"layer{i}:{j}" for j in range(width)] for i in range(levels)])
    layers.append(["t"])
    edges = [
        (u, v)
        for left, right in zip(layers, layers[1:])
        for u in left
        for v in right
    ]
    return fnx.Graph(edges), nx.Graph(edges), layers[len(layers) // 2]


@pytest.mark.parametrize(("width", "levels"), [(2, 64), (3, 42)])
@pytest.mark.parametrize("group_size", [1, 2])
@pytest.mark.parametrize("normalized", [False, True])
def test_combinatorial_path_counts_match_networkx(
    width, levels, group_size, normalized, monkeypatch
):
    fg, ng, middle = _layered_pair(width, levels)
    group = middle[:group_size]
    expected = nx.group_betweenness_centrality(ng, group, normalized=normalized)
    assert math.isfinite(expected)

    def forbidden(*args, **kwargs):
        raise AssertionError("overflow recovery must use the owned centrality solver")

    monkeypatch.setattr(nx, "group_betweenness_centrality", forbidden)
    monkeypatch.setattr(nx.algorithms.centrality, "group_betweenness_centrality", forbidden)
    actual = fnx.group_betweenness_centrality(fg, group, normalized=normalized)
    assert math.isfinite(actual)
    assert actual == pytest.approx(expected, rel=1e-13, abs=1e-13)


@pytest.mark.parametrize("normalized", [False, True])
def test_overflow_in_later_group_recomputes_complete_result(normalized):
    fg, ng, middle = _layered_pair(2, 8 * struct.calcsize("P"))
    groups = [["s", "t"], middle]
    # Excluding both endpoints removes the only sources with overflowing
    # counts. The second group must recover after one native score exists.
    assert fnx._fnx.group_betweenness_centrality_rust(fg, groups[0]) is not None
    assert fnx._fnx.group_betweenness_centrality_rust(fg, groups[1]) is None
    expected = nx.group_betweenness_centrality(ng, groups, normalized=normalized)
    assert fnx.group_betweenness_centrality(
        fg, groups, normalized=normalized
    ) == pytest.approx(expected, rel=1e-13, abs=1e-13)


def test_large_sparse_graph_retains_native_counting(monkeypatch):
    # Node count alone must not divert large graphs whose multiplicity is low.
    nodes = [f"node{i}" for i in range(180)]
    edges = list(zip(nodes, nodes[1:]))
    fg, ng = fnx.Graph(edges), nx.Graph(edges)
    groups = [[nodes[40]], [nodes[60], nodes[110]]]
    expected = nx.group_betweenness_centrality(ng, groups)

    def forbidden(*args, **kwargs):
        raise AssertionError("representable path counts should retain the native solver")

    monkeypatch.setattr(fnx, "_group_preprocessing_local", forbidden)
    assert fnx.group_betweenness_centrality(fg, groups) == pytest.approx(expected)
