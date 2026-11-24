# EXISTING_NETWORKX_STRUCTURE

## 1. Legacy Oracle

- Root: /dp/franken_networkx/legacy_networkx_code/networkx
- Upstream: networkx/networkx

## 1.1 Spec-First Contract

This document is the implementation source-of-truth for Rust behavior parity.

Rules:

1. Implement from this spec and packet artifacts, not by translating legacy files line-by-line.
2. If behavior is missing here, perform extraction first; do not guess and do not silently diverge.
3. Preserve strict-mode fail-closed compatibility defaults for unknown incompatible behavior.

## 1.2 Extraction Coverage Matrix

| Extraction category | Coverage status | Primary anchors |
|---|---|---|
| data models and mutability | complete for active packet families | sections 9, 10, 17 |
| validation and failure rules | complete for strict/hardened contract surfaces | sections 11, 13, 18 |
| dispatch/conversion/readwrite behavior | complete for scoped V1 packet families | sections 2-8, 14, 19 |
| deterministic ordering/tie-break semantics | complete for implemented families; expands per new packet | sections 3, 8, 17 |
| conformance and replay evidence crosswalk | complete for active gates and artifacts | sections 14-16, 21 |
| unresolved extraction backlog | tracked via gap queue and linked beads | section 14.2 |

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
| view cache (`fnx-views`) | cached snapshot, parent revision pointer, filters | stale cache cannot be served after parent revision, attributes, or predicate state changes | ordering parity with parent graph |
| dispatch registry (`fnx-dispatch`) | backend list, decision ledger | unknown incompatible feature always rejects route | deterministic backend selection |
| conversion/readwrite pipeline (`fnx-convert`, `fnx-readwrite`) | parser cursor, warnings, graph builder state | malformed parse cannot silently alter strict-mode output | deterministic round-trip + bounded hardened recovery |
| algorithm/conformance surface (`fnx-algorithms`, `fnx-conformance`) | work queue, witness payload, mismatch vector, structured logs | zero-tolerance drift in strict parity gates | deterministic packet routing and replay metadata integrity |

## 10. Critical State Machine Transitions

1. Graph mutation lifecycle:
- `empty|stable -> mutating`: add/remove operations begin.
- `mutating -> stable`: commit only if invariants hold; otherwise rollback then fail-closed.
2. View cache lifecycle:
- `cache_cold -> cache_hot`: first read materializes deterministic snapshot.
- `cache_hot -> cache_stale`: parent revision, observed attributes, or graph-attribute mapping identity changes.
- `cache_stale -> cache_hot`: refresh if ordering invariants validate; else reset and fail-closed.
- User predicates are evaluated again when materializing views: even closure-free functions can invoke mutable node truthiness or comparison protocols. Default filters retain caching; built-in node-set filters require immutable built-in keys on both sides of membership tests as well as explicit selection-state tokens.
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

## 17. Concurrency/Lifecycle Semantics and Ordering Guarantees (DOC-PASS-06)

### 17.1 Legacy anchor points to preserve

- Graph mutation is in-place over shared adjacency dictionaries (`legacy_networkx_code/networkx/networkx/classes/graph.py`, `digraph.py`), with explicit list materialization in removal loops to avoid iterator invalidation.
- Node/edge/adjacency views are live wrappers (`legacy_networkx_code/networkx/networkx/classes/coreviews.py`, `reportviews.py`) and therefore reflect current backing-map state, not snapshot-isolated state.
- Dispatch backend resolution is driven by global backend registries and backend-priority policy (`legacy_networkx_code/networkx/networkx/utils/backends.py`), making route choice deterministic only when config and backend availability are held constant.
- Traversal output order in shortest-path routines inherits adjacency iteration order (`legacy_networkx_code/networkx/networkx/algorithms/shortest_paths/unweighted.py`).
- Random generator reproducibility depends on explicit seed handling via `@py_random_state` (`legacy_networkx_code/networkx/networkx/generators/random_graphs.py`).
- Composite partition generators share the same advancing random stream across
  normalization boundaries. Resolving an already resolved Python or NumPy seed
  preserves its identity and consumes no draws. Legacy `RandomState` instances
  retain their own draw algorithms; the NumPy global state and `Generator`
  retain their established bit adapters. Successive stochastic-block, random,
  planted, and Gaussian partition calls preserve graph order and full RNG state.
- Read/write parsing is sequential and line-ordered (`legacy_networkx_code/networkx/networkx/readwrite/edgelist.py`, `adjlist.py`), so warning/failure order is part of observable behavior.

### 17.2 Rust-port hazard matrix and containment

| Hazard | Observable regression | Required containment in FrankenNetworkX |
|---|---|---|
| mutation while iterating views/neighbors | non-deterministic edge order, stale reads, replay mismatch | revision-gated mutation commits plus deterministic view invalidation/rebuild |
| stale cache served after parent mutation | strict/hardened parity drift | enforce monotonic revision checks; fail-closed on stale-cache detection |
| backend registry/config drift during dispatch | backend route flaps across runs | capture deterministic dispatch decision ledgers (policy IDs + selected backend + conversion path) |
| parser parallelization/reordering | unstable warning vectors and first-failure positions | preserve deterministic input order and canonical warning ordering |
| shared RNG streams across scenarios | seed replay instability | isolate RNG per scenario and persist replay seeds in structured telemetry |

### 17.3 Mandatory parity assertions for this pass

1. Neighbor/view iteration order remains stable after scripted mutation sequences.
2. Cached view refresh behavior is deterministic and never silently serves stale state.
3. Dispatch decisions are replay-identical under fixed inputs, mode, and backend config.
4. Parse-warning and fail-row ordering are deterministic for malformed fixture corpora.
5. Seeded generator runs are replay-identical across reruns and linked to e2e replay metadata.

## 18. Security/Compatibility Edge Cases and Undefined Zones (DOC-PASS-08)

### 18.1 Undefined-zone inventory

| Zone | Legacy anchor | Required policy |
|---|---|---|
| mutable-but-hashable node identity drift | `legacy_networkx_code/networkx/networkx/classes/graph.py` hashability notes (`565-570`) | treat identity instability as incompatible input; fail-closed |
| `None` node admission | `graph.py` / `digraph.py` node validation paths | hard fail-closed in strict and hardened |
| live-view mutation during iteration | `graph.py` list-materialized removal loops + `coreviews.py` live wrappers | deterministic rollback/rebuild or fail-closed; never serve partially-mutated state |
| multi-edge key allocation/reuse subtleties | `multigraph.py::new_edge_key`, `multidigraph.py::add_edge/remove_edge` | preserve deterministic key semantics; never rewrite keys heuristically |
| backend-route ambiguity and unsupported conversion | `utils/backends.py` dispatch/convert gates | fail-closed with deterministic route evidence |
| delimiter and literal-parse ambiguities in ingest | `readwrite/adjlist.py`, `readwrite/edgelist.py` | strict fail-closed; hardened bounded warning-only recovery with budgets |

### 18.2 Hardened-mode rationale (non-negotiable)

1. Hardened recovery is allowed only for bounded, row-local parse anomalies with deterministic warning artifacts.
2. Unknown incompatible features, telemetry schema violations, and route ambiguity remain fail-closed in both modes.
3. Any hardened recovery must emit policy ID, reason code, replay command, and artifact links; otherwise gate failure.

## 19. Pass-A Topology and Ownership Closure Map

### 19.1 Subsystem ownership matrix (legacy -> Rust -> evidence)

| Legacy subsystem anchor | Rust owner(s) | Dependency position | Primary evidence / gate surface |
|---|---|---|---|
| `networkx/classes/graph.py`, `digraph.py`, `multigraph.py`, `multidigraph.py` | `crates/fnx-classes` | foundational storage/mutation layer | `crates/fnx-classes` unit tests + conformance fixtures (`graph_core_*`) |
| `networkx/classes/coreviews.py`, `reportviews.py`, `graphviews.py` | `crates/fnx-views` (+ `fnx-classes`) | projection/view layer over graph store | `crates/fnx-conformance/fixtures/generated/view_neighbors_strict.json` |
| `networkx/utils/backends.py` | `crates/fnx-dispatch` (+ `fnx-runtime`) | dispatch/routing compatibility boundary | dispatch strict fixtures + decision-ledger checks |
| `networkx/convert.py` and conversion helpers | `crates/fnx-convert` | ingest/transform boundary before algorithm execution | conversion fixtures (`convert_edge_list_strict.json`) + malformed-input e2e |
| `networkx/readwrite/*` | `crates/fnx-readwrite` | serialization and parser boundary | read/write round-trip + malformed fixture suites |
| `networkx/algorithms/*` (shortest path, components, centrality, etc.) | `crates/fnx-algorithms` | deterministic algorithm core | algorithm parity fixtures + complexity witness artifacts |
| `networkx/generators/*` | `crates/fnx-generators` | graph-construction boundary feeding tests and workloads | seeded generator fixtures + adversarial/happy-path e2e scripts |
| `networkx/tests/*` parity/oracle behavior | `crates/fnx-conformance` | top-level behavior verification and mismatch taxonomy | smoke + packet gates + structured log contracts |
| durability/recovery adjunct (FrankenNetworkX addition) | `crates/fnx-durability`, `crates/fnx-runtime` | artifact integrity and fail-closed recovery boundary | decode-proof artifacts + readiness/durability gates |

### 19.2 Dependency narrative (ordered and explicit)

1. Graph API enters through `fnx-classes` (state source of truth).
2. Views (`fnx-views`) and dispatch (`fnx-dispatch`) consume graph/runtime contracts without mutating policy law.
3. Conversion and read/write (`fnx-convert`, `fnx-readwrite`) normalize ingress/egress while preserving strict/hardened mode contracts.
4. Algorithms and generators (`fnx-algorithms`, `fnx-generators`) consume deterministic graph semantics and emit witness-compatible outputs.
5. Conformance (`fnx-conformance`) validates behavior parity and forensics telemetry across all packets.
6. Durability/runtime (`fnx-durability`, `fnx-runtime`) seal artifact integrity, state-machine safety, and replay guarantees.

### 19.3 Reviewer traceability checklist

1. Every topology claim maps to a legacy path plus a Rust crate owner.
2. Every owner row has at least one concrete fixture/test/gate evidence hook.
3. Every cross-layer dependency has an explicit failure boundary (fail-closed, bounded hardened recovery, or deterministic witness requirement).
4. No structure claim depends on undocumented implicit behavior.

## 20. Structure Specialist Review Artifact (bd-315.24.15)

### 20.1 Corrections and enrichments applied

1. Added explicit concurrency/lifecycle ordering contracts with legacy anchors (`section 17`) where the prior draft had only high-level state language.
2. Added security/compatibility undefined-zone register and hardened rationale boundaries (`section 18`) to remove ambiguity around fail-closed vs bounded recovery.
3. Added subsystem ownership/evidence topology map and ordered dependency narrative (`section 19`) to make structural decomposition reviewer-verifiable.

### 20.2 Section-level confidence annotations

| Section range | Scope | Confidence | Basis |
|---|---|---|---|
| `1-8` | legacy oracle framing, scope, subsystem map | High | aligns with workspace crate topology and documented project charter files |
| `9-12` | data model, transitions, invariants, ownership artifacts | High | cross-referenced against `fnx-*` crate boundaries and machine-auditable artifact paths |
| `13-16` | error taxonomy, verification index, reliability, CI topology | High | linked to concrete gate schemas/tests/scripts already present in repo |
| `17` | concurrency/lifecycle ordering guarantees | Medium-High | source anchors are explicit; deeper algorithm-family-by-family ordering notes remain future pass material |
| `18` | security/compat edge cases and undefined zones | Medium-High | fail-closed boundaries are explicit; additional adversarial examples can be expanded in later review passes |
| `19` | pass-A topology/ownership closure map | High | legacy->Rust ownership and dependency ordering are directly traceable to file paths and crate responsibilities |

### 20.3 Residual structural risks for next pass

1. Expand algorithm-family-specific ordering/tie-break notes (beyond shortest-path/generator anchors) as packet-level implementations land.
2. Add per-section backlinks into `EXHAUSTIVE_LEGACY_ANALYSIS.md` to tighten bidirectional traceability.

## 21. Final Integrated Consistency Sweep and Sign-off (DOC-PASS-13)

### 21.1 Cross-document synchronization ledger

| Integrated topic | `EXISTING_NETWORKX_STRUCTURE.md` anchor | `EXHAUSTIVE_LEGACY_ANALYSIS.md` anchor | Consistency verdict |
|---|---|---|---|
| Legacy inventory counts + hotspot concentration | sections `2`, `3`, `8` | sections `2`, `12`, `26.1` | aligned to current measured totals and hotspot families |
| Path-anchor namespace clarity | sections `2`, `17`, `18` | sections `3`, `26.1` (`RT-002`) | shorthand/absolute path semantics explicitly disambiguated |
| Behavior-invariant deep pass | sections `9`, `10`, `17`, `18` | sections `18.6`, `18.7`, `19.2`, `25.1`, `25.2`, `27` | contradictions reconciled; policy-driven edge behavior clarified |
| Verification/replay/logging topology | sections `14`, `15`, `16` | sections `20`, `21`, `22`, `28` | replay commands, artifact contracts, and gap routing are cross-linked |
| Risk/perf/test closure mapping | sections `14.2`, `15` | sections `24`, `25.3`, `28.2` | no orphan critical surface: partial rows map to explicit closure beads |

### 21.2 Final sign-off assertions for DOC-PASS-13

1. Both docs are source-anchored and execution-facing rather than narrative-only summaries.
2. Red-team and behavior-specialist contradictions are explicitly logged and resolved (`RT-*`, `BH-*`).
3. Risk/perf/test specialist pass confirms all critical behavior surfaces are either covered or explicitly mapped to closure beads with replay + forensic requirements.
4. Remaining uncertainty is bounded and documented as explicit follow-up work, not hidden assumptions.

## 22. Weighted Shortest-Path Contract (P2C005 Extension)

Legacy anchors:
- `legacy_networkx_code/networkx/networkx/algorithms/shortest_paths/weighted.py`
- `legacy_networkx_code/networkx/networkx/algorithms/shortest_paths/tests/test_weighted.py`

Rust parity contract for the current weighted slice (`fnx-algorithms::shortest_path_weighted`):

1. Input/output shape:
- Inputs: `(graph, source, target, weight_attr)`
- Output: `ShortestPathResult { path: Option<Vec<String>>, witness }`

2. Existence semantics:
- If either endpoint is absent, `path = None`.
- If `source == target`, `path = [source]`.

3. Weight semantics:
- Read edge weight from edge attribute key `weight_attr`.
- Missing weight defaults to `1.0`.
- Non-finite, negative, or non-parseable weight values are treated as default `1.0` in this scoped slice.

4. Determinism/tie-break semantics:
- Candidate-node selection for Dijkstra frontier ties is deterministic by graph node insertion order.
- Neighbor relaxation order follows deterministic neighbor iteration order from `fnx-classes`.
- Equal-cost relaxations do not overwrite an existing predecessor (first-seen predecessor wins).

5. Complexity witness contract:
- Algorithm label: `dijkstra_shortest_path`
- Complexity claim: `O(|V|^2 + |E|)` for the current deterministic linear-select implementation.

6. Verification hooks:
- Unit tests in `crates/fnx-algorithms/src/lib.rs` assert weighted-vs-unweighted divergence and tie-break replay stability.
- Differential fixture `crates/fnx-conformance/fixtures/generated/shortest_path_weighted_strict.json` asserts strict-mode expected path.

Python's generic `shortest_path(..., method="bellman-ford")` applies the same
exact-weight admission as the dedicated Bellman-Ford APIs before a source-only
or target-only native projection. Path-only output still requires exact
arithmetic: rounding can invent a tie or hide an integer negative cycle.
Wide integer edges and sums, Fraction/Decimal values, and custom numeric
protocols retain Python arithmetic; admitted ordinary finite weights,
including negative weights, retain their native routes. Generic path/length
parity across pair, source, target and all-pairs forms is covered in
`tests/python/test_weighted_path_adversarial_parity.py`.

### 22.1 Python Dijkstra overflow reachability

For `Graph`, `DiGraph`, `MultiGraph`, and `MultiDiGraph`, a sum of finite,
nonnegative edge weights can overflow to positive infinity. NetworkX 3.6.1
treats this as a reachable distance, distinct from an undiscovered node:

- Discover and expand an infinite-distance node once, retaining its concrete
  path and propagating reachability to subsequent neighbors. Zero-weight cycles
  and self-loops must not cause repeated expansion or cyclic returned paths.
- A finite alternative improves a pending infinite distance and replaces its
  path. Equal-distance alternatives retain the API's existing tie behavior.
- A finite cutoff excludes infinite-distance nodes; `cutoff=float("inf")` and
  an omitted cutoff include them.
- Source and multisource dictionaries, and each all-pairs row, include reachable
  infinite distances while omitting disconnected nodes. Target queries return
  the infinite distance and concrete path; a genuinely disconnected target
  still raises `NetworkXNoPath`.
- These rules apply with the default weight attribute, an explicit attribute,
  and callable weights. Finite floating-point edges remain eligible for native
  Dijkstra routing even when their accumulated distance overflows.
- `all_shortest_paths(..., method="dijkstra")` enumerates the reachable simple
  paths represented by the Dijkstra predecessor relation, including infinite
  distances, in NetworkX order. Cyclic predecessor relations must terminate.

For example, edges `s-a: 1e308`, `a-b: 1e308`, and `b-t: 1.0` produce distance
`inf` and path `[s, a, b, t]`. An additional path `s-c: 1.5e308`, `c-t: 0.0`
instead gives finite distance `1.5e308` and path `[s, c, t]`.

### 22.2 Weighted centrality consumers

Weighted node and edge betweenness, their subset variants, Newman load, and
percolation centrality must retain vertices first reached at positive infinity.
Finite edge validation does not establish that accumulated distances are finite.
First discovery enqueues a vertex; a later finite improvement replaces its
predecessors. Equal-distance relaxations preserve the existing predecessor and
path-count rules, including equality with an already finalized infinite distance.
Source order, heap tie order, dependency accumulation order, normalization, and
endpoint handling remain observable parts of the NetworkX 3.6.1 contract.
An isolated vertex contributes zero and must not enter another source's traversal.
Newman load distributes the current accumulated load in predecessor order; a
self-predecessor update must be visible to subsequent predecessors of that node.

Weighted subset node/edge betweenness, percolation, and Newman load use the
shared Dijkstra exact-weight admission before native projection. Oversized
integer weights or path sums, Fraction/Decimal values, and other custom
numerics retain Python arithmetic so rounding cannot invent shortest-path ties
or redistribute credit. This applies to both NetworkX and fnx input graphs;
ordinary eligible weights retain their native routes, including finite floating
weights whose sums overflow as described above. Callable weights read the
caller's live graph and attribute mappings; mutations remain visible to later
reads and callback exceptions propagate unchanged. Subset Brandes and
percolation preserve the arithmetic TypeError for `None` edge costs, while
Newman load follows Dijkstra's hidden-edge semantics for `None`.
`tests/python/test_weighted_centrality_overflow.py` covers these consumers and
native-route controls across all four graph classes.

### 22.3 Metric-closure weight domain

The Python metric-closure fast path must use the same exact-weight eligibility
gate as public Dijkstra before entering packed native all-pairs traversal.
Weights outside that domain retain Python numeric values and Dijkstra's error
behavior; they must not become default-unit edges or rounded floating-point
distances. Finite floating-point edges remain eligible when only their sum
overflows, and the resulting closure edge retains its infinite distance and path.

### 22.4 Native shortest-simple-path discovery

The native Yen implementation must discover the first path and subsequent spur
paths when finite, nonnegative edge weights accumulate to positive infinity.
An absent distance-map entry is distinct from a known infinite distance. Strict
improvements replace predecessors; equal costs preserve the existing native tie
policy. Zero-weight cycles and self-loops do not create cyclic returned paths,
and a genuinely unreachable target yields an empty native path collection.

### 22.5 Negative-cycle predicate arithmetic and callbacks

`negative_edge_cycle(G, weight, heuristic)` follows the NetworkX 3.6.1
virtual-source search, including its floating-point arithmetic:

- The temporary source has default-weight-1 edges to every original node.
  Directed native relaxation therefore starts real vertices at distance 1,
  with one enqueue already counted and a total-node threshold of `|V| + 1`.
  Ordered predecessor lists control the queued-predecessor skip rule.
- With the default heuristic enabled, a repeated vertex on the recent update
  chain detects a cycle before negative overflow can turn all later updates
  into equal negative-infinity ties. Many unrelated isolated vertices must
  not delay this early witness.
- `heuristic=False` must reach the count-only relaxation loop. Its answer can
  differ after floating saturation; the public option must not be ignored.
  On an undirected graph the temporary reverse edges back to the source are
  part of that loop.
- Negative self-loops are checked before relaxation, including a float such
  as `-1e-300` that rounds away when added to 1. An ordinary undirected edge
  with that weight does not improve the virtual-source seed. The finite
  native undirected shortcut is therefore a negative self-loop or an edge
  satisfying `1.0 + weight < 1.0`, not an unconditional negative-edge test.
- Callable weights see original edge attributes and the empty attributes on
  temporary source edges in traversal order. Missing required attributes
  raise their normal exceptions. Multigraph self-loop callbacks receive
  the individual `{key: attrs}` mapping, not a bare attribute dictionary.
- The in-process implementation inserts the temporary source into the caller's
  graph and reuses the shared Bellman-Ford kernel over its live adjacency.
  Callbacks can inspect that source and add or remove graph structure during
  the search; subsequent relaxation must observe those edits. A detached
  adjacency snapshot can silently miss a newly introduced negative cycle.
- Cleanup removes only the temporary source after success or a search error,
  retaining caller mutations and existing attribute dictionary identities.
  Source insertion and graph-size protocols remain observable. Frozen graphs
  and views reject source insertion with the reference exception, and custom
  heuristic truth protocols are evaluated at the relaxation boundary.

The overflow/heuristic and callback behavior was characterized with extracted
Python source against NetworkX 3.6.1. Tiny-edge/self-loop behavior additionally
follows directly from that version's virtual-source and self-loop code.
Regressions are in `tests/python/test_negative_edge_cycle_weight_parity.py`
and the native predicate tests; these contracts do not imply native build or
performance qualification.

### 22.6 Bellman-Ford predecessor modes and targets

`bellman_ford_predecessor_and_distance(G, source, target, weight, heuristic)`
preserves NetworkX 3.6.1's choice of negative-cycle detector on all four graph
classes. The default `heuristic=False` uses count-based detection; an enabled
heuristic checks the recent update chain during each strict improvement. These
modes can differ when finite negative weights overflow to negative infinity:
the early detector can identify a cycle before further improvements become
equal-infinity ties. The caller's heuristic value must reach relaxation
unchanged. A non-bool object's truth protocol is evaluated where the algorithm
uses it, rather than during route selection.

