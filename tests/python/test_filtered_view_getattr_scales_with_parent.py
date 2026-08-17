"""A FAILED attribute lookup on a filtered view must not walk the whole parent.

br-r37-c1-fvgetattr. The worst cell this pane has measured.

``_FilteredGraphView.__getattr__`` ends in ``return getattr(self.copy(), name)``.
``self.copy()`` materialises the view, which walks the PARENT graph - so every
attribute miss on a four-node subgraph of a 3200-node parent pays for the whole
parent, and then raises ``AttributeError`` anyway.

MEASURED, view size held CONSTANT at 4 nodes while only the parent grows:

    parent    fnx us/getattr    networkx us/getattr    ratio
      200          57.84               0.41           0.0072x
      800         127.14               0.33           0.0026x
     3200         394.48               0.33           0.0008x

networkx is flat; fnx grows linearly in the PARENT and the ratio degrades without
bound - 1250x at 3200 nodes, worse at every larger size.

WHY THIS IS NOT EXOTIC. An attribute miss is not a programming error, it is how
Python asks questions. ``hasattr(view, x)``, duck-typing probes for
``__wrapped__`` / ``shape`` / ``__array__``, ``copy``, ``pickle``, and the repr
machinery in pytest and IPython all probe attributes that graphs do not have.
Each probe silently copies the parent.

THE ASSERTION IS A SCALING SHAPE, not a ratio, because that is what identifies
the defect and what a fix must flatten: hold the VIEW fixed, grow the PARENT, and
the cost of a miss must not follow the parent. It is deliberately loose - a 4x
parent increase is allowed to cost up to 2x - so it cannot fail on a slow or busy
host, only on the real defect. See `scale_the_request_not_the_graph`.

THE FIX IS NOT OBVIOUS, which is why this lands as a guard rather than a repair.
When ``__getattr__`` fires, the name is already absent from the entire MRO - the
synthetic view class inherits the canonical graph class - so ``self.copy()`` can
only help for attributes that exist as INSTANCE state on a copy. Raising
immediately would be wrong for those. A cheap probe against an EMPTY graph of the
same class is the candidate, and it needs validating against attributes that
appear only once a graph holds data.
"""

from __future__ import annotations

import time

import networkx as nx
import pytest

import franken_networkx as fnx

SMALL_PARENT = 200
LARGE_PARENT = 3200
# 16x the parent for at most 2x the cost. Measured growth is ~6.8x, and a fix
# should make it ~1x; the bound sits far from both.
MAX_GROWTH = 2.0


def _view(lib, parent_nodes: int):
    graph = getattr(lib, "MultiDiGraph")()
    for i in range(parent_nodes):
        graph.add_edge(f"n{i}", f"n{(i + 1) % parent_nodes}", w=i)
    edges = list(graph.edges(keys=True))[:3]
    return graph.edge_subgraph(edges)


def _time_miss(view, reps: int = 200, rounds: int = 5) -> float:
    def probe():
        try:
            getattr(view, "totally_missing_attr")
        except AttributeError:
            pass

    probe()
    samples = []
    for _ in range(rounds):
        start = time.perf_counter()
        for _ in range(reps):
            probe()
        samples.append((time.perf_counter() - start) / reps)
    return min(samples)  # contention only makes samples slower


def test_missing_attribute_still_raises_like_networkx():
    """The claim is about COST; the behaviour must be unchanged."""
    got, want = _view(fnx, 40), _view(nx, 40)
    for name in ("totally_missing_attr", "_nope", "shape"):
        with pytest.raises(AttributeError):
            getattr(got, name)
        with pytest.raises(AttributeError):
            getattr(want, name)


def test_view_is_much_smaller_than_its_parent():
    """Guards the fixture: the scaling claim is meaningless if the view grows."""
    for parent in (SMALL_PARENT, LARGE_PARENT):
        view = _view(fnx, parent)
        assert view.number_of_nodes() <= 6, "view must stay small as the parent grows"


