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
- DOC-PASS-01 module/package cartography coverage (workspace Rust implementation):
  - `fnx-runtime` (runtime-policy layer) owns strict/hardened mode policy types, decision-theoretic action law, evidence ledger schema, and structured test-log contracts.
  - `fnx-classes` (graph-storage layer) owns deterministic adjacency/node/edge mutation semantics, revision monotonicity, and snapshot contracts.
  - `fnx-views` (graph-view-api layer) owns live and cached view semantics, stale-cache invalidation, and ordering parity with graph store.
  - `fnx-dispatch` (compat-dispatch layer) owns backend registration, deterministic selection tie-break, and fail-closed incompatibility decisions.
  - `fnx-convert` (conversion-ingest layer) owns edge-list/adjacency ingestion behavior and conversion warning/failure policies.
  - `fnx-readwrite` (io-serialization layer) owns edgelist/json graph parser+serializer behavior and malformed-input handling split by mode.
  - `fnx-generators` (graph-generators layer) owns deterministic graph family constructors plus seeded stochastic generation.
  - `fnx-algorithms` (algorithm-engine layer) owns shortest-path/components/centrality output contracts and complexity witness fields.
  - `fnx-durability` (durability-repair layer) owns RaptorQ sidecar generation, scrub integrity checks, and decode-proof drill artifacts.
  - `fnx-conformance` (conformance-harness layer) owns fixture execution, mismatch taxonomy, packet routing, and structured telemetry artifact emission.
- Explicit cross-module dependency direction map (compile-time):
  - `fnx-classes -> fnx-runtime`
  - `fnx-views -> fnx-classes`
  - `fnx-dispatch -> fnx-runtime`
  - `fnx-convert -> fnx-classes, fnx-dispatch, fnx-runtime`
  - `fnx-readwrite -> fnx-classes, fnx-dispatch, fnx-runtime`
  - `fnx-generators -> fnx-classes, fnx-runtime`
  - `fnx-algorithms -> fnx-classes`
  - `fnx-conformance -> fnx-algorithms, fnx-classes, fnx-convert, fnx-dispatch, fnx-generators, fnx-readwrite, fnx-runtime, fnx-views`
  - `fnx-durability` is intentionally isolated from workspace crate dependencies to preserve artifact-layer portability.
- Hidden/implicit coupling hotspots requiring drift gates:
  - Backend capability string duplication across dispatch defaults and caller crates (`fnx-convert`, `fnx-readwrite`, `fnx-conformance`) can silently desynchronize route availability.
  - Stable hash implementations currently exist in both `fnx-runtime` and `fnx-conformance`; algorithm drift would fork telemetry/artifact identity.
  - Conformance packet routing currently infers packet ID from fixture naming heuristics; naming drift can corrupt release gate accounting without schema-level packet fields.
  - Deterministic ordering guarantees in `fnx-views` and `fnx-algorithms` depend on `fnx-classes` insertion-order contracts and therefore require dedicated ordering parity fixtures.
- Machine-auditable DOC-PASS-01 artifact and gates:
  - `artifacts/docs/v1/doc_pass01_module_cartography_v1.json`
  - `artifacts/docs/v1/doc_pass01_module_cartography_v1.md`
  - `artifacts/docs/schema/v1/doc_pass01_module_cartography_schema_v1.json`
  - `scripts/generate_doc_pass01_module_cartography.py`
  - `scripts/validate_doc_pass01_module_cartography.py`
  - `scripts/run_doc_pass01_module_cartography.sh`
  - `crates/fnx-conformance/tests/doc_pass01_module_cartography_gate.rs`

## 13. Error Taxonomy and Recovery Operations (DOC-PASS-07)

### 13.1 Operational failure matrix

| Domain surface | Trigger | Strict response | Hardened response | Recovery artifact |
|---|---|---|---|---|
| dispatch (`fnx-dispatch`) | unknown incompatible feature / unsupported backend route | fail-closed | fail-closed | deterministic dispatch decision ledger |
| graph mutation (`fnx-classes`) | incompatible edge metadata (`__fnx_incompatible*`) | fail-closed | fail-closed | edge mutation decision record |
| convert ingestion (`fnx-convert`) | empty node IDs / malformed endpoints | fail-closed | bounded skip + warning | conversion warning ledger + normalized graph |
| readwrite ingestion (`fnx-readwrite`) | malformed edgelist/json payload | fail-closed | bounded recovery with warning (including empty-graph fallback for malformed JSON root) | warning list + replayable parse context |
| generators (`fnx-generators`) | oversize `n`, out-of-range `p` | fail-closed | clamp with warning when allowed, else fail-closed | generator rationale evidence term |
| runtime sync (`fnx-runtime`) | capability mismatch, checksum mismatch, cursor conflict, retry exhaustion | fail-closed terminal state | fail-closed terminal state | reason-coded transition log |
| conformance (`fnx-conformance`) | fixture mismatch / expected warning not observed | fail gate | fail gate | mismatch taxonomy + deterministic replay command + forensics bundle index |

### 13.2 User-visible error contract

- Explicit typed failures are surfaced as:
  - `GraphError::FailClosed`
  - `DispatchError::{FailClosed, NoCompatibleBackend}`
  - `ConvertError::FailClosed`
  - `ReadWriteError::FailClosed`
  - `GenerationError::FailClosed`
