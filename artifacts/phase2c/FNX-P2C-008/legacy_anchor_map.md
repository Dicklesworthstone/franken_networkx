# Legacy Anchor Map

## Legacy Scope
- packet id: FNX-P2C-008
- subsystem: Runtime config and optional dependencies
- legacy module paths: networkx/__init__.py, networkx/utils/configs.py, networkx/utils/backends.py, networkx/lazy_imports.py
- legacy symbols: Config, BackendPriorities, NetworkXConfig, _set_configs_from_environment, _dispatchable, attach, _lazy_import, DelayedImportErrorModule

## Anchor Map
- region: P2C008-R1
  - pathway: config-core
  - source anchors: networkx/utils/configs.py:8-225; networkx/utils/tests/test_config.py:29-118; networkx/utils/tests/test_config.py:227-263
  - symbols: Config.__new__, Config.__setattr__, Config.__delattr__, Config.__call__, Config.__enter__, Config.__exit__, Config.__getitem__
  - behavior note: strict configs reject unknown keys and deletion, mapping access mirrors attribute semantics (`AttributeError` translated to `KeyError`), and context-manager updates deterministically roll back to staged previous values.
  - compatibility policy: strict mode preserves no-new-keys/no-delete envelopes and deterministic context rollback.
  - downstream contract rows: Input Contract: packet operations; Error Contract: malformed input affecting compatibility; Strict/Hardened Divergence: strict no repair heuristics
  - planned oracle tests: networkx/utils/tests/test_config.py:29-118; networkx/utils/tests/test_config.py:227-263
- region: P2C008-R2
  - pathway: backend-config-validation
  - source anchors: networkx/utils/configs.py:228-275; networkx/utils/configs.py:277-396; networkx/utils/tests/test_config.py:119-170
  - symbols: BackendPriorities._on_setattr, NetworkXConfig._on_setattr
  - behavior note: backend priority accepts list/dict/BackendPriorities normalization with strict type and unknown-backend checks, plus validated boolean and warning-set envelopes.
  - compatibility policy: unknown backend and invalid warning names fail closed with deterministic error classes/messages.
  - downstream contract rows: Error Contract: unknown incompatible feature; Input Contract: compatibility mode; Strict/Hardened Divergence: hardened bounded recovery only when allowlisted
  - planned oracle tests: networkx/utils/tests/test_config.py:119-170
- region: P2C008-R3
  - pathway: environment-bootstrap
  - source anchors: networkx/__init__.py:15-24; networkx/utils/backends.py:113-185; networkx/conftest.py:45-88
  - symbols: _set_configs_from_environment, backend_priority.algos/generators, NETWORKX_* env wiring
  - behavior note: import-time bootstrap constructs backend config from entry points, applies environment-derived defaults, and resolves backend-priority precedence (`NETWORKX_BACKEND_PRIORITY_ALGOS` over general fallback env path).
  - compatibility policy: deterministic env-to-config projection with explicit precedence and no implicit backend guessing.
  - downstream contract rows: Input Contract: packet operations; Determinism Commitments: stable traversal and output ordering; Error Contract: unknown incompatible feature
  - planned oracle tests: networkx/utils/tests/test_config.py:140-170; networkx/conftest.py:45-88
- region: P2C008-R4
  - pathway: dispatch-fallback-optional-deps
  - source anchors: networkx/utils/backends.py:202-212; networkx/utils/backends.py:621-715; networkx/utils/backends.py:717-813; networkx/utils/backends.py:879-1045; networkx/utils/tests/test_backends.py:44-95; networkx/utils/tests/test_backends.py:162-225
  - symbols: _load_backend, _dispatchable._call_if_any_backends_installed, _dispatchable._can_convert
  - behavior note: runtime dispatch computes backend try-order from input backends + priority/fallback groups, disallows backend-to-backend conversion beyond `networkx` bridge, and emits deterministic `TypeError`/`NotImplementedError` envelopes when no valid route exists.
  - compatibility policy: preserve fallback-to-networkx behavior only when configured and graph compatibility checks pass; otherwise fail closed.
  - downstream contract rows: Error Contract: unknown incompatible feature; Strict/Hardened Divergence: strict no repair heuristics; Determinism Commitments: stable traversal and output ordering
  - planned oracle tests: networkx/utils/tests/test_backends.py:44-95; networkx/utils/tests/test_backends.py:162-225
