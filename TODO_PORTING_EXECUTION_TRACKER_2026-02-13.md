# TODO Porting Execution Tracker (2026-02-13)

Status legend:
- `[ ]` not started
- `[-]` in progress
- `[x]` done
- `[!]` blocked / deferred with explicit reason

## A. Governance and Tracking

- [x] Create this granular tracker with explicit dependency ordering.
- [x] Keep statuses updated after every substantial implementation block.
- [x] Produce final landing-the-plane summary with residual risks and next steps.

## B. Dispatch / Convert / Readwrite Implementation

### B1. `fnx-dispatch` crate

- [x] Define strict/hardened dispatch configuration model.
- [x] Implement deterministic backend registry ordering.
- [x] Implement fail-closed route decision for unknown backends/features.
- [x] Integrate decision-theoretic action selection from `fnx-runtime`.
- [x] Add evidence ledger emission for dispatch decisions.
- [x] Add unit tests for:
  - [x] strict route rejection
  - [x] hardened route validation path
  - [x] deterministic backend priority selection

### B2. `fnx-convert` crate

- [x] Define normalized graph payload model (`nodes`, `edges`, attrs).
- [x] Implement conversion from edge list structures into `fnx-classes::Graph`.
- [x] Implement conversion from adjacency-map structures into `fnx-classes::Graph`.
- [x] Implement conversion from `fnx-classes::Graph` to normalized snapshot.
- [x] Enforce strict/hardened mode behavior for malformed payloads.
- [x] Emit evidence records for conversion route and validation decisions.
- [x] Add tests for:
  - [x] deterministic node/edge ordering
  - [x] malformed edge payload fail-closed behavior
  - [x] attribute merge behavior consistency

### B3. `fnx-readwrite` crate

- [x] Implement deterministic edgelist writer from `fnx-classes::Graph`.
- [x] Implement deterministic edgelist parser -> `fnx-classes::Graph`.
- [x] Add strict/hardened parser mode.
- [x] Fail-closed on malformed records in strict mode.
- [x] Hardened bounded diagnostics while preserving API contract.
- [x] Emit parse/write evidence records.
- [x] Add tests for:
  - [x] round-trip parity
  - [x] malformed line handling
  - [x] deterministic serialized ordering

## C. Conformance Harness Expansion

### C1. Oracle capture tooling

- [x] Add Python oracle script to run legacy NetworkX and emit fixture expectations.
- [x] Define fixture schema shared by oracle script and Rust harness.
- [x] Add at least 3 generated fixture families for current slice:
  - [x] dispatch route fixtures
  - [x] conversion fixtures
  - [x] readwrite round-trip fixtures

### C2. Rust harness extension (`fnx-conformance`)

- [x] Parse and execute new fixture operation types.
- [x] Route operations through `fnx-dispatch`, `fnx-convert`, `fnx-readwrite`.
- [x] Compare expected vs actual output with mismatch taxonomy labels.
- [x] Emit machine-readable report JSON artifact for each run.
- [x] Add tests validating zero drift for generated fixture corpus.

## D. Durability Pipeline (RaptorQ sidecars)

### D1. New crate scaffolding

- [x] Add new workspace crate `fnx-durability`.
- [x] Define artifact envelope schema:
  - [x] source hash
  - [x] symbol manifest
  - [x] scrub status
  - [x] decode proof log

### D2. Sidecar generation and recovery proof

- [x] Integrate a RaptorQ-capable encoder/decoder library (or explicit fallback with clear gate).
- [x] Implement sidecar generation for conformance report artifacts.
- [x] Implement decode/recovery drill command path and proof artifact.
- [x] Implement integrity scrub routine with status report output.
- [x] Add unit/integration tests for sidecar generation and decode proof.

### D3. Pipeline wiring

- [x] Add script or binary to run:
  - [x] conformance report generation
  - [x] sidecar generation
  - [x] scrub verification
  - [x] decode proof drill
- [x] Document artifact locations and naming conventions.

## E. Docs and Spec Synchronization

- [x] Update `FEATURE_PARITY.md` with new statuses after implementation.
- [x] Update `PROPOSED_ARCHITECTURE.md` with new crate + flow.
- [x] Update `README.md` next-step section to reflect completed work.
- [x] Add/update method-stack evidence artifact log for this session.

## F. Required Command Gates

- [x] `cargo fmt --check`
- [x] `cargo check --all-targets`
- [x] `cargo clippy --all-targets -- -D warnings`
- [x] `cargo test --workspace`
- [x] `cargo test -p fnx-conformance -- --nocapture`
- [x] `cargo bench`

## G. Explicit Deferred Items (only if still unresolved at end)

- [x] None. All required items in this tracker were completed in this session.
