# Legacy Anchor Map

## Legacy Scope
- packet id: FNX-P2C-001
- subsystem: Graph core semantics
- legacy module paths: networkx/classes/graph.py, networkx/classes/digraph.py, networkx/classes/multigraph.py, networkx/classes/multidigraph.py

## Anchor Map
- path: networkx/classes/graph.py
  - lines: extracted during clean-room analysis pass
  - behavior: deterministic observable contract for graph core semantics
- path: networkx/classes/digraph.py
  - lines: extracted during clean-room analysis pass
  - behavior: deterministic observable contract for graph core semantics
- path: networkx/classes/multigraph.py
  - lines: extracted during clean-room analysis pass
  - behavior: deterministic observable contract for graph core semantics
- path: networkx/classes/multidigraph.py
  - lines: extracted during clean-room analysis pass
  - behavior: deterministic observable contract for graph core semantics

## Behavior Notes
- deterministic constraints: Stable node insertion ordering for graph snapshots; Deterministic edge ordering by endpoint lexical tie-break
- compatibility-sensitive edge cases: adjacency mutation drift; edge attribute merge precedence drift

## Compatibility Risk
- risk level: critical
- rationale: mutation invariant replay is required to guard compatibility-sensitive behavior.
