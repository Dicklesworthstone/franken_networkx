# Contract Table

## Input Contract
| row id | API/behavior | preconditions | strict policy | hardened policy | legacy anchor regions | required validations |
|---|---|---|---|---|---|---|
| P2C008-IC-1 | Config object mutation semantics (`Config` strict mode) | config fields are known at construction and updates occur via attribute/mapping paths | reject unknown keys and deletes; preserve deterministic context rollback behavior | same schema-level contract; only bounded audit metadata may be added | P2C008-R1 | networkx/utils/tests/test_config.py:29-118; networkx/utils/tests/test_config.py:227-263 |
| P2C008-IC-2 | Backend priority normalization (`backend_priority`) | incoming value is list/dict/BackendPriorities and backend names are expected to be registered | enforce strict type checks and unknown-backend rejection with fail-closed envelopes | same input schema checks; bounded diagnostics only on allowlisted categories | P2C008-R2 | networkx/utils/tests/test_config.py:119-170; networkx/utils/configs.py:351-380 |
| P2C008-IC-3 | Environment bootstrap to runtime config | import-time environment variables are read once and projected into config fields | preserve deterministic env precedence and no implicit backend guessing | same precedence with bounded telemetry enrichment only | P2C008-R3 | networkx/utils/backends.py:118-185; networkx/__init__.py:15-24 |
| P2C008-IC-4 | Dispatch backend route inputs | runtime call includes backend kwarg, resolved graph backends, and conversion eligibility | deterministic route ordering; no ambiguous conversion across multiple unspecified backends | same route ordering; bounded fallback only under explicit policy gates | P2C008-R4 | networkx/utils/backends.py:621-715; networkx/utils/backends.py:879-1045 |
| P2C008-IC-5 | Lazy import attachment contract | module export surface is declared via `attach` and optional eager-import env toggle | lazy import must preserve module attribute surface and delayed error behavior exactly | same surface; no hidden fallback imports on unknown symbols | P2C008-R5 | networkx/lazy_imports.py:11-79; networkx/tests/test_lazy_imports.py:70-96 |

## Output Contract
| row id | output behavior | postconditions | strict policy | hardened policy | legacy anchor regions | required validations |
|---|---|---|---|---|---|---|
| P2C008-OC-1 | Config mapping/attribute parity | get/set/del behavior and equality/pickle semantics remain stable | zero drift for key/value visibility and rollback behavior | same observable mapping semantics | P2C008-R1 | networkx/utils/tests/test_config.py:29-118 |
| P2C008-OC-2 | Backend dispatch route determinism | selected backend and fallback decision are reproducible for identical inputs/config | deterministic try-order with fail-closed ambiguity handling | same route selection plus bounded fallback when explicitly enabled | P2C008-R3; P2C008-R4 | networkx/utils/backends.py:879-945; generated/runtime_config_optional_strict.json |
| P2C008-OC-3 | Optional dependency integration envelope | missing/unsupported backend pathways surface deterministic fail-closed diagnostics | no silent conversion or implicit backend substitution | same API contract with bounded diagnostics only | P2C008-R4 | networkx/utils/tests/test_backends.py:93-95; networkx/utils/tests/test_backends.py:162-168 |
| P2C008-OC-4 | Lazy import proxy behavior | module loads on first attribute access and missing modules raise delayed callsite-aware errors | preserve delayed `ModuleNotFoundError` behavior | same delayed error contract; no eager mutation of module registry beyond specified behavior | P2C008-R5 | networkx/tests/test_lazy_imports.py:9-68 |

