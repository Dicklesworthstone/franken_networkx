# Legacy Anchor Map

## Legacy Scope
- packet id: FNX-P2C-008
- subsystem: Runtime config and optional dependencies
- legacy module paths: networkx/utils/configs.py, networkx/lazy_imports.py

## Anchor Map
- path: networkx/utils/configs.py
  - lines: extracted during clean-room analysis pass
  - behavior: deterministic observable contract for runtime config and optional dependencies
- path: networkx/lazy_imports.py
  - lines: extracted during clean-room analysis pass
  - behavior: deterministic observable contract for runtime config and optional dependencies

## Behavior Notes
- deterministic constraints: Config resolution and fingerprints are deterministic; Unknown incompatible features fail closed
- compatibility-sensitive edge cases: environment-based behavior skew; optional dependency fallback ambiguity

## Compatibility Risk
- risk level: high
- rationale: runtime dependency route lock is required to guard compatibility-sensitive behavior.
