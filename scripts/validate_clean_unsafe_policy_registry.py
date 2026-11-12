#!/usr/bin/env python3
"""Validate clean unsafe policy + exception registry artifacts."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
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
    if not (root / path_text).exists():
        errors.append(f"{ctx} path does not exist: {path_text}")


def parse_ts(value: str, ctx: str, errors: list[str]) -> datetime | None:
    text = ensure_non_empty_string(value, ctx, errors)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        errors.append(f"{ctx} must be ISO-8601 timestamp")
        return None


def ensure_string_list(value: Any, ctx: str, errors: list[str]) -> list[str]:
    rows = ensure_list(value, ctx, errors)
    out: list[str] = []
    for idx, row in enumerate(rows):
        text = ensure_non_empty_string(row, f"{ctx}[{idx}]", errors)
        if text:
            out.append(text)
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--artifact",
        default="artifacts/clean/v1/clean_unsafe_exception_registry_v1.json",
        help="Path to unsafe policy artifact",
    )
    parser.add_argument(
        "--schema",
        default="artifacts/clean/schema/v1/clean_unsafe_exception_registry_schema_v1.json",
        help="Path to unsafe policy schema",
    )
    parser.add_argument(
        "--output",
        default="artifacts/clean/latest/clean_unsafe_policy_validation_v1.json",
        help="Output validation report path",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    artifact = load_json(root / args.artifact)
    schema = load_json(root / args.schema)

    errors: list[str] = []
    require_keys(artifact, schema["required_top_level_keys"], "artifact", errors)

    policy_defaults = ensure_dict(artifact.get("policy_defaults"), "artifact.policy_defaults", errors)
    require_keys(
        policy_defaults,
        schema["required_policy_default_keys"],
        "artifact.policy_defaults",
        errors,
    )
    unknown_behavior = ensure_non_empty_string(
        policy_defaults.get("unknown_unsafe_behavior"),
        "artifact.policy_defaults.unknown_unsafe_behavior",
        errors,
    )
    if unknown_behavior and unknown_behavior != "fail_closed":
        errors.append("artifact.policy_defaults.unknown_unsafe_behavior must equal `fail_closed`")

    snapshot = ensure_dict(artifact.get("coverage_snapshot"), "artifact.coverage_snapshot", errors)
    require_keys(
        snapshot,
        schema["required_coverage_snapshot_keys"],
        "artifact.coverage_snapshot",
        errors,
    )

    workspace_crates = ensure_string_list(
        snapshot.get("workspace_crates"),
        "artifact.coverage_snapshot.workspace_crates",
        errors,
    )
    if not workspace_crates:
        errors.append("artifact.coverage_snapshot.workspace_crates must be non-empty")
    for idx, crate_path in enumerate(workspace_crates):
        ensure_existing_path(crate_path, f"artifact.coverage_snapshot.workspace_crates[{idx}]", root, errors)

    forbid_missing = ensure_string_list(
        snapshot.get("forbid_unsafe_missing"),
        "artifact.coverage_snapshot.forbid_unsafe_missing",
        errors,
    )
    for idx, path_text in enumerate(forbid_missing):
        ensure_existing_path(
            path_text,
            f"artifact.coverage_snapshot.forbid_unsafe_missing[{idx}]",
            root,
            errors,
        )

    unsafe_findings = ensure_list(
        snapshot.get("unsafe_findings"),
        "artifact.coverage_snapshot.unsafe_findings",
        errors,
    )
    finding_keys = {"path", "line", "snippet"}
    findings_by_path: dict[str, list[int]] = {}
    for idx, finding in enumerate(unsafe_findings):
        if not isinstance(finding, dict):
            errors.append(f"artifact.coverage_snapshot.unsafe_findings[{idx}] must be object")
            continue
        missing_keys = sorted(finding_keys - set(finding.keys()))
        if missing_keys:
            errors.append(
                f"artifact.coverage_snapshot.unsafe_findings[{idx}] missing keys: {', '.join(missing_keys)}"
            )
        path_text = ensure_non_empty_string(
            finding.get("path"),
            f"artifact.coverage_snapshot.unsafe_findings[{idx}].path",
            errors,
        )
        ensure_existing_path(
            path_text,
            f"artifact.coverage_snapshot.unsafe_findings[{idx}].path",
            root,
            errors,
        )
        line = finding.get("line")
        if not isinstance(line, int) or line < 1:
            errors.append(
                f"artifact.coverage_snapshot.unsafe_findings[{idx}].line must be integer >= 1"
            )
        else:
            findings_by_path.setdefault(path_text, []).append(line)
        ensure_non_empty_string(
            finding.get("snippet"),
            f"artifact.coverage_snapshot.unsafe_findings[{idx}].snippet",
            errors,
        )

    exceptions = ensure_list(artifact.get("exception_registry"), "artifact.exception_registry", errors)
    allowed_status = set(schema["allowed_exception_status"])
    approved_exceptions_by_path: dict[str, list[dict[str, Any]]] = {}
    now = datetime.now(timezone.utc)

    for idx, exception in enumerate(exceptions):
        if not isinstance(exception, dict):
            errors.append(f"artifact.exception_registry[{idx}] must be object")
            continue
        require_keys(
            exception,
            schema["required_exception_entry_keys"],
            f"artifact.exception_registry[{idx}]",
            errors,
        )
        exception_id = ensure_non_empty_string(
            exception.get("exception_id"),
            f"artifact.exception_registry[{idx}].exception_id",
            errors,
        )
        _ = exception_id
        crate_name = ensure_non_empty_string(
            exception.get("crate"),
            f"artifact.exception_registry[{idx}].crate",
            errors,
        )
        _ = crate_name
        path_text = ensure_non_empty_string(
            exception.get("path"),
            f"artifact.exception_registry[{idx}].path",
            errors,
        )
        ensure_existing_path(path_text, f"artifact.exception_registry[{idx}].path", root, errors)
        ensure_non_empty_string(
            exception.get("symbol"),
            f"artifact.exception_registry[{idx}].symbol",
            errors,
        )
        ensure_non_empty_string(
            exception.get("rationale"),
            f"artifact.exception_registry[{idx}].rationale",
            errors,
        )
        ensure_non_empty_string(
            exception.get("owner"),
            f"artifact.exception_registry[{idx}].owner",
            errors,
        )
        parse_ts(
            exception.get("created_at_utc"),
            f"artifact.exception_registry[{idx}].created_at_utc",
            errors,
        )
        review_every_days = exception.get("review_every_days")
        if not isinstance(review_every_days, int) or review_every_days < 1:
            errors.append(
                f"artifact.exception_registry[{idx}].review_every_days must be integer >= 1"
            )
        expires_at = parse_ts(
            exception.get("expires_at_utc"),
            f"artifact.exception_registry[{idx}].expires_at_utc",
            errors,
        )
        ensure_non_empty_string(
            exception.get("mitigation_plan"),
            f"artifact.exception_registry[{idx}].mitigation_plan",
            errors,
        )
        ensure_non_empty_string(
            exception.get("threat_note"),
            f"artifact.exception_registry[{idx}].threat_note",
            errors,
        )
        tests = ensure_string_list(
            exception.get("tests"),
            f"artifact.exception_registry[{idx}].tests",
            errors,
        )
        for test_idx, test_path in enumerate(tests):
            ensure_existing_path(
                test_path,
                f"artifact.exception_registry[{idx}].tests[{test_idx}]",
                root,
                errors,
            )
        status = ensure_non_empty_string(
            exception.get("status"),
            f"artifact.exception_registry[{idx}].status",
            errors,
        )
        if status and status not in allowed_status:
            errors.append(
                f"artifact.exception_registry[{idx}].status `{status}` not in allowed statuses"
            )

        if status == "approved":
            if expires_at is None:
                errors.append(
                    f"artifact.exception_registry[{idx}] approved status requires valid expires_at_utc"
                )
            elif expires_at <= now:
                errors.append(
                    f"artifact.exception_registry[{idx}] approved status cannot be expired"
                )
            if not tests:
                errors.append(
                    f"artifact.exception_registry[{idx}] approved status requires non-empty tests"
                )
            approved_exceptions_by_path.setdefault(path_text, []).append(exception)

    if forbid_missing:
        errors.append("artifact.coverage_snapshot.forbid_unsafe_missing must be empty")

    if unsafe_findings:
        for path_text, _lines in findings_by_path.items():
            if path_text not in approved_exceptions_by_path:
                errors.append(
                    f"unsafe finding path `{path_text}` has no approved exception mapping"
                )

    fail_closed_controls = ensure_list(
        artifact.get("fail_closed_controls"),
        "artifact.fail_closed_controls",
        errors,
    )
    if not fail_closed_controls:
        errors.append("artifact.fail_closed_controls must be non-empty")
    for idx, control in enumerate(fail_closed_controls):
        if not isinstance(control, dict):
            errors.append(f"artifact.fail_closed_controls[{idx}] must be object")
            continue
        require_keys(
            control,
            schema["required_fail_closed_control_keys"],
            f"artifact.fail_closed_controls[{idx}]",
            errors,
        )

    audit = ensure_dict(artifact.get("audit_enforcement"), "artifact.audit_enforcement", errors)
    require_keys(audit, schema["required_audit_enforcement_keys"], "artifact.audit_enforcement", errors)
    for key in schema["required_audit_enforcement_keys"]:
        ensure_non_empty_string(audit.get(key), f"artifact.audit_enforcement.{key}", errors)

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
        "max_unmapped_unsafe_findings",
        "max_expired_approved_exceptions",
        "max_missing_forbid_crates",
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
        "report_id": "clean-unsafe-policy-validation-v1",
        "artifact": args.artifact,
        "schema": args.schema,
        "ready": len(errors) == 0,
        "error_count": len(errors),
        "errors": errors,
        "summary": {
            "workspace_crate_count": len(workspace_crates),
            "forbid_missing_count": len(forbid_missing),
            "unsafe_finding_count": len(unsafe_findings),
            "exception_count": len(exceptions),
        },
    }

    output_path = root / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(report, indent=2))
    return 0 if report["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
