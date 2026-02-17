# Contract Table

## Scope
- packet id: `FNX-P2C-002`
- subsystem: view layer semantics
- fixture anchor: `crates/fnx-conformance/fixtures/generated/view_neighbors_strict.json`
- legacy anchors: `networkx/classes/coreviews.py`, `networkx/classes/graphviews.py`

## Input Contract
| input | type | constraints |
|---|---|---|
| packet operations | structured args | must preserve NetworkX-observable contract for FNX-P2C-002 |
| compatibility mode | enum | strict and hardened behavior split with fail-closed handling |
| metadata paths | namespaced object | unknown paths are fail-closed unless explicitly allowlisted |

## Output Contract
| output | type | semantics |
|---|---|---|
| algorithm/state result | graph data or query payload | deterministic tie-break and ordering guarantees |
| evidence artifacts | structured files | replayable, machine-auditable, and linked to fixture IDs |
| audit trail | deterministic log fields | recovery/coercion decisions are explicitly recorded |

## Error Contract
| condition | mode | behavior |
|---|---|---|
| unknown incompatible feature | strict/hardened | fail-closed |
| malformed input affecting compatibility | strict | fail-closed |
| malformed known-safe allowlisted input | hardened | bounded defensive recovery + deterministic audit |
| budget exceeded during recovery | hardened | escalate to fail-closed |

## Machine-Checkable Contract Rows
| contract_id | operation | preconditions | postconditions | strict policy | hardened allowlist policy | legacy anchors | validation hooks |
|---|---|---|---|---|---|---|---|
| FNX-P2C-002-C1 | graph mutation projection into views | graph revision token is monotonic; mutation payload is schema-valid | neighbor projection order remains deterministic for identical input graph + seed; outward API shape unchanged | fail-closed on any compatibility ambiguity | one bounded recovery: recompute projection once and emit deterministic audit | `coreviews.py` (`AtlasView`, `AdjacencyView`) | unit `unit::fnx-p2c-002::contract`, property `property::fnx-p2c-002::invariants`, differential `differential::fnx-p2c-002::fixtures` |
| FNX-P2C-002-C2 | view/cache coherence | cache has revision provenance; cache key hash is deterministic | stale cache is never served after revision mismatch; recomputation remains deterministic | fail-closed if revision provenance is missing or malformed | allowlisted defensive recovery: invalidate cache and recompute exactly once | `coreviews.py`, `graphviews.py` (`generic_graph_view`, `subgraph_view`) | adversarial `adversarial::fnx-p2c-002::malformed_inputs`, e2e `e2e::fnx-p2c-002::golden_journey` |
| FNX-P2C-002-C3 | dispatch backend route for view operations | backend capability metadata present and canonicalized | chosen backend is deterministic for equal-ranked candidates; unknown incompatible route hints never alter strict outputs | fail-closed on unknown incompatible backend hint | allowlisted hardened coercion: normalize known-safe hint formats with audit record | `graphviews.py` (`reverse_view`) | conformance fixture `generated/view_neighbors_strict.json`, readiness gate `crates/fnx-conformance/tests/phase2c_packet_readiness_gate.rs` |
| FNX-P2C-002-C4 | conversion/readwrite around view payloads | payload path is admitted by packet scope; serializer settings are canonicalized | serialized and deserialized forms preserve scoped observable behavior | fail-closed on unknown serializer feature flags | allowlisted fallback for known malformed-but-safe flags with deterministic warning | `coreviews.py`, `graphviews.py` | fixture report `artifacts/conformance/latest/generated_view_neighbors_strict_json.report.json` |
| FNX-P2C-002-C5 | error path semantics | input has been parsed into canonical validation state | strict path is always fail-closed; hardened path stays within bounded defensive budget and emits audit | fail-closed | bounded recovery only for allowlisted classes below | legacy tests `networkx/classes/tests/test_coreviews.py`, `networkx/classes/tests/test_graphviews.py` | risk gate evidence `artifacts/phase2c/FNX-P2C-002/risk_note.md` |

## Determinism Invariants
| invariant_id | invariant statement | machine-check predicate | evidence path |
|---|---|---|---|
| FNX-P2C-002-I1 | View layer semantics output contract is deterministic and parity-preserving. | For identical graph+mode+seed, neighbor sequence hash is stable and equal to oracle fixture hash. | `artifacts/phase2c/essence_extraction_ledger_v1.json`, `artifacts/conformance/latest/generated_view_neighbors_strict_json.report.json` |
| FNX-P2C-002-I2 | Revision-aware cache invalidation is atomic and deterministic. | Any revision mismatch forces invalidation before read; no stale result returned after mismatch. | `artifacts/phase2c/FNX-P2C-002/risk_note.md` |
| FNX-P2C-002-I3 | Tie-break behavior remains lexical/canonical under equal-priority outcomes. | Candidate set ordering is deterministic and stable under repeated execution. | `artifacts/proofs/ISOMORPHISM_PROOF_FNX_P2C_002_V1.md` |

## Strict/Hardened Divergence
Strict and hardened policies preserve the same outward API contract; hardened mode only permits bounded, explicit recovery classes.

