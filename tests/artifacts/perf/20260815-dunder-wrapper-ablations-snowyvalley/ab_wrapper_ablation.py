"""Wall-clock ablation: what does the PYTHON `__contains__` wrapper cost?

`python/franken_networkx/__init__.py` replaces `_fnx.EdgeView.__contains__`
with a Python function that adds networkx's permissive `e[:2]` semantics around
the native pymethod. This measures that wrapper, in ONE invocation, on ONE ELF,
with both arms present:

  incumbent  = the shipped wrapped `__contains__` (what users run today)
  candidate  = the native pymethod restored as the type's `__contains__`
  networkx   = live networkx 3.6.1, same fixture, same probe sequence

Same balanced ABBAABBA square and per-arm A/A nulls as
scripts/balanced_square_ab.py, so a busy host shows up as a failed null rather
than as a fake effect. The type attribute is swapped OUTSIDE every timed
region.

Ratios are reported as t_incumbent / t_candidate (>1 means the candidate is
faster) and t_networkx / t_arm for the vs-incumbent rows.
"""

import gc
import hashlib
import os
import platform
import random
import statistics
import sys
import time

import networkx as nx

import franken_networkx as fnx
import franken_networkx._fnx as ext

SQUARE = "ABBAABBA"
NULL_BOUND = 0.02
ROUNDS = int(os.environ.get("ROUNDS", "41"))
REPS = int(os.environ.get("REPS", "400"))
WARMUP = 8

NATIVE = ext.EdgeView.__contains__
if getattr(NATIVE, "__closure__", None) is not None:
    # Pre-dtrpe build: the shipped slot IS the wrapper, native is its closure.
    WRAPPED, NATIVE = NATIVE, NATIVE.__closure__[0].cell_contents
else:
    # Post-dtrpe build: the slot is native, so rebuild the OLD shipped path by
    # re-applying the module's own wrapper over it. Same function, same frame.
    WRAPPED = fnx._edgeview_contains_with_nx_semantics(NATIVE)


def build(module, nodes=2000, edges=8000, seed=11):
    rng = random.Random(seed)
    graph = module.Graph()
    names = [f"n{i}" for i in range(nodes)]
    graph.add_nodes_from((n, {"color": "r", "rank": i}) for i, n in enumerate(names))
    seen = set()
    while len(seen) < edges:
        a, b = rng.randrange(nodes), rng.randrange(nodes)
        if a == b:
            continue
        pair = (min(a, b), max(a, b))
        if pair in seen:
            continue
        seen.add(pair)
        graph.add_edge(names[pair[0]], names[pair[1]], weight=1.0)
    return graph, [(names[a], names[b]) for a, b in seen]


def time_slot(fn) -> int:
    gc.collect()
    gc.disable()
    try:
        start = time.perf_counter_ns()
        fn()
        return time.perf_counter_ns() - start
    finally:
        gc.enable()


def bootstrap_ci(values, iters=4000, seed=3):
    rng = random.Random(seed)
    n = len(values)
    medians = sorted(
        statistics.median(values[rng.randrange(n)] for _ in range(n))
        for _ in range(iters)
    )
    return medians[int(0.025 * iters)], medians[int(0.975 * iters)]


def run_row(label, a_setup, a_fn, b_setup, b_fn):
    for _ in range(WARMUP):
        a_setup()
        a_fn()
        b_setup()
        b_fn()
    ratios, null_a, null_b = [], [], []
    for _ in range(ROUNDS):
        a_slots, b_slots = [], []
        for slot in SQUARE:
            if slot == "A":
                a_setup()
                a_slots.append(time_slot(a_fn))
            else:
                b_setup()
                b_slots.append(time_slot(b_fn))
        ratios.append(statistics.median(a_slots) / statistics.median(b_slots))
        null_a.append(statistics.median(a_slots[:2]) / statistics.median(a_slots[2:]))
        null_b.append(statistics.median(b_slots[:2]) / statistics.median(b_slots[2:]))
    ratio = statistics.median(ratios)
    low, high = bootstrap_ci(ratios)
    n_a, n_b = statistics.median(null_a), statistics.median(null_b)
    ok = abs(n_a - 1.0) <= NULL_BOUND and abs(n_b - 1.0) <= NULL_BOUND
    verdict = (
        "NULL-FAILED"
        if not ok
        else ("STRADDLES-1" if low <= 1.0 <= high else "ADMISSIBLE")
    )
    print(
        f"  {label:34s} {ratio:7.4f}x  CI [{low:.4f}, {high:.4f}]  "
        f"nulls {n_a:.4f}/{n_b:.4f}  {verdict}"
    )
    return ratio, verdict