Supplying `target` does not truncate this API's predecessor or distance maps.
Every reachable node is still considered, including nodes beyond that target,
and a later reachable negative cycle still raises. Missing or unhashable
targets do not introduce a new validation error. Source validation occurs
before weight evaluation. Negative self-loops are checked before relaxation,
including self-loops outside the source component; an unreachable longer
negative cycle does not affect the source's result.

Predecessor lists, dictionary insertion order, exact integer/Fraction/Decimal
arithmetic, and callable weight evaluation remain observable. Callbacks and
assigned private adjacency must retain their original live rows. Regression
coverage is in `tests/python/test_bellman_ford_heuristic.py`, including a
two-edge integer negative cycle whose enabled detector performs two weight
evaluations regardless of unrelated isolated vertices. This is a relaxation
work bound, not a claim that every setup operation is independent of graph
size.

### 22.7 Negative-cycle witnesses over live weighted rows

`find_negative_cycle` uses the shared Bellman-Ford relaxation engine and
reconstructs the reference predecessor witness. Each relaxation evaluates
its current edge cost; revisiting a row must call its weight provider again.
Caching a weighted row can miss a cycle introduced by a later callback.
Early detection stops before reading unused outgoing edges, preserving
callback side effects and errors at the detection boundary.

Source validation precedes any graph conversion or weight read. Foreign
graphs, directed/undirected views and private logical rows stay authoritative
throughout relaxation, including the original multigraph key mappings.
Exact Python numerics retain their arithmetic and returned witness order.
The existing owned self-loop divergence remains: reconstruction evaluates
the actual self-loop dictionary instead of reproducing the reference's
erroneous argument order in its fallback self-loop check.

### 22.8 Bellman-Ford overflow and bounded path reconstruction

For finite floating-point edge weights, Bellman-Ford uses strict relaxation
against positive infinity for an undiscovered node. A sum that overflows to
positive infinity does not discover that node; a later finite alternative
still can. Negative infinity is an already reached distance, and another
negative-infinity candidate adds an equal predecessor without re-enqueuing
the node. The default shortest-path APIs apply the recent-update cycle
heuristic before the enqueue-count backstop, including when unrelated
isolates would otherwise delay detection until arithmetic has saturated.

Finite rounding or negative-infinity saturation can leave cyclic selected
parents without the reference relaxation reporting a negative cycle.
Distance queries retain their relaxation results and arithmetic types.
Path reconstruction is bounded by the reached-node count and reports a
distinct internal outcome for such parent chains. Python then searches the
complete predecessor lists: an alternative predecessor may supply a valid
path; when none does, the reference search's exception is preserved.
This applies to pair, source, target and all-pairs queries over all four
graph classes, including explicit backend dispatch. Regressions are in
`tests/python/test_bellman_ford_float_overflow.py` and the native Bellman-Ford
unit tests; current-native execution is required to qualify the full change.

## 23. Initial Flow Contract (P2C005 Extension)

Legacy anchors:
- `legacy_networkx_code/networkx/networkx/algorithms/flow/edmondskarp.py`
- `legacy_networkx_code/networkx/networkx/algorithms/flow/tests/`

Rust parity contract for the first flow slice (`fnx-algorithms::{max_flow_edmonds_karp, minimum_cut_edmonds_karp}`):

1. Input/output shape:
- Inputs: `(graph, source, sink, capacity_attr)`
- Output: `MaxFlowResult { value: f64, witness }`

2. Existence semantics:
- If either endpoint is absent, `value = 0.0`.
- If `source == sink`, `value = 0.0`.

3. Capacity semantics:
- Read edge capacity from edge attribute key `capacity_attr`.
- Missing capacity defaults to `1.0`.
- Non-finite, negative, or non-parseable capacity values are treated as default `1.0` in this scoped slice.

4. Determinism/tie-break semantics:
- Augmenting-path discovery uses BFS with deterministic neighbor iteration from `fnx-classes`.
- Replay on an identical graph state must produce identical max-flow value and witness metrics.

5. Complexity witness contract:
- Algorithm label: `edmonds_karp_max_flow`
- Complexity claim: `O(|V| * |E|^2)`

6. Verification hooks:
- Unit tests in `crates/fnx-algorithms/src/lib.rs` cover expected-value, replay-stability, and missing-node behavior.
- Differential fixture `crates/fnx-conformance/fixtures/generated/flow_max_strict.json` asserts strict-mode flow value parity.
- Differential fixture `crates/fnx-conformance/fixtures/generated/flow_min_cut_strict.json` asserts strict-mode min-cut value and partition parity.

7. Min-cut output and partition semantics:
- Inputs: `(graph, source, sink, capacity_attr)`
- Output: `MinimumCutResult { value: f64, source_partition: Vec<String>, sink_partition: Vec<String>, witness }`
- Partition extraction uses residual-positive reachability from `source` after deterministic max-flow completion.
- Partitions are emitted in deterministic graph node order and replay on identical graph state must be bitwise stable.

8. Min-cut witness contract:
- Algorithm label: `edmonds_karp_minimum_cut`
- Complexity claim: `O(|V| * |E|^2)`


### 23.1 Python custom-flow solver boundary

The public `maximum_flow`, `maximum_flow_value`, `minimum_cut`, and
`minimum_cut_value` entry points pass a supplied `flow_func` the caller's
original graph object. This includes NetworkX graphs, filtered and reverse
views, assigned private mappings, and shallow copies with shared storage.
Graph conversion and native-only validation belong to the built-in native
route; a supplied solver owns its input validation.

Callbacks may observe or mutate the graph during the call. Such mutations
remain visible through the caller's graph, and subsequent flow/partition
extraction uses that same graph. The callback receives the original
`capacity`, `value_only`, and extra keyword arguments, including any
caller-owned residual network. Passing extra solver arguments without an
explicit `flow_func` remains an error.

Regression cases are in
`tests/python/test_flow_algorithms_conformance.py`:
`test_custom_flow_solver_receives_live_caller_graph` and
`test_custom_flow_solver_owns_input_validation`.


### 23.2 Capacity-scaling minimum-cost flow

`capacity_scaling` is a successive shortest augmenting path algorithm with
decreasing powers-of-two residual-capacity thresholds. It is not an alias
for network simplex: equivalent optimal costs do not imply the same flow
assignment, heap callbacks, or validation contract.

- Directed simple and multigraph inputs retain node, neighbor, and parallel
  arc order. A residual arc has an independent reverse arc, including when
  the input already contains an antiparallel edge.
- The exact sum of demands must be zero; the failure message is
  `Sum of the demands should be 0.`. Nonpositive capacities are excluded
  from the residual and remain zero in the result.
- Missing capacities are infinite. Infinite-capacity negative cycles,
  including self-loops, raise `NetworkXUnbounded`; finite negative loops
  saturate and contribute to cost. No floating-point conversion is allowed.
- Each scaling phase saturates negative reduced-cost residual arcs,
  searches from active supply nodes to active deficit nodes, and updates
  node potentials after each successful augmentation. Equal-cost arc and
  heap order are observable through the returned flow dictionary.
- A caller-supplied MinHeap-compatible class is instantiated for each
  search, receives original node labels, and owns its errors and callbacks.
- Cost includes positive residual flows and negative self-loops. Unused
  float-weighted edges do not convert an integer cost to float.
- Empty residuals retain the upstream early-return behavior; otherwise
  any remaining imbalance raises `No flow satisfying all demands.`.
- Residual extraction retains live attribute-provider read order. In
  particular, capacity is read before the selected cost is captured for an
  arc; a capacity provider can update that cost for the same calculation.
  Repeated reads, custom numeric operations and their failures are observable
  and must not be reordered by indexed storage construction.

The owned implementation uses paired arc arrays and ordered neighbor groups
in `_capacity_scaling.py`; its public wrapper validates backend keywords.
Differential contracts live in `test_capacity_scaling_solver.py`.


## 24. Bethe Hessian Matrix Selection Contract

For an undirected simple graph, `bethe_hessian_matrix(G, r, nodelist)`
returns `(r**2 - 1) * I - r * A + D` in CSR array form. The selected
nodes determine the order and extent of the weighted adjacency matrix
`A`; `D` contains its row sums.

When `r` is omitted, compute `sum(d*d) / sum(d) - 1` from the
unweighted degrees of **all nodes in G**, before sparse conversion.
Selecting a subset, reordering it, or selecting isolates does not change
that regularizer. An edgeless graph therefore raises `ZeroDivisionError`
for the default regularizer before nodelist validation. An explicit
regularizer retains the sparse converter's normal validation order.

A supplied nodelist must be sized, matching NetworkX 3.6.1; rejecting an
unsized iterator must not consume it. The empty-graph error takes precedence
over this size check when an explicit regularizer is supplied.

Regression cases in `tests/python/test_linalg_namespace_native_routing.py`
cover subsets, selected isolates, weighted adjacency, explicit regularizers,
validation order, and unsized iterators through both public namespaces.


## 25. Minimum Cycle Basis with Exact and Overflowing Weights

For finite, nonnegative edge weights, a cycle remains part of the cycle space
when its accumulated floating-point weight overflows to positive infinity.
The native `minimum_cycle_basis_core` and `minimum_cycle_basis` Rust APIs,
and the exported `_fnx.minimum_cycle_basis` binding, must retain such cycles
instead of returning an incomplete basis. A triangle whose three edges each
weigh `1e308` has one basis cycle; a square with a diagonal has two. A
disconnected graph retains the basis of every component, including components
whose cycle weights overflow.

The native cycle-basis spanning forest accepts arbitrary input edge order.
Union-find retains its lower-index representative and first-accepted-edge
ordering while using iterative path compression; a long reverse-ordered path
followed by a closing chord must not exhaust the native call stack.

The lifted shortest-path search must distinguish an undiscovered node from a
discovered node at infinite distance. Selecting a starting node must accept
the first reachable candidate even when its distance is infinite, replace it
with any strictly shorter finite candidate, and retain the existing first
candidate on equal distances. Missing lifted paths remain absent.

The public Python `minimum_cycle_basis` wrapper also retains the complete
basis in these cases and must work without SciPy. Its owned de Pina solver
preserves Python integer, Fraction, and Decimal arithmetic instead of
converting all costs to float64. Component filtering must read the caller's
logical nodes, edges, and live attributes, including assigned private graph
storage. Nonstring weight keys are selected from edge dictionaries directly.
NetworkX 3.6.1 also selects a literal `None` attribute key when `weight=None`
inside this algorithm; an absent key defaults to one.

Both lifted sheets use internal integer indices, separate from user node
labels. A valid tuple label such as `(u, 1)` must not be merged with a lifted
copy of `u`. For such collisions, cycle validity, cycle-space rank, and
minimum total weight define the result; the invalid basis produced by the
upstream tuple-based lift is not reproduced. Ordinary tied cycles retain
NetworkX's component, chord-set, and shortest-path selection order.

Optional acceleration must preserve those contracts. The existing native
kernel is used only for single-chord components with supported labels and
safe exact integral costs; its general multicycle chord order differs from
the Python contract. Optional SciPy distance batches are restricted to
nonnegative built-in integer costs with exactly representable lifted-path
sums, and retain explicit zero-cost edges. Distances are processed in bounded
source batches; all other numeric domains use the shared exact Python
shortest-path primitives. Joining component bases must not repeatedly copy
the already-computed basis.

These expectations were checked against NetworkX 3.6.1. Native regression
cases live beside the existing minimum-cycle-basis Rust tests and in
`tests/python/test_misc_tier2_parity.py`. Public dependency, numeric-domain,
label-collision, ordering, filtering, and routing contracts live in
`tests/python/test_minimum_cycle_basis_exact.py`.


## 26. Relabeling with Colliding Node Labels

`relabel_nodes(G, mapping, copy=True)` inserts target nodes in the order of
their first mapped occurrence. When several source nodes map to one target,
the last source node in graph iteration order supplies the target's entire
node-attribute dictionary. Attributes unique to earlier source nodes are
discarded, including when the last source has an empty dictionary. Mapping
dictionary order does not select the winning attributes.

Copied node, edge, and graph dictionaries are independent shallow copies:
changing their fields does not mutate the input graph, while nested attribute
values keep their identity. The source graph remains unchanged. In-place
relabeling (`copy=False`) has a different contract: it updates the surviving
node dictionary and retains non-overlapping fields.

Regression coverage in `tests/python/test_relabel_edge_cases_parity.py`
checks all four graph types, both source insertion orders, fresh and existing
target labels, callable mappings, empty final attributes, nonstring attribute
keys, and shallow-copy identity.


## 27. A* Python Callback and Priority Contract

Supplied A* heuristic and weight callbacks run against the caller's original
live graph, including NetworkX inputs, filtered subgraphs, and reverse views.
Callbacks may read adjacency or update edge attributes. They must execute
without a native graph borrow and must not observe a copied or collapsed
graph in place of the caller's input.

Heuristic priorities retain Python arithmetic, including arbitrary-size
integers, fractions, and decimals. Converting a valid negative integer
heuristic to floating point can erase the difference between competing path
costs and select a longer path. Callback caching and invocation order,
hidden edges, cutoff handling, and source/target errors follow NetworkX.
`astar_path_length` rereads the final path's weights after the search.

The default heuristic continues to use the native implementation when the
existing weight checks admit it. Regression coverage in
`tests/python/test_astar_yen.py` exercises both A* APIs across all four graph
types, graph-reading callbacks, live edge mutations, views, and exact numeric
heuristics that previously selected a cost-5 path over a cost-2 path.


## 28. Spectral Centrality Solver Contract

Algebraic connectivity, Fiedler vectors and spectral bisection use the same
weighted graph preparation as spectral ordering: take absolute edge weights,
sum parallel-edge magnitudes, and remove self-loops and zero-weight edges.
Connectivity checks apply to that prepared graph. A zero-weight bridge can
therefore disconnect the spectral problem even when the input is connected.
The caller's graph and node order remain unchanged; normalized and ordinary
Laplacians both consume the prepared graph's canonical weights.

`eigenvector_centrality_numpy` returns the real left eigenvector selected by
SciPy's largest-real eigenpair, normalized to unit Euclidean norm with one
global sign chosen from the sum of its entries. Signed edge weights retain
relative component signs: taking componentwise absolute values can produce
a result that no longer satisfies the eigenvector equation.

Sparse adjacency construction selects floating dtype before converting the
edge weights, allowing Python integer weights outside the machine-integer
range when they have a usable floating representation. `max_iter` and `tol`
are forwarded to ARPACK. `ArpackNoConvergence` propagates unchanged, including
partial eigenpairs; a failed bounded sparse iteration does not trigger an
unbounded dense decomposition.

Empty and disconnected graph errors precede solver parameter errors.
Connected one- and two-node graphs retain SciPy's small-matrix error behavior.
`tests/python/test_eigenvector_numpy_directed_parity.py` covers signed
undirected and directed inputs, eigenpair residuals, solver sign orientation,
large integer weights, nonconvergence, and validation order.

Iterative eigenvector and Katz centrality retain their distinct weight-key
rules. Eigenvector iteration treats a falsy selector as unweighted, while
Katz iteration looks up the supplied key, including literal `None`. Their
Python arithmetic is observable: unnormalized Katz scores can remain
`Decimal` or `Fraction`, and unsupported mixed numeric operations raise at
the same iteration boundary as the reference solver. Sparse conversion must
not silently replace those values or errors with floating-point results.

Iteration reads the caller's graph and vector providers in reference order.
Custom initial-vector or beta mappings can mutate adjacency before later
reads; those updates apply to the same calculation. Foreign graphs, views,
private logical storage and observable mapping/numeric protocols therefore
use the existing owned iterations. Ordinary concrete storage with admitted
numeric values retains native or sparse acceleration.

Assigned public graph readers follow the same rule. A `number_of_nodes`
provider runs at the reference iteration boundary, and its graph mutations
affect subsequent adjacency reads. Spectral admission inspects reader
identity without invoking it; an assigned `edges` provider must not be called
merely to build a snapshot when the iteration itself only reads adjacency.
Class-level reader replacements and inherited providers follow the same
contract. Admission resolves the original descriptors without invoking them,
then keeps changed readers on the owned live iteration. Backend dispatch
checks the original NetworkX graph before conversion, including when a warm
conversion already exists. Mutations and exceptions from those providers
invalidate cached conversions before later algorithms reuse the source.
Owned per-graph edge-dictionary subclasses remain eligible for numeric sparse
iteration when their reads are unchanged builtins. Overridden reads retain
their call order through the owned iteration without an admission-time probe.

Backend dispatch preserves the same provider ordering on both cold and warm
conversion caches. Assigned graph readers, custom node or vector keys, and
logical adjacency keep the original source graph through the owned iteration;
admission does not invoke their hashing or read protocols. Provider mutations
and failures invalidate prior conversions before subsequent algorithms run.
Ordinary cached node, edge and adjacency views remain eligible for conversion.

Native node-key tuple inspection does not hash or compare node labels.
Spectral admission checks labels through that tuple; custom labels, including
members of tuple or frozenset labels, retain the owned live iteration. The
solver's private node iterator tracks insertion order and live node-set changes
without hashing its labels. Their hash callbacks first run when the reference
builds or reads a score mapping, outside any native graph borrow. Topology
updates at that boundary affect the current scores, and callback errors retain
their original type and timing. A previously warmed node iterator or key cache
does not change these rules. Plain immutable builtin labels retain native
acceleration, and public graph iterator types remain unchanged.
Batch Katz admission uses the same callback-free key inspection before
retaining ordered single-query execution for observable node labels.

Sparse iterations require arithmetic compatible with their reordered
matrix reductions. Signed weights or vectors can expose catastrophic
cancellation in the reference per-edge update order, so they retain owned
iteration instead of being silently reassociated. Admission inspects plain
values without calling user numeric conversion methods.

Batched `katz_centrality_many` retains the ordered contract of repeated single
queries. Consume query iterators between completed solves, stop at the first
failure, and keep beta mappings, iteration parameters, exact arithmetic, and
live graph providers on the original graph. A later invalid beta must not
replace an earlier convergence failure. Literal weight keys, including `None`,
follow the single-query lookup rule.

Plain numeric lists or tuples on concrete graphs without observable reader or
key protocols can share one sparse matrix and the existing block worker pool.
NumPy and SciPy remain optional; unavailable matrix accelerators fall back to
the ordered solver. `tests/python/test_centrality.py` covers both execution
paths, query/provider mutation timing, exact results, optional dependencies,
and shared matrix construction.


## 29. Lazy Shortest-Simple-Path Input Lifetime

`shortest_simple_paths` retains the caller's live graph or view from iterator
creation through each resumption. Edge insertion, removal, and attribute
changes before the first result or between results affect subsequent searches
as they do in NetworkX. Callable weights receive the original edge dictionaries,
and their mutations remain visible to the caller and later searches. Already
buffered candidate paths retain NetworkX's existing behavior; this contract
does not promise to rebuild every queued candidate after a mutation.

Multigraph inputs are rejected at the initial function call. Source/target
membership and missing-path validation occur when iteration begins, allowing
node changes between iterator construction and its first advancement.
`tests/python/test_astar_yen.py` covers weighted and unweighted enumeration,
NetworkX and fnx inputs, filtered and reverse views, callback identity, and
the timing of validation.


## 30. Renamed Graph Union

`union` and `union_all` apply each non-`None` prefix using copied relabeling
before checking disjointness between input graphs. Distinct labels within one
input, such as `1` and `"1"`, may map to the same prefixed label. The merged
node keeps its first insertion position and the complete attributes of its
last source node, including an empty attribute dictionary. Simple-edge
attributes follow copied-relabel merge order; multigraph key collisions retain
every edge through key reassignment. Overlap between separately relabeled
inputs remains an error, as do incompatible directedness or multiplicity.

Graph, node, and edge attribute dictionaries are independent shallow copies:
arbitrary attribute keys survive, nested values remain shared, and inputs are
unchanged. Short prefix iterators leave subsequent inputs unrenamed; infinite
iterators are accepted; unused prefixes remain unconsumed.
`tests/python/test_graph_operators_parity.py` covers these rules for both public
operators and all four graph classes without a NetworkX operator fallback.


## 31. Directed Multigraph View Attribute Identity

Reverse and filtered directed multigraph views expose the original parallel
edge dictionaries even when those attributes have not previously been read
from native storage. Predecessor and successor row adapters obtain each
requested pair's live key dictionary instead of returning native attribute
snapshots. Work stays within the requested row; unrelated adjacency and edge
attributes are not materialized.

Attribute writes through a view or a weight callback remain visible in the
parent graph and subsequent traversals. Reading an edge earlier must not
change whether later view writes persist. Simple directed graphs and native
algorithm routes retain their existing access paths.

Reverse `edges`, `in_edges`, and `out_edges` support mapping lookup by `(u, v)`
for DiGraph and `(u, v, key)` for MultiDiGraph, including tuple-valued keys.
The returned dictionary is the original opposite-direction edge's live
attributes. Mapping `get`, `keys`, `items`, and `values` retain their live
behavior as edges are added or removed, including filtered reverse views.

Held reverse adjacency rows observe neighbor and parallel-key changes while
their source row exists. Removing a node or clearing the parent detaches the
held row; reusing that node label must not attach it to the new row. Likewise,
a held parallel-key dictionary emptied by removing its final edge stays
detached when a new edge is added for the same pair. These rules apply to
node indexing, `adj`, `succ`, `pred`, and rows returned by `adjacency()`, using
row-local access rather than materializing unrelated graph storage.

Directed and undirected conversion edge views provide the same keyed mapping
lookup and live key collections. Lookup resolves through the converted
adjacency, preserving filters, original attribute identity, and reciprocal
edge precedence. Multigraph lookup uses an explicit `(u, v, key)` triple;
malformed indices and slices retain their public exception behavior.

Self-loop counts on logical views and assigned private storage read visible
adjacency directly. Each visible parallel self-loop counts separately, and
later graph or filter changes affect the next query. Counts must not copy a
view, coerce its topology, or inspect its attributes. Ordinary native graphs
and foreign inputs retain their existing routing and error behavior.
Conversion edge counts and full unweighted degree queries admit the native
undirected-degree helper only for a concrete DiGraph with native storage;
filtered, reverse, and private-storage sources use their visible topology,
including when a collection asks for a length hint before iteration.

Conversion views share their source's graph-attribute mapping at construction.
Mutating that mapping remains visible through both objects, while assigning a
replacement mapping on either object changes only that object's attributes.
Materialized view caches must track replacement mapping identities.
Union and composition consume the public graph-attribute mapping, including
view overrides, with the later input's values taking precedence.


## 32. Live Weighted Shortest-Path Queries

