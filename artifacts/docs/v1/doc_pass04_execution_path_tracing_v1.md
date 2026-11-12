# DOC-PASS-04 Execution-Path Tracing v1

Generated at: `2026-02-16T07:07:36.663944+00:00`
Baseline comparator: `legacy_networkx/main@python3.12`

## Summary
- workflow_count: `8`
- branch_count: `16`
- fallback_count: `8`
- workspace_crate_count: `9`
- verification_bead_count: `7`

## Workflow Index

| path_id | subsystem | branches | fallbacks | replay |
|---|---|---:|---:|---|
| graph_mutation_lifecycle | graph-storage | 2 | 1 | `rch exec -- cargo test -q -p fnx-classes --lib -- --nocapture` |
| view_cache_projection_refresh | graph-view-api | 2 | 1 | `rch exec -- cargo test -q -p fnx-views --lib -- --nocapture` |
| dispatch_resolution_runtime | compat-dispatch | 2 | 1 | `rch exec -- cargo test -q -p fnx-dispatch --lib -- --nocapture` |
| conversion_payload_ingest | conversion-ingest | 2 | 1 | `rch exec -- cargo test -q -p fnx-convert --lib -- --nocapture` |
| readwrite_serialization_roundtrip | io-serialization | 2 | 1 | `rch exec -- cargo test -q -p fnx-readwrite --lib -- --nocapture` |
| algorithm_execution_bfs_centrality | algorithm-engine | 2 | 1 | `rch exec -- cargo test -q -p fnx-algorithms --lib -- --nocapture` |
| conformance_harness_fixture_execution | conformance-harness | 2 | 1 | `rch exec -- cargo run -q -p fnx-conformance --bin run_smoke -- --mode strict` |
| durability_sidecar_scrub_decode | durability-repair | 2 | 1 | `rch exec -- cargo test -q -p fnx-durability --lib -- --nocapture` |

## Graph Mutation and Fail-Closed Edge Admission

- path_id: `graph_mutation_lifecycle`
- objective: Mutate adjacency/edge state deterministically while enforcing strict fail-closed metadata policy.
- linked beads: `bd-315.24.5`, `bd-315.24.10`, `bd-315.23`, `bd-315.10`

### Branches
- `unknown_feature_fail_closed`: Unknown incompatible edge metadata encountered. -> mutation_rejected
- `autocreate_missing_nodes`: Edge endpoint not present in node table. -> mutation_committed

### Fallbacks
- `graph_mutation_forensics`: trigger `DecisionAction::FailClosed` -> terminal `fail_closed`

### Verification
- unit: 2 references
- property: 1 references
- differential: 1 references
- e2e: 1 references

## Graph View Projection and Cached Snapshot Refresh

- path_id: `view_cache_projection_refresh`
- objective: Serve deterministic read views while refreshing stale cache snapshots on revision drift.
- linked beads: `bd-315.24.5`, `bd-315.24.10`, `bd-315.23`

### Branches
- `cache_fresh_no_refresh`: Cached revision matches current graph revision. -> cache_hot
- `cache_stale_refresh`: Cached revision differs from graph revision. -> cache_refreshed

### Fallbacks
- `view_refresh_recompute`: trigger `revision_mismatch` -> terminal `cache_hot`

### Verification
- unit: 1 references
- property: 1 references
- differential: 1 references
- e2e: 1 references

## Compatibility-Aware Dispatch Resolution

- path_id: `dispatch_resolution_runtime`
- objective: Resolve backend deterministically with fail-closed handling for incompatible requests.
- linked beads: `bd-315.24.5`, `bd-315.24.10`, `bd-315.10`, `bd-315.23`

### Branches
- `dispatch_unknown_feature_fail_closed`: unknown_incompatible_feature=true -> dispatch_rejected
- `dispatch_no_backend`: No backend satisfies compatibility + feature constraints. -> dispatch_rejected

### Fallbacks
- `dispatch_failure_forensics`: trigger `decision_action_fail_closed` -> terminal `fail_closed`

