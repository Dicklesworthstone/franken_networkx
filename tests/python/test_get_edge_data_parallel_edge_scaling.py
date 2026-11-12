"""br-r37-c1-f3i50 / br-r37-c1-ptiz2 — unkeyed `get_edge_data` must stay BOUNDED
in parallel-edge count.

THE DEFECT THIS GUARDS WAS NOT A SLOW RATIO, IT WAS AN UNBOUNDED ONE. networkx
returns `self._adj[u][v]` — the live keydict — in O(1). fnx rebuilt that mapping
on every call, so the cost grew linearly in the number of parallel edges between
the pair and the ratio fell without limit:

    parallel edges   nx        fnx        ratio
    1                 77 ns     312 ns    0.2482
    16                77 ns    2838 ns    0.0259
    64                74 ns   12409 ns    0.0061

That 0.0061x was the worst cell measured in this project, and at 256 parallel
edges it would have been roughly 0.0015x. A single-size ratio check could not see
it: the par=1 row looks like an ordinary constant-factor loss.

The keydict cache fixed it. Measured on the same substrate after:

    parallel edges   nx        fnx        ratio
    1                 77 ns     157 ns    0.4935
    16                78 ns     211 ns    0.3680
    64                78 ns     329 ns    0.2373

fnx now grows about 2x across a 64x span of parallel edges, against roughly 40x
before.

WHY THIS TEST MEASURES GROWTH AND NOT A RATIO. A ratio threshold would be a
timing assertion, and this pane has banked that absolute nanoseconds move 1.6x
between windows and that a busy SMT sibling shifts a ratio 17 percent. Growth
across parallel-edge count within ONE process is far more robust: both
measurements share a window, a core and a clock, so the common-mode factors
divide out. networkx's own growth is the control — it should be flat, and if the
host makes IT look non-flat the test says so rather than blaming fnx.

The bound is deliberately loose. Before the fix the growth ratio was ~40x; after,
~2x. Failing at 8x leaves a 4x margin on either side, so this catches a
reintroduced rebuild-per-call without firing on ordinary noise.
"""

from __future__ import annotations

import statistics
import time

import networkx as nx
import pytest

import franken_networkx as fnx

N = 200
LOW_PAR = 1
HIGH_PAR = 64
# Before the fix fnx grew ~40x across this span; after, ~2x. See the module
# docstring for why the bound sits between them rather than near either.
MAX_RELATIVE_GROWTH = 8.0


def _build(lib, cls_name, par):
    graph = getattr(lib, cls_name)()
    for i in range(N):
        for k in range(par):
            graph.add_edge(f"n{i}", f"n{(i * 7 + 3) % N}", weight=float(k))
    return graph


def _time_get_edge_data(graph, reps=3000, rounds=5):
    u, v = "n5", f"n{(5 * 7 + 3) % N}"
    getter = graph.get_edge_data
    getter(u, v)  # warm
    samples = []
    for _ in range(rounds):
        start = time.perf_counter()
        for _ in range(reps):
            getter(u, v)
        samples.append((time.perf_counter() - start) / reps)
    return statistics.median(samples)


def _growth(lib, cls_name):
    low = _time_get_edge_data(_build(lib, cls_name, LOW_PAR))
    high = _time_get_edge_data(_build(lib, cls_name, HIGH_PAR))
    return high / low if low > 0 else float("inf")


@pytest.mark.parametrize("cls_name", ["MultiGraph", "MultiDiGraph"])
def test_get_edge_data_is_bounded_in_parallel_edge_count(cls_name):
    """fnx's growth must not wildly exceed networkx's across a 64x span.

    networkx is the control and is measured in the same process, on the same
    core, in the same window, so clock and contention divide out.
    """
    nx_growth = _growth(nx, cls_name)
    fnx_growth = _growth(fnx, cls_name)
    relative = fnx_growth / nx_growth if nx_growth > 0 else float("inf")
    assert relative < MAX_RELATIVE_GROWTH, (
        f"{cls_name}: get_edge_data cost grew {fnx_growth:.1f}x across "
        f"{LOW_PAR}->{HIGH_PAR} parallel edges against networkx's {nx_growth:.1f}x "
        f"(relative {relative:.1f}x, bound {MAX_RELATIVE_GROWTH}x). "
        "br-r37-c1-f3i50: this is the signature of rebuilding the keydict on "
        "every call, which made this the worst cell in the project at 0.0061x."
    )


@pytest.mark.parametrize("cls_name", ["MultiGraph", "MultiDiGraph"])
def test_the_control_is_itself_flat(cls_name):
    """If networkx's own growth is not flat, the host is lying to us.

    This is what stops the test above from blaming fnx for a bad window: a
    non-flat control invalidates the comparison rather than convicting anyone.
    """
    nx_growth = _growth(nx, cls_name)
    assert nx_growth < MAX_RELATIVE_GROWTH, (
        f"{cls_name}: networkx's own get_edge_data grew {nx_growth:.1f}x across "
        f"{LOW_PAR}->{HIGH_PAR} parallel edges. networkx returns the live "
        "keydict in O(1), so this measurement is untrustworthy — re-run in a "
        "quieter window before reading the companion test."
    )


@pytest.mark.parametrize("cls_name", ["MultiGraph", "MultiDiGraph"])
def test_values_stay_correct_at_high_parallel_edge_counts(cls_name):
    """Boundedness is worthless if the fast path returns the wrong mapping.

    Pins content and key order against networkx at the high end, so a cache that
    achieved O(1) by going stale would fail here rather than pass quietly.
    """
    gnx = _build(nx, cls_name, HIGH_PAR)
    gfx = _build(fnx, cls_name, HIGH_PAR)
    u, v = "n5", f"n{(5 * 7 + 3) % N}"
    want = gnx.get_edge_data(u, v)
    got = gfx.get_edge_data(u, v)
    assert list(got) == list(want)
    assert {k: dict(d) for k, d in got.items()} == {k: dict(d) for k, d in want.items()}


@pytest.mark.parametrize("cls_name", ["MultiGraph", "MultiDiGraph"])
def test_the_mapping_tracks_later_edge_additions(cls_name):
    """A cache must not serve a stale keydict after the graph grows.

    Separate from br-r37-c1-f3i50's liveness divergence, which is about a HELD
    reference: this asks only that a FRESH call sees a new parallel edge.
    """
    gnx = _build(nx, cls_name, 2)
    gfx = _build(fnx, cls_name, 2)
    u, v = "n5", f"n{(5 * 7 + 3) % N}"
    gfx.get_edge_data(u, v)  # warm the cache before mutating
    for graph in (gnx, gfx):
        graph.add_edge(u, v, weight=99.0)
    want = gnx.get_edge_data(u, v)
    got = gfx.get_edge_data(u, v)
    assert list(got) == list(want)
    assert {k: dict(d) for k, d in got.items()} == {k: dict(d) for k, d in want.items()}


@pytest.mark.parametrize("cls_name", ["MultiGraph", "MultiDiGraph"])
def test_the_mapping_tracks_edge_removal(cls_name):
    gnx = _build(nx, cls_name, 4)
    gfx = _build(fnx, cls_name, 4)
    u, v = "n5", f"n{(5 * 7 + 3) % N}"
    gfx.get_edge_data(u, v)
    for graph in (gnx, gfx):
        graph.remove_edge(u, v)
    want = gnx.get_edge_data(u, v)
    got = gfx.get_edge_data(u, v)
    assert list(got) == list(want)
    assert {k: dict(d) for k, d in got.items()} == {k: dict(d) for k, d in want.items()}
