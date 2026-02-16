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
REPLAY_REPORT_SCHEMA_VERSION = "1.0.0"
REQUIRED_FORENSICS_KEYS: tuple[str, ...] = (
    "structured_log_hash_id",
    "forensic_bundle_id",
    "forensics_bundle_hash_id",
    "forensics_bundle_replay_ref",
)


@dataclass(frozen=True)
class ScenarioSpec:
    scenario_id: str
    scenario_kind: str
    journey_id: str
    mode: str
    fixture_id: str
    packet_id: str
    soak_profile: str = ""
    soak_threat_class: str = ""


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
    ScenarioSpec(
        scenario_id="adversarial_soak",
        scenario_kind="adversarial_soak",
        journey_id="J-READWRITE",
        mode="hardened",
        fixture_id="generated/readwrite_hardened_malformed.json",
        packet_id="FNX-P2C-006",
        soak_profile="long_tail_stability",
        soak_threat_class="algorithmic_denial",
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


def non_empty_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def forensics_links_from_log(log_row: dict[str, Any] | None) -> dict[str, Any]:
    if log_row is None:
        return {
            "structured_log_hash_id": None,
            "forensic_bundle_id": None,
            "forensics_bundle_hash_id": None,
            "forensics_bundle_replay_ref": None,
        }
    forensics_bundle = log_row.get("forensics_bundle_index", {})
    return {
        "structured_log_hash_id": log_row.get("hash_id"),
        "forensic_bundle_id": log_row.get("forensic_bundle_id"),
        "forensics_bundle_hash_id": forensics_bundle.get("bundle_hash_id"),
        "forensics_bundle_replay_ref": forensics_bundle.get("replay_ref"),
    }


def missing_forensics_fields(forensics_links: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    for key in REQUIRED_FORENSICS_KEYS:
        if not non_empty_str(forensics_links.get(key)):
            missing.append(key)
    return missing


def build_soak_health_metrics(
    *,
    run_id: str,
    pass_label: str,
    scenario: ScenarioSpec,
    deterministic_seed: int,
    cycle_results: list[dict[str, Any]],
    cycle_target: int,
    checkpoint_interval_ms: int,
    start_ms: int,
    end_ms: int,
    status: str,
    reason_code: str | None,
) -> dict[str, Any]:
    checkpoints: list[dict[str, Any]] = []
    health_samples: list[dict[str, Any]] = []
    for cycle_index in range(cycle_target):
        checkpoint_hash_id = fnv1a64(
            f"{scenario.scenario_id}|{deterministic_seed}|{checkpoint_interval_ms}|{cycle_index + 1}"
        )
        hash_value = int(checkpoint_hash_id, 16)
        cycle = cycle_results[cycle_index] if cycle_index < len(cycle_results) else None
        checkpoints.append(
            {
                "checkpoint_id": f"soak-checkpoint-{cycle_index + 1:02d}",
                "cycle_index": cycle_index + 1,
                "offset_ms": cycle_index * checkpoint_interval_ms,
                "checkpoint_hash_id": checkpoint_hash_id,
            }
        )
        health_samples.append(
            {
                "checkpoint_id": f"soak-checkpoint-{cycle_index + 1:02d}",
                "cycle_index": cycle_index + 1,
                "synthetic_cpu_load_pct": round(20.0 + float(hash_value % 700) / 10.0, 1),
                "synthetic_memory_mb": 256 + (hash_value % 4096),
                "synthetic_queue_depth": hash_value % 32,
                "cycle_status": cycle["status"] if cycle else "not_executed",
                "cycle_duration_ms": cycle["duration_ms"] if cycle else None,
                "cycle_start_unix_ms": cycle["start_unix_ms"] if cycle else None,
                "cycle_end_unix_ms": cycle["end_unix_ms"] if cycle else None,
            }
        )
    return {
        "schema_version": "1.0.0",
        "artifact_id": "adversarial-soak-health-checkpoints-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "pass_label": pass_label,
        "scenario_id": scenario.scenario_id,
        "soak_profile": scenario.soak_profile,
        "soak_threat_class": scenario.soak_threat_class,
        "deterministic_seed": deterministic_seed,
        "status": status,
        "reason_code": reason_code,
        "target_cycle_count": cycle_target,
        "realized_cycle_count": len(cycle_results),
        "checkpoint_interval_ms": checkpoint_interval_ms,
        "start_unix_ms": start_ms,
        "end_unix_ms": end_ms,
        "duration_ms": end_ms - start_ms,
        "deterministic_checkpoints": checkpoints,
        "health_samples": health_samples,
    }


def build_soak_triage_summary(
    *,
    run_id: str,
    pass_label: str,
    scenario: ScenarioSpec,
    status: str,
    reason_code: str | None,
    manifest_path: Path,
    replay_command: str,
    forensics_links: dict[str, Any],
    missing_forensics: list[str],
    checkpoint_path: Path,
    cycle_target: int,
    cycle_results: list[dict[str, Any]],
) -> dict[str, Any]:
    replay_manifest_rel = repo_relative(manifest_path)
    replay_invocation = (
        "python3 ./scripts/run_e2e_script_pack.py "
        f"--replay-manifest {replay_manifest_rel} --output-dir artifacts/e2e/latest"
    )
    recommended_actions = [
        replay_invocation,
        f"cat {repo_relative(checkpoint_path)}",
    ]
    if status != "passed":
        recommended_actions.append(
            "Inspect command.log + selected_structured_log.json in the same bundle directory."
        )
    return {
        "schema_version": "1.0.0",
        "artifact_id": "adversarial-soak-triage-summary-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "pass_label": pass_label,
        "scenario_id": scenario.scenario_id,
        "soak_profile": scenario.soak_profile,
        "soak_threat_class": scenario.soak_threat_class,
        "status": status,
        "reason_code": reason_code,
        "decode_ready_replay_bundle": len(missing_forensics) == 0,
        "replay_manifest_path": replay_manifest_rel,
        "replay_command": replay_command,
        "forensics_links": forensics_links,
        "missing_forensics_fields": missing_forensics,
        "target_cycle_count": cycle_target,
        "realized_cycle_count": len(cycle_results),
        "checkpoint_artifact_path": repo_relative(checkpoint_path),
        "recommended_actions": recommended_actions,
    }


def replay_manifest_diagnostics(manifest: dict[str, Any]) -> list[str]:
    diagnostics: list[str] = []
    for key in [
        "scenario_id",
        "mode",
        "fixture_id",
        "bundle_id",
        "stable_fingerprint",
        "replay_command",
        "forensics_links",
    ]:
        if key not in manifest:
            diagnostics.append(f"manifest missing required key `{key}`")
    replay_command = manifest.get("replay_command")
    if not non_empty_str(replay_command):
        diagnostics.append("manifest.replay_command must be a non-empty string")
    forensics = manifest.get("forensics_links")
    if not isinstance(forensics, dict):
        diagnostics.append("manifest.forensics_links must be an object")
    else:
        for key in missing_forensics_fields(forensics):
            diagnostics.append(f"manifest.forensics_links.{key} must be a non-empty string")
    return diagnostics


def run_scenario(
    *,
    run_id: str,
    pass_label: str,
    scenario: ScenarioSpec,
    deterministic_seed: int,
    soak_cycles: int,
    soak_checkpoint_interval_ms: int,
    output_dir: Path,
    events_path: Path,
) -> dict[str, Any]:
    command = conformance_command(scenario.fixture_id, scenario.mode)
    is_soak = bool(scenario.soak_profile)
    cycle_target = soak_cycles if is_soak else 1
    checkpoint_interval_ms = soak_checkpoint_interval_ms if is_soak else 0

    start_ms = unix_ms()
    cycle_results: list[dict[str, Any]] = []
    command_log_sections: list[str] = []
    for cycle_index in range(cycle_target):
        cycle_start_ms = unix_ms()
        completed = subprocess.run(
            ["bash", "-lc", command],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        cycle_end_ms = unix_ms()
        cycle_status = "passed" if completed.returncode == 0 else "failed"
        cycle_results.append(
            {
                "cycle_index": cycle_index + 1,
                "status": cycle_status,
                "return_code": completed.returncode,
                "start_unix_ms": cycle_start_ms,
                "end_unix_ms": cycle_end_ms,
                "duration_ms": cycle_end_ms - cycle_start_ms,
            }
        )
        command_log_sections.append(
            "\n".join(
                [
                    f"### cycle {cycle_index + 1:02d}/{cycle_target:02d}",
                    f"start_unix_ms={cycle_start_ms}",
                    f"end_unix_ms={cycle_end_ms}",
                    f"duration_ms={cycle_end_ms - cycle_start_ms}",
                    f"return_code={completed.returncode}",
                    "",
                    completed.stdout,
                    completed.stderr,
                    "",
                ]
            )
        )
        if completed.returncode != 0:
            break

    end_ms = unix_ms()
    duration_ms = end_ms - start_ms
    status = (
        "passed"
        if cycle_results
        and len(cycle_results) == cycle_target
        and all(row["status"] == "passed" for row in cycle_results)
        else "failed"
    )
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
    command_log_path.write_text("".join(command_log_sections), encoding="utf-8")

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
    forensics_links = forensics_links_from_log(log_row)
    if status == "passed":
        if log_row is None:
            status = "failed"
            reason_code = "missing_structured_log"
        else:
            missing_fields = missing_forensics_fields(forensics_links)
            if missing_fields:
                status = "failed"
                reason_code = f"missing_forensics_fields:{','.join(missing_fields)}"

    soak_checkpoint_path: Path | None = None
    soak_triage_path: Path | None = None
    if is_soak:
        soak_checkpoint_path = scenario_dir / "soak_health_checkpoints_v1.json"
        soak_metrics = build_soak_health_metrics(
            run_id=run_id,
            pass_label=pass_label,
            scenario=scenario,
            deterministic_seed=deterministic_seed,
            cycle_results=cycle_results,
            cycle_target=cycle_target,
            checkpoint_interval_ms=checkpoint_interval_ms,
            start_ms=start_ms,
            end_ms=end_ms,
            status=status,
            reason_code=reason_code,
        )
        write_json(soak_checkpoint_path, soak_metrics)
        soak_triage_path = scenario_dir / "soak_triage_summary_v1.json"

    artifact_refs = [
        repo_relative(copied_smoke),
        repo_relative(copied_fixture_report),
        repo_relative(copied_structured_logs),
        repo_relative(command_log_path),
        repo_relative(selected_log_path),
    ]
    if soak_checkpoint_path is not None and soak_triage_path is not None:
        artifact_refs.append(repo_relative(soak_checkpoint_path))
        artifact_refs.append(repo_relative(soak_triage_path))

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
        "forensics_links": forensics_links,
        "artifact_refs": artifact_refs,
    }
    if is_soak and soak_checkpoint_path is not None and soak_triage_path is not None:
        manifest["soak_telemetry"] = {
            "soak_profile": scenario.soak_profile,
            "soak_threat_class": scenario.soak_threat_class,
            "target_cycle_count": cycle_target,
            "realized_cycle_count": len(cycle_results),
            "checkpoint_interval_ms": checkpoint_interval_ms,
            "checkpoint_artifact_path": repo_relative(soak_checkpoint_path),
            "triage_summary_path": repo_relative(soak_triage_path),
        }
    manifest_path = scenario_dir / "bundle_manifest_v1.json"
    write_json(manifest_path, manifest)

    if is_soak and soak_checkpoint_path is not None and soak_triage_path is not None:
        triage_summary = build_soak_triage_summary(
            run_id=run_id,
            pass_label=pass_label,
            scenario=scenario,
            status=status,
            reason_code=reason_code,
            manifest_path=manifest_path,
            replay_command=manifest["replay_command"],
            forensics_links=forensics_links,
            missing_forensics=missing_forensics_fields(forensics_links),
            checkpoint_path=soak_checkpoint_path,
            cycle_target=cycle_target,
            cycle_results=cycle_results,
        )
        write_json(soak_triage_path, triage_summary)

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
    if is_soak and soak_checkpoint_path is not None and soak_triage_path is not None:
        event.update(
            {
                "soak_profile": scenario.soak_profile,
                "soak_threat_class": scenario.soak_threat_class,
                "soak_cycle_count": cycle_target,
                "soak_realized_cycle_count": len(cycle_results),
                "soak_checkpoint_interval_ms": checkpoint_interval_ms,
                "soak_checkpoint_artifact_path": repo_relative(soak_checkpoint_path),
                "soak_triage_summary_path": repo_relative(soak_triage_path),
            }
        )
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


def replay_from_manifest(*, manifest_path: Path, output_dir: Path) -> int:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = load_json(manifest_path)
    diagnostics = replay_manifest_diagnostics(manifest)

    fixture_id = manifest.get("fixture_id")
    mode = manifest.get("mode")
    scenario_id = manifest.get("scenario_id")
    replay_command_expected = manifest.get("replay_command")

    if not diagnostics and isinstance(fixture_id, str) and isinstance(mode, str):
        replay_command_executed = conformance_command(fixture_id, mode)
    else:
        replay_command_executed = ""

    replay_dir = output_dir / "replay" / str(scenario_id or "unknown")
    replay_dir.mkdir(parents=True, exist_ok=True)
    command_log_path = replay_dir / "replay_command.log"

    start_ms = unix_ms()
    completed: subprocess.CompletedProcess[str] | None = None
    if not diagnostics:
        completed = subprocess.run(
            ["bash", "-lc", replay_command_executed],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        command_log_path.write_text(
            completed.stdout + ("\n" if completed.stdout else "") + completed.stderr,
            encoding="utf-8",
        )
    end_ms = unix_ms()

    observed_forensics = forensics_links_from_log(None)
    forensics_match = False
    status = "failed"
    reason_code = "manifest_invalid"
    if diagnostics:
        run_diagnostics = diagnostics
    else:
        run_diagnostics = []
        logs = parse_structured_logs()
        assert isinstance(fixture_id, str)
        assert isinstance(mode, str)
        log_row = find_log_for_fixture(logs, fixture_id, mode)
        observed_forensics = forensics_links_from_log(log_row)
        missing_observed = missing_forensics_fields(observed_forensics)
        expected_forensics = manifest["forensics_links"]
        assert isinstance(expected_forensics, dict)
        forensics_match = all(
            expected_forensics.get(key) == observed_forensics.get(key)
            for key in REQUIRED_FORENSICS_KEYS
        )
        if completed is not None and completed.returncode != 0:
            run_diagnostics.append("replay command returned non-zero exit status")
            reason_code = "command_failed"
        if log_row is None:
            run_diagnostics.append("structured log row not found for replay fixture/mode")
            reason_code = "missing_structured_log"
        if missing_observed:
            run_diagnostics.append(
                "observed forensics links missing required fields: "
                + ",".join(missing_observed)
            )
            reason_code = "missing_forensics_fields"
        if not forensics_match:
            run_diagnostics.append(
                "observed forensics links do not match manifest forensics links"
            )
            reason_code = "forensics_mismatch"
        if not run_diagnostics:
            status = "passed"
            reason_code = None

    report = {
        "schema_version": REPLAY_REPORT_SCHEMA_VERSION,
        "artifact_id": "e2e-script-pack-replay-report-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "reason_code": reason_code,
        "scenario_id": scenario_id,
        "bundle_id": manifest.get("bundle_id"),
        "fixture_id": fixture_id,
        "mode": mode,
        "replayed_manifest_path": repo_relative(manifest_path),
        "replay_command_expected": replay_command_expected,
        "replay_command_executed": replay_command_executed,
        "command_log_path": repo_relative(command_log_path),
        "start_unix_ms": start_ms,
        "end_unix_ms": end_ms,
        "duration_ms": end_ms - start_ms,
        "forensics_links_expected": manifest.get("forensics_links"),
        "forensics_links_observed": observed_forensics,
        "forensics_match": forensics_match,
        "diagnostics": run_diagnostics,
    }
    output_path = output_dir / "e2e_script_pack_replay_report_v1.json"
    write_json(output_path, report)
    print(json.dumps(report, indent=2))
    return 0 if status == "passed" else 2


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
        help="Scenario to run: all | happy_path | edge_path | malformed_input | adversarial_soak",
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
    parser.add_argument(
        "--replay-manifest",
        default="",
        help="Replay from a bundle manifest path and emit replay report",
    )
    parser.add_argument(
        "--soak-cycles",
        type=int,
        default=4,
        help="Cycle count for adversarial_soak scenario per pass (default: 4)",
    )
    parser.add_argument(
        "--soak-checkpoint-interval-ms",
        type=int,
        default=15000,
        help="Deterministic checkpoint interval in ms for adversarial_soak (default: 15000)",
    )
    args = parser.parse_args()

    if args.passes < 1:
        raise SystemExit("--passes must be >= 1")
    if args.soak_cycles < 1:
        raise SystemExit("--soak-cycles must be >= 1")
    if args.soak_checkpoint_interval_ms < 1:
        raise SystemExit("--soak-checkpoint-interval-ms must be >= 1")

    output_dir = REPO_ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    if args.replay_manifest:
        manifest_path = Path(args.replay_manifest)
        if not manifest_path.is_absolute():
            manifest_path = REPO_ROOT / manifest_path
        return replay_from_manifest(manifest_path=manifest_path, output_dir=output_dir)

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
                soak_cycles=args.soak_cycles,
                soak_checkpoint_interval_ms=args.soak_checkpoint_interval_ms,
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
