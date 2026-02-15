#!/usr/bin/env python3
"""Validate deterministic E2E script-pack events/manifests/report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if text:
                rows.append(json.loads(text))
    return rows


def ensure_keys(payload: dict[str, Any], keys: list[str], ctx: str, errors: list[str]) -> None:
    for key in keys:
        if key not in payload:
            errors.append(f"{ctx} missing key `{key}`")


def ensure_path(path_str: str, ctx: str, errors: list[str]) -> None:
    if not isinstance(path_str, str) or not path_str:
        errors.append(f"{ctx} must be non-empty path string")
        return
    abs_path = REPO_ROOT / path_str
    if not abs_path.exists():
        errors.append(f"{ctx} path does not exist: {path_str}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--events",
        default="artifacts/e2e/latest/e2e_script_pack_events_v1.jsonl",
        help="Path to JSONL events",
    )
    parser.add_argument(
        "--report",
        default="artifacts/e2e/latest/e2e_script_pack_determinism_report_v1.json",
        help="Path to determinism report JSON",
    )
    parser.add_argument(
        "--schema",
        default="artifacts/e2e/schema/v1/e2e_script_pack_schema_v1.json",
        help="Path to schema JSON",
    )
    parser.add_argument("--output", default="", help="Optional validation report output path")
    args = parser.parse_args()

    schema = load_json(REPO_ROOT / args.schema)
    events_path = REPO_ROOT / args.events
    report_path = REPO_ROOT / args.report
    events = load_jsonl(events_path)
    report = load_json(report_path)

    errors: list[str] = []
    required_scenarios = schema["required_scenarios"]
    required_pass_labels = schema["required_pass_labels"]

    ensure_keys(report, schema["required_report_keys"], "report", errors)
    if report.get("status") != "pass":
        errors.append("report.status must be `pass`")

    if report.get("required_scenarios") != required_scenarios:
        errors.append("report.required_scenarios mismatch schema")
    if report.get("pass_labels") != required_pass_labels:
        errors.append("report.pass_labels mismatch schema")

    if not isinstance(events, list) or not events:
        errors.append("events JSONL must contain at least one row")
        events = []

    by_scenario_pass: dict[tuple[str, str], dict[str, Any]] = {}
    bundle_by_scenario: dict[str, set[str]] = {}
    fingerprint_by_scenario: dict[str, set[str]] = {}
    for event in events:
        if not isinstance(event, dict):
            errors.append("event row must be object")
            continue
        ensure_keys(event, schema["required_event_keys"], "event", errors)
        scenario_id = event.get("scenario_id")
        pass_label = event.get("pass_label")
        if scenario_id not in required_scenarios:
            errors.append(f"event has unexpected scenario_id `{scenario_id}`")
            continue
        if pass_label not in required_pass_labels:
            errors.append(f"event has unexpected pass_label `{pass_label}`")
            continue
        key = (scenario_id, pass_label)
        if key in by_scenario_pass:
            errors.append(f"duplicate event for scenario/pass {key}")
        by_scenario_pass[key] = event

        if event.get("status") != "passed":
            errors.append(f"event {key} has non-passed status `{event.get('status')}`")
        start_ms = event.get("start_unix_ms")
        end_ms = event.get("end_unix_ms")
        duration_ms = event.get("duration_ms")
        if isinstance(start_ms, int) and isinstance(end_ms, int):
            if start_ms > end_ms:
                errors.append(f"event {key} start_unix_ms > end_unix_ms")
            if isinstance(duration_ms, int) and duration_ms != end_ms - start_ms:
                errors.append(f"event {key} duration_ms mismatch")
        else:
            errors.append(f"event {key} start/end timestamps must be integers")

        bundle_id = event.get("bundle_id")
        fingerprint = event.get("stable_fingerprint")
        if isinstance(bundle_id, str):
            bundle_by_scenario.setdefault(scenario_id, set()).add(bundle_id)
        if isinstance(fingerprint, str):
            fingerprint_by_scenario.setdefault(scenario_id, set()).add(fingerprint)

        manifest_path = event.get("bundle_manifest_path", "")
        ensure_path(manifest_path, f"event {key} bundle_manifest_path", errors)
        manifest_abs = REPO_ROOT / manifest_path
        if manifest_abs.exists():
            manifest = load_json(manifest_abs)
            ensure_keys(
                manifest,
                schema["required_bundle_manifest_keys"],
                f"bundle_manifest {key}",
                errors,
            )
            execution_metadata = manifest.get("execution_metadata")
            if isinstance(execution_metadata, dict):
                ensure_keys(
                    execution_metadata,
                    schema["required_execution_metadata_keys"],
                    f"bundle_manifest {key}.execution_metadata",
                    errors,
                )
            else:
                errors.append(f"bundle_manifest {key}.execution_metadata must be object")
            forensics = manifest.get("forensics_links")
            if isinstance(forensics, dict):
                ensure_keys(
                    forensics,
                    schema["required_forensics_keys"],
                    f"bundle_manifest {key}.forensics_links",
                    errors,
                )
            else:
                errors.append(f"bundle_manifest {key}.forensics_links must be object")
            artifact_refs = manifest.get("artifact_refs")
            if not isinstance(artifact_refs, list) or not artifact_refs:
                errors.append(f"bundle_manifest {key}.artifact_refs must be non-empty list")
            else:
                for index, path in enumerate(artifact_refs):
                    ensure_path(path, f"bundle_manifest {key}.artifact_refs[{index}]", errors)
            if manifest.get("bundle_id") != bundle_id:
                errors.append(f"bundle_manifest {key} bundle_id mismatch event")
            if manifest.get("stable_fingerprint") != fingerprint:
                errors.append(f"bundle_manifest {key} stable_fingerprint mismatch event")

    for scenario_id in required_scenarios:
        for pass_label in required_pass_labels:
            if (scenario_id, pass_label) not in by_scenario_pass:
                errors.append(f"missing event for scenario={scenario_id} pass={pass_label}")
        if bundle_by_scenario.get(scenario_id, set()) and len(bundle_by_scenario[scenario_id]) != 1:
            errors.append(f"bundle_id must be stable across passes for {scenario_id}")
        if fingerprint_by_scenario.get(scenario_id, set()) and len(fingerprint_by_scenario[scenario_id]) != 1:
            errors.append(f"stable_fingerprint must be stable across passes for {scenario_id}")

    report_runs = report.get("runs", [])
    if not isinstance(report_runs, list) or len(report_runs) != len(required_scenarios) * len(
        required_pass_labels
    ):
        errors.append("report.runs must include all scenario/pass combinations")

    check_rows = report.get("scenario_checks", [])
    if not isinstance(check_rows, list) or len(check_rows) != len(required_scenarios):
        errors.append("report.scenario_checks must include one row per required scenario")
    else:
        for row in check_rows:
            if not isinstance(row, dict):
                errors.append("scenario_checks rows must be objects")
                continue
            for key in [
                "scenario_id",
                "bundle_id_match",
                "stable_fingerprint_match",
                "status_ok",
            ]:
                if key not in row:
                    errors.append(f"scenario_checks row missing `{key}`")
            if row.get("bundle_id_match") is not True:
                errors.append(f"scenario_checks bundle_id_match false for {row.get('scenario_id')}")
            if row.get("stable_fingerprint_match") is not True:
                errors.append(
                    f"scenario_checks stable_fingerprint_match false for {row.get('scenario_id')}"
                )
            if row.get("status_ok") is not True:
                errors.append(f"scenario_checks status_ok false for {row.get('scenario_id')}")

    report_data = {
        "schema_version": "1.0.0",
        "report_id": "e2e-script-pack-validation-v1",
        "events_path": args.events,
        "determinism_report_path": args.report,
        "ready": len(errors) == 0,
        "error_count": len(errors),
        "errors": errors,
        "summary": {
            "event_count": len(events),
            "required_scenario_count": len(required_scenarios),
            "required_pass_count": len(required_pass_labels),
        },
    }

    if args.output:
        output_path = REPO_ROOT / args.output
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report_data, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(report_data, indent=2))
    return 0 if report_data["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
