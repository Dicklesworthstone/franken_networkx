# Contract Table

## Input Contract
| row id | API/behavior | preconditions | strict policy | hardened policy | legacy anchor regions | required validations |
|---|---|---|---|---|---|---|
| P2C003-IC-1 | explicit backend kwarg resolution (`backend=...`) | backend name is `None`, `networkx`, or installed backend identifier | fail-closed on unknown backend; no implicit route repair | same fail-closed behavior unless category is allowlisted + audited | P2C003-R1; P2C003-R3 | networkx/utils/tests/test_backends.py:44-95; networkx/utils/tests/test_backends.py:162-168 |
| P2C003-IC-2 | mutation-aware route eligibility | mutates_input predicate resolved from args/kwargs before backend conversion | block auto-conversion for mutating calls unless safe native route exists | same blocking default; allowlisted fallback requires deterministic audit trail | P2C003-R2 | networkx/utils/tests/test_backends.py:135-160; networkx/utils/tests/test_backends.py:194-225 |
| P2C003-IC-3 | backend priority route selection | backend_priority config is defined and normalized | deterministic backend ordering and tie-breaks only | deterministic ordering unchanged; diagnostics may be enriched | P2C003-R1; P2C003-R4 | networkx/utils/tests/test_config.py:120-170; networkx/utils/tests/test_backends.py:101-129 |

## Output Contract
| row id | output behavior | postconditions | strict policy | hardened policy | legacy anchor regions | required validations |
|---|---|---|---|---|---|---|
| P2C003-OC-1 | selected backend implementation identity | chosen backend is deterministic for same args/config/graph backend provenance | zero mismatch budget for route identity drift | same route identity unless deterministic fallback category is allowlisted | P2C003-R1 | networkx/utils/tests/test_backends.py:101-129; networkx/classes/tests/dispatch_interface.py:52-78 |
| P2C003-OC-2 | conversion/cache reuse semantics | cache key + cache hit behavior is deterministic and replayable | no silent cache mutation outside declared key compatibility logic | same key semantics; only bounded diagnostic enrichment allowed | P2C003-R4 | networkx/classes/tests/dispatch_interface.py:67-78; networkx/classes/tests/dispatch_interface.py:186-190 |

## Error Contract
| row id | trigger | strict behavior | hardened behavior | allowlisted divergence category | legacy anchor regions | required validations |
|---|---|---|---|---|---|---|
| P2C003-EC-1 | unknown backend identifier | raise ImportError (fail-closed) | raise ImportError unless deterministic fallback category is allowlisted and audited | deterministic_backend_fallback_with_audit | P2C003-R3 | networkx/utils/tests/test_backends.py:162-168 |
| P2C003-EC-2 | backend lacks dispatchable implementation for algorithm | raise NotImplementedError with route context | same default; no opaque fallback | none | P2C003-R1; P2C003-R3 | networkx/utils/tests/test_backends.py:170-187 |
| P2C003-EC-3 | incompatible backend conversion graph provenance | raise TypeError (fail-closed conversion boundary) | quarantine unsupported metadata then fail closed if parity proof absent | quarantine_of_unsupported_metadata | P2C003-R3 | networkx/utils/tests/test_backends.py:135-160 |

## Strict/Hardened Divergence
- strict: fail-closed for unknown backend/features/metadata paths and zero mismatch budget for route identity.
- hardened: divergence allowed only in allowlisted categories: bounded_diagnostic_enrichment; bounded_resource_clamp; deterministic_backend_fallback_with_audit; quarantine_of_unsupported_metadata.
- unknown incompatible features/metadata paths: fail-closed unless allowlist category + deterministic audit evidence is present.

## Determinism Commitments
| row id | commitment | tie-break rule | legacy anchor regions | required validations |
|---|---|---|---|---|
| P2C003-DC-1 | backend priority tie-break is lexical + stable | equal-priority backend candidates ordered by backend name | P2C003-R1 | networkx/utils/tests/test_config.py:120-170 |
| P2C003-DC-2 | cache key canonicalization is deterministic | edge/node key sets normalized before lookup | P2C003-R4 | networkx/classes/tests/dispatch_interface.py:67-78; networkx/classes/tests/dispatch_interface.py:186-190 |

### Machine-Checkable Invariant Matrix
| invariant id | precondition | postcondition | preservation obligation | legacy anchor regions | required validations |
|---|---|---|---|---|---|
| P2C003-IV-1 | dispatch inputs are signature-valid and backend metadata is loaded | route selection is deterministic for identical inputs | no mutation of route semantics across strict/hardened except allowlisted categories | P2C003-R1; P2C003-R2 | unit::fnx-p2c-003::contract; property::fnx-p2c-003::invariants |
| P2C003-IV-2 | cache key derivation receives explicit attr-preservation flags | cache lookup outcome is replayable and deterministic | FAILED_TO_CONVERT sentinel must prevent repeated unsafe conversion attempts | P2C003-R4 | differential::fnx-p2c-003::fixtures; e2e::fnx-p2c-003::golden_journey |


