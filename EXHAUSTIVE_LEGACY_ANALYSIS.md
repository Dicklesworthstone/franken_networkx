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

- Total files: `996`
- Python: `687`
- Native code: negligible for core graph logic
- Test-like files: `307`

High-density zones:
- `networkx/algorithms` (401 files)
- `networkx/generators` (60)
- `networkx/readwrite` (35)
- `networkx/classes` (26)

## 3. Subsystem Extraction Matrix (Legacy -> Rust)

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
- file count: `996`
- concentration: `networkx/algorithms` (`401` files), `networkx/generators` (`60`), `networkx/readwrite` (`35`), `networkx/classes` (`26`)

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
