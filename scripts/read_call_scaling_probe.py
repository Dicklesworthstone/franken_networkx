#!/usr/bin/env python3
"""Read-side scaling probe: hold the REQUEST fixed, grow the PARENT, count CALLS.

WHAT IT ANSWERS, and how it differs from the probe next to it.
``batch_call_scaling_probe.py`` asks whether a BATCH MUTATOR's per-call cost
tracks the node count, and it answers in microseconds. This one asks whether a
small READ - one node's degree, one edge lookup, a two-node subgraph - drags in
work proportional to the whole graph, and it answers in CALL COUNTS.

Counting rather than timing is the point, not a compromise:

  * it is LOAD-INDEPENDENT. This repo's host routinely sits at loadavg 15-30 with
    a dozen agents on it, and the campaign's own ledger records timing verdicts
    inverting under load. A call count does not move when a neighbour starts a
    build, so this probe stays admissible in windows where no ratio is.
  * it survives a BUILD FREEZE, when benchmarking is banned outright.
  * a complexity defect is a SHAPE, and the shape is what the count shows. An
    operation that materialises the parent shows ratio ~= the size ratio; one
    that does not shows ~1.0. There is no interval to argue about.

IT ONLY SEES PYTHON. This is the limitation that matters most, and the sweep
below demonstrates it rather than merely asserting it: ``dict(G.degree())`` walks
every node and reads FLAT, because that walk happens inside Rust and cProfile
counts Python-level calls only. So "flat" means "no PYTHON-level scan of the
parent" - NOT "O(1)". A native kernel that scans the whole graph is invisible
here by construction, and that is exactly the kind of work this repo pushes into
Rust on purpose.

Read a flat verdict as: whatever this costs, the shim is not looping over the
parent to produce it. That is the question the probe answers, and it is worth
answering because the shim IS where this campaign's O(parent) cliffs have been.

It also cannot tell you a ratio against networkx, and is not meant to. Constant
factors are invisible - an operation doing 100 flat Python calls and one doing 5
both read as "flat". Use it to find O(parent) cliffs; use the balanced-square
substrate for ratios.

READING THE OUTPUT. ``ratio`` is calls at the large size divided by calls at the
small one, for the SAME request. With sizes 200 and 800 a defect reads ~4.0.

    flat   (< 1.3)   the request does not scan the parent
    mild   (1.3-2.0) worth a look; often a hash-table resize or a cache miss
    SCALES (> 2.0)   the request touches work proportional to the parent

TWO OPERATIONS SCALE FOR SOUND REASONS and are included as CONTROLS rather than
filtered out, because a probe whose every row is "flat" teaches the reader
nothing about what a real hit looks like:

  * ``len(restricted_view)`` - a non-default node filter has to ask the predicate
    about every node. O(N) is the contract. What this probe DID catch here is the
    per-node cost: it must be ~1 predicate call per node, and it is (measured
    1.00). Before br-r37-c1-h0t5k the same walk paid three Python frames per node.
  * ``list(view)[:2]`` - ``list()`` consumes the whole iterator before the slice.
    Inherent to the expression, not to the view.

A THIRD, ``dict(G.degree())``, is carried as the negative control described
above: an all-node request that reads FLAT because its scan is native. It is
labelled in the output so nobody mistakes it for an O(1) operation.

If a row that is not one of those reads SCALES, that is a finding.

USAGE

    scripts/read_call_scaling_probe.py                 # default sweep
    scripts/read_call_scaling_probe.py --sizes 100 1600
    scripts/read_call_scaling_probe.py --class MultiDiGraph --reps 40
"""

from __future__ import annotations

import argparse
import cProfile
import pstats
import sys
import tracemalloc

import franken_networkx as fnx

# Operations that SHOULD scale, with the scan in PYTHON. They are the positive
# controls: if they ever read flat, the probe has stopped measuring.
CONTROLS = {"len(restricted_view)", "list(view)[:2]"}

