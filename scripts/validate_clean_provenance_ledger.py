#!/usr/bin/env python3
"""Validate clean-room provenance ledger artifacts."""

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


def ensure_existing_path(path_text: str, ctx: str, root: Path, errors: list[str]) -> None:
    if not path_text:
        return
    path = root / path_text
    if not path.exists():
        errors.append(f"{ctx} path does not exist: {path_text}")


def ensure_confidence(
    value: Any,
    ctx: str,
    min_value: float,
    max_value: float,
    errors: list[str],
) -> float:
    if not isinstance(value, (int, float)):
        errors.append(f"{ctx} must be numeric")
        return min_value
    score = float(value)
    if score < min_value or score > max_value:
        errors.append(f"{ctx}={score} outside range [{min_value}, {max_value}]")
    return score


def ensure_string_list(value: Any, ctx: str, errors: list[str]) -> list[str]:
    rows = ensure_list(value, ctx, errors)
    out: list[str] = []
    for idx, row in enumerate(rows):
        text = ensure_non_empty_string(row, f"{ctx}[{idx}]", errors)
        if text:
            out.append(text)
    return out


def validate_workflow(
    workflow: dict[str, Any],
    schema: dict[str, Any],
    errors: list[str],
) -> None:
    require_keys(workflow, schema["required_workflow_keys"], "separation_workflow", errors)

    stages = ensure_list(workflow.get("separation_stages"), "separation_workflow.separation_stages", errors)
    if not stages:
        errors.append("separation_workflow.separation_stages must be non-empty")
    for idx, stage in enumerate(stages):
        if not isinstance(stage, dict):
            errors.append(f"separation_workflow.separation_stages[{idx}] must be object")
            continue
        require_keys(
            stage,
            schema["required_stage_keys"],
            f"separation_workflow.separation_stages[{idx}]",
            errors,
        )
        ensure_non_empty_string(stage.get("stage_id"), f"separation_workflow.separation_stages[{idx}].stage_id", errors)
        ensure_non_empty_string(stage.get("name"), f"separation_workflow.separation_stages[{idx}].name", errors)
        ensure_non_empty_string(stage.get("owner_role"), f"separation_workflow.separation_stages[{idx}].owner_role", errors)
        inputs = ensure_string_list(stage.get("inputs"), f"separation_workflow.separation_stages[{idx}].inputs", errors)
        outputs = ensure_string_list(stage.get("outputs"), f"separation_workflow.separation_stages[{idx}].outputs", errors)
        must_not_modify = ensure_string_list(
            stage.get("must_not_modify"),
            f"separation_workflow.separation_stages[{idx}].must_not_modify",
            errors,
        )
        if not inputs:
            errors.append(f"separation_workflow.separation_stages[{idx}] must list at least one input")
        if not outputs:
            errors.append(f"separation_workflow.separation_stages[{idx}] must list at least one output")
        if not must_not_modify:
            errors.append(f"separation_workflow.separation_stages[{idx}] must list must_not_modify patterns")

    controls = ensure_list(workflow.get("handoff_controls"), "separation_workflow.handoff_controls", errors)
    if not controls:
        errors.append("separation_workflow.handoff_controls must be non-empty")
    for idx, control in enumerate(controls):
        if not isinstance(control, dict):
            errors.append(f"separation_workflow.handoff_controls[{idx}] must be object")
            continue
        require_keys(
            control,
            schema["required_handoff_control_keys"],
            f"separation_workflow.handoff_controls[{idx}]",
            errors,
        )


