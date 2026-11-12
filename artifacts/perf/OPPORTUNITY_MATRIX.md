# Opportunity Matrix

Scoring rule:
`score = (impact * confidence) / effort`

Only `score >= 2.0` is implementable.

| Hotspot | Impact | Confidence | Effort | Score | Decision |
|---|---:|---:|---:|---:|---|
| graph mutation determinism kernel (`fnx-classes`) | 5 | 5 | 2 | 12.5 | implemented |
| unweighted shortest path tie-break determinism (`fnx-algorithms`) | 5 | 4 | 2 | 10.0 | implemented |
| traversal neighbor allocation elimination (`fnx-classes` + `fnx-algorithms`) | 4 | 4 | 1 | 16.0 | implemented (2026-02-13) |
| full read/write parser hardening (`fnx-readwrite`) | 5 | 3 | 4 | 3.75 | queued |
| backend dispatch matrix parity (`fnx-dispatch`) | 4 | 3 | 3 | 4.0 | queued |
| RaptorQ sidecar pipeline (`fnx-conformance`) | 5 | 3 | 4 | 3.75 | queued |

Protocol artifacts:

- Baseline matrix: `artifacts/perf/phase2c/perf_baseline_matrix_v1.json`
- Structured run logs: `artifacts/perf/phase2c/perf_baseline_matrix_events_v1.jsonl`
- One-lever ranked backlog: `artifacts/perf/phase2c/hotspot_one_lever_backlog_v1.json`
- Optimization playbook: `artifacts/perf/phase2c/optimization_playbook_v1.md`
- Isomorphism harness report: `artifacts/perf/phase2c/isomorphism_harness_report_v1.json`
- Regression gate report: `artifacts/perf/phase2c/perf_regression_gate_report_v1.json`
