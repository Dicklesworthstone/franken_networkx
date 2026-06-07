# EXHAUSTIVE_LEGACY_ANALYSIS.md — FrankenNetworkX

Date: 2026-02-13  
Method stack: `$porting-to-rust` Phase-2 Deep Extraction + `$alien-artifact-coding` + `$extreme-software-optimization` + RaptorQ durability + frankenlibc/frankenfs strict/hardened doctrine.

## 0. Mission and Completion Criteria

This document defines exhaustive legacy extraction for FrankenNetworkX. Phase-2 is complete only when each scoped subsystem has:
1. explicit invariants,
2. explicit crate ownership,
3. explicit oracle families,
4. explicit strict/hardened policy behavior,
5. explicit performance and durability gates.

## 1. Source-of-Truth Crosswalk

Legacy corpus:
- `/data/projects/franken_networkx/legacy_networkx_code/networkx`
- Upstream oracle: `networkx/networkx`

Project contracts:
- `/data/projects/franken_networkx/COMPREHENSIVE_SPEC_FOR_FRANKENNETWORKX_V1.md`
- `/data/projects/franken_networkx/EXISTING_NETWORKX_STRUCTURE.md`
- `/data/projects/franken_networkx/PLAN_TO_PORT_NETWORKX_TO_RUST.md`
- `/data/projects/franken_networkx/PROPOSED_ARCHITECTURE.md`
- `/data/projects/franken_networkx/FEATURE_PARITY.md`

Important specification gap:
- the comprehensive spec currently defines sections `0-13` then jumps to `21`; missing sections for crate contracts/conformance matrix/threat matrix/perf budgets/CI/RaptorQ envelope must be backfilled.

## 2. Quantitative Legacy Inventory (Measured)

- Total files: `1247`
- Python: `687`
- Native code: negligible for core graph logic
- Test-like files: `307`

High-density zones (`*.py` files):
- `networkx/algorithms` (393 files)
- `networkx/generators` (59)
- `networkx/readwrite` (35)
- `networkx/classes` (26)

## 3. Subsystem Extraction Matrix (Legacy -> Rust)

Path namespace rule for this section: unless an absolute repo path is shown, legacy module paths are relative to `legacy_networkx_code/networkx/networkx/`.

| Legacy locus | Non-negotiable behavior to preserve | Target crates | Primary oracles | Phase-2 extraction deliverables |
|---|---|---|---|---|
| `networkx/classes/graph.py` | adjacency dictionary and attribute aliasing semantics | `fnx-classes` | `classes/tests/test_graph.py` | graph mutation state machine |
| `classes/digraph.py`, `multigraph.py`, `multidigraph.py` | directed/multiedge key semantics | `fnx-classes` | class test suites | directed+multiedge invariant ledger |
| `classes/coreviews.py`, `graphviews.py`, `reportviews.py` | live view behavior and cache reset semantics | `fnx-views` | `test_graphviews.py`, `test_coreviews.py` | view consistency contract |
| `utils/backends.py` | `_dispatchable` backend routing behavior | `fnx-dispatch` | `classes/tests/dispatch_interface.py` | backend routing decision table |
| `convert.py`, `convert_matrix.py`, `relabel.py` | conversion and ingestion behavior | `fnx-convert` | `tests/test_convert.py` | conversion precedence/error map |
| `algorithms/shortest_paths/weighted.py` + core algorithms | algorithm output/error semantics | `fnx-algorithms` | shortest-path and related algorithm tests | algorithm contract matrix |
| `generators/*` | deterministic and random generator semantics | `fnx-generators` | `generators/tests/*` | generator seed/ordering ledger |
| `readwrite/*` | parser/writer behavior, compressed-file convenience | `fnx-readwrite` | `readwrite/tests/*` | format contract and parser state maps |
| `utils/configs.py`, `lazy_imports.py` | runtime config and optional dependency behavior | `fnx-runtime` | utils and integration tests | runtime compatibility ledger |

## 4. Alien-Artifact Invariant Ledger (Formal Obligations)

- `FNX-I1` Adjacency integrity: graph mutation preserves adjacency and edge-attribute invariants.
- `FNX-I2` View consistency: read-only/live views remain semantically synchronized with parent graph state.
- `FNX-I3` Dispatch determinism: backend routing decisions are deterministic under scoped configuration.
- `FNX-I4` Conversion determinism: accepted input forms resolve through deterministic precedence with stable errors.
- `FNX-I5` Algorithm contract integrity: scoped algorithms preserve documented output/error semantics.

Required proof artifacts per implemented slice:
1. invariant statement,
2. executable witness fixtures,
3. counterexample archive,
4. remediation proof.

## 5. Interop Boundary Register

| Boundary | Files | Risk | Mandatory mitigation |
|---|---|---|---|
| optional dependency conversion | `convert.py`, `convert_matrix.py` | high | optional-dependency route fixtures |
| backend dispatch | `utils/backends.py` | high | loopback backend conformance corpus |
| compressed read/write handling | `utils/decorators.py`, `readwrite/*` | medium | malformed/compressed input corpus |
| GraphML/GML parsers | `readwrite/graphml.py`, `gml.py` | high | parser robustness and safety fixtures |

## 6. Compatibility and Security Doctrine (Mode-Split)

Decision law (runtime):
`mode + graph_contract + risk_score + budget -> allow | full_validate | fail_closed`

| Threat | Strict mode | Hardened mode | Required ledger artifact |
|---|---|---|---|
| malformed graph payload | fail-closed | fail-closed with bounded diagnostics | parser incident ledger |
| backend override ambiguity | fail ambiguous route | stricter route checks + audit | backend decision ledger |
| optional dependency mismatch | fail unsupported path | fail unsupported path + richer diagnostics | dependency compatibility report |
| unknown incompatible format metadata | fail-closed | fail-closed | compatibility drift report |
| algorithm mismatch | fail conformance gate | fail conformance gate | differential failure bundle |

## 7. Conformance Program (Exhaustive First Wave)

### 7.1 Fixture families

1. Core classes mutation/attribute fixtures
2. View consistency fixtures
3. Backend dispatch fixtures
4. Conversion precedence/error fixtures
5. Shortest-path and core algorithm fixtures
6. Generator determinism fixtures
7. Read/write round-trip and parser fixtures

### 7.2 Differential harness outputs (`fnx-conformance`)

Each run emits:
- machine-readable parity report,
- mismatch taxonomy,
- minimized repro bundle,
- strict/hardened divergence report.

Release gate rule: critical-family drift => hard fail.

## 8. Extreme Optimization Program

Primary hotspots:
- shortest-path and core algorithm loops
- conversion and relabel hotpaths on large graphs
- read/write parse and serialization loops

Current governance state:
- comprehensive spec lacks explicit numeric budgets (sections 14-20 absent).

Provisional Phase-2 budgets (must be ratified):
- algorithm hotpath p95 regression <= +10%
- conversion/readwrite p95 regression <= +10%
- p99 regression <= +10%, RSS regression <= +10%

Optimization governance:
1. baseline,
2. profile,
3. one lever,
4. conformance proof,
5. budget gate,
6. evidence commit.

## 9. RaptorQ-Everywhere Artifact Contract

Durable artifacts requiring RaptorQ sidecars:
- conformance fixture bundles,
- benchmark baselines,
- dispatch/conversion compatibility ledgers.

Required envelope fields:
- source hash,
- symbol manifest,
- scrub status,
- decode proof chain.

## 10. Phase-2 Execution Backlog (Concrete)

1. Extract core Graph/DiGraph/MultiGraph mutation semantics.
2. Extract view synchronization and cache-reset behavior.
3. Extract backend dispatch route semantics.
4. Extract conversion precedence and error behavior.
5. Extract shortest-path contract behavior.
6. Extract deterministic generator behavior for scoped families.
7. Extract read/write format contracts and parser failure surfaces.
8. Build first differential fixture corpus for items 1-7.
9. Implement mismatch taxonomy in `fnx-conformance`.
10. Add strict/hardened divergence reporting.
11. Attach RaptorQ sidecar generation and decode-proof validation.
12. Ratify section-14-20 budgets/gates against first benchmark and conformance runs.

Definition of done for Phase-2:
- each section-3 row has extraction artifacts,
- all seven fixture families runnable,
- governance sections 14-20 empirically ratified and tied to harness outputs.

## 11. Residual Gaps and Risks

- sections 14-20 now exist; top release risk is benchmark-budget calibration on representative graph classes.
- `PROPOSED_ARCHITECTURE.md` crate map formatting contains literal `\n`; normalize before automation.
- backend and conversion routes need broad fixture breadth to avoid silent compatibility drift.

## 12. Deep-Pass Hotspot Inventory (Measured)

Measured from `/data/projects/franken_networkx/legacy_networkx_code/networkx`:
- file count: `1247` total files (`687` Python files)
- concentration (`*.py` files): `networkx/algorithms` (`393`), `networkx/generators` (`59`), `networkx/readwrite` (`35`), `networkx/classes` (`26`)

Top source hotspots by line count (first-wave extraction anchors):
1. `networkx/algorithms/shortest_paths/weighted.py` (`2542`)
2. `networkx/utils/backends.py` (`2183`)
3. `networkx/classes/graph.py` (`2081`)
4. `networkx/algorithms/similarity.py` (`2107`)
5. `networkx/classes/function.py` (`1575`)
6. `networkx/classes/reportviews.py` (`1555`)

Interpretation:
- graph core + view + dispatch interplay defines most observable semantics,
- shortest-path behavior is high-value and high-risk,
- conversion/readwrite paths need explicit parser/format contract extraction.

## 13. Phase-2C Extraction Payload Contract (Per Ticket)

Each `FNX-P2C-*` ticket MUST produce:
1. graph/view/type inventory,
2. mutation and cache/reset rule ledger,
3. conversion/dispatch precedence rules,
4. error and warning contract map,
5. strict/hardened split policy,
6. exclusion ledger,
7. fixture mapping manifest,
8. optimization candidate + isomorphism risk note,
9. RaptorQ artifact declaration,
10. governance backfill linkage note.

Artifact location (normative):
- `artifacts/phase2c/FNX-P2C-00X/legacy_anchor_map.md`
- `artifacts/phase2c/FNX-P2C-00X/contract_table.md`
- `artifacts/phase2c/FNX-P2C-00X/fixture_manifest.json`
- `artifacts/phase2c/FNX-P2C-00X/parity_gate.yaml`
- `artifacts/phase2c/FNX-P2C-00X/risk_note.md`

## 14. Strict/Hardened Compatibility Drift Budgets

Packet acceptance budgets:
- strict critical drift budget: `0`
- strict non-critical drift budget: `<= 0.10%`
- hardened divergence budget: `<= 1.00%` and allowlisted only
- unknown format/backend behavior: fail-closed

Per-packet report requirements:
- `strict_parity`,
- `hardened_parity`,
- `graph_semantics_drift_summary`,
- `dispatch_route_drift_summary`,
- `compatibility_drift_hash`.

## 15. Extreme-Software-Optimization Execution Law

Mandatory loop:
1. baseline,
2. profile,
3. one lever,
4. conformance + invariant replay,
5. re-baseline.

Primary sentinel workloads:
- weighted shortest-path suites (`FNX-P2C-005`),
- conversion-heavy workloads (`FNX-P2C-004`, `FNX-P2C-006`),
- graph mutation/view refresh workloads (`FNX-P2C-001`, `FNX-P2C-002`).

Optimization scoring gate:
`score = (impact * confidence) / effort`, merge only if `score >= 2.0`.

## 16. RaptorQ Evidence Topology and Recovery Drills

Durable artifacts requiring sidecars:
- parity reports,
- mismatch corpora,
- conversion/dispatch ledgers,
- benchmark baselines,
- strict/hardened decision logs.

Naming convention:
- payload: `packet_<id>_<artifact>.json`
- sidecar: `packet_<id>_<artifact>.raptorq.json`
- proof: `packet_<id>_<artifact>.decode_proof.json`

Decode-proof failures are hard blockers.

## 17. Phase-2C Exit Checklist (Operational)

Phase-2C is complete only when:
1. `FNX-P2C-001..009` artifact packs exist and validate.
2. All packets have strict and hardened fixture coverage.
3. Drift budgets from section 14 are satisfied.
4. High-risk packets include optimization proof artifacts.
5. RaptorQ sidecars + decode proofs are scrub-clean.
6. Governance backfill tasks are explicitly linked to packet outputs.

