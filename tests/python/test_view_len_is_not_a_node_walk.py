"""``len()`` on a view whose node filter is default must not walk the nodes.

br-r37-c1-vlenall. Third unbounded cell found in the view family this session,
by the same instrument as the other two: hold the REQUEST fixed, grow the PARENT,
and see what tracks it.

``_FilteredGraphView.__len__`` ended in ``sum(1 for _ in self)``. For a view whose
NODE filter is the default - ``G.copy(as_view=True)``, and
``subgraph_view(filter_edge=...)`` - every parent node is present, so that walk
recounted the whole parent on every call:

    N=200    29.87us      N=3200   497.34us     growth 16.65x
    networkx  0.07us               0.09us       growth  1.27x

networkx proxies the parent's mapping, so its view length is O(1). After the fix
fnx is 0.147us / 0.164us, growth 1.12x, 3033x faster at N=3200.

CONSTRUCTION WAS NEVER THE PROBLEM and measuring it first is what kept this
honest: ``copy(as_view=True)`` construction is FLAT at 0.68x. Only the read grew.
A sweep that had timed "build a view and read it" as one unit would have found a
10.99x growth and blamed the constructor.

WHY THE GUARD IS SAFE, which is the whole correctness question. The flag
``_filter_node_is_default`` is computed by the view constructor and is True
exactly when every parent node is visible - verified directly: it is True for
``copy(as_view=True)`` (len == parent len) and False for ``subgraph()`` and
``edge_subgraph()`` (len < parent len). An EDGE filter cannot remove a node, so a
default node filter is sufficient on its own.

These tests pin both halves: that the length still MATCHES networkx for every
view kind, and that it no longer tracks the parent.
"""

from __future__ import annotations

import time

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]
SMALL_PARENT, LARGE_PARENT = 200, 3200
MAX_GROWTH = 2.0



def _best_growth(measure, build_small, build_large, attempts: int = 3) -> float:
    """Smallest growth ratio across `attempts` independent measurements.

    A growth assertion inside the full suite competes with every other test for
    the machine, and contention can only make a sample SLOWER - so a single
    reading can inflate the ratio arbitrarily. Taking the BEST of several is the
    same reasoning that makes `min()` the right per-round statistic, applied one
    level up. Without this the guard fails intermittently in the suite while
    passing every time standalone, which trains people to ignore it.
    """
    best = float("inf")
    for _ in range(attempts):
        small = measure(build_small())
        large = measure(build_large())
        best = min(best, large / small)
    return best

def _build(lib, cls, n):
    graph = getattr(lib, cls)()
    for i in range(n):
        graph.add_edge(f"n{i}", f"n{(i + 1) % n}", w=i)
    graph.add_node("isolated")
    return graph


def _views(lib, cls, n):
    g = _build(lib, cls, n)
    edges = (list(g.edges(keys=True)) if g.is_multigraph() else list(g.edges()))[:3]
    return g, [
        ("copy_as_view", g.copy(as_view=True)),
        ("subgraph", g.subgraph(list(g)[:4])),
        ("edge_subgraph", g.edge_subgraph(edges)),
    ]


@pytest.mark.parametrize("cls", CLASSES)
@pytest.mark.parametrize("n", [5, 20, 200])
def test_view_len_matches_networkx(cls, n):
    """The fast path must not change any answer."""
    _gf, vf = _views(fnx, cls, n)
    _gx, vx = _views(nx, cls, n)
    assert [(k, len(v)) for k, v in vf] == [(k, len(v)) for k, v in vx]


@pytest.mark.parametrize("cls", CLASSES)
def test_view_len_agrees_with_iteration(cls):
    """len() and iteration must not disagree - the fast path bypasses the walk."""
    _g, views = _views(fnx, cls, 40)
    for label, view in views:
        assert len(view) == sum(1 for _ in view), f"{label}: len != iteration count"


@pytest.mark.parametrize("cls", CLASSES)
def test_view_len_follows_parent_mutation(cls):
    """A view is LIVE: len() must reflect nodes added to the parent afterwards."""
    g, x = _build(fnx, cls, 20), _build(nx, cls, 20)
    vf, vx = g.copy(as_view=True), x.copy(as_view=True)
    before = (len(vf), len(vx))
    g.add_node("added-later")
    x.add_node("added-later")
    assert (len(vf), len(vx)) == (before[0] + 1, before[1] + 1)
    assert len(vf) == len(vx)
    g.remove_node("added-later")
    x.remove_node("added-later")
    assert len(vf) == len(vx) == before[0]


def _time_len(view, reps: int = 200, rounds: int = 5) -> float:
    for _ in range(50):
        len(view)
    samples = []
    for _ in range(rounds):
        start = time.perf_counter()
        for _ in range(reps):
            len(view)
        samples.append((time.perf_counter() - start) / reps)
    return min(samples)


def test_as_view_len_does_not_track_parent_size():
    """Measured 29.87us -> 497.34us (16.65x) before, 0.147 -> 0.164us (1.12x) after."""
    growth = _best_growth(
        _time_len,
        lambda: _build(fnx, "MultiDiGraph", SMALL_PARENT).copy(as_view=True),
        lambda: _build(fnx, "MultiDiGraph", LARGE_PARENT).copy(as_view=True),
    )
    assert growth < MAX_GROWTH, (
        f"len() on an as_view copy grew {growth:.2f}x when only the PARENT went "
        f"from {SMALL_PARENT} to {LARGE_PARENT} nodes "
        f"({small * 1e6:.3f}us -> {large * 1e6:.3f}us)"
    )


def test_networkx_len_is_flat_on_the_same_axis():
    growth = _best_growth(
        _time_len,
        lambda: _build(nx, "MultiDiGraph", SMALL_PARENT).copy(as_view=True),
        lambda: _build(nx, "MultiDiGraph", LARGE_PARENT).copy(as_view=True),
    )
    assert growth < MAX_GROWTH


def test_filtered_views_still_count_correctly():
    """The guard must NOT fire for views that really do hold fewer nodes."""
    g = _build(fnx, "MultiDiGraph", 200)
    assert len(g.subgraph(list(g)[:4])) == 4
    assert len(g.edge_subgraph(list(g.edges(keys=True))[:3])) < len(g)
