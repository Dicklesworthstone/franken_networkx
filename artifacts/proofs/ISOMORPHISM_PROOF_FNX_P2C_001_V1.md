# Isomorphism Proof — FNX-P2C-001 (V1)

## Baseline
- comparator: legacy_networkx/main@python3.12
- packet: FNX-P2C-001 (Graph core semantics)

## Observable Contract
- output contract preserved under strict mode.
- hardened mode preserves API contract while applying bounded defensive controls.
- deterministic tie-break and ordering invariants maintained.

## Evidence
- fixture ids: graph_core_mutation_hardened.json, graph_core_shortest_path_strict.json
- parity report: artifacts/phase2c/FNX-P2C-001/parity_report.json
- raptorq sidecar: artifacts/phase2c/FNX-P2C-001/parity_report.raptorq.json
- decode proof: artifacts/phase2c/FNX-P2C-001/parity_report.decode_proof.json

## Optimization Lever
- neighbor iteration clone elision under witness checks

## Result
- status: pass
- mismatch budget: 0
