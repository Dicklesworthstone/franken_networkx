# Isomorphism Proof — FNX-P2C-007 (V1)

## Baseline
- comparator: legacy_networkx/main@python3.12
- packet: FNX-P2C-007 (Generator first wave)

## Observable Contract
- output contract preserved under strict mode.
- hardened mode preserves API contract while applying bounded defensive controls.
- deterministic tie-break and ordering invariants maintained.

## Profile-First Evidence
- baseline profile matrix (p50/p95/p99 latency + memory): artifacts/perf/phase2c/perf_baseline_matrix_v1.json
- hotspot backlog + one-lever policy + EV score (`perf-one-lever-01`, EV 38.91): artifacts/perf/phase2c/hotspot_one_lever_backlog_v1.json
- post-change regression delta gate (p95/p99 and memory tails): artifacts/perf/phase2c/perf_regression_gate_report_v1.json
- behavior-isomorphism harness (golden signatures, mismatch policy): artifacts/perf/phase2c/isomorphism_harness_report_v1.json

## Optimization Lever
- pre-sized node-label buffer reused across generator edge emission paths (`GraphGenerator::{path,cycle,complete,gnp_random_graph}`) to avoid repeated integer-to-string formatting during edge insertion.

## Decision-Theoretic Runtime Contract
- states: `{regression, parity_preserved_speedup}`
- actions: `{ship_optimization, rollback}`
- loss model: `regression_cost >> unrealized_speedup`
- safe-mode fallback trigger: rollback if p95/p99 regresses by `>5%` for two consecutive gate runs
- rollback path: `git revert <optimization-commit-sha>`

## Differential + Parity Artifacts
- fixture ids: generated/generators_path_strict.json, generated/generators_cycle_strict.json, generated/generators_complete_strict.json
- parity report: artifacts/phase2c/FNX-P2C-007/parity_report.json
- raptorq sidecar: artifacts/phase2c/FNX-P2C-007/parity_report.raptorq.json
- decode proof: artifacts/phase2c/FNX-P2C-007/parity_report.decode_proof.json

## Structured Replay / Forensics
- unit replay command metadata: `rch exec -- cargo test -p fnx-generators unit_packet_007_contract_asserted -- --nocapture` (embedded in structured test log schema)
- property replay command metadata: `rch exec -- cargo test -p fnx-generators property_packet_007_invariants -- --nocapture` (embedded in structured test log schema)
- e2e bundle references: artifacts/e2e/latest/bundles/generators_path_strict/, artifacts/e2e/latest/bundles/generators_cycle_hardened/

## Result
- status: pass
- mismatch budget: 0