## 18. Data Model and State Transition Ledger (DOC-PASS-03)

### 18.1 Canonical component state models

| Component | Legacy anchors | Rust ownership | Mutable fields | Invariant focus |
|---|---|---|---|---|
| Graph adjacency store | `classes/graph.py`, `digraph.py`, `multigraph.py` | `fnx-classes` | nodes, adjacency map, attrs, revision | adjacency integrity + revision monotonicity |
| View cache/projection layer | `classes/coreviews.py`, `graphviews.py` | `fnx-views` + `fnx-classes` | cached snapshot, revision pointer, filters | view ordering parity + cache coherence |
| Dispatch registry | `utils/backends.py` | `fnx-dispatch` + `fnx-runtime` | backend registry, decision ledger | deterministic route selection + fail-closed ambiguity handling |
| Conversion/readwrite pipeline | `convert.py`, `readwrite/edgelist.py` | `fnx-convert` + `fnx-readwrite` | parser cursor, warnings, graph builder | deterministic conversion precedence + parse safety |
| Algorithm + conformance surface | `algorithms/*`, `tests/*` | `fnx-algorithms` + `fnx-conformance` | work queue, witness, mismatch vector, structured logs | deterministic output/tie-break + replay-forensics integrity |

### 18.2 Critical state transitions (explicit)

1. Graph store:
- `stable -> mutating` on any graph mutation request.
- `mutating -> stable` only after invariant checks pass.
- invariant failure -> `rollback -> fail_closed` (strict and hardened).
2. View cache:
- `cache_cold -> cache_hot` on first read.
- `cache_hot -> cache_stale` when parent revision changes.
- `cache_stale -> cache_hot` after deterministic rebuild and invariant pass; else `reset -> fail_closed`.
3. Dispatch:
- `registered -> resolved` when compatible backend exists and no unknown incompatible feature.
- `registered -> rejected` on incompatible/ambiguous route; always fail-closed.
4. Conversion/readwrite:
- `parsing -> parsed` for valid rows.
- `parsing -> recovered` only in hardened mode with bounded skip/warning.
- strict malformed row or hardened budget exhaustion -> fail-closed.
5. Conformance:
- `fixture_loaded -> executing -> validated` for zero-drift result.
- any mismatch -> failure report with deterministic replay command + forensics bundle references.

### 18.3 Invariant violation matrix and recovery policy

| Invariant family | Violation class | Strict mode | Hardened mode | Recovery behavior |
|---|---|---|---|---|
| Graph mutation invariants | adjacency asymmetry, revision drift | fail-closed | rollback then fail-closed with audit | restore last stable snapshot |
| View invariants | stale cache read, ordering mismatch | fail-closed | cache reset then fail-closed | force snapshot rebuild |
| Dispatch invariants | unknown incompatible feature, route ambiguity | fail-closed | fail-closed (diagnostics only) | deterministic decision ledger record |
| Conversion/readwrite invariants | malformed parse, precedence drift | fail-closed | bounded recovery then fail-closed | warning ledger + reproduction artifact |
| Conformance invariants | packet misrouting, replay metadata drift | fail-closed | fail-closed with forensic enrichment | regenerate logs and bundle index |

### 18.4 Method-stack evidence bindings

- Alien-uplift contract card:
  - EV score `2.45`, baseline comparator `legacy_networkx/main@python3.12`.
- Profile-first artifacts:
  - `artifacts/perf/BASELINE_BFS_V1.md`
  - `artifacts/perf/OPPORTUNITY_MATRIX.md`
  - `artifacts/perf/phase2c/bfs_neighbor_iter_delta.json`
- Decision-theoretic runtime contract:
  - states/actions/loss/fallback in `artifacts/docs/v1/doc_pass03_data_model_state_invariant_v1.json`.
- Isomorphism proof anchors:
  - `artifacts/proofs/ISOMORPHISM_PROOF_FNX_P2C_001_V1.md`
  - `artifacts/proofs/ISOMORPHISM_PROOF_FNX_P2C_005_V1.md`
  - `artifacts/proofs/ISOMORPHISM_PROOF_FNX_P2C_009_V1.md`
- Structured logging evidence:
  - `artifacts/conformance/latest/structured_logs.jsonl`
  - `artifacts/conformance/latest/structured_log_emitter_normalization_report.json`
  - `artifacts/phase2c/latest/phase2c_readiness_e2e_steps_v1.jsonl`

### 18.5 Legacy concurrency and ordering anchors (DOC-PASS-06)

NetworkX execution semantics for graph mutation and traversal are effectively single-threaded with live, non-snapshot views:
- Core mutation routines perform in-place dictionary mutation on shared adjacency maps (`legacy_networkx_code/networkx/networkx/classes/graph.py::add_edge`, `remove_node`; `legacy_networkx_code/networkx/networkx/classes/digraph.py::add_edge`, `remove_node`).
- Node/edge removal paths explicitly materialize key lists (`list(adj[n])`) to avoid runtime iterator invalidation (`legacy_networkx_code/networkx/networkx/classes/graph.py:693`, `legacy_networkx_code/networkx/networkx/classes/graph.py:748`, plus the corresponding warning patterns in `legacy_networkx_code/networkx/networkx/classes/digraph.py:522`, `638`, `775`).
- View objects are live wrappers over backing mappings (`legacy_networkx_code/networkx/networkx/classes/coreviews.py::AtlasView/AdjacencyView`, `legacy_networkx_code/networkx/networkx/classes/reportviews.py::NodeView/EdgeView`), so read order is inherited from current backing dict state.
- Dispatch lifecycle is globally shared and lazy-loaded (`legacy_networkx_code/networkx/networkx/utils/backends.py` globals `backends`, `backend_info`, `_loaded_backends`, and `_dispatchable`); route determinism depends on stable config and deterministic backend priority evaluation.
- Shortest-path traversal order inherits adjacency iteration order (`legacy_networkx_code/networkx/networkx/algorithms/shortest_paths/unweighted.py` loops on `for w in adj[v]`).
- Generator replay determinism requires explicit seed control (`legacy_networkx_code/networkx/networkx/generators/random_graphs.py`, `@py_random_state` entry points and `seed.*` calls).
- Read/write parsing is line-sequential and order-sensitive (`legacy_networkx_code/networkx/networkx/readwrite/edgelist.py::parse_edgelist`, `legacy_networkx_code/networkx/networkx/readwrite/adjlist.py::parse_adjlist`); concurrent parsing would alter warning and failure ordering unless canonicalized.

### 18.6 Concurrency/lifecycle hazard register for Rust parity

| Hazard surface | Legacy anchor | Regression risk if mishandled | Rust containment requirement |
|---|---|---|---|
| Mutation during neighbor/view iteration | `graph.py::remove_node`, `coreviews.py` / `reportviews.py` live iterators | non-deterministic neighbor/edge emission order; stale reads; panic-prone iterator invalidation equivalents | revision-gated snapshots for cached views; deterministic invalidation on every mutating commit; never expose partially-mutated adjacency |
| View cache refresh races | live-view model in `coreviews.py` + mutable dict backing in `graph.py`/`digraph.py` | serving cache built on prior revision; drift between strict/hardened outputs | enforce monotonic revision counter in `fnx-classes`; `fnx-views` callers must run `refresh_if_stale()` before consuming cached snapshots and treat unrefreshed stale reads as contract violations |
| Backend registry/config drift during dispatch | `utils/backends.py` global `backends`, `_loaded_backends`, backend-priority logic | route choice changes across runs for same inputs; compatibility drift masked as backend variance | freeze dispatch decision inputs per operation; preserve deterministic backend sort (`priority` desc then `name` asc); emit decision ledger with selected backend and policy IDs |
| Parser pipeline reordering | `parse_edgelist` / `parse_adjlist` line-ordered loops | warning ordering drift; different first-failure line; mismatched replay artifacts | preserve input-line order in strict and hardened modes; canonicalize warning emission ordering and include stable row indices |
| Seeded RNG object reuse across concurrent calls | `random_graphs.py` seeded `seed.random/choice/shuffle` surfaces | reproducibility loss and cross-scenario contamination | one RNG stream per scenario/test-id; explicit replay seed recorded in structured logs and e2e replay bundles |
| Durability/recovery state transition reentrancy | fail-closed state-machine contract in `fnx-runtime` + adapter gates | illegal post-terminal transitions; ambiguous recovery outcomes | transition guards must reject out-of-order events; terminal states immutable; transition log must remain append-only and reason-coded |

### 18.7 Required lifecycle and ordering parity checks

1. Mutate-then-iterate checks:
- after deterministic add/remove sequences, `neighbors()` / `adjacency()` / edge views must emit stable order matching fixture baselines.
2. View revision checks:
- cached view consumers must call `refresh_if_stale()` before reading `snapshot()`; stale-cache serving without refresh is forbidden and treated as a conformance failure.
3. Dispatch replay checks:
- identical input + mode + backend configuration must yield identical backend choice and identical decision-ledger payload.
4. Parser replay checks:
- malformed edgelist/adjlist/json fixtures must produce stable first-failure row IDs (strict) and stable warning vectors (hardened).
5. Seed replay checks:
- scenario reruns with same seed must regenerate identical generator edge sets and witness metadata.
6. Recovery transition checks:
- fail-closed terminal states in durability/recovery flows cannot transition back to active without explicit, audited restart semantics.

## 19. Error Taxonomy, Failure Modes, and Recovery Semantics (DOC-PASS-07)

### 19.1 Decision boundary and fail-closed law

Runtime guardrail (normative): `decision_theoretic_action(mode, p, unknown_feature)` in `crates/fnx-runtime/src/lib.rs:1140` decides `{allow, full_validate, fail_closed}` and forces `FailClosed` whenever `unknown_incompatible_feature=true`.

Operational consequence:
- strict mode defaults to immediate fail-closed for malformed or incompatible inputs across graph, dispatch, conversion, and read/write surfaces.
- hardened mode may perform bounded recovery (`warning + continue`) only where code paths explicitly allow it; unknown incompatible features still fail-closed.

### 19.2 Failure taxonomy matrix (trigger/impact/recovery)

| Failure family | Trigger + detection signal | User-facing semantics | Strict mode | Hardened mode | Recovery + evidence artifacts |
|---|---|---|---|---|---|
| Dispatch incompatibility | `unknown_incompatible_feature` or unsupported route in `BackendRegistry::resolve` (`crates/fnx-dispatch/src/lib.rs:103`) | `DispatchError::FailClosed` or `DispatchError::NoCompatibleBackend` | fail-closed | fail-closed | deterministic dispatch decision ledger entry with operation, mode, selected backend signal |
| Graph metadata incompatibility | edge attrs include `__fnx_incompatible*` in `Graph::add_edge_with_attrs` (`crates/fnx-classes/src/lib.rs:225`) and policy gate evaluates `decision_theoretic_action` (`crates/fnx-runtime/src/lib.rs:1146`) | either `GraphError::FailClosed` or accepted mutation with recorded `DecisionAction` | fail-closed when action resolves to `FailClosed`; otherwise allow/full-validate with ledger evidence | fail-closed for unknown incompatible feature; otherwise allow/full-validate according to loss-based policy | decision record must include incompatibility probability, action, and evidence terms; mutation only proceeds on non-fail-closed action |
| Conversion payload malformation | empty node IDs / malformed endpoints in `GraphConverter::{from_edge_list,from_adjacency}` (`crates/fnx-convert/src/lib.rs:136`) | `ConvertError::FailClosed` (strict) or warning stream in `ConvertReport.warnings` (hardened) | fail-closed | bounded skip + warning | preserve valid rows, emit warning ledger, continue deterministic conversion |
| Edgelist parse failure | malformed line/endpoint/attr pair in `EdgeListEngine::read_edgelist` and `decode_attrs` (`crates/fnx-readwrite/src/lib.rs:127`, `crates/fnx-readwrite/src/lib.rs:346`) | `ReadWriteError::FailClosed` (strict) or warnings (hardened) | fail-closed | bounded skip + warning | keep valid edges, collect warning fragments for conformance assertion |
| JSON graph parse/schema failure | invalid JSON or empty node/edge endpoint in `EdgeListEngine::read_json_graph` (`crates/fnx-readwrite/src/lib.rs:219`) | strict returns `ReadWriteError::FailClosed`; hardened returns empty graph + warning on parse errors | fail-closed | bounded recovery path for parse failure; malformed elements skipped with warnings | return deterministic empty graph for malformed top-level JSON, preserve parse warning and ledger decision |
| Generator parameter abuse | `n > max_allowed` / `p` outside `[0,1]` in `GraphGenerator::{validate_n,validate_probability}` (`crates/fnx-generators/src/lib.rs:225`) | `GenerationError::FailClosed` or hardened clamp warning | fail-closed | clamp + warning when explicitly allowlisted; otherwise fail-closed | bounded clamping with rationale signal, or immediate fail-closed on strict/high-risk |
| Artifact sync integrity failure | unsupported capability, cursor regression, retry exhaustion, checksum mismatch in `AsupersyncAdapterMachine` (`crates/fnx-runtime/src/lib.rs:245`) | terminal `FailedClosed` state with reason codes (`UnsupportedCapability`, `ConflictDetected`, `RetryExhausted`, etc.) | fail-closed | fail-closed | deterministic transition log + reason code chain; no post-terminal transitions |
| Structured log contract violations | missing required fields (`reason_code`, replay metadata, forensic bundle links) in `StructuredTestLog::validate` (`crates/fnx-runtime/src/lib.rs:782`) | validation `Err(String)`; conformance gating failure | fail-closed | fail-closed | reject artifact; regenerate telemetry row with full canonical field set |
| Conformance behavior drift | fixture mismatches/warning expectation misses in `execute_fixture` (`crates/fnx-conformance/src/lib.rs:824`) | `FixtureReport { passed=false, reason_code=\"mismatch\" }` | fail gate | fail gate | emit mismatch taxonomy + deterministic replay command + forensics bundle index |

