# Isomorphism Proof — FNX-P2C-007 (V1)

## Baseline
- comparator: legacy_networkx/main@python3.12
- packet: FNX-P2C-007 (Generator first wave)

## Observable Contract
- output contract preserved under strict mode.
- hardened mode preserves API contract while applying bounded defensive controls.
- deterministic tie-break and ordering invariants maintained.

## Evidence
- fixture ids: generated/generators_path_strict.json, generated/generators_cycle_strict.json, generated/generators_complete_strict.json
- parity report: artifacts/phase2c/FNX-P2C-007/parity_report.json
- raptorq sidecar: artifacts/phase2c/FNX-P2C-007/parity_report.raptorq.json
- decode proof: artifacts/phase2c/FNX-P2C-007/parity_report.decode_proof.json

## Optimization Lever
- pre-sized edge emission buffers

## Result
- status: pass
- mismatch budget: 0