| divergence_class | strict behavior | hardened allowlist behavior | bounded budget | audit requirement |
|---|---|---|---|---|
| stale cache exposure | fail-closed | invalidate cache, recompute once | max 1 retry | emit deterministic recovery record |
| projection filter nondeterminism | fail-closed | canonicalize filter order once | max 1 canonicalization pass | emit ordering-normalization warning |
| malformed known-safe metadata encoding | fail-closed | normalize known-safe encoding and continue | max 1 coercion | emit coercion reason + source field |
| unknown incompatible feature/metadata path | fail-closed | fail-closed | no recovery | emit strict rejection reason code |

## Unknown Metadata/Feature Contract
All unknown paths are fail-closed unless explicitly allowlisted above.

| metadata path | strict | hardened | allowlisted |
|---|---|---|---|
| `packet.metadata.cache_revision_hint` | fail-closed if unknown shape | bounded normalization if known-safe shape | yes |
| `packet.options.view_projection_filter` | fail-closed on nondeterministic ordering | bounded canonicalization | yes |
| `packet.metadata.backend_route_hint` | fail-closed on unknown backend compatibility | bounded normalization for known-safe route aliases | yes |
| `packet.metadata.serializer_flags` | fail-closed on unknown flags | bounded normalization for known-safe flags | yes |
| `packet.metadata.*` (all other paths) | fail-closed | fail-closed | no |

## Determinism Commitments
- tie-break policy: lexical/canonical ordering for equal-priority outcomes.
- ordering policy: stable traversal and output ordering under identical inputs and seeds.
- replay policy: packet fixture replay command must deterministically reproduce the same status and report hash under identical inputs.

## Decision-Theoretic Runtime Contract
- states: `allow`, `full_validate`, `fail_closed`
- actions: `allow`, `full_validate`, `fail_closed`
- loss model: minimize compatibility drift + security risk under deterministic constraints.
- safe-mode fallback: `fail_closed`

| trigger | threshold | resulting action |
|---|---|---|
| unknown incompatible feature detected | `true` | `fail_closed` |
| `risk_probability(full_validate)` | `>= 0.25` | `full_validate` |
| strict contract violation count | `> 0` | `fail_closed` |

## Profile-First + Alien Uplift Card
| field | value |
|---|---|
| EV score | `2.4` |
| baseline comparator | `legacy_networkx/main@python3.12` |
| optimization lever | single-pass cache invalidation scan with stable ordering |
| baseline artifact | `artifacts/perf/BASELINE_BFS_V1.md` |
| hotspot artifact | `artifacts/perf/OPPORTUNITY_MATRIX.md` |
| delta artifact | `artifacts/perf/phase2c/bfs_neighbor_iter_delta.json` |

## Structured Logging + Replay Contract
| requirement | evidence path |
|---|---|
| deterministic replay command for packet fixture | `artifacts/conformance/latest/generated_view_neighbors_strict_json.report.json` (`replay_command`) |
| canonical structured log schema + required forensic fields | `artifacts/conformance/latest/telemetry_dependent_unblock_matrix_v1.json` |
| normalized structured log emitter report | `artifacts/conformance/latest/structured_log_emitter_normalization_report.json` |
| run log bundle | `artifacts/conformance/latest/structured_logs.jsonl` |

## Security Threat Model Crosswalk
| threat class | strict response contract row | hardened response contract row | adversarial mapping source | crash triage source |
|---|---|---|---|---|
| parser_abuse | FNX-P2C-002-C5 | FNX-P2C-002-C5 | `artifacts/phase2c/security/v1/adversarial_corpus_manifest_v1.json` | `artifacts/phase2c/latest/adversarial_regression_promotion_queue_v1.json` |
| metadata_ambiguity | FNX-P2C-002-C5 | FNX-P2C-002-C3, FNX-P2C-002-C5 | `artifacts/phase2c/security/v1/adversarial_seed_ledger_v1.json` | `artifacts/phase2c/latest/adversarial_crash_triage_report_v1.json` |
| version_skew | FNX-P2C-002-C5 | FNX-P2C-002-C5 | `artifacts/phase2c/security/v1/adversarial_seed_ledger_v1.json` | `artifacts/phase2c/latest/adversarial_crash_triage_report_v1.json` |
| resource_exhaustion | FNX-P2C-002-C5 | FNX-P2C-002-C5 | `artifacts/phase2c/security/v1/adversarial_seed_ledger_v1.json` | `artifacts/phase2c/latest/adversarial_crash_triage_report_v1.json` |
| state_corruption | FNX-P2C-002-C2, FNX-P2C-002-C5 | FNX-P2C-002-C2, FNX-P2C-002-C5 | `artifacts/phase2c/security/v1/adversarial_seed_ledger_v1.json` | `artifacts/phase2c/latest/adversarial_regression_promotion_queue_v1.json` |

## Module Boundary Crosswalk
| module seam | contract rows | public API boundary | internal ownership boundary | verification entrypoint |
|---|---|---|---|---|
| `fnx-classes::Graph` | C1, C2, C5 | graph mutation/query APIs | revision counter and adjacency internals | packet readiness gate |
| `fnx-views::GraphView/CachedSnapshotView` | C1, C2 | view projection/read APIs | cache invalidation and coherence internals | `generated/view_neighbors_strict.json` fixture |
| `fnx-dispatch::BackendRegistry` | C3, C5 | dispatch request/decision APIs | route ranking and hint normalization internals | threat matrix + adversarial seed ledger |
