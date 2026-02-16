#!/usr/bin/env python3
"""Validate DOC-PASS-02 symbol/API census artifacts."""

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
    with path.open("rb") as handle:
        return tomllib.load(handle)


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
        default="artifacts/docs/v1/doc_pass02_symbol_api_census_v1.json",
        help="Path to DOC-PASS-02 artifact JSON",
    )
    parser.add_argument(
        "--schema",
        default="artifacts/docs/schema/v1/doc_pass02_symbol_api_census_schema_v1.json",
        help="Path to DOC-PASS-02 schema JSON",
    )
    parser.add_argument("--output", default="", help="Optional validation report path")
    args = parser.parse_args()

    artifact = load_json(REPO_ROOT / args.artifact)
    schema = load_json(REPO_ROOT / args.schema)
    errors: list[str] = []

    ensure_keys(artifact, schema["required_top_level_keys"], "artifact", errors)

    summary = artifact.get("census_summary")
    if isinstance(summary, dict):
        ensure_keys(summary, schema["required_summary_keys"], "census_summary", errors)
    else:
        errors.append("census_summary must be object")
        summary = {}

    families = artifact.get("subsystem_families")
    if not isinstance(families, list) or not families:
        errors.append("subsystem_families must be a non-empty list")
        families = []
    for idx, family in enumerate(families):
        if not isinstance(family, dict):
            errors.append(f"subsystem_families[{idx}] must be object")
            continue
        ensure_keys(family, schema["required_family_keys"], f"subsystem_families[{idx}]", errors)
        crates = family.get("crates")
        if not isinstance(crates, list) or not crates:
            errors.append(f"subsystem_families[{idx}].crates must be non-empty list")

    symbols = artifact.get("symbol_inventory")
    if not isinstance(symbols, list) or not symbols:
        errors.append("symbol_inventory must be non-empty list")
        symbols = []

    symbol_ids: set[str] = set()
    high_ids: set[str] = set()
    observed_crates: set[str] = set()
    public_count = 0
    internal_count = 0
    for idx, symbol in enumerate(symbols):
        if not isinstance(symbol, dict):
            errors.append(f"symbol_inventory[{idx}] must be object")
            continue
        ensure_keys(symbol, schema["required_symbol_keys"], f"symbol_inventory[{idx}]", errors)

        symbol_id = symbol.get("symbol_id")
        if not isinstance(symbol_id, str) or not symbol_id.strip():
            errors.append(f"symbol_inventory[{idx}].symbol_id must be non-empty string")
            continue
        if symbol_id in symbol_ids:
            errors.append(f"duplicate symbol_id `{symbol_id}`")
        symbol_ids.add(symbol_id)

        crate_name = symbol.get("crate_name")
        if not isinstance(crate_name, str) or not crate_name.strip():
            errors.append(f"symbol_inventory[{idx}].crate_name must be non-empty string")
            continue
        observed_crates.add(crate_name)

        module_path = symbol.get("module_path")
        ensure_path(module_path, f"symbol_inventory[{idx}].module_path", errors)

        line = symbol.get("line")
        if not isinstance(line, int) or line < 1:
            errors.append(f"symbol_inventory[{idx}].line must be integer >= 1")

        visibility = symbol.get("visibility")
        if visibility not in {"public", "internal"}:
            errors.append(
                f"symbol_inventory[{idx}].visibility must be `public` or `internal`, got `{visibility}`"
            )
        elif visibility == "public":
            public_count += 1
        else:
            internal_count += 1

        api_surface = symbol.get("api_surface")
        if api_surface not in {"public_contract", "internal_impl"}:
            errors.append(
                "symbol_inventory[{idx}].api_surface must be `public_contract` or `internal_impl`".format(
                    idx=idx
                )
            )

        regression_risk = symbol.get("regression_risk")
        if regression_risk not in {"high", "medium", "low"}:
            errors.append(
                f"symbol_inventory[{idx}].regression_risk must be high|medium|low, got `{regression_risk}`"
            )
        if regression_risk == "high":
            high_ids.add(symbol_id)

        test_bindings = symbol.get("test_bindings")
        if not isinstance(test_bindings, list) or not test_bindings:
            errors.append(f"symbol_inventory[{idx}].test_bindings must be non-empty list")

        replay_command = symbol.get("replay_command")
        if not isinstance(replay_command, str) or not replay_command.strip():
            errors.append(f"symbol_inventory[{idx}].replay_command must be non-empty string")
        elif "rch exec --" not in replay_command:
            errors.append(f"symbol_inventory[{idx}].replay_command must use rch offload")

    expected_crates = workspace_crate_set()
    if observed_crates != expected_crates:
        errors.append(
            "symbol_inventory crate coverage mismatch: "
            f"expected={sorted(expected_crates)} observed={sorted(observed_crates)}"
        )

    high_symbols = artifact.get("high_regression_symbols")
    if not isinstance(high_symbols, list) or not high_symbols:
        errors.append("high_regression_symbols must be non-empty list")
        high_symbols = []
    observed_high_ids: set[str] = set()
    for idx, row in enumerate(high_symbols):
        if not isinstance(row, dict):
            errors.append(f"high_regression_symbols[{idx}] must be object")
            continue
        symbol_id = row.get("symbol_id")
        if not isinstance(symbol_id, str):
            errors.append(f"high_regression_symbols[{idx}].symbol_id must be string")
            continue
        if symbol_id not in symbol_ids:
            errors.append(f"high_regression_symbols[{idx}] unknown symbol_id `{symbol_id}`")
        observed_high_ids.add(symbol_id)

    if observed_high_ids != high_ids:
        errors.append(
            "high_regression_symbols mismatch computed high-risk symbol set: "
            f"expected={len(high_ids)} observed={len(observed_high_ids)}"
        )

    risk_notes = artifact.get("risk_notes")
    if not isinstance(risk_notes, list) or not risk_notes:
        errors.append("risk_notes must be non-empty list")
        risk_notes = []
    risk_note_ids: set[str] = set()
    for idx, note in enumerate(risk_notes):
        if not isinstance(note, dict):
            errors.append(f"risk_notes[{idx}] must be object")
            continue
        ensure_keys(note, schema["required_risk_note_keys"], f"risk_notes[{idx}]", errors)
        symbol_id = note.get("symbol_id")
        if symbol_id not in observed_high_ids:
            errors.append(f"risk_notes[{idx}] references unknown high-risk symbol `{symbol_id}`")
        note_id = note.get("note_id")
        if isinstance(note_id, str):
            if note_id in risk_note_ids:
                errors.append(f"duplicate risk note_id `{note_id}`")
            risk_note_ids.add(note_id)
    if len(risk_notes) != len(observed_high_ids):
        errors.append("risk_notes count must match high_regression_symbols count")

    if isinstance(summary, dict):
        expected_total = len(symbol_ids)
        if summary.get("symbol_count_total") != expected_total:
            errors.append("census_summary.symbol_count_total mismatch symbol_inventory size")
        if summary.get("public_symbol_count") != public_count:
            errors.append("census_summary.public_symbol_count mismatch observed public count")
        if summary.get("internal_symbol_count") != internal_count:
            errors.append("census_summary.internal_symbol_count mismatch observed internal count")
        if summary.get("high_regression_count") != len(high_ids):
            errors.append("census_summary.high_regression_count mismatch observed high-risk count")
        if summary.get("workspace_crate_count") != len(expected_crates):
            errors.append("census_summary.workspace_crate_count mismatch workspace crate count")

    alien = artifact.get("alien_uplift_contract_card")
    if isinstance(alien, dict):
        ev_score = alien.get("ev_score")
        if not isinstance(ev_score, (int, float)) or float(ev_score) < 2.0:
            errors.append("alien_uplift_contract_card.ev_score must be >= 2.0")
        baseline_comparator = alien.get("baseline_comparator")
        if not isinstance(baseline_comparator, str) or not baseline_comparator.strip():
            errors.append("alien_uplift_contract_card.baseline_comparator must be non-empty string")
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
        ensure_path(optimization.get("evidence_path", ""), "optimization_lever_policy.evidence_path", errors)
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
        "report_id": "doc-pass-02-symbol-api-census-validation-v1",
        "artifact_path": args.artifact,
        "ready": len(errors) == 0,
        "error_count": len(errors),
        "errors": errors,
        "summary": {
            "symbol_count": len(symbol_ids),
            "family_count": len(families),
            "high_risk_count": len(high_ids),
            "risk_note_count": len(risk_notes),
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
