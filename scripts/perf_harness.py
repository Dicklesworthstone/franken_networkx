#!/usr/bin/env python3
"""Paired fnx-vs-nx measurement harness — the §2 bench-harness contract.

Adopted 2026-07-25 (br-r37-c1-wbwkb, cc lane) from the fleet-wide contract in
`PERF_CAMPAIGN_2026-07-25`. Three properties, all mandatory:

1. **Self-reporting binary sha256.** The provenance header hashes the `_fnx`
   extension that is actually loaded and prints it as line 1. A hash computed by a
   shell step *next to* the run proves nothing about which ELF executed, and rch
   compiles into an opaque per-worker pool target dir.

2. **A/A null controls in the same invocation.** Every row measures both
   `paired(nx, nx)` and `paired(fnx, fnx)` before `paired(nx, fnx)`. The wider
   arm-specific null establishes the noise floor. Both arms are timed INTERLEAVED
   inside one round with the order alternating per round, and the statistic is the
   **median of per-round ratios** — not a ratio of medians, which lets drift in
   either arm leak into the result.

3. **Use the corrected three-clause median gate, never `cv`.** A claim is
   decidable iff its bootstrap 95% CI of the median excludes 1.0, its median
   deviation from 1.0 exceeds twice the larger A/A null-CI half-width, and every
   A/A null median is within 2% of 1.0. The median clause bounds arm-order bias
   without incorrectly requiring a precise null CI to straddle 1.0. `cv` is
   reported as provenance only.

4. **Require host-wide benchmark exclusivity.** Before suite setup and again
   immediately before measurement, the harness requires five consecutive clear
   one-second samples of every CPU in the effective cgroup cpuset. A bounded
   300-window settle loop records rejected windows, allowing compile tail to
   drain without admitting sustained work. During timing it also accounts for
   every non-affinity CPU in 300 ms windows and aborts if the same CPU exceeds
   20% busy in two consecutive windows. That distinguishes sustained co-tenancy
   from one recorded control-plane wakeup without letting a task that starts
   after the two admission stages hide behind the benchmark's narrow affinity.
   Linux guest counters are excluded from the total because they are already
   included in user/nice; steal remains busy because it is host-level
   contention.

Knobs follow §2.4: `min_sample ~2 ms`, `min_of = 3` inner replicates keeping the
minimum (the dominant knob; longer samples are a bigger target for preemption).

Usage:
    python3 scripts/perf_harness.py view-accessors
    python3 scripts/perf_harness.py adj-descriptor
    python3 scripts/perf_harness.py adj-len
    python3 scripts/perf_harness.py adj-iter
    python3 scripts/perf_harness.py multi-adj-iter
    python3 scripts/perf_harness.py multi-adj-contains
    python3 scripts/perf_harness.py multi-row-getitem
    python3 scripts/perf_harness.py multiedge-getitem
    python3 scripts/perf_harness.py multiedge-iter
    python3 scripts/perf_harness.py multikeydict-iter
    python3 scripts/perf_harness.py digraph-descriptors
    python3 scripts/perf_harness.py multidigraph-descriptors
    python3 scripts/perf_harness.py node-primitives
    python3 scripts/perf_harness.py edge-primitives
    python3 scripts/perf_harness.py edge-data-primitives
    python3 scripts/perf_harness.py multigraph-edge-data-admission
    python3 scripts/perf_harness.py multigraph-degree-scalar
    python3 scripts/perf_harness.py simple-edge-getitem
    python3 scripts/perf_harness.py nodeview-contains
    python3 scripts/perf_harness.py multi-neighbor-keydict
    python3 scripts/perf_harness.py digraph-neighbor-descriptors
    python3 scripts/perf_harness.py nodeview-getitem
    python3 scripts/perf_harness.py lazy-rows
    python3 scripts/perf_harness.py constant-predicates
    python3 scripts/perf_harness.py digraph-string-attr-construction
    python3 scripts/perf_harness.py multidigraph-string-attr-construction
    python3 scripts/perf_harness.py multigraph-compose
    python3 scripts/perf_harness.py marshaling
    python3 scripts/perf_harness.py class1-scaling
    python3 scripts/perf_harness.py class1-frontier
    python3 scripts/perf_harness.py claim-incumbent
    python3 scripts/perf_harness.py cold-after-mutation-cc
    python3 scripts/perf_harness.py realistic-workloads

Point `PYTHONPATH` at the package tree under test; the header records which one ran.
Set `FNX_EXTENSION_PATH` to preload an exact freshly built `_fnx` shared object
instead of accepting whichever installed extension happens to be importable.
"""

from __future__ import annotations

import gzip
import hashlib
import hmac
import importlib.util
import io
import json
import os
import statistics
import sys
import threading
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter, sleep

MIN_SAMPLE_S = 0.002
MIN_OF = 3
ROUNDS = int(os.environ.get("FNX_PERF_ROUNDS", "21"))
MAX_NULL_MEDIAN_BIAS = 0.02
HOST_WIDE_CPU_SAMPLE_S = 0.3
HOST_WIDE_MAX_BUSY_FRACTION = 0.20
HOST_WIDE_ADMISSION_SAMPLE_S = 1.0
HOST_WIDE_ADMISSION_CLEAR_WINDOWS = 5
HOST_WIDE_ADMISSION_MAX_WINDOWS = 300
HOST_WIDE_CONSECUTIVE_BUSY_WINDOWS = 2
EXTRA_PROVENANCE: dict[str, object] = {}
_MEASUREMENT_EXCLUSIVITY = None
NETWORKX_361_WHEEL_URL = (
    "https://files.pythonhosted.org/packages/9e/c9/"
    "b2622292ea83fbb4ec318f5b9ab867d0a28ab43c5717bb85b0a5f6b3b0a4/"
    "networkx-3.6.1-py3-none-any.whl"
)
NETWORKX_361_WHEEL_SHA256 = (
    "d47fbf302e7d9cbbb9e2555a0d267983d2aa476bac30e90dfbe5669bd57f3762"
)
NETWORKX_361_WHEEL_FILENAME = (
    "networkx-3.6.1-py3-none-any-d47fbf302e7d9cbb.whl"
)

# The nx arm must be genuinely unpatched upstream: a "2.6x faster" claim in this
# repo's history was once measured against an already-dispatched fnx baseline and
# genuine NetworkX turned out to be 1.88x FASTER. Clear the dispatch env first.
for _var in ("NETWORKX_AUTOMATIC_BACKENDS", "NETWORKX_BACKEND_PRIORITY", "NETWORKX_FALLBACK_TO_NX"):
    os.environ.pop(_var, None)


def ensure_networkx_361() -> None:
    """Make the exact incumbent importable before PyO3 imports its exceptions."""
    try:
        import networkx as nx
    except ModuleNotFoundError:
        nx = None

    if nx is not None:
        if nx.__version__ != "3.6.1":
            raise RuntimeError(
                "the installed NetworkX is not the required live 3.6.1: "
                f"{nx.__version__} from {nx.__file__}"
            )
        EXTRA_PROVENANCE["networkx_dependency"] = {
            "source": "preinstalled",
            "version": nx.__version__,
            "path": nx.__file__,
        }
        return

    cache_root = Path(
        os.environ.get(
            "FNX_DEPENDENCY_CACHE_DIR",
            "/tmp/franken-networkx-dependency-cache",
        )
    )
    cache_root.mkdir(parents=True, exist_ok=True)
    wheel_path = cache_root / NETWORKX_361_WHEEL_FILENAME
    if not wheel_path.exists():
        with urllib.request.urlopen(NETWORKX_361_WHEEL_URL, timeout=60) as response:
            wheel_bytes = response.read()
        wheel_sha256 = hashlib.sha256(wheel_bytes).hexdigest()
        if not hmac.compare_digest(wheel_sha256, NETWORKX_361_WHEEL_SHA256):
            raise RuntimeError(
                "NetworkX 3.6.1 wheel SHA-256 mismatch: "
                f"expected {NETWORKX_361_WHEEL_SHA256}, got {wheel_sha256}"
            )
        try:
            with wheel_path.open("xb") as target:
                target.write(wheel_bytes)
        except FileExistsError:
            # Another benchmark populated the one shared cache concurrently.
            pass

    wheel_digest = hashlib.sha256()
    with wheel_path.open("rb") as wheel_file:
        for chunk in iter(lambda: wheel_file.read(1 << 20), b""):
            wheel_digest.update(chunk)
    wheel_sha256 = wheel_digest.hexdigest()
    if not hmac.compare_digest(wheel_sha256, NETWORKX_361_WHEEL_SHA256):
        raise RuntimeError(
            "cached NetworkX 3.6.1 wheel SHA-256 mismatch: "
            f"expected {NETWORKX_361_WHEEL_SHA256}, got {wheel_sha256} "
            f"at {wheel_path}"
        )

    sys.path.insert(0, str(wheel_path))
    import networkx as nx

    if nx.__version__ != "3.6.1":
        raise RuntimeError(
            "hash-pinned wheel did not import NetworkX 3.6.1: "
            f"{nx.__version__} from {nx.__file__}"
        )
    EXTRA_PROVENANCE["networkx_dependency"] = {
        "source": "hash_pinned_pypi_wheel",
        "version": nx.__version__,
        "path": nx.__file__,
        "wheel_url": NETWORKX_361_WHEEL_URL,
        "wheel_sha256": wheel_sha256,
        "wheel_path": str(wheel_path),
        "wheel_bytes": wheel_path.stat().st_size,
    }


