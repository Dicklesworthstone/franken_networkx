# Risk Note

## Risk Surface
- parser/ingestion: malformed payloads for shortest-path and algorithm wave.
- algorithmic denial vectors: adversarial graph shapes designed to trigger tail latency spikes.
- packet gate: `path witness suite`.

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
| P2C005-TM-1 | parser_abuse | Fail-closed on malformed weighted-path request payloads and invalid source/target selectors. | Fail-closed with bounded diagnostics and defensive parse recovery before deterministic abort. | weighted request schema checks; source/target existence guards; malformed payload fixtures | artifacts/phase2c/FNX-P2C-005/risk_note.md | algorithm_request_malformed_payload | shortest_path.parse.malformed_payload; shortest_path.parse.invalid_source_target | bounded_diagnostic_enrichment; defensive_parse_recovery | weighted request parse boundary |
| P2C005-TM-2 | metadata_ambiguity | Fail-closed on ambiguous weight metadata, hidden-edge callbacks, or conflicting route hints. | Quarantine unsupported metadata and preserve deterministic weighted-route semantics. | weight metadata precedence table; hidden-edge callback contract checks; metadata drift classification | artifacts/phase2c/FNX-P2C-005/contract_table.md | algorithm_conflicting_weight_metadata | shortest_path.metadata.ambiguous_weight_selector; shortest_path.metadata.hidden_edge_callback_conflict | bounded_diagnostic_enrichment; quarantine_of_unsupported_metadata | weighted metadata normalization boundary |
| P2C005-TM-3 | version_skew | Fail-closed on unsupported algorithm contract versions. | Reject incompatible version envelopes with deterministic compatibility diagnostics. | algorithm contract version pinning; versioned fixture bundle checks; compatibility matrix probes | artifacts/phase2c/FNX-P2C-005/parity_gate.yaml | algorithm_contract_version_skew | shortest_path.version.unsupported_contract_envelope; shortest_path.version.contract_mismatch | bounded_diagnostic_enrichment | algorithm contract version envelope boundary |
| P2C005-TM-4 | resource_exhaustion | Fail-closed when weighted frontier expansion exceeds strict complexity budgets. | Apply bounded resource clamps and reject once deterministic thresholds are exceeded. | frontier expansion ratio guards; priority-queue work caps; runtime tail budget sentinels | artifacts/phase2c/FNX-P2C-005/parity_gate.yaml | shortest_path_frontier_blowup | shortest_path.resource.frontier_budget_exceeded; shortest_path.resource.priority_queue_cap_exceeded | bounded_diagnostic_enrichment; bounded_resource_clamp | weighted frontier expansion budget boundary |
| P2C005-TM-5 | state_corruption | Fail-closed when path witness, predecessor state, or component route invariants drift. | Reset transient route state and fail-closed with deterministic incident evidence. | witness invariant checkpoints; predecessor map consistency checks; state-reset replay hooks | artifacts/phase2c/FNX-P2C-005/contract_table.md | shortest_path_witness_state_break | shortest_path.state.witness_invariant_break; shortest_path.state.predecessor_state_mismatch | bounded_diagnostic_enrichment | path witness and route-state determinism boundary |
| P2C005-TM-6 | algorithmic_complexity_dos | Fail-closed on adversarial graph classes outside strict complexity envelopes. | Apply bounded admission checks and deterministic tie-break normalization before rejection. | adversarial graph taxonomy gates; complexity witness artifacts; runtime tail regression sentinels | artifacts/phase2c/FNX-P2C-005/risk_note.md | shortest_path_lollipop_and_barbell_stressor | shortest_path.complexity.hostile_graph_class; shortest_path.complexity.tail_budget_exceeded | bounded_diagnostic_enrichment; bounded_resource_clamp; deterministic_tie_break_normalization | hostile graph complexity admission boundary |

## Compatibility Boundary Matrix
| boundary id | strict parity obligation | hardened allowlisted deviation categories | fail-closed default | evidence hooks |
|---|---|---|---|---|
| P2C005-CB-1 | Malformed weighted request payloads and invalid source/target selectors fail closed. | bounded_diagnostic_enrichment; defensive_parse_recovery | fail_closed_on_malformed_weighted_request | networkx/algorithms/shortest_paths/tests/test_weighted.py:156-170; artifacts/phase2c/FNX-P2C-005/risk_note.md#packet-threat-matrix |
| P2C005-CB-2 | Weight metadata precedence and hidden-edge callback semantics remain deterministic. | bounded_diagnostic_enrichment; quarantine_of_unsupported_metadata | fail_closed_on_ambiguous_weight_metadata | networkx/algorithms/shortest_paths/tests/test_weighted.py:199-241; artifacts/phase2c/FNX-P2C-005/contract_table.md#input-contract |
| P2C005-CB-3 | Unsupported algorithm contract/version envelopes are rejected deterministically. | bounded_diagnostic_enrichment | fail_closed_on_algorithm_version_skew | networkx/algorithms/shortest_paths/tests/test_weighted.py:331-347; artifacts/phase2c/FNX-P2C-005/parity_gate.yaml |
| P2C005-CB-4 | Weighted frontier growth remains within strict complexity budgets. | bounded_diagnostic_enrichment; bounded_resource_clamp; deterministic_tie_break_normalization | fail_closed_when_weighted_frontier_budget_exhausted | artifacts/phase2c/FNX-P2C-005/parity_gate.yaml; artifacts/perf/phase2c/perf_regression_gate_report_v1.json |
| P2C005-CB-5 | Negative-cycle and contradictory-path states never emit finite shortest-path witnesses. | bounded_diagnostic_enrichment | fail_closed_on_negative_cycle_or_contradictory_path | networkx/algorithms/shortest_paths/tests/test_weighted.py:533-620; artifacts/phase2c/FNX-P2C-005/contract_table.md#machine-checkable-invariant-matrix |
| P2C005-CB-6 | Connected-components backend loopback and directed-input boundaries fail closed. | bounded_diagnostic_enrichment | fail_closed_on_components_backend_or_graph_type_violation | networkx/algorithms/components/tests/test_connected.py:75-130; artifacts/phase2c/FNX-P2C-005/risk_note.md#compatibility-boundary-matrix |

## Hardened Deviation Guardrails
- allowlisted categories only: bounded_diagnostic_enrichment; defensive_parse_recovery; bounded_resource_clamp; deterministic_tie_break_normalization; quarantine_of_unsupported_metadata.
- ad hoc hardened deviations: forbidden.
- unknown incompatible feature policy: fail_closed.

## Residual Risk
- unresolved risks: tie-break drift; algorithmic complexity DOS on hostile dense graphs.
- follow-up actions: expand adversarial fixture diversity and keep crash triage mappings deterministic.