Dijkstra and Bellman-Ford entry points select their in-process traversal before
graph conversion whenever `weight` is callable. The same rule applies to the
generic path/length dispatchers, predecessor queries, single-source and
multi-source variants, all-shortest-path enumeration, and average distance.
Callbacks receive original edge attributes, including parallel-key mappings,
so a write to a later edge affects subsequent relaxation and writes through
callback arguments remain visible in the caller's graph. Native graph borrows
must not remain active while user callback code runs. Ordinary eligible
attribute-name weights retain their native routes.

The same live-input boundary applies to selector hashing and equality, numeric
weight arithmetic, custom attribute readers, and graph or view providers.
Their callbacks may change weights that later relaxation steps read. Admission
checks exact storage and value types before looking up a weight, and does not
invoke custom readers or arithmetic merely to select a route. Ordinary native
graphs retain their constant-cost admission check; foreign builtin storage
remains eligible for conversion and native traversal.

Generic all-pairs path and length iterators retain the original graph and
compute one source when consumed. They do not execute callbacks at iterator
creation or freeze weights for later sources. Average-distance queries validate
empty, singleton, disconnected, and non-strongly-connected graphs before
evaluating a weight callback. `tests/python/test_weighted_path_adversarial_parity.py`
covers the public variants across all four graph classes, NetworkX and fnx
inputs, filtered views, original-dictionary writes, and lazy consumption.


## 33. Live Distance Measures and Barycenter Writes

Callable-weight eccentricity, diameter, radius, center, periphery, and barycenter
retain the caller's graph throughout their per-source traversals. A callback
sees original edge dictionaries, and later relaxations and sources observe its
attribute changes. Supplied eccentricity or shortest-path dictionaries are
consumed without converting the graph or invoking an unused weight callback.
Safe unweighted defaults retain their native kernels and existing caches.

`barycenter(..., attr=...)` stores each completed distance sum in the original
node dictionary, including a view's parent-shared dictionary. Writes happen as
rows are consumed; an error in a later row does not undo earlier writes. The
graph's NetworkX conversion cache is cleared only after successful completion
of the attribute-writing route. `tests/python/test_distance_measures_parity.py`
covers live callbacks, reverse and filtered views, supplied distances, original
attribute writes, and partial progress on errors.


## 34. Shared Extrema Bounding

Literal `usebounds=True` on an undirected graph with no supplied eccentricity
mapping activates a shared owned bounding engine for diameter, radius, center,
and periphery. Each pivot's shortest-path row tightens lower and upper
eccentricity bounds using the triangle inequality. Alternating low-lower and
high-upper pivots, with degree tie-breaking and metric-specific pruning,
avoids searching every source when the requested extreme is already known.
Pivot selection and callback traversal order follow the NetworkX contract.

The engine reuses public shortest-path queries, retains original graphs for
callable weights, and materializes an ordinary native input at most once.
It keeps linear bound/candidate state and one source-distance row instead of
an all-pairs matrix. A stable finite distance metric requires at most one
search per vertex; cycle and clique cases can still require that worst case.
Directed graphs and supplied eccentricity mappings retain their existing routes.

An unweighted full-distance cache is published only when every bound interval
has collapsed to an exact eccentricity and the topology key remains unchanged.
Pruned but unresolved bounds must never populate that cache. Existing complete
snapshots remain reusable. `tests/python/test_distance_measures_parity.py`
checks results and actual search counts against the live oracle, sparse and
worst-case graph families, exact numeric weights, live callbacks, bypass and
error behavior, and complete versus partial cache publication.


## 35. Incremental Traversal and Live Row Cursors

Lazy traversal APIs retain their execution state between yielded results.
Requesting a prefix must not construct the complete reachable tree or a full
list of its edges. The state contains only visited nodes, active row cursors,
and the pending BFS frontier or DFS stack. Eager tree and dictionary APIs may
continue to use their bulk native kernels.

An ordinary BFS binds the neighbor provider when iteration begins, captures
the initial node count and default depth, and opens the source row. Each newly
discovered child's row is opened before its tree edge is yielded. Its cursor
is retained for the following level. Changes to an unopened row are visible;
resizing an already opened row raises the same iterator error at the same
later advancement as NetworkX. The initial-count early exit is checked after
a parent row is exhausted, not immediately after discovering a child.
Custom neighbor providers can return iterable row objects: provider invocation
and acquiring the row's iterator are separate observable operations, with the
latter deferred until the row is consumed. Callback-raised `StopIteration`
becomes `RuntimeError` with the original cause, as it does in a Python generator.

Labeled BFS selects the stored adjacency mapping after source membership is
checked and before querying directedness or consuming a source iterable.
It keeps that mapping across yields, even if a provider replaces `G._adj`.
Changes within the selected mapping's rows remain visible. Traversal does
not invoke a subclass's public `__getitem__` in place of this stored provider.

DFS emits a forward result before marking the child visited and opening its
row on the next advancement. Preorder emits each component root before its
first row lookup; postorder emits completed rows and omits nodes stopped by
the depth cutoff. A forest retains the caller's node iterator instead of a
snapshot. Explicit depth limits remain valid after graph growth; only a
missing depth limit defaults to the initial graph size.
Direct edge DFS does not infer tree edges by comparing the endpoints of
labeled events: valid non-reflexive nodes such as NaN must never create a
spurious root self-edge. It retains each provider's row object across child
descent; preorder and postorder retain the labeled walk's iterator wrapping.

Native iterator state owns Python node objects and genuine live row cursors,
preserving discovery-object identity, adjacency order, and Python equality.
It holds no graph borrow while executing Python callbacks or returning to the
caller. Stored Python references participate in garbage collection. Existing
Python routes remain available for views, custom sorting, and non-integer
depth comparisons. `tests/python/test_native_traversal_streaming.py` checks
prefix work, between-yield mutations, active-row invalidation, directed
predecessors, provider binding, and suspended-iterator lifetime.

## 36. Label-Constrained Isomorphism Search

The labeled VF2++ entry points compare node labels during candidate selection,
before expanding a partial bijection. Asking whether an isomorphism exists or
requesting one mapping must stop at the first accepted mapping. The iterator
form retains only its active search state and yields independent mapping dicts;
it must not collect all structural automorphisms before applying labels.

Supplied labels use Python's hash/equality semantics, including a shared
non-reflexive label object. Missing labels use `default_label`. Unhashable
labels raise `TypeError`. Empty inputs yield no VF2++ mappings. The default
`node_label=None` looks up attributes actually keyed by `None` and uses
`default_label` for nodes without that key.

A candidate bijection preserves directedness, every self-loop, and the number
of parallel edges between each pair. Simple and multigraph inputs may match
when their per-pair multiplicities agree. Matching node degrees and the simple
projection alone is insufficient. Sparse adjacency counts and an iterative
search stack avoid a dense quadratic matrix and recursion-depth limits.

These multiplicity checks also apply to unlabeled multigraph predicates and
single-mapping queries. All `vf2pp_all_isomorphisms` calls use the sparse
iterator, including calls without a label argument; the native binding that
collects all mappings cannot satisfy prefix-consumption bounds. Simple-graph
predicates and single-mapping queries retain their native short-circuit route
when no actual `None` attribute key or custom label/default needs inspection.
Order and degree mismatches, and empty inputs, are resolved before hashing an
otherwise-unused default label.

Ordinary `is_isomorphic` ignores attributes unless a callback is supplied,
including attributes keyed by `None`. Node and edge callbacks prune partial
assignments before the search descends. Edge callbacks receive attribute
dicts for simple graphs and whole per-pair keydicts for multigraphs; directed
incoming edges and self-loops are included. Both empty graphs are isomorphic
without invoking callbacks, whereas VF2++ returns no empty-graph mapping.

Direct fnx isomorphism calls preserve the caller's attribute dictionaries.
Node and edge callbacks receive the original objects for native, NetworkX,
mixed and view inputs; their writes remain visible on the caller's graphs.
GraphMatcher, DiGraphMatcher, MultiGraphMatcher and MultiDiGraphMatcher retain
those original graph objects, so attribute changes made after construction or
an earlier query remain visible. Labeled and all-mapping VF2++ queries read
custom node mappings through their original protocols. Conversion belongs only
to the admitted native predicate/single-mapping boundary, not to the callback
or custom-reader path.

NetworkX backend dispatch for `is_isomorphic` and the three VF2++ entry points
recovers both original inputs before invoking these same owned wrappers,
including warm conversions, views and mixed native inputs. Callback and
label-reader failures retain their exact exception objects. Both inputs'
conversions are invalidated after eager execution and after each lazy
advancement or close. The all-mapping iterator defers graph and label reads
until first advancement and retains its input owners while its search is
alive. A caller-supplied native graph stays independent even when it is also
cached as the conversion of the other argument.

The existing labeled mapping contract accepts any valid first mapping and the
complete set of valid mappings; input-node positions deterministically break
candidate-order ties and order result keys. The canonical tests in
`tests/python/test_isomorphism_parity.py` compare
mapping sets with NetworkX 3.6.1 and separately check prefix consumption,
label pruning, loop/multiplicity preservation, and exact graph protocols.

## 37. Live Simple-Path Enumeration

`all_simple_paths` and `all_simple_edge_paths` retain the caller's graph when
enumeration begins and whenever the depth-first walk resumes. They must not
convert a foreign graph or a filtered view into a snapshot. Changes to an
unopened branch and changes to live view filters affect later paths. Resizing
an active edge row preserves the caller's iterator error on advancement.
Creating an iterator does not inspect the graph or consume iterable targets;
target consumption can itself mutate the graph before traversal starts.

Both APIs traverse each node through its public `edges` provider, including
subclass overrides. Multigraph traversal requests keys and preserves parallel
edge order; converting edge paths into node paths retains duplicates caused
by parallel edges. A source that is also a target yields the zero-edge path
only when the cutoff comparison accepts zero. Negative and NaN cutoffs yield
no paths, while fractional and infinite limits use their ordinary Python
comparisons. Multiple targets can produce a path to an intermediate target
and then continue toward another target without revisiting a node.

`tests/python/test_simple_paths_conformance.py` compares ordered results,
lazy target consumption, suspended mutations, active-row errors, custom edge
providers, keyed duplicates, and cutoff boundaries against NetworkX 3.6.1
across all four graph classes, foreign inputs, and live filtered views.

## 38. Backend Dispatch Preserves Live Inputs

NetworkX shares converted graphs between algorithms with compatible attribute
hints. Algorithm names are not part of its conversion-cache key, and a cache
hit bypasses `convert_from_nx`. Every cached FrankenNetworkX conversion remains
a native graph; a topological call must not insert the NetworkX source itself
into that cache. Ordinary eager kernels continue to reuse those conversions.
This also means a first live call still pays for a native conversion when
NetworkX requests one; the conversion can serve later eager kernels.

Weighted centrality wrappers recognize both `weight` and `distance` argument
names when recovering live source rows. Wiener index and closeness vitality
use the same boundary. Iterative eigenvector and Katz queries recover graph,
vector and numeric providers whose operations can mutate the original input;
ordinary plain numeric queries retain reusable native conversions. Literal
`None` edge keys in iterative Katz require original attributes even though
the dispatcher's `weight=None` hint normally omits edge attributes.
Provider-driven calls clear stale conversions before and after execution.
Spectral providers requiring original inputs are also identified before a
cold conversion: numeric conversion must not call an edge object's custom
`__float__` before its reference arithmetic. Such calls temporarily pass the
source through the dispatcher, remove that pass-through cache entry on
invocation, and preserve ordinary cached native graphs for other queries.
Admission does not look up selected weights through observable custom
attribute keys; their equality/hash protocols belong to the owned iteration.

Capacity scaling and flow hierarchy are registered owned backend operations.
They share this pre-conversion source boundary for live demand, capacity,
heap, component-size and numeric providers, including warm-cache calls.
Their temporary source cache entries are removed before execution so later
unrelated kernels still receive ordinary native conversions.
`min_cost_flow`, `min_cost_flow_cost` and `network_simplex` use this same
original-input boundary and the shared owned simplex solve. Their directed
simple/multigraph inputs retain keyed flows, selected attribute names, exact
numeric domains and infeasibility/unbounded errors under explicit and
automatic backend selection, without re-entering the upstream dispatcher.

The backend retains a weak reference to each conversion's original input.
Traversal, topological, all-pairs shortest-path, and simple-path iterators
recover that input when invoked, including after an eager call has populated
the cache. They retain it for the lifetime of iteration and observe mutations
at the same iteration boundaries as their direct-call counterparts. Callback
driven path and traversal queries also recover the input, so weight functions
receive its original edge dictionaries and later expansions observe writes
made by weight, heuristic, and neighbor-order callbacks. Positional and keyword
callbacks have the same behavior. The cached native graph does not keep an
otherwise unused source alive, and remains usable after the source expires.
The generic `shortest_path` and `shortest_path_length` calls with neither
endpoint supplied also follow this live all-pairs contract, including for
unweighted and string-weight queries. `all_shortest_paths` computes its
predecessors at call time while passing original dictionaries to callbacks.

`can_run` refreshes conversion provenance from the actual caller before a
cache hit, including caches retained by copying or unpickling a NetworkX
graph. An explicitly supplied native graph is independent: its own mutations
remain authoritative. Callback calls discard cached backend conversions
before and after execution, including failures and individual lazy advances,
because in-place attribute writes do not invoke NetworkX's cache-clearing
graph mutators. Callback-free eager calls retain normal cache reuse.

Generic BFS, labeled BFS and DFS, and beam BFS are available through explicit
and automatic NetworkX backend dispatch. Both cold calls and warmed conversion
caches retain the original graph. Neighbor, sort, beam-value and source-iterator
providers execute when the owned walk advances. Their mutations remain live,
and conversions are invalidated after each advancement, failure and close.

`tests/python/test_backend_convert_from_nx_hints.py` exercises public backend
dispatch with cold and pre-populated caches, mutations before and between
yields, multigraph callback dictionaries, native-cache reuse, and input
lifetime, independent native conversions, copied caches, and queries after
callback writes. The underlying direct-call algorithm contracts remain authoritative
for each supported iterator's exact mutation and error timing.

## 39. Incremental Graph Edit Search

Graph edit distance on simple directed or undirected graphs minimizes node
and edge substitution, deletion, and insertion costs. Cost callbacks receive
attribute dictionaries; explicit substitution costs take precedence over
matching predicates. Roots force the specified node pair to be substituted.
Missing roots raise before timeout validation. The documented cost domain is
nonnegative numeric costs, including zero-cost substitutions.

`optimize_edit_paths` yields a complete, valid edit script whenever the search
improves its incumbent. With `strictly_decreasing=False`, equal-cost scripts
may also be yielded. `optimize_graph_edit_distance` exposes the decreasing
cost sequence. Neither iterator waits for every node correspondence to be
enumerated before yielding, and neither retains a list of all solutions.
Intermediate estimates and tie order follow the local search order; their
costs decrease, and an exhausted search reaches the exact optimum.

The owned search uses an explicit stack of partial injective node mappings,
including node deletions. It charges edge edits when their endpoints become
decided and uses admissible remaining-cost bounds. Its domain is no longer
limited to eight total nodes. Existing small, callback-free native distance
and all-optimal-path queries remain available. Parallel-edge handling extends
this search as specified in section 44.

A supplied timeout must be greater than zero and bounds search time using a
monotonic clock. As in NetworkX 3.6.1, root and cost setup precede the timeout
check. Expiration stops enumeration; `graph_edit_distance` returns the best
complete cost seen, or `None` if no admissible complete script was found.
User callbacks cannot be preempted. An upper bound excludes more expensive
scripts, including when a timeout is used. Iterators validate and initialize
on advancement, and can be closed without completing the search.

Returned edge edits must realize the reported cost: when deleting and
reinserting an edge is cheaper than substituting it, the script contains the
deletion and insertion. Equal-cost alternatives remain eligible for the
all-optimal-path collector across node correspondences; tied edge operations
need not have the same representative or order as NetworkX. Tests compare
exact final costs against NetworkX,
validate edit scripts, and exercise bounded prefix work, roots, callbacks,
timeouts, upper bounds, loops, and graphs beyond the former size limit.

Existing compatibility limits remain: NetworkX 3.6.1 sometimes substitutes a
self-loop for a non-loop under a node mapping that does not preserve both
endpoints, whereas both the previous owned solver and this search preserve
endpoints. Some callback cost models also produce different optima from
NetworkX's search. These are pre-existing differences, not resolved by adding
incremental search. Small exhaustive comparisons against the previous owned
solver additionally check that pruning preserves its minimum costs.

## 40. Graph Deepcopy Object Identity

`copy.deepcopy(G, memo)` creates an independent graph of the same class and
registers it in the shared memo before copying any user-controlled contents.
Graph, node, edge, and custom instance attributes can refer back to the graph,
to their own dictionaries, or to dictionaries in another attribute layer.
Those cycles and aliases remain intact in the copy, without references leaking
back to mutable source objects. Existing memo entries remain authoritative.

Node objects, multigraph keys, attribute keys, and attribute values all follow
Python's deepcopy protocol. A copied node referenced by an attribute is the
same object as that node's key in the copied graph. Neighbor and parallel-key
order, undirected edge sharing, and directed successor/predecessor sharing
remain unchanged. Frozen state and user instance attributes survive copying;
exceptions raised by a user object's `__deepcopy__` propagate unchanged.
Canonical cached graph views referenced by attributes remain bound to the
copied graph and retain live access to its copied stores.

Concrete shallow and deep copies retain the source graph's compatibility
mode, independent of the ambient mode during copying. Their decision history
starts fresh, as on the native copy route. User copy callbacks still observe
the ambient mode; constructing the copy must not change their context.

Filtered, reverse, and directed/undirected conversion views use the same
memo-aware object-copy boundary. Allocate and register the concrete snapshot
before copying the original view's logical stores or user attributes. A
graph/node/edge attribute can refer back to the view without recursion, and
aliases to attribute dictionaries remain intact in an enclosing copied
container. The snapshot retains frozen state, visible topology, neighbor/key
order, and directed successor/predecessor sharing. An undirected conversion
view can expose distinct attributes in reciprocal rows; copying preserves
those rows instead of merging them through a structural `copy()` operation.
User instance state, including private and non-string attribute names and
replaced cached readers, survives both deepcopy and pickle snapshots. Only
the view's own parent, filter machinery, and generated readers are excluded.

The ordinary native route is eligible only when its inputs cannot require
object remapping or observable copy callbacks. Explicit assignments to public
cached readers use the general route before those values can be consulted as
structural providers; ordinary scalar graphs retain their existing native
eligibility. Built-in private node facades enumerate through captured native
node readers for deepcopy and pickle, so replacing `G.nodes` does not replace
the logical node store. Assigned private mappings retain their own persistence
protocols. General Python object graphs use a memo-aware route that preserves
the complete identity relationships.
`tests/python/test_deepcopy_conformance_guard.py` and
`tests/python/test_copy_semantics_parity.py` compare these semantics with
NetworkX across all four graph classes, including recursive attributes,
mutable node objects, shared dictionaries, supplied memos, and copy failures.
`tests/python/test_view_descriptor_parity.py` also checks caller assignments
after cached-reader access through both deepcopy and pickle round trips.

## 41. Disjoint Paths Across Graph Inputs and Backend Dispatch

`edge_disjoint_paths` and `node_disjoint_paths` accept all four graph classes,
including NetworkX inputs, live views, and graph subclasses. They expose
generators: endpoint validation, auxiliary-network construction, and flow
execution start on advancement. Changes made before the first advancement
affect the result. Unit-capacity auxiliaries use the caller's public node and
edge providers, including their order and custom behavior. Concrete native
graphs without Python storage overrides retain their native default route.

An explicit auxiliary graph or residual network remains the caller's object;
custom flow functions receive those same objects and the established solver
options. Cutoff, missing endpoints, disconnected terminals, and same-terminal
queries retain NetworkX's outcomes and error timing. Path decomposition does
not consume the residual network, which can immediately be reused for another
terminal pair. For node-disjoint paths, auxiliary node identifiers map back to
the original node objects through the supplied `mapping` and node `id` data.

Both algorithms are registered for public NetworkX backend dispatch. The main
graph and an optional auxiliary graph recover their own live source on a
conversion-cache hit. This applies independently when either input is already
native, when arguments are positional or keyword arguments, and when cached
conversions survive graph copying. Callback writes invalidate conversions of
every restored graph, including on later generator advances and failures;
ordinary unrelated native kernels retain their normal cached inputs.

`tests/python/test_disjoint_paths_nopath_contract.py` compares ordered paths,
lazy validation, changed views, caller-owned auxiliary/residual state, and
public backend dispatch with cold and pre-populated caches against NetworkX
3.6.1. Existing solver-specific cutoff and path-order cases remain part of the
contract.

## 42. Native Eligibility with Logical Python Storage

Assigned node and adjacency mappings are the authoritative graph, including
when they represent a deep copy with recursive Python objects. A native
kernel that reads a graph's internal Rust storage is eligible only when that
storage represents the public graph. Exact concrete type alone does not prove
this: concrete graphs can carry assigned mappings too. Views and subclasses
retain their public mapping behavior.

Predicates, path validation, attribute readers and writers, graph copies,
dictionary exports, matrix exports, and minimum-cost flow must observe the
same logical nodes, edges, keys, and attributes as ordinary graph iteration.
Replacing or mutating a logical row affects the next call. In-place setters
write the caller's attribute dictionaries rather than hidden native mirrors.
The ordinary concrete graph route retains its native fast paths.

Native admission checks fall back to existing owned public-row operations,
or materialize a graph only at a static read-only kernel boundary. Callback
algorithms continue receiving the caller's live dictionaries. Minimum-cost
flow extracts capacities, costs, and demands from the same graph and rejects
negative logical capacities before optimization. Dense and sparse matrix
families and their Laplacian/spectral consumers preserve logical graph data
and nodelist order instead of interpreting empty or stale native storage.

Focused tests compare assigned-storage graphs, graph views, and copied graphs
against NetworkX, with deliberately different native and logical contents.
They also verify retained native routes on ordinary concrete graphs.

Private adjacency writes through a native graph's writable facade replace or
remove every existing key in a nonempty parallel-edge set, including self-loops.
Replacing a row or key dictionary from an alias first captures its shallow
contents, so removing old edges does not erase the replacement input. New
attributes are applied as mappings and retain nonstring keys, parameter-name
keys such as `key`, and nested value identity.

An independently assigned node store or opposite directed row does not change
the storage authority of a native adjacency side. Its edge-key dictionary
retains requested-key deletion, an empty pair after deleting the final key,
and detachment when the graph later removes the pair. These repairs retain
the existing native facade's whole-edge write policy; they do not claim raw
row-object aliasing or inconsistent half-edge storage parity.

## 43. Graph Pickle Persistence and Object Identity

Shallow copies of concrete graph subclasses retain inherited and name-mangled
slot values by identity, including aliases to instance attributes or the source
graph. Unset slots stay unset, and replacing a slot on the copy does not replace
the source's slot. Copying does not rerun subclass initialization. Concrete
graphs and graph views share the same slot-preservation mechanism.

