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
from collections.abc import Sequence
from dataclasses import dataclass, field


def read_loadavg() -> float:
    """One-minute load average. Read from /proc so it costs no subprocess."""
    with open("/proc/loadavg", encoding="ascii") as handle:
        return float(handle.read().split()[0])


# A sibling-utilisation sample needs several jiffies to be meaningful; see the
# resolution gate in `end_arm`.
_SIBLING_MIN_BLOCK_S = 0.05

# br-r37-c1-jycsb: a sibling at 100 percent shifted this harness's ratio by 17
# percent. Twenty percent is the occupancy above which a row is re-taken rather
# than banked.
_SIBLING_CONTENDED_PCT = 20.0


def read_sibling_cpu(cpu: int) -> int:
    """The SMT sibling of `cpu`, or -1 if SMT is off or unreadable.

    This host is 64 logical over 32 physical cores, siblings paired (n, n+32).
    Two arms running SEQUENTIALLY in one process never contend with each other —
    but the sibling is an uncontrolled tenant sharing the physical core, and if
    its load differs between arms that IS arm-correlated bias, which the balanced
    square does not cancel.
    """
    try:
        raw = open(
            f"/sys/devices/system/cpu/cpu{cpu}/topology/thread_siblings_list",
            encoding="ascii",
        ).read().strip()
    except Exception:  # noqa: BLE001
        return -1
    ids = []
    for part in raw.split(","):
        if "-" in part:
            lo, hi = part.split("-")
            ids.extend(range(int(lo), int(hi) + 1))
        else:
            ids.append(int(part))
    others = [i for i in ids if i != cpu]
    return others[0] if others else -1


def read_cpu_busy_jiffies(cpu: int) -> int:
    """Non-idle jiffies for one logical cpu from /proc/stat; -1 if unreadable."""
    if cpu < 0:
        return -1
    try:
        with open("/proc/stat", encoding="ascii") as handle:
            for line in handle:
                if line.startswith(f"cpu{cpu} "):
                    f = [int(x) for x in line.split()[1:]]
                    idle = f[3] + (f[4] if len(f) > 4 else 0)
                    return sum(f) - idle
    except Exception:  # noqa: BLE001
        return -1
    return -1


def read_physical_core(cpu: int) -> int:
    try:
        return int(
            open(f"/sys/devices/system/cpu/cpu{cpu}/topology/core_id", encoding="ascii").read()
        )
    except Exception:  # noqa: BLE001
        return -1


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


def _cpu_ticks(cores: set[str]) -> dict[str, tuple[int, int, int]]:
    """(total, idle, iowait) jiffies for the named cpuN lines."""
    out: dict[str, tuple[int, int, int]] = {}
    with open("/proc/stat", encoding="ascii") as handle:
        for line in handle:
            name = line.split(maxsplit=1)[0]
            if name in cores:
                fields = [int(x) for x in line.split()[1:]]
                out[name] = (sum(fields), fields[3], fields[4])
    return out


def core_busy_pct(cores: Sequence[int], interval: float = 2.0) -> dict[int, float]:
    """LIVE busy percentage per core, sampled over `interval` seconds.

    Neither loadavg nor machine-wide idle answers the question a PINNED
    benchmark actually asks. Measured on this host 2026-08-17 within one minute:

        loadavg 32.54          -- the level rule below says BLOCKED
        machine-wide idle 69%  -- looks like a quiet host
        cpu14 busy 35.4%, cpu15 busy 53.2%   -- the cores the bench pins to

    All three are true at once. loadavg counts uninterruptible tasks that are not
    competing for CPU, so it over-reports; machine-wide idle averages over cores
    the benchmark will never touch, so it under-reports for a pinned run. Only
    the per-core figure describes the contention the measurement will actually
    experience, and here it disagreed with the machine-wide number by enough to
    invert the decision.

    `/proc/stat`'s counters are cumulative since boot, so a single read is
    useless for this — the sample interval is the whole point.
    """
    names = {f"cpu{c}" for c in cores}
    first = _cpu_ticks(names)
    time.sleep(interval)
    second = _cpu_ticks(names)
    busy: dict[int, float] = {}
    for name in names:
        if name not in first or name not in second:
            continue
        total = second[name][0] - first[name][0]
        idle = second[name][1] - first[name][1]
        if total > 0:
            busy[int(name[3:])] = 100.0 * (total - idle) / total
    return busy


