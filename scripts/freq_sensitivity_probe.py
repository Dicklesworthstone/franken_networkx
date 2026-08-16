"""Does my harness's RATIO depend on the core frequency it ran at?

br-r37-c1-freqsens. The cross-core clock spread on this host is real, but its
impact is harness-specific and must be measured per harness rather than inherited
from another project's finding.

THE MECHANISM THAT WOULD MATTER. This harness runs both arms sequentially inside
one process, so they cannot contend with each other. Frequency can still bias a
RATIO if the two arms respond to a clock change by different factors — e.g. if one
arm is memory-bound (insensitive to core clock) and the other is core-bound
(proportional to it). Then the same code measured on a 3.3 GHz core and a 4.3 GHz
core yields two different ratios, and every row is implicitly a statement about
whichever clock it happened to get.

THE TEST. Run the identical workload pinned to each of several single CPUs whose
frequencies differ, record each row's on-core clock and its ratio, and ask whether
ratio tracks clock. A flat relationship means frequency is common-mode for this
harness and cancels; a sloped one means rows must be quoted with their clock.

Two row shapes are carried on purpose:
  - a LARGE-ratio row (fnx ~20x its old self, still far from networkx), and
  - a NEAR-PARITY row,
because a multiplicative bias is easiest to see far from 1.0 while an additive one
is easiest to see near it.
"""

import json
import os
import re
import subprocess
import sys

REPO = "/data/projects/franken_networkx"
ROW = re.compile(
    r"^\s{2}(?P<name>.+?)\s+(?P<ratio>[0-9.]+)x\s+CI \[(?P<lo>[0-9.]+), (?P<hi>[0-9.]+)\]\s+"
    r"nulls (?P<na>[0-9.]+)/(?P<nb>[0-9.]+)\s+clk (?P<ma>\d+)/(?P<mb>\d+)MHz\s+"
    r"skew (?P<skew>[-+0-9.]+)%\s+spread (?P<spread>[0-9.]+)%.*?\s(?P<verdict>[A-Z-]+)\s*$"
)


def run_on(cpu, rounds, reps, calls):
    env = dict(os.environ)
    env.update(
        PYTHONPATH="python",
        PYTHONHASHSEED="0",
        OPENBLAS_NUM_THREADS="1",
        OMP_NUM_THREADS="1",
    )
    proc = subprocess.run(
        [
            "taskset", "-c", str(cpu),
            f"{REPO}/.venv/bin/python", f"{REPO}/scripts/balanced_square_ab.py",
            "--workload", "parallel-keydict",
            "--rounds", str(rounds), "--reps", str(reps), "--calls-per-slot", str(calls),
        ],
        cwd=REPO, env=env, capture_output=True, text=True, timeout=1800,
    )
    out = []
    for line in proc.stdout.splitlines():
        m = ROW.match(line)
        if m:
            d = m.groupdict()
            out.append(
                {
                    "cpu": cpu,
                    "name": d["name"].strip(),
                    "ratio": float(d["ratio"]),
                    "mhz": (int(d["ma"]) + int(d["mb"])) / 2.0,
                    "skew": float(d["skew"]),
                    "spread": float(d["spread"]),
                    "verdict": d["verdict"],
                }
            )
    return out


def main():
    cpus = [int(c) for c in sys.argv[1].split(",")]
    rounds, reps, calls = int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
    rows = []
    for cpu in cpus:
        got = run_on(cpu, rounds, reps, calls)
        print(f"  cpu{cpu}: {len(got)} rows", flush=True)
        rows.extend(got)
    path = sys.argv[5]
    with open(path, "w") as handle:
        json.dump(rows, handle)
    print(f"wrote {len(rows)} rows to {path}")


if __name__ == "__main__":
    main()
