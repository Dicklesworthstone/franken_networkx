#!/usr/bin/env python3
"""Validate machine-auditable Phase2C essence extraction ledger coverage."""

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


def ensure_path(path_str: str, ctx: str, errors: list[str]) -> None:
    if not isinstance(path_str, str) or not path_str:
        errors.append(f"{ctx} must be a non-empty string path")
        return
    if not Path(path_str).exists():
        errors.append(f"{ctx} path does not exist: {path_str}")


def validate_packet_entry(
    entry: dict[str, Any],
    schema: dict[str, Any],
    packet_ids: set[str],
    errors: list[str],
) -> None:
    packet_id = entry.get("packet_id", "<unknown>")
    require_keys(entry, schema["required_packet_keys"], f"packet `{packet_id}`", errors)
    if packet_id == "<unknown>":
        return

    packet_ids.add(packet_id)

    for list_field in [
        "legacy_paths",
        "legacy_symbols",
        "excluded_scope",
        "oracle_tests",
        "performance_sentinels",
        "compatibility_risks",
        "isomorphism_proof_artifacts",
        "structured_logging_evidence",
    ]:
        values = ensure_list(entry.get(list_field), f"packet `{packet_id}` field `{list_field}`", errors)
        if not values:
            errors.append(f"packet `{packet_id}` field `{list_field}` must be non-empty")

    for path_field in ["performance_sentinels", "isomorphism_proof_artifacts", "structured_logging_evidence"]:
        for idx, value in enumerate(entry.get(path_field, [])):
            ensure_path(value, f"packet `{packet_id}` field `{path_field}`[{idx}]", errors)

    artifacts = entry.get("raptorq_artifacts")
    if isinstance(artifacts, dict):
        for key, path_str in artifacts.items():
            ensure_path(path_str, f"packet `{packet_id}` raptorq_artifacts.{key}", errors)
    else:
        errors.append(f"packet `{packet_id}` raptorq_artifacts must be an object")

    invariants = ensure_list(entry.get("invariants"), f"packet `{packet_id}` field `invariants`", errors)
    if not invariants:
        errors.append(f"packet `{packet_id}` must define at least one invariant")
    for inv in invariants:
        if not isinstance(inv, dict):
            errors.append(f"packet `{packet_id}` has non-object invariant row")
            continue
        require_keys(inv, schema["required_invariant_keys"], f"packet `{packet_id}` invariant", errors)
        hooks = inv.get("verification_hooks")
        if not isinstance(hooks, dict):
            errors.append(f"packet `{packet_id}` invariant verification_hooks must be object")
            continue
        for hook_key in schema["required_verification_hook_keys"]:
            hook_values = ensure_list(
                hooks.get(hook_key),
                f"packet `{packet_id}` invariant verification hook `{hook_key}`",
                errors,
            )
            if not hook_values:
                errors.append(
                    f"packet `{packet_id}` invariant verification hook `{hook_key}` must be non-empty"
                )

    alien = entry.get("alien_uplift_contract_card")
    if isinstance(alien, dict):
        require_keys(alien, schema["required_alien_card_keys"], f"packet `{packet_id}` alien card", errors)
        ev_score = alien.get("ev_score")
        if not isinstance(ev_score, (int, float)) or ev_score < 2.0:
            errors.append(f"packet `{packet_id}` alien card ev_score must be >= 2.0")
    else:
        errors.append(f"packet `{packet_id}` alien_uplift_contract_card must be an object")

    profile = entry.get("profile_first_artifacts")
    if isinstance(profile, dict):
        require_keys(
            profile,
            schema["required_profile_artifact_keys"],
            f"packet `{packet_id}` profile_first_artifacts",
            errors,
        )
        for key in schema["required_profile_artifact_keys"]:
            if key in profile:
                ensure_path(
                    profile[key],
                    f"packet `{packet_id}` profile_first_artifacts.{key}",
                    errors,
                )
    else:
        errors.append(f"packet `{packet_id}` profile_first_artifacts must be an object")

    runtime_contract = entry.get("decision_theoretic_runtime_contract")
    if isinstance(runtime_contract, dict):
        require_keys(
            runtime_contract,
            schema["required_runtime_contract_keys"],
            f"packet `{packet_id}` decision_theoretic_runtime_contract",
            errors,
        )
        for key in ["states", "actions"]:
            values = ensure_list(
                runtime_contract.get(key),
                f"packet `{packet_id}` decision_theoretic_runtime_contract.{key}",
                errors,
            )
            if not values:
                errors.append(
                    f"packet `{packet_id}` decision_theoretic_runtime_contract.{key} must be non-empty"
                )
    else:
        errors.append(f"packet `{packet_id}` decision_theoretic_runtime_contract must be object")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--ledger",
        default="artifacts/phase2c/essence_extraction_ledger_v1.json",
        help="Path to phase2c essence extraction ledger",
    )
    parser.add_argument(
        "--schema",
        default="artifacts/phase2c/schema/v1/essence_extraction_ledger_schema_v1.json",
        help="Path to essence extraction schema",
    )
    parser.add_argument(
        "--topology",
        default="artifacts/phase2c/packet_topology_v1.json",
        help="Path to packet topology manifest",
    )
    parser.add_argument(
        "--security-contract",
        default="artifacts/phase2c/schema/v1/security_compatibility_contract_schema_v1.json",
        help="Path to security compatibility contract schema",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Optional output path for validation report",
    )
    args = parser.parse_args()

    ledger = load_json(Path(args.ledger))
    schema = load_json(Path(args.schema))
    topology = load_json(Path(args.topology))
    security_contract = load_json(Path(args.security_contract))

    errors: list[str] = []
    require_keys(ledger, schema["required_top_level_keys"], "ledger", errors)

    packet_ids_from_ledger: set[str] = set()
    for entry in ensure_list(ledger.get("packets"), "ledger.packets", errors):
        if not isinstance(entry, dict):
            errors.append("ledger packet entry must be an object")
            continue
        validate_packet_entry(entry, schema, packet_ids_from_ledger, errors)

    topology_packets = {
        packet["packet_id"]
        for packet in ensure_list(topology.get("packets"), "topology.packets", errors)
        if isinstance(packet, dict) and "packet_id" in packet
    }
    missing_from_ledger = sorted(topology_packets.difference(packet_ids_from_ledger))
    missing_from_topology = sorted(packet_ids_from_ledger.difference(topology_packets))
    if missing_from_ledger:
        errors.append(f"ledger missing packets from topology: {missing_from_ledger}")
    if missing_from_topology:
        errors.append(f"ledger contains packets not in topology: {missing_from_topology}")

    security_packets = set(security_contract.get("required_packet_ids", []))
    security_missing = sorted(security_packets.difference(packet_ids_from_ledger))
    if security_missing:
        errors.append(f"ledger missing security-contract packets: {security_missing}")

    report = {
        "schema_version": "1.0.0",
        "ledger_id": ledger.get("ledger_id", "<unknown>"),
        "ready": len(errors) == 0,
        "error_count": len(errors),
        "errors": errors,
        "summary": {
            "packet_count": len(packet_ids_from_ledger),
            "topology_packet_count": len(topology_packets),
            "security_packet_count": len(security_packets),
        },
    }

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(report, indent=2))
    return 0 if report["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
