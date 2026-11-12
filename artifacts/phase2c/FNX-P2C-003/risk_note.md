# Risk Note

## Risk Surface
- parser/ingestion: malformed payloads for dispatchable backend routing.
- algorithmic denial vectors: adversarial graph shapes designed to trigger tail latency spikes.
- packet gate: `dispatch route lock`.

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
| P2C003-TM-1 | parser_abuse | Fail-closed on malformed backend configuration payloads and route signatures. | Fail-closed with bounded deterministic diagnostics; no permissive parse fallback. | backend config schema checks; route signature validation; deterministic parse error taxonomy | artifacts/phase2c/FNX-P2C-003/risk_note.md | dispatch_config_malformed_payload | dispatch.parse.malformed_payload; dispatch.parse.signature_mismatch | bounded_diagnostic_enrichment | backend config parse boundary |
| P2C003-TM-2 | metadata_ambiguity | Fail-closed on ambiguous backend metadata and conflicting routing hints. | Quarantine unsupported metadata and fail-closed when parity impact is not provably safe. | backend metadata allowlist; deterministic route ranking; metadata drift ledger | artifacts/phase2c/FNX-P2C-003/risk_note.md | dispatch_conflicting_backend_metadata | dispatch.metadata.ambiguous_hint; dispatch.metadata.conflicting_source | bounded_diagnostic_enrichment; quarantine_of_unsupported_metadata | metadata normalization boundary |
| P2C003-TM-3 | version_skew | Fail-closed on unsupported backend API versions or incompatible route contracts. | Reject incompatible versions with deterministic remediation diagnostics. | version envelope lock; backend feature compatibility matrix; upgrade gate checks | artifacts/phase2c/FNX-P2C-003/parity_gate.yaml | dispatch_backend_api_version_skew | dispatch.version.unsupported_backend_api; dispatch.version.contract_mismatch | bounded_diagnostic_enrichment | backend API version envelope boundary |
| P2C003-TM-4 | resource_exhaustion | Fail-closed on route-search or dispatch costs above strict policy budgets. | Apply bounded dispatch clamps and reject when budget thresholds are exhausted. | dispatch budget caps; timeout guards; tail latency monitoring | artifacts/phase2c/FNX-P2C-003/parity_gate.yaml | dispatch_route_fanout_exhaustion | dispatch.resource.route_fanout_exhaustion; dispatch.resource.budget_threshold_exceeded | bounded_diagnostic_enrichment; bounded_resource_clamp | dispatch budget boundary |
| P2C003-TM-5 | state_corruption | Fail-closed when dispatch cache state violates deterministic invariants. | Reset dispatch cache state and fail-closed with deterministic incident evidence. | cache key determinism tests; route state checksums; cache rollback hooks | artifacts/phase2c/FNX-P2C-003/contract_table.md | dispatch_cache_state_break | dispatch.state.cache_invariant_break; dispatch.state.replay_mismatch | bounded_diagnostic_enrichment | dispatch cache determinism boundary |
| P2C003-TM-6 | backend_route_ambiguity | Fail-closed on equal-precedence competing backend routes. | Apply deterministic allowlisted fallback route with full audit trace or fail-closed. | explicit route priority matrix; tie-break policy witness; route drift tests | artifacts/phase2c/FNX-P2C-003/contract_table.md | dispatch_equal_priority_route_collision | dispatch.route.equal_precedence_collision; dispatch.route.fallback_audit_required | bounded_diagnostic_enrichment; deterministic_backend_fallback_with_audit | backend route priority boundary |
| P2C003-TM-7 | policy_bypass | Fail-closed on any policy override or unsafe enforcement bypass attempt. | Ignore unauthorized overrides, emit deterministic bypass evidence, and halt route execution. | policy signature verification; immutable enforcement toggle registry; override injection adversarial fixtures | artifacts/phase2c/FNX-P2C-003/risk_note.md | dispatch_policy_override_injection | dispatch.policy.unauthorized_override; dispatch.policy.signature_verification_failed | bounded_diagnostic_enrichment | policy enforcement boundary |

## Compatibility Boundary Matrix
| boundary id | strict parity obligation | hardened allowlisted deviation categories | fail-closed default | evidence hooks |
|---|---|---|---|---|
| P2C003-CB-1 | Backend override and selection remain deterministic and parity-preserving. | bounded_diagnostic_enrichment; deterministic_backend_fallback_with_audit | fail_closed_on_unknown_or_unsupported_backend | networkx/utils/tests/test_backends.py:44-95; artifacts/phase2c/FNX-P2C-003/contract_table.md#input-contract |
| P2C003-CB-2 | Unsupported metadata never changes observable route identity. | bounded_diagnostic_enrichment; quarantine_of_unsupported_metadata | fail_closed_on_unproven_metadata_safety | networkx/utils/tests/test_backends.py:135-160; artifacts/phase2c/FNX-P2C-003/risk_note.md#packet-threat-matrix |
| P2C003-CB-3 | Unsupported backend API envelopes are rejected with deterministic errors. | bounded_diagnostic_enrichment | fail_closed_on_version_skew | networkx/utils/tests/test_config.py:120-170; artifacts/phase2c/FNX-P2C-003/parity_gate.yaml |
| P2C003-CB-4 | Dispatch search does not exceed strict complexity budgets. | bounded_diagnostic_enrichment; bounded_resource_clamp | fail_closed_when_budget_exhausted | artifacts/phase2c/FNX-P2C-003/parity_gate.yaml; artifacts/perf/phase2c/perf_regression_gate_report_v1.json |
| P2C003-CB-5 | Dispatch cache semantics remain deterministic and replayable. | bounded_diagnostic_enrichment | fail_closed_on_cache_invariant_break | networkx/classes/tests/dispatch_interface.py:186-190; artifacts/phase2c/FNX-P2C-003/contract_table.md#machine-checkable-invariant-matrix |
| P2C003-CB-6 | Unknown incompatible feature paths fail closed with no implicit repair. | bounded_diagnostic_enrichment | fail_closed_on_unknown_incompatible_feature | networkx/utils/tests/test_backends.py:162-168; artifacts/phase2c/FNX-P2C-003/risk_note.md#compatibility-boundary-matrix |

## Hardened Deviation Guardrails
- allowlisted categories only: bounded_diagnostic_enrichment; bounded_resource_clamp; deterministic_backend_fallback_with_audit; quarantine_of_unsupported_metadata.
- ad hoc hardened deviations: forbidden.
- unknown incompatible feature policy: fail_closed.

## Residual Risk
- unresolved risks: backend route ambiguity; unknown feature bypass risk.
- follow-up actions: expand adversarial fixture diversity and keep crash triage mappings deterministic.
