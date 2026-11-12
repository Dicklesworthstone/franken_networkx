# Legacy Anchor Map

## Legacy Scope
- packet id: FNX-P2C-005
- subsystem: Shortest-path and algorithm wave
- legacy module paths: networkx/algorithms/shortest_paths/weighted.py, networkx/algorithms/centrality/, networkx/algorithms/components/
- legacy symbols: _weight_function, dijkstra_path, bellman_ford_path, bidirectional_dijkstra

## Anchor Map
- region: P2C005-R1
  - pathway: normal
  - source anchors: networkx/algorithms/shortest_paths/weighted.py:41-123; networkx/algorithms/shortest_paths/weighted.py:393-430; networkx/algorithms/shortest_paths/weighted.py:784-907
  - symbols: _weight_function, dijkstra_path, single_source_dijkstra, _dijkstra_multisource
  - behavior note: Weighted shortest-path entrypoints and multisource queue expansion preserve deterministic distance/path behavior, including stable predecessor-path reconstruction for equal-cost frontier expansion.
  - compatibility policy: strict mode preserves weighted shortest-path outputs and tie-break ordering exactly
  - downstream contract rows: Input Contract: packet operations; Output Contract: algorithm/state result; Determinism Commitments: stable traversal and output ordering
  - planned oracle tests: networkx/algorithms/shortest_paths/tests/test_weighted.py:113-198; networkx/algorithms/shortest_paths/tests/test_weighted.py:271-330
- region: P2C005-R2
  - pathway: edge
  - source anchors: networkx/algorithms/shortest_paths/weighted.py:41-78; networkx/algorithms/shortest_paths/weighted.py:862-885; networkx/algorithms/shortest_paths/weighted.py:2310-2380
  - symbols: _weight_function, _dijkstra_multisource, bidirectional_dijkstra
  - behavior note: Multigraph weight selection uses minimum parallel-edge cost and hidden-edge semantics (weight callback returns None) are handled deterministically without accidental frontier drift.
  - compatibility policy: retain legacy multigraph minimum-weight and hidden-edge semantics across all weighted APIs
  - downstream contract rows: Input Contract: compatibility mode; Output Contract: algorithm/state result; Strict/Hardened Divergence: strict no repair heuristics
  - planned oracle tests: networkx/algorithms/shortest_paths/tests/test_weighted.py:199-241; networkx/algorithms/shortest_paths/tests/test_weighted.py:316-329; networkx/algorithms/shortest_paths/tests/test_weighted.py:358-388
- region: P2C005-R3
  - pathway: adversarial
  - source anchors: networkx/algorithms/shortest_paths/weighted.py:1493-1510; networkx/algorithms/shortest_paths/weighted.py:1514-1640; networkx/algorithms/shortest_paths/weighted.py:2280-2306
  - symbols: bellman_ford_path, single_source_bellman_ford, negative_edge_cycle, bidirectional_dijkstra
  - behavior note: Negative-cycle detection, contradictory-path guards, and unreachable/absent-node pathways must fail closed with explicit ValueError/NodeNotFound/NetworkXUnbounded envelopes.
  - compatibility policy: strict fail-closed on negative-cycle and malformed-source conditions; no silent repair
  - downstream contract rows: Error Contract: malformed input affecting compatibility; Error Contract: unknown incompatible feature; Strict/Hardened Divergence: hardened bounded recovery only when allowlisted
  - planned oracle tests: networkx/algorithms/shortest_paths/tests/test_weighted.py:245-347; networkx/algorithms/shortest_paths/tests/test_weighted.py:533-610; networkx/algorithms/shortest_paths/tests/test_weighted.py:872-889
