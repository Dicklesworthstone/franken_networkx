"""Tests for scripts/bench_window_guard.py — the per-round load/volatility instrument.

The module exists because a single `uptime` before and after a benchmark cannot
tell "quiet throughout" apart from "quiet at both ends with a spike in the
middle", and the fleet finding is that VOLATILITY rather than absolute load is
what blocks certification.

These tests pin the two properties that make the instrument worth trusting:

  * `spread` and `iqr` DISAGREE in the informative case — one excursion inflates
    spread while leaving iqr small, sustained churn moves both. A summary that
    collapsed them into one number would hide exactly the distinction the
    instrument was built to draw.
  * `corr_load_ratio` is the direct test of whether contention reached the
    measurement, and it must be near zero when the ratio is independent of load
    even if the load series itself is wild.

They are ordinary unit tests over synthetic series, so they carry no timing and
cannot themselves be perturbed by load — which matters, since this file has to be
runnable in exactly the windows where benchmarking is forbidden.
"""

from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "bench_window_guard",
    Path(__file__).resolve().parents[2] / "scripts" / "bench_window_guard.py",
)
bench_window_guard = importlib.util.module_from_spec(_SPEC)
# Registered BEFORE exec: @dataclass resolves annotations via
# sys.modules[cls.__module__], which is None for an unregistered module and
# raises AttributeError at class-creation time.
sys.modules["bench_window_guard"] = bench_window_guard
_SPEC.loader.exec_module(bench_window_guard)
WindowGuard = bench_window_guard.WindowGuard


def _guard(loads, ratios=None):
    guard = WindowGuard()
    guard.loads = list(loads)
    guard.ratios = list(ratios) if ratios is not None else []
    return guard


def test_reads_the_real_loadavg():
    value = bench_window_guard.read_loadavg()
    assert isinstance(value, float)
    assert value >= 0.0


def test_level_is_the_median_not_the_endpoints():
    """A spike in the middle must not move the level much.

    Recording only the first and last sample is the failure mode this module
    replaces; the median over the series is what makes the level robust.
    """
    guard = _guard([8.0, 8.0, 90.0, 8.0, 8.0])
    assert guard.level == 8.0


def test_spread_and_iqr_disagree_on_a_single_spike():
    """THE distinction the instrument exists to draw.

    One excursion: spread is huge, iqr stays small. If both moved together the
    two numbers would be redundant and a spike would be indistinguishable from
    sustained churn.
    """
    spike = _guard([8.0] * 10 + [90.0] + [8.0] * 10)
    assert spike.spread == pytest.approx(82.0)
    assert spike.iqr == pytest.approx(0.0)


def test_spread_and_iqr_agree_on_sustained_churn():
    churn = _guard([5.0, 40.0, 6.0, 45.0, 7.0, 50.0, 8.0, 55.0, 9.0, 60.0])
    assert churn.spread == pytest.approx(55.0)
    assert churn.iqr > 30.0, "sustained churn must move the iqr, unlike a spike"


def test_relative_volatility_scales_with_level():
    """A swing of 16 is catastrophic at level 8 and unremarkable at level 80."""
    quiet_but_swinging = _guard([4.0, 20.0, 4.0, 20.0, 4.0, 20.0, 4.0, 20.0])
    loud_but_steady = _guard([80.0, 82.0, 80.0, 82.0, 80.0, 82.0, 80.0, 82.0])
    assert quiet_but_swinging.relative_volatility > loud_but_steady.relative_volatility
    assert loud_but_steady.relative_volatility < 0.1


def test_correlation_is_zero_when_the_ratio_ignores_load():
    """The result that would VALIDATE the balanced square under contention."""
    loads = [5.0, 60.0, 7.0, 55.0, 6.0, 70.0, 8.0, 65.0]
    ratios = [0.9] * len(loads)
    assert _guard(loads, ratios).corr_load_ratio == 0.0


def test_correlation_is_strong_when_load_drags_the_ratio():
    """The result that would INVALIDATE a row regardless of endpoint loadavg."""
    loads = [5.0, 10.0, 15.0, 20.0, 25.0, 30.0, 35.0, 40.0]
    ratios = [1.00, 0.98, 0.96, 0.94, 0.92, 0.90, 0.88, 0.86]
    corr = _guard(loads, ratios).corr_load_ratio
    assert corr < -0.9


def test_verdict_prefers_perturbation_over_level():
    """A LOADED but unperturbed window is usable; a perturbed quiet one is not.

    This encodes the fleet finding: stable-and-moderate beats quiet-and-spiky.
    """
    loaded_steady = _guard([40.0] * 8, [0.5] * 8)
    assert loaded_steady.verdict == "LOADED-STABLE"

    quiet_perturbed = _guard(
        [4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0],
        [1.00, 0.98, 0.96, 0.94, 0.92, 0.90, 0.88, 0.86],
    )
    assert quiet_perturbed.verdict == "PERTURBED"


