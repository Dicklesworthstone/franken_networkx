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


def test_khz_spread_pct_reports_a_clock_swing():
    """br-r37-c1-jycsb: a row taken while the core clock moved is not comparable.

    On a `powersave` host an idle core clocks DOWN, so this is the covariate
    that may explain the 1.66x process-level split that load alone did not.
    """
    guard = _guard([20.0] * 6, [0.9] * 6)
    guard.khz = [4_200_000, 4_200_000, 3_200_000, 4_200_000, 4_100_000, 4_200_000]
    assert guard.khz_spread_pct == pytest.approx(100.0 * 1_000_000 / 4_200_000, rel=1e-6)


def test_khz_spread_is_zero_at_a_steady_clock():
    guard = _guard([20.0] * 4, [0.9] * 4)
    guard.khz = [4_200_000] * 4
    assert guard.khz_spread_pct == 0.0


def test_unreadable_clock_degrades_to_a_note_not_a_crash():
    """cpufreq is absent on plenty of hosts; a guard must never break a run."""
    guard = _guard([20.0] * 4, [0.9] * 4)
    guard.khz = [-1, -1, -1, -1]
    assert math.isnan(guard.khz_spread_pct)
    assert "cpu clock unavailable" in guard.provenance_line()


def test_provenance_line_carries_the_clock_when_available():
    guard = _guard([20.0] * 4, [0.9] * 4)
    guard.khz = [4_200_000, 3_200_000, 4_200_000, 4_100_000]
    line = guard.provenance_line()
    for token in ("cpu clock median", "swing"):
        assert token in line, token


def test_sample_collects_the_clock_series():
    """Two clock samples per round: one at sample() before the round's work and
    one at record_ratio() after it. See br-r37-c1-jycsb -- a pre-work sample
    alone reads an unboosted core."""
    guard = WindowGuard()
    for _ in range(4):
        guard.sample()
        guard.record_ratio(0.5)
    assert len(guard.khz) == 8


def test_record_ratio_also_samples_the_clock():
    """br-r37-c1-jycsb: sample() runs BEFORE a round's work, so it reads a
    pre-boost clock. Bracketing each round with a post-work sample is what keeps
    an idle-core reading from being mistaken for a benchmark condition."""
    guard = WindowGuard()
    for _ in range(3):
        guard.sample()
        guard.record_ratio(1.0)
    assert len(guard.khz) == 6, "each round should contribute a pre- and post-work clock"
    assert len(guard.loads) == 3
    assert len(guard.ratios) == 3


def test_duty_cycle_flags_an_idle_sampled_window():
    """The guard against this module's own worst mistake.

    A clock reading only describes the work if the process was BUSY when taken.
    Sampling in a tight loop with no work between calls once produced a 1429 MHz
    reading that was reported as a 3.0x host-wide swing; it was a property of an
    idle process.
    """
    guard = _guard([20.0] * 4, [0.9] * 4)
    guard.khz = [3_400_000] * 4
    guard._wall = [0.0, 2e-5, 4e-5, 6e-5]     # samples 20us apart: no work bracketed
    guard._cpu = [0.0, 2e-5, 4e-5, 6e-5]      # duty ~1.0 -- reading /proc IS cpu work
    assert guard.duty_cycle == pytest.approx(1.0)
    assert guard.median_interval_s == pytest.approx(2e-5)
    assert guard.verdict == "IDLE-SAMPLED", (
        "duty cycle cannot detect this; the wall interval is what distinguishes it"
    )


def test_duty_cycle_passes_a_busy_window():
    guard = _guard([20.0] * 4, [0.9] * 4)
    guard.khz = [4_200_000] * 4
    guard._wall = [0.0, 1.0, 2.0, 3.0]
    guard._cpu = [0.0, 0.99, 1.98, 2.97]
    assert guard.duty_cycle == pytest.approx(0.99)
    assert guard.median_interval_s == pytest.approx(1.0)
    assert guard.verdict != "IDLE-SAMPLED"


def test_idle_sampling_outranks_the_correlation_flag():
    """An idle-sampled window's correlations are not worth interpreting."""
    guard = _guard(
        [4.0, 5.0, 6.0, 7.0], [1.00, 0.96, 0.92, 0.88]
    )
    guard._wall = [0.0, 3e-5, 6e-5, 9e-5]
    guard._cpu = [0.0, 3e-5, 6e-5, 9e-5]
    assert guard.verdict == "IDLE-SAMPLED"


def test_interval_metrics_are_nan_before_two_samples():
    assert math.isnan(WindowGuard().duty_cycle)
    assert math.isnan(WindowGuard().median_interval_s)