### 19.3 User-facing error semantics by crate boundary

| Boundary | Primary external surface | Error/warning contract | Recovery contract |
|---|---|---|---|
| `fnx-classes` | graph mutation APIs | returns `GraphError::FailClosed` on incompatible edge metadata | no silent mutation; edge add aborted, node/edge ordering remains deterministic |
| `fnx-dispatch` | backend route resolution | returns `DispatchError::{FailClosed,NoCompatibleBackend}` with operation context | deterministic backend fallback is never implicit; caller must handle explicit failure |
| `fnx-convert` | edge-list/adjacency ingestion | strict returns `ConvertError::FailClosed`; hardened records warnings for skipped malformed records | bounded row-skip recovery only; malformed data never rewritten into strict output |
| `fnx-readwrite` | edgelist/json parse+serialize | strict fail-closed on malformed input; hardened keeps valid subset and reports warning fragments | parser warnings are first-class outputs and must flow to conformance comparisons |
| `fnx-generators` | graph family constructors | strict rejects invalid `n`/`p`; hardened may clamp with warning depending on risk action | clamping is deterministic and logged; overflow/resource-amplification requests can still fail-closed |
| `fnx-runtime` | policy + telemetry + sync state machine | explicit reason-coded fail-closed transitions; structured log schema validation errors are hard failures | transition/telemetry contracts enforce reproducible replay metadata and forensic bundle integrity |
| `fnx-conformance` | fixture and gate execution | mismatch taxonomy + `reason_code` + packet-level replay command | gate failure is non-recovering in-run; recovery is rerun after fixture or implementation correction |

### 19.4 Recovery escalation workflow (deterministic)

1. Detect category:
- parse/validation failure, compatibility-route failure, state-machine integrity failure, or parity mismatch.
2. Apply mode policy:
- strict: immediate fail-closed return.
- hardened: attempt only explicitly coded bounded recovery; otherwise fail-closed.
3. Persist forensic evidence:
- decision ledger entry, warning list, mismatch taxonomy, replay command, and forensics bundle index.
4. Enforce gate outcomes:
- any strict mismatch, missing telemetry contract field, or fail-closed terminal condition is a release blocker until artifact-corrected rerun passes.

### 19.5 Security/compatibility undefined-zone register (DOC-PASS-08)

| Edge case / undefined zone | Legacy anchor | Strict-mode policy | Hardened-mode policy | Port rationale |
|---|---|---|---|---|
| Hashable-but-mutable node identity (hash/equality drift after insertion) | `legacy_networkx_code/networkx/networkx/classes/graph.py:565-570`, `digraph.py:480-484` | fail-closed on detected identity instability or incompatible key semantics | fail-closed (no recovery path) | silent key drift corrupts adjacency identity and invalidates replay determinism |
| `None` node admission attempt | `graph.py:574-575`, `graph.py:969-975`, `digraph.py:489-490`, `digraph.py:729-736` | fail-closed with explicit node constraint violation | fail-closed | parity with legacy hard rejection and prevents ambiguous sentinel behavior |
| Mutation while iterating live adjacency/views | `graph.py:693`, `graph.py:748`, `coreviews.py` + `reportviews.py` live wrappers | fail-closed or rollback on invariant breach | bounded rollback, then fail-closed if invariants remain violated | prevents stale-view and ordering drift regressions |
| MultiGraph implicit key allocation after removals (non-contiguous key reuse behavior) | `legacy_networkx_code/networkx/networkx/classes/multigraph.py::new_edge_key`, `multidigraph.py::add_edge/remove_edge` | preserve deterministic key-allocation contract; fail on incompatible key shape | preserve contract; no heuristic key rewrite | edge-key drift breaks observable multiedge semantics and fixture parity |
| Backend ambiguity / unsupported backend conversion path | `legacy_networkx_code/networkx/networkx/utils/backends.py` (`_dispatchable`, `_can_convert`, multi-backend path) | fail-closed with deterministic route evidence | fail-closed | backend-route ambiguity is compatibility-critical, not recoverable input noise |
| Adjacency-list delimiter collisions with whitespace-rich node labels | `legacy_networkx_code/networkx/networkx/readwrite/adjlist.py:85-86`, `144-145` | fail-closed when strict parse contract cannot unambiguously decode labels | bounded warning only when canonical delimiter policy is explicitly allowlisted | avoids silent node relabeling / edge rewiring through ambiguous parsing |
| Edgelist attribute literal parsing failures / malformed attribute payloads | `legacy_networkx_code/networkx/networkx/readwrite/edgelist.py:239`, `275` | fail-closed with row-level parse reason | bounded skip + warning budget; fail-closed when budget exceeded | hardened recovery is allowed only for syntactic row-local faults with full warning telemetry |
| Algorithm tie-break ambiguity from implicit ordering/hashes | `legacy_networkx_code/networkx/networkx/algorithms/shortest_paths/unweighted.py`, `legacy_networkx_code/networkx/networkx/algorithms/shortest_paths/astar.py:112` | require deterministic tie policy and witness fields; fail on missing tie metadata | same deterministic policy; no random tie resolution | protects observable ordering contracts and replay-isomorphism proofs |

### 19.6 Hardened-mode rationale boundaries

Hardened mode is not “best effort”; it is bounded recovery under explicit policy:
1. Allowed bounded recovery:
- row-local parse anomalies (edgelist/adjlist/json) with deterministic warning emission and preserved valid subset.
- numeric parameter clamping only where allowlisted by policy (`n`, `p` bounds) and only with explicit rationale fields.
2. Disallowed recovery (always fail-closed):
- unknown incompatible features, backend route ambiguity, telemetry contract/schema violations, and illegal state-machine transitions.
- identity/ordering integrity violations that would invalidate parity witnesses.
3. Audit requirements:
- every hardened recovery must emit policy ID, reason code, replay command, and artifact links.
- any recovery path without deterministic forensic outputs is treated as a gate failure.

## 20. Unit/E2E Test Corpus and Logging Evidence Crosswalk (DOC-PASS-09)

### 20.1 Canonical crosswalk schema

Required columns for every crosswalk row:
- `crosswalk_id`
- `behavior_or_invariant`
- `packet_id`
- `owning_bead`
- `unit_property_assets`
- `differential_fixture_assets`
- `e2e_script_assets`
- `required_structured_log_fields`
- `artifact_bundle_paths`
- `replay_command_template`
- `coverage_status`

### 20.2 Machine-parsable behavior-to-verification matrix

