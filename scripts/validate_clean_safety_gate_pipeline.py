#!/usr/bin/env python3
"""Validate clean safety gate pipeline artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def require_keys(payload: dict[str, Any], keys: list[str], ctx: str, errors: list[str]) -> None:
    for key in keys:
        if key not in payload:
            errors.append(f"{ctx} missing key `{key}`")


def ensure_dict(value: Any, ctx: str, errors: list[str]) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    errors.append(f"{ctx} must be an object")
    return {}


def ensure_list(value: Any, ctx: str, errors: list[str]) -> list[Any]:
    if isinstance(value, list):
        return value
    errors.append(f"{ctx} must be a list")
    return []


def ensure_non_empty_string(value: Any, ctx: str, errors: list[str]) -> str:
    if isinstance(value, str) and value.strip():
        return value
    errors.append(f"{ctx} must be a non-empty string")
    return ""


def ensure_string_list(value: Any, ctx: str, errors: list[str]) -> list[str]:
    rows = ensure_list(value, ctx, errors)
    out: list[str] = []
    for idx, row in enumerate(rows):
        text = ensure_non_empty_string(row, f"{ctx}[{idx}]", errors)
        if text:
            out.append(text)
    return out


def ensure_existing_path(path_text: str, ctx: str, root: Path, errors: list[str]) -> None:
    if not path_text:
        return
    if not (root / path_text).exists():
        errors.append(f"{ctx} path does not exist: {path_text}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--artifact",
        default="artifacts/clean/v1/clean_safety_gate_pipeline_v1.json",
        help="Path to safety gate pipeline artifact",
    )
    parser.add_argument(
        "--schema",
        default="artifacts/clean/schema/v1/clean_safety_gate_pipeline_schema_v1.json",
        help="Path to safety gate schema",
    )
    parser.add_argument(
        "--output",
        default="artifacts/clean/latest/clean_safety_gate_pipeline_validation_v1.json",
        help="Output validation report path",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    artifact = load_json(root / args.artifact)
    schema = load_json(root / args.schema)

    errors: list[str] = []
    require_keys(artifact, schema["required_top_level_keys"], "artifact", errors)

    gate_matrix = ensure_list(artifact.get("gate_matrix"), "artifact.gate_matrix", errors)
    if not gate_matrix:
        errors.append("artifact.gate_matrix must be non-empty")

    gate_ids: set[str] = set()
    gate_type_observed: set[str] = set()
    for idx, row in enumerate(gate_matrix):
        if not isinstance(row, dict):
            errors.append(f"artifact.gate_matrix[{idx}] must be object")
            continue
        require_keys(row, schema["required_gate_row_keys"], f"artifact.gate_matrix[{idx}]", errors)

        gate_id = ensure_non_empty_string(row.get("gate_id"), f"artifact.gate_matrix[{idx}].gate_id", errors)
        if gate_id:
            if gate_id in gate_ids:
                errors.append(f"duplicate gate_id `{gate_id}`")
            gate_ids.add(gate_id)

        gate_type = ensure_non_empty_string(
            row.get("gate_type"),
            f"artifact.gate_matrix[{idx}].gate_type",
            errors,
        )
        if gate_type:
            gate_type_observed.add(gate_type)
            if gate_type not in schema["allowed_gate_types"]:
                errors.append(
                    f"artifact.gate_matrix[{idx}].gate_type `{gate_type}` outside allowed types"
                )

        ensure_non_empty_string(row.get("command"), f"artifact.gate_matrix[{idx}].command", errors)
        ensure_non_empty_string(row.get("owner"), f"artifact.gate_matrix[{idx}].owner", errors)
        ensure_non_empty_string(
            row.get("pass_condition"),
            f"artifact.gate_matrix[{idx}].pass_condition",
            errors,
        )
        ensure_non_empty_string(
            row.get("fail_condition"),
            f"artifact.gate_matrix[{idx}].fail_condition",
            errors,
        )

        output_artifact = ensure_non_empty_string(
            row.get("output_artifact"),
            f"artifact.gate_matrix[{idx}].output_artifact",
            errors,
        )
        ensure_existing_path(
            output_artifact,
            f"artifact.gate_matrix[{idx}].output_artifact",
            root,
            errors,
        )

        reproducibility = ensure_dict(
            row.get("reproducibility"),
            f"artifact.gate_matrix[{idx}].reproducibility",
            errors,
        )
        require_keys(
            reproducibility,
            schema["required_reproducibility_keys"],
            f"artifact.gate_matrix[{idx}].reproducibility",
            errors,
        )
        for key in schema["required_reproducibility_keys"]:
            ensure_non_empty_string(
                reproducibility.get(key),
                f"artifact.gate_matrix[{idx}].reproducibility.{key}",
                errors,
            )

    if "static" not in gate_type_observed:
        errors.append("artifact.gate_matrix must include at least one static gate")
    if "dynamic" not in gate_type_observed:
        errors.append("artifact.gate_matrix must include at least one dynamic gate")

    high_risk_coverage = ensure_list(
        artifact.get("high_risk_coverage"),
        "artifact.high_risk_coverage",
        errors,
    )
    if not high_risk_coverage:
        errors.append("artifact.high_risk_coverage must be non-empty")

    required_coverage_modes = set(schema["required_coverage_modes"])
    required_triage_buckets = set(schema["required_triage_buckets"])

    high_risk_target_ids: set[str] = set()
    high_risk_triage_buckets: set[str] = set()
    for idx, row in enumerate(high_risk_coverage):
        if not isinstance(row, dict):
            errors.append(f"artifact.high_risk_coverage[{idx}] must be object")
            continue
        require_keys(
            row,
            schema["required_high_risk_entry_keys"],
            f"artifact.high_risk_coverage[{idx}]",
            errors,
        )

        target_id = ensure_non_empty_string(
            row.get("target_id"),
            f"artifact.high_risk_coverage[{idx}].target_id",
            errors,
        )
        if target_id:
            if target_id in high_risk_target_ids:
                errors.append(f"duplicate high_risk target_id `{target_id}`")
            high_risk_target_ids.add(target_id)

        ensure_non_empty_string(
            row.get("category"),
            f"artifact.high_risk_coverage[{idx}].category",
            errors,
        )
        ensure_non_empty_string(
            row.get("risk_level"),
            f"artifact.high_risk_coverage[{idx}].risk_level",
            errors,
        )

        coverage_modes = set(
            ensure_string_list(
                row.get("coverage_modes"),
                f"artifact.high_risk_coverage[{idx}].coverage_modes",
                errors,
            )
        )
        missing_modes = sorted(required_coverage_modes - coverage_modes)
        if missing_modes:
            errors.append(
                f"artifact.high_risk_coverage[{idx}] missing required coverage modes: {', '.join(missing_modes)}"
            )

        entrypoint = ensure_non_empty_string(
            row.get("entrypoint_path"),
            f"artifact.high_risk_coverage[{idx}].entrypoint_path",
            errors,
        )
        ensure_existing_path(
            entrypoint,
            f"artifact.high_risk_coverage[{idx}].entrypoint_path",
            root,
            errors,
        )

        fixtures = ensure_string_list(
            row.get("fixtures"),
            f"artifact.high_risk_coverage[{idx}].fixtures",
            errors,
        )
        if not fixtures:
            errors.append(f"artifact.high_risk_coverage[{idx}].fixtures must be non-empty")
        for fixture_idx, fixture_path in enumerate(fixtures):
            ensure_existing_path(
                fixture_path,
                f"artifact.high_risk_coverage[{idx}].fixtures[{fixture_idx}]",
                root,
                errors,
            )

        triage_bucket = ensure_non_empty_string(
            row.get("triage_bucket"),
            f"artifact.high_risk_coverage[{idx}].triage_bucket",
            errors,
        )
        if triage_bucket:
            high_risk_triage_buckets.add(triage_bucket)
            if triage_bucket not in required_triage_buckets:
                errors.append(
                    f"artifact.high_risk_coverage[{idx}].triage_bucket `{triage_bucket}` outside required buckets"
                )

    execution_workflows = ensure_dict(
        artifact.get("execution_workflows"),
        "artifact.execution_workflows",
        errors,
    )
    require_keys(
        execution_workflows,
        schema["required_execution_workflow_keys"],
        "artifact.execution_workflows",
        errors,
    )

    local_commands = ensure_string_list(
        execution_workflows.get("local_commands"),
        "artifact.execution_workflows.local_commands",
        errors,
    )
    if not local_commands:
        errors.append("artifact.execution_workflows.local_commands must be non-empty")

    ci_commands = ensure_string_list(
        execution_workflows.get("ci_commands"),
        "artifact.execution_workflows.ci_commands",
        errors,
    )
    if not ci_commands:
        errors.append("artifact.execution_workflows.ci_commands must be non-empty")

    ensure_non_empty_string(
        execution_workflows.get("determinism_notes"),
        "artifact.execution_workflows.determinism_notes",
        errors,
    )

    artifact_index = ensure_list(artifact.get("artifact_index"), "artifact.artifact_index", errors)
    if not artifact_index:
        errors.append("artifact.artifact_index must be non-empty")

    artifact_index_ids: set[str] = set()
    for idx, row in enumerate(artifact_index):
        if not isinstance(row, dict):
            errors.append(f"artifact.artifact_index[{idx}] must be object")
            continue
        require_keys(row, schema["required_artifact_index_keys"], f"artifact.artifact_index[{idx}]", errors)

        artifact_id = ensure_non_empty_string(
            row.get("artifact_id"),
            f"artifact.artifact_index[{idx}].artifact_id",
            errors,
        )
        if artifact_id:
            if artifact_id in artifact_index_ids:
                errors.append(f"duplicate artifact_index artifact_id `{artifact_id}`")
            artifact_index_ids.add(artifact_id)

        path_text = ensure_non_empty_string(
            row.get("path"),
            f"artifact.artifact_index[{idx}].path",
            errors,
        )
        ensure_existing_path(
            path_text,
            f"artifact.artifact_index[{idx}].path",
            root,
            errors,
        )

        producer_gate = ensure_non_empty_string(
            row.get("producer_gate_id"),
            f"artifact.artifact_index[{idx}].producer_gate_id",
            errors,
        )
        if producer_gate and producer_gate not in gate_ids:
            errors.append(
                f"artifact.artifact_index[{idx}].producer_gate_id `{producer_gate}` does not map to gate_matrix"
            )

    triage_taxonomy = ensure_list(artifact.get("triage_taxonomy"), "artifact.triage_taxonomy", errors)
    if not triage_taxonomy:
        errors.append("artifact.triage_taxonomy must be non-empty")

    observed_buckets: set[str] = set()
    for idx, bucket in enumerate(triage_taxonomy):
        if not isinstance(bucket, dict):
            errors.append(f"artifact.triage_taxonomy[{idx}] must be object")
            continue
        require_keys(bucket, schema["required_triage_bucket_keys"], f"artifact.triage_taxonomy[{idx}]", errors)

        bucket_id = ensure_non_empty_string(
            bucket.get("bucket_id"),
            f"artifact.triage_taxonomy[{idx}].bucket_id",
            errors,
        )
        if bucket_id:
            observed_buckets.add(bucket_id)
        ensure_non_empty_string(
            bucket.get("severity"),
            f"artifact.triage_taxonomy[{idx}].severity",
            errors,
        )
        ensure_non_empty_string(
            bucket.get("description"),
            f"artifact.triage_taxonomy[{idx}].description",
            errors,
        )
        ensure_non_empty_string(
            bucket.get("owner_role"),
            f"artifact.triage_taxonomy[{idx}].owner_role",
            errors,
        )
        sla = bucket.get("response_sla_hours")
        if not isinstance(sla, int) or sla < 1:
            errors.append(
                f"artifact.triage_taxonomy[{idx}].response_sla_hours must be integer >= 1"
            )

    missing_required_buckets = sorted(required_triage_buckets - observed_buckets)
    if missing_required_buckets:
        errors.append(
            f"artifact.triage_taxonomy missing required buckets: {', '.join(missing_required_buckets)}"
        )

    missing_high_risk_buckets = sorted(high_risk_triage_buckets - observed_buckets)
    if missing_high_risk_buckets:
        errors.append(
            f"high_risk_coverage references undefined triage buckets: {', '.join(missing_high_risk_buckets)}"
        )

    fail_closed = ensure_dict(
        artifact.get("fail_closed_policy_enforcement"),
        "artifact.fail_closed_policy_enforcement",
        errors,
    )
    require_keys(
        fail_closed,
        schema["required_fail_closed_policy_keys"],
        "artifact.fail_closed_policy_enforcement",
        errors,
    )
    unknown_policy = ensure_non_empty_string(
        fail_closed.get("unknown_incompatible_feature_policy"),
        "artifact.fail_closed_policy_enforcement.unknown_incompatible_feature_policy",
        errors,
    )
    if unknown_policy and unknown_policy != "fail_closed":
        errors.append(
            "artifact.fail_closed_policy_enforcement.unknown_incompatible_feature_policy must equal `fail_closed`"
        )
    missing_artifact_policy = ensure_non_empty_string(
        fail_closed.get("missing_artifact_link_policy"),
        "artifact.fail_closed_policy_enforcement.missing_artifact_link_policy",
        errors,
    )
    if missing_artifact_policy and missing_artifact_policy != "fail_closed":
        errors.append(
            "artifact.fail_closed_policy_enforcement.missing_artifact_link_policy must equal `fail_closed`"
        )
    ensure_non_empty_string(
        fail_closed.get("policy_scope"),
        "artifact.fail_closed_policy_enforcement.policy_scope",
        errors,
    )
    ensure_non_empty_string(
        fail_closed.get("violation_action"),
        "artifact.fail_closed_policy_enforcement.violation_action",
        errors,
    )
    fail_closed_audit_log_path = ensure_non_empty_string(
        fail_closed.get("audit_log_path"),
        "artifact.fail_closed_policy_enforcement.audit_log_path",
        errors,
    )
    ensure_existing_path(
        fail_closed_audit_log_path,
        "artifact.fail_closed_policy_enforcement.audit_log_path",
        root,
        errors,
    )
    enforcement_triggers = ensure_list(
        fail_closed.get("enforcement_triggers"),
        "artifact.fail_closed_policy_enforcement.enforcement_triggers",
        errors,
    )
    if not enforcement_triggers:
        errors.append("artifact.fail_closed_policy_enforcement.enforcement_triggers must be non-empty")
    observed_fail_closed_reason_codes: set[str] = set()
    for idx, trigger in enumerate(enforcement_triggers):
        if not isinstance(trigger, dict):
            errors.append(
                f"artifact.fail_closed_policy_enforcement.enforcement_triggers[{idx}] must be object"
            )
            continue
        require_keys(
            trigger,
            schema["required_fail_closed_trigger_keys"],
            f"artifact.fail_closed_policy_enforcement.enforcement_triggers[{idx}]",
            errors,
        )
        ensure_non_empty_string(
            trigger.get("trigger_id"),
            f"artifact.fail_closed_policy_enforcement.enforcement_triggers[{idx}].trigger_id",
            errors,
        )
        ensure_non_empty_string(
            trigger.get("condition"),
            f"artifact.fail_closed_policy_enforcement.enforcement_triggers[{idx}].condition",
            errors,
        )
        threshold = trigger.get("threshold")
        if not isinstance(threshold, int) or threshold < 1:
            errors.append(
                f"artifact.fail_closed_policy_enforcement.enforcement_triggers[{idx}].threshold must be integer >= 1"
            )
        fallback_action = ensure_non_empty_string(
            trigger.get("fallback_action"),
            f"artifact.fail_closed_policy_enforcement.enforcement_triggers[{idx}].fallback_action",
            errors,
        )
        if fallback_action and "fail_closed" not in fallback_action:
            errors.append(
                f"artifact.fail_closed_policy_enforcement.enforcement_triggers[{idx}].fallback_action must include `fail_closed`"
            )
        reason_code = ensure_non_empty_string(
            trigger.get("reason_code"),
            f"artifact.fail_closed_policy_enforcement.enforcement_triggers[{idx}].reason_code",
            errors,
        )
        if reason_code:
            observed_fail_closed_reason_codes.add(reason_code)
    for reason_code in ["unknown_incompatible_feature", "missing_artifact_link"]:
        if reason_code not in observed_fail_closed_reason_codes:
            errors.append(
                f"artifact.fail_closed_policy_enforcement.enforcement_triggers missing reason_code `{reason_code}`"
            )

    playbook = ensure_dict(
        artifact.get("operator_triage_playbook"),
        "artifact.operator_triage_playbook",
        errors,
    )
    require_keys(
        playbook,
        schema["required_operator_playbook_keys"],
        "artifact.operator_triage_playbook",
        errors,
    )
    ensure_non_empty_string(
        playbook.get("primary_oncall_role"),
        "artifact.operator_triage_playbook.primary_oncall_role",
        errors,
    )
    first_response_flow = ensure_list(
        playbook.get("first_response_flow"),
        "artifact.operator_triage_playbook.first_response_flow",
        errors,
    )
    if not first_response_flow:
        errors.append("artifact.operator_triage_playbook.first_response_flow must be non-empty")
    for idx, step in enumerate(first_response_flow):
        if not isinstance(step, dict):
            errors.append(f"artifact.operator_triage_playbook.first_response_flow[{idx}] must be object")
            continue
        require_keys(
            step,
            schema["required_playbook_step_keys"],
            f"artifact.operator_triage_playbook.first_response_flow[{idx}]",
            errors,
        )
        for key in ["step_id", "action", "owner_role"]:
            ensure_non_empty_string(
                step.get(key),
                f"artifact.operator_triage_playbook.first_response_flow[{idx}].{key}",
                errors,
            )
        max_response = step.get("max_response_minutes")
        if not isinstance(max_response, int) or max_response < 1:
            errors.append(
                f"artifact.operator_triage_playbook.first_response_flow[{idx}].max_response_minutes must be integer >= 1"
            )
    escalation_rules = ensure_list(
        playbook.get("escalation_rules"),
        "artifact.operator_triage_playbook.escalation_rules",
        errors,
    )
    if not escalation_rules:
        errors.append("artifact.operator_triage_playbook.escalation_rules must be non-empty")
    for idx, rule in enumerate(escalation_rules):
        if not isinstance(rule, dict):
            errors.append(f"artifact.operator_triage_playbook.escalation_rules[{idx}] must be object")
            continue
        require_keys(
            rule,
            schema["required_escalation_rule_keys"],
            f"artifact.operator_triage_playbook.escalation_rules[{idx}]",
            errors,
        )
        for key in ["rule_id", "condition", "escalate_to", "severity_floor"]:
            ensure_non_empty_string(
                rule.get(key),
                f"artifact.operator_triage_playbook.escalation_rules[{idx}].{key}",
                errors,
            )
        max_minutes = rule.get("max_minutes")
        if not isinstance(max_minutes, int) or max_minutes < 1:
            errors.append(
                f"artifact.operator_triage_playbook.escalation_rules[{idx}].max_minutes must be integer >= 1"
            )
    audit_trail_requirements = ensure_string_list(
        playbook.get("audit_trail_requirements"),
        "artifact.operator_triage_playbook.audit_trail_requirements",
        errors,
    )
    if not audit_trail_requirements:
        errors.append("artifact.operator_triage_playbook.audit_trail_requirements must be non-empty")

    dashboard_contract = ensure_dict(
        artifact.get("gate_dashboard_contract"),
        "artifact.gate_dashboard_contract",
        errors,
    )
    require_keys(
        dashboard_contract,
        schema["required_dashboard_contract_keys"],
        "artifact.gate_dashboard_contract",
        errors,
    )
    dashboard_path = ensure_non_empty_string(
        dashboard_contract.get("path"),
        "artifact.gate_dashboard_contract.path",
        errors,
    )
    ensure_existing_path(dashboard_path, "artifact.gate_dashboard_contract.path", root, errors)
    ensure_non_empty_string(
        dashboard_contract.get("schema_version"),
        "artifact.gate_dashboard_contract.schema_version",
        errors,
    )
    dashboard_required_fields = ensure_string_list(
        dashboard_contract.get("required_fields"),
        "artifact.gate_dashboard_contract.required_fields",
        errors,
    )
    if set(dashboard_required_fields) != set(schema["required_dashboard_fields"]):
        errors.append(
            "artifact.gate_dashboard_contract.required_fields must match schema.required_dashboard_fields"
        )
    dashboard_sort_keys = ensure_string_list(
        dashboard_contract.get("deterministic_sort_keys"),
        "artifact.gate_dashboard_contract.deterministic_sort_keys",
        errors,
    )
    if not dashboard_sort_keys:
        errors.append("artifact.gate_dashboard_contract.deterministic_sort_keys must be non-empty")
    deterministic_ordering = ensure_non_empty_string(
        dashboard_contract.get("deterministic_ordering"),
        "artifact.gate_dashboard_contract.deterministic_ordering",
        errors,
    )
    if deterministic_ordering and deterministic_ordering != "lexicographic":
        errors.append("artifact.gate_dashboard_contract.deterministic_ordering must equal `lexicographic`")
    ensure_non_empty_string(
        dashboard_contract.get("audit_mode"),
        "artifact.gate_dashboard_contract.audit_mode",
        errors,
    )

    if dashboard_path and (root / dashboard_path).exists():
        dashboard = load_json(root / dashboard_path)
        for key in schema["required_dashboard_fields"]:
            if key not in dashboard:
                errors.append(f"dashboard missing required key `{key}`")
        if dashboard.get("status") != "pass":
            errors.append("dashboard.status must be `pass`")
        if dashboard.get("audit_friendly") is not True:
            errors.append("dashboard.audit_friendly must be true")
        if dashboard.get("deterministic") is not True:
            errors.append("dashboard.deterministic must be true")
        gate_summary = ensure_dict(dashboard.get("gate_summary"), "dashboard.gate_summary", errors)
        if gate_summary.get("total_gates") != len(gate_matrix):
            errors.append("dashboard.gate_summary.total_gates mismatch gate_matrix size")
        required_gate_ids = gate_summary.get("required_gate_ids")
        if isinstance(required_gate_ids, list):
            observed_required_gate_ids = sorted(
                gate_id for gate_id in required_gate_ids if isinstance(gate_id, str)
            )
            if observed_required_gate_ids != sorted(gate_ids):
                errors.append("dashboard.gate_summary.required_gate_ids mismatch gate_matrix gate IDs")
        else:
            errors.append("dashboard.gate_summary.required_gate_ids must be array")
        fail_closed_summary = ensure_dict(
            dashboard.get("fail_closed_summary"),
            "dashboard.fail_closed_summary",
            errors,
        )
        if fail_closed_summary.get("unknown_incompatible_feature_policy") != unknown_policy:
            errors.append(
                "dashboard.fail_closed_summary.unknown_incompatible_feature_policy mismatch artifact contract"
            )
        if fail_closed_summary.get("missing_artifact_link_policy") != missing_artifact_policy:
            errors.append("dashboard.fail_closed_summary.missing_artifact_link_policy mismatch artifact contract")
        triage_summary = ensure_dict(
            dashboard.get("triage_summary"),
            "dashboard.triage_summary",
            errors,
        )
        if triage_summary.get("bucket_count") != len(triage_taxonomy):
            errors.append("dashboard.triage_summary.bucket_count mismatch triage_taxonomy size")
        bucket_ids = triage_summary.get("bucket_ids")
        if isinstance(bucket_ids, list):
            observed_bucket_ids = sorted(bucket_id for bucket_id in bucket_ids if isinstance(bucket_id, str))
            if observed_bucket_ids != sorted(required_triage_buckets):
                errors.append("dashboard.triage_summary.bucket_ids mismatch required triage buckets")
        else:
            errors.append("dashboard.triage_summary.bucket_ids must be array")
        if triage_summary.get("primary_oncall_role") != playbook.get("primary_oncall_role"):
            errors.append("dashboard.triage_summary.primary_oncall_role mismatch operator_triage_playbook")
        artifact_health = ensure_dict(
            dashboard.get("artifact_health"),
            "dashboard.artifact_health",
            errors,
        )
        if artifact_health.get("artifact_index_count") != len(artifact_index):
            errors.append("dashboard.artifact_health.artifact_index_count mismatch artifact_index size")
        if artifact_health.get("missing_artifact_links") != 0:
            errors.append("dashboard.artifact_health.missing_artifact_links must equal 0")
        if artifact_health.get("audit_log_path") != fail_closed_audit_log_path:
            errors.append("dashboard.artifact_health.audit_log_path mismatch fail_closed audit log path")

    alien = ensure_dict(artifact.get("alien_uplift_contract_card"), "artifact.alien_uplift_contract_card", errors)
    require_keys(alien, schema["required_alien_contract_card_keys"], "artifact.alien_uplift_contract_card", errors)
    ev_score = alien.get("ev_score")
    if not isinstance(ev_score, (int, float)) or float(ev_score) < 2.0:
        errors.append("artifact.alien_uplift_contract_card.ev_score must be >= 2.0")

    profile = ensure_dict(artifact.get("profile_first_artifacts"), "artifact.profile_first_artifacts", errors)
    require_keys(profile, schema["required_profile_artifact_keys"], "artifact.profile_first_artifacts", errors)
    for key in schema["required_profile_artifact_keys"]:
        path_text = ensure_non_empty_string(profile.get(key), f"artifact.profile_first_artifacts.{key}", errors)
        ensure_existing_path(path_text, f"artifact.profile_first_artifacts.{key}", root, errors)

    optimization = ensure_dict(artifact.get("optimization_lever_policy"), "artifact.optimization_lever_policy", errors)
    require_keys(
        optimization,
        schema["required_optimization_policy_keys"],
        "artifact.optimization_lever_policy",
        errors,
    )
    optimization_evidence = ensure_non_empty_string(
        optimization.get("evidence_path"),
        "artifact.optimization_lever_policy.evidence_path",
        errors,
    )
    ensure_existing_path(
        optimization_evidence,
        "artifact.optimization_lever_policy.evidence_path",
        root,
        errors,
    )
    if optimization.get("max_levers_per_change") != 1:
        errors.append("artifact.optimization_lever_policy.max_levers_per_change must equal 1")

    parity = ensure_dict(artifact.get("drop_in_parity_contract"), "artifact.drop_in_parity_contract", errors)
    require_keys(parity, schema["required_drop_in_parity_keys"], "artifact.drop_in_parity_contract", errors)
    target = ensure_non_empty_string(
        parity.get("legacy_feature_overlap_target"),
        "artifact.drop_in_parity_contract.legacy_feature_overlap_target",
        errors,
    )
    if target and target != "100%":
        errors.append("artifact.drop_in_parity_contract.legacy_feature_overlap_target must be `100%`")
    gaps = ensure_list(
        parity.get("intentional_capability_gaps"),
        "artifact.drop_in_parity_contract.intentional_capability_gaps",
        errors,
    )
    if gaps:
        errors.append("artifact.drop_in_parity_contract.intentional_capability_gaps must be empty")

    runtime = ensure_dict(
        artifact.get("decision_theoretic_runtime_contract"),
        "artifact.decision_theoretic_runtime_contract",
        errors,
    )
    require_keys(
        runtime,
        schema["required_runtime_contract_keys"],
        "artifact.decision_theoretic_runtime_contract",
        errors,
    )

    states = ensure_string_list(runtime.get("states"), "artifact.decision_theoretic_runtime_contract.states", errors)
    actions = ensure_string_list(runtime.get("actions"), "artifact.decision_theoretic_runtime_contract.actions", errors)
    if not states:
        errors.append("artifact.decision_theoretic_runtime_contract.states must be non-empty")
    if not actions:
        errors.append("artifact.decision_theoretic_runtime_contract.actions must be non-empty")
    ensure_non_empty_string(runtime.get("loss_model"), "artifact.decision_theoretic_runtime_contract.loss_model", errors)
    ensure_non_empty_string(
        runtime.get("safe_mode_fallback"),
        "artifact.decision_theoretic_runtime_contract.safe_mode_fallback",
        errors,
    )

    safe_mode_budget = ensure_dict(
        runtime.get("safe_mode_budget"),
        "artifact.decision_theoretic_runtime_contract.safe_mode_budget",
        errors,
    )
    for key in [
        "max_failed_required_gates",
        "max_unmapped_high_risk_targets",
        "max_missing_artifact_links",
    ]:
        value = safe_mode_budget.get(key)
        if not isinstance(value, int) or value < 0:
            errors.append(
                f"artifact.decision_theoretic_runtime_contract.safe_mode_budget.{key} must be non-negative integer"
            )

    thresholds = ensure_list(
        runtime.get("trigger_thresholds"),
        "artifact.decision_theoretic_runtime_contract.trigger_thresholds",
        errors,
    )
    if not thresholds:
        errors.append("artifact.decision_theoretic_runtime_contract.trigger_thresholds must be non-empty")
    for idx, trigger in enumerate(thresholds):
        if not isinstance(trigger, dict):
            errors.append(
                f"artifact.decision_theoretic_runtime_contract.trigger_thresholds[{idx}] must be object"
            )
            continue
        require_keys(
            trigger,
            schema["required_runtime_trigger_keys"],
            f"artifact.decision_theoretic_runtime_contract.trigger_thresholds[{idx}]",
            errors,
        )
        threshold_value = trigger.get("threshold")
        if not isinstance(threshold_value, int) or threshold_value < 1:
            errors.append(
                f"artifact.decision_theoretic_runtime_contract.trigger_thresholds[{idx}].threshold must be integer >= 1"
            )

    iso_paths = ensure_string_list(
        artifact.get("isomorphism_proof_artifacts"),
        "artifact.isomorphism_proof_artifacts",
        errors,
    )
    for idx, path_text in enumerate(iso_paths):
        ensure_existing_path(path_text, f"artifact.isomorphism_proof_artifacts[{idx}]", root, errors)

    logging_paths = ensure_string_list(
        artifact.get("structured_logging_evidence"),
        "artifact.structured_logging_evidence",
        errors,
    )
    if len(logging_paths) < 3:
        errors.append("artifact.structured_logging_evidence should include log + replay + forensics evidence")
    for idx, path_text in enumerate(logging_paths):
        ensure_existing_path(path_text, f"artifact.structured_logging_evidence[{idx}]", root, errors)

    report = {
        "schema_version": "1.0.0",
        "report_id": "clean-safety-gate-pipeline-validation-v1",
        "artifact": args.artifact,
        "schema": args.schema,
        "ready": len(errors) == 0,
        "error_count": len(errors),
        "errors": errors,
        "summary": {
            "gate_count": len(gate_matrix),
            "high_risk_target_count": len(high_risk_coverage),
            "artifact_index_count": len(artifact_index),
            "triage_bucket_count": len(triage_taxonomy),
        },
    }

    output_path = root / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(report, indent=2))
    return 0 if report["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
