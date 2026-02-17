# PLAN_TO_PORT_NETWORKX_TO_RUST

## 1. Purpose

Apply a strict spec-first Rust porting workflow for FrankenNetworkX:

1. Legacy -> executable spec extraction
2. Rust implementation from spec
3. Differential conformance against legacy oracle
4. Performance tuning only after behavior-isomorphism proof

Line-by-line translation is forbidden.

## 2. Non-Negotiable Method

1. Extract behavior from legacy into `EXISTING_NETWORKX_STRUCTURE.md`.
2. Design crate/module boundaries in `PROPOSED_ARCHITECTURE.md`.
3. Implement only from those docs and packet artifacts.
4. Prove parity with conformance fixtures and deterministic replay metadata.
5. Track completion in `FEATURE_PARITY.md`.

## 3. Legacy Oracle

- path: `/dp/franken_networkx/legacy_networkx_code/networkx`
- upstream: `networkx/networkx`

## 4. Scope and Explicit Exclusions

### In scope

- graph class semantics and mutable views
- high-value algorithm families (shortest path, components, centrality, flow-increment)
- conversion/relabel/readwrite core paths and backend dispatch
- deterministic conformance evidence + durability artifacts

### Explicit exclusions (current V1 boundary)

- drawing/matplotlib ecosystem and visualization integrations
- optional heavy linalg/scientific dependency pathways not yet admitted by packet roadmap
- full backend plugin ecosystem breadth before core parity closure
- non-runtime niceties (tutorial UX/docs polish) that do not affect behavior parity

## 5. Phase Detection and Current State

Decision tree:

- no docs -> phase 1
- spec incomplete -> phase 2
- no architecture doc -> phase 3
- spec complete and coding active -> phase 4
- implementation active with parity verification -> phase 5

Current project state: **Phase 4 + Phase 5 in parallel**.

- phase 4 evidence: implemented crates and packet execution artifacts
- phase 5 evidence: conformance harness, packet readiness gate, structured replay artifacts

## 6. Phase Plan (Entry/Exit Criteria)

### Phase 1: Bootstrap + Planning

- entry: missing scope/exclusion contract
- exit: scope/exclusions and success criteria frozen in this file

### Phase 2: Deep Structure Extraction

- entry: unresolved legacy behavior contracts
- exit: `EXISTING_NETWORKX_STRUCTURE.md` contains behavior, invariants, edge zones, and verification crosswalk

### Phase 3: Architecture Synthesis

- entry: no stable Rust boundary map from spec
- exit: `PROPOSED_ARCHITECTURE.md` defines module seams, strict/hardened policy boundaries, and test strategy

### Phase 4: Implementation from Spec

- entry: spec + architecture complete for target packet/family
- exit: implementation artifacts and packet docs map to spec rows without legacy line-translation dependency

### Phase 5: Conformance and QA

- entry: packet implementation complete enough for parity execution
- exit: differential parity, adversarial coverage, structured replay metadata, and durability evidence gates are green

## 7. Implementation-from-Spec Protocol

1. Identify packet/family and target section in `EXISTING_NETWORKX_STRUCTURE.md`.
2. Implement using `PROPOSED_ARCHITECTURE.md` seams.
3. Do not consult legacy code for implementation mechanics once spec section is complete.
4. Preserve strict-mode fail-closed defaults; hardened-mode deviations must be explicit and allowlisted.
5. Record deterministic replay evidence for all non-trivial validation paths.

## 8. Conformance and QA Protocol

All CPU-heavy commands are offloaded with `rch`.

```bash
rch exec -- cargo test -p fnx-conformance --test smoke -- --nocapture
rch exec -- cargo test -p fnx-conformance --test phase2c_packet_readiness_gate -- --nocapture
rch exec -- cargo test --workspace
rch exec -- cargo clippy --workspace --all-targets -- -D warnings
rch exec -- cargo fmt --check
```

## 9. Session Checklist

1. Re-read `AGENTS.md` and `README.md`.
2. Use `br ready --json` / `bv --robot-*` to choose work.
3. Reserve files and announce start in Agent Mail.
4. Implement from spec docs + packet artifacts.
5. Validate with offloaded conformance/quality gates.
6. Close/update beads, sync, release reservations, and hand off.

## 10. Exit Criteria

1. Differential parity green for scoped APIs.
2. No critical unresolved semantic drift.
3. Performance gates pass without correctness regressions.
4. RaptorQ sidecar + decode-proof artifacts validated for conformance and benchmark evidence.
