#!/usr/bin/env python3
"""Run deterministic E2E script pack and emit bundle manifests/logs."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFORMANCE_LATEST = REPO_ROOT / "artifacts/conformance/latest"
SCENARIO_MATRIX_PATH = (
    REPO_ROOT / "artifacts/e2e/v1/e2e_scenario_matrix_oracle_contract_v1.json"
)

EVENT_SCHEMA_VERSION = "1.0.0"
BUNDLE_SCHEMA_VERSION = "1.0.0"
REPORT_SCHEMA_VERSION = "1.0.0"


@dataclass(frozen=True)
class ScenarioSpec:
    scenario_id: str
    scenario_kind: str
    journey_id: str
    mode: str
    fixture_id: str
    packet_id: str


SCENARIOS: tuple[ScenarioSpec, ...] = (
    ScenarioSpec(
        scenario_id="happy_path",
        scenario_kind="happy_path",
        journey_id="J-GRAPH-CORE",
        mode="strict",
        fixture_id="graph_core_shortest_path_strict.json",
        packet_id="FNX-P2C-001",
    ),
    ScenarioSpec(
        scenario_id="edge_path",
        scenario_kind="edge_path",
        journey_id="J-CENTRALITY",
        mode="strict",
        fixture_id="generated/centrality_closeness_strict.json",
        packet_id="FNX-P2C-005",
    ),
    ScenarioSpec(
        scenario_id="malformed_input",
        scenario_kind="malformed_input",
        journey_id="J-READWRITE",
        mode="hardened",
        fixture_id="generated/readwrite_hardened_malformed.json",
        packet_id="FNX-P2C-006",
    ),
)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def fnv1a64(text: str) -> str:
    value = 0xCBF29CE484222325
    for byte in text.encode("utf-8"):
        value ^= byte
        value = (value * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return f"{value:016x}"


def unix_ms() -> int:
    return int(time.time() * 1000)


def sanitize_label(label: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in label)


def scenario_seed_map() -> dict[tuple[str, str], int]:
    matrix = load_json(SCENARIO_MATRIX_PATH)
    by_journey_mode: dict[tuple[str, str], int] = {}
    for journey in matrix.get("journeys", []):
        journey_id = journey.get("journey_id")
        strict_path = journey.get("strict_path", {})
        hardened_path = journey.get("hardened_path", {})
        if isinstance(journey_id, str):
            if isinstance(strict_path.get("deterministic_seed"), int):
                by_journey_mode[(journey_id, "strict")] = strict_path["deterministic_seed"]
            if isinstance(hardened_path.get("deterministic_seed"), int):
                by_journey_mode[(journey_id, "hardened")] = hardened_path["deterministic_seed"]
    return by_journey_mode


def conformance_command(fixture_id: str, mode: str) -> str:
    return (
        "rch exec -- cargo run -q -p fnx-conformance --bin run_smoke -- "
        f"--fixture {fixture_id} --mode {mode}"
    )


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def copy_if_exists(source: Path, target: Path) -> None:
    if source.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def repo_relative(path: Path) -> str:
    if not path.is_absolute():
        return path.as_posix()
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def parse_structured_logs() -> list[dict[str, Any]]:
    path = CONFORMANCE_LATEST / "structured_logs.jsonl"
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if text:
                rows.append(json.loads(text))
    return rows


def find_log_for_fixture(logs: list[dict[str, Any]], fixture_id: str, mode: str) -> dict[str, Any] | None:
    for row in logs:
        if row.get("fixture_id") == fixture_id and row.get("mode") == mode:
            return row
    return None


def run_scenario(
    *,
    run_id: str,
    pass_label: str,
    scenario: ScenarioSpec,
    deterministic_seed: int,
    output_dir: Path,
    events_path: Path,
) -> dict[str, Any]:
    command = conformance_command(scenario.fixture_id, scenario.mode)
    start_ms = unix_ms()
    completed = subprocess.run(
        ["bash", "-lc", command],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    end_ms = unix_ms()
    duration_ms = end_ms - start_ms
    status = "passed" if completed.returncode == 0 else "failed"
    reason_code = None if status == "passed" else "command_failed"

    bundle_id = (
        "e2e-bundle-"
        + fnv1a64(
            "|".join(
                [
                    BUNDLE_SCHEMA_VERSION,
                    scenario.scenario_id,
                    scenario.mode,
                    scenario.fixture_id,
                    str(deterministic_seed),
                ]
            )
        )
    )
    stable_fingerprint = fnv1a64(
        "|".join(
            [
                scenario.scenario_id,
                scenario.scenario_kind,
                scenario.journey_id,
                scenario.packet_id,
                scenario.mode,
                scenario.fixture_id,
                str(deterministic_seed),
            ]
        )
    )

    scenario_dir = output_dir / "bundles" / scenario.scenario_id / pass_label
    scenario_dir.mkdir(parents=True, exist_ok=True)
    command_log_path = scenario_dir / "command.log"
    command_log_path.write_text(
        completed.stdout + ("\n" if completed.stdout else "") + completed.stderr,
        encoding="utf-8",
    )

    smoke_report_path = CONFORMANCE_LATEST / "smoke_report.json"
    structured_logs_path = CONFORMANCE_LATEST / "structured_logs.jsonl"
    fixture_report_name = f"{sanitize_label(scenario.fixture_id)}.report.json"
    fixture_report_path = CONFORMANCE_LATEST / fixture_report_name

    copied_smoke = scenario_dir / "smoke_report.json"
    copied_structured_logs = scenario_dir / "structured_logs.jsonl"
    copied_fixture_report = scenario_dir / "fixture_report.json"
    copy_if_exists(smoke_report_path, copied_smoke)
    copy_if_exists(structured_logs_path, copied_structured_logs)
    copy_if_exists(fixture_report_path, copied_fixture_report)

    logs = parse_structured_logs()
    log_row = find_log_for_fixture(logs, scenario.fixture_id, scenario.mode)
    selected_log_path = scenario_dir / "selected_structured_log.json"
    if log_row is not None:
        write_json(selected_log_path, log_row)

    manifest = {
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "artifact_id": "e2e-script-pack-bundle-manifest-v1",
        "bundle_id": bundle_id,
        "stable_fingerprint": stable_fingerprint,
        "scenario_id": scenario.scenario_id,
        "scenario_kind": scenario.scenario_kind,
        "journey_id": scenario.journey_id,
        "packet_id": scenario.packet_id,
        "mode": scenario.mode,
        "fixture_id": scenario.fixture_id,
        "deterministic_seed": deterministic_seed,
        "replay_command": (
            "CARGO_TARGET_DIR=target-codex cargo run -q -p fnx-conformance "
            f"--bin run_smoke -- --fixture {scenario.fixture_id} --mode {scenario.mode}"
        ),
        "execution_metadata": {
            "run_id": run_id,
            "pass_label": pass_label,
            "status": status,
            "reason_code": reason_code,
            "start_unix_ms": start_ms,
            "end_unix_ms": end_ms,
            "duration_ms": duration_ms,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        },
        "forensics_links": {
            "structured_log_hash_id": None if log_row is None else log_row.get("hash_id"),
            "forensic_bundle_id": None
            if log_row is None
            else log_row.get("forensic_bundle_id"),
            "forensics_bundle_hash_id": None
            if log_row is None
            else log_row.get("forensics_bundle_index", {}).get("bundle_hash_id"),
            "forensics_bundle_replay_ref": None
            if log_row is None
            else log_row.get("forensics_bundle_index", {}).get("replay_ref"),
        },
        "artifact_refs": [
            repo_relative(copied_smoke),
            repo_relative(copied_fixture_report),
            repo_relative(copied_structured_logs),
            repo_relative(command_log_path),
            repo_relative(selected_log_path),
        ],
    }
    manifest_path = scenario_dir / "bundle_manifest_v1.json"
    write_json(manifest_path, manifest)

    event = {
        "schema_version": EVENT_SCHEMA_VERSION,
        "run_id": run_id,
        "scenario_id": scenario.scenario_id,
        "scenario_kind": scenario.scenario_kind,
        "journey_id": scenario.journey_id,
        "packet_id": scenario.packet_id,
        "pass_label": pass_label,
        "fixture_id": scenario.fixture_id,
        "mode": scenario.mode,
        "deterministic_seed": deterministic_seed,
        "command": command,
        "status": status,
        "reason_code": reason_code,
        "start_unix_ms": start_ms,
        "end_unix_ms": end_ms,
        "duration_ms": duration_ms,
        "bundle_id": bundle_id,
        "stable_fingerprint": stable_fingerprint,
        "bundle_manifest_path": repo_relative(manifest_path),
        "artifact_refs": manifest["artifact_refs"],
    }
    append_jsonl(events_path, event)

    return {
        "scenario_id": scenario.scenario_id,
        "pass_label": pass_label,
        "status": status,
        "reason_code": reason_code,
        "bundle_id": bundle_id,
        "stable_fingerprint": stable_fingerprint,
        "bundle_manifest_path": repo_relative(manifest_path),
    }


def determinism_report(
    *,
    run_id: str,
    output_dir: Path,
    run_results: list[dict[str, Any]],
    expected_passes: list[str],
    expected_scenarios: list[str],
) -> dict[str, Any]:
    by_scenario: dict[str, dict[str, dict[str, Any]]] = {}
    for row in run_results:
        by_scenario.setdefault(row["scenario_id"], {})[row["pass_label"]] = row

    checks = []
    failures = []
    for scenario_id in expected_scenarios:
        passes = by_scenario.get(scenario_id, {})
        missing = [label for label in expected_passes if label not in passes]
        if missing:
            failures.append(f"{scenario_id}: missing passes {missing}")
            continue
        baseline = passes[expected_passes[0]]
        replay = passes[expected_passes[1]]
        bundle_id_match = baseline["bundle_id"] == replay["bundle_id"]
        fingerprint_match = baseline["stable_fingerprint"] == replay["stable_fingerprint"]
        status_ok = baseline["status"] == "passed" and replay["status"] == "passed"
        if not bundle_id_match:
            failures.append(f"{scenario_id}: bundle_id mismatch across passes")
        if not fingerprint_match:
            failures.append(f"{scenario_id}: stable_fingerprint mismatch across passes")
        if not status_ok:
            failures.append(f"{scenario_id}: pass status not successful in both passes")
        checks.append(
            {
                "scenario_id": scenario_id,
                "bundle_id_pass_a": baseline["bundle_id"],
                "bundle_id_pass_b": replay["bundle_id"],
                "stable_fingerprint_pass_a": baseline["stable_fingerprint"],
                "stable_fingerprint_pass_b": replay["stable_fingerprint"],
                "bundle_id_match": bundle_id_match,
                "stable_fingerprint_match": fingerprint_match,
                "status_ok": status_ok,
            }
        )

    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "artifact_id": "e2e-script-pack-determinism-report-v1",
        "run_id": run_id,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "pass_labels": expected_passes,
        "required_scenarios": expected_scenarios,
        "result_count": len(run_results),
        "status": "pass" if not failures else "fail",
        "failures": failures,
        "scenario_checks": checks,
        "runs": run_results,
        "events_path": repo_relative(output_dir / "e2e_script_pack_events_v1.jsonl"),
    }
    write_json(output_dir / "e2e_script_pack_determinism_report_v1.json", report)
    return report


def selected_scenarios(selected_id: str) -> list[ScenarioSpec]:
    if selected_id == "all":
        return list(SCENARIOS)
    for scenario in SCENARIOS:
        if scenario.scenario_id == selected_id:
            return [scenario]
    raise SystemExit(f"unknown --scenario value `{selected_id}`")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scenario",
        default="all",
        help="Scenario to run: all | happy_path | edge_path | malformed_input",
    )
    parser.add_argument(
        "--passes",
        type=int,
        default=2,
        help="Number of deterministic passes to run (default: 2)",
    )
    parser.add_argument(
        "--output-dir",
        default="artifacts/e2e/latest",
        help="Output directory for events/manifests/report",
    )
    parser.add_argument(
        "--clear-output",
        action="store_true",
        help="Delete output events/report files before running",
    )
    args = parser.parse_args()

    if args.passes < 1:
        raise SystemExit("--passes must be >= 1")

    output_dir = REPO_ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    events_path = output_dir / "e2e_script_pack_events_v1.jsonl"
    if args.clear_output:
        for path in [
            events_path,
            output_dir / "e2e_script_pack_determinism_report_v1.json",
        ]:
            if path.exists():
                path.unlink()

    scenarios = selected_scenarios(args.scenario)
    seed_lookup = scenario_seed_map()

    pass_labels = (
        ["baseline", "replay"]
        if args.passes == 2
        else [f"pass_{index + 1:02d}" for index in range(args.passes)]
    )
    run_id = f"e2e-script-pack-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"

    run_results: list[dict[str, Any]] = []
    for pass_label in pass_labels:
        for scenario in scenarios:
            seed = seed_lookup.get((scenario.journey_id, scenario.mode))
            if seed is None:
                raise SystemExit(
                    f"missing deterministic seed in scenario matrix for {(scenario.journey_id, scenario.mode)}"
                )
            result = run_scenario(
                run_id=run_id,
                pass_label=pass_label,
                scenario=scenario,
                deterministic_seed=seed,
                output_dir=output_dir,
                events_path=events_path,
            )
            run_results.append(result)
            if result["status"] != "passed":
                report = determinism_report(
                    run_id=run_id,
                    output_dir=output_dir,
                    run_results=run_results,
                    expected_passes=pass_labels,
                    expected_scenarios=[scenario.scenario_id for scenario in scenarios],
                )
                print(json.dumps(report, indent=2))
                return 2

    report = determinism_report(
        run_id=run_id,
        output_dir=output_dir,
        run_results=run_results,
        expected_passes=pass_labels,
        expected_scenarios=[scenario.scenario_id for scenario in scenarios],
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "run_id": run_id,
                "events_path": repo_relative(events_path),
                "determinism_report_path": repo_relative(
                    output_dir / "e2e_script_pack_determinism_report_v1.json"
                ),
                "scenario_count": len(scenarios),
                "passes": pass_labels,
            },
            indent=2,
        )
    )
    return 0 if report["status"] == "pass" else 2


if __name__ == "__main__":
    sys.exit(main())
