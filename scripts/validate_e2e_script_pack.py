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


def ensure_gate_step_id(value: Any, prefix: str, ctx: str, errors: list[str]) -> None:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{ctx} must be non-empty string")
        return
    if prefix and not value.startswith(prefix):
        errors.append(f"{ctx} must start with `{prefix}`")


def ensure_path(path_str: str, ctx: str, errors: list[str]) -> None:
    if not isinstance(path_str, str) or not path_str:
        errors.append(f"{ctx} must be non-empty path string")
        return
    abs_path = REPO_ROOT / path_str
    if not abs_path.exists():
        errors.append(f"{ctx} path does not exist: {path_str}")


def ensure_retention_policy(
    policy: Any,
    schema: dict[str, Any],
    ctx: str,
    errors: list[str],
) -> None:
    if not isinstance(policy, dict):
        errors.append(f"{ctx} must be object")
        return
    ensure_keys(policy, schema["required_retention_policy_keys"], ctx, errors)
    policy_id = policy.get("policy_id")
    if not isinstance(policy_id, str) or not policy_id.strip():
        errors.append(f"{ctx}.policy_id must be non-empty string")
    min_days = policy.get("min_retention_days")
    if not isinstance(min_days, int) or min_days < 1:
        errors.append(f"{ctx}.min_retention_days must be integer >= 1")
    ensure_path(policy.get("storage_root", ""), f"{ctx}.storage_root", errors)


