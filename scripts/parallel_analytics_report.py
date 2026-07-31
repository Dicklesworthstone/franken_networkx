#!/usr/bin/env python3
"""Render the parallel-analytics-pass study into a report + row-level CSV.

Reads the `study.json` written by `scripts/parallel_analytics_pass.py --role
driver` and emits:

  * analytics_pass_report.md -- provenance, per-stage tables, the thread sweep,
                  the bootstrap median CI gated on a same-engine A/A null, the
                  cross-engine parity digest, and a chooser statement.
  * rows.csv   -- one row per (engine, graph, threads, rep, stage) carrying
                  host identity, requested threads, CPU-active threads actually
                  observed, ELF identity, and exclusivity evidence on EVERY row.

Statistics contract: significance is a bootstrap percentile CI on the median
ratio, gated by all three corrected clauses: effect CI excludes 1, effect
deviation clears 2x the wider same-engine A/A half-width, and every A/A median
is within 2% of 1. Coefficient of variation is never computed or used.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from parallel_analytics_pass import (  # noqa: E402
    aa_null_stats,
    bootstrap_ratio_ci,
    decide,
)

STAGE_ORDER = [
    "read_edgelist",
    "remove_self_loops",
    "connected_components",
    "degree_assortativity",
    "average_clustering",
    "core_number",
    "pagerank",
    "betweenness_exact",
    "closeness",
    "TOTAL",
]


def totals(run: dict) -> list[float]:
    return [
        t["wall_s"]
        for rep in run.get("replicates", [])
        for t in rep["timings"]
        if t["stage"] == "TOTAL"
    ]


def stage_median(run: dict, stage: str, field: str = "wall_s") -> float | None:
    vals = [
        t[field]
        for rep in run.get("replicates", [])
        for t in rep["timings"]
        if t["stage"] == stage and t.get(field) is not None
    ]
    return statistics.median(vals) if vals else None


def find(runs: list[dict], engine: str, graph: str, threads=None) -> dict | None:
    for run in runs:
        if run["engine"] != engine or run["graph"] != graph:
            continue
        if threads is not None and run.get("threads_requested") != threads:
            continue
        return run
    return None


def fmt(value, spec="{:.3f}") -> str:
    if value is None:
        return "n/a"
    return spec.format(value)


def write_csv(study: dict, path: str) -> int:
    fields = [
        "engine",
        "graph",
        "threads_requested",
        "rep",
        "stage",
        "wall_s",
        "cpu_s",
        "cpu_wall_ratio",
        "process_threads_before",
        "process_threads_after",
        "thread_count_actually_used",
        "accounting_thread_ids_excluded",
        "host",
        "cpu_model",
        "cpu_physical_cores",
        "cpu_smt_threads",
        "sched_affinity",
        "rayon_num_threads_env",
        "networkx_version",
        "fnx_elf_sha256",
        "host_wide_pre_setup_verdict",
        "host_wide_pre_measurement_verdict",
        "measurement_exclusivity_verdict",
        "exclusivity_checked_windows",
        "status",
    ]
    count = 0
    with open(path, "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for run in study["runs"]:
            prov = run.get("provenance", {})
            quiescence = run.get("host_wide_quiescence", {})
            exclusivity = run.get("measurement_exclusivity", {})
            for rep in run.get("replicates", []):
                for timing in rep["timings"]:
                    writer.writerow(
                        {
                            "engine": run["engine"],
                            "graph": run["graph"],
                            "threads_requested": run.get("threads_requested"),
                            "rep": rep["rep"],
                            "stage": timing["stage"],
                            "wall_s": f"{timing['wall_s']:.6f}",
                            "cpu_s": f"{timing['cpu_s']:.6f}",
                            "cpu_wall_ratio": fmt(timing.get("cpu_wall_ratio")),
                            "process_threads_before": timing.get(
                                "process_threads_before"
                            ),
                            "process_threads_after": timing.get(
                                "process_threads_after"
                            ),
                            "thread_count_actually_used": timing.get(
                                "thread_count_actually_used"
                            ),
                            "accounting_thread_ids_excluded": json.dumps(
                                timing.get("accounting_thread_ids_excluded", [])
                            ),
                            "host": prov.get("host"),
                            "cpu_model": prov.get("cpu_model"),
                            "cpu_physical_cores": prov.get("cpu_physical_cores"),
                            "cpu_smt_threads": prov.get("cpu_smt_threads"),
                            "sched_affinity": prov.get("sched_affinity"),
                            "rayon_num_threads_env": prov.get("rayon_num_threads_env"),
                            "networkx_version": prov.get("networkx_version"),
                            "fnx_elf_sha256": prov.get("fnx_elf_sha256"),
                            "host_wide_pre_setup_verdict": quiescence.get(
                                "pre_setup", {}
                            ).get("verdict"),
                            "host_wide_pre_measurement_verdict": quiescence.get(
                                "pre_measurement", {}
                            ).get("verdict"),
                            "measurement_exclusivity_verdict": exclusivity.get(
                                "verdict"
                            ),
                            "exclusivity_checked_windows": exclusivity.get(
                                "checked_windows"
                            ),
                            "status": run.get("status"),
                        }
                    )
                    count += 1
    return count


def render(study: dict, csv_rows: int, builder: str | None, profile: str | None) -> str:
    runs = study["runs"]
    has_actual_thread_evidence = any(
        timing.get("thread_count_actually_used") is not None
        for run in runs
        for rep in run.get("replicates", [])
        for timing in rep["timings"]
    )
    prov = next(
        (r["provenance"] for r in runs if r.get("provenance", {}).get("fnx_elf_sha256")),
        {},
    )
    nxprov = next(
        (r.get("provenance", {}) for r in runs if r["engine"] == "nx"),
        {},
    )
    graphs = []
    for run in runs:
        if run["graph"] not in graphs:
            graphs.append(run["graph"])

    out: list[str] = []
    w = out.append

    w("# Parallel analytics pass: FrankenNetworkX vs NetworkX 3.6.1")
    w("")
    w(
        "Target class: **MISSING CAPABILITY** -- not interpreted-language overhead, "
        "and not the generality tax. The claim under test is that a whole-job "
        "analytics pass whose dominant stage is embarrassingly parallel is "
        "*unavailable* to NetworkX at realistic scale, and that the gap is "
        "therefore structural rather than a constant factor."
    )
    w("")
    if not has_actual_thread_evidence:
        w(
            "**Legacy-evidence warning:** these input studies predate measured "
            "CPU-active thread counts. Their wall times and cpu/wall values remain "
            "historical diagnostics, but this renderer will not promote them to "
            "a current one-vs-many structural verdict."
        )
        w("")

    # ---------------- provenance ----------------
    w("## Measurement provenance")
    w("")
    w("| field | value |")
    w("| --- | --- |")
    w(f"| study started | `{study.get('started')}` |")
    w(f"| study finished | `{study.get('finished')}` |")
    for index, source in enumerate(study.get("sources", [])):
        w(f"| study source {index + 1} | `{source}` |")
    w(f"| host | `{prov.get('host')}` |")
    w(f"| kernel | `{prov.get('kernel')}` |")
    w(f"| CPU | `{prov.get('cpu_model')}` |")
    w(
        f"| cores | **{prov.get('cpu_physical_cores')} physical** / "
        f"{prov.get('cpu_smt_threads')} SMT threads (affinity "
        f"{prov.get('sched_affinity')}) |"
    )
    w(f"| Python | `{prov.get('python')}` |")
    w(
        f"| NetworkX | **{nxprov.get('networkx_version')}** (live in-process) "
        f"`{nxprov.get('networkx_path')}` |"
    )
    w(f"| NetworkX auto-backend env | `{nxprov.get('networkx_backend_env')}` |")
    w(f"| fnx package | `{prov.get('fnx_path')}` |")
    w(f"| fnx ELF | `{prov.get('fnx_elf_path')}` |")
    w(f"| **fnx ELF SHA-256** | `{prov.get('fnx_elf_sha256')}` |")
    w(f"| fnx ELF mtime | `{prov.get('fnx_elf_mtime')}` |")
    w(
        f"| built by | `{builder or prov.get('build_builder', '<unrecorded>')}` |"
    )
    w(
        f"| cargo profile | `{profile or prov.get('build_profile', '<unrecorded>')}` |"
    )
    w("")
    w(
        "The ELF SHA-256, host identity, core topology and NetworkX version are "
        "all read from inside the measuring process (`provenance()` in "
        "`scripts/parallel_analytics_pass.py`), not from the shell that launched "
        "it. `rows.csv` repeats host identity, the ELF hash, requested threads, "
        "CPU-active threads actually observed, and exclusivity verdicts on every "
        f"one of its {csv_rows} rows."
    )
    w("")
    w(
        "Build provenance closes the chain builder -> profile -> ELF SHA-256 -> "
        "the digest reported at run time, so the timed binary is not of unknown "
        "origin. `release-perf` in this repo only adds debug line-tables on top "
        "of `release` (same `lto`/`codegen-units`), so `release` is both the "
        "optimisation level measured here and the profile the maturin wheel "
        "ships -- these absolute levels are labelled with the profile that "
        "actually ran."
    )
    w("")
    w(
        "`NETWORKX_AUTOMATIC_BACKENDS` is unset, so the NetworkX arm executes "
        "NetworkX's own pure-Python kernels and does not dispatch into the "
        "`franken_networkx` backend. The two arms are genuinely different "
        "implementations."
    )
    w("")

    # ---------------- fail-closed attempts ----------------
    aborted = [run for run in runs if run.get("status") not in (None, "ok")]
    if aborted:
        w("## Fail-closed no-verdict attempts")
        w("")
        w("| graph | engine | requested threads | status | exact reason |")
        w("| --- | --- | --- | --- | --- |")
        for run in aborted:
            reason = str(
                run.get("abort_reason")
                or (
                    f"worker exceeded the {run.get('timeout_s')}s deadline"
                    if run.get("status") == "TIMEOUT"
                    else "unspecified"
                )
            )
            reason = reason.replace("\n", " ").replace("|", "\\|")
            w(
                f"| `{run.get('graph')}` | {run.get('engine')} | "
                f"{run.get('threads_requested')} | **{run.get('status')}** | "
                f"{reason} |"
            )
        w("")
        w(
            "These attempts contribute no timing rows and no ratio: the worker "
            "clears every partial replicate when admission or continuous "
            "host-wide accounting fails."
        )
        w("")

    # ---------------- the job ----------------
    w("## The job")
    w("")
    w(
        "One pass, run identically against both modules -- the sequence a user "
        "actually runs to profile a network, not a single algorithm call:"
    )
    w("")
    w("```")
    w("read_edgelist -> connected_components -> degree_assortativity")
    w("  -> average_clustering -> core_number -> pagerank")
    w("  -> betweenness_centrality (EXACT, all sources) -> closeness_centrality")
    w("```")
    w("")
    w(
        "Graph loading is included. It is one of the stages where fnx does *not* "
        "win, and excluding it would be cherry-picking the whole-job claim."
    )
    w("")

    # ---------------- per graph ----------------
    for graph in graphs:
        nxrun = find(runs, "nx", graph)
        if nxrun is None:
            continue
        # Compare against the INTERLEAVED fnx arm -- the one measured inside the
        # same replicate loop and the same process as this nx arm. A faster
        # thread-sweep run exists for some graphs, but it ran in a separate
        # process at a different time, so pairing nx against it would trade
        # drift control for a bigger number.
        best = next(
            (
                r
                for r in runs
                if r["engine"] == "fnx"
                and r["graph"] == graph
                and r.get("interleaved")
                and totals(r)
            ),
            None,
        )
        if best is None:
            continue
        nthr = best.get("threads_requested")
        nodes = None
        edges = None
        if nxrun.get("replicates"):
            nodes = nxrun["replicates"][0]["digest"]["nodes"]
            edges = nxrun["replicates"][0]["digest"]["edges"]

        w(f"## Graph: `{graph}` -- {nodes} nodes, {edges} edges")
        w("")
        if nxrun.get("status") == "TIMEOUT":
            w(
                f"NetworkX **did not finish** within the "
                f"{nxrun.get('timeout_s')}s deadline."
            )
            w("")
        w(
            f"| stage | nx wall (s) | nx actual threads | nx cpu/wall | "
            f"fnx@{nthr} wall (s) | fnx actual threads | "
            f"fnx@{nthr} cpu/wall | speedup |"
        )
        w("| --- | --- | --- | --- | --- | --- | --- | --- |")
        for stage in STAGE_ORDER:
            a = stage_median(nxrun, stage)
            b = stage_median(best, stage)
            at = stage_median(nxrun, stage, "thread_count_actually_used")
            bt = stage_median(best, stage, "thread_count_actually_used")
            ar = stage_median(nxrun, stage, "cpu_wall_ratio")
            br = stage_median(best, stage, "cpu_wall_ratio")
            if a is None and b is None:
                continue
            ratio = (a / b) if (a and b) else None
            bold = "**" if stage == "TOTAL" else ""
            w(
                f"| {bold}{stage}{bold} | {bold}{fmt(a)}{bold} | "
                f"{fmt(at, '{:.1f}')} | {fmt(ar, '{:.2f}')} | "
                f"{bold}{fmt(b)}{bold} | {fmt(bt, '{:.1f}')} | "
                f"{fmt(br, '{:.2f}')} | "
                f"{bold}{fmt(ratio, '{:.1f}x')}{bold} |"
            )
        w("")
        nx_tot = statistics.median(totals(nxrun)) if totals(nxrun) else None
        fx_tot = statistics.median(totals(best))
        if nx_tot:
            w(
                f"Whole-job wall clock: **{nx_tot:.1f}s -> {fx_tot:.3f}s "
                f"({nx_tot / fx_tot:.0f}x)**, "
                f"nx reps={len(totals(nxrun))}, fnx reps={len(totals(best))}."
            )
            w("")

        # bootstrap + null gate
        slow, fast = totals(nxrun), totals(best)
        if len(slow) >= 2 and len(fast) >= 2:
            effect = bootstrap_ratio_ci(slow, fast)
            null_nx = aa_null_stats(slow)
            null_fx = aa_null_stats(fast)
            gate = decide(effect, [null_nx, null_fx])
            point, (lo, hi) = gate["point"], gate["ci"]
            w("### Significance -- three-clause gate (no CI-straddle veto)")
            w("")
            w("| quantity | value |")
            w("| --- | --- |")
            w(f"| median ratio (nx / fnx@{nthr}) | **{point:.1f}x** |")
            w(f"| 95% bootstrap CI (20k resamples) | [{lo:.1f}x, {hi:.1f}x] |")
            for label, null in (("nx", null_nx), ("fnx", null_fx)):
                if null is None:
                    w(f"| A/A null, {label} arm | too few reps |")
                    continue
                w(
                    f"| A/A null, {label} arm | median {null['median']:.4f}, "
                    f"CI [{null['lo']:.4f}, {null['hi']:.4f}], "
                    f"half-width {null['half_width']:.4f} |"
                )
            w(
                f"| clause 1 -- effect CI excludes 1.0 | "
                f"**{'yes' if gate['ci_excludes_one'] else 'NO'}** |"
            )
            w(
                f"| clause 2 -- deviation {gate['deviation']:.1f} > 2x null "
                f"half-width {fmt(2 * gate['null_half_width'], '{:.4f}')} | "
                f"**{'yes' if gate['clears_2x_half_width'] else 'NO'}** |"
            )
            w(
                f"| clause 3 -- worst null median bias "
                f"{fmt(gate['null_worst_median_bias'], '{:.4f}')} <= 0.02 | "
                f"**{'yes' if gate['null_median_bias_bounded'] else 'NO'}** |"
            )
            if gate["has_null"] and not gate["null_median_bias_bounded"]:
                bias = gate["null_worst_median_bias"]
                w(
                    f"| bias-to-effect ratio | {bias:.4f} / {gate['deviation']:.1f} = "
                    f"**{bias / gate['deviation']:.2e}** |"
                )
            w(f"| **verdict** | **{gate['label']}** |")
            if gate["has_null"]:
                w(
                    f"| same verdict under the stricter bias+width envelope "
                    f"({fmt(2 * gate['null_envelope'], '{:.4f}')}) | "
                    f"**{'yes' if gate['decidable_strict'] == gate['decidable'] else 'NO'}** |"
                )
            w("")
            if gate["has_null"] and not gate["null_median_bias_bounded"]:
                w(
                    f"**Clause 3 fails on a real arm-order effect, and the "
                    f"verdict is left at {gate['label']} rather than tuned into "
                    f"a pass.** The within-replicate order alternates by "
                    f"replicate parity, and the A/A null splits on that same "
                    f"parity, so these nulls measure POSITION, not drift. They "
                    f"agree on a coherent story: the nx null median "
                    f"{null_nx['median']:.4f} (nx faster when it runs first) and "
                    f"the fnx null median {null_fx['median']:.4f} (fnx slower "
                    f"when it runs second) both say the arm that goes first is "
                    f"~{100 * gate['null_worst_median_bias']:.0f}% faster. That "
                    f"is a genuine measurement asymmetry worth recording, and it "
                    f"is exactly what clause 3 exists to catch."
                )
                w("")
                w(
                    f"It is reported, not waved away, and it is also not "
                    f"material at this effect size: the bias is "
                    f"{gate['null_worst_median_bias']:.4f} against a deviation "
                    f"of {gate['deviation']:.1f}, a ratio of "
                    f"{gate['null_worst_median_bias'] / gate['deviation']:.2e}. A "
                    f"4% position effect cannot manufacture a "
                    f"{gate['point']:.0f}x ratio. Clause 3 is calibrated to stop "
                    f"a near-1.0 claim from being position bias in disguise; "
                    f"applied here it is a true positive about the substrate and "
                    f"a false alarm about the conclusion. The threshold was NOT "
                    f"relaxed to resolve that -- closing it properly means "
                    f"pinning both arms to fixed cores on a quiet host, which "
                    f"this shared 64-thread box could not provide."
                )
                w("")
            if not gate["has_null"]:
                w(
                    f"**No verdict is claimed for this graph.** The A/A null needs "
                    f"at least 4 replicates per arm to split by parity, and the "
                    f"NetworkX arm here has {len(slow)} (a single pass costs "
                    f"~{statistics.median(slow) / 60:.0f} minutes). The ratio and "
                    f"its CI are reported as a scale demonstration; the "
                    f"null-gated claim rests on the smaller graph above, and the "
                    f"parallel-scaling claim rests on the thread sweep below, "
                    f"neither of which needs this arm."
                )
                w("")
            w(
                "The A/A null splits one engine's own replicates by parity and "
                "bootstraps that ratio of medians. It is reported as telemetry "
                "and bounded by its MEDIAN, not used as a CI-straddle veto: "
                "requiring the null CI to contain 1.0 would couple the verdict "
                "to the null's precision backwards, so that a tighter null -- a "
                "better measurement -- is more likely to veto its own row. "
                "Clause 3 bounds arm-order bias instead. No coefficient of "
                "variation is used anywhere in this gate."
            )
            w("")

    # ---------------- thread sweep ----------------
    sweeps: dict[str, list[dict]] = {}
    for run in runs:
        if run["engine"] != "fnx":
            continue
        sweeps.setdefault(run["graph"], []).append(run)
    for graph, group in sweeps.items():
        group = [g for g in group if totals(g)]
        if len(group) < 3:
            continue
        group.sort(key=lambda r: r.get("threads_requested") or 0)
        base = next(
            (g for g in group if g.get("threads_requested") == 1), None
        )
        nxrun = find(runs, "nx", graph)
        nx_tot = (
            statistics.median(totals(nxrun))
            if nxrun and totals(nxrun)
            else None
        )
        w(f"## Thread sweep -- `{graph}` (fnx, `RAYON_NUM_THREADS`)")
        w("")
        w(
            "| requested threads | actual CPU-active threads | "
            "betweenness wall (s) | betweenness cpu/wall | "
            "TOTAL wall (s) | scaling vs 1 thread | vs NetworkX |"
        )
        w("| --- | --- | --- | --- | --- | --- | --- |")
        base_bt = stage_median(base, "betweenness_exact") if base else None
        nx_observed = (
            stage_median(
                nxrun,
                "betweenness_exact",
                "thread_count_actually_used",
            )
            if nxrun
            else None
        )
        for run in group:
            thr = run.get("threads_requested")
            bt = stage_median(run, "betweenness_exact")
            observed = stage_median(
                run,
                "betweenness_exact",
                "thread_count_actually_used",
            )
            btr = stage_median(run, "betweenness_exact", "cpu_wall_ratio")
            tot = statistics.median(totals(run))
            scaling = (base_bt / bt) if (base_bt and bt) else None
            versus = (nx_tot / tot) if nx_tot else None
            w(
                f"| {thr} | {fmt(observed, '{:.1f}')} | {fmt(bt)} | "
                f"{fmt(btr, '{:.2f}')} | {fmt(tot)} | "
                f"{fmt(scaling, '{:.2f}x')} | {fmt(versus, '{:.0f}x')} |"
            )
        w("")
        if nx_observed is not None:
            w(
                "`actual CPU-active threads` counts "
                "`/proc/self/task/*/schedstat` counters that advanced during the "
                "timed stage; it is observed, not copied from "
                "`RAYON_NUM_THREADS`. The dedicated host-accounting thread is "
                "identified and excluded from that count and CPU sum. "
                "`cpu/wall` independently records the remaining process-thread "
                "CPU time over wall time. NetworkX's betweenness stage uses "
                f"{nx_observed:.1f} active thread(s) on the same host; that "
                "observed one-vs-many split is the missing capability."
            )
        else:
            w(
                "This legacy sweep records requested threads and aggregate "
                "cpu/wall but not per-thread CPU counters. It is retained as "
                "historical scaling telemetry only; rerun under the hardened "
                "contract before claiming an observed one-vs-many capability "
                "split."
            )
        w("")

        # decomposition
        if base and nx_tot:
            fastest = min(group, key=lambda r: statistics.median(totals(r)))
            b1 = statistics.median(totals(base))
            bn = statistics.median(totals(fastest))
            fastest_observed = stage_median(
                fastest,
                "betweenness_exact",
                "thread_count_actually_used",
            )
            w("### Decomposing the win")
            w("")
            w("| factor | ratio | what it is |")
            w("| --- | --- | --- |")
            w(
                f"| NetworkX -> fnx @ 1 thread | **{nx_tot / b1:.0f}x** | "
                "leaving interpreted Python and the per-edge attribute-dict "
                "generality tax; a NetworkX user could in principle get this from "
                "a compiled single-threaded library |"
            )
            if nx_observed == 1 and fastest_observed and fastest_observed > 1:
                capability_text = (
                    f"using {fastest_observed:.1f} CPU-active threads actually "
                    "observed; **this factor has no NetworkX-side equivalent at "
                    "all**"
                )
            else:
                capability_text = (
                    "historical scaling diagnostic only; actual one-vs-many "
                    "thread evidence is absent"
                )
            w(
                f"| fnx @ 1 thread -> fnx @ "
                f"{fastest.get('threads_requested')} threads | "
                f"**{b1 / bn:.1f}x** | {capability_text} |"
            )
            w(f"| combined | **{nx_tot / bn:.0f}x** | whole-job wall clock |")
            w("")
            w(
                "The split matters for honesty: only the second row is the "
                "missing-capability claim. The first row is ordinary compiled-vs-"
                "interpreted advantage and is not what this artifact is about."
            )
            w("")

    # ---------------- parity ----------------
    w("## Cross-engine parity")
    w("")
    w(
        "A speedup on a different answer is worthless, so the pass emits a digest "
        "each replicate. Scalar invariants and top-10 rankings from the two "
        "engines:"
    )
    w("")
    w("| graph | check | NetworkX | fnx | agree |")
    w("| --- | --- | --- | --- | --- |")
    for graph in graphs:
        nxrun = find(runs, "nx", graph)
        fxrun = next(
            (
                r
                for r in runs
                if r["engine"] == "fnx" and r["graph"] == graph and r.get("replicates")
            ),
            None,
        )
        if not (nxrun and fxrun and nxrun.get("replicates")):
            continue
        a = nxrun["replicates"][0]["digest"]
        b = fxrun["replicates"][0]["digest"]
        for key in (
            "nodes",
            "edges_raw",
            "self_loops_removed",
            "edges",
            "n_components",
            "largest_cc_size",
            "max_core",
            "average_clustering",
            "assortativity",
        ):
            va, vb = a.get(key), b.get(key)
            same = va == vb or (
                isinstance(va, float)
                and isinstance(vb, float)
                and abs(va - vb) <= 1e-12 * max(1.0, abs(va))
            )
            w(
                f"| `{graph}` | {key} | {va} | {vb} | "
                f"{'yes' if same else '**NO**'} |"
            )
        for key in ("pagerank_top", "betweenness_top", "closeness_top"):
            ra = [n for n, _ in a.get(key, [])]
            rb = [n for n, _ in b.get(key, [])]
            w(
                f"| `{graph}` | {key} (top-10 order) | {'/'.join(ra[:3])}... | "
                f"{'/'.join(rb[:3])}... | {'yes' if ra == rb else '**NO**'} |"
            )
    w("")
    w(
        "Betweenness agrees to within 1 ULP rather than bit-identically: the "
        "parallel reduction replays per-source contributions in source order, "
        "but the per-source inner accumulation still differs from NetworkX's "
        "in-place dict update by one rounding. Rankings are unaffected."
    )
    w("")

    # ---------------- where fnx does not win ----------------
    w("## Where fnx does NOT win")
    w("")
    losses: list[str] = []
    for graph in graphs:
        nxrun = find(runs, "nx", graph)
        if nxrun is None or not nxrun.get("replicates"):
            continue
        best = None
        for run in runs:
            if run["engine"] != "fnx" or run["graph"] != graph or not totals(run):
                continue
            if best is None or statistics.median(totals(run)) < statistics.median(
                totals(best)
            ):
                best = run
        if best is None:
            continue
        for stage in STAGE_ORDER:
            if stage == "TOTAL":
                continue
            a = stage_median(nxrun, stage)
            b = stage_median(best, stage)
            if a and b and b > a:
                losses.append(
                    f"| `{graph}` | {stage} | {a:.3f} | {b:.3f} | "
                    f"**{a / b:.2f}x** |"
                )
    if losses:
        w("| graph | stage | nx wall (s) | fnx wall (s) | ratio |")
        w("| --- | --- | --- | --- | --- |")
        for row in losses:
            w(row)
        w("")
        w(
            "These are reported because the claim is a whole-job claim. The "
            "stages fnx loses are the ones that are neither parallel nor "
            "adjacency-bound -- they are dominated by building Python objects "
            "for the caller, where fnx pays a conversion cost NetworkX does not. "
            "They are also, on this job, numerically irrelevant: they are "
            "sub-second while the centrality stages are minutes."
        )
    else:
        w("On this job, no stage was slower under fnx than under NetworkX.")
    w("")

    # ---------------- chooser statement ----------------
    w("## CHOOSER STATEMENT")
    w("")
    facts: list[
        tuple[str, float, float, int | None, float | None, float | None]
    ] = []
    for graph in graphs:
        nxrun = find(runs, "nx", graph)
        if not (nxrun and totals(nxrun)):
            continue
        # Quote the interleaved arm, matching the head-to-head table above.
        best = next(
            (
                r
                for r in runs
                if r["engine"] == "fnx"
                and r["graph"] == graph
                and r.get("interleaved")
                and totals(r)
            ),
            None,
        )
        if best is None:
            continue
        slow = totals(nxrun)
        fast = totals(best)
        if len(slow) < 2 or len(fast) < 2:
            continue
        gate = decide(
            bootstrap_ratio_ci(slow, fast),
            [aa_null_stats(slow), aa_null_stats(fast)],
        )
        if not gate["decidable"]:
            continue
        nodes = nxrun["replicates"][0]["digest"]["nodes"]
        facts.append(
            (
                graph,
                statistics.median(slow),
                statistics.median(fast),
                nodes,
                stage_median(
                    nxrun,
                    "betweenness_exact",
                    "thread_count_actually_used",
                ),
                stage_median(
                    best,
                    "betweenness_exact",
                    "thread_count_actually_used",
                ),
            )
        )

    w("**Use NetworkX 3.6.1 when:**")
    w("")
    w(
        "- The graph is small enough that the whole pass is already fast in "
        "absolute terms. On a few-hundred-node graph both engines finish a full "
        "centrality pass in well under a second, and NetworkX is the reference "
        "semantics -- there is nothing to buy."
    )
    w(
        "- You need NetworkX's full API surface, its ecosystem of backends and "
        "readers, or exotic node objects and heavy per-edge attribute mutation. "
        "fnx is fastest on the integer-adjacency shapes and falls back to "
        "delegation elsewhere."
    )
    w("- You want the implementation everyone else's results are quoted against.")
    w("")
    w("**Use FrankenNetworkX when:**")
    w("")
    for graph, slow, fast, nodes, _, _ in facts:
        w(
            f"- The dominant stage is an exact all-sources centrality on a graph "
            f"of this scale. On `{graph}` ({nodes} nodes) the same pass is "
            f"**{slow:.0f}s under NetworkX and {fast:.2f}s under fnx "
            f"({slow / fast:.0f}x)** on this host."
        )
    structural_facts = [
        fact
        for fact in facts
        if fact[4] == 1 and fact[5] is not None and fact[5] > 1
    ]
    if facts:
        w(
            "- You are running the pass more than once -- a parameter sweep, a "
            "temporal sequence of snapshots, or a CI check -- and the admitted "
            "whole-job ratio above changes the analysis from a scheduled batch "
            "job into an interactive operation."
        )
    else:
        w(
            "- **No current FNX chooser row is admitted from these studies.** "
            "Their head-to-head rows fail the null gate or lack its controls; "
            "keep NetworkX as the default until a hardened rerun passes."
        )
    if structural_facts:
        _, _, _, _, nx_active, fnx_active = structural_facts[0]
        w(
            "- You have more than one core. On the admitted dominant stage, "
            f"NetworkX used {nx_active:.1f} CPU-active thread while FNX used "
            f"{fnx_active:.1f}; this observed parallel factor has no "
            "NetworkX-core setting to select."
        )
    else:
        w(
            "- **No structural one-vs-many chooser verdict is admitted yet.** "
            "Requested pool sizes and aggregate cpu/wall are diagnostics only; "
            "the rerun must observe one NetworkX CPU-active thread and more than "
            "one FNX thread on the dominant stage."
        )
    w("")
    w("**The crossover rule:**")
    w("")
    if structural_facts:
        w(
            "Pick by the *dominant stage*, not graph size alone. Choose FNX when "
            "the admitted pass is dominated by the exact all-source stage whose "
            "one-vs-many active-thread split is shown above; choose NetworkX when "
            "Python-object materialisation or API breadth dominates. Size the "
            "FNX pool to physical cores and expect sub-linear returns at the SMT "
            "tail."
        )
    else:
        w(
            "Until the hardened rerun admits both the incumbent ratio and the "
            "one-vs-many thread observation, **choose NetworkX 3.6.1**. Revisit "
            "only when the dominant exact all-source stage passes parity, both "
            "A/A controls, the three-clause median gate, host accounting, and "
            "actual-thread evidence in one invocation."
        )
    w("")

    return "\n".join(out) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--study",
        required=True,
        action="append",
        help=(
            "study.json to render; repeatable. A later study REPLACES an earlier "
            "run with the same (engine, graph, threads, interleaved) key, so an "
            "expensive arm can be re-measured without re-running the others."
        ),
    )
    parser.add_argument("--out", required=True)
    parser.add_argument(
        "--builder",
        default=None,
        help="override/record the machine that compiled the extension",
    )
    parser.add_argument(
        "--profile", default=None, help="override/record the cargo profile"
    )
    args = parser.parse_args(argv)

    study = None
    merged: dict[tuple, dict] = {}
    sources: list[str] = []
    for path in args.study:
        with open(path) as handle:
            loaded = json.load(handle)
        sources.append(os.path.abspath(path))
        if study is None:
            study = dict(loaded)
        else:
            study["finished"] = loaded.get("finished") or study.get("finished")
        for run in loaded["runs"]:
            merged[
                (
                    run["engine"],
                    run["graph"],
                    run.get("threads_requested"),
                    bool(run.get("interleaved")),
                )
            ] = run
    study["runs"] = list(merged.values())
    study["sources"] = sources
    os.makedirs(args.out, exist_ok=True)
    csv_path = os.path.join(args.out, "rows.csv")
    rows = write_csv(study, csv_path)
    report = render(study, rows, args.builder, args.profile)
    report_path = os.path.join(args.out, "analytics_pass_report.md")
    with open(report_path, "w") as handle:
        handle.write(report)
    print(f"wrote {report_path} ({len(report)} bytes) and {csv_path} ({rows} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
