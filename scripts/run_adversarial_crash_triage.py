#!/usr/bin/env python3
"""Classify adversarial harness outputs and promote confirmed regressions."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]

TRIAGE_EVENT_SCHEMA_VERSION = "1.0.0"
TRIAGE_REPORT_SCHEMA_VERSION = "1.0.0"
PROMOTION_QUEUE_SCHEMA_VERSION = "1.0.0"
REGRESSION_BUNDLE_SCHEMA_VERSION = "1.0.0"

SEVERITY_BY_CLASSIFICATION = {
    "security": "critical",
    "memory_state_corruption": "critical",
    "determinism": "high",
    "compatibility": "high",
    "performance_tail": "medium",
}

OWNER_BEAD_BY_PACKET = {
    "FNX-P2C-001": "bd-315.12",
    "FNX-P2C-002": "bd-315.13",
    "FNX-P2C-003": "bd-315.14",
    "FNX-P2C-004": "bd-315.15",
    "FNX-P2C-005": "bd-315.16",
    "FNX-P2C-006": "bd-315.17",
    "FNX-P2C-007": "bd-315.18",
    "FNX-P2C-008": "bd-315.19",
    "FNX-P2C-009": "bd-315.20",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if text:
                rows.append(json.loads(text))
    return rows


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def fnv1a64(text: str) -> str:
    value = 0xCBF29CE484222325
    for byte in text.encode("utf-8"):
        value ^= byte
        value = (value * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return f"{value:016x}"


def unix_ms() -> int:
    return int(time.time() * 1000)


def current_environment() -> tuple[dict[str, str], str]:
    env = {
        "os_name": os.name,
        "sys_platform": sys.platform,
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
    }
    fingerprint = fnv1a64("|".join(f"{key}={env[key]}" for key in sorted(env)))
    return env, fingerprint


def routing_policy_for_classification(classification: str) -> str:
    if classification in {"security", "memory_state_corruption", "determinism"}:
        return "bug"
    if classification == "performance_tail":
        return "known_risk_allowlist"
    return "compatibility_exception"


def to_triage_rows(seed_rows: list[dict[str, Any]], run_id: str, now_ms: int) -> list[dict[str, Any]]:
    triage_rows = []
    env, env_fingerprint = current_environment()
    for seed_row in seed_rows:
        packet_id = str(seed_row["packet_id"])
        threat_class = str(seed_row["threat_class"])
        classification = str(seed_row["failure_classification"])
        fixture_hash_id = str(seed_row["fixture_hash_id"])
        severity = SEVERITY_BY_CLASSIFICATION.get(classification, "medium")
        routing_policy = routing_policy_for_classification(classification)
        owner_bead = OWNER_BEAD_BY_PACKET.get(packet_id, "bd-315")
        triage_id = f"triage-{fnv1a64('|'.join([packet_id, threat_class, fixture_hash_id]))}"
        regression_fixture_id = (
            f"adversarial_regression::{packet_id.lower()}::{threat_class}::{fixture_hash_id[:12]}"
        )
        stack_signature = fnv1a64(
            "|".join(
                [
                    packet_id,
                    threat_class,
                    str(seed_row["validation_gate"]),
                    str(seed_row["expected_failure_mode"]),
                ]
            )
        )
        triage_rows.append(
            {
                "schema_version": TRIAGE_EVENT_SCHEMA_VERSION,
                "run_id": run_id,
                "ts_unix_ms": now_ms,
                "triage_id": triage_id,
                "packet_id": packet_id,
                "owner_bead_id": owner_bead,
                "threat_class": threat_class,
                "severity_tag": severity,
                "failure_classification": classification,
                "fixture_hash_id": fixture_hash_id,
                "seed": int(seed_row["seed"]),
                "validation_gate": seed_row["validation_gate"],
                "generator_variant": seed_row["generator_variant"],
                "expected_failure_mode": seed_row["expected_failure_mode"],
                "stack_signature": stack_signature,
                "environment_fingerprint": env_fingerprint,
                "environment": env,
                "routing_policy": routing_policy,
                "triage_status": "confirmed_regression_candidate",
                "routing_tags": [
                    "adversarial",
                    f"severity:{severity}",
                    f"classification:{classification}",
                    f"owner:{owner_bead}",
                ],
                "minimal_reproducer": {
                    "command": seed_row["replay_command"],
                    "seed": int(seed_row["seed"]),
                    "packet_id": packet_id,
                    "threat_class": threat_class,
                },
                "replay_command": seed_row["replay_command"],
                "conformance_gate_ids": ["phase2c_packet_readiness_gate"],
                "forensics_refs": [
                    "artifacts/phase2c/latest/adversarial_seed_harness_events_v1.jsonl",
                    "artifacts/phase2c/latest/adversarial_crash_triage_report_v1.json",
                ],
                "regression_fixture_id": regression_fixture_id,
                "promotion_action": "promote_to_regression_fixture_bundle",
            }
        )

    triage_rows.sort(key=lambda row: (row["severity_tag"], row["packet_id"], row["threat_class"]))
    return triage_rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--seed-events",
        default="artifacts/phase2c/latest/adversarial_seed_harness_events_v1.jsonl",
        help="Seed harness events JSONL input",
    )
    parser.add_argument(
        "--triage-events-output",
        default="artifacts/phase2c/latest/adversarial_crash_triage_events_v1.jsonl",
        help="Crash triage events JSONL output",
    )
    parser.add_argument(
        "--triage-report-output",
        default="artifacts/phase2c/latest/adversarial_crash_triage_report_v1.json",
        help="Crash triage summary report output",
    )
    parser.add_argument(
        "--promotion-queue-output",
        default="artifacts/phase2c/latest/adversarial_regression_promotion_queue_v1.json",
        help="Regression promotion queue output",
    )
    parser.add_argument(
        "--fixture-bundle-output",
        default="crates/fnx-conformance/fixtures/generated/adversarial_regression_bundle_v1.json",
        help="Persistent regression fixture bundle output",
    )
    parser.add_argument(
        "--run-id",
        default="",
        help="Optional deterministic run id",
    )
    args = parser.parse_args()

    seed_rows = load_jsonl(REPO_ROOT / args.seed_events)
    run_id = args.run_id or f"adversarial-crash-triage-{unix_ms()}"
    now_ms = unix_ms()
    now_utc = datetime.now(timezone.utc).isoformat()

    triage_rows = to_triage_rows(seed_rows, run_id, now_ms)
    write_jsonl(REPO_ROOT / args.triage_events_output, triage_rows)

    promotion_rows = []
    fixture_rows = []
    for triage_row in triage_rows:
        packet_id = triage_row["packet_id"]
        owner_bead = triage_row["owner_bead_id"]
        regression_fixture_id = triage_row["regression_fixture_id"]
        fixture_payload = {
            "fixture_id": regression_fixture_id,
            "packet_id": packet_id,
            "owner_bead_id": owner_bead,
            "threat_class": triage_row["threat_class"],
            "severity_tag": triage_row["severity_tag"],
            "routing_policy": triage_row["routing_policy"],
            "seed": triage_row["seed"],
            "fixture_hash_id": triage_row["fixture_hash_id"],
            "stack_signature": triage_row["stack_signature"],
            "environment_fingerprint": triage_row["environment_fingerprint"],
            "replay_command": triage_row["replay_command"],
            "expected_failure_mode": triage_row["expected_failure_mode"],
            "conformance_gate_ids": triage_row["conformance_gate_ids"],
            "source_triage_id": triage_row["triage_id"],
        }
        fixture_rows.append(fixture_payload)
        promotion_rows.append(
            {
                "regression_fixture_id": regression_fixture_id,
                "packet_id": packet_id,
                "owner_bead_id": owner_bead,
                "promotion_status": "promoted",
                "promotion_reason": "confirmed_regression_candidate",
                "routing_policy": triage_row["routing_policy"],
                "source_triage_id": triage_row["triage_id"],
                "target_fixture_bundle_path": args.fixture_bundle_output,
                "replay_command": triage_row["replay_command"],
            }
        )

    promotion_payload = {
        "schema_version": PROMOTION_QUEUE_SCHEMA_VERSION,
        "queue_id": "adversarial-regression-promotion-queue-v1",
        "generated_at_utc": now_utc,
        "run_id": run_id,
        "entry_count": len(promotion_rows),
        "entries": promotion_rows,
    }
    write_json(REPO_ROOT / args.promotion_queue_output, promotion_payload)

    fixture_bundle_payload = {
        "schema_version": REGRESSION_BUNDLE_SCHEMA_VERSION,
        "bundle_id": "adversarial-regression-bundle-v1",
        "generated_at_utc": now_utc,
        "run_id": run_id,
        "fixture_count": len(fixture_rows),
        "fixtures": fixture_rows,
    }
    write_json(REPO_ROOT / args.fixture_bundle_output, fixture_bundle_payload)

    severity_counts: dict[str, int] = {}
    routing_policy_counts: dict[str, int] = {}
    owner_counts: dict[str, int] = {}
    for triage_row in triage_rows:
        sev = triage_row["severity_tag"]
        policy = triage_row["routing_policy"]
        owner = triage_row["owner_bead_id"]
        severity_counts[sev] = severity_counts.get(sev, 0) + 1
        routing_policy_counts[policy] = routing_policy_counts.get(policy, 0) + 1
        owner_counts[owner] = owner_counts.get(owner, 0) + 1

    report_payload = {
        "schema_version": TRIAGE_REPORT_SCHEMA_VERSION,
        "report_id": "adversarial-crash-triage-report-v1",
        "generated_at_utc": now_utc,
        "run_id": run_id,
        "status": "pass",
        "triage_count": len(triage_rows),
        "promotion_count": len(promotion_rows),
        "severity_counts": severity_counts,
        "routing_policy_counts": routing_policy_counts,
        "owner_bead_counts": owner_counts,
        "artifact_refs": [
            args.triage_events_output,
            args.promotion_queue_output,
            args.fixture_bundle_output,
        ],
    }
    write_json(REPO_ROOT / args.triage_report_output, report_payload)

    print(f"adversarial_crash_triage_events:{args.triage_events_output}")
    print(f"adversarial_crash_triage_report:{args.triage_report_output}")
    print(f"adversarial_regression_promotion_queue:{args.promotion_queue_output}")
    print(f"adversarial_regression_fixture_bundle:{args.fixture_bundle_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
