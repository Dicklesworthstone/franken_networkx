"""Host-wide perf-harness admission rejects overlapping invocations."""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
HARNESS_PATH = REPO_ROOT / "scripts" / "perf_harness.py"


def _load_harness():
    module_name = f"perf_harness_test_{os.getpid()}"
    spec = importlib.util.spec_from_file_location(module_name, HARNESS_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_overlapping_harness_lease_reports_the_live_holder(tmp_path):
    harness = _load_harness()
    path = tmp_path / "perf-harness.lock"

    with harness.BenchmarkLease("first", path):
        with pytest.raises(RuntimeError, match="another perf_harness.py invocation") as error:
            with harness.BenchmarkLease("second", path):
                raise AssertionError("the second lease must not be admitted")

    assert '"suite": "first"' in str(error.value)


def test_released_harness_lease_allows_the_next_invocation(tmp_path):
    harness = _load_harness()
    path = tmp_path / "perf-harness.lock"

    with harness.BenchmarkLease("first", path):
        pass
    with harness.BenchmarkLease("second", path) as lease:
        assert lease["suite"] == "second"
