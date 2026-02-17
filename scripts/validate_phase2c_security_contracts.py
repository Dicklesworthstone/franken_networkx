#!/usr/bin/env python3
"""Validate Phase2C security/compatibility threat matrix and hardened allowlist."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def require_keys(
    payload: dict[str, Any],
    required_keys: list[str],
    context: str,
    errors: list[str],
) -> None:
    for key in required_keys:
        if key not in payload:
            errors.append(f"{context} missing key `{key}`")


def ensure_list(value: Any, context: str, errors: list[str]) -> list[Any]:
    if isinstance(value, list):
        return value
    errors.append(f"{context} must be a list")
    return []


P2C003_MATRIX_EXTRA_KEYS = [
    "compatibility_boundary",
    "adversarial_fixture_hooks",
    "crash_triage_taxonomy",
    "hardened_allowlisted_categories",
]
P2C003_ALLOWLIST_EXTRA_KEYS = [
    "compatibility_boundary_matrix",
    "fail_closed_default",
    "threat_taxonomy",
]
P2C003_BOUNDARY_ROW_KEYS = [
    "boundary_id",
    "strict_parity_obligation",
    "hardened_allowlisted_deviation_categories",
    "fail_closed_default",
    "evidence_hooks",
]


def validate_matrix(
    contract: dict[str, Any],
    matrix: dict[str, Any],
    errors: list[str],
) -> dict[str, Any]:
    start_errors = len(errors)
    require_keys(matrix, contract["required_matrix_keys"], "matrix", errors)
    if len(errors) > start_errors:
        return {"packet_count": 0, "entry_count": 0}

    if matrix["contract_id"] != contract["contract_id"]:
        errors.append(
            "matrix contract_id mismatch: "
            f"{matrix['contract_id']} != {contract['contract_id']}"
        )

    required_packets = set(contract["required_packet_ids"])
    packet_rows = ensure_list(matrix["packet_families"], "matrix.packet_families", errors)
    packet_seen: set[str] = set()

    all_threat_classes = set(contract["required_threat_classes"]) | set(
        contract["optional_threat_classes"]
    )
    all_allowlist_categories = set(contract["hardened_deviation_allowlist_categories"])
    entry_required_keys = contract["matrix_entry_required_keys"]
    packet_required_keys = contract["matrix_packet_required_keys"]

    entry_count = 0
    for row in packet_rows:
        if not isinstance(row, dict):
            errors.append("matrix packet row must be an object")
            continue
        require_keys(row, packet_required_keys, "matrix packet row", errors)
        if "packet_id" not in row or "threats" not in row:
            continue

        packet_id = row["packet_id"]
        packet_seen.add(packet_id)
        if packet_id not in required_packets:
            errors.append(f"matrix has unknown packet_id `{packet_id}`")

        threat_rows = ensure_list(
            row["threats"], f"matrix packet `{packet_id}` threats", errors
        )
        if not threat_rows:
            errors.append(f"matrix packet `{packet_id}` has no threat rows")
            continue

        required_classes = set(contract["required_threat_classes"])
        seen_classes: set[str] = set()

        for entry in threat_rows:
            if not isinstance(entry, dict):
                errors.append(f"matrix packet `{packet_id}` has non-object threat row")
                continue
            require_keys(entry, entry_required_keys, f"matrix packet `{packet_id}` threat", errors)
            if "threat_class" not in entry:
                continue

            entry_count += 1
            threat_class = entry["threat_class"]
            seen_classes.add(threat_class)
            if threat_class not in all_threat_classes:
                errors.append(
                    f"matrix packet `{packet_id}` has unknown threat_class `{threat_class}`"
                )

            mitigations = entry.get("mitigations")
            if not isinstance(mitigations, list) or not mitigations:
                errors.append(
                    f"matrix packet `{packet_id}` threat `{threat_class}` must have non-empty mitigations list"
                )

            strict_response = entry.get("strict_mode_response", "")
            if isinstance(strict_response, str) and "fail-closed" not in strict_response.lower():
                errors.append(
                    f"matrix packet `{packet_id}` threat `{threat_class}` strict response must state fail-closed behavior"
                )

            if packet_id == "FNX-P2C-003":
                require_keys(
                    entry,
                    P2C003_MATRIX_EXTRA_KEYS,
                    f"matrix packet `{packet_id}` threat `{threat_class}`",
                    errors,
                )
                boundary = entry.get("compatibility_boundary")
                if not isinstance(boundary, str) or not boundary.strip():
                    errors.append(
                        f"matrix packet `{packet_id}` threat `{threat_class}` compatibility_boundary must be non-empty string"
                    )
                hooks = ensure_list(
                    entry.get("adversarial_fixture_hooks"),
                    f"matrix packet `{packet_id}` threat `{threat_class}` adversarial_fixture_hooks",
                    errors,
                )
                if not hooks:
                    errors.append(
                        f"matrix packet `{packet_id}` threat `{threat_class}` adversarial_fixture_hooks must be non-empty"
                    )
                triage = ensure_list(
                    entry.get("crash_triage_taxonomy"),
                    f"matrix packet `{packet_id}` threat `{threat_class}` crash_triage_taxonomy",
                    errors,
                )
                if not triage:
                    errors.append(
                        f"matrix packet `{packet_id}` threat `{threat_class}` crash_triage_taxonomy must be non-empty"
                    )
                allowlisted_categories = ensure_list(
                    entry.get("hardened_allowlisted_categories"),
                    f"matrix packet `{packet_id}` threat `{threat_class}` hardened_allowlisted_categories",
                    errors,
                )
                if not allowlisted_categories:
                    errors.append(
                        f"matrix packet `{packet_id}` threat `{threat_class}` hardened_allowlisted_categories must be non-empty"
                    )
                for category in allowlisted_categories:
                    if not isinstance(category, str):
                        errors.append(
                            f"matrix packet `{packet_id}` threat `{threat_class}` hardened category `{category}` is not a string"
                        )
                        continue
                    if category not in all_allowlist_categories:
                        errors.append(
                            f"matrix packet `{packet_id}` threat `{threat_class}` uses unknown hardened category `{category}`"
                        )

        missing_required_classes = sorted(required_classes.difference(seen_classes))
        if missing_required_classes:
            errors.append(
                f"matrix packet `{packet_id}` missing required threat classes: {missing_required_classes}"
            )

    missing_packets = sorted(required_packets.difference(packet_seen))
    extra_packets = sorted(packet_seen.difference(required_packets))
    if missing_packets:
        errors.append(f"matrix missing required packet_ids: {missing_packets}")
    if extra_packets:
        errors.append(f"matrix includes unknown packet_ids: {extra_packets}")

    return {"packet_count": len(packet_seen), "entry_count": entry_count}


def validate_allowlist(
    contract: dict[str, Any],
    allowlist: dict[str, Any],
    errors: list[str],
) -> dict[str, Any]:
    start_errors = len(errors)
    require_keys(allowlist, contract["required_allowlist_keys"], "allowlist", errors)
    if len(errors) > start_errors:
        return {"packet_count": 0, "category_count": 0}

    if allowlist["contract_id"] != contract["contract_id"]:
        errors.append(
            "allowlist contract_id mismatch: "
            f"{allowlist['contract_id']} != {contract['contract_id']}"
        )

    expected_categories = set(contract["hardened_deviation_allowlist_categories"])
    category_rows = ensure_list(allowlist["categories"], "allowlist.categories", errors)

    category_required_keys = contract["allowlist_category_required_keys"]
    category_names: set[str] = set()

    for category_row in category_rows:
        if not isinstance(category_row, dict):
            errors.append("allowlist category row must be an object")
            continue
        require_keys(category_row, category_required_keys, "allowlist category row", errors)
        if "category" not in category_row:
            continue
        category = category_row["category"]
        category_names.add(category)
        if category not in expected_categories:
            errors.append(f"allowlist has unknown category `{category}`")

        strict_allowed = category_row.get("strict_mode_allowed")
        hardened_allowed = category_row.get("hardened_mode_allowed")
        if strict_allowed not in (True, False):
            errors.append(f"allowlist category `{category}` strict_mode_allowed must be boolean")
        if hardened_allowed not in (True, False):
            errors.append(
                f"allowlist category `{category}` hardened_mode_allowed must be boolean"
            )
        if strict_allowed:
            errors.append(
                f"allowlist category `{category}` must not be strict-mode allowed"
            )
        if not hardened_allowed:
            errors.append(
                f"allowlist category `{category}` must be hardened-mode allowed"
            )

    missing_categories = sorted(expected_categories.difference(category_names))
    extra_categories = sorted(category_names.difference(expected_categories))
    if missing_categories:
        errors.append(f"allowlist missing required categories: {missing_categories}")
    if extra_categories:
        errors.append(f"allowlist includes unknown categories: {extra_categories}")

    required_packets = set(contract["required_packet_ids"])
    packet_rows = ensure_list(allowlist["packet_allowlist"], "allowlist.packet_allowlist", errors)
    packet_required_keys = contract["allowlist_packet_required_keys"]
    packet_seen: set[str] = set()

    for row in packet_rows:
        if not isinstance(row, dict):
            errors.append("allowlist packet row must be an object")
            continue
        require_keys(row, packet_required_keys, "allowlist packet row", errors)
        if "packet_id" not in row or "allowed_categories" not in row:
            continue
        packet_id = row["packet_id"]
        packet_seen.add(packet_id)
        if packet_id not in required_packets:
            errors.append(f"allowlist has unknown packet_id `{packet_id}`")

        allowed_categories = ensure_list(
            row["allowed_categories"],
            f"allowlist packet `{packet_id}` categories",
            errors,
        )
        if not allowed_categories:
            errors.append(f"allowlist packet `{packet_id}` has no allowed categories")
            continue

        seen_local: set[str] = set()
        for category in allowed_categories:
            if not isinstance(category, str):
                errors.append(
                    f"allowlist packet `{packet_id}` category `{category}` is not a string"
                )
                continue
            if category in seen_local:
                errors.append(
                    f"allowlist packet `{packet_id}` duplicates category `{category}`"
                )
            seen_local.add(category)
            if category not in expected_categories:
                errors.append(
                    f"allowlist packet `{packet_id}` uses unknown category `{category}`"
                )

        if packet_id == "FNX-P2C-003":
            require_keys(
                row,
                P2C003_ALLOWLIST_EXTRA_KEYS,
                f"allowlist packet `{packet_id}`",
                errors,
            )
            fail_closed_default = row.get("fail_closed_default")
            if fail_closed_default != "unknown_incompatible_feature":
                errors.append(
                    f"allowlist packet `{packet_id}` fail_closed_default must be `unknown_incompatible_feature`"
                )

            threat_taxonomy = ensure_list(
                row.get("threat_taxonomy"),
                f"allowlist packet `{packet_id}` threat_taxonomy",
                errors,
            )
            for threat_value in threat_taxonomy:
                if not isinstance(threat_value, str):
                    errors.append(
                        f"allowlist packet `{packet_id}` threat_taxonomy value `{threat_value}` is not a string"
                    )
            for threat_class in contract["required_threat_classes"]:
                if threat_class not in threat_taxonomy:
                    errors.append(
                        f"allowlist packet `{packet_id}` threat_taxonomy missing required class `{threat_class}`"
                    )

            boundary_rows = ensure_list(
                row.get("compatibility_boundary_matrix"),
                f"allowlist packet `{packet_id}` compatibility_boundary_matrix",
                errors,
            )
            if not boundary_rows:
                errors.append(
                    f"allowlist packet `{packet_id}` compatibility_boundary_matrix must be non-empty"
                )
            boundary_ids_seen: set[str] = set()
            for boundary_row in boundary_rows:
                if not isinstance(boundary_row, dict):
                    errors.append(
                        f"allowlist packet `{packet_id}` compatibility boundary row must be an object"
                    )
                    continue
                require_keys(
                    boundary_row,
                    P2C003_BOUNDARY_ROW_KEYS,
                    f"allowlist packet `{packet_id}` compatibility boundary row",
                    errors,
                )
                boundary_id = boundary_row.get("boundary_id")
                if not isinstance(boundary_id, str) or not boundary_id:
                    errors.append(
                        f"allowlist packet `{packet_id}` compatibility boundary row has invalid boundary_id"
                    )
                elif boundary_id in boundary_ids_seen:
                    errors.append(
                        f"allowlist packet `{packet_id}` duplicates compatibility boundary_id `{boundary_id}`"
                    )
                else:
                    boundary_ids_seen.add(boundary_id)

                deviation_categories = ensure_list(
                    boundary_row.get("hardened_allowlisted_deviation_categories"),
                    f"allowlist packet `{packet_id}` boundary `{boundary_id}` hardened_allowlisted_deviation_categories",
                    errors,
                )
                if not deviation_categories:
                    errors.append(
                        f"allowlist packet `{packet_id}` boundary `{boundary_id}` must include at least one hardened category"
                    )
                for category in deviation_categories:
                    if not isinstance(category, str):
                        errors.append(
                            f"allowlist packet `{packet_id}` boundary `{boundary_id}` category `{category}` is not a string"
                        )
                        continue
                    if category not in expected_categories:
                        errors.append(
                            f"allowlist packet `{packet_id}` boundary `{boundary_id}` uses unknown hardened category `{category}`"
                        )

                evidence_hooks = ensure_list(
                    boundary_row.get("evidence_hooks"),
                    f"allowlist packet `{packet_id}` boundary `{boundary_id}` evidence_hooks",
                    errors,
                )
                if not evidence_hooks:
                    errors.append(
                        f"allowlist packet `{packet_id}` boundary `{boundary_id}` evidence_hooks must be non-empty"
                    )

    missing_packets = sorted(required_packets.difference(packet_seen))
    extra_packets = sorted(packet_seen.difference(required_packets))
    if missing_packets:
        errors.append(f"allowlist missing required packet_ids: {missing_packets}")
    if extra_packets:
        errors.append(f"allowlist includes unknown packet_ids: {extra_packets}")

    return {"packet_count": len(packet_seen), "category_count": len(category_names)}


def validate_adversarial_manifest(
    contract: dict[str, Any],
    matrix: dict[str, Any],
    manifest: dict[str, Any],
    errors: list[str],
) -> dict[str, Any]:
    start_errors = len(errors)
    require_keys(
        manifest,
        contract["required_adversarial_manifest_keys"],
        "adversarial_manifest",
        errors,
    )
    if len(errors) > start_errors:
        return {"class_count": 0, "mapping_count": 0}

    if manifest["contract_id"] != contract["contract_id"]:
        errors.append(
            "adversarial_manifest contract_id mismatch: "
            f"{manifest['contract_id']} != {contract['contract_id']}"
        )

    seed_policy = manifest["seed_policy"]
    if not isinstance(seed_policy, dict):
        errors.append("adversarial_manifest.seed_policy must be an object")
    else:
        require_keys(
            seed_policy,
            contract["adversarial_manifest_seed_policy_required_keys"],
            "adversarial_manifest.seed_policy",
            errors,
        )
        if seed_policy.get("deterministic") is not True:
            errors.append("adversarial_manifest.seed_policy.deterministic must be true")
        replay_fields = seed_policy.get("replay_metadata_fields")
        if not isinstance(replay_fields, list) or not replay_fields:
            errors.append(
                "adversarial_manifest.seed_policy.replay_metadata_fields must be a non-empty list"
            )

    matrix_rows = ensure_list(matrix.get("packet_families", []), "matrix.packet_families", errors)
    matrix_pairs: dict[tuple[str, str], str] = {}
    matrix_classes: set[str] = set()
    for packet_row in matrix_rows:
        if not isinstance(packet_row, dict):
            continue
        packet_id = packet_row.get("packet_id")
        threat_rows = packet_row.get("threats", [])
        if not isinstance(packet_id, str):
            continue
        if not isinstance(threat_rows, list):
            continue
        for threat_row in threat_rows:
            if not isinstance(threat_row, dict):
                continue
            threat_class = threat_row.get("threat_class")
            drift_gate = threat_row.get("drift_gate")
            if not isinstance(threat_class, str) or not isinstance(drift_gate, str):
                continue
            matrix_classes.add(threat_class)
            matrix_pairs[(packet_id, threat_class)] = drift_gate

    taxonomy_rows = ensure_list(
        manifest["threat_taxonomy"], "adversarial_manifest.threat_taxonomy", errors
    )
    entry_required_keys = contract["adversarial_manifest_entry_required_keys"]
    mapping_required_keys = contract["adversarial_manifest_mapping_required_keys"]

    seen_classes: set[str] = set()
    manifest_pairs: set[tuple[str, str]] = set()
    mapping_count = 0

    for taxonomy_row in taxonomy_rows:
        if not isinstance(taxonomy_row, dict):
            errors.append("adversarial_manifest.threat_taxonomy row must be an object")
            continue
        require_keys(
            taxonomy_row,
            entry_required_keys,
            "adversarial_manifest threat row",
            errors,
        )
        if "threat_class" not in taxonomy_row or "packet_gate_mappings" not in taxonomy_row:
            continue

        threat_class = taxonomy_row["threat_class"]
        seen_classes.add(threat_class)
        if threat_class not in matrix_classes:
            errors.append(
                f"adversarial_manifest includes unknown threat_class `{threat_class}`"
            )

        local_seed_policy = taxonomy_row.get("seed_policy")
        if not isinstance(local_seed_policy, dict):
            errors.append(
                f"adversarial_manifest threat `{threat_class}` seed_policy must be an object"
            )
        elif not isinstance(local_seed_policy.get("class_seed"), int):
            errors.append(
                f"adversarial_manifest threat `{threat_class}` seed_policy.class_seed must be integer"
            )

        mappings = ensure_list(
            taxonomy_row["packet_gate_mappings"],
            f"adversarial_manifest threat `{threat_class}` packet_gate_mappings",
            errors,
        )
        if not mappings:
            errors.append(
                f"adversarial_manifest threat `{threat_class}` must map to at least one packet gate"
            )
            continue

        for mapping_row in mappings:
            if not isinstance(mapping_row, dict):
                errors.append(
                    f"adversarial_manifest threat `{threat_class}` mapping row must be an object"
                )
                continue
            require_keys(
                mapping_row,
                mapping_required_keys,
                f"adversarial_manifest threat `{threat_class}` mapping",
                errors,
            )
            if "packet_id" not in mapping_row or "validation_gate" not in mapping_row:
                continue

            packet_id = mapping_row["packet_id"]
            validation_gate = mapping_row["validation_gate"]
            matrix_pair = (packet_id, threat_class)
            manifest_pairs.add(matrix_pair)
            mapping_count += 1

            if not isinstance(mapping_row.get("seed"), int):
                errors.append(
                    f"adversarial_manifest threat `{threat_class}` mapping `{packet_id}` seed must be integer"
                )

            expected_gate = matrix_pairs.get(matrix_pair)
            if expected_gate is None:
                errors.append(
                    f"adversarial_manifest mapping `{packet_id}` + `{threat_class}` is not present in threat matrix"
                )
            elif validation_gate != expected_gate:
                errors.append(
                    "adversarial_manifest gate mismatch for "
                    f"`{packet_id}` + `{threat_class}`: {validation_gate} != {expected_gate}"
                )

    missing_classes = sorted(matrix_classes.difference(seen_classes))
    extra_classes = sorted(seen_classes.difference(matrix_classes))
    if missing_classes:
        errors.append(
            f"adversarial_manifest missing threat classes present in matrix: {missing_classes}"
        )
    if extra_classes:
        errors.append(f"adversarial_manifest includes unknown threat classes: {extra_classes}")

    missing_pairs = sorted(matrix_pairs.keys() - manifest_pairs)
    extra_pairs = sorted(manifest_pairs - matrix_pairs.keys())
    if missing_pairs:
        compact = [f"{packet_id}:{threat_class}" for packet_id, threat_class in missing_pairs]
        errors.append(
            "adversarial_manifest missing packet/threat mappings required by matrix: "
            f"{compact}"
        )
    if extra_pairs:
        compact = [f"{packet_id}:{threat_class}" for packet_id, threat_class in extra_pairs]
        errors.append(
            "adversarial_manifest includes packet/threat mappings absent from matrix: "
            f"{compact}"
        )

    high_risk_raw = ensure_list(
        manifest["high_risk_classes"], "adversarial_manifest.high_risk_classes", errors
    )
    declared_high_risk = {value for value in high_risk_raw if isinstance(value, str)}
    if len(declared_high_risk) != len(high_risk_raw):
        errors.append("adversarial_manifest.high_risk_classes entries must all be strings")

    required_high_risk = set(contract["required_high_risk_threat_classes"])
    missing_high_risk = sorted(required_high_risk.difference(declared_high_risk))
    if missing_high_risk:
        errors.append(
            "adversarial_manifest missing required high-risk classes: "
            f"{missing_high_risk}"
        )

    return {"class_count": len(seen_classes), "mapping_count": mapping_count}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--contract",
        default="artifacts/phase2c/schema/v1/security_compatibility_contract_schema_v1.json",
        help="Path to security compatibility contract schema",
    )
    parser.add_argument(
        "--matrix",
        default="artifacts/phase2c/security/v1/security_compatibility_threat_matrix_v1.json",
        help="Path to threat matrix artifact",
    )
    parser.add_argument(
        "--allowlist",
        default="artifacts/phase2c/security/v1/hardened_mode_deviation_allowlist_v1.json",
        help="Path to hardened-mode allowlist artifact",
    )
    parser.add_argument(
        "--manifest",
        default="artifacts/phase2c/security/v1/adversarial_corpus_manifest_v1.json",
        help="Path to adversarial corpus manifest artifact",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Optional path for JSON report",
    )
    args = parser.parse_args()

    contract = load_json(Path(args.contract))
    matrix = load_json(Path(args.matrix))
    allowlist = load_json(Path(args.allowlist))
    manifest = load_json(Path(args.manifest))

    errors: list[str] = []
    contract_required_keys = [
        "schema_version",
        "contract_id",
        "required_matrix_keys",
        "required_allowlist_keys",
        "required_packet_ids",
        "matrix_packet_required_keys",
        "matrix_entry_required_keys",
        "required_threat_classes",
        "optional_threat_classes",
        "hardened_deviation_allowlist_categories",
        "allowlist_category_required_keys",
        "allowlist_packet_required_keys",
        "required_adversarial_manifest_keys",
        "adversarial_manifest_seed_policy_required_keys",
        "adversarial_manifest_entry_required_keys",
        "adversarial_manifest_mapping_required_keys",
        "required_high_risk_threat_classes",
    ]
    require_keys(contract, contract_required_keys, "contract", errors)

    matrix_summary = {"packet_count": 0, "entry_count": 0}
    allowlist_summary = {"packet_count": 0, "category_count": 0}
    manifest_summary = {"class_count": 0, "mapping_count": 0}

    if not errors:
        matrix_summary = validate_matrix(contract, matrix, errors)
        allowlist_summary = validate_allowlist(contract, allowlist, errors)
        manifest_summary = validate_adversarial_manifest(contract, matrix, manifest, errors)

    report = {
        "schema_version": "1.0.0",
        "contract_id": contract.get("contract_id", "<unknown>"),
        "ready": len(errors) == 0,
        "error_count": len(errors),
        "errors": errors,
        "summary": {
            "required_packet_count": len(contract.get("required_packet_ids", [])),
            "matrix_packets_validated": matrix_summary["packet_count"],
            "matrix_entries_validated": matrix_summary["entry_count"],
            "allowlist_packets_validated": allowlist_summary["packet_count"],
            "allowlist_categories_validated": allowlist_summary["category_count"],
            "manifest_threat_classes_validated": manifest_summary["class_count"],
            "manifest_mappings_validated": manifest_summary["mapping_count"],
        },
    }

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(report, indent=2))
    return 0 if report["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
