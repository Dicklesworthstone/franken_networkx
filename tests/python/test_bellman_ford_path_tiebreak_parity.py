"""Parity for Bellman-Ford shortest-PATH selection under equal-length ties.

Bead br-r37-c1-wloxg.

networkx implements Bellman-Ford as the SPFA variant (a FIFO deque seeded
with the source, relaxing each popped node's out-edges in adjacency-insertion
order, recording a predecessor only on a strict distance improvement).  fnx
previously used the textbook |V|-1-pass relaxation over edge-iteration order,
which finalises equal-distance ties in a different order and therefore returned
a *different* (but equally short) shortest path than nx whenever more than one
minimum-weight path exists.

Concrete witness (weighted 5-cycle + chords, weights 1,2,3,1,2,3,1):
    src=2 -> tgt=3 :  nx [2, 3]   vs   old-fnx [2, 1, 3]

These tests pin the path *values* (not merely lengths) to nx across directed
and undirected graphs, integer and negative weights, and confirm negative-cycle
detection still agrees.  Graphs are built from an *identical* edge sequence in
both libraries so adjacency-insertion order — which legitimately drives the
tie-break — matches.
"""

from __future__ import annotations

import random

import pytest

import franken_networkx as fnx

try:
    import networkx as nx
    HAS_NX = True
except ImportError:
    HAS_NX = False

needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


def _witness_edges():
    return [
        (0, 1, 1.0),
        (1, 2, 2.0),
        (2, 3, 3.0),
        (3, 4, 1.0),
        (4, 0, 2.0),
        (0, 2, 3.0),
        (1, 3, 1.0),
    ]


def _build(lib, edges, directed=False):
    g = lib.DiGraph() if directed else lib.Graph()
    for u, v, w in edges:
        g.add_edge(u, v, weight=w)
    return g


@needs_nx
def test_witness_single_source_path_values_match():
    f = _build(fnx, _witness_edges())
    n = _build(nx, _witness_edges())
    for src in n.nodes():
        fp = dict(fnx.single_source_bellman_ford_path(f, src, weight="weight"))
        npp = dict(nx.single_source_bellman_ford_path(n, src, weight="weight"))
        assert fp == npp, f"src={src}: fnx={fp} nx={npp}"


@needs_nx
def test_witness_specific_tie():
    """src=2 -> 3 has two equal-weight paths; nx picks the direct edge."""
    f = _build(fnx, _witness_edges())
    n = _build(nx, _witness_edges())
    fp = dict(fnx.single_source_bellman_ford_path(f, 2, weight="weight"))
    npp = dict(nx.single_source_bellman_ford_path(n, 2, weight="weight"))
    assert fp[3] == npp[3]


@needs_nx
def test_all_pairs_bellman_ford_path_values_match():
    f = _build(fnx, _witness_edges())
    n = _build(nx, _witness_edges())
    fa = dict(fnx.all_pairs_bellman_ford_path(f, weight="weight"))
    na = dict(nx.all_pairs_bellman_ford_path(n, weight="weight"))
    assert set(fa) == set(na)
    for src in na:
        assert dict(fa[src]) == dict(na[src]), f"src={src}"


@needs_nx
@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("seed", list(range(40)))
def test_random_path_values_match_networkx(directed, seed):
    """Build identical graphs in both libs from the same edge sequence and
    assert Bellman-Ford returns the exact same shortest paths (values)."""
    rng = random.Random(seed * 31 + (7 if directed else 3))
    n = rng.randint(3, 10)
    nodes = list(range(n))
    rng.shuffle(nodes)
    f = fnx.DiGraph() if directed else fnx.Graph()
    g = nx.DiGraph() if directed else nx.Graph()
    for u in nodes:
        f.add_node(u)
        g.add_node(u)
    seen = set()
    max_edges = n * (n - 1) // (1 if directed else 2)
    target = rng.randint(0, max_edges)
    tries = 0
    placed = 0
    while placed < target and tries < max_edges * 5:
        tries += 1
        u, v = rng.sample(nodes, 2)
        key = (u, v) if directed else tuple(sorted((u, v)))
        if key in seen:
            continue
        seen.add(key)
        w = float(rng.choice([1, 1, 2, 2, 3]))  # non-negative -> no cycles
        f.add_edge(u, v, weight=w)
        g.add_edge(u, v, weight=w)
        placed += 1
    for src in nodes:
        fp = dict(fnx.single_source_bellman_ford_path(f, src, weight="weight"))
        npp = dict(nx.single_source_bellman_ford_path(g, src, weight="weight"))
        assert fp == npp, f"directed={directed} seed={seed} src={src}"


@needs_nx
def test_negative_cycle_detection_parity():
    edges = [(0, 1, 1.0), (1, 2, -1.0), (2, 0, -1.0), (2, 3, 2.0)]
    f = _build(fnx, edges, directed=True)
    g = _build(nx, edges, directed=True)
    with pytest.raises(Exception) as fe:
        fnx.single_source_bellman_ford_path(f, 0, weight="weight")
    with pytest.raises(nx.NetworkXUnbounded):
        nx.single_source_bellman_ford_path(g, 0, weight="weight")
    assert "Unbounded" in type(fe.value).__name__ or "cycle" in str(fe.value).lower()


@needs_nx
def test_negative_weight_no_cycle_path_values_match():
    # negative edges but no negative cycle (a DAG-ish directed graph)
    edges = [
        (0, 1, 2.0), (0, 2, 4.0), (1, 2, -1.0),
        (1, 3, 5.0), (2, 3, 1.0), (2, 4, 3.0), (3, 4, -2.0),
    ]
    f = _build(fnx, edges, directed=True)
    g = _build(nx, edges, directed=True)
    fp = dict(fnx.single_source_bellman_ford_path(f, 0, weight="weight"))
    npp = dict(nx.single_source_bellman_ford_path(g, 0, weight="weight"))
    assert fp == npp
