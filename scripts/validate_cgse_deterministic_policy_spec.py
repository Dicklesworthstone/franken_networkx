#!/usr/bin/env python3
"""Validate CGSE deterministic policy spec artifact."""

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


def ensure_existing_path(path_text: str, ctx: str, root: Path, errors: list[str]) -> None:
    if not path_text:
        return
    path = root / path_text
    if not path.exists():
        errors.append(f"{ctx} path does not exist: {path_text}")


def build_ledger_index(ledger: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, set[str]], dict[str, dict[str, set[str]]]]:
    rules = {row["rule_id"]: row for row in ledger.get("rules", []) if isinstance(row, dict) and isinstance(row.get("rule_id"), str)}
    ambiguity_by_rule: dict[str, set[str]] = {}
    hooks_by_rule: dict[str, dict[str, set[str]]] = {}

    for rule_id, rule in rules.items():
        ambiguity_by_rule[rule_id] = {
            tag["ambiguity_id"]
            for tag in rule.get("ambiguity_tags", [])
            if isinstance(tag, dict) and isinstance(tag.get("ambiguity_id"), str)
        }
        channel_map: dict[str, set[str]] = {}
        for channel in ["unit", "property", "differential", "e2e"]:
            hook_ids = {
                hook_row["hook_id"]
                for hook_row in rule.get("test_hooks", {}).get(channel, [])
                if isinstance(hook_row, dict) and isinstance(hook_row.get("hook_id"), str)
            }
            channel_map[channel] = hook_ids
        hooks_by_rule[rule_id] = channel_map

    return rules, ambiguity_by_rule, hooks_by_rule


