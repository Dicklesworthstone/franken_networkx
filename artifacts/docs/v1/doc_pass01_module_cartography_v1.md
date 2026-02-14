# DOC-PASS-01 Module/Package Cartography (V1)

- generated_at_utc: 2026-02-14T16:18:40.152003+00:00
- baseline_comparator: legacy_networkx/main@python3.12
- crate_count: 10
- dependency_edge_count: 20
- hidden_coupling_count: 5
- layering_violation_count: 0

## Crate Topology

| Crate | Layer | Depends On | Public Surface Count | Legacy Anchors |
|---|---|---|---:|---:|
| `fnx-runtime` | `runtime-policy` | - | 16 | 2 |
| `fnx-classes` | `graph-storage` | `fnx-runtime` | 16 | 2 |
| `fnx-dispatch` | `compat-dispatch` | `fnx-runtime` | 11 | 1 |
| `fnx-views` | `graph-view-api` | `fnx-classes` | 13 | 3 |
| `fnx-algorithms` | `algorithm-engine` | `fnx-classes` | 12 | 3 |
| `fnx-convert` | `conversion-ingest` | `fnx-classes`, `fnx-dispatch`, `fnx-runtime` | 15 | 3 |
| `fnx-generators` | `graph-generators` | `fnx-classes`, `fnx-runtime` | 12 | 2 |
| `fnx-readwrite` | `io-serialization` | `fnx-classes`, `fnx-dispatch`, `fnx-runtime` | 11 | 2 |
| `fnx-durability` | `durability-repair` | - | 11 | 1 |
| `fnx-conformance` | `conformance-harness` | `fnx-algorithms`, `fnx-classes`, `fnx-convert`, `fnx-dispatch`, `fnx-generators`, `fnx-readwrite`, `fnx-runtime`, `fnx-views` | 9 | 3 |

## Hidden Coupling Hotspots

| Coupling ID | Crates Involved | Risk | Mitigation |
|---|---|---|---|
| `HC-001` | `fnx-convert`, `fnx-readwrite`, `fnx-conformance`, `fnx-dispatch` | high | Generate capability constants from a single registry contract and assert parity in conformance gates. |
| `HC-002` | `fnx-runtime`, `fnx-conformance` | medium | Centralize stable hash helper in `fnx-runtime` and consume from conformance crate. |
| `HC-003` | `fnx-conformance`, `fnx-algorithms`, `fnx-readwrite`, `fnx-generators` | high | Move packet IDs into fixture schema fields and fail closed when absent. |
| `HC-004` | `fnx-classes`, `fnx-views`, `fnx-algorithms` | medium | Keep explicit deterministic ordering invariants and differential fixture checks for every ordering-sensitive API. |
| `HC-005` | `fnx-durability`, `fnx-conformance` | high | Define shared durability envelope schema in a single contract crate and validate conformance artifact names against it. |

## Layering Violations

- none (all compile-time dependencies respect declared layering order).
