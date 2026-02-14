# Legacy Anchor Map

## Legacy Scope
- packet id: FNX-P2C-005
- subsystem: Shortest-path and algorithm wave
- legacy module paths: networkx/algorithms/shortest_paths/weighted.py, networkx/algorithms/centrality/, networkx/algorithms/components/

## Anchor Map
- path: networkx/algorithms/shortest_paths/weighted.py
  - lines: extracted during clean-room analysis pass
  - behavior: deterministic observable contract for shortest-path and algorithm wave
- path: networkx/algorithms/centrality/
  - lines: extracted during clean-room analysis pass
  - behavior: deterministic observable contract for shortest-path and algorithm wave
- path: networkx/algorithms/components/
  - lines: extracted during clean-room analysis pass
  - behavior: deterministic observable contract for shortest-path and algorithm wave

## Behavior Notes
- deterministic constraints: Tie-break policies remain deterministic across equal-cost paths; Component and centrality ordering is stable
- compatibility-sensitive edge cases: tie-break drift; algorithmic complexity DOS on hostile dense graphs

## Compatibility Risk
- risk level: critical
- rationale: path witness suite is required to guard compatibility-sensitive behavior.
