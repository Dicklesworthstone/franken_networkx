"""Parity for dominating_set's default start node.

Bead br-r37-c1-8zxph.

``dominating_set(G, start_with=None)`` seeds a greedy from ``start_with``;
networkx defaults it to ``arbitrary_element(set(G))`` == ``next(iter(set(G)))``.
fnx called a Rust kernel that seeded from a different node, so the returned
(still valid) dominating set differed from nx on ~half of random graphs. With a
matching seed the greedy already agrees exactly, so the fix computes nx's
default seed and reuses the matching greedy.
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


@needs_nx
def test_witness_default_start():
    edges = [(0, 1), (1, 2), (2, 3), (3, 4), (4, 0), (0, 2), (1, 3), (2, 4)]
    f, n = fnx.Graph(), nx.Graph()
    for u, v in edges:
        f.add_edge(u, v)
        n.add_edge(u, v)
    assert fnx.dominating_set(f) == nx.dominating_set(n)


@needs_nx
def test_explicit_start_still_matches():
    edges = [(0, 1), (1, 2), (2, 3), (3, 4), (4, 0), (0, 2), (1, 3), (2, 4)]
    f, n = fnx.Graph(), nx.Graph()
    for u, v in edges:
        f.add_edge(u, v)
        n.add_edge(u, v)
    for s in range(5):
        assert fnx.dominating_set(f, start_with=s) == nx.dominating_set(n, start_with=s)


@needs_nx
@pytest.mark.parametrize("kind", ["simple", "multigraph", "string"])
@pytest.mark.parametrize("seed", list(range(30)))
def test_random_default_start_matches(kind, seed):
    rng = random.Random(seed * 53 + hash(kind) % 97)
    if kind == "string":
        nodes = [chr(97 + i) for i in range(rng.randint(2, 9))]
    else:
        nodes = list(range(rng.randint(1, 11)))
    fg = fnx.MultiGraph() if kind == "multigraph" else fnx.Graph()
    ng = nx.MultiGraph() if kind == "multigraph" else nx.Graph()
    for u in nodes:
        fg.add_node(u)
        ng.add_node(u)
    for _ in range(rng.randint(0, len(nodes) * 2)):
        if len(nodes) < 2:
            break
        u, v = rng.sample(nodes, 2)
        fg.add_edge(u, v)
        ng.add_edge(u, v)
    assert fnx.dominating_set(fg) == nx.dominating_set(ng)


@needs_nx
def test_single_node_and_disconnected():
    f, n = fnx.Graph(), nx.Graph()
    f.add_node(0)
    n.add_node(0)
    assert fnx.dominating_set(f) == nx.dominating_set(n)
    f2, n2 = fnx.Graph(), nx.Graph()
    f2.add_edge(0, 1)
    f2.add_edge(2, 3)
    n2.add_edge(0, 1)
    n2.add_edge(2, 3)
    assert fnx.dominating_set(f2) == nx.dominating_set(n2)
