# Risk Note

## Risk Surface
- parser/ingestion: malformed payloads for generator first wave.
- algorithmic denial vectors: adversarial graph shapes designed to trigger tail latency spikes.
- packet gate: `generator determinism gate`.

## Failure Modes
- fail-closed triggers: unknown incompatible feature, unsupported backend/version paths, contract-breaking malformed inputs.
- hardened degraded-mode triggers: allowlisted bounded controls only, with deterministic audit evidence.

## Mitigations
- controls: strict/hardened split, compatibility boundary matrix, and deterministic crash taxonomy.
- evidence coupling: threat rows map directly to adversarial fixture hooks and packet validation gates.
- policy: ad hoc hardened deviations are forbidden; unknown incompatible feature paths fail closed.

## Packet Threat Matrix
| threat id | threat class | strict mode response | hardened mode response | mitigations | evidence artifact | adversarial fixture / fuzz entrypoint | crash triage taxonomy | hardened allowlisted categories | compatibility boundary |
|---|---|---|---|---|---|---|---|---|---|
| P2C007-TM-1 | input_shape_abuse | Fail-closed on invalid create_using graph descriptors and preserve duplicate-node container semantics exactly without silent repair. | Apply only allowlisted deterministic diagnostics/tie-break normalization metadata and otherwise fail closed for incompatible input-shape pathways. | create_using type/instance guardrails; duplicate-node container parity assertions; deterministic node-order normalization checks | artifacts/phase2c/FNX-P2C-007/contract_table.md | generators_invalid_create_using_payload; generators_duplicate_node_container | generators.input.invalid_create_using_type; generators.input.duplicate_container_semantic_drift | bounded_diagnostic_enrichment; deterministic_tie_break_normalization | generator constructor and node-container boundary |
| P2C007-TM-2 | ordering_drift | Fail-closed when complete/cycle/path edge-order signatures diverge from legacy-observable order. | Permit only allowlisted deterministic tie-break normalization evidence; no output topology/order drift is allowed. | edge-order signature checkpoints; directed/undirected orientation parity assertions; fixture-level isomorphism signature verification | artifacts/phase2c/FNX-P2C-007/legacy_anchor_map.md | generators_ordering_drift_probe | generators.ordering.cycle_closure_drift; generators.ordering.path_emit_drift | bounded_diagnostic_enrichment; deterministic_tie_break_normalization | generator deterministic edge-order boundary |
| P2C007-TM-3 | resource_exhaustion | Fail-closed when generator workloads exceed strict node/edge budget envelopes. | Apply bounded resource clamps with deterministic admission diagnostics, then fail closed when budget violations remain unresolved. | node/edge budget sentinels; bounded workload admission checks; deterministic budget-exceeded telemetry | artifacts/phase2c/FNX-P2C-007/parity_gate.yaml | generators_large_n_budget_blowup | generators.resource.node_budget_exceeded; generators.resource.edge_budget_exceeded | bounded_diagnostic_enrichment; bounded_resource_clamp | generator workload budget boundary |
| P2C007-TM-4 | state_corruption | Fail-closed if create_using instance pathways violate clear-before-populate state invariants. | Run deterministic preflight/postflight state checks and fail closed if stale-state leakage is detected. | create_using.clear() invariant checks; post-generation edge/node cardinality assertions; state-reset replay forensics hooks | artifacts/phase2c/FNX-P2C-007/contract_table.md | generators_state_leak_reuse_instance | generators.state.preexisting_edges_not_cleared; generators.state.create_using_clear_contract_breach | bounded_diagnostic_enrichment | create_using state-reset boundary |
| P2C007-TM-5 | version_skew | Fail-closed on unsupported packet contract/version envelopes for generator-first-wave artifacts. | Reject incompatible envelopes with deterministic diagnostics; no compatibility fallback shims. | artifact contract version pinning; packet schema compatibility probes; gate-time version envelope checks | artifacts/phase2c/FNX-P2C-007/parity_gate.yaml | generators_contract_version_skew | generators.version.unsupported_contract_envelope; generators.version.packet_schema_mismatch | bounded_diagnostic_enrichment | generator contract version envelope boundary |

## Compatibility Boundary Matrix
| boundary id | strict parity obligation | hardened allowlisted deviation categories | fail-closed default | evidence hooks |
|---|---|---|---|---|
| P2C007-CB-1 | create_using dispatch and graph-instance clearing semantics match legacy behavior exactly. | bounded_diagnostic_enrichment; deterministic_tie_break_normalization | fail_closed_on_invalid_generator_create_using | networkx/generators/classic.py:667-680; networkx/generators/tests/test_classic.py:268-335; artifacts/phase2c/FNX-P2C-007/contract_table.md#error-contract |
| P2C007-CB-2 | duplicate-node container semantics for complete/cycle/path generators remain legacy-observable. | bounded_diagnostic_enrichment; deterministic_tie_break_normalization | fail_closed_on_duplicate_container_semantic_drift | networkx/generators/tests/test_classic.py:162-170; networkx/generators/tests/test_classic.py:225-235; networkx/generators/tests/test_classic.py:431-444 |
| P2C007-CB-3 | complete/cycle/path edge-order emission and directed orientation signatures remain deterministic. | bounded_diagnostic_enrichment; deterministic_tie_break_normalization | fail_closed_on_generator_edge_order_drift | generated/generators_complete_strict.json; generated/generators_cycle_strict.json; generated/generators_path_strict.json; artifacts/phase2c/FNX-P2C-007/legacy_anchor_map.md#extraction-ledger-crosswalk |
| P2C007-CB-4 | generator workloads remain within strict node/edge budget envelopes. | bounded_diagnostic_enrichment; bounded_resource_clamp | fail_closed_on_generator_workload_budget_exhausted | artifacts/phase2c/FNX-P2C-007/parity_gate.yaml; artifacts/perf/phase2c/perf_regression_gate_report_v1.json |
| P2C007-CB-5 | unknown generator feature/metadata pathways are rejected deterministically with zero output drift. | bounded_diagnostic_enrichment | fail_closed_on_unknown_generator_feature_path | artifacts/phase2c/FNX-P2C-007/parity_gate.yaml; artifacts/phase2c/FNX-P2C-007/risk_note.md#packet-threat-matrix |

## Hardened Deviation Guardrails
- allowlisted categories only: bounded_diagnostic_enrichment; deterministic_tie_break_normalization; bounded_resource_clamp.
- ad hoc hardened deviations: forbidden.
- unknown incompatible feature policy: fail_closed.

## Residual Risk
- unresolved risks: seed interpretation drift; edge emission order drift.
- follow-up actions: expand adversarial fixture diversity and keep crash triage mappings deterministic.
