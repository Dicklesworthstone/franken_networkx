"""Differential + golden parity for ``has_bridges`` / ``local_bridges``.

``has_bridges(G)`` is a boolean; ``local_bridges(G, with_span=...)`` yields
local-bridge edges (optionally with their span). ``bridges`` itself already
has coverage.

br-r37-c1-vrdid
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _connected(seed, p=0.35):
    rng = random.Random(seed)
    n = rng.randint(5, 10)
    p_cur = p
    for _ in range(60):
        fg = fnx.Graph()
        ng = nx.Graph()
        fg.add_nodes_from(range(n))
        ng.add_nodes_from(range(n))
        for u in range(n):
            for v in range(u + 1, n):
                if rng.random() < p_cur:
                    fg.add_edge(u, v)
                    ng.add_edge(u, v)
        if nx.is_connected(ng):
            return fg, ng
        p_cur = min(0.9, p_cur + 0.05)
    return None


def _span_set(edges):
    return {(tuple(sorted((e[0], e[1]))), e[2]) for e in edges}


def _edge_set(edges):
    return {tuple(sorted((e[0], e[1]))) for e in edges}


@pytest.mark.parametrize("seed", range(60))
def test_has_bridges_matches_networkx(seed):
    pair = _connected(seed)
    if pair is None:
        pytest.skip("no connected graph")
    fg, ng = pair
    assert fnx.has_bridges(fg) == nx.has_bridges(ng)


@pytest.mark.parametrize("seed", range(60))
def test_local_bridges_matches_networkx(seed):
    pair = _connected(seed)
    if pair is None:
        pytest.skip("no connected graph")
    fg, ng = pair
    assert _span_set(fnx.local_bridges(fg)) == _span_set(nx.local_bridges(ng))
    assert _edge_set(fnx.local_bridges(fg, with_span=False)) == _edge_set(
        nx.local_bridges(ng, with_span=False)
    )


def test_bridges_goldens():
    # Every edge of a path is a bridge; a cycle has none.
    assert fnx.has_bridges(fnx.path_graph(4))
    assert not fnx.has_bridges(fnx.cycle_graph(4))
    # In a tree every edge is a local bridge with infinite span.
    p4 = fnx.path_graph(4)
    assert _span_set(fnx.local_bridges(p4)) == {
        ((0, 1), float("inf")), ((1, 2), float("inf")), ((2, 3), float("inf"))
    }


# br-r37-c1-64xcg: local_bridges(weight=...) ran its own Dijkstra on a
# (distance, node) heap, so a distance tie compared two nodes - TypeError on
# mixed int / str labels, where networkx's heap breaks ties with a counter.
@pytest.mark.parametrize("weight", [None, "weight", lambda u, v, d: d.get("weight", 1)])
@pytest.mark.parametrize("with_span", [True, False])
def test_local_bridges_on_mixed_labels_matches_networkx(with_span, weight):
    edges = [(0, "n1", 1.5), ("n1", 2, 2.5), (2, "n3", 1.0), ("n3", 0, 2.0), (2, "n5", 1.0),
             ("n5", 6, 0.5), (6, "n7", 1.5), ("n7", 0, 3.0), ("n5", 8, 2.0), (8, "n9", 1.0)]

    def bridges(lib):
        g = lib.Graph()
        g.add_weighted_edges_from(edges)
        return list(lib.local_bridges(g, with_span=with_span, weight=weight))

    assert bridges(fnx) == bridges(nx)
