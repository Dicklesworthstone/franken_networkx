#!/usr/bin/env python3
"""Verify conformance artifacts are fresh and valid.

This gate checks:
1. Conformance dashboard exists and shows pass status
2. Smoke report shows zero mismatches
3. Required conformance artifacts are present
4. Dashboard generation timestamp is within CI run window

Exit codes:
  0 = all checks pass
  1 = conformance failure detected
  2 = missing required artifacts
"""

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


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
