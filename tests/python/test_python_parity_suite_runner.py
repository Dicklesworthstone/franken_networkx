"""scripts/run_python_parity_suite.py must fail when any test is red (hhj5p.1).

The runner is the full-suite gate; the negative cases are the point: a planted
failing test makes the run exit non-zero and names the test, and a host
without enough free disk is refused before anything starts.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "run_python_parity_suite.py"


def _load_runner():
    spec = importlib.util.spec_from_file_location("run_python_parity_suite", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


runner = _load_runner()


def test_parse_summary_reads_the_final_line():
    text = "....F\nFAILED t.py::test_x - assert 0\n3 failed, 10 passed, 2 skipped, 1 xfailed, 1 warning in 1.20s\n"
    counts = runner.parse_summary(text)
    assert (counts["passed"], counts["failed"], counts["skipped"], counts["xfailed"]) == (10, 3, 2, 1)
    assert runner.parse_summary("1 error in 0.10s\n")["errors"] == 1
    assert runner.parse_summary("2 errors, 5 passed in 0.10s\n")["errors"] == 2
    assert runner.parse_summary("no summary here")["passed"] == 0


def test_shards_cover_every_file_once_in_order():
    files = [f"f{i}" for i in range(7)]
    shards = runner.shard(files, 3)
    assert shards == [["f0", "f1", "f2"], ["f3", "f4", "f5"], ["f6"]]


def _suite(tmp_path, *, red):
    tests = tmp_path / "suite"
    tests.mkdir()
    (tests / "test_green.py").write_text("def test_green():\n    assert 1 + 1 == 2\n")
    if red:
        (tests / "test_planted.py").write_text(
            textwrap.dedent(
                """\
                def test_planted_red():
                    assert 1 + 1 == 3
                """
            )
        )
    return tests


def _run(tmp_path, tests, *extra):
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--test-dir", str(tests), "--workers", "2",
         "--files-per-shard", "1", "--log-dir", str(tmp_path / "logs"), *extra],
        capture_output=True, text=True, timeout=600,
    )


def test_a_green_suite_passes(tmp_path):
    proc = _run(tmp_path, _suite(tmp_path, red=False))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "1 passed, 0 failed, 0 errors" in proc.stdout


def test_a_planted_red_test_fails_the_run_and_is_named(tmp_path):
    proc = _run(tmp_path, _suite(tmp_path, red=True))
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "RED shard" in proc.stdout
    assert "test_planted.py::test_planted_red" in proc.stdout
    assert "TOTAL 2 files: 1 passed, 1 failed" in proc.stdout


def test_too_little_free_disk_is_refused_before_running(tmp_path):
    proc = _run(tmp_path, _suite(tmp_path, red=False), "--min-free-gb", str(10**9))
    assert proc.returncode == 2
    assert "refusing to start" in proc.stdout
    assert not (tmp_path / "logs").exists()
