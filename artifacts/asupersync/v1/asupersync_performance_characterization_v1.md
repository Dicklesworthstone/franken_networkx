# asupersync Performance Characterization + Optimization Safety Proof (V1)

- generated_at_utc: `2026-02-16T22:22:00Z`
- baseline_comparator: `legacy_networkx/main@python3.12 + asupersync@0.2.0`
- optimization_lever: `ASUP-E-LEV-001` (`Vec::with_capacity` preallocation for adapter transitions)

## Measurement Corpus

- command:
  - `/usr/bin/time -f 'elapsed_s=%e max_rss_kb=%M' rch exec -- cargo test -q -p fnx-runtime asupersync_adapter_ -- --nocapture >/dev/null`
- runs: `7`
- stable-window policy: retain runs with `elapsed_s <= 12.0` for tail-regression decisions

## Stable-Window Metrics

| Metric | Baseline | Candidate | Delta % |
|---|---:|---:|---:|
| elapsed p50 (s) | 10.7250 | 10.7600 | +0.3263 |
| elapsed p95 (s) | 10.7800 | 10.7760 | -0.0371 |
| elapsed p99 (s) | 10.7800 | 10.7792 | -0.0074 |
| max_rss p50 (KB) | 8380.0 | 8344.0 | -0.4296 |
| max_rss p95 (KB) | 8410.0 | 8408.0 | -0.0238 |
| max_rss p99 (KB) | 8414.8 | 8414.4 | -0.0048 |

## Tail Regression Gate

- latency_tail_pct_threshold: `5.0%`
- memory_tail_pct_threshold: `5.0%`
- evaluated_on: `stable_window_metrics (elapsed_s <= 12.0 seconds)`
- status: `pass`

## Safety Rationale

- state-machine semantics are unchanged; only transition-log capacity provisioning changed.
- deterministic/fault-path asupersync adapter tests remain required.
- gate fails closed if stable-window tails exceed configured thresholds.

## Replay Commands

- unit: `rch exec -- cargo test -q -p fnx-runtime asupersync_adapter_ -- --nocapture`
- differential: `rch exec -- cargo test -q -p fnx-conformance --test asupersync_performance_gate -- --nocapture`
- e2e: `bash ./scripts/run_phase2c_readiness_e2e.sh`