## Error Contract
| row id | trigger | strict behavior | hardened behavior | allowlisted divergence category | legacy anchor regions | required validations |
|---|---|---|---|---|---|---|
| P2C008-EC-1 | unknown backend name in backend-priority or backend kwarg | fail closed with deterministic `ValueError`/`ImportError` envelope | same fail-closed default; diagnostics may annotate allowlisted context only | bounded_diagnostic_enrichment | P2C008-R2; P2C008-R4 | networkx/utils/tests/test_config.py:125-132; networkx/utils/tests/test_backends.py:162-168 |
| P2C008-EC-2 | invalid backend-priority payload type | fail closed on non-list/non-dict/non-BackendPriorities payload | same type contract; no coercion repairs | none | P2C008-R2 | networkx/utils/configs.py:351-368; networkx/utils/tests/test_config.py:123-130 |
| P2C008-EC-3 | invalid warning-name set or non-bool config fields | fail closed with deterministic `TypeError`/`ValueError` envelope | same fail-closed envelope with deterministic audit metadata | bounded_diagnostic_enrichment | P2C008-R2 | networkx/utils/configs.py:381-395; networkx/utils/tests/test_config.py:133-138 |
| P2C008-EC-4 | mixed-backend ambiguous route with no configured conversion priority | fail closed and refuse backend tie-breaking guesses | same fail-closed default unless explicit fallback policy conditions are met | bounded_policy_override | P2C008-R4 | networkx/utils/backends.py:902-931; networkx/utils/backends.py:1023-1031 |
| P2C008-EC-5 | lazy import for missing optional dependency | delayed fail-closed `ModuleNotFoundError` with preserved callsite context | same delayed failure contract | none | P2C008-R5 | networkx/lazy_imports.py:82-98; networkx/tests/test_lazy_imports.py:16-27 |

## Strict/Hardened Divergence
- strict: exact env/config/dispatch/lazy-import compatibility with zero behavior-repair heuristics and fail-closed defaults on ambiguity.
- hardened: preserve API/output contracts while allowing only bounded metadata-level diagnostics and explicit fallback policies.
- unknown incompatible runtime-config or backend-route pathways fail closed unless explicitly allowlisted with deterministic audit evidence.

## Determinism Commitments
| row id | commitment | tie-break rule | legacy anchor regions | required validations |
|---|---|---|---|---|
| P2C008-DC-1 | environment-to-config projection is deterministic | explicit precedence: `NETWORKX_BACKEND_PRIORITY_ALGOS` over general backend-priority env fallback path | P2C008-R3 | networkx/utils/backends.py:164-183 |
| P2C008-DC-2 | backend try-order construction is deterministic | priority groups resolved in stable sequence (`group1..group5`) with no ambiguous tie guesses | P2C008-R4 | networkx/utils/backends.py:879-939 |
| P2C008-DC-3 | strict config field semantics are deterministic | unknown keys/deletes always rejected in strict mode | P2C008-R1 | networkx/utils/configs.py:109-123; networkx/utils/tests/test_config.py:80-101 |
| P2C008-DC-4 | lazy import surface is deterministic | `attach` exports fixed `__all__` and resolves attr->submodule mapping deterministically | P2C008-R5 | networkx/lazy_imports.py:57-79; networkx/tests/test_lazy_imports.py:70-96 |
| P2C008-DC-5 | fail-closed envelopes are deterministic | unresolved backend ambiguity and unknown backend names emit stable error class families | P2C008-R2; P2C008-R4 | networkx/utils/tests/test_config.py:123-132; networkx/utils/tests/test_backends.py:162-168 |

### Machine-Checkable Invariant Matrix
| invariant id | precondition | postcondition | preservation obligation | legacy anchor regions | required validations |
|---|---|---|---|---|---|
| P2C008-IV-1 | runtime config is constructed/updated from env + explicit backend-priority payloads | resolved config state matches deterministic precedence and validation contracts | strict mode forbids silent coercions and unknown-backend acceptance | P2C008-R1; P2C008-R2; P2C008-R3 | generated/runtime_config_optional_strict.json; unit::fnx-p2c-008::contract |
| P2C008-IV-2 | dispatch path includes backend inputs, fallback flags, and optional dependency availability | route selection and fail-closed decisions are deterministic and replay-stable | both modes preserve deterministic backend ordering and ambiguity refusal | P2C008-R4 | differential::fnx-p2c-008::fixtures; adversarial::fnx-p2c-008::malformed_inputs |
| P2C008-IV-3 | lazy import pathways are exercised for present and missing optional dependencies | import-proxy behavior and delayed error envelopes remain parity-stable | no hidden eager import side effects that alter observable module behavior | P2C008-R5 | networkx/tests/test_lazy_imports.py:9-68; e2e::fnx-p2c-008::golden_journey |