def main():
    with open(ext.__file__, "rb") as fh:
        elf_sha = hashlib.sha256(fh.read()).hexdigest()
    print("PROVENANCE (self-reported from inside the process)")
    print(f"  host                 {platform.node()}")
    print(f"  elf                  {ext.__file__}")
    print(f"  bench_elf_sha256={elf_sha}")
    print(f"  python               {platform.python_version()}")
    print(f"  incumbent_networkx   {nx.__version__}")
    print(f"  affinity_cpus        {len(os.sched_getaffinity(0))}")
    print(f"  loadavg_start        {os.getloadavg()}")
    print(f"  rounds/reps          {ROUNDS}/{REPS}")

    g_fx, edges_fx = build(fnx)
    g_nx, edges_nx = build(nx)
    rng = random.Random(7)
    probes = [edges_fx[rng.randrange(len(edges_fx))] for _ in range(REPS)]
    view_fx, view_nx = g_fx.edges, g_nx.edges

    def wrap():
        ext.EdgeView.__contains__ = WRAPPED

    def unwrap():
        ext.EdgeView.__contains__ = NATIVE

    def probe_fx():
        return sum(1 for p in probes if p in view_fx)

    # br-r37-c1-y4r63: the SAME probe content, but built from networkx's own
    # fixture, so every key object is the object networkx already has in its
    # adjacency dict. CPython's dict compares pointers before it compares
    # strings, so this arm gets an identity shortcut the shared-object arm
    # above denies it. fnx has no such shortcut either way: it canonicalises
    # and memcmps every probe.
    rng_nx = random.Random(7)
    probes_nx_own = [edges_nx[rng_nx.randrange(len(edges_nx))] for _ in range(REPS)]
    assert probes_nx_own == probes
    assert all(a is not b for a, b in zip(probes_nx_own[0], probes[0]))

    def probe_nx():
        return sum(1 for p in probes if p in view_nx)

    def probe_nx_own_objects():
        return sum(1 for p in probes_nx_own if p in view_nx)

    def noop():
        return None

    # Parity gate before timing: every arm must answer identically.
    wrap()
    assert probe_fx() == REPS == probe_nx()
    unwrap()
    assert probe_fx() == REPS
    wrap()

    print(f"\nsquare={SQUARE}  null bound +/-{NULL_BOUND}")
    print("  RATIO t_wrapped / t_native   (>1 means dropping the wrapper is faster)")
    run_row("wrapped -> native", wrap, probe_fx, unwrap, probe_fx)
    print("  RATIO t_networkx / t_fnx     (>1 means fnx faster)")
    run_row("nx vs fnx WRAPPED (shipped)", noop, probe_nx, wrap, probe_fx)
    run_row("nx vs fnx NATIVE (ablated)", noop, probe_nx, unwrap, probe_fx)
    run_row("nx(own objs) vs fnx NATIVE", noop, probe_nx_own_objects, unwrap, probe_fx)
    run_row("nx shared objs vs nx own objs", noop, probe_nx, noop, probe_nx_own_objects)
    # Control: an A/A of the incumbent against itself must land on 1.0.
    run_row("CONTROL nx vs nx", noop, probe_nx, noop, probe_nx)
    wrap()
    print(f"  loadavg_end          {os.getloadavg()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
