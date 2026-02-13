# TODO Phase 4 Execution Tracker (2026-02-13)

Status legend:
- `[ ]` not started
- `[-]` in progress
- `[x]` done
- `[!]` blocked / deferred with explicit reason

## A. Tracker and Method Stack Discipline

- [x] Create this phase-4 tracker with granular subtasks.
- [x] Update task statuses continuously after each implementation block.
- [x] Ensure each substantive change has method-stack evidence notes.
- [x] Close with residual risk + next-step summary.

## B. Algorithm Breadth Expansion (`fnx-algorithms`)

### B1. Connected components algorithm
- [x] Define deterministic output contract for connected components.
- [x] Implement `connected_components` preserving deterministic traversal order.
- [x] Implement `number_connected_components` helper.
- [x] Emit complexity witness artifact for component routines.
- [x] Add strict tests for:
  - [x] disconnected graph with multiple components
  - [x] deterministic tie-break ordering
  - [x] empty graph behavior
  - [x] isolated-node behavior

### B2. Conformance-facing output model
- [x] Add serializable result structures for components output.
- [x] Ensure stable ordering in serialized comparison paths.

## C. Generator Breadth Expansion (`fnx-generators`)

### C1. Deterministic structural generators
- [x] Implement `path_graph(n)` generator.
- [x] Implement `cycle_graph(n)` generator.
- [x] Implement `complete_graph(n)` generator.
- [x] Implement `empty_graph(n)` generator.

### C2. Seeded probabilistic generator
- [x] Implement `gnp_random_graph(n, p, seed)` with deterministic RNG.
- [x] Strict mode: fail-closed for invalid parameters.
- [x] Hardened mode: bounded recovery/clamp path with warnings.
- [x] Emit generator evidence ledger entries.

### C3. Generator tests
- [x] Deterministic structure tests for path/cycle/complete/empty.
- [x] Seed reproducibility tests for `gnp_random_graph`.
- [x] Strict/hardened parameter handling tests.

## D. Conformance Harness Expansion (`fnx-conformance`)

### D1. New fixture operations
- [x] Add operation: connected components query.
- [x] Add operation: number connected components query.
- [x] Add operation: structural generator invocation.

### D2. Expected schema and comparisons
- [x] Extend expected schema with component outputs.
- [x] Extend expected schema with generated graph snapshot checks.
- [x] Add mismatch taxonomy entries for generator/component families.

### D3. Dispatch feature surface updates
- [x] Add component/generator feature flags to default dispatch registry.

## E. Oracle Fixture Capture Expansion (`scripts/capture_oracle_fixtures.py`)

### E1. Components fixtures
- [x] Generate connected-components fixture from legacy NetworkX.
- [x] Generate number-connected-components fixture from legacy NetworkX.

### E2. Generator fixtures
- [x] Generate path-graph fixture from legacy NetworkX.
- [x] Generate cycle-graph fixture from legacy NetworkX.
- [x] Generate complete-graph fixture from legacy NetworkX.

### E3. Artifact updates
- [x] Regenerate fixture bundle under `crates/fnx-conformance/fixtures/generated/`.
- [x] Update oracle capture artifact with new fixture metadata.

## F. Documentation and Status Sync

- [x] Update `FEATURE_PARITY.md` statuses and notes.
- [x] Update `README.md` current-state and next-steps bullets.
- [x] Update `PROPOSED_ARCHITECTURE.md` current implemented vertical slice notes.
- [x] Update `artifacts/METHOD_STACK_STATUS_2026-02-13.md` with phase-4 evidence.

## G. Validation and Gates

- [x] `cargo fmt --check`
- [x] `cargo check --all-targets`
- [x] `cargo clippy --all-targets -- -D warnings`
- [x] `cargo test --workspace`
- [x] `cargo test -p fnx-conformance -- --nocapture`
- [x] `cargo bench`
- [x] `./scripts/run_conformance_with_durability.sh`
- [x] `./scripts/run_benchmark_gate.sh`

## H. Landing the Plane

- [x] Confirm no destructive operations were used.
- [x] Summarize rationale for each major change.
- [x] List residual risks and highest-value next steps.
- [x] Confirm method-stack artifacts produced vs deferred.
