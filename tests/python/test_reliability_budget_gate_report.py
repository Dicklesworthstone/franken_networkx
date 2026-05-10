"""Regression tests for reliability budget gate report generation."""

from __future__ import annotations

import json
from pathlib import Path

from scripts import generate_reliability_budget_gate_report as gate


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_phase2c_passed_status_satisfies_e2e_replay_stage(
    tmp_path: Path, monkeypatch
) -> None:
    evidence_path = tmp_path / "evidence.json"
    _write_json(evidence_path, {"status": "pass"})

    spec_path = tmp_path / "reliability_budget_gate_v1.json"
    _write_json(
        spec_path,
        {
            "artifact_id": "test-reliability-budget",
            "budget_definitions": [
                {
                    "budget_id": "REL-TEST",
                    "packet_family": "FNX-P2C-TEST",
                    "coverage_floor": {"unit_line_pct": 90, "branch_pct": 80},
                    "property_floor": 1,
                    "e2e_replay_pass_floor": 1.0,
                    "flake_ceiling_pct_7d": 0.5,
                    "runtime_guardrail": {"metric": "none", "threshold": "none"},
                    "gate_command": "rch exec -- cargo test -q -p fnx-conformance",
                    "evidence_paths": [str(evidence_path)],
                }
            ],
            "packet_family_mapping": [
                {"packet_id": "FNX-P2C-TEST", "budget_id": "REL-TEST"}
            ],
            "flake_policy": {
                "warn_threshold_pct": 0.25,
                "fail_threshold_pct": 1.0,
                "quarantine_enter": {"flakes_in_window": 3, "window_hours": 24},
            },
            "gate_stage_contract": {
                "required_stage_ids": [
                    "coverage",
                    "property",
                    "e2e_replay",
                    "flake",
                    "runtime_guardrail",
                    "evidence_presence",
                ],
                "run_id_prefix": "test-reliability-gate-",
            },
        },
    )

    structured_logs_path = tmp_path / "structured_logs.jsonl"
    _write_jsonl(
        structured_logs_path,
        [
            {
                "packet_id": "FNX-P2C-TEST",
                "test_id": "fixture::test",
                "status": "passed",
                "ts_unix_ms": 1,
            }
        ],
    )
    e2e_events_path = tmp_path / "e2e_events.jsonl"
    _write_jsonl(e2e_events_path, [])
    smoke_report_path = tmp_path / "smoke_report.json"
    _write_json(smoke_report_path, {"fixture_count": 1, "mismatch_count": 0})
    normalization_report_path = tmp_path / "normalization_report.json"
    _write_json(
        normalization_report_path,
        {"valid_log_count": 1, "fixture_count": 1, "normalized_fields": ["status"]},
    )
    perf_report_path = tmp_path / "perf_report.json"
    _write_json(perf_report_path, {"status": "pass"})
    durability_report_path = tmp_path / "durability_report.json"
    _write_json(durability_report_path, {"entries": [{"decode_proof_count": 1}]})
    phase2c_report_path = tmp_path / "phase2c_report.json"
    _write_json(phase2c_report_path, {"status": "passed"})

    output_path = tmp_path / "reliability_budget_report_v1.json"
    quarantine_path = tmp_path / "flake_quarantine_v1.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "generate_reliability_budget_gate_report.py",
            "--spec",
            str(spec_path),
            "--structured-logs",
            str(structured_logs_path),
            "--e2e-events",
            str(e2e_events_path),
            "--smoke-report",
            str(smoke_report_path),
            "--normalization-report",
            str(normalization_report_path),
            "--perf-regression-report",
            str(perf_report_path),
            "--durability-report",
            str(durability_report_path),
            "--phase2c-e2e-report",
            str(phase2c_report_path),
            "--output",
            str(output_path),
            "--quarantine-output",
            str(quarantine_path),
        ],
    )

    assert gate.main() == 0

    report = json.loads(output_path.read_text(encoding="utf-8"))
    stages = report["budgets"][0]["stage_results"]

    assert report["status"] == "pass"
    assert {stage["stage_id"]: stage["status"] for stage in stages} == {
        "coverage": "pass",
        "property": "pass",
        "e2e_replay": "pass",
        "flake": "pass",
        "runtime_guardrail": "pass",
        "evidence_presence": "pass",
    }
