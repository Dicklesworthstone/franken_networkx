# CGSE Deterministic Policy Spec

- artifact id: `cgse-deterministic-policy-spec-v1`
- generated at (utc): `2026-02-18T06:42:15Z`
- baseline comparator: `legacy_networkx_code/networkx/networkx (repository checkout in current workspace)`
- source ledger: `artifacts/cgse/v1/cgse_legacy_tiebreak_ordering_ledger_v1.json`

## Scope
Deterministic strict/hardened policy compilation from CGSE legacy tie-break extraction rules.

## Policy Table
| policy id | rule id | family | tie-break contract | ordering contract | strict invariant | hardened invariant | allowlist |
|---|---|---|---|---|---|---|---|
| CGSE-POL-R01 | CGSE-R01 | graph_core_mutation | first-unused-integer key scan | stable for fixed keydict state; gaps may be skipped after deletions | CGSE-R01 strict mode preserves `first-unused-integer key scan` and `stable for fixed keydict state; gaps may be skipped after deletions` with zero mismatch budget. | CGSE-R01 hardened mode may deviate only through allowlisted ambiguity controls while retaining observable output compatibility. | CGSE-AMB-001 |
| CGSE-POL-R02 | CGSE-R02 | graph_core_mutation | remove newest edge first when key=None | LIFO across multiedges between same endpoints | CGSE-R02 strict mode preserves `remove newest edge first when key=None` and `LIFO across multiedges between same endpoints` with zero mismatch budget. | CGSE-R02 hardened mode may deviate only through allowlisted ambiguity controls while retaining observable output compatibility. | CGSE-AMB-002 |
| CGSE-POL-R03 | CGSE-R03 | graph_core_mutation | preserve encounter-order attr selection | directed edge traversal order determines conflict winner | CGSE-R03 strict mode preserves `preserve encounter-order attr selection` and `directed edge traversal order determines conflict winner` with zero mismatch budget. | CGSE-R03 hardened mode may deviate only through allowlisted ambiguity controls while retaining observable output compatibility. | CGSE-AMB-003 |
| CGSE-POL-R04 | CGSE-R04 | view_semantics | prefer direct dict-order surfaces; treat set-union surfaces as ambiguity hotspots | deterministic for pure dict proxies; ambiguous for set-union composites | CGSE-R04 strict mode preserves `prefer direct dict-order surfaces; treat set-union surfaces as ambiguity hotspots` and `deterministic for pure dict proxies; ambiguous for set-union composites` with zero mismatch budget. | CGSE-R04 hardened mode may deviate only through allowlisted ambiguity controls while retaining observable output compatibility. | CGSE-AMB-004 |
| CGSE-POL-R05 | CGSE-R05 | dispatch_routing | sorted-key application for unknown priority categories | stable env-variable fold order after normalization | CGSE-R05 strict mode preserves `sorted-key application for unknown priority categories` and `stable env-variable fold order after normalization` with zero mismatch budget. | CGSE-R05 hardened mode may deviate only through allowlisted ambiguity controls while retaining observable output compatibility. | CGSE-AMB-005 |
| CGSE-POL-R06 | CGSE-R06 | dispatch_routing | grouped-priority try-order with no implicit alphabetical fallback for ambiguous group3 | group1 -> group2 -> group3 -> group4 -> group5 | CGSE-R06 strict mode preserves `grouped-priority try-order with no implicit alphabetical fallback for ambiguous group3` and `group1 -> group2 -> group3 -> group4 -> group5` with zero mismatch budget. | CGSE-R06 hardened mode may deviate only through allowlisted ambiguity controls while retaining observable output compatibility. | CGSE-AMB-006 |
| CGSE-POL-R07 | CGSE-R07 | conversion_contracts | fixed probe-order precedence | first successful conversion branch wins | CGSE-R07 strict mode preserves `fixed probe-order precedence` and `first successful conversion branch wins` with zero mismatch budget. | CGSE-R07 hardened mode may deviate only through allowlisted ambiguity controls while retaining observable output compatibility. | CGSE-AMB-007 |
| CGSE-POL-R08 | CGSE-R08 | shortest_path_algorithms | distance then insertion counter then predecessor-list first element | equal-weight predecessors tracked in encounter order | CGSE-R08 strict mode preserves `distance then insertion counter then predecessor-list first element` and `equal-weight predecessors tracked in encounter order` with zero mismatch budget. | CGSE-R08 hardened mode may deviate only through allowlisted ambiguity controls while retaining observable output compatibility. | CGSE-AMB-008 |
| CGSE-POL-R09 | CGSE-R09 | shortest_path_algorithms | alternating direction + monotonic fringe counter | first discovered best meet-node wins unless shorter path found | CGSE-R09 strict mode preserves `alternating direction + monotonic fringe counter` and `first discovered best meet-node wins unless shorter path found` with zero mismatch budget. | CGSE-R09 hardened mode may deviate only through allowlisted ambiguity controls while retaining observable output compatibility. | bounded_diagnostic_enrichment |
| CGSE-POL-R10 | CGSE-R10 | readwrite_serialization | graph-edge iteration order | output row order follows edge iterator traversal | CGSE-R10 strict mode preserves `graph-edge iteration order` and `output row order follows edge iterator traversal` with zero mismatch budget. | CGSE-R10 hardened mode may deviate only through allowlisted ambiguity controls while retaining observable output compatibility. | CGSE-AMB-009 |
| CGSE-POL-R11 | CGSE-R11 | readwrite_serialization | first-seen line order for duplicate/same-endpoint edges | edge insertion order matches parsed line order | CGSE-R11 strict mode preserves `first-seen line order for duplicate/same-endpoint edges` and `edge insertion order matches parsed line order` with zero mismatch budget. | CGSE-R11 hardened mode may deviate only through allowlisted ambiguity controls while retaining observable output compatibility. | bounded_diagnostic_enrichment |
| CGSE-POL-R12 | CGSE-R12 | generator_semantics | input-iterable order and documented directed orientation | generator edge emission follows pairwise traversal | CGSE-R12 strict mode preserves `input-iterable order and documented directed orientation` and `generator edge emission follows pairwise traversal` with zero mismatch budget. | CGSE-R12 hardened mode may deviate only through allowlisted ambiguity controls while retaining observable output compatibility. | CGSE-AMB-010 |
| CGSE-POL-R13 | CGSE-R13 | runtime_config | deterministic sorted error-report ordering | stable validation message ordering across runs | CGSE-R13 strict mode preserves `deterministic sorted error-report ordering` and `stable validation message ordering across runs` with zero mismatch budget. | CGSE-R13 hardened mode may deviate only through allowlisted ambiguity controls while retaining observable output compatibility. | bounded_diagnostic_enrichment |
| CGSE-POL-R14 | CGSE-R14 | oracle_test_surface | accept multiple equivalent predecessor orderings where legacy oracle permits | maintain compatibility allowlist for equal-cost ambiguity | CGSE-R14 strict mode preserves `accept multiple equivalent predecessor orderings where legacy oracle permits` and `maintain compatibility allowlist for equal-cost ambiguity` with zero mismatch budget. | CGSE-R14 hardened mode may deviate only through allowlisted ambiguity controls while retaining observable output compatibility. | CGSE-AMB-011 |

