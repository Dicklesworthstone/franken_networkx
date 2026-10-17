"""End-to-end and negative-case tests for scripts/check_bead_receipts.py (wvztf.6)."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

import check_bead_receipts as gate  # noqa: E402


def test_live_beads_jsonl_passes_closure_receipt_gate():
    rc = gate.main([])
    assert rc == 0
    report = gate.check_issues_jsonl(REPO_ROOT / ".beads/issues.jsonl")
    assert report["passed"] is True
    assert report["total_checked"] >= 11
    for hist in report["historical_checks"]:
        assert hist["present"] is True
        assert hist["has_incident_comment"] is True

    jsonl_path = REPO_ROOT / "artifacts/conformance/latest/bead_closure_receipts_e2e.jsonl"
    assert jsonl_path.exists()
    lines = [
        json.loads(line)
        for line in jsonl_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(lines) == report["total_checked"]
    assert all(rec["pass"] is True for rec in lines)


def test_closure_receipt_gate_rejects_narrative_only_close(tmp_path: Path):
    """wvztf.6 negative test: a closed bead carrying label 'gate' or 'perf-claim'
    without a machine-parsable receipt must fail check_issues_jsonl."""
    bad_jsonl = tmp_path / "issues_bad.jsonl"
    records = [
        {
            "id": "br-test-good-1",
            "status": "closed",
            "labels": ["gate"],
            "close_reason": "Verified by scripts/run_perf_slo_gate.py (2 passed)",
            "comments": [],
        },
        {
            "id": "br-test-narrative-only-2",
            "status": "closed",
            "labels": ["perf-claim"],
            "close_reason": "Completed and verified everything works nicely",
            "comments": [],
        },
    ]
    bad_jsonl.write_text(
        "\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8"
    )
    report = gate.check_issues_jsonl(bad_jsonl)
    assert report["passed"] is False
    assert [v["id"] for v in report["violations"]] == ["br-test-narrative-only-2"]

    jsonl_sha = hashlib.sha256(
        (REPO_ROOT / "artifacts/conformance/latest/bead_closure_receipts_e2e.jsonl").read_bytes()
    ).hexdigest()
    assert len(jsonl_sha) == 64
