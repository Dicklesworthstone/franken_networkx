"""br-r37-c1-1m155: regression tests for group_degree_centrality directed.

nx supports DiGraph for group_degree_centrality; the Rust kernel
has require_undirected. Wrapper now delegates directed to nx.
"""

from __future__ import annotations

import pytest

import franken_networkx as fnx

try:
    import networkx as nx

    HAS_NX = True
except ImportError:
    HAS_NX = False


needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


@needs_nx
def test_group_degree_centrality_digraph_matches_nx():
    g = fnx.DiGraph()
    gx = nx.DiGraph()
    for u, v in [(0, 1), (1, 2)]:
        g.add_edge(u, v)
        gx.add_edge(u, v)
    assert fnx.group_degree_centrality(g, {0}) == nx.group_degree_centrality(gx, {0})


@needs_nx
def test_group_degree_centrality_multidigraph_matches_nx():
    g = fnx.MultiDiGraph()
    gx = nx.MultiDiGraph()
    for u, v in [(0, 1), (1, 2)]:
        g.add_edge(u, v)
        gx.add_edge(u, v)
    assert fnx.group_degree_centrality(g, {0}) == nx.group_degree_centrality(gx, {0})


def test_group_degree_centrality_undirected_unchanged():
    g = fnx.path_graph(3)
    # On a 3-node path, group {1} dominates outsiders {0, 2}.
    result = fnx.group_degree_centrality(g, {1})
    assert result == pytest.approx(2 / 2)  # 2 outsiders, 2 connected → 1.0
