"""The upstream-suite ratchet must be able to fail (hhj5p.3).

scripts/run_upstream_networkx_suite.py runs networkx's own tests with fnx as
the test backend and holds them to artifacts/upstream_suite/ratchet_v1.json.
A ratchet that cannot fail is worse than none, so the negative cases here are
the point: a planted fnx regression, a pass count under the floor, and an
--update that tries to admit a new failure must each be refused.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import networkx as nx
import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "run_upstream_networkx_suite.py"
COVERING = "networkx.algorithms.tests.test_covering"


def _load_runner():
    spec = importlib.util.spec_from_file_location("run_upstream_networkx_suite", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    # dataclasses resolve string annotations through sys.modules[cls.__module__]
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


runner = _load_runner()


def _ratchet(allowed=None, min_passed=0):
    return {
        "schema": runner.SCHEMA,
        "networkx_version": nx.__version__,
        "min_passed": min_passed,
        "allowed_failures": dict(allowed or {}),
    }


def _result(passed=0, failed=(), errors=(), ran=()):
    failed, errors = set(failed), set(errors)
    return runner.RunResult(
        passed=passed, failed=failed, errors=errors, ran=set(ran) | failed | errors
    )


def test_parse_junit_counts_each_outcome_once(tmp_path):
    junit = tmp_path / "junit.xml"
    junit.write_text(
        textwrap.dedent(
            """\
            <testsuites><testsuite>
              <testcase classname="pkg.test_a.TestX" name="test_ok"/>
              <testcase classname="pkg.test_a.TestX" name="test_bad"><failure message="x"/></testcase>
              <testcase classname="pkg.test_b" name="test_boom"><error message="y"/></testcase>
              <testcase classname="pkg.test_b" name="test_skip"><skipped message="z"/></testcase>
            </testsuite></testsuites>
            """
        )
    )
    result = runner.parse_junit(junit)
    assert result.passed == 1
    assert result.skipped == 1
    assert result.failed == {"pkg.test_a.TestX::test_bad"}
    assert result.errors == {"pkg.test_b::test_boom"}
    assert len(result.ran) == 4


def test_a_failure_outside_the_ratchet_is_refused():
    ratchet = _ratchet({"m::allowed": "reason"})
    verdict = runner.compare(ratchet, _result(failed={"m::allowed", "m::new"}), full_run=True)
    assert verdict.new_failures == ["m::new"]
    assert not verdict.ok


def test_errors_count_as_failures():
    verdict = runner.compare(_ratchet(), _result(errors={"m::fixture"}), full_run=True)
    assert verdict.new_failures == ["m::fixture"]


def test_allowed_failures_pass_the_check():
    ratchet = _ratchet({"m::allowed": "reason"}, min_passed=10)
    assert runner.compare(ratchet, _result(passed=10, failed={"m::allowed"}), full_run=True).ok


def test_the_pass_floor_binds_full_runs_only():
    ratchet = _ratchet(min_passed=10)
    full = runner.compare(ratchet, _result(passed=9), full_run=True)
    assert full.pass_floor_breach == (9, 10)
    assert not full.ok
    assert runner.compare(ratchet, _result(passed=9), full_run=False).ok


def test_now_passing_names_only_tests_that_ran():
    ratchet = _ratchet({"m::fixed": "r", "m::elsewhere": "r"})
    verdict = runner.compare(ratchet, _result(passed=1, ran={"m::fixed"}), full_run=False)
    assert verdict.now_passing == ["m::fixed"]


def test_update_only_moves_forward():
    ratchet = _ratchet({"m::fixed": "r1", "m::still": "r2"}, min_passed=5)
    advanced = runner.advance(ratchet, _result(passed=7, failed={"m::still"}), {"run": 1})
    assert advanced["allowed_failures"] == {"m::still": "r2"}
    assert advanced["min_passed"] == 7
    lowered = runner.advance(ratchet, _result(passed=3, failed={"m::still"}), {"run": 2})
    assert lowered["min_passed"] == 5
    with pytest.raises(ValueError, match="refusing to admit new failures"):
        runner.advance(ratchet, _result(passed=7, failed={"m::new"}), {"run": 3})


def _run_script(tmp_path, ratchet, extra_pythonpath=None):
    ratchet_path = tmp_path / "ratchet.json"
    ratchet_path.write_text(json.dumps(ratchet))
    env = dict(os.environ)
    if extra_pythonpath:
        env["PYTHONPATH"] = os.pathsep.join(
            [str(extra_pythonpath), *filter(None, [env.get("PYTHONPATH")])]
        )
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--ratchet", str(ratchet_path), "--target", COVERING],
        capture_output=True, text=True, env=env, timeout=600,
    )


def test_live_subset_run_passes_against_its_ratchet(tmp_path):
    proc = _run_script(tmp_path, _ratchet())
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "0 failed, 0 errors" in proc.stdout


def test_a_planted_fnx_regression_fails_the_live_run(tmp_path):
    # Invert fnx's is_edge_cover inside the suite's interpreter only.
    plant = tmp_path / "plant"
    plant.mkdir()
    (plant / "sitecustomize.py").write_text(
        textwrap.dedent(
            """\
            import franken_networkx.backend as _backend
            _orig = _backend._SUPPORTED_ALGORITHMS["is_edge_cover"]
            _backend._SUPPORTED_ALGORITHMS["is_edge_cover"] = lambda G, cover: not _orig(G, cover)
            """
        )
    )
    proc = _run_script(tmp_path, _ratchet(), extra_pythonpath=plant)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "NEW FAILURE (not in the ratchet): " in proc.stdout
    assert "TestIsEdgeCover" in proc.stdout