## Conflict Scan
- status: `no_conflicts`
- duplicate policy ids: none
- duplicate rule ids: none

## Hardened Guardrails
- allowlisted categories: `CGSE-AMB-001; CGSE-AMB-002; CGSE-AMB-003; CGSE-AMB-004; CGSE-AMB-005; CGSE-AMB-006; CGSE-AMB-007; CGSE-AMB-008; CGSE-AMB-009; CGSE-AMB-010; CGSE-AMB-011; bounded_diagnostic_enrichment`
- hardened behavior must remain allowlist-bounded and fail-closed for unknown drift.

## Evidence References
- profile baseline: `artifacts/perf/phase2c/perf_baseline_matrix_v1.json`
- profile hotspot: `artifacts/perf/phase2c/hotspot_one_lever_backlog_v1.json`
- profile delta: `artifacts/perf/phase2c/perf_regression_gate_report_v1.json`
- isomorphism proof: `artifacts/proofs/ISOMORPHISM_PROOF_FNX_P2C_001_V1.md`
- isomorphism proof: `artifacts/proofs/ISOMORPHISM_PROOF_FNX_P2C_005_V1.md`
- isomorphism proof: `artifacts/proofs/ISOMORPHISM_PROOF_NEIGHBOR_ITER_BFS_V2.md`
- structured logging evidence: `artifacts/conformance/latest/structured_logs.json`
- structured logging evidence: `artifacts/conformance/latest/structured_logs.jsonl`
- structured logging evidence: `artifacts/conformance/latest/telemetry_dependent_unblock_matrix_v1.json`
