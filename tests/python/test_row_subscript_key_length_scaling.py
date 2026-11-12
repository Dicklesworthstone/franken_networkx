"""br-r37-c1-0k6zl / br-r37-c1-2ndmw — row subscripts must stay BOUNDED in node-key length.

`G.adj[u][v]` and `G[u][v]` resolve an edge attribute mapping from two node keys.
networkx does two dict lookups on strings whose hash CPython caches in the
object, so its cost does not depend on how long those keys are. fnx canonicalises each endpoint, and where it
does that per subscript the cost tracks key length.

Measured on a commit-pinned HEAD build, `G.adj[u][v]`, 3- against
2000-character keys. The two effects are SEPARATE and only one class has both:

    class          K=3      K=2000   degradation
    Graph          0.5917   0.5570   1.06x  -- flat, has the row-index cache
    DiGraph        0.2906   0.0913   3.2x   -- key-length driven
    MultiGraph     0.2544   0.1742   1.46x  -- constant-factor loss
    MultiDiGraph   0.2403   0.1635   1.47x  -- constant-factor loss

Every class except Graph carries a CONSTANT ~0.25x loss at short keys, which is
br-r37-c1-2ndmw's missing native row view. Only DiGraph additionally DEGRADES
with key length, down to 0.0913x -- the worst cell this pane currently measures.

Simple `Graph` is the exception because `AdjacencyView.__getitem__` routes ONLY
`type(owner) is Graph` to the native `_fnx.AtlasView`, which caches the row's
node index once per `G.adj[u]` (br-r37-c1-ptiz2). Every other class takes the
Python `AtlasView`, which re-canonicalises both endpoints on every access.

WHY THIS ASSERTS GROWTH AND NOT A RATIO. A ratio threshold is a timing
assertion, and this pane has banked that absolute nanoseconds move 1.6x between
measurement windows and that a contended SMT sibling shifts a ratio by 17
percent. Growth across key length WITHIN one process is far more robust: both
points share a window, a core and a clock, so the common-mode factors divide out.
networkx is the in-process control — it should be flat in key length, and a
separate test fails if it is not, so a bad window invalidates the comparison
rather than convicting fnx.

THE BOUND WAS SET FROM MEASUREMENT, AFTER A GUESS FAILED. An earlier draft
assumed the unfixed classes grew "8-12x", set the bound at 4.0, and marked all
three `xfail(strict=True)` -- whereupon the multigraph params XPASSED, because
the guess was wrong and their growth is only ~1.5x. Relative growth measures
Graph 1.06-1.53x, MultiGraph 1.43-1.46x, MultiDiGraph 1.47-1.52x and DiGraph
3.2-3.44x, so the bound sits at 2.5x, between the two clusters.

`Graph` and both multigraph classes are asserted STRICTLY: Graph must not lose
its index cache, and the multigraphs must not START tracking key length, since
today their loss is a fixed per-call cost. Only `DiGraph` is `xfail(strict=True)`
-- the day it reaches an index-cached row view this file turns green loudly and
becomes that fix's acceptance gate.
"""

from __future__ import annotations

import statistics
import time

import networkx as nx
import pytest

import franken_networkx as fnx

N = 200
SHORT_KEY = 3
LONG_KEY = 2000
# MEASURED, not assumed -- an earlier draft of this file guessed "8-12x" for the
# unfixed classes, set the bound at 4.0, and the strict xfails XPASSED because the
# guess was wrong. Relative growth actually measures: Graph 1.06-1.53x, MultiGraph
# 1.43-1.46x, MultiDiGraph 1.47-1.52x, DiGraph 3.2-3.44x. Only DiGraph is
# genuinely key-length driven. The bound sits between the two clusters.
MAX_RELATIVE_GROWTH = 2.5

SUBSCRIPTS = {
    "G.adj[u][v]": lambda g, u, v: g.adj[u][v],
    "G[u][v]": lambda g, u, v: g[u][v],
}


def _build(lib, cls_name, key_len):
    nodes = [f"n{i}".ljust(key_len, "z") for i in range(N)]
    graph = getattr(lib, cls_name)()
    for i in range(N):
        graph.add_edge(nodes[i], nodes[(i * 7 + 3) % N], weight=1.0)
    return graph, nodes


def _time(graph, nodes, op, reps=4000, rounds=5):
    u, v = nodes[5], nodes[(5 * 7 + 3) % N]
    op(graph, u, v)  # warm
    samples = []
    for _ in range(rounds):
        start = time.perf_counter()
        for _ in range(reps):
            op(graph, u, v)
        samples.append((time.perf_counter() - start) / reps)
    return statistics.median(samples)


def _growth(lib, cls_name, op):
    short_graph, short_nodes = _build(lib, cls_name, SHORT_KEY)
    long_graph, long_nodes = _build(lib, cls_name, LONG_KEY)
    short = _time(short_graph, short_nodes, op)
    long = _time(long_graph, long_nodes, op)
    return long / short if short > 0 else float("inf")


def _relative(cls_name, op):
    nx_growth = _growth(nx, cls_name, op)
    fnx_growth = _growth(fnx, cls_name, op)
    return fnx_growth, nx_growth, (fnx_growth / nx_growth if nx_growth > 0 else float("inf"))


