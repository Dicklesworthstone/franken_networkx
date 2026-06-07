# FRANKENSQLITE_CROSSWALK

Purpose: map FrankenSQLite V1 patterns onto FrankenNetworkX implementation law.

Reference:
- `reference_specs/COMPREHENSIVE_SPEC_FOR_FRANKENSQLITE_V1.md`

## 1. Direct Pattern Transfer

1. Gate topology:
- adopt release-blocking gates for lint/test/conformance/perf/durability as first-class artifacts.

2. Artifact envelope:
- conformance and benchmark outputs must be emitted with hash manifests and durability sidecars.

3. Strict vs hardened mode:
- strict = maximum observable compatibility.
- hardened = same API contract with bounded defensive checks.

4. Evidence-ledger decision core:
- consequential runtime decisions must emit machine-readable evidence records.

5. Profile-first optimization:
- baseline -> profile -> one lever -> isomorphism proof -> re-baseline.

## 2. FrankenNetworkX Adaptation

1. Graph semantics become the non-regression kernel:
- deterministic mutation and tie-break semantics are correctness-critical.

2. Complexity witness artifacts:
- each algorithm family emits operation counters and complexity claims.

3. Adversarial graph threat model:
- malformed graph ingestion,
- attribute confusion,
- algorithmic denial on hostile graph shapes.

## 3. Current Status

- Runtime decision ledger: implemented (`fnx-runtime`).
- Deterministic graph core: implemented (`fnx-classes`).
- First algorithm witness path: implemented (`fnx-algorithms`).
- Differential fixture harness: implemented (`fnx-conformance`).
- Full RaptorQ sidecar generation and recovery drill: implemented (`fnx-durability` + `scripts/run_conformance_with_durability.sh`).

## 4. Next Mandatory Moves

1. Expand conformance fixtures from legacy oracle test families.
2. Add benchmark corpus with p50/p95/p99 + RSS gates.
3. Expand sidecar coverage from conformance reports to benchmark and migration artifacts.
4. Implement dispatch/convert/readwrite crates with strict/hardened drift gates.