# The negative control, and the tool's own caveat made executable: an all-node
# request whose scan lives in RUST. It reads flat, which is the correct answer to
# "does the shim loop over the parent" and the wrong answer to "is this O(1)".
NATIVE_SCAN_EXHIBITS = {"dict(G.degree())"}

# Under --metric allocations the question changes. An operation whose RESULT is
# O(parent) MUST allocate O(parent) - that is not a defect, it is the answer
# being big. These are expected to scale on that metric and only on it.
RESULT_SCALES_WITH_PARENT = {"dict(G.degree())", "list(view)[:2]", "len(restricted_view)"}


def build(cls: str, n: int, axis: str = "nodes"):
    """``axis="nodes"`` grows the node count; ``axis="multiplicity"`` does not.

    The multiplicity axis holds the NODE count fixed and piles parallel edges
    onto pairs the probed request never touches. A read about node ``n0`` that
    grows when unrelated pair ``n7-n8`` gains 400 parallel edges is scanning the
    edge set. Only multigraphs can carry parallel edges, so on the simple classes
    this axis grows the edge count between fixed nodes instead, which is still
    the right question: does a per-node read track the global edge count?
    """
    graph = getattr(fnx, cls)()
    if axis == "nodes":
        for i in range(n):
            graph.add_edge("n%d" % i, "n%d" % ((i + 1) % n), w=i)
        return graph
    for i in range(60):
        graph.add_edge("n%d" % i, "n%d" % ((i + 1) % 60), w=i)
    # bulk of the edges land on a pair the probed reads never mention
    if graph.is_multigraph():
        for k in range(n):
            graph.add_edge("n40", "n41", w=k)
    else:
        for k in range(n):
            graph.add_edge("far%d" % k, "far%d" % (k + 1), w=k)
    return graph


class Unsupported(Exception):
    """The operation does not apply to this graph class."""


def total_allocations(fn, reps: int) -> int:
    """Bytes allocated through the Python allocator for ``reps`` invocations.

    br-r37-c1-6tuw8: the companion to the call metric, and it exists to cover
    that metric's blind spot. A native kernel that materialises a Vec<PyObject>
    of every node costs ZERO Python-level calls and is invisible to cProfile -
    but every one of those PyObjects comes from the Python allocator, so
    tracemalloc sees it. `number_of_selfloops` building a node list purely to
    take its length is precisely this shape (br-r37-c1-hkijj).

    NOISY, AND THE NOISE PRODUCED THREE FALSE FINDINGS before this was calibrated.
    Every one looked like a textbook defect and every one was disproved by
    re-measuring across five sizes at higher reps:

        next(iter(G))                  x2.63  -> flat 98-196 B, 200..3200 nodes
        G.edge_subgraph(one_edge)      x1.32  -> non-monotonic 997..3176 B
        list(G.edges([u],data=True))   x3.45  -> flat 25.9/26.4/25.2/70.5 B

    The allocator's fill state moves these numbers far more than the operations
    do. So this metric now runs 5x the reps AND takes the MINIMUM of two
    independent replicates per cell, which suppresses the upward noise that
    caused all three. Treat a surviving finding as a lead to confirm across
    several sizes by hand - as above - never as a result on its own.
    """
    try:
        fn()
    except Exception as exc:  # noqa: BLE001 - class-inapplicable, same as total_calls
        raise Unsupported(type(exc).__name__) from exc

    def once() -> int:
        tracemalloc.start()
        before = tracemalloc.get_traced_memory()[0]
        for _ in range(reps):
            fn()
        after, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        return max(after - before, peak - before, 0)

    # min of two replicates: allocator noise is one-sided (it inflates), so the
    # smaller of two runs is much closer to the real cost than either alone.
    return min(once(), once())