def cores_are_quiet(
    cores: Sequence[int],
    busy_max: float = 15.0,
    interval: float = 2.0,
) -> tuple[bool, str]:
    """Are the cores this run will PIN to actually free?

    Answers the question `window_is_certifiable` cannot: that one reads the
    machine, this one reads the seats the benchmark will sit in. Use BOTH — a
    quiet machine with a busy bench core still produces a contended measurement,
    and a loaded machine with free bench cores may be perfectly measurable.
    """
    busy = core_busy_pct(cores, interval)
    if not busy:
        return False, "no per-core samples (cores absent from /proc/stat?)"
    worst_core, worst = max(busy.items(), key=lambda kv: kv[1])
    detail = ", ".join(f"cpu{c} {b:.1f}% busy" for c, b in sorted(busy.items()))
    if worst > busy_max:
        return False, f"bench cores CONTENDED: {detail} (max {busy_max:.0f}%)"
    return True, f"bench cores quiet: {detail}"


def window_is_certifiable(
    level_max: float = 30.0,
    ratio_max: float = 1.25,
    recovery_level_max: float | None = None,
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

    # br-r37-c1-gatedir: DIRECTION MATTERS, and the original symmetric ratio
    # could not see it.
    #
    # `max/min` treats 1-min 30 against 5-min 20 the same as 1-min 20 against
    # 5-min 30. They are opposite situations. The first is load ARRIVING: the
    # window will be worse than it looks. The second is load LEAVING: the window
    # will be better. Because a recovery holds `one < five` for its whole
    # duration, the symmetric form rejected every moment of it — which cost this
    # pane two certifications whose rows then replicated tightly with clean
    # nulls, the `has_edge` row failing all four squares and the row-membership
    # row three of four, in both cases for this reason alone.
    if one > five * ratio_max:
        rising = one / five if five > 0 else float("inf")
        return False, (
            f"unstable: RISING, 1-min {one:.2f} against 5-min {five:.2f}, "
            f"ratio {rising:.2f} (max {ratio_max:.2f}) — arriving load"
        )

    # Falling or flat. NOT simply accepted: a high 5-minute average means real
    # work ran recently and may resume, and the 1-minute number cannot rule that
    # out. `(18.4, 27.6)` is pinned as a rejection by an existing test precisely
    # for this, and it is a falling pair — so a recovery must land inside a
    # TIGHTER level bound than a flat window has to clear.
    if recovery_level_max is None:
        recovery_level_max = level_max * 0.75
    if five > recovery_level_max:
        return False, (
            f"unstable: recovering, 5-min {five:.2f} still above the recovery "
            f"bound {recovery_level_max:.2f} (1-min {one:.2f}) — a host on its "
            f"way down is not yet a quiet one"
        )

    hi, lo = max(one, five), min(one, five)
    ratio = hi / lo if lo > 0 else float("inf")
    shape = "steady" if one >= five else "recovering"
    return True, f"stable: {shape}, 1-min {one:.2f}, 5-min {five:.2f}, ratio {ratio:.2f}"


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
    arm_phys: dict[str, list[int]] = field(default_factory=dict)
    arm_sibling_busy: dict[str, list[float]] = field(default_factory=dict)
    arm_sibling_unresolved: dict[str, int] = field(default_factory=dict)
    _pending: dict[str, tuple[int, int, float]] = field(default_factory=dict)
    _run_sib: tuple[int, int, float] | None = None
    run_sibling_busy: float = float("nan")
    # br-r37-c1-9i169 follow-up: busy share of the core the WORKER is pinned to,
    # measured across the whole run rather than sampled before it.
    _bench_core: tuple[int, int, float] | None = None
    bench_core_busy: float = float("nan")
    bench_core_id: int = -1

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
        cpu = read_current_cpu()
        self.arm_cpus.setdefault(arm, []).append(cpu)
        self.arm_phys.setdefault(arm, []).append(read_physical_core(cpu))
        sib = read_sibling_cpu(cpu)
        self._pending[arm] = (sib, read_cpu_busy_jiffies(sib), time.perf_counter())

    def begin_run(self) -> None:
        """Open a WHOLE-RUN sibling-utilisation measurement.

        br-r37-c1-jycsb measured that a busy SMT sibling moves this harness's
        ratio by 17 percent, hitting the two arms unequally (1.93x against
        1.61x) so that interleaving does not cancel it. Per-ARM sibling load is
        unmeasurable on a fast arm at jiffy resolution, but the WHOLE RUN spans
        seconds and resolves easily — so this is the measurement that can
        actually gate a row.

        Pair with `end_run()` around the entire measurement loop.
        """
        cpu = read_current_cpu()
        sib = read_sibling_cpu(cpu)
        self._run_sib = (sib, read_cpu_busy_jiffies(sib), time.perf_counter())

    def begin_bench_core_watch(self, core: int) -> None:
        """Watch the core the WORKER is pinned to, for the whole run.

        br-r37-c1-9i169: `cores_are_quiet()` samples BEFORE the run and there is
        a race. Measured 2026-08-17: cpu16 and cpu28 read 1.0 percent busy on a
        survey, and 27-31 percent busy by the time the square started ~30 seconds
        later — the fleet moved in between. That square's base A/A null came back
        1.0417 with its interval excluding unity, i.e. the arm differed from
        ITSELF by 4.2 percent against an effect of ~1 percent, and the row could
        not be taken.

        A pre-run check answers "was it quiet?"; this answers "was it quiet
        THROUGHOUT?", which is the question a banked row actually needs. Pair
        with `end_bench_core_watch()` around the whole measurement loop, and
        report `bench_core_busy` on the row next to loadavg and MHz.
        """
        self.bench_core_id = core
        self._bench_core = (core, read_cpu_busy_jiffies(core), time.perf_counter())

    def end_bench_core_watch(self) -> None:
        got, self._bench_core = self._bench_core, None
        if got is None:
            return
        core, before, t0 = got
        if core < 0 or before < 0:
            return
        after = read_cpu_busy_jiffies(core)
        dt = time.perf_counter() - t0
        if after < 0 or dt < _SIBLING_MIN_BLOCK_S:
            return
        self.bench_core_busy = 100.0 * (after - before) / (dt * 100.0)

    def end_run(self) -> None:
        got, self._run_sib = self._run_sib, None
        if got is None:
            return
        sib, before, t0 = got
        if sib < 0 or before < 0:
            return
        after = read_cpu_busy_jiffies(sib)
        dt = time.perf_counter() - t0
        if after < 0 or dt < _SIBLING_MIN_BLOCK_S:
            return
        self.run_sibling_busy = 100.0 * (after - before) / (dt * 100.0)

    def end_arm(self, arm: str) -> None:
        """Close an arm's block and record how busy its SMT SIBLING was.

        Called after the block, paired with `sample_arm` before it. The value is
        the sibling's non-idle jiffy rate over the block: near 100 means another
        tenant was hammering the other half of the physical core for the whole
        of that arm's measurement.
        """
        got = self._pending.pop(arm, None)
        if got is None:
            return
        sib, before, t0 = got
        if sib < 0 or before < 0:
            return
        after = read_cpu_busy_jiffies(sib)
        dt = time.perf_counter() - t0
        if after < 0 or dt <= 0:
            return
        # RESOLUTION GATE, added after this metric produced a false
        # ARM-SIBLING-SKEW. /proc/stat counts JIFFIES, 10 ms apiece at
        # USER_HZ=100. A block shorter than several jiffies cannot observe a
        # tick and reads 0 percent no matter how busy the sibling is. In this
        # pane's own worst cell the fnx block runs ~61 ms (6 jiffies) and the nx
        # block ~0.46 ms (0.05 jiffies), so nx read 0 percent in EVERY run and
        # the metric "found" a 45-point asymmetry that was pure granularity.
        # Blocks that cannot resolve are recorded as unmeasured, not as zero.
        if dt < _SIBLING_MIN_BLOCK_S:
            self.arm_sibling_unresolved.setdefault(arm, 0)
            self.arm_sibling_unresolved[arm] += 1
            return
        hz = 100.0  # USER_HZ on Linux
        self.arm_sibling_busy.setdefault(arm, []).append(
            100.0 * (after - before) / (dt * hz)
        )

    def arm_sibling_busy_median(self, arm: str) -> float:
        vals = self.arm_sibling_busy.get(arm, [])
        return statistics.median(vals) if vals else float("nan")

    @property
    def sibling_busy_skew_pp(self) -> float:
        """Largest per-arm difference in SMT-sibling utilisation, percentage points."""
        meds = [self.arm_sibling_busy_median(a) for a in self.arm_sibling_busy]
        meds = [m for m in meds if m == m]
        if len(meds) < 2:
            return float("nan")
        return max(meds) - min(meds)

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
                f"clock {self.arm_khz_median(arm) / 1000:.0f} MHz "
                f"cpu{self.arm_cpus.get(arm, [-1])[-1]}"
                f"/phys{self.arm_phys.get(arm, [-1])[-1]} "
                f"sib-busy {self.arm_sibling_busy_median(arm):.0f}%"
                + (
                    f" (unresolved x{self.arm_sibling_unresolved[arm]})"
                    if arm in self.arm_sibling_unresolved
                    else ""
                )
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
        run_sib = self.run_sibling_busy
        if run_sib == run_sib and run_sib >= _SIBLING_CONTENDED_PCT:
            return "SIBLING-CONTENDED"
        if self.arm_sibling_unresolved:
            return "SIBLING-UNRESOLVED"
        sib = self.sibling_busy_skew_pp
        if sib == sib and sib >= 20.0:
            return "ARM-SIBLING-SKEW"
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
            f"run-sibling {self.run_sibling_busy:.0f}%; "
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