def test_real_sampling_records_wall_and_cpu():
    guard = WindowGuard()
    for _ in range(3):
        guard.sample()
        guard.record_ratio(1.0)
    assert len(guard._wall) == 3 and len(guard._cpu) == 3
    assert "duty" in guard.provenance_line()


def test_per_arm_clock_skew_is_detected():
    """Arm-correlated bias is NOT cancelled by the balanced square.

    A common-mode ramp affects both arms and interleaving removes it. A clock
    difference that tracks WHICH ARM is running does not cancel, and round-level
    sampling cannot see it at all.
    """
    guard = WindowGuard()
    guard.arm_khz = {"nx": [4_200_000] * 5, "fnx": [3_800_000] * 5}
    guard.arm_loads = {"nx": [20.0] * 5, "fnx": [20.0] * 5}
    assert guard.arm_khz_median("nx") == 4_200_000
    assert guard.arm_khz_skew_pct == pytest.approx(100.0 * 400_000 / 3_800_000)
    guard._wall = [0.0, 1.0, 2.0]
    guard._cpu = [0.0, 1.0, 2.0]
    assert guard.verdict == "ARM-CLOCK-SKEW"


def test_matched_arms_do_not_trip_the_skew_flag():
    guard = WindowGuard()
    guard.arm_khz = {"nx": [4_200_000] * 5, "fnx": [4_190_000] * 5}
    guard.arm_loads = {"nx": [20.0] * 5, "fnx": [20.0] * 5}
    guard._wall = [0.0, 1.0, 2.0]
    guard._cpu = [0.0, 1.0, 2.0]
    assert guard.arm_khz_skew_pct < 1.0
    assert guard.verdict != "ARM-CLOCK-SKEW"


def test_idle_sampling_outranks_arm_skew():
    """An idle-sampled window's per-arm clocks are not worth interpreting."""
    guard = WindowGuard()
    guard.arm_khz = {"nx": [4_200_000] * 5, "fnx": [3_000_000] * 5}
    guard.arm_loads = {"nx": [20.0] * 5, "fnx": [20.0] * 5}
    guard._wall = [0.0, 2e-5, 4e-5]
    guard._cpu = [0.0, 2e-5, 4e-5]
    assert guard.verdict == "IDLE-SAMPLED"


def test_arm_fragment_names_both_arms():
    guard = WindowGuard()
    for arm in ("nx", "fnx"):
        guard.arm_khz[arm] = [4_000_000]
        guard.arm_loads[arm] = [12.5]
    frag = guard.arm_fragment()
    assert "nx:" in frag and "fnx:" in frag and "skew" in frag


def test_arm_sampling_is_absent_by_default():
    """Harnesses that do not call sample_arm must not gain a bogus fragment."""
    assert WindowGuard().arm_fragment() == ""
    assert math.isnan(WindowGuard().arm_khz_skew_pct)


def test_same_core_pct_detects_arms_on_different_cores():
    """A ratio whose arms sat on different cores can be a frequency ratio.

    Cores run at 1429-3943 MHz simultaneously on this host, so this is the check
    that makes "both arms were comparable" a fact rather than an assumption.
    """
    guard = WindowGuard()
    guard.arm_cpus = {"nx": [5, 5, 5, 5], "fnx": [9, 9, 9, 9]}
    assert guard.same_core_pct == 0.0
    assert guard.distinct_cores == 2


def test_same_core_pct_is_100_when_arms_share_a_core():
    guard = WindowGuard()
    guard.arm_cpus = {"nx": [7, 7, 7, 7], "fnx": [7, 7, 7, 7]}
    assert guard.same_core_pct == 100.0
    assert guard.distinct_cores == 1


def test_same_core_pct_counts_partial_migration():
    guard = WindowGuard()
    guard.arm_cpus = {"nx": [7, 7, 3, 7], "fnx": [7, 7, 7, 7]}
    assert guard.same_core_pct == pytest.approx(75.0)


def test_same_core_is_nan_without_two_arms():
    guard = WindowGuard()
    guard.arm_cpus = {"nx": [1, 1]}
    assert math.isnan(guard.same_core_pct)


def test_arm_fragment_reports_core_agreement():
    guard = WindowGuard()
    for arm in ("nx", "fnx"):
        guard.arm_khz[arm] = [4_000_000]
        guard.arm_loads[arm] = [12.5]
        guard.arm_cpus[arm] = [7]
    frag = guard.arm_fragment()
    assert "same-core 100%" in frag and "1 core(s)" in frag
