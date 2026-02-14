# Legacy Anchor Map

## Legacy Scope
- packet id: FNX-P2C-002
- subsystem: View layer semantics
- legacy module paths: networkx/classes/coreviews.py, networkx/classes/graphviews.py

## Anchor Map
- path: networkx/classes/coreviews.py
  - lines: extracted during clean-room analysis pass
  - behavior: deterministic observable contract for view layer semantics
- path: networkx/classes/graphviews.py
  - lines: extracted during clean-room analysis pass
  - behavior: deterministic observable contract for view layer semantics

## Behavior Notes
- deterministic constraints: View adjacency iteration order is deterministic; Revision-aware cache invalidation remains deterministic
- compatibility-sensitive edge cases: stale cache exposure; projection filter nondeterminism

## Compatibility Risk
- risk level: high
- rationale: view coherence witness gate is required to guard compatibility-sensitive behavior.
