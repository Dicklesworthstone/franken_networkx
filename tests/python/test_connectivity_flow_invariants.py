"""Metamorphic theorem-invariants for the flow / connectivity family.

These lock relations that must hold by graph-theoretic theorems, as
regression guards (and cross-check against networkx):

* max-flow min-cut: ``maximum_flow_value == minimum_cut_value``
* Menger (edges): ``edge_connectivity(s, t) == #edge_disjoint_paths(s, t)``
* Menger (nodes): ``node_connectivity(s, t) == #node_disjoint_paths(s, t)``
  — including ADJACENT pairs (the relation that surfaced br-r37-c1-cqlms)
* global connectivity equals the minimum over all node pairs

br-r37-c1-gubl5
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _undirected(seed, p=0.5):
    rng = random.Random(seed)
    n = rng.randint(4, 8)
    fg = fnx.Graph()
    ng = nx.Graph()
    fg.add_nodes_from(range(n))
    ng.add_nodes_from(range(n))
    for u in range(n):
        for v in range(u + 1, n):
            if rng.random() < p:
                fg.add_edge(u, v)
                ng.add_edge(u, v)
    return fg, ng, n


def _capacitated_digraph(seed, p=0.4):
    rng = random.Random(seed)
    n = rng.randint(4, 7)
    fg = fnx.DiGraph()
    ng = nx.DiGraph()
    fg.add_nodes_from(range(n))
    ng.add_nodes_from(range(n))
    for u in range(n):
        for v in range(n):
            if u != v and rng.random() < p:
                c = rng.randint(1, 9)
                fg.add_edge(u, v, capacity=c)
                ng.add_edge(u, v, capacity=c)
    return fg, ng, n


@pytest.mark.parametrize("seed", range(40))
def test_max_flow_equals_min_cut(seed):
    fg, ng, n = _capacitated_digraph(seed)
    for s in range(n):
        for t in range(n):
            if s == t:
                continue
            mf = fnx.maximum_flow_value(fg, s, t)
            mc = fnx.minimum_cut_value(fg, s, t)
            assert mf == mc
            assert mf == nx.maximum_flow_value(ng, s, t)


@pytest.mark.parametrize("seed", range(40))
def test_menger_edge_and_node_connectivity(seed):
    fg, ng, n = _undirected(seed)
    if not nx.is_connected(ng):
        pytest.skip("disconnected")
    for s in range(n):
        for t in range(s + 1, n):
            # Menger (edges): edge connectivity = max edge-disjoint paths.
            ec = fnx.edge_connectivity(fg, s, t)
            assert ec == len(list(fnx.edge_disjoint_paths(fg, s, t)))
            assert ec == nx.edge_connectivity(ng, s, t)
            # Menger (nodes): node connectivity = max node-disjoint paths,
            # including adjacent pairs (br-r37-c1-cqlms).
            nc = fnx.node_connectivity(fg, s, t)
            assert nc == len(list(fnx.node_disjoint_paths(fg, s, t)))
            assert nc == nx.node_connectivity(ng, s, t)


@pytest.mark.parametrize("seed", range(40))
def test_global_connectivity_is_min_over_pairs(seed):
    fg, ng, n = _undirected(seed)
    if not nx.is_connected(ng) or n < 2:
        pytest.skip("disconnected or trivial")
    pairs = [(s, t) for s in range(n) for t in range(s + 1, n)]
    assert fnx.node_connectivity(fg) == min(
        fnx.node_connectivity(fg, s, t) for s, t in pairs
    )
    assert fnx.edge_connectivity(fg) == min(
        fnx.edge_connectivity(fg, s, t) for s, t in pairs
    )
