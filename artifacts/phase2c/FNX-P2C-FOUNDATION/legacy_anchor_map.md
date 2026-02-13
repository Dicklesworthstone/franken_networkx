# Legacy Anchor Map

## Legacy Scope
- packet id: FNX-P2C-FOUNDATION
- legacy module paths: networkx/classes, networkx/algorithms, networkx/readwrite

## Anchor Map
- path: networkx/classes/graph.py
  - lines: mutation and adjacency semantics
  - behavior: deterministic observable graph contracts for scoped APIs

## Behavior Notes
- deterministic constraints: stable node and edge ordering in scoped outputs
- compatibility-sensitive edge cases: malformed input handling under strict vs hardened modes

## Compatibility Risk
- risk level: medium
- rationale: schema drift can silently break downstream packet automation
