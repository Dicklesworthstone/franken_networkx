"""End-to-end and negative-case tests for the wvztf.2 empirical-complexity slope gate."""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

import run_empirical_complexity_gate as gate  # noqa: E402


def test_empirical_complexity_catalogue_and_jsonl_artifacts_are_valid():
    catalogue_path = REPO_ROOT / "artifacts/perf/latest/empirical_complexity_catalogue_v1.json"
    jsonl_path = REPO_ROOT / "artifacts/perf/latest/empirical_complexity_e2e.jsonl"
    assert catalogue_path.exists(), "missing empirical_complexity_catalogue_v1.json"
    assert jsonl_path.exists(), "missing empirical_complexity_e2e.jsonl"

    report = json.loads(catalogue_path.read_text(encoding="utf-8"))
    assert report["schema_version"] == "1.0.0"
    assert report["summary"]["total_cases"] == 54
    assert report["summary"]["passed_green"] == 50
    assert report["summary"]["allowlisted_debt"] == 4
    assert report["summary"]["failed"] == 0
    assert report["summary"]["stale_allowlist"] == 0

    rows_by_key = {(r["op_id"], r["graph_class"]): r for r in report["rows"]}
    for cls_name in ("Graph", "DiGraph", "MultiGraph", "MultiDiGraph"):
        assert rows_by_key[("remove_node", cls_name)]["status"] == "PASS"
        assert rows_by_key[("remove_node", cls_name)]["fnx_effective_slope"] <= 0.15
        assert rows_by_key[("copy_shallow", cls_name)]["status"] == "ALLOWLISTED_DEBT"
        assert (
            rows_by_key[("copy_shallow", cls_name)]["allowlisted_debt_bead"]
            == "br-r37-c1-epic-storage-architecture-yr2oc.3"
        )

    lines = [
        json.loads(line)
        for line in jsonl_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(lines) == 54
    required_keys = {
        "ts",
        "case_id",
        "input_sha256",
        "fnx_version",
        "nx_version",
        "so_sha256",
        "graph_class",
        "construction_path",
        "expected",
        "actual",
        "pass",
        "duration_ms",
    }
    for rec in lines:
        assert required_keys.issubset(rec.keys())
        assert rec["pass"] is True


def test_slope_gate_negative_cases_fail_closed_on_copy_shallow_and_planted_linear_scan():
    """wvztf.2 negative test:
    1. Unfixed copy.copy (yr2oc.3) fails closed when disallowing the debt allowlist.
    2. A planted O(N) hidden scan in Python or native code fails closed (slope ~ 1.0 > 0.15).
    3. An O(1) operation (has_node / remove_node) passes (slope <= 0.15).
    """
    sizes = (250, 1000, 4000, 16000)

    # 1. Unfixed copy.copy fails raw_pass (native O(N) loop)
    copy_row = gate.measure_op_across_scales(
        op_id="copy_shallow",
        cls_name="Graph",
        theoretical_max_slope=0.0,
        runner_factory=lambda g, _n: (lambda: copy.copy(g)),
        sizes=sizes,
        iters=4,
    )
    assert copy_row["raw_pass"] is False, f"expected raw failure on copy.copy, got {copy_row}"
    assert copy_row["fnx_effective_slope"] >= 0.75

    # 2. Planted O(N) hidden scan in a supposedly O(1) operation fails closed
    planted_row = gate.measure_op_across_scales(
        op_id="planted_hidden_linear_scan",
        cls_name="Graph",
        theoretical_max_slope=0.0,
        runner_factory=lambda g, n: (
            (lambda: sum(1 for _ in g.nodes()))
            if type(g).__module__.startswith("franken_networkx")
            else (lambda u=n // 2: u in g)
        ),
        sizes=sizes,
        iters=5,
    )
    assert planted_row["status"] == "FAIL"
    assert planted_row["raw_pass"] is False
    assert planted_row["fnx_inst_slope"] >= 0.90

    # 3. O(1) operation passes
    o1_row = gate.measure_op_across_scales(
        op_id="has_node",
        cls_name="Graph",
        theoretical_max_slope=0.0,
        runner_factory=lambda g, n: (lambda u=n // 2: u in g),
        sizes=sizes,
        iters=10,
    )
    assert o1_row["status"] == "PASS"
    assert o1_row["raw_pass"] is True
    assert abs(o1_row["fnx_effective_slope"]) <= 0.15
    jsonl_sha = hashlib.sha256(
        (REPO_ROOT / "artifacts/perf/latest/empirical_complexity_e2e.jsonl").read_bytes()
    ).hexdigest()
    assert len(jsonl_sha) == 64