Node and edge contraction retain the removed node's actual attribute dictionary
in contraction metadata. In-place contraction preserves caller-held aliases and
self-references; copied contraction retains the independent shallow dictionary
from the graph copy, with its nested values still shared. The same rule applies
to `identified_nodes`, `contracted_nodes`, and `contracted_edge`, on all four
graph classes and NetworkX graph inputs.

Shallow copying a graph view creates a distinct live wrapper of the same
view class. It shares the source view's graph, node, adjacency, edge-key and
attribute mappings, filter predicates, cached public views, and user attribute
values. Parent topology changes and mutable filter state remain visible through
both wrappers. The instance dictionary itself and native dispatch bookkeeping
belong to the new wrapper; replacing an instance attribute must not replace it
on the original view. Preserve subclass slots and frozen state without rerunning
initialization, visiting graph rows, or invoking filter predicates. This applies
to filtered, reverse and conversion views, including nested combinations.
Inherited edge-data lookup reads the view's logical adjacency: filtering a
reverse view does not reverse endpoints a second time or reveal hidden edges.
`view.copy()` and deep-copy/pickle snapshots retain their separate independent
graph contracts.

A pickle round trip allocates and memoizes each graph before restoring its
contents. Graph, node, edge, and instance attributes may refer back to that
graph, to their own dictionaries, or to other attribute layers. Those cycles
and aliases survive saving and loading, including graphs inside larger Python
containers and mutually referring graphs. Python's pickle protocol owns node
objects, multigraph keys, attribute keys, and values; unsupported objects and
user serialization errors remain visible to the caller.

The persisted graph is its logical public storage. Python-owned graph metadata
and assigned node/adjacency mappings, including those produced by deepcopy,
must not be replaced by stale or empty native storage. Restored graph classes,
node and neighbor order, parallel keys, directed predecessor/successor sharing,
and undirected edge sharing remain intact. Custom mapping classes, Python
instance attributes, subclass slots, and frozen state survive the round trip.
Loading does not rerun a graph subclass's initialization.

Public graph attributes referenced alongside the graph in one pickle retain
their identity with the corresponding restored graph dictionaries. Ordinary
graphs remain usable for algorithms and mutation after loading; private logical
stores retain the same authoritative behavior. Native reconstruction may be
used only when it does not discard Python object identity or state. Tests use
the supported pickle protocols and real NetworkX round trips as the oracle,
alongside existing row-order, frozen-state, and private-storage regressions.

Filtered, reverse, and conversion graph views persist as independent frozen
concrete snapshots. Their reduction allocates and memoizes the concrete graph
before serializing the original view's attributes and visible logical stores.
Do not place a structural copy in reconstruction arguments: attributes can
refer back to the original view, and dictionaries can also occur outside it
in the same pickle. Keep those cycles and shared dictionaries intact without
serializing filter functions or a hidden parent topology. Preserve visible
node, neighbor, and parallel-key order, reciprocal attribute rows, and node
and edge-key object identities. Reverse snapshots retain the same output
class as their existing copy operation without rerunning its initializer.

## 44. Multigraph Edit Distance and Keyed Edit Scripts

All four graph edit APIs accept `MultiGraph` and `MultiDiGraph`, including
mixed simple/multigraph pairs with the same directedness, foreign NetworkX
graphs, and logical graph views. Every parallel edge is a separate editable
object. An edge's key identifies it in the returned script but is not itself
an edit cost. Simple-graph edges remain pairs and multigraph edges are triples,
retaining the original node and key objects on each side independently.

Edge substitution and matching callbacks receive each individual edge's live
attribute dictionary, rather than the dictionary containing all parallel
keys. Explicit substitution costs override matching predicates. Once a node
correspondence fixes an endpoint pair, the edges between those endpoints need
an exact minimum-cost partial one-to-one assignment. Independent greedy edge
matches are insufficient: two parallel edges can require a crossed assignment
to achieve the minimum. Deletions and insertions remain available when they
cost less than any substitution. Each original edge occurs exactly once in
a complete edit script, and the operations realize its reported total cost.

The owned search solves these endpoint-local assignments without requiring
SciPy or delegating to NetworkX. Default unit costs admit a linear bundle
match; custom costs use a polynomial augmenting-path assignment. Resolved
bundle pairs are reused across node correspondences. Search timeout checks
also apply during a nontrivial edge assignment. Node roots, bounds, lazy
initialization, improving iterators, and equal-cost node correspondences keep
the section-39 contract; tied edge assignments have a deterministic
representative without a promise to enumerate every equivalent permutation.

Self-loops are edited as loops at their mapped node. Existing section-39
endpoint-preservation differences from NetworkX also apply to multigraphs:
NetworkX 3.6.1 can omit loops from a script or substitute a loop with an
ordinary edge. Those outputs are not used to weaken edge coverage or cost
validation. Focused oracle comparisons cover loop-free multigraphs, while
independent exhaustive checks cover loop scripts and arbitrary edge costs.

NetworkX backend dispatch exposes all four edit APIs with the same two input
graphs, including mixed native/NetworkX inputs. Conversion must not detach
either graph's node or edge attribute dictionaries from cost and matching
callbacks. A warmed conversion cache cannot substitute an earlier snapshot,
and a graph explicitly supplied as a native input remains that independent
input even when it originated from an earlier conversion. Both incremental
APIs retain their input graphs and defer search initialization until the first
advancement. Callback writes invalidate cached conversions on both inputs,
including after an exception, iterator advancement, or iterator closure.

## 45. Incremental Component Decomposition

`connected_components`, `weakly_connected_components`,
`strongly_connected_components`, `biconnected_components`,
`biconnected_component_edges`, and `articulation_points` return true generators.
The directed/undirected type restrictions are checked when the function is
called. Graph traversal begins only when the result is advanced, so edits to
the caller's graph or a view's filter before the first advance are visible.
Foreign graphs, native graphs, and assigned logical adjacency follow the same
contract; component discovery does not require copying attributes or graph
storage.

The iterator keeps its traversal frontier and yields a component as soon as
that component is complete. Requesting a prefix does not enumerate all later
components or prepare their edges. Connected and weak components are emitted
in graph node order; weak connectivity follows both directed adjacency rows.
Strong components follow ordered depth-first search and emit a completed
strong component before returning to its predecessors. Each member set starts
with its DFS root and inserts the other members in reverse DFS completion
order. Reverse discovery order is not equivalent: colliding node hashes can
change set iteration, subsequent cycle pivots and attracting-component output.
A separate pending-completion stack preserves this contract in linear space
and O(V + E) traversal time. An iterative low-link search supports long chains
without Python recursion. No iterator wraps an eager native list of every
component.

Undirected biconnected decomposition follows depth-first discovery and returns
edge pairs in traversal orientation and order. A bridge forms a two-node
component, while an isolated node forms no biconnected component. Parallel
edges do not repeat neighbor pairs in this API. Root self-loops and non-root
self-loops retain the NetworkX 3.6.1 traversal behavior. Articulation points are
emitted once in the order their separating subtree is completed; the DFS root
is an articulation point only when it has multiple tree children. The search
stores uncompleted DFS edges, rather than the list of all finished components.

Public backend dispatch restores the original graph for these iterator calls
even after an unrelated eager algorithm warmed NetworkX's conversion cache.
Cold dispatch passes the source through without materializing the graph and
removes its temporary conversion-cache entry before calling the iterator;
an unrelated subsequent algorithm must still obtain a native conversion.
Explicitly supplied native graphs continue to use their own public topology.
Completed or closed generators release traversal state normally. Eager count
and connectivity-predicate APIs retain their existing native implementations.
Focused tests compare ordered results, eager type errors, lazy row access,
pre-advance mutations, graph views, multigraphs, deep chains, and cold/warm
public backend calls against NetworkX 3.6.1.

## 46. Target Shortest Paths on Public Graph Inputs

`single_target_shortest_path` and `single_target_shortest_path_length` accept
all four graph classes from either library, graph subclasses, and filtered or
reversed views. They follow the caller's current predecessor rows for directed
graphs and adjacency rows for undirected graphs. Returned dictionaries retain
BFS discovery order, and equal-length path ties follow the original row order.
Paths end in the target object supplied by the caller, including an object
equal to a stored key but distinct by identity.

These eager queries validate a missing target with their established distinct
error wording. Fractional, negative, and unbounded cutoffs retain the public
BFS boundary behavior. Logical/private stores and nonconcrete graph objects
use owned traversal without being handed to a strict native type gate. Exact
native graphs keep their native route, and an eligible native reverse view
still uses the root's forward BFS when the cutoff supports that route.

## 47. Owned Louvain Levels and Random-Source Protocol

`community.louvain_communities` and `community.louvain_partitions` use the
same weighted Louvain level semantics for Graph, DiGraph, MultiGraph, and
MultiDiGraph. Ordinary native inputs retain the existing kernel. Views,
subclasses, nonstring weight keys, unsupported numeric domains, and custom
random sources run an owned Python level engine without calling NetworkX's
Louvain algorithms or converting the caller to a NetworkX graph.

Resolve and validate the random source when the public API is called, before
graph traversal or `max_level` validation. An integer seed, the global
`random` module, `None`, `random.Random`, and NumPy random sources retain
NetworkX 3.6.1's state and error behavior. The native MT19937 state handoff
must not bypass custom `shuffle`, `_randbelow`, `getrandbits`, `random`,
`getstate`, `setstate`, or Random construction/seed hooks. Resolve an integer
seed only once, including large integers that require an RNG object.
Instance overrides, Random subclasses, and class-level monkeypatches after
import require the owned route.

The partition iterator does not inspect graph topology or weights until
its first resume. Edits before that resume are visible. Once the working
graph has been built, later edits to the caller's graph do not change the
remaining levels. Each yielded partition has independent sets. Consuming
one level must not compute later levels or consume their random draws;
external RNG draws between resumes affect subsequent shuffles normally.

Start with one community per node in graph iteration order. An edgeless
graph yields this partition once without shuffling, including `[]` for
the null graph. Otherwise compute its initial modularity before preparing
the working graph. Parallel-edge weights are added in input edge order;
self-loops contribute to degree/modularity but are excluded from candidate
neighbor communities. A simple graph preserves its construction class;
multigraphs reduce to the corresponding simple directed/undirected graph.
Subclass constructors can change working-node order and node memberships;
read a moved node's actual `nodes` membership at each move.
Read live attribute dictionaries explicitly so filtered views support
arbitrary weight keys. Preserve NetworkX's algorithm-specific behavior for
`weight=None`: degrees use the unweighted convention, while projected edge
values can select an actual `None` key; absent keys default to one. Literal
boolean selectors retain their upstream errors.

At each level, shuffle the current node labels once and reuse that order
until a complete pass makes no moves. Candidate communities follow the
first encounter of neighbors; directed graphs consider outgoing then
incoming neighbors. Remove the node's degree from its current community
temporarily and choose only a strictly positive modularity gain. Equal
gains retain the first candidate. The undirected gain includes the
resolution-scaled product of community degree and node degree divided by
`2*m**2`; the directed gain uses the sum of outgoing/incoming cross-products
divided by `m**2`. Keep Python arithmetic and summation order, including
the float-zero accumulation used for neighbor-community weights; do not
coerce arbitrary input weights to float64.

Communities retain their set update history and list order. Coarsening
assigns integer node IDs in nonempty community order, sums inter-community
edges in the previous graph's edge order, and preserves merged self-loops.
The original working graph's weighted size `m` remains the denominator for
subsequent move phases. Yield the first local optimum even if no node moved.
After a yield resumes, stop when its modularity gain is at most `threshold`;
otherwise coarsen and search again, yielding only levels that improve by
moving nodes. `max_level` limits consumption rather than computing levels
in advance. Nonpositive values raise the existing ValueError; other invalid
limits retain `itertools.islice` validation and timing.

`tests/python/test_louvain_owned.py` compares yielded levels and RNG state,
custom shuffle hooks, exact/nonstring weights, directed parallel edges,
filtered/private graphs, level limits, independent yielded sets, graph edits
before/after first resume, and native-route retention. Its large-Fraction
regressions also require weighted degree and size to preserve exact numeric
types before exponentiation; matching ordinary partitions alone does not
establish that numeric-domain contract.

## 48. Streaming Line-Based Graph I/O

`parse_edgelist`, `parse_adjlist`, and `parse_multiline_adjlist` consume an
arbitrary line iterator in order. They clear an existing `create_using`
graph before requesting its first line. Completed records are visible before
the iterator is advanced again, and a later iteration, decoding, conversion,
or graph-mutation failure retains the successful prefix. An adjacency-list
record adds its source before converting neighbors; a multiline record adds
its source before requesting neighbor records. Edge-list conversion finishes
before the corresponding edge is added. Per-line graph method hooks remain
observable, including subclass and instance methods. Node and edge order,
parallel-edge multiplicity, duplicate updates, literal attributes, and typed
attribute error messages retain their existing public contracts.

Readers accept string and pathlib paths with suffix-directed gzip (`.gz` or
`.gzip`) and bzip2 (`.bz2`) decompression. They also accept caller-owned binary
and text streams without closing them. Streaming reader fallbacks decode and
parse one physical line at a time; they must not require an unbounded `read`,
seek, full line list, or whole-graph edge buffer. String convenience parser
inputs retain their established split-lines interpretation. Existing default
native file routes and the default multiline byte scanner are separately
admitted fast paths, with no claim that these whole-file routes are bounded.

`write_weighted_edgelist` and `write_multiline_adjlist` use the same compressed
path ownership contract, encode and write records incrementally, and leave
caller-owned binary/text destinations open on success or failure. Weighted
output includes only an existing `weight` attribute; a missing weight does
not invent a numeric value. Multiline output retains its three comment
headers and the format's node/edge order. Successfully written prefix records
remain when a later conversion, encoding, or output operation fails.

FrankenNetworkX's existing acceptance of text-mode multiline reader handles
and dictionary-literal multiline attributes with an `edgetype` hint remains
available. NetworkX 3.6.1 rejects those combinations; tests distinguish
these established extensions from direct oracle comparisons.

`tests/python/test_streaming_line_io.py` covers all four graph classes,
compressed roundtrips, foreign graph protocols, subclass/instance mutation
hooks, source/converter event ordering, invalid later lines, encoding
failures, nonseekable streams, handle lifetime, and bounded outstanding input.

The graph6 and sparse6 file interfaces share the same suffix-directed
compression and handle-ownership contract. Readers parse one physical line
before requesting the next, ignore blank lines, and preserve NetworkX's
single-graph result versus a list for zero or multiple records. A malformed
record raises at that record, leaving later records unread on caller streams.
Input bytes are streamed, while returned graphs retain the documented eager
result shape. Writers emit the existing format bytes through the shared
compressed-path opener. Caller-owned binary streams stay open on success or
failure; the established ASCII text-stream extension remains available.
`tests/python/test_graph6_sparse6_weighted.py` compares compressed payloads,
cross-library reads, result shapes, nonseekable sources, and failure positions.

## 49. Configurable GraphML Decoding

GraphML's complete decoder owns XML interpretation and constructs the selected
FrankenNetworkX graph directly. The native simple-document route remains an
independently admitted fast path. The complete decoder handles defaults,
parallel edges, lexical edge IDs, configurable node/edge-key conversions, and
yFiles data without creating a NetworkX graph or calling its GraphML reader.

Convert every declared node and each edge endpoint in read order; do not memoize
user conversion callbacks. Process a graph's direct nodes before its direct
edges, then graph data. Node conversion may merge lexical IDs and create
parallel edges. Detect parallelism before a converted edge key merges an
existing keyed edge. Preserve original edge-ID strings as `id` attributes when
returning a simple graph. Only `ValueError` from edge-key conversion retains the
lexical ID; other exceptions propagate. Defaults populate `node_default` and
`edge_default` metadata without being copied onto every node and edge.

`GraphMLReader` exposes its key/type/data decoding methods and produces graphs
lazily: callbacks for the next graph wait until the iterator resumes. Its
multigraph and edge-ID state persists across graphs and repeated calls. The
public `parse_graphml` and `read_graphml` functions consume the complete reader
before returning its first graph, so an invalid later graph still raises.

String and file readers retain distinct missing-namespace recovery protocols.
Only literal `<graphml>` receives the standard namespace. A file reader seeks
the original source to zero and performs its recovery read there; caller-owned
streams stay open. Text/byte mismatches, unavailable seeking, nonzero starting
offsets, literal byte paths, XML encodings, and malformed XML retain their
observable errors. Strict full decoding retains NetworkX's format behavior;
explicit native validation and hardened recovery continue to own policy
decisions and audit records, including existing unsupported-recovery errors.

`tests/python/test_graphml_reader_surface.py` and the GraphML cases in
`tests/python/test_gml_graphml_attribute_roundtrip.py` cover these contracts,
including planted failures if the full decoder delegates to NetworkX.

Recovered GraphML node-type collisions merge attributes in source node order:
earlier distinct keys survive, later values overwrite repeated keys without
moving their positions, and the first converted node keeps its position.
Reconstruction retains the parser's compatibility mode and recovery ledger.
Missing, blank, or unsupported scalar key types can recover through the full
owned decoder, retaining parallel edges, lexical edge IDs, defaults, typed
node collisions, custom key conversion, and force-multigraph options. The
original native validator remains the policy authority. Repair only scalar
key declarations in a private XML tree, decline DOCTYPE, CDATA, unsupported
encodings and non-scalar declarations, then require strict native validation
of the entire repaired document before reconstructing it. This admission
cannot infer safety from a truncated recovery ledger. Copy the original
policy and decision records to the complete result after decoding.

Other recoveries keep their existing restrictions. When those paths cannot
represent parallel edges, including edges introduced by node conversion,
raise the unsupported-recovery error before replacing the policy carrier's
data; never silently collapse those edges.

## 50. Connectivity Queries with Custom Flow Solvers and Cutoffs

`edge_connectivity` owns local and global queries with a supplied solver or
cutoff. `minimum_edge_cut` and `minimum_node_cut` own their custom-solver
orchestration. These routes use the caller's graph protocol without converting
it into a NetworkX graph. Ordinary default native routes remain separately
admitted. Global queries construct one auxiliary graph and one residual and
reuse them for their local flow computations; callback-visible endpoints,
solver options, residual identity, and invocation order are observable.

Default native node-connectivity queries use exact unit-capacity vertex-split
residual flows. Reverse residual arcs may reroute earlier paths, a direct
source-to-target edge contributes one path, and self-loops add no independent
route. Local queries, averages, and full or subset pair matrices share this
contract; selecting fewer endpoints must not change their pairwise values.
Simple directed global queries take the minimum over all ordered endpoint
pairs, preserving the existing intentional correction of NetworkX's global
shortcut on strongly connected counterexamples. Reused workspaces reset their
residual capacities for every pair. The approximation namespace remains a
separate API.

Default flow selection uses Edmonds-Karp. Solver-specific options depend on
the identity of actual built-in solvers, not a callable's name. Falsey callable
objects are still supplied solvers. Cutoffs keep their numeric semantics:
global bounds can remain fractional, while a local query reports the achieved
flow. Source/target omissions, missing endpoints, null graphs, disconnected
graphs, and malformed callback results retain their existing error precedence.

Connectivity's local cut extraction removes saturated residual arcs, traverses
the resulting residual, then restores the removed arcs. This operation is
observable through custom mutation hooks and through residual row ordering on
later solver calls. Required flow metadata is read at the same completion
boundary. The standalone `minimum_cut` API retains its existing non-mutating
residual contract. High-level edge-cut extraction uses the auxiliary graph
captured before the callback; mutation of the original graph remains visible
to the caller without retroactively changing that captured cut graph.

`tests/python/test_connectivity_namespace_native_routing.py` compares all four
graph families and four flow solvers, exact cutoff domains, shared state,
callback mutations, invalid residuals, and the custom-hook cut lifecycle, with
NetworkX connectivity delegation and whole-graph conversion disabled.

## 51. Live Weighted Betweenness Queries

Callable weights in node and edge betweenness receive the original graph's
live edge attribute mapping, including the keyed mapping of a multigraph.
Mutations of weights or topology observed by later traversal steps affect
that same calculation. Foreign graphs, subclasses and views retain their
public graph protocol; an undirected view of a directed graph can expose
different attribute mappings for opposite endpoint lookups. These inputs use
the existing owned Brandes traversal without a coercion snapshot. Ordinary
concrete graphs retain their separately admitted native routes.

Source sampling retains the caller's random-state advancement. Structural
mutations preserve the oracle's error boundary too: a multigraph edge removed
during traversal can make the final keyed contribution split fail. The
regression matrix compares returned scores or exception type/arguments,
callback traces, edge dictionary identity, resulting graph attributes,
private adjacency, filtered views and sampled RNG state.

Node betweenness evaluates endpoint truth after each source search and again
when choosing its normalization domain. Both node and edge betweenness read
normalization truth during final rescaling, preserving version-specific
small-graph early returns. Non-boolean option providers use the owned traversal on
the caller's graph; neither native parameter extraction nor a cached backend
conversion may evaluate their truth early or freeze later source searches.
The legacy normalization branch reads endpoint truth exactly once.
Rescaling captures the current node count after traversal, so a sampled
endpoint provider can add an isolated node and change the denominator without
adding a score entry for that node.

Subset node and edge betweenness accepts native and NetworkX graphs through
standalone and backend calls. Admitted simple inputs convert before either
unweighted or weighted native kernels. Source and target iterables and custom
label hash/equality protocols remain live: a source traversal completes before
its target set is consumed, including after an unrelated cached backend
conversion.

## 52. Flow Solvers over Caller Graphs and Residuals

Residual construction consumes the original graph's node iteration,
`edges(data=True)`, direction and multigraph predicates. Numeric attributes
and custom graph providers retain their identity and evaluation order.
Edmonds-Karp, Dinitz, shortest augmenting path, preflow push and
Boykov-Kolmogorov validate source, sink and endpoint equality against that
original graph. A supplied residual is reused by identity and avoids reading
input topology that the solver does not need. Solver-specific initialization,
attribute mutation, errors and partial results remain observable.

Custom-solver node connectivity, all-pairs connectivity and average node
connectivity preserve the caller's graph, degree and neighbor protocols.
Global queries share their auxiliary and residual objects across local
computations. Directed all-pairs queries also use this owned protocol path.
Ordinary native routes keep their existing input admission.

Conversion from FrankenNetworkX to NetworkX reads assigned logical node,
adjacency, successor and predecessor mappings rather than stale native
storage. Node iteration and outer adjacency iteration can have different
orders and equal-valued keys with distinct Python identities; both survive
conversion, along with live attributes and directed predecessor order.
This applies to all four graph classes and to callbacks
that enter NetworkX through backend dispatch. Ordinary native storage retains
its bulk conversion routes.