@pytest.mark.parametrize("op_name", sorted(SUBSCRIPTS))
def test_graph_row_subscript_is_bounded_in_key_length(op_name):
    """Simple Graph HAS the row-index cache and must not lose it.

    This is the strict half of the file: a regression here means the
    `type(owner) is Graph` route to the native AtlasView stopped being taken.
    """
    fnx_growth, nx_growth, relative = _relative("Graph", SUBSCRIPTS[op_name])
    assert relative < MAX_RELATIVE_GROWTH, (
        f"Graph {op_name}: fnx grew {fnx_growth:.1f}x across {SHORT_KEY}->{LONG_KEY} "
        f"character keys against networkx's {nx_growth:.1f}x (relative {relative:.1f}x, "
        f"bound {MAX_RELATIVE_GROWTH}x). br-r37-c1-ptiz2's row node-index cache "
        "appears to have stopped applying."
    )


@pytest.mark.parametrize("op_name", sorted(SUBSCRIPTS))
@pytest.mark.parametrize("cls_name", ["MultiGraph", "MultiDiGraph"])
def test_multigraph_rows_are_bounded_in_key_length(cls_name, op_name):
    """The multigraph classes are a CONSTANT-factor loss, not a growing one.

    They sit at 0.24-0.25x even with 3-character keys and only degrade to
    0.16-0.17x at 2000 characters -- 1.5x of growth, inside the bound. Their
    problem is br-r37-c1-2ndmw's missing native row view, which costs a fixed
    per-call amount; it is NOT the key-length blowup DiGraph shows. Asserted
    strictly so that if one of them ever starts growing, it is caught.
    """
    fnx_growth, nx_growth, relative = _relative(cls_name, SUBSCRIPTS[op_name])
    assert relative < MAX_RELATIVE_GROWTH, (
        f"{cls_name} {op_name}: fnx grew {fnx_growth:.1f}x against networkx's "
        f"{nx_growth:.1f}x (relative {relative:.1f}x) -- this class was a "
        "constant-factor loss and has started tracking key length"
    )


@pytest.mark.parametrize("op_name", sorted(SUBSCRIPTS))
# br-r37-c1-0k6zl FIXED: the strict xfail below is REMOVED, not relaxed.
#
# It read: "DiGraph rows re-canonicalise both endpoints per subscript, so cost
# tracks key length -- 0.2906x at 3 characters falling to 0.0913x at 2000."
# That is no longer true. `PyDiGraph` now carries the same endpoint-index
# lookaside `PyGraph` has, so `_fnx_edge_attr_dict_fast` — which the Python
# `AtlasView` calls on every subscript — answers from two `usize`s instead of
# re-canonicalising both endpoints three times over. `G.adj[u][v]` at 2000-char
# keys moved 0.0804x -> 0.4691x and `G[u][v]` -> 0.5990x.
#
# `strict=True` is what surfaced the fix: the params XPASSED and the suite went
# red rather than quietly passing an expected-failure. Leaving a strict xfail in
# place after the defect is gone would hide the next regression behind an
# expected failure, so it goes.
def test_digraph_rows_are_bounded_in_key_length(op_name):
    fnx_growth, nx_growth, relative = _relative("DiGraph", SUBSCRIPTS[op_name])
    assert relative < MAX_RELATIVE_GROWTH, (
        f"DiGraph {op_name}: fnx grew {fnx_growth:.1f}x against networkx's "
        f"{nx_growth:.1f}x (relative {relative:.1f}x)"
    )


@pytest.mark.parametrize("cls_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
def test_the_control_is_flat_in_key_length(cls_name):
    """networkx caches a str's hash, so its cost must not track key length.

    If this fails the host is lying and the companion assertions are unreadable
    — that is the point of measuring the control in the same process.
    """
    nx_growth = _growth(nx, cls_name, SUBSCRIPTS["G.adj[u][v]"])
    assert nx_growth < MAX_RELATIVE_GROWTH, (
        f"{cls_name}: networkx's own G.adj[u][v] grew {nx_growth:.1f}x across "
        f"{SHORT_KEY}->{LONG_KEY} character keys. CPython caches a str's hash, so "
        "this measurement is untrustworthy — re-run in a quieter window."
    )


@pytest.mark.parametrize("cls_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
def test_long_key_subscripts_are_still_correct(cls_name):
    """Boundedness is worthless if the fast path answers wrongly.

    Pins value and identity semantics at the long-key end, so a future index
    cache that resolved to the wrong row fails here rather than passing.
    """
    gnx, nodes = _build(nx, cls_name, LONG_KEY)
    gfx, _ = _build(fnx, cls_name, LONG_KEY)
    u, v = nodes[5], nodes[(5 * 7 + 3) % N]
    assert dict(gfx.adj[u][v]) == dict(gnx.adj[u][v])
    assert dict(gfx[u][v]) == dict(gnx[u][v])
    assert list(gfx.adj[u]) == list(gnx.adj[u])
    with pytest.raises(KeyError):
        gnx.adj[u]["absent".ljust(LONG_KEY, "z")]
    with pytest.raises(KeyError):
        gfx.adj[u]["absent".ljust(LONG_KEY, "z")]
