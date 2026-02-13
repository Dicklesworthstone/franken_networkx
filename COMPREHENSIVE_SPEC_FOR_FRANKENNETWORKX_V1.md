# COMPREHENSIVE_SPEC_FOR_FRANKENNETWORKX_V1

## 0. Prime Directive

Build a system that is simultaneously:

1. Behaviorally trustworthy for scoped compatibility.
2. Mathematically explicit in decision and risk handling.
3. Operationally resilient via RaptorQ-backed durability.
4. Performance-competitive via profile-and-proof discipline.

Crown-jewel innovation:

Canonical Graph Semantics Engine (CGSE): deterministic tie-break policies with complexity witness artifacts per algorithm family.

Legacy oracle:

- /dp/franken_networkx/legacy_networkx_code/networkx
- upstream: https://github.com/networkx/networkx

FrankenSQLite exemplar reference (copied locally for direct consultation):

- `reference_specs/COMPREHENSIVE_SPEC_FOR_FRANKENSQLITE_V1.md`

## 1. Product Thesis

Most reimplementations fail by being partially compatible and operationally brittle. FrankenNetworkX will instead combine compatibility realism with first-principles architecture and strict quality gates.

## 2. V1 Scope Contract

Included in V1:

- Graph, DiGraph, MultiGraph core semantics; - shortest path/components/centrality/flow scoped sets; - serialization core formats.

Deferred from V1:

- long-tail API surface outside highest-value use cases
- broad ecosystem parity not required for core migration value
- distributed/platform expansion not needed for V1 acceptance

## 3. Architecture Blueprint

graph API -> graph storage -> algorithm modules -> analysis and serialization

Planned crate families:
- fnx-types
- fnx-graph
- fnx-algo-shortestpath
- fnx-algo-components
- fnx-algo-centrality
- fnx-algo-flow
- fnx-algo-matching
- fnx-io
- fnx-durability
- fnx-conformance
- franken_networkx

## 4. Compatibility Model (frankenlibc/frankenfs-inspired)

Two explicit operating modes:

1. strict mode:
   - maximize observable compatibility for scoped APIs
   - no behavior-altering repair heuristics
2. hardened mode:
   - maintain outward contract while enabling defensive runtime checks and bounded repairs

Compatibility focus for this project:

Preserve NetworkX-observable algorithm outputs, tie-break behavior, and graph mutation semantics for scoped APIs.

Fail-closed policy:

- unknown incompatible features or protocol fields must fail closed by default
- compatibility exceptions require explicit allowlist entries and audit traces

## 5. Security Model

Security focus for this project:

Defend against malformed graph ingestion, attribute confusion, and algorithmic denial vectors on adversarial graphs.

Threat model baseline:

1. malformed input and parser abuse
2. state-machine desynchronization
3. downgrade and compatibility confusion paths
4. persistence corruption and replay tampering

Mandatory controls:

- adversarial fixtures and fuzz/property suites for high-risk entry points
- deterministic audit trail for recoveries and mode/policy overrides
- explicit subsystem ownership and trust-boundary notes

## 6. Alien-Artifact Decision Layer

Runtime controllers (scheduling, adaptation, fallback, admission) must document:

1. state space
2. evidence signals
3. loss matrix with asymmetric costs
4. posterior or confidence update model
5. action rule minimizing expected loss
6. calibration fallback trigger

Output requirements:

- evidence ledger entries for consequential decisions
- calibrated confidence metrics and drift alarms

## 7. Extreme Optimization Contract

Track algorithm runtime tails and memory by graph size/density; gate complexity regressions for adversarial classes.

Optimization loop is mandatory:

1. baseline metrics
2. hotspot profile
3. single-lever optimization
4. behavior-isomorphism proof
5. re-profile and compare

No optimization is accepted without associated correctness evidence.

## 8. Correctness and Conformance Contract

Maintain deterministic graph semantics, tie-break policies, and serialization round-trip invariants.

Conformance process:

1. generate canonical fixture corpus
2. run legacy oracle and capture normalized outputs
3. run FrankenNetworkX and compare under explicit equality/tolerance policy
4. produce machine-readable parity report artifact

Assurance ladder:

- Tier A: unit/integration/golden fixtures
- Tier B: differential conformance
- Tier C: property/fuzz/adversarial tests
- Tier D: regression corpus for historical failures

## 9. RaptorQ-Everywhere Durability Contract

RaptorQ repair-symbol sidecars are required for long-lived project evidence:

1. conformance snapshots
2. benchmark baselines
3. migration manifests
4. reproducibility ledgers
5. release-grade state artifacts

