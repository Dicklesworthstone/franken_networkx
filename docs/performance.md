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

It enforces or derives checks across Spec §17 representative scale workloads with a live `networkx` comparator arm in the same worker invocation:

- shortest-path latency (`250x250` unweighted grid and `25,000`-node sparse weighted graph),
- connected-components latency (`100,000` nodes, `1,000,000` edges across `20` components),
- centrality latency (`50,000` nodes, `100,000` edges PageRank),
- flow latency (multi-seed layered flow corpus),
- I/O throughput (`12,000` nodes, `60,000` edges edgelist write+read roundtrip),
- mutation regression (`5,000` nodes, `44,993` operations including incident-edge `remove_node`),
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

## Release Quality Gate (DSR)

Doodlestein Self-Releaser (`dsr quality --tool franken_networkx`) is the exclusive quality and release authority. The SLO gate (`scripts/run_perf_slo_gate.py`) records self-reported provenance (host, CPU governor, thread configuration, and `_fnx` ELF SHA-256) alongside paired `fnx` and `networkx` latency/memory distributions and explicit win/loss splits in `artifacts/perf/latest/slo_gate_report_v1.json`.

## Reading The Artifact Tree

- `artifacts/perf/phase2c/perf_baseline_matrix_v1.json` stores the structured candidate matrix.
- `artifacts/perf/phase2c/perf_regression_gate_report_v1.json` summarizes drift against the stored comparator.
- `artifacts/perf/latest/slo_gate_report_v1.json` stores the Spec §17 SLO gate report with live NetworkX comparator measurements and provenance.
- `artifacts/perf/cgse/` tracks deterministic tie-break policy benchmarks.
- `artifacts/perf/proof/` stores supporting evidence and proofs for specific optimizations.

For development workflow details, including `rch` usage for remote builds, see [contributing.md](contributing.md).
