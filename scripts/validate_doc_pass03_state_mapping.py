#!/usr/bin/env python3
"""Validate DOC-PASS-03 data model/state/invariant artifact."""

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


def ensure_path(path: str, ctx: str, errors: list[str]) -> None:
    if not isinstance(path, str) or not path:
        errors.append(f"{ctx} must be a non-empty string path")
        return
    if not Path(path).exists():
        errors.append(f"{ctx} path does not exist: {path}")


def validate_component(component: dict[str, Any], schema: dict[str, Any], errors: list[str]) -> None:
    cid = component.get("component_id", "<unknown>")
    require_keys(component, schema["required_component_keys"], f"component `{cid}`", errors)

    state_model = component.get("state_model")
    if isinstance(state_model, dict):
        require_keys(state_model, schema["required_state_model_keys"], f"component `{cid}` state_model", errors)
        for key in ["states", "mutable_fields"]:
            values = ensure_list(state_model.get(key), f"component `{cid}` state_model.{key}", errors)
            if not values:
                errors.append(f"component `{cid}` state_model.{key} must be non-empty")
    else:
        errors.append(f"component `{cid}` state_model must be object")

    transitions = ensure_list(component.get("state_transitions"), f"component `{cid}` state_transitions", errors)
    if not transitions:
        errors.append(f"component `{cid}` must declare at least one state transition")
    for transition in transitions:
        if not isinstance(transition, dict):
            errors.append(f"component `{cid}` has non-object transition")
            continue
        require_keys(transition, schema["required_transition_keys"], f"component `{cid}` transition", errors)
        guards = ensure_list(transition.get("guards"), f"component `{cid}` transition guards", errors)
        if not guards:
            errors.append(f"component `{cid}` transition guards must be non-empty")

    invariants = ensure_list(component.get("invariants"), f"component `{cid}` invariants", errors)
    if not invariants:
        errors.append(f"component `{cid}` must define at least one invariant")
    for invariant in invariants:
        if not isinstance(invariant, dict):
            errors.append(f"component `{cid}` has non-object invariant")
            continue
        require_keys(invariant, schema["required_invariant_keys"], f"component `{cid}` invariant", errors)
        for key in ["recovery_steps", "test_hooks"]:
            values = ensure_list(invariant.get(key), f"component `{cid}` invariant {key}", errors)
            if not values:
                errors.append(f"component `{cid}` invariant {key} must be non-empty")

    ambiguity_tags = ensure_list(component.get("ambiguity_tags"), f"component `{cid}` ambiguity_tags", errors)
    if not ambiguity_tags:
        errors.append(f"component `{cid}` must define ambiguity_tags")
    for tag in ambiguity_tags:
        if not isinstance(tag, dict):
            errors.append(f"component `{cid}` has non-object ambiguity tag")
            continue
        require_keys(tag, schema["required_ambiguity_keys"], f"component `{cid}` ambiguity_tag", errors)
        options = ensure_list(tag.get("policy_options"), f"component `{cid}` policy_options", errors)
        if not options:
            errors.append(f"component `{cid}` policy_options must be non-empty")

    hooks = component.get("verification_hooks")
    if isinstance(hooks, dict):
        require_keys(hooks, schema["required_verification_hook_keys"], f"component `{cid}` verification_hooks", errors)
        for key in schema["required_verification_hook_keys"]:
            values = ensure_list(hooks.get(key), f"component `{cid}` verification hook `{key}`", errors)
            if not values:
                errors.append(f"component `{cid}` verification hook `{key}` must be non-empty")
    else:
        errors.append(f"component `{cid}` verification_hooks must be object")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--artifact",
        default="artifacts/docs/v1/doc_pass03_data_model_state_invariant_v1.json",
        help="Path to DOC-PASS-03 artifact JSON",
    )
    parser.add_argument(
        "--schema",
        default="artifacts/docs/schema/v1/doc_pass03_data_model_state_invariant_schema_v1.json",
        help="Path to schema JSON",
    )
    parser.add_argument("--output", default="", help="Optional validation report path")
    args = parser.parse_args()

    artifact = load_json(Path(args.artifact))
    schema = load_json(Path(args.schema))

    errors: list[str] = []
    require_keys(artifact, schema["required_top_level_keys"], "artifact", errors)

    components = ensure_list(artifact.get("components"), "artifact.components", errors)
    if not components:
        errors.append("artifact must define at least one component")
    for component in components:
        if not isinstance(component, dict):
            errors.append("component row must be object")
            continue
        validate_component(component, schema, errors)

    alien = artifact.get("alien_uplift_contract_card")
    if isinstance(alien, dict):
        ev_score = alien.get("ev_score")
        if not isinstance(ev_score, (int, float)) or ev_score < 2.0:
            errors.append("alien_uplift_contract_card.ev_score must be >= 2.0")
    else:
        errors.append("alien_uplift_contract_card must be object")

    profile = artifact.get("profile_first_artifacts", {})
    if isinstance(profile, dict):
        for key in ["baseline", "hotspot", "delta"]:
            if key not in profile:
                errors.append(f"profile_first_artifacts missing key `{key}`")
                continue
            ensure_path(profile[key], f"profile_first_artifacts.{key}", errors)
    else:
        errors.append("profile_first_artifacts must be object")

    for idx, path in enumerate(ensure_list(artifact.get("isomorphism_proof_artifacts"), "isomorphism_proof_artifacts", errors)):
        ensure_path(path, f"isomorphism_proof_artifacts[{idx}]", errors)
    for idx, path in enumerate(ensure_list(artifact.get("structured_logging_evidence"), "structured_logging_evidence", errors)):
        ensure_path(path, f"structured_logging_evidence[{idx}]", errors)

    report = {
        "schema_version": "1.0.0",
        "report_id": "doc-pass-03-state-mapping-validation-v1",
        "artifact_id": artifact.get("artifact_id", "<unknown>"),
        "ready": len(errors) == 0,
        "error_count": len(errors),
        "errors": errors,
        "summary": {"component_count": len(components)},
    }

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(report, indent=2))
    return 0 if report["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
