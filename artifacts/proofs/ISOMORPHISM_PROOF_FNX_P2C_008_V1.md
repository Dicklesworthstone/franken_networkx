# Isomorphism Proof — FNX-P2C-008 (V1)

## Baseline
- comparator: legacy_networkx/main@python3.12
- packet: FNX-P2C-008 (Runtime config and optional dependencies)

## Observable Contract
- output contract preserved under strict mode.
- hardened mode preserves API contract while applying bounded defensive controls.
- deterministic tie-break and ordering invariants maintained.

## Evidence
- fixture ids: generated/runtime_config_optional_strict.json
- parity report: artifacts/phase2c/FNX-P2C-008/parity_report.json
- raptorq sidecar: artifacts/phase2c/FNX-P2C-008/parity_report.raptorq.json
- decode proof: artifacts/phase2c/FNX-P2C-008/parity_report.decode_proof.json

## Optimization Lever
- single-pass environment fingerprint canonicalization

## Result
- status: pass
- mismatch budget: 0
