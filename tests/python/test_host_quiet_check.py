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


def test_it_reports_loadavg_and_idle_beside_the_verdict():
    """Both summary stats must appear NEXT TO the per-core answer.

    br-r37-c1-d4xot: two fleet briefs in two days called this host a clean window
    on the strength of a summary statistic. loadavg 12.33 and loadavg 15.94 both
    looked fine and both refused; aggregate idle is no better, because the gate is
    PER-CORE and a minority of saturated cores is diluted by the idle majority -
    measured 15 of 64 CPUs over the bound at 76.7 percent idle. Printing them
    together is what makes the disagreement visible in one line instead of after a
    five-minute refusal.
    """
    mod = _load()
    _ok, _off, info = mod.check(1)
    assert len(info["loadavg"]) == 3
    assert 0.0 <= info["idle_pct"] <= 100.0

    proc = subprocess.run(
        [sys.executable, str(SCRIPT)], capture_output=True, text=True, timeout=120
    )
    assert "loadavg" in proc.stdout
    assert "aggregate idle" in proc.stdout
    assert "NEITHER predicts this gate" in proc.stdout


def test_idle_and_percore_can_disagree_by_construction():
    """The arithmetic behind the warning, so it is not just an assertion.

    N saturated cores out of M give roughly (M-N)/M aggregate idle, so a host can
    read 88 percent idle with ~7 cores pinned and still fail a per-core bound.
    """
    cores, pinned = 64, 7
    aggregate_idle = 100.0 * (cores - pinned) / cores
    assert aggregate_idle > 80.0, "this host would look quiet by the idle statistic"
    # ...while pinned cores sit at 100 percent, far over a 20 percent bound.
    assert 100.0 > 20.0


def test_idle_is_measured_over_an_interval_not_since_boot():
    """/proc/stat counters are CUMULATIVE; a single read is a lifetime average.

    br-r37-c1-d4xot. The first version of this tool read /proc/stat once and
    divided, and therefore printed 76.6-76.7 percent at EVERY load sampled on
    2026-08-17 - a near-idle host and a host running five builds gave the same
    figure, because both are dominated by two days of uptime. A quiet-window
    signal that cannot move is worse than none: it looks like corroboration.

    This is a structural check on `check()` rather than a behavioural one, and
    deliberately so: moving aggregate idle on a 64-core box takes several busy
    cores, and a test has no business loading a shared host to prove a point.
    """
    import inspect

    mod = _load()
    source = inspect.getsource(mod.check)
    assert "idle_b - idle_a" in source, "idle must be a difference of two reads"
    assert "total_b - total_a" in source, "the divisor must be the interval total"
    # The single-read form this replaced.
    assert "int(parts[4]) / max(1, total)" not in source


def test_idle_reading_is_plausible_and_bounded():
    mod = _load()
    _ok, _off, info = mod.check(1)
    assert 0.0 <= info["idle_pct"] <= 100.0

