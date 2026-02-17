# PROPOSED_ARCHITECTURE

## 1. Architecture Principles

1. Spec-first implementation, no line translation.
2. Strict mode for compatibility; hardened mode for defensive operation.
3. RaptorQ sidecars for long-lived conformance and benchmark artifacts.
4. Profile-first optimization with behavior proof artifacts.

## 1.1 Porting-to-Rust Application Mode

Current execution mode follows the skill decision tree as:

- phase 4 (implementation from spec) for active packet development
- phase 5 (conformance/QA) continuously in parallel via packet and readiness gates

Implementation protocol:

1. derive module responsibilities from `EXISTING_NETWORKX_STRUCTURE.md` and packet contract rows.
2. implement in Rust crate seams below.
3. validate with deterministic fixture replay and parity artifacts before advancing breadth.

## 2. Crate Map

- `fnx-classes`: Graph/DiGraph/MultiGraph core.
- `fnx-views`: adjacency/report view contracts.
- `fnx-dispatch`: dispatchable/decorator backend routing.
- `fnx-convert`: ingestion and conversion utilities.
- `fnx-algorithms`: shortest-path/flow/components core.
- `fnx-generators`: deterministic/random graph generators.
- `fnx-readwrite`: adjlist/edgelist/json/graphml scoped IO.
- `fnx-durability`: RaptorQ sidecar generation, scrub verification, decode proof artifacts.
- `fnx-conformance`: NetworkX differential harness.
- `fnx-runtime`: strict/hardened policy + evidence ledger.

## 2.1 External Leverage (FrankenSuite)

- `asupersync` integration point lives in `fnx-runtime` feature: `asupersync-integration`.
- `frankentui` integration point lives in `fnx-runtime` feature: `ftui-integration`.
- FrankenSQLite reference spec copied to:
  - `reference_specs/COMPREHENSIVE_SPEC_FOR_FRANKENSQLITE_V1.md`

## 3. Runtime Plan

- API layer normalizes inputs and validates invariants.
- Planner/dispatcher selects algorithm implementation.
- Core engine executes with explicit invariant checks.
- Conformance adapter captures oracle and target outputs.
- Evidence layer emits parity reports, benchmark deltas, and decode proofs.

## 3.1 Module Boundary and Ownership Contract

| Boundary | Public API seam | Internal ownership seam | Verification seam |
|---|---|---|---|
| `fnx-classes` | graph mutation/query interfaces | adjacency storage + revision counters | graph-core conformance fixtures |
| `fnx-views` | projection/read view interfaces | cache invalidation + coherence internals | `generated/view_neighbors_strict.json` |
| `fnx-dispatch` | route decision interface | backend ranking/tie-break internals | dispatch strict fixtures + policy logs |
| `fnx-convert` + `fnx-readwrite` | conversion/IO entry interfaces | parser normalization + warning budget internals | convert/readwrite parity fixtures |
| `fnx-algorithms` | algorithm APIs + witness payloads | traversal/work-queue internals | differential fixtures + witness checks |
| `fnx-conformance` | packet/run harness interfaces | mismatch taxonomy + forensics links | smoke/readiness/e2e gates |

## 4. Compatibility and Security

- strict mode: maximize scoped behavioral parity.
- hardened mode: same outward contract plus bounded defensive checks.
- fail-closed on unknown incompatible metadata/protocol fields.

## 5. Performance Contract

- baseline, profile, one-lever optimization, verify parity, re-baseline.
- p95/p99 and memory budgets enforced in CI.

## 6. Conformance Contract

- feature-family fixtures captured from legacy oracle.
- machine-readable parity report per run.
- regression corpus for previously observed mismatches.

## 7. Current Vertical Slice (Implemented)

- deterministic undirected graph core in `fnx-classes`:
  - node/edge mutation,
  - attribute merge semantics,
  - deterministic insertion ordering.
- decision-theoretic strict/hardened runtime policy with evidence ledger in `fnx-runtime`.
- deterministic unweighted shortest path + connected components/component-count witnesses in `fnx-algorithms`.
- deterministic degree-centrality with explicit score-order contract in `fnx-algorithms`.
- deterministic closeness-centrality with NetworkX-aligned WF-improved semantics in `fnx-algorithms`.
- deterministic and seeded graph generators with strict/hardened guards in `fnx-generators`.
- cycle-generator insertion policy aligned with legacy edge-order behavior for larger `n`.
- fixture-driven conformance harness with drift detection in `fnx-conformance`.
- conformance expansion for component, generator, and centrality fixture operations (14-fixture corpus).
- durability sidecar pipeline in `fnx-durability` + `scripts/run_conformance_with_durability.sh`.
- view layer with revision-aware cache invalidation in `fnx-views`.
- percentile benchmark gate pipeline in `scripts/run_benchmark_gate.sh`.
