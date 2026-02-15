# Baseline - BFS V1 (Phase2C Matrix)

This document is retained as the profile baseline path referenced by
`artifacts/phase2c/essence_extraction_ledger_v1.json`.

Canonical machine artifact:

- `artifacts/perf/phase2c/perf_baseline_matrix_v1.json`
- `artifacts/perf/phase2c/perf_baseline_matrix_events_v1.jsonl`
- `artifacts/perf/phase2c/hotspot_one_lever_backlog_v1.json`
- `artifacts/perf/phase2c/optimization_playbook_v1.md`
- `artifacts/perf/phase2c/isomorphism_harness_report_v1.json`
- `artifacts/perf/phase2c/perf_regression_gate_report_v1.json`

Generation command:

```bash
./scripts/run_benchmark_gate.sh
```

Protocol guarantees:

- deterministic scenario seeds (`--seed` explicitly set per scenario),
- fixed run/warmup counts (`runs=5`, `warmup=1`),
- reproducibility metadata (`environment`, `environment_fingerprint`, `git_commit`),
- per-scenario timing and memory tails (`p50`, `p95`, `p99` for runtime + max RSS).

Representative matrix dimensions:

- topology: `grid`, `line`, `star`, `complete`, `erdos_renyi`
- size buckets: `small`, `medium`, `large`
- density classes: `ultra_sparse`, `sparse_lattice`, `hub_sparse`, `medium_random`, `dense_complete`

The versioned JSON artifact is the source of truth for numerical baselines.