- region: P2C008-R5
  - pathway: lazy-import-proxy
  - source anchors: networkx/lazy_imports.py:11-79; networkx/lazy_imports.py:82-98; networkx/lazy_imports.py:100-188; networkx/tests/test_lazy_imports.py:9-96
  - symbols: attach, _lazy_import, DelayedImportErrorModule.__getattr__
  - behavior note: lazy proxies defer imports until attribute access, preserve module-style access semantics, and lazily surface missing-module failures with captured callsite context.
  - compatibility policy: retain delayed error surfacing and eager-import override behavior (`EAGER_IMPORT`) exactly for observable module-loading semantics.
  - downstream contract rows: Input Contract: packet operations; Error Contract: malformed input affecting compatibility; Determinism Commitments: stable traversal and output ordering
  - planned oracle tests: networkx/tests/test_lazy_imports.py:9-96

## Behavior Notes
- deterministic constraints: env/bootstrap route ordering, lazy-load trigger points, and dispatch fallback envelopes are deterministic under identical config/env inputs.
- compatibility-sensitive edge cases: truthiness of string env vars (`bool("0") is True`), backend-priority precedence collisions, mixed-backend mutation calls, and delayed-import subpackage caveats.
- undefined/ambiguous legacy regions:
  - `_lazy_import` uses broad `except` around `sys.modules` fast-path (`lazy_imports.py:160-163`), so non-KeyError failures are intentionally swallowed before spec lookup.
  - fallback-to-networkx behavior depends on both config and graph-instance compatibility checks (`backends.py:758-775`, `backends.py:788-810`).
  - when multiple unspecified backends are present, dispatch refuses tie-breaking and raises (`backends.py:902-931`, `backends.py:1023-1031`).
- ambiguity resolution:
  - legacy ambiguity: optional dependency route preference when multiple backends are available.
  - policy decision: deterministic backend priority + fail-closed on unresolved multi-backend ambiguity.
  - rationale: preserves reproducibility and prevents silent behavior drift.

## Extraction Ledger Crosswalk
| region id | pathway | downstream contract rows | planned oracle tests |
|---|---|---|---|
| P2C008-R1 | config-core | Input Contract: packet operations; Error Contract: malformed input affecting compatibility; Strict/Hardened Divergence: strict no repair heuristics | networkx/utils/tests/test_config.py:29-118; networkx/utils/tests/test_config.py:227-263 |
| P2C008-R2 | backend-config-validation | Error Contract: unknown incompatible feature; Input Contract: compatibility mode; Strict/Hardened Divergence: hardened bounded recovery only when allowlisted | networkx/utils/tests/test_config.py:119-170 |
| P2C008-R3 | environment-bootstrap | Input Contract: packet operations; Determinism Commitments: stable traversal and output ordering; Error Contract: unknown incompatible feature | networkx/utils/tests/test_config.py:140-170; networkx/conftest.py:45-88 |
| P2C008-R4 | dispatch-fallback-optional-deps | Error Contract: unknown incompatible feature; Strict/Hardened Divergence: strict no repair heuristics; Determinism Commitments: stable traversal and output ordering | networkx/utils/tests/test_backends.py:44-95; networkx/utils/tests/test_backends.py:162-225 |
| P2C008-R5 | lazy-import-proxy | Input Contract: packet operations; Error Contract: malformed input affecting compatibility; Determinism Commitments: stable traversal and output ordering | networkx/tests/test_lazy_imports.py:9-96 |

## Compatibility Risk
- risk level: high
- rationale: runtime dependency routing, env precedence, and lazy import failure surfaces are highly compatibility-sensitive and must stay deterministic.