The regression cases prohibit unnecessary input topology/attribute exports,
compare live capacity-provider reads and endpoint validation, and retain
residual and edge-dictionary identity across all five solvers. Removing
conversion avoids rebuilding the input when a reusable residual is supplied;
it is not evidence of a measured speedup.

## 53. Complete GEXF Decoding

The complete GEXF decoder constructs FrankenNetworkX graphs directly from
ElementTree records. The reader first tries its selected namespace, then
the supported version namespaces in declaration order, and reads the first
matching direct graph. Version selection and detected multigraph state
persist across calls on a reader. Graph names and start/end metadata remain
strings; only literal dynamic mode selects dynamic metadata. Date time
formats use strings. Attribute definitions and defaults have independent
node/edge scopes, with the historical static double `weight` edge definition.
Defaults remain metadata rather than being copied onto every graph object.

Node attributes, parents, version-specific intervals, visualization and times
are decoded before node conversion. Nested nodes are inserted before their
parent, retaining inherited parent IDs. Conversion runs for each declared
node and edge endpoint, without callback memoization. Edges validate mixed
direction before endpoint conversion, decode dynamic attributes and times,
then preserve lexical IDs, optional typed `networkx_key`, weights and labels.
Parallelism is detected before keyed insertion can collapse an existing edge.
Mutual edges add the reverse arc. A reader that has observed parallelism
continues returning multigraphs on later calls.

Dynamic values retain ordered `(value, start, end)` lists, including repeated
titles and their observable errors. Version 1.1 slices retain textual bounds;
later spells and start/end values use the declared time converter. The
decoder preserves boolean and numeric conversion failures, missing attribute
errors, callback order, public reader method hooks and visualization defaults.
File ownership, compression, relabeling, native simple-input admission and
explicit strict/hardened validation remain the responsibility of the existing
readwrite boundary. Repaired native results retain their policy ledger.

For rich input, explicit strict/hardened modes and ambient hardened mode use a
native validation projection before complete reconstruction. The projection
validates every parallel edge and keeps node/edge attribute IDs in independent
scopes; it is not the public multigraph result. Its validation-only numeric
path accepts signed decimal integers beyond the native i64 range. The complete
decoder retains their exact Python integer values, defaults, edge keys and
metadata, and receives the validated policy ledger. The ordinary native reader
retains its simple-graph and bounded-integer contract.

When native recovery repairs a document, a simple projection cannot preserve
parallel edges, dynamic values, hierarchy, visualization data or wide integer
attributes. The boundary raises `NetworkXNotImplemented` for those repairs
rather than returning incomplete data. The full input scan retains rich-feature
markers on malformed XML, and repaired rich documents cannot return projections
that omit defaults or metadata. Scalar repairs on representable simple inputs
continue to return the native result and its policy evidence.

## 54. Complete GML Decoding

Strict GML decoding parses the complete ordered key/value document before
constructing its graph. Keys are ASCII identifiers; values include arbitrary
width signed integers, decimal/exponent floats, infinities, NaN, quoted XML
character entities, nested mappings and repeated-key lists. The
`_networkx_list_start` marker preserves singleton lists. Destringizers run on
decoded strings in lexical encounter order; only `ValueError` is swallowed,
and falsey callable objects retain the existing conditional-call behavior.

Nodes are constructed before edges even when edge declarations occur first.
ID, label, endpoint, duplicate edge and multigraph-key validation preserve
their exact ordering and errors. Renaming to labels happens after edge
validation and preserves each label's type even when it compares equal to
the original ID. Truthiness selects direction and multigraph flags. A
restricted native parse cannot reject valid full-grammar input before the
complete decoder sees it, including wide IDs and edges declared before nodes.

File reads retain ASCII decoding, compressed paths and caller stream
ownership; parser inputs retain established text, bytes and line-iterator
normalization. Ordinary strict reads use one complete decode. Explicit
native read modes and hardened parsing preserve native validation, bounded
recovery and decision records; clean complete reconstructions retain that
policy metadata where applicable.

## 55. Single Minimum-Cost Flow Solve Boundary

`min_cost_flow`, `min_cost_flow_cost` and `network_simplex` share one ordered
input extraction and one simplex result. Node demands are read before edge
records. Foreign graphs, subclasses and assigned logical storage retain
their public providers through extraction; ordinary native storage can use
the existing bulk reader when selected demands, capacities and weights are
ordinary scalar values in plain attribute dictionaries. Numeric validation
callbacks can change later self-loop scans and must retain live public
storage. A demand provider can change later edge input, and a solved cost
must not be reconstructed from a later graph snapshot.

A non-self-loop edge with zero capacity appears as zero flow but does not
participate in weight validation, optimization arithmetic or the result's
numeric type. Self-loops retain their separate validation and cost rules.
Active-edge validation preserves infinite-demand/weight, demand-balance,
negative-capacity and infeasibility ordering. The solver's exact cost and
ordered keyed flow dictionary are the authoritative public outputs.

## 56. Weighted Label Propagation State

Candidate community labels retain first-neighbor encounter order. A label
is recorded once even if its accumulated weight is zero or contributions
cancel before a later positive contribution. Numeric zero is not an unseen
marker. Weighted accumulation begins at floating-point zero, retaining the
reference arithmetic and failures for non-interoperable scalar domains.

Random choices, shuffle order and random-state advancement are part of the
partition contract. Ordinary indexed adjacency remains eligible for the
sparse accumulator path. Custom graph, numeric or random providers that can
observe or mutate later work retain the owned live traversal, including
class-level overrides of random methods.

Edge-data selectors follow the same node-bunch orientation and neighbor
order for string and non-string attribute keys. Literal `True` and `False`
retain their distinct view-shape meanings. A live edge-row iterator projects
each selected value when that edge is yielded, so arithmetic on one weight
can update a later weight in the same row before it is read.

## 57. Live Weighted Distance and Spanning Inputs

Weighted eccentricity preserves authoritative public rows for named as well
as callable weights. An undirected view can expose distinct reciprocal costs
from its directed parent; materializing one undirected edge loses those
costs. Diameter, radius, center and periphery inherit the same per-source
distance semantics. Supplied distance mappings retain their read and error
order without unnecessary input conversion. Backend dispatch recovers the
original source when weighted-query admission requires live rows, including
when an earlier call populated the conversion cache.

Native weighted conversion admission also requires complete node coverage
and reciprocal adjacency identity, including directed successor/predecessor
agreement. Independently assigned rows retain their directional weights,
topology, membership validation and error boundaries. Identity checks follow
the plain-key/type checks and do not compare user attribute values.

Weighted closeness, harmonic centrality and Wiener index obey the same
live-row contract. Directed closeness retains its reference reverse-copy
boundary, while harmonic centrality uses a live reverse view. Closeness
vitality computes each removed-node result through the original graph's
subgraph view; copying that view can collapse reciprocal edge costs or
detach a callback's attributes. Distance callbacks receive the dictionaries
selected by these public graph protocols, and subsequent queries observe
their mutations. Shared shortest-path primitives retain the existing
validation, unreachable-node and exact-arithmetic behavior.

Wiener index consumes the shared weighted shortest-path rows and sums their
reachable distances in source/target iteration order. First discovery at
positive infinity remains a reachable distance, `None` costs hide an edge,
and negative edges follow Dijkstra's actual contradiction boundary rather
than an unconditional sign rejection. Weighted directed graphs can have
valid results containing negative distances when no such contradiction is
encountered.

Spanning-edge queries validate direction, algorithm selection and Boruvka's
multigraph restriction when called. Foreign graphs, subclasses, private
storage and views are consumed by the owned Kruskal, Prim and Boruvka engines
when their iterators advance, without a conversion snapshot. Changes before
first advancement are visible, yielded attribute dictionaries remain the
caller's dictionaries, and later Prim/Boruvka reads observe subsequent
mutations. Kruskal reads and sorts its edge records before its first yield.
Ordinary concrete native storage retains its existing selector routes.

Minimum and maximum spanning-tree wrappers preserve those original rows
before conversion, including backend calls with an existing conversion
cache. Minimum trees copy graph metadata and `nodes.items()` before consuming
the edge selector; maximum trees finish edge selection first. Both preserve
shallow attribute values and validate directed inputs, unknown algorithms
and Boruvka's multigraph restriction before reading metadata. Assigned node,
edge and adjacency providers also prevent a nested edge query from re-entering
a native selector that would ignore those providers.

## 58. Constructor Copies of Authoritative Graph Storage

All graph-to-graph constructors use the source's active logical storage.
Assigned node, adjacency, successor or predecessor mappings and shared view
storage take precedence over any obsolete native graph underneath them.
Native absorb operations require an ordinary concrete source with native
storage; matching source and destination classes alone are insufficient.
The simple-to-undirected-multigraph absorb route also requires edge
attributes that round-trip through its native store. Arbitrary attribute
keys, large integers and nested Python values use public reconstruction so
their types and shallow identity remain intact.

Across all sixteen combinations of `Graph`, `DiGraph`, `MultiGraph` and
`MultiDiGraph`, reconstruction preserves node order, adjacency-row order,
parallel-edge keys and the reference directed/undirected merge rules. A
directed target receives reciprocal arcs in source adjacency order instead
of interleaving reverse arcs while visiting an undirected edge list.

Graph, node and edge attribute dictionaries belong to the new graph while
their nested values retain shallow-copy identity. Explicit constructor
attributes override copied graph attributes. Generic graph reconstruction
uses the established adjacency decoder and preserves the reference error
boundary when public graph providers cannot be converted. Algorithms that
construct an auxiliary graph inherit these storage and copy guarantees.

Adjacency decoding consumes observable mapping providers incrementally. A
custom edge-attribute read can change a later adjacency row, which must be
read after that callback runs. Ordinary dictionary-backed inputs retain bulk
insertion, while custom mapping protocols preserve public read, mutation
and partial-construction error order through the shared decoder.

## 59. Flow Hierarchy Arithmetic and Graph Providers

Flow hierarchy divides the weighted sizes of strongly connected component
subgraphs by the caller's graph size. Graph size follows degree accumulation
order, and component sizes follow each induced subgraph's degree order.
Replacing those operations with one edge-weight fold changes cancellation
and can turn a fully cyclic graph's score from zero into one. Numeric values,
custom size providers and graph views retain the reference operation order
and error boundary. Acceleration requires inputs for which the aggregate
transformation preserves those observable operations.

Unweighted multigraph hierarchy counts every parallel arc in both the
whole graph and each strongly connected component. Replacing keyed arcs
with a simple directed graph changes the proportion of cyclic edges and
is not an admissible native projection.

Filtered and reverse graph views share the public graph-size primitive:
sum weighted node degrees in their iteration order, then divide by two.
Ordinary unweighted edge counts remain integers. Weighted division preserves
the Python numeric result type, including `Decimal` and `Fraction`, without
an intermediate float cast. Both in- and out-degree contributions of a
directed view participate in their public degree order.

## 60. Quotient Graph Aggregation and Source Views

Quotient graph construction reads the caller's graph. Each default block's
`graph` attribute is an induced view of that source, including when the source
is a NetworkX graph, a filtered view or a reverse view. Later source mutations
remain visible through these block views; `nnodes`, `nedges` and `density`
remain the values captured during construction.

The default edge aggregator looks up the supplied weight key literally,
including `None`, zero and the empty string, and uses one only when that key
is absent. Exact integer totals may be bucketed for ordinary native storage.
Floating, exact noninteger and custom numeric values retain the ordered
Python `sum` operation over the block pair's public edge traversal. Scalar
preaggregation must not change cancellation, overflow or callback behavior.

Custom node and edge providers run during result construction, without an
earlier whole-graph attribute read. Node-data mappings may have arbitrary
hashable keys; they are mappings rather than keyword arguments. Backend
dispatch preserves the original source because the result contains live
views and callbacks may mutate edges consumed later in construction.

Block metadata follows the subgraph's public methods: `nnodes` uses `len`,
`nedges` uses `number_of_edges`, and density uses that subgraph's node count,
edge count and direction. A custom subgraph provider must not inherit the
parent graph's direction or substitute its node-count method for `len`.

## 61. Implicit Unit Weights and Exact Shortest Paths

Every missing selected edge weight contributes its integer default, one, to
the native exact-arithmetic admission bound. This applies to native-only
attributes, materialized Python dictionaries, global scans and expanded-row
checks across all four graph classes. Explicit integer magnitudes alone do
not bound a path that also contains default unit weights.

Removing an explicit zero weight invalidates cached admission. Dijkstra,
Bellman-Ford and Johnson retain exact distances and optimal paths across the
`2**53` boundary by selecting the owned Python arithmetic route when needed.
Ordinary integer values inside the bound remain eligible for native kernels.
Johnson backend dispatch preserves source dictionaries for callable weights
and custom graph or numeric providers, including after a cached conversion.

## 62. Owned Structural-Hole Centrality

`constraint`, `local_constraint` and `effective_size` use owned scalar
calculations for weighted, directed, multigraph and observable-provider
inputs. All-node queries retain the distinct sparse matrix behavior when
NumPy and SciPy are available; missing optional dependencies select the
scalar calculation. Eligible ordinary unweighted graphs retain their native
kernels without pre-materializing every requested adjacency row.

Scalar node selections are consumed as supplied, including duplicate nodes
and mutations between iterator yields. Arithmetic reads the caller's live
edge dictionaries without coercing exact numeric values to floating point.
Unweighted effective size preserves the caller's induced ego graph and its
`subgraph`, `copy` and `size` providers. Empty explicit subsets return an
empty mapping. Backend dispatch preserves these same source and mutation
boundaries on both cold calls and calls with a cached native conversion.

## 63. Backend Flow Solvers and Residual Ownership

The five residual solvers (`edmonds_karp`, `dinitz`,
`shortest_augmenting_path`, `preflow_push` and `boykov_kolmogorov`) are also
available through NetworkX backend dispatch. They retain the caller's graph
and optional residual across cold and previously cached conversions, keeping
capacity arithmetic, solver options, validation and residual identity intact.

Backend-dispatched `maximum_flow`, `maximum_flow_value`, `minimum_cut` and
`minimum_cut_value` preserve the original `flowG` when a solver or solver
arguments are supplied. Positional and keyword graph arguments have the
same identity and mutation contract. A cached native conversion must not
substitute its graph for the caller's graph or copy a supplied residual.

Solver mutations remain visible to flow-dictionary construction, cut
partition extraction and later queries. Conversion caches are cleared
around callbacks, including failure, so direct attribute writes cannot
leave a stale capacity graph for subsequent native calls. An explicitly
supplied native graph remains an independent input even if it originated
from an earlier conversion.

Default-solver calls admit native conversion only after inspecting the
original graph's storage and capacity-reader protocols. Views, assigned
logical rows, custom attribute readers and observable capacity selectors
retain the original graph through residual construction. Admission must not
invoke a custom reader or attribute-key comparison before the solver would
read it. A held edge dictionary changed through a base `dict` method must
affect the next flow or cut query even if an earlier query cached a view's
materialization. Ordinary concrete storage with builtin readers retains its
native conversion and solver route.

## 64. Community Detection Through Backend Dispatch

The owned semi-synchronous, asynchronous and fast label-propagation APIs,
Girvan-Newman, clique percolation, Kernighan-Lin bisection and asynchronous
fluid communities are available through NetworkX backend dispatch.

Asynchronous and fast label propagation, Girvan-Newman and clique
percolation keep their original graph until iteration starts. Source edits
after iterator construction, live views, random-source hooks, clique
providers and working-graph copy hooks retain their direct-call behavior.
Seed validation remains at the public call boundary where specified.

Conversion caches are invalidated around lazy provider execution, including
advancement, close and failure. A later native query must observe attribute
writes made by random or graph callbacks. Eager community algorithms keep
their eager computation boundary. Semi-synchronous label propagation keeps
the original graph through backend dispatch, including warm conversion caches,
and admits an ordinary native snapshot at its own algorithm boundary.

Semi-synchronous label propagation finishes largest-first coloring before
initializing labels or capturing propagation rows. Degree providers may change
the graph during coloring; subsequent completion checks and label updates read
the resulting live adjacency. Color classes retain their set iteration order,
isolated nodes retain their labels, and ties use the Prec-Max rule. Assigned
private rows, graph views, custom labels and graph readers use the owned live
solver. Ordinary callback-free native graphs with the canonical largest-first
coloring strategy retain the index-space solver. Custom coloring strategies may
invalidate color-class independence and must preserve live set-ordered updates.
The returned values view contains the completed partition: edits after the
call returns cannot change it. Coloring errors propagate before propagation
reads, with the same exception type through backend dispatch.

## 65. Weighted Query Dispatch and Live Source Collections

Backend dispatch includes all three multi-source Dijkstra variants,
`dijkstra_predecessor_and_distance` and `bidirectional_dijkstra`. Callable
weights retain the original edge or parallel-edge dictionaries, may hide
edges by returning `None`, and may update edges read by subsequent steps.
Literal nonstring selectors and cutoffs with Python numeric protocols retain
the owned search's public operation order and numeric types.

Multi-source variants retain the caller's graph when sources is a user
iterable or contains labels with Python protocols. Admission does not
consume that iterable or invoke its truth protocol. Source truth testing,
validation, membership, path-root initialization and traversal seeding follow
the reference consumption steps, including exhausted one-shot iterators.
Changes made while supplying sources affect subsequent validation and
traversal, on direct calls and cold or cached backend calls alike.

Exact reusable collections of ordinary labels remain eligible for native
searches. Length-only queries retain their distance-only engine. Conversion
caches are invalidated after observable source or weight providers run,
including failures, so later ordinary native queries see their writes.

Dijkstra, Bellman-Ford, A* and generic weighted-path backend calls apply this
admission before even a cold conversion. Restoring the original graph only
after conversion is too late for observable attribute providers. Numeric and
selector providers invalidate conversions just as callable weights do, on
success and error alike.

## 66. Incremental Multigraph Spanning Trees

`SpanningTreeIterator` snapshots the input graph at construction and enumerates
spanning trees in nondecreasing or nonincreasing cost. Parallel edges are
distinct alternatives identified by `(u, v, key)`. Each emitted tree retains
its selected keys, graph/node/edge attributes and the native graph family;
partition bookkeeping must not escape in returned attributes or modify the
caller's graph. Self-loops never participate in a spanning tree.

Enumeration maintains a frontier of disjoint included/excluded/open edge
partitions. Requesting a prefix selects only the partitions needed for that
prefix; it must not enumerate the full tree space first. The existing owned
Kruskal selector handles multigraph constraints and the existing native
selector remains available for eligible simple graphs. Equal-cost ties may
be emitted in arbitrary order, as documented by NetworkX. Empty, singleton
and disconnected inputs retain the reference initial-forest behavior, and
the NaN rejection/ignore policy applies to every parallel edge.

## 67. Owned Greedy Modularity Communities

Greedy modularity retains the native merge kernel for its admitted primitive
domain. Other labels, numeric values, edge selectors and graph providers use
an owned sparse CNM solver over the original graph. Its degree products,
parallel-edge gains, self-loop accounting and merge priorities preserve
Python arithmetic and caller-defined node comparisons. Indexed row heaps
retain one live entry per adjacent community pair, including for nonfinite
priorities; stale duplicate heap entries must not alter comparisons.

The solver absorbs the first selected community into the second and retains
the reference frozenset construction and final size-sort order. `cutoff` and
`best_n` preserve their validation and stopping boundaries; after adjacent
merge candidates are exhausted, required remaining merges consume the largest
communities in reference order. Directed non-string selectors use indexed
directional degree reads rather than a native iterator restricted to strings.

Views, custom edge dictionaries and graph-instance providers are not consumed
by speculative native admission or graph conversion. Direct and backend calls,
including calls with cached conversions, retain the original providers and
invalidate conversions after those providers run. Ordinary primitive graphs
continue to use the existing native merge kernel.

## 68. Floyd-Warshall Numeric and Provider Domains

The dictionary distance and predecessor APIs consume the original graph.
Custom graph views, attribute readers and numeric subclasses retain their
Python traversal, comparison and addition behavior, including scalar result
types and arithmetic exceptions. Converting an `int` or `float` subclass to
a matrix scalar is not admissible merely because `isinstance` succeeds.

The existing vectorized distance route remains available for ordinary simple
graphs with exact builtin scalar weights, its existing integer magnitude
bound and ordinary cached views. Admission must not invoke custom descriptors
or consume instance-level edge, node or direction providers. Owned slot-only
edge mirrors with builtin reads remain eligible; dictionary classes allowing
instance read-method shadows use the owned dictionary route. Eligibility is
rechecked on each query, with read-class inspection shared within that query.

Backend calls retain the same original-graph boundary, including after an
earlier call cached a native conversion. Matrix negative-cycle and nonfinite
fallback behavior remains governed by the ordered dictionary solver.

## 69. PageRank Matrix and Provider Boundaries

PageRank captures its sparse matrix from the caller's visible graph before
consuming `nstart`, `personalization`, `dangling` and the iteration-count
protocol. The generic route validates the node bunch, reads edge values,
consults directedness and separately rereads undirected self-loop values for
their correction. Observable reads and failures retain this order; an empty
graph returns its empty result before iteration-count validation.

Sparse weight selection honors a literal `None` attribute key when present,
as well as other hashable selectors. Native unit-weight producers remain
available when that key is absent, including parallel-edge inputs. Views
read their visible attribute dictionaries, and assigned parent adjacency
must not be bypassed by a filtered view's native-row optimization.

Native ordinary matrix/cache routes remain available. Custom graph, edge,
vector and scalar providers select the owned matrix and power-iteration path.
Backend dispatch recognizes that provider route before additional weighted
admission probes, so an early direction callback cannot mutate the graph
before its intended edge snapshot. Both successful and failing provider calls
invalidate conversion caches before subsequent ordinary queries.

`pagerank_many` preserves the ordered semantics of repeated single-query
PageRank calls. Query iterators advance only after the previous solve completes;
mapping, numeric and graph-provider callbacks run on the caller's original
graph, and their mutations affect later snapshots. The first failing query
leaves later iterator elements unread. Empty batches do not inspect the graph
or algorithm parameters. Plain numeric lists and tuples on ordinary native
graphs share the single-query transition-matrix producer and power iteration,
including its cache invalidation and literal weight-key rules. Each worker owns
its rank vector and results retain query order. Default, personalized and batch
queries all use the reference's ordered dangling-rank sum, including on graphs
with many sinks or isolated nodes.

`google_matrix` captures the dense adjacency and validates its node selection
before checking graph emptiness or reading personalization and dangling
providers. Its default vector uses the whole graph's node count. Explicit
personalization rejects exactly zero total; signed and nonfinite values
otherwise retain NumPy normalization semantics. Explicit dangling vectors
are normalized even when there are no dangling rows, without replacement by a
default distribution. Dangling rows are replaced before final row normalization,
preserving floating-point rounding, shape errors for partial selections and
configured NumPy floating-point exceptions. Provider mutations affect the source
graph after the matrix snapshot and do not change that snapshot.

