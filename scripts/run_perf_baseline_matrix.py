#!/usr/bin/env python3
"""Emit deterministic phase2c performance baseline matrix with env capture."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import subprocess
import tempfile
import time
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
    ordered = sorted(values)
    return {
        "samples": float(len(values)),
        "mean": sum(values) / len(values),
        "p50": percentile(ordered, 0.50),
        "p95": percentile(ordered, 0.95),
        "p99": percentile(ordered, 0.99),
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
    return subprocess.check_output(command, text=True).strip()


def run_once(command: str) -> tuple[float, int]:
    with tempfile.NamedTemporaryFile(prefix="fnx-perf-", suffix=".rss", delete=False) as temp:
        rss_path = Path(temp.name)
    try:
        started = time.perf_counter()
        proc = subprocess.run(
            ["/usr/bin/time", "-f", "%M", "-o", str(rss_path), "bash", "-lc", command],
            text=True,
            capture_output=True,
            check=False,
        )
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        if proc.returncode != 0:
            raise RuntimeError(
                "benchmark command failed\n"
                f"command: {command}\n"
                f"returncode: {proc.returncode}\n"
                f"stdout:\n{proc.stdout}\n"
                f"stderr:\n{proc.stderr}"
            )
        rss_kb = int(rss_path.read_text(encoding="utf-8").strip())
        return elapsed_ms, rss_kb
    finally:
        rss_path.unlink(missing_ok=True)


def max_undirected_edges(node_count: int) -> int:
    return node_count * (node_count - 1) // 2


def estimated_edge_count(scenario: dict[str, object]) -> int:
    topology = scenario["topology"]
    if topology == "grid":
        width = int(scenario["width"])
        height = int(scenario["height"])
        return ((width - 1) * height) + ((height - 1) * width)
    if topology in {"line", "star"}:
        return int(scenario["nodes"]) - 1
    if topology == "complete":
        nodes = int(scenario["nodes"])
        return max_undirected_edges(nodes)
    if topology == "erdos_renyi":
        nodes = int(scenario["nodes"])
        backbone = nodes - 1
        possible = max_undirected_edges(nodes) - backbone
        return backbone + int(round(float(scenario["edge_prob"]) * possible))
    raise ValueError(f"unsupported topology {topology}")


def build_command(
    target_dir: str, cargo_wrapper: str, scenario: dict[str, object]
) -> str:
    parts = [
        f"CARGO_TARGET_DIR={target_dir}",
        f"{cargo_wrapper} run -q -p fnx-algorithms --example bfs_baseline --",
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--artifact",
        default="artifacts/perf/phase2c/perf_baseline_matrix_v1.json",
    )
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--target-dir", default="target-codex")
    parser.add_argument("--cargo-wrapper", default="cargo")
    parser.add_argument(
        "--events-jsonl",
        default="artifacts/perf/phase2c/perf_baseline_matrix_events_v1.jsonl",
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
            "density_class": "sparse_lattice",
        },
        {
            "scenario_id": "line_15000_seed1337",
            "topology": "line",
            "nodes": 15000,
            "seed": 1337,
            "size_bucket": "large",
            "density_class": "ultra_sparse",
        },
        {
            "scenario_id": "star_15000_seed1337",
            "topology": "star",
            "nodes": 15000,
            "seed": 1337,
            "size_bucket": "large",
            "density_class": "hub_sparse",
        },
        {
            "scenario_id": "complete_700_seed1337",
            "topology": "complete",
            "nodes": 700,
            "seed": 1337,
            "size_bucket": "small",
            "density_class": "dense_complete",
        },
        {
            "scenario_id": "erdos_renyi_n2500_p001_seed1337",
            "topology": "erdos_renyi",
            "nodes": 2500,
            "edge_prob": 0.01,
            "seed": 1337,
            "size_bucket": "medium",
            "density_class": "medium_random",
        },
    ]

    scenario_rows = []
    event_rows = []
    for scenario in scenarios:
        command = build_command(args.target_dir, args.cargo_wrapper, scenario)
        node_count = (
            int(scenario["width"]) * int(scenario["height"])
            if scenario["topology"] == "grid"
            else int(scenario["nodes"])
        )
        edge_count_estimate = estimated_edge_count(scenario)

        for warmup_index in range(args.warmup):
            elapsed_ms, rss_kb = run_once(command)
            event_rows.append(
                {
                    "phase": "warmup",
                    "scenario_id": scenario["scenario_id"],
                    "topology": scenario["topology"],
                    "run_index": warmup_index,
                    "seed": int(scenario["seed"]),
                    "node_count": node_count,
                    "edge_count_estimate": edge_count_estimate,
                    "replay_command": command,
                    "elapsed_ms": elapsed_ms,
                    "max_rss_kb": rss_kb,
                }
            )

        times_ms = []
        rss_kb_values = []
        for sample_index in range(args.runs):
            elapsed_ms, rss_kb = run_once(command)
            times_ms.append(elapsed_ms)
            rss_kb_values.append(float(rss_kb))
            event_rows.append(
                {
                    "phase": "measurement",
                    "scenario_id": scenario["scenario_id"],
                    "topology": scenario["topology"],
                    "run_index": sample_index,
                    "seed": int(scenario["seed"]),
                    "node_count": node_count,
                    "edge_count_estimate": edge_count_estimate,
                    "replay_command": command,
                    "elapsed_ms": elapsed_ms,
                    "max_rss_kb": rss_kb,
                }
            )

        density_estimate = edge_count_estimate / max_undirected_edges(node_count)

        scenario_rows.append(
            {
                "scenario_id": scenario["scenario_id"],
                "topology": scenario["topology"],
                "size_bucket": scenario["size_bucket"],
                "density_class": scenario["density_class"],
                "seed": int(scenario["seed"]),
                "command": command,
                "node_count": node_count,
                "edge_count_estimate": edge_count_estimate,
                "density_estimate": density_estimate,
                "sample_count": len(times_ms),
                "time_ms": summarize(times_ms),
                "max_rss_kb": summarize(rss_kb_values),
            }
        )

    environment = {
        "hostname": platform.node(),
        "os": platform.platform(),
        "cpu_model": cpu_model(),
        "python_version": platform.python_version(),
        "cargo_version": shell_output(["cargo", "--version"]),
        "rustc_version": shell_output(["rustc", "--version", "--verbose"]),
        "git_commit": shell_output(["git", "rev-parse", "HEAD"]),
    }
    environment_fingerprint = hashlib.sha256(
        json.dumps(environment, sort_keys=True).encode("utf-8")
    ).hexdigest()

    artifact_payload = {
        "schema_version": "1.0.0",
        "matrix_id": "phase2c-perf-baseline-matrix-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "events_path": args.events_jsonl,
        "measurement_protocol": {
            "runs": args.runs,
            "warmup_runs": args.warmup,
            "timer": "python.time.perf_counter",
            "memory_capture": "/usr/bin/time -f %M",
            "fixed_seed_policy": "explicit per-scenario seed",
            "target_dir": args.target_dir,
        },
        "environment": environment,
        "environment_fingerprint": environment_fingerprint,
        "scenario_count": len(scenario_rows),
        "scenarios": scenario_rows,
        "summary": {
            "topology_classes": sorted({row["topology"] for row in scenario_rows}),
            "size_buckets": sorted({row["size_bucket"] for row in scenario_rows}),
            "density_classes": sorted({row["density_class"] for row in scenario_rows}),
            "max_p95_ms": max(row["time_ms"]["p95"] for row in scenario_rows),
            "max_p99_ms": max(row["time_ms"]["p99"] for row in scenario_rows),
            "max_memory_p95_kb": max(row["max_rss_kb"]["p95"] for row in scenario_rows),
        },
    }

    artifact_path = Path(args.artifact)
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(artifact_payload, indent=2) + "\n", encoding="utf-8")
    events_path = Path(args.events_jsonl)
    events_path.parent.mkdir(parents=True, exist_ok=True)
    events_path.write_text(
        "".join(json.dumps(row) + "\n" for row in event_rows), encoding="utf-8"
    )
    print(f"perf_baseline_matrix:{artifact_path}")
    print(f"perf_baseline_events:{events_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
