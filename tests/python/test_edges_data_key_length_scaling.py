"""``G.edges(data=True)`` must stay BOUNDED in node-key length.

br-r37-c1-f3i50. Found by scanning both halves of each directed/undirected pair,
the heuristic that produced the keyed-subscript fix: a workload covering one half
of a pair is itself a lead, and here the halves disagree by 12.6x.

MEASURED, 300 edges, medians of repeated whole-list materialisations:

    class      K=3                    K=2000
    Graph      2.7992x   114.9 us     0.4538x   713.5 us     <- 6.2x SLOWER
    DiGraph    5.3019x    26.7 us     7.3555x    19.1 us     <- flat

networkx is flat across the same axis (321.6 us -> 323.8 us on Graph), so this is
not the workload getting harder. The simple-Graph path grows with node-key length
and the directed path does not, which is the same defect class already fixed twice
on this surface -- ``get_edge_data`` and ``edges[u, v, k]`` -- and the same
signature: a per-element canonical rebuild that the twin avoids.

WHY A SCALING TEST RATHER THAN A RATIO TEST. A vs-networkx ratio at one key length
cannot distinguish "slower" from "unbounded", and unbounded is the property that
matters: at K=3 the Graph row is a 2.8x WIN and looks healthy. Only the growth
across the key-length axis exposes it, and only relative to networkx's own growth,
which controls for the fixture getting bigger.

THE BOUND IS MEASURED, NOT GUESSED. The sibling file
``test_row_subscript_key_length_scaling.py`` records that an earlier draft guessed
its bound, set it wrong, and had its strict xfails XPASS as a result. Relative
growth here measures roughly 1.0-1.3x for the three bounded classes and about 6x
for Graph, so the bound sits between the clusters with room for noise.

The three bounded classes are asserted STRICTLY, so a regression that spreads this
defect to them fails the suite. Graph is ``xfail(strict=True)``: it documents the
open defect AND flips the suite red the moment someone fixes it, which is how
br-r37-c1-0k6zl's guard surfaced its own fix.
"""

from __future__ import annotations

import statistics
import time

import networkx as nx
import pytest

import franken_networkx as fnx

N = 300
SHORT_KEY = 3
LONG_KEY = 2000
# Measured: bounded classes cluster near 1.0-1.3x relative growth, Graph near 6x.
MAX_RELATIVE_GROWTH = 2.5

BOUNDED_CLASSES = ["DiGraph", "MultiGraph", "MultiDiGraph"]


def _build(lib, cls_name: str, key_len: int):
    graph = getattr(lib, cls_name)()
    for i in range(N):
        graph.add_edge(
            f"a{i}".ljust(key_len, "x"),
            f"b{i}".ljust(key_len, "y"),
            weight=i,
        )
    return graph


def _time(graph, reps: int = 40, rounds: int = 7) -> float:
    """MINIMUM across rounds, not the median.

    These assertions are strict and timing-based, so a false failure reddens the
    suite for every agent on a shared host. Contention can only ever make a
    sample SLOWER, so the minimum is the least contaminated estimator; the median
    still carries whatever load was present for half the rounds.

    Measured need: at loadavg 53 the median estimator reported DiGraph growing
    4.66x and failed the strict assertion, while a direct measurement taken at
    the same moment showed it flat (29.7us at 3-character keys against 28.7us at
    2000). That was pure contention, not a regression.
    """
    list(graph.edges(data=True))  # warm any per-generation cache
    samples = []
    for _ in range(rounds):
        start = time.perf_counter()
        for _ in range(reps):
            list(graph.edges(data=True))
        samples.append((time.perf_counter() - start) / reps)
    return min(samples)


def _growth(lib, cls_name: str) -> float:
    short = _time(_build(lib, cls_name, SHORT_KEY))
    long = _time(_build(lib, cls_name, LONG_KEY))
    return long / short if short > 0 else float("inf")


def _relative(cls_name: str):
    nx_growth = _growth(nx, cls_name)
    fnx_growth = _growth(fnx, cls_name)
    relative = fnx_growth / nx_growth if nx_growth > 0 else float("inf")
    return fnx_growth, nx_growth, relative


@pytest.mark.parametrize("cls_name", BOUNDED_CLASSES)
def test_bounded_classes_stay_bounded(cls_name):
    """These three do NOT grow with key length and must not start.

    This is the strict half. A regression here means whatever keeps them flat —
    a borrowed canonical, an index path, a cached tuple list — stopped applying,
    and it would show up as the Graph defect spreading rather than as an
    outright failure at any single key length.
    """
    fnx_growth, nx_growth, relative = _relative(cls_name)
    assert relative < MAX_RELATIVE_GROWTH, (
        f"{cls_name} edges(data=True): fnx grew {fnx_growth:.2f}x across "
        f"{SHORT_KEY}->{LONG_KEY} character keys against networkx's "
        f"{nx_growth:.2f}x (relative {relative:.2f}x, bound "
        f"{MAX_RELATIVE_GROWTH}x). This class has started tracking node-key "
        "length, which is the br-r37-c1-f3i50 defect spreading."
    )


# br-r37-c1-ml7s5 FIXED: the xfail that stood here is REMOVED, not relaxed.
#
# It read "PARTLY FIXED and still over the bound". The whole-graph list cache
# closed the rest: at K=2000 Graph reads 5.2558x against networkx (42.5us -> 56.9us
# across a 667x key-length range) where it began at 0.4538x/713.5us. Growth is
# 1.34x against networkx's own, inside the 2.5x bound.
#
# A strict xfail left in place after the defect is gone would hide the next
# regression behind an expected failure, so this is now an ordinary strict
# assertion like the other three classes.
def test_graph_edges_data_is_bounded_in_key_length():
    fnx_growth, nx_growth, relative = _relative("Graph")
    assert relative < MAX_RELATIVE_GROWTH, (
        f"Graph edges(data=True): fnx grew {fnx_growth:.2f}x across "
        f"{SHORT_KEY}->{LONG_KEY} character keys against networkx's "
        f"{nx_growth:.2f}x (relative {relative:.2f}x, bound {MAX_RELATIVE_GROWTH}x)"
    )


def test_values_match_networkx_at_both_key_lengths():
    """The scaling claim is only meaningful if both sides return the same thing.

    Guards the fixture itself: if fnx and networkx disagreed about what
    edges(data=True) yields, the timings above would be comparing two different
    computations and the growth ratio would be meaningless.
    """
    for cls_name in ["Graph", *BOUNDED_CLASSES]:
        for key_len in (SHORT_KEY, LONG_KEY):
            got = _build(fnx, cls_name, key_len).edges(data=True)
            want = _build(nx, cls_name, key_len).edges(data=True)
            assert sorted((u, v, tuple(sorted(d.items()))) for u, v, d in got) == sorted(
                (u, v, tuple(sorted(d.items()))) for u, v, d in want
            ), f"{cls_name} at key length {key_len} disagreed with networkx"
