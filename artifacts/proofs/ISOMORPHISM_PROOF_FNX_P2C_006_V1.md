# Isomorphism Proof — FNX-P2C-006 (V1)

## Baseline
- comparator: legacy_networkx/main@python3.12
- packet: FNX-P2C-006 (Read/write edgelist and json graph)

## Observable Contract
- output contract preserved under strict mode.
- hardened mode preserves API contract while applying bounded defensive controls.
- deterministic tie-break and ordering invariants maintained.

## Evidence
- fixture ids: generated/readwrite_roundtrip_strict.json, generated/readwrite_hardened_malformed.json, generated/readwrite_json_roundtrip_strict.json
- parity report: artifacts/phase2c/FNX-P2C-006/parity_report.json
- raptorq sidecar: artifacts/phase2c/FNX-P2C-006/parity_report.raptorq.json
- decode proof: artifacts/phase2c/FNX-P2C-006/parity_report.decode_proof.json

## Optimization Lever
- streaming parse buffer reuse

## Result
- status: pass
- mismatch budget: 0
