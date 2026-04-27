"""Parity for core-decomposition family + eulerian_path on self-loop graphs.

Bead br-r37-c1-dg2dn. Two related parity defects on graphs with
self-loops:

1. ``core_number`` / ``k_core`` / ``k_shell`` / ``k_crust`` /
   ``k_corona`` silently accepted self-loop inputs and returned
   value dicts; nx raises NetworkXNotImplemented:
       "Input graph has self loops which is not permitted; Consider
        using G.remove_edges_from(nx.selfloop_edges(G))."

2. ``eulerian_path`` raised ``NetworkXError('Graph has no Eulerian
   paths.')`` on graphs that ARE Eulerian after the
   br-r37-c1-792dv has_eulerian_path / is_eulerian fix — the Rust
   _raw_eulerian_path mishandled self-loops the same way the
   boolean predicates did.
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


# ---------------------------------------------------------------------------
# core_number family — must raise NetworkXNotImplemented on self-loops
# ---------------------------------------------------------------------------

@needs_nx
@pytest.mark.parametrize(
    "fn_name", ["core_number", "k_core", "k_shell", "k_crust"]
)
def test_core_family_rejects_self_loop_graph(fn_name):
    """All five core-decomposition functions must raise
    NetworkXNotImplemented (matching nx) when the input has at least
    one self-loop. Pre-fix fnx silently included self-loops in the
    degree count and returned a value dict."""
    G = fnx.Graph([(1, 2), (2, 3), (3, 1), (1, 1)])
    GX = nx.Graph([(1, 2), (2, 3), (3, 1), (1, 1)])
    f_fn = getattr(fnx, fn_name)
    n_fn = getattr(nx, fn_name)
    with pytest.raises(
        fnx.NetworkXNotImplemented,
        match=r"Input graph has self loops which is not permitted",
    ):
        f_fn(G)
    with pytest.raises(
        nx.NetworkXNotImplemented,
        match=r"Input graph has self loops which is not permitted",
    ):
        n_fn(GX)


@needs_nx
def test_k_corona_rejects_self_loop_graph():
    """k_corona has a different signature (k is positional-required)
    so it gets its own test."""
    G = fnx.Graph([(1, 2), (2, 3), (3, 1), (1, 1)])
    GX = nx.Graph([(1, 2), (2, 3), (3, 1), (1, 1)])
    with pytest.raises(
        fnx.NetworkXNotImplemented,
        match=r"Input graph has self loops which is not permitted",
    ):
        fnx.k_corona(G, k=1)
    with pytest.raises(
        nx.NetworkXNotImplemented,
        match=r"Input graph has self loops which is not permitted",
    ):
        nx.k_corona(GX, k=1)


@needs_nx
def test_core_family_message_matches_nx_word_for_word():
    G = fnx.Graph([(1, 1)])
    GX = nx.Graph([(1, 1)])
    try:
        fnx.core_number(G)
    except fnx.NetworkXNotImplemented as e:
        f_msg = str(e)
    try:
        nx.core_number(GX)
    except nx.NetworkXNotImplemented as e:
        n_msg = str(e)
    assert f_msg == n_msg, (f_msg, n_msg)


@needs_nx
def test_core_family_caught_by_nx_class():
    """Drop-in: the fnx-raised NetworkXNotImplemented must be
    catchable via ``except nx.NetworkXNotImplemented``."""
    G = fnx.Graph([(1, 1)])
    try:
        fnx.core_number(G)
    except nx.NetworkXNotImplemented:
        return
    pytest.fail("fnx.core_number should raise NetworkXNotImplemented on self-loop input")


# ---------------------------------------------------------------------------
# eulerian_path — must succeed on self-loop graphs that have an Eulerian path
# ---------------------------------------------------------------------------

@needs_nx
def test_eulerian_path_K3_plus_self_loop_yields_full_path():
    """K3 + self-loop on node 1 has an Eulerian path that traverses
    every edge once (including the self-loop). Pre-fix fnx raised
    'Graph has no Eulerian paths.'; nx returns a complete edge
    sequence."""
    edges = [(1, 2), (2, 3), (3, 1), (1, 1)]
    G = fnx.Graph(edges)
    GX = nx.Graph(edges)

    # Pre-condition: predicates agree (br-r37-c1-792dv fix).
    assert fnx.has_eulerian_path(G) is nx.has_eulerian_path(GX) is True
    assert fnx.is_eulerian(G) is nx.is_eulerian(GX) is True

    # eulerian_path must now succeed and yield 4 edges (3 triangle +
    # 1 self-loop).
    f_path = list(fnx.eulerian_path(G))
    n_path = list(nx.eulerian_path(GX))
    assert f_path == n_path
    assert len(f_path) == 4


@needs_nx
def test_eulerian_path_single_self_loop_yields_self_loop():
    """A graph consisting of a single self-loop is Eulerian; the
    path is just that self-loop."""
    G = fnx.Graph([(0, 0)])
    GX = nx.Graph([(0, 0)])
    assert list(fnx.eulerian_path(G)) == list(nx.eulerian_path(GX)) == [(0, 0)]


# ---------------------------------------------------------------------------
# Regression guards — ensure self-loop-free fast path is unchanged
# ---------------------------------------------------------------------------

@needs_nx
@pytest.mark.parametrize("graph_factory_name", ["path_graph", "cycle_graph", "complete_graph"])
def test_core_family_no_self_loop_fast_path_unchanged(graph_factory_name):
    G = getattr(fnx, graph_factory_name)(5)
    GX = getattr(nx, graph_factory_name)(5)
    assert fnx.core_number(G) == nx.core_number(GX)
    assert sorted(fnx.k_core(G).edges()) == sorted(nx.k_core(GX).edges())


@needs_nx
def test_eulerian_path_no_self_loop_fast_path_unchanged():
    G = fnx.cycle_graph(4)
    GX = nx.cycle_graph(4)
    assert list(fnx.eulerian_path(G)) == list(nx.eulerian_path(GX))