## 70. DataFrame Export from Authoritative Graph Storage

`to_pandas_edgelist` exports the graph's visible edges and attribute dictionaries,
including when a concrete Graph or DiGraph has assigned logical adjacency,
shared storage, or storage installed by a general deep copy. A prior native
export must not make its old edges or attributes authoritative after that
replacement. Empty logical storage produces an empty edge table even if the
native store still contains edges.

Ordinary concrete graphs retain the native bulk exporter. Graphs with logical
storage use their public edge view, preserving edge order, selected column
names, nested attribute identity, and subsequent mutations of held rows.

Attributed `from_pandas_edgelist` imports commit each row before advancing an
observable table or column iterator. The edge exists before its attributes are
updated, including duplicate-edge merges and failures during an attribute
update. Later input failures retain the completed prefix in `create_using`.
Graph mutation hooks, custom object values and custom extension arrays retain
this incremental path. Ordinary scalar DataFrame columns on unmodified native
graphs can still use bulk insertion when inspecting them cannot invoke input
providers or lose attribute values.

## 71. Owned Greedy Coloring and Strategy Protocols

`greedy_color` returns an empty dictionary for an empty graph before resolving
the strategy. Nonempty inputs resolve named strategies through the owned
strategy registry and validate callable strategies with the reference hashing
and error behavior. A custom strategy receives the original graph and the
same mutable color dictionary that the ordinary driver returns. Generator
strategies resume after each yielded node has been colored from its currently
visible neighbors. Graph metadata, graph mutations, custom adjacency reads
and callback failures remain observable at those boundaries.

All named strategies use the existing owned ordering implementations.
Directed ordinary coloring reads successors while degree-based strategies
retain their total-degree ordering. Parallel edges contribute to degree
ordering without becoming separate neighbor colors. Eligible ordinary native
graphs may retain the existing native largest-first and connected-ordering
routes only when those routes preserve the public strategy contract.

Backend dispatch preserves the original graph for strategy execution, including
after a prior call cached a native conversion. Successful and failing callbacks
invalidate conversion caches so subsequent native queries see their mutations.
Explicitly supplied native graphs remain independent of earlier source graphs.

Color interchange snapshots graph nodes and undirected edge incidences after
the strategy is called but before its iterator is advanced. Its strategy color
dictionary remains separate from the engine's assignments. When a new color
would otherwise be needed, candidate color pairs are tried in ascending order;
the two-color components reached from lower-color neighbors may be swapped
only when no higher-color neighbor is reached. The result retains the initial
node order, with unvisited strategy nodes reported as `-1`. Directed and
parallel edges participate as undirected incidences in this engine. Independent
set and saturation strategies reject interchange before strategy execution.

## 72. Incremental Directed Arborescence Scheduling

`ArborescenceIterator` snapshots its input at construction. For directed
graphs, iteration owns a priority frontier of included/excluded/open edge
partitions and uses the existing minimum/maximum arborescence selectors. Each
new partition excludes one open edge of the selected tree while including the
preceding open edges, so requesting a prefix only explores the necessary
frontier. Equal-cost ties have arbitrary order.

An included incoming edge excludes every other incoming edge at that node
before selection, including when a later Edmonds contraction would otherwise
make the alternatives eligible. Initial included/excluded iterables are
captured at construction, with exclusions taking precedence. The initial
infeasible partition raises the reference exception; infeasible child
partitions contribute no candidate. The existing selector's weight transforms
and edge-attribute behavior remain in force. Partition markers are removed
from returned native trees and never reach the caller's original graph.

Empty and undirected graphs retain their iteration-time errors. Starting a
new iteration before exhaustion resets the frontier; advancing before starting
or after exhausted state has been released retains the established state
errors.

For MultiDiGraph, each `(u, v, key)` is a distinct alternative. The owned
frontier yields each feasible keyed tree once, preserving original keys and
edge attributes. It retains the selected tree for each pending partition and
ranks it by an exact sum of its weights, without converting large integers or
exact numeric objects to floating point. The existing selectors retain their
native admission and numerical fallback rules. Internal edge-identity and
partition markers use unused attribute names and are removed from snapshots
and results, preserving colliding user attributes.

Multigraph initial partitions accept keyed triples. Endpoint pairs are accepted
only when they identify at most one key; ambiguous parallel pairs raise
`ValueError` requesting a triple. Missing included keys, multiple included
parents, and included cycles make the initial partition infeasible. Initial
exclusions continue to take precedence. This is an explicit functionality
extension over NetworkX 3.6.1, whose multigraph iterator can duplicate its best
parallel edge, omit other keyed trees, and ignore keyed initial constraints.
Small independent exhaustive edge-subset oracles define complete keyed output
and cost ordering; the faulty reference iterator does not define these cases.

## 73. Streaming Dictionary-of-Lists Imports

`from_dict_of_lists` completes each edge insertion before advancing a lazy
neighbor iterator or an observable mapping provider. Provider failures and
invalid neighbors leave the already imported prefix intact. An overridden
`add_edges_from` receives one live edge generator and retains control over
its consumption. The ordinary simple-graph path continues to bypass an
overridden `add_edge`, matching the public bulk-insertion contract.

Plain built-in mappings and neighbor containers retain native bulk insertion
when their node keys, graph storage and attribute factories permit it. This
admission does not consume custom iterators or subclasses speculatively.

## 74. Harmonic Centrality Selector Boundaries

Harmonic centrality resolves target nodes before source nodes on the caller's
original graph when selections can expose live providers. Lazy selectors may
change topology or node membership before distance queries begin. The result
retains its selected target keys, default sources observe the correct graph
state, and an admitted source removed by a later selector retains its source
error. A transposed distance traversal must preserve the same boundaries.

Backend calls with explicit target or source selections preserve the original
graph even after a previous call populated the conversion cache. Ordinary
owned graphs retain their admitted native centrality routes.

## 75. Negative-Weight Predecessor Queries

`bellman_ford_predecessor_and_distance` and `goldberg_radzik` are available
through explicit backend dispatch. Original graphs, live weight callbacks,
target and heuristic arguments, predecessor maps and source/negative-cycle
errors retain their public behavior. Successful and failing provider calls
invalidate previously cached conversions.

Goldberg-Radzik uses its existing owned live relaxation engine for observable
graph, attribute and numeric providers. Repeated edge reads remain live, and
unreachable rows are not evaluated by speculative numeric admission. The
existing snapshot engine remains available for concrete simple graphs with
ordinary storage, plain attribute reads and exact built-in scalar weights.
Admission inspects scalar types without coercing custom numbers.

## 76. Weighted Query Validation and Average-Distance Dispatch

Goldberg-Radzik and Bellman-Ford predecessor/distance queries validate source
membership once at their public boundary, before weight reads. Their internal
engines do not repeat that observable membership operation. Snapshot admission
rejects graph-method and graph-view overrides without invoking those readers.

Average shortest-path length accepts the same explicit method choices through
backend dispatch as through direct calls. Method validation, graph-connectivity
requirements, callable-weight behavior and exceptional cases belong to the
owned public algorithm rather than a blanket backend method rejection.
An explicitly selected weighted method treats `None` as an edge-attribute key;
only default method selection interprets an absent weight as unweighted.
The Dijkstra, Bellman-Ford and dictionary Floyd-Warshall routes retain Python
numeric arithmetic through accumulation and the final division, including
rational, decimal and large integer values. The NumPy matrix route retains
the reference's numeric conversion behavior.

## 77. Checked Group Betweenness Path Counts

The native unweighted group-betweenness route checks every shortest-path
multiplicity accumulation and its normalization product. A count outside the
native integer domain produces an explicit unavailable result, never a wrapped
count, a non-finite centrality, or a partially accumulated score.

The public algorithm then recomputes the complete requested group result with
its existing owned preprocessing and inclusion-exclusion implementation. This
includes requests where an earlier group already completed natively. Normalized
and unnormalized results retain the reference arithmetic and group semantics.
Ordinary graphs with representable counts retain their native route regardless
of node count; graph size alone is not an overflow criterion.

Small-group queries accept foreign NetworkX graphs and live graph views as
well as native graphs. Admit concrete native storage only after validating the
groups; custom graph and weight providers retain the original graph through
the owned Brandes traversal. A weighted Brandes callback returning `None`
raises its arithmetic error rather than silently hiding an edge.

Group closeness first takes the directed reverse-copy boundary when required,
captures the graph's node set, and consumes the group into a set once. It
validates membership and then traverses from that group, retaining live weight
dictionaries and their mutations on the selected graph. Its `weight=None` is
a literal Dijkstra attribute selector, so an edge attribute keyed by `None`
contributes its value. Empty source groups raise `ValueError`, including on an
empty graph. A full group still performs traversal before returning zero, so
weight callbacks and their errors remain visible. Distance accumulation starts
from integer zero and preserves the arithmetic of exact numeric weight types.

Explicit backend calls support group betweenness and group closeness. They
retain the caller's original graph and group providers before conversion and
clear conversion caches after successful or failing provider execution.
Custom group iterables bypass speculative native size probes that would
consume them before the owned algorithm's preprocessing boundary.

## 78. Live Attribute Protocols During Graph Conversion

Copy-producing `to_directed` and `to_undirected` operations for all four graph
families execute user deepcopy protocols outside a native source borrow.
Copy graph metadata before node dictionaries, then traverse live private
adjacency. Earlier callbacks can change later attributes, rows and reciprocal
membership. Resizing an active node iterator retains its iterator error, and
copy exceptions propagate unchanged after any completed source writes.

Each attribute dictionary has an independent deepcopy memo. Preserve aliases
within that dictionary, arbitrary mapping keys, and key and value copy
protocols. Filtered, conversion and reverse views copy their visible logical
node attributes. Public node, edge and graph-kind overrides do not replace the
logical private stores or the family's default conversion class.

Ordinary builtin data retains eligible native conversion routes. Concrete
results retain source compatibility mode and fresh decision history; copy
callbacks observe the ambient compatibility mode. The `as_view=True` sharing
and freezing contract remains unchanged.

## 79. Structural Iterator Dispatch and Bridge Spans

Backend calls for `find_cliques`, `enumerate_all_cliques`, `all_triangles`,
`simple_cycles`, `antichains`, `all_simple_edge_paths`, `bridges` and
`local_bridges` retain the caller's original graph, including when an earlier
algorithm populated the conversion cache. Each algorithm owns its existing
snapshot point. Changes before first advancement remain visible, and failures
inside iterator bodies retain their deferred timing. The owned edge-path
iterator is available through explicit backend dispatch.

Native maximal-clique searches ignore self-loops when building their open
neighborhoods. Loops must not remove a clique, change clique counts or per-node
clique sizes, or change the derived clique graph and clique-percolation
communities. Inputs retain their original nodes and loops, and complexity
witnesses still count scanned loop entries.

`eulerian_circuit` and `eulerian_path` also retain the original graph until
first advancement, including after a prior algorithm cached a conversion.
Topology changes before that boundary affect the traversal and its Eulerian
validation. The owned working copy is then fixed: source changes after the
first yielded edge do not alter the remaining traversal. This applies to all
four graph families, with keyed and unkeyed output.

`simple_cycles` keeps the original adjacency live through self-loop and
undirected parallel-edge yields. Edge mutations and mutable filter changes
between these yields remain visible before construction of the owned simple
graph used for longer-cycle search. Once that structural copy exists, later
source mutations do not alter its remaining cycles. Bound validation precedes
graph access, and backend dispatch retains the same suspension boundaries.

Bridge classification starts at first advancement. Unrestricted simple graphs
retain a live edge walk after classification; a root-restricted component or
multigraph projection retains its established snapshot behavior. Parallel-edge
checks continue to read the original multigraph as results are yielded.

Local bridge spans are enabled only by literal `True`. Common-neighbor tests
include endpoint self-loops. The shared weighted shortest-path engine hides
the candidate edge while preserving exact Python arithmetic, hidden edges,
arbitrary attribute keys including `None`, and callback dictionary identity,
mutations and exceptions. Callback-driven backend iterators invalidate cached
conversions around each advancement and close.

## 80. Node-Link Round Trips and Metadata Aliases

Node-link field uniqueness applies to the edge source, target and effective
multigraph key. Node identifier fields have their own scope and may reuse an
edge field name. The effective key is `None` for simple graphs, preserving
the reference validation for `None` source or target selectors.

Export reads the graph's public node and edge providers in their observable
order. Both export and import retain the graph metadata object itself,
including non-dictionary metadata. Node and edge attribute dictionaries are
independent shallow copies, with nested values shared; decoding converts
attribute names to strings and reconstructs tuple labels and keyed edges.

Ordinary scalar JSON lists retain bulk insertion. Custom node labels, field
keys, mappings or iterators are decoded and inserted incrementally so their
callbacks can affect later records. The decoder does not consume those
providers merely to select a fast path.

Adjacency-format JSON decoding observes the same incremental boundary for
custom node labels, mappings and record iterators. It copies and removes the
identifier field of each node or edge record immediately before inserting that
record; callbacks from insertion can therefore change records not yet read.
Ordinary scalar lists retain bulk insertion, while nested attributes retain
shallow identity and literal attribute keys are not stringified. Invalid
identifiers and excess adjacency rows keep the first offending record's
reference exception instead of surfacing a later buffering failure first.

Copies of graphs with logical metadata aliases own a fresh metadata dictionary
and retain its shallow values. Native copies restore plain metadata aliases;
custom metadata providers run before topology is copied. Subsequent JSON,
GML and GraphML exports observe metadata changes made through the original
node-link payload, including after a graph copy.

All four graph constructors read the logical metadata when converting an
imported graph, preserve shallow values and apply explicit constructor
attributes afterward. Metadata providers run before the topology is copied.
Minimum and maximum spanning trees retain that metadata. Minimum trees read
custom metadata providers before edge selection; maximum trees read them
after selection, matching the distinct reference boundaries. Native GML admission rejects logical
metadata aliases so plain integer-node graphs cannot silently lose metadata.

## 81. Weighted Degree Connectivity and Backend Inputs

`average_degree_connectivity` buckets results by unweighted source degree and
uses unweighted target-degree coefficients. Weighted numerators and source
strengths preserve Python numeric domains, including Decimal, Fraction and
arbitrarily large integers. Empty degree buckets retain integer zero.

Reductions follow per-row Python summation order. Undirected self-loops are
added a second time after the complete row sum; directed outgoing and incoming
strengths are summed separately. A directed `source="in"` walks predecessor
insertion order, while `source="out"` and `source="in+out"` use successors for
the numerator. Multigraph strengths flatten parallel-edge weights into those
same directional reductions.

Logical views retain their endpoint-specific weights. Node selectors preserve
nbunch validation, scalar-node handling, duplicates and custom-provider
identity. Neighbor selections are resolved before edge arithmetic, and later
numeric callbacks are followed by fresh degree and row reads, retaining the
reference failure behavior for graph mutations.

Plain builtin Graph and DiGraph inputs retain bulk native extraction and
cached backend conversion. Views and observable graph, degree, neighbor,
mapping, selector or numeric providers execute on the original graph, even
when another backend call already populated the conversion cache. Admission
does not invoke custom providers or numeric protocols.

Weighted `average_neighbor_degree` reads retained edge-attribute dictionaries
on every call before an admitted native reduction. Its numerator uses
unweighted target degrees and its denominator uses source strength; directed
incoming and outgoing terms retain their distinct rows. Views preserve
endpoint-specific attributes instead of collapsing them into one undirected
edge. Nonfinite weights, potentially overflowing intermediates, and unsupported
numeric domains keep the owned Python arithmetic. Observable graph, degree,
mapping and node-selector providers retain the original graph through backend
dispatch, with cached conversions invalidated after provider execution and
exceptions.

## 82. Core Decomposition Backend Availability

Explicit backend dispatch advertises and executes `k_core`, `k_shell`,
`k_crust`, `k_corona`, `k_truss` and `onion_layers`, alongside `core_number`.
Runtime and package metadata derive these names from the same owned registry.

Core subgraphs retain directed support, supplied core-number maps, thresholds
and existing default/empty-graph behavior. Returned graphs own their structure
and attribute dictionaries while preserving shallow attribute values. Prior
structure-only conversions cannot discard the attributes requested by a
subsequent graph-returning decomposition.

The owned core family preserves documented `NetworkXNotImplemented` errors
for unsupported graph types and self-loops through backend dispatch. Other
algorithms retain their existing backend fallback policy.

## 83. Bipartite Matching Backend Availability and Live Inputs

The backend advertises `hopcroft_karp_matching`, `eppstein_matching`,
`to_vertex_cover` and `minimum_weight_full_matching`. NetworkX's
`maximum_matching` alias dispatches under `hopcroft_karp_matching`.
Explicit and automatic backend selection use the same owned implementations.

Partition iterables are consumed once at the algorithm's normal boundary.
Their graph mutations, matching-map iteration and weight-provider reads remain
attached to the original graph, including views and calls after a conversion
cache was populated. Matching results preserve reference dictionary order,
node representations and exception contracts for invalid or ambiguous
partitions. Hopcroft-Karp reads adjacency without invoking unrelated public
edge providers.

Ordinary concrete graph storage with plain, valid partitions retains the native
Hopcroft-Karp kernel. Native admission does not consume custom or one-shot
selectors, flatten assigned adjacency or substitute canonical labels for
boolean/float aliases or signed zero. Other inputs run the owned Python
matching implementation over their live rows.

The native Hopcroft-Karp search uses an explicit, reusable path stack so long
alternating paths do not exhaust the process call stack. It retains partition
and neighbor iteration order, failed-branch pruning and reverse path rematching,
including the exact matching and result order produced by recursive traversal.

## 84. Global Minimum Cut Backend Availability and Weight Reads

`stoer_wagner` is available through explicit and automatic backend dispatch.
The backend preserves the original graph so an earlier conversion cannot
consume observable weight providers or substitute stale cached attributes.
Unsupported directed and multigraph inputs retain `NetworkXNotImplemented`.
Connectivity walks the caller's private adjacency without converting the
graph or invoking an unrelated public node provider. Changes made by a row
provider remain visible to the subsequent weight snapshot.

The owned contraction implementation snapshots each visible non-loop edge
weight once, then validates the copied weights and runs the selected heap.
Custom attribute mappings are not read by a preliminary negative-weight scan
or by native admission. Their read order, mutations and exceptions remain
observable at the reference algorithm's snapshot boundary. A custom heap
can mutate the caller's graph without changing the weights already copied
for the cut computation.
An explicit `heap=None` retains the reference construction error after graph
and negative-weight validation; omitting the argument selects the default
binary heap.

Exact cut values, numeric types and the reference partition order are
preserved, including arbitrary-size integers, Fraction and Decimal weights.
Ordinary native Graph inputs with builtin attribute storage and supported
numeric weights retain the native contraction route. Assigned adjacency,
observable public providers and custom weight selectors use the owned Python
implementation without speculative provider reads.

For all four graph families, unrestricted edge iteration over assigned private
adjacency consumes the mapping's items directly. Supplying a node selection
retains explicit row lookups, provider exceptions, missing-scalar errors and
missing-list filtering. This keeps the global-cut snapshot from re-reading
adjacency providers already used to establish connectivity.

## 85. Live Collider and V-Structure Iteration

`colliders` and `v_structures` reject undirected graphs immediately, but read
nodes and predecessor rows only when their iterators advance. Each node's
parent combinations are fixed when that node is reached; later predecessor
rows and v-structure adjacency checks remain live. The original public node
iterator stays active, preserving its ordering and graph-mutation errors.

Ordinary native directed graphs retain one bulk predecessor read. Admission
uses exact provider and primitive label types without calling user hash or
equality protocols. The saved rows are reused only while the graph revision,
predecessor provider and logical storage remain unchanged. At the next node
after invalidation, traversal continues over public predecessor rows. Views,
assigned storage and custom graph or node providers use that live traversal
from the start, without materializing a graph snapshot.

## 86. DAG Transitive Closure Copy and Ordering

`transitive_closure_dag` validates directedness first. Without a supplied
topological order, it resolves that order against the original graph before
calling its `copy()` method. The returned copy retains the provider's class,
visible graph state and shallow attribute identities.

Supplied orders are reversed after copying, without first consuming their
forward iterator. A one-shot iterator therefore raises its reversibility error
after the copy exists. Each reversed node reads distance-two descendants from
the current working copy and immediately inserts the resulting edges. Changes
made by ordering, adjacency or mutation providers remain visible to later
nodes. An invalid later node leaves already completed closure additions in a
copy retained by its provider.

Ordinary concrete DiGraph copies with passive orders, plain node labels and
unmodified graph protocols retain bulk native adjacency reads and one final
edge batch. Other inputs use the owned live traversal. Explicit backend
dispatch preserves the original input and its copy protocol even after an
earlier algorithm populated the conversion cache.

## 87. Bipartite Projection Backend Availability and Metadata

The backend exposes `projected_graph`, `weighted_projected_graph`,
`collaboration_weighted_projected_graph`,
`generic_weighted_projected_graph` and `overlap_weighted_projected_graph`.
Calls bind the public graph parameter `B`, including keyword arguments.
The owned implementations retain directed projections, keyed multigraph
outputs, ratio weights, collaboration weights and both overlap conventions.

Projection reads the original input graph even after another algorithm has
populated its conversion cache. Graph and node metadata, live filtered views
and custom weight callbacks must therefore see the caller's current state.
Custom weighting receives that same graph object with its edge attributes
and preserves the callback's exact numeric result. Callback mutations remain
visible to later backend calls.

Result graph and node attributes are shallow copies: nested values retain
their identities, and node attribute keys need not be strings. Simple and
multigraph projection output both copy node mappings without expanding them
as keyword arguments. Regressions are in
`tests/python/test_bipartite_projection_backend.py`.

## 88. Graph Resilience Backend Contract

Explicit NetworkX backend dispatch supports `is_k_edge_connected`,
`k_edge_components`, `k_edge_subgraphs`, `k_edge_augmentation`, `k_components`
and `all_node_cuts` through the owned implementations. Original-input recovery
survives an earlier cached conversion. Low-k component/subgraph iteration and
node-cut enumeration retain the caller's graph until advancement; higher-k
component auxiliary construction retains its eager snapshot. Backend edge
augmentation exposes a lazy generator. Supplied flow solvers and augmentation
candidates observe the original graph state and invalidate affected conversion
caches. Node-cut verification must retain the input graph's implementation
family when constructing a graph with the cut vertices removed.