def test_quiet_and_steady_is_stable():
    assert _guard([8.0] * 8, [0.5] * 8).verdict == "STABLE"


def test_volatile_window_is_flagged_even_without_ratios():
    """Ratios may be absent (a survey run); volatility must still be reported."""
    guard = _guard([2.0, 30.0, 3.0, 28.0, 2.5, 31.0, 2.0, 29.0])
    assert math.isnan(guard.corr_load_ratio)
    assert guard.verdict == "VOLATILE"


def test_degenerate_inputs_do_not_raise():
    """A guard is stamped onto every row, so it must never break a benchmark."""
    empty = WindowGuard()
    assert math.isnan(empty.level)
    assert math.isnan(empty.corr_load_ratio)
    assert empty.verdict in {"STABLE", "VOLATILE", "PERTURBED", "LOADED-STABLE"}
    two = _guard([8.0, 9.0], [0.5, 0.5])
    assert math.isnan(two.iqr)
    assert math.isnan(two.corr_load_ratio)


def test_constant_load_gives_zero_correlation_not_a_crash():
    """statistics.correlation raises on a constant input; the guard must not."""
    assert _guard([8.0] * 8, [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]).corr_load_ratio == 0.0


def test_sample_and_record_build_the_series():
    guard = WindowGuard()
    for _ in range(5):
        guard.sample()
        guard.record_ratio(0.5)
    assert len(guard.loads) == 5
    assert len(guard.ratios) == 5
    assert "corr(load,ratio)" in guard.report()
    assert "loadavg per round" in guard.provenance_line()


def test_provenance_line_carries_the_numbers_a_banked_row_needs():
    line = _guard([8.0, 9.0, 8.5, 30.0, 8.0, 9.0], [0.5] * 6).provenance_line()
    for token in ("median", "min", "max", "iqr", "relvol", "corr(load, per-round ratio)"):
        assert token in line, token


def test_provenance_line_is_empty_safe_when_runnable_was_never_sampled():
    """Found by this file failing: `min()` over an empty runnable series raised.

    A guard is stamped onto every banked row, so a hand-built guard — or a
    caller that only recorded loads — must degrade to a note rather than take
    the benchmark down.
    """
    line = _guard([8.0, 9.0, 8.5, 30.0], [0.5] * 4).provenance_line()
    assert "runnable unsampled" in line
    assert "corr(runnable, per-round ratio)" in line


def test_runnable_spread_sees_what_the_load_average_cannot():
    """The defect that motivated `read_runnable`, as a unit test.

    A run shorter than the load average's ~5s refresh reads one identical value
    every round: `spread` is 0.00 and the window looks perfectly stable. The
    instantaneous runnable count still moves, and the verdict must follow it.
    """
    guard = _guard([60.0] * 12, [0.9] * 12)
    guard.runnable = [24, 30, 25, 38, 26, 31, 24, 29, 27, 33, 25, 30]
    assert guard.spread == 0.0, "the averaged signal is blind here, by construction"
    assert guard.runnable_spread == 14.0


def test_certifiable_gate_rejects_a_falling_load(monkeypatch):
    """The exact shape this pane was handed: 1-min 10.2 against 5-min 34.9.

    Eyeballing the 1-minute number alone calls that a quiet host. It is a host
    that was heavily loaded three minutes ago and may be again, which is the
    volatility the fleet identified as the real blocker.
    """
    monkeypatch.setattr(bench_window_guard, "read_loadavg_triple", lambda: (10.2, 34.9, 36.0))
    ok, reason = bench_window_guard.window_is_certifiable()
    assert not ok
    assert "level too high" in reason


def test_certifiable_gate_rejects_a_close_but_unstable_pair(monkeypatch):
    """Both LOW yet not close: 18.4 against 27.6 is a 1.5x gap, not a window.

    The first threshold this pane wrote admitted exactly this and had to be
    tightened; the case is pinned so it cannot drift back.
    """
    monkeypatch.setattr(bench_window_guard, "read_loadavg_triple", lambda: (18.4, 27.6, 30.0))
    ok, reason = bench_window_guard.window_is_certifiable()
    assert not ok
    assert "unstable" in reason


def test_certifiable_gate_accepts_low_and_close(monkeypatch):
    monkeypatch.setattr(bench_window_guard, "read_loadavg_triple", lambda: (8.4, 9.1, 20.0))
    ok, reason = bench_window_guard.window_is_certifiable()
    assert ok
    assert "stable" in reason


def test_certifiable_gate_rejects_high_but_stable(monkeypatch):
    """Stable is necessary, not sufficient — the level bound still applies."""
    monkeypatch.setattr(bench_window_guard, "read_loadavg_triple", lambda: (60.0, 61.0, 60.0))
    ok, _ = bench_window_guard.window_is_certifiable()
    assert not ok
