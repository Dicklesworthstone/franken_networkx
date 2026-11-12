#!/usr/bin/env python3
"""Validate CGSE legacy tie-break ordering ledger artifact."""

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


def validate_rule(
    rule: dict[str, Any],
    schema: dict[str, Any],
    errors: list[str],
    root: Path,
) -> None:
    rid = ensure_non_empty_string(rule.get("rule_id"), "rule.rule_id", errors) or "<unknown>"
    require_keys(rule, schema["required_rule_keys"], f"rule `{rid}`", errors)

    operation_family = ensure_non_empty_string(
        rule.get("operation_family"),
        f"rule `{rid}` operation_family",
        errors,
    )
    if operation_family and operation_family not in schema["required_operation_families"]:
        errors.append(
            f"rule `{rid}` operation_family `{operation_family}` is outside allowed families"
        )

    anchors = ensure_list(rule.get("source_anchors"), f"rule `{rid}` source_anchors", errors)
    if not anchors:
        errors.append(f"rule `{rid}` must define at least one source anchor")
    for idx, anchor in enumerate(anchors):
        if not isinstance(anchor, dict):
            errors.append(f"rule `{rid}` source_anchor[{idx}] must be object")
            continue
        require_keys(
            anchor,
            schema["required_anchor_keys"],
            f"rule `{rid}` source_anchor[{idx}]",
            errors,
        )
        path_text = ensure_non_empty_string(
            anchor.get("path"),
            f"rule `{rid}` source_anchor[{idx}].path",
            errors,
        )
        ensure_existing_path(
            path_text,
            f"rule `{rid}` source_anchor[{idx}]",
            root,
            errors,
        )
        symbols = ensure_list(
            anchor.get("symbols"),
            f"rule `{rid}` source_anchor[{idx}].symbols",
            errors,
        )
        if not symbols:
            errors.append(f"rule `{rid}` source_anchor[{idx}] must list symbols")

    ambiguities = ensure_list(rule.get("ambiguity_tags"), f"rule `{rid}` ambiguity_tags", errors)
    for idx, ambiguity in enumerate(ambiguities):
        if not isinstance(ambiguity, dict):
            errors.append(f"rule `{rid}` ambiguity_tags[{idx}] must be object")
            continue
        require_keys(
            ambiguity,
            schema["required_ambiguity_keys"],
            f"rule `{rid}` ambiguity_tags[{idx}]",
            errors,
        )
        opts = ensure_list(
            ambiguity.get("policy_options"),
            f"rule `{rid}` ambiguity_tags[{idx}].policy_options",
            errors,
        )
        if len(opts) < 2:
            errors.append(
                f"rule `{rid}` ambiguity_tags[{idx}] must include at least two policy options"
            )

    hooks = rule.get("test_hooks")
    if not isinstance(hooks, dict):
        errors.append(f"rule `{rid}` test_hooks must be object")
        return

    for channel in schema["required_test_hook_channels"]:
        rows = ensure_list(hooks.get(channel), f"rule `{rid}` test_hooks.{channel}", errors)
        if not rows:
            errors.append(f"rule `{rid}` test_hooks.{channel} must be non-empty")
            continue
        for idx, row in enumerate(rows):
            if not isinstance(row, dict):
                errors.append(f"rule `{rid}` {channel}[{idx}] must be object")
                continue
            require_keys(
                row,
                schema["required_test_hook_keys"],
                f"rule `{rid}` test_hooks.{channel}[{idx}]",
                errors,
            )
            path_text = ensure_non_empty_string(
                row.get("path"),
                f"rule `{rid}` test_hooks.{channel}[{idx}].path",
                errors,
            )
            ensure_existing_path(
                path_text,
                f"rule `{rid}` test_hooks.{channel}[{idx}]",
                root,
                errors,
            )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--artifact",
        default="artifacts/cgse/v1/cgse_legacy_tiebreak_ordering_ledger_v1.json",
        help="Path to CGSE ledger artifact JSON",
    )
    parser.add_argument(
        "--schema",
        default="artifacts/cgse/schema/v1/cgse_legacy_tiebreak_ordering_ledger_schema_v1.json",
        help="Path to CGSE schema JSON",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Optional output validation report path",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    artifact_path = root / args.artifact
    schema_path = root / args.schema

    artifact = load_json(artifact_path)
    schema = load_json(schema_path)

    errors: list[str] = []
    require_keys(artifact, schema["required_top_level_keys"], "artifact", errors)

    families = ensure_list(artifact.get("rule_families"), "artifact.rule_families", errors)
    if sorted(families) != sorted(schema["required_operation_families"]):
        errors.append("artifact.rule_families does not match schema required_operation_families")

    rules = ensure_list(artifact.get("rules"), "artifact.rules", errors)
    if len(rules) < len(schema["required_operation_families"]):
        errors.append("artifact.rules should include at least one rule per operation family")

    observed_families: set[str] = set()
    rule_ids: set[str] = set()
    for idx, rule in enumerate(rules):
        if not isinstance(rule, dict):
            errors.append(f"artifact.rules[{idx}] must be object")
            continue
        validate_rule(rule, schema, errors, root)
        rid = rule.get("rule_id")
        family = rule.get("operation_family")
        if isinstance(rid, str):
            if rid in rule_ids:
                errors.append(f"duplicate rule_id `{rid}`")
            rule_ids.add(rid)
        if isinstance(family, str):
            observed_families.add(family)

    missing_families = sorted(set(schema["required_operation_families"]) - observed_families)
    if missing_families:
        errors.append(f"missing operation families in rules: {', '.join(missing_families)}")

    ambiguity_register = ensure_list(
        artifact.get("ambiguity_register"),
        "artifact.ambiguity_register",
        errors,
    )
    for idx, row in enumerate(ambiguity_register):
        if not isinstance(row, dict):
            errors.append(f"ambiguity_register[{idx}] must be object")
            continue
        for key in ["ambiguity_id", "rule_id", "operation_family", "selected_policy", "risk_note"]:
            ensure_non_empty_string(row.get(key), f"ambiguity_register[{idx}].{key}", errors)
        rule_id = row.get("rule_id")
        if isinstance(rule_id, str) and rule_id not in rule_ids:
            errors.append(f"ambiguity_register[{idx}] references unknown rule_id `{rule_id}`")

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
            path_text = ensure_non_empty_string(profile.get(key), f"profile_first_artifacts.{key}", errors)
            ensure_existing_path(path_text, f"profile_first_artifacts.{key}", root, errors)
    else:
        errors.append("profile_first_artifacts must be object")

    for idx, path_text in enumerate(
        ensure_list(artifact.get("isomorphism_proof_artifacts"), "isomorphism_proof_artifacts", errors)
    ):
        ensure_existing_path(
            ensure_non_empty_string(path_text, f"isomorphism_proof_artifacts[{idx}]", errors),
            f"isomorphism_proof_artifacts[{idx}]",
            root,
            errors,
        )

    for idx, path_text in enumerate(
        ensure_list(artifact.get("structured_logging_evidence"), "structured_logging_evidence", errors)
    ):
        ensure_existing_path(
            ensure_non_empty_string(path_text, f"structured_logging_evidence[{idx}]", errors),
            f"structured_logging_evidence[{idx}]",
            root,
            errors,
        )

    report = {
        "schema_version": "1.0.0",
        "report_id": "cgse-legacy-tiebreak-ordering-ledger-validation-v1",
        "artifact": args.artifact,
        "schema": args.schema,
        "ready": len(errors) == 0,
        "error_count": len(errors),
        "errors": errors,
        "summary": {
            "rule_count": len(rules),
            "operation_family_count": len(observed_families),
            "ambiguity_count": len(ambiguity_register),
        },
    }

    if args.output:
        output_path = root / args.output
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(report, indent=2))
    return 0 if report["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