- region: P2C005-R4
  - pathway: centrality-components
  - source anchors: networkx/algorithms/centrality/degree_alg.py:10-50; networkx/algorithms/centrality/closeness.py:14-136; networkx/algorithms/components/connected.py:18-149
  - symbols: degree_centrality, closeness_centrality, connected_components, number_connected_components
  - behavior note: Degree/closeness/component calculations keep deterministic normalization and traversal semantics, including closeness inward-distance policy for directed graphs and stable component partition outputs.
  - compatibility policy: preserve legacy normalization and directed-distance orientation semantics exactly
  - downstream contract rows: Output Contract: algorithm/state result; Determinism Commitments: stable traversal and output ordering; Input Contract: packet operations
  - planned oracle tests: networkx/algorithms/centrality/tests/test_degree_centrality.py:50-102; networkx/algorithms/centrality/tests/test_closeness_centrality.py:18-37; networkx/algorithms/centrality/tests/test_closeness_centrality.py:178-197; networkx/algorithms/components/tests/test_connected.py:64-111
- region: P2C005-R5
  - pathway: adversarial-dispatch-loopback
  - source anchors: networkx/algorithms/components/connected.py:16-47; networkx/algorithms/components/tests/test_connected.py:75-97
  - symbols: connected_components
  - behavior note: Dispatchable-loopback execution for connected-components raises deterministic import failures when unknown backends are configured, preventing ambiguous backend fallback.
  - compatibility policy: fail closed for unregistered backends while preserving loopback fast-path determinism
  - downstream contract rows: Error Contract: unknown incompatible feature; Input Contract: compatibility mode; Determinism Commitments: stable traversal and output ordering
  - planned oracle tests: networkx/algorithms/components/tests/test_connected.py:75-97; networkx/algorithms/components/tests/test_connected.py:124-130

## Behavior Notes
- deterministic constraints: Tie-break policies remain deterministic across equal-cost paths; Component and centrality ordering is stable
- compatibility-sensitive edge cases: tie-break drift; algorithmic complexity DOS on hostile dense graphs
- ambiguity resolution:
- legacy ambiguity: equal-weight multi-path tie-breaks
  - policy decision: canonical path comparison by lexical node sequence
  - rationale: locks observable results under adversarial equal-weight graphs
- legacy ambiguity: directed closeness orientation (inward vs outward distance)
  - policy decision: preserve inward-distance default and require explicit reverse() for outward mode
  - rationale: matches documented NetworkX semantics and avoids directional drift

## Extraction Ledger Crosswalk
| region id | pathway | downstream contract rows | planned oracle tests |
|---|---|---|---|
| P2C005-R1 | normal | Input Contract: packet operations; Output Contract: algorithm/state result; Determinism Commitments: stable traversal and output ordering | networkx/algorithms/shortest_paths/tests/test_weighted.py:113-198; networkx/algorithms/shortest_paths/tests/test_weighted.py:271-330 |
| P2C005-R2 | edge | Input Contract: compatibility mode; Output Contract: algorithm/state result; Strict/Hardened Divergence: strict no repair heuristics | networkx/algorithms/shortest_paths/tests/test_weighted.py:199-241; networkx/algorithms/shortest_paths/tests/test_weighted.py:316-329; networkx/algorithms/shortest_paths/tests/test_weighted.py:358-388 |
| P2C005-R3 | adversarial | Error Contract: malformed input affecting compatibility; Error Contract: unknown incompatible feature; Strict/Hardened Divergence: hardened bounded recovery only when allowlisted | networkx/algorithms/shortest_paths/tests/test_weighted.py:245-347; networkx/algorithms/shortest_paths/tests/test_weighted.py:533-610; networkx/algorithms/shortest_paths/tests/test_weighted.py:872-889 |
| P2C005-R4 | centrality-components | Output Contract: algorithm/state result; Determinism Commitments: stable traversal and output ordering; Input Contract: packet operations | networkx/algorithms/centrality/tests/test_degree_centrality.py:50-102; networkx/algorithms/centrality/tests/test_closeness_centrality.py:18-37; networkx/algorithms/centrality/tests/test_closeness_centrality.py:178-197; networkx/algorithms/components/tests/test_connected.py:64-111 |
| P2C005-R5 | adversarial-dispatch-loopback | Error Contract: unknown incompatible feature; Input Contract: compatibility mode; Determinism Commitments: stable traversal and output ordering | networkx/algorithms/components/tests/test_connected.py:75-97; networkx/algorithms/components/tests/test_connected.py:124-130 |

## Compatibility Risk
- risk level: critical
- rationale: path witness suite is required to guard compatibility-sensitive behavior.
