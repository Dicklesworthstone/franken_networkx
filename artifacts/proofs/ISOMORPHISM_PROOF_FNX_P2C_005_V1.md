# Isomorphism Proof — FNX-P2C-005 (V1)

## Baseline
- comparator: legacy_networkx/main@python3.12
- packet: FNX-P2C-005 (Shortest-path and algorithm wave)

## Observable Contract
- output contract preserved under strict mode.
- hardened mode preserves API contract while applying bounded defensive controls.
- deterministic tie-break and ordering invariants maintained.

## Evidence
- fixture ids: graph_core_shortest_path_strict.json, generated/centrality_degree_strict.json, generated/centrality_closeness_strict.json, generated/components_connected_strict.json
- parity report: artifacts/phase2c/FNX-P2C-005/parity_report.json
- raptorq sidecar: artifacts/phase2c/FNX-P2C-005/parity_report.raptorq.json
- decode proof: artifacts/phase2c/FNX-P2C-005/parity_report.decode_proof.json

## Optimization Lever
- priority-queue hot loop allocation reduction

## Result
- status: pass
- mismatch budget: 0
