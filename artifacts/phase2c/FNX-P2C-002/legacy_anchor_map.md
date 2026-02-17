# Legacy Anchor Map

## Legacy Scope
- packet id: FNX-P2C-002
- subsystem: View layer semantics
- legacy module paths: networkx/classes/coreviews.py, networkx/classes/graphviews.py

## Anchor Map
- path: networkx/classes/coreviews.py
  - lines: extracted during clean-room analysis pass
  - symbols: AtlasView, AdjacencyView
  - behavior: deterministic observable contract for adjacency projection and stable neighbor iteration.
- path: networkx/classes/graphviews.py
  - lines: extracted during clean-room analysis pass
  - symbols: generic_graph_view, subgraph_view, reverse_view
  - behavior: deterministic observable contract for filtered/reversed graph views with stable ordering.

## Contract Row Mapping
| contract_row | legacy anchors | local packet artifacts | validation targets |
|---|---|---|---|
| FNX-P2C-002-C1 | `coreviews.py` (`AtlasView`, `AdjacencyView`) | `contract_table.md` graph mutation row | `generated/view_neighbors_strict.json`, readiness gate |
| FNX-P2C-002-C2 | `coreviews.py`, `graphviews.py` | `contract_table.md` cache coherence row | packet risk note + adversarial fixture suite |
| FNX-P2C-002-C3 | `graphviews.py` (`reverse_view`) | `contract_table.md` dispatch row | conformance fixture report + packet gate |
| FNX-P2C-002-C4 | `coreviews.py`, `graphviews.py` | `fixture_manifest.json` conversion/readwrite contract | conformance fixture report |
| FNX-P2C-002-C5 | legacy class view tests | strict/hardened error rows in `contract_table.md` | structured telemetry + forensics matrix |

## Legacy Test Anchors
- `networkx/classes/tests/test_coreviews.py`
- `networkx/classes/tests/test_graphviews.py`

## Rust Module Boundary Skeleton
| crate/module boundary | ownership | contract coverage | public seam | internal seam | threat boundary |
|---|---|---|---|---|---|
| `crates/fnx-classes::Graph` | graph mutation state + revision counters | C1, C2, C5 | deterministic graph mutation/query APIs | revision tokens, adjacency/index mutation internals | state_corruption, parser_abuse |
| `crates/fnx-views::GraphView` + `CachedSnapshotView` | view projection + cache invalidation semantics | C1, C2 | view projection/read APIs | cache invalidation and revision-cache coherence internals | metadata_ambiguity, state_corruption, resource_exhaustion |
| `crates/fnx-dispatch::BackendRegistry` | deterministic backend route ranking/selection | C3, C5 | dispatch request/decision APIs | backend ranking + route hint normalization internals | metadata_ambiguity, version_skew |
| `crates/fnx-convert::GraphConverter` | conversion envelope + compatibility guard integration | C4, C5 | conversion entry APIs | payload normalization and route mediation internals | parser_abuse, metadata_ambiguity |
| `crates/fnx-readwrite::EdgeListEngine` (and JSON read/write path) | serialization/deserialization contract | C4, C5 | read/write public APIs | parser + encoded-attribute normalization internals | parser_abuse, version_skew |
| `crates/fnx-conformance` fixture harness | parity verification and artifact emission | C1-C5 | fixture execution/report APIs | mismatch taxonomy + forensics artifact wiring | all packet threat classes |

## Dependency-Aware Implementation Sequence
1. Boundary freeze checkpoint:
   - bind C1-C5 contract rows to module seams above and freeze fail-closed defaults before implementation deltas.
2. API seam checkpoint:
   - keep public APIs stable (`Graph`, `GraphView`, dispatch request paths) and isolate normalization/recovery logic to internal seams.
3. Instrumentation checkpoint:
   - ensure structured log fields and replay metadata are emitted at mutation, view-projection, and dispatch decision boundaries.
4. Verification checkpoint:
   - unit/property hooks: contract/invariant checks for C1-C5.
   - differential/e2e hooks: conformance fixture `generated/view_neighbors_strict.json` and packet readiness gate.
5. Merge checkpoint:
   - confirm packet artifacts + threat model + implementation sequence remain cross-linked and auditable.

## Parallel Contributor Ownership Plan
| edit surface | owner responsibility | compile-check boundary | verification entrypoint |
|---|---|---|---|
| `artifacts/phase2c/FNX-P2C-002/contract_table.md` | contract/invariant semantics | C1-C5 rows remain complete | `phase2c_packet_readiness_gate` |
| `artifacts/phase2c/FNX-P2C-002/risk_note.md` | threat + compatibility envelope | strict/hardened matrix + allowlist | security matrix + adversarial mappings |
| `artifacts/phase2c/FNX-P2C-002/fixture_manifest.json` | machine-checkable crosswalk | keys/refs remain parseable and complete | `jq empty` + readiness gate |
| `crates/fnx-views` and `crates/fnx-conformance` | implementation + verification plumbing | public API stable, internals isolated | conformance smoke + packet gate |

## Behavior Notes
- deterministic constraints: view adjacency iteration order is deterministic; revision-aware cache invalidation remains deterministic.
- compatibility-sensitive edge cases: stale cache exposure; projection filter nondeterminism

## Compatibility Risk
- risk level: high
- rationale: view coherence witness gate is required to guard compatibility-sensitive behavior.
