# DOC-PASS-03 Data Model, State, and Invariant Mapping (V1)

- generated_at_utc: 2026-02-14T06:35:27.976495+00:00
- baseline_comparator: legacy_networkx/main@python3.12

## Component Matrix

| Component | Mutable Fields | Transition Count | Invariant Count |
|---|---|---:|---:|
| `graph_store` | nodes, adjacency, attrs, revision | 2 | 2 |
| `view_cache` | cached_snapshot, parent_revision, filters | 3 | 1 |
| `dispatch_registry` | backend_specs, decision_ledger | 2 | 1 |
| `conversion_readwrite` | parse_cursor, warnings, graph_builder_state | 2 | 1 |
| `algo_conformance` | work_queue, witness, mismatch_vector, structured_logs | 2 | 2 |

## Notes

- Strict mode invariant violations are fail-closed.
- Hardened mode allows bounded recovery only when explicitly documented and auditable.
- Each invariant row maps to unit/property/differential/e2e hooks.