Constrained `k=1` augmentation contracts the original connected components
and retains the lightest original edge per unordered component pair. The
reference `(weight, u, v)` tie-break applies only within that pair. A stable
cost-ordered minimum spanning forest over component IDs preserves exact
Python costs, original endpoint identities and orientations, and quotient
forest edge order. Mixed labels on different component links need not be
orderable. Complete augmentation raises `NetworkXUnfeasible` when candidates
cannot connect the quotient; partial augmentation returns the minimum-cost
forest without redundant candidates. Neither mode mutates the input graph.
`tests/python/test_k_edge_augmentation_parity.py` checks these contracts
against NetworkX through direct and backend entry points.

Constrained `k=2` augmentation uses the reference weighted bridge reduction.
Disconnected inputs first receive the weighted `k=1` connectors. Contract
bridge-connected components of that connected graph, retain the lightest
original candidate per unordered component pair, and root the quotient tree
at its first leaf. Its reversed tree arcs have zero cost. Candidate links
generate downward arcs from their lowest common ancestor, in the reference
LCA emission order, carrying the original link and its Python cost. Remove
incoming arcs at the root and find a minimum spanning arborescence through
the existing branching implementation. Emit the initial connectors followed
by the distinct selected original generators in reference set order. This
is weighted approximation, with the branching implementation's numeric and
tie semantics; it does not accumulate redundant links using local flow tests.

If complete constrained `k=2` augmentation is infeasible and `partial=True`,
add the available edges to a private graph, identify its bridge-connected
blocks, and augment each feasible block independently. Keep the available
links crossing different blocks. Partial results must respect the candidate
set even when the input has fewer than three nodes. Preserve reference
candidate unpacking and error order, including the partial fallback's raw
pair iteration and its errors for weighted triples. Complete and partial
paths leave the original graph and its attributes unchanged.

For higher `k`, infeasible constrained partial augmentation uses the same
block strategy with `k_edge_subgraphs` of the maximally augmented private
graph. Each non-singleton block receives the existing deterministic greedy
augmentation for that `k`; only the selected internal candidates are emitted,
followed by every available link crossing blocks. Traverse blocks in the
existing `k_edge_subgraphs` order and retain reference edge and neighbor-set
iteration within each block or block pair, exact Python costs, original
endpoint objects, and the raw-pair fallback errors. The candidate restriction also
applies when there are fewer than `k + 1` nodes or no available edges. The
original graph and attributes remain unchanged, and the complete higher-k
augmentation policy is unchanged.

## 89. Owned Leiden Community Detection Contract

This implementation contract derives from Traag, Waltman and van Eck,
"From Louvain to Leiden: guaranteeing well-connected communities" (2019),
Appendix A, algorithm A.2: https://arxiv.org/abs/1810.08473.
The existing public signatures retain the NetworkX 3.6.1 modularity contract;
the later NetworkX 3.7 CPM default is not adopted. Implement the algorithm in
an owned Python helper behind `community.py`, without a new runtime dependency
or delegation to another community detector.

Accept undirected Graph/MultiGraph inputs with finite nonnegative edge weights
and finite positive resolution, interpreted with checked floating-point
arithmetic. A missing weight attribute defaults to one;
`weight=None` counts every edge once. Sum parallel edges and retain self-loops.
Reject directed inputs before resolving the RNG, matching the existing wrapper
order. Empty or zero-total-weight inputs yield one singleton partition (an empty
list for an empty graph); the zero-total rule is an explicit defined extension.
Reject nonfinite accumulated arithmetic instead of optimizing an invalid score.

Let m count each weighted edge once, including loops; k(u) counts loop weight
twice. For disjoint sets A and B, define D(A,B) = w(A,B) - resolution *
K(A)*K(B)/(2m), where K sums original weighted degrees. Merging changes
modularity by D(A,B)/m. Moving u from A to B changes it by
[D({u},B)-D({u},A-{u})]/m. Aggregation must preserve m, all degree sums and
internal edge mass in aggregate self-loops.

The fast local move phase starts with a randomized queue. Consider adjacent
communities and a new singleton destination, move only for a strictly positive
best gain, and prefer staying on ties. Requeue unqueued neighbors outside the
destination after a move. A new singleton destination is essential for splitting
coarse communities inherited from an earlier aggregation.

Refinement restarts with singleton current nodes inside each coarse community
S. Only still-singleton u with D({u},S-{u}) >= 0 is eligible. Candidate refined
blocks C remain inside S, share an edge with u, satisfy D(C,S-C) >= 0 and admit
D({u},C) >= 0; staying is a zero-gain candidate. Choose randomly with probabilities proportional to
exp(D/0.01), using subtract-max normalization. Re-evaluate a block's eligibility
after it grows. This phase must remain randomized rather than choosing only
the best merge.

Build the next graph from REFINED blocks, and initialize its communities from
the COARSE partition that contains those blocks. Keep each aggregate node's
original-node membership. Stop when local moving leaves singleton communities
on the current aggregate graph; a stalled coarse score alone is insufficient.
If randomized refinement makes no contraction, retry the local/refinement
step rather than falsely reporting convergence. After 64 consecutive passes
without contraction, raise `NetworkXError("Leiden refinement made no progress
after 64 attempts")`; reset the counter after a real contraction. This is an
explicit failure, never a convergence result or a forced greedy repair. It
bounds pathological random providers, including a constant draw that always
selects staying. When each pass has an admissible merge and draws are uniform,
the probability of 64 all-stay passes is at most 2**-64.

Public partition levels are copied original-node sets after successful refined
contractions. This explicit projection of the internal algorithm makes levels
nested, connected and nondecreasing in modularity relative to the preceding
refined level; it does not promise the same random partition as another Leiden
implementation. Yield the singleton partition once when no contraction occurs,
and do not duplicate the terminal level. `max_level` limits consumed public
levels and must be positive or None, with the established islice validation.
Resolve the RNG at API invocation, snapshot the graph only on first iterator
advancement, and isolate later graph mutations and edits to yielded sets.

## 90. Public-Row Source Distances and Distance Centrality

`single_source_shortest_path_length` traverses the supplied graph's current
successor/adjacency rows in BFS discovery order. Graph subclasses, filtered
views and assigned mappings may expose asymmetric rows even when the graph
reports itself undirected. Reconstructing edges into a simple undirected graph
would add reverse reachability that is not present in those rows. Foreign
graphs and nonconcrete/private native graphs therefore use owned row traversal;
ordinary concrete native graphs and eligible native reverse views retain their
existing native routes. Missing-source validation precedes adjacency access.
The traversal reads `len(G._adj)` once and retains its established per-level
cutoff and all-nodes-discovered early termination boundaries.

`predecessor` retains the same original row traversal and appends every parent
that reaches a node at its shortest BFS level. Native indexing is reserved for
ordinary concrete storage and built-in cutoff values. Custom cutoff objects
are neither converted to integers nor evaluated before traversal: each complete
level evaluates the option's truthiness and then its `cutoff <= level`
comparison. A falsy zero cutoff is unbounded; a negative cutoff still permits
the first BFS level. Target-specific return forms and unreachable-target
sentinels follow the same completed traversal.

`closeness_centrality` preserves the same rows for unweighted as well as
weighted searches. For directed inputs it calls the original `G.reverse()`
without explicit arguments before source validation, retaining that public
copy boundary, provider side effects and exceptions. The result of `reverse`
is the graph used for every subsequent operation. For an all-node query it
captures `G.nodes` as an iterable rather than a node snapshot; a point query
uses only the requested node. Each source search completes before summing its
distances and reading `len(G)` anew. A source with positive total distance in
a graph of at least two nodes has score `(reachable - 1) / total`; only that
branch evaluates `wf_improved`, whose truthy value applies the additional
`(reachable - 1) / (len(G) - 1)` factor. Other sources have score `0.0` without
touching that option's truth protocol. Search errors retain their original
order and wording.

Native closeness admission must exclude live topology, reverse-copy and
option providers before any conversion snapshot. Backend dispatch recovers
the original input for source-length and closeness queries that require those
public protocols, including after another query warmed the conversion cache.
No source-length or closeness fallback delegates its algorithm to NetworkX.

`harmonic_centrality` also retains authoritative unweighted rows. It selects
targets first, then sources, initializes targets to integer zero, and transposes
only when there are fewer targets than sources. Directed transposition invokes
the original `G.reverse(copy=False)` provider. It adds `1 / distance` for each
nonzero distance to a selected target in the established source and search
order. Selector callbacks can change topology before traversal; rechecking
native admission must retain the already-selected sets rather than select
again or discard a removed source. Cached backend conversions must not replace
these original inputs.

## 91. Matrix Import Storage and Construction Contract

`from_numpy_array` and `from_scipy_sparse_array` populate the graph supplied
through `create_using` and return that same instance. Its existing graph data
is cleared first. Assigned node/adjacency storage and public bulk-mutation
methods remain authoritative during construction.
This contract also applies through `from_pandas_adjacency`, generic graph
conversion, and the `convert_matrix` module aliases.

All matrix indices become nodes before edge values are consumed. NumPy array
subclasses and sparse providers may observe those nodes while computing their
nonzero coordinates or converting their values. Public bulk insertion methods
must run on custom graph instances, including when they raise; prior inserted
nodes/edges and the caller's own mutation effects remain visible after failure.
Directed imports retain their separate predecessor and successor mappings.
CSR/CSC inputs snapshot their compressed coordinate and value lists before
calling weighted edge insertion; they need not provide COO conversion.
DOK entry iteration remains lazy until weighted edge
insertion advances it. Preserve stored-edge order, duplicate entries, loops,
parallel-edge expansion, and NumPy's scalar conversion without narrowing
extended-precision values.

An empty native graph is not sufficient proof that its Python-visible storage
is native. The one-call weighted matrix fill is admitted only for concrete
simple graph classes with unmodified construction methods, standard factories,
and no assigned storage. Source admission must exclude observable matrix
providers; ordinary numeric arrays and supported ordinary sparse arrays retain
the native fill. Declining that fill leaves the existing public construction
path responsible for dtype conversion, multigraph parallel-edge semantics,
node ordering, attributes, and errors.

Custom node/edge factory support is a separate, still-incomplete core graph
mutation contract. Such factories disqualify the native matrix fill, but this
packet does not claim to complete those public mutation implementations.

## 92. Load and Percolation Centrality Input Contracts

NetworkX 3.6.1 dispatches node load under `newman_betweenness_centrality`,
edge load under `edge_load_centrality`, and percolation under
`percolation_centrality`. The backend must retain the original graph across
cached conversions: state mappings, weight callbacks, and public graph rows
can affect later source traversals. Each owned implementation admits its own
native route after these input protocols have run.

Node load uses the shared shortest-path predecessor relation. Edge load emits
both orientations of each edge and accumulates each source's contribution in
source order. Its zero/False cutoff is unbounded, as in the predecessor
contract. A live row or cutoff provider requires a fresh predecessor traversal
for each source; ordinary rows and built-in cutoff values retain the indexed
snapshot path.

Percolation state defaults are one for nodes missing the selected attribute.
An explicit mapping is authoritative. Fold all its values sequentially from
`0.0`, in mapping order, including entries outside the graph. During each
source's dependency accumulation, read `states[source]` and `states[node]`
from that mapping. Preserve Python arithmetic and exceptions; for example,
all-zero states on a connected graph raise `ZeroDivisionError`, while three
isolated nodes yield zero scores without dividing by a state denominator.
Decimal states fail during the initial float fold, and missing state keys
fail only when the traversal actually reads them.

The native percolation vector is valid only when its values, graph order,
coverage, and float arithmetic reproduce that contract. Extra keys, reordered
keys, custom mappings or numerics, and zero denominators retain the owned
Python traversal. Ordinary NetworkX simple graphs must be converted before a
native call. Unweighted queries ignore every edge attribute, including a
user attribute that collides with an internal unit-weight sentinel. Live
graph and state providers must not be frozen by the indexed Python path.

## 93. Factories for Complete Assigned Graph Storage

When a caller supplies `_node` and the complete adjacency mappings (`_adj`,
plus `_pred` for directed graphs), those dictionaries are the storage authority.
Node, edge, adjacency-row and multiedge-key dictionaries are created through
the graph's current factories. Preserve the exact objects returned by those
factories, including deliberately shared edge-attribute dictionaries. Existing
node/edge attributes retain their identities when updated. Factory replacements
on instances or classes take effect on subsequent mutations without replacing
existing dictionaries. Outer storage factories do not replace mappings already
assigned by the caller.

New undirected nodes create and install an adjacency row before creating their
node attributes; directed nodes create successor and predecessor rows first.
Scalar directed `add_node` tests successor membership, while `add_nodes_from`
tests node-store membership on all four graph families. Simple `add_edge`
always evaluates the edge-attribute factory, including for an existing edge.
Multigraph insertion evaluates that factory for an existing key too; a new
neighbor pair creates and updates attributes before creating its shared key
dictionary. Failures retain exactly the already-created rows, nodes, attributes
or edges; there is no rollback.

Simple bulk edge insertion creates endpoints before applying common attributes
and each edge's data provider. Multigraph bulk insertion first merges attributes
in a temporary dictionary, calls the public `add_edge` with no attributes, and
then updates the published edge. Its ambiguous three-tuple key interpretation
retains partial temporary updates before `TypeError`/`ValueError`. Weighted bulk
insertion delegates to the public `add_edges_from` over lazy triples. Successful
public mutations clear the NetworkX conversion cache.

This contract covers complete caller-assigned storage. General factory support
for plain native storage and native subclass construction remains incomplete;
this change does not wrap native allocators or ordinary native mutators.

## 94. Live Chordless-Cycle Enumeration

Direct `chordless_cycles` calls validate the length bound before inspecting
the graph. They retain the caller through self-loop and parallel-edge yields,
including NetworkX inputs and filtered views. Mutations made while enumeration
is suspended affect the later source reads at the same boundaries as NetworkX.
The longer search owns its `F` and `B` structural graphs; directed stem checks
continue to consult the original graph after digons have been yielded.
Conversion must not replace these live source reads with an eager snapshot.

The focused regressions cover all four graph families, mutable filters,
parallel-key changes, directed chords after suspension, and bound-validation
ordering. NetworkX backend registration and cache integration are separate
from this direct API contract.

## 95. Directed Growth Generators and Caller Protocols

`gn_graph`, `gnc_graph` and `gnr_graph` resolve the random source before graph
construction. A supplied graph class is constructed once and retains its
constructor metadata; a supplied instance is cleared once and reused. The
seed node is installed before an undirected graph is rejected. GN starts with
edge `(1, 0)` except for its singleton case; GNC and GNR retain their seed-node
behavior for nonpositive integral sizes.

Python and NumPy random streams, their adapters, and custom Random methods
keep their draw order and resulting state. Complete each graph mutation before
the next random callback. GNC reads the selected target's live successors;
GNR reads its first live successor when redirection is selected. A failure
retains the completed graph prefix. Custom graph, size and probability
protocols stay on the owned Python path; ordinary admitted native routes remain
available. Native admission must not require NumPy streams to provide a Python
MT19937 `getstate` method.

## 96. Graph Product Input Providers

`cartesian_product`, `tensor_product`, `strong_product` and
`lexicographic_product` retain the original factors when their views, storage
or attribute mappings have observable readers. Pairing attributes invokes the
original mappings' `get` methods; mutations made by those readers affect later
product layers. The initial Cartesian node-label pools are snapshots, while
edge layers read the factors anew in each product's specified order. Invalid
concurrent changes retain the source iterator's exception instead of silently
completing against an earlier conversion.

Results contain fresh shallow attribute dictionaries, retain nested value
identity and arbitrary attribute keys, and preserve parallel-edge keys and
self-loops. Factor graph metadata is not inherited or read. Ordinary concrete
factors with plain providers remain eligible for the existing native kernels.
`tests/python/test_graph_products.py` compares all four graph families with
NetworkX 3.6.1, including mutations from node and edge attribute readers.

## 97. Graph Combination Read and Construction Boundaries

The public `compose_all`, `union_all`, `intersection_all` and
`disjoint_union_all` interfaces first normalize the outer graph iterable,
matching NetworkX 3.6.1's public dispatcher. Composition and union then copy
each graph's metadata, nodes and edges before advancing to the next graph's
providers. Later reads cannot retroactively change previously copied attribute
dictionaries. Nested attribute values remain shared. Union consumes each
rename prefix when processing its graph, leaving unused prefixes unconsumed;
arbitrary prefix iterables are not truth-tested.

Genuine graph subclasses retain their result-construction effects. Synthetic
fnx views produce a concrete graph of the same directedness and multiplicity
without detaching their source providers. Observable integer relabeling in a
disjoint union completes before the resulting graph families are validated.
Ordinary native inputs retain fused pairwise operations and direct disjoint
assembly; batch operations remain linear in total input size.

`difference` and `symmetric_difference` require equal node sets and compatible
multiplicity, but permit differing directedness. Each edge is tested with the
other operand's own live `has_edge` method, so directed membership, provider
mutations and provider exceptions retain their original meaning. These set
operations do not read attributes that their result discards. The focused
contracts are exercised by `tests/python/test_cross_type_operators.py` and
`tests/python/test_graph_operators_parity.py`.

## 98. Graph Combination Backend Dispatch

The NetworkX backend exposes `disjoint_union`, `compose_all`, `union_all`,
`intersection_all`, `disjoint_union_all`, `cartesian_product`, `tensor_product`,
`lexicographic_product` and `strong_product`. Existing binary set operators
also retain their original operands across backend dispatch.

Each invocation records its graph owners before conversion. A cached native
conversion can represent a NetworkX argument while also appearing explicitly
as an independent native argument; these remain distinct inputs. Graph-list
calls recover every owner in order, preserving repeated arguments and mixed
NetworkX/fnx sequences. Recovery validates the complete invocation before
substitution, and abandoned backend probes hold only weak references.

The owned implementations determine when to read live attributes, membership
methods, filters and constructors. Their mutations remain visible on the
caller's graphs. Conversion caches are invalidated around execution, including
when a provider creates another cache and then raises. A standalone `can_run`
probe does not consume a graph generator. Coverage lives in
`tests/python/test_graph_operator_backend.py`; current-native DSR qualification
is still required by the open `br-r37-c1-78u12` work item.

## 99. Minimum Edge Cover Matching Callbacks

`min_edge_cover` rejects unsupported graph families before returning an empty
cover for an empty graph. Empty graphs never invoke a supplied matcher.

An explicit `matching_algorithm` receives the caller's original graph,
including through NetworkX backend dispatch and a warm conversion cache.
The matcher may change that graph; the completion phase selects uncovered
nodes through graph iteration over its resulting live topology and obtains
each chosen neighbor through public adjacency lookup. Iterator-only adjacency
providers retain the `arbitrary_element` rejection contract.

A set-returning matcher supplies the result object itself. The algorithm adds
completion edges to that same set and returns it. A mapping-returning matcher
instead produces a new edge set containing both directions, including both
directions of completion edges.

Callback exceptions retain their identity, type and arguments. Conversion
caches are invalidated around callback execution, including conversions
created by nested backend calls before the callback raises. Calls using the
default matcher retain their existing native conversion route.

The focused contract is covered by
`tests/python/test_covering_module_parity.py`; current-native DSR execution is
required before claiming whole-package qualification.

Matching predicates (`is_matching`, `is_maximal_matching`, and
`is_perfect_matching`) also retain the original graph. Candidate iterables
are consumed incrementally; dictionary candidates normalize through their
live `items()` provider before any graph lookup. Each candidate edge checks
its shape and endpoint membership before self-loop, `has_edge`, and overlap
validation. Empty or malformed candidates do not trigger an eager graph
copy or unrelated graph-kind/attribute reads.

Membership, edge presence, final graph length and maximality edge enumeration
use the caller's public providers, preserving asymmetric filtered rows and
topology edits made while consuming candidates. Backend dispatch preserves
this behavior with both cold and warm conversion caches, invalidates those
caches around provider execution, and propagates provider exceptions without
reclassifying them as a request for upstream fallback. Regression coverage
lives in `tests/python/test_matching_predicates_parity.py`.

## 100. Unweighted Distance Measures on Live Adjacency

Unweighted eccentricity, diameter, radius, center and periphery retain the
caller's adjacency whenever a filtered view or assigned logical storage can
expose different reachability at opposite endpoints. Materializing an
undirected graph must not introduce reciprocal edges that its public rows
exclude. This applies to the existing bounds algorithm and to calls made after
another query has populated a backend conversion cache.

Live eccentricity consumes its source bunch one node at a time, so filter and
adjacency changes between source yields affect subsequent searches. Ordinary
concrete storage retains native BFS and the shared topology-revision cache.
Observable providers neither read nor publish that cache.

Average shortest path length, Wiener index and barycenter use the same live
adjacency admission for unweighted searches. Their per-source traversal must
not restore hidden reciprocal edges through conversion or a neighbor snapshot.
Connectivity checks retain the reference graph-kind reads and operate on
current adjacency even when native witness collection is armed. These checks
retain the reference first-component semantics for asymmetric undirected rows.

An explicitly unweighted average-path method ignores its weight argument,
including callable and unhashable selectors. Live distance totals preserve
flat accumulation order and Wiener retains its final directedness read.
Barycenter retains its existing per-source reachability error contract.

The focused cases extend `tests/python/test_distance_measures_parity.py`.
Their execution and current-native DSR qualification remain outstanding under
`br-r37-c1-78u12`; the implementation and tests received source review only
because the execution environment disconnected during this session.

## 101. In-Place Graph Mutation Utilities

`freeze` returns the exact graph supplied by the caller and prevents structural
mutation on that object, including foreign NetworkX graphs and views. It
retains shared graph, node and edge attributes. Subclasses observe each
mutator assignment through their own `__setattr__`; an assignment failure
preserves the reference exception and preceding assignments. Exact native
graph classes retain their existing instance-dictionary optimization.

`set_node_attributes` and `set_edge_attributes` consume mapping-like
`items()` providers without requiring a Mapping base class. Named node
assignments read `values[node]` afresh, while edge assignments use each
yielded value and address the supplied orientation in `G._adj`. Scalar
broadcasts share the original value object. Attribute names may be any
supported hashable key. Streaming writes, missing-key handling, malformed
edge identifiers and the named-form AttributeError broadcast boundary
preserve the caller's observable protocol.

Native bulk setters remain available for ordinary concrete storage, exact
dict inputs and supported names. Assigned public providers, custom attribute
factories and nonordinary mappings keep their live Python access. Broadcast
admission is reevaluated after a provider callback, because that callback can
replace public storage before requesting the scalar fallback.

Every successfully completed setter clears a truthy backend-conversion
cache, including empty updates and native fast paths. Failed partial writes
retain the reference exception boundary; falsey custom caches are untouched.
This prevents a subsequent cached backend query from using old attributes.

Focused cases extend `tests/python/test_attribute_access_parity.py` and
`tests/python/test_graph_utilities.py`. They received independent source
review; execution and current-native DSR qualification remain outstanding
under `br-r37-c1-78u12` because the execution environment is unavailable.

## 102. Native Multi-Source Search with Compound Builtin Labels

