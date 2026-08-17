#!/usr/bin/env python3
"""Would `perf_harness.py` admit RIGHT NOW? Answer in a second, not five minutes.

br-r37-c1-d4xot. `require_host_wide_quiescence` is fail-closed over the entire
host cpuset and retries for `HOST_WIDE_ADMISSION_MAX_WINDOWS` one-second windows
before giving up - so on a busy fleet a doomed run costs FIVE MINUTES to find out
it was doomed. Every pane pays that, repeatedly, and the cost is why "just capture
a run" keeps not happening.

This asks the same question against the same constants and answers in about a
second.

WHY IT EXISTS AT ALL, i.e. why loadavg is not enough. Fleet briefs quote loadavg,
and loadavg cannot see per-core occupancy. Measured on 2026-08-17: a brief
reported "load fell to 12 - clean certification window" while the host actually
had loadavg 25.69 and **57 of 64 CPUs over the 20 percent bound**, several pinned
at 100 percent. A pane trusting the loadavg figure would have started a five
minute harness run into one of the busiest states of the day. The gate is right
and the summary statistic is wrong; this tool reports what the gate reports.

AGGREGATE IDLE DOES NOT PREDICT IT EITHER, and for a structural reason worth
stating because it is the natural second guess after loadavg. The gate is
PER-CORE, so a minority of saturated cores - which is exactly what a build looks
like - is diluted away by the idle majority. Measured 2026-08-17: 15 of 64 CPUs
over the bound, several at 100 percent, while cumulative idle read 76.7 percent.
An "88 percent idle" host is consistent with roughly seven fully pinned cores and
is still a refusal. Idle above 80 percent is NECESSARY for admission and nowhere
near SUFFICIENT; only the per-core check answers the question.

IT DOES NOT WEAKEN OR REPLACE THE GATE. It imports the harness's own constants
and scope function, so it cannot drift from them, and it is advisory only - the
harness still runs its full admission sequence. A pass here means "worth
attempting", never "admitted".

    scripts/host_quiet_check.py            # one window, exit 0 if it would admit
    scripts/host_quiet_check.py --windows 5   # the gate's own clear-streak length
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

HARNESS = Path(__file__).resolve().parent / "perf_harness.py"


def _harness():
    """Import perf_harness for its constants WITHOUT running its admission gate."""
    name = "perf_harness_constants"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, HARNESS)
    module = importlib.util.module_from_spec(spec)
    # Register BEFORE exec: perf_harness defines @dataclass types, and
    # dataclasses resolves each class's __module__ through sys.modules. Without
    # this the import dies in dataclasses._is_type with an opaque
    # "'NoneType' object has no attribute '__dict__'".
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        del sys.modules[name]
        raise
    return module


def check(windows: int) -> tuple[bool, list, dict]:
    mod = _harness()
    scope, _source = mod._host_wide_cpu_scope()
    bound = mod.HOST_WIDE_MAX_BUSY_FRACTION
    sample_s = mod.HOST_WIDE_ADMISSION_SAMPLE_S
    worst: dict = {}
    clear = 0
    for _ in range(windows):
        busy = mod._sample_cpu_busy(scope, sample_s)
        offenders = {c: f for c, f in busy.items() if f > bound}
        if offenders:
            clear = 0
            if len(offenders) >= len(worst):
                worst = offenders
        else:
            clear += 1
    # br-r37-c1-d4xot: idle must be a DELTA over an interval, not the first line
    # of /proc/stat. Those counters are cumulative SINCE BOOT, so a single read
    # yields a lifetime average that barely moves: an earlier version of this
    # tool printed 76.6-76.7 percent at every load sampled on 2026-08-17, from a
    # near-idle host to one running five builds. That is not a quiet-window
    # signal, it is the machine's uptime history.
    import os as _os
    import time as _time

    def _idle_snapshot():
        with open("/proc/stat", encoding="utf-8") as handle:
            parts = handle.readline().split()
        return sum(int(x) for x in parts[1:]), int(parts[4])

    total_a, idle_a = _idle_snapshot()
    _time.sleep(sample_s)
    total_b, idle_b = _idle_snapshot()
    idle_pct = 100.0 * (idle_b - idle_a) / max(1, total_b - total_a)

    return clear == windows, sorted(worst.items(), key=lambda kv: -kv[1]), {
        "loadavg": _os.getloadavg(),
        "idle_pct": idle_pct,
        "bound": bound,
        "sample_s": sample_s,
        "scope_size": len(scope),
        "clear_windows_required": mod.HOST_WIDE_ADMISSION_CLEAR_WINDOWS,
        "max_windows": mod.HOST_WIDE_ADMISSION_MAX_WINDOWS,
    }


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--windows", type=int, default=1)
    args = ap.parse_args(argv[1:])

    ok, offenders, info = check(args.windows)
    print(
        f"gate: all {info['scope_size']} CPUs < {info['bound'] * 100:.0f}% busy for "
        f"{info['clear_windows_required']} consecutive {info['sample_s']:.0f}s windows "
        f"(harness retries up to {info['max_windows']})"
    )
    # Report the two summary statistics people actually quote, next to the
    # per-core verdict, so their disagreement is visible in ONE line rather than
    # discovered after a five-minute refusal.
    print(
        f"summary stats (NEITHER predicts this gate): "
        f"loadavg {info['loadavg'][0]:.2f}/{info['loadavg'][1]:.2f}/"
        f"{info['loadavg'][2]:.2f}, aggregate idle {info['idle_pct']:.1f}%"
    )
    if ok:
        print(f"WOULD ATTEMPT: {args.windows}/{args.windows} sampled windows clear.")
        print("Advisory only - the harness still runs its own admission sequence.")
        return 0
    top = ", ".join(f"cpu{c}={f * 100:.1f}%" for c, f in offenders[:8])
    print(f"WOULD REFUSE: {len(offenders)} CPUs over the bound. {top}")
    print("Do not start a harness run; it will burn the full retry budget and fail.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
