# Legacy Anchor Map

## Legacy Scope
- packet id: FNX-P2C-003
- subsystem: Dispatchable backend routing
- legacy module paths: networkx/utils/backends.py

## Anchor Map
- path: networkx/utils/backends.py
  - lines: extracted during clean-room analysis pass
  - behavior: deterministic observable contract for dispatchable backend routing

## Behavior Notes
- deterministic constraints: Backend priority sort is deterministic; Requested-backend override resolves deterministically
- compatibility-sensitive edge cases: backend route ambiguity; unknown feature bypass risk

## Compatibility Risk
- risk level: high
- rationale: dispatch route lock is required to guard compatibility-sensitive behavior.
