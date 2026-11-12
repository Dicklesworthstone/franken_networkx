"""``edges(nbunch, data=True)``: CLOSED, 0.2788x -> 0.9636x at 2000-char keys.

br-r37-c1-nbidx. This file began as an attribution guard for a defect nobody had
located, carried a strict xfail through four attempts, and is now a regression
lock. The history is kept because the two DEAD ENDS cost more than the fix did.

THE DEFECT AS FOUND. ``Graph.edges(nbunch, data=True)`` read 0.2788x against
networkx at 2000-character node keys while its DIRECTED twin was flat at
1.1224x — the fourth directed/undirected asymmetry found on this surface.
networkx is flat across the same axis by construction.

TWO REASONED FIXES, BOTH MEASURED, BOTH WORTH NOTHING:

  1. A POSITION MASK replacing the per-edge name filter. 0.2804x against a
     0.2788x baseline.
  2. RESOLVING nbunch items through the cached exact-``str`` index path — the
     lever that had already worked for ``get_edge_data``, the keyed subscript
     and the attr mirror. 0.2379x against 0.2971x.

WHY BOTH MEASURED NOTHING, which is the reusable lesson and was invisible from
reading the code. Both patched ``views.rs::edge_alldata_items``. A cProfile of
the actual call shows it never enters that function: it enters
``readwrite.rs::edges_nbunch_data``, plus ``edges_nbunch_count`` for the size
hint. Two careful measurements of code the path does not execute. Read those two
NEGATIVE results as "wrong file", not "wrong idea" — hypothesis 2 was in fact
half the eventual fix, applied to the wrong function.

WHAT ACTUALLY FIXED IT, once the profile named the right file — both halves the
same lever, an O(key length) canonical replaced by an index:

  * PER NBUNCH ITEM, ``node_key_to_string`` built a ``str:{len}:{s}`` canonical.
    Replaced by ``cached_exact_string_node_index``.      0.2788x -> 0.4589x
  * PER EDGE, ``edge_key(u_name, v_name)`` built an owned key from BOTH endpoint
    names — ~4000 bytes allocated, copied and hashed per edge. Replaced by
    ``cached_edge_py_attrs_by_index``.                   0.4589x -> 0.9636x

The second half needed a MUTABLE graph borrow to populate the lookaside, which
``extract_graph`` cannot give; the kernel now takes ``PyRefMut`` directly and
returns ``None`` if it cannot, falling back to the Python walk rather than
panicking on a read path.

WARM-CALL COST. A lookaside must be populated before it can be read, so the
first call on a fresh graph is unchanged: 0.2494x cold against 0.9636x warm at
K=2000. That is the honest limit of this fix and it is asserted nowhere, so it is
recorded here.

The assertion below pins the SHAPE — cost rising with key length — because that
is what identified the defect. It is not a ratio gate and will not fail on a slow
host.
"""

from __future__ import annotations

import time

import networkx as nx

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


def test_nbunch_edges_data_is_bounded_in_key_length():
    """FIXED, and this is now a regression lock rather than an xfail.

    It was ``xfail(strict=True)`` from the day the defect was found until
    br-r37-c1-nbidx closed both halves of it, at which point it XPASSED and
    reddened the suite - which is the entire reason the marker was strict. The
    marker is gone; the ASSERTION and its bound are unchanged from the day it was
    written, so what passes now is the same statement that failed then.

    Measured across the two levers, nbunch=200, min of 7 rounds of 30:

        original                    0.2788x     relative growth 4.24x
        after the per-ITEM fix      0.4589x
        after the per-EDGE fix      0.9636x     relative growth 1.84x

    THE COST IS WARM-CALL COST. The first call on a fresh graph still pays the
    full canonical for every edge, because a lookaside has to be populated before
    it can be read: measured 0.2494x cold at K=2000 against 0.9636x warm. This
    test times a warmed graph, like every other lookaside test in this suite, and
    the sibling file records the cold number so nobody has to rediscover it.

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