```csv
crosswalk_id,behavior_or_invariant,packet_id,owning_bead,unit_property_assets,differential_fixture_assets,e2e_script_assets,required_structured_log_fields,artifact_bundle_paths,replay_command_template,coverage_status
XW-001,"graph adjacency integrity + deterministic mutation ordering",FNX-P2C-001,bd-315.12.1,"crates/fnx-classes/src/lib.rs::add_edge_autocreates_nodes_and_preserves_order|neighbors_iter_preserves_deterministic_order|strict_mode_fails_closed_for_unknown_incompatible_feature","crates/fnx-conformance/fixtures/graph_core_mutation_hardened.json|crates/fnx-conformance/fixtures/generated/conformance_harness_strict.json","scripts/e2e/run_happy_path.sh|scripts/e2e/run_edge_path.sh","schema_version|run_id|suite_id|packet_id|test_id|mode|status|reason_code|replay_command|forensic_bundle_id|forensics_bundle_index.bundle_hash_id|artifact_refs|env_fingerprint","artifacts/conformance/latest/smoke_report.json|artifacts/conformance/latest/structured_logs.jsonl|artifacts/conformance/latest/structured_logs.json","CARGO_TARGET_DIR=target-codex cargo run -q -p fnx-conformance --bin run_smoke -- --fixture graph_core_mutation_hardened.json --mode hardened",covered
XW-002,"view cache staleness invalidation + ordering parity",FNX-P2C-002,bd-315.24.11,"crates/fnx-views/src/lib.rs::live_view_observes_graph_mutations|cached_snapshot_refreshes_on_revision_change|view_preserves_deterministic_ordering","crates/fnx-conformance/fixtures/generated/view_neighbors_strict.json","scripts/e2e/run_cross_packet_golden.sh","schema_version|packet_id|test_id|mode|status|replay_command|forensic_bundle_id|artifact_refs|env_fingerprint","artifacts/conformance/latest/smoke_report.json|artifacts/phase2c/latest/phase2c_readiness_e2e_steps_v1.jsonl","CARGO_TARGET_DIR=target-codex cargo run -q -p fnx-conformance --bin run_smoke -- --fixture generated/view_neighbors_strict.json --mode strict",partial
XW-003,"dispatch deterministic backend selection + fail-closed incompatibility handling",FNX-P2C-008,bd-315.19.1,"crates/fnx-dispatch/src/lib.rs::strict_mode_rejects_unknown_incompatible_request|hardened_mode_uses_validation_action_for_moderate_risk|deterministic_priority_selects_highest_then_name","crates/fnx-conformance/fixtures/generated/dispatch_route_strict.json","scripts/e2e/run_cross_packet_golden.sh","schema_version|packet_id|test_id|mode|status|reason_code|replay_command|forensic_bundle_id|artifact_refs","artifacts/conformance/latest/smoke_report.json|artifacts/conformance/latest/structured_log_emitter_normalization_report.json","CARGO_TARGET_DIR=target-codex cargo run -q -p fnx-conformance --bin run_smoke -- --fixture generated/dispatch_route_strict.json --mode strict",covered
XW-004,"conversion precedence + malformed payload handling (strict fail-closed / hardened warning)",FNX-P2C-004,bd-315.15.5,"crates/fnx-convert/src/lib.rs::edge_list_conversion_is_deterministic|strict_mode_fails_closed_for_malformed_edge|hardened_mode_skips_malformed_and_keeps_good_edges","crates/fnx-conformance/fixtures/generated/convert_edge_list_strict.json","scripts/e2e/run_malformed_input.sh|scripts/e2e/run_happy_path.sh","schema_version|packet_id|test_id|mode|status|reason_code|replay_command|forensic_bundle_id|forensics_bundle_index.bundle_id|artifact_refs","artifacts/conformance/latest/smoke_report.json|artifacts/conformance/latest/structured_logs.jsonl","CARGO_TARGET_DIR=target-codex cargo run -q -p fnx-conformance --bin run_smoke -- --fixture generated/convert_edge_list_strict.json --mode strict",partial
XW-005,"readwrite round-trip determinism + malformed edgelist/json recovery policy",FNX-P2C-004,bd-315.15.6,"crates/fnx-readwrite/src/lib.rs::round_trip_is_deterministic|strict_mode_fails_closed_for_malformed_line|hardened_mode_keeps_valid_lines_with_warnings|strict_mode_fails_closed_for_malformed_json|hardened_mode_warns_and_recovers_for_malformed_json","crates/fnx-conformance/fixtures/generated/readwrite_roundtrip_strict.json|crates/fnx-conformance/fixtures/generated/readwrite_json_roundtrip_strict.json|crates/fnx-conformance/fixtures/generated/readwrite_hardened_malformed.json","scripts/e2e/run_malformed_input.sh|scripts/e2e/run_edge_path.sh","schema_version|packet_id|test_id|mode|status|reason_code|replay_command|forensic_bundle_id|forensics_bundle_index.replay_ref|artifact_refs|env_fingerprint","artifacts/conformance/latest/smoke_report.json|artifacts/conformance/latest/structured_logs.json|artifacts/conformance/latest/telemetry_dependent_unblock_matrix_v1.json","CARGO_TARGET_DIR=target-codex cargo run -q -p fnx-conformance --bin run_smoke -- --fixture generated/readwrite_hardened_malformed.json --mode hardened",covered
XW-006,"shortest-path deterministic output + complexity witness integrity",FNX-P2C-005,bd-315.16,"crates/fnx-algorithms/src/lib.rs::bfs_shortest_path_uses_deterministic_neighbor_order|returns_none_when_nodes_are_missing","crates/fnx-conformance/fixtures/graph_core_shortest_path_strict.json","scripts/e2e/run_edge_path.sh","schema_version|packet_id|test_id|mode|status|replay_command|forensic_bundle_id|artifact_refs|env_fingerprint","artifacts/conformance/latest/smoke_report.json|artifacts/perf/BASELINE_BFS_V1.md|artifacts/perf/phase2c/bfs_neighbor_iter_delta.json","CARGO_TARGET_DIR=target-codex cargo run -q -p fnx-conformance --bin run_smoke -- --fixture graph_core_shortest_path_strict.json --mode strict",partial
XW-007,"connected-components + centrality parity (degree/closeness) with deterministic ordering",FNX-P2C-007,bd-315.18.5,"crates/fnx-algorithms/src/lib.rs::connected_components_are_deterministic_and_partitioned|number_connected_components_matches_components_len|degree_centrality_matches_expected_values_and_order|closeness_centrality_matches_expected_values_and_order","crates/fnx-conformance/fixtures/generated/components_connected_strict.json|crates/fnx-conformance/fixtures/generated/centrality_degree_strict.json|crates/fnx-conformance/fixtures/generated/centrality_closeness_strict.json","scripts/e2e/run_cross_packet_golden.sh","schema_version|packet_id|test_id|mode|status|reason_code|replay_command|forensic_bundle_id|artifact_refs","artifacts/conformance/latest/smoke_report.json|artifacts/conformance/latest/structured_logs.jsonl","CARGO_TARGET_DIR=target-codex cargo run -q -p fnx-conformance --bin run_smoke -- --fixture generated/centrality_closeness_strict.json --mode strict",partial
XW-008,"generator determinism + hardened guardrails for resource/parameter abuse",FNX-P2C-007,bd-315.18.5,"crates/fnx-generators/src/lib.rs::cycle_graph_edge_order_matches_networkx_for_n_five|gnp_random_graph_is_seed_reproducible|strict_mode_fails_for_invalid_probability|hardened_mode_clamps_invalid_probability_with_warning","crates/fnx-conformance/fixtures/generated/generators_path_strict.json|crates/fnx-conformance/fixtures/generated/generators_cycle_strict.json|crates/fnx-conformance/fixtures/generated/generators_complete_strict.json","scripts/e2e/run_happy_path.sh|scripts/e2e/run_adversarial_soak.sh","schema_version|packet_id|test_id|mode|status|reason_code|replay_command|forensic_bundle_id|artifact_refs","artifacts/conformance/latest/smoke_report.json|artifacts/phase2c/latest/phase2c_adversarial_manifest_v1.json","CARGO_TARGET_DIR=target-codex cargo run -q -p fnx-conformance --bin run_smoke -- --fixture generated/generators_cycle_strict.json --mode strict",partial
XW-009,"structured logging schema + replay/forensics contract + asupersync fail-closed state machine",FNX-P2C-008,bd-315.26.4,"crates/fnx-runtime/src/lib.rs::structured_test_log_validates_passed_record|structured_test_log_failed_requires_repro_seed_or_fixture|structured_test_log_skipped_requires_reason_code|asupersync_adapter_checksum_mismatch_is_fail_closed_and_audited|asupersync_adapter_retry_budget_exhaustion_fault_injection_is_fail_closed","crates/fnx-conformance/tests/structured_log_gate.rs|crates/fnx-conformance/tests/asupersync_adapter_state_machine_gate.rs|crates/fnx-conformance/tests/asupersync_fault_injection_gate.rs","scripts/run_e2e_script_pack.py|scripts/run_phase2c_readiness_e2e.sh","schema_version|run_id|suite_id|packet_id|test_id|mode|status|reason_code|failure_repro|replay_command|forensic_bundle_id|forensics_bundle_index.bundle_hash_id|forensics_bundle_index.replay_ref|artifact_refs|env_fingerprint|e2e_step_traces","artifacts/conformance/latest/structured_logs.jsonl|artifacts/conformance/latest/structured_log_emitter_normalization_report.json|artifacts/conformance/latest/telemetry_dependent_unblock_matrix_v1.json","cargo test -p fnx-conformance structured_log_gate -- --nocapture",covered
XW-010,"RaptorQ sidecar generation/scrub/decode proof for long-lived evidence bundles",FNX-P2C-009,bd-315.26,"crates/fnx-durability/src/lib.rs::sidecar_generation_and_scrub_recovery_work|decode_drill_emits_recovered_output|crates/fnx-conformance/tests/phase2c_packet_readiness_gate.rs::topology_and_packet_artifacts_are_complete_and_decode_proof_enforced","crates/fnx-conformance/fixtures/generated/adversarial_regression_bundle_v1.json","scripts/run_conformance_with_durability.sh|scripts/e2e/run_adversarial_soak.sh","schema_version|packet_id|test_id|mode|status|reason_code|replay_command|forensic_bundle_id|artifact_refs","artifacts/conformance/latest/structured_logs.raptorq.json|artifacts/conformance/latest/structured_logs.recovered.json|artifacts/phase2c/FNX-P2C-009","cargo test -p fnx-durability -- --nocapture",partial
```

### 20.3 Explicit coverage gaps, priority, and closure mapping

| Gap ID | Impacted crosswalk IDs | Priority | Linked bead IDs | Closure criteria |
|---|---|---|---|---|
| GAP-01 | `XW-001`, `XW-002`, `XW-004`, `XW-005` | P1 | `bd-315.23` | add property/invariant families and flake budgets for graph/view/convert/readwrite; wire into reliability gate outputs |
| GAP-02 | `XW-006`, `XW-007`, `XW-008` | P0 | `bd-315.16`, `bd-315.18.6`, `bd-315.18.7` | extend differential/metamorphic/adversarial coverage for weighted shortest-path and centrality/generator families; emit mismatch taxonomy with replay artifacts |
| GAP-03 | `XW-009` | P1 | `bd-315.26.4` | complete deterministic e2e recovery scenarios for interruption/resume/conflict/checksum mismatch with decode-proof-linked logs |
| GAP-04 | `XW-010` | P1 | `bd-315.26` | route all long-lived artifact classes through asupersync + durability pipeline; enforce scrub/decode proofs in packet readiness gates |
| GAP-05 | `XW-001..XW-010` | P1 | `bd-315.10.1`, `bd-315.10` | gate mapping is codified in `artifacts/conformance/v1/ci_gate_topology_v1.json` + schema/test lock; remaining closure is wiring full automated CI execution for every gate command path |

### 20.4 Canonical replay command templates

- Conformance fixture replay template:
  - `CARGO_TARGET_DIR=target-codex cargo run -q -p fnx-conformance --bin run_smoke -- --fixture <fixture_name> --mode <strict|hardened>`
- E2E script-pack replay template:
  - `python3 scripts/run_e2e_script_pack.py --scenario <scenario_id> --emit-json`
- Packet readiness replay template:
  - `bash scripts/run_phase2c_readiness_e2e.sh`

## 21. Coverage/Flake Budgets and Reliability Gate Baseline (bd-315.23)

### 21.1 Reliability budget matrix (packet-family SLOs)

| Budget ID | Packet family scope | Unit line floor | Branch floor | Property invariant floor | E2E replay pass floor | Flake ceiling (7d) | Runtime guardrail | Evidence artifacts | Primary gate command (offloaded) |
|---|---|---:|---:|---:|---:|---:|---|---|---|
| `REL-BUD-001` | core graph + view (`FNX-P2C-001`, `FNX-P2C-002`) | 90% | 80% | 5 families | 100% | 0.50% | p95 <= baseline + 10% | `artifacts/conformance/latest/smoke_report.json`, `artifacts/conformance/latest/structured_logs.jsonl` | `rch exec -- cargo test -q -p fnx-conformance --test smoke -- --nocapture` |
| `REL-BUD-002` | convert/readwrite (`FNX-P2C-004`) | 90% | 80% | 5 families | 100% | 0.50% | p95 <= baseline + 10% | `artifacts/conformance/latest/generated_convert_edge_list_strict_json.report.json`, `artifacts/conformance/latest/generated_readwrite_roundtrip_strict_json.report.json` | `rch exec -- cargo test -q -p fnx-conformance --bin run_smoke -- --nocapture` |
| `REL-BUD-003` | shortest-path critical (`FNX-P2C-005`) | 92% | 82% | 6 families | 100% | 0.25% | p99 <= baseline + 10% | `artifacts/perf/BASELINE_BFS_V1.md`, `artifacts/perf/phase2c/perf_regression_gate_report_v1.json` | `rch exec -- cargo test -q -p fnx-algorithms -- --nocapture` |
| `REL-BUD-004` | centrality + generators (`FNX-P2C-007`) | 90% | 80% | 5 families | 100% | 0.50% | p95 <= baseline + 10% | `artifacts/conformance/latest/generated_centrality_degree_strict_json.report.json`, `artifacts/conformance/latest/generated_generators_cycle_strict_json.report.json` | `rch exec -- cargo test -q -p fnx-conformance --test phase2c_packet_readiness_gate -- --nocapture` |
| `REL-BUD-005` | runtime/dispatch/log schema (`FNX-P2C-008`) | 92% | 85% | 6 families | 100% | 0.25% | fail-closed telemetry contract | `artifacts/conformance/latest/structured_log_emitter_normalization_report.json`, `artifacts/conformance/latest/telemetry_dependent_unblock_matrix_v1.json` | `rch exec -- cargo test -q -p fnx-conformance --test structured_log_gate -- --nocapture` |
| `REL-BUD-006` | conformance + durability lifecycle (`FNX-P2C-009`) | 90% | 80% | 4 families | 100% | 0.50% | decode-proof required | `artifacts/conformance/latest/structured_logs.raptorq.json`, `artifacts/conformance/latest/structured_logs.recovered.json`, `artifacts/phase2c/latest/phase2c_readiness_e2e_report_v1.json` | `rch exec -- cargo test -q -p fnx-conformance --test phase2c_packet_readiness_gate -- --nocapture` |

### 21.2 Flake detection and quarantine policy

| Policy key | Rule | Trigger | Action | Required artifact |
|---|---|---|---|---|
| `FLK-DET-001` | classify flaky when first failure passes on immediate deterministic rerun | fail -> pass sequence on same `test_id` + `packet_id` + `mode` | mark as flaky event, increment rolling flake counter | `artifacts/conformance/latest/structured_logs.jsonl` with shared replay metadata |
| `FLK-DET-002` | warn threshold | rolling flake rate `> 0.25%` and `<= 1.00%` | soft warning in gate summary with top offending test groups | `artifacts/conformance/latest/logging_final_gate_report_v1.json` |
| `FLK-DET-003` | hard-fail threshold | rolling flake rate `> 1.00%` | fail reliability gate and emit explicit budget breach | `artifacts/conformance/latest/smoke_report.json` + budget breach report |
| `FLK-QUA-001` | quarantine admission | same test flakes >= 3 times in 24h | move test to quarantine roster; block release path until owner assigned | `artifacts/conformance/latest/flake_quarantine_v1.json` (to be generated by gate automation bead) |
| `FLK-QUA-002` | quarantine exit | 20 consecutive deterministic passes with zero flakes | auto-remove from quarantine and close incident | `artifacts/conformance/latest/flake_quarantine_v1.json` + pass streak ledger |

