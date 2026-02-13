# PLAN_TO_PORT_NETWORKX_TO_RUST

## 1. Porting Methodology (Mandatory)

This project follows the spec-first porting-to-rust method:

1. Extract legacy behavior into executable specs.
2. Implement from spec, not line-by-line translation.
3. Use differential conformance to prove parity.
4. Gate optimizations behind behavior-isomorphism checks.

## 2. Legacy Oracle

- Path: /dp/franken_networkx/legacy_networkx_code/networkx

## 3. Scope for V1

- graph class semantics and mutable views\n- high-value algorithm families (flow, shortest paths, components)\n- conversion/relabel/readwrite core paths and backend dispatch

## 4. Explicit Exclusions for V1

- drawing/matplotlib and heavy optional linalg paths in V1\n- full optional backend plugin ecosystem before core parity\n- docs/examples/tooling outside runtime scope

## 5. Phase Plan

### Phase 1: Bootstrap + Planning
- finalize scope and exclusions
- freeze compatibility contract

### Phase 2: Deep Structure Extraction
- complete EXISTING_NETWORKX_STRUCTURE.md
- enumerate invariants and failure modes

### Phase 3: Architecture Synthesis
- produce crate-level design and boundaries
- define strict/hardened mode behavior

### Phase 4: Implementation
- build smallest end-to-end vertical slice
- expand by feature family with parity checks

### Phase 5: Conformance and QA
- run differential suites
- run adversarial/fuzz/property tests
- run benchmark and regression gates

## 6. Mandatory Exit Criteria

1. Differential parity green for scoped APIs.
2. No critical unresolved semantic drift.
3. Performance gates pass without correctness regressions.
4. RaptorQ sidecar artifacts validated for conformance + benchmark evidence.
