"""``edges(nbunch, data=True)`` costs per NBUNCH ITEM, not per edge.

br-r37-c1-nbidx. Landed as an attribution guard, not a fix: the fix is specified
below and is not yet written.

THE DEFECT. ``Graph.edges(nbunch, data=True)`` reads 0.2788x against networkx at
2000-character node keys while its DIRECTED twin is flat at 1.1224x — the fourth
directed/undirected asymmetry found on this surface. networkx is flat across the
same axis (34.1us at 3 characters, 27.8us at 2000).

WHERE THE COST IS, measured rather than assumed, on one graph of 300 edges at
K=2000 with only the nbunch size varied:

    nbunch=1        5.0 us
    nbunch=10      19.0 us
    nbunch=60      92.1 us
    nbunch=300    456.9 us
    nbunch=600    965.4 us
    whole graph    23.5 us   (served from the list cache, br-r37-c1-ml7s5)

Linear in the NBUNCH, at roughly 1.6us per item, on a graph whose edge count
never changes. So the cost is per-item work while collecting the nbunch —
``node_key_to_string`` builds a ``str:{len}:{s}`` canonical for every item, which
at 2000 characters is an allocation and a copy each — and NOT the per-edge
filter.

A HYPOTHESIS THIS TEST EXISTS TO KILL. The obvious reading is that the per-edge
filter is to blame: it does ``node_set.contains(left) || node_set.contains(right)``,
two full canonical hashes per edge, 600 of them here. I implemented a position
MASK to replace exactly that, measured it, and it changed nothing — 0.2804x
against 0.2788x. Removing 600 per-edge hashes and adding 60 per-node ones is a
wash, which is only possible if neither was the cost. The change was reverted;
this scaling shape is what should have been measured first.

THE FIX, for whoever takes it: resolve nbunch items to node positions through
the cached exact-``str`` index path, which reuses CPython's cached string hash,
instead of building a canonical per item. That is the same lever already landed
for ``get_edge_data``, the keyed subscript and the attr mirror. It needs the
nbunch collection loop restructured so the string set is built only for the
fallback path that actually walks names.

The assertion here is deliberately loose. It pins the SHAPE — cost rising with
nbunch — because that is what identifies the defect and what a fix must flatten.
It is not a ratio gate and will not fail on a slow host.
"""

from __future__ import annotations

import statistics
import time

import networkx as nx
import pytest

import franken_networkx as fnx

EDGES = 300
KEY_LEN = 2000


def _build(lib):
    graph = lib.Graph()
    for i in range(EDGES):
        graph.add_edge(
            f"a{i}".ljust(KEY_LEN, "x"), f"b{i}".ljust(KEY_LEN, "y"), weight=i
        )
    return graph, list(graph.nodes())


def _time(graph, nbunch, reps: int = 30, rounds: int = 5) -> float:
    list(graph.edges(nbunch, data=True))
    samples = []
    for _ in range(rounds):
        start = time.perf_counter()
        for _ in range(reps):
            list(graph.edges(nbunch, data=True))
        samples.append((time.perf_counter() - start) / reps)
    # min, not median: contention can only make a sample slower.
    return min(samples)


def test_nbunch_results_match_networkx():
    """The scaling claim is meaningless if the two disagree about the answer."""
    got, nodes = _build(fnx)
    want, _ = _build(nx)
    for nbunch in ([nodes[0]], nodes[:8], nodes[:60], [], ["absent-key"]):
        assert sorted(
            (u, v, tuple(sorted(d.items()))) for u, v, d in got.edges(nbunch, data=True)
        ) == sorted(
            (u, v, tuple(sorted(d.items())))
            for u, v, d in want.edges(nbunch, data=True)
        )


def test_cost_rises_with_nbunch_size_and_networkx_does_not():
    """The attribution: fnx pays per nbunch ITEM, networkx does not.

    Both libraries are measured on the same shapes, so a slow host moves both.
    The claim is a RATIO of growth, not an absolute time.
    """
    fnx_graph, nodes = _build(fnx)
    nx_graph, _ = _build(nx)
    small, large = nodes[:5], nodes[:200]

    fnx_growth = _time(fnx_graph, large) / _time(fnx_graph, small)
    nx_growth = _time(nx_graph, large) / _time(nx_graph, small)

    assert fnx_growth > 4.0 * nx_growth, (
        f"fnx edges(nbunch) grew {fnx_growth:.1f}x from a 5-item to a 200-item "
        f"nbunch against networkx's {nx_growth:.1f}x. If this has FALLEN, the "
        "per-item canonical build was fixed — delete this test and its bead."
    )


def test_whole_graph_call_is_not_the_expensive_one():
    """Guards the attribution: the cached whole-graph path is much cheaper.

    If this ever inverts, the list cache (br-r37-c1-ml7s5) stopped applying and
    the nbunch reading above would be measuring something else entirely.
    """
    graph, nodes = _build(fnx)
    whole = _time(graph, None) if False else None  # nbunch=None takes another path
    del whole
    graph.edges(data=True)  # warm the cache
    start = time.perf_counter()
    for _ in range(30):
        list(graph.edges(data=True))
    cached = (time.perf_counter() - start) / 30

    big = _time(graph, nodes[:200])
    assert cached < big, (
        f"the cached whole-graph call ({cached * 1e6:.0f}us) should be cheaper "
        f"than a 200-item nbunch call ({big * 1e6:.0f}us)"
    )
