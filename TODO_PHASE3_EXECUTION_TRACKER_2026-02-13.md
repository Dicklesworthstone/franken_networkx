# TODO Phase 3 Execution Tracker (2026-02-13)

Status legend:
- `[ ]` not started
- `[-]` in progress
- `[x]` done
- `[!]` blocked / deferred with explicit reason

## A. Tracker Discipline

- [x] Create phase-3 tracker with granular sub-tasks.
- [x] Update statuses continuously while implementing.
- [x] Close with final residual-risk summary.

## B. View Semantics (`fnx-views`)

- [x] Add `fnx-views` dependencies and core types.
- [x] Implement live graph views:
  - [x] node view
  - [x] edge view
  - [x] neighbor view
- [x] Implement cache-aware snapshot view with revision checks.
- [x] Add view-focused tests:
  - [x] live view sees mutations
  - [x] cached snapshot refreshes on revision change
  - [x] deterministic order preservation in view output

## C. Graph Revision / Cache Contracts (`fnx-classes`)

- [x] Add graph revision counter.
- [x] Increment revision on mutation-changing operations.
- [x] Expose revision getter for view/cache invalidation.
- [x] Add tests for revision semantics.

## D. Read/Write Format Breadth (`fnx-readwrite`)

- [x] Add JSON graph writer/reader for scoped format breadth.
- [x] Keep strict/hardened behavior for malformed JSON.
- [x] Add tests:
  - [x] JSON round-trip parity
  - [x] strict fail-closed malformed JSON
  - [x] hardened bounded warning behavior

## E. Conformance Expansion (`fnx-conformance`)

- [x] Add fixture operations for:
  - [x] view-neighbor query
  - [x] JSON read/write
- [x] Extend expected schema for new outputs.
- [x] Add fixtures covering view + JSON paths.
- [x] Keep report artifact emission stable.

## F. Oracle Capture Expansion

- [x] Extend `scripts/capture_oracle_fixtures.py` to emit:
  - [x] view behavior fixture
  - [x] JSON round-trip fixture (using legacy oracle behavior constraints)
- [x] Re-generate fixture bundle and oracle capture artifact.

## G. Benchmark Percentile Gating

- [x] Add percentile benchmark runner script (`p50/p95/p99`).
- [x] Emit machine-readable benchmark artifact JSON.
- [x] Add gate script checking budget thresholds.
- [x] Optional: sidecar durability generation for benchmark artifact.

## H. Docs + Parity Sync

- [x] Update `FEATURE_PARITY.md` with views/JSON/benchmark gate status.
- [x] Update `README.md` and architecture notes.
- [x] Update method-stack status artifact with phase-3 outputs.

## I. Validation Gates

- [x] `cargo fmt --check`
- [x] `cargo check --all-targets`
- [x] `cargo clippy --all-targets -- -D warnings`
- [x] `cargo test --workspace`
- [x] `cargo test -p fnx-conformance -- --nocapture`
- [x] `cargo bench`
- [x] run pipeline: `./scripts/run_conformance_with_durability.sh`
