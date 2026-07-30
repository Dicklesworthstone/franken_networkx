#!/usr/bin/env python3
"""End-to-end parallel analytics-pass benchmark: FrankenNetworkX vs NetworkX.

This harness targets the MISSING CAPABILITY class rather than constant-factor
overhead. The measured job is a whole analytics pass over a real graph -- the
sequence a user actually runs to profile a network -- not a single algorithm
call:

    read_edgelist -> largest connected component -> degree assortativity
    -> average clustering -> k-core numbers -> PageRank
    -> EXACT betweenness centrality -> closeness centrality

Why the parallel arm is structurally unavailable to NetworkX 3.6.1
-----------------------------------------------------------------
NetworkX's kernels are pure Python. The dominant stage of any centrality pass
is Brandes betweenness: |V| independent single-source shortest-path passes,
which is textbook embarrassingly parallel. NetworkX cannot exploit that:

  1. CPython's GIL serialises bytecode, so `threading` over the source loop
     yields ~1x, not Nx. NetworkX ships no thread pool and no `n_jobs`.
  2. The `multiprocessing` escape hatch requires pickling the graph into every
     worker. A dict-of-dict adjacency with a per-edge attribute dict is a large
     Python object graph, so that costs both the pickle round-trip and an
     N-fold memory blowup -- it does not survive contact with a real graph.
  3. Parallel NetworkX lives in a separate `nx-parallel` backend project, not
     in core 3.6.1, and it too pays the pickling cost.

So "use the other 31 cores" is not a knob a NetworkX user has. It is absent
from the library, not merely slow in it. FrankenNetworkX stores adjacency as
compact integer rows and fans the per-source passes over a rayon pool, reducing
per-source contributions in strict source order so the float summation order --
and therefore the result -- matches the sequential path.

The `--threads 1` row is load-bearing: it separates the two effects. The
NetworkX -> fnx@1-thread ratio is the cost of leaving interpreted Python (the
generality tax). The fnx@1 -> fnx@N ratio is the capability NetworkX lacks.

Measurement contract
--------------------
  * NetworkX 3.6.1 is imported and executed live in the same invocation as fnx;
    no archived or quoted baseline is used.
  * Every row records host identity, CPU model, physical/SMT core counts,
    scheduler affinity, the requested rayon thread count, and the SHA-256 of
    the loaded `_fnx` ELF -- all self-reported from inside the measuring
    process.
  * Concurrency is MEASURED, not asserted: each stage records CPU time and wall
    time, so cpu/wall is the observed parallelism. NetworkX pins to ~1.0 by
    construction; that ratio is the missing-capability evidence.
  * Arms are interleaved inside a single replicate loop so machine drift hits
    both engines equally.
  * Significance uses a bootstrap CI on the median ratio, gated against a
    same-engine A/A null. Coefficient of variation is never used.

Usage
-----
    # fetch the real graphs (SNAP), cached; needed once
    python3 scripts/parallel_analytics_pass.py --role fetch --graph-dir <dir>

    # one engine, one thread setting; emits a JSON record on stdout
    python3 scripts/parallel_analytics_pass.py --role worker \
        --engine fnx --graph ca-AstroPh --threads 32

    # full study: interleaved head-to-head + fnx thread sweep
    python3 scripts/parallel_analytics_pass.py --role driver \
        --graph-dir <dir> --out <artifact-dir> --plan '[...]'

    # render the report + row-level CSV
    python3 scripts/parallel_analytics_report.py \
        --study <artifact-dir>/study.json --out <artifact-dir>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import random
import socket
import statistics
import subprocess
import sys
import time

# --------------------------------------------------------------------------
# provenance -- everything here is computed inside the measuring process
# --------------------------------------------------------------------------


def _physical_cores() -> int | None:
    """Distinct (physical id, core id) pairs from /proc/cpuinfo."""
    try:
        seen = set()
        pkg = core = None
        with open("/proc/cpuinfo") as handle:
            for line in handle:
                if line.startswith("physical id"):
                    pkg = line.split(":", 1)[1].strip()
                elif line.startswith("core id"):
                    core = line.split(":", 1)[1].strip()
                elif not line.strip():
                    if pkg is not None and core is not None:
                        seen.add((pkg, core))
                    pkg = core = None
        if pkg is not None and core is not None:
            seen.add((pkg, core))
        return len(seen) or None
    except OSError:
        return None


def _cpu_model() -> str:
    try:
        with open("/proc/cpuinfo") as handle:
            for line in handle:
                if line.startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or "unknown"


def _sha256(path: str) -> str | None:
    try:
        digest = hashlib.sha256()
        with open(path, "rb") as handle:
            for block in iter(lambda: handle.read(1 << 20), b""):
                digest.update(block)
        return digest.hexdigest()
    except OSError:
        return None


def provenance(engine: str, builder: str | None = None, profile: str | None = None) -> dict:
    """Host/build identity, self-reported from inside this process.

    `builder` names the machine that COMPILED the extension (an rch remote
    worker, or "local"), and `profile` names the cargo profile. A binary of
    unknown origin is not evidence, so these sit next to the ELF SHA-256 to
    close the chain: builder -> cargo profile -> ELF SHA-256 -> the digest this
    process reports at run time.
    """
    import networkx

    record = {
        "host": socket.gethostname(),
        "kernel": platform.release(),
        "python": sys.version.split()[0],
        "cpu_model": _cpu_model(),
        "cpu_physical_cores": _physical_cores(),
        "cpu_smt_threads": os.cpu_count(),
        "sched_affinity": len(os.sched_getaffinity(0)),
        "pid": os.getpid(),
        "rayon_num_threads_env": os.environ.get("RAYON_NUM_THREADS", "<unset>"),
        "networkx_version": networkx.__version__,
        "networkx_path": networkx.__file__,
    }
    # The NetworkX arm must be a genuine pure-Python NetworkX run, not a
    # dispatch into a backend. Record enough to prove it.
    record["networkx_backend_env"] = os.environ.get(
        "NETWORKX_AUTOMATIC_BACKENDS", "<unset>"
    )
    if engine == "fnx":
        import franken_networkx
        from franken_networkx import _fnx

        record["build_builder"] = builder or os.environ.get(
            "FNX_BUILD_BUILDER", "<unrecorded>"
        )
        record["build_profile"] = profile or os.environ.get(
            "FNX_BUILD_PROFILE", "<unrecorded>"
        )
        elf = getattr(_fnx, "__file__", None)
        record["fnx_version"] = getattr(franken_networkx, "__version__", "unknown")
        record["fnx_path"] = franken_networkx.__file__
        record["fnx_elf_path"] = elf
        record["fnx_elf_sha256"] = _sha256(elf) if elf else None
        record["fnx_elf_mtime"] = (
            time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(os.path.getmtime(elf)))
            if elf and os.path.exists(elf)
            else None
        )
    return record


# --------------------------------------------------------------------------
# the analytics pass
# --------------------------------------------------------------------------


def resolved_impls(mod) -> dict:
    """Which module/file each stage's callable actually resolves to.

    This is the guard against a silent backend dispatch making the two arms the
    same code. Recorded per engine so the artifact can prove the NetworkX arm
    really ran NetworkX.
    """
    out = {}
    for name in (
        "betweenness_centrality",
        "closeness_centrality",
        "pagerank",
        "core_number",
    ):
        fn = getattr(mod, name, None)
        out[name] = {
            "module": getattr(fn, "__module__", None),
            "qualname": getattr(fn, "__qualname__", None),
            "file": getattr(getattr(fn, "__code__", None), "co_filename", None),
        }
    return out


def run_pass(mod, graph_path: str) -> tuple[list[dict], dict]:
    """Run the identical analytics pass against `mod` (networkx or fnx).

    Returns (stage timings, result digest). The digest lets the report prove
    both engines computed the same thing.
    """
    timings: list[dict] = []
    digest: dict = {}

    def stage(name, fn):
        # CPU time across ALL threads of this process (rayon workers included),
        # so cpu/wall is the observed parallelism of the stage.
        cpu0 = time.process_time()
        wall0 = time.perf_counter()
        value = fn()
        wall = time.perf_counter() - wall0
        cpu = time.process_time() - cpu0
        timings.append(
            {
                "stage": name,
                "wall_s": wall,
                "cpu_s": cpu,
                "cpu_wall_ratio": (cpu / wall) if wall > 0 else None,
            }
        )
        return value

    graph = stage("read_edgelist", lambda: mod.read_edgelist(graph_path))
    digest["nodes"] = graph.number_of_nodes()
    digest["edges_raw"] = graph.number_of_edges()

    # Several real SNAP graphs carry self-loops, and `core_number` rejects them
    # on BOTH engines with the same NetworkXNotImplemented ("Consider using
    # G.remove_edges_from(nx.selfloop_edges(G))"). Doing exactly what that
    # message prescribes is part of the real job, so it is a timed stage rather
    # than pre-cleaned input.
    def _deloop():
        loops = list(mod.selfloop_edges(graph))
        graph.remove_edges_from(loops)
        return loops

    digest["self_loops_removed"] = len(stage("remove_self_loops", _deloop))
    digest["edges"] = graph.number_of_edges()

    components = stage(
        "connected_components",
        lambda: sorted(mod.connected_components(graph), key=len, reverse=True),
    )
    digest["n_components"] = len(components)
    digest["largest_cc_size"] = len(components[0]) if components else 0

    digest["assortativity"] = stage(
        "degree_assortativity",
        lambda: mod.degree_assortativity_coefficient(graph),
    )
    digest["average_clustering"] = stage(
        "average_clustering", lambda: mod.average_clustering(graph)
    )

    cores = stage("core_number", lambda: mod.core_number(graph))
    digest["max_core"] = max(cores.values()) if cores else 0

    pagerank = stage("pagerank", lambda: mod.pagerank(graph))
    digest["pagerank_top"] = _top(pagerank)

    betweenness = stage(
        "betweenness_exact", lambda: mod.betweenness_centrality(graph)
    )
    digest["betweenness_top"] = _top(betweenness)

    closeness = stage("closeness", lambda: mod.closeness_centrality(graph))
    digest["closeness_top"] = _top(closeness)

    total_wall = sum(t["wall_s"] for t in timings)
    total_cpu = sum(t["cpu_s"] for t in timings)
    timings.append(
        {
            "stage": "TOTAL",
            "wall_s": total_wall,
            "cpu_s": total_cpu,
            "cpu_wall_ratio": (total_cpu / total_wall) if total_wall > 0 else None,
        }
    )
    return timings, digest


def _top(scores: dict, k: int = 10) -> list[list]:
    """Top-k (node, value) with values rounded so the two engines can be
    compared across float-summation-order differences."""
    ordered = sorted(scores.items(), key=lambda kv: (-kv[1], str(kv[0])))[:k]
    return [[str(node), round(float(value), 12)] for node, value in ordered]


# --------------------------------------------------------------------------
# worker role
# --------------------------------------------------------------------------


def _load_engine(engine: str):
    if engine == "fnx":
        import franken_networkx as mod
    elif engine == "nx":
        import networkx as mod
    else:  # pragma: no cover
        raise SystemExit(f"unknown engine {engine!r}")
    return mod


def role_worker(args) -> int:
    """Run one or more engines over `--reps` replicates.

    With `--engine both`, the arms are interleaved INSIDE a single replicate
    loop and a single process, so machine drift, thermal state and page-cache
    warmth hit both engines equally, and the within-replicate ORDER alternates
    so neither arm is systematically first. Cross-engine comparisons should use
    this mode; the thread sweep necessarily uses separate processes because
    rayon fixes its pool size at first use.

    Use at least 8 replicates for a gated claim: the A/A null splits them by
    parity, so 6 reps leave only 3 per half and the null's own median is then
    far noisier than the 2% bias bound it is checked against.
    """
    engines = ["nx", "fnx"] if args.engine == "both" else [args.engine]
    mods = {name: _load_engine(name) for name in engines}
    graph_path = os.path.join(args.graph_dir, f"{args.graph}.txt.gz")

    records = {}
    for name in engines:
        records[name] = {
            "engine": name,
            "graph": args.graph,
            "threads_requested": args.threads,
            "provenance": provenance(name, args.builder, args.profile),
            "resolved_impls": resolved_impls(mods[name]),
            "interleaved": args.engine == "both",
            "replicates": [],
        }

    for rep in range(args.reps):
        # Alternate which engine goes first each replicate. Running one arm
        # always-first is a real arm-order bias source (page cache, turbo
        # residency, allocator state), and it is exactly what the A/A null's
        # median clause is meant to bound -- so remove it at the source rather
        # than absorb it into the null.
        order = engines if rep % 2 == 0 else list(reversed(engines))
        for name in order:
            timings, digest = run_pass(mods[name], graph_path)
            records[name]["replicates"].append(
                {"rep": rep, "timings": timings, "digest": digest}
            )
            total = next(t for t in timings if t["stage"] == "TOTAL")
            print(
                f"[worker] rep={rep} {name} TOTAL={total['wall_s']:.3f}s "
                f"cpu/wall={total['cpu_wall_ratio']:.2f}",
                file=sys.stderr,
                flush=True,
            )

    for name in engines:
        print("@@RESULT@@" + json.dumps(records[name]))
    return 0


# --------------------------------------------------------------------------
# statistics -- bootstrap median CI, A/A null gate. No CV anywhere.
# --------------------------------------------------------------------------


def bootstrap_ratio_ci(
    slow: list[float],
    fast: list[float],
    *,
    iterations: int = 20000,
    seed: int = 20260729,
    alpha: float = 0.05,
) -> tuple[float, float, float]:
    """Percentile bootstrap CI for median(slow)/median(fast)."""
    rng = random.Random(seed)
    point = statistics.median(slow) / statistics.median(fast)
    draws = []
    for _ in range(iterations):
        rs = [slow[rng.randrange(len(slow))] for _ in range(len(slow))]
        rf = [fast[rng.randrange(len(fast))] for _ in range(len(fast))]
        draws.append(statistics.median(rs) / statistics.median(rf))
    draws.sort()
    lo = draws[int((alpha / 2) * iterations)]
    hi = draws[min(int((1 - alpha / 2) * iterations), iterations - 1)]
    return point, lo, hi


def aa_null_stats(samples: list[float], **kwargs) -> dict | None:
    """Same-engine A/A null: split replicates by parity, bootstrap the ratio of
    medians, and report it as telemetry rather than as a veto.

    Deliberately NOT a CI-straddle test. Requiring the null CI to contain 1.0
    couples the verdict to the null's PRECISION and does so backwards: a
    tighter null (a better measurement) has a narrower CI, so it is more likely
    to exclude 1.0 and veto its own row. This returns:

      median      -- the null's point ratio; its distance from 1.0 is
                     arm-order bias, which IS worth bounding
      half_width  -- (hi-lo)/2, the substrate's resolution
      margin      -- max(|hi-1|, |1-lo|), a conservative bias+width envelope
                     kept for continuity with earlier rows in this repo

    Bias is bounded by the median clause; precision is reported, never a veto.
    """
    even = samples[0::2]
    odd = samples[1::2]
    if len(even) < 2 or len(odd) < 2:
        return None
    point, lo, hi = bootstrap_ratio_ci(even, odd, **kwargs)
    return {
        "median": point,
        "lo": lo,
        "hi": hi,
        "half_width": (hi - lo) / 2.0,
        "margin": max(abs(hi - 1.0), abs(1.0 - lo)),
        "median_bias": abs(point - 1.0),
        "excludes_one": lo > 1.0 or hi < 1.0,
    }


def aa_null_margin(samples: list[float], **kwargs) -> float:
    """Conservative bias+width envelope; NaN when there are too few reps."""
    stats = aa_null_stats(samples, **kwargs)
    return float("nan") if stats is None else stats["margin"]


def decide(
    effect: tuple[float, float, float],
    nulls: list[dict],
    *,
    max_null_median_bias: float = 0.02,
) -> dict:
    """The corrected three-clause gate.

    A row is decidable when ALL hold:
      1. the effect CI excludes 1.0;
      2. the effect deviation exceeds 2x the LARGER null half-width;
      3. every null MEDIAN sits within `max_null_median_bias` of 1.0.

    Clause 3 replaces a CI-straddle veto: it bounds arm-order bias without
    letting the null's precision decide the row. Null CIs remain telemetry.
    """
    point, lo, hi = effect
    live = [n for n in nulls if n is not None]
    deviation = abs(point - 1.0)
    ci_excludes_one = lo > 1.0 or hi < 1.0

    # A missing null is NOT a satisfied clause. Without a same-invocation A/A
    # control the row is unfalsifiable, which is exactly the VOID-NONULL failure
    # this repo's ledger preflight exists to block, so it reports
    # UNDECIDABLE-NO-NULL rather than borrowing a verdict it did not earn.
    if not live:
        return {
            "point": point,
            "ci": (lo, hi),
            "deviation": deviation,
            "null_half_width": float("nan"),
            "null_envelope": float("nan"),
            "null_worst_median_bias": float("nan"),
            "ci_excludes_one": ci_excludes_one,
            "clears_2x_half_width": False,
            "clears_2x_envelope": False,
            "null_median_bias_bounded": False,
            "has_null": False,
            "decidable": False,
            "decidable_strict": False,
            "label": "UNDECIDABLE-NO-NULL",
        }

    half = max(n["half_width"] for n in live)
    envelope = max(n["margin"] for n in live)
    worst_bias = max(n["median_bias"] for n in live)

    clears_half_width = deviation > 2 * half
    # Also evaluate the stricter bias+width envelope so this is a tightening,
    # not a loosening: the reported verdict must hold under BOTH.
    clears_envelope = deviation > 2 * envelope
    bias_bounded = worst_bias <= max_null_median_bias
    decidable = ci_excludes_one and clears_half_width and bias_bounded

    return {
        "point": point,
        "ci": (lo, hi),
        "deviation": deviation,
        "null_half_width": half,
        "null_envelope": envelope,
        "null_worst_median_bias": worst_bias,
        "ci_excludes_one": ci_excludes_one,
        "clears_2x_half_width": clears_half_width,
        "clears_2x_envelope": clears_envelope,
        "null_median_bias_bounded": bias_bounded,
        "has_null": True,
        "decidable": decidable,
        "decidable_strict": ci_excludes_one and clears_envelope and bias_bounded,
        "label": "DECIDABLE" if decidable else "UNDECIDABLE",
    }


# --------------------------------------------------------------------------
# driver role
# --------------------------------------------------------------------------


def _spawn(args, engine: str, graph: str, threads: int | None, reps: int) -> list[dict]:
    env = dict(os.environ)
    if threads is None:
        env.pop("RAYON_NUM_THREADS", None)
    else:
        env["RAYON_NUM_THREADS"] = str(threads)
    cmd = [
        sys.executable,
        os.path.abspath(__file__),
        "--role",
        "worker",
        "--engine",
        engine,
        "--graph",
        graph,
        "--graph-dir",
        args.graph_dir,
        "--reps",
        str(reps),
        "--threads",
        str(threads if threads is not None else -1),
    ]
    if args.builder:
        cmd += ["--builder", args.builder]
    if args.profile:
        cmd += ["--profile", args.profile]
    proc = subprocess.run(
        cmd, env=env, capture_output=True, text=True, timeout=args.timeout
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"worker {engine}/{graph}/threads={threads} failed rc={proc.returncode}\n"
            f"{proc.stderr[-4000:]}"
        )
    found = [
        json.loads(line[len("@@RESULT@@") :])
        for line in proc.stdout.splitlines()
        if line.startswith("@@RESULT@@")
    ]
    if not found:
        raise RuntimeError(
            f"no result from worker {engine}/{graph}: {proc.stdout[-2000:]}"
        )
    return found


def role_driver(args) -> int:
    os.makedirs(args.out, exist_ok=True)
    study: dict = {
        "started": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "graph_dir": os.path.abspath(args.graph_dir),
        "runs": [],
    }

    plan = json.loads(args.plan)
    for step in plan:
        engine = step["engine"]
        graph = step["graph"]
        threads = step.get("threads")
        reps = step["reps"]
        label = f"{engine}/{graph}/threads={threads}/reps={reps}"
        print(f"[driver] {label} ...", flush=True)
        started = time.perf_counter()
        try:
            records = _spawn(args, engine, graph, threads, reps)
            for record in records:
                record["status"] = "ok"
        except subprocess.TimeoutExpired:
            records = [
                {
                    "engine": engine,
                    "graph": graph,
                    "threads_requested": threads,
                    "status": "TIMEOUT",
                    "timeout_s": args.timeout,
                    "replicates": [],
                }
            ]
            print(f"[driver] {label} TIMEOUT after {args.timeout}s", flush=True)
        elapsed = time.perf_counter() - started
        for record in records:
            record["driver_wall_s"] = elapsed
            study["runs"].append(record)
        with open(os.path.join(args.out, "study.json"), "w") as handle:
            json.dump(study, handle, indent=2)
        for record in records:
            reptotals = [
                t["wall_s"]
                for rep in record.get("replicates", [])
                for t in rep["timings"]
                if t["stage"] == "TOTAL"
            ]
            if reptotals:
                print(
                    f"[driver] {record['engine']}/{graph}/threads={threads} "
                    f"median TOTAL = {statistics.median(reptotals):.3f}s "
                    f"({len(reptotals)} reps)",
                    flush=True,
                )

    study["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    with open(os.path.join(args.out, "study.json"), "w") as handle:
        json.dump(study, handle, indent=2)
    print(f"[driver] wrote {os.path.join(args.out, 'study.json')}")
    return 0


def role_selfcheck(args) -> int:
    """Prove the statistical gate discriminates, rather than rubber-stamping.

    A gate that cannot fail is not evidence. These assertions check calibration
    in both directions: a real effect must clear the null, and a fake effect
    inside the null must be rejected.
    """
    failures: list[str] = []

    point, lo, hi = bootstrap_ratio_ci([10.0] * 6, [1.0] * 6)
    if not (abs(point - 10) < 1e-9 and abs(lo - 10) < 1e-9 and abs(hi - 10) < 1e-9):
        failures.append(f"degenerate 10x ratio mis-estimated: {point} [{lo}, {hi}]")

    if aa_null_margin([5.0] * 8) != 0.0:
        failures.append("A/A null on constant samples is not zero")

    rng = random.Random(7)
    covered = 0
    trials = 200
    for _ in range(trials):
        slow = [rng.gauss(100, 8) for _ in range(6)]
        fast = [rng.gauss(10, 0.8) for _ in range(6)]
        _, lo, hi = bootstrap_ratio_ci(
            slow, fast, iterations=2000, seed=rng.randrange(10**6)
        )
        if lo <= 10.0 <= hi:
            covered += 1
    coverage = covered / trials
    if not 0.88 <= coverage <= 1.0:
        failures.append(f"95% CI coverage of the true ratio is {coverage:.1%}")

    margin = aa_null_margin([rng.gauss(100, 5) for _ in range(6)])
    if not 0.0 < margin < 0.5:
        failures.append(f"A/A null on a noisy same-engine arm is {margin}")

    # The three-clause gate must DISCRIMINATE. A gate that cannot return
    # UNDECIDABLE is not evidence, and a "fix" that turns a loss into a win is
    # a loosening. Both directions are asserted here.
    def verdict(slow, fast):
        return decide(
            bootstrap_ratio_ci(slow, fast), [aa_null_stats(slow), aa_null_stats(fast)]
        )

    no_effect = verdict(
        [100.5, 99.2, 101.1, 98.8, 100.2, 99.9],
        [100.1, 99.8, 100.4, 99.5, 100.7, 100.0],
    )
    if no_effect["decidable"]:
        failures.append(
            f"gate decided a no-effect pair (ratio={no_effect['point']:.4f})"
        )

    marginal = verdict(
        [100.5, 99.2, 101.1, 98.8, 100.2, 99.9],
        [98.5, 97.2, 99.1, 96.8, 98.2, 97.9],
    )
    if marginal["decidable"]:
        failures.append(
            f"gate decided a marginal effect inside the null "
            f"(ratio={marginal['point']:.4f})"
        )

    real = verdict(
        [116.5, 117.1, 116.2, 116.9, 116.4, 116.8],
        [0.271, 0.273, 0.270, 0.274, 0.272, 0.271],
    )
    if not (real["decidable"] and real["decidable_strict"]):
        failures.append("gate failed to decide a genuine two-orders-of-magnitude effect")

    # A real regression must be DECIDABLE and reported as a loss, not silently
    # rescued into a win by the gate correction.
    loss = verdict(
        [50.0, 50.2, 49.8, 50.1, 49.9, 50.3],
        [100.1, 99.8, 100.4, 99.5, 100.7, 100.0],
    )
    if not loss["decidable"] or loss["point"] >= 1.0:
        failures.append(
            f"gate mishandled a genuine regression (ratio={loss['point']:.4f}, "
            f"decidable={loss['decidable']})"
        )

    # The straddle defect must not be reintroduced: a null whose CI EXCLUDES 1.0
    # but whose median bias is tiny must not veto a large effect.
    tight_null = {
        "median": 1.00289,
        "lo": 1.000400,
        "hi": 1.005380,
        "half_width": 0.00249,
        "margin": 0.00538,
        "median_bias": 0.00289,
        "excludes_one": True,
    }
    straddle = decide((430.0, 426.0, 432.0), [tight_null])
    if not straddle["decidable"]:
        failures.append(
            "a tight null whose CI excludes 1.0 vetoed a 430x effect -- the "
            "CI-straddle defect has been reintroduced"
        )

    for problem in failures:
        print(f"selfcheck FAIL: {problem}")
    if failures:
        return 1
    print(
        f"selfcheck OK: ratio estimator exact on degenerate input, A/A null zero "
        f"on constants, {coverage:.1%} CI coverage of the true ratio; the "
        f"three-clause gate returns UNDECIDABLE for a no-effect pair and for a "
        f"marginal effect inside the null, decides a genuine regression AS a "
        f"loss, and does not veto a large effect on a tight null whose CI "
        f"excludes 1.0 (no CI-straddle defect)."
    )
    return 0


GRAPH_SOURCES = {
    "facebook_combined": "https://snap.stanford.edu/data/facebook_combined.txt.gz",
    "ca-AstroPh": "https://snap.stanford.edu/data/ca-AstroPh.txt.gz",
    "ca-CondMat": "https://snap.stanford.edu/data/ca-CondMat.txt.gz",
}


def role_fetch(args) -> int:
    """Cache the real SNAP graphs this study measures."""
    import urllib.request

    os.makedirs(args.graph_dir, exist_ok=True)
    for name, url in GRAPH_SOURCES.items():
        dest = os.path.join(args.graph_dir, f"{name}.txt.gz")
        if os.path.exists(dest):
            print(f"[fetch] {name}: cached ({os.path.getsize(dest)} bytes)")
            continue
        print(f"[fetch] {name}: {url}")
        with urllib.request.urlopen(url, timeout=180) as response:
            payload = response.read()
        with open(dest, "wb") as handle:
            handle.write(payload)
        print(
            f"[fetch] {name}: {len(payload)} bytes  "
            f"sha256={hashlib.sha256(payload).hexdigest()}"
        )
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--role", choices=["fetch", "worker", "driver", "selfcheck"], required=True
    )
    parser.add_argument(
        "--builder",
        default=None,
        help="machine that COMPILED the extension (rch worker id, or 'local')",
    )
    parser.add_argument(
        "--profile", default=None, help="cargo profile the extension was built with"
    )
    parser.add_argument("--engine", choices=["nx", "fnx", "both"])
    parser.add_argument("--graph")
    parser.add_argument("--graph-dir", default="graphs")
    parser.add_argument("--threads", type=int, default=-1)
    parser.add_argument("--reps", type=int, default=1)
    parser.add_argument("--out", default="artifact")
    parser.add_argument("--timeout", type=float, default=7200.0)
    parser.add_argument(
        "--plan",
        default="[]",
        help="JSON list of {engine, graph, threads, reps} steps, run in order.",
    )
    args = parser.parse_args(argv)
    if args.role == "selfcheck":
        return role_selfcheck(args)
    if args.role == "fetch":
        return role_fetch(args)
    if args.role == "worker":
        return role_worker(args)
    return role_driver(args)


if __name__ == "__main__":
    raise SystemExit(main())
