#!/usr/bin/env python3
"""Per-call scaling probe for batch mutators — the br-r37-c1-uta2n diagnostic.

WHAT IT ANSWERS. A batch entry point that materialises the whole node set on
every call costs O(N) per call no matter how few items the call carries. That is
invisible in a whole-build benchmark, because a single large batch amortises it
away; it shows up as a cliff when callers batch in small chunks. This probe
separates the two by measuring the per-call cost DIRECTLY at a known graph size.

It found four such defects in `add_edges_from` collectors (br-r37-c1-uta2n,
-hepb5, -ab5u7, -iozi3, k=8 costs of 15-18 us/edge falling to 0.6-1.5 us) and
correctly cleared five other collectors that did not have it (-09irv, -b1z21,
-lka35). Full evidence in docs/NEGATIVE_EVIDENCE.md.

THE SIGNATURE. Defective: per-call cost scales with NODE count and is flat in
EDGE count (measured x15.2-x19.3 in nodes, x1.0 in edges). Clean: flat in both
(x1.0-x1.2). Edge-count growth alone is a different question and not this defect.

THE ACCEPTANCE TEST, which is the reason this is a committed script rather than a
scratch file. A fix is proven when the largest-N figure STOPS TRACKING N. An
improved chunk-size-8 number on its own is NOT sufficient: amortisation changes
produce that without removing the pass. Several beads name this test as their
gate; run `--mode scaling` before and after and compare the final ratio column.

This is deliberately a shape test, not a ratio test, and that choice is forced by
a repeatedly observed property of MUTATION workloads on this repo's balanced-square
A/A substrate: their arms are not stationary within a round, so the A/A null blows
out and the pair cannot be cleanly timed. Three independent instances, all
mutation loops, all caught only because a null was carried:

  * chunked add_edges_from, k=8 arm            null 1.4966x, then 1.4447x after
                                               raising warm-up 2 -> 8 iterations
  * per-call add_node loop vs add_nodes_from   null 1.3255x on the loop arm

In each case the UNNULLED version of the same comparison produced a confident,
plausible, publishable-looking number — and in the add_node case the sign
reversed between runs (36% slower unnulled, 7% faster nulled). Treat any
mutation-arm A/B on this substrate as inadmissible until its own A/A null is
shown to sit near 1.0.

A scaling-SHAPE result survives all of that, because it asks what the cost
DEPENDS ON rather than how two arms compare: a x19.30 -> x1.10 change in
node-scaling cannot be manufactured by an arm that drifts within a round.

USAGE
    python3 scripts/batch_call_scaling_probe.py --mode chunk    # find the cliff
    python3 scripts/batch_call_scaling_probe.py --mode scaling  # N vs E: the gate
    python3 scripts/batch_call_scaling_probe.py --graph MultiDiGraph --shape attributed

Set FNX_EXTENSION_PATH to pin the exact `_fnx` ELF under test; the loaded
artifact's SHA-256 is printed as line one, because a shell hash next to the run
does not prove which binary the process loaded.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import os
import random
import statistics
import sys
import time

if (_requested := os.environ.get("FNX_EXTENSION_PATH")) is not None:
    _spec = importlib.util.spec_from_file_location("franken_networkx._fnx", _requested)
    if _spec is None or _spec.loader is None:
        raise ImportError(f"cannot load an extension from {_requested}")
    _mod = importlib.util.module_from_spec(_spec)
    sys.modules["franken_networkx._fnx"] = _mod
    _spec.loader.exec_module(_mod)

import franken_networkx as fnx  # noqa: E402

CHUNKS = (1, 2, 4, 6, 7, 8, 9, 12, 16, 32, 64)
NODE_SWEEP = (500, 1000, 2000, 4000, 8000)
EDGE_SWEEP = (1000, 4000, 16000)
# The node sweep holds edges at this value and the edge sweep holds nodes at
# this one. They are named rather than indexed out of the sweep tuples: an
# earlier revision used EDGE_SWEEP[1] (4,000) for the node sweep while every
# published acceptance-test row in docs/NEGATIVE_EVIDENCE.md cites 8,000, so a
# reader reproducing those numbers would have measured a different workload and
# could have concluded the fixes did not hold.
FIXED_EDGES = 8000
FIXED_NODES = 2000


def _elf_sha256() -> str:
    import franken_networkx._fnx as ext

    digest = hashlib.sha256()
    with open(ext.__file__, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def make_edges(n: int, count: int, shape: str, directed: bool, seed: int = 11):
    """Distinct endpoint pairs in the requested tuple shape."""
    rng = random.Random(seed)
    seen: set = set()
    out: list = []
    while len(out) < count:
        u, v = rng.randrange(n), rng.randrange(n)
        if u == v:
            continue
        key = (u, v) if directed else (min(u, v), max(u, v))
        if key in seen:
            continue
        seen.add(key)
        su, sv = str(u), str(v)
        if shape == "plain":
            out.append((su, sv))
        elif shape == "attributed":
            out.append((su, sv, {"weight": rng.randint(1, 20)}))
        else:  # keyed
            out.append((su, sv, len(out), {"weight": rng.randint(1, 20)}))
    return out


def build(cls, nodes, edges, chunk):
    graph = cls()
    graph.add_nodes_from(nodes)
    for index in range(0, len(edges), chunk):
        graph.add_edges_from(edges[index : index + chunk])
    return graph


def median_ns_per_edge(fn, total, reps):
    for _ in range(2):
        fn()
    samples = []
    for _ in range(reps):
        start = time.perf_counter_ns()
        fn()
        samples.append((time.perf_counter_ns() - start) / total)
    return statistics.median(samples)


def mode_chunk(cls, shape, directed, n, m, reps):
    """Sweep chunk size. A step at k=8 is the PLAIN_EDGE_BATCH_MIN cliff."""
    edges = make_edges(n, m, shape, directed)
    nodes = [str(i) for i in range(n)]
    reference = build(cls, nodes, edges, m)
    ref_edges = list(reference.edges)
    print(f"\nchunk sweep  N={n} E={m}")
    for chunk in (*CHUNKS, m):
        got = build(cls, nodes, edges, chunk)
        # Order is the parity contract these fixes must not disturb.
        assert list(got.edges) == ref_edges, f"chunk {chunk} changed edge ORDER"
        cost = median_ns_per_edge(lambda c=chunk: build(cls, nodes, edges, c), m, reps)
        print(f"  k={chunk:<6d} {cost:9.1f} ns/edge", flush=True)


def _per_call(cls, shape, directed, n, e, chunk, calls, reps):
    """Cost of `calls` successive chunk-sized calls on a graph already at (n, e)."""
    base = make_edges(n, e + chunk * calls, shape, directed)
    seed_edges, extra = base[:e], base[e:]
    nodes = [str(i) for i in range(n)]
    samples = []
    for _ in range(reps):
        graph = cls()
        graph.add_nodes_from(nodes)
        graph.add_edges_from(seed_edges)
        start = time.perf_counter_ns()
        for index in range(0, chunk * calls, chunk):
            graph.add_edges_from(extra[index : index + chunk])
        samples.append((time.perf_counter_ns() - start) / (chunk * calls))
    return statistics.median(samples)


def mode_scaling(cls, shape, directed, chunk, calls, reps):
    """THE ACCEPTANCE TEST. O(N) and flat in E is the defect signature."""
    print(f"\nA) vary NODES, edges fixed {FIXED_EDGES}, k={chunk}")
    first = None
    for n in NODE_SWEEP:
        cost = _per_call(cls, shape, directed, n, FIXED_EDGES, chunk, calls, reps)
        first = first if first is not None else cost
        print(f"   N={n:<6d} {cost:9.1f} ns/edge   x{cost / first:.2f} vs N={NODE_SWEEP[0]}",
              flush=True)
    print(f"\nB) vary EDGES, nodes fixed {FIXED_NODES}, k={chunk}")
    first = None
    for e in EDGE_SWEEP:
        cost = _per_call(cls, shape, directed, FIXED_NODES, e, chunk, calls, reps)
        first = first if first is not None else cost
        print(f"   E={e:<6d} {cost:9.1f} ns/edge   x{cost / first:.2f} vs E={EDGE_SWEEP[0]}",
              flush=True)
    print("\n  PASS when the final A) ratio is near x1 — the cost must STOP TRACKING N.")
    print("  A better k=8 number alone does not pass: amortisation gives that for free.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--mode", choices=("chunk", "scaling"), default="scaling")
    parser.add_argument("--graph", default="Graph",
                        choices=("Graph", "DiGraph", "MultiGraph", "MultiDiGraph"))
    parser.add_argument("--shape", default="plain",
                        choices=("plain", "attributed", "keyed"))
    parser.add_argument("--chunk", type=int, default=8)
    parser.add_argument("--calls", type=int, default=100)
    parser.add_argument("--nodes", type=int, default=2000)
    parser.add_argument("--edges", type=int, default=8000)
    parser.add_argument("--reps", type=int, default=9)
    args = parser.parse_args(argv)

    if args.shape == "keyed" and not args.graph.startswith("Multi"):
        parser.error("the keyed (u, v, key, dict) shape only applies to multigraphs")

    cls = getattr(fnx, args.graph)
    directed = "Di" in args.graph

    print(f"bench_elf_sha256={_elf_sha256()}")
    print(f"{args.graph} / {args.shape}   loadavg={os.getloadavg()[0]:.2f}")
    if args.mode == "chunk":
        mode_chunk(cls, args.shape, directed, args.nodes, args.edges, args.reps)
    else:
        mode_scaling(cls, args.shape, directed, args.chunk, args.calls, args.reps)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
