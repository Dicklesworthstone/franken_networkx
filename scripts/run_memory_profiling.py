#!/usr/bin/env python3
"""Memory profiling harness using dhat for heap allocation tracking.

Runs memory_baseline with dhat-heap feature across multiple scenarios,
collecting allocation statistics and detecting regressions against baseline.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import subprocess
import sys
from datetime import datetime, timezone
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


def summarize(values: list[float]) -> dict[str, float]:
    if not values:
        return {"samples": 0.0, "mean": 0.0, "p50": 0.0, "p95": 0.0, "min": 0.0, "max": 0.0}
    ordered = sorted(values)
    return {
        "samples": float(len(values)),
        "mean": sum(values) / len(values),
        "p50": percentile(ordered, 0.50),
        "p95": percentile(ordered, 0.95),
        "min": ordered[0],
        "max": ordered[-1],
    }


def cpu_model() -> str:
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.exists():
        for line in cpuinfo.read_text(encoding="utf-8").splitlines():
            if line.startswith("model name"):
                parts = line.split(":", 1)
                if len(parts) == 2:
                    return parts[1].strip()
    return platform.processor() or "unknown"


def shell_output(command: list[str]) -> str:
    try:
        return subprocess.check_output(command, text=True, stderr=subprocess.DEVNULL).strip()
    except subprocess.CalledProcessError:
        return "unknown"


def build_command(target_dir: str, cargo_wrapper: str, scenario: dict[str, object]) -> str:
    parts = [
        f"CARGO_TARGET_DIR={target_dir}",
        f"{cargo_wrapper} run --release --features dhat-heap -q -p fnx-algorithms --example memory_baseline --",
        f"--topology {scenario['topology']}",
        f"--seed {scenario['seed']}",
    ]
    if "nodes" in scenario:
        parts.append(f"--nodes {scenario['nodes']}")
    if "width" in scenario:
        parts.append(f"--width {scenario['width']}")
    if "height" in scenario:
        parts.append(f"--height {scenario['height']}")
    if "edge_prob" in scenario:
        parts.append(f"--edge-prob {scenario['edge_prob']}")
    return " ".join(parts)


def run_once(command: str) -> dict[str, object] | None:
    """Run the memory profiler and parse JSON output."""
    try:
        result = subprocess.run(
            ["bash", "-lc", command],
            capture_output=True,
            text=True,
            check=False,
            timeout=300,
        )
        if result.returncode != 0:
            print(f"  [warn] command failed: {result.returncode}", file=sys.stderr)
            print(f"  stderr: {result.stderr[:500]}", file=sys.stderr)
            return None
        # Parse the JSON from stdout or stderr (rch mixes outputs to stderr)
        all_output = result.stdout + "\n" + result.stderr
        for line in all_output.splitlines():
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                try:
                    parsed = json.loads(line)
                    # Validate it's our output (has topology key)
                    if "topology" in parsed:
                        return parsed
                except json.JSONDecodeError:
                    continue
        return None
    except subprocess.TimeoutExpired:
        print("  [warn] command timed out", file=sys.stderr)
        return None


def pct_delta(candidate: float, baseline: float) -> float:
    if baseline == 0.0:
        return 0.0 if candidate == 0.0 else 100.0
    return ((candidate - baseline) / baseline) * 100.0


def main() -> int:
    parser = argparse.ArgumentParser(description="Memory profiling with dhat")
    parser.add_argument(
        "--artifact",
        default="artifacts/perf/memory/memory_profile_v1.json",
        help="Output artifact path",
    )
    parser.add_argument(
        "--baseline",
        default="artifacts/perf/memory/memory_baseline_v1.json",
        help="Baseline artifact for regression detection",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=3,
        help="Number of measurement runs per scenario",
    )
    parser.add_argument(
        "--target-dir",
        default="target-codex",
        help="Cargo target directory",
    )
    parser.add_argument(
        "--cargo-wrapper",
        default="cargo",
        help="Cargo wrapper command (e.g., 'rch exec -- cargo')",
    )
    parser.add_argument(
        "--regression-threshold-pct",
        type=float,
        default=15.0,
        help="Max allowed regression percentage for peak bytes",
    )
    args = parser.parse_args()

    scenarios = [
        {
            "scenario_id": "grid_80x80_seed1337",
            "topology": "grid",
            "width": 80,
            "height": 80,
            "seed": 1337,
            "size_bucket": "medium",
        },
        {
            "scenario_id": "line_10000_seed1337",
            "topology": "line",
            "nodes": 10000,
            "seed": 1337,
            "size_bucket": "large",
        },
        {
            "scenario_id": "star_10000_seed1337",
            "topology": "star",
            "nodes": 10000,
            "seed": 1337,
            "size_bucket": "large",
        },
        {
            "scenario_id": "complete_300_seed1337",
            "topology": "complete",
            "nodes": 300,
            "seed": 1337,
            "size_bucket": "small_dense",
        },
        {
            "scenario_id": "erdos_renyi_n2000_p005_seed1337",
            "topology": "erdos_renyi",
            "nodes": 2000,
            "edge_prob": 0.005,
            "seed": 1337,
            "size_bucket": "medium_random",
        },
    ]

    scenario_rows = []
    print(f"Running {len(scenarios)} memory profiling scenarios...")

    for scenario in scenarios:
        command = build_command(args.target_dir, args.cargo_wrapper, scenario)
        print(f"\n  [{scenario['scenario_id']}] running {args.runs} samples...")

        total_bytes_samples = []
        max_bytes_samples = []
        total_blocks_samples = []
        max_blocks_samples = []
        raw_samples = []

        for run_idx in range(args.runs):
            result = run_once(command)
            if result is None:
                print(f"    run {run_idx + 1}: FAILED")
                continue

            if result.get("dhat_enabled") is False:
                print(f"    run {run_idx + 1}: dhat not enabled")
                continue

            total_bytes_samples.append(float(result.get("total_bytes", 0)))
            max_bytes_samples.append(float(result.get("max_bytes", 0)))
            total_blocks_samples.append(float(result.get("total_blocks", 0)))
            max_blocks_samples.append(float(result.get("max_blocks", 0)))
            raw_samples.append(result)
            print(
                f"    run {run_idx + 1}: max_bytes={result.get('max_bytes', 0):,} "
                f"total_bytes={result.get('total_bytes', 0):,}"
            )

        if not total_bytes_samples:
            print(f"  [{scenario['scenario_id']}] no successful runs!")
            continue

        scenario_rows.append({
            "scenario_id": scenario["scenario_id"],
            "topology": scenario["topology"],
            "size_bucket": scenario["size_bucket"],
            "seed": int(scenario["seed"]),
            "command": command,
            "sample_count": len(total_bytes_samples),
            "total_bytes": summarize(total_bytes_samples),
            "max_bytes": summarize(max_bytes_samples),
            "total_blocks": summarize(total_blocks_samples),
            "max_blocks": summarize(max_blocks_samples),
            "last_sample": raw_samples[-1] if raw_samples else None,
        })

    environment = {
        "hostname": platform.node(),
        "os": platform.platform(),
        "cpu_model": cpu_model(),
        "python_version": platform.python_version(),
        "cargo_version": shell_output(["cargo", "--version"]),
        "rustc_version": shell_output(["rustc", "--version"]),
        "git_commit": shell_output(["git", "rev-parse", "HEAD"]),
    }
    environment_fingerprint = hashlib.sha256(
        json.dumps(environment, sort_keys=True).encode("utf-8")
    ).hexdigest()

    artifact_payload = {
        "schema_version": "1.0.0",
        "profile_id": "memory-dhat-profile-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "measurement_protocol": {
            "runs": args.runs,
            "profiler": "dhat",
            "metrics": ["total_bytes", "max_bytes", "total_blocks", "max_blocks"],
            "target_dir": args.target_dir,
        },
        "environment": environment,
        "environment_fingerprint": environment_fingerprint,
        "scenario_count": len(scenario_rows),
        "scenarios": scenario_rows,
    }

    # Regression detection
    regressions = []
    baseline_path = Path(args.baseline)
    if baseline_path.exists():
        try:
            baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
            baseline_by_id = {row["scenario_id"]: row for row in baseline.get("scenarios", [])}

            for row in scenario_rows:
                scenario_id = row["scenario_id"]
                baseline_row = baseline_by_id.get(scenario_id)
                if baseline_row is None:
                    continue

                candidate_max = row["max_bytes"]["p50"]
                baseline_max = baseline_row["max_bytes"]["p50"]
                delta_pct = pct_delta(candidate_max, baseline_max)

                if delta_pct > args.regression_threshold_pct:
                    regressions.append({
                        "scenario_id": scenario_id,
                        "metric": "max_bytes",
                        "baseline_p50": baseline_max,
                        "candidate_p50": candidate_max,
                        "delta_pct": round(delta_pct, 2),
                        "threshold_pct": args.regression_threshold_pct,
                    })
        except (json.JSONDecodeError, KeyError) as e:
            print(f"  [warn] could not load baseline: {e}", file=sys.stderr)

    artifact_payload["regressions"] = regressions
    artifact_payload["regression_count"] = len(regressions)
    artifact_payload["status"] = "fail" if regressions else "pass"

    # Write artifact
    artifact_path = Path(args.artifact)
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(artifact_payload, indent=2) + "\n", encoding="utf-8")
    print(f"\nmemory_profile:{artifact_path}")
    print(f"status: {artifact_payload['status']}")
    if regressions:
        print(f"regressions: {len(regressions)}")
        for reg in regressions:
            print(f"  - {reg['scenario_id']}: {reg['metric']} +{reg['delta_pct']}%")

    return 1 if regressions else 0


if __name__ == "__main__":
    raise SystemExit(main())
