"""Parity for constraint / effective_size on graphs with self-loops.

Bead br-r37-c1-1boe3.

Burt's structural-holes measures match nx on simple graphs, but fnx's native
Rust kernels effectively *ignore* self-loops, whereas nx's matrix path folds a
self-loop into the mutual-weight row-sum / row-max normalization (while still
excluding the node from its own neighbor sum). The two therefore diverged
whenever a non-isolated node carried a self-loop. fnx now delegates self-loop
graphs to nx for the unweighted-undirected path (same delegation pattern
already used for weighted / directed inputs).
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


def _approx_eq(a, b, tol=1e-7):
    if set(a) != set(b):
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


def _witness(lib):
    g = lib.Graph()
    g.add_edges_from([(0, 1), (1, 2), (2, 0), (2, 3), (0, 0), (3, 3), (2, 2)])
    return g


@needs_nx
@pytest.mark.parametrize("fn", ["constraint", "effective_size"])
def test_witness_selfloops(fn):
    f = getattr(fnx, fn)(_witness(fnx))
    n = getattr(nx, fn)(_witness(nx))
    assert _approx_eq(f, n), f"{fn}: fnx={f} nx={n}"


@needs_nx
@pytest.mark.parametrize("fn", ["constraint", "effective_size"])
@pytest.mark.parametrize("seed", list(range(30)))
def test_random_selfloops(fn, seed):
    rng = random.Random(seed * 37 + 5)
    n = rng.randint(2, 10)
    ng = nx.gnp_random_graph(n, rng.choice([0.2, 0.4, 0.6]), seed=seed)
    for u in list(ng.nodes()):
        if rng.random() < 0.35:
            ng.add_edge(u, u)
    fg = fnx.Graph()
    for u in ng.nodes():
        fg.add_node(u)
    for u, v in ng.edges():
        fg.add_edge(u, v)
    assert _approx_eq(getattr(fnx, fn)(fg), getattr(nx, fn)(ng))


@needs_nx
@pytest.mark.parametrize("fn", ["constraint", "effective_size"])
def test_no_selfloop_unchanged(fn):
    # regression: the native Rust path must keep matching nx
    f, n = fnx.Graph(), nx.Graph()
    for u, v in [(0, 1), (1, 2), (2, 3), (3, 0), (0, 2), (1, 3)]:
        f.add_edge(u, v)
        n.add_edge(u, v)
    assert _approx_eq(getattr(fnx, fn)(f), getattr(nx, fn)(n))


@needs_nx
def test_isolated_with_only_selfloop_is_nan():
    f, n = fnx.Graph(), nx.Graph()
    for g in (f, n):
        g.add_edges_from([(0, 1), (1, 2)])
        g.add_edge(4, 4)
    fe = fnx.effective_size(f)
    ne = nx.effective_size(n)
    assert math.isnan(fe[4]) and math.isnan(ne[4])
    assert _approx_eq(fe, ne)
