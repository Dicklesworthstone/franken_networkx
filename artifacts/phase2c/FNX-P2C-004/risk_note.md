# Risk Note

## Risk Surface
- parser/ingestion: malformed payloads for conversion and relabel contracts.
- algorithmic denial vectors: adversarial graph shapes designed to trigger tail latency spikes.
- packet gate: `conversion matrix gate`.

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
| P2C004-TM-1 | parser_abuse | Fail-closed on malformed conversion payload structures and invalid edge-list coercion. | Fail-closed with bounded diagnostics and defensive parse recovery before deterministic abort. | payload schema checks; field cardinality validation; malformed payload fixtures | artifacts/phase2c/FNX-P2C-004/risk_note.md | conversion_payload_malformed_shape | convert.parse.malformed_payload; convert.parse.field_cardinality_invalid | bounded_diagnostic_enrichment; defensive_parse_recovery | conversion parse boundary |
| P2C004-TM-2 | metadata_ambiguity | Fail-closed on ambiguous node/edge attribute precedence and conflicting metadata envelopes. | Quarantine unsupported metadata and preserve deterministic precedence ordering. | attribute precedence table; metadata allowlist; attribute drift report | artifacts/phase2c/FNX-P2C-004/contract_table.md | conversion_conflicting_attribute_metadata | convert.metadata.ambiguous_precedence; convert.metadata.conflicting_attribute_source | bounded_diagnostic_enrichment; quarantine_of_unsupported_metadata | attribute precedence normalization boundary |
| P2C004-TM-3 | version_skew | Fail-closed on unsupported conversion schema versions or contract envelopes. | Reject incompatible schema versions with deterministic remediation diagnostics. | schema version pinning; compatibility probes; version skew fixtures | artifacts/phase2c/FNX-P2C-004/parity_gate.yaml | conversion_schema_version_skew | convert.version.unsupported_schema; convert.version.contract_mismatch | bounded_diagnostic_enrichment | conversion schema version envelope boundary |
| P2C004-TM-4 | resource_exhaustion | Fail-closed on conversion expansion above strict complexity or memory budget. | Apply bounded resource clamps and reject once deterministic thresholds are exceeded. | bounded conversion passes; memory budget guards; expansion ratio checks | artifacts/phase2c/FNX-P2C-004/parity_gate.yaml | conversion_expansion_ratio_blowup | convert.resource.expansion_ratio_exceeded; convert.resource.budget_threshold_exceeded | bounded_diagnostic_enrichment; bounded_resource_clamp | conversion expansion budget boundary |
| P2C004-TM-5 | state_corruption | Fail-closed when conversion/relabel mutates graph state outside declared transaction boundary. | Rollback conversion transaction and emit deterministic incident evidence before fail-closed exit. | mutation boundary checks; transaction rollback points; round-trip invariants | artifacts/phase2c/FNX-P2C-004/contract_table.md | conversion_transaction_boundary_break | convert.state.transaction_boundary_break; convert.state.roundtrip_invariant_break | bounded_diagnostic_enrichment | conversion transaction boundary |
| P2C004-TM-6 | attribute_confusion | Fail-closed on duplicate/conflicting attribute namespaces and ambiguous relabel collisions. | Apply deterministic namespace canonicalization policy and reject unresolved conflicts. | attribute namespace validation; canonicalization policy; conflict fixtures | artifacts/phase2c/FNX-P2C-004/risk_note.md | conversion_attribute_namespace_collision | convert.metadata.namespace_collision; convert.metadata.canonicalization_conflict | bounded_diagnostic_enrichment; deterministic_tie_break_normalization | attribute namespace canonicalization boundary |

## Compatibility Boundary Matrix
| boundary id | strict parity obligation | hardened allowlisted deviation categories | fail-closed default | evidence hooks |
|---|---|---|---|---|
| P2C004-CB-1 | Malformed conversion payloads never yield repaired outputs in strict mode. | bounded_diagnostic_enrichment; defensive_parse_recovery | fail_closed_on_malformed_conversion_payload | networkx/tests/test_convert.py:45-69; artifacts/phase2c/FNX-P2C-004/risk_note.md#packet-threat-matrix |
| P2C004-CB-2 | Attribute metadata precedence remains deterministic and parity-preserving. | bounded_diagnostic_enrichment; quarantine_of_unsupported_metadata | fail_closed_on_ambiguous_metadata | networkx/tests/test_convert.py:134-210; artifacts/phase2c/FNX-P2C-004/contract_table.md#input-contract |
| P2C004-CB-3 | Unsupported schema/version envelopes are rejected deterministically. | bounded_diagnostic_enrichment | fail_closed_on_version_skew | networkx/tests/test_convert.py:45-69; artifacts/phase2c/FNX-P2C-004/parity_gate.yaml |
| P2C004-CB-4 | Conversion expansion must stay within strict complexity budgets. | bounded_diagnostic_enrichment; bounded_resource_clamp | fail_closed_when_conversion_budget_exhausted | artifacts/phase2c/FNX-P2C-004/parity_gate.yaml; artifacts/perf/phase2c/perf_regression_gate_report_v1.json |
| P2C004-CB-5 | Conversion transaction boundaries preserve graph-state invariants exactly. | bounded_diagnostic_enrichment | fail_closed_on_conversion_state_invariant_break | networkx/tests/test_relabel.py:208-317; artifacts/phase2c/FNX-P2C-004/contract_table.md#machine-checkable-invariant-matrix |
| P2C004-CB-6 | Attribute namespace conflicts fail closed without hidden key rewrites. | bounded_diagnostic_enrichment; deterministic_tie_break_normalization | fail_closed_on_attribute_namespace_conflict | networkx/tests/test_relabel.py:296-310; artifacts/phase2c/FNX-P2C-004/risk_note.md#compatibility-boundary-matrix |

## Hardened Deviation Guardrails
- allowlisted categories only: bounded_diagnostic_enrichment; defensive_parse_recovery; bounded_resource_clamp; deterministic_tie_break_normalization; quarantine_of_unsupported_metadata.
- ad hoc hardened deviations: forbidden.
- unknown incompatible feature policy: fail_closed.

## Residual Risk
- unresolved risks: input precedence drift; relabel contract divergence; multigraph key collision drift.
- follow-up actions: expand adversarial fixture diversity and keep crash triage mappings deterministic.
