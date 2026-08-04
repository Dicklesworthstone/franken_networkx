#!/usr/bin/env python3
"""A/B for read_edgelist: fnx vs live nx 3.6.1, plus an fnx thread sweep.

Discipline (matches scripts/parallel_analytics_pass.py):
  * nx is imported and run live in the same invocation; no archived baseline.
  * Arms are interleaved INSIDE one replicate loop so drift hits both equally.
  * An A/A null (same engine, both arms) runs first; the A/B effect is only
    reported against that null's spread. Coefficient of variation is not used.
  * Significance is a bootstrap CI on the MEDIAN ratio.
  * cpu/wall is recorded per timing: it is the parallelism evidence.

The thread sweep runs as subprocesses because RAYON_NUM_THREADS must be set
before the pool initialises.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import statistics
import subprocess
import sys
import time


def timed(fn):
    """Wall and process-CPU for one call. cpu/wall > 1 means real parallelism."""
    c0, w0 = time.process_time(), time.perf_counter()
    value = fn()
    wall = time.perf_counter() - w0
    cpu = time.process_time() - c0
    return wall, cpu, value


def bootstrap_ci(ratios, iters=20000, alpha=0.05, seed=20260801):
    rng = random.Random(seed)
    n = len(ratios)
    meds = []
    for _ in range(iters):
        meds.append(statistics.median(rng.choices(ratios, k=n)))
    meds.sort()
    lo = meds[int(alpha / 2 * iters)]
    hi = meds[min(iters - 1, int((1 - alpha / 2) * iters))]
    return lo, hi


def paired(fn_a, fn_b, reps):
    """Interleave A and B inside one loop, alternating which runs first."""
    a_t, b_t, a_cpu, b_cpu = [], [], [], []
    for i in range(reps):
        if i % 2 == 0:
            wa, ca, _ = timed(fn_a)
            wb, cb, _ = timed(fn_b)
        else:
            wb, cb, _ = timed(fn_b)
            wa, ca, _ = timed(fn_a)
        a_t.append(wa)
        b_t.append(wb)
        a_cpu.append(ca / wa if wa else 0)
        b_cpu.append(cb / wb if wb else 0)
    return a_t, b_t, a_cpu, b_cpu


def role_worker(args):
    import networkx as nx

    import franken_networkx as fnx

    path = f"graphs/{args.graph}.txt.gz"
    fnx_read = lambda: fnx.read_edgelist(path)  # noqa: E731
    nx_read = lambda: nx.read_edgelist(path)  # noqa: E731

    # warm: first touch pays page-cache + rayon pool spin-up
    fnx_read()
    nx_read()

    out = {
        "graph": args.graph,
        "threads": int(os.environ.get("RAYON_NUM_THREADS", "0")) or None,
        "reps": args.reps,
    }

    if args.aa:
        # A/A null: identical engine on both arms. Any deviation of the median
        # from 1.0 is substrate/position effect, not signal.
        for eng, fn in (("fnx", fnx_read), ("nx", nx_read)):
            if eng == "nx" and args.skip_nx:
                continue
            a, b, _, _ = paired(fn, fn, args.reps)
            r = [x / y for x, y in zip(a, b)]
            lo, hi = bootstrap_ci(r)
            out[f"aa_{eng}"] = {
                "median": statistics.median(r),
                "ci": [lo, hi],
                "half_width": (hi - lo) / 2,
            }

    fnx_t, nx_t, fnx_cw, nx_cw = paired(fnx_read, nx_read, args.reps)
    ratios = [n / f for n, f in zip(nx_t, fnx_t)]
    lo, hi = bootstrap_ci(ratios)
    out["ab"] = {
        "fnx_median_s": statistics.median(fnx_t),
        "nx_median_s": statistics.median(nx_t),
        "ratio_median": statistics.median(ratios),
        "ratio_ci": [lo, hi],
        "fnx_cpu_wall": statistics.median(fnx_cw),
        "nx_cpu_wall": statistics.median(nx_cw),
    }
    print(json.dumps(out))
    return 0


def role_sweep(args):
    results = []
    for threads in [1, 2, 4, 8, 16, 32, 64]:
        env = dict(os.environ, RAYON_NUM_THREADS=str(threads))
        proc = subprocess.run(
            [sys.executable, __file__, "--role", "worker", "--graph", args.graph,
             "--reps", str(args.reps), "--skip-nx"],
            env=env, capture_output=True, text=True,
        )
        line = [ln for ln in proc.stdout.splitlines() if ln.startswith("{")]
        if not line:
            print(proc.stdout, proc.stderr, file=sys.stderr)
            return 1
        rec = json.loads(line[-1])
        rec["threads"] = threads
        results.append(rec)
        ab = rec["ab"]
        print(f"  threads={threads:3d}  fnx {ab['fnx_median_s']*1000:8.2f} ms   "
              f"cpu/wall {ab['fnx_cpu_wall']:6.2f}   vs nx {ab['ratio_median']:8.2f}x")
    with open(args.out, "w") as f:
        json.dump(results, f, indent=2)
    base = results[0]["ab"]["fnx_median_s"]
    best = min(r["ab"]["fnx_median_s"] for r in results)
    print(f"  scaling 1 -> 64 threads: {base/best:.2f}x")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--role", choices=["worker", "sweep"], default="worker")
    ap.add_argument("--graph", default="ca-AstroPh")
    ap.add_argument("--reps", type=int, default=9)
    ap.add_argument("--aa", action="store_true")
    ap.add_argument("--skip-nx", action="store_true")
    ap.add_argument("--out", default="sweep.json")
    args = ap.parse_args()
    return role_sweep(args) if args.role == "sweep" else role_worker(args)


if __name__ == "__main__":
    sys.exit(main())