def preload_requested_extension() -> None:
    """Load the exact `_fnx` ELF requested by the benchmark invocation."""
    requested = os.environ.get("FNX_EXTENSION_PATH")
    if requested is None:
        return
    ensure_networkx_361()
    path = os.path.realpath(requested)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"FNX_EXTENSION_PATH is not a file: {path}")
    spec = importlib.util.spec_from_file_location("franken_networkx._fnx", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot create an extension loader for {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["franken_networkx._fnx"] = module
    spec.loader.exec_module(module)


preload_requested_extension()


# --------------------------------------------------------------------------- #
# provenance
# --------------------------------------------------------------------------- #
def binary_sha256() -> tuple[str, str, int]:
    """Path + sha256 + size of the `_fnx` extension module actually loaded."""
    import franken_networkx._fnx as _fnx

    path = _fnx.__file__
    digest = hashlib.sha256()
    byte_count = 0
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
            byte_count += len(chunk)
    return path, digest.hexdigest(), byte_count


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text().strip()
    except OSError:
        return None


def _cpu_flags() -> set[str]:
    cpuinfo = _read_text(Path("/proc/cpuinfo")) or ""
    for line in cpuinfo.splitlines():
        if line.lower().startswith(("flags", "features")) and ":" in line:
            return set(line.split(":", 1)[1].split())
    return set()


def _process_thread_count() -> int:
    status = _read_text(Path("/proc/self/status")) or ""
    for line in status.splitlines():
        if line.startswith("Threads:"):
            return int(line.split(":", 1)[1].strip())
    raise RuntimeError("cannot read the process thread count from /proc/self/status")


def _thread_cpu_ticks() -> dict[int, int]:
    ticks: dict[int, int] = {}
    for task_dir in Path("/proc/self/task").glob("[0-9]*"):
        stat = _read_text(task_dir / "stat")
        if not stat:
            continue
        close_paren = stat.rfind(")")
        if close_paren < 0:
            continue
        fields = stat[close_paren + 1 :].split()
        if len(fields) <= 12:
            continue
        try:
            ticks[int(task_dir.name)] = int(fields[11]) + int(fields[12])
        except ValueError:
            continue
    if not ticks:
        raise RuntimeError("cannot read per-thread CPU ticks from /proc/self/task")
    return ticks


def probe_operation_threads(fn) -> dict[str, int]:
    """Observe one untimed call and report the threads that actually execute."""
    runtime_available_parallelism = len(os.sched_getaffinity(0))
    process_threads_before_probe = _process_thread_count()
    ticks_before = _thread_cpu_ticks()
    peak_process_threads = process_threads_before_probe
    ready = threading.Event()
    stop = threading.Event()

    def monitor() -> None:
        nonlocal peak_process_threads
        ready.set()
        while not stop.is_set():
            peak_process_threads = max(
                peak_process_threads,
                _process_thread_count(),
            )
            sleep(0.000_020)
        peak_process_threads = max(
            peak_process_threads,
            _process_thread_count(),
        )

    monitor_thread = threading.Thread(
        target=monitor,
        name="fnx-bench-thread-probe",
        daemon=True,
    )
    monitor_thread.start()
    ready.wait()
    monitor_native_id = monitor_thread.native_id
    try:
        fn()
    finally:
        stop.set()
        monitor_thread.join()

    ticks_after = _thread_cpu_ticks()
    cpu_active_threads = sum(
        ticks > ticks_before.get(tid, 0)
        for tid, ticks in ticks_after.items()
        if tid != monitor_native_id
    )
    newly_spawned_workers = max(
        0,
        peak_process_threads - process_threads_before_probe - 1,
    )
    return {
        "runtime_available_parallelism": runtime_available_parallelism,
        "process_threads_before_probe": process_threads_before_probe,
        "peak_process_threads": peak_process_threads,
        "thread_count_actually_used": max(
            1,
            cpu_active_threads,
            newly_spawned_workers,
        ),
    }


def host_fingerprint() -> dict[str, object]:
    """Capture the mandatory host, topology, governor, and ISA provenance."""
    cpu_scope, scope_source = _host_wide_cpu_scope()
    physical_cores: set[tuple[str, str]] = set()
    governor_by_cpu = {}
    missing_topology = []
    missing_governor = []
    for cpu in sorted(cpu_scope):
        topology = Path(f"/sys/devices/system/cpu/cpu{cpu}/topology")
        package = _read_text(topology / "physical_package_id")
        core = _read_text(topology / "core_id")
        if package is None or core is None:
            missing_topology.append(cpu)
        else:
            physical_cores.add((package, core))
        governor = _read_text(
            Path(
                f"/sys/devices/system/cpu/cpu{cpu}/cpufreq/"
                "scaling_governor"
            )
        )
        if governor is None:
            missing_governor.append(cpu)
        else:
            governor_by_cpu[str(cpu)] = governor

    flags = _cpu_flags()
    if missing_topology:
        raise RuntimeError(
            "baseline provenance is missing package/core topology for CPUs "
            f"{missing_topology}"
        )
    if not physical_cores:
        raise RuntimeError("baseline provenance found no physical CPU cores")
    if not flags:
        raise RuntimeError("baseline provenance found no runtime ISA flags")

    tracked_isa = (
        "sse2",
        "avx",
        "avx2",
        "fma",
        "bmi1",
        "bmi2",
        "aes",
        "vaes",
        "avx512f",
    )
    thread_limit_names = (
        "RAYON_NUM_THREADS",
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
        "BLIS_NUM_THREADS",
    )
    return {
        "host_identity": os.uname().nodename,
        "architecture": os.uname().machine,
        "cpu_scope_source": scope_source,
        "cpu_scope": sorted(cpu_scope),
        "physical_cores": len(physical_cores),
        "logical_threads": len(cpu_scope),
        "threads_per_core": len(cpu_scope) / len(physical_cores),
        "process_affinity": sorted(os.sched_getaffinity(0)),
        "requested_thread_limits": {
            name: os.environ.get(name)
            for name in thread_limit_names
        },
        "cpu_governors": (
            sorted(set(governor_by_cpu.values()))
            if governor_by_cpu
            else ["unavailable"]
        ),
        "cpu_governor_by_cpu": governor_by_cpu,
        "cpu_governor_unavailable_cpus": missing_governor,
        "isa_flags": sorted(flags),
        "runtime_detected_isa_features": [
            feature
            for feature in tracked_isa
            if feature in flags
        ],
    }


def provenance_header(tag: str) -> dict:
    import networkx as nx
    import franken_networkx as fnx

    path, sha, byte_count = binary_sha256()
    # Fleet contract: this exact loaded-artifact identity is line one. A shell
    # hash adjacent to the invocation cannot prove which worker-pool ELF ran.
    print(f"bench_elf_sha256={sha} ({byte_count} bytes) {path}", flush=True)
    wrapper_path = fnx.__file__
    wrapper_digest = hashlib.sha256()
    with open(wrapper_path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            wrapper_digest.update(chunk)
    info = {
        "tag": tag,
        "fnx_so": path,
        "fnx_so_sha256": sha,
        "fnx_so_bytes": byte_count,
        "fnx_python": wrapper_path,
        "fnx_python_sha256": wrapper_digest.hexdigest(),
        "nx_version": nx.__version__,
        "nx_file": nx.__file__,
        "python": sys.version.split()[0],
        "pythonhashseed": os.environ.get("PYTHONHASHSEED"),
        "source_base": os.environ.get("FNX_SOURCE_BASE"),
        "rch_clean_overlay": os.environ.get("FNX_RCH_CLEAN_OVERLAY"),
        "pid": os.getpid(),
        "loadavg": os.getloadavg(),
        "host_fingerprint": host_fingerprint(),
    }
    info.update(EXTRA_PROVENANCE)
    print(json.dumps(info), flush=True)
    return info


def _parse_cpu_list(value: str) -> set[int]:
    cpus: set[int] = set()
    for part in value.strip().split(","):
        if not part:
            continue
        if "-" in part:
            start_text, end_text = part.split("-", maxsplit=1)
            start, end = int(start_text), int(end_text)
            if start > end:
                raise RuntimeError(f"descending CPU range in host scope: {part}")
            cpus.update(range(start, end + 1))
        else:
            cpus.add(int(part))
    if not cpus:
        raise RuntimeError("host-wide CPU scope is empty")
    return cpus


def _host_wide_cpu_scope() -> tuple[set[int], str]:
    """Return the cgroup-effective host CPU scope, independent of taskset."""
    candidates = (
        Path("/sys/fs/cgroup/cpuset.cpus.effective"),
        Path("/sys/fs/cgroup/cpuset/cpuset.effective_cpus"),
        Path("/sys/devices/system/cpu/online"),
    )
    for path in candidates:
        try:
            value = path.read_text().strip()
        except OSError:
            continue
        if value:
            return _parse_cpu_list(value), str(path)
    raise RuntimeError("cannot determine host-wide CPU scope")


def _cpu_tick_totals(values: list[int]) -> tuple[int, int]:
    """Return Linux CPU total and idle ticks without double-counting guests."""
    if len(values) < 8:
        raise RuntimeError("/proc/stat CPU row is too short")
    # Linux fields 0..7 are user, nice, system, idle, iowait, irq, softirq,
    # and steal. Later guest/guest_nice fields are already included in
    # user/nice, so summing the full row would count guest work twice.
    return sum(values[:8]), values[3] + values[4]


def _read_cpu_ticks() -> dict[int, tuple[int, int]]:
    ticks: dict[int, tuple[int, int]] = {}
    for line in Path("/proc/stat").read_text().splitlines():
        fields = line.split()
        if not fields:
            continue
        label = fields[0]
        suffix = label.removeprefix("cpu")
        if label == suffix or not suffix.isdigit():
            continue
        values = [int(value) for value in fields[1:]]
        try:
            ticks[int(suffix)] = _cpu_tick_totals(values)
        except RuntimeError as error:
            raise RuntimeError(f"{label} {error}") from error
    if not ticks:
        raise RuntimeError("no per-CPU rows in /proc/stat")
    return ticks


def _sample_cpu_busy(
    cpu_scope: set[int],
    sample_s: float = HOST_WIDE_CPU_SAMPLE_S,
) -> dict[int, float]:
    before = _read_cpu_ticks()
    sleep(sample_s)
    after = _read_cpu_ticks()
    return _cpu_busy_between(before, after, cpu_scope)


def _cpu_busy_between(
    before: dict[int, tuple[int, int]],
    after: dict[int, tuple[int, int]],
    cpu_scope: set[int],
) -> dict[int, float]:
    busy: dict[int, float] = {}
    for cpu in sorted(cpu_scope):
        if cpu not in before or cpu not in after:
            raise RuntimeError(f"host-wide cpu{cpu} disappeared during load sample")
        total = max(0, after[cpu][0] - before[cpu][0])
        idle = max(0, after[cpu][1] - before[cpu][1])
        busy[cpu] = 1.0 if total == 0 else max(0, total - idle) / total
    return busy


class MeasurementExclusivity:
    """Continuously account for work outside the benchmark's pinned CPUs."""

    def __init__(self) -> None:
        cpu_scope, scope_source = _host_wide_cpu_scope()
        process_affinity = set(os.sched_getaffinity(0))
        monitored_cpus = cpu_scope - process_affinity
        if not monitored_cpus:
            raise RuntimeError(
                "host-wide measurement exclusivity requires a taskset affinity "
                "strictly smaller than the effective host CPU scope"
            )
        self.cpu_scope = cpu_scope
        self.scope_source = scope_source
        self.process_affinity = process_affinity
        self.monitored_cpus = monitored_cpus
        self.context = "measurement"
        self.checked_windows = 0
        self.maximum_observed_busy_fraction = 0.0
        self.maximum_consecutive_busy_windows = 0
        self._busy_streaks = {cpu: 0 for cpu in monitored_cpus}
        self._window_started = perf_counter()
        self._window_before = _read_cpu_ticks()

    def checkpoint(self, *, finish: bool = False) -> None:
        elapsed = perf_counter() - self._window_started
        if not finish and elapsed < HOST_WIDE_CPU_SAMPLE_S:
            return
        if finish and elapsed < HOST_WIDE_CPU_SAMPLE_S:
            sleep(HOST_WIDE_CPU_SAMPLE_S - elapsed)
        after = _read_cpu_ticks()
        busy = _cpu_busy_between(
            self._window_before,
            after,
            self.monitored_cpus,
        )
        self.checked_windows += 1
        self.maximum_observed_busy_fraction = max(
            self.maximum_observed_busy_fraction,
            max(busy.values()),
        )
        for cpu, fraction in busy.items():
            self._busy_streaks[cpu] = (
                self._busy_streaks[cpu] + 1
                if fraction > HOST_WIDE_MAX_BUSY_FRACTION
                else 0
            )
        self.maximum_consecutive_busy_windows = max(
            self.maximum_consecutive_busy_windows,
            max(self._busy_streaks.values()),
        )
        offenders = {
            cpu: (fraction, self._busy_streaks[cpu])
            for cpu, fraction in busy.items()
            if self._busy_streaks[cpu] >= HOST_WIDE_CONSECUTIVE_BUSY_WINDOWS
        }
        self._window_started = perf_counter()
        self._window_before = after
        if offenders:
            detail = ", ".join(
                f"cpu{cpu}={fraction * 100.0:.1f}% streak={streak}"
                for cpu, (fraction, streak) in sorted(offenders.items())
            )
            raise RuntimeError(
                "host-wide benchmark exclusivity failed during "
                f"{self.context}; non-affinity CPUs above "
                f"{HOST_WIDE_MAX_BUSY_FRACTION * 100.0:.1f}% busy in "
                f"{HOST_WIDE_CONSECUTIVE_BUSY_WINDOWS} consecutive windows: "
                f"{detail}"
            )

    def provenance(self) -> dict:
        return {
            "verdict": "clear",
            "host": os.uname().nodename,
            "scope_source": self.scope_source,
            "scope_cpus": sorted(self.cpu_scope),
            "process_affinity": sorted(self.process_affinity),
            "monitored_non_affinity_cpus": sorted(self.monitored_cpus),
            "sample_window_s": HOST_WIDE_CPU_SAMPLE_S,
            "maximum_busy_fraction": HOST_WIDE_MAX_BUSY_FRACTION,
            "consecutive_busy_windows_required": (
                HOST_WIDE_CONSECUTIVE_BUSY_WINDOWS
            ),
            "checked_windows": self.checked_windows,
            "maximum_observed_busy_fraction": self.maximum_observed_busy_fraction,
            "maximum_consecutive_busy_windows": (
                self.maximum_consecutive_busy_windows
            ),
        }


def require_host_wide_quiescence(stage: str) -> dict:
    """Fail closed unless the entire effective host cpuset is quiet."""
    cpu_scope, scope_source = _host_wide_cpu_scope()
    started = perf_counter()
    clear_streak = 0
    windows = []
    accepted_windows = []
    busy = {}
    for window_index in range(1, HOST_WIDE_ADMISSION_MAX_WINDOWS + 1):
        busy = _sample_cpu_busy(cpu_scope, HOST_WIDE_ADMISSION_SAMPLE_S)
        offenders = {
            cpu: fraction
            for cpu, fraction in busy.items()
            if fraction > HOST_WIDE_MAX_BUSY_FRACTION
        }
        windows.append(
            {
                "window": window_index,
                "maximum_observed_busy_fraction": max(busy.values()),
                "offenders": {
                    str(cpu): fraction
                    for cpu, fraction in sorted(offenders.items())
                },
            }
        )
        if offenders:
            clear_streak = 0
            accepted_windows.clear()
            continue
        clear_streak += 1
        accepted_windows.append(busy)
        if clear_streak >= HOST_WIDE_ADMISSION_CLEAR_WINDOWS:
            break
    else:
        last_offenders = windows[-1]["offenders"]
        detail = (
            ", ".join(
                f"cpu{cpu}={fraction * 100.0:.1f}%"
                for cpu, fraction in last_offenders.items()
            )
            if last_offenders
            else (
                f"only {clear_streak}/"
                f"{HOST_WIDE_ADMISSION_CLEAR_WINDOWS} final clear windows"
            )
        )
        raise RuntimeError(
            f"host-wide benchmark exclusivity failed at {stage} after "
            f"{HOST_WIDE_ADMISSION_MAX_WINDOWS} windows; required "
            f"{HOST_WIDE_ADMISSION_CLEAR_WINDOWS} consecutive clear windows: "
            f"{detail}"
        )
    process_affinity = sorted(os.sched_getaffinity(0))
    accepted_maximum = max(
        fraction
        for accepted in accepted_windows
        for fraction in accepted.values()
    )
    return {
        "stage": stage,
        "verdict": "clear",
        "host": os.uname().nodename,
        "scope_source": scope_source,
        "scope_cpus": sorted(cpu_scope),
        "scope_cpu_count": len(cpu_scope),
        "process_affinity": process_affinity,
        "sample_interval_s": HOST_WIDE_ADMISSION_SAMPLE_S,
        "maximum_busy_fraction": HOST_WIDE_MAX_BUSY_FRACTION,
        "clear_windows_required": HOST_WIDE_ADMISSION_CLEAR_WINDOWS,
        "maximum_windows": HOST_WIDE_ADMISSION_MAX_WINDOWS,
        "windows_sampled": len(windows),
        "settle_elapsed_s": perf_counter() - started,
        "rejected_window_count": sum(
            bool(window["offenders"])
            for window in windows
        ),
        "rejected_windows": [
            window
            for window in windows
            if window["offenders"]
        ],
        "maximum_observed_busy_fraction": accepted_maximum,
        "settle_maximum_observed_busy_fraction": max(
            window["maximum_observed_busy_fraction"]
            for window in windows
        ),
        "busy_cpu_count_above_limit": 0,
        "busy_fractions": {str(cpu): fraction for cpu, fraction in busy.items()},
        "accepted_clear_busy_fractions": [
            {
                str(cpu): fraction
                for cpu, fraction in accepted.items()
            }
            for accepted in accepted_windows
        ],
    }


# --------------------------------------------------------------------------- #
# timing
# --------------------------------------------------------------------------- #
def _time_batch(fn, inner: int) -> float:
    start = perf_counter()
    for _ in range(inner):
        fn()
    elapsed = perf_counter() - start
    if _MEASUREMENT_EXCLUSIVITY is not None:
        _MEASUREMENT_EXCLUSIVITY.checkpoint()
    return elapsed / inner


def calibrate(fn, target_s: float = MIN_SAMPLE_S) -> int:
    inner = 1
    while True:
        elapsed = _time_batch(fn, inner) * inner
        if elapsed >= target_s or inner >= 1 << 20:
            return max(1, inner)
        inner *= max(2, min(64, int(target_s / max(elapsed, 1e-9)) + 1))


def _sample(fn, inner: int, min_of: int = MIN_OF) -> float:
    return min(_time_batch(fn, inner) for _ in range(min_of))


@dataclass
class PairedResult:
    label: str
    ratio_p50: float
    ratio_ci: tuple[float, float]
    p50_a: float
    p50_b: float
    cv_a: float
    cv_b: float
    mad_ratio: float
    wins: str
    rounds: int
    checksum_a: str = ""
    checksum_b: str = ""
    ratios: list[float] = field(default_factory=list)


def _median_ci(values: list[float], iters: int = 2000, seed: int = 12345) -> tuple[float, float]:
    """Percentile bootstrap 95% CI of the median (fixed seed => reproducible)."""
    import random

    rng = random.Random(seed)
    n = len(values)
    medians = sorted(statistics.median(rng.choices(values, k=n)) for _ in range(iters))
    return medians[int(0.025 * iters)], medians[min(iters - 1, int(0.975 * iters))]


def paired(label: str, arm_a, arm_b, rounds: int = ROUNDS, min_of: int = MIN_OF) -> PairedResult:
    """Interleave both arms inside each round, alternating order per round.

    ratio = t_a / t_b, so ratio > 1 means arm_b is faster. With arm_a = networkx
    and arm_b = franken_networkx this reads as "fnx is Nx faster", matching the
    ledger convention.
    """
    if _MEASUREMENT_EXCLUSIVITY is not None:
        _MEASUREMENT_EXCLUSIVITY.context = label
    inner_a, inner_b = calibrate(arm_a), calibrate(arm_b)
    _sample(arm_a, inner_a, 1)
    _sample(arm_b, inner_b, 1)

    times_a, times_b, ratios = [], [], []
    for round_index in range(rounds):
        if round_index % 2 == 0:
            ta = _sample(arm_a, inner_a, min_of)
            tb = _sample(arm_b, inner_b, min_of)
        else:
            tb = _sample(arm_b, inner_b, min_of)
            ta = _sample(arm_a, inner_a, min_of)
        times_a.append(ta)
        times_b.append(tb)
        ratios.append(ta / tb)

    median_ratio = statistics.median(ratios)

    def cv(values):
        return statistics.pstdev(values) / statistics.fmean(values) * 100.0

    return PairedResult(
        label=label,
        ratio_p50=median_ratio,
        ratio_ci=_median_ci(ratios),
        p50_a=statistics.median(times_a),
        p50_b=statistics.median(times_b),
        cv_a=cv(times_a),
        cv_b=cv(times_b),
        mad_ratio=statistics.median([abs(r - median_ratio) for r in ratios]),
        wins=f"{sum(1 for r in ratios if r > 1.0)}/{len(ratios)}",
        rounds=rounds,
        ratios=ratios,
    )


def gate_decision(
    cand: PairedResult,
    *nulls: PairedResult,
) -> dict[str, object]:
    if not nulls:
        raise ValueError("at least one A/A null is required")
    null_half_width = max(
        (null.ratio_ci[1] - null.ratio_ci[0]) / 2.0
        for null in nulls
    )
    null_worst_median_bias = max(
        abs(null.ratio_p50 - 1.0)
        for null in nulls
    )
    effect_deviation = abs(cand.ratio_p50 - 1.0)
    ci_excludes_one = (
        cand.ratio_ci[0] > 1.0
        or cand.ratio_ci[1] < 1.0
    )
    clears_2x_half_width = effect_deviation > 2.0 * null_half_width
    null_median_bias_bounded = (
        null_worst_median_bias <= MAX_NULL_MEDIAN_BIAS
    )
    return {
        "contract": "corrected_three_clause_median_gate",
        "ci_excludes_one": ci_excludes_one,
        "effect_deviation": effect_deviation,
        "null_half_width": null_half_width,
        "clears_2x_half_width": clears_2x_half_width,
        "null_worst_median_bias": null_worst_median_bias,
        "max_null_median_bias": MAX_NULL_MEDIAN_BIAS,
        "null_median_bias_bounded": null_median_bias_bounded,
        "decidable": (
            ci_excludes_one
            and clears_2x_half_width
            and null_median_bias_bounded
        ),
    }


def decidable(
    cand: PairedResult,
    *nulls: PairedResult,
) -> tuple[bool, str]:
    gate = gate_decision(cand, *nulls)
    null_text = ", ".join(
        f"{null.label.split(']')[0].lstrip('[')} median={null.ratio_p50:.4f} "
        f"CI={null.ratio_ci[0]:.4f}-{null.ratio_ci[1]:.4f}"
        for null in nulls
    )
    return bool(gate["decidable"]), (
        f"clauses=CI_excludes_1:{gate['ci_excludes_one']} "
        f"effect_dev={gate['effect_deviation']:.4f}"
        f">2x_null_half_width={2.0 * gate['null_half_width']:.4f}:"
        f"{gate['clears_2x_half_width']} "
        f"worst_null_median_bias={gate['null_worst_median_bias']:.4f}"
        f"<=0.0200:{gate['null_median_bias_bounded']} "
        f"({null_text})"
    )


def report(
    result: PairedResult,
    nulls: tuple[PairedResult, ...] = (),
) -> str:
    line = (
        f"{result.label:<54} ratio_p50={result.ratio_p50:9.4f}x "
        f"CI=[{result.ratio_ci[0]:.4f},{result.ratio_ci[1]:.4f}] "
        f"a={result.p50_a * 1e6:9.2f}us b={result.p50_b * 1e6:9.2f}us "
        f"cv={result.cv_a:5.2f}/{result.cv_b:5.2f}% wins={result.wins}"
    )
    if nulls:
        ok, why = decidable(result, *nulls)
        line += f"  -> {'DECIDABLE' if ok else 'UNDECIDABLE'} {why}"
    print(line, flush=True)
    return line


# --------------------------------------------------------------------------- #
# byte-identity proof
# --------------------------------------------------------------------------- #
def canon(obj):
    """Order-preserving canonical form — iteration order is part of the contract."""
    if isinstance(obj, dict):
        return ["<dict>"] + [[canon(k), canon(v)] for k, v in obj.items()]
    if isinstance(obj, (list, tuple)):
        return [canon(x) for x in obj]
    if isinstance(obj, (set, frozenset)):
        return ["<set>"] + sorted(canon(x) for x in obj)
    if hasattr(obj, "edges") and hasattr(obj, "nodes"):
        nodes = list(obj.nodes(data=True))
        edges = (
            list(obj.edges(keys=True, data=True))
            if obj.is_multigraph()
            else list(obj.edges(data=True))
        )
        return ["<graph>", [canon(x) for x in nodes], [canon(e) for e in edges]]
    if hasattr(obj, "__iter__") and not isinstance(obj, (str, bytes, int, float)):
        return [canon(x) for x in obj]
    return obj


def canonical_bytes(obj) -> bytes:
    """Complete canonical bytes; equality never relies on a truncated digest."""
    return json.dumps(canon(obj), sort_keys=False, default=str).encode()


def run_rows(tag: str, rows, rounds: int = ROUNDS) -> list[dict]:
    """Prove byte-identity, then gate against both arm-specific A/A nulls."""
    global _MEASUREMENT_EXCLUSIVITY
    quiescence = EXTRA_PROVENANCE.get("host_wide_quiescence")
    if not isinstance(quiescence, dict) or "pre_setup" not in quiescence:
        raise RuntimeError("host-wide pre-setup quiescence proof is missing")
    quiescence["pre_measurement"] = require_host_wide_quiescence(
        "pre_measurement",
    )
    _MEASUREMENT_EXCLUSIVITY = MeasurementExclusivity()
    provenance_header(tag)
    results = []
    for label, arm_nx, arm_fnx in rows:
        left, right = arm_nx(), arm_fnx()
        left_bytes = canonical_bytes(left)
        right_bytes = canonical_bytes(right)
        da = hashlib.sha256(left_bytes).hexdigest()
        db = hashlib.sha256(right_bytes).hexdigest()
        if left_bytes != right_bytes:
            print(f"{label:<54} PARITY-DIVERGENCE nx={da} fnx={db} — NOT TIMED", flush=True)
            results.append({"label": label, "parity": "DIVERGENT"})
            continue
        thread_provenance = {
            "networkx": probe_operation_threads(arm_nx),
            "franken_networkx": probe_operation_threads(arm_fnx),
        }
        null_nx = paired(f"[A/A nx] {label}", arm_nx, arm_nx, rounds=rounds)
        null_fnx = paired(f"[A/A fnx] {label}", arm_fnx, arm_fnx, rounds=rounds)
        cand = paired(label, arm_nx, arm_fnx, rounds=rounds)
        report(null_nx)
        report(null_fnx)
        report(cand, (null_nx, null_fnx))
        gate = gate_decision(cand, null_nx, null_fnx)
        results.append({
            "label": label,
            "parity": "IDENTICAL",
            "checksum": da,
            "ratio_p50": cand.ratio_p50,
            "ratio_ci": list(cand.ratio_ci),
            "ratio_samples": cand.ratios,
            "null_nx_median": null_nx.ratio_p50,
            "null_nx_ci": list(null_nx.ratio_ci),
            "null_nx_samples": null_nx.ratios,
            "null_fnx_median": null_fnx.ratio_p50,
            "null_fnx_ci": list(null_fnx.ratio_ci),
            "null_fnx_samples": null_fnx.ratios,
            "decision_gate": gate,
            "decidable": gate["decidable"],
            "cv": [cand.cv_a, cand.cv_b],
            "p50_us": [cand.p50_a * 1e6, cand.p50_b * 1e6],
            "thread_provenance": thread_provenance,
        })
    _MEASUREMENT_EXCLUSIVITY.context = "measurement closeout"
    _MEASUREMENT_EXCLUSIVITY.checkpoint(finish=True)
    print(
        "host_wide_measurement_exclusivity_json="
        + json.dumps(
            _MEASUREMENT_EXCLUSIVITY.provenance(),
            sort_keys=True,
            separators=(",", ":"),
        ),
        flush=True,
    )
    _MEASUREMENT_EXCLUSIVITY = None
    return results


# --------------------------------------------------------------------------- #
# suites
# --------------------------------------------------------------------------- #
def _build_pair(n, m, seed, weighted, directed=False):
    """Same node/edge insertion order in both libraries."""
    import random

    import networkx as nx
    import franken_networkx as fnx

    rng = random.Random(seed)
    seen, stream = set(), []
    while len(stream) < m:
        u, v = rng.randrange(n), rng.randrange(n)
        if u == v or (min(u, v), max(u, v)) in seen:
            continue
        seen.add((min(u, v), max(u, v)))
        stream.append((str(u), str(v), {"weight": rng.randint(1, 20)} if weighted else {}))
    nodes = [str(i) for i in range(n)]
    gnx = (nx.DiGraph if directed else nx.Graph)()
    gfx = (fnx.DiGraph if directed else fnx.Graph)()
    gnx.add_nodes_from(nodes)
    gfx.add_nodes_from(nodes)
    gnx.add_edges_from([(u, v, dict(d)) for u, v, d in stream])
    gfx.add_edges_from([(u, v, dict(d)) for u, v, d in stream])
    incumbent_module = type(gnx).__module__
    if not incumbent_module.startswith("networkx"):
        raise RuntimeError(
            f"nx arm must be genuine upstream, got module {incumbent_module!r}"
        )
    return gnx, gfx


def _materialize_claim_payload(filename: str, payload: bytes) -> str:
    """Reuse one content-addressed scratch file for path-based reader claims."""
    fixture_root = Path(
        os.environ.get("FNX_CLAIM_FIXTURE_DIR", "/data/tmp")
    )
    if not fixture_root.is_dir():
        raise RuntimeError(
            "claim fixture root must already exist; refusing to mint a "
            f"directory: {fixture_root}"
        )
    path = fixture_root / filename
    if path.exists():
        existing = path.read_bytes()
        if existing != payload:
            raise RuntimeError(
                f"existing claim fixture has unexpected content: {path}"
            )
    else:
        path.write_bytes(payload)
    if path.read_bytes() != payload:
        raise RuntimeError(f"claim fixture write verification failed: {path}")
    return str(path)


def _build_ordered_arc_pair(n, m, seed, weighted):
    """Same directed arc insertion order with ordered-pair deduplication."""
    import random

    import networkx as nx
    import franken_networkx as fnx

    rng = random.Random(seed)
    seen, stream = set(), []
    while len(stream) < m:
        u, v = rng.randrange(n), rng.randrange(n)
        if u == v or (u, v) in seen:
            continue
        seen.add((u, v))
        stream.append(
            (
                str(u),
                str(v),
                {"weight": rng.randint(1, 20)} if weighted else {},
            )
        )
    nodes = [str(index) for index in range(n)]
    gnx, gfx = nx.DiGraph(), fnx.DiGraph()
    for graph in (gnx, gfx):
        graph.add_nodes_from(nodes)
        graph.add_edges_from(
            (source, target, dict(attrs))
            for source, target, attrs in stream
        )
    incumbent_module = type(gnx).__module__
    if not incumbent_module.startswith("networkx"):
        raise RuntimeError(
            f"nx arm must be genuine upstream, got module {incumbent_module!r}"
        )
    return gnx, gfx


def suite_view_accessors():
    """br-r37-c1-wbwkb: the accessor-descriptor surface."""
    gnx, gfx = _build_pair(2000, 8000, seed=7, weighted=True)
    nodes = [str(i) for i in range(500)]
    return [
        ("G.nodes x500 (bare accessor)",
         lambda: [gnx.nodes for _ in nodes], lambda: [gfx.nodes for _ in nodes]),
        ("G.edges x500 (bare accessor)",
         lambda: [gnx.edges for _ in nodes], lambda: [gfx.edges for _ in nodes]),
        ("G.degree x500 (bare accessor)",
         lambda: [gnx.degree for _ in nodes], lambda: [gfx.degree for _ in nodes]),
        ("G.adj x500 (bare accessor)",
         lambda: [gnx.adj for _ in nodes], lambda: [gfx.adj for _ in nodes]),
        ("G.nodes[n] x500",
         lambda: [gnx.nodes[n] for n in nodes], lambda: [gfx.nodes[n] for n in nodes]),
        ("G.degree[n] x500",
         lambda: [gnx.degree[n] for n in nodes], lambda: [gfx.degree[n] for n in nodes]),
        ("len(G.edges) x500",
         lambda: [len(gnx.edges) for _ in nodes], lambda: [len(gfx.edges) for _ in nodes]),
        ("sum(G.nodes[n]['weight']) x500",
         lambda: sum(gnx.nodes[n].get("weight", 0) for n in nodes),
         lambda: sum(gfx.nodes[n].get("weight", 0) for n in nodes)),
    ]


def suite_adj_descriptor():
    """br-r37-c1-pc4hk: cache public Graph.adj; retain private _adj setter."""
    import franken_networkx as fnx

    gnx, gfx = _build_pair(2000, 8000, seed=7, weighted=True)
    repeats = range(500)
    descriptor = fnx.Graph.__dict__["adj"]
    property_descriptor = fnx._GRAPH_PUBLIC_ADJ_PROPERTY
    raw_setattr = fnx._GRAPH_SETATTR_BEFORE_PUBLIC_ADJ_CACHE
    candidate_setattr = fnx._graph_setattr_with_cached_public_adj
    assert isinstance(descriptor, fnx._CachedViewDescriptor)
    _ = gfx.adj

    def property_accessor():
        return [property_descriptor.__get__(gfx, fnx.Graph) for _ in repeats]

    def cached_accessor():
        return [gfx.adj for _ in repeats]

    baseline_mut = fnx.Graph()
    candidate_mut = fnx.Graph()
    for graph in (baseline_mut, candidate_mut):
        graph.add_nodes_from(("left", "right"))

    def property_mutation():
        fnx.Graph.__setattr__ = raw_setattr
        fnx.Graph.adj = property_descriptor
        for _ in range(512):
            baseline_mut.add_edge("left", "right")
            baseline_mut.remove_edge("left", "right")
        return baseline_mut.number_of_edges()

    def cached_mutation():
        fnx.Graph.__setattr__ = candidate_setattr
        fnx.Graph.adj = descriptor
        for _ in range(512):
            candidate_mut.add_edge("left", "right")
            candidate_mut.remove_edge("left", "right")
        return candidate_mut.number_of_edges()

    return [
        (
            "G.adj x500 [property/cached]",
            property_accessor,
            cached_accessor,
        ),
        (
            "G.adj x500 [nx/fnx]",
            lambda: [gnx.adj for _ in repeats],
            cached_accessor,
        ),
        (
            "len(G.adj) x500 [nx/fnx]",
            lambda: [len(gnx.adj) for _ in repeats],
            lambda: [len(gfx.adj) for _ in repeats],
        ),
        (
            "add/remove edge x512 [property/cached]",
            property_mutation,
            cached_mutation,
        ),
    ]


def suite_adjacency_len():
    """br-r37-c1-4rgsf: outer simple adjacency views use raw node count."""
    import franken_networkx as fnx

    gnx, gfx = _build_pair(2000, 8000, seed=7, weighted=True)
    dnx, dfx = _build_pair(2000, 8000, seed=17, weighted=True, directed=True)
    repeats = range(500)
    graph_view = gfx.adj

    def atlas_len_x500():
        return [len(graph_view._atlas()) for _ in repeats]

    def native_len_x500():
        return [len(graph_view) for _ in repeats]

    return [
        (
            "len(G.adj) x500 [atlas/raw-bound]",
            atlas_len_x500,
            native_len_x500,
        ),
        (
            "len(G.adj) x500 [nx/fnx]",
            lambda: [len(gnx.adj) for _ in repeats],
            native_len_x500,
        ),
        (
            "len(DG.adj) x500 [nx/fnx]",
            lambda: [len(dnx.adj) for _ in repeats],
            lambda: [len(dfx.adj) for _ in repeats],
        ),
        (
            "len(DG.succ) x500 [nx/fnx]",
            lambda: [len(dnx.succ) for _ in repeats],
            lambda: [len(dfx.succ) for _ in repeats],
        ),
        (
            "len(DG.pred) x500 [nx/fnx]",
            lambda: [len(dnx.pred) for _ in repeats],
            lambda: [len(dfx.pred) for _ in repeats],
        ),
    ]


def suite_adjacency_iter():
    """br-r37-c1-krg59: outer simple views reuse the live node-key mirror."""
    gnx, gfx = _build_pair(20_000, 0, seed=7, weighted=False)
    dnx, dfx = _build_pair(
        20_000, 0, seed=17, weighted=False, directed=True
    )
    graph_view = gfx.adj
    digraph_view = dfx.adj
    assert graph_view._fnx_native_iter is not None
    assert digraph_view._fnx_native_iter is not None

    def old_graph_iter():
        return iter(dict.fromkeys(graph_view._atlas()))

    def old_digraph_iter():
        return iter(dict.fromkeys(digraph_view._atlas()))

    def old_graph_list():
        return list(old_graph_iter())

    def old_digraph_list():
        return list(old_digraph_iter())

    # Stabilize worker frequency before the first A/A round. Both mechanism
    # arms are warmed outside every timed region.
    warm_deadline = perf_counter() + 2.0
    while perf_counter() < warm_deadline:
        old_graph_iter()
        iter(graph_view)
        old_digraph_iter()
        iter(digraph_view)

    return [
        (
            "iter(G.adj) [fromkeys/raw-bound]",
            old_graph_iter,
            lambda: iter(graph_view),
        ),
        (
            "iter(DG.adj) [fromkeys/raw-bound]",
            old_digraph_iter,
            lambda: iter(digraph_view),
        ),
        (
            "list(G.adj) [fromkeys/raw-bound]",
            old_graph_list,
            lambda: list(graph_view),
        ),
        (
            "list(DG.adj) [fromkeys/raw-bound]",
            old_digraph_list,
            lambda: list(digraph_view),
        ),
        (
            "iter(G.adj) [nx/fnx]",
            lambda: iter(gnx.adj),
            lambda: iter(graph_view),
        ),
        (
            "list(G.adj) [nx/fnx]",
            lambda: list(gnx.adj),
            lambda: list(graph_view),
        ),
        (
            "iter(DG.adj) [nx/fnx]",
            lambda: iter(dnx.adj),
            lambda: iter(digraph_view),
        ),
        (
            "list(DG.adj) [nx/fnx]",
            lambda: list(dnx.adj),
            lambda: list(digraph_view),
        ),
        (
            "list(DG.succ) [nx/fnx]",
            lambda: list(dnx.succ),
            lambda: list(dfx.succ),
        ),
        (
            "list(DG.pred) [nx/fnx]",
            lambda: list(dnx.pred),
            lambda: list(dfx.pred),
        ),
    ]


def suite_multi_adjacency_iter():
    """br-r37-c1-yisq4: multigraph outer views reuse the node-key mirror."""
    import networkx as nx
    import franken_networkx as fnx

    gnx, gfx = nx.MultiGraph(), fnx.MultiGraph()
    dnx, dfx = nx.MultiDiGraph(), fnx.MultiDiGraph()
    nodes = range(20_000)
    for graph in (gnx, gfx, dnx, dfx):
        graph.add_nodes_from(nodes)
    graph_view = gfx.adj
    digraph_view = dfx.adj
    assert graph_view._fnx_native_iter is not None
    assert digraph_view._fnx_native_iter is not None

    def old_graph_iter():
        return iter(dict.fromkeys(graph_view._fnx_owner))

    def old_digraph_iter():
        return iter(dict.fromkeys(digraph_view._fnx_owner))

    def old_graph_list():
        return list(old_graph_iter())

    def old_digraph_list():
        return list(old_digraph_iter())

    warm_deadline = perf_counter() + 2.0
    while perf_counter() < warm_deadline:
        old_graph_iter()
        iter(graph_view)
        old_digraph_iter()
        iter(digraph_view)

    return [
        (
            "iter(MG.adj) [fromkeys/raw-bound]",
            old_graph_iter,
            lambda: iter(graph_view),
        ),
        (
            "iter(MDG.adj) [fromkeys/raw-bound]",
            old_digraph_iter,
            lambda: iter(digraph_view),
        ),
        (
            "list(MG.adj) [fromkeys/raw-bound]",
            old_graph_list,
            lambda: list(graph_view),
        ),
        (
            "list(MDG.adj) [fromkeys/raw-bound]",
            old_digraph_list,
            lambda: list(digraph_view),
        ),
        (
            "iter(MG.adj) [nx/fnx]",
            lambda: iter(gnx.adj),
            lambda: iter(graph_view),
        ),
        (
            "list(MG.adj) [nx/fnx]",
            lambda: list(gnx.adj),
            lambda: list(graph_view),
        ),
        (
            "iter(MDG.adj) [nx/fnx]",
            lambda: iter(dnx.adj),
            lambda: iter(digraph_view),
        ),
        (
            "list(MDG.adj) [nx/fnx]",
            lambda: list(dnx.adj),
            lambda: list(digraph_view),
        ),
        (
            "list(MDG.succ) [nx/fnx]",
            lambda: list(dnx.succ),
            lambda: list(dfx.succ),
        ),
        (
            "list(MDG.pred) [nx/fnx]",
            lambda: list(dnx.pred),
            lambda: list(dfx.pred),
        ),
    ]


def suite_multi_adjacency_contains():
    """br-r37-c1-7icpc: bind raw node membership into multigraph views."""
    import networkx as nx
    import franken_networkx as fnx

    node_names = [f"node-{index}" for index in range(20_000)]
    present = node_names[:512]
    missing = [f"missing-{index}" for index in range(512)]
    gnx, gfx = nx.MultiGraph(), fnx.MultiGraph()
    dnx, dfx = nx.MultiDiGraph(), fnx.MultiDiGraph()
    for graph in (gnx, gfx, dnx, dfx):
        graph.add_nodes_from(node_names)
    graph_view = gfx.adj
    digraph_view = dfx.adj
    assert graph_view._fnx_native_contains is not None
    assert digraph_view._fnx_native_contains is not None

    def old_contains(view, node):
        hash(node)
        owner = view._fnx_owner
        if owner is not None:
            return node in owner
        return node in view._atlas()

    def old_graph_present():
        return sum(old_contains(graph_view, node) for node in present)

    def new_graph_present():
        return sum(node in graph_view for node in present)

    def old_digraph_present():
        return sum(old_contains(digraph_view, node) for node in present)

    def new_digraph_present():
        return sum(node in digraph_view for node in present)

    def old_digraph_missing():
        return sum(old_contains(digraph_view, node) for node in missing)

    def new_digraph_missing():
        return sum(node in digraph_view for node in missing)

    warm_deadline = perf_counter() + 2.0
    while perf_counter() < warm_deadline:
        old_graph_present()
        new_graph_present()
        old_digraph_present()
        new_digraph_present()

    return [
        (
            "n in MG.adj x512 [owner-chain/raw-bound]",
            old_graph_present,
            new_graph_present,
        ),
        (
            "n in MDG.adj x512 [owner-chain/raw-bound]",
            old_digraph_present,
            new_digraph_present,
        ),
        (
            "missing in MDG.adj x512 [owner-chain/raw-bound]",
            old_digraph_missing,
            new_digraph_missing,
        ),
        (
            "n in MG.adj x512 [nx/fnx]",
            lambda: sum(node in gnx.adj for node in present),
            new_graph_present,
        ),
        (
            "missing in MG.adj x512 [nx/fnx]",
            lambda: sum(node in gnx.adj for node in missing),
            lambda: sum(node in graph_view for node in missing),
        ),
        (
            "n in MDG.adj x512 [nx/fnx]",
            lambda: sum(node in dnx.adj for node in present),
            new_digraph_present,
        ),
        (
            "n in MDG.succ x512 [nx/fnx]",
            lambda: sum(node in dnx.succ for node in present),
            lambda: sum(node in dfx.succ for node in present),
        ),
        (
            "n in MDG.pred x512 [nx/fnx]",
            lambda: sum(node in dnx.pred for node in present),
            lambda: sum(node in dfx.pred for node in present),
        ),
    ]


def suite_multi_row_getitem():
    """br-r37-c1-fy913: reuse warm live multigraph adjacency-row views."""
    import networkx as nx
    import franken_networkx as fnx

    nodes = tuple(f"u{index}" for index in range(512))

    def build(graph_type):
        graph = graph_type()
        for index in range(512):
            graph.add_edge(
                f"u{index}", f"v{index}", key=0, weight=index
            )
        return graph

    mg_nx, mg_fnx = build(nx.MultiGraph), build(fnx.MultiGraph)
    mdg_nx, mdg_fnx = build(nx.MultiDiGraph), build(fnx.MultiDiGraph)

    def allocated_mg_row(node):
        """Source-equivalent pre-lever exact-MultiGraph return path."""
        hash(node)
        try:
            mg_fnx._native_adjacency_row(node)
        except KeyError as exc:
            raise KeyError(node) from exc
        return fnx.AdjacencyView(
            lambda: mg_fnx._native_adjacency_row(node)
        )

    def allocated_mdg_row(node):
        """Source-equivalent pre-lever exact-MultiDiGraph return path."""
        hash(node)
        try:
            mdg_fnx._native_successor_row(node)
        except KeyError as exc:
            raise KeyError(node) from exc
        return fnx.AdjacencyView(
            lambda: mdg_fnx._native_successor_row(node)
        )

    def row_batch(getter):
        last = None
        for node in nodes:
            last = getter(node)
        return type(last).__name__, tuple(last)

    return [
        (
            "MG[u] x512 [allocate/cache]",
            lambda: row_batch(allocated_mg_row),
            lambda: row_batch(mg_fnx.__getitem__),
        ),
        (
            "NetworkX/FNX MG[u] x512 [cached]",
            lambda: row_batch(mg_nx.__getitem__),
            lambda: row_batch(mg_fnx.__getitem__),
        ),
        (
            "MDG[u] x512 [allocate/cache]",
            lambda: row_batch(allocated_mdg_row),
            lambda: row_batch(mdg_fnx.__getitem__),
        ),
        (
            "NetworkX/FNX MDG[u] x512 [cached]",
            lambda: row_batch(mdg_nx.__getitem__),
            lambda: row_batch(mdg_fnx.__getitem__),
        ),
    ]


def suite_multiedge_getitem():
    """Scalar keyed edge-data lookup without view/key-resolution layering."""
    import networkx as nx
    import franken_networkx as fnx

    def build_pair(nx_type, fnx_type):
        gnx, gfx = nx_type(), fnx_type()
        for index in range(512):
            left, right = f"u{index}", f"v{index}"
            attrs = {"weight": index, "tag": str(index)}
            gnx.add_edge(left, right, key=0, **attrs)
            gfx.add_edge(left, right, key=0, **attrs)
        keys = [(f"u{index}", f"v{index}", 0) for index in range(512)]
        return gnx, gfx, keys

    mg_nx, mg_fnx, mg_keys = build_pair(nx.MultiGraph, fnx.MultiGraph)
    mdg_nx, mdg_fnx, mdg_keys = build_pair(nx.MultiDiGraph, fnx.MultiDiGraph)
    mg_nx_edges, mg_fnx_edges = mg_nx.edges, mg_fnx.edges
    mdg_nx_edges, mdg_fnx_edges = mdg_nx.edges, mdg_fnx.edges

    def build_resolver_control(graph_type):
        """Identical final graphs; only the conservative remap flag differs."""
        scan, identity = graph_type(), graph_type()
        for index in range(512):
            left, right = f"u{index}", f"v{index}"
            attrs = {"weight": index, "tag": str(index)}
            scan.add_edge(left, right, key=0, **attrs)
            identity.add_edge(left, right, key=0, **attrs)
        scan.add_edge("probe-left", "probe-right", key="remapped-probe")
        scan.remove_edge("probe-left", "probe-right", key="remapped-probe")
        identity.add_edge("probe-left", "probe-right", key=0)
        identity.remove_edge("probe-left", "probe-right", key=0)
        assert list(scan.nodes) == list(identity.nodes)
        assert list(scan.edges(keys=True, data=True)) == list(
            identity.edges(keys=True, data=True)
        )
        keys = [(f"u{index}", f"v{index}", 0) for index in range(512)]
        return scan, identity, keys

    mg_scan, mg_identity, mg_resolver_keys = build_resolver_control(
        fnx.MultiGraph
    )
    mdg_scan, mdg_identity, mdg_resolver_keys = build_resolver_control(
        fnx.MultiDiGraph
    )
    mg_scan_edges, mg_identity_edges = mg_scan.edges, mg_identity.edges
    mdg_scan_edges, mdg_identity_edges = mdg_scan.edges, mdg_identity.edges
    missing = object()
    mg_scan_raw = fnx._MULTIGRAPH_PRIVATE_AWARE_GET_EDGE_DATA.__get__(
        mg_scan, fnx.MultiGraph
    )
    mg_identity_raw = fnx._MULTIGRAPH_PRIVATE_AWARE_GET_EDGE_DATA.__get__(
        mg_identity, fnx.MultiGraph
    )
    mdg_scan_raw = fnx._MULTIDIGRAPH_PRIVATE_AWARE_GET_EDGE_DATA.__get__(
        mdg_scan, fnx.MultiDiGraph
    )
    mdg_identity_raw = fnx._MULTIDIGRAPH_PRIVATE_AWARE_GET_EDGE_DATA.__get__(
        mdg_identity, fnx.MultiDiGraph
    )

    def layered_multigraph_lookup(edge):
        """Source-equivalent pre-lever chain for the causal A/B."""
        u, v, key = edge
        hash(u)
        hash(v)
        hash(key)
        adj = mg_fnx.adj
        try:
            return adj[u][v][key]
        except KeyError:
            return adj[v][u][key]

    def layered_multidigraph_lookup(edge):
        """Source-equivalent pre-lever chain for the directed causal A/B."""
        u, v, key = edge
        hash(u)
        hash(v)
        hash(key)
        succ = mdg_fnx.succ
        if u not in succ:
            raise KeyError(u)
        if v not in succ[u]:
            raise KeyError(v)
        if key not in succ[u][v]:
            raise KeyError(key)
        return succ[u][v][key]

    return [
        (
            "MG.edges[u,v,k] x512 [layered/native]",
            lambda: [layered_multigraph_lookup(edge) for edge in mg_keys],
            lambda: [mg_fnx_edges[edge] for edge in mg_keys],
        ),
        (
            "MG.edges[u,v,k] x512 [nx/fnx]",
            lambda: [mg_nx_edges[edge] for edge in mg_keys],
            lambda: [mg_fnx_edges[edge] for edge in mg_keys],
        ),
        (
            "MDG.edges[u,v,k] x512 [layered/native]",
            lambda: [layered_multidigraph_lookup(edge) for edge in mdg_keys],
            lambda: [mdg_fnx_edges[edge] for edge in mdg_keys],
        ),
        (
            "MDG.edges[u,v,k] x512 [nx/fnx]",
            lambda: [mdg_nx_edges[edge] for edge in mdg_keys],
            lambda: [mdg_fnx_edges[edge] for edge in mdg_keys],
        ),
        (
            "MG raw keyed x512 [scan/identity-int]",
            lambda: [
                mg_scan_raw(u, v, key, missing)
                for u, v, key in mg_resolver_keys
            ],
            lambda: [
                mg_identity_raw(u, v, key, missing)
                for u, v, key in mg_resolver_keys
            ],
        ),
        (
            "MG edge view x512 [scan/identity-int]",
            lambda: [mg_scan_edges[edge] for edge in mg_resolver_keys],
            lambda: [mg_identity_edges[edge] for edge in mg_resolver_keys],
        ),
        (
            "MDG raw keyed x512 [scan/identity-int]",
            lambda: [
                mdg_scan_raw(u, v, key, missing)
                for u, v, key in mdg_resolver_keys
            ],
            lambda: [
                mdg_identity_raw(u, v, key, missing)
                for u, v, key in mdg_resolver_keys
            ],
        ),
        (
            "MDG edge view x512 [scan/identity-int]",
            lambda: [mdg_scan_edges[edge] for edge in mdg_resolver_keys],
            lambda: [mdg_identity_edges[edge] for edge in mdg_resolver_keys],
        ),
    ]


def suite_multiedge_iter():
    """br-r37-c1-c5zn8: reuse direct multiedge keyed-list materialization."""
    import networkx as nx
    import franken_networkx as fnx

    nodes = [str(index) for index in range(2000)]
    edges = [
        (
            str(index % 1999),
            str((index * 37 + 1) % 1999),
            index % 3,
        )
        for index in range(8000)
    ]
    mg_nx, mg_fnx = nx.MultiGraph(), fnx.MultiGraph()
    mdg_nx, mdg_fnx = nx.MultiDiGraph(), fnx.MultiDiGraph()
    for graph in (mg_nx, mg_fnx, mdg_nx, mdg_fnx):
        graph.add_nodes_from(nodes)
        graph.add_edges_from(edges)

    mg_view = mg_fnx.edges
    mdg_view = mdg_fnx.edges

    def old_iter(view):
        """Source-equivalent pre-lever direct-view iterator creation."""
        return fnx._FailFastEdgeIterator(
            view._graph,
            view(keys=True),
            guard_edge_count=True,
        )

    # Populate both private candidate materializations outside timed regions.
    iter(mg_view)
    iter(mdg_view)

    return [
        (
            "MG iter(edges) old/materialized-cache",
            lambda: old_iter(mg_view),
            lambda: iter(mg_view),
        ),
        (
            "MG iter(edges) nx/fnx",
            lambda: iter(mg_nx.edges),
            lambda: iter(mg_view),
        ),
        (
            "MG list(edges) nx/fnx",
            lambda: list(mg_nx.edges),
            lambda: list(mg_view),
        ),
        (
            "MDG iter(edges) old/materialized-cache",
            lambda: old_iter(mdg_view),
            lambda: iter(mdg_view),
        ),
        (
            "MDG iter(edges) nx/fnx",
            lambda: iter(mdg_nx.edges),
            lambda: iter(mdg_view),
        ),
        (
            "MDG list(edges) nx/fnx",
            lambda: list(mdg_nx.edges),
            lambda: list(mdg_view),
        ),
    ]


def suite_multikeydict_iter():
    """br-r37-c1-u4gjj: cache captured multiedge key-view iteration."""
    import networkx as nx
    import franken_networkx as fnx

    keys = [f"k{index}" for index in range(8)]
    mg_nx, mg_fnx = nx.MultiGraph(), fnx.MultiGraph()
    mdg_nx, mdg_fnx = nx.MultiDiGraph(), fnx.MultiDiGraph()
    for graph in (mg_nx, mg_fnx, mdg_nx, mdg_fnx):
        for index, key in enumerate(keys):
            graph.add_edge("left", "right", key=key, weight=index)

    mg_nx_view = mg_nx["left"]["right"]
    mg_fnx_view = mg_fnx["left"]["right"]
    mdg_nx_view = mdg_nx["left"]["right"]
    mdg_fnx_view = mdg_fnx["left"]["right"]
    repeats = range(512)

    def native_iter_batch(view):
        # Source-equivalent pre-lever path: AtlasView.__iter__ delegated to
        # MultiKeyDictView.__iter__, which rebuilt its key vector each call.
        return [iter(view._atlas()) for _ in repeats]

    def cached_iter_batch(view):
        return [iter(view) for _ in repeats]

    def list_batch(view):
        return [list(view) for _ in repeats]

    # The governing surface is warm captured-view iteration. Stabilize worker
    # frequency and populate the candidate cache before any timed region.
    warm_deadline = perf_counter() + 2.0
    while perf_counter() < warm_deadline:
        native_iter_batch(mg_fnx_view)
        cached_iter_batch(mg_fnx_view)
        native_iter_batch(mdg_fnx_view)
        cached_iter_batch(mdg_fnx_view)

    return [
        (
            "MG key iter x512 [native materialize/cached]",
            lambda: native_iter_batch(mg_fnx_view),
            lambda: cached_iter_batch(mg_fnx_view),
        ),
        (
            "MG key iter x512 [nx/fnx]",
            lambda: cached_iter_batch(mg_nx_view),
            lambda: cached_iter_batch(mg_fnx_view),
        ),
        (
            "MG key list x512 [nx/fnx]",
            lambda: list_batch(mg_nx_view),
            lambda: list_batch(mg_fnx_view),
        ),
        (
            "MDG key iter x512 [native materialize/cached]",
            lambda: native_iter_batch(mdg_fnx_view),
            lambda: cached_iter_batch(mdg_fnx_view),
        ),
        (
            "MDG key iter x512 [nx/fnx]",
            lambda: cached_iter_batch(mdg_nx_view),
            lambda: cached_iter_batch(mdg_fnx_view),
        ),
        (
            "MDG key list x512 [nx/fnx]",
            lambda: list_batch(mdg_nx_view),
            lambda: list_batch(mdg_fnx_view),
        ),
    ]


def suite_digraph_descriptors():
    """br-r37-c1-dyuzb: cache directed public adjacency descriptors."""
    import franken_networkx as fnx

    gnx, gfx = _build_pair(
        2000, 8000, seed=17, weighted=True, directed=True
    )
    repeats = range(500)
    properties = fnx._DIGRAPH_PUBLIC_ADJ_PROPERTIES
    assert all(
        isinstance(fnx.DiGraph.__dict__[name], fnx._CachedViewDescriptor)
        for name in ("adj", "succ", "pred")
    )
    _ = gfx.adj, gfx.succ, gfx.pred

    def property_triple():
        return [
            (
                properties["adj"].__get__(gfx, fnx.DiGraph),
                properties["succ"].__get__(gfx, fnx.DiGraph),
                properties["pred"].__get__(gfx, fnx.DiGraph),
            )
            for _ in repeats
        ]

    def cached_triple():
        return [(gfx.adj, gfx.succ, gfx.pred) for _ in repeats]

    return [
        (
            "DG adj/succ/pred x500 [property/cached]",
            property_triple,
            cached_triple,
        ),
        (
            "DG adj/succ/pred x500 [nx/fnx]",
            lambda: [(gnx.adj, gnx.succ, gnx.pred) for _ in repeats],
            cached_triple,
        ),
        (
            "len(DG.adj) x500 [nx/fnx]",
            lambda: [len(gnx.adj) for _ in repeats],
            lambda: [len(gfx.adj) for _ in repeats],
        ),
        (
            "len(DG.succ) x500 [nx/fnx]",
            lambda: [len(gnx.succ) for _ in repeats],
            lambda: [len(gfx.succ) for _ in repeats],
        ),
        (
            "len(DG.pred) x500 [nx/fnx]",
            lambda: [len(gnx.pred) for _ in repeats],
            lambda: [len(gfx.pred) for _ in repeats],
        ),
    ]


def suite_multidigraph_descriptors():
    """br-r37-c1-a5xrj: cache multi-directed public adjacency descriptors."""
    import random

    import networkx as nx
    import franken_networkx as fnx

    rng = random.Random(29)
    nodes = [str(index) for index in range(2000)]
    edges = []
    for index in range(8000):
        source = nodes[rng.randrange(len(nodes))]
        target = nodes[rng.randrange(len(nodes))]
        edges.append(
            (
                source,
                target,
                f"k{index % 3}",
                {"weight": rng.randrange(1, 21)},
            )
        )
    gnx = nx.MultiDiGraph()
    gfx = fnx.MultiDiGraph()
    for graph in (gnx, gfx):
        graph.add_nodes_from(nodes)
        graph.add_edges_from(
            (source, target, key, dict(attrs))
            for source, target, key, attrs in edges
        )
    assert type(gnx).__module__.startswith("networkx")

    repeats = range(500)
    present = nodes[:512]
    properties = fnx._MULTIDIGRAPH_PUBLIC_ADJ_PROPERTIES
    assert all(
        isinstance(fnx.MultiDiGraph.__dict__[name], fnx._CachedViewDescriptor)
        for name in ("adj", "succ", "pred")
    )
    _ = gfx.adj, gfx.succ, gfx.pred

    def property_triple():
        return [
            (
                properties["adj"].__get__(gfx, fnx.MultiDiGraph),
                properties["succ"].__get__(gfx, fnx.MultiDiGraph),
                properties["pred"].__get__(gfx, fnx.MultiDiGraph),
            )
            for _ in repeats
        ]

    def cached_triple():
        return [(gfx.adj, gfx.succ, gfx.pred) for _ in repeats]

    warm_deadline = perf_counter() + 2.0
    while perf_counter() < warm_deadline:
        property_triple()
        cached_triple()

    return [
        (
            "MDG adj/succ/pred x500 [property/cached]",
            property_triple,
            cached_triple,
        ),
        (
            "MDG adj/succ/pred x500 [nx/fnx]",
            lambda: [(gnx.adj, gnx.succ, gnx.pred) for _ in repeats],
            cached_triple,
        ),
        (
            "n in MDG.adj x512 [nx/fnx]",
            lambda: sum(node in gnx.adj for node in present),
            lambda: sum(node in gfx.adj for node in present),
        ),
        (
            "n in MDG.succ x512 [nx/fnx]",
            lambda: sum(node in gnx.succ for node in present),
            lambda: sum(node in gfx.succ for node in present),
        ),
        (
            "n in MDG.pred x512 [nx/fnx]",
            lambda: sum(node in gnx.pred for node in present),
            lambda: sum(node in gfx.pred for node in present),
        ),
        (
            "len(MDG.adj) x500 [nx/fnx]",
            lambda: [len(gnx.adj) for _ in repeats],
            lambda: [len(gfx.adj) for _ in repeats],
        ),
        (
            "len(MDG.succ) x500 [nx/fnx]",
            lambda: [len(gnx.succ) for _ in repeats],
            lambda: [len(gfx.succ) for _ in repeats],
        ),
        (
            "len(MDG.pred) x500 [nx/fnx]",
            lambda: [len(gnx.pred) for _ in repeats],
            lambda: [len(gfx.pred) for _ in repeats],
        ),
    ]


def suite_node_primitives():
    """br-r37-c1-qmi5w: raw-descriptor and competitive primitive proof."""
    import franken_networkx as fnx

    gnx, gfx = _build_pair(2000, 8000, seed=7, weighted=False)
    present = [str(i) for i in range(512)]
    missing = [f"missing-{i}" for i in range(512)]

    wrapped_has_node = fnx._private_aware_has_node(
        fnx._GRAPH_PRIVATE_AWARE_HAS_NODE
    ).__get__(gfx, type(gfx))
    wrapped_number_of_nodes = fnx._private_aware_number_of_nodes(
        fnx._GRAPH_PRIVATE_AWARE_NUMBER_OF_NODES
    ).__get__(gfx, type(gfx))

    return [
        (
            "G.has_node(present) x512 [nx/fnx]",
            lambda: sum(gnx.has_node(node) for node in present),
            lambda: sum(gfx.has_node(node) for node in present),
        ),
        (
            "G.has_node(missing) x512 [nx/fnx]",
            lambda: sum(gnx.has_node(node) for node in missing),
            lambda: sum(gfx.has_node(node) for node in missing),
        ),
        (
            "G.has_node(present) x512 [wrapper/raw]",
            lambda: sum(wrapped_has_node(node) for node in present),
            lambda: sum(gfx.has_node(node) for node in present),
        ),
        (
            "G.number_of_nodes() x512 [nx/fnx]",
            lambda: sum(gnx.number_of_nodes() for _ in present),
            lambda: sum(gfx.number_of_nodes() for _ in present),
        ),
        (
            "G.number_of_nodes() x512 [wrapper/raw]",
            lambda: sum(wrapped_number_of_nodes() for _ in present),
            lambda: sum(gfx.number_of_nodes() for _ in present),
        ),
        (
            "G.order() x512 [nx/fnx]",
            lambda: sum(gnx.order() for _ in present),
            lambda: sum(gfx.order() for _ in present),
        ),
    ]


def suite_edge_primitives():
    """br-r37-c1-6q4wl: raw has_edge descriptors and public residuals."""
    import networkx as nx
    import franken_networkx as fnx

    probes = [(str(i), str(i + 1)) for i in range(512)]
    rows = []
    classes = (
        (nx.Graph, fnx.Graph, fnx._GRAPH_PRIVATE_AWARE_HAS_EDGE),
        (nx.DiGraph, fnx.DiGraph, fnx._DIGRAPH_PRIVATE_AWARE_HAS_EDGE),
        (nx.MultiGraph, fnx.MultiGraph, fnx._MULTIGRAPH_PRIVATE_AWARE_HAS_EDGE),
        (
            nx.MultiDiGraph,
            fnx.MultiDiGraph,
            fnx._MULTIDIGRAPH_PRIVATE_AWARE_HAS_EDGE,
        ),
    )
    for nx_cls, fnx_cls, raw_descriptor in classes:
        gnx, gfx = nx_cls(), fnx_cls()
        nodes = [str(i) for i in range(2000)]
        edges = [(str(i), str(i + 1)) for i in range(1999)]
        gnx.add_nodes_from(nodes)
        gfx.add_nodes_from(nodes)
        gnx.add_edges_from(edges)
        gfx.add_edges_from(edges)
        raw = raw_descriptor.__get__(gfx, fnx_cls)

        if fnx_cls is fnx.MultiGraph:
            uncached = gfx._native_has_edge_uncached_string_control

            def uncached_string_batch(
                probes=probes,
                call=uncached,
            ):
                return sum(call(u, v) for u, v in probes)

            def cached_string_batch(
                probes=probes,
                graph=gfx,
            ):
                return sum(graph.has_edge(u, v) for u, v in probes)

            assert uncached_string_batch() == cached_string_batch()
            # Populate the mutation-tokened candidate cache outside timing.
            cached_string_batch()
            rows.append(
                (
                    "MultiGraph.has_edge exact-string x512 "
                    "[canonical/index-cache]",
                    uncached_string_batch,
                    cached_string_batch,
                )
            )

        def conservative_control(u, v, *, graph=gfx, raw_call=raw):
            # The former wrapper also hash-checked u/v in Python. The candidate
            # raw descriptor now performs those checks itself, so retaining
            # them here would double-charge the control. Measure only the
            # wrapper frame + private-storage probe before the same raw call:
            # this is strictly cheaper than the true old path and therefore a
            # conservative mechanism gate.
            if fnx._has_networkx_private_storage(graph):
                raise AssertionError("ordinary benchmark graph gained private storage")
            return raw_call(u, v)

        rows.extend(
            [
                (
                    f"{fnx_cls.__name__}.has_edge x512 [conservative-wrapper/raw]",
                    lambda probes=probes, call=conservative_control: sum(
                        call(u, v) for u, v in probes
                    ),
                    lambda probes=probes, graph=gfx: sum(
                        graph.has_edge(u, v) for u, v in probes
                    ),
                ),
                (
                    f"{fnx_cls.__name__}.has_edge x512 [nx/fnx]",
                    lambda probes=probes, graph=gnx: sum(
                        graph.has_edge(u, v) for u, v in probes
                    ),
                    lambda probes=probes, graph=gfx: sum(
                        graph.has_edge(u, v) for u, v in probes
                    ),
                ),
            ]
        )
    return rows


def suite_edge_data_primitives():
    """br-r37-c1-57ba1: raw get_edge_data descriptors and public residuals."""
    import networkx as nx
    import franken_networkx as fnx

    probes = [(str(i), str(i + 1)) for i in range(512)]
    rows = []
    classes = (
        (nx.Graph, fnx.Graph, fnx._GRAPH_PRIVATE_AWARE_GET_EDGE_DATA),
        (nx.DiGraph, fnx.DiGraph, fnx._DIGRAPH_PRIVATE_AWARE_GET_EDGE_DATA),
        (
            nx.MultiGraph,
            fnx.MultiGraph,
            fnx._MULTIGRAPH_PRIVATE_AWARE_GET_EDGE_DATA,
        ),
        (
            nx.MultiDiGraph,
            fnx.MultiDiGraph,
            fnx._MULTIDIGRAPH_PRIVATE_AWARE_GET_EDGE_DATA,
        ),
    )
    for nx_cls, fnx_cls, raw_descriptor in classes:
        gnx, gfx = nx_cls(), fnx_cls()
        nodes = [str(i) for i in range(2000)]
        edges = [
            (str(i), str(i + 1), {"weight": i})
            for i in range(1999)
        ]
        gnx.add_nodes_from(nodes)
        gfx.add_nodes_from(nodes)
        gnx.add_edges_from(edges)
        gfx.add_edges_from(edges)
        raw = raw_descriptor.__get__(gfx, fnx_cls)

        def conservative_control(u, v, *, graph=gfx, raw_call=raw):
            # As in the has_edge sibling, do not retain the former wrapper's
            # Python hash calls before a raw descriptor that now hashes for
            # itself. This measures only the wrapper/private-store chain and is
            # strictly cheaper than the true old path.
            if fnx._has_networkx_private_storage(graph):
                raise AssertionError("ordinary benchmark graph gained private storage")
            return raw_call(u, v)

        rows.extend(
            [
                (
                    f"{fnx_cls.__name__}.get_edge_data x512 "
                    "[conservative-wrapper/raw]",
                    lambda probes=probes, call=conservative_control: sum(
                        len(call(u, v)) for u, v in probes
                    ),
                    lambda probes=probes, graph=gfx: sum(
                        len(graph.get_edge_data(u, v)) for u, v in probes
                    ),
                ),
                (
                    f"{fnx_cls.__name__}.get_edge_data x512 [nx/fnx]",
                    lambda probes=probes, graph=gnx: sum(
                        len(graph.get_edge_data(u, v)) for u, v in probes
                    ),
                    lambda probes=probes, graph=gfx: sum(
                        len(graph.get_edge_data(u, v)) for u, v in probes
                    ),
                ),
            ]
        )
    return rows


def suite_multigraph_edge_data_admission():
    """A/A-only gate for the keyless multigraph live-keydict retry.

    The governing ``br-r37-c1-zfu6g`` retry predicate requires two consecutive
    invocations of this unchanged 512-call workload to produce doubled-log null
    floors below 1.02x before any source candidate may be built.  Both arms are
    deliberately the exact current public path: this suite establishes only
    measurement admission and makes no candidate-effect claim.
    """
    import franken_networkx as fnx

    repeats = range(512)
    rows = []
    for graph_class in (fnx.MultiGraph, fnx.MultiDiGraph):
        graph = graph_class()
        for key in range(8):
            graph.add_edge(
                "left",
                "right",
                key=key,
                weight=key,
                label=f"edge-{key}",
            )

        current = graph.get_edge_data("left", "right")
        assert type(current) is dict
        assert list(current) == list(range(8))
        assert current[3] is graph.get_edge_data("left", "right", key=3)

        def keyless_batch(graph=graph):
            return sum(
                len(graph.get_edge_data("left", "right"))
                for _ in repeats
            )

        rows.append(
            (
                f"{graph_class.__name__}.get_edge_data keyless x512 "
                "[public/public A/A admission]",
                keyless_batch,
                keyless_batch,
            )
        )

    # Match the preregistered screen: stabilize frequency for two seconds before
    # the first timed null while preserving the exact 512-call batch.
    warm_deadline = perf_counter() + 2.0
    while perf_counter() < warm_deadline:
        for _label, arm_a, arm_b in rows:
            arm_a()
            arm_b()
    return rows


def suite_multigraph_degree_scalar():
    """Profile screen for caching the raw base view in live multi DegreeViews."""
    import networkx as nx
    import franken_networkx as fnx

    nodes = [str(index) for index in range(2_000)]
    edges = [
        (str(index), str(index + 1), index % 3)
        for index in range(1_999)
    ]
    probes = nodes[:512]
    rows = []
    classes = (
        (
            nx.MultiGraph,
            fnx.MultiGraph,
            fnx._MULTIGRAPH_DEGREE_DESCRIPTOR,
        ),
        (
            nx.MultiDiGraph,
            fnx.MultiDiGraph,
            fnx._MULTIDIGRAPH_DEGREE_DESCRIPTOR,
        ),
    )
    for nx_class, fnx_class, raw_descriptor in classes:
        nx_graph, fnx_graph = nx_class(), fnx_class()
        nx_graph.add_nodes_from(nodes)
        fnx_graph.add_nodes_from(nodes)
        nx_graph.add_edges_from(edges)
        fnx_graph.add_edges_from(edges)
        nx_view = nx_graph.degree
        current_view = fnx_graph.degree
        cached_base = raw_descriptor.__get__(fnx_graph, fnx_class)

        def current_batch(view=current_view):
            return sum(view[node] for node in probes)

        def cached_base_batch(view=cached_base):
            total = 0
            for node in probes:
                # Retain the public wrapper's eager unhashable-node contract.
                hash(node)
                total += view[node]
            return total

        def incumbent_batch(view=nx_view):
            return sum(view[node] for node in probes)

        assert incumbent_batch() == current_batch() == cached_base_batch()
        label = fnx_class.__name__
        rows.extend(
            [
                (
                    f"{label}.degree[n] x512 [current/cached-base prototype]",
                    current_batch,
                    cached_base_batch,
                ),
                (
                    f"{label}.degree[n] x512 [nx/cached-base prototype]",
                    incumbent_batch,
                    cached_base_batch,
                ),
                (
                    f"{label}.degree[n] x512 [nx/current]",
                    incumbent_batch,
                    current_batch,
                ),
            ]
        )
    return rows


def suite_simple_edge_getitem():
    """br-r37-c1-sivs2: bypass simple EdgeView mapping-wrapper chains."""
    import franken_networkx as fnx

    rows = []
    for directed, label in ((False, "Graph"), (True, "DiGraph")):
        gnx, gfx = _build_pair(
            2000,
            8000,
            seed=7,
            weighted=True,
            directed=directed,
        )
        probes = list(gnx.edges)[:512]
        fnx_view = gfx.edges
        nx_view = gnx.edges

        if directed:
            def old_lookup(edge, *, graph=gfx):
                u, v = edge
                if not graph.has_edge(u, v):
                    raise KeyError(f"The edge {edge} is not in the graph.")
                return graph.succ[u][v]
        else:
            def old_lookup(edge, *, view=fnx_view):
                u, v = edge
                hash(u)
                hash(v)
                owner = fnx._EDGE_VIEW_GRAPH_OWNER.get(id(view))
                if owner is None:
                    raise AssertionError("exact Graph EdgeView lost its owner")
                return owner.adj[u][v]

        def old_batch(*, call=old_lookup, edges=probes):
            return [call(edge) for edge in edges]

        def candidate_batch(*, view=fnx_view, edges=probes):
            return [view[edge] for edge in edges]

        def networkx_batch(*, view=nx_view, edges=probes):
            return [view[edge] for edge in edges]

        rows.extend(
            [
                (
                    f"{label}.edges[u,v] x512 [view-chain/native]",
                    old_batch,
                    candidate_batch,
                ),
                (
                    f"{label}.edges[u,v] x512 [nx/fnx]",
                    networkx_batch,
                    candidate_batch,
                ),
            ]
        )
    return rows


def suite_nodeview_contains():
    """br-r37-c1-m7xek: move Graph NodeView's hash guard into its C slot."""
    gnx, gfx = _build_pair(2048, 8192, seed=7, weighted=True)
    nx_view = gnx.nodes
    fnx_view = gfx.nodes
    raw_contains = type(fnx_view).__dict__["__contains__"]
    present = "1024"
    missing = "not-present"

    def old_batch(item, *, view=fnx_view, raw=raw_contains):
        # The native candidate now performs the one mandatory hash itself.
        # Retain only the former Python delegate frame here; calling hash()
        # again would charge the control twice for work the old path did once.
        total = 0
        for _ in range(512):
            total += raw(view, item)
        return total

    def candidate_batch(item, *, view=fnx_view):
        return sum(item in view for _ in range(512))

    def networkx_batch(item, *, view=nx_view):
        return sum(item in view for _ in range(512))

    return [
        (
            "Graph NodeView contains present x512 [wrapper/native]",
            lambda: old_batch(present),
            lambda: candidate_batch(present),
        ),
        (
            "Graph NodeView contains present x512 [nx/fnx]",
            lambda: networkx_batch(present),
            lambda: candidate_batch(present),
        ),
        (
            "Graph NodeView contains missing x512 [wrapper/native]",
            lambda: old_batch(missing),
            lambda: candidate_batch(missing),
        ),
        (
            "Graph NodeView contains missing x512 [nx/fnx]",
            lambda: networkx_batch(missing),
            lambda: candidate_batch(missing),
        ),
    ]


def suite_multi_neighbor_keydict():
    """br-r37-c1-zrsuc: cache lazy multigraph neighbor-key returns."""
    import networkx as nx
    import franken_networkx as fnx

    nodes = [str(i) for i in range(2000)]
    mg_edges = [
        ("0", str(i)) for i in range(1, 65)
    ] + [
        (str(i), str(i + 1)) for i in range(65, 1999)
    ]
    mdg_edges = (
        [("0", str(i)) for i in range(1, 65)]
        + [(str(i), "0") for i in range(65, 129)]
        + [(str(i), str(i + 1)) for i in range(129, 1999)]
    )
    mg_nx, mg_fx = nx.MultiGraph(), fnx.MultiGraph()
    mdg_nx, mdg_fx = nx.MultiDiGraph(), fnx.MultiDiGraph()
    for graph in (mg_nx, mg_fx):
        graph.add_nodes_from(nodes)
        graph.add_edges_from(mg_edges)
    for graph in (mdg_nx, mdg_fx):
        graph.add_nodes_from(nodes)
        graph.add_edges_from(mdg_edges)

    rebuild_mg = fnx._MULTIGRAPH_PRIVATE_AWARE_NEIGHBORS.__get__(
        mg_fx, fnx.MultiGraph
    )
    rebuild_succ = fnx._MULTIDIGRAPH_PRIVATE_AWARE_SUCCESSORS.__get__(
        mdg_fx, fnx.MultiDiGraph
    )
    rebuild_pred = fnx._MULTIDIGRAPH_PRIVATE_AWARE_PREDECESSORS.__get__(
        mdg_fx, fnx.MultiDiGraph
    )
    # Populate the candidate cache before every timed region.
    list(mg_fx.neighbors("0"))
    list(mdg_fx.successors("0"))
    list(mdg_fx.predecessors("0"))
    repeats = range(512)

    def calls(call):
        return [call("0") for _ in repeats]

    return [
        (
            "MG.neighbors x512 [rebuild/cached-keydict]",
            lambda: calls(rebuild_mg),
            lambda: calls(mg_fx.neighbors),
        ),
        (
            "MG.neighbors x512 [nx/fnx]",
            lambda: calls(mg_nx.neighbors),
            lambda: calls(mg_fx.neighbors),
        ),
        (
            "MDG.successors x512 [rebuild/cached-keydict]",
            lambda: calls(rebuild_succ),
            lambda: calls(mdg_fx.successors),
        ),
        (
            "MDG.successors x512 [nx/fnx]",
            lambda: calls(mdg_nx.successors),
            lambda: calls(mdg_fx.successors),
        ),
        (
            "MDG.predecessors x512 [rebuild/cached-keydict]",
            lambda: calls(rebuild_pred),
            lambda: calls(mdg_fx.predecessors),
        ),
        (
            "MDG.predecessors x512 [nx/fnx]",
            lambda: calls(mdg_nx.predecessors),
            lambda: calls(mdg_fx.predecessors),
        ),
    ]


def suite_nodeview_getitem():
    """br-r37-c1-yere4: intern warm public keys in each live NodeView."""
    gnx, gfx = _build_pair(2000, 8000, seed=7, weighted=True)
    nx_view = gnx.nodes
    fnx_view = gfx.nodes
    raw_getitem = type(fnx_view).__getitem__
    nodes = [str(i) for i in range(512)]

    def canonical_lookup():
        # ``get`` retains the former native canonical-string path for present
        # nodes, making it a conservative control: the removed Python
        # hash/try-except wrapper is not charged to this arm.
        return [fnx_view.get(node) for node in nodes]

    def interned_lookup():
        return [raw_getitem(fnx_view, node) for node in nodes]

    # Stabilize worker frequency before the first A/A round. This is benchmark
    # setup, outside every timed region, and warms both control and candidate.
    warm_deadline = perf_counter() + 2.0
    while perf_counter() < warm_deadline:
        canonical_lookup()
        interned_lookup()

    return [
        (
            "NodeView.__getitem__ x512 [canonical/interned]",
            canonical_lookup,
            interned_lookup,
        ),
        (
            "G.nodes[n] x512 [nx/fnx]",
            lambda: [gnx.nodes[node] for node in nodes],
            lambda: [gfx.nodes[node] for node in nodes],
        ),
        (
            "sum(G.nodes[n]['weight']) x512 [nx/fnx]",
            lambda: sum(gnx.nodes[node].get("weight", 0) for node in nodes),
            lambda: sum(gfx.nodes[node].get("weight", 0) for node in nodes),
        ),
    ]


def suite_digraph_neighbor_descriptors():
    """br-r37-c1-heyxu: directed successor calls use raw live-row descriptors."""
    import networkx as nx
    import franken_networkx as fnx

    neighbors = tuple(f"n{index}" for index in range(64))
    dnx, dfx = nx.DiGraph(), fnx.DiGraph()
    dnx.add_edges_from(("hub", node) for node in neighbors)
    dfx.add_edges_from(("hub", node) for node in neighbors)
    dnx.add_edges_from((node, "sink") for node in neighbors)
    dfx.add_edges_from((node, "sink") for node in neighbors)

    old_successors = fnx._private_aware_digraph_successors().__get__(
        dfx, fnx.DiGraph
    )

    def batch(call, node):
        last = None
        for _ in range(512):
            last = call(node)
        return type(last).__name__, list(last)

    controls = ((old_successors, dfx.successors, "hub"),)
    warm_deadline = perf_counter() + 2.0
    while perf_counter() < warm_deadline:
        for old, raw, node in controls:
            batch(old, node)
            batch(raw, node)

    return [
        (
            "DiGraph.successors x512 [wrapper/raw]",
            lambda: batch(old_successors, "hub"),
            lambda: batch(dfx.successors, "hub"),
        ),
        (
            "DiGraph.successors x512 [nx/fnx]",
            lambda: batch(dnx.successors, "hub"),
            lambda: batch(dfx.successors, "hub"),
        ),
    ]


def suite_lazy_rows():
    """br-r37-c1-v9auw: live row-mirror materialization and counted mechanism."""
    import networkx as nx
    import franken_networkx as fnx

    undirected_edges = [(0, node, {"weight": node}) for node in range(1, 65)]
    gnx = nx.Graph()
    gfx = fnx.Graph()
    gnx.add_edges_from((u, v, dict(attrs)) for u, v, attrs in undirected_edges)
    gfx.add_edges_from((u, v, dict(attrs)) for u, v, attrs in undirected_edges)

    directed_edges = [
        (0, node, {"weight": node}) for node in range(1, 65)
    ] + [
        (node, 0, {"weight": -node}) for node in range(65, 129)
    ]
    dnx = nx.DiGraph()
    dfx = fnx.DiGraph()
    dnx.add_edges_from((u, v, dict(attrs)) for u, v, attrs in directed_edges)
    dfx.add_edges_from((u, v, dict(attrs)) for u, v, attrs in directed_edges)

    nx_row = gnx[0]
    fnx_row = gfx[0]
    nx_succ = dnx.succ[0]
    fnx_succ = dfx.succ[0]
    nx_pred = dnx.pred[0]
    fnx_pred = dfx.pred[0]

    # Materialize each persistent mirror before timing so both mechanism arms
    # measure the steady-state most-used call, not one-time observation cost.
    dict(fnx_row)
    dict(fnx_succ)
    dict(fnx_pred)

    nodes = tuple(fnx_row)
    live = fnx_row._fnx_live_keydict
    baseline_revision = (gfx.nodes_seq, gfx.edges_seq)

    def token_checked_copy():
        # Exact counted mechanism removed by the lever: the old __getitem__
        # fetched both counters and compared this tuple for every neighbor.
        return {
            node: live[node]
            if baseline_revision == (gfx.nodes_seq, gfx.edges_seq)
            else fnx_row[node]
            for node in nodes
        }

    def live_mirror_copy():
        return {node: live[node] for node in nodes}

    return [
        (
            "dict(G[u]) degree=64 [nx/fnx]",
            lambda: dict(nx_row),
            lambda: dict(fnx_row),
        ),
        (
            "list(G[u].keys()) degree=64 [nx/fnx]",
            lambda: list(nx_row.keys()),
            lambda: list(fnx_row.keys()),
        ),
        (
            "dict(DG.succ[u]) degree=64 [nx/fnx]",
            lambda: dict(nx_succ),
            lambda: dict(fnx_succ),
        ),
        (
            "dict(DG.pred[u]) degree=64 [nx/fnx]",
            lambda: dict(nx_pred),
            lambda: dict(fnx_pred),
        ),
        (
            "row-copy loop degree=64 [token/live]",
            token_checked_copy,
            live_mirror_copy,
        ),
    ]


def suite_constant_predicates():
    """br-r37-c1-8a89c: class-safe wrappers become cached raw instance methods."""
    import franken_networkx as fnx
    import networkx as nx

    repeats = range(512)
    graph_classes = (
        ("Graph", nx.Graph, fnx.Graph),
        ("DiGraph", nx.DiGraph, fnx.DiGraph),
        ("MultiGraph", nx.MultiGraph, fnx.MultiGraph),
        ("MultiDiGraph", nx.MultiDiGraph, fnx.MultiDiGraph),
    )
    rows = []
    for class_name, nx_class, fnx_class in graph_classes:
        nx_graph = nx_class()
        fnx_graph = fnx_class()
        for predicate_name in ("is_directed", "is_multigraph"):
            descriptor = fnx_class.__dict__[predicate_name]
            wrapper = descriptor._class_callable
            nx_bound = getattr(nx_graph, predicate_name)
            fnx_bound = getattr(fnx_graph, predicate_name)
            expected = nx_bound()
            assert wrapper(fnx_graph) is expected
            assert fnx_bound() is expected
            assert vars(fnx_graph)[predicate_name].__self__ is fnx_graph

            def wrapper_batch(
                wrapper=wrapper,
                graph=fnx_graph,
                repeats=repeats,
            ):
                return sum(wrapper(graph) for _ in repeats)

            def raw_batch(bound=fnx_bound, repeats=repeats):
                return sum(bound() for _ in repeats)

            def networkx_batch(bound=nx_bound, repeats=repeats):
                return sum(bound() for _ in repeats)

            rows.extend(
                (
                    (
                        f"{class_name}.{predicate_name} x512 [wrapper/raw-cached]",
                        wrapper_batch,
                        raw_batch,
                    ),
                    (
                        f"{class_name}.{predicate_name} x512 [nx/fnx]",
                        networkx_batch,
                        raw_batch,
                    ),
                )
            )
    return rows


def suite_digraph_string_attr_construction():
    """br-r37-c1-cu8me: exact-string fresh attributed DiGraph batch."""
    import networkx as nx
    import franken_networkx as fnx

    edge_count = 8_000
    nx_rows = [
        (f"node-{source}", f"node-{source + 1}", {"weight": source})
        for source in range(edge_count)
    ]
    fnx_rows = [
        (f"node-{source}", f"node-{source + 1}", {"weight": source})
        for source in range(edge_count)
    ]

    def build_nx():
        graph = nx.DiGraph(nx_rows)
        assert graph.number_of_nodes() == edge_count + 1
        assert graph.number_of_edges() == edge_count
        return graph

    def build_fnx():
        graph = fnx.DiGraph(fnx_rows)
        assert graph.number_of_nodes() == edge_count + 1
        assert graph.number_of_edges() == edge_count
        return graph

    return [
        (
            "DiGraph(list[str,str,{weight}]) e=8000 [nx/fnx]",
            build_nx,
            build_fnx,
        ),
    ]


def suite_multidigraph_string_attr_construction():
    """br-r37-c1-z9f09: exact-string fresh attributed MultiDiGraph batch."""
    import networkx as nx
    import franken_networkx as fnx

    edge_count = 8_000
    nx_rows = [
        (f"node-{source}", f"node-{source + 1}", {"weight": float(source)})
        for source in range(edge_count)
    ]
    fnx_rows = [
        (f"node-{source}", f"node-{source + 1}", {"weight": float(source)})
        for source in range(edge_count)
    ]

    def build_nx():
        graph = nx.MultiDiGraph(nx_rows)
        assert graph.number_of_nodes() == edge_count + 1
        assert graph.number_of_edges() == edge_count
        assert graph["node-17"]["node-18"][0]["weight"] == 17.0
        return graph

    def build_fnx():
        graph = fnx.MultiDiGraph(fnx_rows)
        assert graph.number_of_nodes() == edge_count + 1
        assert graph.number_of_edges() == edge_count
        assert graph["node-17"]["node-18"][0]["weight"] == 17.0
        return graph

    return [
        (
            "MultiDiGraph(list[str,str,{weight}]) e=8000 [nx/fnx]",
            build_nx,
            build_fnx,
        ),
    ]


def suite_multigraph_compose():
    """Re-admit attributed multigraph compose after the stable-slot cutover.

    The governing 2026-06-21 negative-evidence row permits a retry only after
    the multigraph attribute substrate changes.  Each factor has 12,600 keyed
    edges; 6,300 overlap with H updating G, yielding the historical 18,900-edge
    result shape.  String nodes, explicit string keys, graph attrs, node attrs,
    and partially overlapping edge attrs exercise the observable merge contract.
    """
    import networkx as nx
    import franken_networkx as fnx

    node_count = 420
    factor_edges = 12_600
    overlap_edges = 6_300
    result_edges = factor_edges * 2 - overlap_edges
    nodes = [f"node-{index}" for index in range(node_count)]

    def edge_stream(directed):
        pairs = []
        for source in range(node_count):
            targets = range(node_count) if directed else range(source + 1, node_count)
            for target in targets:
                if source != target:
                    pairs.append((nodes[source], nodes[target]))
                    if len(pairs) == result_edges:
                        return pairs
        raise AssertionError("fixture does not contain enough unique pairs")

    def factors(graph_class, directed):
        pairs = edge_stream(directed)
        graph_g = graph_class()
        graph_h = graph_class()
        graph_g.graph.update({"owner": "G", "shared": "G"})
        graph_h.graph.update({"owner_h": "H", "shared": "H"})
        graph_g.add_nodes_from(
            (node, {"source": "G", "rank": index}) for index, node in enumerate(nodes)
        )
        graph_h.add_nodes_from(
            (node, {"source": "H", "color": index % 7}) for index, node in enumerate(nodes)
        )
        graph_g.add_edges_from(
            (
                u,
                v,
                f"key-{index % 3}",
                {"g": index, "shared": f"G-{index}", "payload": f"g-{index % 11}"},
            )
            for index, (u, v) in enumerate(pairs[:factor_edges])
        )
        graph_h.add_edges_from(
            (
                u,
                v,
                f"key-{index % 3}",
                {"h": index, "shared": f"H-{index}", "payload_h": f"h-{index % 13}"},
            )
            for index, (u, v) in enumerate(
                pairs[factor_edges - overlap_edges : result_edges],
                start=factor_edges - overlap_edges,
            )
        )
        return graph_g, graph_h

    nx_mg = factors(nx.MultiGraph, directed=False)
    fnx_mg = factors(fnx.MultiGraph, directed=False)
    nx_mdg = factors(nx.MultiDiGraph, directed=True)
    fnx_mdg = factors(fnx.MultiDiGraph, directed=True)

    def snapshot(compose, pair):
        result = compose(*pair)
        assert result.number_of_nodes() == node_count
        assert result.number_of_edges() == result_edges
        return (
            dict(result.graph),
            list(result.nodes(data=True)),
            list(result.edges(keys=True, data=True)),
        )

    return [
        (
            "compose MultiGraph str attrs n=420 e=18900 [nx/fnx]",
            lambda: snapshot(nx.compose, nx_mg),
            lambda: snapshot(fnx.compose, fnx_mg),
        ),
        (
            "compose MultiDiGraph str attrs n=420 e=18900 [nx/fnx]",
            lambda: snapshot(nx.compose, nx_mdg),
            lambda: snapshot(fnx.compose, fnx_mdg),
        ),
    ]


def suite_marshaling():
    """Return-shape / materialization surface."""
    import networkx as nx
    import franken_networkx as fnx

    gnx, gfx = _build_pair(2000, 8000, seed=7, weighted=True)
    src = "0"
    return [
        ("bfs_tree", lambda: nx.bfs_tree(gnx, src), lambda: fnx.bfs_tree(gfx, src)),
        ("dfs_tree", lambda: nx.dfs_tree(gnx, src), lambda: fnx.dfs_tree(gfx, src)),
        ("single_source_shortest_path",
         lambda: nx.single_source_shortest_path(gnx, src),
         lambda: fnx.single_source_shortest_path(gfx, src)),
        ("to_dict_of_lists",
         lambda: nx.to_dict_of_lists(gnx), lambda: fnx.to_dict_of_lists(gfx)),
        ("node_link_data",
         lambda: nx.node_link_data(gnx), lambda: fnx.node_link_data(gfx)),
        ("adjacency()->list",
         lambda: list(gnx.adjacency()), lambda: list(gfx.adjacency())),
    ]


def suite_class1_scaling():
    """Scale exact-output native kernels against NetworkX's Python loops."""
    import networkx as nx
    import franken_networkx as fnx

    raw_sizes = os.environ.get("FNX_CLASS1_SIZES", "1000,5000,10000")
    try:
        sizes = tuple(int(part) for part in raw_sizes.split(","))
    except ValueError as error:
        raise ValueError("FNX_CLASS1_SIZES must be comma-separated integers") from error
    if not sizes or any(size < 2 for size in sizes):
        raise ValueError("FNX_CLASS1_SIZES must contain integers >= 2")

    rows = []
    for size in sizes:
        gnx, gfx = _build_pair(size, 4 * size, seed=91_840 + size, weighted=True)
        source = "0"
        distances = nx.single_source_dijkstra_path_length(
            gnx,
            source,
            weight="weight",
        )
        target = max(distances, key=distances.__getitem__)
        if nx.dijkstra_path(
            gnx, source, target, weight="weight"
        ) != fnx.dijkstra_path(gfx, source, target, weight="weight"):
            raise RuntimeError("weighted Dijkstra target-selection parity failed")
        rows.extend(
            [
                (
                    f"triangles n={size} m={4 * size}",
                    lambda graph=gnx: nx.triangles(graph),
                    lambda graph=gfx: fnx.triangles(graph),
                ),
                (
                    f"clustering n={size} m={4 * size}",
                    lambda graph=gnx: nx.clustering(graph),
                    lambda graph=gfx: fnx.clustering(graph),
                ),
                (
                    f"transitivity n={size} m={4 * size}",
                    lambda graph=gnx: nx.transitivity(graph),
                    lambda graph=gfx: fnx.transitivity(graph),
                ),
                (
                    f"core_number n={size} m={4 * size}",
                    lambda graph=gnx: nx.core_number(graph),
                    lambda graph=gfx: fnx.core_number(graph),
                ),
                (
                    f"connected_components n={size} m={4 * size}",
                    lambda graph=gnx: list(nx.connected_components(graph)),
                    lambda graph=gfx: list(fnx.connected_components(graph)),
                ),
                (
                    f"dijkstra_path n={size} m={4 * size}",
                    lambda graph=gnx, goal=target: nx.dijkstra_path(
                        graph,
                        source,
                        goal,
                        weight="weight",
                    ),
                    lambda graph=gfx, goal=target: fnx.dijkstra_path(
                        graph,
                        source,
                        goal,
                        weight="weight",
                    ),
                ),
            ]
        )
    return rows


def suite_class1_frontier():
    """Strictly revalidate pure-Python-loop incumbent families across scale."""
    import networkx as nx
    import franken_networkx as fnx

    raw_sizes = os.environ.get("FNX_CLASS1_SIZES", "1000,5000,10000")
    try:
        sizes = tuple(int(part) for part in raw_sizes.split(","))
    except ValueError as error:
        raise ValueError("FNX_CLASS1_SIZES must be comma-separated integers") from error
    if not sizes or any(size < 2 for size in sizes):
        raise ValueError("FNX_CLASS1_SIZES must contain integers >= 2")

    raw_edge_multipliers = os.environ.get("FNX_CLASS1_EDGE_MULTIPLIERS", "4")
    try:
        edge_multipliers = tuple(
            int(part)
            for part in raw_edge_multipliers.split(",")
        )
    except ValueError as error:
        raise ValueError(
            "FNX_CLASS1_EDGE_MULTIPLIERS must be comma-separated integers"
        ) from error
    if not edge_multipliers or any(multiplier < 1 for multiplier in edge_multipliers):
        raise ValueError("FNX_CLASS1_EDGE_MULTIPLIERS must contain integers >= 1")

    available_scale_jobs = (
        "rich_club_coefficient",
        "onion_layers",
        "square_clustering",
        "k_core",
        "enumerate_all_cliques",
    )
    requested_scale_jobs = os.environ.get("FNX_CLASS1_FRONTIER_JOBS")
    if requested_scale_jobs is None:
        scale_jobs = available_scale_jobs
    else:
        selected = {
            name.strip()
            for name in requested_scale_jobs.split(",")
            if name.strip()
        }
        unknown = selected - set(available_scale_jobs)
        if not selected or unknown:
            raise ValueError(
                "FNX_CLASS1_FRONTIER_JOBS must select known comma-separated jobs; "
                f"unknown={sorted(unknown)} known={list(available_scale_jobs)}"
            )
        scale_jobs = tuple(
            name
            for name in available_scale_jobs
            if name in selected
        )

    EXTRA_PROVENANCE["class1_sizes"] = list(sizes)
    EXTRA_PROVENANCE["class1_edge_multipliers"] = list(edge_multipliers)
    EXTRA_PROVENANCE["class1_frontier_jobs"] = list(scale_jobs)

    rows = []
    for edge_multiplier in edge_multipliers:
        for size in sizes:
            edge_count = edge_multiplier * size
            seed = (
                92_840 + size
                if edge_multiplier == 4
                else 9_284_000 + size + 1_000_000 * edge_multiplier
            )
            gnx, gfx = _build_pair(
                size,
                edge_count,
                seed=seed,
                weighted=False,
            )
            scale_rows = {
                "rich_club_coefficient": (
                    f"rich_club_coefficient n={size} m={edge_count}",
                    lambda graph=gnx: nx.rich_club_coefficient(
                        graph,
                        normalized=False,
                    ),
                    lambda graph=gfx: fnx.rich_club_coefficient(
                        graph,
                        normalized=False,
                    ),
                ),
                "onion_layers": (
                    f"onion_layers n={size} m={edge_count}",
                    lambda graph=gnx: nx.onion_layers(graph),
                    lambda graph=gfx: fnx.onion_layers(graph),
                ),
                "square_clustering": (
                    f"square_clustering n={size} m={edge_count}",
                    lambda graph=gnx: nx.square_clustering(graph),
                    lambda graph=gfx: fnx.square_clustering(graph),
                ),
                "k_core": (
                    f"k_core n={size} m={edge_count}",
                    lambda graph=gnx: nx.k_core(graph),
                    lambda graph=gfx: fnx.k_core(graph),
                ),
                "enumerate_all_cliques": (
                    f"enumerate_all_cliques n={size} m={edge_count}",
                    lambda graph=gnx: list(nx.enumerate_all_cliques(graph)),
                    lambda graph=gfx: list(fnx.enumerate_all_cliques(graph)),
                ),
            }
            rows.extend(scale_rows[name] for name in scale_jobs)

    if requested_scale_jobs is not None:
        return rows

    gnx, gfx = _build_pair(1_200, 6_000, seed=11, weighted=False)
    wnx, wfx = _build_pair(1_200, 6_000, seed=11, weighted=True)
    small_nx, small_fx = _build_pair(220, 900, seed=13, weighted=False)
    directed_nx, directed_fx = _build_pair(
        200,
        800,
        seed=13,
        weighted=False,
        directed=True,
    )
    pairs = [(str(index), str(index + 3)) for index in range(0, 600, 2)]
    rows.extend(
        [
            (
                "closeness_centrality n=220 m=900",
                lambda: nx.closeness_centrality(small_nx),
                lambda: fnx.closeness_centrality(small_fx),
            ),
            (
                "triadic_census n=200 m=800 directed",
                lambda: nx.triadic_census(directed_nx),
                lambda: fnx.triadic_census(directed_fx),
            ),
            (
                "node_connectivity n=220 m=900",
                lambda: nx.node_connectivity(small_nx),
                lambda: fnx.node_connectivity(small_fx),
            ),
            (
                "faster_could_be_isomorphic n=1200 m=6000",
                lambda: nx.faster_could_be_isomorphic(gnx, gnx),
                lambda: fnx.faster_could_be_isomorphic(gfx, gfx),
            ),
            (
                "dfs_postorder_nodes n=1200 m=6000",
                lambda: list(nx.dfs_postorder_nodes(gnx, "0")),
                lambda: list(fnx.dfs_postorder_nodes(gfx, "0")),
            ),
            (
                "minimum_spanning_tree n=1200 m=6000",
                lambda: nx.minimum_spanning_tree(wnx),
                lambda: fnx.minimum_spanning_tree(wfx),
            ),
            (
                "jaccard_coefficient n=1200 pairs=300",
                lambda: list(nx.jaccard_coefficient(gnx, pairs)),
                lambda: list(fnx.jaccard_coefficient(gfx, pairs)),
            ),
            (
                "label_propagation n=1200 m=6000",
                lambda: list(nx.community.label_propagation_communities(gnx)),
                lambda: list(fnx.community.label_propagation_communities(gfx)),
            ),
            (
                "transitive_closure n=200 m=800 directed",
                lambda: nx.transitive_closure(directed_nx),
                lambda: fnx.transitive_closure(directed_fx),
            ),
            (
                "preferential_attachment n=1200 pairs=300",
                lambda: list(nx.preferential_attachment(gnx, pairs)),
                lambda: list(fnx.preferential_attachment(gfx, pairs)),
            ),
        ]
    )
    return rows


def suite_claim_incumbent():
    """Convert published claims into permanent live-incumbent contract rows."""
    import networkx as nx
    import franken_networkx as fnx

    if nx.__version__ != "3.6.1":
        raise RuntimeError(
            "claim-incumbent requires live NetworkX 3.6.1; "
            f"loaded {nx.__version__} from {nx.__file__}"
        )

    available_jobs = (
        "all_pairs_dijkstra_path_length",
        "all_pairs_shortest_path",
        "all_pairs_shortest_path_length",
        "all_simple_edge_paths",
        "bidirectional_dijkstra",
        "dfs_successors",
        "edges_data_true",
        "erdos_renyi_graph",
        "graph_has_node",
        "k_corona",
        "k_crust",
        "kosaraju_strongly_connected_components",
        "label_propagation_communities",
        "minimum_branching",
        "pagerank",
        "partition_spanning_tree",
        "read_gml",
        "read_graph6",
        "read_multiline_adjlist",
        "read_sparse6",
        "shortest_path_weighted",
        "single_pair_shortest_path",
        "single_source_shortest_path_length",
        "subgraph_view_edges",
        "to_scipy_sparse_array",
    )
    requested_jobs = os.environ.get(
        "FNX_CLAIM_INCUMBENT_JOBS",
        ",".join(available_jobs),
    )
    selected = {
        name.strip()
        for name in requested_jobs.split(",")
        if name.strip()
    }
    unknown = selected - set(available_jobs)
    if not selected or unknown:
        raise ValueError(
            "FNX_CLAIM_INCUMBENT_JOBS must select known comma-separated jobs; "
            f"unknown={sorted(unknown)} known={list(available_jobs)}"
        )

    jobs = tuple(name for name in available_jobs if name in selected)
    EXTRA_PROVENANCE["claim_incumbent_jobs"] = list(jobs)
    rows = []
    if "all_pairs_dijkstra_path_length" in jobs:
        if os.environ.get("PYTHONHASHSEED") != "0":
            raise RuntimeError(
                "the all_pairs_dijkstra_path_length claim fixture requires "
                "PYTHONHASHSEED=0 because nested mapping order is part of "
                "the public contract"
            )
        node_count = 300
        edge_count = 1_200
        seed = 11
        weight = "weight"
        expected_input_bytes = 57_598
        expected_input_sha256 = (
            "2108911c9c11fa2afdda9d5d010f21288f95bd012730d3810ee3c13fa46de2d6"
        )
        expected_outer_items = 300
        expected_inner_items = 90_000
        expected_output_bytes = 1_137_894
        expected_output_sha256 = (
            "de93300bb2abf14f69ef6ed4c3097799ef34f2c69c6272ea2457a426e53364ac"
        )
        all_pairs_dijkstra_nx, all_pairs_dijkstra_fnx = _build_pair(
            node_count,
            edge_count,
            seed=seed,
            weighted=True,
        )
        input_nx_bytes = canonical_bytes(all_pairs_dijkstra_nx)
        input_fnx_bytes = canonical_bytes(all_pairs_dijkstra_fnx)
        input_sha256 = hashlib.sha256(input_nx_bytes).hexdigest()
        if input_nx_bytes != input_fnx_bytes:
            raise RuntimeError(
                "all_pairs_dijkstra_path_length claim input graphs diverged"
            )
        if (
            len(input_nx_bytes) != expected_input_bytes
            or not hmac.compare_digest(input_sha256, expected_input_sha256)
        ):
            raise RuntimeError(
                "all_pairs_dijkstra_path_length claim input no longer "
                "matches its preregistered canonical byte count and SHA-256"
            )

        preflight_nx = {
            source: dict(lengths)
            for source, lengths in nx.all_pairs_dijkstra_path_length(
                all_pairs_dijkstra_nx,
                weight=weight,
            )
        }
        preflight_fnx = {
            source: dict(lengths)
            for source, lengths in fnx.all_pairs_dijkstra_path_length(
                all_pairs_dijkstra_fnx,
                weight=weight,
            )
        }
        preflight_nx_bytes = canonical_bytes(preflight_nx)
        preflight_fnx_bytes = canonical_bytes(preflight_fnx)
        output_sha256 = hashlib.sha256(preflight_nx_bytes).hexdigest()
        if preflight_nx_bytes != preflight_fnx_bytes:
            raise RuntimeError(
                "all_pairs_dijkstra_path_length claim complete ordered "
                "output diverged"
            )
        if (
            len(preflight_nx) != expected_outer_items
            or sum(map(len, preflight_nx.values())) != expected_inner_items
            or len(preflight_nx_bytes) != expected_output_bytes
            or not hmac.compare_digest(output_sha256, expected_output_sha256)
        ):
            raise RuntimeError(
                "all_pairs_dijkstra_path_length claim fixture no longer "
                "matches its preregistered complete ordered output"
            )
        EXTRA_PROVENANCE["claim_all_pairs_dijkstra_path_length_fixture"] = {
            "nodes": node_count,
            "edges": edge_count,
            "seed": seed,
            "weight": weight,
            "cutoff": None,
            "weight_range_inclusive": [1, 20],
            "python_hash_seed": 0,
            "input_canonical_bytes": expected_input_bytes,
            "input_sha256": expected_input_sha256,
            "outer_items": expected_outer_items,
            "inner_items": expected_inner_items,
            "output_canonical_bytes": expected_output_bytes,
            "complete_output_sha256": expected_output_sha256,
        }
        rows.append(
            (
                "claim/all_pairs_dijkstra_path_length "
                "n=300 m=1200 seed=11 weight=\"weight\" cutoff=None [nx/fnx]",
                lambda graph=all_pairs_dijkstra_nx, weight_name=weight: {
                    source: dict(lengths)
                    for source, lengths in nx.all_pairs_dijkstra_path_length(
                        graph,
                        weight=weight_name,
                    )
                },
                lambda graph=all_pairs_dijkstra_fnx, weight_name=weight: {
                    source: dict(lengths)
                    for source, lengths in fnx.all_pairs_dijkstra_path_length(
                        graph,
                        weight=weight_name,
                    )
                },
            )
        )
    if "all_pairs_shortest_path_length" in jobs:
        if os.environ.get("PYTHONHASHSEED") != "0":
            raise RuntimeError(
                "the all_pairs_shortest_path_length claim fixture requires "
                "PYTHONHASHSEED=0 because nested mapping order is part of "
                "the public contract"
            )
        node_count = 300
        edge_count = 1_200
        seed = 11
        expected_input_bytes = 38_940
        expected_input_sha256 = (
            "2daafd467b5e6398ec112e760ee67e0dcb66fe02af6eb87816b2efd8f5fbc8a6"
        )
        expected_outer_items = 300
        expected_inner_items = 90_000
        expected_output_bytes = 1_053_200
        expected_output_sha256 = (
            "a8752cbe5fe30288b7de8354511cd509392dd2fa95f1dbb0ba0d8c923e7d76e5"
        )
        all_pairs_nx, all_pairs_fnx = _build_pair(
            node_count,
            edge_count,
            seed=seed,
            weighted=False,
        )
        input_nx_bytes = canonical_bytes(all_pairs_nx)
        input_fnx_bytes = canonical_bytes(all_pairs_fnx)
        input_sha256 = hashlib.sha256(input_nx_bytes).hexdigest()
        if input_nx_bytes != input_fnx_bytes:
            raise RuntimeError(
                "all_pairs_shortest_path_length claim input graphs diverged"
            )
        if (
            len(input_nx_bytes) != expected_input_bytes
            or not hmac.compare_digest(input_sha256, expected_input_sha256)
        ):
            raise RuntimeError(
                "all_pairs_shortest_path_length claim input no longer "
                "matches its preregistered canonical byte count and SHA-256"
            )

        preflight_nx = {
            source: dict(lengths)
            for source, lengths in nx.all_pairs_shortest_path_length(
                all_pairs_nx
            )
        }
        preflight_fnx = {
            source: dict(lengths)
            for source, lengths in fnx.all_pairs_shortest_path_length(
                all_pairs_fnx
            )
        }
        preflight_nx_bytes = canonical_bytes(preflight_nx)
        preflight_fnx_bytes = canonical_bytes(preflight_fnx)
        output_sha256 = hashlib.sha256(preflight_nx_bytes).hexdigest()
        if preflight_nx_bytes != preflight_fnx_bytes:
            raise RuntimeError(
                "all_pairs_shortest_path_length claim complete ordered "
                "output diverged"
            )
        if (
            len(preflight_nx) != expected_outer_items
            or sum(map(len, preflight_nx.values())) != expected_inner_items
            or len(preflight_nx_bytes) != expected_output_bytes
            or not hmac.compare_digest(output_sha256, expected_output_sha256)
        ):
            raise RuntimeError(
                "all_pairs_shortest_path_length claim fixture no longer "
                "matches its preregistered complete ordered output"
            )
        EXTRA_PROVENANCE["claim_all_pairs_shortest_path_length_fixture"] = {
            "nodes": node_count,
            "edges": edge_count,
            "seed": seed,
            "cutoff": None,
            "python_hash_seed": 0,
            "input_canonical_bytes": expected_input_bytes,
            "input_sha256": expected_input_sha256,
            "outer_items": expected_outer_items,
            "inner_items": expected_inner_items,
            "output_canonical_bytes": expected_output_bytes,
            "complete_output_sha256": expected_output_sha256,
        }
        rows.append(
            (
                "claim/all_pairs_shortest_path_length "
                "n=300 m=1200 seed=11 cutoff=None [nx/fnx]",
                lambda: {
                    source: dict(lengths)
                    for source, lengths in nx.all_pairs_shortest_path_length(
                        all_pairs_nx
                    )
                },
                lambda: {
                    source: dict(lengths)
                    for source, lengths in fnx.all_pairs_shortest_path_length(
                        all_pairs_fnx
                    )
                },
            )
        )
    if "all_pairs_shortest_path" in jobs:
        if os.environ.get("PYTHONHASHSEED") != "0":
            raise RuntimeError(
                "the all_pairs_shortest_path claim fixture requires "
                "PYTHONHASHSEED=0 because nested mapping and path order "
                "are part of the public contract"
            )
        node_count = 300
        edge_count = 1_200
        seed = 11
        expected_input_bytes = 38_940
        expected_input_sha256 = (
            "2daafd467b5e6398ec112e760ee67e0dcb66fe02af6eb87816b2efd8f5fbc8a6"
        )
        expected_outer_items = 300
        expected_inner_items = 90_000
        expected_total_path_nodes = 356_164
        expected_path_node_histogram = {
            1: 300,
            2: 2_400,
            3: 16_650,
            4: 52_420,
            5: 17_946,
            6: 284,
        }
        expected_output_bytes = 3_327_168
        expected_output_sha256 = (
            "8bdcf4bfa5352c827c87113147911d192ce9b3c3d1b2a8ec8370682d88043e5a"
        )
        all_paths_nx, all_paths_fnx = _build_pair(
            node_count,
            edge_count,
            seed=seed,
            weighted=False,
        )
        input_nx_bytes = canonical_bytes(all_paths_nx)
        input_fnx_bytes = canonical_bytes(all_paths_fnx)
        input_sha256 = hashlib.sha256(input_nx_bytes).hexdigest()
        if input_nx_bytes != input_fnx_bytes:
            raise RuntimeError(
                "all_pairs_shortest_path claim input graphs diverged"
            )
        if (
            len(input_nx_bytes) != expected_input_bytes
            or not hmac.compare_digest(input_sha256, expected_input_sha256)
        ):
            raise RuntimeError(
                "all_pairs_shortest_path claim input no longer matches "
                "its preregistered canonical byte count and SHA-256"
            )

        preflight_nx = {
            source: dict(paths)
            for source, paths in nx.all_pairs_shortest_path(all_paths_nx)
        }
        preflight_fnx = {
            source: dict(paths)
            for source, paths in fnx.all_pairs_shortest_path(all_paths_fnx)
        }
        preflight_nx_bytes = canonical_bytes(preflight_nx)
        preflight_fnx_bytes = canonical_bytes(preflight_fnx)
        output_sha256 = hashlib.sha256(preflight_nx_bytes).hexdigest()
        path_node_histogram = {}
        total_path_nodes = 0
        for paths in preflight_nx.values():
            for path in paths.values():
                path_nodes = len(path)
                total_path_nodes += path_nodes
                path_node_histogram[path_nodes] = (
                    path_node_histogram.get(path_nodes, 0) + 1
                )
        if preflight_nx_bytes != preflight_fnx_bytes:
            raise RuntimeError(
                "all_pairs_shortest_path claim complete ordered nested "
                "path mapping diverged"
            )
        if (
            len(preflight_nx) != expected_outer_items
            or sum(map(len, preflight_nx.values())) != expected_inner_items
            or total_path_nodes != expected_total_path_nodes
            or path_node_histogram != expected_path_node_histogram
            or len(preflight_nx_bytes) != expected_output_bytes
            or not hmac.compare_digest(output_sha256, expected_output_sha256)
        ):
            raise RuntimeError(
                "all_pairs_shortest_path claim fixture no longer matches "
                "its preregistered complete ordered nested path mapping"
            )
        EXTRA_PROVENANCE["claim_all_pairs_shortest_path_fixture"] = {
            "publishing_commit": "87cf65e54a4e13a72a12c2bc7458655c7d4b3ac1",
            "recovered_harness_sha256": (
                "40e03ac078cff1d930e5e3fa8232688becf1c1a67ab1cda6da93b88109e47a0f"
            ),
            "recovered_result_sha256": (
                "eb2400d0a022d02325310ade2fb97beeff35f90ccc35170bd094f0492564a415"
            ),
            "nodes": node_count,
            "edges": edge_count,
            "seed": seed,
            "weighted": False,
            "directed": False,
            "cutoff": None,
            "parameters": "all omitted (NetworkX 3.6.1 defaults)",
            "python_hash_seed": 0,
            "input_canonical_bytes": expected_input_bytes,
            "input_sha256": expected_input_sha256,
            "outer_items": expected_outer_items,
            "inner_items": expected_inner_items,
            "total_path_nodes": expected_total_path_nodes,
            "path_node_histogram": expected_path_node_histogram,
            "output_canonical_bytes": expected_output_bytes,
            "complete_ordered_nested_output_sha256": expected_output_sha256,
        }
        rows.append(
            (
                "claim/all_pairs_shortest_path "
                "n=300 m=1200 seed=11 cutoff=None [nx/fnx]",
                lambda graph=all_paths_nx: {
                    source: dict(paths)
                    for source, paths in nx.all_pairs_shortest_path(graph)
                },
                lambda graph=all_paths_fnx: {
                    source: dict(paths)
                    for source, paths in fnx.all_pairs_shortest_path(graph)
                },
            )
        )
    if "all_simple_edge_paths" in jobs:
        if os.environ.get("PYTHONHASHSEED") != "0":
            raise RuntimeError(
                "the all_simple_edge_paths claim fixture requires "
                "PYTHONHASHSEED=0 because generator and edge order are "
                "part of the public contract"
            )
        node_count = 200
        edge_count = 800
        seed = 13
        source = "0"
        target = "5"
        cutoff = 4
        expected_input_bytes = 25_609
        expected_input_sha256 = (
            "c80713ae36d3b7ddc46899d9b4691edc1ccdfd6df61722ae0e03a246a65705cc"
        )
        expected_output_paths = 41
        expected_edge_occurrences = 156
        expected_path_edge_histogram = {3: 8, 4: 33}
        expected_output_bytes = 2_266
        expected_output_sha256 = (
            "e0fc4294e336f7edaef6bdb9900e8a48ebefabb28204801cab809d92df67ba86"
        )
        simple_paths_nx, simple_paths_fnx = _build_pair(
            node_count,
            edge_count,
            seed=seed,
            weighted=False,
        )
        input_nx_bytes = canonical_bytes(simple_paths_nx)
        input_fnx_bytes = canonical_bytes(simple_paths_fnx)
        input_sha256 = hashlib.sha256(input_nx_bytes).hexdigest()
        if input_nx_bytes != input_fnx_bytes:
            raise RuntimeError(
                "all_simple_edge_paths claim input graphs diverged"
            )
        if (
            len(input_nx_bytes) != expected_input_bytes
            or not hmac.compare_digest(input_sha256, expected_input_sha256)
        ):
            raise RuntimeError(
                "all_simple_edge_paths claim input no longer matches its "
                "preregistered canonical byte count and SHA-256"
            )

        preflight_nx = list(
            nx.all_simple_edge_paths(
                simple_paths_nx,
                source,
                target,
                cutoff=cutoff,
            )
        )
        preflight_fnx = list(
            fnx.all_simple_edge_paths(
                simple_paths_fnx,
                source,
                target,
                cutoff=cutoff,
            )
        )
        preflight_nx_bytes = canonical_bytes(preflight_nx)
        preflight_fnx_bytes = canonical_bytes(preflight_fnx)
        output_sha256 = hashlib.sha256(preflight_nx_bytes).hexdigest()
        path_edge_histogram = {}
        for path in preflight_nx:
            path_edges = len(path)
            path_edge_histogram[path_edges] = (
                path_edge_histogram.get(path_edges, 0) + 1
            )
        if preflight_nx_bytes != preflight_fnx_bytes:
            raise RuntimeError(
                "all_simple_edge_paths claim complete ordered generator "
                "output diverged"
            )
        if (
            len(preflight_nx) != expected_output_paths
            or sum(map(len, preflight_nx)) != expected_edge_occurrences
            or path_edge_histogram != expected_path_edge_histogram
            or len(preflight_nx_bytes) != expected_output_bytes
            or not hmac.compare_digest(output_sha256, expected_output_sha256)
        ):
            raise RuntimeError(
                "all_simple_edge_paths claim fixture no longer matches "
                "its preregistered complete ordered generator output"
            )
        EXTRA_PROVENANCE["claim_all_simple_edge_paths_fixture"] = {
            "publishing_commit": "87cf65e54a4e13a72a12c2bc7458655c7d4b3ac1",
            "recovered_harness_sha256": (
                "1114f244b93787b9e1d6a900633ccd93f3a09c91de8d669bde9ba75df5a611e3"
            ),
            "recovered_result_sha256": (
                "40040b7b90de11721263864fff0e3e79f260ca2779e16c8252784dc9236ef249"
            ),
            "recovered_builder_sha256": (
                "fb051cf48508ad56ee0c64103335090bd7866b12d65cb2e29d522cfa33b4cba1"
            ),
            "nodes": node_count,
            "edges": edge_count,
            "seed": seed,
            "weighted": False,
            "directed": False,
            "source": source,
            "target": target,
            "cutoff": cutoff,
            "parameters": (
                "source and target positional; cutoff=4; "
                "all remaining parameters omitted"
            ),
            "timed_projection": "len(list(result_generator))",
            "python_hash_seed": 0,
            "input_canonical_bytes": expected_input_bytes,
            "input_sha256": expected_input_sha256,
            "output_paths": expected_output_paths,
            "edge_occurrences": expected_edge_occurrences,
            "path_edge_histogram": expected_path_edge_histogram,
            "complete_generator_output_canonical_bytes": (
                expected_output_bytes
            ),
            "complete_ordered_generator_output_sha256": (
                expected_output_sha256
            ),
        }
        rows.append(
            (
                "claim/all_simple_edge_paths "
                "n=200 m=800 seed=13 source=\"0\" target=\"5\" "
                "cutoff=4 then=len(list) [nx/fnx]",
                lambda graph=simple_paths_nx, src=source, dst=target,
                limit=cutoff: len(
                    list(
                        nx.all_simple_edge_paths(
                            graph,
                            src,
                            dst,
                            cutoff=limit,
                        )
                    )
                ),
                lambda graph=simple_paths_fnx, src=source, dst=target,
                limit=cutoff: len(
                    list(
                        fnx.all_simple_edge_paths(
                            graph,
                            src,
                            dst,
                            cutoff=limit,
                        )
                    )
                ),
            )
        )
    if "bidirectional_dijkstra" in jobs:
        if os.environ.get("PYTHONHASHSEED") != "0":
            raise RuntimeError(
                "the bidirectional_dijkstra claim fixture requires "
                "PYTHONHASHSEED=0 because the selected equal-cost path is "
                "part of the public contract"
            )
        node_count = 2_000
        edge_count = 8_000
        seed = 7
        source = "0"
        target = "1999"
        weight = "weight"
        expected_input_bytes = 398_318
        expected_input_sha256 = (
            "03c62edb3bc632ec6fedf20e7a7061e42688aa1d655e9128dbc4980c2af54de0"
        )
        expected_distance = 19
        expected_path = (
            "0",
            "1610",
            "1531",
            "1102",
            "184",
            "452",
            "1999",
        )
        expected_edge_weights = (4, 1, 4, 5, 3, 2)
        expected_output_bytes = 57
        expected_output_sha256 = (
            "84ecf9bc779cbb276688ce9745bb7637609808b51b7d7a4d8de03cead8532516"
        )
        bidirectional_nx, bidirectional_fnx = _build_pair(
            node_count,
            edge_count,
            seed=seed,
            weighted=True,
        )
        input_nx_bytes = canonical_bytes(bidirectional_nx)
        input_fnx_bytes = canonical_bytes(bidirectional_fnx)
        input_sha256 = hashlib.sha256(input_nx_bytes).hexdigest()
        if input_nx_bytes != input_fnx_bytes:
            raise RuntimeError(
                "bidirectional_dijkstra claim input graphs diverged"
            )
        if (
            len(input_nx_bytes) != expected_input_bytes
            or not hmac.compare_digest(input_sha256, expected_input_sha256)
        ):
            raise RuntimeError(
                "bidirectional_dijkstra claim input no longer matches its "
                "preregistered canonical byte count and SHA-256"
            )

        preflight_nx = nx.bidirectional_dijkstra(
            bidirectional_nx,
            source,
            target,
            weight=weight,
        )
        preflight_fnx = fnx.bidirectional_dijkstra(
            bidirectional_fnx,
            source,
            target,
            weight=weight,
        )
        preflight_nx_bytes = canonical_bytes(preflight_nx)
        preflight_fnx_bytes = canonical_bytes(preflight_fnx)
        output_sha256 = hashlib.sha256(preflight_nx_bytes).hexdigest()
        distance, path = preflight_nx
        edge_weights = tuple(
            bidirectional_nx[u][v][weight]
            for u, v in zip(path, path[1:])
        )
        if preflight_nx_bytes != preflight_fnx_bytes:
            raise RuntimeError(
                "bidirectional_dijkstra claim complete distance/path "
                "tuple diverged"
            )
        if (
            type(distance) is not int
            or distance != expected_distance
            or tuple(path) != expected_path
            or edge_weights != expected_edge_weights
            or sum(edge_weights) != distance
            or len(preflight_nx_bytes) != expected_output_bytes
            or not hmac.compare_digest(output_sha256, expected_output_sha256)
        ):
            raise RuntimeError(
                "bidirectional_dijkstra claim fixture no longer matches "
                "its preregistered complete distance/path result"
            )
        EXTRA_PROVENANCE["claim_bidirectional_dijkstra_fixture"] = {
            "publishing_commit": "87cf65e54a4e13a72a12c2bc7458655c7d4b3ac1",
            "recovered_harness_sha256": (
                "40e03ac078cff1d930e5e3fa8232688becf1c1a67ab1cda6da93b88109e47a0f"
            ),
            "recovered_result_sha256": (
                "eb2400d0a022d02325310ade2fb97beeff35f90ccc35170bd094f0492564a415"
            ),
            "nodes": node_count,
            "edges": edge_count,
            "seed": seed,
            "weighted": True,
            "directed": False,
            "source": source,
            "target": target,
            "weight": weight,
            "parameters": (
                "source and target positional; weight=\"weight\"; "
                "all remaining parameters omitted"
            ),
            "weight_range_inclusive": [1, 20],
            "python_hash_seed": 0,
            "input_canonical_bytes": expected_input_bytes,
            "input_sha256": expected_input_sha256,
            "distance": expected_distance,
            "distance_type": "int",
            "path": list(expected_path),
            "path_nodes": len(expected_path),
            "path_edges": len(expected_edge_weights),
            "path_edge_weights": list(expected_edge_weights),
            "output_canonical_bytes": expected_output_bytes,
            "complete_distance_path_sha256": expected_output_sha256,
        }
        rows.append(
            (
                "claim/bidirectional_dijkstra "
                "n=2000 m=8000 seed=7 source=\"0\" target=\"1999\" "
                "weight=\"weight\" [nx/fnx]",
                lambda graph=bidirectional_nx, src=source, dst=target,
                weight_name=weight: nx.bidirectional_dijkstra(
                    graph,
                    src,
                    dst,
                    weight=weight_name,
                ),
                lambda graph=bidirectional_fnx, src=source, dst=target,
                weight_name=weight: fnx.bidirectional_dijkstra(
                    graph,
                    src,
                    dst,
                    weight=weight_name,
                ),
            )
        )
    if "dfs_successors" in jobs:
        if os.environ.get("PYTHONHASHSEED") != "0":
            raise RuntimeError(
                "the dfs_successors claim fixture requires PYTHONHASHSEED=0 "
                "because parent-key and child-list order are part of the "
                "public contract"
            )
        node_count = 1_200
        edge_count = 6_000
        seed = 11
        source = "0"
        expected_input_bytes = 194_277
        expected_input_sha256 = (
            "199d564350ec6f70885e8f8236fad28d6620b44e3e7917a470f6fba73024e653"
        )
        expected_parent_items = 1_068
        expected_tree_edges = 1_198
        expected_reached_nodes = 1_199
        expected_unreached_nodes = ("135",)
        expected_output_bytes = 20_319
        expected_output_sha256 = (
            "cd00bea96de613a14e82b48cf29f3d7beedf2dac8e3b22102bfe4c875e01829b"
        )
        successors_nx, successors_fnx = _build_pair(
            node_count,
            edge_count,
            seed=seed,
            weighted=False,
        )
        input_nx_bytes = canonical_bytes(successors_nx)
        input_fnx_bytes = canonical_bytes(successors_fnx)
        input_sha256 = hashlib.sha256(input_nx_bytes).hexdigest()
        if input_nx_bytes != input_fnx_bytes:
            raise RuntimeError("dfs_successors claim input graphs diverged")
        if (
            len(input_nx_bytes) != expected_input_bytes
            or not hmac.compare_digest(input_sha256, expected_input_sha256)
        ):
            raise RuntimeError(
                "dfs_successors claim input no longer matches its "
                "preregistered canonical byte count and SHA-256"
            )

        preflight_nx = nx.dfs_successors(successors_nx, source)
        preflight_fnx = fnx.dfs_successors(successors_fnx, source)
        preflight_nx_bytes = canonical_bytes(preflight_nx)
        preflight_fnx_bytes = canonical_bytes(preflight_fnx)
        output_sha256 = hashlib.sha256(preflight_nx_bytes).hexdigest()
        reached_nodes = {source}
        reached_nodes.update(
            child
            for children in preflight_nx.values()
            for child in children
        )
        unreached_nodes = tuple(
            node for node in successors_nx if node not in reached_nodes
        )
        if preflight_nx_bytes != preflight_fnx_bytes:
            raise RuntimeError(
                "dfs_successors claim complete ordered mapping diverged"
            )
        if (
            len(preflight_nx) != expected_parent_items
            or sum(map(len, preflight_nx.values())) != expected_tree_edges
            or len(reached_nodes) != expected_reached_nodes
            or unreached_nodes != expected_unreached_nodes
            or len(preflight_nx_bytes) != expected_output_bytes
            or not hmac.compare_digest(output_sha256, expected_output_sha256)
        ):
            raise RuntimeError(
                "dfs_successors claim fixture no longer matches its "
                "preregistered complete ordered output"
            )
        EXTRA_PROVENANCE["claim_dfs_successors_fixture"] = {
            "publishing_commit": "87cf65e54a4e13a72a12c2bc7458655c7d4b3ac1",
            "recovered_harness_sha256": (
                "1114f244b93787b9e1d6a900633ccd93f3a09c91de8d669bde9ba75df5a611e3"
            ),
            "recovered_result_sha256": (
                "40040b7b90de11721263864fff0e3e79f260ca2779e16c8252784dc9236ef249"
            ),
            "recovered_builder_sha256": (
                "fb051cf48508ad56ee0c64103335090bd7866b12d65cb2e29d522cfa33b4cba1"
            ),
            "nodes": node_count,
            "edges": edge_count,
            "seed": seed,
            "weighted": False,
            "directed": False,
            "source": source,
            "depth_limit": None,
            "sort_neighbors": None,
            "parameters": "source positional; all remaining parameters omitted",
            "python_hash_seed": 0,
            "input_canonical_bytes": expected_input_bytes,
            "input_sha256": expected_input_sha256,
            "parent_items": expected_parent_items,
            "tree_edges": expected_tree_edges,
            "reached_nodes_including_source": expected_reached_nodes,
            "unreached_nodes": list(expected_unreached_nodes),
            "output_canonical_bytes": expected_output_bytes,
            "complete_ordered_output_sha256": expected_output_sha256,
        }
        rows.append(
            (
                "claim/dfs_successors "
                "n=1200 m=6000 seed=11 source=\"0\" "
                "depth_limit=None sort_neighbors=None [nx/fnx]",
                lambda graph=successors_nx, root=source: nx.dfs_successors(
                    graph,
                    root,
                ),
                lambda graph=successors_fnx, root=source: fnx.dfs_successors(
                    graph,
                    root,
                ),
            )
        )
    if "edges_data_true" in jobs:
        if os.environ.get("PYTHONHASHSEED") != "0":
            raise RuntimeError(
                "the edges(data=True) claim fixture requires "
                "PYTHONHASHSEED=0 because edge and attribute order are "
                "part of the public contract"
            )
        node_count = 2_000
        edge_count = 8_000
        seed = 7
        expected_input_bytes = 398_318
        expected_input_sha256 = (
            "03c62edb3bc632ec6fedf20e7a7061e42688aa1d655e9128dbc4980c2af54de0"
        )
        expected_output_items = 8_000
        expected_weight_sum = 83_411
        expected_weight_histogram = {
            1: 400,
            2: 416,
            3: 404,
            4: 395,
            5: 442,
            6: 360,
            7: 399,
            8: 443,
            9: 392,
            10: 385,
            11: 416,
            12: 395,
            13: 370,
            14: 399,
            15: 415,
            16: 380,
            17: 440,
            18: 389,
            19: 397,
            20: 363,
        }
        expected_output_bytes = 355_413
        expected_output_sha256 = (
            "fe91930c1b22fc69497a50bea3d7850dc6cc854f9388bf7675865b96349cbdc8"
        )
        edges_data_nx, edges_data_fnx = _build_pair(
            node_count,
            edge_count,
            seed=seed,
            weighted=True,
        )
        input_nx_bytes = canonical_bytes(edges_data_nx)
        input_fnx_bytes = canonical_bytes(edges_data_fnx)
        input_sha256 = hashlib.sha256(input_nx_bytes).hexdigest()
        if input_nx_bytes != input_fnx_bytes:
            raise RuntimeError(
                "edges(data=True) claim input graphs diverged"
            )
        if (
            len(input_nx_bytes) != expected_input_bytes
            or not hmac.compare_digest(input_sha256, expected_input_sha256)
        ):
            raise RuntimeError(
                "edges(data=True) claim input no longer matches its "
                "preregistered canonical byte count and SHA-256"
            )

        preflight_nx = list(edges_data_nx.edges(data=True))
        preflight_fnx = list(edges_data_fnx.edges(data=True))
        preflight_nx_bytes = canonical_bytes(preflight_nx)
        preflight_fnx_bytes = canonical_bytes(preflight_fnx)
        output_sha256 = hashlib.sha256(preflight_nx_bytes).hexdigest()
        weight_histogram = {}
        weight_sum = 0
        for _left, _right, attributes in preflight_nx:
            weight = attributes["weight"]
            weight_sum += weight
            weight_histogram[weight] = weight_histogram.get(weight, 0) + 1
        if preflight_nx_bytes != preflight_fnx_bytes:
            raise RuntimeError(
                "edges(data=True) claim complete ordered edge/attribute "
                "list diverged"
            )
        if (
            type(preflight_nx) is not list
            or any(
                type(edge) is not tuple
                or len(edge) != 3
                or type(edge[2]) is not dict
                for edge in preflight_nx
            )
            or len(preflight_nx) != expected_output_items
            or weight_sum != expected_weight_sum
            or weight_histogram != expected_weight_histogram
            or len(preflight_nx_bytes) != expected_output_bytes
            or not hmac.compare_digest(output_sha256, expected_output_sha256)
        ):
            raise RuntimeError(
                "edges(data=True) claim fixture no longer matches its "
                "preregistered complete ordered edge/attribute list"
            )
        EXTRA_PROVENANCE["claim_edges_data_true_fixture"] = {
            "publishing_commit": "87cf65e54a4e13a72a12c2bc7458655c7d4b3ac1",
            "recovered_harness_sha256": (
                "12613c60217d14798a75558b18230afba6282547e48e6d89caaf9cafd083cf07"
            ),
            "recovered_result_sha256": (
                "622b1c016891f709aad9fd545b41a08f51ca73f9b7be46393cf8415b4b11a1ed"
            ),
            "recovered_builder_sha256": (
                "40e03ac078cff1d930e5e3fa8232688becf1c1a67ab1cda6da93b88109e47a0f"
            ),
            "nodes": node_count,
            "edges": edge_count,
            "seed": seed,
            "weighted": True,
            "directed": False,
            "data": True,
            "default": None,
            "nbunch": None,
            "parameters": "data=True; all remaining parameters omitted",
            "weight_range_inclusive": [1, 20],
            "python_hash_seed": 0,
            "input_canonical_bytes": expected_input_bytes,
            "input_sha256": expected_input_sha256,
            "output_items": expected_output_items,
            "weight_sum": expected_weight_sum,
            "weight_histogram": expected_weight_histogram,
            "output_canonical_bytes": expected_output_bytes,
            "complete_ordered_output_sha256": expected_output_sha256,
        }
        rows.append(
            (
                "claim/edges(data=True)->list "
                "n=2000 m=8000 seed=7 weights=1..20 [nx/fnx]",
                lambda graph=edges_data_nx: list(
                    graph.edges(data=True)
                ),
                lambda graph=edges_data_fnx: list(
                    graph.edges(data=True)
                ),
            )
        )
    if "erdos_renyi_graph" in jobs:
        node_count = 1_500
        probability = 0.004
        seed = 5
        expected_edges = 4_508
        expected_output_sha256 = (
            "93fcf9aedb4b1f6dde8523bae73a673e92f3a50c2b958e4b37ee468002002e20"
        )
        preflight_nx = nx.erdos_renyi_graph(
            node_count,
            probability,
            seed=seed,
        )
        preflight_fnx = fnx.erdos_renyi_graph(
            node_count,
            probability,
            seed=seed,
        )
        preflight_nx_bytes = canonical_bytes(preflight_nx)
        preflight_fnx_bytes = canonical_bytes(preflight_fnx)
        if preflight_nx_bytes != preflight_fnx_bytes:
            raise RuntimeError(
                "erdos_renyi_graph claim fixture complete output diverged"
            )
        fixture_sha256 = hashlib.sha256(preflight_nx_bytes).hexdigest()
        if (
            preflight_nx.number_of_edges() != expected_edges
            or preflight_fnx.number_of_edges() != expected_edges
            or not hmac.compare_digest(fixture_sha256, expected_output_sha256)
        ):
            raise RuntimeError(
                "erdos_renyi_graph claim fixture no longer matches its "
                "preregistered edge count and output SHA-256"
            )
        EXTRA_PROVENANCE["claim_erdos_renyi_graph_fixture"] = {
            "nodes": node_count,
            "probability": probability,
            "seed": seed,
            "directed": False,
            "expected_edges": expected_edges,
            "complete_output_sha256": expected_output_sha256,
        }
        rows.append(
            (
                "claim/erdos_renyi_graph n=1500 p=0.004 seed=5 [nx/fnx]",
                lambda n=node_count, p=probability, s=seed: nx.erdos_renyi_graph(
                    n,
                    p,
                    seed=s,
                ),
                lambda n=node_count, p=probability, s=seed: fnx.erdos_renyi_graph(
                    n,
                    p,
                    seed=s,
                ),
            )
        )
    if "graph_has_node" in jobs:
        if os.environ.get("PYTHONHASHSEED") != "0":
            raise RuntimeError(
                "the G.has_node claim fixture requires PYTHONHASHSEED=0 "
                "because graph order is part of the public contract"
            )
        node_count = 2_000
        edge_count = 8_000
        seed = 7
        query_count = 512
        expected_input_bytes = 273_938
        expected_input_sha256 = (
            "03635cb95fcf023b79a245e0dc38125225ba216e6eb77a9270ef5121024f6164"
        )
        expected_present_keys_bytes = 3_474
        expected_present_keys_sha256 = (
            "6fbb25288e6fcf809d85064c41486f60b1c7c2361b486d6f7db7a1bd2fd09ea3"
        )
        expected_missing_keys_bytes = 7_570
        expected_missing_keys_sha256 = (
            "74c9abc0810cfa51f233b1b95679963dbf2e5f1825e72fe04c3b5de21f9e84ed"
        )
        expected_present_output_bytes = 3_072
        expected_present_output_sha256 = (
            "717355d2676c36a4dda6d9018d9e63347323e7d7d9931cc844973b68491f443f"
        )
        expected_missing_output_bytes = 3_584
        expected_missing_output_sha256 = (
            "772cc368dffbbc3ab66c244cc1da8c8d32f32ceb57c3eca2eae212bd450ba546"
        )
        has_node_nx, has_node_fnx = _build_pair(
            node_count,
            edge_count,
            seed=seed,
            weighted=False,
        )
        present = [str(index) for index in range(query_count)]
        missing = [f"missing-{index}" for index in range(query_count)]
        input_nx_bytes = canonical_bytes(has_node_nx)
        input_fnx_bytes = canonical_bytes(has_node_fnx)
        input_sha256 = hashlib.sha256(input_nx_bytes).hexdigest()
        present_keys_bytes = canonical_bytes(present)
        missing_keys_bytes = canonical_bytes(missing)
        present_keys_sha256 = hashlib.sha256(
            present_keys_bytes
        ).hexdigest()
        missing_keys_sha256 = hashlib.sha256(
            missing_keys_bytes
        ).hexdigest()
        if input_nx_bytes != input_fnx_bytes:
            raise RuntimeError("G.has_node claim input graphs diverged")
        if (
            len(input_nx_bytes) != expected_input_bytes
            or not hmac.compare_digest(input_sha256, expected_input_sha256)
            or len(present_keys_bytes) != expected_present_keys_bytes
            or not hmac.compare_digest(
                present_keys_sha256,
                expected_present_keys_sha256,
            )
            or len(missing_keys_bytes) != expected_missing_keys_bytes
            or not hmac.compare_digest(
                missing_keys_sha256,
                expected_missing_keys_sha256,
            )
        ):
            raise RuntimeError(
                "G.has_node claim input no longer matches its "
                "preregistered graph and ordered query keys"
            )

        present_nx = [
            has_node_nx.has_node(node)
            for node in present
        ]
        present_fnx = [
            has_node_fnx.has_node(node)
            for node in present
        ]
        missing_nx = [
            has_node_nx.has_node(node)
            for node in missing
        ]
        missing_fnx = [
            has_node_fnx.has_node(node)
            for node in missing
        ]
        present_nx_bytes = canonical_bytes(present_nx)
        present_fnx_bytes = canonical_bytes(present_fnx)
        missing_nx_bytes = canonical_bytes(missing_nx)
        missing_fnx_bytes = canonical_bytes(missing_fnx)
        present_output_sha256 = hashlib.sha256(
            present_nx_bytes
        ).hexdigest()
        missing_output_sha256 = hashlib.sha256(
            missing_nx_bytes
        ).hexdigest()
        if (
            present_nx_bytes != present_fnx_bytes
            or missing_nx_bytes != missing_fnx_bytes
        ):
            raise RuntimeError(
                "G.has_node claim ordered per-key results diverged"
            )
        if (
            any(type(result) is not bool for result in present_nx)
            or any(type(result) is not bool for result in missing_nx)
            or sum(present_nx) != query_count
            or sum(missing_nx) != 0
            or len(present_nx_bytes) != expected_present_output_bytes
            or not hmac.compare_digest(
                present_output_sha256,
                expected_present_output_sha256,
            )
            or len(missing_nx_bytes) != expected_missing_output_bytes
            or not hmac.compare_digest(
                missing_output_sha256,
                expected_missing_output_sha256,
            )
        ):
            raise RuntimeError(
                "G.has_node claim fixture no longer matches its "
                "preregistered complete ordered outputs"
            )
        EXTRA_PROVENANCE["claim_graph_has_node_fixture"] = {
            "publishing_commit": "85bb7263662f2c4f2d0b2c553d9b00c76d19f209",
            "measurement_commit": "08456fc932a0d1622660e117d55af79cb3283148",
            "recovered_harness_sha256": (
                "b30318548a7190e3d1f16767c7f5aeea5e94927aee9954e455511d3a4d3277dd"
            ),
            "recovered_ledger_sha256": (
                "515932b66c8b533e0949471c4dfa5652951096f79c79bd2ea2c1dd5ca7040627"
            ),
            "nodes": node_count,
            "edges": edge_count,
            "seed": seed,
            "weighted": False,
            "directed": False,
            "query_count_per_row": query_count,
            "present_query": "str(index) for index in range(512)",
            "missing_query": (
                "f'missing-{index}' for index in range(512)"
            ),
            "parameters": "node positional",
            "python_hash_seed": 0,
            "input_canonical_bytes": expected_input_bytes,
            "input_sha256": expected_input_sha256,
            "present_keys_canonical_bytes": expected_present_keys_bytes,
            "present_keys_sha256": expected_present_keys_sha256,
            "missing_keys_canonical_bytes": expected_missing_keys_bytes,
            "missing_keys_sha256": expected_missing_keys_sha256,
            "present_complete_output_canonical_bytes": (
                expected_present_output_bytes
            ),
            "present_complete_output_sha256": (
                expected_present_output_sha256
            ),
            "present_true_count": query_count,
            "missing_complete_output_canonical_bytes": (
                expected_missing_output_bytes
            ),
            "missing_complete_output_sha256": (
                expected_missing_output_sha256
            ),
            "missing_true_count": 0,
            "timed_projection": "sum(512 ordered has_node results)",
        }
        rows.extend(
            (
                (
                    "claim/G.has_node(present) x512 "
                    "n=2000 m=8000 seed=7 [nx/fnx]",
                    lambda graph=has_node_nx, keys=present: sum(
                        graph.has_node(node)
                        for node in keys
                    ),
                    lambda graph=has_node_fnx, keys=present: sum(
                        graph.has_node(node)
                        for node in keys
                    ),
                ),
                (
                    "claim/G.has_node(missing) x512 "
                    "n=2000 m=8000 seed=7 [nx/fnx]",
                    lambda graph=has_node_nx, keys=missing: sum(
                        graph.has_node(node)
                        for node in keys
                    ),
                    lambda graph=has_node_fnx, keys=missing: sum(
                        graph.has_node(node)
                        for node in keys
                    ),
                ),
            )
        )
    if "k_corona" in jobs:
        if os.environ.get("PYTHONHASHSEED") != "0":
            raise RuntimeError(
                "the k_corona claim fixture requires PYTHONHASHSEED=0 "
                "because output node order is part of the public contract"
            )
        node_count = 1_200
        edge_count = 6_000
        seed = 11
        k = 3
        expected_input_bytes = 194_277
        expected_input_sha256 = (
            "199d564350ec6f70885e8f8236fad28d6620b44e3e7917a470f6fba73024e653"
        )
        expected_output_nodes = (
            "530",
            "24",
            "943",
            "357",
            "667",
            "454",
            "313",
            "944",
            "1059",
            "1182",
            "104",
            "330",
            "1082",
        )
        expected_output_bytes = 292
        expected_output_sha256 = (
            "1be0290d66f0db36835be1959777317a207acedba5567ace56f385e129d36819"
        )
        corona_nx, corona_fnx = _build_pair(
            node_count,
            edge_count,
            seed=seed,
            weighted=False,
        )
        input_nx_bytes = canonical_bytes(corona_nx)
        input_fnx_bytes = canonical_bytes(corona_fnx)
        input_sha256 = hashlib.sha256(input_nx_bytes).hexdigest()
        if input_nx_bytes != input_fnx_bytes:
            raise RuntimeError("k_corona claim input graphs diverged")
        if (
            len(input_nx_bytes) != expected_input_bytes
            or not hmac.compare_digest(input_sha256, expected_input_sha256)
        ):
            raise RuntimeError(
                "k_corona claim input no longer matches its preregistered "
                "canonical byte count and SHA-256"
            )

        preflight_nx = nx.k_corona(corona_nx, k)
        preflight_fnx = fnx.k_corona(corona_fnx, k)
        preflight_nx_bytes = canonical_bytes(preflight_nx)
        preflight_fnx_bytes = canonical_bytes(preflight_fnx)
        output_sha256 = hashlib.sha256(preflight_nx_bytes).hexdigest()
        if preflight_nx_bytes != preflight_fnx_bytes:
            raise RuntimeError("k_corona claim fixture complete output diverged")
        if (
            tuple(preflight_nx) != expected_output_nodes
            or preflight_nx.number_of_edges() != 0
            or len(preflight_nx_bytes) != expected_output_bytes
            or not hmac.compare_digest(output_sha256, expected_output_sha256)
        ):
            raise RuntimeError(
                "k_corona claim fixture no longer matches its preregistered "
                "complete ordered output"
            )
        EXTRA_PROVENANCE["claim_k_corona_fixture"] = {
            "nodes": node_count,
            "edges": edge_count,
            "seed": seed,
            "k": k,
            "python_hash_seed": 0,
            "input_canonical_bytes": expected_input_bytes,
            "input_sha256": expected_input_sha256,
            "output_nodes": list(expected_output_nodes),
            "output_edges": 0,
            "output_canonical_bytes": expected_output_bytes,
            "complete_output_sha256": expected_output_sha256,
        }
        rows.append(
            (
                "claim/k_corona n=1200 m=6000 seed=11 k=3 [nx/fnx]",
                lambda: nx.k_corona(corona_nx, k),
                lambda: fnx.k_corona(corona_fnx, k),
            )
        )
    if "k_crust" in jobs:
        if os.environ.get("PYTHONHASHSEED") != "0":
            raise RuntimeError(
                "the k_crust claim fixture requires PYTHONHASHSEED=0 "
                "because output node order is part of the public contract"
            )
        node_count = 1_200
        edge_count = 6_000
        seed = 11
        expected_input_bytes = 194_277
        expected_input_sha256 = (
            "199d564350ec6f70885e8f8236fad28d6620b44e3e7917a470f6fba73024e653"
        )
        expected_output_nodes = 274
        expected_output_edges = 251
        expected_output_bytes = 12_843
        expected_output_sha256 = (
            "880731d3c6d28201e49e92b745cd767810574aa250b627f8751de9b135817923"
        )
        crust_nx, crust_fnx = _build_pair(
            node_count,
            edge_count,
            seed=seed,
            weighted=False,
        )
        input_nx_bytes = canonical_bytes(crust_nx)
        input_fnx_bytes = canonical_bytes(crust_fnx)
        input_sha256 = hashlib.sha256(input_nx_bytes).hexdigest()
        if input_nx_bytes != input_fnx_bytes:
            raise RuntimeError("k_crust claim input graphs diverged")
        if (
            len(input_nx_bytes) != expected_input_bytes
            or not hmac.compare_digest(input_sha256, expected_input_sha256)
        ):
            raise RuntimeError(
                "k_crust claim input no longer matches its preregistered "
                "canonical byte count and SHA-256"
            )

        preflight_nx = nx.k_crust(crust_nx)
        preflight_fnx = fnx.k_crust(crust_fnx)
        preflight_nx_bytes = canonical_bytes(preflight_nx)
        preflight_fnx_bytes = canonical_bytes(preflight_fnx)
        output_sha256 = hashlib.sha256(preflight_nx_bytes).hexdigest()
        if preflight_nx_bytes != preflight_fnx_bytes:
            raise RuntimeError("k_crust claim fixture complete output diverged")
        if (
            preflight_nx.number_of_nodes() != expected_output_nodes
            or preflight_nx.number_of_edges() != expected_output_edges
            or len(preflight_nx_bytes) != expected_output_bytes
            or not hmac.compare_digest(output_sha256, expected_output_sha256)
        ):
            raise RuntimeError(
                "k_crust claim fixture no longer matches its preregistered "
                "complete ordered output"
            )
        EXTRA_PROVENANCE["claim_k_crust_fixture"] = {
            "nodes": node_count,
            "edges": edge_count,
            "seed": seed,
            "k": None,
            "python_hash_seed": 0,
            "input_canonical_bytes": expected_input_bytes,
            "input_sha256": expected_input_sha256,
            "output_nodes": expected_output_nodes,
            "output_edges": expected_output_edges,
            "output_canonical_bytes": expected_output_bytes,
            "complete_output_sha256": expected_output_sha256,
        }
        rows.append(
            (
                "claim/k_crust n=1200 m=6000 seed=11 k=None [nx/fnx]",
                lambda: nx.k_crust(crust_nx),
                lambda: fnx.k_crust(crust_fnx),
            )
        )
    if "label_propagation_communities" in jobs:
        if os.environ.get("PYTHONHASHSEED") != "0":
            raise RuntimeError(
                "the label_propagation_communities claim fixture requires "
                "PYTHONHASHSEED=0 because community generator order is "
                "part of the public contract"
            )
        node_count = 1_200
        edge_count = 6_000
        seed = 11
        expected_input_bytes = 194_277
        expected_input_sha256 = (
            "199d564350ec6f70885e8f8236fad28d6620b44e3e7917a470f6fba73024e653"
        )
        expected_communities = 2
        expected_community_sizes = (1_199, 1)
        expected_covered_nodes = 1_200
        expected_output_bytes = 8_512
        expected_output_sha256 = (
            "bb8d5710d2f0eb09435f865e9561438c2c54bac87c02c2b41fd92f2406687ea9"
        )
        expected_normalized_output_bytes = 8_494
        expected_normalized_output_sha256 = (
            "d53bb137b4413e187056ed1d85c987bb20da30e4910d2c0fbfe1e203487e37a5"
        )
        label_nx, label_fnx = _build_pair(
            node_count,
            edge_count,
            seed=seed,
            weighted=False,
        )
        input_nx_bytes = canonical_bytes(label_nx)
        input_fnx_bytes = canonical_bytes(label_fnx)
        input_sha256 = hashlib.sha256(input_nx_bytes).hexdigest()
        if input_nx_bytes != input_fnx_bytes:
            raise RuntimeError(
                "label_propagation_communities claim input graphs diverged"
            )
        if (
            len(input_nx_bytes) != expected_input_bytes
            or not hmac.compare_digest(input_sha256, expected_input_sha256)
        ):
            raise RuntimeError(
                "label_propagation_communities claim input no longer "
                "matches its preregistered canonical byte count and SHA-256"
            )

        preflight_nx = list(
            nx.community.label_propagation_communities(label_nx)
        )
        preflight_fnx = list(
            fnx.community.label_propagation_communities(label_fnx)
        )
        preflight_nx_bytes = canonical_bytes(preflight_nx)
        preflight_fnx_bytes = canonical_bytes(preflight_fnx)
        output_sha256 = hashlib.sha256(preflight_nx_bytes).hexdigest()
        if preflight_nx_bytes != preflight_fnx_bytes:
            raise RuntimeError(
                "label_propagation_communities complete ordered output "
                "diverged"
            )
        if (
            len(preflight_nx) != expected_communities
            or tuple(map(len, preflight_nx)) != expected_community_sizes
            or sum(map(len, preflight_nx)) != expected_covered_nodes
            or set().union(*preflight_nx) != set(label_nx)
            or len(preflight_nx_bytes) != expected_output_bytes
            or not hmac.compare_digest(output_sha256, expected_output_sha256)
        ):
            raise RuntimeError(
                "label_propagation_communities claim fixture no longer "
                "matches its preregistered complete ordered partition"
            )

        normalized_nx_bytes = canonical_bytes(
            sorted(sorted(community) for community in preflight_nx)
        )
        normalized_fnx_bytes = canonical_bytes(
            sorted(sorted(community) for community in preflight_fnx)
        )
        normalized_output_sha256 = hashlib.sha256(
            normalized_nx_bytes
        ).hexdigest()
        if normalized_nx_bytes != normalized_fnx_bytes:
            raise RuntimeError(
                "label_propagation_communities normalized partition diverged"
            )
        if (
            len(normalized_nx_bytes) != expected_normalized_output_bytes
            or not hmac.compare_digest(
                normalized_output_sha256,
                expected_normalized_output_sha256,
            )
        ):
            raise RuntimeError(
                "label_propagation_communities normalized partition no "
                "longer matches its preregistered output"
            )
        EXTRA_PROVENANCE[
            "claim_label_propagation_communities_fixture"
        ] = {
            "source_commit": "87cf65e54a4e13a72a12c2bc7458655c7d4b3ac1",
            "measured_harness_sha256": (
                "92917fa41376111f6490278651545d465c8d726dce21037facd1a3f29e0e36c0"
            ),
            "nodes": node_count,
            "edges": edge_count,
            "seed": seed,
            "weighted": False,
            "directed": False,
            "parameters": "none",
            "python_hash_seed": 0,
            "input_canonical_bytes": expected_input_bytes,
            "input_sha256": expected_input_sha256,
            "communities": expected_communities,
            "community_sizes_in_order": list(expected_community_sizes),
            "covered_nodes": expected_covered_nodes,
            "output_canonical_bytes": expected_output_bytes,
            "complete_ordered_output_sha256": expected_output_sha256,
            "normalized_output_canonical_bytes": (
                expected_normalized_output_bytes
            ),
            "normalized_output_sha256": (
                expected_normalized_output_sha256
            ),
        }
        rows.append(
            (
                "claim/label_propagation_communities "
                "n=1200 m=6000 seed=11 [nx/fnx]",
                lambda graph=label_nx: list(
                    nx.community.label_propagation_communities(graph)
                ),
                lambda graph=label_fnx: list(
                    fnx.community.label_propagation_communities(graph)
                ),
            )
        )
    if "kosaraju_strongly_connected_components" in jobs:
        if os.environ.get("PYTHONHASHSEED") != "0":
            raise RuntimeError(
                "the kosaraju_strongly_connected_components claim fixture "
                "requires PYTHONHASHSEED=0 because component order is part "
                "of the public contract"
            )
        node_count = 800
        edge_count = 4_000
        seed = 11
        expected_input_bytes = 189_843
        expected_input_sha256 = (
            "5d7c003cd5c7507408804b01e266bb81d7cfb2fe6546c58dfebff60f621ea89b"
        )
        expected_components = 11
        expected_component_sizes = (1, 1, 1, 1, 1, 790, 1, 1, 1, 1, 1)
        expected_ordered_output_bytes = 5_512
        expected_ordered_output_sha256 = (
            "d75eb49951307e7288928ee8174a752851f4e53c84c0739ed1e3292ddf7f6b60"
        )
        expected_normalized_output_sha256 = (
            "8a2d25bce721d744f9d57470cf21a9c82890d0c5181f24b426cd35090eb73995"
        )

        # Preserve the recovered claim fixture exactly. Unlike `_build_pair`,
        # its directed builder deduplicates ordered arcs, so (u, v) and
        # (v, u) may both be present.
        kosaraju_nx, kosaraju_fnx = _build_ordered_arc_pair(
            node_count,
            edge_count,
            seed=seed,
            weighted=True,
        )

        input_nx_bytes = canonical_bytes(kosaraju_nx)
        input_fnx_bytes = canonical_bytes(kosaraju_fnx)
        input_sha256 = hashlib.sha256(input_nx_bytes).hexdigest()
        if input_nx_bytes != input_fnx_bytes:
            raise RuntimeError(
                "kosaraju_strongly_connected_components claim input graphs "
                "diverged"
            )
        if (
            len(input_nx_bytes) != expected_input_bytes
            or not hmac.compare_digest(input_sha256, expected_input_sha256)
        ):
            raise RuntimeError(
                "kosaraju_strongly_connected_components claim input no "
                "longer matches its preregistered canonical byte count and "
                "SHA-256"
            )

        ordered_nx = [
            sorted(component)
            for component in nx.kosaraju_strongly_connected_components(
                kosaraju_nx
            )
        ]
        ordered_fnx = [
            sorted(component)
            for component in fnx.kosaraju_strongly_connected_components(
                kosaraju_fnx
            )
        ]
        ordered_nx_bytes = canonical_bytes(ordered_nx)
        ordered_fnx_bytes = canonical_bytes(ordered_fnx)
        ordered_output_sha256 = hashlib.sha256(ordered_nx_bytes).hexdigest()
        if ordered_nx_bytes != ordered_fnx_bytes:
            raise RuntimeError(
                "kosaraju_strongly_connected_components complete ordered "
                "output diverged"
            )
        if (
            len(ordered_nx) != expected_components
            or tuple(map(len, ordered_nx)) != expected_component_sizes
            or len(ordered_nx_bytes) != expected_ordered_output_bytes
            or not hmac.compare_digest(
                ordered_output_sha256,
                expected_ordered_output_sha256,
            )
        ):
            raise RuntimeError(
                "kosaraju_strongly_connected_components claim fixture no "
                "longer matches its preregistered complete ordered output"
            )

        normalized_nx_bytes = canonical_bytes(sorted(ordered_nx))
        normalized_fnx_bytes = canonical_bytes(sorted(ordered_fnx))
        normalized_output_sha256 = hashlib.sha256(
            normalized_nx_bytes
        ).hexdigest()
        if normalized_nx_bytes != normalized_fnx_bytes:
            raise RuntimeError(
                "kosaraju_strongly_connected_components published normalized "
                "output diverged"
            )
        if (
            len(normalized_nx_bytes) != expected_ordered_output_bytes
            or not hmac.compare_digest(
                normalized_output_sha256,
                expected_normalized_output_sha256,
            )
        ):
            raise RuntimeError(
                "kosaraju_strongly_connected_components claim fixture no "
                "longer matches its preregistered normalized output"
            )
        EXTRA_PROVENANCE[
            "claim_kosaraju_strongly_connected_components_fixture"
        ] = {
            "nodes": node_count,
            "edges": edge_count,
            "seed": seed,
            "weighted": True,
            "directed": True,
            "ordered_arc_deduplication": True,
            "python_hash_seed": 0,
            "input_canonical_bytes": expected_input_bytes,
            "input_sha256": expected_input_sha256,
            "components": expected_components,
            "component_sizes_in_order": list(expected_component_sizes),
            "ordered_output_canonical_bytes": expected_ordered_output_bytes,
            "complete_ordered_output_sha256": (
                expected_ordered_output_sha256
            ),
            "published_normalized_output_sha256": (
                expected_normalized_output_sha256
            ),
        }
        rows.append(
            (
                "claim/kosaraju_strongly_connected_components "
                "n=800 m=4000 seed=11 weighted=True directed=True [nx/fnx]",
                lambda: sorted(
                    map(
                        sorted,
                        nx.kosaraju_strongly_connected_components(
                            kosaraju_nx
                        ),
                    )
                ),
                lambda: sorted(
                    map(
                        sorted,
                        fnx.kosaraju_strongly_connected_components(
                            kosaraju_fnx
                        ),
                    )
                ),
            )
        )
    if "minimum_branching" in jobs:
        if os.environ.get("PYTHONHASHSEED") != "0":
            raise RuntimeError(
                "the minimum_branching claim fixture requires "
                "PYTHONHASHSEED=0 because output node order is part of the "
                "public contract"
            )
        node_count = 800
        edge_count = 4_000
        seed = 11
        expected_input_bytes = 189_843
        expected_input_sha256 = (
            "5d7c003cd5c7507408804b01e266bb81d7cfb2fe6546c58dfebff60f621ea89b"
        )
        expected_projected_output_bytes = 2
        expected_projected_output_sha256 = (
            "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945"
        )
        expected_output_nodes = 800
        expected_output_edges = 0
        expected_output_bytes = 16_707
        expected_output_sha256 = (
            "e6fd694bc8cd85ad2b23c9bc1ed6a76292330fde172c0f2f6beb6f48ebdf2469"
        )
        branching_nx, branching_fnx = _build_ordered_arc_pair(
            node_count,
            edge_count,
            seed=seed,
            weighted=True,
        )
        input_nx_bytes = canonical_bytes(branching_nx)
        input_fnx_bytes = canonical_bytes(branching_fnx)
        input_sha256 = hashlib.sha256(input_nx_bytes).hexdigest()
        if input_nx_bytes != input_fnx_bytes:
            raise RuntimeError("minimum_branching claim input graphs diverged")
        if (
            len(input_nx_bytes) != expected_input_bytes
            or not hmac.compare_digest(input_sha256, expected_input_sha256)
        ):
            raise RuntimeError(
                "minimum_branching claim input no longer matches its "
                "preregistered canonical byte count and SHA-256"
            )

        preflight_nx = nx.minimum_branching(branching_nx)
        preflight_fnx = fnx.minimum_branching(branching_fnx)
        projected_nx_bytes = canonical_bytes(sorted(preflight_nx.edges()))
        projected_fnx_bytes = canonical_bytes(sorted(preflight_fnx.edges()))
        projected_output_sha256 = hashlib.sha256(
            projected_nx_bytes
        ).hexdigest()
        if projected_nx_bytes != projected_fnx_bytes:
            raise RuntimeError(
                "minimum_branching claim recovered edge projection diverged"
            )
        if (
            len(projected_nx_bytes) != expected_projected_output_bytes
            or not hmac.compare_digest(
                projected_output_sha256,
                expected_projected_output_sha256,
            )
        ):
            raise RuntimeError(
                "minimum_branching claim recovered edge projection no "
                "longer matches its preregistered empty result"
            )

        preflight_nx_bytes = canonical_bytes(preflight_nx)
        preflight_fnx_bytes = canonical_bytes(preflight_fnx)
        output_sha256 = hashlib.sha256(preflight_nx_bytes).hexdigest()
        if preflight_nx_bytes != preflight_fnx_bytes:
            raise RuntimeError(
                "minimum_branching claim complete ordered output diverged"
            )
        if (
            preflight_nx.number_of_nodes() != expected_output_nodes
            or preflight_nx.number_of_edges() != expected_output_edges
            or len(preflight_nx_bytes) != expected_output_bytes
            or not hmac.compare_digest(output_sha256, expected_output_sha256)
        ):
            raise RuntimeError(
                "minimum_branching claim fixture no longer matches its "
                "preregistered complete ordered output"
            )
        EXTRA_PROVENANCE["claim_minimum_branching_fixture"] = {
            "nodes": node_count,
            "edges": edge_count,
            "seed": seed,
            "weighted": True,
            "directed": True,
            "ordered_arc_deduplication": True,
            "weight_range_inclusive": [1, 20],
            "python_hash_seed": 0,
            "input_canonical_bytes": expected_input_bytes,
            "input_sha256": expected_input_sha256,
            "recovered_projection": "sorted(result.edges())",
            "projected_output_canonical_bytes": (
                expected_projected_output_bytes
            ),
            "projected_output_sha256": expected_projected_output_sha256,
            "output_nodes": expected_output_nodes,
            "output_edges": expected_output_edges,
            "output_canonical_bytes": expected_output_bytes,
            "complete_output_sha256": expected_output_sha256,
        }
        rows.append(
            (
                "claim/minimum_branching "
                "n=800 m=4000 seed=11 weights=1..20 directed=True [nx/fnx]",
                lambda: nx.minimum_branching(branching_nx),
                lambda: fnx.minimum_branching(branching_fnx),
            )
        )
    if "pagerank" in jobs:
        if os.environ.get("PYTHONHASHSEED") != "0":
            raise RuntimeError(
                "the pagerank claim fixture requires PYTHONHASHSEED=0 "
                "because float mapping order is part of the public contract"
            )
        node_count = 2_000
        edge_count = 8_000
        seed = 7
        expected_input_bytes = 273_938
        expected_input_sha256 = (
            "03635cb95fcf023b79a245e0dc38125225ba216e6eb77a9270ef5121024f6164"
        )
        expected_output_items = 2_000
        expected_output_sum = 0.9999999999999998
        expected_output_bytes = 65_176
        expected_output_sha256 = (
            "f95e2d04fb5164b372aeba0fc78ff7563c2fd295ee994152f47c2e3c4a62032f"
        )
        pagerank_nx, pagerank_fnx = _build_pair(
            node_count,
            edge_count,
            seed=seed,
            weighted=False,
        )
        input_nx_bytes = canonical_bytes(pagerank_nx)
        input_fnx_bytes = canonical_bytes(pagerank_fnx)
        input_sha256 = hashlib.sha256(input_nx_bytes).hexdigest()
        if input_nx_bytes != input_fnx_bytes:
            raise RuntimeError("pagerank claim input graphs diverged")
        if (
            len(input_nx_bytes) != expected_input_bytes
            or not hmac.compare_digest(input_sha256, expected_input_sha256)
        ):
            raise RuntimeError(
                "pagerank claim input no longer matches its preregistered "
                "canonical byte count and SHA-256"
            )

        preflight_nx = nx.pagerank(pagerank_nx)
        preflight_fnx = fnx.pagerank(pagerank_fnx)
        preflight_nx_bytes = canonical_bytes(preflight_nx)
        preflight_fnx_bytes = canonical_bytes(preflight_fnx)
        output_sha256 = hashlib.sha256(preflight_nx_bytes).hexdigest()
        if preflight_nx_bytes != preflight_fnx_bytes:
            raise RuntimeError(
                "pagerank claim complete ordered float mapping diverged"
            )
        if (
            len(preflight_nx) != expected_output_items
            or sum(preflight_nx.values()) != expected_output_sum
            or len(preflight_nx_bytes) != expected_output_bytes
            or not hmac.compare_digest(output_sha256, expected_output_sha256)
        ):
            raise RuntimeError(
                "pagerank claim fixture no longer matches its preregistered "
                "complete ordered float mapping"
            )
        EXTRA_PROVENANCE["claim_pagerank_fixture"] = {
            "nodes": node_count,
            "edges": edge_count,
            "seed": seed,
            "weighted_graph": False,
            "alpha": 0.85,
            "personalization": None,
            "max_iter": 100,
            "tol": 1e-6,
            "nstart": None,
            "weight": "weight",
            "dangling": None,
            "parameters": "all omitted (NetworkX 3.6.1 defaults)",
            "python_hash_seed": 0,
            "input_canonical_bytes": expected_input_bytes,
            "input_sha256": expected_input_sha256,
            "output_items": expected_output_items,
            "output_sum": expected_output_sum,
            "output_canonical_bytes": expected_output_bytes,
            "complete_output_sha256": expected_output_sha256,
        }
        rows.append(
            (
                "claim/pagerank "
                "n=2000 m=8000 seed=7 parameters=defaults [nx/fnx]",
                lambda graph=pagerank_nx: nx.pagerank(graph),
                lambda graph=pagerank_fnx: fnx.pagerank(graph),
            )
        )
    if "partition_spanning_tree" in jobs:
        if os.environ.get("PYTHONHASHSEED") != "0":
            raise RuntimeError(
                "the partition_spanning_tree claim fixture requires "
                "PYTHONHASHSEED=0 because complete graph order is part of "
                "the public contract"
            )
        node_count = 800
        edge_count = 4_000
        seed = 11
        expected_input_bytes = 189_846
        expected_input_sha256 = (
            "584eb6bafa6fb460a577fdc11478c50bbd8c0238c9f2f9b8552252fb6cb624c4"
        )
        expected_projected_output_edges = 799
        expected_projected_output_bytes = 12_546
        expected_projected_output_sha256 = (
            "13186f9d9ff25bc03b54d572af8e9b4d2e3d2221f08374ce8b3bd9922fb2a9e5"
        )
        expected_output_nodes = 800
        expected_output_edges = 799
        expected_output_bytes = 50_835
        expected_output_sha256 = (
            "43826cfdd7e7f3c42220eafa49be7f64eb0c18ae7bb27b3ef9f4fd9b0592628b"
        )
        spanning_nx, spanning_fnx = _build_pair(
            node_count,
            edge_count,
            seed=seed,
            weighted=True,
        )
        input_nx_bytes = canonical_bytes(spanning_nx)
        input_fnx_bytes = canonical_bytes(spanning_fnx)
        input_sha256 = hashlib.sha256(input_nx_bytes).hexdigest()
        if input_nx_bytes != input_fnx_bytes:
            raise RuntimeError(
                "partition_spanning_tree claim input graphs diverged"
            )
        if (
            len(input_nx_bytes) != expected_input_bytes
            or not hmac.compare_digest(input_sha256, expected_input_sha256)
        ):
            raise RuntimeError(
                "partition_spanning_tree claim input no longer matches its "
                "preregistered canonical byte count and SHA-256"
        )

        preflight_nx = nx.partition_spanning_tree(spanning_nx)
        preflight_fnx = fnx.partition_spanning_tree(spanning_fnx)
        projected_nx = sorted(preflight_nx.edges())
        projected_fnx = sorted(preflight_fnx.edges())
        projected_nx_bytes = canonical_bytes(projected_nx)
        projected_fnx_bytes = canonical_bytes(projected_fnx)
        projected_output_sha256 = hashlib.sha256(
            projected_nx_bytes
        ).hexdigest()
        if projected_nx_bytes != projected_fnx_bytes:
            raise RuntimeError(
                "partition_spanning_tree recovered edge projection diverged"
            )
        if (
            len(projected_nx) != expected_projected_output_edges
            or len(projected_nx_bytes) != expected_projected_output_bytes
            or not hmac.compare_digest(
                projected_output_sha256,
                expected_projected_output_sha256,
            )
        ):
            raise RuntimeError(
                "partition_spanning_tree recovered edge projection no "
                "longer matches its preregistered result"
            )

        preflight_nx_bytes = canonical_bytes(preflight_nx)
        preflight_fnx_bytes = canonical_bytes(preflight_fnx)
        output_sha256 = hashlib.sha256(preflight_nx_bytes).hexdigest()
        if preflight_nx_bytes != preflight_fnx_bytes:
            raise RuntimeError(
                "partition_spanning_tree complete ordered output diverged"
            )
        if (
            preflight_nx.number_of_nodes() != expected_output_nodes
            or preflight_nx.number_of_edges() != expected_output_edges
            or len(preflight_nx_bytes) != expected_output_bytes
            or not hmac.compare_digest(output_sha256, expected_output_sha256)
        ):
            raise RuntimeError(
                "partition_spanning_tree claim fixture no longer matches "
                "its preregistered complete ordered output"
            )
        EXTRA_PROVENANCE["claim_partition_spanning_tree_fixture"] = {
            "nodes": node_count,
            "edges": edge_count,
            "seed": seed,
            "weighted": True,
            "directed": False,
            "weight_range_inclusive": [1, 20],
            "minimum": True,
            "weight": "weight",
            "partition": "partition",
            "ignore_nan": False,
            "parameters": "all omitted (NetworkX 3.6.1 defaults)",
            "python_hash_seed": 0,
            "input_canonical_bytes": expected_input_bytes,
            "input_sha256": expected_input_sha256,
            "recovered_projection": "sorted(result.edges())",
            "projected_output_edges": expected_projected_output_edges,
            "projected_output_canonical_bytes": (
                expected_projected_output_bytes
            ),
            "projected_output_sha256": expected_projected_output_sha256,
            "output_nodes": expected_output_nodes,
            "output_edges": expected_output_edges,
            "output_canonical_bytes": expected_output_bytes,
            "complete_output_sha256": expected_output_sha256,
        }
        rows.append(
            (
                "claim/partition_spanning_tree "
                "n=800 m=4000 seed=11 weights=1..20 "
                "parameters=defaults [nx/fnx]",
                lambda graph=spanning_nx: nx.partition_spanning_tree(graph),
                lambda graph=spanning_fnx: fnx.partition_spanning_tree(graph),
            )
        )
    if "read_gml" in jobs:
        if os.environ.get("PYTHONHASHSEED") != "0":
            raise RuntimeError(
                "the read_gml claim fixture requires PYTHONHASHSEED=0 "
                "because decoded graph and projection order are part of "
                "the public contract"
            )
        source_node_count = 1_200
        source_edge_count = 6_000
        source_seed = 11
        expected_payload_bytes = 307_162
        expected_payload_sha256 = (
            "e750bdb0901f2da65fe9b8809c84d5e254bf26525a24026ea28a62f9664d85ce"
        )
        expected_output_nodes = 1_200
        expected_output_edges = 6_000
        expected_output_bytes = 194_277
        expected_output_sha256 = (
            "199d564350ec6f70885e8f8236fad28d6620b44e3e7917a470f6fba73024e653"
        )
        expected_projection_items = 6_000
        expected_projection_bytes = 108_972
        expected_projection_sha256 = (
            "2f54f4c0b59355453688e92a940bfa0c702ceb99046bdcc3c246cb7ac20f3295"
        )
        gml_source_nx, _gml_source_fnx = _build_pair(
            source_node_count,
            source_edge_count,
            seed=source_seed,
            weighted=False,
        )
        gml_source_nx = nx.convert_node_labels_to_integers(gml_source_nx)
        gml_output = io.BytesIO()
        nx.write_gml(gml_source_nx, gml_output)
        gml_payload = gml_output.getvalue()
        payload_sha256 = hashlib.sha256(gml_payload).hexdigest()
        if (
            len(gml_payload) != expected_payload_bytes
            or not hmac.compare_digest(
                payload_sha256,
                expected_payload_sha256,
            )
        ):
            raise RuntimeError(
                "read_gml claim payload no longer matches its "
                "preregistered byte count and SHA-256"
            )
        gml_path = _materialize_claim_payload(
            "franken_networkx-claim-read_gml-e750bdb0901f2da6.gml",
            gml_payload,
        )
        preflight_nx = nx.read_gml(gml_path)
        preflight_fnx = fnx.read_gml(gml_path)
        preflight_nx_bytes = canonical_bytes(preflight_nx)
        preflight_fnx_bytes = canonical_bytes(preflight_fnx)
        output_sha256 = hashlib.sha256(preflight_nx_bytes).hexdigest()
        projected_nx = sorted(map(str, preflight_nx.edges()))
        projected_fnx = sorted(map(str, preflight_fnx.edges()))
        projected_nx_bytes = canonical_bytes(projected_nx)
        projected_fnx_bytes = canonical_bytes(projected_fnx)
        projection_sha256 = hashlib.sha256(projected_nx_bytes).hexdigest()
        if preflight_nx_bytes != preflight_fnx_bytes:
            raise RuntimeError("read_gml claim complete decoded graph diverged")
        if projected_nx_bytes != projected_fnx_bytes:
            raise RuntimeError(
                "read_gml claim recovered sorted string-edge projection "
                "diverged"
            )
        if (
            type(preflight_nx).__name__ != "Graph"
            or type(preflight_fnx).__name__ != "Graph"
            or preflight_nx.is_directed()
            or preflight_nx.is_multigraph()
            or preflight_nx.number_of_nodes() != expected_output_nodes
            or preflight_nx.number_of_edges() != expected_output_edges
            or len(preflight_nx_bytes) != expected_output_bytes
            or not hmac.compare_digest(output_sha256, expected_output_sha256)
            or len(projected_nx) != expected_projection_items
            or len(projected_nx_bytes) != expected_projection_bytes
            or not hmac.compare_digest(
                projection_sha256,
                expected_projection_sha256,
            )
        ):
            raise RuntimeError(
                "read_gml claim fixture no longer matches its "
                "preregistered decoded graph and projection"
            )
        EXTRA_PROVENANCE["claim_read_gml_fixture"] = {
            "publishing_commit": "87cf65e54a4e13a72a12c2bc7458655c7d4b3ac1",
            "recovered_harness_sha256": (
                "1114f244b93787b9e1d6a900633ccd93f3a09c91de8d669bde9ba75df5a611e3"
            ),
            "recovered_result_sha256": (
                "40040b7b90de11721263864fff0e3e79f260ca2779e16c8252784dc9236ef249"
            ),
            "recovered_builder_sha256": (
                "fb051cf48508ad56ee0c64103335090bd7866b12d65cb2e29d522cfa33b4cba1"
            ),
            "source_nodes": source_node_count,
            "source_edges": source_edge_count,
            "source_seed": source_seed,
            "source_weighted": False,
            "source_directed": False,
            "source_relabel": "networkx.convert_node_labels_to_integers",
            "writer": "networkx.write_gml",
            "writer_parameters": "all omitted (NetworkX 3.6.1 defaults)",
            "reader_input": "path",
            "reader_parameters": "path positional; all others omitted",
            "fixture_path": gml_path,
            "python_hash_seed": 0,
            "payload_bytes": expected_payload_bytes,
            "payload_sha256": expected_payload_sha256,
            "output_type": "Graph",
            "output_nodes": expected_output_nodes,
            "output_edges": expected_output_edges,
            "output_canonical_bytes": expected_output_bytes,
            "complete_decoded_graph_sha256": expected_output_sha256,
            "timed_projection": "sorted(map(str, result.edges()))",
            "projection_items": expected_projection_items,
            "projection_canonical_bytes": expected_projection_bytes,
            "projection_sha256": expected_projection_sha256,
        }
        rows.append(
            (
                "claim/read_gml "
                "source_n=1200 source_m=6000 source_seed=11 "
                "input=path then=sorted(map(str,edges)) [nx/fnx]",
                lambda path=gml_path: sorted(
                    map(str, nx.read_gml(path).edges())
                ),
                lambda path=gml_path: sorted(
                    map(str, fnx.read_gml(path).edges())
                ),
            )
        )
    if "read_graph6" in jobs or "read_sparse6" in jobs:
        source_node_count = 200
        source_edge_count = 800
        source_seed = 13
        reader_source_nx, _reader_source_fnx = _build_pair(
            source_node_count,
            source_edge_count,
            seed=source_seed,
            weighted=False,
        )
        reader_source_nx = nx.convert_node_labels_to_integers(
            reader_source_nx
        )
    if "read_graph6" in jobs:
        if os.environ.get("PYTHONHASHSEED") != "0":
            raise RuntimeError(
                "the read_graph6 claim fixture requires PYTHONHASHSEED=0 "
                "because decoded graph and edge order are part of the "
                "public contract"
            )
        expected_payload_bytes = 3_332
        expected_payload_sha256 = (
            "0512c5270c4fead9ee7017e54dd8f9cd8f241a48b01f10460eccf07203c57f16"
        )
        expected_output_nodes = 200
        expected_output_edges = 800
        expected_output_bytes = 22_009
        expected_output_sha256 = (
            "ea60802d53f9e77b41646c010b9178468d3e9ca8442307cf576687e0ba333c73"
        )
        expected_projection_bytes = 8_704
        expected_projection_sha256 = (
            "ed01731bc0e1c3142752f78ca678da69ccb2599730ba059a6b1d2f52e18ee151"
        )
        graph6_output = io.BytesIO()
        nx.write_graph6(reader_source_nx, graph6_output)
        graph6_payload = graph6_output.getvalue()
        payload_sha256 = hashlib.sha256(graph6_payload).hexdigest()
        if (
            len(graph6_payload) != expected_payload_bytes
            or not hmac.compare_digest(
                payload_sha256,
                expected_payload_sha256,
            )
        ):
            raise RuntimeError(
                "read_graph6 claim payload no longer matches its "
                "preregistered byte count and SHA-256"
            )
        graph6_path = _materialize_claim_payload(
            "franken_networkx-claim-read_graph6-0512c5270c4fead9.g6",
            graph6_payload,
        )
        preflight_nx = nx.read_graph6(graph6_path)
        preflight_fnx = fnx.read_graph6(graph6_path)
        preflight_nx_bytes = canonical_bytes(preflight_nx)
        preflight_fnx_bytes = canonical_bytes(preflight_fnx)
        output_sha256 = hashlib.sha256(preflight_nx_bytes).hexdigest()
        projected_nx = sorted(preflight_nx.edges())
        projected_fnx = sorted(preflight_fnx.edges())
        projected_nx_bytes = canonical_bytes(projected_nx)
        projected_fnx_bytes = canonical_bytes(projected_fnx)
        projection_sha256 = hashlib.sha256(projected_nx_bytes).hexdigest()
        if preflight_nx_bytes != preflight_fnx_bytes:
            raise RuntimeError(
                "read_graph6 claim complete decoded graph diverged"
            )
        if projected_nx_bytes != projected_fnx_bytes:
            raise RuntimeError(
                "read_graph6 claim recovered sorted-edge projection diverged"
            )
        if (
            type(preflight_nx).__name__ != "Graph"
            or type(preflight_fnx).__name__ != "Graph"
            or preflight_nx.is_directed()
            or preflight_nx.is_multigraph()
            or preflight_nx.number_of_nodes() != expected_output_nodes
            or preflight_nx.number_of_edges() != expected_output_edges
            or len(preflight_nx_bytes) != expected_output_bytes
            or not hmac.compare_digest(output_sha256, expected_output_sha256)
            or len(projected_nx_bytes) != expected_projection_bytes
            or not hmac.compare_digest(
                projection_sha256,
                expected_projection_sha256,
            )
        ):
            raise RuntimeError(
                "read_graph6 claim fixture no longer matches its "
                "preregistered decoded graph and projection"
            )
        EXTRA_PROVENANCE["claim_read_graph6_fixture"] = {
            "publishing_commit": "87cf65e54a4e13a72a12c2bc7458655c7d4b3ac1",
            "recovered_harness_sha256": (
                "1114f244b93787b9e1d6a900633ccd93f3a09c91de8d669bde9ba75df5a611e3"
            ),
            "recovered_result_sha256": (
                "40040b7b90de11721263864fff0e3e79f260ca2779e16c8252784dc9236ef249"
            ),
            "recovered_builder_sha256": (
                "fb051cf48508ad56ee0c64103335090bd7866b12d65cb2e29d522cfa33b4cba1"
            ),
            "source_nodes": source_node_count,
            "source_edges": source_edge_count,
            "source_seed": source_seed,
            "source_weighted": False,
            "source_directed": False,
            "source_relabel": "networkx.convert_node_labels_to_integers",
            "writer": "networkx.write_graph6",
            "writer_parameters": "all omitted (NetworkX 3.6.1 defaults)",
            "reader_input": "path",
            "reader_parameters": "path positional; all others omitted",
            "fixture_path": graph6_path,
            "python_hash_seed": 0,
            "payload_bytes": expected_payload_bytes,
            "payload_sha256": expected_payload_sha256,
            "output_type": "Graph",
            "output_nodes": expected_output_nodes,
            "output_edges": expected_output_edges,
            "output_canonical_bytes": expected_output_bytes,
            "complete_decoded_graph_sha256": expected_output_sha256,
            "timed_projection": "sorted(result.edges())",
            "projection_canonical_bytes": expected_projection_bytes,
            "projection_sha256": expected_projection_sha256,
        }
        rows.append(
            (
                "claim/read_graph6 "
                "source_n=200 source_m=800 source_seed=13 "
                "input=path then=sorted(edges) [nx/fnx]",
                lambda path=graph6_path: sorted(
                    nx.read_graph6(path).edges()
                ),
                lambda path=graph6_path: sorted(
                    fnx.read_graph6(path).edges()
                ),
            )
        )
    if "read_multiline_adjlist" in jobs:
        if os.environ.get("PYTHONHASHSEED") != "0":
            raise RuntimeError(
                "the read_multiline_adjlist claim fixture requires "
                "PYTHONHASHSEED=0 because decoded graph and edge order "
                "are part of the public contract"
            )
        source_node_count = 1_200
        source_edge_count = 6_000
        source_seed = 11
        expected_payload_bytes = 51_331
        expected_payload_sha256 = (
            "80bc7e583290c22464518fb7c1b5372a5933fc89809591d5e9c50aff3785f725"
        )
        expected_output_nodes = 1_200
        expected_output_edges = 6_000
        expected_output_bytes = 194_277
        expected_output_sha256 = (
            "46bb7cc108e04fc72c658ae0cd44d54736ad0709ee78ace906b3594cae89c9d1"
        )
        expected_projection_items = 6_000
        expected_projection_bytes = 96_972
        expected_projection_sha256 = (
            "acc5ea16612d9cb19e0fe90a20bdf75b5403ccec804dc1d1609aa2e562e6e457"
        )
        multiline_source_nx, _multiline_source_fnx = _build_pair(
            source_node_count,
            source_edge_count,
            seed=source_seed,
            weighted=False,
        )
        multiline_output = io.BytesIO()
        nx.write_multiline_adjlist(multiline_source_nx, multiline_output)
        generated_lines = multiline_output.getvalue().splitlines(
            keepends=True
        )
        if len(generated_lines) < 4:
            raise RuntimeError(
                "read_multiline_adjlist writer emitted an incomplete payload"
            )
        recovered_header = (
            b"#hunt_unmeasured.py\n"
            b"# GMT Tue Jul 28 22:49:34 2026\n"
            b"# \n"
        )
        multiline_payload = recovered_header + b"".join(generated_lines[3:])
        payload_sha256 = hashlib.sha256(multiline_payload).hexdigest()
        if (
            len(multiline_payload) != expected_payload_bytes
            or not hmac.compare_digest(
                payload_sha256,
                expected_payload_sha256,
            )
        ):
            raise RuntimeError(
                "read_multiline_adjlist claim payload no longer matches "
                "its preregistered byte count and SHA-256"
            )
        multiline_path = _materialize_claim_payload(
            (
                "franken_networkx-claim-read_multiline_adjlist-"
                "80bc7e583290c224.mla"
            ),
            multiline_payload,
        )
        preflight_nx = nx.read_multiline_adjlist(multiline_path)
        preflight_fnx = fnx.read_multiline_adjlist(multiline_path)
        preflight_nx_bytes = canonical_bytes(preflight_nx)
        preflight_fnx_bytes = canonical_bytes(preflight_fnx)
        output_sha256 = hashlib.sha256(preflight_nx_bytes).hexdigest()
        projected_nx = sorted(preflight_nx.edges())
        projected_fnx = sorted(preflight_fnx.edges())
        projected_nx_bytes = canonical_bytes(projected_nx)
        projected_fnx_bytes = canonical_bytes(projected_fnx)
        projection_sha256 = hashlib.sha256(projected_nx_bytes).hexdigest()
        if preflight_nx_bytes != preflight_fnx_bytes:
            raise RuntimeError(
                "read_multiline_adjlist claim complete decoded graph "
                "diverged"
            )
        if projected_nx_bytes != projected_fnx_bytes:
            raise RuntimeError(
                "read_multiline_adjlist claim recovered sorted-edge "
                "projection diverged"
            )
        if (
            type(preflight_nx).__name__ != "Graph"
            or type(preflight_fnx).__name__ != "Graph"
            or preflight_nx.is_directed()
            or preflight_nx.is_multigraph()
            or preflight_nx.number_of_nodes() != expected_output_nodes
            or preflight_nx.number_of_edges() != expected_output_edges
            or len(preflight_nx_bytes) != expected_output_bytes
            or not hmac.compare_digest(output_sha256, expected_output_sha256)
            or len(projected_nx) != expected_projection_items
            or len(projected_nx_bytes) != expected_projection_bytes
            or not hmac.compare_digest(
                projection_sha256,
                expected_projection_sha256,
            )
        ):
            raise RuntimeError(
                "read_multiline_adjlist claim fixture no longer matches "
                "its preregistered decoded graph and projection"
            )
        EXTRA_PROVENANCE["claim_read_multiline_adjlist_fixture"] = {
            "publishing_commit": "87cf65e54a4e13a72a12c2bc7458655c7d4b3ac1",
            "recovered_harness_sha256": (
                "1114f244b93787b9e1d6a900633ccd93f3a09c91de8d669bde9ba75df5a611e3"
            ),
            "recovered_result_sha256": (
                "40040b7b90de11721263864fff0e3e79f260ca2779e16c8252784dc9236ef249"
            ),
            "recovered_builder_sha256": (
                "fb051cf48508ad56ee0c64103335090bd7866b12d65cb2e29d522cfa33b4cba1"
            ),
            "source_nodes": source_node_count,
            "source_edges": source_edge_count,
            "source_seed": source_seed,
            "source_weighted": False,
            "source_directed": False,
            "writer": "networkx.write_multiline_adjlist",
            "writer_parameters": "all omitted (NetworkX 3.6.1 defaults)",
            "recovered_writer_header": (
                "#hunt_unmeasured.py\\n"
                "# GMT Tue Jul 28 22:49:34 2026\\n"
                "# \\n"
            ),
            "payload_reconstruction": (
                "exact recovered three-line writer header plus unchanged "
                "NetworkX 3.6.1 writer body"
            ),
            "reader_input": "path",
            "reader_parameters": "path positional; all others omitted",
            "fixture_path": multiline_path,
            "python_hash_seed": 0,
            "payload_bytes": expected_payload_bytes,
            "payload_sha256": expected_payload_sha256,
            "output_type": "Graph",
            "output_nodes": expected_output_nodes,
            "output_edges": expected_output_edges,
            "output_canonical_bytes": expected_output_bytes,
            "complete_decoded_graph_sha256": expected_output_sha256,
            "timed_projection": "sorted(result.edges())",
            "projection_items": expected_projection_items,
            "projection_canonical_bytes": expected_projection_bytes,
            "projection_sha256": expected_projection_sha256,
        }
        rows.append(
            (
                "claim/read_multiline_adjlist "
                "source_n=1200 source_m=6000 source_seed=11 "
                "input=path then=sorted(edges) [nx/fnx]",
                lambda path=multiline_path: sorted(
                    nx.read_multiline_adjlist(path).edges()
                ),
                lambda path=multiline_path: sorted(
                    fnx.read_multiline_adjlist(path).edges()
                ),
            )
        )
    if "read_sparse6" in jobs:
        if os.environ.get("PYTHONHASHSEED") != "0":
            raise RuntimeError(
                "the read_sparse6 claim fixture requires PYTHONHASHSEED=0 "
                "because decoded graph and edge order are part of the "
                "public contract"
            )
        expected_payload_bytes = 1_238
        expected_payload_sha256 = (
            "3d6752e3c198cbfc2a21911408653a8682da3affc3c5850512baef0a5b09bdf7"
        )
        expected_output_nodes = 200
        expected_output_edges = 800
        expected_output_bytes = 22_009
        expected_output_sha256 = (
            "ea60802d53f9e77b41646c010b9178468d3e9ca8442307cf576687e0ba333c73"
        )
        expected_projection_bytes = 8_704
        expected_projection_sha256 = (
            "ed01731bc0e1c3142752f78ca678da69ccb2599730ba059a6b1d2f52e18ee151"
        )
        sparse6_output = io.BytesIO()
        nx.write_sparse6(reader_source_nx, sparse6_output)
        sparse6_payload = sparse6_output.getvalue()
        payload_sha256 = hashlib.sha256(sparse6_payload).hexdigest()
        if (
            len(sparse6_payload) != expected_payload_bytes
            or not hmac.compare_digest(
                payload_sha256,
                expected_payload_sha256,
            )
        ):
            raise RuntimeError(
                "read_sparse6 claim payload no longer matches its "
                "preregistered byte count and SHA-256"
            )
        sparse6_path = _materialize_claim_payload(
            "franken_networkx-claim-read_sparse6-3d6752e3c198cbfc.s6",
            sparse6_payload,
        )
        preflight_nx = nx.read_sparse6(sparse6_path)
        preflight_fnx = fnx.read_sparse6(sparse6_path)
        preflight_nx_bytes = canonical_bytes(preflight_nx)
        preflight_fnx_bytes = canonical_bytes(preflight_fnx)
        output_sha256 = hashlib.sha256(preflight_nx_bytes).hexdigest()
        projected_nx = sorted(preflight_nx.edges())
        projected_fnx = sorted(preflight_fnx.edges())
        projected_nx_bytes = canonical_bytes(projected_nx)
        projected_fnx_bytes = canonical_bytes(projected_fnx)
        projection_sha256 = hashlib.sha256(projected_nx_bytes).hexdigest()
        if preflight_nx_bytes != preflight_fnx_bytes:
            raise RuntimeError(
                "read_sparse6 claim complete decoded graph diverged"
            )
        if projected_nx_bytes != projected_fnx_bytes:
            raise RuntimeError(
                "read_sparse6 claim recovered sorted-edge projection diverged"
            )
        if (
            type(preflight_nx).__name__ != "Graph"
            or type(preflight_fnx).__name__ != "Graph"
            or preflight_nx.is_directed()
            or preflight_nx.is_multigraph()
            or preflight_nx.number_of_nodes() != expected_output_nodes
            or preflight_nx.number_of_edges() != expected_output_edges
            or len(preflight_nx_bytes) != expected_output_bytes
            or not hmac.compare_digest(output_sha256, expected_output_sha256)
            or len(projected_nx_bytes) != expected_projection_bytes
            or not hmac.compare_digest(
                projection_sha256,
                expected_projection_sha256,
            )
        ):
            raise RuntimeError(
                "read_sparse6 claim fixture no longer matches its "
                "preregistered decoded graph and projection"
            )
        EXTRA_PROVENANCE["claim_read_sparse6_fixture"] = {
            "publishing_commit": "87cf65e54a4e13a72a12c2bc7458655c7d4b3ac1",
            "recovered_harness_sha256": (
                "1114f244b93787b9e1d6a900633ccd93f3a09c91de8d669bde9ba75df5a611e3"
            ),
            "recovered_result_sha256": (
                "40040b7b90de11721263864fff0e3e79f260ca2779e16c8252784dc9236ef249"
            ),
            "recovered_builder_sha256": (
                "fb051cf48508ad56ee0c64103335090bd7866b12d65cb2e29d522cfa33b4cba1"
            ),
            "source_nodes": source_node_count,
            "source_edges": source_edge_count,
            "source_seed": source_seed,
            "source_weighted": False,
            "source_directed": False,
            "source_relabel": "networkx.convert_node_labels_to_integers",
            "writer": "networkx.write_sparse6",
            "writer_parameters": "all omitted (NetworkX 3.6.1 defaults)",
            "reader_input": "path",
            "reader_parameters": "path positional; all others omitted",
            "fixture_path": sparse6_path,
            "python_hash_seed": 0,
            "payload_bytes": expected_payload_bytes,
            "payload_sha256": expected_payload_sha256,
            "output_type": "Graph",
            "output_nodes": expected_output_nodes,
            "output_edges": expected_output_edges,
            "output_canonical_bytes": expected_output_bytes,
            "complete_decoded_graph_sha256": expected_output_sha256,
            "timed_projection": "sorted(result.edges())",
            "projection_canonical_bytes": expected_projection_bytes,
            "projection_sha256": expected_projection_sha256,
        }
        rows.append(
            (
                "claim/read_sparse6 "
                "source_n=200 source_m=800 source_seed=13 "
                "input=path then=sorted(edges) [nx/fnx]",
                lambda path=sparse6_path: sorted(
                    nx.read_sparse6(path).edges()
                ),
                lambda path=sparse6_path: sorted(
                    fnx.read_sparse6(path).edges()
                ),
            )
        )
    if "shortest_path_weighted" in jobs:
        if os.environ.get("PYTHONHASHSEED") != "0":
            raise RuntimeError(
                "the weighted shortest_path claim fixture requires "
                "PYTHONHASHSEED=0 because the selected equal-cost path is "
                "part of the public contract"
            )
        node_count = 2_000
        edge_count = 8_000
        seed = 7
        source = "0"
        target = "1999"
        weight = "weight"
        expected_input_bytes = 398_318
        expected_input_sha256 = (
            "03c62edb3bc632ec6fedf20e7a7061e42688aa1d655e9128dbc4980c2af54de0"
        )
        expected_path = (
            "0",
            "1610",
            "1531",
            "1102",
            "184",
            "452",
            "1999",
        )
        expected_edge_weights = (4, 1, 4, 5, 3, 2)
        expected_total_weight = 19
        expected_output_bytes = 51
        expected_output_sha256 = (
            "52a956a6868cbe0c02c56c5b963e2739aeb19a60b4d876fe747111db192676bb"
        )
        weighted_shortest_nx, weighted_shortest_fnx = _build_pair(
            node_count,
            edge_count,
            seed=seed,
            weighted=True,
        )
        input_nx_bytes = canonical_bytes(weighted_shortest_nx)
        input_fnx_bytes = canonical_bytes(weighted_shortest_fnx)
        input_sha256 = hashlib.sha256(input_nx_bytes).hexdigest()
        if input_nx_bytes != input_fnx_bytes:
            raise RuntimeError(
                "weighted shortest_path claim input graphs diverged"
            )
        if (
            len(input_nx_bytes) != expected_input_bytes
            or not hmac.compare_digest(input_sha256, expected_input_sha256)
        ):
            raise RuntimeError(
                "weighted shortest_path claim input no longer matches its "
                "preregistered canonical byte count and SHA-256"
            )

        preflight_nx = nx.shortest_path(
            weighted_shortest_nx,
            source,
            target,
            weight=weight,
        )
        preflight_fnx = fnx.shortest_path(
            weighted_shortest_fnx,
            source,
            target,
            weight=weight,
        )
        preflight_nx_bytes = canonical_bytes(preflight_nx)
        preflight_fnx_bytes = canonical_bytes(preflight_fnx)
        output_sha256 = hashlib.sha256(preflight_nx_bytes).hexdigest()
        edge_weights = tuple(
            weighted_shortest_nx[u][v][weight]
            for u, v in zip(preflight_nx, preflight_nx[1:])
        )
        if preflight_nx_bytes != preflight_fnx_bytes:
            raise RuntimeError(
                "weighted shortest_path claim complete ordered path diverged"
            )
        if (
            type(preflight_nx) is not list
            or tuple(preflight_nx) != expected_path
            or edge_weights != expected_edge_weights
            or sum(edge_weights) != expected_total_weight
            or len(preflight_nx_bytes) != expected_output_bytes
            or not hmac.compare_digest(output_sha256, expected_output_sha256)
        ):
            raise RuntimeError(
                "weighted shortest_path claim fixture no longer matches "
                "its preregistered complete ordered path"
            )
        EXTRA_PROVENANCE["claim_shortest_path_weighted_fixture"] = {
            "publishing_commit": "87cf65e54a4e13a72a12c2bc7458655c7d4b3ac1",
            "recovered_harness_sha256": (
                "40e03ac078cff1d930e5e3fa8232688becf1c1a67ab1cda6da93b88109e47a0f"
            ),
            "recovered_result_sha256": (
                "eb2400d0a022d02325310ade2fb97beeff35f90ccc35170bd094f0492564a415"
            ),
            "nodes": node_count,
            "edges": edge_count,
            "seed": seed,
            "weighted": True,
            "directed": False,
            "source": source,
            "target": target,
            "weight": weight,
            "method": "omitted (NetworkX default=dijkstra)",
            "parameters": (
                "source and target positional; weight=\"weight\"; "
                "method omitted"
            ),
            "weight_range_inclusive": [1, 20],
            "python_hash_seed": 0,
            "input_canonical_bytes": expected_input_bytes,
            "input_sha256": expected_input_sha256,
            "path": list(expected_path),
            "path_nodes": len(expected_path),
            "path_edges": len(expected_edge_weights),
            "path_edge_weights": list(expected_edge_weights),
            "path_total_weight": expected_total_weight,
            "output_canonical_bytes": expected_output_bytes,
            "complete_ordered_path_sha256": expected_output_sha256,
        }
        rows.append(
            (
                "claim/shortest_path(weighted) "
                "n=2000 m=8000 seed=7 source=\"0\" target=\"1999\" "
                "weight=\"weight\" method=default [nx/fnx]",
                lambda graph=weighted_shortest_nx, src=source, dst=target,
                weight_name=weight: nx.shortest_path(
                    graph,
                    src,
                    dst,
                    weight=weight_name,
                ),
                lambda graph=weighted_shortest_fnx, src=source, dst=target,
                weight_name=weight: fnx.shortest_path(
                    graph,
                    src,
                    dst,
                    weight=weight_name,
                ),
            )
        )
    if "single_pair_shortest_path" in jobs:
        if os.environ.get("PYTHONHASHSEED") != "0":
            raise RuntimeError(
                "the single_pair_shortest_path claim fixture requires "
                "PYTHONHASHSEED=0 because tie-selected path order is part "
                "of the public contract"
            )
        node_count = 2_000
        edge_count = 8_000
        seed = 7
        source = "0"
        target = "1999"
        expected_input_bytes = 273_938
        expected_input_sha256 = (
            "03635cb95fcf023b79a245e0dc38125225ba216e6eb77a9270ef5121024f6164"
        )
        expected_path = ("0", "192", "496", "1859", "1999")
        expected_output_bytes = 35
        expected_output_sha256 = (
            "3d12fd29fa77af06bee45cffb008230978741861778d85719ec5936635d6749b"
        )
        single_pair_nx, single_pair_fnx = _build_pair(
            node_count,
            edge_count,
            seed=seed,
            weighted=False,
        )
        input_nx_bytes = canonical_bytes(single_pair_nx)
        input_fnx_bytes = canonical_bytes(single_pair_fnx)
        input_sha256 = hashlib.sha256(input_nx_bytes).hexdigest()
        if input_nx_bytes != input_fnx_bytes:
            raise RuntimeError(
                "single_pair_shortest_path claim input graphs diverged"
            )
        if (
            len(input_nx_bytes) != expected_input_bytes
            or not hmac.compare_digest(input_sha256, expected_input_sha256)
        ):
            raise RuntimeError(
                "single_pair_shortest_path claim input no longer matches "
                "its preregistered canonical byte count and SHA-256"
            )

        preflight_nx = nx.shortest_path(
            single_pair_nx,
            source,
            target,
        )
        preflight_fnx = fnx.shortest_path(
            single_pair_fnx,
            source,
            target,
        )
        preflight_nx_bytes = canonical_bytes(preflight_nx)
        preflight_fnx_bytes = canonical_bytes(preflight_fnx)
        output_sha256 = hashlib.sha256(preflight_nx_bytes).hexdigest()
        if preflight_nx_bytes != preflight_fnx_bytes:
            raise RuntimeError(
                "single_pair_shortest_path complete ordered path diverged"
            )
        if (
            tuple(preflight_nx) != expected_path
            or len(preflight_nx_bytes) != expected_output_bytes
            or not hmac.compare_digest(output_sha256, expected_output_sha256)
        ):
            raise RuntimeError(
                "single_pair_shortest_path claim fixture no longer matches "
                "its preregistered complete ordered path"
            )
        EXTRA_PROVENANCE["claim_single_pair_shortest_path_fixture"] = {
            "nodes": node_count,
            "edges": edge_count,
            "seed": seed,
            "weighted": False,
            "source": source,
            "target": target,
            "weight": None,
            "method": "omitted (NetworkX default=dijkstra)",
            "python_hash_seed": 0,
            "input_canonical_bytes": expected_input_bytes,
            "input_sha256": expected_input_sha256,
            "path": list(expected_path),
            "path_edges": len(expected_path) - 1,
            "output_canonical_bytes": expected_output_bytes,
            "complete_output_sha256": expected_output_sha256,
        }
        rows.append(
            (
                "claim/single_pair_shortest_path "
                'n=2000 m=8000 seed=7 source="0" target="1999" '
                "weight=None method=default [nx/fnx]",
                lambda graph=single_pair_nx, src=source, dst=target: (
                    nx.shortest_path(graph, src, dst)
                ),
                lambda graph=single_pair_fnx, src=source, dst=target: (
                    fnx.shortest_path(graph, src, dst)
                ),
            )
        )
    if "single_source_shortest_path_length" in jobs:
        if os.environ.get("PYTHONHASHSEED") != "0":
            raise RuntimeError(
                "the single_source_shortest_path_length claim fixture requires "
                "PYTHONHASHSEED=0 because output mapping order is part of the "
                "public contract"
            )
        node_count = 2_000
        edge_count = 8_000
        seed = 7
        source = "0"
        expected_input_bytes = 273_938
        expected_input_sha256 = (
            "03635cb95fcf023b79a245e0dc38125225ba216e6eb77a9270ef5121024f6164"
        )
        expected_output_items = 1_999
        expected_output_bytes = 24_887
        expected_output_sha256 = (
            "86b41dbb4e78476d3551f6775092cb2170b44a8333bfd2ac5e489f7b13edc453"
        )
        lengths_nx, lengths_fnx = _build_pair(
            node_count,
            edge_count,
            seed=seed,
            weighted=False,
        )
        input_nx_bytes = canonical_bytes(lengths_nx)
        input_fnx_bytes = canonical_bytes(lengths_fnx)
        input_sha256 = hashlib.sha256(input_nx_bytes).hexdigest()
        if input_nx_bytes != input_fnx_bytes:
            raise RuntimeError(
                "single_source_shortest_path_length claim input graphs diverged"
            )
        if (
            len(input_nx_bytes) != expected_input_bytes
            or not hmac.compare_digest(input_sha256, expected_input_sha256)
        ):
            raise RuntimeError(
                "single_source_shortest_path_length claim input no longer "
                "matches its preregistered canonical byte count and SHA-256"
            )

        preflight_nx = dict(
            nx.single_source_shortest_path_length(lengths_nx, source)
        )
        preflight_fnx = dict(
            fnx.single_source_shortest_path_length(lengths_fnx, source)
        )
        preflight_nx_bytes = canonical_bytes(preflight_nx)
        preflight_fnx_bytes = canonical_bytes(preflight_fnx)
        output_sha256 = hashlib.sha256(preflight_nx_bytes).hexdigest()
        if preflight_nx_bytes != preflight_fnx_bytes:
            raise RuntimeError(
                "single_source_shortest_path_length claim complete output diverged"
            )
        if (
            len(preflight_nx) != expected_output_items
            or len(preflight_nx_bytes) != expected_output_bytes
            or not hmac.compare_digest(output_sha256, expected_output_sha256)
        ):
            raise RuntimeError(
                "single_source_shortest_path_length claim fixture no longer "
                "matches its preregistered complete ordered output"
            )
        EXTRA_PROVENANCE["claim_single_source_shortest_path_length_fixture"] = {
            "nodes": node_count,
            "edges": edge_count,
            "seed": seed,
            "source": source,
            "cutoff": None,
            "python_hash_seed": 0,
            "input_canonical_bytes": expected_input_bytes,
            "input_sha256": expected_input_sha256,
            "output_items": expected_output_items,
            "output_canonical_bytes": expected_output_bytes,
            "complete_output_sha256": expected_output_sha256,
        }
        rows.append(
            (
                "claim/single_source_shortest_path_length "
                'n=2000 m=8000 seed=7 source="0" cutoff=None [nx/fnx]',
                lambda: dict(
                    nx.single_source_shortest_path_length(lengths_nx, source)
                ),
                lambda: dict(
                    fnx.single_source_shortest_path_length(lengths_fnx, source)
                ),
            )
        )
    if "subgraph_view_edges" in jobs:
        if os.environ.get("PYTHONHASHSEED") != "0":
            raise RuntimeError(
                "the subgraph_view_edges claim fixture requires "
                "PYTHONHASHSEED=0 because view and edge order are part of "
                "the public contract"
            )
        node_count = 2_000
        edge_count = 8_000
        seed = 7
        selected_nodes = [
            str(index)
            for index in range(0, node_count, 4)
        ]
        expected_selected_items = 500
        expected_selector_bytes = 3_722
        expected_selector_sha256 = (
            "1e2309408844387cafef1e27da619296d79adec5550e8fb4d7ba3a7ec6d04733"
        )
        expected_input_bytes = 273_938
        expected_input_sha256 = (
            "03635cb95fcf023b79a245e0dc38125225ba216e6eb77a9270ef5121024f6164"
        )
        expected_view_nodes = 500
        expected_view_edges = 497
        expected_view_bytes = 25_050
        expected_view_sha256 = (
            "62e0dcf1d54a45ec2083479afccda5f25ed87751a94a0792c2ba0f14b86720c6"
        )
        expected_output_edges = 497
        expected_output_bytes = 8_349
        expected_output_sha256 = (
            "32b6cc468804d8ec28717da2e85bce6bdb45cca399b214461cd09134db122004"
        )
        subgraph_nx, subgraph_fnx = _build_pair(
            node_count,
            edge_count,
            seed=seed,
            weighted=False,
        )
        selector_bytes = canonical_bytes(selected_nodes)
        selector_sha256 = hashlib.sha256(selector_bytes).hexdigest()
        if (
            len(selected_nodes) != expected_selected_items
            or len(selector_bytes) != expected_selector_bytes
            or not hmac.compare_digest(
                selector_sha256,
                expected_selector_sha256,
            )
        ):
            raise RuntimeError(
                "subgraph_view_edges selector no longer matches its "
                "preregistered item count, byte count, and SHA-256"
            )

        input_nx_bytes = canonical_bytes(subgraph_nx)
        input_fnx_bytes = canonical_bytes(subgraph_fnx)
        input_sha256 = hashlib.sha256(input_nx_bytes).hexdigest()
        if input_nx_bytes != input_fnx_bytes:
            raise RuntimeError(
                "subgraph_view_edges claim input graphs diverged"
            )
        if (
            len(input_nx_bytes) != expected_input_bytes
            or not hmac.compare_digest(input_sha256, expected_input_sha256)
        ):
            raise RuntimeError(
                "subgraph_view_edges claim input no longer matches its "
                "preregistered canonical byte count and SHA-256"
            )

        preflight_view_nx = subgraph_nx.subgraph(selected_nodes)
        preflight_view_fnx = subgraph_fnx.subgraph(selected_nodes)
        view_nx_bytes = canonical_bytes(preflight_view_nx)
        view_fnx_bytes = canonical_bytes(preflight_view_fnx)
        view_sha256 = hashlib.sha256(view_nx_bytes).hexdigest()
        if view_nx_bytes != view_fnx_bytes:
            raise RuntimeError(
                "subgraph_view_edges complete ordered view diverged"
            )
        if (
            preflight_view_nx.number_of_nodes() != expected_view_nodes
            or preflight_view_nx.number_of_edges() != expected_view_edges
            or len(view_nx_bytes) != expected_view_bytes
            or not hmac.compare_digest(view_sha256, expected_view_sha256)
        ):
            raise RuntimeError(
                "subgraph_view_edges claim fixture no longer matches its "
                "preregistered complete ordered view"
            )

        preflight_nx = list(preflight_view_nx.edges())
        preflight_fnx = list(preflight_view_fnx.edges())
        preflight_nx_bytes = canonical_bytes(preflight_nx)
        preflight_fnx_bytes = canonical_bytes(preflight_fnx)
        output_sha256 = hashlib.sha256(preflight_nx_bytes).hexdigest()
        if preflight_nx_bytes != preflight_fnx_bytes:
            raise RuntimeError(
                "subgraph_view_edges complete ordered edge list diverged"
            )
        if (
            len(preflight_nx) != expected_output_edges
            or len(preflight_nx_bytes) != expected_output_bytes
            or not hmac.compare_digest(output_sha256, expected_output_sha256)
        ):
            raise RuntimeError(
                "subgraph_view_edges claim fixture no longer matches its "
                "preregistered complete ordered edge list"
            )
        EXTRA_PROVENANCE["claim_subgraph_view_edges_fixture"] = {
            "nodes": node_count,
            "edges": edge_count,
            "seed": seed,
            "weighted": False,
            "selection": "str(index) for index in range(0, 2000, 4)",
            "selected_items": expected_selected_items,
            "selector_canonical_bytes": expected_selector_bytes,
            "selector_sha256": expected_selector_sha256,
            "python_hash_seed": 0,
            "input_canonical_bytes": expected_input_bytes,
            "input_sha256": expected_input_sha256,
            "view_nodes": expected_view_nodes,
            "view_edges": expected_view_edges,
            "view_canonical_bytes": expected_view_bytes,
            "complete_view_sha256": expected_view_sha256,
            "output_edges": expected_output_edges,
            "output_canonical_bytes": expected_output_bytes,
            "complete_output_sha256": expected_output_sha256,
        }
        rows.append(
            (
                "claim/subgraph(view)->edges "
                "n=2000 m=8000 seed=7 selected=range(0,2000,4) [nx/fnx]",
                lambda graph=subgraph_nx, nodes=selected_nodes: list(
                    graph.subgraph(nodes).edges()
                ),
                lambda graph=subgraph_fnx, nodes=selected_nodes: list(
                    graph.subgraph(nodes).edges()
                ),
            )
        )
    if "to_scipy_sparse_array" in jobs:
        if os.environ.get("PYTHONHASHSEED") != "0":
            raise RuntimeError(
                "the to_scipy_sparse_array claim fixture requires "
                "PYTHONHASHSEED=0 because default node order is part of "
                "the public contract"
            )
        node_count = 600
        edge_count = 3_000
        seed = 5
        expected_input_bytes = 142_062
        expected_input_sha256 = (
            "593355561a9d5fcaf7a4a9673eb5fd1a9164531173724078bc504d1300233470"
        )
        expected_sparse_shape = (600, 600)
        expected_sparse_format = "csr"
        expected_sparse_dtype = "<i8"
        expected_sparse_nnz = 6_000
        expected_sparse_state_bytes = 202_028
        expected_sparse_state_sha256 = (
            "5d073aa0f7ae5016b49ca26e24d85947af97c603475dfe8800e3b0807311c4dd"
        )
        expected_data_bytes = 48_000
        expected_data_sha256 = (
            "a6359e5cc9a2eab1c8da1ba91fc12524c670d12312de39a8b4cd9628f8c25c5f"
        )
        expected_indices_bytes = 48_000
        expected_indices_sha256 = (
            "ddd0b3fead65ceb09fbc3a4cc267006da27f0e84c51e41d71ebfae8a4ac8b729"
        )
        expected_indptr_bytes = 4_808
        expected_indptr_sha256 = (
            "c546597694cb1dd52923ead2c7577e6cbf823aa59c3ec5e2ae7dd81c431f5b71"
        )
        expected_dense_dtype = "<i8"
        expected_dense_elements = 360_000
        expected_dense_sum = 62_592
        expected_dense_raw_bytes = 2_880_000
        expected_dense_raw_sha256 = (
            "339a92a60ca9a406b7815b9b01d6b1b1b335e4530665930be5d215be9ddfa7f1"
        )
        expected_output_bytes = 1_804_464
        expected_output_sha256 = (
            "dbb685fac46c14ffdf75e8801021f07e086a6e8bba0d64f91d9669cfa16a49b0"
        )
        sparse_nx, sparse_fnx = _build_pair(
            node_count,
            edge_count,
            seed=seed,
            weighted=True,
        )
        input_nx_bytes = canonical_bytes(sparse_nx)
        input_fnx_bytes = canonical_bytes(sparse_fnx)
        input_sha256 = hashlib.sha256(input_nx_bytes).hexdigest()
        if input_nx_bytes != input_fnx_bytes:
            raise RuntimeError(
                "to_scipy_sparse_array claim input graphs diverged"
            )
        if (
            len(input_nx_bytes) != expected_input_bytes
            or not hmac.compare_digest(input_sha256, expected_input_sha256)
        ):
            raise RuntimeError(
                "to_scipy_sparse_array claim input no longer matches its "
                "preregistered canonical byte count and SHA-256"
            )

        preflight_sparse_nx = nx.to_scipy_sparse_array(sparse_nx)
        preflight_sparse_fnx = fnx.to_scipy_sparse_array(sparse_fnx)

        def sparse_state(matrix):
            return {
                "module": type(matrix).__module__,
                "type": type(matrix).__name__,
                "format": matrix.format,
                "shape": list(matrix.shape),
                "dtype": matrix.dtype.str,
                "nnz": matrix.nnz,
                "has_sorted_indices": matrix.has_sorted_indices,
                "has_canonical_format": matrix.has_canonical_format,
                "data_dtype": matrix.data.dtype.str,
                "data_shape": list(matrix.data.shape),
                "data_hex": matrix.data.tobytes().hex(),
                "indices_dtype": matrix.indices.dtype.str,
                "indices_shape": list(matrix.indices.shape),
                "indices_hex": matrix.indices.tobytes().hex(),
                "indptr_dtype": matrix.indptr.dtype.str,
                "indptr_shape": list(matrix.indptr.shape),
                "indptr_hex": matrix.indptr.tobytes().hex(),
            }

        sparse_nx_bytes = canonical_bytes(sparse_state(preflight_sparse_nx))
        sparse_fnx_bytes = canonical_bytes(sparse_state(preflight_sparse_fnx))
        sparse_state_sha256 = hashlib.sha256(sparse_nx_bytes).hexdigest()
        data_bytes = preflight_sparse_nx.data.tobytes()
        indices_bytes = preflight_sparse_nx.indices.tobytes()
        indptr_bytes = preflight_sparse_nx.indptr.tobytes()
        if sparse_nx_bytes != sparse_fnx_bytes:
            raise RuntimeError(
                "to_scipy_sparse_array complete CSR state diverged"
            )
        if (
            preflight_sparse_nx.shape != expected_sparse_shape
            or preflight_sparse_nx.format != expected_sparse_format
            or preflight_sparse_nx.dtype.str != expected_sparse_dtype
            or preflight_sparse_nx.nnz != expected_sparse_nnz
            or not preflight_sparse_nx.has_sorted_indices
            or not preflight_sparse_nx.has_canonical_format
            or len(sparse_nx_bytes) != expected_sparse_state_bytes
            or not hmac.compare_digest(
                sparse_state_sha256,
                expected_sparse_state_sha256,
            )
            or len(data_bytes) != expected_data_bytes
            or not hmac.compare_digest(
                hashlib.sha256(data_bytes).hexdigest(),
                expected_data_sha256,
            )
            or len(indices_bytes) != expected_indices_bytes
            or not hmac.compare_digest(
                hashlib.sha256(indices_bytes).hexdigest(),
                expected_indices_sha256,
            )
            or len(indptr_bytes) != expected_indptr_bytes
            or not hmac.compare_digest(
                hashlib.sha256(indptr_bytes).hexdigest(),
                expected_indptr_sha256,
            )
        ):
            raise RuntimeError(
                "to_scipy_sparse_array claim fixture no longer matches its "
                "preregistered complete CSR state"
            )

        preflight_nx = preflight_sparse_nx.toarray()
        preflight_fnx = preflight_sparse_fnx.toarray()
        preflight_nx_bytes = canonical_bytes(preflight_nx)
        preflight_fnx_bytes = canonical_bytes(preflight_fnx)
        output_sha256 = hashlib.sha256(preflight_nx_bytes).hexdigest()
        dense_raw_bytes = preflight_nx.tobytes()
        if preflight_nx_bytes != preflight_fnx_bytes:
            raise RuntimeError(
                "to_scipy_sparse_array claim complete dense output diverged"
            )
        if (
            preflight_nx.shape != expected_sparse_shape
            or preflight_nx.dtype.str != expected_dense_dtype
            or preflight_nx.size != expected_dense_elements
            or preflight_nx.sum() != expected_dense_sum
            or len(dense_raw_bytes) != expected_dense_raw_bytes
            or not hmac.compare_digest(
                hashlib.sha256(dense_raw_bytes).hexdigest(),
                expected_dense_raw_sha256,
            )
            or len(preflight_nx_bytes) != expected_output_bytes
            or not hmac.compare_digest(output_sha256, expected_output_sha256)
        ):
            raise RuntimeError(
                "to_scipy_sparse_array claim fixture no longer matches its "
                "preregistered complete dense output"
            )
        EXTRA_PROVENANCE["claim_to_scipy_sparse_array_fixture"] = {
            "nodes": node_count,
            "edges": edge_count,
            "seed": seed,
            "weighted": True,
            "directed": False,
            "weight_range_inclusive": [1, 20],
            "nodelist": None,
            "dtype": None,
            "weight": "weight",
            "format": "csr",
            "parameters": "all omitted (NetworkX 3.6.1 defaults)",
            "timed_projection": "to_scipy_sparse_array(graph).toarray()",
            "python_hash_seed": 0,
            "input_canonical_bytes": expected_input_bytes,
            "input_sha256": expected_input_sha256,
            "sparse_shape": list(expected_sparse_shape),
            "sparse_format": expected_sparse_format,
            "sparse_dtype": expected_sparse_dtype,
            "sparse_nnz": expected_sparse_nnz,
            "sparse_state_canonical_bytes": expected_sparse_state_bytes,
            "complete_sparse_state_sha256": expected_sparse_state_sha256,
            "sparse_data_bytes": expected_data_bytes,
            "sparse_data_sha256": expected_data_sha256,
            "sparse_indices_bytes": expected_indices_bytes,
            "sparse_indices_sha256": expected_indices_sha256,
            "sparse_indptr_bytes": expected_indptr_bytes,
            "sparse_indptr_sha256": expected_indptr_sha256,
            "dense_dtype": expected_dense_dtype,
            "dense_elements": expected_dense_elements,
            "dense_sum": expected_dense_sum,
            "dense_raw_bytes": expected_dense_raw_bytes,
            "dense_raw_sha256": expected_dense_raw_sha256,
            "output_canonical_bytes": expected_output_bytes,
            "complete_output_sha256": expected_output_sha256,
        }
        rows.append(
            (
                "claim/to_scipy_sparse_array "
                "n=600 m=3000 seed=5 weights=1..20 "
                "parameters=defaults then=toarray [nx/fnx]",
                lambda graph=sparse_nx: (
                    nx.to_scipy_sparse_array(graph).toarray()
                ),
                lambda graph=sparse_fnx: (
                    fnx.to_scipy_sparse_array(graph).toarray()
                ),
            )
        )
    return rows


def suite_cold_after_mutation_cc():
    """Re-measure thp6w S4's whole public operation against live NetworkX."""
    import networkx as nx
    import franken_networkx as fnx

    if nx.__version__ != "3.6.1":
        raise RuntimeError(
            "cold-after-mutation-cc requires live NetworkX 3.6.1; "
            f"loaded {nx.__version__} from {nx.__file__}"
        )

    node_count = 20_000
    chord_count = 3 * node_count
    parallel_count = 1_000
    mutation = (0, node_count // 2, (1 << 63) - 1)
    edges = [
        (node, (node + 1) % node_count)
        for node in range(node_count)
    ]
    for index in range(chord_count):
        left = (index * 7_919 + 17) % node_count
        right = (index * 15_407 + 6_119) % node_count
        if left == right:
            right = (right + 1) % node_count
        edges.append((left, right))
    edges.extend(
        (node, (node + 1) % node_count)
        for node in range(parallel_count)
    )

    edge_bytes = json.dumps(
        edges,
        separators=(",", ":"),
    ).encode()
    EXTRA_PROVENANCE["cold_after_mutation_fixture"] = {
        "nodes": node_count,
        "cycle_edges": node_count,
        "chord_edges": chord_count,
        "parallel_edges": parallel_count,
        "total_edges": len(edges),
        "chord_formula": {
            "left": "(index * 7919 + 17) % 20000",
            "right": "(index * 15407 + 6119) % 20000; +1 if self-loop",
        },
        "edge_stream_sha256": hashlib.sha256(edge_bytes).hexdigest(),
        "mutation_edge": list(mutation),
        "operation": (
            "add explicit-key edge; remove the same edge; "
            "materialize connected_components"
        ),
    }

    def build_pair():
        graph_nx = nx.MultiGraph()
        graph_fnx = fnx.MultiGraph()
        nodes = range(node_count)
        graph_nx.add_nodes_from(nodes)
        graph_fnx.add_nodes_from(nodes)
        graph_nx.add_edges_from(edges)
        graph_fnx.add_edges_from(edges)
        if graph_nx.number_of_edges() != len(edges):
            raise RuntimeError("NetworkX fixture edge count changed")
        if graph_fnx.number_of_edges() != len(edges):
            raise RuntimeError("FrankenNetworkX fixture edge count changed")
        return graph_nx, graph_fnx

    graph_nx, graph_fnx = build_pair()

    def whole_job(module, graph):
        left, right, key = mutation
        graph.add_edge(left, right, key=key)
        graph.remove_edge(left, right, key=key)
        return list(module.connected_components(graph))

    arm_nx = lambda: whole_job(nx, graph_nx)
    arm_fnx = lambda: whole_job(fnx, graph_fnx)

    # The measured state is explicitly warm before the single-edge mutation.
    # S4's mechanism is retaining that warm integer-adjacency memo through the
    # add/remove pair; its pre-S4 comparator rebuilt it after the revision bump.
    list(nx.connected_components(graph_nx))
    list(fnx.connected_components(graph_fnx))
    if canonical_bytes(arm_nx()) != canonical_bytes(arm_fnx()):
        raise RuntimeError("cold-after-mutation fixture parity failed")

    return [
        (
            "MultiGraph add+remove then connected_components "
            "n=20000 m=81000 [nx/fnx]",
            arm_nx,
            arm_fnx,
        ),
    ]


REALISTIC_DATASET_URL = "https://snap.stanford.edu/data/ca-AstroPh.txt.gz"
REALISTIC_DATASET_PAGE = "https://snap.stanford.edu/data/ca-AstroPh.html"
REALISTIC_DATASET_SHA256 = (
    "51bf1e2cace269b884481a8502474efa67c0fd01d998ff7f5a154d7d3e527f27"
)


def _prepare_realistic_fixtures(sizes: tuple[int, ...]) -> dict[int, Path]:
    """Materialize deterministic induced prefixes of the real SNAP graph."""
    cache_dir = Path(
        os.environ.get(
            "FNX_REALISTIC_CACHE_DIR",
            "/data/tmp/franken_networkx-realistic",
        )
    )
    source_override = os.environ.get("FNX_REALISTIC_DATASET")
    source_path = (
        Path(source_override)
        if source_override is not None
        else cache_dir / "ca-AstroPh.txt.gz"
    )
    if not source_path.exists():
        if source_override is not None:
            raise FileNotFoundError(f"FNX_REALISTIC_DATASET does not exist: {source_path}")
        cache_dir.mkdir(parents=True, exist_ok=True)
        request = urllib.request.Request(
            REALISTIC_DATASET_URL,
            headers={"User-Agent": "franken-networkx-perf-harness/1"},
        )
        # The URL is a module constant with an HTTPS scheme and fixed SNAP host.
        with urllib.request.urlopen(request, timeout=60) as response:  # nosec B310
            downloaded = response.read()
        downloaded_sha = hashlib.sha256(downloaded).hexdigest()
        if not hmac.compare_digest(downloaded_sha, REALISTIC_DATASET_SHA256):
            raise RuntimeError(
                "downloaded ca-AstroPh archive has unexpected SHA-256: "
                f"{downloaded_sha}"
            )
        with source_path.open("xb") as handle:
            handle.write(downloaded)

    source_payload = source_path.read_bytes()
    source_sha = hashlib.sha256(source_payload).hexdigest()
    if not hmac.compare_digest(source_sha, REALISTIC_DATASET_SHA256):
        raise RuntimeError(
            f"ca-AstroPh source SHA-256 mismatch at {source_path}: {source_sha}"
        )

    node_order: list[str] = []
    seen_nodes: set[str] = set()
    seen_edges: set[tuple[str, str]] = set()
    unique_rows: list[tuple[str, str]] = []
    source_text = gzip.decompress(source_payload).decode("ascii")
    for line in source_text.splitlines():
        if not line or line.startswith("#"):
            continue
        u, v = line.split()[:2]
        for node in (u, v):
            if node not in seen_nodes:
                seen_nodes.add(node)
                node_order.append(node)
        edge_key = (u, v) if u <= v else (v, u)
        if edge_key not in seen_edges:
            seen_edges.add(edge_key)
            unique_rows.append((u, v))

    if max(sizes) > len(node_order):
        raise ValueError(
            f"requested n={max(sizes)} exceeds ca-AstroPh's {len(node_order)} nodes"
        )

    fixture_paths: dict[int, Path] = {}
    fixture_metadata = []
    cache_dir.mkdir(parents=True, exist_ok=True)
    for size in sizes:
        selected = set(node_order[:size])
        edges = [
            (u, v)
            for u, v in unique_rows
            if u in selected and v in selected
        ]
        header = (
            f"# SNAP ca-AstroPh induced prefix n={size}\n"
            f"# source_sha256={source_sha}\n"
            f"# nodes={size} undirected_edges={len(edges)}\n"
        )
        raw = (
            header + "".join(f"{u} {v}\n" for u, v in edges)
        ).encode("ascii")
        payload = gzip.compress(raw, compresslevel=9, mtime=0)
        fixture_path = cache_dir / f"ca-AstroPh-n{size}.txt.gz"
        if fixture_path.exists():
            if fixture_path.read_bytes() != payload:
                raise RuntimeError(
                    f"existing realistic fixture differs: {fixture_path}"
                )
        else:
            with fixture_path.open("xb") as handle:
                handle.write(payload)
        fixture_sha = hashlib.sha256(payload).hexdigest()
        fixture_paths[size] = fixture_path
        fixture_metadata.append(
            {
                "n": size,
                "undirected_edges": len(edges),
                "bytes": len(payload),
                "sha256": fixture_sha,
                "path": str(fixture_path),
            }
        )

    EXTRA_PROVENANCE.update(
        {
            "realistic_dataset_page": REALISTIC_DATASET_PAGE,
            "realistic_dataset_url": REALISTIC_DATASET_URL,
            "realistic_dataset_source_path": str(source_path),
            "realistic_dataset_source_sha256": source_sha,
            "realistic_dataset_fixtures": fixture_metadata,
        }
    )
    return fixture_paths


def _load_real_graph(module, path: Path, expected_nodes: int):
    graph = module.read_edgelist(
        str(path),
        comments="#",
        create_using=module.Graph,
        nodetype=str,
        data=False,
    )
    expected_module = module.__name__.split(".", maxsplit=1)[0]
    actual_module = type(graph).__module__
    if not actual_module.startswith(expected_module):
        raise RuntimeError(
            f"{module.__name__} arm dispatch trap: got graph type {actual_module}"
        )
    if graph.number_of_nodes() != expected_nodes:
        raise RuntimeError(
            f"{path} loaded {graph.number_of_nodes()} nodes, expected {expected_nodes}"
        )
    self_loops = list(module.selfloop_edges(graph))
    graph.remove_edges_from(self_loops)
    return graph, len(self_loops)


def _write_edgelist_bytes(module, graph) -> bytes:
    output = io.BytesIO()
    module.write_edgelist(graph, output, data=False)
    return output.getvalue()


def _pack_realistic_result(summary: dict, *serialized_graphs: bytes) -> bytes:
    summary_bytes = json.dumps(
        summary,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()
    return summary_bytes + b"\n--serialized-graph--\n" + (
        b"\n--serialized-graph--\n".join(serialized_graphs)
    )


def _workload_collaboration_core(module, path: Path, size: int) -> bytes:
    """Load, find components/cores, extract a cohort, and export it."""
    from collections import Counter

    graph, self_loops_removed = _load_real_graph(module, path, size)
    components = [sorted(component) for component in module.connected_components(graph)]
    components.sort(key=lambda nodes: (-len(nodes), nodes[0] if nodes else ""))
    cores = module.core_number(graph)
    ranked = sorted(graph, key=lambda node: (-cores[node], node))
    cohort_nodes = ranked[: max(50, size // 10)]
    cohort = graph.subgraph(cohort_nodes).copy()
    summary = {
        "job": "collaboration-core-export",
        "nodes": graph.number_of_nodes(),
        "edges": graph.number_of_edges(),
        "self_loops_removed": self_loops_removed,
        "component_count": len(components),
        "largest_component_nodes": len(components[0]),
        "component_sizes_top10": [len(nodes) for nodes in components[:10]],
        "max_core": max(cores.values()),
        "core_histogram": sorted(Counter(cores.values()).items()),
        "cohort_nodes": cohort.number_of_nodes(),
        "cohort_edges": cohort.number_of_edges(),
    }
    return _pack_realistic_result(
        summary,
        _write_edgelist_bytes(module, cohort),
    )


def _workload_hub_routing(module, path: Path, size: int) -> bytes:
    """Load, route from the busiest author, extract its radius, and export."""
    from collections import Counter

    graph, self_loops_removed = _load_real_graph(module, path, size)
    ranked = sorted(
        graph,
        key=lambda node: (-int(graph.degree[node]), node),
    )
    hub = ranked[0]
    lengths = dict(module.single_source_shortest_path_length(graph, hub))
    tree = module.bfs_tree(graph, hub)
    local_nodes = sorted(node for node, distance in lengths.items() if distance <= 2)
    local = graph.subgraph(local_nodes).copy()
    summary = {
        "job": "hub-routing-export",
        "nodes": graph.number_of_nodes(),
        "edges": graph.number_of_edges(),
        "self_loops_removed": self_loops_removed,
        "hub": hub,
        "hub_degree": int(graph.degree[hub]),
        "reachable_nodes": len(lengths),
        "distance_histogram": sorted(Counter(lengths.values()).items()),
        "bfs_tree_edges": tree.number_of_edges(),
        "radius2_nodes": local.number_of_nodes(),
        "radius2_edges": local.number_of_edges(),
    }
    return _pack_realistic_result(
        summary,
        _write_edgelist_bytes(module, tree),
        _write_edgelist_bytes(module, local),
    )


def _workload_rich_club(module, path: Path, size: int) -> bytes:
    """Load, compute rich-club/onion structure, extract leaders, and export."""
    from collections import Counter

    graph, self_loops_removed = _load_real_graph(module, path, size)
    rich_club = module.rich_club_coefficient(graph, normalized=False)
    layers = module.onion_layers(graph)
    ranked = sorted(graph, key=lambda node: (-layers[node], node))
    cohort_nodes = ranked[: max(50, size // 10)]
    cohort = graph.subgraph(cohort_nodes).copy()
    summary = {
        "job": "rich-club-onion-export",
        "nodes": graph.number_of_nodes(),
        "edges": graph.number_of_edges(),
        "self_loops_removed": self_loops_removed,
        "rich_club": sorted((int(degree), value) for degree, value in rich_club.items()),
        "max_onion_layer": max(layers.values()),
        "onion_histogram": sorted(Counter(layers.values()).items()),
        "cohort_nodes": cohort.number_of_nodes(),
        "cohort_edges": cohort.number_of_edges(),
    }
    return _pack_realistic_result(
        summary,
        _write_edgelist_bytes(module, cohort),
    )


def _workload_link_recommendation(module, path: Path, size: int) -> bytes:
    """Load, rank a core cohort, score missing links, and export the report."""
    graph, self_loops_removed = _load_real_graph(module, path, size)
    cores = module.core_number(graph)
    ranked = sorted(
        graph,
        key=lambda node: (-cores[node], -int(graph.degree[node]), node),
    )
    cohort_nodes = ranked[: min(384, size)]
    pair_limit = min(2_000, max(500, size // 2))
    pairs = []
    for index, u in enumerate(cohort_nodes):
        for v in cohort_nodes[index + 1 :]:
            if not graph.has_edge(u, v):
                pairs.append((u, v))
                if len(pairs) == pair_limit:
                    break
        if len(pairs) == pair_limit:
            break
    if not pairs:
        raise RuntimeError("realistic recommendation cohort contains no missing links")
    jaccard = list(module.jaccard_coefficient(graph, pairs))
    preferential = list(module.preferential_attachment(graph, pairs))
    cohort = graph.subgraph(cohort_nodes).copy()
    summary = {
        "job": "link-recommendation-export",
        "nodes": graph.number_of_nodes(),
        "edges": graph.number_of_edges(),
        "self_loops_removed": self_loops_removed,
        "cohort_nodes": cohort.number_of_nodes(),
        "cohort_edges": cohort.number_of_edges(),
        "pair_count": len(pairs),
        "jaccard": jaccard,
        "preferential_attachment": preferential,
    }
    return _pack_realistic_result(
        summary,
        _write_edgelist_bytes(module, cohort),
    )


def _workload_community_detection(module, path: Path, size: int) -> bytes:
    """Load, detect collaboration communities, extract the largest, and export."""
    graph, self_loops_removed = _load_real_graph(module, path, size)
    communities = [
        sorted(community)
        for community in module.community.label_propagation_communities(graph)
    ]
    communities.sort(
        key=lambda nodes: (-len(nodes), nodes[0] if nodes else ""),
    )
    if not communities:
        raise RuntimeError("realistic community workload returned no communities")
    largest = graph.subgraph(communities[0]).copy()
    assignments = sorted(
        (node, community_index)
        for community_index, nodes in enumerate(communities)
        for node in nodes
    )
    summary = {
        "job": "community-detection-export",
        "nodes": graph.number_of_nodes(),
        "edges": graph.number_of_edges(),
        "self_loops_removed": self_loops_removed,
        "community_count": len(communities),
        "community_sizes": [len(nodes) for nodes in communities],
        "assignments": assignments,
        "largest_community_nodes": largest.number_of_nodes(),
        "largest_community_edges": largest.number_of_edges(),
    }
    return _pack_realistic_result(
        summary,
        _write_edgelist_bytes(module, largest),
    )


def suite_realistic_workloads():
    """Phase 2: whole real-world jobs, from compressed input to output bytes."""
    import networkx as nx
    import franken_networkx as fnx

    hash_seed = os.environ.get("PYTHONHASHSEED")
    if hash_seed is None or hash_seed.lower() == "random":
        raise RuntimeError(
            "realistic-workloads requires a fixed PYTHONHASHSEED set before Python starts"
        )

    raw_sizes = os.environ.get("FNX_REALISTIC_SIZES", "1000,5000,10000")
    try:
        sizes = tuple(int(part) for part in raw_sizes.split(","))
    except ValueError as error:
        raise ValueError("FNX_REALISTIC_SIZES must be comma-separated integers") from error
    if not sizes or any(size < 2 for size in sizes):
        raise ValueError("FNX_REALISTIC_SIZES must contain integers >= 2")

    fixture_paths = _prepare_realistic_fixtures(sizes)
    available_workloads = (
        ("collaboration-core-export", _workload_collaboration_core),
        ("hub-routing-export", _workload_hub_routing),
        ("rich-club-onion-export", _workload_rich_club),
        ("link-recommendation-export", _workload_link_recommendation),
        ("community-detection-export", _workload_community_detection),
    )
    requested_names = os.environ.get("FNX_REALISTIC_JOBS")
    if requested_names is None:
        workloads = available_workloads
    else:
        selected = {
            name.strip()
            for name in requested_names.split(",")
            if name.strip()
        }
        known = {name for name, _ in available_workloads}
        unknown = selected - known
        if not selected or unknown:
            raise ValueError(
                "FNX_REALISTIC_JOBS must select known comma-separated jobs; "
                f"unknown={sorted(unknown)} known={sorted(known)}"
            )
        workloads = tuple(
            item
            for item in available_workloads
            if item[0] in selected
        )
    EXTRA_PROVENANCE["realistic_jobs"] = [name for name, _ in workloads]
    rows = []
    for workload_name, workload in workloads:
        for size in sizes:
            path = fixture_paths[size]
            rows.append(
                (
                    f"real/{workload_name} n={size}",
                    lambda job=workload, fixture=path, n=size: job(nx, fixture, n),
                    lambda job=workload, fixture=path, n=size: job(fnx, fixture, n),
                )
            )
    return rows


SUITES = {
    "view-accessors": suite_view_accessors,
    "adj-descriptor": suite_adj_descriptor,
    "adj-len": suite_adjacency_len,
    "adj-iter": suite_adjacency_iter,
    "multi-adj-iter": suite_multi_adjacency_iter,
    "multi-adj-contains": suite_multi_adjacency_contains,
    "multi-row-getitem": suite_multi_row_getitem,
    "multiedge-getitem": suite_multiedge_getitem,
    "multiedge-iter": suite_multiedge_iter,
    "multikeydict-iter": suite_multikeydict_iter,
    "digraph-descriptors": suite_digraph_descriptors,
    "multidigraph-descriptors": suite_multidigraph_descriptors,
    "node-primitives": suite_node_primitives,
    "edge-primitives": suite_edge_primitives,
    "edge-data-primitives": suite_edge_data_primitives,
    "multigraph-edge-data-admission": suite_multigraph_edge_data_admission,
    "multigraph-degree-scalar": suite_multigraph_degree_scalar,
    "simple-edge-getitem": suite_simple_edge_getitem,
    "nodeview-contains": suite_nodeview_contains,
    "multi-neighbor-keydict": suite_multi_neighbor_keydict,
    "digraph-neighbor-descriptors": suite_digraph_neighbor_descriptors,
    "nodeview-getitem": suite_nodeview_getitem,
    "lazy-rows": suite_lazy_rows,
    "constant-predicates": suite_constant_predicates,
    "digraph-string-attr-construction": suite_digraph_string_attr_construction,
    "multidigraph-string-attr-construction": suite_multidigraph_string_attr_construction,
    "multigraph-compose": suite_multigraph_compose,
    "marshaling": suite_marshaling,
    "class1-scaling": suite_class1_scaling,
    "class1-frontier": suite_class1_frontier,
    "claim-incumbent": suite_claim_incumbent,
    "cold-after-mutation-cc": suite_cold_after_mutation_cc,
    "realistic-workloads": suite_realistic_workloads,
}


def main(argv):
    if len(argv) != 2 or argv[1] not in SUITES:
        print(f"usage: {argv[0]} {{{'|'.join(SUITES)}}}", file=sys.stderr)
        return 2
    name = argv[1]
    EXTRA_PROVENANCE["host_wide_quiescence"] = {
        "contract": "required",
        "pre_setup": require_host_wide_quiescence("pre_setup"),
    }
    results = run_rows(f"suite={name}", SUITES[name]())
    losses = [r for r in results if r.get("ratio_p50", 1) < 1.0 and r.get("decidable")]
    if losses:
        print("\ndecidable losses (fnx slower):", flush=True)
        for row in sorted(losses, key=lambda r: r["ratio_p50"]):
            print(f"  {row['ratio_p50']:7.4f}x  {row['label']}", flush=True)
    print(
        "benchmark_results_json="
        + json.dumps(results, sort_keys=True, separators=(",", ":")),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
