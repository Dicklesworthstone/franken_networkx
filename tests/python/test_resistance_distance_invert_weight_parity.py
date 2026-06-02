"""Parity for resistance_distance weight handling and endpoint branches.

Bead br-r37-c1-b2lck.

``resistance_distance`` builds the Laplacian from edge *conductances*. When
``invert_weight`` is True (the nx default), the weight attribute is treated as
*resistance*, so each edge weight w is replaced by 1/w before building the
Laplacian. fnx previously ignored ``invert_weight`` entirely — always behaving
as ``invert_weight=False`` — so weighted graphs were wrong by default. fnx also
lacked nx's single-endpoint branches (returning a flat dict when exactly one of
nodeA/nodeB is given).
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


def _witness(lib):
    g = lib.Graph()
    for i, (u, v) in enumerate([(0, 1), (1, 2), (2, 3), (3, 4), (4, 0),
                                (0, 2), (1, 3), (2, 4)]):
        g.add_edge(u, v, weight=float(i % 3 + 1))
    return g


@needs_nx
def test_invert_weight_default_matches_nx():
    f, n = _witness(fnx), _witness(nx)
    # default invert_weight=True
    fr = fnx.resistance_distance(f, 0, 1, weight="weight")
    nr = nx.resistance_distance(n, 0, 1, weight="weight")
    assert fr == pytest.approx(nr, abs=1e-9)
    # the bug: this used to equal the invert_weight=False value (~0.3688)
    assert fr != pytest.approx(
        nx.resistance_distance(n, 0, 1, weight="weight", invert_weight=False), abs=1e-6
    )


@needs_nx
@pytest.mark.parametrize("invert", [True, False])
def test_invert_weight_both_values_match(invert):
    f, n = _witness(fnx), _witness(nx)
    fr = fnx.resistance_distance(f, 0, 1, weight="weight", invert_weight=invert)
    nr = nx.resistance_distance(n, 0, 1, weight="weight", invert_weight=invert)
    assert fr == pytest.approx(nr, abs=1e-9)


@needs_nx
def test_single_endpoint_returns_flat_dict():
    f, n = _witness(fnx), _witness(nx)
    # only nodeA
    fa = fnx.resistance_distance(f, 0, weight="weight")
    na = nx.resistance_distance(n, 0, weight="weight")
    assert isinstance(fa, dict) and not isinstance(next(iter(fa.values())), dict)
    assert set(fa) == set(na)
    for k in na:
        assert fa[k] == pytest.approx(na[k], abs=1e-9)
    # only nodeB
    fb = fnx.resistance_distance(f, nodeB=2, weight="weight")
    nb = nx.resistance_distance(n, nodeB=2, weight="weight")
    assert set(fb) == set(nb)
    for k in nb:
        assert fb[k] == pytest.approx(nb[k], abs=1e-9)


@needs_nx
def test_full_dict_of_dicts_matches():
    f, n = _witness(fnx), _witness(nx)
    fr = fnx.resistance_distance(f, weight="weight")
    nr = nx.resistance_distance(n, weight="weight")
    assert set(fr) == set(nr)
    for u in nr:
        for v in nr[u]:
            assert fr[u][v] == pytest.approx(nr[u][v], abs=1e-9)


@needs_nx
def test_unweighted_unchanged():
    f, n = fnx.Graph(), nx.Graph()
    for u, v in [(0, 1), (1, 2), (2, 3), (3, 0), (0, 2)]:
        f.add_edge(u, v)
        n.add_edge(u, v)
    assert fnx.resistance_distance(f, 0, 2) == pytest.approx(
        nx.resistance_distance(n, 0, 2), abs=1e-9
    )


@needs_nx
@pytest.mark.parametrize("multigraph", [False, True])
@pytest.mark.parametrize("seed", list(range(25)))
def test_random_connected_matches_nx(multigraph, seed):
    rng = random.Random(seed * 41 + (3 if multigraph else 1))
    n = rng.randint(2, 8)
    fg = fnx.MultiGraph() if multigraph else fnx.Graph()
    ng = nx.MultiGraph() if multigraph else nx.Graph()
    for u in range(n):
        fg.add_node(u)
        ng.add_node(u)
    # connected spanning chain
    for u in range(n - 1):
        w = float(rng.choice([0.5, 1.0, 2.0, 3.0]))
        fg.add_edge(u, u + 1, weight=w)
        ng.add_edge(u, u + 1, weight=w)
    for _ in range(rng.randint(0, n)):
        if n < 2:
            break
        u, v = rng.sample(range(n), 2)
        w = float(rng.choice([0.5, 1.0, 2.0, 3.0]))
        fg.add_edge(u, v, weight=w)
        ng.add_edge(u, v, weight=w)
    for invert in (True, False):
        fr = fnx.resistance_distance(fg, 0, n - 1, weight="weight", invert_weight=invert)
        nr = nx.resistance_distance(ng, 0, n - 1, weight="weight", invert_weight=invert)
        assert fr == pytest.approx(nr, abs=1e-7), f"multi={multigraph} seed={seed} invert={invert}"
