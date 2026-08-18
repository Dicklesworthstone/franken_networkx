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

import franken_networkx as fnx

# Operations that SHOULD scale, with the scan in PYTHON. They are the positive
# controls: if they ever read flat, the probe has stopped measuring.
CONTROLS = {"len(restricted_view)", "list(view)[:2]"}

# The negative control, and the tool's own caveat made executable: an all-node
# request whose scan lives in RUST. It reads flat, which is the correct answer to
# "does the shim loop over the parent" and the wrong answer to "is this O(1)".
NATIVE_SCAN_EXHIBITS = {"dict(G.degree())"}


def build(cls: str, n: int):
    graph = getattr(fnx, cls)()
    for i in range(n):
        graph.add_edge("n%d" % i, "n%d" % ((i + 1) % n), w=i)
    return graph


def total_calls(fn, reps: int) -> int:
    """Total Python-level calls for ``reps`` invocations, warm."""
    fn()  # warm caches so a first-call materialisation is not counted as scaling
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
    args = ap.parse_args(argv[1:])

    small, large = args.sizes
    if large <= small:
        print("LARGE must exceed SMALL", file=sys.stderr)
        return 2
    size_ratio = large / small

    counts: dict[str, list[int]] = {}
    for n in (small, large):
        graph = build(args.cls, n)
        for label, thunk in operations(graph):
            counts.setdefault(label, []).append(total_calls(thunk, args.reps))

    print(f"class={args.cls} sizes={small}->{large} (x{size_ratio:g}) reps={args.reps}")
    print(f"{'operation':<24}{'calls@' + str(small):>12}{'calls@' + str(large):>12}{'ratio':>8}  verdict")
    findings = 0
    for label, (a, b) in counts.items():
        ratio = b / max(a, 1)
        if ratio > 2.0:
            verdict = "SCALES (expected)" if label in CONTROLS else "SCALES <-- FINDING"
            if label not in CONTROLS:
                findings += 1
        elif ratio < 1.3:
            verdict = (
                "flat (scan is NATIVE - not O(1))"
                if label in NATIVE_SCAN_EXHIBITS
                else "flat"
            )
        else:
            verdict = "mild"
        print(f"{label:<24}{a:>12}{b:>12}{ratio:>8.2f}  {verdict}")

    for label in CONTROLS:
        if label in counts:
            a, b = counts[label]
            if b / max(a, 1) <= 2.0:
                print(
                    f"\nNOTE: positive control {label!r} did NOT scale (ratio "
                    f"{b / max(a, 1):.2f}). Either it was optimised - in which "
                    "case move it out of CONTROLS - or the probe has stopped "
                    "measuring and every 'flat' above is meaningless."
                )
    for label in NATIVE_SCAN_EXHIBITS:
        if label in counts:
            a, b = counts[label]
            if b / max(a, 1) > 2.0:
                print(
                    f"\nNOTE: {label!r} now scales in PYTHON (ratio "
                    f"{b / max(a, 1):.2f}). It used to be served by a native "
                    "scan; a shim-level walk has appeared under it."
                )

    print(f"\n{findings} finding(s).")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
