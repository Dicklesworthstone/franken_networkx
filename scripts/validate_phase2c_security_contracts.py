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

    missing_packets = sorted(required_packets.difference(packet_seen))
    extra_packets = sorted(packet_seen.difference(required_packets))
    if missing_packets:
        errors.append(f"allowlist missing required packet_ids: {missing_packets}")
    if extra_packets:
        errors.append(f"allowlist includes unknown packet_ids: {extra_packets}")

    return {"packet_count": len(packet_seen), "category_count": len(category_names)}


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
        "--output",
        default="",
        help="Optional path for JSON report",
    )
    args = parser.parse_args()

    contract = load_json(Path(args.contract))
    matrix = load_json(Path(args.matrix))
    allowlist = load_json(Path(args.allowlist))

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
    ]
    require_keys(contract, contract_required_keys, "contract", errors)

    matrix_summary = {"packet_count": 0, "entry_count": 0}
    allowlist_summary = {"packet_count": 0, "category_count": 0}

    if not errors:
        matrix_summary = validate_matrix(contract, matrix, errors)
        allowlist_summary = validate_allowlist(contract, allowlist, errors)

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
