"""Parity for is_chordal / complete_to_chordal_graph on self-loop graphs.

Bead br-r37-c1-i8qr5. fnx silently accepted graphs that nx rejects:

  >>> g = fnx.Graph([(0,1),(0,2),(0,3),(1,2),(1,3),(2,3),(0,0)])  # K4 + self-loop
  >>> fnx.is_chordal(g)                       # True
  >>> nx.is_chordal(nx.Graph(g))
  NetworkXError: Self loop found in _is_complete_graph()

  >>> fnx.complete_to_chordal_graph(g)
  (Graph(...), {...})
  >>> nx.complete_to_chordal_graph(nx.Graph(g))
  NetworkXError: Self loop found in _is_complete_graph()

The drift is *selective* — nx's _is_complete_graph internal helper
only raises when the algorithm reaches a candidate complete subgraph
that contains a self-loop. For triangle + self-loop or chain +
self-loop, neither algorithm reaches that branch and both nx and fnx
return True.

Drop-in code that does ``pytest.raises(NetworkXError, match='Self loop
found')`` on the K4-plus-self-loop case won't trigger on fnx. Both
fnx wrappers now delegate to nx whenever the input has a self-loop,
preserving nx's exact selective raise pattern.
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
# K4 + self-loop: nx's _is_complete_graph helper raises
# ---------------------------------------------------------------------------

@needs_nx
def test_is_chordal_K4_plus_self_loop_raises():
    edges = [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3), (0, 0)]
    G = fnx.Graph(edges)
    GX = nx.Graph(edges)
    with pytest.raises(fnx.NetworkXError, match=r"Self loop found in _is_complete_graph"):
        fnx.is_chordal(G)
    with pytest.raises(nx.NetworkXError, match=r"Self loop found in _is_complete_graph"):
        nx.is_chordal(GX)


@needs_nx
def test_complete_to_chordal_graph_K4_plus_self_loop_raises():
    edges = [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3), (0, 0)]
    G = fnx.Graph(edges)
    GX = nx.Graph(edges)
    with pytest.raises(fnx.NetworkXError, match=r"Self loop found in _is_complete_graph"):
        fnx.complete_to_chordal_graph(G)
    with pytest.raises(nx.NetworkXError, match=r"Self loop found in _is_complete_graph"):
        nx.complete_to_chordal_graph(GX)


# ---------------------------------------------------------------------------
# Other self-loop graphs nx does NOT raise on — fnx must match
# ---------------------------------------------------------------------------

@needs_nx
@pytest.mark.parametrize(
    "label,edges",
    [
        ("triangle + self-loop", [(1, 2), (2, 3), (3, 1), (1, 1)]),
        ("chain + self-loop", [(1, 1), (1, 2), (2, 3)]),
        ("only self-loops", [(1, 1), (2, 2)]),
        ("single self-loop", [(0, 0)]),
    ],
)
def test_is_chordal_self_loop_subset_matches_nx(label, edges):
    """For these self-loop shapes, nx's algorithm doesn't reach the
    _is_complete_graph branch — both libraries agree."""
    G = fnx.Graph(edges)
    GX = nx.Graph(edges)
    f = fnx.is_chordal(G)
    n = nx.is_chordal(GX)
    assert f == n, f"{label}: fnx={f} nx={n}"


# ---------------------------------------------------------------------------
# Regression guard: clean graphs unchanged
# ---------------------------------------------------------------------------

@needs_nx
@pytest.mark.parametrize(
    "graph_factory_name", ["path_graph", "cycle_graph", "complete_graph", "balanced_tree"]
)
def test_is_chordal_no_self_loop_fast_path_unchanged(graph_factory_name):
    """The Rust fast path remains the default for self-loop-free
    inputs. Sweep across factory shapes."""
    if graph_factory_name == "balanced_tree":
        G = getattr(fnx, graph_factory_name)(2, 3)
        GX = getattr(nx, graph_factory_name)(2, 3)
    else:
        G = getattr(fnx, graph_factory_name)(5)
        GX = getattr(nx, graph_factory_name)(5)
    assert fnx.is_chordal(G) == nx.is_chordal(GX)


@needs_nx
def test_complete_to_chordal_graph_no_self_loop_unchanged():
    """Clean cycle_graph(4) is non-chordal — both libraries return
    a chordal supergraph plus an alpha mapping."""
    G = fnx.cycle_graph(4)
    GX = nx.cycle_graph(4)
    H_f, alpha_f = fnx.complete_to_chordal_graph(G)
    H_n, alpha_n = nx.complete_to_chordal_graph(GX)
    # Both produce a chordal completion (structurally equivalent —
    # specific edges may differ in tie-breaking, but is_chordal must
    # be True for both).
    assert fnx.is_chordal(H_f)
    assert nx.is_chordal(H_n)
    assert set(alpha_f.keys()) == set(alpha_n.keys())


# ---------------------------------------------------------------------------
# Cross-class catching
# ---------------------------------------------------------------------------

@needs_nx
def test_is_chordal_self_loop_raise_caught_by_nx_class():
    """Drop-in: the fnx-raised NetworkXError must be catchable via
    ``except nx.NetworkXError``."""
    G = fnx.Graph([(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3), (0, 0)])
    try:
        fnx.is_chordal(G)
    except nx.NetworkXError:
        return
    pytest.fail("fnx.is_chordal should raise NetworkXError on K4+self-loop")
