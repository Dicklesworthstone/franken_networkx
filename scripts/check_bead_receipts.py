#!/usr/bin/env python3
"""Verify that closed release / perf-claim / gate / docs-integrity beads carry machine-parsable closure receipts (wvztf.6)."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "python") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "python"))

RECEIPT_REQUIRED_LABELS = frozenset({"release", "perf-claim", "gate", "docs-integrity"})

# The 4 historical false-close beads documented in wvztf.6 must carry incident comments.
HISTORICAL_FALSE_CLOSE_BEADS = (
    "br-r37-c1-rc-pypi-release-v022-dd9ux",
    "br-r37-c1-epic-release-pypi-z1tdt.2",
    "br-r37-c1-remove-node-is-quadratic-tv8wd",
    "br-r37-c1-epic-docs-integrity-a4daa.1",
)

# Machine-parsable receipt patterns accepted in close_reason or CLOSE EVIDENCE comments:
RECEIPT_PATTERNS = (
    re.compile(r"\b(?:scripts|tests|artifacts|crates|docs|python)/[\w./-]+"),
    re.compile(r"\b[0-9a-f]{7,40}\b"),
    re.compile(r"\b\d+\s+passed\b"),
    re.compile(r"\bdsr:[\w:-]+\b"),
    re.compile(r"\bsha256[:=]?[0-9a-f]{16,64}\b", re.IGNORECASE),
    re.compile(r"https?://\S+"),
)


def has_parsable_receipt(issue: dict[str, Any]) -> bool:
    close_reason = str(issue.get("close_reason") or "")
    comment_texts = [
        str(c.get("text") or "")
        for c in (issue.get("comments") or [])
        if isinstance(c, dict)
    ]
    combined = "\n".join([close_reason, *comment_texts])
    if len(close_reason.strip()) < 12 and not any(
        "CLOSE EVIDENCE" in t for t in comment_texts
    ):
        return False
    return any(pattern.search(combined) is not None for pattern in RECEIPT_PATTERNS)


def check_issues_jsonl(issues_path: Path) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    for line in issues_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            issues.append(json.loads(line))

    by_id = {rec["id"]: rec for rec in issues if "id" in rec}
    violations: list[dict[str, Any]] = []
    checked_beads: list[dict[str, Any]] = []
    historical_checks: list[dict[str, Any]] = []

    for rec in issues:
        if rec.get("status") != "closed":
            continue
        labels = set(rec.get("labels") or [])
        matched_labels = sorted(labels & RECEIPT_REQUIRED_LABELS)
        if not matched_labels:
            continue
        ok = has_parsable_receipt(rec)
        entry = {
            "id": rec["id"],
            "labels": matched_labels,
            "close_reason": rec.get("close_reason", ""),
            "has_receipt": ok,
        }
        checked_beads.append(entry)
        if not ok:
            violations.append(entry)

    for hist_id in HISTORICAL_FALSE_CLOSE_BEADS:
        rec = by_id.get(hist_id)
        has_incident_comment = bool(rec and (rec.get("comments") or []))
        historical_checks.append(
            {
                "id": hist_id,
                "present": rec is not None,
                "has_incident_comment": has_incident_comment,
            }
        )
        if rec is not None and not has_incident_comment:
            violations.append(
                {
                    "id": hist_id,
                    "labels": ["historical-incident"],
                    "close_reason": rec.get("close_reason", ""),
                    "has_receipt": False,
                }
            )

    return {
        "issues_path": str(issues_path),
        "total_checked": len(checked_beads),
        "violations": violations,
        "checked_beads": checked_beads,
        "historical_checks": historical_checks,
        "passed": len(violations) == 0,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--issues-jsonl",
        type=Path,
        default=REPO_ROOT / ".beads/issues.jsonl",
    )
    parser.add_argument(
        "--output-jsonl",
        type=Path,
        default=REPO_ROOT / "artifacts/conformance/latest/bead_closure_receipts_e2e.jsonl",
    )
    args = parser.parse_args(argv)

    t0 = time.perf_counter()
    report = check_issues_jsonl(args.issues_jsonl)
    duration_ms = round((time.perf_counter() - t0) * 1000.0, 3)

    try:
        import franken_networkx as fnx
        import networkx as nx

        so_sha256 = hashlib.sha256(Path(fnx._fnx.__file__).read_bytes()).hexdigest()
        fnx_ver = getattr(fnx, "__version__", "0.1.0")
        nx_ver = nx.__version__
    except Exception:
        so_sha256 = "unavailable"
        fnx_ver = "0.1.0"
        nx_ver = "unknown"

    input_sha256 = hashlib.sha256(args.issues_jsonl.read_bytes()).hexdigest()
    jsonl_records = [
        {
            "ts": dt.datetime.now(dt.timezone.utc).isoformat(),
            "case_id": f"bead_receipt::{entry['id']}",
            "input_sha256": input_sha256,
            "fnx_version": fnx_ver,
            "nx_version": nx_ver,
            "so_sha256": so_sha256,
            "graph_class": "BeadWorkGraph",
            "construction_path": str(args.issues_jsonl.name),
            "expected": "has_receipt=True",
            "actual": f"has_receipt={entry['has_receipt']}",
            "pass": bool(entry["has_receipt"]),
            "duration_ms": duration_ms,
        }
        for entry in report["checked_beads"]
    ]
    args.output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    args.output_jsonl.write_text(
        "\n".join(json.dumps(r, sort_keys=True) for r in jsonl_records) + "\n",
        encoding="utf-8",
    )

    if not report["passed"]:
        for v in report["violations"]:
            print(
                f"BEAD RECEIPT VIOLATION: {v['id']} (labels={v['labels']}) lacks machine-parsable receipt in close_reason/comments",
                file=sys.stderr,
            )
        return 1

    print(
        f"BEAD RECEIPT GATE PASSED: {report['total_checked']} labelled closed beads and "
        f"{len(report['historical_checks'])} historical incident annotations verified."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
