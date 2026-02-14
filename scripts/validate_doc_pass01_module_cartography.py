#!/usr/bin/env python3
"""Validate DOC-PASS-01 module/package cartography artifact."""

from __future__ import annotations

import argparse
import json
import tomllib
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as f:
        return tomllib.load(f)


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


def workspace_crate_set() -> set[str]:
    root_toml = load_toml(REPO_ROOT / "Cargo.toml")
    members = root_toml.get("workspace", {}).get("members", [])
    names: set[str] = set()
    for member in members:
        manifest = REPO_ROOT / member / "Cargo.toml"
        if not manifest.exists():
            continue
        package_name = load_toml(manifest).get("package", {}).get("name")
        if isinstance(package_name, str):
            names.add(package_name)
    return names


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--artifact",
        default="artifacts/docs/v1/doc_pass01_module_cartography_v1.json",
        help="Path to DOC-PASS-01 artifact JSON",
    )
    parser.add_argument(
        "--schema",
        default="artifacts/docs/schema/v1/doc_pass01_module_cartography_schema_v1.json",
        help="Path to schema JSON",
    )
    parser.add_argument("--output", default="", help="Optional validation report path")
    args = parser.parse_args()

    artifact = load_json(REPO_ROOT / args.artifact)
    schema = load_json(REPO_ROOT / args.schema)
    errors: list[str] = []

    ensure_keys(artifact, schema["required_top_level_keys"], "artifact", errors)

    summary = artifact.get("workspace_summary")
    if isinstance(summary, dict):
        ensure_keys(summary, schema["required_workspace_summary_keys"], "workspace_summary", errors)
    else:
        errors.append("workspace_summary must be object")

    modules = artifact.get("module_cartography")
    if not isinstance(modules, list) or not modules:
        errors.append("module_cartography must be a non-empty list")
        modules = []

    module_names: set[str] = set()
    for module in modules:
        if not isinstance(module, dict):
            errors.append("module row must be object")
            continue
        ensure_keys(module, schema["required_module_keys"], "module", errors)
        crate_name = module.get("crate_name")
        if not isinstance(crate_name, str) or not crate_name:
            errors.append("module crate_name must be non-empty string")
            continue
        if crate_name in module_names:
            errors.append(f"duplicate module crate_name `{crate_name}`")
        module_names.add(crate_name)

        ensure_path(module.get("manifest_path", ""), f"{crate_name}.manifest_path", errors)
        ensure_path(module.get("source_root", ""), f"{crate_name}.source_root", errors)

        depends_on = module.get("depends_on")
        if not isinstance(depends_on, list):
            errors.append(f"{crate_name}.depends_on must be list")
        else:
            for dep in depends_on:
                if not isinstance(dep, str):
                    errors.append(f"{crate_name}.depends_on entries must be strings")

        hooks = module.get("verification_hooks")
        if isinstance(hooks, dict):
            for key in schema["required_verification_hook_keys"]:
                values = hooks.get(key)
                if not isinstance(values, list) or not values:
                    errors.append(f"{crate_name}.verification_hooks.{key} must be non-empty list")
        else:
            errors.append(f"{crate_name}.verification_hooks must be object")

        policy = module.get("strict_hardened_policy")
        if isinstance(policy, dict):
            ensure_keys(policy, schema["required_policy_keys"], f"{crate_name}.strict_hardened_policy", errors)
            for key in schema["required_policy_keys"]:
                value = policy.get(key)
                if not isinstance(value, str) or not value.strip():
                    errors.append(f"{crate_name}.strict_hardened_policy.{key} must be non-empty string")
        else:
            errors.append(f"{crate_name}.strict_hardened_policy must be object")

        hidden_refs = module.get("known_hidden_couplings")
        if not isinstance(hidden_refs, list) or not hidden_refs:
            errors.append(f"{crate_name}.known_hidden_couplings must be non-empty list")

        legacy_scope = module.get("legacy_scope_paths")
        if not isinstance(legacy_scope, list) or not legacy_scope:
            errors.append(f"{crate_name}.legacy_scope_paths must be non-empty list")

    expected_crates = workspace_crate_set()
    if module_names != expected_crates:
        errors.append(
            "module cartography crate set mismatch: "
            f"expected={sorted(expected_crates)} observed={sorted(module_names)}"
        )

    edges = artifact.get("cross_module_dependency_map")
    if not isinstance(edges, list) or not edges:
        errors.append("cross_module_dependency_map must be non-empty list")
        edges = []
    for edge in edges:
        if not isinstance(edge, dict):
            errors.append("dependency edge must be object")
            continue
        ensure_keys(edge, schema["required_edge_keys"], "dependency edge", errors)
        from_crate = edge.get("from_crate")
        to_crate = edge.get("to_crate")
        if from_crate not in module_names:
            errors.append(f"dependency edge references unknown from_crate `{from_crate}`")
        if to_crate not in module_names:
            errors.append(f"dependency edge references unknown to_crate `{to_crate}`")

    constraints = artifact.get("layering_constraints")
    if not isinstance(constraints, list) or not constraints:
        errors.append("layering_constraints must be non-empty list")
        constraints = []
    for constraint in constraints:
        if not isinstance(constraint, dict):
            errors.append("layering constraint must be object")
            continue
        ensure_keys(constraint, schema["required_constraint_keys"], "layering constraint", errors)

    violations = artifact.get("layering_violations")
    if not isinstance(violations, list):
        errors.append("layering_violations must be list")

    hidden_hotspots = artifact.get("hidden_coupling_hotspots")
    if not isinstance(hidden_hotspots, list) or len(hidden_hotspots) < 3:
        errors.append("hidden_coupling_hotspots must contain at least three entries")
        hidden_hotspots = []
    for hotspot in hidden_hotspots:
        if not isinstance(hotspot, dict):
            errors.append("hidden coupling hotspot must be object")
            continue
        ensure_keys(hotspot, schema["required_hidden_coupling_keys"], "hidden coupling hotspot", errors)

    alien = artifact.get("alien_uplift_contract_card")
    if isinstance(alien, dict):
        ev_score = alien.get("ev_score")
        if not isinstance(ev_score, (int, float)) or ev_score < 2.0:
            errors.append("alien_uplift_contract_card.ev_score must be >= 2.0")
    else:
        errors.append("alien_uplift_contract_card must be object")

    profile = artifact.get("profile_first_artifacts")
    if isinstance(profile, dict):
        ensure_keys(profile, ["baseline", "hotspot", "delta"], "profile_first_artifacts", errors)
        for key in ["baseline", "hotspot", "delta"]:
            ensure_path(profile.get(key, ""), f"profile_first_artifacts.{key}", errors)
    else:
        errors.append("profile_first_artifacts must be object")

    for idx, path in enumerate(artifact.get("isomorphism_proof_artifacts", [])):
        ensure_path(path, f"isomorphism_proof_artifacts[{idx}]", errors)
    for idx, path in enumerate(artifact.get("structured_logging_evidence", [])):
        ensure_path(path, f"structured_logging_evidence[{idx}]", errors)

    report = {
        "schema_version": "1.0.0",
        "report_id": "doc-pass-01-module-cartography-validation-v1",
        "artifact_path": args.artifact,
        "ready": len(errors) == 0,
        "error_count": len(errors),
        "errors": errors,
        "summary": {
            "module_count": len(modules),
            "dependency_edge_count": len(edges),
            "layering_violation_count": len(violations) if isinstance(violations, list) else 0,
            "hidden_coupling_count": len(hidden_hotspots),
        },
    }

    if args.output:
        out_path = REPO_ROOT / args.output
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(report, indent=2))
    return 0 if report["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