Ordinary source labels include exact builtin tuples and frozensets containing
only exact builtin immutable scalars or nested tuples and frozensets. Their
admission inspects element types without invoking hashing, equality, repr,
or user iteration. Concrete native `Graph` and `DiGraph` inputs with ordinary
storage and canonical readers retain the existing native kernels for all
three multi-source Dijkstra entry points. Distance types, selected paths and
result insertion order remain identical to the reference search.

Nested custom objects or subclasses inside source labels retain caller-row
traversal and source-provider operation order, as do graphs with assigned
private rows or custom readers. Reusable source collections remain distinct
from effectful or one-shot source iterables. Foreign NetworkX inputs and both
multigraph classes retain their prior admission; compound labels do not newly
trigger graph conversion or whole-graph directed-multigraph projections.
Bounded queries retain their existing routing, and length-only queries do not
build path dictionaries.


## 103. Clustering on Live Views and Attribute Providers

`clustering` and `average_clustering` retain the caller's graph when a view,
assigned adjacency, node selector, attribute reader or numeric value has an
observable protocol. In particular, an undirected view of a directed graph
may expose different weights at its two endpoints. Conversion to a concrete
undirected graph and a symmetric edge-weight cache both lose that information.

Weighted normalization uses the original edge enumeration. Triangle products
then read the oriented adjacency cells needed by each triangle; a later read
observes mutations made by earlier reads or arithmetic. Node-bunch iterators
remain lazy and are consumed after the weighted maximum scan, between the
corresponding triangle counts. Directed counts retain their predecessor and
successor rows. The same owned counting loops support live and snapshot
access; ordinary whole-graph and unweighted native queries retain their
existing native or snapshot routes. Weighted scalar and subset queries read
their selected rows live after the required maximum-weight scan, avoiding a
second full-graph admission pass. MultiGraph and MultiDiGraph rejection
remains unchanged.

Backend dispatch shares the live-input admission check before conversion,
including calls made after an earlier query populated a conversion cache.
A cached triangle census cannot override assigned logical/public readers.

Native generalized-degree histograms and square-clustering coefficients use
open neighborhoods at every endpoint. Self-loops do not create triangle
incidences or four-cycles, affect coefficient denominators, or remove isolated
vertices. All-node and subset results retain these semantics without mutating
graph storage.

Transitivity and generalized degree also retain the caller's live adjacency.
Their all-node counts read `G.adj.items()`, preserving row orientation and
the owner lookup before construction of each neighbor set.
Transitivity accepts simple directed graphs and intersects successor rows.
Generalized degree rejects directed graphs first, checks node membership
before multigraph rejection, and consumes node selections between counts.
The live counting path runs label callbacks outside graph borrows. Small
selected queries on native graphs inspect only their requested neighborhoods.
Backend dispatch preserves these original-graph reads through both cold and
warm conversion caches.

Square clustering reads the caller's private adjacency rows (`G._adj`),
including oriented rows of filtered undirected views and assigned private
storage. Public `adj`, `neighbors`, and `__getitem__` providers do not replace
that row source. Copying through those readers can therefore change the
answer even when the provider itself should be ignored.

Within one square-clustering call, each open neighborhood is cached on its
first use. The cache survives between selected-node counts: an effectful
node-bunch iterator runs between those counts, while previously observed
neighborhoods remain cached and unseen neighborhoods reflect later mutations.
Node selection and scalar-result membership follow the caller's graph, and
directed graphs use successor rows. Parallel edges collapse to neighbor keys.
Backend dispatch keeps these same original rows and selectors on both cold
and warm conversion caches. Ordinary native Graph queries retain the existing
all-node and subset kernels; a bounded query must not hash unrelated labels
merely to decide whether it can use a native kernel.

Regression cases are added to `tests/python/test_clustering.py` and
`tests/python/test_backend_convert_from_nx_hints.py`. The baseline mismatch
was reproduced through the whole current Python package and released 0.4.1
native dependency before the workspace disconnected. After recovery and
correction of the extra admission scan, the bounded DSR diagnostic described
below passed all 357 clustering cases, including both existing single-node
scan-budget checks, and all 52 selected backend cases. This remains targeted
evidence; `br-r37-c1-78u12` full qualification work stays open.

## 104. Degree Assortativity on Original Graph Providers

Degree assortativity keeps the original graph/view through weighted degree
mapping and degree-pair reads before building its mixing matrix. Undirected
views of directed edges can expose different endpoint weights; materializing
them must not merge those weights or restore hidden adjacency.

Assigned private/public readers, custom degree or edge providers, and
mutating node selectors retain their own read order. Native bulk admission
requires callback-free native storage; the unweighted multigraph route
retains parallel-edge multiplicity. Repeated attribute writes are visible to
subsequent weighted coefficient calls.

Focused cases extend `tests/python/test_assortativity_parity.py`. Baseline
differences were reproduced before execution-environment loss. The recovered
DSR diagnostic passed all 443 cases across the parity and extensions modules.
The regression fixtures accept multigraph edge keys and populate a reciprocal
view's conversion cache before activating its asymmetric filter, testing
that subsequent calls recover the original live view.

## 105. In-Place Relabeling Partial Progress

An in-place relabel completes each accepted rename before the next observable
mapping, graph or node callback. If a later rename fails, the graph retains
exactly the previously completed renames and their attributes, without
isolated old labels left behind by deferred cleanup.

Deferred native deletion is allowed only when native graph readers, labels
and mapping inputs cannot call user code. Ordinary disjoint-label batch
relabeling retains its existing fast route. Subclasses and custom mappings
keep the incremental mutation boundary. Deferred native removals are finalized
even when a later invalid label or attribute raises.

The all-class baseline `{0: 10, 1: None}` on a three-node path leaves
`[1, 2, 10]` after the reference exception. The prior implementation left
the stale node `0` as well. Regressions extend
`tests/python/test_relabel_edge_cases_parity.py`. All 148 cases in that module
passed the bounded DSR diagnostic below: 64 new cases cover failure state,
callbacks and attribute sharing, and eight additional cases verify that
ordinary native bulk removal remains admitted before and after public
readers are cached, then stops being admitted after nested payloads appear.

## 106. Bounded Live-Graph Parity Validation

DSR diagnostic run `20261122T005909-pNxIe6Td` executed five checks against
`b83db9e33462c8a0306c9a7606bf2e788d380f1a` plus the relabel, weighted-local
clustering and regression-fixture changes above. Its before/after source
snapshots are identical. The selected checks and receipt are preserved in
[`checks-config.yaml`](../../artifacts/diagnostics/live_graph_parity_20261122/checks-config.yaml)
and [`receipt.json`](../../artifacts/diagnostics/live_graph_parity_20261122/receipt.json).

| Guarded pytest group | Passed |
| --- | ---: |
| Assortativity parity and extensions | 443 |
| Clustering, coefficient identities and triangle order | 357 |
| In-place relabel edge cases and bulk admission | 148 |
| Backend clustering dispatch, providers and conversion caches | 52 |
| **Total** | **1,000** |

The Python checkout used the published 0.4.1 native extension, SHA-256
`9314ccf170b8a43ca54f2c77822cd26012e5ba6b121cc314386bfbebbf34e386`.
The native crates, Cargo manifests/lockfile and Rust toolchain configuration
have no differences from tag `v0.4.1` at the tested revision. This is an
unchanged release dependency, not a freshly built native artifact.
Concurrent native integer-simplex commit `23519093faee162c6d6c63a01dbb5de5da8aa15b`
landed after this frozen run and is preserved on `main`; its native changes
are outside this receipt's qualification scope.

The aggregate diagnostic is **failed, 4/5 checks passed**. UBS scanned 12
files but returned partial status (exit 2): its Python taint analysis could
not resolve generator-consumer identities in existing split-module code.
Its single critical finding is an unchanged self-pickle roundtrip test in
`test_backend_convert_from_nx_hints.py`; it is not introduced by these changes.
No scanner findings or checks were suppressed. This diagnostic does not
claim a green UBS run, the canonical full-repository DSR quality gate, a
cross-platform build, or release qualification.

## 107. Composition Preserves Live Node Attributes

`compose` and disjoint `union` on ordinary native `Graph` inputs merge the
authoritative node dictionaries after native topology and edge composition.
Reading an input dictionary before the operation must not change its result;
cleared attributes cannot reappear from older native storage. Right-hand
attributes take precedence, earlier nonconflicting fields and insertion order
survive, and each result dictionary is a fresh shallow copy whose nested
values retain their original identity. Attribute-free inputs keep the native
fast return. Other graph classes retain their existing composition routes.

The eight failing storage-history baselines now pass. The guarded DSR operator
checks passed 678 cases, including 56 new cases across graph classes and
public, namespace and backend routes. These are scoped Python checks using
the published 0.4.1 native dependency, not current-native release qualification.

## 108. Exact Numeric Modularity

Undirected modularity retains Python's arithmetic domain for edge weights.
Decimal and Fraction weights, including values equal to one, use their exact
weighted degree and community-edge sums. The normalization expressions match
NetworkX (`degree_sum / 2` and `1 / degree_sum**2`), preserving result types,
rounding, division errors and float-overflow exceptions. Ordinary primitive
unit weights retain the single whole-graph edge-count route; directed graphs
retain their existing in/out-degree formula.

The twenty failing numeric baselines now pass. DSR passed all 501 cases in
the focused modularity and community-quality suites, including 44 new exact
arithmetic, overflow and route-control cases. The native dependency and
qualification limits are the same as in Section 107.

## 109. Complete GML File Reads in Runtime Modes

`read_gml` preserves the complete GML value model under explicit strict and
hardened modes and ambient hardened mode: all four graph classes, parallel
edge keys, graph/node/edge attributes, repeated values and nested mappings.
Compressed paths use the existing opener. Caller-owned streams are consumed
once, remain open and are not rewound.

Default-option reads validate the original decoded input through the native
reader. Clean documents are reconstructed by the owned GML decoder, then
receive the actual native policy and decision records. Custom labels,
`label=None` and destringizers use the existing complete-parser boundary:
grammar, IDs, labels and endpoints are validated, malformed input fails closed
in either mode, and no native read/recovery receipt is fabricated.

Native recovery remains available for simple scalar graphs and nested scalar
maps. Recovery rejects a declared multigraph and repeated/list/tuple values
recognized by the complete decoder, preventing silent parallel-edge collapse
or attribute-list truncation. Incomplete syntax retains the established
bounded recovery; lossless recovery of rich malformed documents is not
claimed. Thirty-three failing file-reader baselines now pass, with 78 new
mode, graph-class, option, recovery and ownership regression cases.

### Scoped diagnostic evidence for Sections 107-109

Real DSR runs `20261122T020246-YB5sqgfb` and
`20261122T020506-BfA7YYpd` have identical before/after source snapshots. Their
[initial receipt](../../artifacts/diagnostics/core_functionality_20261122/initial-receipt.json),
[initial checks](../../artifacts/diagnostics/core_functionality_20261122/initial-checks.yaml),
[final receipt](../../artifacts/diagnostics/core_functionality_20261122/final-receipt.json)
and [final checks](../../artifacts/diagnostics/core_functionality_20261122/final-checks.yaml)
are retained without rewriting their failed aggregate statuses.

| Guarded pytest group | Passed | Failed |
| --- | ---: | ---: |
| Composition, graph operators, backend and merge contracts | 678 | 0 |
| Modularity and community quality | 501 | 0 |
| GML, runtime modes, readwrite audit and GML/GraphML roundtrips | 1,546 | 1 |
| **Distinct cases, excluding isolated reruns** | **2,725** | **1** |

All 178 newly added cases pass. The remaining failure is the unchanged
`test_hardened_graphml_repair_revalidates_beyond_retained_ledger`. Its final
assertion expects an earlier native FullValidate record to have been retired;
the native ledger intentionally retains non-Allow decisions. The GraphML
adapter correctly rejects the unsupported repair, and the same assertion
fails in isolation. The GML change does not enter that execution path.

Each of the three UBS checks scanned its two selected source/test files and
reported zero critical findings. All returned partial exit 2 because Python
flow analysis could not resolve existing generator-consumer identities; no
partial acceptance setting or finding suppression was used. The aggregate
DSR results are **failed (3/4 and 1/5 checks passed)**, not green quality gates.

The frozen checkout is based on `b83db9e33462c8a0306c9a7606bf2e788d380f1a`
with the preceding live-graph changes and the three changes above. It uses
NetworkX 3.6.1 and the published 0.4.1 native extension, SHA-256
`9314ccf170b8a43ca54f2c77822cd26012e5ba6b121cc314386bfbebbf34e386`.
Concurrent native and Python commits on main were preserved when publishing;
they are outside these frozen-source receipts. Current-native compilation,
canonical full DSR quality and release qualification remain open under
`br-r37-c1-78u12`.

## 110. Standard node-link JSON file ingestion

`read_json_graph` accepts the standard node-link documents produced by
`node_link_data` and `json.dump`, including all four graph classes, graph/node/
edge attributes, parallel edge keys, implicit endpoint nodes, missing node IDs,
and JSON arrays used as tuple node labels. The owned constructor supplies its
existing defaults (`directed=False`, `multigraph=True`) when flags are absent.
Current `edges` and historical `links` arrays are accepted; a document containing
both arrays is ambiguous and fails closed. Explicit private snapshot envelopes
retain the existing native reader and its bounded recovery behavior.

The native readwrite engine validates the original standard document, including
every record, flag, label/key domain, envelope field and reserved incompatible
feature marker. Validation borrows raw JSON values, so integer IDs and attributes
within the Python decoder's configured digit limit are never normalized through
floating point or the native scalar attribute representation. The complete
owned constructor receives the original Python JSON values and the resulting
graph receives the actual native validation policy. Its policy carrier is not
a decoded graph or a surrogate document and must not be returned as the
ingestion result.

Recognized standard documents with invalid structure, unsupported envelope
fields or incompatible metadata fail closed in both modes. Hardened mode does
not invent repairs for this new schema. Standard JSON syntax excludes NaN and
Infinity literals; missing IDs, implicit endpoints and repeated ordinary records
are constructor semantics, not recoveries. Tuple-label validation uses an
iterative walk with a 128-level nesting limit. Callers may provide paths (including
gzip/bzip2 files) or text/binary streams; streams are read once, remain open and
are not rewound. Explicit and ambient compatibility modes govern both native
validation and graph construction.

DSR run `20261122T101950-6Eu8wG54` passed all six new native regression tests,
the `fnx-readwrite` compile check, and formatting for the two changed Rust
packages, with identical source snapshots before and after execution. Run
`20261122T102434-00gAH8oq` then built a fresh development-profile extension from
the frozen candidate and passed all 119 Python ingestion cases, followed by
740 neighboring operator, spanning-count and node-link tests (26 existing
skips). The staged wheel's Python sources were compared with the candidate
before execution. This is current-candidate functional evidence; it makes no
performance, release or full canonical qualification claim.

## 111. Weighted spanning-tree count domains

`number_of_spanning_trees` preserves the selected edge-value domain and accepts
literal hashable attribute selectors; `weight=None` retains unit weights.
Complex and nonfinite values use the existing owned Matrix-Tree builders and
determinant, preserving their returned values, warnings and errors.
Numeric-looking strings and invalid objects must not silently become native
numbers or unit weights. Null-graph and directed-root errors retain their
precedence, and disconnected graphs with valid inputs return literal integer
zero.

The directed cofactor uses incoming-degree sums and the requested root;
undirected cofactors use the ordinary Laplacian. Parallel weights and self-loop
cancellation follow the matrix builders. Ordinary unweighted and admitted
finite builtin-real simple graphs retain the native kernel; integer totals
above `2**53` are conservatively declined. Admission uses the shared weight
scan, including live attribute mirrors and mutation-sensitive caching.

The published 0.4.1 baseline DSR run `20261122T100333-ZI127YPY` reproduced 46
failures and 66 passing controls across all graph types and direct/backend
routes. DSR run `20261122T101126-GTOD1n70` passed the complete candidate count
module (405 passed, 26 existing skips), including all 128 new cases, with the
published 0.4.1 native extension and verified candidate Python sources. The
expanded matrix covers native-route retention and changes to held edge-attribute
dictionaries. The fresh extension run in section 110 repeated this complete
module successfully. Neither run establishes release, performance or full
canonical qualification.

## 112. Stochastic normalization domains and graph copies

`stochastic_graph` normalizes directed simple and keyed parallel graphs using a
canonical shallow graph copy when requested. Imported graph metadata, arbitrary
graph/node/edge attribute keys and nested shared values survive; graph and
attribute dictionaries are independent under `copy=True`. The public out-degree
reduction preserves exact integer totals, Decimal/Fraction arithmetic, Python
compensated float sums, parallel multiplicity and integer-zero outputs.

In-place normalization returns the original graph and retains completed edge
updates if later numeric division fails. With `weight=None`, denominators are
unweighted out-degrees and the written edge key is `None`, matching NetworkX.
Native fused copy/in-place kernels remain admitted for ordinary native storage
and positive builtin weights whose numerator total over a common binary
denominator is at most `2**53`. Aliases, zero/negative/nonfinite values and other
numeric domains use the owned public path. Directed whole-view degree iteration
admits only string selectors to its string-only native kernel.

The published 0.4.1 release baseline reproduced 17 failures and 13 passing
controls across the initial 30 cases. The candidate adds 64 cases, including
eight native-route controls, in `tests/python/test_graph_operators_parity.py`.
DSR run `20261122T101126-GTOD1n70` passed all 320 tests in the complete operator
module with the published 0.4.1 extension and verified candidate Python sources.
The source and lockfile snapshots remained unchanged. The fresh extension run
in section 110 repeated this complete module successfully. Neither run makes a
performance, release or full-suite qualification claim.

## 113. Attribute Matrix Unit-Weight Topology

`attr_matrix(..., edge_attr=None)` counts graph incidences without inspecting
edge values. All attribute keys remain available to callers, including literal
`None` keys and strings that resemble internal sentinels. Mutating those values
through a held edge dictionary cannot change a unit-weight matrix.

Ordinary simple graphs use the existing topology-only COO exporter, retaining
directed orientation, one contribution per self-loop, and the requested row and
column ordering. An omitted isolated node is allowed; an omitted edge endpoint
retains the general path's error. Duplicate row orders retain the last-position
index semantics of the owned general builder. Explicit weighted selectors
continue to use their actual edge values, including a key that formerly served
as an internal sentinel. Dtype, normalization and namespace aliases preserve
the same public contract.

## 114. Live Unweighted Degree Iteration

Native unweighted degree iteration reads each result at that node's yield
boundary. The ordinary bulk snapshot remains usable while both node and edge
revisions match its captured state. Once topology changes, the remainder of
that walk computes degrees from the current graph instead of consuming stale
snapshot values. It does not rescan the whole graph for each yielded node.

Whole-graph walks keep the original live dictionary iterator, including its
size/key-change checks and final exhaustion check. A legal same-size node
replacement uses the node actually yielded by that iterator, not the old
snapshot's label. A failing generator stays exhausted and releases its source.

Explicit node selections keep their resolved order and duplicates. They have
no whole-graph resize guard; removal of a selected node raises when the walk
reaches that node, leaving earlier results observable. Ordinary `G.degree`
and `G.degree()` consumption follow the same live contract across the four
graph families, including directed total, incoming and outgoing degree.

## 115. Lowest Common Ancestor Queries and Streaming

The DAG ancestor APIs validate graph direction, acyclicity, empty inputs and
explicit node pairs at the public call boundary. Explicit pairs retain their
deduplicated encounter order. Each endpoint's ancestor set is computed once
when first needed; that documented cache does not permit caching unrelated
predecessor or successor rows across queries. A later search or descent reads
the caller's current public rows, including views and replaced readers.

The tree all-pairs API is a lazy Tarjan traversal. It validates roots and tree
structure when advanced, preserves postorder and pair orientation, and yields
each answer before continuing the traversal. Partial consumption must not
materialize the quadratic set of all pair answers. Supplied pairs restrict
the emitted results, and mutations or provider exceptions remain observable
at the reference traversal boundary. Closing an iterator releases its source
and traversal state without consuming further pairs.

All three APIs are available through explicit and automatic NetworkX backend
dispatch. Cached conversions must not replace the caller's graph, node labels
or default return object. The two iterator APIs retain their live sources
through advancement and close; graph-contract errors and provider exceptions
propagate without being mistaken for an unsupported backend operation.

## 116. Live Common Neighbors in Link Prediction

`common_neighbors(G, u, v)` rejects directed graphs before validating `u` and
then `v`. It intersects the live keys of the two private adjacency rows and
removes the endpoints. Hashing an endpoint or a stored neighbor can run caller
code, including a topology mutation. Those callbacks must execute outside a
native graph borrow, and later row reads must observe the resulting topology
at the reference boundary. The result remains a set.

The seven link predictors that use common neighbors retain that contract when
each score is consumed. Resource allocation and Adamic–Adar read the common
neighbor's degree after constructing the intersection. Jaccard first builds
its union from the public `G[u]` and `G[v]` rows, then independently reads the
private rows for its numerator. A snapshot shared across these distinct reads
can therefore change the result. Explicit candidate-pair validation remains
eager, while callbacks used only to score a pair remain lazy.

Ordinary primitive-label queries retain native batching and local endpoint-row
admission. A query must not inspect unrelated graph labels to decide whether
the native path is safe. Direct `common_neighbors` is not backend-dispatchable
in NetworkX 3.6.1; explicit backend coverage applies to the eight registered
link predictors, preserving their original graph on both cold and warm
conversion caches.

## 117. Live Weighted All-Pairs and Average Distances

Unbounded weighted all-pairs queries retain the caller's graph and begin each
source search when that result is consumed. Node hashing and equality can
execute caller code; these protocols must run outside a native graph borrow.
A first callback may change a weight or topology, and later relaxations read
the resulting live edge dictionaries. Multigraph searches retain the parallel
edge-key map and reduce its current weights at the same boundary as the
reference algorithm. Row iteration preserves encounter order and dictionary
invalidation behavior when a callback changes its contents.

Weighted `average_shortest_path_length` preserves method, empty-graph,
singleton and connectivity validation before weight callbacks. Its per-source
searches use the same live weighted rows rather than computing a stale native
mean before a stored-label callback executes. A callback-free ordinary concrete
graph retains the native route. Global label and row-alias admission may be
cached for these already-unbounded queries; a bounded shortest-path query must
not acquire a whole-graph admission scan from this correction.

Native undirected neighbor-data cursors expose persistent live
`(neighbor, edge_attributes)` or `(neighbor, parallel_edge_map)` rows without
hashing display labels while holding the graph. Edge insertion, deletion,
parallel-key changes and graph clearing update or detach these rows with the
same lifetime rules as the existing directed cursors. Backend conversion
caches must not replace the original graph for observable live queries. Cache
population itself is not part of the weighted average-distance contract.
