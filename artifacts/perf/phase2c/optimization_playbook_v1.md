# Optimization Playbook V1

## Purpose
Define a profile-first optimization workflow that preserves NetworkX-observable behavior.

## One-Lever Rule
- Every optimization change must target exactly one lever.
- Multi-lever changes are rejected until split into independently verifiable patches.
- Candidate levers must come from `artifacts/perf/phase2c/hotspot_one_lever_backlog_v1.json`.

## Required Evidence Per Change
1. Baseline comparator from `artifacts/perf/phase2c/perf_baseline_matrix_v1.json`.
2. Hotspot profile linkage from `artifacts/perf/phase2c/hotspot_one_lever_backlog_v1.json`.
3. Isomorphism harness pass report from `artifacts/perf/phase2c/isomorphism_harness_report_v1.json`.
4. Risk note and rollback path recorded in the backlog entry.

## Behavior-Isomorphism Obligations
- Observable outputs (including tie-break-sensitive paths) must match golden signatures.
- Harness command:
  ```bash
  python3 scripts/run_perf_isomorphism_harness.py
  ```
- Golden signatures:
  `artifacts/perf/phase2c/isomorphism_golden_signatures_v1.json`

## Divergence Policy
- Default policy is fail-closed: any signature mismatch blocks landing.
- Divergence must be explicitly approved by adding scenario-specific entries to:
  `artifacts/perf/phase2c/isomorphism_divergence_allowlist_v1.json`
- Unapproved divergence is a hard failure.

## Decision-Theoretic Runtime Contract
- States: `{regression, parity_preserved_speedup}`
- Actions: `{ship_optimization, rollback}`
- Loss model: `regression_cost >> unrealized_speedup`
- Fallback trigger: rollback when p95/p99 regress by more than 5% for two consecutive gate runs.
