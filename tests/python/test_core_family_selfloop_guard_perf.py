"""Core family (k_core/k_shell/k_crust/k_corona) self-loop guard.

Bead br-r37-c1-lczjd.

These four functions used to run a redundant Python EdgeView pass
``any(u == v for u, v in G.edges())`` to reject self-loop inputs, then
immediately call ``core_number(G)`` which runs the SAME check natively
(``number_of_selfloops``, the br-gauntlet-perf4 fix). At n=20000 the Python
guard alone was ~86ms of k_crust's ~199ms. The guard is now skipped when
``core_number`` is computed (``core_number()`` raises the identical
``NetworkXNotImplemented``) and uses the native fast check only when the caller
supplies a precomputed ``core_number``.

This is a pure perf change: structural output and the self-loop error contract
must be byte-identical. These tests pin parity with nx and confirm self-loops
are rejected on BOTH the computed and supplied-``core_number`` paths.
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

FNS = ["k_core", "k_shell", "k_crust", "k_corona"]


def _fbuild(g):
    f = fnx.Graph()
    for n in g.nodes():
        f.add_node(n)
    for u, v in g.edges():
        f.add_edge(u, v)
    return f


@needs_nx
@pytest.mark.parametrize("name", FNS)
@pytest.mark.parametrize("seed", list(range(25)))
def test_structural_parity_with_nx(name, seed):
    rng = random.Random(seed * 7 + 3)
    n = rng.randint(0, 30)
    g = nx.gnm_random_graph(n, rng.randint(0, n * 2), seed=seed) if n else nx.Graph()
    f = _fbuild(g)
    nfn, ffn = getattr(nx, name), getattr(fnx, name)
    if name == "k_corona":
        k = rng.randint(0, 4)
        nargs, fargs = (g, k), (f, k)
    else:
        nargs, fargs = (g,), (f,)
    try:
        expected = set(nfn(*nargs))
        err = None
    except Exception as e:  # e.g. empty graph -> ValueError from max()
        expected, err = None, type(e).__name__
    if err is None:
        assert set(ffn(*fargs)) == expected
    else:
        with pytest.raises(Exception) as ei:
            ffn(*fargs)
        assert type(ei.value).__name__ == err


@needs_nx
@pytest.mark.parametrize("name", FNS)
def test_selfloop_rejected_both_paths(name):
    sl = fnx.Graph()
    sl.add_edges_from([(0, 0), (0, 1), (1, 2)])
    ffn = getattr(fnx, name)
    base = (sl, 1) if name == "k_corona" else (sl,)
    # computed-core_number path
    with pytest.raises(fnx.NetworkXNotImplemented, match="self loops"):
        ffn(*base)
    # supplied-core_number path bypasses core_number(); must still reject
    cn = {0: 1, 1: 1, 2: 1}
    with pytest.raises(fnx.NetworkXNotImplemented, match="self loops"):
        if name == "k_corona":
            ffn(sl, 1, core_number=cn)
        else:
            ffn(sl, core_number=cn)


@needs_nx
@pytest.mark.parametrize("name", ["k_core", "k_shell", "k_crust", "k_corona"])
def test_supplied_core_number_no_selfloop_matches_computed(name):
    # When a (correct) core_number is supplied for a loop-free graph the result
    # must equal the computed-core_number result.
    g = nx.gnm_random_graph(40, 120, seed=4)
    f = _fbuild(g)
    cn = fnx.core_number(f)
    ffn = getattr(fnx, name)
    if name == "k_corona":
        assert set(ffn(f, 2, core_number=cn)) == set(ffn(f, 2))
    else:
        assert set(ffn(f, core_number=cn)) == set(ffn(f))