- Hardened-mode non-fatal degradations are surfaced as warning vectors (`warnings: Vec<String>`) in conversion/readwrite/generator reports and are required conformance signals, not optional debug text.
- Structured telemetry validation failures in `fnx-runtime` are hard errors (missing replay, reason code, or forensic index fields cannot be tolerated in release evidence).

### 13.3 Deterministic escalation and containment

1. classify the failure (`compatibility`, `parse`, `resource guard`, `telemetry contract`, `parity mismatch`).
2. apply mode law from `decision_theoretic_action` (`fnx-runtime`) with unknown incompatible features always fail-closed.
3. emit canonical forensic payloads (decision ledger, warning fragments, mismatch records, replay command, bundle index).
4. rerun only after correction; strict parity drift and telemetry contract violations remain hard blockers.

## 14. Verification Crosswalk Index (DOC-PASS-09)

Canonical source:
- `EXHAUSTIVE_LEGACY_ANALYSIS.md` section `20` (machine-parsable CSV matrix + explicit gap register).

### 14.1 Fast index by subsystem

| Subsystem family | Crosswalk IDs | Primary verification assets |
|---|---|---|
| graph/view core | `XW-001`, `XW-002` | `fnx-classes` + `fnx-views` unit tests, `graph_core_mutation_hardened.json`, `view_neighbors_strict.json`, `scripts/e2e/run_happy_path.sh` |
| dispatch/convert/readwrite | `XW-003`, `XW-004`, `XW-005` | dispatch/convert/readwrite unit tests, `dispatch_route_strict.json`, `convert_edge_list_strict.json`, readwrite fixture set, malformed-input e2e scripts |
| algorithms/generators | `XW-006`, `XW-007`, `XW-008` | algorithm/generator unit suites, shortest/components/centrality/generator fixtures, path/adversarial e2e scripts |
| runtime/conformance telemetry | `XW-009` | `structured_log_gate.rs`, asupersync gates, `structured_logs.jsonl`, normalization report, replay metadata checks |
| durability/evidence lifecycle | `XW-010` | `fnx-durability` unit tests, `phase2c_packet_readiness_gate.rs`, durability run scripts and decode-proof artifacts |

### 14.2 Priority gap queue (linked to beads)

| Priority | Gap ID | Bead links | Immediate closure target |
|---|---|---|---|
| P0 | `GAP-02` | `bd-315.16`, `bd-315.18.6`, `bd-315.18.7` | weighted shortest-path + centrality/generator differential/adversarial parity expansion |
| P1 | `GAP-01` | `bd-315.23` | reliability/flake budget closure for graph/view/convert/readwrite verification families |
| P1 | `GAP-03` | `bd-315.26.4` | deterministic recovery e2e scenarios with decode-proof and replay-linked telemetry |
| P1 | `GAP-04` | `bd-315.26` | asupersync-backed durability replication across long-lived artifact classes |
| P1 | `GAP-05` | `bd-315.10.1`, `bd-315.10` | CI gate topology promotion of crosswalk schema (G1..G8 contract matrix) |

## 15. Reliability Gate Operations (bd-315.23 baseline)

### 15.1 Budget keys to enforce in CI

| Budget key | Scope | Gate expectation |
|---|---|---|
| `REL-BUD-001` | graph/view core packets | maintain coverage floors + deterministic smoke/e2e replay success |
| `REL-BUD-002` | convert/readwrite packet family | enforce malformed-input robustness without strict-mode drift |
| `REL-BUD-003` | shortest-path critical family | enforce tighter p99 and flake ceiling for critical path correctness |
| `REL-BUD-004` | centrality/generator family | enforce parity + runtime-tail guardrails across generated fixtures |
| `REL-BUD-005` | runtime/dispatch/log schema family | enforce fail-closed telemetry contract and structured log completeness |
| `REL-BUD-006` | conformance/durability family | enforce decode-proof and evidence bundle recovery invariants |

### 15.2 Flake/quarantine state machine (operational)

1. detect:
- identify `fail -> pass` on immediate deterministic rerun for same `test_id` + `packet_id` + `mode`.
2. classify:
- `warn` when rolling flake rate exceeds `0.25%`.
- `fail` when rolling flake rate exceeds `1.00%`.
3. quarantine:
- enter after 3 flakes in 24h.
- exit after 20 consecutive deterministic passes.
4. report:
- gate output must include `budget_id`, failing test groups, artifact refs, replay commands, and owner bead linkage.

### 15.3 Command discipline

- CPU-heavy gate commands must run offloaded, e.g.:
  - `rch exec -- cargo test -q -p fnx-conformance --test smoke -- --nocapture`
  - `rch exec -- cargo test -q -p fnx-conformance --test structured_log_gate -- --nocapture`
  - `rch exec -- cargo test -q -p fnx-conformance --test phase2c_packet_readiness_gate -- --nocapture`

## 16. CI Gate Topology Contract Index (bd-315.10.1)

Canonical lock artifacts:
- `artifacts/conformance/v1/ci_gate_topology_v1.json`
- `artifacts/conformance/schema/v1/ci_gate_topology_schema_v1.json`
- `crates/fnx-conformance/tests/ci_gate_topology_gate.rs`

Operational invariants:
1. Gate order is deterministic: `G1 -> G2 -> G3 -> G4 -> G5 -> G6 -> G7 -> G8`.
2. Every gate is blocking and fail-closed.
3. The first gate failure short-circuits downstream gates and must emit policy/budget-scoped remediation metadata.
4. Compatibility and security drift checks are encoded via deterministic rule IDs rather than ad-hoc prose in CI output.
