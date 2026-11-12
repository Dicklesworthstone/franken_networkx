#!/usr/bin/env python3
"""Validate CGSE semantics-boundary threat model artifact."""

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


def path_without_line_suffix(path_text: str) -> str:
    if ":" in path_text:
        candidate, remainder = path_text.split(":", 1)
        if remainder and remainder[0].isdigit():
            return candidate
    return path_text


def ensure_existing_path(path_text: str, ctx: str, root: Path, errors: list[str]) -> None:
    if not path_text:
        return
    normalized = path_without_line_suffix(path_text)
    if not (root / normalized).exists():
        errors.append(f"{ctx} path does not exist: {path_text}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--artifact",
        default="artifacts/cgse/v1/cgse_semantics_threat_model_v1.json",
        help="Path to CGSE semantics threat model JSON",
    )
    parser.add_argument(
        "--schema",
        default="artifacts/cgse/schema/v1/cgse_semantics_threat_model_schema_v1.json",
        help="Path to CGSE semantics threat model schema JSON",
    )
    parser.add_argument(
        "--policy",
        default="artifacts/cgse/v1/cgse_deterministic_policy_spec_v1.json",
        help="Path to CGSE deterministic policy spec JSON",
    )
    parser.add_argument(
        "--ledger",
        default="artifacts/cgse/v1/cgse_legacy_tiebreak_ordering_ledger_v1.json",
        help="Path to CGSE legacy ledger JSON",
    )
    parser.add_argument(
        "--output",
        default="artifacts/cgse/latest/cgse_semantics_threat_model_validation_v1.json",
        help="Output validation report path",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    artifact = load_json(root / args.artifact)
    schema = load_json(root / args.schema)
    policy = load_json(root / args.policy)
    ledger = load_json(root / args.ledger)

    errors: list[str] = []
    require_keys(artifact, schema["required_top_level_keys"], "artifact", errors)

    for key in ["source_ledger", "source_policy"]:
        ensure_existing_path(
            ensure_non_empty_string(artifact.get(key), f"artifact.{key}", errors),
            f"artifact.{key}",
            root,
            errors,
        )

    policy_rows = ensure_list(policy.get("policy_rows"), "policy.policy_rows", errors)
    policy_by_rule = {
        row["rule_id"]: row
        for row in policy_rows
        if isinstance(row, dict) and isinstance(row.get("rule_id"), str)
    }
    ledger_rule_ids = {
        row["rule_id"]
        for row in ensure_list(ledger.get("rules"), "ledger.rules", errors)
        if isinstance(row, dict) and isinstance(row.get("rule_id"), str)
    }

    threat_rows = ensure_list(artifact.get("threat_rows"), "artifact.threat_rows", errors)
    seen_threat_ids: set[str] = set()
    seen_threat_rules: set[str] = set()
    threat_allowlist_union: set[str] = set()

    for idx, row in enumerate(threat_rows):
        if not isinstance(row, dict):
            errors.append(f"threat_rows[{idx}] must be object")
            continue
        require_keys(row, schema["required_threat_row_keys"], f"threat_rows[{idx}]", errors)
        threat_id = ensure_non_empty_string(row.get("threat_id"), f"threat_rows[{idx}].threat_id", errors)
        rule_id = ensure_non_empty_string(row.get("rule_id"), f"threat_rows[{idx}].rule_id", errors)
        if threat_id in seen_threat_ids:
            errors.append(f"duplicate threat_id `{threat_id}`")
        if threat_id:
            seen_threat_ids.add(threat_id)

        if rule_id in seen_threat_rules:
            errors.append(f"duplicate threat row for rule_id `{rule_id}`")
        if rule_id:
            seen_threat_rules.add(rule_id)
        if rule_id and rule_id not in policy_by_rule:
            errors.append(f"threat_rows[{idx}] references unknown policy rule_id `{rule_id}`")
        if rule_id and rule_id not in ledger_rule_ids:
            errors.append(f"threat_rows[{idx}] references unknown ledger rule_id `{rule_id}`")

        strict_response = ensure_non_empty_string(
            row.get("strict_mode_response"),
            f"threat_rows[{idx}].strict_mode_response",
            errors,
        )
        if "fail-closed" not in strict_response.lower():
            errors.append(f"threat_rows[{idx}] strict_mode_response should include fail-closed behavior")

        hardened_response = ensure_non_empty_string(
            row.get("hardened_mode_response"),
            f"threat_rows[{idx}].hardened_mode_response",
            errors,
        )
        lowered = hardened_response.lower()
        if "allowlist" not in lowered and "fail closed" not in lowered:
            errors.append(
                f"threat_rows[{idx}] hardened_mode_response should include allowlist/fail-closed language"
            )

        mitigations = ensure_list(row.get("mitigations"), f"threat_rows[{idx}].mitigations", errors)
        if not mitigations:
            errors.append(f"threat_rows[{idx}] mitigations must be non-empty")

        evidence_artifact = ensure_non_empty_string(
            row.get("evidence_artifact"),
            f"threat_rows[{idx}].evidence_artifact",
            errors,
        )
        ensure_existing_path(evidence_artifact, f"threat_rows[{idx}].evidence_artifact", root, errors)

        adversarial_hooks = ensure_list(
            row.get("adversarial_fixture_hooks"),
            f"threat_rows[{idx}].adversarial_fixture_hooks",
            errors,
        )
        if not adversarial_hooks:
            errors.append(f"threat_rows[{idx}] adversarial_fixture_hooks must be non-empty")
        if rule_id in policy_by_rule:
            known_diff_hooks = set(policy_by_rule[rule_id]["verification_hooks"]["differential"])
            for hook_id in adversarial_hooks:
                if isinstance(hook_id, str) and hook_id not in known_diff_hooks:
                    errors.append(
                        f"threat_rows[{idx}] adversarial hook `{hook_id}` not present in policy differential hooks for `{rule_id}`"
                    )

        taxonomy = ensure_list(row.get("crash_triage_taxonomy"), f"threat_rows[{idx}].crash_triage_taxonomy", errors)
        if not taxonomy:
            errors.append(f"threat_rows[{idx}] crash_triage_taxonomy must be non-empty")

        allowlisted = ensure_list(
            row.get("hardened_allowlisted_categories"),
            f"threat_rows[{idx}].hardened_allowlisted_categories",
            errors,
        )
        if not allowlisted:
            errors.append(f"threat_rows[{idx}] hardened_allowlisted_categories must be non-empty")
        threat_allowlist_union.update(item for item in allowlisted if isinstance(item, str))
        if rule_id in policy_by_rule:
            policy_allowlist = set(policy_by_rule[rule_id]["hardened_allowlist"])
            for item in allowlisted:
                if isinstance(item, str) and item not in policy_allowlist:
                    errors.append(
                        f"threat_rows[{idx}] allowlist token `{item}` not found in policy row allowlist for `{rule_id}`"
                    )

        ensure_non_empty_string(
            row.get("compatibility_boundary"),
            f"threat_rows[{idx}].compatibility_boundary",
            errors,
        )

    boundary_rows = ensure_list(
        artifact.get("compatibility_boundary_rows"),
        "artifact.compatibility_boundary_rows",
        errors,
    )
    seen_boundary_ids: set[str] = set()
    seen_boundary_rules: set[str] = set()
    boundary_allowlist_union: set[str] = set()
    for idx, row in enumerate(boundary_rows):
        if not isinstance(row, dict):
            errors.append(f"compatibility_boundary_rows[{idx}] must be object")
            continue
        require_keys(row, schema["required_boundary_row_keys"], f"compatibility_boundary_rows[{idx}]", errors)
        boundary_id = ensure_non_empty_string(
            row.get("boundary_id"),
            f"compatibility_boundary_rows[{idx}].boundary_id",
            errors,
        )
        rule_id = ensure_non_empty_string(
            row.get("rule_id"),
            f"compatibility_boundary_rows[{idx}].rule_id",
            errors,
        )
        if boundary_id in seen_boundary_ids:
            errors.append(f"duplicate boundary_id `{boundary_id}`")
        if boundary_id:
            seen_boundary_ids.add(boundary_id)
        if rule_id in seen_boundary_rules:
            errors.append(f"duplicate compatibility boundary for rule_id `{rule_id}`")
        if rule_id:
            seen_boundary_rules.add(rule_id)
        if rule_id and rule_id not in policy_by_rule:
            errors.append(
                f"compatibility_boundary_rows[{idx}] references unknown policy rule_id `{rule_id}`"
            )

        ensure_non_empty_string(
            row.get("strict_parity_obligation"),
            f"compatibility_boundary_rows[{idx}].strict_parity_obligation",
            errors,
        )
        allowlisted = ensure_list(
            row.get("hardened_allowlisted_deviation_categories"),
            f"compatibility_boundary_rows[{idx}].hardened_allowlisted_deviation_categories",
            errors,
        )
        if not allowlisted:
            errors.append(
                f"compatibility_boundary_rows[{idx}] hardened_allowlisted_deviation_categories must be non-empty"
            )
        boundary_allowlist_union.update(item for item in allowlisted if isinstance(item, str))
        if rule_id in policy_by_rule:
            policy_allowlist = set(policy_by_rule[rule_id]["hardened_allowlist"])
            for item in allowlisted:
                if isinstance(item, str) and item not in policy_allowlist:
                    errors.append(
                        f"compatibility_boundary_rows[{idx}] token `{item}` not in policy allowlist for `{rule_id}`"
                    )

            expected_fail_closed = policy_by_rule[rule_id]["fail_closed_default"]
            fail_closed_default = ensure_non_empty_string(
                row.get("fail_closed_default"),
                f"compatibility_boundary_rows[{idx}].fail_closed_default",
                errors,
            )
            if fail_closed_default and fail_closed_default != expected_fail_closed:
                errors.append(
                    f"compatibility_boundary_rows[{idx}] fail_closed_default does not match policy row `{rule_id}`"
                )

        evidence_hooks = ensure_list(
            row.get("evidence_hooks"),
            f"compatibility_boundary_rows[{idx}].evidence_hooks",
            errors,
        )
        if not evidence_hooks:
            errors.append(f"compatibility_boundary_rows[{idx}] evidence_hooks must be non-empty")
        for hook in evidence_hooks:
            if isinstance(hook, str):
                ensure_existing_path(hook, f"compatibility_boundary_rows[{idx}].evidence_hooks", root, errors)

    if seen_threat_rules != set(policy_by_rule.keys()):
        errors.append("threat_rows rule coverage must match policy_rows rule coverage exactly")
    if seen_boundary_rules != set(policy_by_rule.keys()):
        errors.append("compatibility_boundary_rows rule coverage must match policy_rows rule coverage exactly")

    top_allowlisted = set(
        ensure_list(
            artifact.get("hardened_allowlisted_categories"),
            "artifact.hardened_allowlisted_categories",
            errors,
        )
    )
    expected_allowlisted = threat_allowlist_union | boundary_allowlist_union
    if not expected_allowlisted.issubset(top_allowlisted):
        errors.append(
            "artifact.hardened_allowlisted_categories must include all threat/boundary allowlist tokens"
        )

    alien = artifact.get("alien_uplift_contract_card")
    if isinstance(alien, dict):
        ev_score = alien.get("ev_score")
        if not isinstance(ev_score, (int, float)) or ev_score < 2.0:
            errors.append("alien_uplift_contract_card.ev_score must be >= 2.0")
    else:
        errors.append("alien_uplift_contract_card must be object")

    profile = artifact.get("profile_first_artifacts")
    if isinstance(profile, dict):
        for key in schema["required_profile_artifact_keys"]:
            ensure_existing_path(
                ensure_non_empty_string(profile.get(key), f"profile_first_artifacts.{key}", errors),
                f"profile_first_artifacts.{key}",
                root,
                errors,
            )
    else:
        errors.append("profile_first_artifacts must be object")

    for idx, path_text in enumerate(
        ensure_list(artifact.get("isomorphism_proof_artifacts"), "artifact.isomorphism_proof_artifacts", errors)
    ):
        ensure_existing_path(
            ensure_non_empty_string(path_text, f"isomorphism_proof_artifacts[{idx}]", errors),
            f"isomorphism_proof_artifacts[{idx}]",
            root,
            errors,
        )

    for idx, path_text in enumerate(
        ensure_list(artifact.get("structured_logging_evidence"), "artifact.structured_logging_evidence", errors)
    ):
        ensure_existing_path(
            ensure_non_empty_string(path_text, f"structured_logging_evidence[{idx}]", errors),
            f"structured_logging_evidence[{idx}]",
            root,
            errors,
        )

    report = {
        "schema_version": "1.0.0",
        "report_id": "cgse-semantics-threat-model-validation-v1",
        "artifact": args.artifact,
        "schema": args.schema,
        "policy": args.policy,
        "ledger": args.ledger,
        "ready": len(errors) == 0,
        "error_count": len(errors),
        "errors": errors,
        "summary": {
            "threat_row_count": len(threat_rows),
            "boundary_row_count": len(boundary_rows),
            "policy_row_count": len(policy_by_rule),
            "threat_allowlist_count": len(threat_allowlist_union),
        },
    }

    output_path = root / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
