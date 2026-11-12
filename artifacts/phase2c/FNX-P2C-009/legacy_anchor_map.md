# Legacy Anchor Map

## Legacy Scope
- packet id: FNX-P2C-009
- subsystem: Conformance harness corpus wiring
- legacy module paths: networkx/tests/, networkx/algorithms/tests/

## Anchor Map
- path: networkx/tests/
  - lines: extracted during clean-room analysis pass
  - behavior: deterministic observable contract for conformance harness corpus wiring
- path: networkx/algorithms/tests/
  - lines: extracted during clean-room analysis pass
  - behavior: deterministic observable contract for conformance harness corpus wiring

## Behavior Notes
- deterministic constraints: Fixture ordering and packet routing are deterministic; Replay command and forensics bundle links are deterministic
- compatibility-sensitive edge cases: fixture routing drift; log schema drift

## Compatibility Risk
- risk level: high
- rationale: harness normalization lock is required to guard compatibility-sensitive behavior.