Required artifacts:

- symbol generation manifest
- scrub verification report
- decode proof for each recovery event

## 10. Milestones and Exit Criteria

### M0 — Bootstrap

- workspace skeleton
- CI and quality gate wiring

Exit:
- fmt/check/clippy/test baseline green

### M1 — Core Model

- core data/runtime structures
- first invariant suite

Exit:
- invariant suite green
- first conformance fixtures passing

### M2 — First Vertical Slice

- end-to-end scoped workflow implemented

Exit:
- differential parity for first major API family
- baseline benchmark report published

### M3 — Scope Expansion

- additional V1 API families

Exit:
- expanded parity reports green
- no unresolved critical compatibility defects

### M4 — Hardening

- adversarial coverage and perf hardening

Exit:
- regression gates stable
- conformance drift zero for V1 scope

## 11. Acceptance Gates

Gate A: compatibility parity report passes for V1 scope.

Gate B: security/fuzz/adversarial suite passes for high-risk paths.

Gate C: performance budgets pass with no semantic regressions.

Gate D: RaptorQ durability artifacts validated and scrub-clean.

All four gates must pass for V1 release readiness.

## 12. Risk Register

Primary risk focus:

Nondeterministic ordering and complexity regressions that evade shallow correctness tests.

Mitigations:

1. compatibility-first development for risky API families
2. explicit invariants and adversarial tests
3. profile-driven optimization with proof artifacts
4. strict mode/hardened mode separation with audited policy transitions
5. RaptorQ-backed resilience for critical persistent artifacts

## 13. Immediate Execution Checklist

1. Create workspace and crate skeleton.
2. Implement smallest high-value end-to-end path in V1 scope.
3. Stand up differential conformance harness against legacy oracle.
4. Add benchmark baseline generation and regression gating.
5. Add RaptorQ sidecar pipeline for conformance and benchmark artifacts.

## 14. Detailed Crate Contracts (V1)

| Crate | Primary Responsibility | Explicit Non-Goal | Invariants | Mandatory Tests |
|---|---|---|---|---|
| fnx-types | graph metadata, node/edge attribute policy types | algorithm execution | stable metadata encoding and deterministic key handling | metadata matrix tests |
| fnx-graph | core Graph/DiGraph/MultiGraph mutation model | algorithm implementations | mutation semantics and adjacency consistency preserved | graph mutation parity fixtures |
| fnx-algo-shortestpath | shortest-path first-wave algorithms | flow/matching algorithms | path/tie-break semantics deterministic | shortest-path parity corpus |
| fnx-algo-components | connected/strongly connected component routines | shortest-path logic | component partition determinism | component parity fixtures |
| fnx-algo-centrality | scoped centrality routines | full metric ecosystem parity | centrality output ordering/tolerance policy explicit | centrality differential tests |
| fnx-algo-flow | scoped flow routines | matching domain | flow value/invariant semantics preserved | flow parity fixtures |
| fnx-algo-matching | scoped matching routines | full combinatorial optimization parity | matching validity and determinism | matching parity fixtures |
| fnx-io | graph read/write format bridges | algorithm logic | round-trip and parser error contracts stable | GraphML/edgelist/GEXF fixtures |
| fnx-conformance | differential harness vs NetworkX oracle | production serving | comparison policy explicit per algorithm family | report schema + runner tests |
| franken_networkx | integration binary/library and policy loading | algorithm design | strict/hardened mode wiring + evidence logging | mode gate/startup tests |

## 15. Conformance Matrix (V1)

| Family | Oracle Workload | Pass Criterion | Drift Severity |
|---|---|---|---|
| core graph mutation semantics | add/remove/update fixture corpus | adjacency + attribute parity | critical |
| view behavior and cache reset | graph/coreview fixture corpus | view output + cache coherence parity | high |
| shortest-path first wave | weighted/unweighted path fixtures | path and distance parity with tie-break policy | critical |
| component analysis | connected/strongly connected fixtures | component partition parity | high |
| centrality first wave | scoped centrality fixtures | score parity under tolerance policy | high |
| flow/matching first wave | scoped flow/matching fixtures | value + structural parity | high |
| read/write format parity | graphml/gexf/edgelist fixtures | round-trip + parser error parity | critical |
| mixed E2E workflow | parse -> mutate -> analyze -> serialize | reproducible parity report with no critical drift | critical |

## 16. Security and Compatibility Threat Matrix

