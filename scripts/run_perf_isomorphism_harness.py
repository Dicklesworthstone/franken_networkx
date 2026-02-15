#!/usr/bin/env python3
"""Run performance scenario isomorphism checks against golden output signatures."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def observable_output(output_text: str) -> str:
    lines = [line.strip() for line in output_text.splitlines() if line.strip()]
    for line in reversed(lines):
        if line.startswith("topology="):
            return line
    raise RuntimeError("missing observable output line starting with `topology=`")


def run_command(command: str) -> tuple[str, str]:
    proc = subprocess.run(
        ["bash", "-lc", command],
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            "isomorphism harness command failed\n"
            f"command: {command}\n"
            f"returncode: {proc.returncode}\n"
            f"stdout:\n{proc.stdout}\n"
            f"stderr:\n{proc.stderr}"
        )
    observed = observable_output("\n".join([proc.stdout, proc.stderr]))
    signature = hashlib.sha256(observed.encode("utf-8")).hexdigest()
    return observed, signature


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--matrix",
        default="artifacts/perf/phase2c/perf_baseline_matrix_v1.json",
    )
    parser.add_argument(
        "--golden",
        default="artifacts/perf/phase2c/isomorphism_golden_signatures_v1.json",
    )
    parser.add_argument(
        "--allowlist",
        default="artifacts/perf/phase2c/isomorphism_divergence_allowlist_v1.json",
    )
    parser.add_argument(
        "--report",
        default="artifacts/perf/phase2c/isomorphism_harness_report_v1.json",
    )
    parser.add_argument("--update-golden", action="store_true")
    args = parser.parse_args()

    matrix_path = Path(args.matrix)
    golden_path = Path(args.golden)
    allowlist_path = Path(args.allowlist)
    report_path = Path(args.report)

    matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
    scenarios = matrix["scenarios"]

    if allowlist_path.exists():
        allowlist = json.loads(allowlist_path.read_text(encoding="utf-8"))
    else:
        allowlist = {
            "schema_version": "1.0.0",
            "allowlist_id": "phase2c-isomorphism-divergence-allowlist-v1",
            "approved_divergences": [],
        }
        allowlist_path.parent.mkdir(parents=True, exist_ok=True)
        allowlist_path.write_text(json.dumps(allowlist, indent=2) + "\n", encoding="utf-8")

    approved = {
        row["scenario_id"]: row
        for row in allowlist.get("approved_divergences", [])
        if "scenario_id" in row
    }

    observed_rows = []
    golden_signatures: dict[str, str] = {}
    if golden_path.exists():
        golden_payload = json.loads(golden_path.read_text(encoding="utf-8"))
        golden_signatures = dict(golden_payload.get("signatures", {}))

    for scenario in scenarios:
        scenario_id = scenario["scenario_id"]
        command = scenario["command"]
        observed_line, signature = run_command(command)
        observed_rows.append(
            {
                "scenario_id": scenario_id,
                "command": command,
                "observable_output": observed_line,
                "signature": signature,
            }
        )
        if args.update_golden:
            golden_signatures[scenario_id] = signature

    if args.update_golden or not golden_path.exists():
        golden_payload = {
            "schema_version": "1.0.0",
            "golden_id": "phase2c-isomorphism-golden-signatures-v1",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "source_matrix_path": str(matrix_path),
            "signatures": golden_signatures,
        }
        golden_path.parent.mkdir(parents=True, exist_ok=True)
        golden_path.write_text(json.dumps(golden_payload, indent=2) + "\n", encoding="utf-8")

    failures = []
    approved_divergences = []
    for row in observed_rows:
        scenario_id = row["scenario_id"]
        observed_sig = row["signature"]
        expected_sig = golden_signatures.get(scenario_id)
        if expected_sig is None:
            failures.append(
                {
                    "scenario_id": scenario_id,
                    "reason": "missing_golden_signature",
                    "observed_signature": observed_sig,
                }
            )
            continue
        if observed_sig == expected_sig:
            continue
        if scenario_id in approved:
            approved_divergences.append(
                {
                    "scenario_id": scenario_id,
                    "approved_reason": approved[scenario_id].get("reason", "unspecified"),
                    "expected_signature": expected_sig,
                    "observed_signature": observed_sig,
                }
            )
            continue
        failures.append(
            {
                "scenario_id": scenario_id,
                "reason": "signature_mismatch",
                "expected_signature": expected_sig,
                "observed_signature": observed_sig,
            }
        )

    report = {
        "schema_version": "1.0.0",
        "report_id": "phase2c-isomorphism-harness-report-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_matrix_path": str(matrix_path),
        "golden_signatures_path": str(golden_path),
        "allowlist_path": str(allowlist_path),
        "divergence_policy": {
            "blocking_default": True,
            "requires_explicit_approval": True,
        },
        "scenario_count": len(observed_rows),
        "observed": observed_rows,
        "approved_divergences": approved_divergences,
        "failures": failures,
        "status": "pass" if not failures else "fail",
    }

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"isomorphism_harness_report:{report_path}")

    if failures:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
