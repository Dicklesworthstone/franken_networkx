# Risk Note

## Risk Surface
- parser/ingestion: malformed payloads for view layer semantics.
- algorithmic denial vectors: adversarial graph shapes designed to trigger tail latency spikes.
- compatibility drift vectors: stale cache exposure and projection filter nondeterminism.
- metadata ambiguity vectors: unknown packet metadata paths that could bypass deterministic behavior if not fail-closed.
- version skew vectors: unsupported view-contract schema or compatibility claims.
- state integrity vectors: cache invalidation and revision-tracking corruption.

## Failure Modes
- fail-closed triggers: unknown incompatible feature, contract-breaking malformed inputs.
- degraded-mode triggers: bounded hardened-mode recovery only when allowlisted and auditable.
- replay integrity risk: missing replay/forensics fields in structured telemetry can block deterministic incident reconstruction.
- resource budget failure: iterator/materialization growth beyond strict limits must fail-closed.
- state corruption failure: revision/cache invariant breaks must fail-closed with deterministic incident records.

## Mitigations
- controls: deterministic compatibility policy, strict/hardened split, packet-specific gate `view coherence witness gate`.
- tests: unit/property/differential/adversarial/e2e coverage linked through fixture IDs.
- unknown metadata policy: default fail-closed for unrecognized `packet.metadata.*` fields unless explicitly allowlisted in `contract_table.md`.
- hardened budgets: at most one retry/canonicalization/coercion event per request path; budget excess escalates to fail-closed.
- threat contract sources: `artifacts/phase2c/security/v1/security_compatibility_threat_matrix_v1.json` and `artifacts/phase2c/security/v1/hardened_mode_deviation_allowlist_v1.json`.
- adversarial/fuzz sources: `artifacts/phase2c/security/v1/adversarial_corpus_manifest_v1.json` and `artifacts/phase2c/security/v1/adversarial_seed_ledger_v1.json`.
- crash triage sources: `artifacts/phase2c/latest/adversarial_crash_triage_report_v1.json` and `artifacts/phase2c/latest/adversarial_regression_promotion_queue_v1.json`.

## Threat Class Matrix
| threat_class | strict mode response | hardened mode response | required mitigations | evidence artifact | validation gate |
|---|---|---|---|---|---|
| parser_abuse | fail-closed on malformed view construction inputs | fail-closed with bounded diagnostics for malformed view inputs | view argument validation; cache key validation; adversarial view fixtures | `artifacts/phase2c/FNX-P2C-002/risk_note.md` | `view-layer-threat-gate` |
| metadata_ambiguity | fail-closed on ambiguous filter/projection metadata | quarantine unsupported metadata and preserve deterministic view semantics | filter metadata allowlist; projection normalization; drift classification logs | `artifacts/phase2c/FNX-P2C-002/risk_note.md` | `view-layer-threat-gate` |
| version_skew | fail-closed on incompatible view-contract versions | reject unsupported version skew with deterministic diagnostics | contract version lock; compatibility matrix checks; cross-version conformance tests | `artifacts/phase2c/FNX-P2C-002/parity_gate.yaml` | `view-layer-threat-gate` |
| resource_exhaustion | fail-closed when view expansion exceeds strict limits | bound iterator/materialization costs and reject after budget exhaustion | iterator guardrails; bounded cache growth; memory budget checks | `artifacts/phase2c/FNX-P2C-002/parity_gate.yaml` | `view-layer-threat-gate` |
| state_corruption | fail-closed when cache invalidation invariants are violated | reset affected cache segments and fail-closed with audit evidence | cache coherence checks; revision counters; invalidation property tests | `artifacts/phase2c/FNX-P2C-002/contract_table.md` | `view-layer-threat-gate` |

## Adversarial Fixture + Fuzz Entry Mapping
All mappings use deterministic replay via `python3 scripts/run_adversarial_seed_harness.py --threat-class <class> --packet-id FNX-P2C-002 --run-id <id>`.