### 21.3 CI failure envelope contract (budget-specific remediation)

Every reliability gate failure must emit a machine-readable envelope with:
- `budget_id`
- `packet_scope`
- `observed_value`
- `threshold_value`
- `status` (`warn` or `fail`)
- `failing_test_groups` (stable test IDs)
- `artifact_paths` (primary evidence refs)
- `replay_commands` (one-command reproduction)
- `owner_bead_id`
- `remediation_hint`

Normative output behavior:
- failure text must name the exact `budget_id` and include direct artifact/replay pointers.
- no generic “tests failed” output is acceptable for reliability gates.

### 21.4 Closure linkage for bd-315.23 dependents

| Dependent bead family | Reliability dependency unlocked by this baseline | Remaining closure step |
|---|---|---|
| `bd-315.12.5`, `bd-315.13.5`, `bd-315.14.5`, `bd-315.15.5`, `bd-315.16.5`, `bd-315.17.5`, `bd-315.18.5`, `bd-315.19.5`, `bd-315.20.5` | packet-level unit/property reliability budgets are now explicit and packet-scoped | implement budget evaluator + flake/quarantine artifact emission in CI gate topology (`bd-315.10`) |
| `bd-315.10`, `bd-315.10.1` | gate-level budget IDs and envelope schema are now specified | wire automated checks so failures print budget-specific remediation hints from schema fields |
| `bd-315.11` | readiness drill now has explicit reliability SLO set and flake thresholds | run full readiness drill with budget breach report and quarantine ledger outputs |

## 22. CI Gate Topology Contract Matrix (bd-315.10.1)

Canonical machine-checkable assets:
- `artifacts/conformance/v1/ci_gate_topology_v1.json`
- `artifacts/conformance/schema/v1/ci_gate_topology_schema_v1.json`
- `crates/fnx-conformance/tests/ci_gate_topology_gate.rs`

### 22.1 Deterministic gate order and fail-closed short-circuit

1. Ordered topology: `G1 -> G2 -> G3 -> G4 -> G5 -> G6 -> G7 -> G8`.
2. Every gate is explicitly blocking and release-critical.
3. Short-circuit policy: first failing gate halts all downstream gates and emits policy/budget linked failure envelope fields (`budget_id`, replay command, artifact refs, owner bead linkage).
4. Override policy remains explicit and auditable (`CI-POL-OVERRIDE-001`), never implicit.

### 22.2 Compatibility/security drift policy IDs

| Drift rule ID | Domain | Deterministic threshold | Violation action |
|---|---|---|---|
| `DRIFT-COMPAT-STRICT-000` | compatibility | strict critical drift must equal `0` | fail-closed |
| `DRIFT-COMPAT-HARDENED-001` | compatibility | hardened allowlisted divergence must remain `<= 1.00%` | fail-closed when exceeded |
| `DRIFT-SEC-INVARIANT-000` | security | zero tolerance for unsafe/unknown-incompatible behavior | fail-closed |
| `DRIFT-TELEMETRY-CONTRACT-000` | security/telemetry | zero missing replay-critical fields | fail-closed |
| `DRIFT-DURABILITY-DECODE-000` | durability | decode-proof artifacts required for recovery paths | fail-closed |

### 22.3 Gate I/O contract summary

| Gate | Input contract family | Output artifact family | Policy + budget linkage |
|---|---|---|---|
| `G1` | workspace manifests + lint surfaces | lint diagnostics | fail-closed + security drift |
| `G2` | unit/integration test targets | smoke + structured logs | fail-closed + compatibility drift (`REL-BUD-001/002`) |
| `G3` | differential fixtures + oracle capture | parity fixture reports | fail-closed + compatibility drift |
| `G4` | adversarial/property harness + telemetry gates | normalization + unblock matrix | fail-closed + security drift |
| `G5` | e2e script-pack + scenario matrix contracts | e2e gate reports + replay logs | fail-closed + envelope policy |
| `G6` | perf/isomorphism harnesses | perf regression + isomorphism reports | fail-closed + compatibility drift (`REL-BUD-003/004`) |
| `G7` | reliability schema/spec + validator | reliability report + gate validation artifact | fail-closed + envelope policy (`REL-BUD-001..006`) |
| `G8` | durability pipeline + packet readiness contract | durability report + recovered artifacts/decode proof linkage | fail-closed + durability policy |

## 23. Structure Specialist Review Artifact (bd-315.24.15)

### 23.1 Review scope and correction log

Pass-A structure specialist sweep focused on sections `18-22` and cross-doc alignment with `EXISTING_NETWORKX_STRUCTURE.md`.

Corrections/enrichments applied:
1. Added explicit concurrency/lifecycle legacy anchors and Rust hazard containment matrix (`18.5`, `18.6`, `18.7`).
2. Added explicit undefined-zone and hardened-rationale boundaries for security/compatibility edge behavior (`19.5`, `19.6`).
3. Verified CI topology contract section remains consistent with gate artifacts and gate tests after closure of `bd-315.10` (`section 22`).

### 23.2 Section-level confidence annotations

| Section | Focus | Confidence | Justification |
|---|---|---|---|
| `18` | data model, lifecycle, ordering, hazard containment | High | includes direct legacy path anchors + Rust containment obligations + parity checks |
| `19` | fail-closed taxonomy, undefined zones, hardened boundaries | High | strict/hardened split is explicit and tied to concrete failure surfaces |
| `20` | crosswalk matrix and gap register | Medium-High | matrix is explicit and machine-parsable; some rows remain `partial` pending packet closure |
| `21` | reliability/flake budgets and closure linkage | High | budget IDs, envelope fields, and gate linkage are explicit and reproducible |
| `22` | CI G1..G8 topology contract | High | artifact/schema/test triad is locked and recently re-validated |

### 23.3 Outstanding structural follow-ups

1. As packet implementation beads close, upgrade `partial` crosswalk rows to `covered` and refresh confidence for section `20`.
2. Expand section-level backlinks from this doc to `EXISTING_NETWORKX_STRUCTURE.md` sections `17-20` for tighter reviewer traversal.

## 24. Complexity/Performance/Memory Characterization Contract (DOC-PASS-05)

DOC-PASS-05 is now codified as a machine-auditable artifact set:

- `artifacts/docs/v1/doc_pass05_complexity_perf_memory_v1.json`
- `artifacts/docs/v1/doc_pass05_complexity_perf_memory_v1.md`
- `artifacts/docs/schema/v1/doc_pass05_complexity_perf_memory_schema_v1.json`
- `scripts/generate_doc_pass05_complexity_perf_memory.py`
- `scripts/validate_doc_pass05_complexity_perf_memory.py`
- `scripts/run_doc_pass05_complexity_perf_memory.sh`
- `crates/fnx-conformance/tests/doc_pass05_complexity_perf_memory_gate.rs`

### 24.1 Family-level envelope summary

Artifact summary (`characterization_summary`) currently reports:

- `family_count = 6`
- `operation_count = 20`
- `high_risk_operation_count = 13`
- `hotspot_hypothesis_count = 8`
- `optimization_risk_note_count = 20`

Family distribution:

| Family ID | Operation Count | High-Risk Ops | Dominant Runtime Envelope | Dominant Memory Growth Driver |
|---|---:|---:|---|---|
| `graph_storage_semantics` | 4 | 2 | `O(1)` mutation; `O(deg(v))` adjacency operations | node/adjacency map expansion and neighbor materialization |
| `algorithmic_core` | 4 | 3 | `O(V+E)` traversals; `O(V*(V+E))` for closeness | frontier/visited maps and all-source traversal accumulation |
| `generator_workloads` | 3 | 1 | `O(V)` / `O(V^2)` depending on topology density | dense edge materialization and seeded edge sampling state |
| `conversion_and_io` | 5 | 4 | `O(V+E)` / `O(L)` parse-and-build pipelines | parser token buffers, warning queues, graph builder state |
| `dispatch_runtime_policy` | 2 | 1 | `O(B*F)` backend filtering + `O(1)` runtime policy decisions | candidate backend sets and decision ledger records |
| `conformance_execution` | 2 | 2 | `O(F*(V+E))` harness sweeps and fixture replay | mismatch vectors, witness bundles, structured log payloads |

### 24.2 Hotspot hypotheses (explicit + testable)

DOC-PASS-05 records eight testable hotspot hypotheses (`HS-001..HS-008`) tied to concrete operation IDs and expected observable signals:

| Hypothesis | Operation ID | Testable Expected Signal |
|---|---|---|
| `HS-001` | `algo_shortest_path_unweighted` | queue push/pop hotspots exceed 30% inclusive CPU time |
| `HS-002` | `algo_connected_components` | visited-state allocations dominate retained bytes at p99 |
| `HS-003` | `algo_closeness_centrality` | one-lever memoization lowers p95 with parity unchanged |
| `HS-004` | `rw_read_edgelist` | malformed-row branch cost exceeds nominal parse path on adversarial fixtures |
| `HS-005` | `convert_from_adjacency` | fan-out-heavy payloads show superlinear allocation peaks without pre-sizing |
| `HS-006` | `gen_gnp_random_graph` | edge-sampling loop dominates runtime above density threshold |
| `HS-007` | `dispatch_backend_resolve` | resolve latency scales linearly with backend and feature cardinality |
| `HS-008` | `conformance_run_fixture` | log serialization + mismatch formatting dominate post-execution time |

Each hypothesis is evidence-linked to performance and replay artifacts and mapped to closure-related beads (notably `bd-315.24.6`, `bd-315.8.1`, `bd-315.8.2`, `bd-315.8.4`, `bd-315.6`, `bd-315.10`).

### 24.3 Optimization risk note binding to parity constraints

Every operation in DOC-PASS-05 is bound to at least one explicit optimization risk note (`risk::<operation_id>`), with:

1. A parity constraint lifted directly from operation-level deterministic behavior requirements.
2. Allowed one-lever optimization classes only (allocation pre-sizing, branch hoisting, single-lever data-structure tuning).
3. Forbidden changes that would induce semantic drift:
   - non-deterministic iteration/tie-break behavior,
   - strict/hardened policy collapse,
   - output-schema mutation without contract updates.
4. A fail-closed rollback trigger:
   - any strict-mode parity mismatch, or
   - missing replay metadata in gate outputs.

This section is the explicit linkage requested by `bd-315.24.6` acceptance criteria: optimization risk notes are now concretely attached to behavior-parity constraints rather than left as narrative guidance.

### 24.4 Verification and gate linkage

The DOC-PASS-05 run path and gate linkage are now deterministic and reproducible:

1. `./scripts/run_doc_pass05_complexity_perf_memory.sh`
2. `rch exec -- cargo test -q -p fnx-conformance --test doc_pass05_complexity_perf_memory_gate -- --nocapture`
3. `rch exec -- cargo check --workspace --all-targets`
4. `rch exec -- cargo clippy --workspace --all-targets -- -D warnings`
5. `cargo fmt --check`

This closes DOC-PASS-05 and unblocks `bd-315.24.12` and its downstream pass-B expansion chain (`bd-315.24.13`, `bd-315.24.16`, `bd-315.24.17`).

## 25. Pass-B Expansion: Source-Anchored Behavioral Contract and Risk Topology (DOC-PASS-11)

This section is the explicit Pass-B deepening layer for `bd-315.24.12`: it binds concrete crate entry points, failure semantics, and evidence obligations into one execution-facing map that downstream reviewers can audit without reopening archaeology notes.

### 25.1 Crate execution map (source-anchored)