def validate_record(
    record: dict[str, Any],
    idx: int,
    schema: dict[str, Any],
    root: Path,
    errors: list[str],
    seen_record_ids: set[str],
    previous_record_ids: set[str],
    ambiguity_refs_by_record: dict[str, set[str]],
) -> tuple[str, str]:
    require_keys(record, schema["required_record_keys"], f"provenance_records[{idx}]", errors)

    record_id = ensure_non_empty_string(record.get("record_id"), f"provenance_records[{idx}].record_id", errors)
    if record_id and record_id in seen_record_ids:
        errors.append(f"duplicate record_id `{record_id}`")
    if record_id:
        seen_record_ids.add(record_id)

    packet_id = ensure_non_empty_string(record.get("packet_id"), f"provenance_records[{idx}].packet_id", errors)

    lineage_family = ensure_non_empty_string(
        record.get("lineage_family"),
        f"provenance_records[{idx}].lineage_family",
        errors,
    )
    if lineage_family and lineage_family not in schema["allowed_lineage_families"]:
        errors.append(
            f"provenance_records[{idx}].lineage_family `{lineage_family}` outside allowed families"
        )

    anchor = ensure_dict(record.get("legacy_source_anchor"), f"provenance_records[{idx}].legacy_source_anchor", errors)
    require_keys(anchor, schema["required_anchor_keys"], f"provenance_records[{idx}].legacy_source_anchor", errors)
    anchor_path = ensure_non_empty_string(
        anchor.get("path"),
        f"provenance_records[{idx}].legacy_source_anchor.path",
        errors,
    )
    ensure_existing_path(anchor_path, f"provenance_records[{idx}].legacy_source_anchor.path", root, errors)
    ensure_non_empty_string(anchor.get("lines"), f"provenance_records[{idx}].legacy_source_anchor.lines", errors)
    symbols = ensure_string_list(
        anchor.get("symbols"),
        f"provenance_records[{idx}].legacy_source_anchor.symbols",
        errors,
    )
    if not symbols:
        errors.append(f"provenance_records[{idx}].legacy_source_anchor.symbols must be non-empty")

    ensure_non_empty_string(
        record.get("extracted_behavior_claim"),
        f"provenance_records[{idx}].extracted_behavior_claim",
        errors,
    )

    impl_refs = ensure_list(
        record.get("implementation_artifact_refs"),
        f"provenance_records[{idx}].implementation_artifact_refs",
        errors,
    )
    if not impl_refs:
        errors.append(f"provenance_records[{idx}].implementation_artifact_refs must be non-empty")
    for impl_idx, impl_row in enumerate(impl_refs):
        if not isinstance(impl_row, dict):
            errors.append(
                f"provenance_records[{idx}].implementation_artifact_refs[{impl_idx}] must be object"
            )
            continue
        require_keys(
            impl_row,
            schema["required_implementation_ref_keys"],
            f"provenance_records[{idx}].implementation_artifact_refs[{impl_idx}]",
            errors,
        )
        impl_path = ensure_non_empty_string(
            impl_row.get("path"),
            f"provenance_records[{idx}].implementation_artifact_refs[{impl_idx}].path",
            errors,
        )
        ensure_existing_path(
            impl_path,
            f"provenance_records[{idx}].implementation_artifact_refs[{impl_idx}].path",
            root,
            errors,
        )
        ensure_non_empty_string(
            impl_row.get("symbol"),
            f"provenance_records[{idx}].implementation_artifact_refs[{impl_idx}].symbol",
            errors,
        )
        ensure_non_empty_string(
            impl_row.get("change_type"),
            f"provenance_records[{idx}].implementation_artifact_refs[{impl_idx}].change_type",
            errors,
        )

    conformance_refs = ensure_string_list(
        record.get("conformance_evidence_refs"),
        f"provenance_records[{idx}].conformance_evidence_refs",
        errors,
    )
    if not conformance_refs:
        errors.append(f"provenance_records[{idx}].conformance_evidence_refs must be non-empty")
    for ref_idx, ref_path in enumerate(conformance_refs):
        ensure_existing_path(
            ref_path,
            f"provenance_records[{idx}].conformance_evidence_refs[{ref_idx}]",
            root,
            errors,
        )

    boundary = ensure_dict(record.get("handoff_boundary"), f"provenance_records[{idx}].handoff_boundary", errors)
    require_keys(
        boundary,
        schema["required_handoff_boundary_keys"],
        f"provenance_records[{idx}].handoff_boundary",
        errors,
    )
    ensure_non_empty_string(boundary.get("extractor_role"), f"provenance_records[{idx}].handoff_boundary.extractor_role", errors)
    ensure_non_empty_string(boundary.get("implementer_role"), f"provenance_records[{idx}].handoff_boundary.implementer_role", errors)
    handoff_path = ensure_non_empty_string(
        boundary.get("handoff_artifact"),
        f"provenance_records[{idx}].handoff_boundary.handoff_artifact",
        errors,
    )
    ensure_existing_path(handoff_path, f"provenance_records[{idx}].handoff_boundary.handoff_artifact", root, errors)
    ensure_non_empty_string(boundary.get("handoff_ts_utc"), f"provenance_records[{idx}].handoff_boundary.handoff_ts_utc", errors)

    signoff = ensure_dict(record.get("reviewer_signoff"), f"provenance_records[{idx}].reviewer_signoff", errors)
    require_keys(signoff, schema["required_signoff_keys"], f"provenance_records[{idx}].reviewer_signoff", errors)
    ensure_non_empty_string(signoff.get("reviewer"), f"provenance_records[{idx}].reviewer_signoff.reviewer", errors)
    ensure_non_empty_string(signoff.get("signoff_ts_utc"), f"provenance_records[{idx}].reviewer_signoff.signoff_ts_utc", errors)
    status = ensure_non_empty_string(signoff.get("status"), f"provenance_records[{idx}].reviewer_signoff.status", errors)
    if status and status not in schema["allowed_signoff_status"]:
        errors.append(
            f"provenance_records[{idx}].reviewer_signoff.status `{status}` not in allowed statuses"
        )
    ensure_non_empty_string(signoff.get("notes"), f"provenance_records[{idx}].reviewer_signoff.notes", errors)

    ambiguity_refs = set(
        ensure_string_list(
            record.get("ambiguity_ref_ids"),
            f"provenance_records[{idx}].ambiguity_ref_ids",
            errors,
        )
    )
    if record_id:
        ambiguity_refs_by_record[record_id] = ambiguity_refs

    ensure_confidence(
        record.get("confidence_rating"),
        f"provenance_records[{idx}].confidence_rating",
        schema["confidence_range"]["min"],
        schema["confidence_range"]["max"],
        errors,
    )

    prev_record_id = record.get("lineage_prev_record_id")
    if prev_record_id is not None:
        prev_record_text = ensure_non_empty_string(
            prev_record_id,
            f"provenance_records[{idx}].lineage_prev_record_id",
            errors,
        )
        if prev_record_text and prev_record_text not in previous_record_ids:
            errors.append(
                f"provenance_records[{idx}].lineage_prev_record_id `{prev_record_text}` must reference a previously declared record"
            )

    return packet_id, lineage_family


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--artifact",
        default="artifacts/clean/v1/clean_provenance_ledger_v1.json",
        help="Path to clean provenance ledger artifact JSON",
    )
    parser.add_argument(
        "--schema",
        default="artifacts/clean/schema/v1/clean_provenance_ledger_schema_v1.json",
        help="Path to clean provenance schema JSON",
    )
    parser.add_argument(
        "--output",
        default="artifacts/clean/latest/clean_provenance_validation_v1.json",
        help="Output validation report path",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    artifact_path = root / args.artifact
    schema_path = root / args.schema

    artifact = load_json(artifact_path)
    schema = load_json(schema_path)

    errors: list[str] = []
    require_keys(artifact, schema["required_top_level_keys"], "artifact", errors)

    workflow = ensure_dict(artifact.get("separation_workflow"), "artifact.separation_workflow", errors)
    validate_workflow(workflow, schema, errors)

    records = ensure_list(artifact.get("provenance_records"), "artifact.provenance_records", errors)
    if len(records) < len(schema["allowed_lineage_families"]):
        errors.append("artifact.provenance_records should include at least one record per lineage family")

    seen_record_ids: set[str] = set()
    previous_record_ids: set[str] = set()
    packet_ids: set[str] = set()
    observed_families: set[str] = set()
    ambiguity_refs_by_record: dict[str, set[str]] = {}

    for idx, record in enumerate(records):
        if not isinstance(record, dict):
            errors.append(f"artifact.provenance_records[{idx}] must be object")
            continue

        packet_id, lineage_family = validate_record(
            record,
            idx,
            schema,
            root,
            errors,
            seen_record_ids,
            previous_record_ids,
            ambiguity_refs_by_record,
        )
        record_id = record.get("record_id")
        if isinstance(record_id, str):
            previous_record_ids.add(record_id)
        if packet_id:
            if packet_id in packet_ids:
                errors.append(f"duplicate packet_id `{packet_id}`")
            packet_ids.add(packet_id)
        if lineage_family:
            observed_families.add(lineage_family)

    expected_families = set(schema["allowed_lineage_families"])
    if observed_families != expected_families:
        missing = sorted(expected_families - observed_families)
        extra = sorted(observed_families - expected_families)
        if missing:
            errors.append(f"missing lineage families in records: {', '.join(missing)}")
        if extra:
            errors.append(f"unexpected lineage families in records: {', '.join(extra)}")

    decisions = ensure_list(artifact.get("ambiguity_decisions"), "artifact.ambiguity_decisions", errors)
    decision_ids: set[str] = set()
    record_ids_in_decisions: set[str] = set()
    for idx, decision in enumerate(decisions):
        if not isinstance(decision, dict):
            errors.append(f"artifact.ambiguity_decisions[{idx}] must be object")
            continue
        require_keys(
            decision,
            schema["required_ambiguity_decision_keys"],
            f"artifact.ambiguity_decisions[{idx}]",
            errors,
        )
        decision_id = ensure_non_empty_string(
            decision.get("decision_id"),
            f"artifact.ambiguity_decisions[{idx}].decision_id",
            errors,
        )
        if decision_id:
            if decision_id in decision_ids:
                errors.append(f"duplicate ambiguity decision_id `{decision_id}`")
            decision_ids.add(decision_id)

        record_id = ensure_non_empty_string(
            decision.get("record_id"),
            f"artifact.ambiguity_decisions[{idx}].record_id",
            errors,
        )
        if record_id:
            record_ids_in_decisions.add(record_id)
            if record_id not in seen_record_ids:
                errors.append(
                    f"artifact.ambiguity_decisions[{idx}].record_id `{record_id}` not found in provenance records"
                )

        ensure_non_empty_string(
            decision.get("ambiguity_topic"),
            f"artifact.ambiguity_decisions[{idx}].ambiguity_topic",
            errors,
        )
        ensure_non_empty_string(
            decision.get("selected_policy"),
            f"artifact.ambiguity_decisions[{idx}].selected_policy",
            errors,
        )
        ensure_confidence(
            decision.get("confidence_rating"),
            f"artifact.ambiguity_decisions[{idx}].confidence_rating",
            schema["confidence_range"]["min"],
            schema["confidence_range"]["max"],
            errors,
        )
        ensure_non_empty_string(
            decision.get("rationale"),
            f"artifact.ambiguity_decisions[{idx}].rationale",
            errors,
        )

    for record_id, ref_ids in ambiguity_refs_by_record.items():
        for decision_id in ref_ids:
            if decision_id not in decision_ids:
                errors.append(
                    f"provenance record `{record_id}` references unknown ambiguity decision `{decision_id}`"
                )

    for decision in decisions:
        if not isinstance(decision, dict):
            continue
        decision_id = decision.get("decision_id")
        record_id = decision.get("record_id")
        if isinstance(decision_id, str) and isinstance(record_id, str):
            refs = ambiguity_refs_by_record.get(record_id, set())
            if decision_id not in refs:
                errors.append(
                    f"ambiguity decision `{decision_id}` for record `{record_id}` is not referenced by that record's ambiguity_ref_ids"
                )

    queries = ensure_list(artifact.get("audit_query_index"), "artifact.audit_query_index", errors)
    query_ids: set[str] = set()
    for idx, query in enumerate(queries):
        if not isinstance(query, dict):
            errors.append(f"artifact.audit_query_index[{idx}] must be object")
            continue
        require_keys(query, schema["required_audit_query_keys"], f"artifact.audit_query_index[{idx}]", errors)

        query_id = ensure_non_empty_string(query.get("query_id"), f"artifact.audit_query_index[{idx}].query_id", errors)
        if query_id:
            if query_id in query_ids:
                errors.append(f"duplicate audit query_id `{query_id}`")
            query_ids.add(query_id)

        ensure_non_empty_string(query.get("question"), f"artifact.audit_query_index[{idx}].question", errors)

        record_path = ensure_string_list(
            query.get("record_path"),
            f"artifact.audit_query_index[{idx}].record_path",
            errors,
        )
        if not record_path:
            errors.append(f"artifact.audit_query_index[{idx}].record_path must be non-empty")
        for rid in record_path:
            if rid not in seen_record_ids:
                errors.append(
                    f"artifact.audit_query_index[{idx}] references unknown record id `{rid}`"
                )

        expected_fields = ensure_string_list(
            query.get("expected_end_to_end_fields"),
            f"artifact.audit_query_index[{idx}].expected_end_to_end_fields",
            errors,
        )
        if sorted(expected_fields) != sorted(schema["required_audit_fields"]):
            errors.append(
                f"artifact.audit_query_index[{idx}].expected_end_to_end_fields must match schema.required_audit_fields"
            )

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
    require_keys(optimization, schema["required_optimization_policy_keys"], "artifact.optimization_lever_policy", errors)
    ensure_non_empty_string(optimization.get("policy"), "artifact.optimization_lever_policy.policy", errors)
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
    max_levers = optimization.get("max_levers_per_change")
    if not isinstance(max_levers, int) or max_levers != 1:
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
    ensure_non_empty_string(
        parity.get("contract_statement"),
        "artifact.drop_in_parity_contract.contract_statement",
        errors,
    )

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
    runtime_states = ensure_string_list(runtime.get("states"), "artifact.decision_theoretic_runtime_contract.states", errors)
    runtime_actions = ensure_string_list(runtime.get("actions"), "artifact.decision_theoretic_runtime_contract.actions", errors)
    if not runtime_states:
        errors.append("artifact.decision_theoretic_runtime_contract.states must be non-empty")
    if not runtime_actions:
        errors.append("artifact.decision_theoretic_runtime_contract.actions must be non-empty")
    ensure_non_empty_string(runtime.get("loss_model"), "artifact.decision_theoretic_runtime_contract.loss_model", errors)
    ensure_non_empty_string(runtime.get("safe_mode_fallback"), "artifact.decision_theoretic_runtime_contract.safe_mode_fallback", errors)

    safe_mode_budget = ensure_dict(
        runtime.get("safe_mode_budget"),
        "artifact.decision_theoretic_runtime_contract.safe_mode_budget",
        errors,
    )
    for key in [
        "max_blocked_promotions_per_run",
        "max_unsigned_records_before_halt",
        "max_unresolved_ambiguities_before_halt",
    ]:
        value = safe_mode_budget.get(key)
        if not isinstance(value, int) or value < 0:
            errors.append(
                f"artifact.decision_theoretic_runtime_contract.safe_mode_budget.{key} must be a non-negative integer"
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
        ensure_non_empty_string(
            trigger.get("trigger_id"),
            f"artifact.decision_theoretic_runtime_contract.trigger_thresholds[{idx}].trigger_id",
            errors,
        )
        ensure_non_empty_string(
            trigger.get("condition"),
            f"artifact.decision_theoretic_runtime_contract.trigger_thresholds[{idx}].condition",
            errors,
        )
        threshold_value = trigger.get("threshold")
        if not isinstance(threshold_value, int) or threshold_value < 1:
            errors.append(
                f"artifact.decision_theoretic_runtime_contract.trigger_thresholds[{idx}].threshold must be integer >= 1"
            )
        ensure_non_empty_string(
            trigger.get("fallback_action"),
            f"artifact.decision_theoretic_runtime_contract.trigger_thresholds[{idx}].fallback_action",
            errors,
        )

    for idx, path_text in enumerate(
        ensure_string_list(
            artifact.get("isomorphism_proof_artifacts"),
            "artifact.isomorphism_proof_artifacts",
            errors,
        )
    ):
        ensure_existing_path(path_text, f"artifact.isomorphism_proof_artifacts[{idx}]", root, errors)

    logging_evidence = ensure_string_list(
        artifact.get("structured_logging_evidence"),
        "artifact.structured_logging_evidence",
        errors,
    )
    if len(logging_evidence) < 3:
        errors.append("artifact.structured_logging_evidence should include logs + replay + forensics artifacts")
    for idx, path_text in enumerate(logging_evidence):
        ensure_existing_path(path_text, f"artifact.structured_logging_evidence[{idx}]", root, errors)

    report = {
        "schema_version": "1.0.0",
        "report_id": "clean-provenance-ledger-validation-v1",
        "artifact": args.artifact,
        "schema": args.schema,
        "ready": len(errors) == 0,
        "error_count": len(errors),
        "errors": errors,
        "summary": {
            "record_count": len(records),
            "lineage_family_count": len(observed_families),
            "ambiguity_count": len(decisions),
            "audit_query_count": len(queries),
        },
    }

    output_path = root / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(report, indent=2))
    return 0 if report["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
