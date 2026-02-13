# Performance Artifact Layout

## Percentile benchmark gate

Run:

```bash
./scripts/run_benchmark_gate.sh
```

Produces:

- `artifacts/perf/latest/bfs_percentiles.json`
- `artifacts/perf/latest/bfs_percentiles.raptorq.json`
- `artifacts/perf/latest/bfs_percentiles.recovered.json`

Schema highlights in `bfs_percentiles.json`:
- `mean_ms`
- `p50_ms`
- `p95_ms`
- `p99_ms`
- `budgets.p95_pass`
- `budgets.p99_pass`