| Crate | Primary source anchors | Normal-path contract | Edge/adversarial contract | Required evidence/logging linkage |
|---|---|---|---|---|
| `fnx-classes` | `crates/fnx-classes/src/lib.rs:71-170`, `crates/fnx-classes/src/lib.rs:172-334` | deterministic graph storage and ordered traversal via insertion-ordered maps/sets; revision increments on mutating change | edge mutation routes through decision-theoretic guard; unknown incompatible attrs force fail-closed while non-terminal actions may allow/full-validate with evidence | decision records in graph `EvidenceLedger`; crosswalk coverage in section `20` rows `XW-001`/`XW-005` |
| `fnx-runtime` | `crates/fnx-runtime/src/lib.rs:758-930`, `crates/fnx-runtime/src/lib.rs:1061-1172` | canonical structured test telemetry schema and decision-theoretic policy action selection | missing replay/forensics metadata or schema drift is validation-fatal; unknown incompatible feature bit is immediate `FailClosed` | `artifacts/conformance/latest/structured_logs.jsonl`, `artifacts/conformance/latest/structured_log_emitter_normalization_report.json` |
| `fnx-dispatch` | `crates/fnx-dispatch/src/lib.rs:60-166` | deterministic backend selection by descending priority then backend name | no compatible backend or unavailable requested backend returns fail-closed error paths | dispatch decision ledger + conformance dispatch fixture (`XW-003`) |
| `fnx-convert` | `crates/fnx-convert/src/lib.rs:90-250` | edge-list/adjacency payload conversion into canonical `Graph` state | strict mode fails on empty/malformed node/edge surfaces; hardened records warnings and continues within bounded recovery | conversion warnings + ledger + fixture reports in `artifacts/conformance/latest/*.report.json` |
| `fnx-readwrite` | `crates/fnx-readwrite/src/lib.rs:54-240` | deterministic edge-list and JSON graph read/write using dispatch-gated backend route | malformed line/JSON branches are strict fail-closed; hardened path records warnings and salvages valid rows | `artifacts/conformance/latest/smoke_report.json` + `artifacts/conformance/latest/structured_logs.jsonl`; crosswalk rows `XW-005`/gap matrix in section `20.3` |
| `fnx-algorithms` | `crates/fnx-algorithms/src/lib.rs:53-320` | deterministic BFS shortest-path/components and deterministic degree/closeness centrality outputs with complexity witnesses | shortest-path tie behavior inherits deterministic neighbor insertion order from `Graph::neighbors_iter`; missing endpoints return `None`/empty-safe outputs rather than panic | perf + parity evidence in `artifacts/perf/*` and conformance fixture outputs (`XW-006`, `XW-007`) |
| `fnx-generators` | `crates/fnx-generators/src/lib.rs:42-272` | deterministic classic graph generators; seeded `gnp_random_graph` reproducibility | strict rejects out-of-range `n`/`p`; hardened clamps with explicit warning and `FullValidate` decision trace | generator warnings + policy evidence, linked to section `21` reliability budgets |
| `fnx-views` | `crates/fnx-views/src/lib.rs:6-80` | live view and cached snapshot semantics preserve deterministic ordering and revision alignment | stale cache is explicitly detectable and refreshable; stale reads are contained by revision check | view fixture parity + replay coverage (`XW-002`) |
| `fnx-durability` | `crates/fnx-durability/src/lib.rs:70-219` | sidecar generation, scrub, and decode drill produce deterministic envelope/proof artifacts | source hash mismatch triggers recovery or hard failure; decode failure paths are explicit and auditable | sidecar/decode proof artifacts in durability pipeline (`XW-010`) |
| `fnx-conformance` | `crates/fnx-conformance/src/lib.rs:276-380`, `crates/fnx-conformance/src/lib.rs:790-980` | fixture-driven orchestration writes smoke + per-fixture + structured-log artifacts deterministically | parser errors, operation failures, and mismatch conditions are normalized into typed mismatch categories | canonical CI gate inputs/outputs in sections `21` and `22`; dependent-unblock matrix artifact emitted by harness |

### 25.2 Behavior-risk matrix (normal/edge/adversarial pathways)

| Behavior family | Trigger / observable signal | Strict-mode contract | Hardened-mode contract | Evidence + replay obligations |
|---|---|---|---|---|
| Graph mutation compatibility | incompatible edge metadata key prefix (`__fnx_incompatible*`) plus policy outcome from `decision_theoretic_action` | fail-closed when policy resolves `FailClosed`; otherwise mutation proceeds with recorded `DecisionAction` | fail-closed for unknown incompatible feature; otherwise policy may select `FullValidate`/`Allow` with evidence | graph decision ledger + fixture replay command with mutation op |
| Read/parse boundary | malformed edge-list row or malformed JSON payload | immediate fail-closed read error | bounded salvage with warning emission and deterministic warning order | warning rows in fixture report + structured logs + replay command |
| Generator safety boundary | `n` above family cap or `p` outside `[0,1]` | fail-closed generation error | clamp + warning when permitted by policy; otherwise fail-closed | generator ledger records + adversarial fixture artifacts |
| Dispatch compatibility boundary | no compatible backend for required feature set | fail-closed dispatch error | fail-closed dispatch error (compatibility-critical) | dispatch mismatch rows + decision record terms |
| Telemetry contract boundary | missing structured-log required fields or invalid bundle index coupling | fail gate and reject artifact | fail gate and reject artifact | `artifacts/conformance/latest/structured_log_emitter_normalization_report.json` + schema-linked gate failures |
| Durability integrity boundary | artifact hash mismatch after recovery attempt | fail scrub/decode path | fail scrub/decode path | decode proof hashes + scrub status in envelope |

### 25.3 Explicit Pass-B parity gap register (current code vs required full overlap)

The current Rust surface is strong on deterministic graph core, dispatch, conversion/readwrite, durability, conformance orchestration, and first-wave algorithms; however, full drop-in overlap requirements still include unclosed families:

1. Flow and matching algorithm families are not yet present in `fnx-algorithms` (no corresponding implementations discovered in `crates/fnx-algorithms/src/lib.rs`).
2. Read/write format breadth beyond edge-list/JSON remains open for scoped formats called out in roadmap work (e.g., adjlist/GraphML entry points are not yet represented in `crates/fnx-readwrite/src/lib.rs`).
3. Crosswalk rows marked `partial` in section `20.2` remain release-relevant until packet beads close and artifacts are promoted to `covered`.

This gap register is intentionally explicit so downstream review beads (`bd-315.24.13`, `bd-315.24.16`, `bd-315.24.17`) can challenge contradictions against named source anchors instead of narrative summaries.

### 25.4 Pass-B closure binding to downstream review beads

`bd-315.24.12` Pass-B deepening is now represented as:

1. Source-anchored crate execution map with normal/edge/adversarial contracts (`25.1` + `25.2`).
2. Direct linkage to test/logging crosswalk and CI topology contracts (sections `20`, `21`, `22`).
3. Explicit residual parity gaps and closure routing (`25.3`).
4. Deterministic audit path for reviewers:
   - run conformance smoke and structured-log checks with offloaded commands in sections `21.1`, `24.4`;
   - verify artifacts listed in sections `20.2`, `21.1`, and `22.3`;
   - validate no contradiction between crate source anchors and gate-policy mappings.

This section is the direct execution artifact for Pass-B and is the handoff substrate for contradiction/completeness review in `bd-315.24.13` and specialist deep passes `bd-315.24.16`/`bd-315.24.17`.

## 26. DOC-PASS-12 Red-Team Contradiction and Completeness Log (`bd-315.24.13`)

### 26.1 Findings and resolutions

| Finding ID | Red-team finding | Risk if uncorrected | Resolution applied in this pass |
|---|---|---|---|
| `RT-001` | quantitative inventory counts in sections `2` and `12` were stale | reviewers could challenge credibility of measured inventory basis | updated counts to current measured totals (`1247` total, `687` Python; hotspot family counts `393/59/35/26`) |
| `RT-002` | section-3 legacy path references mixed shorthand and absolute forms without namespace rule | ambiguous interpretation of anchors during follow-on reviews | added explicit path namespace rule: shorthand legacy modules are relative to `legacy_networkx_code/networkx/networkx/` |
| `RT-003` | some Pass-B evidence links used basename-only artifacts (`smoke_report.json`, `structured_logs.jsonl`) | artifact lookup ambiguity and potential false contradiction reports | normalized these references to full project-relative artifact paths under `artifacts/conformance/latest/` |
| `RT-004` | telemetry boundary row referenced normalization report without path root | weakens reproducibility of risk/test assertions | normalized to `artifacts/conformance/latest/structured_log_emitter_normalization_report.json` |

### 26.2 Bounded residual uncertainty (explicit)

1. Section `20.2` still contains rows intentionally marked `partial`; this is not a contradiction, but a declared closure dependency on packet implementation beads.
2. Full drop-in overlap remains open for flow/matching families and broader read/write formats; this is documented as an explicit parity gap in section `25.3`.
3. No unresolved direct contradiction remains between sections `18-25` and currently inspected crate entry points (`fnx-classes`, `fnx-runtime`, `fnx-dispatch`, `fnx-convert`, `fnx-readwrite`, `fnx-algorithms`, `fnx-generators`, `fnx-views`, `fnx-durability`, `fnx-conformance`).

## 27. DOC-PASS-15 Behavior Specialist Deep-Pass Log (`bd-315.24.16`)

### 27.1 Findings and applied clarifications

| Finding ID | Behavior review finding | Applied clarification |
|---|---|---|
| `BH-001` | stale-cache handling text implied automatic rebuild-or-fail in `fnx-views`, but implementation requires explicit caller refresh (`refresh_if_stale`) before consuming `snapshot()` | sections `18.6` and `18.7` now state caller-side refresh contract explicitly and classify unrefreshed stale reads as conformance failures |
| `BH-002` | graph metadata incompatibility was documented as always fail-closed, but runtime policy gate may return `Allow`/`FullValidate` for non-terminal cases | sections `19.2`, `25.1`, and `25.2` now describe policy-driven outcomes and preserve explicit fail-closed conditions |
| `BH-003` | deterministic ordering/tie-break behavior needed tighter linkage to concrete mechanisms | section `25.1` now binds determinism to insertion-ordered graph storage and BFS neighbor iteration; section `18.6` now explicitly captures dispatch backend sort rule (`priority`, then `name`) |

### 27.2 Behavior validation anchors

1. View cache behavior: `crates/fnx-views/src/lib.rs:63-79`.
2. Graph edge-policy gate and evidence recording: `crates/fnx-classes/src/lib.rs:225-334`, `crates/fnx-runtime/src/lib.rs:1146-1171`.
3. Dispatch deterministic ordering: `crates/fnx-dispatch/src/lib.rs:86-92`.
4. BFS tie behavior through neighbor iteration: `crates/fnx-algorithms/src/lib.rs:91-121`, `crates/fnx-classes/src/lib.rs:146-150`.

### 27.3 Residual bounded uncertainty

1. Directed and multigraph deep semantics are still tracked as packet-level follow-on work and are not fully closed by this docs pass.
2. Flow/matching family tie-break semantics remain open until those implementations land and are fixture-anchored.

## 28. DOC-PASS-16 Risk/Perf/Test Specialist Deep-Pass Log (`bd-315.24.17`)

### 28.1 Critical behavior-surface coverage audit

| Critical surface | Crosswalk IDs | Replay command baseline (offloaded) | Forensics/logging artifacts | Current status |
|---|---|---|---|---|
| Graph mutation + view lifecycle | `XW-001`, `XW-002` | `rch exec -- cargo run -q -p fnx-conformance --bin run_smoke -- --fixture graph_core_mutation_hardened.json --mode hardened` | `artifacts/conformance/latest/smoke_report.json`, `artifacts/conformance/latest/structured_logs.jsonl` | `XW-001=covered`, `XW-002=partial` |
| Conversion + read/write parser safety | `XW-004`, `XW-005` | `rch exec -- cargo run -q -p fnx-conformance --bin run_smoke -- --fixture generated/readwrite_hardened_malformed.json --mode hardened` | fixture report JSON + structured logs + replay metadata | `XW-004=partial`, `XW-005=covered` |
| Algorithm parity + complexity witnesses | `XW-006`, `XW-007` | `rch exec -- cargo run -q -p fnx-conformance --bin run_smoke -- --fixture graph_core_shortest_path_strict.json --mode strict` | witness-linked smoke outputs + perf artifacts | partial |
| Generator determinism + abuse guards | `XW-008` | `rch exec -- cargo run -q -p fnx-conformance --bin run_smoke -- --fixture generated/generators_cycle_strict.json --mode strict` | structured logs + adversarial manifest linkage | partial |
| Telemetry schema + replay/forensics integrity | `XW-009` | `rch exec -- cargo test -q -p fnx-conformance structured_log_gate -- --nocapture` | `structured_logs.jsonl`, emitter normalization report, unblock matrix | covered |
| Durability scrub/decode proofs | `XW-010` | `rch exec -- cargo test -q -p fnx-durability -- --nocapture` | `structured_logs.raptorq.json`, `structured_logs.recovered.json`, decode proofs | partial |

