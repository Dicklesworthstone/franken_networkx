"""Parity for ``generate_random_paths`` weight-default + walk semantics.

Self-review followup to br-r37-c1-rygbm. The default-arg sweep flagged
that ``fnx.generate_random_paths`` defaulted ``weight=None`` while nx
defaults to ``weight='weight'``. The fnx implementation also did a
uniform random walk regardless of edge weights — a behavioural divergence
on every weighted graph.

Fix landed: align default to ``'weight'`` AND honour edge weights via
``random.choices(nbrs, weights=...)``. ``weight=None`` still gives the
legacy uniform walk.
"""

from __future__ import annotations

import inspect
from collections import Counter

import pytest

import franken_networkx as fnx

try:
    import networkx as nx
    HAS_NX = True
except ImportError:
    HAS_NX = False

needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


@needs_nx
def test_generate_random_paths_weight_default_matches_networkx():
    fnx_default = inspect.signature(fnx.generate_random_paths).parameters["weight"].default
    nx_default = inspect.signature(nx.generate_random_paths).parameters["weight"].default
    assert fnx_default == nx_default == "weight"


@needs_nx
def test_generate_random_paths_honours_weights_by_default():
    """When edge (0,1) has weight 10 and (0,2) has weight 1, walks from
    0 should reach node 1 about 10x more often than node 2."""
    G = fnx.Graph()
    G.add_edge(0, 1, weight=10.0)
    G.add_edge(0, 2, weight=1.0)
    G.add_edge(1, 2, weight=1.0)

    paths = list(fnx.generate_random_paths(G, 1000, path_length=1, source=0, seed=42))
    endpoints = Counter(p[-1] for p in paths)
    # Roughly 10:1 ratio expected; allow generous slack
    assert endpoints[1] > 5 * endpoints[2], f"weighted bias absent: {endpoints}"


@needs_nx
def test_generate_random_paths_uniform_with_weight_none():
    """Pass weight=None for legacy uniform random walk; the bias
    toward node 1 must disappear (within sampling noise)."""
    G = fnx.Graph()
    G.add_edge(0, 1, weight=10.0)
    G.add_edge(0, 2, weight=1.0)

    paths = list(
        fnx.generate_random_paths(
            G, 500, path_length=1, source=0, weight=None, seed=42
        )
    )
    endpoints = Counter(p[-1] for p in paths)
    # 1:1 ratio expected; allow generous slack
    diff = abs(endpoints[1] - endpoints[2])
    assert diff < 100, f"unexpected bias under weight=None: {endpoints}"


@needs_nx
def test_generate_random_paths_path_length_matches_networkx():
    """nx path_length counts edges → produces path_length+1 nodes."""
    G = fnx.Graph()
    G.add_edges_from([(0, 1), (1, 2), (2, 3), (3, 0)])

    for length in [1, 2, 5, 10]:
        paths = list(
            fnx.generate_random_paths(G, 5, path_length=length, source=0, seed=42)
        )
        for p in paths:
            assert len(p) <= length + 1
            # In a connected graph with no dead-ends, equal:
            assert len(p) == length + 1


@needs_nx
def test_generate_random_paths_source_pinning():
    """When source= is set, every walk starts at that node."""
    G = fnx.karate_club_graph()
    paths = list(fnx.generate_random_paths(G, 50, path_length=3, source=5, seed=42))
    assert all(p[0] == 5 for p in paths)


@needs_nx
def test_generate_random_paths_missing_source_raises():
    G = fnx.path_graph(3)
    with pytest.raises(fnx.NodeNotFound):
        list(fnx.generate_random_paths(G, 1, source=99))


@needs_nx
def test_generate_random_paths_empty_graph_yields_nothing():
    G = fnx.Graph()
    paths = list(fnx.generate_random_paths(G, 5))
    assert paths == []


@needs_nx
def test_generate_random_paths_directed_respects_outgoing_edges():
    """On a DiGraph, walks should only follow outgoing edges."""
    D = fnx.DiGraph()
    D.add_edges_from([(0, 1), (1, 2), (2, 0)])

    paths = list(fnx.generate_random_paths(D, 50, path_length=3, source=0, seed=42))
    # 0 -> 1 -> 2 -> 0 -> ... is the only walk; no backwards traversal possible
    for p in paths:
        # Each step must be an actual edge in D
        for i in range(len(p) - 1):
            assert D.has_edge(p[i], p[i + 1])


@needs_nx
def test_generate_random_paths_multigraph_aggregates_parallel_weights():
    """On a MultiGraph with two parallel edges of weight 5 between 0 and
    1, plus one edge of weight 1 between 0 and 2, the effective transition
    weight from 0 should heavily favour 1 (10 vs 1)."""
    M = fnx.MultiGraph()
    M.add_edge(0, 1, weight=5.0)
    M.add_edge(0, 1, weight=5.0)
    M.add_edge(0, 2, weight=1.0)

    paths = list(fnx.generate_random_paths(M, 500, path_length=1, source=0, seed=42))
    endpoints = Counter(p[-1] for p in paths)
    assert endpoints[1] > 5 * endpoints[2]
