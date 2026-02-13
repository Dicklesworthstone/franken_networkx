#!/usr/bin/env python3
"""Run benchmark command via hyperfine and emit percentile artifact."""

from __future__ import annotations

import argparse
import json
import math
import statistics
import subprocess
import tempfile
from pathlib import Path


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = (len(ordered) - 1) * p
    lo = math.floor(idx)
    hi = math.ceil(idx)
    if lo == hi:
        return ordered[lo]
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (idx - lo)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--command", required=True)
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--warmup", type=int, default=3)
    parser.add_argument("--p95-budget-ms", type=float, default=None)
    parser.add_argument("--p99-budget-ms", type=float, default=None)
    args = parser.parse_args()

    artifact_path = Path(args.artifact)
    artifact_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as temp_json:
        temp_path = Path(temp_json.name)

    cmd = [
        "hyperfine",
        "--warmup",
        str(args.warmup),
        "--runs",
        str(args.runs),
        "--export-json",
        str(temp_path),
        args.command,
    ]
    subprocess.run(cmd, check=True)

    data = json.loads(temp_path.read_text(encoding="utf-8"))
    times_sec = data["results"][0]["times"]
    times_ms = [value * 1000.0 for value in times_sec]
    summary = {
        "command": args.command,
        "runs": len(times_ms),
        "times_ms": times_ms,
        "mean_ms": statistics.mean(times_ms),
        "p50_ms": percentile(times_ms, 0.50),
        "p95_ms": percentile(times_ms, 0.95),
        "p99_ms": percentile(times_ms, 0.99),
        "min_ms": min(times_ms),
        "max_ms": max(times_ms),
    }

    budgets = {}
    if args.p95_budget_ms is not None:
        budgets["p95_budget_ms"] = args.p95_budget_ms
        budgets["p95_pass"] = summary["p95_ms"] <= args.p95_budget_ms
    if args.p99_budget_ms is not None:
        budgets["p99_budget_ms"] = args.p99_budget_ms
        budgets["p99_pass"] = summary["p99_ms"] <= args.p99_budget_ms
    summary["budgets"] = budgets

    artifact_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))

    if ("p95_pass" in budgets and not budgets["p95_pass"]) or (
        "p99_pass" in budgets and not budgets["p99_pass"]
    ):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
