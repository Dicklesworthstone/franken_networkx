# Risk Note

## Risk Surface
- parser/ingestion: malformed payloads for read/write edgelist and json graph.
- algorithmic denial vectors: adversarial graph shapes designed to trigger tail latency spikes.
- packet gate: `parser adversarial gate`.

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
| P2C006-TM-1 | parser_abuse | Fail-closed on malformed edgelist rows, invalid nodetype coercions, and malformed typed edge-data payloads. | Perform bounded defensive parse recovery only for allowlisted malformed-line categories, otherwise fail closed with deterministic diagnostics. | line-shape cardinality checks; nodetype conversion guards; typed edge-data coercion checks | artifacts/phase2c/FNX-P2C-006/risk_note.md | readwrite_malformed_edgelist_rows | readwrite.parse.malformed_line; readwrite.parse.invalid_nodetype_conversion | bounded_diagnostic_enrichment; defensive_parse_recovery | edgelist parse boundary |
| P2C006-TM-2 | metadata_ambiguity | Fail-closed on ambiguous json_graph id/source/target/key naming and conflicting readwrite metadata envelopes. | Quarantine unsupported metadata, preserve deterministic precedence, and fail closed if compatibility parity cannot be proven. | json_graph attribute uniqueness validation; metadata namespace allowlist; deterministic metadata precedence table | artifacts/phase2c/FNX-P2C-006/contract_table.md | readwrite_json_attribute_namespace_collision | readwrite.metadata.ambiguous_attribute_namespace; readwrite.metadata.conflicting_envelope_fields | bounded_diagnostic_enrichment; quarantine_of_unsupported_metadata | json_graph metadata normalization boundary |
| P2C006-TM-3 | version_skew | Fail-closed on unsupported packet contract or fixture schema versions. | Reject incompatible version envelopes with deterministic compatibility diagnostics. | contract version pinning; schema compatibility probes; fixture manifest version checks | artifacts/phase2c/FNX-P2C-006/parity_gate.yaml | readwrite_contract_version_skew | readwrite.version.unsupported_contract_envelope; readwrite.version.fixture_schema_mismatch | bounded_diagnostic_enrichment | readwrite contract version envelope boundary |
| P2C006-TM-4 | resource_exhaustion | Fail-closed when readwrite ingest workload exceeds strict line/edge/attribute budgets. | Apply bounded resource clamps and deterministic admission checks before fail-closed exit. | line and token budget guards; bounded ingest work caps; readwrite tail-budget sentinels | artifacts/phase2c/FNX-P2C-006/parity_gate.yaml | readwrite_ingest_budget_blowup | readwrite.resource.ingest_budget_exceeded; readwrite.resource.token_budget_exceeded | bounded_diagnostic_enrichment; bounded_resource_clamp | readwrite ingestion budget boundary |
| P2C006-TM-5 | state_corruption | Fail-closed when round-trip reconstruction violates node/edge/state invariants. | Reset transient reconstruction state and emit deterministic incident evidence before fail-closed exit. | round-trip invariant checkpoints; tuple-node identity restoration checks; state reset replay hooks | artifacts/phase2c/FNX-P2C-006/contract_table.md | readwrite_roundtrip_state_invariant_break | readwrite.state.roundtrip_invariant_break; readwrite.state.identity_restoration_mismatch | bounded_diagnostic_enrichment; deterministic_tie_break_normalization | round-trip state invariance boundary |

## Compatibility Boundary Matrix
| boundary id | strict parity obligation | hardened allowlisted deviation categories | fail-closed default | evidence hooks |
|---|---|---|---|---|
| P2C006-CB-1 | Malformed edgelist payloads and invalid nodetype coercions fail closed with no repaired output. | bounded_diagnostic_enrichment; defensive_parse_recovery | fail_closed_on_malformed_edgelist_payload | networkx/readwrite/tests/test_edgelist.py:142-165; artifacts/phase2c/FNX-P2C-006/risk_note.md#packet-threat-matrix |
| P2C006-CB-2 | json_graph attribute namespace conflicts are rejected deterministically. | bounded_diagnostic_enrichment; quarantine_of_unsupported_metadata | fail_closed_on_ambiguous_json_attribute_namespace | networkx/readwrite/json_graph/tests/test_adjacency.py:74-78; networkx/readwrite/json_graph/tests/test_node_link.py:10-14; artifacts/phase2c/FNX-P2C-006/contract_table.md#input-contract |
| P2C006-CB-3 | Unsupported readwrite contract/version envelopes are rejected deterministically. | bounded_diagnostic_enrichment | fail_closed_on_readwrite_contract_version_skew | artifacts/phase2c/FNX-P2C-006/parity_gate.yaml; artifacts/phase2c/FNX-P2C-006/fixture_manifest.json |
| P2C006-CB-4 | Readwrite ingest and reconstruction workload stays within strict budgets. | bounded_diagnostic_enrichment; bounded_resource_clamp | fail_closed_when_readwrite_ingest_budget_exhausted | artifacts/phase2c/FNX-P2C-006/parity_gate.yaml; artifacts/perf/phase2c/perf_regression_gate_report_v1.json |
| P2C006-CB-5 | Round-trip reconstruction preserves node/edge identity and graph-mode invariants. | bounded_diagnostic_enrichment; deterministic_tie_break_normalization | fail_closed_on_roundtrip_state_invariant_break | artifacts/phase2c/FNX-P2C-006/contract_table.md#machine-checkable-invariant-matrix; artifacts/phase2c/FNX-P2C-006/risk_note.md#compatibility-boundary-matrix |

## Hardened Deviation Guardrails
- allowlisted categories only: bounded_diagnostic_enrichment; defensive_parse_recovery; bounded_resource_clamp; deterministic_tie_break_normalization; quarantine_of_unsupported_metadata.
- ad hoc hardened deviations: forbidden.
- unknown incompatible feature policy: fail_closed.

## Residual Risk
- unresolved risks: parser ambiguity; serialization round-trip drift.
- follow-up actions: expand adversarial fixture diversity and keep crash triage mappings deterministic.
