"""Parity for ``group_betweenness_centrality`` on groups of size >= 3.

Both the native fast path (undirected/unweighted) and the in-process
slow path (directed/weighted) mishandled the inclusion-exclusion
correction for shortest paths traversing three or more members of a
group, undercounting the score. Size-1 and size-2 groups were already
exact. The fix delegates any >=3-member group to nx.

br-r37-c1-ejuhf
"""

from __future__ import annotations

import random

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