### 28.2 Missing mapping resolution (no orphan critical surfaces)

All currently partial critical surfaces are explicitly mapped to existing closure beads and therefore are not orphaned:

1. `XW-001`, `XW-002`, `XW-004`, `XW-005` -> `GAP-01` -> `bd-315.23`.
2. `XW-006`, `XW-007`, `XW-008` -> `GAP-02` -> `bd-315.16`, `bd-315.18.6`, `bd-315.18.7`.
3. `XW-010` -> `GAP-04` -> `bd-315.26`.
4. Gate automation and CI wiring for all crosswalk IDs remains bound to `GAP-05` -> `bd-315.10.1`, `bd-315.10`.

### 28.3 Risk taxonomy tightening (specialist corrections)

1. Critical (`P0`) behavior surfaces now require an explicit tuple: replay command + structured log references + forensic artifact bundle links.
2. Any row that lacks either replay command determinism or forensic artifact linkage must be converted to a blocking gap row before release review.
3. Performance claims remain bounded by section `24` one-lever optimization law; no optimization acceptance without parity witness continuity and replayability.

### 28.4 Specialist pass verdict

`bd-315.24.17` criterion is satisfied in documentation form: no critical behavior surface is left without replayable test/logging mapping. Surfaces not yet fully covered are explicitly bounded as `partial` with named closure beads and fail-closed gate linkage.

## 29. FNX-P2C-001 Legacy Anchor Map + Extraction Ledger (`bd-315.12.1`)

### 29.1 Legacy anchor map (normal/edge/adversarial pathways)

| Anchor ID | Legacy source anchor | Symbol / behavior locus | Normal-path behavior to preserve | Edge/adversarial behavior + policy |
|---|---|---|---|---|
| `LM-001` | `legacy_networkx_code/networkx/networkx/classes/graph.py::add_edge` | undirected adjacency mutation and node auto-creation | endpoint insertion mutates adjacency deterministically with attribute merge semantics | unknown incompatible metadata routes through policy gate; fail-closed when incompatibility action resolves to terminal reject |
| `LM-002` | `legacy_networkx_code/networkx/networkx/classes/graph.py:693`, `legacy_networkx_code/networkx/networkx/classes/graph.py:748` | list-materialized neighbor iteration during removals | mutation/removal loops avoid in-loop iterator corruption by materializing neighbor lists | iteration/mutation race analogs are treated as invariant violations; stale or partial state exposure is forbidden |
| `LM-003` | `legacy_networkx_code/networkx/networkx/classes/digraph.py:522`, `legacy_networkx_code/networkx/networkx/classes/digraph.py:638`, `legacy_networkx_code/networkx/networkx/classes/digraph.py:775` | directed mutation/removal boundary behavior | directed adjacency updates preserve endpoint semantics and deterministic container order | malformed identity or incompatible key semantics are escalated to fail-closed compatibility outcomes |
| `LM-004` | `legacy_networkx_code/networkx/networkx/classes/coreviews.py::AtlasView/AdjacencyView`, `legacy_networkx_code/networkx/networkx/classes/reportviews.py::NodeView/EdgeView` | live view projection contract | view traversal reflects current backing mapping order | cached stale-read without refresh is treated as a conformance failure in Rust parity layer |
| `LM-005` | `legacy_networkx_code/networkx/networkx/utils/backends.py` (`_dispatchable`, `_can_convert`) | backend dispatch/convert route arbitration | backend route choice is deterministic under fixed capability/prioritization inputs | ambiguous/unsupported route selection is compatibility-critical and fail-closed in strict/hardened |
| `LM-006` | `legacy_networkx_code/networkx/networkx/algorithms/shortest_paths/unweighted.py` (`for w in adj[v]`) | shortest-path traversal tie-break source | traversal order inherits adjacency iteration order | tie-break drift is treated as behavior drift and must fail parity gates |
| `LM-007` | `legacy_networkx_code/networkx/networkx/readwrite/edgelist.py:239`, `legacy_networkx_code/networkx/networkx/readwrite/edgelist.py:275` | edgelist parse/literal handling | line-sequential parser accepts valid rows deterministically | strict mode fail-closed on malformed rows; hardened bounded skip + warning with deterministic warning order |
| `LM-008` | `legacy_networkx_code/networkx/networkx/readwrite/adjlist.py:85-86`, `legacy_networkx_code/networkx/networkx/readwrite/adjlist.py:144-145` | adjacency-list delimiter and token boundaries | canonical delimiter policy yields stable decode behavior | ambiguous delimiter/label collisions are strict fail-closed unless explicitly allowlisted recovery policy exists |

### 29.2 Ambiguous/undefined legacy behavior decisions (explicitly bounded)

| Decision ID | Ambiguity / undefined zone | Chosen compatibility policy | Rationale |
|---|---|---|---|
| `DEC-001` | mutable-but-hashable node identity drift after insertion | fail-closed in strict and hardened | silent key drift corrupts adjacency identity and invalidates replay determinism |
| `DEC-002` | incompatible metadata attached to edge mutation | policy-driven action (`Allow`/`FullValidate`/`FailClosed`) with unknown incompatible feature forced fail-closed | aligns with explicit decision-theoretic guard while preserving terminal safety for incompatible features |
| `DEC-003` | cached view consumed after parent revision change | mandatory caller refresh; stale read without refresh is conformance failure | implementation contract is explicit (`refresh_if_stale`) and avoids silent stale serving |
| `DEC-004` | parser ambiguity for malformed rows / delimiter collisions | strict fail-closed, hardened bounded warning-recovery only | preserves deterministic output while allowing bounded hardened salvage for row-local syntax faults |
| `DEC-005` | backend route ambiguity across capability sets | fail-closed in both modes | backend-route ambiguity is compatibility-critical and not recoverable noise |

### 29.3 Extraction ledger: behavior region -> contract rows -> oracle tests

| Ledger ID | Anchor IDs | Downstream contract rows | Planned/linked oracle tests and fixtures | Implementation target surface |
|---|---|---|---|---|
| `LED-001` | `LM-001`, `LM-002`, `LM-004` | `XW-001`, `XW-002` | `graph_core_mutation_hardened.json`, `view_neighbors_strict.json`, `fnx-classes` + `fnx-views` unit suites | `fnx-classes`, `fnx-views` |
| `LED-002` | `LM-005` | `XW-003` | `dispatch_route_strict.json`, dispatch selection tests, decision-ledger assertions | `fnx-dispatch`, `fnx-runtime` |
| `LED-003` | `LM-007`, `LM-008` | `XW-004`, `XW-005` | conversion/readwrite strict+hardened malformed fixtures, parser warning-order assertions | `fnx-convert`, `fnx-readwrite` |
| `LED-004` | `LM-006` | `XW-006`, `XW-007` | shortest-path/components/centrality parity fixtures and witness checks | `fnx-algorithms`, `fnx-conformance` |
| `LED-005` | `LM-005`, `LM-007`, `LM-008` | `XW-009`, `XW-010` | structured-log gate + durability scrub/decode proof gates and adversarial regression bundle | `fnx-runtime`, `fnx-conformance`, `fnx-durability` |

### 29.4 FNX-P2C-001 completion criterion verdict

`bd-315.12.1` deliverable is now explicit in-document: source-path anchors, bounded ambiguity decisions, and extraction-ledger mapping to downstream contract rows and oracle evidence are all codified in this section.

## 30. FNX-P2C-001 Contract Table + Strict/Hardened Invariant Spec (`bd-315.12.2`)

### 30.1 Machine-checkable contract table

| Contract ID | API / behavior surface | Preconditions (machine-checkable) | Postconditions (machine-checkable) | Preservation invariants | Strict policy | Hardened policy | Legacy anchor + validation linkage |
|---|---|---|---|---|---|---|---|
| `CT-001` | node insertion (`Graph::add_node_with_attrs`) | `node_id != ""` | node exists; attrs merged; revision increments iff semantic change | insertion order preserved; revision monotonic | allow unless incompatible feature gate triggers fail-closed | same; no unbounded recovery | `LM-001`; `XW-001`; `fnx-classes` unit tests |
| `CT-002` | edge insertion (`Graph::add_edge_with_attrs`) | endpoints non-empty; metadata parse succeeds | edge exists or fail-closed error returned; ledger decision recorded | undirected adjacency symmetry; deterministic neighbor order | fail-closed when action=`FailClosed`; unknown incompatible feature always terminal | may allow/full-validate when policy permits, but unknown incompatible feature remains terminal | `LM-001`, `LM-002`; `XW-001`; conformance mutation fixtures |
| `CT-003` | node/edge removal lifecycle | target entity exists or no-op | incident edges removed deterministically; revision increments on mutation | no dangling adjacency entries; deterministic post-removal order | fail-closed on invariant breach | rollback then fail-closed on invariant breach | `LM-002`, `LM-003`; `XW-001`, `XW-002` |
| `CT-004` | cached view consumption (`CachedSnapshotView`) | caller checks staleness before snapshot consumption | refreshed snapshot aligns with graph revision | stale snapshot cannot be treated as valid parity output | stale read without refresh is contract failure | same | `LM-004`; `XW-002`; view refresh tests |
| `CT-005` | dispatch route resolution (`BackendRegistry::resolve`) | required features set + mode + risk inputs provided | deterministic backend selected or fail-closed/no-compatible error | backend tie-break is stable (`priority` desc then `name` asc) | unknown incompatible feature and route ambiguity fail-closed | same fail-closed boundary | `LM-005`; `XW-003`; dispatch fixtures |
| `CT-006` | conversion/readwrite parse surfaces | payload line/token schema satisfies parser contract | deterministic graph output or typed fail-closed/warning outcome | warning ordering deterministic; replay metadata retained | malformed payload is fail-closed | bounded row-local recovery allowlisted; budget overflow fail-closed | `LM-007`, `LM-008`; `XW-004`, `XW-005` |
| `CT-007` | algorithm tie-break + witness emission | source/target or operation inputs valid per API | output ordering deterministic; witness populated | tie-break derives from deterministic neighbor order | parity drift is gate-fail | parity drift is gate-fail | `LM-006`; `XW-006`, `XW-007` |
| `CT-008` | telemetry + durability evidence pipeline | required structured-log fields + bundle index present | artifact accepted only when schema-valid and replayable | forensics linkage and decode proofs remain consistent | schema violation/durability mismatch fail-closed | schema violation/durability mismatch fail-closed | `LM-005`, `LED-005`; `XW-009`, `XW-010` |

### 30.2 Explicit allowlisted divergence classes

Only the following hardened-mode divergences are allowlisted; all others default to fail-closed:

1. Row-local malformed parse recovery with deterministic warning emission (`CT-006`).
2. Parameter clamping for bounded generator guards where policy explicitly permits recovery.
3. Non-terminal policy outcomes (`FullValidate`) that preserve output contract and emit evidence ledger rows.

Unknown incompatible features/metadata are not an allowlisted divergence class and remain fail-closed by default.

### 30.3 Contract-to-validation bindings (forward + backward traceability)

| Contract ID range | Backward link (legacy anchor) | Forward link (validation assets) |
|---|---|---|
| `CT-001..CT-004` | `LM-001..LM-004` | `XW-001`, `XW-002`, graph/view unit suites, smoke fixtures |
| `CT-005` | `LM-005` | `XW-003`, dispatch strict fixture + decision-ledger checks |
| `CT-006` | `LM-007`, `LM-008` | `XW-004`, `XW-005`, malformed-input conformance fixtures/e2e scripts |
| `CT-007` | `LM-006` | `XW-006`, `XW-007`, witness-bearing parity fixtures |
| `CT-008` | `LM-005` + durability anchors | `XW-009`, `XW-010`, structured-log/durability gate tests |

### 30.4 FNX-P2C-001-B completion verdict

