"""Same-invocation A/B for br-r37-c1-l7ww9: the `len(G)` private-override wrapper.

incumbent = the pre-change shipped path, rebuilt by re-installing the exact
            Python wrapper (`_private_aware_len`'s body) over the native slot
candidate = the native slot, which now consults the assigned `_node` mapping
            itself behind a bool
networkx  = live networkx 3.6.1, same fixture, same invocation

Balanced ABBAABBA square with per-arm A/A nulls, same design as
scripts/balanced_square_ab.py. The class attribute is rebound OUTSIDE every
timed region.
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
ROUNDS = int(os.environ.get("ROUNDS", "61"))
REPS = int(os.environ.get("REPS", "400"))
WARMUP = 8

NATIVE_LEN = ext.Graph.__len__
_PRIVATE_MISSING = fnx._PRIVATE_MISSING
_PRIVATE_NODE_OVERRIDE = fnx._PRIVATE_NODE_OVERRIDE


def _wrapped_len(raw_len):
    """Byte-for-byte the wrapper that was installed before this change."""

    def __len__(self):
        node_mapping = fnx._private_override(self, _PRIVATE_NODE_OVERRIDE)
        if node_mapping is not _PRIVATE_MISSING:
            return len(node_mapping)
        return raw_len(self)

    return __len__


WRAPPED_LEN = _wrapped_len(NATIVE_LEN)


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
    return graph


def time_slot(fn):
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
        "NULL-FAILED" if not ok else ("STRADDLES-1" if low <= 1.0 <= high else "ADMISSIBLE")
    )
    print(
        f"  {label:34s} {ratio:7.4f}x  CI [{low:.4f}, {high:.4f}]  "
        f"nulls {n_a:.4f}/{n_b:.4f}  {verdict}"
    )


def main():
    with open(ext.__file__, "rb") as fh:
        elf_sha = hashlib.sha256(fh.read()).hexdigest()
    print("PROVENANCE (self-reported from inside the process)")
    print(f"  host                 {platform.node()}")
    print(f"  bench_elf_sha256={elf_sha}")
    print(f"  incumbent_networkx   {nx.__version__}   python {platform.python_version()}")
    print(f"  affinity_cpus        {len(os.sched_getaffinity(0))}")
    print(f"  loadavg_start        {os.getloadavg()}   rounds/reps {ROUNDS}/{REPS}")

    g_fx, g_nx = build(fnx), build(nx)

    def wrap():
        ext.Graph.__len__ = WRAPPED_LEN

    def unwrap():
        ext.Graph.__len__ = NATIVE_LEN

    def noop():
        return None

    def len_fx():
        return sum(len(g_fx) for _ in range(REPS))

    def len_nx():
        return sum(len(g_nx) for _ in range(REPS))

    wrap()
    assert len_fx() == len_nx() == 2000 * REPS
    unwrap()
    assert len_fx() == 2000 * REPS

    print(f"\nsquare={SQUARE}  null bound +/-{NULL_BOUND}")
    print("  RATIO t_wrapped / t_native   (>1 means dropping the wrapper is faster)")
    run_row("len(G): wrapped -> native", wrap, len_fx, unwrap, len_fx)
    print("  RATIO t_networkx / t_fnx     (>1 means fnx faster)")
    run_row("nx vs fnx WRAPPED (before)", noop, len_nx, wrap, len_fx)
    run_row("nx vs fnx NATIVE (after)", noop, len_nx, unwrap, len_fx)
    run_row("CONTROL nx vs nx", noop, len_nx, noop, len_nx)
    unwrap()
    print(f"  loadavg_end          {os.getloadavg()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
