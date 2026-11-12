"""br-r37-c1-rgmef: did `subclass` on the native AtlasView cost the hot G[u] path?

I committed `#[pyclass(module="franken_networkx", mapping, subclass)]` UNBUILT
during the disk freeze and put a condition on the bead with it: that type is the
row `G[u]` returns for a plain Graph on br-r37-c1-ey6ob's C-slot fast path, and
`subclass` sets Py_TPFLAGS_BASETYPE. If it regresses `G[u]`, the Python half of
the Graph fix must NOT be wired up. This is the row that settles it.

WHY SUBPROCESSES. The first version loaded both arms into one process, which is
impossible for a compiled extension: `_fnx` is a single-phase-init C extension
named `franken_networkx._fnx`, and CPython will not load two copies of it under
different package names. Each arm therefore runs in its OWN process, and the
arms are INTERLEAVED at the process level in ABBA order so a monotone load ramp
cancels instead of landing on whichever arm ran first.

THE ARMS ARE MATCHED BY CONSTRUCTION. Two package dirs of identical shape, both
symlinking the SAME repo files, differing only in `_fnx.abi3.so` — one built from
HEAD, one from a detached worktree at the same HEAD with only the word
`subclass` removed. Verified before measuring: same row class, 87 entries each,
subclassable False vs True. That matching is the part I got wrong earlier this
session, when an unmatched pair reported 1722 failures against 57 and reproduced
EXACTLY twice purely because the arms resolved `_fnx` differently.

NETWORKX IS THE COMMON-MODE CELL, timed in every subprocess. It is byte
identical in both arms, so `nx_before / nx_after` must be ~1. If it is not, the
host moved under the measurement and the row is void whatever the treatment
cells say.

PER-ARM loadavg AND CPU MHz are recorded on every sample, because cross-core
clock spread is the dominant confounder: an unrecorded frequency difference is a
frequency ratio wearing the costume of a code effect.
"""

from __future__ import annotations

import json
import os
import statistics
import subprocess
import sys

ROUNDS = 12
PKG = {
    "before": "/data/tmp/claude-1000/pkg_before",
    "after": "/data/tmp/claude-1000/pkg_after",
}

CHILD = r'''
import gc, json, os, statistics, sys, time
import networkx as nx
import franken_networkx as fnx

REPS = 300
N = 400

def cpu_mhz():
    try:
        with open("/proc/cpuinfo") as h:
            v = [float(l.split(":")[1]) for l in h if l.lower().startswith("cpu mhz")]
        return round(statistics.mean(v), 1) if v else float("nan")
    except OSError:
        return float("nan")

def build(lib):
    g = lib.Graph()
    g.add_edges_from((i, i + 1, {"weight": 1.0}) for i in range(N))
    g.add_edges_from((i, i + 7, {"weight": 2.0}) for i in range(N - 7))
    return g

def timeit(g, nodes):
    best = float("inf")
    for _ in range(5):
        gc.collect(); gc.disable()
        t0 = time.perf_counter()
        for _ in range(REPS):
            for u in nodes:
                g[u]
        dt = time.perf_counter() - t0
        gc.enable()
        best = min(best, dt)
    return best / (REPS * len(nodes)) * 1e9

nodes = list(range(0, N, 17))
gn, gf = build(nx), build(fnx)
# warm both, then interleave nx/fnx inside the process too
timeit(gn, nodes); timeit(gf, nodes)
res = {
    "nx": timeit(gn, nodes),
    "fnx": timeit(gf, nodes),
    "loadavg": round(os.getloadavg()[0], 2),
    "mhz": cpu_mhz(),
    "so": fnx._fnx.__file__,
}
row = type(gf[0])
try:
    type("P", (row,), {}); res["subclassable"] = True
except Exception:
    res["subclassable"] = False
print("RESULT " + json.dumps(res))
'''


def run(arm):
    env = dict(os.environ, PYTHONPATH=PKG[arm])
    env.pop("CARGO_TARGET_DIR", None)
    out = subprocess.run(
        [sys.executable, "-c", CHILD], env=env, capture_output=True, text=True,
        timeout=600,
    )
    for line in out.stdout.splitlines():
        if line.startswith("RESULT "):
            return json.loads(line[7:])
    raise RuntimeError(f"{arm}: no result\n{out.stdout[-500:]}\n{out.stderr[-800:]}")


def main():
    samples = {"before": [], "after": []}
    print(f"subject: G[u] on a plain Graph — native AtlasView row (br-r37-c1-ey6ob)")
    print(f"rounds={ROUNDS} (ABBA per round)\n")
    for _ in range(ROUNDS):
        for arm in ("before", "after", "after", "before"):
            samples[arm].append(run(arm))

    print(f"  {'arm':7s} {'nx ns':>9s} {'fnx ns':>9s} {'vs nx':>8s} {'load':>6s} {'MHz':>8s} sub")
    med = {}
    for arm in ("before", "after"):
        rows = samples[arm]
        nx_med = statistics.median(r["nx"] for r in rows)
        fx_med = statistics.median(r["fnx"] for r in rows)
        med[arm] = (nx_med, fx_med)
        print(f"  {arm:7s} {nx_med:9.1f} {fx_med:9.1f} {nx_med / fx_med:8.4f}x "
              f"{statistics.median(r['loadavg'] for r in rows):6.2f} "
              f"{statistics.median(r['mhz'] for r in rows):8.1f} "
              f"{rows[0]['subclassable']}")

    print()
    common = med["before"][0] / med["after"][0]
    print(f"COMMON-MODE nx_before/nx_after = {common:.4f}  "
          f"({'OK' if 0.97 <= common <= 1.03 else 'VOID — the host moved'})")
    self_ratio = med["before"][1] / med["after"][1]
    print(f"SELF before/after (fnx G[u])   = {self_ratio:.4f}  "
          f"({'subclass made G[u] SLOWER' if self_ratio < 0.97 else 'no regression'})")


if __name__ == "__main__":
    main()
