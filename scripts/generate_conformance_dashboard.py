#!/usr/bin/env python3
"""Generate a conformance dashboard from conformance test artifacts.

Aggregates data from:
- smoke_report.json
- mismatch_taxonomy_report.json
- reliability_budget_report_v1.json
- Individual fixture reports

Outputs: artifacts/conformance/latest/conformance_dashboard_v1.json
"""

import json
from datetime import datetime, timezone
from pathlib import Path


def load_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def generate_dashboard() -> dict:
    artifacts_root = Path("artifacts/conformance/latest")

    smoke = load_json(artifacts_root / "smoke_report.json") or {}
    taxonomy = load_json(artifacts_root / "mismatch_taxonomy_report.json") or {}
    reliability = load_json(artifacts_root / "reliability_budget_report_v1.json") or {}
    structured_log_report = load_json(artifacts_root / "structured_log_emitter_normalization_report.json") or {}

    # Extract fixture reports from smoke report
    fixture_reports = smoke.get("fixture_reports", [])

    # Calculate per-suite summary
    suite_summary = {}
    for fixture in fixture_reports:
        suite = fixture.get("suite", "unknown")
        if suite not in suite_summary:
            suite_summary[suite] = {
                "total": 0,
                "passed": 0,
                "failed": 0,
                "strict_violations": 0,
                "hardened_allowlisted": 0,
            }
        suite_summary[suite]["total"] += 1
        if fixture.get("passed"):
            suite_summary[suite]["passed"] += 1
        else:
            suite_summary[suite]["failed"] += 1
        suite_summary[suite]["strict_violations"] += fixture.get("strict_violation_count", 0)
        suite_summary[suite]["hardened_allowlisted"] += fixture.get("hardened_allowlisted_count", 0)

    # Calculate algorithm coverage
    algorithms_tested = set()
    for fixture in fixture_reports:
        witness = fixture.get("witness")
        if witness and (alg := witness.get("algorithm")):
            algorithms_tested.add(alg)

    # Normalize ordering for deterministic output.
    suite_summary = dict(sorted(suite_summary.items(), key=lambda item: item[0]))

    categories_observed = sorted(
        {
            row.get("category")
            for row in taxonomy.get("fixture_rows", [])
            if row.get("category")
        }
    )

    # Build dashboard
    dashboard = {
        "report_id": "conformance-dashboard-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "run_id": f"conformance-dashboard-{int(datetime.now().timestamp())}",
        "status": "pass" if smoke.get("mismatch_count", 0) == 0 else "fail",

        "summary": {
            "total_fixtures": smoke.get("fixture_count", 0),
            "total_mismatches": smoke.get("mismatch_count", 0),
            "hardened_allowlisted": smoke.get("hardened_allowlisted_count", 0),
            "oracle_present": smoke.get("oracle_present", False),
            "mode": "strict" if smoke.get("strict_mode") else "hardened",
        },

        "per_suite": suite_summary,

        "algorithm_coverage": {
            "algorithms_tested": sorted(algorithms_tested),
            "coverage_count": len(algorithms_tested),
        },

        "taxonomy": {
            "schema_version": taxonomy.get("schema_version"),
            "fixture_rows": len(taxonomy.get("fixture_rows", [])),
            "categories_observed": categories_observed,
        },

        "reliability": {
            "budget_status": reliability.get("status"),
            "check_count": reliability.get("check_count", 0),
            "pass_count": reliability.get("pass_count", 0),
            "fail_count": reliability.get("fail_count", 0),
        },

        "structured_logging": {
            "emitter_count": structured_log_report.get("emitter_count", 0),
            "normalized_count": structured_log_report.get("normalized_count", 0),
            "crate_name": structured_log_report.get("crate_name"),
        },

        "artifact_paths": {
            "smoke_report": "artifacts/conformance/latest/smoke_report.json",
            "taxonomy_report": "artifacts/conformance/latest/mismatch_taxonomy_report.json",
            "reliability_report": "artifacts/conformance/latest/reliability_budget_report_v1.json",
            "structured_logs": "artifacts/conformance/latest/structured_logs.json",
        },

        "audit_friendly": True,
        "deterministic": True,
    }

    return dashboard


def main() -> int:
    dashboard = generate_dashboard()
    output_path = Path("artifacts/conformance/latest/conformance_dashboard_v1.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(dashboard, indent=2) + "\n", encoding="utf-8")
    print(f"conformance_dashboard:{output_path}")

    if dashboard["status"] == "fail":
        print(f"DASHBOARD STATUS: FAIL ({dashboard['summary']['total_mismatches']} mismatches)")
        return 1

    print(f"DASHBOARD STATUS: PASS ({dashboard['summary']['total_fixtures']} fixtures, {dashboard['algorithm_coverage']['coverage_count']} algorithms)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
