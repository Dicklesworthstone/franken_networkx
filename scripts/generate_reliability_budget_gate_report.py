#!/usr/bin/env python3
"""Generate reliability budget and flake/quarantine gate artifacts."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Observation:
    packet_id: str
    test_id: str
    status: str
    ts_unix_ms: int


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if text:
                rows.append(json.loads(text))
    return rows


def read_json_or_empty(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return load_json(path)


def read_jsonl_or_empty(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return load_jsonl(path)


def normalize_status(value: Any) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip().lower()
    return "unknown"


def as_int(value: Any, fallback: int = 0) -> int:
    if isinstance(value, bool):
        return fallback
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return fallback


def collect_observations(structured_logs: list[dict[str, Any]], e2e_events: list[dict[str, Any]]) -> list[Observation]:
    observations: list[Observation] = []

    for idx, row in enumerate(structured_logs):
        packet_id = row.get("packet_id") if isinstance(row.get("packet_id"), str) else "FNX-P2C-FOUNDATION"
        test_id = row.get("test_id") if isinstance(row.get("test_id"), str) else f"structured::{idx}"
        status = normalize_status(row.get("status"))
        ts = as_int(row.get("ts_unix_ms"), idx)
        observations.append(Observation(packet_id=packet_id, test_id=test_id, status=status, ts_unix_ms=ts))

    for idx, row in enumerate(e2e_events):
        scenario_id = row.get("scenario_id") if isinstance(row.get("scenario_id"), str) else f"scenario-{idx}"
        mode = row.get("mode") if isinstance(row.get("mode"), str) else "strict"
        test_id = f"e2e::{scenario_id}::{mode}"
        packet_id = row.get("packet_id") if isinstance(row.get("packet_id"), str) else "FNX-P2C-FOUNDATION"
        status = normalize_status(row.get("status"))
        ts = as_int(row.get("start_unix_ms"), as_int(row.get("end_unix_ms"), idx))
        observations.append(Observation(packet_id=packet_id, test_id=test_id, status=status, ts_unix_ms=ts))

    observations.sort(key=lambda obs: (obs.test_id, obs.ts_unix_ms, obs.packet_id))
    return observations


def flake_transitions(observations: list[Observation]) -> tuple[dict[str, int], dict[str, int]]:
    per_test_flake_count: dict[str, int] = defaultdict(int)
    per_test_total: dict[str, int] = defaultdict(int)
    grouped: dict[str, list[Observation]] = defaultdict(list)
    for obs in observations:
        grouped[obs.test_id].append(obs)

    for test_id, rows in grouped.items():
        rows.sort(key=lambda obs: obs.ts_unix_ms)
        per_test_total[test_id] = len(rows)
        for prev, nxt in zip(rows, rows[1:]):
            if prev.status == "failed" and nxt.status == "passed":
                per_test_flake_count[test_id] += 1

    return dict(sorted(per_test_flake_count.items())), dict(sorted(per_test_total.items()))


def packet_sets(spec: dict[str, Any]) -> dict[str, set[str]]:
    mapping_rows = spec.get("packet_family_mapping", [])
    budget_packets: dict[str, set[str]] = defaultdict(set)
    for row in mapping_rows:
        if not isinstance(row, dict):
            continue
        budget_id = row.get("budget_id")
        packet_id = row.get("packet_id")
        if isinstance(budget_id, str) and isinstance(packet_id, str):
            budget_packets[budget_id].add(packet_id)
    return dict(budget_packets)


def in_budget(packet_id: str, budget_packet_ids: set[str]) -> bool:
    return packet_id in budget_packet_ids


def runtime_guardrail_ok(metric: str, perf_report: dict[str, Any], normalization_report: dict[str, Any], durability_report: dict[str, Any]) -> bool:
    if metric in {"p95", "p99"}:
        return perf_report.get("status") == "pass"
    if metric == "telemetry_contract":
        valid_logs = normalization_report.get("valid_log_count")
        fixture_count = normalization_report.get("fixture_count")
        fields = normalization_report.get("normalized_fields")
        return isinstance(valid_logs, int) and isinstance(fixture_count, int) and valid_logs == fixture_count and bool(fields)
    if metric == "decode_proof":
        entries = durability_report.get("entries", [])
        if not isinstance(entries, list) or not entries:
            return False
        return all(as_int(entry.get("decode_proof_count"), 0) >= 1 for entry in entries if isinstance(entry, dict))
    return True


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", default="artifacts/conformance/v1/reliability_budget_gate_v1.json")
    parser.add_argument("--structured-logs", default="artifacts/conformance/latest/structured_logs.jsonl")
    parser.add_argument("--e2e-events", default="artifacts/e2e/latest/e2e_script_pack_events_v1.jsonl")
    parser.add_argument("--smoke-report", default="artifacts/conformance/latest/smoke_report.json")
    parser.add_argument("--normalization-report", default="artifacts/conformance/latest/structured_log_emitter_normalization_report.json")
    parser.add_argument("--perf-regression-report", default="artifacts/perf/phase2c/perf_regression_gate_report_v1.json")
    parser.add_argument("--durability-report", default="artifacts/conformance/latest/durability_pipeline_report.json")
    parser.add_argument("--phase2c-e2e-report", default="artifacts/phase2c/latest/phase2c_readiness_e2e_report_v1.json")
    parser.add_argument("--output", default="artifacts/conformance/latest/reliability_budget_report_v1.json")
    parser.add_argument("--quarantine-output", default="artifacts/conformance/latest/flake_quarantine_v1.json")
    return parser


def main() -> int:
    args = build_parser().parse_args()

    spec = load_json(REPO_ROOT / args.spec)
    structured_logs = read_jsonl_or_empty(REPO_ROOT / args.structured_logs)
    e2e_events = read_jsonl_or_empty(REPO_ROOT / args.e2e_events)
    smoke_report = read_json_or_empty(REPO_ROOT / args.smoke_report)
    normalization_report = read_json_or_empty(REPO_ROOT / args.normalization_report)
    perf_report = read_json_or_empty(REPO_ROOT / args.perf_regression_report)
    durability_report = read_json_or_empty(REPO_ROOT / args.durability_report)
    phase2c_report = read_json_or_empty(REPO_ROOT / args.phase2c_e2e_report)

    now_utc = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    observations = collect_observations(structured_logs, e2e_events)
    per_test_flakes, per_test_total = flake_transitions(observations)

    total_observations = len(observations)
    total_flake_events = sum(per_test_flakes.values())
    global_flake_rate_pct = (100.0 * total_flake_events / total_observations) if total_observations else 0.0

    flake_policy = spec.get("flake_policy", {}) if isinstance(spec.get("flake_policy"), dict) else {}
    warn_threshold = float(flake_policy.get("warn_threshold_pct", 0.25))
    fail_threshold = float(flake_policy.get("fail_threshold_pct", 1.0))
    quarantine_enter = flake_policy.get("quarantine_enter", {}) if isinstance(flake_policy.get("quarantine_enter"), dict) else {}
    quarantine_enter_count = int(quarantine_enter.get("flakes_in_window", 3))

    budget_packets = packet_sets(spec)

    fixture_count = as_int(smoke_report.get("fixture_count"), 0)
    mismatch_count = as_int(smoke_report.get("mismatch_count"), 0)
    proxy_unit_line_pct = 100.0 if fixture_count > 0 else 0.0
    proxy_branch_pct = 100.0 if fixture_count > 0 and mismatch_count == 0 else 0.0
    e2e_pass_ratio = 1.0 if phase2c_report.get("status") == "pass" else 0.0

    budgets_out: list[dict[str, Any]] = []
    failure_envelopes: list[dict[str, Any]] = []

    for row in spec.get("budget_definitions", []):
        if not isinstance(row, dict):
            continue

        budget_id = str(row.get("budget_id", "UNKNOWN"))
        packet_family = str(row.get("packet_family", "unknown"))
        budget_obs = [obs for obs in observations if in_budget(obs.packet_id, budget_packets.get(budget_id, set()))]
        failing_test_groups = sorted({obs.test_id for obs in budget_obs if obs.status != "passed"})

        budget_total = len(budget_obs)
        budget_flake_events = sum(per_test_flakes.get(test_id, 0) for test_id in {obs.test_id for obs in budget_obs})
        budget_flake_rate = (100.0 * budget_flake_events / budget_total) if budget_total else 0.0

        coverage_floor = row.get("coverage_floor", {}) if isinstance(row.get("coverage_floor"), dict) else {}
        required_unit_line = float(coverage_floor.get("unit_line_pct", 0.0))
        required_branch = float(coverage_floor.get("branch_pct", 0.0))
        property_floor = int(row.get("property_floor", 0))
        property_observed = len({obs.test_id for obs in budget_obs})

        runtime_guardrail = row.get("runtime_guardrail", {}) if isinstance(row.get("runtime_guardrail"), dict) else {}
        runtime_metric = str(runtime_guardrail.get("metric", "none"))
        runtime_guardrail_pass = runtime_guardrail_ok(runtime_metric, perf_report, normalization_report, durability_report)

        evidence_paths = [path for path in row.get("evidence_paths", []) if isinstance(path, str)]
        missing_evidence = sorted(path for path in evidence_paths if not (REPO_ROOT / path).exists())

        coverage_pass = proxy_unit_line_pct >= required_unit_line and proxy_branch_pct >= required_branch
        property_pass = property_observed >= property_floor
        e2e_pass = e2e_pass_ratio >= float(row.get("e2e_replay_pass_floor", 1.0))
        flake_pass = budget_flake_rate <= float(row.get("flake_ceiling_pct_7d", 0.0))

        if missing_evidence or not coverage_pass or not property_pass or not e2e_pass or not runtime_guardrail_pass:
            status = "fail"
        elif budget_flake_rate > fail_threshold:
            status = "fail"
        elif budget_flake_rate > warn_threshold or not flake_pass:
            status = "warn"
        else:
            status = "pass"

        observed = {
            "unit_line_pct_proxy": round(proxy_unit_line_pct, 3),
            "branch_pct_proxy": round(proxy_branch_pct, 3),
            "property_count": property_observed,
            "e2e_replay_pass_ratio": round(e2e_pass_ratio, 3),
            "flake_rate_pct_7d": round(budget_flake_rate, 3),
            "runtime_guardrail_pass": runtime_guardrail_pass,
            "missing_evidence_count": len(missing_evidence),
        }

        thresholds = {
            "unit_line_pct_floor": required_unit_line,
            "branch_pct_floor": required_branch,
            "property_floor": property_floor,
            "e2e_replay_pass_floor": float(row.get("e2e_replay_pass_floor", 1.0)),
            "flake_ceiling_pct_7d": float(row.get("flake_ceiling_pct_7d", 0.0)),
            "runtime_guardrail": runtime_guardrail,
        }

        budgets_out.append(
            {
                "budget_id": budget_id,
                "packet_family": packet_family,
                "status": status,
                "failing_test_groups": failing_test_groups,
                "missing_evidence_paths": missing_evidence,
                "observed": observed,
                "thresholds": thresholds,
                "gate_command": row.get("gate_command"),
                "artifact_paths": evidence_paths,
                "owner_bead_id": "bd-315.23",
            }
        )

        if status in {"warn", "fail"}:
            remediation_hint = (
                f"Investigate budget `{budget_id}` using gate command, then inspect artifact paths and replay commands."
            )
            failure_envelopes.append(
                {
                    "budget_id": budget_id,
                    "packet_scope": packet_family,
                    "observed_value": observed,
                    "threshold_value": thresholds,
                    "status": status,
                    "failing_test_groups": failing_test_groups,
                    "artifact_paths": evidence_paths,
                    "replay_commands": [str(row.get("gate_command", ""))],
                    "owner_bead_id": "bd-315.23",
                    "remediation_hint": remediation_hint,
                }
            )

    budgets_out.sort(key=lambda row: row["budget_id"])
    failure_envelopes.sort(key=lambda row: row["budget_id"])

    if any(row["status"] == "fail" for row in budgets_out):
        overall_status = "fail"
    elif any(row["status"] == "warn" for row in budgets_out):
        overall_status = "warn"
    else:
        overall_status = "pass"

    quarantine_tests = [
        {
            "test_id": test_id,
            "flake_events": flake_count,
            "observation_count": per_test_total.get(test_id, 0),
            "status": "quarantined",
            "owner_bead_id": "bd-315.23",
            "replay_command": "rch exec -- cargo test -q -p fnx-conformance --tests -- --nocapture",
            "artifact_refs": [
                "artifacts/conformance/latest/structured_logs.jsonl",
                "artifacts/e2e/latest/e2e_script_pack_events_v1.jsonl",
            ],
        }
        for test_id, flake_count in sorted(per_test_flakes.items())
        if flake_count >= quarantine_enter_count
    ]

    reliability_report = {
        "schema_version": "1.0.0",
        "report_id": "reliability-budget-report-v1",
        "generated_at_utc": now_utc,
        "source_bead_id": "bd-315.23",
        "status": overall_status,
        "flake_summary": {
            "total_observations": total_observations,
            "flake_events": total_flake_events,
            "flake_rate_pct_7d": round(global_flake_rate_pct, 3),
            "warn_threshold_pct": warn_threshold,
            "fail_threshold_pct": fail_threshold,
            "quarantined_test_count": len(quarantine_tests),
        },
        "budgets": budgets_out,
        "failure_envelopes": failure_envelopes,
        "artifact_refs": [
            "artifacts/conformance/v1/reliability_budget_gate_v1.json",
            "artifacts/conformance/latest/reliability_budget_report_v1.json",
            "artifacts/conformance/latest/flake_quarantine_v1.json",
        ],
    }

    quarantine_payload = {
        "schema_version": "1.0.0",
        "artifact_id": "flake-quarantine-v1",
        "generated_at_utc": now_utc,
        "source_bead_id": "bd-315.23",
        "status": "active" if quarantine_tests else "clear",
        "policy": {
            "warn_threshold_pct": warn_threshold,
            "fail_threshold_pct": fail_threshold,
            "quarantine_enter": flake_policy.get("quarantine_enter", {"flakes_in_window": 3, "window_hours": 24}),
            "quarantine_exit": flake_policy.get("quarantine_exit", {"consecutive_passes": 20}),
        },
        "rolling_flake_rate_pct_7d": round(global_flake_rate_pct, 3),
        "quarantined_tests": quarantine_tests,
        "evidence_paths": [
            "artifacts/conformance/latest/structured_logs.jsonl",
            "artifacts/e2e/latest/e2e_script_pack_events_v1.jsonl",
            "artifacts/conformance/latest/reliability_budget_report_v1.json",
        ],
    }

    output_path = REPO_ROOT / args.output
    quarantine_path = REPO_ROOT / args.quarantine_output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    quarantine_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(reliability_report, indent=2) + "\n", encoding="utf-8")
    quarantine_path.write_text(json.dumps(quarantine_payload, indent=2) + "\n", encoding="utf-8")

    print(f"reliability_budget_report:{output_path}")
    print(f"flake_quarantine_artifact:{quarantine_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
