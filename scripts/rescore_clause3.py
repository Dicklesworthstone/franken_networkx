#!/usr/bin/env python3
"""Re-decide archived perf_harness rows under candidate clause-3 gates (br-r37-c1-d4xot).

WHY THIS EXISTS. br-r37-c1-d4xot reports that clause 3 — worst A/A null median
bias <= MAX_NULL_MEDIAN_BIAS — vetoes a reproducible 4.4x effect roughly a
quarter of the time on a contended host, and its blocking predicate demands the
integrity check before any gate change: run the full claim-incumbent suite under
the current clause and under the candidate, then report how many previously
vetoed rows become decidable AND the WIN vs LOSE split of exactly those rows. A
variant that admits only wins is a loosening, not a fix, and must be reverted.

That predicate has been treated as needing two admitted full-suite runs on a host
that has not admitted one in weeks. It does not. `perf_harness.py` already emits,
per row, the RAW per-round sample lists for the candidate and both nulls —
`ratio_samples`, `null_nx_samples`, `null_fnx_samples` — and every clause variant
is a pure function of those three lists. So ONE admitted run, whose stdout is
saved, supplies everything needed to score every variant offline, repeatedly,
forever.

    python3 scripts/perf_harness.py claim-incumbent | tee artifacts/<run>.txt
    python3 scripts/rescore_clause3.py artifacts/<run>.txt

No archived run currently retains those samples (`grep -rl ratio_samples` over
tests/artifacts, docs and artifacts returns nothing), which is the only reason
this cannot be run today. Capturing one is a shell redirect.

WHAT IT DOES NOT DO. It does not change any gate, and it is not evidence for
changing one on its own — it computes the table the predicate asks for so a human
can read the WIN/LOSE split and decide. Feeding it samples from anything other
than an admitted harness invocation would be proof-class substitution; the point
of the predicate is that the decision rests on the harness's own measurements.

CLAUSE VARIANTS, from the bead:
  current   worst arm |null median - 1| <= MAX_NULL_MEDIAN_BIAS
  pooled    |median(all null ratios, BOTH arms) - 1| <= MAX_NULL_MEDIAN_BIAS
  relative  worst arm bias <= MAX, OR bias <= |candidate median - 1| / RELATIVE_K

Clauses 1 (candidate CI excludes 1) and 2 (effect deviation > 2x null half-width)
are held fixed throughout; only clause 3 varies, so a row that flips can only have
flipped because of clause 3.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import statistics
import sys

MAX_NULL_MEDIAN_BIAS = 0.02  # scripts/perf_harness.py
RELATIVE_K = 10.0
# This tool is an offline replay of the production gate, not an independent
# estimator.  Keep these exactly aligned with perf_harness._median_ci so that
# clauses 1 and 2 remain fixed while clause 3 is rescored.
BOOT_REPS = 2000
BOOT_SEED = 12345


def _median_ci(values, reps=BOOT_REPS, seed=BOOT_SEED):
    """Bootstrap median CI, matching the harness's decision statistic."""
    rng = random.Random(seed)
    count = len(values)
    medians = sorted(
        statistics.median(values[rng.randrange(count)] for _ in range(count))
        for _ in range(reps)
    )
    return medians[int(0.025 * reps)], medians[int(0.975 * reps) - 1]


def _clause3(name, nx_samples, fnx_samples, effect_median):
    nx_med, fnx_med = statistics.median(nx_samples), statistics.median(fnx_samples)
    worst = max(abs(nx_med - 1.0), abs(fnx_med - 1.0))
    if name == "current":
        return worst <= MAX_NULL_MEDIAN_BIAS
    if name == "pooled":
        pooled = statistics.median(list(nx_samples) + list(fnx_samples))
        return abs(pooled - 1.0) <= MAX_NULL_MEDIAN_BIAS
    if name == "relative":
        return (worst <= MAX_NULL_MEDIAN_BIAS
                or worst <= abs(effect_median - 1.0) / RELATIVE_K)
    raise ValueError(name)


def decide(row, variant):
    """Clauses 1 and 2 held fixed; only clause 3 varies."""
    cand = row["ratio_samples"]
    nx_s, fnx_s = row["null_nx_samples"], row["null_fnx_samples"]
    median = statistics.median(cand)
    lo, hi = _median_ci(cand)
    nx_lo, nx_hi = _median_ci(nx_s)
    fnx_lo, fnx_hi = _median_ci(fnx_s)
    half = max((nx_hi - nx_lo) / 2.0, (fnx_hi - fnx_lo) / 2.0)
    c1 = lo > 1.0 or hi < 1.0
    c2 = abs(median - 1.0) > 2.0 * half
    c3 = _clause3(variant, nx_s, fnx_s, median)
    return {"median": median, "c1": c1, "c2": c2, "c3": c3,
            "decidable": c1 and c2 and c3}


def load_rows(path):
    """Accept a raw harness stdout capture or a bare JSON array."""
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    match = re.search(r"^benchmark_results_json=(.*)$", text, re.M)
    payload = match.group(1) if match else text
    try:
        rows = json.loads(payload)
    except json.JSONDecodeError as error:
        raise SystemExit(
            f"{path}: not a harness capture or JSON array of rows ({error}). "
            "Expected the `benchmark_results_json=` line from perf_harness stdout."
        ) from error
    usable = [r for r in rows
              if all(k in r for k in
                     ("ratio_samples", "null_nx_samples", "null_fnx_samples"))]
    return rows, usable


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("capture", help="harness stdout capture, or a JSON array of rows")
    ap.add_argument("--variant", default="pooled", choices=("pooled", "relative"))
    args = ap.parse_args(argv)

    rows, usable = load_rows(args.capture)
    if not usable:
        print(f"no rows carry raw samples in {args.capture}.", file=sys.stderr)
        print("The harness emits ratio_samples / null_nx_samples / null_fnx_samples;"
              " capture its stdout, not its summary.", file=sys.stderr)
        return 2
    print(f"{len(usable)} of {len(rows)} rows carry raw samples\n")

    flipped, unchanged, lost = [], 0, []
    for row in usable:
        cur = decide(row, "current")
        alt = decide(row, args.variant)
        if cur["decidable"] == alt["decidable"]:
            unchanged += 1
        elif alt["decidable"]:
            flipped.append((row.get("label", "?"), alt["median"]))
        else:
            lost.append((row.get("label", "?"), cur["median"]))

    wins = [f for f in flipped if f[1] > 1.0]
    loses = [f for f in flipped if f[1] <= 1.0]
    print(f"variant: {args.variant}   (clauses 1 and 2 held fixed)")
    print(f"  unchanged                     {unchanged}")
    print(f"  newly decidable               {len(flipped)}")
    print(f"    of which WIN  (>1.0x)       {len(wins)}")
    print(f"    of which LOSE (<=1.0x)      {len(loses)}")
    print(f"  newly UNdecidable             {len(lost)}")
    for label, median in flipped:
        print(f"    + {median:8.4f}x  {label}")
    for label, median in lost:
        print(f"    - {median:8.4f}x  {label}")

    print("\nREAD THIS BEFORE ACTING. The predicate on br-r37-c1-d4xot is that a")
    print("variant admitting ONLY wins is a loosening and must be reverted. Compare")
    print("the WIN and LOSE counts above: a fix should admit both, in roughly the")
    print("proportion the suite already shows. This tool reports; it does not decide.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
