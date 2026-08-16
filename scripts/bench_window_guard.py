"""Per-round load sampling for balanced-square benchmarks — measure VOLATILITY, not just level.

WHY THIS EXISTS. The fleet finding (mermaid, 2026-08-16) is that the blocker on
certification is host VOLATILITY rather than absolute load: a stable moderate
window beats a brief quiet spike. This pane's own history is consistent with that
and cannot prove it, which is the point of this module.

    loadavg 6.12 at window start, spiking to 24.72   `(u,v) in G.edges`
                                                     ratio CI [0.8954, 1.1021]
                                                     incumbent A/A null 1.1743
    loadavg 8.39-9.13, flat across the block         `G.degree(u)`
                                                     ratio CI [0.8646, 0.8718]
    loadavg 29.63, flat                              `u in G` certified, three
                                                     replicates within 1.4%

The quietest window produced the WORST interval and a 17 percent null; a
sustained loadavg of 29 certified cleanly. But those runs also differed in
DURATION (12000 against 60000 reps per block), and this pane has separately shown
duration alone tightens a fast op's CI by 3-7x. So level, volatility and duration
are mutually confounded in every row banked so far, and no honest conclusion can
be drawn from them about which one matters.

WHAT THIS SEPARATES THEM. A single `uptime` before and after a run cannot
distinguish "quiet throughout" from "quiet at both ends with a spike in the
middle" — which is exactly the failure mode suspected. Sampling per ROUND turns
load into a series that can be correlated against the per-round ratio series the
balanced square already produces:

  * `spread` and `iqr` describe the window's stability independent of its level;
  * `corr_load_ratio` is the DIRECT test — if contention perturbs the measured
    ratio, rounds that ran hot should deviate systematically. A balanced square
    is supposed to cancel a common-mode ramp, so a correlation near zero under
    HIGH volatility is evidence the design is working, and a strong one is
    evidence it is not.

That last number is what no amount of endpoint `uptime` recording can give, and
it is most informative precisely when the host is at its worst — so it can be
collected in windows where certification is forbidden.

USAGE, from a balanced-square harness:

    from bench_window_guard import WindowGuard
    guard = WindowGuard()
    for _ in range(ROUNDS):
        guard.sample()                     # once per round, before its blocks
        ...
        guard.record_ratio(round_ratio)    # the round's A/B ratio
    print(guard.report())

The verdict is advisory. It never rejects a row by itself: this pane's rule is
that a failing gate is not a loss, and a row is judged by REPLICATION.
"""

from __future__ import annotations

import statistics
import time
from dataclasses import dataclass, field


def read_loadavg() -> float:
    """One-minute load average. Read from /proc so it costs no subprocess."""
    with open("/proc/loadavg", encoding="ascii") as handle:
        return float(handle.read().split()[0])


def read_current_cpu() -> int:
    """Which core this process is running on right now; -1 if unreadable.

    br-r37-c1-jycsb: cores run at very different clocks SIMULTANEOUSLY — 1429 to
    3943 MHz observed here at one instant, a 2.76x spread, matching frankenfs's
    2.879x. So a ratio whose two arms sat on different cores can be a frequency
    ratio wearing a benchmark's clothes. Recording the core each arm ran on is
    what turns "both arms were comparable" from an assumption into a fact.
    """
    try:
        return int(open("/proc/self/stat", encoding="ascii").read().split()[38])
    except Exception:  # noqa: BLE001 - never break a benchmark
        return -1


