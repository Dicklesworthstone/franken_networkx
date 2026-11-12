"""Parity for communicability_betweenness_centrality on disconnected graphs.

Bead br-r37-c1-zuly1.

nx computes ``B = (expA - expm(A_r)) / expA`` element-wise. On a disconnected
graph ``expA`` has zero entries between components, so the raw division yields
nan and nx returns nan for the connected nodes (isolated nodes get 0.0). fnx's
Rust kernel guards the division and returns finite values, so it diverged from
nx on every disconnected graph. Connected graphs already matched; fnx now
delegates the disconnected case to nx.
"""

from __future__ import annotations

import math
import random

import pytest

import franken_networkx as fnx

try:
    import networkx as nx
    HAS_NX = True
except ImportError:
    HAS_NX = False

needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


def _eq(a, b, tol=1e-6):
    if list(a) != list(b):  # keys + order
        return False
    for k in a:
        x, y = a[k], b[k]
        if math.isnan(x) and math.isnan(y):
            continue
        if math.isnan(x) != math.isnan(y):
            return False
        if abs(x - y) > tol:
            return False
    return True


@needs_nx
def test_isolated_node_yields_nan():
    f, n = fnx.Graph(), nx.Graph()
    for g in (f, n):
        g.add_edge(0, 1)
        g.add_node(2)  # isolated
    fr = fnx.communicability_betweenness_centrality(f)
    nr = nx.communicability_betweenness_centrality(n)
    assert _eq(fr, nr)
    # connected nodes are nan, the isolated node is 0.0 (nx contract)
    assert math.isnan(fr[0]) and math.isnan(fr[1])
    assert fr[2] == pytest.approx(0.0)


@needs_nx
def test_two_components():
    f, n = fnx.Graph(), nx.Graph()
    for g in (f, n):
        g.add_edges_from([(0, 1), (1, 2), (3, 4), (4, 5)])
    assert _eq(
        fnx.communicability_betweenness_centrality(f),
        nx.communicability_betweenness_centrality(n),
    )


@needs_nx
@pytest.mark.parametrize("seed", list(range(40)))
def test_random_match(seed):
    rng = random.Random(seed * 43 + 7)
    n = rng.randint(1, 11)
    ng = nx.gnp_random_graph(n, rng.choice([0.1, 0.25, 0.5]), seed=seed)
    fg = fnx.Graph()
    for u in ng.nodes():
        fg.add_node(u)
    for u, v in ng.edges():
        fg.add_edge(u, v)
    assert _eq(
        fnx.communicability_betweenness_centrality(fg),
        nx.communicability_betweenness_centrality(ng),
    )


@needs_nx
def test_connected_unchanged():
    f, n = fnx.Graph(), nx.Graph()
    for g in (f, n):
        g.add_edges_from([(0, 1), (1, 2), (2, 3), (3, 0), (0, 2)])
    assert _eq(
        fnx.communicability_betweenness_centrality(f),
        nx.communicability_betweenness_centrality(n),
    )


@needs_nx
def test_empty_and_single():
    assert fnx.communicability_betweenness_centrality(fnx.Graph()) == {}
    g = fnx.Graph()
    g.add_node(0)
    assert fnx.communicability_betweenness_centrality(g) == {0: 0.0}