def validate_row(
    row: dict[str, Any],
    schema: dict[str, Any],
    ledger_rules: dict[str, dict[str, Any]],
    ambiguity_by_rule: dict[str, set[str]],
    hooks_by_rule: dict[str, dict[str, set[str]]],
    errors: list[str],
) -> tuple[str, str]:
    policy_id = ensure_non_empty_string(row.get("policy_id"), "policy_row.policy_id", errors)
    rule_id = ensure_non_empty_string(row.get("rule_id"), f"policy_row `{policy_id}` rule_id", errors)
    require_keys(row, schema["required_policy_row_keys"], f"policy_row `{policy_id or '<unknown>'}`", errors)

    family = ensure_non_empty_string(
        row.get("operation_family"),
        f"policy_row `{policy_id or '<unknown>'}` operation_family",
        errors,
    )
    if family and family not in schema["required_operation_families"]:
        errors.append(
            f"policy_row `{policy_id}` operation_family `{family}` is outside allowed families"
        )

    ledger_rule = ledger_rules.get(rule_id)
    if not ledger_rule:
        errors.append(f"policy_row `{policy_id}` references unknown ledger rule_id `{rule_id}`")
    else:
        if row.get("tie_break_contract") != ledger_rule.get("tie_break_policy"):
            errors.append(
                f"policy_row `{policy_id}` tie_break_contract does not match ledger tie_break_policy for `{rule_id}`"
            )
        if row.get("ordering_contract") != ledger_rule.get("ordering_policy"):
            errors.append(
                f"policy_row `{policy_id}` ordering_contract does not match ledger ordering_policy for `{rule_id}`"
            )

    strict_mode_behavior = ensure_non_empty_string(
        row.get("strict_mode_behavior"),
        f"policy_row `{policy_id}` strict_mode_behavior",
        errors,
    )
    hardened_mode_behavior = ensure_non_empty_string(
        row.get("hardened_mode_behavior"),
        f"policy_row `{policy_id}` hardened_mode_behavior",
        errors,
    )
    ensure_non_empty_string(
        row.get("strict_invariant"),
        f"policy_row `{policy_id}` strict_invariant",
        errors,
    )
    ensure_non_empty_string(
        row.get("hardened_invariant"),
        f"policy_row `{policy_id}` hardened_invariant",
        errors,
    )
    ensure_non_empty_string(
        row.get("preservation_obligation"),
        f"policy_row `{policy_id}` preservation_obligation",
        errors,
    )
    ensure_non_empty_string(
        row.get("hardened_security_rationale"),
        f"policy_row `{policy_id}` hardened_security_rationale",
        errors,
    )

    if "legacy" not in strict_mode_behavior.lower():
        errors.append(f"policy_row `{policy_id}` strict_mode_behavior should explicitly reference legacy parity")
    hardened_text = hardened_mode_behavior.lower()
    if "fail closed" not in hardened_text and "allowlist" not in hardened_text:
        errors.append(
            f"policy_row `{policy_id}` hardened_mode_behavior must include fail-closed or allowlist language"
        )

    for field in ["preconditions", "postconditions"]:
        items = ensure_list(row.get(field), f"policy_row `{policy_id}` {field}", errors)
        if not items:
            errors.append(f"policy_row `{policy_id}` {field} must be non-empty")
        for idx, item in enumerate(items):
            ensure_non_empty_string(item, f"policy_row `{policy_id}` {field}[{idx}]", errors)

    allowlist = ensure_list(row.get("hardened_allowlist"), f"policy_row `{policy_id}` hardened_allowlist", errors)
    if not allowlist:
        errors.append(f"policy_row `{policy_id}` hardened_allowlist must be non-empty")
    allowed_builtin = set(schema["builtin_hardened_allowlist_categories"])
    allowed_ambiguity = ambiguity_by_rule.get(rule_id, set())
    for idx, item in enumerate(allowlist):
        token = ensure_non_empty_string(item, f"policy_row `{policy_id}` hardened_allowlist[{idx}]", errors)
        if token and token not in allowed_builtin and token not in allowed_ambiguity:
            errors.append(
                f"policy_row `{policy_id}` hardened_allowlist token `{token}` is not a built-in category or ambiguity_id for `{rule_id}`"
            )

    fail_closed_default = ensure_non_empty_string(
        row.get("fail_closed_default"),
        f"policy_row `{policy_id}` fail_closed_default",
        errors,
    )
    if fail_closed_default and not fail_closed_default.startswith("fail_closed_on_"):
        errors.append(
            f"policy_row `{policy_id}` fail_closed_default must start with `fail_closed_on_`"
        )

    verification_hooks = row.get("verification_hooks")
    if not isinstance(verification_hooks, dict):
        errors.append(f"policy_row `{policy_id}` verification_hooks must be object")
    else:
        for channel in schema["required_verification_channels"]:
            channel_hooks = ensure_list(
                verification_hooks.get(channel),
                f"policy_row `{policy_id}` verification_hooks.{channel}",
                errors,
            )
            if not channel_hooks:
                errors.append(f"policy_row `{policy_id}` verification_hooks.{channel} must be non-empty")
            known_hooks = hooks_by_rule.get(rule_id, {}).get(channel, set())
            for idx, hook_id in enumerate(channel_hooks):
                hid = ensure_non_empty_string(
                    hook_id,
                    f"policy_row `{policy_id}` verification_hooks.{channel}[{idx}]",
                    errors,
                )
                if hid and hid not in known_hooks:
                    errors.append(
                        f"policy_row `{policy_id}` verification hook `{hid}` not found for `{rule_id}` channel `{channel}` in ledger"
                    )

    return policy_id, rule_id


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--artifact",
        default="artifacts/cgse/v1/cgse_deterministic_policy_spec_v1.json",
        help="Path to CGSE deterministic policy spec JSON",
    )
    parser.add_argument(
        "--schema",
        default="artifacts/cgse/schema/v1/cgse_deterministic_policy_spec_schema_v1.json",
        help="Path to CGSE deterministic policy schema JSON",
    )
    parser.add_argument(
        "--ledger",
        default="artifacts/cgse/v1/cgse_legacy_tiebreak_ordering_ledger_v1.json",
        help="Path to CGSE legacy ledger JSON used for cross-checks",
    )
    parser.add_argument(
        "--output",
        default="artifacts/cgse/latest/cgse_deterministic_policy_spec_validation_v1.json",
        help="Output validation report path",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    artifact_path = root / args.artifact
    schema_path = root / args.schema
    ledger_path = root / args.ledger

    artifact = load_json(artifact_path)
    schema = load_json(schema_path)
    ledger = load_json(ledger_path)
    ledger_rules, ambiguity_by_rule, hooks_by_rule = build_ledger_index(ledger)

    errors: list[str] = []
    require_keys(artifact, schema["required_top_level_keys"], "artifact", errors)
    ensure_existing_path(
        ensure_non_empty_string(artifact.get("source_ledger"), "artifact.source_ledger", errors),
        "artifact.source_ledger",
        root,
        errors,
    )

    profile = artifact.get("profile_first_artifacts")
    if isinstance(profile, dict):
        for key in schema["required_profile_artifact_keys"]:
            path_text = ensure_non_empty_string(profile.get(key), f"profile_first_artifacts.{key}", errors)
            ensure_existing_path(path_text, f"profile_first_artifacts.{key}", root, errors)
    else:
        errors.append("profile_first_artifacts must be object")

    policy_rows = ensure_list(artifact.get("policy_rows"), "artifact.policy_rows", errors)
    policy_ids: set[str] = set()
    rule_ids: set[str] = set()
    duplicate_policy_ids: set[str] = set()
    duplicate_rule_ids: set[str] = set()

    for idx, row in enumerate(policy_rows):
        if not isinstance(row, dict):
            errors.append(f"policy_rows[{idx}] must be object")
            continue
        policy_id, rule_id = validate_row(
            row,
            schema,
            ledger_rules,
            ambiguity_by_rule,
            hooks_by_rule,
            errors,
        )
        if policy_id in policy_ids:
            duplicate_policy_ids.add(policy_id)
        if policy_id:
            policy_ids.add(policy_id)
        if rule_id in rule_ids:
            duplicate_rule_ids.add(rule_id)
        if rule_id:
            rule_ids.add(rule_id)

    if len(policy_rows) < len(ledger_rules):
        errors.append("artifact.policy_rows should cover all ledger rules")

    conflict_scan = artifact.get("conflict_scan")
    if isinstance(conflict_scan, dict):
        require_keys(conflict_scan, schema["required_conflict_scan_keys"], "artifact.conflict_scan", errors)
        status = ensure_non_empty_string(conflict_scan.get("status"), "artifact.conflict_scan.status", errors)
        listed_dup_policy = set(
            ensure_list(conflict_scan.get("duplicate_policy_ids"), "artifact.conflict_scan.duplicate_policy_ids", errors)
        )
        listed_dup_rules = set(
            ensure_list(conflict_scan.get("duplicate_rule_ids"), "artifact.conflict_scan.duplicate_rule_ids", errors)
        )
        if listed_dup_policy != duplicate_policy_ids:
            errors.append("artifact.conflict_scan.duplicate_policy_ids does not match observed duplicates")
        if listed_dup_rules != duplicate_rule_ids:
            errors.append("artifact.conflict_scan.duplicate_rule_ids does not match observed duplicates")
        expected_status = "no_conflicts" if not duplicate_policy_ids and not duplicate_rule_ids else "conflicts_detected"
        if status and status != expected_status:
            errors.append(
                f"artifact.conflict_scan.status `{status}` does not match expected `{expected_status}`"
            )
    else:
        errors.append("artifact.conflict_scan must be object")

    top_allowlist = set(
        ensure_list(
            artifact.get("hardened_allowlisted_categories"),
            "artifact.hardened_allowlisted_categories",
            errors,
        )
    )
    row_allowlist = {
        token
        for row in policy_rows
        if isinstance(row, dict)
        for token in ensure_list(row.get("hardened_allowlist"), "policy_row.hardened_allowlist", errors)
        if isinstance(token, str)
    }
    if not row_allowlist.issubset(top_allowlist):
        errors.append("artifact.hardened_allowlisted_categories must include all row-level allowlist tokens")

    alien = artifact.get("alien_uplift_contract_card")
    if isinstance(alien, dict):
        ev_score = alien.get("ev_score")
        if not isinstance(ev_score, (int, float)) or ev_score < 2.0:
            errors.append("alien_uplift_contract_card.ev_score must be >= 2.0")
    else:
        errors.append("alien_uplift_contract_card must be object")

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
        "report_id": "cgse-deterministic-policy-spec-validation-v1",
        "artifact": args.artifact,
        "schema": args.schema,
        "ledger": args.ledger,
        "ready": len(errors) == 0,
        "error_count": len(errors),
        "errors": errors,
        "summary": {
            "policy_row_count": len(policy_rows),
            "ledger_rule_count": len(ledger_rules),
            "duplicate_policy_id_count": len(duplicate_policy_ids),
            "duplicate_rule_id_count": len(duplicate_rule_ids),
        },
    }

    output_path = root / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(report, indent=2))
    return 0 if report["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