def read_cpu_khz(cpu: int | None = None) -> int:
    """Current clock of the core this process is on, in kHz; -1 if unreadable.

    ADDED BECAUSE LOAD ALONE DID NOT EXPLAIN A 1.66x SPLIT. br-r37-c1-jycsb
    recorded the fnx arm running at 101-104 ns in 3 processes and 160-179 ns in
    21 others, same ELF, same graph, decided at process start. Hash-seed
    randomization was the leading hypothesis and was REFUTED — fixing
    `PYTHONHASHSEED=0` left the distribution unchanged.

    This host runs the `powersave` governor, and the slow readings were taken
    when the 1-minute load was 6.5-8.0 while the 5-minute average was 12.8-14.8
    — a host winding DOWN, whose cores clock down with it. Sampled at loadavg
    22, every core read 4.0-4.3 GHz and the same operation took a tight
    104-109 ns; one sample dipped to 3222 MHz mid-run.

    That is a hypothesis with partial support, not a demonstration: the observed
    frequency range (3.2-4.3 GHz, 1.32x) is the same ORDER as the timing split
    (1.66x) but does not by itself account for all of it, and the slow mode has
    not yet been captured WITH frequency data, because a quiet host cannot be
    manufactured on demand. Recording the clock on every row is what will settle
    it — and it inverts the usual instinct, since it predicts a QUIET window can
    be slower and more variable than a moderately loaded one.
    """
    if cpu is None:
        try:
            cpu = int(open("/proc/self/stat", encoding="ascii").read().split()[38])
        except Exception:  # noqa: BLE001 - never break a benchmark
            return -1
    try:
        with open(
            f"/sys/devices/system/cpu/cpu{cpu}/cpufreq/scaling_cur_freq", encoding="ascii"
        ) as handle:
            return int(handle.read())
    except Exception:  # noqa: BLE001 - not all hosts expose cpufreq
        return -1


def read_loadavg_triple() -> tuple[float, float, float]:
    """The 1-, 5- and 15-minute averages together."""
    with open("/proc/loadavg", encoding="ascii") as handle:
        parts = handle.read().split()
    return float(parts[0]), float(parts[1]), float(parts[2])


def window_is_certifiable(
    level_max: float = 30.0, ratio_max: float = 1.25
) -> tuple[bool, str]:
    """Today's standing rule, machine-checked instead of eyeballed.

    The rule is that the 1- and 5-minute averages must be CLOSE and both LOW.
    Closeness is the half that eyeballing gets wrong: a 1-minute average of 10.1
    against a 5-minute of 32.5 looks like a quiet host and is actually a host
    that was heavily loaded 3 minutes ago and may be again — the volatility
    mermaid identified, and the shape this pane measured when its "quietest
    window of the session" at 6.12 produced a 17 percent A/A null and a 21-point
    ratio interval.

    Returns (ok, reason) rather than raising or sleeping: this pane's standing
    orders forbid wait loops, so a caller checks, and if it is not certifiable
    does code work instead.
    """
    one, five, _ = read_loadavg_triple()
    if one > level_max or five > level_max:
        return False, f"level too high: 1-min {one:.2f}, 5-min {five:.2f} (max {level_max:.0f})"
    hi, lo = max(one, five), min(one, five)
    ratio = hi / lo if lo > 0 else float("inf")
    if ratio > ratio_max:
        return False, (
            f"unstable: 1-min {one:.2f} against 5-min {five:.2f}, "
            f"ratio {ratio:.2f} (max {ratio_max:.2f}) — falling load is not a quiet host"
        )
    return True, f"stable: 1-min {one:.2f}, 5-min {five:.2f}, ratio {ratio:.2f}"


def read_runnable() -> int:
    """Instantaneous count of RUNNABLE processes (field 4, before the slash).

    FOUND BY RUNNING THIS MODULE AGAINST A REAL BENCHMARK, which is the only
    reason it exists. The one-minute load average in `/proc/loadavg` is
    recomputed on a ~5 second timer, so a benchmark whose rounds are shorter
    than that reads the IDENTICAL value every round and the guard reports
    `spread 0.00, iqr 0.00` — a perfectly stable window, from an instrument that
    simply could not see. Observed directly: a 21-round run of
    `Graph G[u][v]` at loadavg 60 returned twenty-one identical samples, while a
    longer run in the same window recorded 59.91 to 67.13.

    That is the same duration trap this pane already documented for benchmarks
    themselves, reappearing one level up in the tool built to police it. The
    runnable count has no averaging window, so it moves within a single round
    and gives the volatility measure something to see on short runs.
    """
    with open("/proc/loadavg", encoding="ascii") as handle:
        return int(handle.read().split()[3].split("/")[0])