## Rust Module Boundary Skeleton
| boundary id | crate | module path | public seam | internal ownership | legacy compatibility surface | threat boundary refs | compile-check proof | parallel contributor scope |
|---|---|---|---|---|---|---|---|---|
| P2C003-MB-1 | fnx-dispatch | crates/fnx-dispatch/src/route_policy.rs | pub trait DispatchRoutePlanner | route candidate ranking and compatibility preflight policy | _dispatchable._can_backend_run / _should_backend_run | P2C003-CB-1; P2C003-CB-2 | cargo check -p fnx-dispatch | routing policy and candidate ordering only |
| P2C003-MB-2 | fnx-runtime | crates/fnx-runtime/src/backend_probe.rs | pub trait BackendProbeRegistry | backend discovery/version envelope checks and strict fail-closed decisions | _load_backend / backend API version checks | P2C003-CB-3; P2C003-CB-6 | cargo check -p fnx-runtime | backend probe + version compatibility only |
| P2C003-MB-3 | fnx-dispatch | crates/fnx-dispatch/src/cache_key.rs | pub struct DispatchCacheKey + pub fn canonicalize_cache_key | cache-key normalization and FAILED_TO_CONVERT sentinel management | _get_cache_key / _get_from_cache | P2C003-CB-4; P2C003-CB-5 | cargo test -p fnx-dispatch dispatch_cache -- --nocapture | cache-key derivation and cache state transitions only |
| P2C003-MB-4 | fnx-runtime | crates/fnx-runtime/src/hardened_guardrails.rs | pub struct HardenedDispatchGuardrails | allowlisted hardened deviations, audit envelopes, and deterministic policy bypass rejection | strict/hardened divergence envelope for dispatch paths | P2C003-CB-1; P2C003-CB-2; P2C003-CB-6 | cargo check -p fnx-runtime --all-targets | hardened diagnostics/audit policy only |


## Dependency-Aware Implementation Sequence
| checkpoint id | order | depends on | objective | modules touched | verification entrypoints | structured logging hooks | risk checkpoint |
|---|---|---|---|---|---|---|---|
| P2C003-SEQ-1 | 1 | none | Land compile-checkable route policy and backend probe seams before behavior changes. | crates/fnx-dispatch/src/route_policy.rs; crates/fnx-runtime/src/backend_probe.rs | unit::fnx-p2c-003::route_policy_shape; cargo check -p fnx-dispatch | dispatch.route.policy_selected; dispatch.backend_probe.result | fail if public/internal seam ownership is ambiguous |
| P2C003-SEQ-2 | 2 | P2C003-SEQ-1 | Implement strict-mode route selection parity and unknown-feature fail-closed handling. | crates/fnx-dispatch/src/route_policy.rs; crates/fnx-runtime/src/policy.rs | networkx/utils/tests/test_backends.py:44-95; differential::fnx-p2c-003::fixtures | dispatch.route.strict_decision; dispatch.fail_closed.trigger | halt if strict mismatch budget deviates from zero |
| P2C003-SEQ-3 | 3 | P2C003-SEQ-2 | Implement deterministic cache-key canonicalization and sentinel-safe cache transitions. | crates/fnx-dispatch/src/cache_key.rs; crates/fnx-dispatch/src/cache_store.rs | networkx/classes/tests/dispatch_interface.py:186-190; property::fnx-p2c-003::cache_invariants | dispatch.cache.key_canonicalized; dispatch.cache.sentinel_transition | fail on replay-metadata drift in cache traces |
| P2C003-SEQ-4 | 4 | P2C003-SEQ-2; P2C003-SEQ-3 | Layer hardened allowlisted controls with deterministic audit envelopes. | crates/fnx-runtime/src/hardened_guardrails.rs; crates/fnx-runtime/src/structured_logging.rs | adversarial::fnx-p2c-003::policy_bypass; adversarial::fnx-p2c-003::resource_exhaustion | dispatch.hardened.allowlisted_category; dispatch.audit.envelope_emitted | reject any non-allowlisted hardened deviation |
| P2C003-SEQ-5 | 5 | P2C003-SEQ-4 | Run end-to-end differential/e2e/perf readiness gates and finalize packet evidence. | crates/fnx-conformance/tests/phase2c_packet_readiness_gate.rs; scripts/run_phase2c_readiness_e2e.sh | e2e::fnx-p2c-003::golden_journey; cargo test -p fnx-conformance --test phase2c_packet_readiness_gate | dispatch.e2e.replay_bundle; dispatch.readiness.gate_result | stop on any strict/hardened parity gate mismatch |


## Structured Logging + Verification Entry Points
| stage | harness | structured log hook | replay metadata fields | failure forensics artifact |
|---|---|---|---|---|
| unit | unit::fnx-p2c-003::contract | dispatch.unit.contract_asserted | packet_id; route_id; backend_name; strict_mode | artifacts/conformance/latest/structured_logs.jsonl |
| property | property::fnx-p2c-003::invariants | dispatch.property.invariant_checkpoint | seed; graph_fingerprint; cache_key_digest; invariant_id | artifacts/conformance/latest/structured_log_emitter_normalization_report.json |
| differential | differential::fnx-p2c-003::fixtures | dispatch.diff.oracle_comparison | fixture_id; oracle_ref; route_signature; mismatch_count | artifacts/phase2c/FNX-P2C-003/parity_report.json |
| e2e | e2e::fnx-p2c-003::golden_journey | dispatch.e2e.replay_emitted | scenario_id; thread_id; trace_id; forensics_bundle | artifacts/conformance/latest/telemetry_dependent_unblock_matrix_v1.json |
