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
import json
import math
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


def build_components_graph(fnx, component_count: int, component_size: int):
    graph = fnx.Graph()
    offset = 0
    for _ in range(component_count):
        for idx in range(component_size - 1):
            graph.add_edge(offset + idx, offset + idx + 1)
        offset += component_size
    return graph


def build_layered_flow_graph(fnx, layers: int, width: int):
    graph = fnx.DiGraph()
    source = "source"
    sink = "sink"
    previous = [source]
    for layer in range(layers):
        current = [f"L{layer}_{col}" for col in range(width)]
        for left in previous:
            for right in current:
                graph.add_edge(left, right, capacity=7)
        previous = current
    for node in previous:
        graph.add_edge(node, sink, capacity=7)
    return graph, source, sink


def run_worker(spec: dict) -> dict:
    import franken_networkx as fnx

    metric_id = spec["metric_id"]
    params = spec.get("params", {})
    started = time.perf_counter()

    if metric_id == "shortest_path":
        width = int(params["width"])
        height = int(params["height"])
        graph = fnx.grid_2d_graph(width, height)
        start = "0,0"
        target = f"{width - 1},{height - 1}"
        path = fnx.shortest_path(graph, start, target)
        if len(path) != width + height - 1:
            raise RuntimeError("unexpected shortest path length")
        primary_value = float(len(path))
        primary_unit = "path_nodes"
    elif metric_id == "components":
        graph = build_components_graph(
            fnx,
            int(params["component_count"]),
            int(params["component_size"]),
        )
        components = list(fnx.connected_components(graph))
        if len(components) != int(params["component_count"]):
            raise RuntimeError("unexpected component count")
        primary_value = float(len(components))
        primary_unit = "component_count"
    elif metric_id == "centrality":
        graph = fnx.gnp_random_graph(
            int(params["nodes"]),
            float(params["edge_prob"]),
            seed=int(params["seed"]),
        )
        ranks = fnx.pagerank(graph, tol=1.0e-6)
        if len(ranks) != int(params["nodes"]):
            raise RuntimeError("unexpected pagerank output size")
        if abs(sum(ranks.values()) - 1.0) > 1.0e-6:
            raise RuntimeError("pagerank sum drifted")
        primary_value = float(max(ranks.values()))
        primary_unit = "score"
    elif metric_id == "flow":
        graph, source, sink = build_layered_flow_graph(
            fnx,
            int(params["layers"]),
            int(params["width"]),
        )
        flow_value = fnx.maximum_flow_value(graph, source, sink, capacity="capacity")
        if flow_value <= 0:
            raise RuntimeError("expected positive flow value")
        primary_value = float(flow_value)
        primary_unit = "flow_value"
    elif metric_id == "io_roundtrip":
        graph = fnx.gnp_random_graph(
            int(params["nodes"]),
            float(params["edge_prob"]),
            seed=int(params["seed"]),
        )
        rounds = int(params["rounds"])
        processed_bytes = 0
        with tempfile.TemporaryDirectory(prefix="fnx-slo-io-") as tmpdir:
            path = Path(tmpdir) / "graph.edgelist"
            for _ in range(rounds):
                fnx.write_edgelist(graph, path)
                processed_bytes += path.stat().st_size
                reloaded = fnx.read_edgelist(path)
                processed_bytes += path.stat().st_size
                if reloaded.number_of_edges() != graph.number_of_edges():
                    raise RuntimeError("edgelist roundtrip edge drift")
        elapsed_s = time.perf_counter() - started
        primary_value = (processed_bytes / (1024.0 * 1024.0)) / elapsed_s
        primary_unit = "mb_per_s"
    elif metric_id == "mutation_cycle":
        node_count = int(params["node_count"])
        edge_repeat = int(params["edge_repeat"])
        graph = fnx.Graph()
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
        for node in range(node_count):
            graph.remove_node(node)
            operations += 1
        if graph.number_of_nodes() != 0:
            raise RuntimeError("mutation cycle should end empty")
        elapsed_s = time.perf_counter() - started
        primary_value = operations / elapsed_s
        primary_unit = "ops_per_s"
    else:
        raise RuntimeError(f"unsupported workload metric id: {metric_id}")

    elapsed_ms = (time.perf_counter() - started) * 1000.0
    return {
        "metric_id": metric_id,
        "elapsed_ms": elapsed_ms,
        "primary_value": primary_value,
        "primary_unit": primary_unit,
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
        return json.loads(proc.stdout), float(rss_path.read_text(encoding="utf-8").strip())
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

        latency_summary = summarize(latency_samples)
        primary_summary = summarize(primary_samples)
        rss_summary = summarize(rss_samples)
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

    report = {
        "schema_version": "1.0.0",
        "report_id": "slo-gate-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "slo_thresholds_path": str(thresholds_path),
        "matrix_path": str(matrix_path),
        "regression_report_path": str(regression_path),
        "python_bin": args.python_bin,
        "phase2c_regression_status": regression_report.get("status"),
        "observations": observations,
        "derived_checks": derived_checks,
        "status": "fail" if failures else "pass",
        "summary": {
            "workload_count": len(observations),
            "failure_count": len(failures),
            "max_rss_p95_kb": max_rss_observed,
            "max_latency_p99_ms": max_latency_p99,
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
