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


@pytest.mark.xfail(
    strict=True,
    reason="br-r37-c1-fvgetattr: _FilteredGraphView.__getattr__ falls back to "
    "getattr(self.copy(), name), so an attribute MISS on a 4-node view walks the "
    "whole parent. Measured 57.84us at a 200-node parent against 394.48us at "
    "3200 (6.8x for a 16x parent) while networkx stays flat at 0.33-0.41us. "
    "Ratio degrades from 0.0072x to 0.0008x and keeps going.",
)
def test_failed_lookup_cost_does_not_track_parent_size():
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