@dataclass
class WindowGuard:
    """Collects a per-round load series alongside the per-round ratio series."""

    loads: list[float] = field(default_factory=list)
    ratios: list[float] = field(default_factory=list)
    runnable: list[int] = field(default_factory=list)
    khz: list[int] = field(default_factory=list)
    _wall: list[float] = field(default_factory=list)
    _cpu: list[float] = field(default_factory=list)
    arm_khz: dict[str, list[int]] = field(default_factory=dict)
    arm_loads: dict[str, list[float]] = field(default_factory=dict)
    arm_cpus: dict[str, list[int]] = field(default_factory=dict)

    def sample(self) -> float:
        value = read_loadavg()
        self.loads.append(value)
        self.runnable.append(read_runnable())
        self.khz.append(read_cpu_khz())
        self._wall.append(time.perf_counter())
        self._cpu.append(time.process_time())
        return value

    def record_ratio(self, ratio: float) -> None:
        """Record a round's ratio, and sample the clock AFTER its work.

        `sample()` runs at round START, before any of that round's blocks, so it
        reads the core clock BEFORE the governor has boosted for the work about
        to happen. That is how this module recorded a 1429 MHz sample and led
        this pane to overstate a 3.0x clock swing as a benchmark condition: an
        idle core reads flat and low, a busy one boosts. Sampling here as well
        brackets each round with a pre-work and a post-work clock, and
        `khz_spread_pct` is computed over both.
        """
        self.ratios.append(ratio)
        self.khz.append(read_cpu_khz())

    # -- derived statistics -------------------------------------------------

    @property
    def level(self) -> float:
        return statistics.median(self.loads) if self.loads else float("nan")

    @property
    def spread(self) -> float:
        """max - min. The blunt volatility measure, sensitive to one spike."""
        return (max(self.loads) - min(self.loads)) if self.loads else float("nan")

    @property
    def iqr(self) -> float:
        """Interquartile range — volatility that a single excursion cannot fake.

        Reported ALONGSIDE spread rather than instead of it, because the two
        disagree in the informative case: one spike gives a large spread and a
        small IQR, sustained churn gives both.
        """
        if len(self.loads) < 4:
            return float("nan")
        ordered = sorted(self.loads)
        mid = len(ordered) // 2
        lower = statistics.median(ordered[:mid])
        upper = statistics.median(ordered[-mid:])
        return upper - lower

    @property
    def relative_volatility(self) -> float:
        """spread / level — 8 to 24 is far worse at level 8 than at level 80."""
        lvl = self.level
        if not lvl:
            return float("nan")
        return self.spread / lvl

    @property
    def corr_load_ratio(self) -> float:
        """Pearson correlation of per-round load against per-round ratio.

        THE POINT OF THE MODULE. Near zero means the balanced square cancelled
        the contention it ran through; large in magnitude means it did not, and
        the row should be re-run whatever its endpoint loadavg said.
        """
        n = min(len(self.loads), len(self.ratios))
        if n < 3:
            return float("nan")
        loads, ratios = self.loads[:n], self.ratios[:n]
        if len(set(loads)) < 2 or len(set(ratios)) < 2:
            return 0.0
        return statistics.correlation(loads, ratios)

    @property
    def runnable_spread(self) -> float:
        """Volatility from the INSTANTANEOUS signal, usable on short runs.

        `spread` reads the one-minute average and is blind whenever a run is
        shorter than that average's ~5 second refresh; this is not. When the two
        disagree — a flat `spread` with a moving `runnable_spread` — believe this
        one and treat the window as volatile.
        """
        if not self.runnable:
            return float("nan")
        return float(max(self.runnable) - min(self.runnable))

    @property
    def corr_runnable_ratio(self) -> float:
        """Correlation against the instantaneous signal rather than the average."""
        n = min(len(self.runnable), len(self.ratios))
        if n < 3:
            return float("nan")
        runnable = [float(v) for v in self.runnable[:n]]
        ratios = self.ratios[:n]
        if len(set(runnable)) < 2 or len(set(ratios)) < 2:
            return 0.0
        return statistics.correlation(runnable, ratios)

    def sample_arm(self, arm: str) -> None:
        """Record loadavg and core clock FOR ONE ARM, called around its block.

        Round-level sampling cannot see a per-arm difference. If one arm
        systematically lands on busier cores, or is consistently measured while
        the clock is lower, that is a bias the balanced square does NOT cancel —
        it is not common-mode, it is arm-correlated. `arm_khz_skew_pct` turns
        that into a number, and it is the same class of hazard as the
        cross-project contention finding: something that differs BETWEEN arms
        rather than moving both together.
        """
        self.arm_khz.setdefault(arm, []).append(read_cpu_khz())
        self.arm_loads.setdefault(arm, []).append(read_loadavg())
        self.arm_cpus.setdefault(arm, []).append(read_current_cpu())

    def arm_khz_median(self, arm: str) -> float:
        live = [k for k in self.arm_khz.get(arm, []) if k > 0]
        return statistics.median(live) if live else float("nan")

    def arm_load_median(self, arm: str) -> float:
        vals = self.arm_loads.get(arm, [])
        return statistics.median(vals) if vals else float("nan")

    @property
    def same_core_pct(self) -> float:
        """Percentage of sampled positions where ALL arms were on one core.

        Both arms of a balanced square run in the SAME PROCESS, alternating
        inside one loop, so they share a core unless the scheduler migrates the
        process mid-run. That is the structural reason arm clock skew comes out
        near zero — but it is a claim that should be measured, not assumed, since
        a migration between arms is exactly how a cross-core clock spread would
        leak into a ratio.
        """
        arms = list(self.arm_cpus)
        if len(arms) < 2:
            return float("nan")
        n = min(len(self.arm_cpus[a]) for a in arms)
        if n == 0:
            return float("nan")
        same = sum(
            1 for i in range(n) if len({self.arm_cpus[a][i] for a in arms}) == 1
        )
        return 100.0 * same / n

    @property
    def distinct_cores(self) -> int:
        seen = set()
        for vals in self.arm_cpus.values():
            seen.update(v for v in vals if v >= 0)
        return len(seen)

    @property
    def arm_khz_skew_pct(self) -> float:
        """Largest per-arm median clock difference, as a percentage.

        Near zero means both arms were measured at the same clock, which is what
        keeping both arms in one window is supposed to buy. A large value means
        the arms were NOT measured under the same conditions however good the
        window looked.
        """
        meds = [self.arm_khz_median(a) for a in self.arm_khz]
        meds = [m for m in meds if m == m]
        if len(meds) < 2:
            return float("nan")
        lo, hi = min(meds), max(meds)
        return 100.0 * (hi - lo) / lo if lo else float("nan")

    def arm_fragment(self) -> str:
        if not self.arm_khz:
            return ""
        parts = []
        for arm in sorted(self.arm_khz):
            parts.append(
                f"{arm}: load {self.arm_load_median(arm):.2f} "
                f"clock {self.arm_khz_median(arm) / 1000:.0f} MHz"
            )
        return (
            "per-arm [" + "; ".join(parts) + f"] skew {self.arm_khz_skew_pct:.1f}% "
            f"same-core {self.same_core_pct:.0f}% over {self.distinct_cores} core(s); "
        )

    @property
    def median_interval_s(self) -> float:
        """Median wall time between consecutive samples.

        THE ACTUAL SIGNATURE of the mistake this module made, after a first
        attempt at detecting it also failed. I reported a 3.0x core-clock swing
        that turned out to be an artifact of sampling in a tight loop with no
        work between calls. The obvious guard was a DUTY CYCLE — CPU time over
        wall time — on the theory that the process had been idle. It had not:
        reading `/proc` is itself CPU work, so a tight sampling loop scores a
        duty cycle near 1.0 and sails through. The detector failed for precisely
        the reason the original claim did.

        What actually distinguishes the bad sampling is that no WALL TIME
        elapsed: the samples were microseconds apart, bracketing no work for the
        governor to respond to. A benchmark round is milliseconds to seconds.
        """
        if len(self._wall) < 2:
            return float("nan")
        gaps = [b - a for a, b in zip(self._wall, self._wall[1:])]
        return statistics.median(gaps) if gaps else float("nan")

    @property
    def duty_cycle(self) -> float:
        """CPU time consumed per unit wall time between samples.

        Informational only — see `median_interval_s` for why this does NOT
        detect idle sampling: reading `/proc` is CPU work, so a tight sampling
        loop scores near 1.0.

        THE GUARD AGAINST THE MISTAKE THIS MODULE ITSELF MADE. A clock reading is
        only a benchmark condition if the process was BUSY when it was taken. I
        once sampled `read_cpu_khz()` fifteen times in a tight loop with no work
        between calls, read 1429 MHz, and reported a 3.0x core-clock swing as a
        property of the host. It was a property of an idle process: re-measured,
        idle sampling reads flat (0.5 percent swing) while a busy benchmark core
        swings 22 percent.

        Near 1.0 means the process was computing between samples and the clock
        readings describe the work. Well below 1.0 means it was waiting, and any
        frequency conclusion drawn from those samples is about idleness.
        """
        if len(self._wall) < 2:
            return float("nan")
        wall = self._wall[-1] - self._wall[0]
        cpu = self._cpu[-1] - self._cpu[0]
        if wall <= 0:
            return float("nan")
        return cpu / wall

    @property
    def khz_spread_pct(self) -> float:
        """Core-clock swing across the run, as a percentage of the median.

        br-r37-c1-jycsb: on a `powersave` host an idle core clocks DOWN, so a
        quiet window can be slower and more variable than a busy one. A row whose
        clock moved during it is not comparable to one taken at a steady clock,
        however good its loadavg looked.
        """
        live = [k for k in self.khz if k > 0]
        if len(live) < 2:
            return float("nan")
        mid = statistics.median(live)
        return 100.0 * (max(live) - min(live)) / mid if mid else float("nan")

    @property
    def verdict(self) -> str:
        """Advisory only. Never rejects a row on its own — replication decides."""
        gap = self.median_interval_s
        if gap == gap and gap < 1e-3:
            return "IDLE-SAMPLED"
        skew = self.arm_khz_skew_pct
        if skew == skew and skew >= 5.0:
            return "ARM-CLOCK-SKEW"
        for corr in (self.corr_load_ratio, self.corr_runnable_ratio):
            if corr == corr and abs(corr) >= 0.5:
                return "PERTURBED"
        if self.relative_volatility >= 1.0:
            return "VOLATILE"
        if self.level >= 30.0:
            return "LOADED-STABLE"
        return "STABLE"

    def report(self) -> str:
        return (
            f"window: level {self.level:.2f} spread {self.spread:.2f} "
            f"iqr {self.iqr:.2f} relvol {self.relative_volatility:.2f} "
            f"runspread {self.runnable_spread:.0f} "
            f"corr(load,ratio) {self.corr_load_ratio:+.3f} "
            f"corr(run,ratio) {self.corr_runnable_ratio:+.3f} -> {self.verdict}"
        )

    def provenance_line(self) -> str:
        """One line to paste into a banked row's provenance block."""
        return (
            f"loadavg per round: n={len(self.loads)} median {self.level:.2f} "
            f"min {min(self.loads):.2f} max {max(self.loads):.2f} "
            f"iqr {self.iqr:.2f} relvol {self.relative_volatility:.2f}; "
            f"{self._runnable_fragment()}"
            f"{self._khz_fragment()}"
            f"{self.arm_fragment()}"
            f"duty {self.duty_cycle:.2f} interval {self.median_interval_s * 1e3:.1f} ms; "
            f"corr(load, per-round ratio) {self.corr_load_ratio:+.3f}, "
            f"corr(runnable, per-round ratio) {self.corr_runnable_ratio:+.3f} "
            f"[{self.verdict}]"
        )

    def _khz_fragment(self) -> str:
        live = [k for k in self.khz if k > 0]
        if not live:
            return "cpu clock unavailable; "
        return (
            f"cpu clock median {statistics.median(live) / 1000:.0f} MHz "
            f"min {min(live) / 1000:.0f} max {max(live) / 1000:.0f} "
            f"swing {self.khz_spread_pct:.1f}%; "
        )

    def _runnable_fragment(self) -> str:
        """Empty-safe. A guard is stamped onto every banked row, so it must
        never raise — a caller that only recorded loads (or a hand-built guard
        in a test) would otherwise take `min()` over an empty list and take the
        benchmark down with it."""
        if not self.runnable:
            return "runnable unsampled; "
        return (
            f"runnable min {min(self.runnable)} max {max(self.runnable)} "
            f"spread {self.runnable_spread:.0f}; "
        )