def total_calls(fn, reps: int) -> int:
    """Total Python-level calls for ``reps`` invocations, warm.

    An operation the class does not implement is REPORTED, not fatal: a sweep
    that aborts on the first NetworkXNotImplemented hides every row after it,
    which is how a crash on `common_neighbors` for DiGraph cost a whole class's
    results the first time this ran.
    """
    try:
        fn()  # warm; a first-call materialisation must not read as scaling
    except Exception as exc:  # noqa: BLE001 - any class-inapplicable error
        raise Unsupported(type(exc).__name__) from exc
    profiler = cProfile.Profile()
    profiler.enable()
    for _ in range(reps):
        fn()
    profiler.disable()
    return sum(nc for (_cc, nc, _tt, _ct, _cs) in pstats.Stats(profiler).stats.values())


def operations(graph):
    """(label, thunk) pairs: each thunk is a FIXED-size request."""
    u, v = "n0", "n1"
    keep = [str(x) for x in list(graph)[:3]]
    one_edge = [tuple(map(str, e)) for e in list(graph.edges(keys=True) if graph.is_multigraph() else graph.edges())[:1]]
    hide = [str(x) for x in list(graph)[:1]]
    subgraph = graph.subgraph(keep)
    restricted = fnx.restricted_view(graph, hide, [])
    as_view = graph.copy(as_view=True)
    ops = [
        ("G[u]", lambda: graph[u]),
        ("u in G", lambda: u in graph),
        ("len(G)", lambda: len(graph)),
        ("G.degree(u)", lambda: graph.degree(u)),
        ("list(G.neighbors(u))", lambda: list(graph.neighbors(u))),
        ("G.has_edge(u,v)", lambda: graph.has_edge(u, v)),
        ("G.subgraph([u,v])", lambda: graph.subgraph([u, v])),
        ("list(G.edges([u]))", lambda: list(graph.edges([u]))),
        ("G.nodes[u]", lambda: graph.nodes[u]),
        ("G.get_edge_data(u,v)", lambda: graph.get_edge_data(u, v)),
        ("G.edges[u,v]", lambda: graph.edges[(u, v)] if not graph.is_multigraph() else graph.edges[(u, v, 0)]),
        ("G.adj[u]", lambda: graph.adj[u]),
        ("len(G.nodes)", lambda: len(graph.nodes)),
        ("len(G.edges)", lambda: len(graph.edges)),
        ("len(G.adj)", lambda: len(graph.adj)),
        ("G.number_of_edges()", lambda: graph.number_of_edges()),
        ("G.number_of_edges(u,v)", lambda: graph.number_of_edges(u, v)),
        ("next(iter(G))", lambda: next(iter(graph))),
        ("list(G.nbunch_iter([u]))", lambda: list(graph.nbunch_iter([u]))),
        ("list(G.edges([u],data=True))", lambda: list(graph.edges([u], data=True))),
        ("G.edge_subgraph(one_edge)", lambda: graph.edge_subgraph(one_edge)),
        ("fnx.degree(G,u)", lambda: fnx.degree(graph, u)),
        ("list(fnx.neighbors(G,u))", lambda: list(fnx.neighbors(graph, u))),
        ("list(fnx.common_neighbors)", lambda: list(fnx.common_neighbors(graph, u, v))),
        ("G.nodes[u] write", lambda: graph.nodes[u].get("w")),
        ("subgraph.has_edge", lambda: subgraph.has_edge(keep[0], keep[1])),
        ("as_view[u]", lambda: as_view[u]),
        ("restricted_view.degree(u)", lambda: restricted.degree(v)),
        ("subgraph.degree(u)", lambda: subgraph.degree(u)),
        ("subgraph[u]", lambda: subgraph[keep[1]]),
        ("len(subgraph)", lambda: len(subgraph)),
        ("as_view.degree(u)", lambda: as_view.degree(u)),
        ("len(as_view)", lambda: len(as_view)),
        ("u in restricted_view", lambda: u in restricted),
        ("restricted_view[u]", lambda: restricted[v]),
        # controls - these SHOULD scale
        ("len(restricted_view)", lambda: len(restricted)),
        ("list(view)[:2]", lambda: list(as_view)[:2]),
        ("dict(G.degree())", lambda: dict(graph.degree())),
    ]
    if not graph.is_multigraph():
        ops.insert(1, ("G[u][v]", lambda: graph[u][v]))
    return ops


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sizes", nargs=2, type=int, default=[200, 800], metavar=("SMALL", "LARGE"))
    ap.add_argument("--class", dest="cls", default="Graph")
    ap.add_argument("--reps", type=int, default=20)
    ap.add_argument(
        "--metric",
        choices=("calls", "allocations"),
        default="calls",
        help="calls sees only Python frames; allocations also sees native PyObjects",
    )
    ap.add_argument(
        "--axis",
        choices=("nodes", "multiplicity"),
        default="nodes",
        help="what to grow: the node count, or unrelated edge multiplicity",
    )
    args = ap.parse_args(argv[1:])

    small, large = args.sizes
    if large <= small:
        print("LARGE must exceed SMALL", file=sys.stderr)
        return 2
    size_ratio = large / small

    counts: dict[str, list[int]] = {}
    unsupported: dict[str, str] = {}
    for n in (small, large):
        graph = build(args.cls, n, axis=args.axis)
        for label, thunk in operations(graph):
            # allocations need more reps to clear allocator noise (see the
            # docstring: 20 reps produced a phantom x2.63 on next(iter(G)))
            measure = total_calls if args.metric == "calls" else total_allocations
            reps = args.reps if args.metric == "calls" else args.reps * 5
            try:
                counts.setdefault(label, []).append(measure(thunk, reps))
            except Unsupported as exc:
                unsupported[label] = str(exc)
                counts.pop(label, None)

    print(
        f"class={args.cls} metric={args.metric} axis={args.axis} "
        f"sizes={small}->{large} (x{size_ratio:g}) reps={args.reps}"
    )
    unit = "calls" if args.metric == "calls" else "bytes"
    print(
        f"{'operation':<24}{unit + '@' + str(small):>12}"
        f"{unit + '@' + str(large):>12}{'ratio':>8}  verdict"
    )
    findings = 0
    for label, ab in counts.items():
        if len(ab) != 2:
            continue
        a, b = ab
        ratio = b / max(a, 1)
        expected = (
            CONTROLS if args.metric == "calls" else RESULT_SCALES_WITH_PARENT
        )
        if ratio > 2.0:
            verdict = "SCALES (expected)" if label in expected else "SCALES <-- FINDING"
            if label not in expected:
                findings += 1
        elif ratio < 1.3:
            verdict = (
                "flat (scan is NATIVE - not O(1))"
                if label in NATIVE_SCAN_EXHIBITS and args.metric == "calls"
                else "flat"
            )
        else:
            verdict = "mild"
        print(f"{label:<24}{a:>12}{b:>12}{ratio:>8.2f}  {verdict}")

    for label in (CONTROLS if args.axis == "nodes" else ()):
        if label in counts and len(counts[label]) == 2:
            a, b = counts[label]
            if b / max(a, 1) <= 2.0:
                print(
                    f"\nNOTE: positive control {label!r} did NOT scale (ratio "
                    f"{b / max(a, 1):.2f}). Either it was optimised - in which "
                    "case move it out of CONTROLS - or the probe has stopped "
                    "measuring and every 'flat' above is meaningless."
                )
    for label in (NATIVE_SCAN_EXHIBITS if args.metric == "calls" else ()):
        if label in counts and len(counts[label]) == 2:
            a, b = counts[label]
            if b / max(a, 1) > 2.0:
                print(
                    f"\nNOTE: {label!r} now scales in PYTHON (ratio "
                    f"{b / max(a, 1):.2f}). It used to be served by a native "
                    "scan; a shim-level walk has appeared under it."
                )

    for label, why in sorted(unsupported.items()):
        print(f"{label:<24}{'n/a':>12}{'n/a':>12}{'':>8}  not implemented for this class ({why})")

    print(f"\n{findings} finding(s).")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
