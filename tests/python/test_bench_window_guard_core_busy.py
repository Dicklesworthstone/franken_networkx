"""Per-core busy gating for the bench window guard.

`window_is_certifiable` reads the MACHINE. A pinned benchmark does not run on the
machine, it runs on two named cores, and those are different questions. Measured
on this host within one minute on 2026-08-17:

    loadavg 32.54          -> the machine rule says BLOCKED
    machine-wide idle 69%  -> looks like a quiet host
    cpu14 busy 35.4%, cpu15 busy 53.2%   -> the cores the bench pins to

All three were true simultaneously. loadavg over-reports because it counts
uninterruptible tasks that are not competing for CPU; machine-wide idle
under-reports for a pinned run because it averages over cores the benchmark will
never touch.

These tests drive `_cpu_ticks` directly rather than sampling the live host, so
they assert the LOGIC and cannot go flaky when the fleet gets busy.
"""

import sys

import pytest

sys.path.insert(0, "/data/projects/franken_networkx/scripts")

import bench_window_guard as guard  # noqa: E402


@pytest.fixture
def fake_ticks(monkeypatch):
    """Drive core_busy_pct from a scripted pair of /proc/stat snapshots."""

    def install(before, after):
        calls = {"n": 0}

        def _ticks(cores):
            snap = before if calls["n"] == 0 else after
            calls["n"] += 1
            return {c: snap[c] for c in cores if c in snap}

        monkeypatch.setattr(guard, "_cpu_ticks", _ticks)
        monkeypatch.setattr(guard.time, "sleep", lambda _s: None)

    return install


def test_busy_pct_is_computed_from_the_DELTA_not_the_totals(fake_ticks):
    """/proc/stat is cumulative since boot, so a single read means nothing."""
    # cpu14: 1000 total ticks pass, 250 of them idle -> 75% busy
    fake_ticks(
        {"cpu14": (10_000, 9_000, 0)},
        {"cpu14": (11_000, 9_250, 0)},
    )
    busy = guard.core_busy_pct([14])
    assert busy[14] == pytest.approx(75.0)


def test_a_core_that_was_busy_since_boot_but_is_idle_now_reads_idle(fake_ticks):
    """The since-boot ratio would call this core busy; the delta calls it free."""
    fake_ticks(
        {"cpu14": (1_000_000, 100_000, 0)},   # 90% busy since boot
        {"cpu14": (1_001_000, 101_000, 0)},   # but 100% idle in this interval
    )
    assert guard.core_busy_pct([14])[14] == pytest.approx(0.0)


def test_cores_are_quiet_blocks_on_the_WORST_core(fake_ticks):
    """One contended seat is enough to spoil a pinned run."""
    fake_ticks(
        {"cpu14": (0, 0, 0), "cpu15": (0, 0, 0)},
        {"cpu14": (1000, 990, 0), "cpu15": (1000, 400, 0)},  # 1% and 60% busy
    )
    ok, msg = guard.cores_are_quiet([14, 15], busy_max=15.0)
    assert ok is False
    assert "CONTENDED" in msg
    assert "cpu15" in msg and "60.0% busy" in msg
    assert "cpu14" in msg, "the quiet core must still be reported, not hidden"


def test_cores_are_quiet_passes_when_both_are_free(fake_ticks):
    fake_ticks(
        {"cpu14": (0, 0, 0), "cpu15": (0, 0, 0)},
        {"cpu14": (1000, 980, 0), "cpu15": (1000, 950, 0)},  # 2% and 5%
    )
    ok, msg = guard.cores_are_quiet([14, 15], busy_max=15.0)
    assert ok is True
    assert "quiet" in msg
    assert "cpu14" in msg and "cpu15" in msg


def test_missing_cores_fail_closed(fake_ticks):
    """No sample is not the same as a quiet sample."""
    fake_ticks({}, {})
    ok, msg = guard.cores_are_quiet([99])
    assert ok is False
    assert "no per-core samples" in msg


def test_zero_elapsed_ticks_are_skipped_not_divided_by(fake_ticks):
    fake_ticks({"cpu14": (500, 400, 0)}, {"cpu14": (500, 400, 0)})
    assert guard.core_busy_pct([14]) == {}