`bd-315.12.2` contract deliverable is now explicit: strict/hardened boundaries, machine-checkable pre/post/invariant rows, allowlisted divergence classes, and bidirectional traceability to legacy anchors and validation assets are all codified.

## 31. FNX-P2C-001 Security + Compatibility Threat Model (`bd-315.12.3`)

### 31.1 Packet-boundary threat matrix

| Threat class | Typical trigger vector | Strict-mode response | Hardened-mode response | Required mitigation controls | Required evidence artifacts |
|---|---|---|---|---|---|
| Parser abuse | malformed edge-list/adjlist/json payloads, delimiter ambiguity, hostile literal payloads | fail-closed on first terminal parse violation | bounded row-local recovery only for allowlisted syntax faults; otherwise fail-closed | deterministic parser ordering, warning-budget caps, explicit row-index diagnostics | malformed fixture reports + structured logs + replay commands (`XW-004`, `XW-005`) |
| Metadata ambiguity | unknown/incompatible feature keys, ambiguous attr schemas | fail-closed when policy action resolves terminal reject; unknown incompatible features default terminal | identical terminal default for unknown incompatibles; non-terminal policy outcomes require full evidence | policy gate with explicit incompatibility probability/action, no silent metadata coercion | graph/dispatch decision ledgers (`XW-001`, `XW-003`) |
| Version/schema skew | stale telemetry schema, artifact envelope incompatibility | fail-closed on schema mismatch or missing required fields | fail-closed (diagnostic enrichment only) | canonical schema version checks + forensics index coupling validation | `structured_log_emitter_normalization_report.json`, gate failures (`XW-009`) |
| Resource exhaustion | oversized `n`, dense generation requests, pathological fixture bundles | fail-closed at guard threshold | clamp only where allowlisted; otherwise fail-closed | hard caps + deterministic clamp policy + explicit rationale emission | generator warnings, guardrail logs, adversarial manifests (`XW-008`) |
| State corruption/recovery drift | checksum mismatch, decode inconsistency, illegal state transitions | fail-closed terminal state | fail-closed terminal state | immutable terminal states, append-only transition log, decode-proof verification | durability scrub/decode proofs + transition logs (`XW-009`, `XW-010`) |

### 31.2 Hardened-mode allowlist (ad hoc deviations forbidden)

Allowed hardened deviations:

1. Row-local parse recovery with deterministic warning output and replay metadata.
2. Guardrail clamping for explicitly allowlisted parameter bounds (e.g., generator probability/size caps).
3. Non-terminal decision-theoretic `FullValidate` outcomes that preserve output contract and emit full evidence terms.

Forbidden hardened deviations:

1. Unknown incompatible features/metadata bypass.
2. Backend route ambiguity fallback.
3. Telemetry schema relaxation.
4. Durability decode-proof bypass.

### 31.3 Compatibility boundary matrix (strict obligations vs hardened allowlisted deviations)

| Boundary | Strict-mode parity obligation | Hardened-mode allowlisted deviation | Default for unknown incompatible features |
|---|---|---|---|
| Graph mutation/metadata | preserve deterministic mutation semantics or fail-closed | only policy-approved non-terminal action with evidence | fail-closed |
| Dispatch/backend selection | deterministic route or fail-closed | none for ambiguity; diagnostics only | fail-closed |
| Conversion/readwrite parsing | fail-closed on malformed critical rows | bounded row-local skip+warning within budget | fail-closed |
| Telemetry contract | schema-complete, replayable, forensics-linked logs required | none; hardened cannot weaken schema | fail-closed |
| Durability recovery | checksum/decode proof required for acceptance | none; hardened cannot bypass proof | fail-closed |

### 31.4 Adversarial fixture/fuzz/crash triage mapping

| Threat class | Adversarial fixtures / fuzz entrypoints | Crash triage taxonomy key |
|---|---|---|
| Parser abuse | `generated/readwrite_hardened_malformed.json`, malformed edgelist fixtures, parser fuzz seeds from `scripts/e2e/run_malformed_input.sh` | `TRIAGE-PARSE-*` (tokenization, delimiter, literal decode, warning-budget overflow) |
| Metadata ambiguity | graph/dispatch incompatibility fixtures (`graph_core_mutation_hardened.json`, `dispatch_route_strict.json`) | `TRIAGE-COMPAT-*` (unknown feature, route ambiguity, metadata contract mismatch) |
| Version/schema skew | structured log gate + schema validator paths (`structured_log_gate.rs`) | `TRIAGE-SCHEMA-*` (version mismatch, missing replay field, forensic index divergence) |
| Resource exhaustion | generator adversarial e2e (`scripts/e2e/run_adversarial_soak.sh`) and large-parameter guard fixtures | `TRIAGE-RESOURCE-*` (cap breach, clamp policy violation, memory/runtime envelope breach) |
| State corruption/recovery drift | durability decode drills and packet readiness gates | `TRIAGE-DURABILITY-*` (checksum mismatch, decode failure, illegal terminal transition) |

### 31.5 FNX-P2C-001-C completion verdict

`bd-315.12.3` threat-model deliverable is now explicit: threat classes, strict/hardened responses, allowlisted deviations, compatibility boundaries, and adversarial triage mappings are codified with fail-closed defaults for unknown incompatible features.

## 32. FNX-P2C-001 Rust Implementation Plan + Module Boundary Skeleton (`bd-315.12.4`)

### 32.1 Compile-checkable module boundary skeleton

| Boundary ID | Crate/module seam | Compile-checkable public surface (current) | Ownership/state boundary | Legacy compatibility surface |
|---|---|---|---|---|
| `MB-001` | graph storage core (`fnx-classes`) | `Graph`, `GraphError`, `add_node_with_attrs`, `add_edge_with_attrs`, `remove_node`, `snapshot` | canonical ownership of adjacency/node/edge/revision state | `graph.py`/`digraph.py` mutation and ordering semantics |
| `MB-002` | runtime policy + telemetry (`fnx-runtime`) | `CompatibilityMode`, `DecisionAction`, `decision_theoretic_action`, `StructuredTestLog::validate`, `EvidenceLedger` | canonical ownership of policy action law, telemetry schema, decision records | strict/hardened policy envelope + replay/forensics contract |
| `MB-003` | dispatch routing (`fnx-dispatch`) | `BackendRegistry`, `DispatchRequest`, `DispatchDecision`, `resolve` | ownership of backend capability arbitration and deterministic selection | `_dispatchable` / backend priority behavior |
| `MB-004` | conversion ingress (`fnx-convert`) | `GraphConverter::from_edge_list`, `GraphConverter::from_adjacency`, `ConvertReport`, `ConvertError` | ownership of conversion warning/fail paths and payload normalization | `convert.py`/`convert_matrix.py` behavior surfaces |
| `MB-005` | read/write parser+serializer (`fnx-readwrite`) | `EdgeListEngine::{read_edgelist,write_edgelist,read_json_graph,write_json_graph}` | ownership of parser lifecycle and warning ordering | `readwrite/edgelist.py` + `readwrite/adjlist.py` semantics |
| `MB-006` | algorithm deterministic core (`fnx-algorithms`) | `shortest_path_unweighted`, `connected_components`, `degree_centrality`, `closeness_centrality`, `ComplexityWitness` | ownership of tie-break and witness emission semantics | unweighted shortest-path + centrality parity surfaces |
| `MB-007` | generator boundary (`fnx-generators`) | `GraphGenerator::{path_graph,cycle_graph,complete_graph,gnp_random_graph}` | ownership of deterministic generation and guardrail policy outcomes | `generators/random_graphs.py` seeded behavior class |
| `MB-008` | view projection layer (`fnx-views`) | `GraphView`, `CachedSnapshotView::{is_stale,refresh_if_stale}` | ownership of live/cached read behavior and stale handling contract | `coreviews.py`/`reportviews.py` live view behavior |
| `MB-009` | conformance harness orchestrator (`fnx-conformance`) | `HarnessConfig`, `run_smoke`, `FixtureReport`, `HarnessReport` | ownership of fixture execution, mismatch taxonomy, artifact emission | oracle-driven parity gating and replay command surfaces |
| `MB-010` | durability envelope layer (`fnx-durability`) | `generate_sidecar_for_file`, `scrub_artifact`, `run_decode_drill`, `ArtifactEnvelope` | ownership of sidecar integrity, scrub/decode-proof lifecycle | RaptorQ-everywhere artifact durability contract |

### 32.2 Dependency-aware implementation sequence and checkpoints

| Checkpoint | Ordered implementation scope | Dependency rationale | Semantic-risk control | Required verification entrypoint (offloaded) |
|---|---|---|---|---|
| `CP-001` | lock graph/runtime boundary (`MB-001`, `MB-002`) | all downstream crates depend on graph state + policy law | freeze invariants and fail-closed defaults first | `rch exec -- cargo check -q -p fnx-classes -p fnx-runtime` |
| `CP-002` | lock dispatch/ingress boundaries (`MB-003`, `MB-004`, `MB-005`) | parsing and routing semantics feed all algorithm/generator paths | eliminate silent route/parse drift before algorithm expansion | `rch exec -- cargo check -q -p fnx-dispatch -p fnx-convert -p fnx-readwrite` |
| `CP-003` | lock algorithm/view/generator boundaries (`MB-006`, `MB-007`, `MB-008`) | tie-break/order semantics depend on prior boundaries | enforce deterministic ordering + witness continuity | `rch exec -- cargo check -q -p fnx-algorithms -p fnx-generators -p fnx-views` |
| `CP-004` | lock conformance/durability boundaries (`MB-009`, `MB-010`) | top-level parity and artifact integrity are release gates | enforce replayable mismatch and decode-proof evidence | `rch exec -- cargo check -q -p fnx-conformance -p fnx-durability` |
| `CP-005` | workspace integration freeze | prevents hidden cross-crate coupling drift | one-pass compile + lint + format gate | `rch exec -- cargo check --workspace --all-targets`, `rch exec -- cargo clippy --workspace --all-targets -- -D warnings`, `cargo fmt --check` |

### 32.3 Instrumentation hooks and verification stage map

| Stage | Hook location(s) | Required structured evidence fields | Verification assets |
|---|---|---|---|
| unit/property | `fnx-classes`, `fnx-convert`, `fnx-readwrite`, `fnx-generators`, `fnx-algorithms` unit surfaces | `schema_version`, `packet_id`, `test_id`, `mode`, `status`, `replay_command`, `forensic_bundle_id` | per-crate tests + crosswalk rows `XW-001..XW-008` |
| differential/conformance | `fnx-conformance::run_smoke`, fixture operation executor paths | full `StructuredTestLog` contract including `forensics_bundle_index` and `artifact_refs` | smoke reports, per-fixture reports, normalization report |
| e2e recovery | script pack and conformance/durability gate runners | deterministic replay seed/fixture IDs + reason codes + forensics links | e2e scripts listed in section `20.2`, readiness reports |
| durability proofs | `fnx-durability::{scrub_artifact,run_decode_drill}` | decode proof hashes + scrub status + artifact identity linkage | `XW-010` artifacts and packet readiness gates |

### 32.4 Public/internal API boundary and state ownership transitions

| Transition ID | Inbound owner -> outbound owner | Public API seam | Internal state handoff rule |
|---|---|---|---|
| `TR-001` | readwrite/convert -> graph core | `GraphConverter`, `EdgeListEngine` mutation calls | only validated/allowlisted records may mutate graph state in target mode |
| `TR-002` | graph core -> algorithms/views | `Graph` read APIs (`neighbors_iter`, `nodes_ordered`, snapshots) | consumers are read-only with deterministic ordering derived from graph storage |
| `TR-003` | runtime policy -> graph/dispatch/generator guards | `decision_theoretic_action` and mode enums | action choice must be recorded before terminal/allow outcomes are exposed |
| `TR-004` | harness -> telemetry artifacts | `run_smoke` + structured log builders | fixture execution results become immutable artifact records after validation |
| `TR-005` | telemetry/conformance -> durability | artifact file paths and envelope APIs | only schema-valid artifacts enter durability sidecar pipeline |

### 32.5 FNX-P2C-001-D completion verdict

`bd-315.12.4` deliverable is now explicit: module boundaries are compile-checkable via concrete public seams, implementation order is dependency-aware with risk checkpoints, instrumentation hooks and verification entrypoints are mapped, and API/state ownership transitions are sufficiently explicit for parallel contributors.
