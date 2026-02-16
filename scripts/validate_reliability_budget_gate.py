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
        "required_failure_replay_metadata_keys",
        "required_budget_ids",
        "allowed_status_values",
        "required_report_top_level_keys",
        "required_report_budget_keys",
        "required_stage_result_keys",
        "required_stage_ids",
        "required_quarantine_top_level_keys",
        "required_quarantine_test_keys",
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
    required_failure_replay_metadata_keys = ensure_string_list(
        schema.get("required_failure_replay_metadata_keys"),
        "schema.required_failure_replay_metadata_keys",
        errors,
    )
    required_report_top_level_keys = ensure_string_list(
        schema.get("required_report_top_level_keys"),
        "schema.required_report_top_level_keys",
        errors,
    )
    required_report_budget_keys = ensure_string_list(
        schema.get("required_report_budget_keys"),
        "schema.required_report_budget_keys",
        errors,
    )
    required_stage_result_keys = ensure_string_list(
        schema.get("required_stage_result_keys"),
        "schema.required_stage_result_keys",
        errors,
    )
    required_stage_ids = set(
        ensure_string_list(schema.get("required_stage_ids"), "schema.required_stage_ids", errors)
    )
    required_quarantine_top_level_keys = ensure_string_list(
        schema.get("required_quarantine_top_level_keys"),
        "schema.required_quarantine_top_level_keys",
        errors,
    )
    required_quarantine_test_keys = ensure_string_list(
        schema.get("required_quarantine_test_keys"),
        "schema.required_quarantine_test_keys",
        errors,
    )
    required_budget_ids = set(
        ensure_string_list(schema.get("required_budget_ids"), "schema.required_budget_ids", errors)
    )
    allowed_status_values = set(
        ensure_string_list(schema.get("allowed_status_values"), "schema.allowed_status_values", errors)
    )

    ensure_keys(spec, required_top_level_keys, "spec", errors)
    gate_stage_contract = ensure_dict(spec.get("gate_stage_contract"), "spec.gate_stage_contract", errors)
    stage_contract_ids = set(
        ensure_string_list(
            gate_stage_contract.get("required_stage_ids"),
            "spec.gate_stage_contract.required_stage_ids",
            errors,
        )
    )
    if stage_contract_ids and stage_contract_ids != required_stage_ids:
        errors.append(
            "spec.gate_stage_contract.required_stage_ids drifted from schema.required_stage_ids: "
            f"spec={sorted(stage_contract_ids)} schema={sorted(required_stage_ids)}"
        )
    run_id_prefix = ensure_non_empty_string(
        gate_stage_contract.get("run_id_prefix"),
        "spec.gate_stage_contract.run_id_prefix",
        errors,
    )

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

    ensure_keys(report, required_report_top_level_keys, "report", errors)
    if report.get("source_bead_id") != SOURCE_BEAD_ID:
        errors.append("report.source_bead_id must be `bd-315.23`")
    report_run_id = ensure_non_empty_string(report.get("run_id"), "report.run_id", errors)
    report_deterministic_seed = ensure_non_empty_string(
        report.get("deterministic_seed"),
        "report.deterministic_seed",
        errors,
    )
    if report_run_id and run_id_prefix and not report_run_id.startswith(run_id_prefix):
        errors.append(
            f"report.run_id must start with `{run_id_prefix}`; got `{report_run_id}`"
        )
    if report_deterministic_seed and len(report_deterministic_seed) < 16:
        errors.append("report.deterministic_seed should be hash-like (len >= 16)")

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

    observed_report_budget_ids: set[str] = set()
    budget_status_by_id: dict[str, str] = {}
    non_pass_stage_ids_by_budget: dict[str, list[str]] = {}
    for idx, budget in enumerate(report_budgets):
        ctx = f"report.budgets[{idx}]"
        ensure_keys(budget, required_report_budget_keys, ctx, errors)
        budget_id = ensure_non_empty_string(budget.get("budget_id"), f"{ctx}.budget_id", errors)
        budget_run_id = ensure_non_empty_string(budget.get("run_id"), f"{ctx}.run_id", errors)
        if report_run_id and budget_run_id and budget_run_id != report_run_id:
            errors.append(f"{ctx}.run_id must match report.run_id")
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

        stage_results = ensure_dict_list(budget.get("stage_results"), f"{ctx}.stage_results", errors)
        if not stage_results:
            errors.append(f"{ctx}.stage_results must be non-empty")
        observed_stage_ids: set[str] = set()
        non_pass_stage_ids: list[str] = []
        for stage_idx, stage in enumerate(stage_results):
            stage_ctx = f"{ctx}.stage_results[{stage_idx}]"
            ensure_keys(stage, required_stage_result_keys, stage_ctx, errors)
            stage_id = ensure_non_empty_string(stage.get("stage_id"), f"{stage_ctx}.stage_id", errors)
            stage_run_id = ensure_non_empty_string(stage.get("run_id"), f"{stage_ctx}.run_id", errors)
            stage_status = ensure_non_empty_string(stage.get("status"), f"{stage_ctx}.status", errors)
            if stage_status and stage_status not in allowed_status_values:
                errors.append(
                    f"{stage_ctx}.status must be one of {sorted(allowed_status_values)}; got `{stage_status}`"
                )
            if stage_id:
                if stage_id in observed_stage_ids:
                    errors.append(f"{stage_ctx}.stage_id duplicates `{stage_id}`")
                observed_stage_ids.add(stage_id)
            if budget_id and stage_run_id and not stage_run_id.startswith(f"{report_run_id}::{budget_id}::"):
                errors.append(f"{stage_ctx}.run_id must be namespaced by report/budget run id")
            stage_replay = ensure_non_empty_string(stage.get("replay_command"), f"{stage_ctx}.replay_command", errors)
            if stage_replay and "cargo " in stage_replay and "rch exec --" not in stage_replay:
                errors.append(f"{stage_ctx}.replay_command must use `rch exec --` for cargo commands")
            stage_artifacts = ensure_string_list(stage.get("artifact_refs"), f"{stage_ctx}.artifact_refs", errors)
            if not stage_artifacts:
                errors.append(f"{stage_ctx}.artifact_refs must be non-empty")
            for art_idx, path_text in enumerate(stage_artifacts):
                ensure_rel_path(path_text, f"{stage_ctx}.artifact_refs[{art_idx}]", errors)
            ensure_dict(stage.get("observed_value"), f"{stage_ctx}.observed_value", errors)
            ensure_dict(stage.get("threshold_value"), f"{stage_ctx}.threshold_value", errors)
            if stage_status and stage_status != "pass":
                non_pass_stage_ids.append(stage_id)

        if observed_stage_ids and observed_stage_ids != required_stage_ids:
            errors.append(
                f"{ctx}.stage_results stage IDs drifted from schema: observed={sorted(observed_stage_ids)} "
                f"required={sorted(required_stage_ids)}"
            )
        if budget_id:
            non_pass_stage_ids_by_budget[budget_id] = [stage for stage in non_pass_stage_ids if stage]

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
            if non_pass_stage_ids:
                errors.append(f"{ctx}.stage_results must all be `pass` for budget pass status")
        elif not non_pass_stage_ids:
            errors.append(f"{ctx}.stage_results must include non-pass stage(s) for budget status `{status}`")

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
        envelope_run_id = ensure_non_empty_string(envelope.get("run_id"), f"{ctx}.run_id", errors)
        if report_run_id and envelope_run_id and envelope_run_id != report_run_id:
            errors.append(f"{ctx}.run_id must match report.run_id")
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
        replay_metadata = ensure_dict(envelope.get("replay_metadata"), f"{ctx}.replay_metadata", errors)
        ensure_keys(
            replay_metadata,
            required_failure_replay_metadata_keys,
            f"{ctx}.replay_metadata",
            errors,
        )
        metadata_run_id = ensure_non_empty_string(
            replay_metadata.get("run_id"),
            f"{ctx}.replay_metadata.run_id",
            errors,
        )
        if envelope_run_id and metadata_run_id and envelope_run_id != metadata_run_id:
            errors.append(f"{ctx}.replay_metadata.run_id must match envelope.run_id")
        metadata_seed = ensure_non_empty_string(
            replay_metadata.get("deterministic_seed"),
            f"{ctx}.replay_metadata.deterministic_seed",
            errors,
        )
        if report_deterministic_seed and metadata_seed and metadata_seed != report_deterministic_seed:
            errors.append(f"{ctx}.replay_metadata.deterministic_seed must match report.deterministic_seed")
        metadata_gate_command = ensure_non_empty_string(
            replay_metadata.get("gate_command"),
            f"{ctx}.replay_metadata.gate_command",
            errors,
        )
        if metadata_gate_command and "rch exec --" not in metadata_gate_command:
            errors.append(f"{ctx}.replay_metadata.gate_command must use `rch exec --`")
        failing_stage_ids = ensure_string_list(
            replay_metadata.get("failing_stage_ids"),
            f"{ctx}.replay_metadata.failing_stage_ids",
            errors,
        )
        failed_stage_count = coerce_int(
            replay_metadata.get("failed_stage_count"),
            f"{ctx}.replay_metadata.failed_stage_count",
            errors,
        )
        if failed_stage_count is not None and failed_stage_count != len(failing_stage_ids):
            errors.append(f"{ctx}.replay_metadata.failed_stage_count must match failing_stage_ids length")
        if budget_id:
            budget_non_pass_stages = non_pass_stage_ids_by_budget.get(budget_id, [])
            if sorted(failing_stage_ids) != sorted(budget_non_pass_stages):
                errors.append(
                    f"{ctx}.replay_metadata.failing_stage_ids mismatch budget stage failures: "
                    f"metadata={sorted(failing_stage_ids)} budget={sorted(budget_non_pass_stages)}"
                )
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

    ensure_keys(quarantine, required_quarantine_top_level_keys, "quarantine", errors)
    if quarantine.get("source_bead_id") != SOURCE_BEAD_ID:
        errors.append("quarantine.source_bead_id must be `bd-315.23`")
    quarantine_run_id = ensure_non_empty_string(quarantine.get("run_id"), "quarantine.run_id", errors)
    if report_run_id and quarantine_run_id and report_run_id != quarantine_run_id:
        errors.append("quarantine.run_id must match report.run_id")

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
    for idx, test_row in enumerate(quarantined_tests):
        ctx = f"quarantine.quarantined_tests[{idx}]"
        ensure_keys(test_row, required_quarantine_test_keys, ctx, errors)
        ensure_non_empty_string(test_row.get("test_id"), f"{ctx}.test_id", errors)
        coerce_int(test_row.get("flake_events"), f"{ctx}.flake_events", errors)
        coerce_int(test_row.get("observation_count"), f"{ctx}.observation_count", errors)
        if test_row.get("status") != "quarantined":
            errors.append(f"{ctx}.status must be `quarantined`")
        if test_row.get("owner_bead_id") != SOURCE_BEAD_ID:
            errors.append(f"{ctx}.owner_bead_id must be `{SOURCE_BEAD_ID}`")
        test_run_id = ensure_non_empty_string(test_row.get("run_id"), f"{ctx}.run_id", errors)
        if quarantine_run_id and test_run_id and test_run_id != quarantine_run_id:
            errors.append(f"{ctx}.run_id must match quarantine.run_id")
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