| threat_class | generator_variant | seed | expected_failure_mode | replay command | crash triage route |
|---|---|---|---|---|---|
| parser_abuse | `view_input_malformed_payload` | `1102` | `fail_closed_malformed_payload` | `... --threat-class parser_abuse --packet-id FNX-P2C-002 --run-id replay-61f3ffae5aa15245` | `bug` |
| metadata_ambiguity | `view_conflicting_projection_metadata` | `2102` | `fail_closed_ambiguous_metadata` | `... --threat-class metadata_ambiguity --packet-id FNX-P2C-002 --run-id replay-ff75380056537eaa` | `compatibility_exception` |
| version_skew | `view_unsupported_contract_version` | `3102` | `fail_closed_version_skew` | `... --threat-class version_skew --packet-id FNX-P2C-002 --run-id replay-528c16e08fb33323` | `compatibility_exception` |
| resource_exhaustion | `view_materialization_blowup` | `4102` | `fail_closed_budget_exceeded` | `... --threat-class resource_exhaustion --packet-id FNX-P2C-002 --run-id replay-97db5bc3de9d2c7e` | `known_risk_allowlist` |
| state_corruption | `view_cache_invalidation_break` | `5102` | `fail_closed_invariant_break` | `... --threat-class state_corruption --packet-id FNX-P2C-002 --run-id replay-2282714c94ea09f0` | `bug` |

## Hardened Deviation Allowlist (Packet-Specific)
Only explicit categories below are allowed; ad hoc deviations are forbidden.

| category | strict mode allowed | hardened mode allowed | packet FNX-P2C-002 |
|---|---|---|---|
| bounded_diagnostic_enrichment | no | yes | allowed |
| quarantine_of_unsupported_metadata | no | yes | allowed |
| defensive_parse_recovery | no | yes | not allowed |
| bounded_resource_clamp | no | yes | not allowed |
| deterministic_backend_fallback_with_audit | no | yes | not allowed |
| deterministic_tie_break_normalization | no | yes | not allowed |

## Compatibility Boundary Matrix
| boundary | strict parity obligation | hardened allowlisted deviation | unknown feature default |
|---|---|---|---|
| parser boundary | reject malformed payloads deterministically | bounded diagnostics only | fail-closed |
| metadata boundary | reject ambiguous projection metadata | quarantine unsupported metadata with deterministic evidence | fail-closed |
| version boundary | reject unsupported contract versions | deterministic rejection diagnostics only | fail-closed |
| resource boundary | reject budget overflow deterministically | no packet-level resource clamp allowlist | fail-closed |
| state boundary | reject invariant breaks and preserve deterministic cache semantics | reset affected cache segment then fail-closed with audit | fail-closed |

## Strict vs Hardened Divergence Classes
| divergence class | strict mode | hardened mode | bounded budget | audit expectation |
|---|---|---|---|---|
| stale cache exposure | fail-closed | invalidate and recompute once | `max_1_retry` | deterministic recovery record |
| projection filter nondeterminism | fail-closed | canonicalize order once | `max_1_pass` | warning with normalized ordering hash |
| malformed known-safe metadata encoding | fail-closed | normalize once and continue | `max_1_coercion` | explicit coercion reason |
| unknown incompatible metadata path | fail-closed | fail-closed | no recovery | strict rejection reason code |

## Decision-Theoretic Runtime Triggers
| trigger | threshold | action |
|---|---|---|
| unknown incompatible feature | `true` | fail-closed |
| `risk_probability(full_validate)` | `>= 0.25` | full validate |
| strict violation count | `> 0` | fail-closed |

## Crash Triage Taxonomy Linkage
| routing policy | packet-002 usage | policy intent | artifact refs |
|---|---|---|---|
| bug | parser_abuse, state_corruption | correctness/security defects requiring regression promotion | `artifacts/phase2c/latest/adversarial_regression_promotion_queue_v1.json` |
| compatibility_exception | metadata_ambiguity, version_skew | strict/hardened envelope mismatch requiring compatibility adjudication | `artifacts/phase2c/latest/adversarial_crash_triage_report_v1.json` |
| known_risk_allowlist | resource_exhaustion | documented risk accepted under explicit policy envelope | `artifacts/phase2c/latest/adversarial_crash_triage_report_v1.json` |

## Residual Risk
- unresolved risks: stale cache exposure; projection filter nondeterminism.
- follow-up actions: expand fixture diversity, keep drift gates active, and enforce telemetry-field completeness in packet gate checks.
