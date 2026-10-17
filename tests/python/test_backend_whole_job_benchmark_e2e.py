"""End-to-end and negative-case tests for the wvztf.5 backend-mode whole-job benchmark."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

import franken_networkx.backend as fnx_backend

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

import run_backend_whole_job_benchmark as bench  # noqa: E402


def test_backend_whole_job_benchmark_artifacts_and_jsonl_are_valid():
    json_path = REPO_ROOT / "artifacts/perf/latest/backend_whole_job_benchmark_v1.json"
    md_path = REPO_ROOT / "artifacts/perf/latest/backend_whole_job_benchmark_v1.md"
    jsonl_path = REPO_ROOT / "artifacts/perf/latest/backend_whole_job_e2e.jsonl"

    assert json_path.exists()
    assert md_path.exists()
    assert jsonl_path.exists()

    report = json.loads(json_path.read_text(encoding="utf-8"))
    assert report["schema_version"] == "1.0.0"
    assert report["summary"]["total_jobs"] == 10
    assert report["summary"]["all_outputs_equal"] is True
    assert len(report["provenance"]["so_sha256"]) == 64

    categories = {r["category"] for r in report["jobs"]}
    assert categories == {"gallery", "pipeline"}
    for job in report["jobs"]:
        assert job["output_parity"] is True
        assert job["cold_cache_on_speedup_vs_nx"] > 0.0
        assert job["warm_cache_on_speedup_vs_nx"] > 0.0
        assert job["cache_off_speedup_vs_nx"] > 0.0

    lines = [
        json.loads(line)
        for line in jsonl_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(lines) == 10
    for rec in lines:
        assert rec["pass"] is True
        assert rec["expected"] == rec["actual"]


def test_backend_whole_job_benchmark_catches_planted_divergent_kernel():
    """wvztf.5 negative test: a planted divergent backend kernel must be caught by
    output equality verification and raise OutputMismatchError."""
    orig = fnx_backend._SUPPORTED_ALGORITHMS["transitivity"]
    try:
        fnx_backend._SUPPORTED_ALGORITHMS["transitivity"] = lambda _G: 0.999999
        with pytest.raises(bench.OutputMismatchError, match="gallery_watts_strogatz_clustering_triangles"):
            bench.run_whole_job_benchmark(trials=1)
    finally:
        fnx_backend._SUPPORTED_ALGORITHMS["transitivity"] = orig

    jsonl_sha = hashlib.sha256(
        (REPO_ROOT / "artifacts/perf/latest/backend_whole_job_e2e.jsonl").read_bytes()
    ).hexdigest()
    assert len(jsonl_sha) == 64
