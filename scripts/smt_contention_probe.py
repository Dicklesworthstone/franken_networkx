"""Does SMT-sibling contention bias MY harness's ratios?

br-r37-c1-freqsens. Every CPU this pane benchmarks on is the second hyperthread of
a physical core whose first thread runs other fleet work. Another project found a
real defect from arm placement; this measures whether the same exposure moves a
ratio HERE, instead of inheriting their conclusion.

THE DESIGN. Pin the harness to one CPU. Alternate two conditions on that same CPU:

    IDLE     — the SMT sibling is left alone
    LOADED   — the SMT sibling is saturated by a spin loop pinned to it

and compare the RATIOS, not the absolute times. Absolute times must degrade under
LOADED; that is not in question and not the point. The question is whether both
arms degrade by the SAME factor. If they do, contention is common-mode and cancels
in the ratio, which is what a sequential-arms harness predicts. If the ratio
moves, the exposure is real for this harness and every row taken on a shared
physical core is suspect.

Conditions ALTERNATE (IDLE, LOADED, IDLE, LOADED, ...) so that host drift across
the experiment hits both conditions equally — the same reason the harness itself
alternates arms, applied one level up.

The spin child is started and stopped around each run and is killed in a `finally`,
so no load outlives the experiment.
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

SPIN = "x=0\nwhile True:\n    x += 1\n"


def run_once(cpu, condition, rounds, reps, calls):
    env = dict(os.environ)
    env.update(
        PYTHONPATH="python",
        PYTHONHASHSEED="0",
        OPENBLAS_NUM_THREADS="1",
        OMP_NUM_THREADS="1",
    )
    sibling = cpu - 32 if cpu >= 32 else cpu + 32
    child = None
    try:
        if condition == "LOADED":
            child = subprocess.Popen(
                ["taskset", "-c", str(sibling), f"{REPO}/.venv/bin/python", "-c", SPIN],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        proc = subprocess.run(
            [
                "taskset", "-c", str(cpu),
                f"{REPO}/.venv/bin/python", f"{REPO}/scripts/balanced_square_ab.py",
                "--workload", "parallel-keydict",
                "--rounds", str(rounds), "--reps", str(reps),
                "--calls-per-slot", str(calls),
            ],
            cwd=REPO, env=env, capture_output=True, text=True, timeout=1800,
        )
    finally:
        if child is not None:
            child.kill()
            child.wait()
    out = []
    for line in proc.stdout.splitlines():
        m = ROW.match(line)
        if m:
            d = m.groupdict()
            out.append(
                {
                    "condition": condition,
                    "cpu": cpu,
                    "sibling": sibling,
                    "name": d["name"].strip(),
                    "ratio": float(d["ratio"]),
                    "mhz": (int(d["ma"]) + int(d["mb"])) / 2.0,
                    "skew": float(d["skew"]),
                    "verdict": d["verdict"],
                }
            )
    return out


def main():
    cpu = int(sys.argv[1])
    reps_of_pair = int(sys.argv[2])
    rounds, reps, calls = int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
    path = sys.argv[6]
    rows = []
    for i in range(reps_of_pair):
        for condition in ("IDLE", "LOADED"):
            got = run_once(cpu, condition, rounds, reps, calls)
            print(f"  pair {i + 1} {condition}: {len(got)} rows", flush=True)
            rows.extend(got)
    with open(path, "w") as handle:
        json.dump(rows, handle)
    print(f"wrote {len(rows)} rows")


if __name__ == "__main__":
    main()
