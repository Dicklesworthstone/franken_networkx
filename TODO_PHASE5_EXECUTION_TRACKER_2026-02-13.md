# TODO Phase 5 Execution Tracker (2026-02-13)

Status legend:
- `[ ]` not started
- `[-]` in progress
- `[x]` done
- `[!]` blocked / deferred with explicit reason

## A. Tracker Discipline

- [x] Create phase-5 tracker.
- [x] Update statuses continuously after each implementation step.
- [x] Close with residual risk and next-step summary.

## B. Algorithm Breadth: Centrality (`fnx-algorithms`)

### B1. Degree centrality implementation
- [x] Define deterministic output contract (stable node order, score semantics).
- [x] Implement `degree_centrality` API.
- [x] Emit complexity witness artifact for centrality path.
- [x] Handle `n <= 1` semantics to mirror legacy behavior for scoped simple graphs.

### B2. Centrality tests
- [x] Add tests for deterministic ordering.
- [x] Add tests for expected values on representative graph.
- [x] Add tests for empty graph behavior.
- [x] Add tests for singleton graph behavior.

## C. Generator Parity Tightening (`fnx-generators`)

### C1. Cycle edge-order parity
- [x] Update `cycle_graph(n)` edge insertion policy to match legacy edge iteration ordering for larger `n`.
- [x] Add/adjust tests validating parity-relevant edge order for `n >= 4`.

## D. Conformance Harness Expansion (`fnx-conformance`)

### D1. New operation and expected schema
- [x] Add operation: `degree_centrality_query`.
- [x] Extend expected schema for centrality scores.
- [x] Add mismatch taxonomy for centrality family.

### D2. Dispatch feature map
- [x] Add centrality feature route in default dispatch registry.

## E. Oracle Capture Expansion (`scripts/capture_oracle_fixtures.py`)

### E1. New centrality fixture
- [x] Generate degree-centrality fixture from legacy NetworkX.

### E2. Cycle fixture strengthening
- [x] Move cycle generator fixture to larger `n` parity case.

### E3. Artifact regeneration
- [x] Regenerate generated fixture bundle.
- [x] Refresh oracle capture artifact metadata.

## F. Docs and Status Sync

- [x] Update `FEATURE_PARITY.md` centrality/conformance notes.
- [x] Update `README.md` current-state bullets.
- [x] Update `PROPOSED_ARCHITECTURE.md` current implemented slice notes.
- [x] Update `crates/fnx-conformance/fixtures/README.md` fixture listing.
- [x] Update `artifacts/METHOD_STACK_STATUS_2026-02-13.md` phase-5 evidence.

## G. Validation Gates

- [x] `cargo fmt --check`
- [x] `cargo check --all-targets`
- [x] `cargo clippy --all-targets -- -D warnings`
- [x] `cargo test --workspace`
- [x] `cargo test -p fnx-conformance -- --nocapture`
- [x] `cargo bench`
- [x] `./scripts/run_conformance_with_durability.sh`
- [x] `./scripts/run_benchmark_gate.sh`

## H. Landing The Plane

- [x] Confirm no destructive operations used.
- [x] Summarize rationale for major changes.
- [x] List residual risks and highest-value next steps.
- [x] Confirm method-stack artifacts produced or deferred.
