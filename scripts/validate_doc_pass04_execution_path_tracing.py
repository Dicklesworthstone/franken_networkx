#!/usr/bin/env python3
"""Validate DOC-PASS-04 execution-path tracing artifact."""

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


def ensure_path(path: str, ctx: str, errors: list[str]) -> None:
    if not isinstance(path, str) or not path:
        errors.append(f"{ctx} must be non-empty string path")
        return
    abs_path = REPO_ROOT / path
    if not abs_path.exists():
        errors.append(f"{ctx} path does not exist: {path}")


def ensure_non_empty_string(value: Any, ctx: str, errors: list[str]) -> None:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{ctx} must be non-empty string")


def validate_anchor(anchor: dict[str, Any], schema: dict[str, Any], ctx: str, errors: list[str]) -> None:
    ensure_keys(anchor, schema["required_anchor_keys"], ctx, errors)
    ensure_non_empty_string(anchor.get("crate_name"), f"{ctx}.crate_name", errors)
    ensure_non_empty_string(anchor.get("symbol"), f"{ctx}.symbol", errors)
    ensure_path(anchor.get("file_path", ""), f"{ctx}.file_path", errors)
    line_start = anchor.get("line_start")
    if not isinstance(line_start, int) or line_start < 1:
        errors.append(f"{ctx}.line_start must be integer >= 1")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--artifact",
        default="artifacts/docs/v1/doc_pass04_execution_path_tracing_v1.json",
        help="Path to DOC-PASS-04 artifact JSON",
    )
    parser.add_argument(
        "--schema",
        default="artifacts/docs/schema/v1/doc_pass04_execution_path_tracing_schema_v1.json",
        help="Path to DOC-PASS-04 schema JSON",
    )
    parser.add_argument("--output", default="", help="Optional validation report path")
    args = parser.parse_args()

    artifact = load_json(REPO_ROOT / args.artifact)
    schema = load_json(REPO_ROOT / args.schema)
    errors: list[str] = []

    ensure_keys(artifact, schema["required_top_level_keys"], "artifact", errors)

    summary = artifact.get("execution_summary")
    if isinstance(summary, dict):
        ensure_keys(summary, schema["required_summary_keys"], "execution_summary", errors)
    else:
        errors.append("execution_summary must be object")
        summary = {}

    execution_paths = artifact.get("execution_paths")
    if not isinstance(execution_paths, list) or not execution_paths:
        errors.append("execution_paths must be non-empty list")
        execution_paths = []

    path_ids: set[str] = set()
    branch_ids_by_path: dict[str, set[str]] = {}
    computed_branch_count = 0
    computed_fallback_count = 0
    computed_crates: set[str] = set()
    computed_beads: set[str] = set()

    for idx, path_row in enumerate(execution_paths):
        ctx = f"execution_paths[{idx}]"
        if not isinstance(path_row, dict):
            errors.append(f"{ctx} must be object")
            continue
        ensure_keys(path_row, schema["required_execution_path_keys"], ctx, errors)

        path_id = path_row.get("path_id")
        if not isinstance(path_id, str) or not path_id.strip():
            errors.append(f"{ctx}.path_id must be non-empty string")
            continue
        if path_id in path_ids:
            errors.append(f"duplicate execution path_id `{path_id}`")
        path_ids.add(path_id)

        ensure_non_empty_string(path_row.get("title"), f"{ctx}.title", errors)
        ensure_non_empty_string(path_row.get("subsystem_family"), f"{ctx}.subsystem_family", errors)
        ensure_non_empty_string(path_row.get("objective"), f"{ctx}.objective", errors)

        entrypoints = path_row.get("entrypoints")
        if not isinstance(entrypoints, list) or not entrypoints:
            errors.append(f"{ctx}.entrypoints must be non-empty list")
            entrypoints = []
        for entry_idx, entry in enumerate(entrypoints):
            entry_ctx = f"{ctx}.entrypoints[{entry_idx}]"
            if not isinstance(entry, dict):
                errors.append(f"{entry_ctx} must be object")
                continue
            validate_anchor(entry, schema, entry_ctx, errors)
            crate_name = entry.get("crate_name")
            if isinstance(crate_name, str) and crate_name.strip():
                computed_crates.add(crate_name)

        steps = path_row.get("primary_steps")
        if not isinstance(steps, list) or not steps:
            errors.append(f"{ctx}.primary_steps must be non-empty list")
            steps = []
        for step_idx, step in enumerate(steps):
            step_ctx = f"{ctx}.primary_steps[{step_idx}]"
            if not isinstance(step, dict):
                errors.append(f"{step_ctx} must be object")
                continue
            ensure_keys(step, schema["required_step_keys"], step_ctx, errors)
            ensure_non_empty_string(step.get("step_id"), f"{step_ctx}.step_id", errors)
            ensure_non_empty_string(step.get("description"), f"{step_ctx}.description", errors)
            code_anchor = step.get("code_anchor")
            if isinstance(code_anchor, dict):
                validate_anchor(code_anchor, schema, f"{step_ctx}.code_anchor", errors)
            else:
                errors.append(f"{step_ctx}.code_anchor must be object")
            output_artifacts = step.get("output_artifacts")
            if not isinstance(output_artifacts, list) or not output_artifacts:
                errors.append(f"{step_ctx}.output_artifacts must be non-empty list")
            else:
                for art_idx, art_path in enumerate(output_artifacts):
                    ensure_path(art_path, f"{step_ctx}.output_artifacts[{art_idx}]", errors)

        branches = path_row.get("branch_paths")
        if not isinstance(branches, list) or not branches:
            errors.append(f"{ctx}.branch_paths must be non-empty list")
            branches = []
        path_branch_ids: set[str] = set()
        for branch_idx, branch in enumerate(branches):
            branch_ctx = f"{ctx}.branch_paths[{branch_idx}]"
            if not isinstance(branch, dict):
                errors.append(f"{branch_ctx} must be object")
                continue
            ensure_keys(branch, schema["required_branch_keys"], branch_ctx, errors)
            branch_id = branch.get("branch_id")
            if not isinstance(branch_id, str) or not branch_id.strip():
                errors.append(f"{branch_ctx}.branch_id must be non-empty string")
            elif branch_id in path_branch_ids:
                errors.append(f"{ctx} duplicate branch_id `{branch_id}`")
            else:
                path_branch_ids.add(branch_id)
            for key in [
                "condition",
                "strict_behavior",
                "hardened_behavior",
                "fallback_behavior",
                "outcome",
            ]:
                ensure_non_empty_string(branch.get(key), f"{branch_ctx}.{key}", errors)
            code_anchor = branch.get("code_anchor")
            if isinstance(code_anchor, dict):
                validate_anchor(code_anchor, schema, f"{branch_ctx}.code_anchor", errors)
            else:
                errors.append(f"{branch_ctx}.code_anchor must be object")
            forensics_links = branch.get("forensics_links")
            if not isinstance(forensics_links, list) or not forensics_links:
                errors.append(f"{branch_ctx}.forensics_links must be non-empty list")
            else:
                for link_idx, link in enumerate(forensics_links):
                    ensure_path(link, f"{branch_ctx}.forensics_links[{link_idx}]", errors)
        branch_ids_by_path[path_id] = path_branch_ids
        computed_branch_count += len(path_branch_ids)

        fallbacks = path_row.get("fallback_paths")
        if not isinstance(fallbacks, list) or not fallbacks:
            errors.append(f"{ctx}.fallback_paths must be non-empty list")
            fallbacks = []
        for fallback_idx, fallback in enumerate(fallbacks):
            fallback_ctx = f"{ctx}.fallback_paths[{fallback_idx}]"
            if not isinstance(fallback, dict):
                errors.append(f"{fallback_ctx} must be object")
                continue
            ensure_keys(fallback, schema["required_fallback_keys"], fallback_ctx, errors)
            fallback_id = fallback.get("fallback_id")
            ensure_non_empty_string(fallback_id, f"{fallback_ctx}.fallback_id", errors)
            branch_id = fallback.get("branch_id")
            if branch_id not in path_branch_ids:
                errors.append(
                    f"{fallback_ctx}.branch_id must reference branch_paths in same path; got `{branch_id}`"
                )
            ensure_non_empty_string(fallback.get("trigger"), f"{fallback_ctx}.trigger", errors)
            ensure_non_empty_string(
                fallback.get("terminal_state"), f"{fallback_ctx}.terminal_state", errors
            )
            recovery_actions = fallback.get("recovery_actions")
            if not isinstance(recovery_actions, list) or not recovery_actions:
                errors.append(f"{fallback_ctx}.recovery_actions must be non-empty list")
            evidence_refs = fallback.get("evidence_refs")
            if not isinstance(evidence_refs, list) or not evidence_refs:
                errors.append(f"{fallback_ctx}.evidence_refs must be non-empty list")
            else:
                for evidence_idx, evidence in enumerate(evidence_refs):
                    ensure_path(evidence, f"{fallback_ctx}.evidence_refs[{evidence_idx}]", errors)
        computed_fallback_count += len(fallbacks)

        verification = path_row.get("verification_links")
        if isinstance(verification, dict):
            ensure_keys(
                verification,
                schema["required_verification_keys"],
                f"{ctx}.verification_links",
                errors,
            )
            for key in schema["required_verification_keys"]:
                values = verification.get(key)
                if not isinstance(values, list) or not values:
                    errors.append(f"{ctx}.verification_links.{key} must be non-empty list")
        else:
            errors.append(f"{ctx}.verification_links must be object")

        linked_beads = path_row.get("linked_bead_ids")
        if not isinstance(linked_beads, list) or not linked_beads:
            errors.append(f"{ctx}.linked_bead_ids must be non-empty list")
        else:
            for bead in linked_beads:
                ensure_non_empty_string(bead, f"{ctx}.linked_bead_ids entry", errors)
                if isinstance(bead, str) and bead.strip():
                    computed_beads.add(bead)

        replay_command = path_row.get("replay_command")
        if not isinstance(replay_command, str) or not replay_command.strip():
            errors.append(f"{ctx}.replay_command must be non-empty string")
        elif "rch exec --" not in replay_command:
            errors.append(f"{ctx}.replay_command must use rch offload")

        structured_refs = path_row.get("structured_log_refs")
        if not isinstance(structured_refs, list) or not structured_refs:
            errors.append(f"{ctx}.structured_log_refs must be non-empty list")
        else:
            for ref_idx, ref in enumerate(structured_refs):
                ensure_path(ref, f"{ctx}.structured_log_refs[{ref_idx}]", errors)

        risk_notes = path_row.get("risk_notes")
        if not isinstance(risk_notes, list) or not risk_notes:
            errors.append(f"{ctx}.risk_notes must be non-empty list")

    branch_catalog = artifact.get("branch_catalog")
    if not isinstance(branch_catalog, list) or not branch_catalog:
        errors.append("branch_catalog must be non-empty list")
        branch_catalog = []
    else:
        for idx, row in enumerate(branch_catalog):
            ctx = f"branch_catalog[{idx}]"
            if not isinstance(row, dict):
                errors.append(f"{ctx} must be object")
                continue
            ensure_keys(row, schema["required_branch_catalog_keys"], ctx, errors)
            path_id = row.get("path_id")
            branch_id = row.get("branch_id")
            if path_id not in path_ids:
                errors.append(f"{ctx}.path_id references unknown path `{path_id}`")
            elif branch_id not in branch_ids_by_path.get(path_id, set()):
                errors.append(
                    f"{ctx}.branch_id `{branch_id}` not present in execution_paths for `{path_id}`"
                )
            code_anchor = row.get("code_anchor")
            if isinstance(code_anchor, dict):
                validate_anchor(code_anchor, schema, f"{ctx}.code_anchor", errors)
            else:
                errors.append(f"{ctx}.code_anchor must be object")

    fallback_index = artifact.get("fallback_index")
    if not isinstance(fallback_index, list) or not fallback_index:
        errors.append("fallback_index must be non-empty list")
    else:
        for idx, row in enumerate(fallback_index):
            ctx = f"fallback_index[{idx}]"
            if not isinstance(row, dict):
                errors.append(f"{ctx} must be object")
                continue
            ensure_keys(row, schema["required_fallback_index_keys"], ctx, errors)
            path_id = row.get("path_id")
            branch_id = row.get("branch_id")
            if path_id not in path_ids:
                errors.append(f"{ctx}.path_id references unknown path `{path_id}`")
            elif branch_id not in branch_ids_by_path.get(path_id, set()):
                errors.append(
                    f"{ctx}.branch_id `{branch_id}` not present in execution_paths for `{path_id}`"
                )

    crosswalk = artifact.get("verification_bead_crosswalk")
    if not isinstance(crosswalk, list) or not crosswalk:
        errors.append("verification_bead_crosswalk must be non-empty list")
    else:
        for idx, row in enumerate(crosswalk):
            ctx = f"verification_bead_crosswalk[{idx}]"
            if not isinstance(row, dict):
                errors.append(f"{ctx} must be object")
                continue
            ensure_keys(row, schema["required_crosswalk_keys"], ctx, errors)
            bead_id = row.get("bead_id")
            ensure_non_empty_string(bead_id, f"{ctx}.bead_id", errors)
            path_refs = row.get("path_ids")
            if not isinstance(path_refs, list) or not path_refs:
                errors.append(f"{ctx}.path_ids must be non-empty list")
            else:
                for path_id in path_refs:
                    if path_id not in path_ids:
                        errors.append(f"{ctx}.path_ids references unknown path `{path_id}`")
            ensure_non_empty_string(row.get("status"), f"{ctx}.status", errors)
            ensure_non_empty_string(row.get("closure_signal"), f"{ctx}.closure_signal", errors)

    if isinstance(summary, dict):
        if summary.get("workflow_count") != len(path_ids):
            errors.append("execution_summary.workflow_count mismatch execution_paths count")
        if summary.get("branch_count") != computed_branch_count:
            errors.append("execution_summary.branch_count mismatch branch_paths count")
        if summary.get("fallback_count") != computed_fallback_count:
            errors.append("execution_summary.fallback_count mismatch fallback_paths count")
        if summary.get("workspace_crate_count") != len(computed_crates):
            errors.append("execution_summary.workspace_crate_count mismatch observed crates")
        if summary.get("verification_bead_count") != len(computed_beads):
            errors.append("execution_summary.verification_bead_count mismatch linked beads")

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

    iso_refs = artifact.get("isomorphism_proof_artifacts")
    if not isinstance(iso_refs, list) or not iso_refs:
        errors.append("isomorphism_proof_artifacts must be non-empty list")
        iso_refs = []
    for idx, path in enumerate(iso_refs):
        ensure_path(path, f"isomorphism_proof_artifacts[{idx}]", errors)

    log_refs = artifact.get("structured_logging_evidence")
    if not isinstance(log_refs, list) or not log_refs:
        errors.append("structured_logging_evidence must be non-empty list")
        log_refs = []
    for idx, path in enumerate(log_refs):
        ensure_path(path, f"structured_logging_evidence[{idx}]", errors)

    report = {
        "schema_version": "1.0.0",
        "report_id": "doc-pass-04-execution-path-tracing-validation-v1",
        "artifact_path": args.artifact,
        "ready": len(errors) == 0,
        "error_count": len(errors),
        "errors": errors,
        "summary": {
            "workflow_count": len(path_ids),
            "branch_count": computed_branch_count,
            "fallback_count": computed_fallback_count,
            "bead_count": len(computed_beads),
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
