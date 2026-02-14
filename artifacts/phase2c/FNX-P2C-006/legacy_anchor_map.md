# Legacy Anchor Map

## Legacy Scope
- packet id: FNX-P2C-006
- subsystem: Read/write edgelist and json graph
- legacy module paths: networkx/readwrite/edgelist.py, networkx/readwrite/json_graph/

## Anchor Map
- path: networkx/readwrite/edgelist.py
  - lines: extracted during clean-room analysis pass
  - behavior: deterministic observable contract for read/write edgelist and json graph
- path: networkx/readwrite/json_graph/
  - lines: extracted during clean-room analysis pass
  - behavior: deterministic observable contract for read/write edgelist and json graph

## Behavior Notes
- deterministic constraints: Round-trip serialization remains deterministic; Malformed line handling is deterministic by mode policy
- compatibility-sensitive edge cases: parser ambiguity; serialization round-trip drift

## Compatibility Risk
- risk level: high
- rationale: parser adversarial gate is required to guard compatibility-sensitive behavior.
