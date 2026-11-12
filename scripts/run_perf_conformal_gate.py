#!/usr/bin/env python3
"""Generate conformal prediction bands for perf matrix and gate regressions."""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path


def iter_history(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows.append(json.loads(line))
    return rows


def split_conformal_upper(samples: list[float], alpha: float) -> float | None:
    if not samples:
        return None
    ordered = sorted(samples)
    n = len(ordered)
    rank = math.ceil((n + 1) * (1.0 - alpha)) - 1
    rank = max(0, min(rank, n - 1))
    return ordered[rank]


def split_conformal_lower(samples: list[float], alpha: float) -> float | None:
    if not samples:
        return None
    ordered = sorted(samples)
    n = len(ordered)
    rank = math.floor((n + 1) * alpha) - 1
    rank = max(0, min(rank, n - 1))
    return ordered[rank]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--history",
        default="artifacts/perf/history/perf_baseline_run_history_v1.jsonl",
    )
    parser.add_argument(
        "--candidate",
        default="artifacts/perf/latest/perf_baseline_matrix_v1.json",
    )
    parser.add_argument(
        "--report",
        default="artifacts/perf/latest/perf_conformal_gate_report_v1.json",
    )
    parser.add_argument("--alpha", type=float, default=0.05)
    parser.add_argument("--min-samples", type=int, default=5)
    args = parser.parse_args()

    history_path = Path(args.history)
    candidate_path = Path(args.candidate)
    report_path = Path(args.report)

    if not history_path.exists():
        raise SystemExit(f"missing history file: {history_path}")
    if not candidate_path.exists():
        raise SystemExit(f"missing candidate matrix: {candidate_path}")

    history = iter_history(history_path)
    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))

    candidate_env = candidate.get("environment_fingerprint")
    filtered = [
        row for row in history if row.get("environment_fingerprint") == candidate_env
    ]
    history_rows = filtered if filtered else history
    environment_note = (
        "matched_environment_fingerprint"
        if filtered
        else "no_environment_match_using_all_history"
    )

    samples: dict[str, dict[str, list[float]]] = {}
    for row in history_rows:
        event = row.get("event", {})
        if event.get("phase") != "measurement":
            continue
        scenario_id = event.get("scenario_id")
        if not scenario_id:
            continue
        entry = samples.setdefault(scenario_id, {"elapsed_ms": [], "max_rss_kb": []})
        if event.get("elapsed_ms") is not None:
            entry["elapsed_ms"].append(float(event["elapsed_ms"]))
        if event.get("max_rss_kb") is not None:
            entry["max_rss_kb"].append(float(event["max_rss_kb"]))

    alpha = float(args.alpha)
    min_samples = int(args.min_samples)

    scenario_reports = []
    regressions = []
    insufficient = []

    for row in candidate.get("scenarios", []):
        scenario_id = row["scenario_id"]
        history_samples = samples.get(scenario_id, {"elapsed_ms": [], "max_rss_kb": []})
        time_samples = history_samples["elapsed_ms"]
        mem_samples = history_samples["max_rss_kb"]

        time_band = None
        mem_band = None
        if len(time_samples) >= min_samples:
            time_band = {
                "lower": split_conformal_lower(time_samples, alpha),
                "upper": split_conformal_upper(time_samples, alpha),
            }
        if len(mem_samples) >= min_samples:
            mem_band = {
                "lower": split_conformal_lower(mem_samples, alpha),
                "upper": split_conformal_upper(mem_samples, alpha),
            }

        candidate_p95 = float(row["time_ms"]["p95"])
        candidate_mem = float(row["max_rss_kb"]["p95"])
        time_regressed = time_band is not None and candidate_p95 > time_band["upper"]
        mem_regressed = mem_band is not None and candidate_mem > mem_band["upper"]

        status = "ok"
        if time_band is None or mem_band is None:
            status = "insufficient_history"
            insufficient.append(scenario_id)
        if time_regressed or mem_regressed:
            status = "regressed"
            regressions.append(
                {
                    "scenario_id": scenario_id,
                    "time_p95_ms": candidate_p95,
                    "memory_p95_kb": candidate_mem,
                    "time_upper_ms": None if time_band is None else time_band["upper"],
                    "memory_upper_kb": None if mem_band is None else mem_band["upper"],
                }
            )

        scenario_reports.append(
            {
                "scenario_id": scenario_id,
                "history_samples": {
                    "elapsed_ms": len(time_samples),
                    "max_rss_kb": len(mem_samples),
                },
                "candidate_p95_ms": candidate_p95,
                "candidate_memory_p95_kb": candidate_mem,
                "time_band": time_band,
                "memory_band": mem_band,
                "status": status,
            }
        )

    fail_closed_on_insufficient = True
    status = "pass"
    if regressions:
        status = "fail"
    if fail_closed_on_insufficient and insufficient:
        status = "fail"

    report = {
        "schema_version": "1.0.0",
        "report_id": "perf-conformal-gate-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "history_path": str(history_path),
        "candidate_path": str(candidate_path),
        "environment_fingerprint": candidate_env,
        "environment_filtering": environment_note,
        "policy": {
            "alpha": alpha,
            "min_samples": min_samples,
            "fail_closed_on_insufficient_history": fail_closed_on_insufficient,
        },
        "scenario_reports": scenario_reports,
        "summary": {
            "scenario_count": len(scenario_reports),
            "regression_count": len(regressions),
            "insufficient_history_count": len(insufficient),
        },
        "regressions": regressions,
        "status": status,
    }

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"perf_conformal_gate_report:{report_path}")
    if status == "fail":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
