# Performance Artifact Layout

## Phase2C baseline matrix gate

Run:

```bash
./scripts/run_benchmark_gate.sh
```

Primary baseline artifacts:

- `artifacts/perf/phase2c/perf_baseline_matrix_v1.json` (versioned source-of-truth)
- `artifacts/perf/phase2c/perf_baseline_matrix_events_v1.jsonl` (deterministic run-event log)
- `artifacts/perf/phase2c/hotspot_one_lever_backlog_v1.json` (ranked single-lever backlog)
- `artifacts/perf/phase2c/optimization_playbook_v1.md` (execution policy + obligations)
- `artifacts/perf/phase2c/isomorphism_golden_signatures_v1.json`
- `artifacts/perf/phase2c/isomorphism_harness_report_v1.json`
- `artifacts/perf/phase2c/isomorphism_divergence_allowlist_v1.json`
- `artifacts/perf/phase2c/perf_regression_gate_report_v1.json`
- `artifacts/perf/latest/perf_baseline_matrix_v1.json` (latest copy)
- `artifacts/perf/latest/perf_baseline_matrix_v1.raptorq.json`
- `artifacts/perf/latest/perf_baseline_matrix_v1.recovered.json`
- `artifacts/perf/latest/durability_pipeline_report.json`

`perf_baseline_matrix_v1.json` highlights:

- `measurement_protocol.runs` / `measurement_protocol.warmup_runs`
- `measurement_protocol.fixed_seed_policy`
- `environment` and `environment_fingerprint`
- `events_path` pointing to JSONL run logs with replay commands
- `scenarios[]` with representative topology/size/density classes
- per-scenario `time_ms.{p50,p95,p99}` and `max_rss_kb.{p50,p95,p99}`
- `summary.topology_classes`, `summary.size_buckets`, `summary.density_classes`

`hotspot_one_lever_backlog_v1.json` highlights:

- `hotspot_profiles[]` ranked by measured bottleneck pressure
- `optimization_backlog[]` sorted by EV score with `lever_count == 1`
- explicit `fallback_trigger` and `rollback_path` per backlog entry
- links to isomorphism proofs and packet optimization beads

Isomorphism harness highlights:

- scenario output signatures must match `isomorphism_golden_signatures_v1.json`
- default policy is fail-closed (`blocking_default: true`)
- any mismatch requires explicit scenario entry in divergence allowlist

Regression gate highlights:

- compares candidate tails/memory against baseline comparator per scenario
- includes hotspot-linked delta summaries and triage rows
- enforces fail-closed policy for critical scenarios
