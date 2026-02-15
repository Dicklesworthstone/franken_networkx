#!/usr/bin/env python3
"""Emit deterministic adversarial seed ledger and replay-ready structured events."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]

LEDGER_SCHEMA_VERSION = "1.0.0"
EVENT_SCHEMA_VERSION = "1.0.0"
REPORT_SCHEMA_VERSION = "1.0.0"

FAILURE_CLASSIFICATION: dict[str, str] = {
    "parser_abuse": "security",
    "metadata_ambiguity": "compatibility",
    "version_skew": "compatibility",
    "resource_exhaustion": "performance_tail",
    "state_corruption": "memory_state_corruption",
    "backend_route_ambiguity": "determinism",
    "attribute_confusion": "compatibility",
    "algorithmic_complexity_dos": "performance_tail",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def unix_ms() -> int:
    return int(time.time() * 1000)


def fnv1a64(text: str) -> str:
    value = 0xCBF29CE484222325
    for byte in text.encode("utf-8"):
        value ^= byte
        value = (value * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return f"{value:016x}"


def build_entries(
    *,
    manifest: dict[str, Any],
    threat_filter: str | None,
    packet_filter: str | None,
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []

    for threat_row in manifest.get("threat_taxonomy", []):
        threat_class = threat_row.get("threat_class")
        if not isinstance(threat_class, str):
            continue
        if threat_filter and threat_class != threat_filter:
            continue
        failure_classification = FAILURE_CLASSIFICATION.get(threat_class, "compatibility")

        seed_policy = threat_row.get("seed_policy", {})
        class_seed = seed_policy.get("class_seed")
        if not isinstance(class_seed, int):
            class_seed = 0

        packet_gate_mappings = threat_row.get("packet_gate_mappings", [])
        if not isinstance(packet_gate_mappings, list):
            continue
        for mapping in packet_gate_mappings:
            if not isinstance(mapping, dict):
                continue
            packet_id = mapping.get("packet_id")
            if not isinstance(packet_id, str):
                continue
            if packet_filter and packet_id != packet_filter:
                continue

            validation_gate = mapping.get("validation_gate", "")
            generator_variant = mapping.get("generator_variant", "")
            expected_failure_mode = mapping.get("expected_failure_mode", "")
            seed = mapping.get("seed")
            if not isinstance(seed, int):
                continue

            fixture_hash_id = fnv1a64(
                "|".join(
                    [
                        packet_id,
                        threat_class,
                        validation_gate,
                        generator_variant,
                        str(seed),
                        expected_failure_mode,
                    ]
                )
            )
            replay_command = (
                "python3 scripts/run_adversarial_seed_harness.py "
                f"--threat-class {threat_class} --packet-id {packet_id} "
                f"--run-id replay-{fixture_hash_id}"
            )
            entries.append(
                {
                    "packet_id": packet_id,
                    "threat_class": threat_class,
                    "validation_gate": validation_gate,
                    "generator_variant": generator_variant,
                    "seed": seed,
                    "class_seed": class_seed,
                    "expected_failure_mode": expected_failure_mode,
                    "failure_classification": failure_classification,
                    "fixture_hash_id": fixture_hash_id,
                    "replay_command": replay_command,
                    "shrink_metadata": {
                        "strategy": "delta_debug_fixed_seed",
                        "minimized_counterexample_id": f"min-{fixture_hash_id[:12]}",
                        "shrink_steps": 0,
                    },
                }
            )

    entries.sort(key=lambda row: (row["threat_class"], row["packet_id"], row["seed"]))
    return entries


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest",
        default="artifacts/phase2c/security/v1/adversarial_corpus_manifest_v1.json",
        help="Path to adversarial corpus manifest",
    )
    parser.add_argument(
        "--ledger-output",
        default="artifacts/phase2c/security/v1/adversarial_seed_ledger_v1.json",
        help="Path to canonical deterministic seed ledger",
    )
    parser.add_argument(
        "--events-output",
        default="artifacts/phase2c/latest/adversarial_seed_harness_events_v1.jsonl",
        help="Path to structured harness events JSONL",
    )
    parser.add_argument(
        "--report-output",
        default="artifacts/phase2c/latest/adversarial_seed_harness_report_v1.json",
        help="Path to harness summary report JSON",
    )
    parser.add_argument(
        "--threat-class",
        default="",
        help="Optional threat class filter for replay",
    )
    parser.add_argument(
        "--packet-id",
        default="",
        help="Optional packet filter for replay",
    )
    parser.add_argument(
        "--run-id",
        default="",
        help="Optional deterministic run id (default is time-based)",
    )
    args = parser.parse_args()

    manifest_path = REPO_ROOT / args.manifest
    manifest = load_json(manifest_path)
    run_id = args.run_id or f"adversarial-seed-harness-{unix_ms()}"
    threat_filter = args.threat_class.strip() or None
    packet_filter = args.packet_id.strip() or None

    entries = build_entries(
        manifest=manifest,
        threat_filter=threat_filter,
        packet_filter=packet_filter,
    )
    now_ms = unix_ms()
    now_utc = datetime.now(timezone.utc).isoformat()

    ledger_payload = {
        "schema_version": LEDGER_SCHEMA_VERSION,
        "ledger_id": "adversarial-seed-ledger-v1",
        "generated_at_utc": now_utc,
        "source_manifest_path": args.manifest,
        "deterministic_seed_strategy": "class_seed_plus_packet_offset",
        "entry_count": len(entries),
        "entries": entries,
    }
    write_json(REPO_ROOT / args.ledger_output, ledger_payload)

    events = []
    for entry in entries:
        events.append(
            {
                "schema_version": EVENT_SCHEMA_VERSION,
                "run_id": run_id,
                "ts_unix_ms": now_ms,
                "packet_id": entry["packet_id"],
                "threat_class": entry["threat_class"],
                "validation_gate": entry["validation_gate"],
                "generator_variant": entry["generator_variant"],
                "seed": entry["seed"],
                "expected_failure_mode": entry["expected_failure_mode"],
                "failure_classification": entry["failure_classification"],
                "fixture_hash_id": entry["fixture_hash_id"],
                "replay_command": entry["replay_command"],
                "shrink_metadata": entry["shrink_metadata"],
                "status": "replay_ready",
            }
        )
    write_jsonl(REPO_ROOT / args.events_output, events)

    classification_counts: dict[str, int] = {}
    for event in events:
        cls = event["failure_classification"]
        classification_counts[cls] = classification_counts.get(cls, 0) + 1

    report_payload = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "report_id": "adversarial-seed-harness-report-v1",
        "generated_at_utc": now_utc,
        "run_id": run_id,
        "status": "pass",
        "threat_filter": threat_filter,
        "packet_filter": packet_filter,
        "entry_count": len(entries),
        "event_count": len(events),
        "deterministic_replay_ready": True,
        "classification_counts": classification_counts,
        "artifact_refs": [
            args.ledger_output,
            args.events_output,
        ],
    }
    write_json(REPO_ROOT / args.report_output, report_payload)

    print(f"adversarial_seed_ledger:{args.ledger_output}")
    print(f"adversarial_seed_events:{args.events_output}")
    print(f"adversarial_seed_report:{args.report_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
