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

TWO FIXES HAVE BEEN TRIED AND BOTH MEASURED NOTHING. Recorded so the next
attempt starts past them rather than repeating them:

  1. A POSITION MASK replacing the per-edge name filter — the filter does
     ``node_set.contains(left) || node_set.contains(right)``, two full canonical
     hashes per edge, 600 on this fixture. Measured 0.2804x against a 0.2788x
     baseline. Nothing.
  2. RESOLVING nbunch items through the cached exact-``str`` index path, so no
     canonical is built per item — the same lever that worked for
     ``get_edge_data``, the keyed subscript and the attr mirror. The nbunch
     collection was deferred and split per branch so only the name-walking
     fallback pays for canonicals. Measured 0.2379x against 0.2971x on the same
     shape. Nothing, or slightly worse.

Both were reverted; ``crates/`` is byte-identical to HEAD. Between them they
eliminate the two obvious readings of the linear-in-nbunch shape below, which
means the per-item cost is NOT the canonical build and NOT the per-edge filter.
The next attempt should PROFILE the filtered path rather than reason about it —
this pane has now guessed the mechanism twice and been wrong twice.

The assertion here is deliberately loose. It pins the SHAPE — cost rising with
nbunch — because that is what identifies the defect and what a fix must flatten.
It is not a ratio gate and will not fail on a slow host.
"""

from __future__ import annotations

import time

import networkx as nx
import pytest

import franken_networkx as fnx

EDGES = 300
KEY_LEN = 2000
SHORT_KEY = 3
LARGE_NBUNCH = 200
# Measured: fnx grows 4.24x across the key-length axis at this nbunch while
# networkx grows 1.01x, i.e. relative ~4.2x. The bound sits well below that and
# well above the noise. It is NOT guessed - the sibling scaling file records a
# draft that guessed a bound and had its strict xfail XPASS as a result.
MAX_RELATIVE_GROWTH = 2.5


def _build_at(lib, key_len: int):
    graph = lib.Graph()
    for i in range(EDGES):
        graph.add_edge(
            f"a{i}".ljust(key_len, "x"), f"b{i}".ljust(key_len, "y"), weight=i
        )
    return graph, list(graph.nodes())


def _build(lib):
    return _build_at(lib, KEY_LEN)


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


@pytest.mark.xfail(
    strict=True,
    reason="br-r37-c1-nbidx: Graph.edges(nbunch, data=True) grows with NODE-KEY "
    "LENGTH at a large nbunch while networkx stays flat. Measured at nbunch=200: "
    "fnx 66.4us at K=3 against 281.8us at K=2000 (4.24x), networkx 82.5us against "
    "83.7us (1.01x). At K=3 the row is a 1.2425x WIN and at K=2000 it is 0.2971x. "
    "The per-item canonical build is the cost; the fix is to resolve nbunch items "
    "through the cached exact-str index path.",
)
def test_nbunch_edges_data_is_bounded_in_key_length():
    """The defect: cost tracks KEY LENGTH at a large nbunch, networkx does not.

    MEASURED SHAPE, and the reason this is the assertion rather than the earlier
    draft's. My first version compared growth across NBUNCH SIZE and asserted
    fnx grew 4x faster than networkx. That failed, because networkx iterates the
    nbunch too and grows with it as well - roughly 21x from 5 to 200 items. The
    axis that separates the two libraries is KEY LENGTH at a fixed nbunch, where
    networkx is flat by construction and fnx is not.

    At a SMALL nbunch there is no key-length effect at all (0.6190x at K=3
    against 0.6171x at K=2000), which is why the large nbunch is the one measured
    - a five-item probe would have reported this surface healthy.
    """
    fnx_short, short_nodes = _build_at(fnx, SHORT_KEY)
    fnx_long, long_nodes = _build_at(fnx, KEY_LEN)
    nx_short, nx_short_nodes = _build_at(nx, SHORT_KEY)
    nx_long, nx_long_nodes = _build_at(nx, KEY_LEN)

    fnx_growth = _time(fnx_long, long_nodes[:LARGE_NBUNCH]) / _time(
        fnx_short, short_nodes[:LARGE_NBUNCH]
    )
    nx_growth = _time(nx_long, nx_long_nodes[:LARGE_NBUNCH]) / _time(
        nx_short, nx_short_nodes[:LARGE_NBUNCH]
    )
    relative = fnx_growth / nx_growth

    assert relative < MAX_RELATIVE_GROWTH, (
        f"edges(nbunch, data=True) grew {fnx_growth:.2f}x across "
        f"{SHORT_KEY}->{KEY_LEN} character keys at a {LARGE_NBUNCH}-item nbunch, "
        f"against networkx's {nx_growth:.2f}x (relative {relative:.2f}x, bound "
        f"{MAX_RELATIVE_GROWTH}x)"
    )


def test_whole_graph_call_is_not_the_expensive_one():
    """Guards the attribution: the cached whole-graph path is much cheaper.

    If this ever inverts, the list cache (br-r37-c1-ml7s5) stopped applying and
    the nbunch reading above would be measuring something else entirely.
    """
    graph, nodes = _build(fnx)
    list(graph.edges(data=True))  # warm the whole-graph list cache
    start = time.perf_counter()
    for _ in range(30):
        list(graph.edges(data=True))
    cached = (time.perf_counter() - start) / 30

    big = _time(graph, nodes[:200])
    assert cached < big, (
        f"the cached whole-graph call ({cached * 1e6:.0f}us) should be cheaper "
        f"than a 200-item nbunch call ({big * 1e6:.0f}us)"
    )