def test_failed_lookup_cost_does_not_track_parent_size():
    """FIXED. Was xfail(strict=True) until the probe landed; now a regression lock.

    After the fix, measured on the same axis:

        parent    fnx us/miss    networkx us/miss    ratio
          200          1.07             0.52        0.4875x
          800          0.71             0.36        0.5068x
         3200          0.71             0.36        0.5015x

    Flat in the parent, where it grew 6.8x before, and 556x faster at a
    3200-node parent. The remaining 0.5x against networkx is a CONSTANT, which is
    the part that matters: the unbounded term is gone. The bound below is
    unchanged from when this test failed.
    """
    small = _time_miss(_view(fnx, SMALL_PARENT))
    large = _time_miss(_view(fnx, LARGE_PARENT))
    growth = large / small
    assert growth < MAX_GROWTH, (
        f"a failed attribute lookup on a fixed 4-node view grew {growth:.2f}x "
        f"when only the PARENT went from {SMALL_PARENT} to {LARGE_PARENT} nodes "
        f"({small * 1e6:.1f}us -> {large * 1e6:.1f}us, bound {MAX_GROWTH}x)"
    )


def test_networkx_is_flat_on_the_same_axis():
    """The control: nx's own filtered view does not pay for the parent."""
    small = _time_miss(_view(nx, SMALL_PARENT))
    large = _time_miss(_view(nx, LARGE_PARENT))
    assert large / small < MAX_GROWTH, (
        "networkx grew on this axis too, so the fixture measures something other "
        "than the defect"
    )


# br-r37-c1-fvgetattr: the family sweep. The copy-fallback was found in
# _FilteredGraphView by measurement and in _ConversionGraphViewBase by accident
# (a patch assertion matched twice instead of once). Rather than trust that two
# is all there are, every view kind that reaches a __getattr__ fallback is pinned
# here on the same axis. _ReverseDirectedViewBase already raised AttributeError
# directly and is carried as the was-always-correct member of the family.
VIEW_KINDS = [
    ("edge_subgraph", lambda g: g.edge_subgraph(list(g.edges(keys=True))[:3])),
    ("subgraph", lambda g: g.subgraph(list(g.nodes())[:4])),
    ("to_undirected_as_view", lambda g: g.to_undirected(as_view=True)),
    ("reverse_as_view", lambda g: g.reverse(copy=False)),
]


@pytest.mark.parametrize("label,make", VIEW_KINDS, ids=[k[0] for k in VIEW_KINDS])
def test_every_view_kind_is_flat_in_the_parent(label, make):
    """No view kind may pay for its parent on an attribute MISS.

    Measured after the fix, parent 200 -> 3200 with the view held small:
    edge_subgraph 0.64x, subgraph 1.01x, to_undirected(as_view) 1.03x,
    reverse(copy=False) 0.96x.
    """

    def build(parent_nodes):
        graph = fnx.MultiDiGraph()
        for i in range(parent_nodes):
            graph.add_edge(f"n{i}", f"n{(i + 1) % parent_nodes}", w=i)
        return make(graph)

    small = _time_miss(build(SMALL_PARENT))
    large = _time_miss(build(LARGE_PARENT))
    growth = large / small
    assert growth < MAX_GROWTH, (
        f"{label}: a failed attribute lookup grew {growth:.2f}x when only the "
        f"PARENT went from {SMALL_PARENT} to {LARGE_PARENT} nodes "
        f"({small * 1e6:.2f}us -> {large * 1e6:.2f}us)"
    )


@pytest.mark.parametrize("label,make", VIEW_KINDS, ids=[k[0] for k in VIEW_KINDS])
def test_every_view_kind_still_raises_attributeerror(label, make):
    """The cost fix must not change the behaviour it was hiding behind."""
    graph = fnx.MultiDiGraph()
    for i in range(40):
        graph.add_edge(f"n{i}", f"n{(i + 1) % 40}", w=i)
    view = make(graph)
    for name in ("totally_missing_attr", "_nope", "shape"):
        with pytest.raises(AttributeError):
            getattr(view, name)


