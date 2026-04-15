#!/usr/bin/env python3
"""Verify conformance artifacts are fresh and valid.

This gate checks:
1. Conformance dashboard exists and shows pass status
2. Smoke report shows zero mismatches
3. Required conformance artifacts are present
4. Fixture-level ``*.report.json`` outputs are newer than the latest change in
   ``crates/fnx-conformance/``, ``crates/fnx-algorithms/``, and
   ``python/franken_networkx/``

Exit codes:
  0 = all checks pass
  1 = conformance failure detected
  2 = missing required artifacts
"""

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

SOURCE_ROOTS = [
    Path("crates/fnx-conformance"),
    Path("crates/fnx-algorithms"),
    Path("python/franken_networkx"),
]


def load_json(path: Path) -> dict | None:
    """Load JSON file or return None if missing/invalid."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"::warning file={path}::failed to load: {e}")
        return None


def check_dashboard(artifacts_root: Path) -> tuple[bool, list[str]]:
    """Check conformance dashboard status."""
    errors = []
    dashboard_path = artifacts_root / "conformance_dashboard_v1.json"
    dashboard = load_json(dashboard_path)

    if dashboard is None:
        errors.append(f"missing required file: {dashboard_path}")
        return False, errors

    # Check status
    status = dashboard.get("status")
    if status != "pass":
        errors.append(f"dashboard status is '{status}', expected 'pass'")

    # Check summary
    summary = dashboard.get("summary", {})
    mismatches = summary.get("total_mismatches", -1)
    if mismatches != 0:
        errors.append(f"dashboard shows {mismatches} mismatches")

    # Check generation timestamp (should be recent if in CI)
    generated_at = dashboard.get("generated_at_utc")
    if generated_at:
        try:
            ts = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
            age = datetime.now(timezone.utc) - ts
            # In CI, dashboard should be generated in the same run
            # Allow 1 hour tolerance for local development
            if age > timedelta(hours=1):
                print(f"::notice::dashboard is {age} old (generated at {generated_at})")
        except ValueError:
            errors.append(f"invalid timestamp format: {generated_at}")

    return len(errors) == 0, errors


def check_smoke_report(artifacts_root: Path) -> tuple[bool, list[str]]:
    """Check smoke report for conformance status."""
    errors = []
    smoke_path = artifacts_root / "smoke_report.json"
    smoke = load_json(smoke_path)

    if smoke is None:
        errors.append(f"missing required file: {smoke_path}")
        return False, errors

    mismatch_count = smoke.get("mismatch_count", -1)
    if mismatch_count != 0:
        errors.append(f"smoke report shows {mismatch_count} mismatches")

    fixture_count = smoke.get("fixture_count", 0)
    if fixture_count == 0:
        errors.append("smoke report shows 0 fixtures (no tests ran?)")

    return len(errors) == 0, errors


def check_required_artifacts(artifacts_root: Path) -> tuple[bool, list[str]]:
    """Check that required artifacts exist."""
    errors = []
    required = [
        "smoke_report.json",
        "conformance_dashboard_v1.json",
        "structured_logs.jsonl",
    ]

    for filename in required:
        path = artifacts_root / filename
        if not path.exists():
            errors.append(f"missing required artifact: {filename}")

    return len(errors) == 0, errors


def format_mtime(path: Path) -> str:
    """Return a path mtime in UTC ISO-8601 form."""
    return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()


def check_fixture_report_freshness(
    artifacts_root: Path, source_roots: list[Path] | None = None
) -> tuple[bool, list[str]]:
    """Ensure fixture-level conformance reports are newer than source surfaces."""
    errors = []
    reports = sorted(artifacts_root.glob("*.report.json"))
    if not reports:
        errors.append("no fixture-level conformance reports were generated")
        return False, errors

    roots = SOURCE_ROOTS if source_roots is None else source_roots
    source_files = [path for root in roots for path in root.rglob("*") if path.is_file()]
    if not source_files:
        errors.append("no source files found for freshness comparison")
        return False, errors

    newest_source = max(source_files, key=lambda path: path.stat().st_mtime)
    newest_source_mtime = newest_source.stat().st_mtime
    stale_reports = [
        report for report in reports if report.stat().st_mtime < newest_source_mtime
    ]
    if stale_reports:
        errors.append(
            "fixture-level conformance reports are stale relative to "
            f"{newest_source} ({format_mtime(newest_source)})"
        )
        for report in stale_reports[:10]:
            errors.append(
                f"stale report: {report} ({format_mtime(report)})"
            )
        if len(stale_reports) > 10:
            errors.append(f"... and {len(stale_reports) - 10} more stale reports")

    return len(errors) == 0, errors


def main() -> int:
    artifacts_root = Path("artifacts/conformance/latest")

    if not artifacts_root.exists():
        print(f"::error::conformance artifacts directory not found: {artifacts_root}")
        return 2

    all_ok = True
    all_errors = []

    # Run all checks
    for check_name, check_fn in [
        ("required_artifacts", check_required_artifacts),
        ("smoke_report", check_smoke_report),
        ("dashboard", check_dashboard),
        ("fixture_report_freshness", check_fixture_report_freshness),
    ]:
        ok, errors = check_fn(artifacts_root)
        if not ok:
            all_ok = False
            for err in errors:
                print(f"::error::[{check_name}] {err}")
                all_errors.append(f"{check_name}: {err}")

    if all_ok:
        print("conformance_freshness: PASS")
        return 0
    else:
        print(f"conformance_freshness: FAIL ({len(all_errors)} errors)")
        return 1


if __name__ == "__main__":
    sys.exit(main())
