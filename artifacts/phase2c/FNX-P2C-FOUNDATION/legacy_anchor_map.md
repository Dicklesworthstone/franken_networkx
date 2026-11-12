# Legacy Anchor Map

## Legacy Scope
- packet id: FNX-P2C-FOUNDATION
- subsystem: Phase2C governance foundation
- legacy module paths: networkx/classes, networkx/algorithms, networkx/readwrite

## Anchor Map
- path: networkx/classes
  - lines: extracted during clean-room analysis pass
  - behavior: deterministic observable contract for phase2c governance foundation
- path: networkx/algorithms
  - lines: extracted during clean-room analysis pass
  - behavior: deterministic observable contract for phase2c governance foundation
- path: networkx/readwrite
  - lines: extracted during clean-room analysis pass
  - behavior: deterministic observable contract for phase2c governance foundation

## Behavior Notes
- deterministic constraints: Packet readiness ordering remains deterministic; Schema contract evaluation is deterministic
- compatibility-sensitive edge cases: schema drift; packet omission

## Compatibility Risk
- risk level: medium
- rationale: topology schema lock is required to guard compatibility-sensitive behavior.
