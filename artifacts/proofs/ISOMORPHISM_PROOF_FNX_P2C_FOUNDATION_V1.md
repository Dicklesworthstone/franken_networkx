# Isomorphism Proof — FNX-P2C-FOUNDATION (V1)

## Baseline
- comparator: legacy_networkx/main@python3.12
- packet: FNX-P2C-FOUNDATION (Phase2C governance foundation)

## Observable Contract
- output contract preserved under strict mode.
- hardened mode preserves API contract while applying bounded defensive controls.
- deterministic tie-break and ordering invariants maintained.

## Evidence
- fixture ids: generated/centrality_degree_strict.json, generated/centrality_closeness_strict.json
- parity report: artifacts/phase2c/FNX-P2C-FOUNDATION/parity_report.json
- raptorq sidecar: artifacts/phase2c/FNX-P2C-FOUNDATION/parity_report.raptorq.json
- decode proof: artifacts/phase2c/FNX-P2C-FOUNDATION/parity_report.decode_proof.json

## Optimization Lever
- validator single-pass artifact key dispatch

## Result
- status: pass
- mismatch budget: 0
