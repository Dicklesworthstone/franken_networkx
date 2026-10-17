#!/usr/bin/env python3
"""Check benchmark results against SLO thresholds defined in slo_thresholds.json.

Reads the SLO threshold file and the regression gate report, then verifies:
  1. Regression-based SLOs (mutation p95, memory RSS, p99 tail) against
     the regression gate's per-scenario deltas.
  2. Absolute latency SLOs against the benchmark matrix (when matching
     algorithm-family benchmarks exist).

Exit 0 = all SLOs met.  Exit 1 = at least one SLO violated.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import math
import os
import platform
import statistics
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = (len(ordered) - 1) * p
    lo = math.floor(idx)
    hi = math.ceil(idx)
    if lo == hi:
        return ordered[lo]
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (idx - lo)


def summarize(values: list[float]) -> dict[str, float]:
    ordered = sorted(values)
    return {
        "samples": float(len(ordered)),
        "mean": statistics.fmean(ordered),
        "p50": percentile(ordered, 0.50),
        "p95": percentile(ordered, 0.95),
        "p99": percentile(ordered, 0.99),
        "min": ordered[0],
        "max": ordered[-1],
    }


def read_proc_rss_kb() -> tuple[float, float]:
    """Return (VmRSS_kB, VmHWM_kB) from /proc/self/status when available."""
    vm_rss = 0.0
    vm_hwm = 0.0
    status_path = Path("/proc/self/status")
    if status_path.exists():
        for line in status_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("VmRSS:"):
                vm_rss = float(line.split()[1])
            elif line.startswith("VmHWM:"):
                vm_hwm = float(line.split()[1])
    return vm_rss, vm_hwm


def collect_provenance() -> dict[str, object]:
    import franken_networkx as fnx
    import networkx as nx

    elf_path = Path(fnx._fnx.__file__).resolve()
    elf_sha256 = hashlib.sha256(elf_path.read_bytes()).hexdigest()
    governor_path = Path("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor")
    governor = (
        governor_path.read_text(encoding="utf-8").strip()
        if governor_path.exists()
        else "unknown"
    )
    return {
        "harness": "scripts/run_perf_slo_gate.py",
        "host": platform.node(),
        "platform": platform.platform(),
        "cpu_count": os.cpu_count() or 1,
        "governor": governor,
        "thread_env": {
            "OMP_NUM_THREADS": os.environ.get("OMP_NUM_THREADS", "1"),
            "OPENBLAS_NUM_THREADS": os.environ.get("OPENBLAS_NUM_THREADS", "1"),
            "MKL_NUM_THREADS": os.environ.get("MKL_NUM_THREADS", "1"),
        },
        "elf_path": str(elf_path),
        "elf_sha256": elf_sha256,
        "python_version": platform.python_version(),
        "networkx_version": nx.__version__,
    }


def maybe_apply_planted_slowdown(metric_id: str, base_elapsed_s: float) -> float:
    """Apply an optional planted slowdown for negative gate testing.

    Syntax via env `FNX_SLO_PLANT_SLOWDOWN`:
      - `<metric_id>` or `<metric_id>:2x`: sleep 500ms + 1.0 * base_elapsed_s
      - `<metric_id>:<ms>ms`: sleep `<ms>` milliseconds
      - `<metric_id>:<mult>x`: sleep `max((mult - 1.0) * base_elapsed_s, 0.5)` seconds
    """
    spec = os.environ.get("FNX_SLO_PLANT_SLOWDOWN", "").strip()
    if not spec:
        return 0.0
    for token in spec.split(","):
        token = token.strip()
        if not token:
            continue
        if ":" in token:
            target, arg = token.split(":", 1)
        else:
            target, arg = token, "500ms"
        if target.strip() != metric_id and target.strip() != "*":
            continue
        arg = arg.strip().lower()
        if arg.endswith("ms"):
            delay_s = float(arg[:-2]) / 1000.0
        elif arg.endswith("x"):
            mult = float(arg[:-1])
            delay_s = max((mult - 1.0) * base_elapsed_s, 0.5)
        else:
            delay_s = float(arg) / 1000.0
        time.sleep(delay_s)
        return delay_s
    return 0.0


def build_components_graph(mod, component_count: int, component_size: int):
    graph = mod.Graph()
    offset = 0
    for _ in range(component_count):
        for idx in range(component_size - 1):
            graph.add_edge(offset + idx, offset + idx + 1)
        offset += component_size
    return graph


def build_layered_flow_graph(mod, layers: int, width: int, seed: int = 0):
    graph = mod.DiGraph()
    source = "source"
    sink = "sink"
    previous = [source]
    for layer in range(layers):
        current = [f"L{layer}_{col}" for col in range(width)]
        for idx_u, left in enumerate(previous):
            for idx_v, right in enumerate(current):
                cap = (
                    7
                    if seed == 0
                    else 3 + ((layer * 17 + idx_u * 31 + idx_v * 13 + seed) % 19)
                )
                graph.add_edge(left, right, capacity=cap)
        previous = current
    for idx_u, node in enumerate(previous):
        cap = 7 if seed == 0 else 5 + ((idx_u * 7 + seed) % 11)
        graph.add_edge(node, sink, capacity=cap)
    return graph, source, sink


def _run_arm(mod, metric_id: str, params: dict, *, is_fnx: bool) -> dict[str, float]:
    setup_started = time.perf_counter()

    if metric_id == "shortest_path":
        width = int(params["width"])
        height = int(params["height"])
        graph = mod.grid_2d_graph(width, height)
        start = (0, 0) if (0, 0) in graph else "0,0"
        target = (
            (width - 1, height - 1)
            if (0, 0) in graph
            else f"{width - 1},{height - 1}"
        )
        setup_ms = (time.perf_counter() - setup_started) * 1000.0
        algo_started = time.perf_counter()
        path = mod.shortest_path(graph, start, target)
        if is_fnx:
            maybe_apply_planted_slowdown(metric_id, time.perf_counter() - algo_started)
        elapsed_ms = (time.perf_counter() - algo_started) * 1000.0
        if len(path) != width + height - 1:
            raise RuntimeError("unexpected shortest path length")
        primary_value = float(len(path))
        primary_unit = "path_nodes"

    elif metric_id == "shortest_path_weighted_delegated":
        node_count = int(params["nodes"])
        nonunit_weight = float(params["nonunit_weight"])
        chord_strides = [int(s) for s in params.get("chord_strides", [])]
        graph = mod.Graph()
        edges = [
            (str(node), str(node + 1), {"weight": nonunit_weight})
            for node in range(node_count - 1)
        ]
        for stride in chord_strides:
            if stride > 1 and node_count > stride:
                chord_w = stride * nonunit_weight + 5.0
                edges.extend(
                    (str(node), str(node + stride), {"weight": chord_w})
                    for node in range(0, node_count - stride, 2)
                )
        graph.add_edges_from(edges)
        setup_ms = (time.perf_counter() - setup_started) * 1000.0
        algo_started = time.perf_counter()
        path = mod.shortest_path(
            graph,
            "0",
            str(node_count - 1),
            weight="weight",
        )
        if is_fnx:
            maybe_apply_planted_slowdown(metric_id, time.perf_counter() - algo_started)
        elapsed_ms = (time.perf_counter() - algo_started) * 1000.0
        if len(path) != node_count:
            raise RuntimeError("unexpected delegated weighted shortest path length")
        primary_value = float(len(path))
        primary_unit = "path_nodes"

    elif metric_id == "components":
        component_count = int(params["component_count"])
        component_size = int(params["component_size"])
        k = int(params.get("k", 0))
        shards = int(params.get("shards", 1))
        if k > 0:
            comps_per_shard = max(1, component_count // shards)
            nodes_per_shard = comps_per_shard * component_size
            half_k = k // 2
            total_setup_s = 0.0
            total_algo_s = 0.0
            total_comps = 0
            total_edges = 0
            for shard in range(shards):
                s0 = time.perf_counter()
                graph = mod.watts_strogatz_graph(
                    nodes_per_shard, k, 0.0, seed=42 + shard
                )
                for c_idx in range(comps_per_shard):
                    boundary = c_idx * component_size
                    for offset in range(1, half_k + 1):
                        u = (boundary - offset) % nodes_per_shard
                        for step in range(offset, half_k + 1):
                            v = (u + step) % nodes_per_shard
                            if graph.has_edge(u, v):
                                graph.remove_edge(u, v)
                            c_u = boundary + offset
                            c_v = boundary + 100 + offset * 20 + step
                            graph.add_edge(c_u, c_v)
                total_edges += graph.number_of_edges()
                total_setup_s += time.perf_counter() - s0
                a0 = time.perf_counter()
                components = list(mod.connected_components(graph))
                total_algo_s += time.perf_counter() - a0
                total_comps += len(components)
                del graph, components
                gc.collect()
            if is_fnx:
                total_algo_s += maybe_apply_planted_slowdown(metric_id, total_algo_s)
            if total_comps != component_count:
                raise RuntimeError(
                    f"unexpected component count: {total_comps} != {component_count}"
                )
            if total_edges < (component_count * component_size * k) // 2:
                raise RuntimeError(f"unexpected total edges: {total_edges}")
            setup_ms = total_setup_s * 1000.0
            elapsed_ms = total_algo_s * 1000.0
            primary_value = float(total_comps)
            primary_unit = "component_count"
        else:
            graph = build_components_graph(mod, component_count, component_size)
            setup_ms = (time.perf_counter() - setup_started) * 1000.0
            algo_started = time.perf_counter()
            components = list(mod.connected_components(graph))
            if is_fnx:
                maybe_apply_planted_slowdown(
                    metric_id, time.perf_counter() - algo_started
                )
            elapsed_ms = (time.perf_counter() - algo_started) * 1000.0
            if len(components) != component_count:
                raise RuntimeError("unexpected component count")
            primary_value = float(len(components))
            primary_unit = "component_count"

    elif metric_id == "centrality":
        node_count = int(params["nodes"])
        edge_prob = float(params["edge_prob"])
        seed = int(params["seed"])
        k = int(params.get("k", 0))
        if k > 0:
            graph = mod.watts_strogatz_graph(node_count, k, edge_prob, seed=seed)
        else:
            graph = mod.gnp_random_graph(node_count, edge_prob, seed=seed)
        setup_ms = (time.perf_counter() - setup_started) * 1000.0
        algo_started = time.perf_counter()
        ranks = mod.pagerank(graph, tol=1.0e-6)
        if is_fnx:
            maybe_apply_planted_slowdown(metric_id, time.perf_counter() - algo_started)
        elapsed_ms = (time.perf_counter() - algo_started) * 1000.0
        if len(ranks) != node_count:
            raise RuntimeError("unexpected pagerank output size")
        if abs(sum(ranks.values()) - 1.0) > 1.0e-5:
            raise RuntimeError("pagerank sum drifted")
        primary_value = float(max(ranks.values()))
        primary_unit = "score"

    elif metric_id == "flow":
        topologies = params.get("topologies")
        if topologies:
            graphs = [
                build_layered_flow_graph(
                    mod,
                    int(topo["layers"]),
                    int(topo["width"]),
                    int(topo.get("seed", 0)),
                )
                for topo in topologies
            ]
        else:
            graphs = [
                build_layered_flow_graph(
                    mod,
                    int(params["layers"]),
                    int(params["width"]),
                    0,
                )
            ]
        setup_ms = (time.perf_counter() - setup_started) * 1000.0
        algo_started = time.perf_counter()
        flow_value = sum(
            mod.maximum_flow_value(g, src, snk, capacity="capacity")
            for g, src, snk in graphs
        )
        if is_fnx:
            maybe_apply_planted_slowdown(metric_id, time.perf_counter() - algo_started)
        elapsed_ms = (time.perf_counter() - algo_started) * 1000.0
        if flow_value <= 0:
            raise RuntimeError("expected positive flow value")
        primary_value = float(flow_value)
        primary_unit = "flow_value"

    elif metric_id == "io_roundtrip":
        node_count = int(params["nodes"])
        edge_prob = float(params["edge_prob"])
        seed = int(params["seed"])
        k = int(params.get("k", 0))
        if k > 0:
            graph = mod.watts_strogatz_graph(node_count, k, edge_prob, seed=seed)
        else:
            graph = mod.gnp_random_graph(node_count, edge_prob, seed=seed)
        setup_ms = (time.perf_counter() - setup_started) * 1000.0
        rounds = int(params["rounds"])
        processed_bytes = 0
        with tempfile.TemporaryDirectory(prefix="fnx-slo-io-") as tmpdir:
            path = Path(tmpdir) / "graph.edgelist"
            io_started = time.perf_counter()
            for _ in range(rounds):
                mod.write_edgelist(graph, path)
                processed_bytes += path.stat().st_size
                reloaded = mod.read_edgelist(path)
                processed_bytes += path.stat().st_size
                if reloaded.number_of_edges() != graph.number_of_edges():
                    raise RuntimeError("edgelist roundtrip edge drift")
            if is_fnx:
                maybe_apply_planted_slowdown(metric_id, time.perf_counter() - io_started)
            elapsed_s = time.perf_counter() - io_started
        elapsed_ms = elapsed_s * 1000.0
        primary_value = (processed_bytes / (1024.0 * 1024.0)) / elapsed_s
        primary_unit = "mb_per_s"

    elif metric_id == "mutation_cycle":
        node_count = int(params["node_count"])
        edge_repeat = int(params["edge_repeat"])
        setup_ms = 0.0
        algo_started = time.perf_counter()
        graph = mod.Graph()
        operations = 0
        for node in range(node_count):
            graph.add_node(node)
            operations += 1
        for _ in range(edge_repeat):
            for node in range(node_count - 1):
                graph.add_edge(node, node + 1)
                operations += 1
            for node in range(node_count - 1):
                graph.remove_edge(node, node + 1)
                operations += 1
        # Re-add incident edges before remove_node so remove_node exercises O(deg(u)) neighbor cleanup
        for node in range(node_count - 1):
            graph.add_edge(node, node + 1)
            operations += 1
        for node in range(node_count):
            graph.remove_node(node)
            operations += 1
        if graph.number_of_nodes() != 0:
            raise RuntimeError("mutation cycle should end empty")
        if is_fnx:
            maybe_apply_planted_slowdown(metric_id, time.perf_counter() - algo_started)
        elapsed_s = time.perf_counter() - algo_started
        elapsed_ms = elapsed_s * 1000.0
        primary_value = operations / elapsed_s
        primary_unit = "ops_per_s"

    else:
        raise RuntimeError(f"unsupported workload metric id: {metric_id}")

    return {
        "setup_ms": setup_ms,
        "elapsed_ms": elapsed_ms,
        "primary_value": primary_value,
        "primary_unit": primary_unit,
    }


def run_worker(spec: dict) -> dict:
    import franken_networkx as fnx

    metric_id = spec["metric_id"]
    params = spec.get("params", {})

    fnx_res = _run_arm(fnx, metric_id, params, is_fnx=True)
    fnx_rss_kb, fnx_hwm_kb = read_proc_rss_kb()
    gc.collect()

    import networkx as nx

    nx_res = _run_arm(nx, metric_id, params, is_fnx=False)
    nx_rss_kb, nx_hwm_kb = read_proc_rss_kb()
    gc.collect()

    # Verify result agreement between fnx and live networkx oracle on non-rate metrics
    if metric_id in {
        "shortest_path",
        "shortest_path_weighted_delegated",
        "components",
        "flow",
    }:
        if abs(fnx_res["primary_value"] - nx_res["primary_value"]) > 1.0e-9:
            raise RuntimeError(
                f"fnx vs nx primary_value mismatch on {metric_id}: "
                f"{fnx_res['primary_value']} != {nx_res['primary_value']}"
            )
    elif metric_id == "centrality":
        if abs(fnx_res["primary_value"] - nx_res["primary_value"]) > 1.0e-4:
            raise RuntimeError(
                f"fnx vs nx pagerank max score mismatch: "
                f"{fnx_res['primary_value']} != {nx_res['primary_value']}"
            )

    speedup_vs_nx = (
        nx_res["elapsed_ms"] / fnx_res["elapsed_ms"]
        if fnx_res["elapsed_ms"] > 0.0
        else 0.0
    )

    return {
        "metric_id": metric_id,
        "setup_ms": fnx_res["setup_ms"],
        "elapsed_ms": fnx_res["elapsed_ms"],
        "primary_value": fnx_res["primary_value"],
        "primary_unit": fnx_res["primary_unit"],
        "fnx_rss_kb": fnx_hwm_kb or fnx_rss_kb,
        "nx_setup_ms": nx_res["setup_ms"],
        "nx_elapsed_ms": nx_res["elapsed_ms"],
        "nx_primary_value": nx_res["primary_value"],
        "nx_rss_kb": nx_hwm_kb or nx_rss_kb,
        "speedup_vs_nx": speedup_vs_nx,
    }


def run_sample(
    python_bin: str,
    script_path: Path,
    spec: dict,
    *,
    measure_rss: bool,
) -> tuple[dict, float | None]:
    command = [
        python_bin,
        str(script_path),
        "--worker",
        "--worker-spec-json",
        json.dumps(spec, separators=(",", ":")),
    ]
    if not measure_rss:
        proc = subprocess.run(
            command,
            text=True,
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                "perf worker failed\n"
                f"metric: {spec['metric_id']}\n"
                f"stdout:\n{proc.stdout}\n"
                f"stderr:\n{proc.stderr}"
            )
        return json.loads(proc.stdout), None

    with tempfile.NamedTemporaryFile(prefix="fnx-slo-rss-", suffix=".txt", delete=False) as temp:
        rss_path = Path(temp.name)
    try:
        proc = subprocess.run(
            ["/usr/bin/time", "-f", "%M", "-o", str(rss_path), *command],
            text=True,
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                "perf worker failed\n"
                f"metric: {spec['metric_id']}\n"
                f"stdout:\n{proc.stdout}\n"
                f"stderr:\n{proc.stderr}"
            )
        payload = json.loads(proc.stdout)
        time_rss_kb = float(rss_path.read_text(encoding="utf-8").strip())
        fnx_rss_kb = float(payload.get("fnx_rss_kb") or time_rss_kb)
        return payload, fnx_rss_kb
    finally:
        rss_path.unlink(missing_ok=True)


def controller(args: argparse.Namespace) -> int:
    thresholds_path = Path(args.slo_thresholds)
    matrix_path = Path(args.matrix)
    regression_path = Path(args.regression_report)
    report_path = Path(args.report)
    script_path = Path(__file__).resolve()
    threshold_data = load_json(thresholds_path)
    regression_report = load_json(regression_path)
    provenance = collect_provenance()

    observations = []
    failures = []

    if regression_report.get("status") != "pass":
        failures.append(
            {
                "metric_id": "phase2c_regression_gate",
                "reason": "phase2c_regression_gate_failed",
                "status": regression_report.get("status"),
            }
        )

    for workload in threshold_data["workloads"]:
        latency_samples = []
        primary_samples = []
        rss_samples = []
        nx_latency_samples = []
        nx_primary_samples = []
        nx_rss_samples = []
        speedup_samples = []

        for _ in range(int(workload.get("warmup_runs", 0))):
            run_sample(args.python_bin, script_path, workload, measure_rss=False)

        for _ in range(int(workload["runs"])):
            payload, rss_kb = run_sample(
                args.python_bin,
                script_path,
                workload,
                measure_rss=True,
            )
            latency_samples.append(float(payload["elapsed_ms"]))
            primary_samples.append(float(payload["primary_value"]))
            rss_samples.append(float(rss_kb))
            nx_latency_samples.append(float(payload["nx_elapsed_ms"]))
            nx_primary_samples.append(float(payload["nx_primary_value"]))
            nx_rss_samples.append(float(payload.get("nx_rss_kb", rss_kb)))
            speedup_samples.append(float(payload["speedup_vs_nx"]))

        latency_summary = summarize(latency_samples)
        primary_summary = summarize(primary_samples)
        rss_summary = summarize(rss_samples)
        nx_latency_summary = summarize(nx_latency_samples)
        nx_primary_summary = summarize(nx_primary_samples)
        nx_rss_summary = summarize(nx_rss_samples)
        speedup_summary = summarize(speedup_samples)
        verdict_vs_nx = "WIN" if speedup_summary["p50"] >= 1.0 else "LOSS"
        checks = []
        status = "pass"

        if "max_p95_ms" in workload:
            passed = latency_summary["p95"] <= float(workload["max_p95_ms"])
            checks.append(
                {
                    "type": "latency_p95_ms",
                    "observed": latency_summary["p95"],
                    "threshold": float(workload["max_p95_ms"]),
                    "passed": passed,
                }
            )
            if not passed:
                status = "fail"

        if "min_primary_value" in workload:
            passed = primary_summary["mean"] >= float(workload["min_primary_value"])
            checks.append(
                {
                    "type": workload["primary_metric"],
                    "observed": primary_summary["mean"],
                    "threshold": float(workload["min_primary_value"]),
                    "passed": passed,
                }
            )
            if not passed:
                status = "fail"

        observation = {
            "metric_id": workload["metric_id"],
            "family": workload["family"],
            "primary_metric": workload["primary_metric"],
            "primary_unit": workload["primary_unit"],
            "workload": workload,
            "latency_ms": latency_summary,
            "primary_value": primary_summary,
            "max_rss_kb": rss_summary,
            "nx_latency_ms": nx_latency_summary,
            "nx_primary_value": nx_primary_summary,
            "nx_max_rss_kb": nx_rss_summary,
            "speedup_vs_nx": speedup_summary,
            "verdict_vs_nx": verdict_vs_nx,
            "checks": checks,
            "status": status,
        }
        observations.append(observation)

        if status != "pass":
            failures.append(
                {
                    "metric_id": workload["metric_id"],
                    "reason": "workload_threshold_exceeded",
                    "checks": [check for check in checks if not check["passed"]],
                }
            )

    max_rss_observed = max(row["max_rss_kb"]["p95"] for row in observations)
    max_latency_p99 = max(row["latency_ms"]["p99"] for row in observations)
    mutation_observation = next(
        row for row in observations if row["metric_id"] == "mutation_cycle"
    )

    derived_checks = []
    for check in threshold_data["derived_checks"]:
        if check["metric_id"] == "mutation_regression":
            baseline = float(check["baseline_ops_per_second"])
            threshold = baseline * (
                1.0 - float(check["max_regression_pct"]) / 100.0
            )
            observed = mutation_observation["primary_value"]["mean"]
            passed = observed >= threshold
            derived_checks.append(
                {
                    "metric_id": check["metric_id"],
                    "observed": observed,
                    "baseline": baseline,
                    "threshold": threshold,
                    "unit": "ops_per_s",
                    "passed": passed,
                }
            )
        elif check["metric_id"] == "memory_regression":
            baseline = float(check["baseline_max_rss_kb"])
            threshold = baseline * (
                1.0 + float(check["max_regression_pct"]) / 100.0
            )
            passed = max_rss_observed <= threshold
            derived_checks.append(
                {
                    "metric_id": check["metric_id"],
                    "observed": max_rss_observed,
                    "baseline": baseline,
                    "threshold": threshold,
                    "unit": "kb",
                    "passed": passed,
                }
            )
        elif check["metric_id"] == "p99_tail_regression":
            baseline = float(check["baseline_max_latency_p99_ms"])
            threshold = baseline * (
                1.0 + float(check["max_regression_pct"]) / 100.0
            )
            passed = max_latency_p99 <= threshold
            derived_checks.append(
                {
                    "metric_id": check["metric_id"],
                    "observed": max_latency_p99,
                    "baseline": baseline,
                    "threshold": threshold,
                    "unit": "ms",
                    "passed": passed,
                }
            )
        else:
            raise RuntimeError(f"unsupported derived check: {check['metric_id']}")

    for row in derived_checks:
        if not row["passed"]:
            failures.append(
                {
                    "metric_id": row["metric_id"],
                    "reason": "derived_threshold_exceeded",
                    "observed": row["observed"],
                    "threshold": row["threshold"],
                }
            )

    wins = [
        row["metric_id"]
        for row in observations
        if row.get("verdict_vs_nx") == "WIN"
    ]
    losses = [
        row["metric_id"]
        for row in observations
        if row.get("verdict_vs_nx") == "LOSS"
    ]

    report = {
        "schema_version": "1.0.0",
        "report_id": "slo-gate-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "slo_thresholds_path": str(thresholds_path),
        "matrix_path": str(matrix_path),
        "regression_report_path": str(regression_path),
        "python_bin": args.python_bin,
        "provenance": provenance,
        "phase2c_regression_status": regression_report.get("status"),
        "observations": observations,
        "derived_checks": derived_checks,
        "status": "fail" if failures else "pass",
        "summary": {
            "workload_count": len(observations),
            "failure_count": len(failures),
            "max_rss_p95_kb": max_rss_observed,
            "max_latency_p99_ms": max_latency_p99,
            "win_lose_split_vs_nx": {
                "wins": wins,
                "losses": losses,
                "win_count": len(wins),
                "loss_count": len(losses),
            },
        },
        "violations": failures,
    }

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"slo_gate_report:{report_path}")

    if failures:
        print(f"SLO GATE FAILED: {len(failures)} violation(s)")
        for failure in failures:
            print(f"  [{failure['metric_id']}] {failure['reason']}")
        return 1

    print(f"SLO GATE PASSED: {len(observations)} workloads and {len(derived_checks)} derived checks")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check benchmark results against SLO thresholds."
    )
    parser.add_argument(
        "--slo-thresholds",
        default="artifacts/perf/slo_thresholds.json",
        help="Path to SLO thresholds JSON file",
    )
    parser.add_argument(
        "--matrix",
        default="artifacts/perf/latest/perf_baseline_matrix_v1.json",
        help="Path to benchmark matrix JSON",
    )
    parser.add_argument(
        "--regression-report",
        default="artifacts/perf/phase2c/perf_regression_gate_report_v1.json",
        help="Path to regression gate report JSON",
    )
    parser.add_argument(
        "--report",
        default="artifacts/perf/latest/slo_gate_report_v1.json",
        help="Output path for SLO gate report",
    )
    parser.add_argument(
        "--python-bin",
        default=sys.executable,
        help="Python interpreter used for isolated workload samples",
    )
    parser.add_argument(
        "--worker",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--worker-spec-json",
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args()

    if args.worker:
        if not args.worker_spec_json:
            raise SystemExit("--worker requires --worker-spec-json")
        print(json.dumps(run_worker(json.loads(args.worker_spec_json))))
        return 0

    return controller(args)


if __name__ == "__main__":
    raise SystemExit(main())
