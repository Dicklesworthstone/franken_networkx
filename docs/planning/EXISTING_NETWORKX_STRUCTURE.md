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

## 17. Concurrency/Lifecycle Semantics and Ordering Guarantees (DOC-PASS-06)

### 17.1 Legacy anchor points to preserve

- Graph mutation is in-place over shared adjacency dictionaries (`legacy_networkx_code/networkx/networkx/classes/graph.py`, `digraph.py`), with explicit list materialization in removal loops to avoid iterator invalidation.
- Node/edge/adjacency views are live wrappers (`legacy_networkx_code/networkx/networkx/classes/coreviews.py`, `reportviews.py`) and therefore reflect current backing-map state, not snapshot-isolated state.
- Dispatch backend resolution is driven by global backend registries and backend-priority policy (`legacy_networkx_code/networkx/networkx/utils/backends.py`), making route choice deterministic only when config and backend availability are held constant.
- Traversal output order in shortest-path routines inherits adjacency iteration order (`legacy_networkx_code/networkx/networkx/algorithms/shortest_paths/unweighted.py`).
- Random generator reproducibility depends on explicit seed handling via `@py_random_state` (`legacy_networkx_code/networkx/networkx/generators/random_graphs.py`).
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
- The in-process implementation reuses the shared Bellman-Ford relaxation
  kernel through private adjacency containers. It preserves the caller's
  nodes and edges, including on exceptions, and keeps existing edge
  attribute dictionaries live.

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

Sparse iterations require arithmetic compatible with their reordered
matrix reductions. Signed weights or vectors can expose catastrophic
cancellation in the reference per-edge update order, so they retain owned
iteration instead of being silently reassociated. Admission inspects plain
values without calling user numeric conversion methods.


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

The ordinary native route is eligible only when its inputs cannot require
object remapping or observable copy callbacks. General Python object graphs
use a memo-aware route that preserves the complete identity relationships.
`tests/python/test_deepcopy_conformance_guard.py` and
`tests/python/test_copy_semantics_parity.py` compare these semantics with
NetworkX across all four graph classes, including recursive attributes,
mutable node objects, shared dictionaries, supplied memos, and copy failures.

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

## 43. Graph Pickle Persistence and Object Identity

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
strong component before returning to its predecessors. An iterative low-link
search supports long chains without Python recursion. No iterator wraps an
eager native list of every component.

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

## 50. Connectivity Queries with Custom Flow Solvers and Cutoffs

`edge_connectivity` owns local and global queries with a supplied solver or
cutoff. `minimum_edge_cut` and `minimum_node_cut` own their custom-solver
orchestration. These routes use the caller's graph protocol without converting
it into a NetworkX graph. Ordinary default native routes remain separately
admitted. Global queries construct one auxiliary graph and one residual and
reuse them for their local flow computations; callback-visible endpoints,
solver options, residual identity, and invocation order are observable.

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
