#!/usr/bin/env python3
"""Validate reliability budget gate artifacts."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE_BEAD_ID = "bd-315.23"


def load_json(path: Path, ctx: str, errors: list[str]) -> dict[str, Any]:
    if not path.exists():
        errors.append(f"{ctx} path does not exist: {path}")
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as err:
        errors.append(f"{ctx} is not valid JSON ({path}): {err}")
        return {}


def ensure_keys(payload: dict[str, Any], keys: list[str], ctx: str, errors: list[str]) -> None:
    for key in keys:
        if key not in payload:
            errors.append(f"{ctx} missing key `{key}`")


def ensure_non_empty_string(value: Any, ctx: str, errors: list[str]) -> str:
    if isinstance(value, str) and value.strip():
        return value
    errors.append(f"{ctx} must be a non-empty string")
    return ""


def ensure_string_list(value: Any, ctx: str, errors: list[str]) -> list[str]:
    if not isinstance(value, list):
        errors.append(f"{ctx} must be a list")
        return []
    out: list[str] = []
    for idx, row in enumerate(value):
        text = ensure_non_empty_string(row, f"{ctx}[{idx}]", errors)
        if text:
            out.append(text)
    return out


def ensure_dict_list(value: Any, ctx: str, errors: list[str]) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        errors.append(f"{ctx} must be a list")
        return []
    out: list[dict[str, Any]] = []
    for idx, row in enumerate(value):
        if isinstance(row, dict):
            out.append(row)
        else:
            errors.append(f"{ctx}[{idx}] must be an object")
    return out


def ensure_dict(value: Any, ctx: str, errors: list[str]) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    errors.append(f"{ctx} must be an object")
    return {}


def ensure_rel_path(path_text: str, ctx: str, errors: list[str]) -> None:
    if not path_text:
        return
    abs_path = REPO_ROOT / path_text
    if not abs_path.exists():
        errors.append(f"{ctx} path does not exist: {path_text}")


def coerce_float(value: Any, ctx: str, errors: list[str]) -> float | None:
    if isinstance(value, bool):
        errors.append(f"{ctx} must be numeric")
        return None
    if isinstance(value, (int, float)):
        return float(value)
    errors.append(f"{ctx} must be numeric")
    return None


def coerce_int(value: Any, ctx: str, errors: list[str]) -> int | None:
    if isinstance(value, bool):
        errors.append(f"{ctx} must be integer")
        return None
    if isinstance(value, int):
        return value
    errors.append(f"{ctx} must be integer")
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--schema",
        default="artifacts/conformance/schema/v1/reliability_budget_gate_schema_v1.json",
        help="Path to reliability schema JSON",
    )
    parser.add_argument(
        "--spec",
        default="artifacts/conformance/v1/reliability_budget_gate_v1.json",
        help="Path to reliability budget spec JSON",
    )
    parser.add_argument(
        "--report",
        default="artifacts/conformance/latest/reliability_budget_report_v1.json",
        help="Path to generated reliability gate report",
    )
    parser.add_argument(
        "--quarantine",
        default="artifacts/conformance/latest/flake_quarantine_v1.json",
        help="Path to generated flake quarantine artifact",
    )
    parser.add_argument(
        "--output",
        default="artifacts/conformance/latest/reliability_budget_gate_validation_v1.json",
        help="Validation result output path",
    )
    args = parser.parse_args()

    errors: list[str] = []

    schema = load_json(REPO_ROOT / args.schema, "schema", errors)
    spec = load_json(REPO_ROOT / args.spec, "spec", errors)
    report = load_json(REPO_ROOT / args.report, "report", errors)
    quarantine = load_json(REPO_ROOT / args.quarantine, "quarantine", errors)

    required_schema_keys = [
        "required_top_level_keys",
        "required_budget_keys",
        "required_coverage_floor_keys",
        "required_runtime_guardrail_keys",
        "required_flake_policy_keys",
        "required_quarantine_enter_keys",
        "required_quarantine_exit_keys",
        "required_failure_envelope_fields",
        "required_budget_ids",
        "allowed_status_values",
    ]
    ensure_keys(schema, required_schema_keys, "schema", errors)

    required_top_level_keys = ensure_string_list(
        schema.get("required_top_level_keys"),
        "schema.required_top_level_keys",
        errors,
    )
    required_budget_keys = ensure_string_list(
        schema.get("required_budget_keys"),
        "schema.required_budget_keys",
        errors,
    )
    required_coverage_floor_keys = ensure_string_list(
        schema.get("required_coverage_floor_keys"),
        "schema.required_coverage_floor_keys",
        errors,
    )
    required_runtime_guardrail_keys = ensure_string_list(
        schema.get("required_runtime_guardrail_keys"),
        "schema.required_runtime_guardrail_keys",
        errors,
    )
    required_flake_policy_keys = ensure_string_list(
        schema.get("required_flake_policy_keys"),
        "schema.required_flake_policy_keys",
        errors,
    )
    required_quarantine_enter_keys = ensure_string_list(
        schema.get("required_quarantine_enter_keys"),
        "schema.required_quarantine_enter_keys",
        errors,
    )
    required_quarantine_exit_keys = ensure_string_list(
        schema.get("required_quarantine_exit_keys"),
        "schema.required_quarantine_exit_keys",
        errors,
    )
    required_failure_envelope_fields = ensure_string_list(
        schema.get("required_failure_envelope_fields"),
        "schema.required_failure_envelope_fields",
        errors,
    )
    required_budget_ids = set(
        ensure_string_list(schema.get("required_budget_ids"), "schema.required_budget_ids", errors)
    )
    allowed_status_values = set(
        ensure_string_list(schema.get("allowed_status_values"), "schema.allowed_status_values", errors)
    )

    ensure_keys(spec, required_top_level_keys, "spec", errors)
    spec_flake_policy = ensure_dict(spec.get("flake_policy"), "spec.flake_policy", errors)
    ensure_keys(spec_flake_policy, required_flake_policy_keys, "spec.flake_policy", errors)
    spec_quarantine_enter = ensure_dict(
        spec_flake_policy.get("quarantine_enter"),
        "spec.flake_policy.quarantine_enter",
        errors,
    )
    spec_quarantine_exit = ensure_dict(
        spec_flake_policy.get("quarantine_exit"),
        "spec.flake_policy.quarantine_exit",
        errors,
    )
    ensure_keys(
        spec_quarantine_enter,
        required_quarantine_enter_keys,
        "spec.flake_policy.quarantine_enter",
        errors,
    )
    ensure_keys(
        spec_quarantine_exit,
        required_quarantine_exit_keys,
        "spec.flake_policy.quarantine_exit",
        errors,
    )

    spec_budgets = ensure_dict_list(spec.get("budget_definitions"), "spec.budget_definitions", errors)
    observed_spec_budget_ids: set[str] = set()
    for idx, budget in enumerate(spec_budgets):
        ctx = f"spec.budget_definitions[{idx}]"
        ensure_keys(budget, required_budget_keys, ctx, errors)
        budget_id = ensure_non_empty_string(budget.get("budget_id"), f"{ctx}.budget_id", errors)
        if budget_id:
            if budget_id in observed_spec_budget_ids:
                errors.append(f"{ctx}.budget_id duplicates `{budget_id}`")
            observed_spec_budget_ids.add(budget_id)
        coverage_floor = ensure_dict(budget.get("coverage_floor"), f"{ctx}.coverage_floor", errors)
        ensure_keys(
            coverage_floor,
            required_coverage_floor_keys,
            f"{ctx}.coverage_floor",
            errors,
        )
        runtime_guardrail = ensure_dict(
            budget.get("runtime_guardrail"),
            f"{ctx}.runtime_guardrail",
            errors,
        )
        ensure_keys(
            runtime_guardrail,
            required_runtime_guardrail_keys,
            f"{ctx}.runtime_guardrail",
            errors,
        )
        evidence_paths = ensure_string_list(budget.get("evidence_paths"), f"{ctx}.evidence_paths", errors)
        if not evidence_paths:
            errors.append(f"{ctx}.evidence_paths must be non-empty")
        for evidence_idx, evidence in enumerate(evidence_paths):
            ensure_rel_path(evidence, f"{ctx}.evidence_paths[{evidence_idx}]", errors)

    if observed_spec_budget_ids != required_budget_ids:
        errors.append(
            "spec budget_id set mismatch schema.required_budget_ids: "
            f"observed={sorted(observed_spec_budget_ids)} required={sorted(required_budget_ids)}"
        )

    report_required_top_keys = [
        "schema_version",
        "report_id",
        "generated_at_utc",
        "source_bead_id",
        "status",
        "flake_summary",
        "budgets",
        "failure_envelopes",
        "artifact_refs",
    ]
    ensure_keys(report, report_required_top_keys, "report", errors)
    if report.get("source_bead_id") != SOURCE_BEAD_ID:
        errors.append("report.source_bead_id must be `bd-315.23`")

    report_status = ensure_non_empty_string(report.get("status"), "report.status", errors)
    if report_status and report_status not in allowed_status_values:
        errors.append(
            "report.status must be one of "
            f"{sorted(allowed_status_values)}; got `{report_status}`"
        )

    flake_summary = ensure_dict(report.get("flake_summary"), "report.flake_summary", errors)
    flake_summary_required_keys = [
        "total_observations",
        "flake_events",
        "flake_rate_pct_7d",
        "warn_threshold_pct",
        "fail_threshold_pct",
        "quarantined_test_count",
    ]
    ensure_keys(flake_summary, flake_summary_required_keys, "report.flake_summary", errors)

    summary_warn = coerce_float(
        flake_summary.get("warn_threshold_pct"),
        "report.flake_summary.warn_threshold_pct",
        errors,
    )
    summary_fail = coerce_float(
        flake_summary.get("fail_threshold_pct"),
        "report.flake_summary.fail_threshold_pct",
        errors,
    )
    spec_warn = coerce_float(spec_flake_policy.get("warn_threshold_pct"), "spec.flake_policy.warn_threshold_pct", errors)
    spec_fail = coerce_float(spec_flake_policy.get("fail_threshold_pct"), "spec.flake_policy.fail_threshold_pct", errors)
    if summary_warn is not None and spec_warn is not None and abs(summary_warn - spec_warn) > 1e-9:
        errors.append("report.flake_summary.warn_threshold_pct drifted from spec")
    if summary_fail is not None and spec_fail is not None and abs(summary_fail - spec_fail) > 1e-9:
        errors.append("report.flake_summary.fail_threshold_pct drifted from spec")

    report_budgets = ensure_dict_list(report.get("budgets"), "report.budgets", errors)
    if not report_budgets:
        errors.append("report.budgets must be non-empty")

    report_budget_required_keys = [
        "budget_id",
        "packet_family",
        "status",
        "failing_test_groups",
        "missing_evidence_paths",
        "observed",
        "thresholds",
        "gate_command",
        "artifact_paths",
        "owner_bead_id",
    ]
    observed_report_budget_ids: set[str] = set()
    budget_status_by_id: dict[str, str] = {}
    for idx, budget in enumerate(report_budgets):
        ctx = f"report.budgets[{idx}]"
        ensure_keys(budget, report_budget_required_keys, ctx, errors)
        budget_id = ensure_non_empty_string(budget.get("budget_id"), f"{ctx}.budget_id", errors)
        status = ensure_non_empty_string(budget.get("status"), f"{ctx}.status", errors)
        if status and status not in allowed_status_values:
            errors.append(f"{ctx}.status must be one of {sorted(allowed_status_values)}; got `{status}`")
        if budget.get("owner_bead_id") != SOURCE_BEAD_ID:
            errors.append(f"{ctx}.owner_bead_id must be `{SOURCE_BEAD_ID}`")
        if budget_id:
            if budget_id in observed_report_budget_ids:
                errors.append(f"{ctx}.budget_id duplicates `{budget_id}`")
            observed_report_budget_ids.add(budget_id)
            budget_status_by_id[budget_id] = status
            if budget_id not in required_budget_ids:
                errors.append(f"{ctx}.budget_id `{budget_id}` not in schema.required_budget_ids")

        ensure_non_empty_string(budget.get("packet_family"), f"{ctx}.packet_family", errors)
        gate_command = ensure_non_empty_string(budget.get("gate_command"), f"{ctx}.gate_command", errors)
        if gate_command and "rch exec --" not in gate_command:
            errors.append(f"{ctx}.gate_command must use `rch exec --`")

        failing_test_groups = ensure_string_list(
            budget.get("failing_test_groups"),
            f"{ctx}.failing_test_groups",
            errors,
        )
        missing_evidence_paths = ensure_string_list(
            budget.get("missing_evidence_paths"),
            f"{ctx}.missing_evidence_paths",
            errors,
        )
        artifact_paths = ensure_string_list(budget.get("artifact_paths"), f"{ctx}.artifact_paths", errors)
        if not artifact_paths:
            errors.append(f"{ctx}.artifact_paths must be non-empty")
        for path_idx, path_text in enumerate(artifact_paths):
            ensure_rel_path(path_text, f"{ctx}.artifact_paths[{path_idx}]", errors)

        observed = ensure_dict(budget.get("observed"), f"{ctx}.observed", errors)
        thresholds = ensure_dict(budget.get("thresholds"), f"{ctx}.thresholds", errors)
        observed_required_keys = [
            "unit_line_pct_proxy",
            "branch_pct_proxy",
            "property_count",
            "e2e_replay_pass_ratio",
            "flake_rate_pct_7d",
            "runtime_guardrail_pass",
            "missing_evidence_count",
        ]
        threshold_required_keys = [
            "unit_line_pct_floor",
            "branch_pct_floor",
            "property_floor",
            "e2e_replay_pass_floor",
            "flake_ceiling_pct_7d",
            "runtime_guardrail",
        ]
        ensure_keys(observed, observed_required_keys, f"{ctx}.observed", errors)
        ensure_keys(thresholds, threshold_required_keys, f"{ctx}.thresholds", errors)

        unit_line = coerce_float(observed.get("unit_line_pct_proxy"), f"{ctx}.observed.unit_line_pct_proxy", errors)
        branch = coerce_float(observed.get("branch_pct_proxy"), f"{ctx}.observed.branch_pct_proxy", errors)
        property_count = coerce_int(observed.get("property_count"), f"{ctx}.observed.property_count", errors)
        e2e_ratio = coerce_float(
            observed.get("e2e_replay_pass_ratio"),
            f"{ctx}.observed.e2e_replay_pass_ratio",
            errors,
        )
        flake_rate = coerce_float(observed.get("flake_rate_pct_7d"), f"{ctx}.observed.flake_rate_pct_7d", errors)
        runtime_pass = observed.get("runtime_guardrail_pass")
        missing_evidence_count = coerce_int(
            observed.get("missing_evidence_count"),
            f"{ctx}.observed.missing_evidence_count",
            errors,
        )

        unit_floor = coerce_float(thresholds.get("unit_line_pct_floor"), f"{ctx}.thresholds.unit_line_pct_floor", errors)
        branch_floor = coerce_float(thresholds.get("branch_pct_floor"), f"{ctx}.thresholds.branch_pct_floor", errors)
        property_floor = coerce_int(thresholds.get("property_floor"), f"{ctx}.thresholds.property_floor", errors)
        e2e_floor = coerce_float(
            thresholds.get("e2e_replay_pass_floor"),
            f"{ctx}.thresholds.e2e_replay_pass_floor",
            errors,
        )
        flake_ceiling = coerce_float(
            thresholds.get("flake_ceiling_pct_7d"),
            f"{ctx}.thresholds.flake_ceiling_pct_7d",
            errors,
        )

        if status == "pass":
            if failing_test_groups:
                errors.append(f"{ctx}.failing_test_groups must be empty for pass status")
            if missing_evidence_paths:
                errors.append(f"{ctx}.missing_evidence_paths must be empty for pass status")
            if runtime_pass is not True:
                errors.append(f"{ctx}.observed.runtime_guardrail_pass must be true for pass status")
            if missing_evidence_count is not None and missing_evidence_count != 0:
                errors.append(f"{ctx}.observed.missing_evidence_count must be 0 for pass status")

            if unit_line is not None and unit_floor is not None and unit_line < unit_floor:
                errors.append(f"{ctx}.observed.unit_line_pct_proxy below floor")
            if branch is not None and branch_floor is not None and branch < branch_floor:
                errors.append(f"{ctx}.observed.branch_pct_proxy below floor")
            if property_count is not None and property_floor is not None and property_count < property_floor:
                errors.append(f"{ctx}.observed.property_count below floor")
            if e2e_ratio is not None and e2e_floor is not None and e2e_ratio < e2e_floor:
                errors.append(f"{ctx}.observed.e2e_replay_pass_ratio below floor")
            if flake_rate is not None and flake_ceiling is not None and flake_rate > flake_ceiling:
                errors.append(f"{ctx}.observed.flake_rate_pct_7d above ceiling")

    if observed_report_budget_ids != required_budget_ids:
        errors.append(
            "report budget_id set mismatch schema.required_budget_ids: "
            f"observed={sorted(observed_report_budget_ids)} required={sorted(required_budget_ids)}"
        )

    failure_envelopes = ensure_dict_list(
        report.get("failure_envelopes"),
        "report.failure_envelopes",
        errors,
    )
    envelope_budget_ids: set[str] = set()
    for idx, envelope in enumerate(failure_envelopes):
        ctx = f"report.failure_envelopes[{idx}]"
        ensure_keys(envelope, required_failure_envelope_fields, ctx, errors)
        budget_id = ensure_non_empty_string(envelope.get("budget_id"), f"{ctx}.budget_id", errors)
        status = ensure_non_empty_string(envelope.get("status"), f"{ctx}.status", errors)
        if status and status not in {"warn", "fail"}:
            errors.append(f"{ctx}.status must be `warn` or `fail`")
        if budget_id:
            envelope_budget_ids.add(budget_id)
            if budget_id not in observed_report_budget_ids:
                errors.append(f"{ctx}.budget_id `{budget_id}` missing from report.budgets")
        artifact_paths = ensure_string_list(envelope.get("artifact_paths"), f"{ctx}.artifact_paths", errors)
        if not artifact_paths:
            errors.append(f"{ctx}.artifact_paths must be non-empty")
        for path_idx, path_text in enumerate(artifact_paths):
            ensure_rel_path(path_text, f"{ctx}.artifact_paths[{path_idx}]", errors)
        replay_commands = ensure_string_list(envelope.get("replay_commands"), f"{ctx}.replay_commands", errors)
        if not replay_commands:
            errors.append(f"{ctx}.replay_commands must be non-empty")
        for replay_idx, command in enumerate(replay_commands):
            if "rch exec --" not in command:
                errors.append(f"{ctx}.replay_commands[{replay_idx}] must use `rch exec --`")
        if envelope.get("owner_bead_id") != SOURCE_BEAD_ID:
            errors.append(f"{ctx}.owner_bead_id must be `{SOURCE_BEAD_ID}`")

    for budget_id, status in budget_status_by_id.items():
        if status in {"warn", "fail"} and budget_id not in envelope_budget_ids:
            errors.append(
                f"report.failure_envelopes missing entry for non-pass budget `{budget_id}`"
            )
        if status == "pass" and budget_id in envelope_budget_ids:
            errors.append(
                f"report.failure_envelopes should not include pass budget `{budget_id}`"
            )

    derived_status = "pass"
    if any(status == "fail" for status in budget_status_by_id.values()):
        derived_status = "fail"
    elif any(status == "warn" for status in budget_status_by_id.values()):
        derived_status = "warn"
    if report_status and report_status != derived_status:
        errors.append(
            f"report.status `{report_status}` inconsistent with budget statuses (`{derived_status}`)"
        )

    artifact_refs = ensure_string_list(report.get("artifact_refs"), "report.artifact_refs", errors)
    for idx, path_text in enumerate(artifact_refs):
        ensure_rel_path(path_text, f"report.artifact_refs[{idx}]", errors)

    quarantine_required_top_keys = [
        "schema_version",
        "artifact_id",
        "generated_at_utc",
        "source_bead_id",
        "status",
        "policy",
        "rolling_flake_rate_pct_7d",
        "quarantined_tests",
        "evidence_paths",
    ]
    ensure_keys(quarantine, quarantine_required_top_keys, "quarantine", errors)
    if quarantine.get("source_bead_id") != SOURCE_BEAD_ID:
        errors.append("quarantine.source_bead_id must be `bd-315.23`")

    quarantine_policy = ensure_dict(quarantine.get("policy"), "quarantine.policy", errors)
    ensure_keys(quarantine_policy, required_flake_policy_keys, "quarantine.policy", errors)
    quarantine_enter = ensure_dict(
        quarantine_policy.get("quarantine_enter"),
        "quarantine.policy.quarantine_enter",
        errors,
    )
    quarantine_exit = ensure_dict(
        quarantine_policy.get("quarantine_exit"),
        "quarantine.policy.quarantine_exit",
        errors,
    )
    ensure_keys(
        quarantine_enter,
        required_quarantine_enter_keys,
        "quarantine.policy.quarantine_enter",
        errors,
    )
    ensure_keys(
        quarantine_exit,
        required_quarantine_exit_keys,
        "quarantine.policy.quarantine_exit",
        errors,
    )

    quarantine_warn = coerce_float(
        quarantine_policy.get("warn_threshold_pct"),
        "quarantine.policy.warn_threshold_pct",
        errors,
    )
    quarantine_fail = coerce_float(
        quarantine_policy.get("fail_threshold_pct"),
        "quarantine.policy.fail_threshold_pct",
        errors,
    )
    if quarantine_warn is not None and summary_warn is not None and abs(quarantine_warn - summary_warn) > 1e-9:
        errors.append("quarantine.policy.warn_threshold_pct drifted from report.flake_summary")
    if quarantine_fail is not None and summary_fail is not None and abs(quarantine_fail - summary_fail) > 1e-9:
        errors.append("quarantine.policy.fail_threshold_pct drifted from report.flake_summary")

    quarantined_tests = ensure_dict_list(quarantine.get("quarantined_tests"), "quarantine.quarantined_tests", errors)
    quarantine_test_required_keys = [
        "test_id",
        "flake_events",
        "observation_count",
        "status",
        "owner_bead_id",
        "replay_command",
        "artifact_refs",
    ]
    for idx, test_row in enumerate(quarantined_tests):
        ctx = f"quarantine.quarantined_tests[{idx}]"
        ensure_keys(test_row, quarantine_test_required_keys, ctx, errors)
        ensure_non_empty_string(test_row.get("test_id"), f"{ctx}.test_id", errors)
        coerce_int(test_row.get("flake_events"), f"{ctx}.flake_events", errors)
        coerce_int(test_row.get("observation_count"), f"{ctx}.observation_count", errors)
        if test_row.get("status") != "quarantined":
            errors.append(f"{ctx}.status must be `quarantined`")
        if test_row.get("owner_bead_id") != SOURCE_BEAD_ID:
            errors.append(f"{ctx}.owner_bead_id must be `{SOURCE_BEAD_ID}`")
        replay_command = ensure_non_empty_string(test_row.get("replay_command"), f"{ctx}.replay_command", errors)
        if replay_command and "rch exec -- cargo" not in replay_command:
            errors.append(f"{ctx}.replay_command must use `rch exec -- cargo`")
        artifact_refs = ensure_string_list(test_row.get("artifact_refs"), f"{ctx}.artifact_refs", errors)
        if not artifact_refs:
            errors.append(f"{ctx}.artifact_refs must be non-empty")
        for ref_idx, path_text in enumerate(artifact_refs):
            ensure_rel_path(path_text, f"{ctx}.artifact_refs[{ref_idx}]", errors)

    quarantine_status = ensure_non_empty_string(quarantine.get("status"), "quarantine.status", errors)
    if quarantine_status == "clear" and quarantined_tests:
        errors.append("quarantine.status `clear` must have zero quarantined_tests")
    if quarantine_status == "active" and not quarantined_tests:
        errors.append("quarantine.status `active` must include quarantined_tests")
    if quarantine_status not in {"active", "clear"}:
        errors.append("quarantine.status must be `active` or `clear`")

    q_count = coerce_int(
        flake_summary.get("quarantined_test_count"),
        "report.flake_summary.quarantined_test_count",
        errors,
    )
    if q_count is not None and q_count != len(quarantined_tests):
        errors.append(
            "report.flake_summary.quarantined_test_count mismatch quarantine.quarantined_tests length"
        )

    summary_rate = coerce_float(
        flake_summary.get("flake_rate_pct_7d"),
        "report.flake_summary.flake_rate_pct_7d",
        errors,
    )
    quarantine_rate = coerce_float(
        quarantine.get("rolling_flake_rate_pct_7d"),
        "quarantine.rolling_flake_rate_pct_7d",
        errors,
    )
    if summary_rate is not None and quarantine_rate is not None and abs(summary_rate - quarantine_rate) > 1e-9:
        errors.append(
            "quarantine.rolling_flake_rate_pct_7d mismatch report.flake_summary.flake_rate_pct_7d"
        )

    evidence_paths = ensure_string_list(quarantine.get("evidence_paths"), "quarantine.evidence_paths", errors)
    if not evidence_paths:
        errors.append("quarantine.evidence_paths must be non-empty")
    for idx, path_text in enumerate(evidence_paths):
        ensure_rel_path(path_text, f"quarantine.evidence_paths[{idx}]", errors)

    output_path = REPO_ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "1.0.0",
        "validation_id": "reliability-budget-gate-validation-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_bead_id": SOURCE_BEAD_ID,
        "status": "pass" if not errors else "fail",
        "error_count": len(errors),
        "errors": errors,
        "inputs": {
            "schema": args.schema,
            "spec": args.spec,
            "report": args.report,
            "quarantine": args.quarantine,
        },
    }
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    print(f"reliability_gate_validation:{output_path}")
    if errors:
        for row in errors:
            print(f"error:{row}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
