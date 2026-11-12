#!/usr/bin/env python3
"""Validate DOC-PASS-05 complexity/performance/memory characterization artifact."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def ensure_keys(payload: dict[str, Any], keys: list[str], ctx: str, errors: list[str]) -> None:
    for key in keys:
        if key not in payload:
            errors.append(f"{ctx} missing key `{key}`")


def ensure_non_empty_string(value: Any, ctx: str, errors: list[str]) -> None:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{ctx} must be non-empty string")


def ensure_non_empty_list(value: Any, ctx: str, errors: list[str]) -> list[Any]:
    if not isinstance(value, list) or not value:
        errors.append(f"{ctx} must be non-empty list")
        return []
    return value


def ensure_path(path: str, ctx: str, errors: list[str]) -> None:
    if not isinstance(path, str) or not path:
        errors.append(f"{ctx} must be non-empty string path")
        return
    abs_path = REPO_ROOT / path
    if not abs_path.exists():
        errors.append(f"{ctx} path does not exist: {path}")


def validate_anchor(anchor_obj: dict[str, Any], schema: dict[str, Any], ctx: str, errors: list[str]) -> None:
    ensure_keys(anchor_obj, schema["required_anchor_keys"], ctx, errors)
    ensure_non_empty_string(anchor_obj.get("crate_name"), f"{ctx}.crate_name", errors)
    ensure_non_empty_string(anchor_obj.get("symbol"), f"{ctx}.symbol", errors)
    ensure_path(anchor_obj.get("file_path", ""), f"{ctx}.file_path", errors)
    line_start = anchor_obj.get("line_start")
    if not isinstance(line_start, int) or line_start < 1:
        errors.append(f"{ctx}.line_start must be integer >= 1")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--artifact",
        default="artifacts/docs/v1/doc_pass05_complexity_perf_memory_v1.json",
        help="Path to DOC-PASS-05 artifact JSON",
    )
    parser.add_argument(
        "--schema",
        default="artifacts/docs/schema/v1/doc_pass05_complexity_perf_memory_schema_v1.json",
        help="Path to DOC-PASS-05 schema JSON",
    )
    parser.add_argument("--output", default="", help="Optional validation report path")
    args = parser.parse_args()

    artifact = load_json(REPO_ROOT / args.artifact)
    schema = load_json(REPO_ROOT / args.schema)
    errors: list[str] = []

    ensure_keys(artifact, schema["required_top_level_keys"], "artifact", errors)

    summary = artifact.get("characterization_summary")
    if isinstance(summary, dict):
        ensure_keys(summary, schema["required_summary_keys"], "characterization_summary", errors)
    else:
        errors.append("characterization_summary must be object")
        summary = {}

    families = ensure_non_empty_list(artifact.get("operation_families"), "operation_families", errors)
    hotspot_hypotheses = ensure_non_empty_list(
        artifact.get("hotspot_hypotheses"), "hotspot_hypotheses", errors
    )
    risk_notes = ensure_non_empty_list(artifact.get("optimization_risk_notes"), "optimization_risk_notes", errors)
    crosswalk = ensure_non_empty_list(
        artifact.get("verification_bead_crosswalk"), "verification_bead_crosswalk", errors
    )

    family_ids: set[str] = set()
    operation_ids: set[str] = set()
    operation_to_risk_refs: dict[str, set[str]] = {}
    high_risk_operation_count = 0
    operation_count = 0

    for family_idx, family in enumerate(families):
        ctx = f"operation_families[{family_idx}]"
        if not isinstance(family, dict):
            errors.append(f"{ctx} must be object")
            continue
        ensure_keys(family, schema["required_family_keys"], ctx, errors)
        family_id = family.get("family_id")
        if not isinstance(family_id, str) or not family_id.strip():
            errors.append(f"{ctx}.family_id must be non-empty string")
            continue
        if family_id in family_ids:
            errors.append(f"duplicate family_id `{family_id}`")
        family_ids.add(family_id)

        ensure_non_empty_string(family.get("name"), f"{ctx}.name", errors)

        for path_idx, path in enumerate(
            ensure_non_empty_list(family.get("legacy_scope_paths"), f"{ctx}.legacy_scope_paths", errors)
        ):
            ensure_non_empty_string(path, f"{ctx}.legacy_scope_paths[{path_idx}]", errors)

        for crate_idx, crate_name in enumerate(
            ensure_non_empty_list(family.get("rust_crates"), f"{ctx}.rust_crates", errors)
        ):
            ensure_non_empty_string(crate_name, f"{ctx}.rust_crates[{crate_idx}]", errors)

        operations = ensure_non_empty_list(family.get("operations"), f"{ctx}.operations", errors)
        for op_idx, operation in enumerate(operations):
            op_ctx = f"{ctx}.operations[{op_idx}]"
            if not isinstance(operation, dict):
                errors.append(f"{op_ctx} must be object")
                continue
            ensure_keys(operation, schema["required_operation_keys"], op_ctx, errors)

            operation_id = operation.get("operation_id")
            if not isinstance(operation_id, str) or not operation_id.strip():
                errors.append(f"{op_ctx}.operation_id must be non-empty string")
                continue
            if operation_id in operation_ids:
                errors.append(f"duplicate operation_id `{operation_id}`")
            operation_ids.add(operation_id)

            ensure_non_empty_string(operation.get("symbol"), f"{op_ctx}.symbol", errors)

            anchor_obj = operation.get("code_anchor")
            if isinstance(anchor_obj, dict):
                validate_anchor(anchor_obj, schema, f"{op_ctx}.code_anchor", errors)
            else:
                errors.append(f"{op_ctx}.code_anchor must be object")

            complexity_time = operation.get("complexity_time")
            ensure_non_empty_string(complexity_time, f"{op_ctx}.complexity_time", errors)
            if isinstance(complexity_time, str) and not complexity_time.startswith("O("):
                errors.append(f"{op_ctx}.complexity_time must start with `O(`")

            complexity_space = operation.get("complexity_space")
            ensure_non_empty_string(complexity_space, f"{op_ctx}.complexity_space", errors)
            if isinstance(complexity_space, str) and not complexity_space.startswith("O("):
                errors.append(f"{op_ctx}.complexity_space must start with `O(`")

            ensure_non_empty_string(
                operation.get("memory_growth_driver"),
                f"{op_ctx}.memory_growth_driver",
                errors,
            )

            for signal_idx, signal_path in enumerate(
                ensure_non_empty_list(operation.get("hotspot_signals"), f"{op_ctx}.hotspot_signals", errors)
            ):
                ensure_path(signal_path, f"{op_ctx}.hotspot_signals[{signal_idx}]", errors)

            for parity_idx, parity_constraint in enumerate(
                ensure_non_empty_list(
                    operation.get("parity_constraints"), f"{op_ctx}.parity_constraints", errors
                )
            ):
                ensure_non_empty_string(parity_constraint, f"{op_ctx}.parity_constraints[{parity_idx}]", errors)

            hooks_obj = operation.get("validation_hooks")
            if isinstance(hooks_obj, dict):
                ensure_keys(
                    hooks_obj,
                    schema["required_validation_hook_keys"],
                    f"{op_ctx}.validation_hooks",
                    errors,
                )
                for hook_key in schema["required_validation_hook_keys"]:
                    for hook_idx, hook_ref in enumerate(
                        ensure_non_empty_list(
                            hooks_obj.get(hook_key),
                            f"{op_ctx}.validation_hooks.{hook_key}",
                            errors,
                        )
                    ):
                        ensure_non_empty_string(
                            hook_ref,
                            f"{op_ctx}.validation_hooks.{hook_key}[{hook_idx}]",
                            errors,
                        )
            else:
                errors.append(f"{op_ctx}.validation_hooks must be object")

            replay_command = operation.get("replay_command")
            ensure_non_empty_string(replay_command, f"{op_ctx}.replay_command", errors)
            if isinstance(replay_command, str) and "rch exec --" not in replay_command:
                errors.append(f"{op_ctx}.replay_command must use rch offload")

            risk_tier = operation.get("risk_tier")
            ensure_non_empty_string(risk_tier, f"{op_ctx}.risk_tier", errors)
            if isinstance(risk_tier, str):
                if risk_tier not in {"low", "medium", "high"}:
                    errors.append(f"{op_ctx}.risk_tier must be one of low|medium|high")
                if risk_tier == "high":
                    high_risk_operation_count += 1

            risk_refs = set()
            for risk_idx, risk_id in enumerate(
                ensure_non_empty_list(
                    operation.get("optimization_risk_note_ids"),
                    f"{op_ctx}.optimization_risk_note_ids",
                    errors,
                )
            ):
                ensure_non_empty_string(risk_id, f"{op_ctx}.optimization_risk_note_ids[{risk_idx}]", errors)
                if isinstance(risk_id, str) and risk_id.strip():
                    risk_refs.add(risk_id)
            operation_to_risk_refs[operation_id] = risk_refs
            operation_count += 1

    hotspot_ids: set[str] = set()
    for idx, hotspot in enumerate(hotspot_hypotheses):
        ctx = f"hotspot_hypotheses[{idx}]"
        if not isinstance(hotspot, dict):
            errors.append(f"{ctx} must be object")
            continue
        ensure_keys(hotspot, schema["required_hotspot_keys"], ctx, errors)

        hypothesis_id = hotspot.get("hypothesis_id")
        if not isinstance(hypothesis_id, str) or not hypothesis_id.strip():
            errors.append(f"{ctx}.hypothesis_id must be non-empty string")
        elif hypothesis_id in hotspot_ids:
            errors.append(f"duplicate hotspot hypothesis_id `{hypothesis_id}`")
        else:
            hotspot_ids.add(hypothesis_id)

        operation_id = hotspot.get("operation_id")
        if operation_id not in operation_ids:
            errors.append(f"{ctx}.operation_id references unknown operation `{operation_id}`")

        ensure_non_empty_string(hotspot.get("statement"), f"{ctx}.statement", errors)
        ensure_non_empty_string(hotspot.get("test_plan"), f"{ctx}.test_plan", errors)
        ensure_non_empty_string(hotspot.get("expected_signal"), f"{ctx}.expected_signal", errors)

        for evidence_idx, evidence_path in enumerate(
            ensure_non_empty_list(hotspot.get("evidence_refs"), f"{ctx}.evidence_refs", errors)
        ):
            ensure_path(evidence_path, f"{ctx}.evidence_refs[{evidence_idx}]", errors)

        for bead_idx, bead_id in enumerate(
            ensure_non_empty_list(hotspot.get("linked_bead_ids"), f"{ctx}.linked_bead_ids", errors)
        ):
            ensure_non_empty_string(bead_id, f"{ctx}.linked_bead_ids[{bead_idx}]", errors)

    risk_note_ids: set[str] = set()
    risk_note_operation_lookup: dict[str, str] = {}
    for idx, risk_note in enumerate(risk_notes):
        ctx = f"optimization_risk_notes[{idx}]"
        if not isinstance(risk_note, dict):
            errors.append(f"{ctx} must be object")
            continue
        ensure_keys(risk_note, schema["required_risk_note_keys"], ctx, errors)

        risk_note_id = risk_note.get("risk_note_id")
        if not isinstance(risk_note_id, str) or not risk_note_id.strip():
            errors.append(f"{ctx}.risk_note_id must be non-empty string")
            continue
        if risk_note_id in risk_note_ids:
            errors.append(f"duplicate risk_note_id `{risk_note_id}`")
            continue
        risk_note_ids.add(risk_note_id)

        operation_id = risk_note.get("operation_id")
        if operation_id not in operation_ids:
            errors.append(f"{ctx}.operation_id references unknown operation `{operation_id}`")
        else:
            risk_note_operation_lookup[risk_note_id] = operation_id

        ensure_non_empty_string(risk_note.get("parity_constraint"), f"{ctx}.parity_constraint", errors)
        ensure_non_empty_string(risk_note.get("risk_statement"), f"{ctx}.risk_statement", errors)
        ensure_non_empty_string(risk_note.get("rollback_trigger"), f"{ctx}.rollback_trigger", errors)

        for allow_idx, lever in enumerate(
            ensure_non_empty_list(
                risk_note.get("allowed_optimization_levers"),
                f"{ctx}.allowed_optimization_levers",
                errors,
            )
        ):
            ensure_non_empty_string(lever, f"{ctx}.allowed_optimization_levers[{allow_idx}]", errors)

        for forbid_idx, forbidden in enumerate(
            ensure_non_empty_list(
                risk_note.get("forbidden_changes"),
                f"{ctx}.forbidden_changes",
                errors,
            )
        ):
            ensure_non_empty_string(forbidden, f"{ctx}.forbidden_changes[{forbid_idx}]", errors)

        for verify_idx, verify in enumerate(
            ensure_non_empty_list(
                risk_note.get("verification_requirements"),
                f"{ctx}.verification_requirements",
                errors,
            )
        ):
            ensure_non_empty_string(verify, f"{ctx}.verification_requirements[{verify_idx}]", errors)

    for operation_id, risk_refs in operation_to_risk_refs.items():
        if not risk_refs:
            errors.append(f"operation `{operation_id}` has no optimization_risk_note_ids")
            continue
        for risk_ref in risk_refs:
            if risk_ref not in risk_note_ids:
                errors.append(
                    f"operation `{operation_id}` references missing risk note `{risk_ref}`"
                )
                continue
            mapped_operation = risk_note_operation_lookup.get(risk_ref)
            if mapped_operation and mapped_operation != operation_id:
                errors.append(
                    f"operation `{operation_id}` references risk note `{risk_ref}` owned by `{mapped_operation}`"
                )

    for idx, row in enumerate(crosswalk):
        ctx = f"verification_bead_crosswalk[{idx}]"
        if not isinstance(row, dict):
            errors.append(f"{ctx} must be object")
            continue
        ensure_keys(row, schema["required_crosswalk_keys"], ctx, errors)
        ensure_non_empty_string(row.get("bead_id"), f"{ctx}.bead_id", errors)
        ensure_non_empty_string(row.get("title"), f"{ctx}.title", errors)
        ensure_non_empty_string(row.get("status"), f"{ctx}.status", errors)
        ensure_non_empty_string(row.get("closure_signal"), f"{ctx}.closure_signal", errors)

        for op_idx, operation_id in enumerate(
            ensure_non_empty_list(row.get("linked_operation_ids"), f"{ctx}.linked_operation_ids", errors)
        ):
            if operation_id not in operation_ids:
                errors.append(
                    f"{ctx}.linked_operation_ids[{op_idx}] references unknown operation `{operation_id}`"
                )

    if isinstance(summary, dict):
        if summary.get("family_count") != len(family_ids):
            errors.append("characterization_summary.family_count mismatch")
        if summary.get("operation_count") != operation_count:
            errors.append("characterization_summary.operation_count mismatch")
        if summary.get("high_risk_operation_count") != high_risk_operation_count:
            errors.append("characterization_summary.high_risk_operation_count mismatch")
        if summary.get("hotspot_hypothesis_count") != len(hotspot_hypotheses):
            errors.append("characterization_summary.hotspot_hypothesis_count mismatch")
        if summary.get("optimization_risk_note_count") != len(risk_note_ids):
            errors.append("characterization_summary.optimization_risk_note_count mismatch")

    alien = artifact.get("alien_uplift_contract_card")
    if isinstance(alien, dict):
        ev_score = alien.get("ev_score")
        if not isinstance(ev_score, (int, float)) or float(ev_score) < 2.0:
            errors.append("alien_uplift_contract_card.ev_score must be >= 2.0")
        ensure_non_empty_string(
            alien.get("baseline_comparator"),
            "alien_uplift_contract_card.baseline_comparator",
            errors,
        )
    else:
        errors.append("alien_uplift_contract_card must be object")

    profile = artifact.get("profile_first_artifacts")
    if isinstance(profile, dict):
        ensure_keys(profile, ["baseline", "hotspot", "delta"], "profile_first_artifacts", errors)
        for key in ["baseline", "hotspot", "delta"]:
            ensure_path(profile.get(key, ""), f"profile_first_artifacts.{key}", errors)
    else:
        errors.append("profile_first_artifacts must be object")

    optimization = artifact.get("optimization_lever_policy")
    if isinstance(optimization, dict):
        if optimization.get("rule") != "exactly_one_optimization_lever_per_change":
            errors.append("optimization_lever_policy.rule mismatch expected one-lever policy")
        ensure_path(
            optimization.get("evidence_path", ""),
            "optimization_lever_policy.evidence_path",
            errors,
        )
    else:
        errors.append("optimization_lever_policy must be object")

    decision_contract = artifact.get("decision_theoretic_runtime_contract")
    if isinstance(decision_contract, dict):
        ensure_keys(
            decision_contract,
            schema["required_decision_contract_keys"],
            "decision_theoretic_runtime_contract",
            errors,
        )
        safe_mode = decision_contract.get("safe_mode_fallback")
        if isinstance(safe_mode, dict):
            thresholds = safe_mode.get("trigger_thresholds")
            if not isinstance(thresholds, dict) or not thresholds:
                errors.append(
                    "decision_theoretic_runtime_contract.safe_mode_fallback.trigger_thresholds must be non-empty object"
                )
        else:
            errors.append("decision_theoretic_runtime_contract.safe_mode_fallback must be object")
    else:
        errors.append("decision_theoretic_runtime_contract must be object")

    iso_refs = ensure_non_empty_list(
        artifact.get("isomorphism_proof_artifacts"),
        "isomorphism_proof_artifacts",
        errors,
    )
    for idx, path in enumerate(iso_refs):
        ensure_path(path, f"isomorphism_proof_artifacts[{idx}]", errors)

    log_refs = ensure_non_empty_list(
        artifact.get("structured_logging_evidence"),
        "structured_logging_evidence",
        errors,
    )
    for idx, path in enumerate(log_refs):
        ensure_path(path, f"structured_logging_evidence[{idx}]", errors)

    report = {
        "schema_version": "1.0.0",
        "report_id": "doc-pass-05-complexity-perf-memory-validation-v1",
        "artifact_path": args.artifact,
        "ready": len(errors) == 0,
        "error_count": len(errors),
        "errors": errors,
        "summary": {
            "family_count": len(family_ids),
            "operation_count": operation_count,
            "high_risk_operation_count": high_risk_operation_count,
            "hotspot_hypothesis_count": len(hotspot_hypotheses),
            "optimization_risk_note_count": len(risk_note_ids),
        },
    }

    if args.output:
        output_path = REPO_ROOT / args.output
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(report, indent=2))
    return 0 if report["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
