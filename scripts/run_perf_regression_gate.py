#!/usr/bin/env python3
"""Evaluate perf drift between baseline and candidate matrices with fail-closed policy."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def pct_delta(candidate: float, baseline: float) -> float:
    if baseline == 0.0:
        return 0.0
    return ((candidate - baseline) / baseline) * 100.0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--baseline",
        default="artifacts/perf/phase2c/perf_baseline_matrix_v1.json",
    )
    parser.add_argument(
        "--candidate",
        default="artifacts/perf/latest/perf_baseline_matrix_v1.json",
    )
    parser.add_argument(
        "--hotspot-backlog",
        default="artifacts/perf/phase2c/hotspot_one_lever_backlog_v1.json",
    )
    parser.add_argument(
        "--report",
        default="artifacts/perf/phase2c/perf_regression_gate_report_v1.json",
    )
    args = parser.parse_args()

    baseline_path = Path(args.baseline)
    candidate_path = Path(args.candidate)
    hotspot_path = Path(args.hotspot_backlog)
    report_path = Path(args.report)

    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    hotspot = json.loads(hotspot_path.read_text(encoding="utf-8"))

    baseline_by_id = {row["scenario_id"]: row for row in baseline["scenarios"]}
    candidate_by_id = {row["scenario_id"]: row for row in candidate["scenarios"]}

    critical_ids = {
        row["target_scenario_id"]
        for row in hotspot["optimization_backlog"]
        if int(row["rank"]) <= 2
    }
    fallback_by_id = {
        row["target_scenario_id"]: row["fallback_trigger"]
        for row in hotspot["optimization_backlog"]
    }

    policy = {
        "critical_latency_tail_pct_threshold": 5.0,
        "critical_memory_pct_threshold": 5.0,
        "noncritical_latency_tail_pct_threshold": 10.0,
        "noncritical_memory_pct_threshold": 12.0,
        "critical_fail_closed": True,
    }

    deltas = []
    regressions = []
    for scenario_id, candidate_row in candidate_by_id.items():
        baseline_row = baseline_by_id.get(scenario_id)
        if baseline_row is None:
            regressions.append(
                {
                    "scenario_id": scenario_id,
                    "severity": "critical",
                    "reason": "missing_baseline_scenario",
                    "fallback_trigger": fallback_by_id.get(scenario_id),
                }
            )
            continue

        p95_delta = pct_delta(
            float(candidate_row["time_ms"]["p95"]), float(baseline_row["time_ms"]["p95"])
        )
        p99_delta = pct_delta(
            float(candidate_row["time_ms"]["p99"]), float(baseline_row["time_ms"]["p99"])
        )
        memory_delta = pct_delta(
            float(candidate_row["max_rss_kb"]["p95"]),
            float(baseline_row["max_rss_kb"]["p95"]),
        )
        is_critical = scenario_id in critical_ids
        latency_threshold = (
            policy["critical_latency_tail_pct_threshold"]
            if is_critical
            else policy["noncritical_latency_tail_pct_threshold"]
        )
        memory_threshold = (
            policy["critical_memory_pct_threshold"]
            if is_critical
            else policy["noncritical_memory_pct_threshold"]
        )
        regressed = (
            p95_delta > latency_threshold
            or p99_delta > latency_threshold
            or memory_delta > memory_threshold
        )

        deltas.append(
            {
                "scenario_id": scenario_id,
                "critical_path": is_critical,
                "baseline_comparator": str(baseline_path),
                "hotspot_ref": str(hotspot_path),
                "delta_pct": {
                    "p95_ms": p95_delta,
                    "p99_ms": p99_delta,
                    "memory_p95_kb": memory_delta,
                },
                "threshold_pct": {
                    "latency_tail": latency_threshold,
                    "memory": memory_threshold,
                },
                "regressed": regressed,
            }
        )

        if regressed:
            regressions.append(
                {
                    "scenario_id": scenario_id,
                    "severity": "critical" if is_critical else "warning",
                    "reason": "tail_or_memory_threshold_exceeded",
                    "fallback_trigger": fallback_by_id.get(scenario_id),
                    "rollback_path": "git revert <optimization-commit-sha>",
                }
            )

    critical_regressions = [
        row for row in regressions if row.get("severity") == "critical"
    ]
    status = "fail" if (policy["critical_fail_closed"] and critical_regressions) else "pass"

    report = {
        "schema_version": "1.0.0",
        "report_id": "phase2c-perf-regression-gate-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "baseline_path": str(baseline_path),
        "candidate_path": str(candidate_path),
        "hotspot_backlog_path": str(hotspot_path),
        "policy": policy,
        "scenario_deltas": deltas,
        "regressions": regressions,
        "summary": {
            "scenario_count": len(deltas),
            "regression_count": len(regressions),
            "critical_regression_count": len(critical_regressions),
        },
        "status": status,
    }

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"perf_regression_gate_report:{report_path}")
    if status == "fail":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
