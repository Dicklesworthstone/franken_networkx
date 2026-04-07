# Performance

FrankenNetworkX is built around the idea that speedups only matter if observable behavior stays compatible with NetworkX. The performance workflow therefore combines measurement, regression detection, and artifact retention.

## What The Repo Measures

The checked-in benchmark pipeline currently tracks:

- topology classes: `grid`, `line`, `star`, `complete`, `erdos_renyi`,
- size buckets: `small`, `medium`, `large`,
- latency tails (`p95`, `p99`) and memory (`max_rss_kb`),
- hotspot backlog ranking and regression drift.

The main entry points are:

- [`scripts/run_benchmark_gate.sh`](../scripts/run_benchmark_gate.sh)
- [`scripts/run_perf_baseline_matrix.py`](../scripts/run_perf_baseline_matrix.py)
- [`scripts/run_perf_regression_gate.py`](../scripts/run_perf_regression_gate.py)
- [`scripts/run_perf_slo_gate.py`](../scripts/run_perf_slo_gate.py)

Artifacts land under [`artifacts/perf/`](../artifacts/perf/).

## Current Checked-In Gate Shape

The checked-in regression report is structured data that downstream tooling can consume directly:

```python
import json
from pathlib import Path

report = json.loads(
    Path("artifacts/perf/phase2c/perf_regression_gate_report_v1.json").read_text()
)

assert report["status"] in {"pass", "fail"}
assert report["summary"]["scenario_count"] >= 1
assert "regression_count" in report["summary"]
```

## SLO Surface

The SLO gate is configured in [`artifacts/perf/slo_thresholds.json`](../artifacts/perf/slo_thresholds.json).

It currently enforces or derives checks for:

- shortest-path latency,
- connected-components latency,
- centrality latency,
- flow latency,
- I/O throughput,
- mutation regression,
- memory regression,
- p99 tail regression.

```python
import json
from pathlib import Path

thresholds = json.loads(Path("artifacts/perf/slo_thresholds.json").read_text())

assert len(thresholds["workloads"]) >= 5
assert len(thresholds["derived_checks"]) >= 3
```

## Local Comparison Against NetworkX

Use the example benchmark script for a fast local sanity check:

```bash
python examples/benchmark_comparison.py
```

That script measures a small set of representative operations on identical graphs in NetworkX and FrankenNetworkX and prints JSON with median latency and speedup ratios.

## CI Gate

The GitHub Actions `G6 performance` job runs the benchmark gate and uploads the resulting artifacts. The goal is not just to catch catastrophic regressions, but to keep a durable paper trail for why the performance posture changed.

## Reading The Artifact Tree

- `artifacts/perf/phase2c/perf_baseline_matrix_v1.json` stores the structured candidate matrix.
- `artifacts/perf/phase2c/perf_regression_gate_report_v1.json` summarizes drift against the stored comparator.
- `artifacts/perf/cgse/` tracks deterministic tie-break policy benchmarks.
- `artifacts/perf/proof/` stores supporting evidence and proofs for specific optimizations.

For development workflow details, including `rch` usage for remote builds, see [contributing.md](contributing.md).