def test_the_machine_rule_and_the_core_rule_are_independent():
    """They answer different questions, so neither substitutes for the other."""
    assert guard.window_is_certifiable is not guard.cores_are_quiet
    import inspect

    machine = inspect.signature(guard.window_is_certifiable).parameters
    cores = inspect.signature(guard.cores_are_quiet).parameters
    assert "level_max" in machine and "cores" not in machine
    assert "busy_max" in cores and "level_max" not in cores


def test_bench_core_watch_measures_the_whole_block(monkeypatch):
    """It measures the block, but NOT what I first claimed it measured.

    The original claim — "a pre-run sample answers 'was it quiet?', this answers
    'was it quiet THROUGHOUT?'" — was WRONG, and the first two squares to use it
    disproved it: 99.6% and 99.7% busy during runs whose core was 0.3% busy
    moments earlier. That is the WORKER saturating its own core. A competitor's
    cycles and the benchmark's own are the same cycles here, so a saturating
    workload pins this near 100 regardless of who else is present.

    What it establishes is the converse: a value well BELOW 100 means the worker
    was descheduled and did not have the core. "Did I get the seat", not "is
    anyone else in it". See test_a_saturating_worker_pins_this_near_100 below.
    """
    ticks = iter([1_000, 1_400])  # 400 busy jiffies
    clock = iter([100.0, 104.0])  # over 4 seconds -> 100% busy
    monkeypatch.setattr(guard, "read_cpu_busy_jiffies", lambda _c: next(ticks))
    monkeypatch.setattr(guard.time, "perf_counter", lambda: next(clock))

    g = guard.WindowGuard()
    g.begin_bench_core_watch(28)
    g.end_bench_core_watch()
    assert g.bench_core_id == 28
    assert g.bench_core_busy == pytest.approx(100.0)


def test_bench_core_watch_is_nan_until_used():
    """An unwatched run must not silently report a quiet core."""
    g = guard.WindowGuard()
    assert g.bench_core_busy != g.bench_core_busy  # NaN
    assert g.bench_core_id == -1


def test_end_without_begin_is_a_no_op():
    g = guard.WindowGuard()
    g.end_bench_core_watch()
    assert g.bench_core_busy != g.bench_core_busy  # still NaN, not 0.0


def test_a_too_short_block_is_refused_rather_than_reported(monkeypatch):
    """Jiffy resolution cannot measure a sub-block; NaN beats a wrong number."""
    monkeypatch.setattr(guard, "read_cpu_busy_jiffies", lambda _c: 10)
    clock = iter([100.0, 100.0001])
    monkeypatch.setattr(guard.time, "perf_counter", lambda: next(clock))
    g = guard.WindowGuard()
    g.begin_bench_core_watch(28)
    g.end_bench_core_watch()
    assert g.bench_core_busy != g.bench_core_busy  # NaN


def test_a_saturating_worker_pins_this_near_100_regardless_of_contention(monkeypatch):
    """The metric cannot separate my cycles from a competitor's — that is the point.

    Both scenarios below report ~100% busy: one where the benchmark had the core
    to itself, and one where it shared it. If this number could detect
    contention, those two would differ. They do not, which is exactly why the
    docstring was corrected and why cores_are_quiet() plus the A/A null remain
    the detectors.
    """
    def busy_run(total_busy_jiffies):
        ticks = iter([0, total_busy_jiffies])
        clock = iter([0.0, 4.0])
        monkeypatch.setattr(guard, "read_cpu_busy_jiffies", lambda _c: next(ticks))
        monkeypatch.setattr(guard.time, "perf_counter", lambda: next(clock))
        g = guard.WindowGuard()
        g.begin_bench_core_watch(26)
        g.end_bench_core_watch()
        return g.bench_core_busy

    alone = busy_run(400)          # worker alone, saturating
    shared = busy_run(400)         # worker + competitor, still saturating
    assert alone == pytest.approx(100.0)
    assert shared == pytest.approx(100.0)
    assert alone == shared, "if these differed the metric could gate contention"
