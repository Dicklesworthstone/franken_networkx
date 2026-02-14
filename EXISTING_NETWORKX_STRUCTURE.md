# EXISTING_NETWORKX_STRUCTURE

## 1. Legacy Oracle

- Root: /dp/franken_networkx/legacy_networkx_code/networkx
- Upstream: networkx/networkx

## 2. Subsystem Map

- networkx/classes: Graph, DiGraph, MultiGraph classes and views.
- networkx/algorithms/*: flow, shortest paths, components, centrality, isomorphism, traversal, matching, etc.
- networkx/generators: graph construction families.
- networkx/convert.py + convert_matrix.py + relabel.py: ingestion and conversion.
- networkx/readwrite: serialization formats and adapters.
- networkx/utils: decorators, backend dispatch, random utilities, union-find.
- networkx/lazy_imports.py: optional dependency behavior.

## 3. Semantic Hotspots (Must Preserve)

1. adjacency dict structure and mutable attribute alias behavior.
2. directed vs undirected and multigraph key semantics.
3. live view behavior from coreviews/reportviews.
4. dispatchable decorator routing and backend priority handling.
5. conversion behavior across dict/list/matrix/graph inputs.
6. deterministic tie-break and ordering behavior in scoped algorithms.

## 4. Compatibility-Critical Behaviors

- Graph/DiGraph/MultiGraph mutation and edge lookup contracts.
- backend priority and runtime backend selection behavior.
- open_file decompression convenience behavior in read/write paths.
- lazy import failure timing and error surface shape.

## 5. Security and Stability Risk Areas

- GraphML XML parser trust boundary and untrusted input risk.
- GML parsing and destringizer/stringizer edge behavior.
- backend override ambiguity and silent route changes.
- compressed file handling and parser robustness.

## 6. V1 Extraction Boundary

Include now:
- classes + views + dispatchable infrastructure, conversion/relabel, core algorithm families, and scoped read/write formats.

Exclude for V1:
- drawing/matplotlib ecosystem, heavy linalg optional paths, full plugin backend breadth.

## 7. High-Value Conformance Fixture Families

- classes/tests for storage and view semantics.
- algorithms/*/tests for flow/connectivity/path/isomorphism scopes.
- generators/tests for deterministic graph creation behavior.
- readwrite/tests for format round-trip and warning behaviors.
- utils/tests for dispatch/backends/decorator/lazy import semantics.

## 8. Extraction Notes for Rust Spec

- Land graph core and view semantics before algorithm breadth.
- Treat dispatch/backends as compatibility-critical infrastructure.
- Make deterministic ordering rules explicit in each algorithm family contract.

## 9. Data Models and Mutability Boundaries (DOC-PASS-03)

| Component | Primary mutable fields | Mutability boundary | Core invariant family |
|---|---|---|---|
| graph store (`fnx-classes`) | `nodes`, `adjacency`, `attrs`, `revision` | mutation commit must preserve deterministic adjacency contract | adjacency symmetry, revision monotonicity |
| view cache (`fnx-views`) | cached snapshot, parent revision pointer, filters | stale cache cannot be served after parent revision changes | ordering parity with parent graph |
| dispatch registry (`fnx-dispatch`) | backend list, decision ledger | unknown incompatible feature always rejects route | deterministic backend selection |
| conversion/readwrite pipeline (`fnx-convert`, `fnx-readwrite`) | parser cursor, warnings, graph builder state | malformed parse cannot silently alter strict-mode output | deterministic round-trip + bounded hardened recovery |
| algorithm/conformance surface (`fnx-algorithms`, `fnx-conformance`) | work queue, witness payload, mismatch vector, structured logs | zero-tolerance drift in strict parity gates | deterministic packet routing and replay metadata integrity |

## 10. Critical State Machine Transitions

1. Graph mutation lifecycle:
- `empty|stable -> mutating`: add/remove operations begin.
- `mutating -> stable`: commit only if invariants hold; otherwise rollback then fail-closed.
2. View cache lifecycle:
- `cache_cold -> cache_hot`: first read materializes deterministic snapshot.
- `cache_hot -> cache_stale`: parent revision changes.
- `cache_stale -> cache_hot`: refresh if ordering invariants validate; else reset and fail-closed.
3. Dispatch lifecycle:
- `registered -> resolved`: deterministic backend selected under strict/hardened policy.
- `registered -> rejected`: no compatible backend or unknown incompatible feature.
4. Parser lifecycle:
- `parsing -> parsed`: valid row accepted.
- `parsing -> recovered` (hardened only): malformed row skipped with bounded warning budget.
- budget exceeded or strict malformed row => fail-closed.
5. Conformance lifecycle:
- `fixture_loaded -> executing -> validated` when mismatch count is zero.
- any mismatch transitions to failure artifact emission with deterministic replay metadata.

## 11. Invariant Violation and Recovery Policy

| Invariant class | Strict mode | Hardened mode | Recovery behavior |
|---|---|---|---|
| graph adjacency / revision invariants | fail-closed | rollback then fail-closed with audit | revert to last stable snapshot |
| view ordering/cache coherence | fail-closed | cache reset then fail-closed | invalidate and rebuild from stable graph |
| dispatch route compatibility | fail-closed | fail-closed (diagnostic enriched only) | emit deterministic decision ledger entry |
| conversion/readwrite contract | fail-closed | bounded recovery then fail-closed when budget exhausted | warning ledger + repro command |
| conformance packet/log routing | fail-closed | fail-closed with forensics links | regenerate fixture report + bundle index |

## 12. Machine-Auditable Artifact Link

- Source of truth for this section:
  - `artifacts/docs/v1/doc_pass03_data_model_state_invariant_v1.json`
  - `artifacts/docs/v1/doc_pass03_data_model_state_invariant_v1.md`
- Gate scripts:
  - `scripts/validate_doc_pass03_state_mapping.py`
  - `scripts/run_doc_pass03_state_mapping.sh`
