# Legacy Anchor Map

## Legacy Scope
- packet id: FNX-P2C-003
- subsystem: Dispatchable backend routing
- legacy module paths: networkx/utils/backends.py, networkx/utils/tests/test_backends.py, networkx/classes/tests/dispatch_interface.py, networkx/utils/tests/test_config.py
- legacy symbols: _dispatchable._call_if_any_backends_installed, _dispatchable._can_backend_run, _dispatchable._should_backend_run, _dispatchable._will_call_mutate_input, _get_cache_key, _get_from_cache, _load_backend

## Anchor Map
- region: P2C003-R1
  - pathway: normal
  - source anchors: networkx/utils/backends.py:553-716; networkx/utils/backends.py:1099-1146
  - symbols: _dispatchable._call_if_any_backends_installed, _dispatchable._can_backend_run, _dispatchable._should_backend_run
  - behavior note: Backend keyword override, can_run/should_run probes, and conversion eligibility produce deterministic backend selection with explicit failure paths.
  - compatibility policy: strict parity in route selection; hardened still fail-closed on incompatibility
  - downstream contract rows: Input Contract: compatibility mode; Output Contract: algorithm/state result; Error Contract: unknown incompatible feature
  - planned oracle tests: networkx/utils/tests/test_backends.py:44-95; networkx/utils/tests/test_backends.py:101-129
- region: P2C003-R2
  - pathway: edge
  - source anchors: networkx/utils/backends.py:717-760; networkx/utils/backends.py:1052-1075
  - symbols: _dispatchable._will_call_mutate_input, _dispatchable._call_if_any_backends_installed
  - behavior note: Mutating calls suppress automatic backend conversion and only fall back when input graph classes are compatible with NetworkX semantics.
  - compatibility policy: prefer non-conversion for mutating operations to preserve observable mutation contract
  - downstream contract rows: Input Contract: packet operations; Strict/Hardened Divergence: strict no repair heuristics; Determinism Commitments: stable traversal ordering
  - planned oracle tests: networkx/utils/tests/test_backends.py:135-160; networkx/utils/tests/test_backends.py:194-225
- region: P2C003-R3
  - pathway: adversarial
  - source anchors: networkx/utils/backends.py:202-212; networkx/utils/backends.py:561-563; networkx/utils/backends.py:640-715
  - symbols: _load_backend, _dispatchable._call_if_any_backends_installed
  - behavior note: Unknown backend names, missing implementations, and incompatible conversion paths must fail closed with explicit ImportError/TypeError semantics.
  - compatibility policy: fail-closed default for unknown or unsupported backend routes
  - downstream contract rows: Error Contract: unknown incompatible feature; Error Contract: malformed input affecting compatibility; Strict/Hardened Divergence: hardened bounded recovery only when allowlisted
  - planned oracle tests: networkx/utils/tests/test_backends.py:162-168; networkx/utils/tests/test_backends.py:170-187
- region: P2C003-R4
  - pathway: deterministic-cache
  - source anchors: networkx/utils/backends.py:1989-2010; networkx/utils/backends.py:2041-2093
  - symbols: _get_cache_key, _get_from_cache
  - behavior note: Cache key canonicalization and FAILED_TO_CONVERT sentinel behavior keep route resolution deterministic and prevent repeated incompatible conversion churn.
  - compatibility policy: cache lookup order remains deterministic before fallback/retry
  - downstream contract rows: Determinism Commitments: stable traversal and output ordering; Output Contract: evidence artifacts are replayable; Error Contract: bounded hardened behavior with audit
  - planned oracle tests: networkx/classes/tests/dispatch_interface.py:52-78; networkx/classes/tests/dispatch_interface.py:186-190; networkx/utils/tests/test_config.py:120-170

## Behavior Notes
- deterministic constraints: Backend priority sort is deterministic; Requested-backend override resolves deterministically
- compatibility-sensitive edge cases: backend route ambiguity; unknown feature bypass risk
- ambiguity resolution:
- legacy ambiguity: backend selection tie among equal priority candidates
  - policy decision: tie-break by backend name lexical order
  - rationale: removes implementation-dependent selection drift

## Extraction Ledger Crosswalk
| region id | pathway | downstream contract rows | planned oracle tests |
|---|---|---|---|
| P2C003-R1 | normal | Input Contract: compatibility mode; Output Contract: algorithm/state result; Error Contract: unknown incompatible feature | networkx/utils/tests/test_backends.py:44-95; networkx/utils/tests/test_backends.py:101-129 |
| P2C003-R2 | edge | Input Contract: packet operations; Strict/Hardened Divergence: strict no repair heuristics; Determinism Commitments: stable traversal ordering | networkx/utils/tests/test_backends.py:135-160; networkx/utils/tests/test_backends.py:194-225 |
| P2C003-R3 | adversarial | Error Contract: unknown incompatible feature; Error Contract: malformed input affecting compatibility; Strict/Hardened Divergence: hardened bounded recovery only when allowlisted | networkx/utils/tests/test_backends.py:162-168; networkx/utils/tests/test_backends.py:170-187 |
| P2C003-R4 | deterministic-cache | Determinism Commitments: stable traversal and output ordering; Output Contract: evidence artifacts are replayable; Error Contract: bounded hardened behavior with audit | networkx/classes/tests/dispatch_interface.py:52-78; networkx/classes/tests/dispatch_interface.py:186-190; networkx/utils/tests/test_config.py:120-170 |

## Compatibility Risk
- risk level: high
- rationale: dispatch route lock is required to guard compatibility-sensitive behavior.
