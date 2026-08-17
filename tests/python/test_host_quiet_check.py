"""The quiescence predictor must mirror the harness gate, not approximate it.

br-r37-c1-d4xot. `perf_harness.require_host_wide_quiescence` retries for up to
300 one-second windows before refusing, so on a busy fleet a doomed run costs
five minutes to discover it was doomed. `scripts/host_quiet_check.py` answers the
same question in about a second.

The risk with such a tool is DRIFT: if it hardcodes the bound or the scope, it
will one day say "worth attempting" about a host the gate rejects, and cost
exactly the five minutes it exists to save. So these tests pin that it reads the
harness's own constants and scope function rather than copies of them.

They also pin the import shim. `perf_harness` defines `@dataclass` types, and
dataclasses resolves `__module__` through `sys.modules` - loading it via
`spec_from_file_location` WITHOUT registering it first dies in
`dataclasses._is_type` with an opaque "'NoneType' object has no attribute
'__dict__'". That is a real failure this file caught.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "host_quiet_check.py"
HARNESS = REPO / "scripts" / "perf_harness.py"


def _load():
    spec = importlib.util.spec_from_file_location("hqc_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["hqc_under_test"] = module
    spec.loader.exec_module(module)
    return module


def test_it_imports_the_harness_without_dying_on_dataclasses():
    """The regression this file was written after."""
    mod = _load()
    harness = mod._harness()
    assert hasattr(harness, "HOST_WIDE_MAX_BUSY_FRACTION")


def test_constants_come_from_the_harness_not_copies():
    """DRIFT is the failure mode: a stale copy would mispredict admission."""
    mod = _load()
    harness = mod._harness()
    _ok, _offenders, info = mod.check(1)
    assert info["bound"] == harness.HOST_WIDE_MAX_BUSY_FRACTION
    assert info["sample_s"] == harness.HOST_WIDE_ADMISSION_SAMPLE_S
    assert info["clear_windows_required"] == harness.HOST_WIDE_ADMISSION_CLEAR_WINDOWS
    assert info["max_windows"] == harness.HOST_WIDE_ADMISSION_MAX_WINDOWS


def test_scope_matches_the_harness_scope_function():
    mod = _load()
    harness = mod._harness()
    scope, _src = harness._host_wide_cpu_scope()
    _ok, _off, info = mod.check(1)
    assert info["scope_size"] == len(scope)


def test_source_hardcodes_no_threshold():
    """A literal 0.20 in this file would be the drift this tool must not have."""
    source = SCRIPT.read_text()
    body = source.split('"""', 2)[-1]  # skip the module docstring
    assert "0.20" not in body and "0.2 " not in body


def test_it_answers_fast_and_exits_nonzero_when_busy():
    """It must not inherit the harness's retry budget."""
    start = time.perf_counter()
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)], capture_output=True, text=True, timeout=120
    )
    elapsed = time.perf_counter() - start
    assert elapsed < 30, f"took {elapsed:.1f}s; must not run the full retry budget"
    assert proc.returncode in (0, 1)
    assert "gate:" in proc.stdout
    if proc.returncode == 1:
        assert "WOULD REFUSE" in proc.stdout
    else:
        assert "WOULD ATTEMPT" in proc.stdout
        assert "Advisory only" in proc.stdout


def test_it_never_claims_admission():
    """A pass means 'worth attempting', never 'admitted' - the gate still runs."""
    source = SCRIPT.read_text()
    assert "Advisory only" in source
    assert "does not weaken" in source.lower() or "DOES NOT WEAKEN" in source
