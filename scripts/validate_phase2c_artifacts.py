#!/usr/bin/env python3
"""Validate Phase2C packet artifact readiness against locked schema v1.

A packet is NOT READY if any mandatory artifact is missing or any mandatory
field/section is missing.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def has_markdown_section(text: str, section: str) -> bool:
    pattern = re.compile(rf"^##\s+{re.escape(section)}\s*$", re.MULTILINE)
    return bool(pattern.search(text))


def top_level_yaml_keys(text: str) -> set[str]:
    keys: set[str] = set()
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if line.startswith((" ", "\t")):
            continue
        if ":" not in line:
            continue
        key = line.split(":", 1)[0].strip()
        if key:
            keys.add(key)
    return keys


def validate_artifact(
    packet_path: Path,
    artifact_key: str,
    contract: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    artifact_spec = contract["artifacts"][artifact_key]
    artifact_path = packet_path / artifact_spec["filename"]
    if not artifact_path.exists():
        errors.append(f"missing artifact: {artifact_spec['filename']}")
        return errors

    kind = artifact_spec["kind"]
    if kind == "markdown_sections":
        text = artifact_path.read_text(encoding="utf-8")
        for section in artifact_spec["required_sections"]:
            if not has_markdown_section(text, section):
                errors.append(
                    f"missing markdown section `{section}` in {artifact_spec['filename']}"
                )
    elif kind == "json_keys":
        try:
            payload = load_json(artifact_path)
        except json.JSONDecodeError as err:
            errors.append(f"invalid json in {artifact_spec['filename']}: {err}")
            return errors
        for key in artifact_spec["required_keys"]:
            if key not in payload:
                errors.append(f"missing json key `{key}` in {artifact_spec['filename']}")
    elif kind == "yaml_keys":
        text = artifact_path.read_text(encoding="utf-8")
        keys = top_level_yaml_keys(text)
        for key in artifact_spec["required_keys"]:
            if key not in keys:
                errors.append(f"missing yaml key `{key}` in {artifact_spec['filename']}")
    else:
        errors.append(f"unsupported artifact kind `{kind}` for `{artifact_key}`")

    return errors


PACKETS_REQUIRE_IMPL_PLAN = {
    "FNX-P2C-003",
    "FNX-P2C-004",
    "FNX-P2C-005",
}


def validate_packet_impl_plan(packet_id: str, packet_path: Path) -> list[str]:
    errors: list[str] = []
    packet_tag = packet_id.lower()

    contract_path = packet_path / "contract_table.md"
    if not contract_path.exists():
        errors.append(f"missing {packet_tag} implementation skeleton source: contract_table.md")
        return errors

    contract_text = contract_path.read_text(encoding="utf-8")
    for section in [
        "Rust Module Boundary Skeleton",
        "Dependency-Aware Implementation Sequence",
        "Structured Logging + Verification Entry Points",
    ]:
        if not has_markdown_section(contract_text, section):
            errors.append(
                f"missing {packet_tag} implementation section `{section}` in contract_table.md"
            )

    manifest_path = packet_path / "fixture_manifest.json"
    if not manifest_path.exists():
        errors.append(f"missing {packet_tag} implementation skeleton source: fixture_manifest.json")
        return errors

    try:
        manifest = load_json(manifest_path)
    except json.JSONDecodeError as err:
        errors.append(f"invalid json in fixture_manifest.json: {err}")
        return errors

    for key in [
        "module_boundary_skeleton",
        "implementation_sequence",
        "verification_entrypoints",
    ]:
        value = manifest.get(key)
        if not isinstance(value, list) or not value:
            errors.append(f"fixture_manifest.json missing non-empty {packet_tag} key `{key}`")

    return errors


def validate_topology_shape(topology: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    req_top = set(schema["required_topology_keys"])
    missing_top = sorted(req_top.difference(topology.keys()))
    if missing_top:
        errors.append(f"topology missing required keys: {missing_top}")

    for packet in topology.get("packets", []):
        req_packet = set(schema["packet_required_keys"])
        missing_packet = sorted(req_packet.difference(packet.keys()))
        if missing_packet:
            pid = packet.get("packet_id", "<unknown>")
            errors.append(
                f"packet `{pid}` missing required keys: {missing_packet}"
            )

    return errors


def validate_packets(topology: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    packets_report: list[dict[str, Any]] = []
    ready_count = 0
    not_ready_count = 0

    contract_keys = set(contract["artifacts"].keys())

    for packet in topology["packets"]:
        packet_id = packet["packet_id"]
        packet_path = Path(packet["path"])
        artifact_keys = packet["required_artifact_keys"]
        packet_errors: list[str] = []

        for artifact_key in artifact_keys:
            if artifact_key not in contract_keys:
                packet_errors.append(f"unknown artifact key `{artifact_key}`")
                continue
            packet_errors.extend(validate_artifact(packet_path, artifact_key, contract))

        if packet_id in PACKETS_REQUIRE_IMPL_PLAN:
            packet_errors.extend(validate_packet_impl_plan(packet_id, packet_path))

        ready = not packet_errors
        if ready:
            ready_count += 1
        else:
            not_ready_count += 1

        packets_report.append(
            {
                "packet_id": packet_id,
                "path": str(packet_path),
                "ready": ready,
                "errors": packet_errors,
            }
        )

    return {
        "ready_count": ready_count,
        "not_ready_count": not_ready_count,
        "packets": packets_report,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--topology",
        default="artifacts/phase2c/packet_topology_v1.json",
        help="path to packet topology manifest",
    )
    parser.add_argument(
        "--schema",
        default="artifacts/phase2c/schema/v1/artifact_contract_schema_v1.json",
        help="path to artifact contract schema",
    )
    parser.add_argument(
        "--topology-schema",
        default="artifacts/phase2c/schema/v1/packet_topology_schema_v1.json",
        help="path to topology schema descriptor",
    )
    parser.add_argument(
        "--output",
        default="",
        help="optional output path for report json",
    )
    args = parser.parse_args()

    topology_path = Path(args.topology)
    contract_path = Path(args.schema)
    topology_schema_path = Path(args.topology_schema)

    topology = load_json(topology_path)
    contract = load_json(contract_path)
    topology_schema = load_json(topology_schema_path)

    shape_errors = validate_topology_shape(topology, topology_schema)

    report: dict[str, Any] = {
        "schema_version": "1.0.0",
        "topology_id": topology.get("topology_id", "<unknown>"),
        "contract_id": contract.get("contract_id", "<unknown>"),
        "shape_errors": shape_errors,
        "packets_report": {
            "ready_count": 0,
            "not_ready_count": 0,
            "packets": [],
        },
    }

    exit_code = 0
    if shape_errors:
        exit_code = 2
    else:
        packet_report = validate_packets(topology, contract)
        report["packets_report"] = packet_report
        if packet_report["not_ready_count"] > 0:
            exit_code = 2

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(report, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