def ensure_evidence_refs(
    refs: Any,
    schema: dict[str, Any],
    ctx: str,
    errors: list[str],
) -> None:
    if not isinstance(refs, dict):
        errors.append(f"{ctx} must be object")
        return
    ensure_keys(refs, schema["required_evidence_ref_keys"], ctx, errors)
    for key in [
        "parity_report",
        "parity_report_raptorq",
        "parity_report_decode_proof",
        "contract_table",
        "risk_note",
        "legacy_anchor_map",
    ]:
        ensure_path(refs.get(key, ""), f"{ctx}.{key}", errors)

    profile = refs.get("profile_first_artifacts")
    if isinstance(profile, dict):
        for key in ["baseline", "hotspot", "delta"]:
            ensure_path(profile.get(key, ""), f"{ctx}.profile_first_artifacts.{key}", errors)
    else:
        errors.append(f"{ctx}.profile_first_artifacts must be object")

    optimization = refs.get("optimization_lever_policy")
    if isinstance(optimization, dict):
        ensure_path(
            optimization.get("evidence_path", ""),
            f"{ctx}.optimization_lever_policy.evidence_path",
            errors,
        )
    else:
        errors.append(f"{ctx}.optimization_lever_policy must be object")

    isomorphism_refs = refs.get("isomorphism_proof_artifacts")
    if isinstance(isomorphism_refs, list) and isomorphism_refs:
        for idx, proof_path in enumerate(isomorphism_refs):
            ensure_path(proof_path, f"{ctx}.isomorphism_proof_artifacts[{idx}]", errors)
    else:
        errors.append(f"{ctx}.isomorphism_proof_artifacts must be non-empty array")

    durability_refs = refs.get("durability_evidence")
    if isinstance(durability_refs, list) and durability_refs:
        for idx, durability_path in enumerate(durability_refs):
            ensure_path(durability_path, f"{ctx}.durability_evidence[{idx}]", errors)
    else:
        errors.append(f"{ctx}.durability_evidence must be non-empty array")

    baseline_comparator = refs.get("baseline_comparator")
    if not isinstance(baseline_comparator, str) or not baseline_comparator.strip():
        errors.append(f"{ctx}.baseline_comparator must be non-empty string")


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
        "--bundle-index",
        default="artifacts/e2e/latest/e2e_script_pack_bundle_index_v1.json",
        help="Path to artifact index JSON",
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
    bundle_index_path = REPO_ROOT / args.bundle_index
    events = load_jsonl(events_path)
    report = load_json(report_path)
    bundle_index = load_json(bundle_index_path)

    errors: list[str] = []
    required_scenarios = schema["required_scenarios"]
    required_pass_labels = schema["required_pass_labels"]
    required_packet_ids = schema["required_packet_ids"]
    required_gate_step_prefix = schema.get("required_gate_step_prefix", "step-")

    ensure_keys(report, schema["required_report_keys"], "report", errors)
    if report.get("status") != "pass":
        errors.append("report.status must be `pass`")

    if report.get("required_scenarios") != required_scenarios:
        errors.append("report.required_scenarios mismatch schema")
    if report.get("required_packet_ids") != required_packet_ids:
        errors.append("report.required_packet_ids mismatch schema")
    if report.get("pass_labels") != required_pass_labels:
        errors.append("report.pass_labels mismatch schema")
    ensure_gate_step_id(report.get("gate_step_id"), required_gate_step_prefix, "report.gate_step_id", errors)
    ensure_path(report.get("forensics_index_path", ""), "report.forensics_index_path", errors)
    ensure_retention_policy(report.get("retention_policy"), schema, "report.retention_policy", errors)

    packet_coverage = report.get("packet_coverage")
    if isinstance(packet_coverage, dict):
        ensure_keys(
            packet_coverage,
            ["required_packet_ids", "observed_packet_ids", "missing_packet_ids", "coverage_ok"],
            "report.packet_coverage",
            errors,
        )
        if packet_coverage.get("required_packet_ids") != required_packet_ids:
            errors.append("report.packet_coverage.required_packet_ids mismatch schema")
        observed_packet_ids = packet_coverage.get("observed_packet_ids")
        if not isinstance(observed_packet_ids, list):
            errors.append("report.packet_coverage.observed_packet_ids must be array")
        missing_packet_ids = packet_coverage.get("missing_packet_ids")
        if not isinstance(missing_packet_ids, list):
            errors.append("report.packet_coverage.missing_packet_ids must be array")
        if packet_coverage.get("coverage_ok") is not True:
            errors.append("report.packet_coverage.coverage_ok must be true")
    else:
        errors.append("report.packet_coverage must be object")

    if not isinstance(events, list) or not events:
        errors.append("events JSONL must contain at least one row")
        events = []

    by_scenario_pass: dict[tuple[str, str], dict[str, Any]] = {}
    bundle_by_scenario: dict[str, set[str]] = {}
    fingerprint_by_scenario: dict[str, set[str]] = {}
    seen_packet_ids: set[str] = set()
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
        packet_id = event.get("packet_id")
        if isinstance(packet_id, str):
            seen_packet_ids.add(packet_id)

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

        replay_command = event.get("replay_command")
        if not isinstance(replay_command, str) or not replay_command.strip():
            errors.append(f"event {key} replay_command must be non-empty string")
        ensure_gate_step_id(
            event.get("gate_step_id"),
            required_gate_step_prefix,
            f"event {key}.gate_step_id",
            errors,
        )
        ensure_path(event.get("forensics_index_path", ""), f"event {key}.forensics_index_path", errors)
        ensure_retention_policy(event.get("retention_policy"), schema, f"event {key}.retention_policy", errors)

        event_forensics = event.get("forensics_links")
        if isinstance(event_forensics, dict):
            ensure_keys(
                event_forensics,
                schema["required_forensics_keys"],
                f"event {key}.forensics_links",
                errors,
            )
            for forensics_key in schema["required_forensics_keys"]:
                value = event_forensics.get(forensics_key)
                if not isinstance(value, str) or not value.strip():
                    errors.append(
                        f"event {key}.forensics_links.{forensics_key} must be non-empty string"
                    )
        else:
            errors.append(f"event {key}.forensics_links must be object")

        ensure_evidence_refs(event.get("evidence_refs"), schema, f"event {key}.evidence_refs", errors)

        replay_metadata = event.get("deterministic_replay_metadata")
        if isinstance(replay_metadata, dict):
            ensure_keys(
                replay_metadata,
                schema["required_deterministic_replay_metadata_keys"],
                f"event {key}.deterministic_replay_metadata",
                errors,
            )
            if replay_metadata.get("run_id") != event.get("run_id"):
                errors.append(f"event {key}.deterministic_replay_metadata.run_id mismatch event")
            if replay_metadata.get("deterministic_seed") != event.get("deterministic_seed"):
                errors.append(
                    f"event {key}.deterministic_replay_metadata.deterministic_seed mismatch event"
                )
            if replay_metadata.get("bundle_id") != bundle_id:
                errors.append(f"event {key}.deterministic_replay_metadata.bundle_id mismatch event")
            if replay_metadata.get("stable_fingerprint") != fingerprint:
                errors.append(
                    f"event {key}.deterministic_replay_metadata.stable_fingerprint mismatch event"
                )
            if replay_metadata.get("replay_command") != replay_command:
                errors.append(
                    f"event {key}.deterministic_replay_metadata.replay_command mismatch event"
                )
        else:
            errors.append(f"event {key}.deterministic_replay_metadata must be object")

        failure_envelope_path = event.get("failure_envelope_path", "")
        ensure_path(failure_envelope_path, f"event {key} failure_envelope_path", errors)
        failure_envelope_abs = REPO_ROOT / failure_envelope_path
        if failure_envelope_abs.exists():
            failure_envelope = load_json(failure_envelope_abs)
            ensure_keys(
                failure_envelope,
                schema["required_failure_envelope_keys"],
                f"failure_envelope {key}",
                errors,
            )
            if failure_envelope.get("scenario_id") != scenario_id:
                errors.append(f"failure_envelope {key} scenario_id mismatch event")
            if failure_envelope.get("pass_label") != pass_label:
                errors.append(f"failure_envelope {key} pass_label mismatch event")
            ensure_gate_step_id(
                failure_envelope.get("gate_step_id"),
                required_gate_step_prefix,
                f"failure_envelope {key}.gate_step_id",
                errors,
            )
            if failure_envelope.get("gate_step_id") != event.get("gate_step_id"):
                errors.append(f"failure_envelope {key} gate_step_id mismatch event")
            if failure_envelope.get("bundle_id") != bundle_id:
                errors.append(f"failure_envelope {key} bundle_id mismatch event")
            if failure_envelope.get("stable_fingerprint") != fingerprint:
                errors.append(f"failure_envelope {key} stable_fingerprint mismatch event")
            if failure_envelope.get("replay_command") != replay_command:
                errors.append(f"failure_envelope {key} replay_command mismatch event")
            ensure_path(
                failure_envelope.get("forensics_index_path", ""),
                f"failure_envelope {key}.forensics_index_path",
                errors,
            )
            if failure_envelope.get("forensics_index_path") != event.get("forensics_index_path"):
                errors.append(f"failure_envelope {key} forensics_index_path mismatch event")
            replay_bundle_manifest_path = failure_envelope.get("replay_bundle_manifest_path", "")
            ensure_path(
                replay_bundle_manifest_path,
                f"failure_envelope {key}.replay_bundle_manifest_path",
                errors,
            )
            if replay_bundle_manifest_path != event.get("bundle_manifest_path"):
                errors.append(f"failure_envelope {key} replay_bundle_manifest_path mismatch event")
            ensure_retention_policy(
                failure_envelope.get("retention_policy"),
                schema,
                f"failure_envelope {key}.retention_policy",
                errors,
            )
            if failure_envelope.get("retention_policy") != event.get("retention_policy"):
                errors.append(f"failure_envelope {key} retention_policy mismatch event")
            if failure_envelope.get("status") not in ("passed", "failed"):
                errors.append(f"failure_envelope {key} status must be `passed` or `failed`")
            if failure_envelope.get("status") == "failed" and not isinstance(
                failure_envelope.get("reason_code"), str
            ):
                errors.append(f"failure_envelope {key} failed status requires reason_code string")
            if failure_envelope.get("status") == "passed" and failure_envelope.get("reason_code") not in (
                None,
                "",
            ):
                errors.append(
                    f"failure_envelope {key} passed status should not carry reason_code value"
                )
            ensure_evidence_refs(
                failure_envelope.get("evidence_refs"),
                schema,
                f"failure_envelope {key}.evidence_refs",
                errors,
            )

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
            replay_command = manifest.get("replay_command")
            if not isinstance(replay_command, str) or not replay_command.strip():
                errors.append(f"bundle_manifest {key}.replay_command must be non-empty string")
            execution_metadata = manifest.get("execution_metadata")
            if isinstance(execution_metadata, dict):
                ensure_keys(
                    execution_metadata,
                    schema["required_execution_metadata_keys"],
                    f"bundle_manifest {key}.execution_metadata",
                    errors,
                )
                if execution_metadata.get("gate_step_id") != manifest.get("gate_step_id"):
                    errors.append(
                        f"bundle_manifest {key}.execution_metadata.gate_step_id mismatch manifest gate_step_id"
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
                for replay_field in schema["required_forensics_keys"]:
                    value = forensics.get(replay_field)
                    if not isinstance(value, str) or not value.strip():
                        errors.append(
                            f"bundle_manifest {key}.forensics_links.{replay_field} must be non-empty string"
                        )
            else:
                errors.append(f"bundle_manifest {key}.forensics_links must be object")
            artifact_refs = manifest.get("artifact_refs")
            if not isinstance(artifact_refs, list) or not artifact_refs:
                errors.append(f"bundle_manifest {key}.artifact_refs must be non-empty list")
            else:
                for index, path in enumerate(artifact_refs):
                    ensure_path(path, f"bundle_manifest {key}.artifact_refs[{index}]", errors)
            ensure_evidence_refs(
                manifest.get("evidence_refs"),
                schema,
                f"bundle_manifest {key}.evidence_refs",
                errors,
            )
            manifest_failure_envelope_path = manifest.get("failure_envelope_path", "")
            ensure_path(
                manifest_failure_envelope_path,
                f"bundle_manifest {key}.failure_envelope_path",
                errors,
            )
            if manifest_failure_envelope_path != failure_envelope_path:
                errors.append(
                    f"bundle_manifest {key}.failure_envelope_path mismatch event failure_envelope_path"
                )
            if manifest.get("bundle_id") != bundle_id:
                errors.append(f"bundle_manifest {key} bundle_id mismatch event")
            if manifest.get("stable_fingerprint") != fingerprint:
                errors.append(f"bundle_manifest {key} stable_fingerprint mismatch event")
            ensure_gate_step_id(
                manifest.get("gate_step_id"),
                required_gate_step_prefix,
                f"bundle_manifest {key}.gate_step_id",
                errors,
            )
            if manifest.get("gate_step_id") != event.get("gate_step_id"):
                errors.append(f"bundle_manifest {key}.gate_step_id mismatch event")
            ensure_path(
                manifest.get("forensics_index_path", ""),
                f"bundle_manifest {key}.forensics_index_path",
                errors,
            )
            if manifest.get("forensics_index_path") != event.get("forensics_index_path"):
                errors.append(f"bundle_manifest {key}.forensics_index_path mismatch event")
            ensure_retention_policy(
                manifest.get("retention_policy"),
                schema,
                f"bundle_manifest {key}.retention_policy",
                errors,
            )
            if manifest.get("retention_policy") != event.get("retention_policy"):
                errors.append(f"bundle_manifest {key}.retention_policy mismatch event")

    for scenario_id in required_scenarios:
        for pass_label in required_pass_labels:
            if (scenario_id, pass_label) not in by_scenario_pass:
                errors.append(f"missing event for scenario={scenario_id} pass={pass_label}")
        if bundle_by_scenario.get(scenario_id, set()) and len(bundle_by_scenario[scenario_id]) != 1:
            errors.append(f"bundle_id must be stable across passes for {scenario_id}")
        if fingerprint_by_scenario.get(scenario_id, set()) and len(fingerprint_by_scenario[scenario_id]) != 1:
            errors.append(f"stable_fingerprint must be stable across passes for {scenario_id}")
    for packet_id in required_packet_ids:
        if packet_id not in seen_packet_ids:
            errors.append(f"missing packet coverage for `{packet_id}`")

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

    profile_first_artifacts = report.get("profile_first_artifacts")
    if isinstance(profile_first_artifacts, dict):
        for profile_key in ["baseline", "hotspot", "delta"]:
            ensure_path(
                profile_first_artifacts.get(profile_key, ""),
                f"report.profile_first_artifacts.{profile_key}",
                errors,
            )
    else:
        errors.append("report.profile_first_artifacts must be object")

    optimization_policy = report.get("optimization_lever_policy")
    if isinstance(optimization_policy, dict):
        rule = optimization_policy.get("rule")
        if rule != "exactly_one_optimization_lever_per_change":
            errors.append("report.optimization_lever_policy.rule mismatch expected policy")
        ensure_path(
            optimization_policy.get("evidence_path", ""),
            "report.optimization_lever_policy.evidence_path",
            errors,
        )
    else:
        errors.append("report.optimization_lever_policy must be object")

    alien_uplift = report.get("alien_uplift_contract_card")
    if isinstance(alien_uplift, dict):
        ev_score = alien_uplift.get("ev_score")
        if not isinstance(ev_score, (int, float)) or float(ev_score) < 2.0:
            errors.append("report.alien_uplift_contract_card.ev_score must be >= 2.0")
        baseline_comparator = alien_uplift.get("baseline_comparator")
        if not isinstance(baseline_comparator, str) or not baseline_comparator.strip():
            errors.append(
                "report.alien_uplift_contract_card.baseline_comparator must be non-empty string"
            )
    else:
        errors.append("report.alien_uplift_contract_card must be object")

    decision_contract = report.get("decision_theoretic_runtime_contract")
    if isinstance(decision_contract, dict):
        ensure_keys(
            decision_contract,
            ["states", "actions", "loss_model", "loss_budget", "safe_mode_fallback"],
            "report.decision_theoretic_runtime_contract",
            errors,
        )
        safe_mode = decision_contract.get("safe_mode_fallback")
        if isinstance(safe_mode, dict):
            trigger_thresholds = safe_mode.get("trigger_thresholds")
            if not isinstance(trigger_thresholds, dict) or not trigger_thresholds:
                errors.append(
                    "report.decision_theoretic_runtime_contract.safe_mode_fallback.trigger_thresholds must be non-empty object"
                )
        else:
            errors.append("report.decision_theoretic_runtime_contract.safe_mode_fallback must be object")
    else:
        errors.append("report.decision_theoretic_runtime_contract must be object")

    isomorphism_artifacts = report.get("isomorphism_proof_artifacts")
    if isinstance(isomorphism_artifacts, list) and isomorphism_artifacts:
        for idx, proof_path in enumerate(isomorphism_artifacts):
            ensure_path(proof_path, f"report.isomorphism_proof_artifacts[{idx}]", errors)
    else:
        errors.append("report.isomorphism_proof_artifacts must be non-empty array")

    structured_logging_evidence = report.get("structured_logging_evidence")
    if isinstance(structured_logging_evidence, list) and structured_logging_evidence:
        for idx, evidence_path in enumerate(structured_logging_evidence):
            ensure_path(evidence_path, f"report.structured_logging_evidence[{idx}]", errors)
    else:
        errors.append("report.structured_logging_evidence must be non-empty array")

    ensure_keys(bundle_index, schema["required_bundle_index_keys"], "bundle_index", errors)
    ensure_gate_step_id(
        bundle_index.get("gate_step_id"),
        required_gate_step_prefix,
        "bundle_index.gate_step_id",
        errors,
    )
    ensure_path(
        bundle_index.get("forensics_index_path", ""),
        "bundle_index.forensics_index_path",
        errors,
    )
    ensure_retention_policy(bundle_index.get("retention_policy"), schema, "bundle_index.retention_policy", errors)
    if bundle_index.get("forensics_index_path") != args.bundle_index:
        errors.append("bundle_index.forensics_index_path must match bundle-index artifact path")
    if bundle_index.get("scenario_count") != len(required_scenarios):
        errors.append("bundle_index.scenario_count mismatch required scenario count")
    if bundle_index.get("failure_count") != len(bundle_index.get("failure_index", [])):
        errors.append("bundle_index.failure_count must equal len(failure_index)")

    bundle_rows = bundle_index.get("rows")
    if not isinstance(bundle_rows, list) or len(bundle_rows) != len(required_scenarios):
        errors.append("bundle_index.rows must include one row per required scenario")
        bundle_rows = []

    seen_bundle_scenarios: set[str] = set()
    for row in bundle_rows:
        if not isinstance(row, dict):
            errors.append("bundle_index.rows entries must be objects")
            continue
        ensure_keys(row, schema["required_bundle_index_row_keys"], "bundle_index.row", errors)
        scenario_id = row.get("scenario_id")
        if scenario_id not in required_scenarios:
            errors.append(f"bundle_index row has unexpected scenario_id `{scenario_id}`")
            continue
        if scenario_id in seen_bundle_scenarios:
            errors.append(f"bundle_index duplicate scenario row `{scenario_id}`")
        seen_bundle_scenarios.add(scenario_id)
        ensure_gate_step_id(
            row.get("gate_step_id"),
            required_gate_step_prefix,
            f"bundle_index.rows[{scenario_id}].gate_step_id",
            errors,
        )
        ensure_path(
            row.get("forensics_index_path", ""),
            f"bundle_index.rows[{scenario_id}].forensics_index_path",
            errors,
        )
        ensure_retention_policy(
            row.get("retention_policy"),
            schema,
            f"bundle_index.rows[{scenario_id}].retention_policy",
            errors,
        )
        if row.get("forensics_index_path") != bundle_index.get("forensics_index_path"):
            errors.append(f"bundle_index row `{scenario_id}` forensics_index_path mismatch bundle_index")

        manifests = row.get("manifests")
        failure_envelopes = row.get("failure_envelopes")
        if isinstance(manifests, dict):
            for pass_label in required_pass_labels:
                manifest_path = manifests.get(pass_label, "")
                ensure_path(
                    manifest_path,
                    f"bundle_index.rows[{scenario_id}].manifests.{pass_label}",
                    errors,
                )
                event_row = by_scenario_pass.get((scenario_id, pass_label))
                if event_row and manifest_path != event_row.get("bundle_manifest_path"):
                    errors.append(
                        f"bundle_index row `{scenario_id}` manifest for `{pass_label}` mismatches event bundle_manifest_path"
                    )
        else:
            errors.append(f"bundle_index.rows[{scenario_id}].manifests must be object")
        if isinstance(failure_envelopes, dict):
            for pass_label in required_pass_labels:
                envelope_path = failure_envelopes.get(pass_label, "")
                ensure_path(
                    envelope_path,
                    f"bundle_index.rows[{scenario_id}].failure_envelopes.{pass_label}",
                    errors,
                )
                event_row = by_scenario_pass.get((scenario_id, pass_label))
                if event_row and envelope_path != event_row.get("failure_envelope_path"):
                    errors.append(
                        f"bundle_index row `{scenario_id}` envelope for `{pass_label}` mismatches event failure_envelope_path"
                    )
                if event_row and row.get("gate_step_id") != event_row.get("gate_step_id"):
                    errors.append(
                        f"bundle_index row `{scenario_id}` gate_step_id mismatch event for pass `{pass_label}`"
                    )
                if event_row and row.get("retention_policy") != event_row.get("retention_policy"):
                    errors.append(
                        f"bundle_index row `{scenario_id}` retention_policy mismatch event for pass `{pass_label}`"
                    )
        else:
            errors.append(f"bundle_index.rows[{scenario_id}].failure_envelopes must be object")

        ensure_evidence_refs(
            row.get("parity_perf_raptorq_evidence"),
            schema,
            f"bundle_index.rows[{scenario_id}].parity_perf_raptorq_evidence",
            errors,
        )

    for scenario_id in required_scenarios:
        if scenario_id not in seen_bundle_scenarios:
            errors.append(f"bundle_index missing row for scenario `{scenario_id}`")

    failure_index = bundle_index.get("failure_index")
    if not isinstance(failure_index, list):
        errors.append("bundle_index.failure_index must be array")
        failure_index = []
    for idx, failure_row in enumerate(failure_index):
        if not isinstance(failure_row, dict):
            errors.append(f"bundle_index.failure_index[{idx}] must be object")
            continue
        ensure_keys(
            failure_row,
            schema["required_bundle_index_failure_keys"],
            f"bundle_index.failure_index[{idx}]",
            errors,
        )
        ensure_path(
            failure_row.get("failure_envelope_path", ""),
            f"bundle_index.failure_index[{idx}].failure_envelope_path",
            errors,
        )
        replay_command = failure_row.get("replay_command")
        if not isinstance(replay_command, str) or not replay_command.strip():
            errors.append(f"bundle_index.failure_index[{idx}].replay_command must be non-empty string")
        scenario_id = failure_row.get("scenario_id")
        pass_label = failure_row.get("pass_label")
        ensure_gate_step_id(
            failure_row.get("gate_step_id"),
            required_gate_step_prefix,
            f"bundle_index.failure_index[{idx}].gate_step_id",
            errors,
        )
        ensure_path(
            failure_row.get("forensics_index_path", ""),
            f"bundle_index.failure_index[{idx}].forensics_index_path",
            errors,
        )
        ensure_path(
            failure_row.get("replay_bundle_manifest_path", ""),
            f"bundle_index.failure_index[{idx}].replay_bundle_manifest_path",
            errors,
        )
        ensure_retention_policy(
            failure_row.get("retention_policy"),
            schema,
            f"bundle_index.failure_index[{idx}].retention_policy",
            errors,
        )
        if failure_row.get("forensics_index_path") != bundle_index.get("forensics_index_path"):
            errors.append(f"bundle_index.failure_index[{idx}] forensics_index_path mismatch bundle_index")
        event_row = None
        if isinstance(scenario_id, str) and isinstance(pass_label, str):
            event_row = by_scenario_pass.get((scenario_id, pass_label))
        if event_row:
            if failure_row.get("replay_bundle_manifest_path") != event_row.get("bundle_manifest_path"):
                errors.append(
                    f"bundle_index.failure_index[{idx}].replay_bundle_manifest_path mismatch event bundle_manifest_path"
                )
            if failure_row.get("gate_step_id") != event_row.get("gate_step_id"):
                errors.append(f"bundle_index.failure_index[{idx}].gate_step_id mismatch event")
            if failure_row.get("retention_policy") != event_row.get("retention_policy"):
                errors.append(f"bundle_index.failure_index[{idx}].retention_policy mismatch event")
        forensics = failure_row.get("forensics_links")
        if isinstance(forensics, dict):
            ensure_keys(
                forensics,
                schema["required_forensics_keys"],
                f"bundle_index.failure_index[{idx}].forensics_links",
                errors,
            )
        else:
            errors.append(f"bundle_index.failure_index[{idx}].forensics_links must be object")
        ensure_evidence_refs(
            failure_row.get("parity_perf_raptorq_evidence"),
            schema,
            f"bundle_index.failure_index[{idx}].parity_perf_raptorq_evidence",
            errors,
        )

    bundle_profile = bundle_index.get("profile_first_artifacts")
    if isinstance(bundle_profile, dict):
        for profile_key in ["baseline", "hotspot", "delta"]:
            ensure_path(
                bundle_profile.get(profile_key, ""),
                f"bundle_index.profile_first_artifacts.{profile_key}",
                errors,
            )
    else:
        errors.append("bundle_index.profile_first_artifacts must be object")

    bundle_optimization = bundle_index.get("optimization_lever_policy")
    if isinstance(bundle_optimization, dict):
        ensure_path(
            bundle_optimization.get("evidence_path", ""),
            "bundle_index.optimization_lever_policy.evidence_path",
            errors,
        )
    else:
        errors.append("bundle_index.optimization_lever_policy must be object")

    bundle_alien = bundle_index.get("alien_uplift_contract_card")
    if isinstance(bundle_alien, dict):
        bundle_ev = bundle_alien.get("ev_score")
        if not isinstance(bundle_ev, (int, float)) or float(bundle_ev) < 2.0:
            errors.append("bundle_index.alien_uplift_contract_card.ev_score must be >= 2.0")
    else:
        errors.append("bundle_index.alien_uplift_contract_card must be object")

    bundle_decision = bundle_index.get("decision_theoretic_runtime_contract")
    if isinstance(bundle_decision, dict):
        ensure_keys(
            bundle_decision,
            ["states", "actions", "loss_model", "loss_budget", "safe_mode_fallback"],
            "bundle_index.decision_theoretic_runtime_contract",
            errors,
        )
    else:
        errors.append("bundle_index.decision_theoretic_runtime_contract must be object")

    bundle_isomorphism = bundle_index.get("isomorphism_proof_artifacts")
    if isinstance(bundle_isomorphism, list) and bundle_isomorphism:
        for idx, proof_path in enumerate(bundle_isomorphism):
            ensure_path(proof_path, f"bundle_index.isomorphism_proof_artifacts[{idx}]", errors)
    else:
        errors.append("bundle_index.isomorphism_proof_artifacts must be non-empty array")

    bundle_logs = bundle_index.get("structured_logging_evidence")
    if isinstance(bundle_logs, list) and bundle_logs:
        for idx, evidence_path in enumerate(bundle_logs):
            ensure_path(evidence_path, f"bundle_index.structured_logging_evidence[{idx}]", errors)
    else:
        errors.append("bundle_index.structured_logging_evidence must be non-empty array")

    report_data = {
        "schema_version": "1.0.0",
        "report_id": "e2e-script-pack-validation-v1",
        "events_path": args.events,
        "determinism_report_path": args.report,
        "bundle_index_path": args.bundle_index,
        "ready": len(errors) == 0,
        "error_count": len(errors),
        "errors": errors,
        "summary": {
            "event_count": len(events),
            "required_scenario_count": len(required_scenarios),
            "required_pass_count": len(required_pass_labels),
            "bundle_row_count": len(bundle_index.get("rows", []))
            if isinstance(bundle_index.get("rows"), list)
            else 0,
            "failure_index_count": len(bundle_index.get("failure_index", []))
            if isinstance(bundle_index.get("failure_index"), list)
            else 0,
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