| Threat | Strict Mode Response | Hardened Mode Response | Required Artifact |
|---|---|---|---|
| malformed graph ingestion | fail-closed parse/validation error | fail-closed with bounded diagnostics | parser incident ledger |
| attribute confusion and type abuse | reject incompatible attribute forms | reject + policy trace | attribute decision ledger |
| adversarial graph complexity attack | execute scoped semantics | admission guards with explicit reject path | admission decision log |
| backend dispatch ambiguity | fail-closed | fail-closed unless allowlisted route | backend route ledger |
| unknown format metadata | fail-closed | fail-closed | compatibility drift report |
| oracle mismatch in conformance | hard fail | hard fail | conformance failure bundle |
| artifact corruption | reject load | recover via RaptorQ when provable | decode proof + scrub report |
| override misuse | explicit override + audit trail | explicit override + audit trail | override audit record |

## 17. Performance Budgets and SLO Targets

| Path | Workload Class | Budget |
|---|---|---|
| shortest-path hot path | large sparse weighted graphs | p95 <= 420 ms |
| component discovery | million-edge graph class | p95 <= 280 ms |
| centrality first wave | medium-large graph class | p95 <= 950 ms |
| flow first wave | scoped flow benchmark corpus | p95 <= 700 ms |
| graph read/write round-trip | medium-large serialized graphs | throughput >= 45 MB/s |
| mutation-heavy graph updates | repeated add/remove workloads | p95 regression <= +8% |
| memory footprint | mixed E2E graph workflow | peak RSS regression <= +10% |
| tail stability | all benchmark families | p99 regression <= +10% |

Optimization acceptance rule:
1. primary metric improves or remains within budget,
2. no critical conformance drift,
3. p99 and memory budgets remain within limits.

## 18. CI Gate Topology (Release-Critical)

| Gate | Name | Blocking | Output Artifact |
|---|---|---|---|
| G1 | format + lint | yes | lint report |
| G2 | unit + integration | yes | junit report |
| G3 | differential conformance | yes | parity report JSON + markdown summary |
| G4 | adversarial + property tests | yes | minimized counterexample corpus |
| G5 | benchmark regression | yes | baseline delta report |
| G6 | RaptorQ scrub + recovery drill | yes | scrub report + decode proof sample |

Release cannot proceed unless all gates pass on the same commit.

## 19. RaptorQ Artifact Envelope (Project-Wide)

Persistent evidence artifacts must be emitted with sidecars:
1. source artifact hash manifest,
2. RaptorQ symbol manifest,
3. scrub status,
4. decode proof log when recovery occurs.

Canonical envelope schema:

~~~json
{
  "artifact_id": "string",
  "artifact_type": "conformance|benchmark|ledger|manifest",
  "source_hash": "blake3:...",
  "raptorq": {
    "k": 0,
    "repair_symbols": 0,
    "overhead_ratio": 0.0,
    "symbol_hashes": ["..."]
  },
  "scrub": {
    "last_ok_unix_ms": 0,
    "status": "ok|recovered|failed"
  },
  "decode_proofs": [
    {
      "ts_unix_ms": 0,
      "reason": "...",
      "recovered_blocks": 0,
      "proof_hash": "blake3:..."
    }
  ]
}
~~~

## 20. 90-Day Execution Plan

Weeks 1-2:
- scaffold workspace and crate boundaries
- finalize graph + algorithm conformance schema

Weeks 3-5:
- implement fnx-types/fnx-graph/fnx-io minimum vertical slice
- land first strict-mode differential conformance reports

Weeks 6-8:
- implement shortest-path/components/centrality first wave
- publish benchmark baselines against section-17 budgets

Weeks 9-10:
- harden parser/dispatch/adversarial graph pathways
- finalize strict/hardened policy transitions and audit trails

Weeks 11-12:
- enforce full gate topology G1-G6 in CI
- run release-candidate drill with complete artifact envelope

## 21. Porting Artifact Index

This spec is paired with the following methodology artifacts:

1. PLAN_TO_PORT_NETWORKX_TO_RUST.md
2. EXISTING_NETWORKX_STRUCTURE.md
3. PROPOSED_ARCHITECTURE.md
4. FEATURE_PARITY.md

Rule of use:

- Extraction and behavior understanding happens in EXISTING_NETWORKX_STRUCTURE.md.
- Scope, exclusions, and phase sequencing live in PLAN_TO_PORT_NETWORKX_TO_RUST.md.
- Rust crate boundaries live in PROPOSED_ARCHITECTURE.md.
- Delivery readiness is tracked in FEATURE_PARITY.md.