### Verification
- unit: 2 references
- property: 1 references
- differential: 1 references
- e2e: 1 references

## Conversion Ingest (Edge List + Adjacency)

- path_id: `conversion_payload_ingest`
- objective: Convert external graph payloads into native graph state with strict/hardened parsing branches.
- linked beads: `bd-315.24.5`, `bd-315.24.10`, `bd-315.23`

### Branches
- `convert_strict_malformed_fail_closed`: Strict mode receives malformed node/edge payload. -> conversion_failed
- `convert_hardened_warn_skip`: Hardened mode receives malformed row. -> conversion_degraded_but_completed

### Fallbacks
- `convert_hardened_continuation`: trigger `malformed_input_hardened_mode` -> terminal `completed_with_warnings`

### Verification
- unit: 2 references
- property: 1 references
- differential: 1 references
- e2e: 1 references

## Read/Write Serialization and Parse Recovery

- path_id: `readwrite_serialization_roundtrip`
- objective: Enforce deterministic edge-list/json serialization with strict fail-closed parse branches and hardened bounded recovery.
- linked beads: `bd-315.24.5`, `bd-315.24.10`, `bd-315.23`

### Branches
- `readwrite_strict_fail_closed`: Strict parser encounters malformed edge-list line or invalid JSON. -> parse_failed
- `readwrite_hardened_warning_recovery`: Hardened parser sees malformed row/json payload. -> parse_completed_with_warnings

### Fallbacks
- `readwrite_replay_recovery`: trigger `hardened_malformed_payload` -> terminal `completed_with_warnings`

### Verification
- unit: 3 references
- property: 1 references
- differential: 1 references
- e2e: 1 references

## Algorithm Execution (Shortest Path + Components + Centrality)

- path_id: `algorithm_execution_bfs_centrality`
- objective: Execute deterministic algorithm routines with complexity witness artifacts and edge-case branch handling.
- linked beads: `bd-315.24.5`, `bd-315.24.10`, `bd-315.23`

### Branches
- `algorithm_missing_nodes`: Source or target node absent for shortest-path query. -> query_no_path
- `algorithm_singleton_special_case`: Singleton graph centrality denominator edge case. -> query_completed

### Fallbacks
- `algorithm_null_result_contract`: trigger `invalid_query_endpoints` -> terminal `completed_without_path`

### Verification
- unit: 3 references
- property: 1 references
- differential: 1 references
- e2e: 1 references

## Conformance Harness Fixture Execution and Artifact Emission

- path_id: `conformance_harness_fixture_execution`
- objective: Run fixture pipelines, compare expected behavior, and emit structured logs + replay metadata.
- linked beads: `bd-315.24.5`, `bd-315.24.10`, `bd-315.10`, `bd-315.6`, `bd-315.5`

### Branches
- `fixture_read_or_parse_error`: Fixture file unreadable or parse fails. -> fixture_failed_continue_suite
- `fixture_operation_mismatch`: Observed output diverges from expected fixture contract. -> suite_failed_with_forensics

### Fallbacks
- `conformance_structured_forensics`: trigger `mismatch_count>0` -> terminal `diagnostic_artifacts_ready`

### Verification
- unit: 1 references
- property: 1 references
- differential: 1 references
- e2e: 1 references

## Durability Sidecar Generation, Scrub Recovery, and Decode Drill

- path_id: `durability_sidecar_scrub_decode`
- objective: Guarantee recoverable artifact durability with RaptorQ sidecars and decode-proof events.
- linked beads: `bd-315.24.5`, `bd-315.24.10`, `bd-315.26.4`, `bd-315.23`

### Branches
- `scrub_hash_match_fastpath`: Artifact hash matches envelope source hash. -> scrub_ok
- `scrub_decode_recovery`: Artifact hash mismatch or artifact missing. -> recovered_or_failed

### Fallbacks
- `durability_decode_drill_retry`: trigger `decode_with_reduced_packets_failed` -> terminal `recovered`

### Verification
- unit: 2 references
- property: 1 references
- differential: 1 references
- e2e: 1 references