@pytest.mark.parametrize("label,make", VIEW_KINDS, ids=[k[0] for k in VIEW_KINDS])
def test_every_view_kind_still_serves_real_attributes(label, make):
    """The probe must not start refusing attributes that DO exist."""
    graph = fnx.MultiDiGraph()
    for i in range(12):
        graph.add_edge(f"n{i}", f"n{(i + 1) % 12}", w=i)
    view = make(graph)
    assert view.number_of_nodes() >= 1
    assert isinstance(view.is_directed(), bool)
    assert isinstance(view.is_multigraph(), bool)
    assert view.graph is not None


# br-r37-c1-vcopynb: `view.copy()` had the SAME shape as the attribute-miss
# defect - a request scoped to a small view paying for the parent - and it was
# found by sweeping every view operation on the axis that caught the first one.
# Two call sites had to be fixed: the `_fnx_materialized_cache` helper and
# `_FilteredGraphView.copy` itself. Patching only the first moved NOTHING,
# because the second was the one the profile actually reached.
def _time_copy(view, reps: int = 30, rounds: int = 5) -> float:
    view.copy()
    samples = []
    for _ in range(rounds):
        start = time.perf_counter()
        for _ in range(reps):
            view.copy()
        samples.append((time.perf_counter() - start) / reps)
    return min(samples)


def test_view_copy_cost_does_not_track_parent_size():
    """Measured 82.31us -> 384.39us across a 16x parent before the fix (6.95x),
    and 40.07us -> 41.90us after (1.05x), while networkx stayed flat at ~32us.
    The ratio had been falling 0.4079x -> 0.2542x -> 0.0812x with no floor.
    """
    small = _time_copy(_view(fnx, SMALL_PARENT))
    large = _time_copy(_view(fnx, LARGE_PARENT))
    growth = large / small
    assert growth < MAX_GROWTH, (
        f"view.copy() grew {growth:.2f}x when only the PARENT went from "
        f"{SMALL_PARENT} to {LARGE_PARENT} nodes "
        f"({small * 1e6:.1f}us -> {large * 1e6:.1f}us)"
    )


def test_networkx_copy_is_flat_on_the_same_axis():
    small = _time_copy(_view(nx, SMALL_PARENT))
    large = _time_copy(_view(nx, LARGE_PARENT))
    assert large / small < MAX_GROWTH, "fixture measures something other than the defect"


@pytest.mark.parametrize("cls", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("take", [1, 3, 7])
def test_view_copy_matches_networkx_including_edge_ORDER(cls, take):
    """The fix narrows a scan, so ORDER is the property most at risk.

    The whole-parent scan it replaces was chosen precisely because it preserved
    parent-adjacency order; restricting it to the selection's endpoints keeps
    that order only because the same nodes are visited in the same sequence.
    Compared as a LIST, not a set.
    """
    n = 60
    got, want = getattr(fnx, cls)(), getattr(nx, cls)()
    for g in (got, want):
        for i in range(n):
            g.add_edge(f"n{i}", f"n{(i + 1) % n}", w=i)
    keys = got.is_multigraph()
    ge = (list(got.edges(keys=True)) if keys else list(got.edges()))[:take]
    xe = (list(want.edges(keys=True)) if keys else list(want.edges()))[:take]
    cf, cx = got.edge_subgraph(ge).copy(), want.edge_subgraph(xe).copy()

    def rows(graph):
        it = graph.edges(keys=True, data=True) if keys else graph.edges(data=True)
        return [(str(a), str(b)) + tuple(rest) for a, b, *rest in it]

    assert rows(cf) == rows(cx)
    assert [str(z) for z in cf.nodes()] == [str(z) for z in cx.nodes()]
