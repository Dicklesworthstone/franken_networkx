#!/usr/bin/env python3
"""Validate E2E scenario matrix + oracle contract artifact."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = REPO_ROOT / "crates/fnx-conformance/fixtures"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def ensure_keys(payload: dict[str, Any], keys: list[str], ctx: str, errors: list[str]) -> None:
    for key in keys:
        if key not in payload:
            errors.append(f"{ctx} missing key `{key}`")


def ensure_rel_path(path: str, ctx: str, errors: list[str]) -> None:
    if not isinstance(path, str) or not path:
        errors.append(f"{ctx} must be a non-empty path string")
        return
    abs_path = REPO_ROOT / path
    if not abs_path.exists():
        errors.append(f"{ctx} path does not exist: {path}")


def fixture_inventory() -> list[str]:
    return [
        path.relative_to(FIXTURE_ROOT).as_posix()
        for path in sorted(FIXTURE_ROOT.rglob("*.json"))
        if path.name != "smoke_case.json"
    ]


def validate_path(
    *,
    journey_id: str,
    path_name: str,
    expected_mode: str,
    row: dict[str, Any],
    schema: dict[str, Any],
    fixture_set: set[str],
    failure_class_set: set[str],
    errors: list[str],
) -> set[str]:
    ensure_keys(row, schema["required_path_keys"], f"{journey_id}.{path_name}", errors)
    observed_mode = row.get("mode")
    if observed_mode != expected_mode:
        errors.append(
            f"{journey_id}.{path_name}.mode must be `{expected_mode}` but was `{observed_mode}`"
        )
    if row.get("mode_strategy") not in {"native_fixture", "mode_override_fixture"}:
        errors.append(
            f"{journey_id}.{path_name}.mode_strategy must be native_fixture or mode_override_fixture"
        )

    fixture_id = row.get("fixture_id")
    if not isinstance(fixture_id, str) or fixture_id not in fixture_set:
        errors.append(f"{journey_id}.{path_name}.fixture_id references unknown fixture `{fixture_id}`")

    fixture_ids = row.get("fixture_ids")
    if not isinstance(fixture_ids, list) or not fixture_ids:
        errors.append(f"{journey_id}.{path_name}.fixture_ids must be non-empty list")
        fixture_ids = []
    for fixture in fixture_ids:
        if not isinstance(fixture, str):
            errors.append(f"{journey_id}.{path_name}.fixture_ids entries must be strings")
            continue
        if fixture not in fixture_set:
            errors.append(f"{journey_id}.{path_name}.fixture_ids has unknown fixture `{fixture}`")
    if isinstance(fixture_id, str) and fixture_ids and fixture_id not in fixture_ids:
        errors.append(f"{journey_id}.{path_name}.fixture_id must be included in fixture_ids")

    seed = row.get("deterministic_seed")
    if not isinstance(seed, int) or seed < 0:
        errors.append(f"{journey_id}.{path_name}.deterministic_seed must be non-negative integer")

    replay_command = row.get("replay_command")
    if not isinstance(replay_command, str) or replay_command.strip() == "":
        errors.append(f"{journey_id}.{path_name}.replay_command must be non-empty string")
    else:
        if isinstance(fixture_id, str) and f"--fixture {fixture_id}" not in replay_command:
            errors.append(
                f"{journey_id}.{path_name}.replay_command must include --fixture {fixture_id}"
            )
        if f"--mode {expected_mode}" not in replay_command:
            errors.append(
                f"{journey_id}.{path_name}.replay_command must include --mode {expected_mode}"
            )

    steps = row.get("step_contract")
    if not isinstance(steps, list) or not steps:
        errors.append(f"{journey_id}.{path_name}.step_contract must be non-empty list")
        steps = []
    step_ids: set[str] = set()
    for step in steps:
        if not isinstance(step, dict):
            errors.append(f"{journey_id}.{path_name}.step_contract entries must be objects")
            continue
        ensure_keys(step, schema["required_step_keys"], f"{journey_id}.{path_name}.step", errors)
        step_id = step.get("step_id")
        if not isinstance(step_id, str) or not step_id:
            errors.append(f"{journey_id}.{path_name}.step.step_id must be non-empty string")
        elif step_id in step_ids:
            errors.append(f"{journey_id}.{path_name}.step_id values must be unique")
        else:
            step_ids.add(step_id)
        expected_outputs = step.get("expected_outputs")
        if not isinstance(expected_outputs, list) or not expected_outputs:
            errors.append(f"{journey_id}.{path_name}.step.expected_outputs must be non-empty list")
        else:
            for expected_ref in expected_outputs:
                if not isinstance(expected_ref, str) or not expected_ref.startswith("expected."):
                    errors.append(
                        f"{journey_id}.{path_name}.step.expected_outputs entries must start with `expected.`"
                    )
        tie_break = step.get("tie_break_behavior")
        if not isinstance(tie_break, str) or tie_break.strip() == "":
            errors.append(f"{journey_id}.{path_name}.step.tie_break_behavior must be non-empty")
        step_failure_classes = step.get("failure_classes")
        if not isinstance(step_failure_classes, list) or not step_failure_classes:
            errors.append(f"{journey_id}.{path_name}.step.failure_classes must be non-empty list")
        else:
            for failure_class in step_failure_classes:
                if failure_class not in failure_class_set:
                    errors.append(
                        f"{journey_id}.{path_name}.step.failure_classes unknown class `{failure_class}`"
                    )

    assertions = row.get("oracle_assertions")
    if not isinstance(assertions, list) or not assertions:
        errors.append(f"{journey_id}.{path_name}.oracle_assertions must be non-empty list")
        assertions = []
    for assertion in assertions:
        if not isinstance(assertion, dict):
            errors.append(f"{journey_id}.{path_name}.oracle_assertions entries must be objects")
            continue
        ensure_keys(
            assertion,
            schema["required_oracle_assertion_keys"],
            f"{journey_id}.{path_name}.oracle_assertion",
            errors,
        )
        expected_ref = assertion.get("expected_ref")
        if not isinstance(expected_ref, str) or not expected_ref.startswith("expected."):
            errors.append(
                f"{journey_id}.{path_name}.oracle_assertion.expected_ref must start with `expected.`"
            )
        failure_class = assertion.get("failure_class")
        if failure_class not in failure_class_set:
            errors.append(
                f"{journey_id}.{path_name}.oracle_assertion.failure_class unknown class `{failure_class}`"
            )

    path_failure_classes = row.get("failure_classes")
    if not isinstance(path_failure_classes, list) or not path_failure_classes:
        errors.append(f"{journey_id}.{path_name}.failure_classes must be non-empty list")
    else:
        for failure_class in path_failure_classes:
            if failure_class not in failure_class_set:
                errors.append(
                    f"{journey_id}.{path_name}.failure_classes unknown class `{failure_class}`"
                )

    return {fixture for fixture in fixture_ids if isinstance(fixture, str)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--artifact",
        default="artifacts/e2e/v1/e2e_scenario_matrix_oracle_contract_v1.json",
        help="Path to artifact JSON",
    )
    parser.add_argument(
        "--schema",
        default="artifacts/e2e/schema/v1/e2e_scenario_matrix_oracle_contract_schema_v1.json",
        help="Path to schema JSON",
    )
    parser.add_argument("--output", default="", help="Optional validation report path")
    args = parser.parse_args()

    artifact_path = REPO_ROOT / args.artifact
    schema_path = REPO_ROOT / args.schema
    artifact = load_json(artifact_path)
    schema = load_json(schema_path)
    errors: list[str] = []

    ensure_keys(artifact, schema["required_top_level_keys"], "artifact", errors)

    journey_summary = artifact.get("journey_summary")
    if not isinstance(journey_summary, dict):
        errors.append("journey_summary must be object")
        journey_summary = {}

    seed_policy = artifact.get("deterministic_seed_policy")
    if isinstance(seed_policy, dict):
        ensure_keys(
            seed_policy,
            schema["required_seed_policy_keys"],
            "deterministic_seed_policy",
            errors,
        )
    else:
        errors.append("deterministic_seed_policy must be object")

    replay_contract = artifact.get("replay_metadata_contract")
    if isinstance(replay_contract, dict):
        ensure_keys(
            replay_contract,
            schema["required_replay_contract_keys"],
            "replay_metadata_contract",
            errors,
        )
        schema_refs = replay_contract.get("schema_refs")
        if not isinstance(schema_refs, list) or not schema_refs:
            errors.append("replay_metadata_contract.schema_refs must be non-empty list")
            schema_refs = []
        for required_ref in schema["required_replay_schema_refs"]:
            if required_ref not in schema_refs:
                errors.append(
                    f"replay_metadata_contract.schema_refs missing required ref `{required_ref}`"
                )
        for schema_ref in schema_refs:
            ensure_rel_path(schema_ref, "replay_metadata_contract.schema_refs[]", errors)
    else:
        errors.append("replay_metadata_contract must be object")

    taxonomy = artifact.get("failure_class_taxonomy")
    if not isinstance(taxonomy, list) or not taxonomy:
        errors.append("failure_class_taxonomy must be non-empty list")
        taxonomy = []
    failure_classes = {
        row.get("failure_class")
        for row in taxonomy
        if isinstance(row, dict) and isinstance(row.get("failure_class"), str)
    }
    for required_class in schema["required_failure_classes"]:
        if required_class not in failure_classes:
            errors.append(f"failure_class_taxonomy missing required class `{required_class}`")

    fixture_set = set(fixture_inventory())
    journeys = artifact.get("journeys")
    if not isinstance(journeys, list) or not journeys:
        errors.append("journeys must be non-empty list")
        journeys = []

    covered_fixture_ids: set[str] = set()
    journey_ids: set[str] = set()
    for journey in journeys:
        if not isinstance(journey, dict):
            errors.append("journey entry must be object")
            continue
        ensure_keys(journey, schema["required_journey_keys"], "journey", errors)
        journey_id = journey.get("journey_id")
        if not isinstance(journey_id, str) or not journey_id:
            errors.append("journey.journey_id must be non-empty string")
            continue
        if journey_id in journey_ids:
            errors.append(f"duplicate journey_id `{journey_id}`")
        journey_ids.add(journey_id)
        packet_id = journey.get("packet_id")
        if not isinstance(packet_id, str) or not packet_id.startswith("FNX-P2C-"):
            errors.append(f"{journey_id}.packet_id must start with `FNX-P2C-`")

        strict_path = journey.get("strict_path")
        if not isinstance(strict_path, dict):
            errors.append(f"{journey_id}.strict_path must be object")
        else:
            covered_fixture_ids.update(
                validate_path(
                    journey_id=journey_id,
                    path_name="strict_path",
                    expected_mode="strict",
                    row=strict_path,
                    schema=schema,
                    fixture_set=fixture_set,
                    failure_class_set=failure_classes,
                    errors=errors,
                )
            )

        hardened_path = journey.get("hardened_path")
        if not isinstance(hardened_path, dict):
            errors.append(f"{journey_id}.hardened_path must be object")
        else:
            covered_fixture_ids.update(
                validate_path(
                    journey_id=journey_id,
                    path_name="hardened_path",
                    expected_mode="hardened",
                    row=hardened_path,
                    schema=schema,
                    fixture_set=fixture_set,
                    failure_class_set=failure_classes,
                    errors=errors,
                )
            )

    coverage = artifact.get("coverage_manifest")
    if isinstance(coverage, dict):
        ensure_keys(coverage, schema["required_coverage_keys"], "coverage_manifest", errors)
        manifest_inventory = coverage.get("fixture_inventory")
        if manifest_inventory != sorted(fixture_set):
            errors.append("coverage_manifest.fixture_inventory must match fixture file inventory")
        manifest_covered = coverage.get("covered_fixture_ids")
        if not isinstance(manifest_covered, list):
            errors.append("coverage_manifest.covered_fixture_ids must be list")
            manifest_covered = []
        if sorted(set(manifest_covered)) != sorted(covered_fixture_ids):
            errors.append("coverage_manifest.covered_fixture_ids drift from journey path coverage")
        manifest_uncovered = coverage.get("uncovered_fixture_ids")
        expected_uncovered = sorted(fixture_set - covered_fixture_ids)
        if manifest_uncovered != expected_uncovered:
            errors.append("coverage_manifest.uncovered_fixture_ids mismatch expected uncovered list")
    else:
        errors.append("coverage_manifest must be object")
        expected_uncovered = sorted(fixture_set - covered_fixture_ids)

    if journey_summary:
        if journey_summary.get("journey_count") != len(journeys):
            errors.append("journey_summary.journey_count mismatch")
        if journey_summary.get("strict_journey_count") != len(journeys):
            errors.append("journey_summary.strict_journey_count mismatch")
        if journey_summary.get("hardened_journey_count") != len(journeys):
            errors.append("journey_summary.hardened_journey_count mismatch")
        if journey_summary.get("fixture_inventory_count") != len(fixture_set):
            errors.append("journey_summary.fixture_inventory_count mismatch")
        if journey_summary.get("covered_fixture_count") != len(covered_fixture_ids):
            errors.append("journey_summary.covered_fixture_count mismatch")
        if journey_summary.get("uncovered_fixture_count") != len(expected_uncovered):
            errors.append("journey_summary.uncovered_fixture_count mismatch")

    profile_artifacts = artifact.get("profile_first_artifacts")
    if isinstance(profile_artifacts, dict):
        ensure_keys(
            profile_artifacts,
            schema["required_profile_artifact_keys"],
            "profile_first_artifacts",
            errors,
        )
        for key in schema["required_profile_artifact_keys"]:
            ensure_rel_path(profile_artifacts.get(key, ""), f"profile_first_artifacts.{key}", errors)
    else:
        errors.append("profile_first_artifacts must be object")

    for index, path in enumerate(artifact.get("isomorphism_proof_artifacts", [])):
        ensure_rel_path(path, f"isomorphism_proof_artifacts[{index}]", errors)
    for index, path in enumerate(artifact.get("structured_logging_evidence", [])):
        ensure_rel_path(path, f"structured_logging_evidence[{index}]", errors)

    alien = artifact.get("alien_uplift_contract_card")
    if isinstance(alien, dict):
        ev_score = alien.get("ev_score")
        if not isinstance(ev_score, (int, float)) or ev_score < 2.0:
            errors.append("alien_uplift_contract_card.ev_score must be >= 2.0")
    else:
        errors.append("alien_uplift_contract_card must be object")

    report = {
        "schema_version": "1.0.0",
        "report_id": "e2e-scenario-matrix-oracle-contract-validation-v1",
        "artifact_path": args.artifact,
        "ready": len(errors) == 0,
        "error_count": len(errors),
        "errors": errors,
        "summary": {
            "journey_count": len(journeys),
            "fixture_inventory_count": len(fixture_set),
            "covered_fixture_count": len(covered_fixture_ids),
            "uncovered_fixture_count": len(expected_uncovered),
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
