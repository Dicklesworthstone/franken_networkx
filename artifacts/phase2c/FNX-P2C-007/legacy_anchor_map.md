# Legacy Anchor Map

## Legacy Scope
- packet id: FNX-P2C-007
- subsystem: Generator first wave
- legacy module paths: networkx/generators/

## Anchor Map
- path: networkx/generators/
  - lines: extracted during clean-room analysis pass
  - behavior: deterministic observable contract for generator first wave

## Behavior Notes
- deterministic constraints: Generated node and edge ordering is deterministic; Seeded random generation remains deterministic across runs
- compatibility-sensitive edge cases: seed interpretation drift; edge emission order drift

## Compatibility Risk
- risk level: high
- rationale: generator determinism gate is required to guard compatibility-sensitive behavior.
