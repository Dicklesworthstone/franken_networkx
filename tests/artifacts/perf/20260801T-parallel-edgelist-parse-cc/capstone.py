#!/usr/bin/env python3
"""Whole-job analytics pass: FrankenNetworkX vs live NetworkX 3.6.1.

Reuses `run_pass` from scripts/parallel_analytics_pass.py verbatim, so the job
and its stage decomposition are exactly the shipped harness's. What this adds
is a fresh, current-build measurement with:

  * nx 3.6.1 imported and executed live in the same process as fnx;
  * arms interleaved inside one replicate loop, alternating which goes first;
  * an A/A null (fnx vs fnx) so the effect is read against substrate spread;
  * a bootstrap CI on the median ratio;
  * per-stage cpu/wall, which is the measured-parallelism evidence;
  * host load recorded before and after, because this box is shared.

Result digests from both engines are compared so the speedup is over the same
computation, not a cheaper one.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import random
import statistics
import sys
import time

sys.path.insert(0, "scripts")
from parallel_analytics_pass import run_pass  # noqa: E402


def loadavg():
    with open("/proc/loadavg") as f:
        return f.read().split()[0:3]


def bootstrap_ci(ratios, iters=20000, alpha=0.05, seed=20260801):
    rng = random.Random(seed)
    n = len(ratios)
    meds = sorted(statistics.median(rng.choices(ratios, k=n)) for _ in range(iters))
    return meds[int(alpha / 2 * iters)], meds[min(iters - 1, int((1 - alpha / 2) * iters))]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--graph", default="facebook_combined")
    ap.add_argument("--reps", type=int, default=8)
    ap.add_argument("--aa-reps", type=int, default=4)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    import networkx as nx

    import franken_networkx as fnx

    path = f"graphs/{args.graph}.txt.gz"
    rec = {
        "graph": args.graph,
        "host": platform.node(),
        "cpu_count": os.cpu_count(),
        "python": platform.python_version(),
        "networkx_version": nx.__version__,
        "networkx_file": nx.__file__,
        "fnx_file": fnx.__file__,
        "nx_auto_backend_env": os.environ.get("NETWORKX_AUTOMATIC_BACKENDS", "<unset>"),
        "load_before": loadavg(),
        "started": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "reps": args.reps,
    }
    import hashlib
    so = os.path.join(os.path.dirname(fnx.__file__), "_fnx.abi3.so")
    rec["fnx_elf_sha256"] = hashlib.sha256(open(so, "rb").read()).hexdigest()

    # ---- A/A null: same engine on both arms -------------------------------
    aa = []
    for i in range(args.aa_reps):
        t0, _ = run_pass(fnx, path, job="analytics", engine_label="fnx-a")
        t1, _ = run_pass(fnx, path, job="analytics", engine_label="fnx-b")
        wa = next(x for x in t0 if x["stage"] == "TOTAL")["wall_s"]
        wb = next(x for x in t1 if x["stage"] == "TOTAL")["wall_s"]
        aa.append(wa / wb)
    lo, hi = bootstrap_ci(aa)
    rec["aa_null"] = {"median": statistics.median(aa), "ci": [lo, hi],
                      "half_width": (hi - lo) / 2, "samples": aa}
    print(f"A/A null median {statistics.median(aa):.4f}  half-width {(hi-lo)/2:.4f}", flush=True)

    # ---- A/B: interleaved --------------------------------------------------
    fnx_totals, nx_totals = [], []
    fnx_stages, nx_stages = [], []
    digests = []
    for i in range(args.reps):
        order = ("fnx", "nx") if i % 2 == 0 else ("nx", "fnx")
        got = {}
        for eng in order:
            mod = fnx if eng == "fnx" else nx
            t, d = run_pass(mod, path, job="analytics", engine_label=eng)
            got[eng] = (t, d)
        ft, fd = got["fnx"]
        nt, nd = got["nx"]
        fw = next(x for x in ft if x["stage"] == "TOTAL")["wall_s"]
        nw = next(x for x in nt if x["stage"] == "TOTAL")["wall_s"]
        fnx_totals.append(fw)
        nx_totals.append(nw)
        fnx_stages.append(ft)
        nx_stages.append(nt)
        digests.append({"fnx": fd, "nx": nd})
        print(f"rep {i}: fnx {fw:8.3f}s   nx {nw:9.3f}s   {nw/fw:8.1f}x", flush=True)

    ratios = [n / f for n, f in zip(nx_totals, fnx_totals)]
    lo, hi = bootstrap_ci(ratios)
    rec["ab"] = {
        "fnx_median_s": statistics.median(fnx_totals),
        "nx_median_s": statistics.median(nx_totals),
        "ratio_median": statistics.median(ratios),
        "ratio_ci": [lo, hi],
        "fnx_totals": fnx_totals,
        "nx_totals": nx_totals,
    }

    # per-stage medians
    stage_names = [x["stage"] for x in fnx_stages[0]]
    rec["stages"] = []
    for s in stage_names:
        fv = [next(x for x in r if x["stage"] == s) for r in fnx_stages]
        nv = [next(x for x in r if x["stage"] == s) for r in nx_stages]
        fw = statistics.median(x["wall_s"] for x in fv)
        nw = statistics.median(x["wall_s"] for x in nv)
        rec["stages"].append({
            "stage": s,
            "fnx_wall_s": fw, "nx_wall_s": nw,
            "ratio": (nw / fw) if fw else None,
            "fnx_cpu_wall": statistics.median(x["cpu_wall_ratio"] for x in fv),
            "nx_cpu_wall": statistics.median(x["cpu_wall_ratio"] for x in nv),
            "fnx_threads": max(x["thread_count_actually_used"] for x in fv),
            "nx_threads": max(x["thread_count_actually_used"] for x in nv),
        })

    # digest agreement: same computation on both engines
    mismatch = []
    d0 = digests[0]
    for k in d0["fnx"]:
        if k in d0["nx"] and d0["fnx"][k] != d0["nx"][k]:
            mismatch.append(k)
    rec["digest_keys_compared"] = sorted(set(d0["fnx"]) & set(d0["nx"]))
    rec["digest_mismatches"] = mismatch
    rec["digest_sample"] = {"fnx": d0["fnx"], "nx": d0["nx"]}
    rec["load_after"] = loadavg()
    rec["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")

    with open(args.out, "w") as f:
        json.dump(rec, f, indent=2, default=str)
    print(f"\nTOTAL {statistics.median(ratios):.1f}x  CI [{lo:.1f}, {hi:.1f}]  "
          f"digest_mismatches={mismatch}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
