# Contract Table

## Input Contract
| row id | API/behavior | preconditions | strict policy | hardened policy | legacy anchor regions | required validations |
|---|---|---|---|---|---|---|
| P2C006-IC-1 | edgelist write/read round-trip contract | graph edge endpoints/data selectors, delimiter, and encoding are explicit for generation and ingest pathways | preserve generate/write/read edgelist semantics with no hidden edge-data coercion | same serialization contract; bounded diagnostics allowed without output-shape drift | P2C006-R1; P2C006-R2 | networkx/readwrite/tests/test_edgelist.py:80-107; networkx/readwrite/tests/test_edgelist.py:187-220; networkx/readwrite/tests/test_edgelist.py:251-302 |
| P2C006-IC-2 | parse_edgelist typed conversion and weighted tuple semantics | nodetype and data tuple schema are explicit; delimiter/comment policy is fixed | preserve literal_eval/typed conversion semantics and fail closed on malformed inputs | same conversion semantics; bounded recovery only for allowlisted malformed-line categories | P2C006-R2; P2C006-R3 | networkx/readwrite/tests/test_edgelist.py:117-173; networkx/readwrite/tests/test_edgelist.py:304-318; networkx/readwrite/tests/test_edgelist.py:86-90 |
| P2C006-IC-3 | json_graph adjacency/node-link attribute mapping and reconstruction | directed/multigraph flags and attrs id/source/target/key names are explicit and unique | preserve adjacency/node-link payload schema and tuple-node restoration semantics exactly | same schema contract; incompatible metadata is quarantined and then fail-closed if unresolved | P2C006-R4; P2C006-R5 | networkx/readwrite/json_graph/tests/test_adjacency.py:12-75; networkx/readwrite/json_graph/tests/test_node_link.py:10-50; networkx/readwrite/json_graph/tests/test_node_link.py:52-109 |
| P2C006-IC-4 | comment stripping and short-line handling in edgelist parsing | comments marker and delimiter policy are fixed by caller | ignore comment-only/short lines deterministically while preserving parse-failure envelopes | same baseline with deterministic audit metadata for recovered malformed-line pathways | P2C006-R2; P2C006-R3 | networkx/readwrite/tests/test_edgelist.py:142-165; networkx/readwrite/tests/test_edgelist.py:167-173; networkx/readwrite/tests/test_edgelist.py:304-318 |

## Output Contract
| row id | output behavior | postconditions | strict policy | hardened policy | legacy anchor regions | required validations |
|---|---|---|---|---|---|---|
| P2C006-OC-1 | edgelist serialization line format and edge-data projection | serialized lines and reloaded graph topology/edge attributes remain parity-preserving | zero mismatch budget for edgelist round-trip drift | same outward output contract; bounded diagnostics must remain out-of-band and deterministic | P2C006-R1; P2C006-R2 | networkx/readwrite/tests/test_edgelist.py:187-220; networkx/readwrite/tests/test_edgelist.py:251-302; generated/readwrite_roundtrip_strict.json |
| P2C006-OC-2 | typed weighted-edgelist parse output | weight/data fields are typed as requested and graph edge set matches parsed payload | typed edge-data conversion must match legacy parse contract exactly | same typed-output contract with deterministic audit envelopes only | P2C006-R2; P2C006-R3 | networkx/readwrite/tests/test_edgelist.py:86-90; networkx/readwrite/tests/test_edgelist.py:117-140; generated/readwrite_hardened_malformed.json |
| P2C006-OC-3 | json_graph adjacency/node-link round-trip reconstruction | directed/multigraph flags, attrs, and tuple-node identity are preserved across JSON round-trip | no payload/key renaming outside documented legacy behavior | same payload contract; allowlisted metadata quarantine cannot alter returned graph semantics | P2C006-R4; P2C006-R5 | networkx/readwrite/json_graph/tests/test_adjacency.py:12-75; networkx/readwrite/json_graph/tests/test_node_link.py:52-109; generated/readwrite_json_roundtrip_strict.json |

## Error Contract
| row id | trigger | strict behavior | hardened behavior | allowlisted divergence category | legacy anchor regions | required validations |
|---|---|---|---|---|---|---|
| P2C006-EC-1 | node token conversion fails under nodetype coercion | raise deterministic TypeError (fail-closed) with no partial edge insertion | same fail-closed default; bounded diagnostics only | bounded_diagnostic_enrichment | P2C006-R3 | networkx/readwrite/tests/test_edgelist.py:147-151; networkx/readwrite/tests/test_edgelist.py:142-165 |
| P2C006-EC-2 | edge data arity mismatch against declared data tuple schema | raise deterministic IndexError and halt parse | same fail-closed default; no implicit schema padding | none | P2C006-R3 | networkx/readwrite/tests/test_edgelist.py:155-160 |
| P2C006-EC-3 | edge data literal cannot be interpreted as dictionary/typed value | raise deterministic TypeError with fail-closed parser exit | allow bounded defensive parse recovery only for allowlisted malformed-line categories | defensive_parse_recovery | P2C006-R2; P2C006-R3 | networkx/readwrite/tests/test_edgelist.py:152-154; networkx/readwrite/tests/test_edgelist.py:162-165 |
| P2C006-EC-4 | json_graph attribute names are non-unique for id/source/target/key | raise deterministic NetworkXError and reject ambiguous payload schema | same fail-closed attribute-boundary enforcement with audit metadata | bounded_diagnostic_enrichment | P2C006-R5 | networkx/readwrite/json_graph/tests/test_adjacency.py:74-78; networkx/readwrite/json_graph/tests/test_node_link.py:10-14; networkx/readwrite/json_graph/tests/test_node_link.py:72-77 |

## Strict/Hardened Divergence
- strict: fail-closed on malformed parse payloads, ambiguous json_graph attribute naming, and unknown readwrite metadata with zero mismatch budget for round-trip outputs
- hardened: bounded divergence only in allowlisted diagnostic/recovery categories with deterministic audit evidence and no outward API-shape drift
- unknown incompatible readwrite features/metadata paths fail closed unless an allowlisted category and deterministic audit trail are present

## Determinism Commitments
| row id | commitment | tie-break rule | legacy anchor regions | required validations |
|---|---|---|---|---|
| P2C006-DC-1 | edgelist line emission and reload ordering are deterministic | graph traversal order drives line order with stable encoding/newline policy | P2C006-R1 | networkx/readwrite/tests/test_edgelist.py:187-220; networkx/readwrite/tests/test_edgelist.py:251-302 |
| P2C006-DC-2 | comment stripping and short-line handling are deterministic | comment-only or underspecified rows are consistently ignored before token coercion | P2C006-R2; P2C006-R3 | networkx/readwrite/tests/test_edgelist.py:142-147; networkx/readwrite/tests/test_edgelist.py:167-173; networkx/readwrite/tests/test_edgelist.py:304-318 |
| P2C006-DC-3 | json_graph reconstruction is deterministic for node/edge identity | adjacency index mapping and node-link tuple restoration preserve stable node/edge identity | P2C006-R4; P2C006-R5 | networkx/readwrite/json_graph/tests/test_adjacency.py:12-67; networkx/readwrite/json_graph/tests/test_node_link.py:52-89 |

### Machine-Checkable Invariant Matrix
| invariant id | precondition | postcondition | preservation obligation | legacy anchor regions | required validations |
|---|---|---|---|---|---|
| P2C006-IV-1 | edgelist write/read invoked with explicit mode parameters | round-tripped graph topology and typed edge data remain parity-preserving | strict mode forbids silent repair that changes observable readwrite outputs | P2C006-R1; P2C006-R2; P2C006-R3 | unit::fnx-p2c-006::contract; differential::fnx-p2c-006::fixtures; generated/readwrite_roundtrip_strict.json |
| P2C006-IV-2 | parse payload includes malformed rows or coercion hazards | fail-closed envelopes are deterministic and replayable by mode policy | hardened recoveries must be allowlisted, bounded, and auditable without API-shape drift | P2C006-R2; P2C006-R3 | networkx/readwrite/tests/test_edgelist.py:142-165; adversarial::fnx-p2c-006::malformed_inputs; generated/readwrite_hardened_malformed.json |
| P2C006-IV-3 | json_graph attrs and graph-mode flags are supplied by caller | adjacency/node-link reconstruction preserves directed/multigraph semantics and tuple nodes | non-unique attribute naming fails closed and unknown metadata paths remain compatibility-bounded | P2C006-R4; P2C006-R5 | networkx/readwrite/json_graph/tests/test_adjacency.py:12-75; networkx/readwrite/json_graph/tests/test_node_link.py:10-109; e2e::fnx-p2c-006::golden_journey |


## Rust Module Boundary Skeleton
| boundary id | crate | module path | public seam | internal ownership | legacy compatibility surface | threat boundary refs | compile-check proof | parallel contributor scope |
|---|---|---|---|---|---|---|---|---|
| P2C006-MB-1 | fnx-readwrite | crates/fnx-readwrite/src/edgelist_emit.rs | pub trait EdgeListEmitter | deterministic edge-line emission, delimiter/encoding policy, and edge-data projection for strict/hardened round-trip parity | generate_edgelist / write_edgelist | P2C006-CB-1; P2C006-CB-4 | cargo check -p fnx-readwrite | edgelist emit pathway only |
| P2C006-MB-2 | fnx-readwrite | crates/fnx-readwrite/src/edgelist_parse.rs | pub struct EdgeListParser | parse tokenization, nodetype/typed-data coercion, malformed-input fail-closed envelopes, and deterministic comment/short-line policy | parse_edgelist / read_edgelist / read_weighted_edgelist | P2C006-CB-1; P2C006-CB-3; P2C006-CB-4 | cargo test -p fnx-readwrite -- --nocapture | edgelist parse semantics and error boundaries only |
| P2C006-MB-3 | fnx-readwrite | crates/fnx-readwrite/src/json_graph_codec.rs | pub trait JsonGraphCodec | adjacency/node-link encode/decode, tuple-node restoration, and json attribute namespace compatibility boundaries | adjacency_data / adjacency_graph / node_link_data / node_link_graph | P2C006-CB-2; P2C006-CB-5 | cargo check -p fnx-readwrite --all-targets | json_graph schema/reconstruction pathway only |
| P2C006-MB-4 | fnx-runtime | crates/fnx-runtime/src/hardened_guardrails.rs | pub struct HardenedReadwriteGuardrails | allowlisted hardened deviation controls, deterministic audit envelopes, and policy enforcement for readwrite packet boundaries | strict/hardened compatibility envelope for edgelist and json_graph contract surfaces | P2C006-CB-1; P2C006-CB-2; P2C006-CB-4; P2C006-CB-5 | cargo check -p fnx-runtime --all-targets | hardened diagnostics/policy guardrails only |


## Dependency-Aware Implementation Sequence
| checkpoint id | order | depends on | objective | modules touched | verification entrypoints | structured logging hooks | risk checkpoint |
|---|---|---|---|---|---|---|---|
| P2C006-SEQ-1 | 1 | none | Establish compile-checkable readwrite module seams and ownership boundaries before behavioral changes. | crates/fnx-readwrite/src/edgelist_emit.rs; crates/fnx-readwrite/src/edgelist_parse.rs; crates/fnx-readwrite/src/json_graph_codec.rs | unit::fnx-p2c-006::boundary_shape; cargo check -p fnx-readwrite | readwrite.boundary.edgelist_emit_ready; readwrite.boundary.edgelist_parse_ready; readwrite.boundary.json_graph_ready | fail if module seam ownership or packet boundary mapping is ambiguous |
| P2C006-SEQ-2 | 2 | P2C006-SEQ-1 | Lock strict-mode edgelist emit/read parity and typed parse semantics with deterministic error envelopes. | crates/fnx-readwrite/src/edgelist_emit.rs; crates/fnx-readwrite/src/edgelist_parse.rs | networkx/readwrite/tests/test_edgelist.py:80-173; differential::fnx-p2c-006::fixtures | readwrite.strict.emit_policy; readwrite.strict.parse_fail_closed | halt if strict round-trip mismatch budget deviates from zero |
| P2C006-SEQ-3 | 3 | P2C006-SEQ-2 | Implement json_graph adjacency/node-link compatibility boundaries and tuple-node identity reconstruction rules. | crates/fnx-readwrite/src/json_graph_codec.rs; crates/fnx-readwrite/src/lib.rs | networkx/readwrite/json_graph/tests/test_adjacency.py:12-78; networkx/readwrite/json_graph/tests/test_node_link.py:10-109 | readwrite.json_graph.schema_validated; readwrite.json_graph.identity_restored | reject any json_graph attribute-namespace ambiguity bypass |
| P2C006-SEQ-4 | 4 | P2C006-SEQ-2; P2C006-SEQ-3 | Layer hardened allowlisted guardrails and crash-taxonomy instrumentation for readwrite threat classes. | crates/fnx-runtime/src/hardened_guardrails.rs; crates/fnx-runtime/src/lib.rs | adversarial::fnx-p2c-006::malformed_inputs; adversarial::fnx-p2c-006::metadata_confusion | readwrite.hardened.allowlisted_category; readwrite.hardened.crash_taxonomy_emitted | fail on any non-allowlisted hardened deviation |
| P2C006-SEQ-5 | 5 | P2C006-SEQ-4 | Run readiness/e2e/perf gates and finalize packet evidence artifacts for handoff to test implementation beads. | crates/fnx-conformance/tests/phase2c_packet_readiness_gate.rs; scripts/run_phase2c_readiness_e2e.sh; artifacts/phase2c/FNX-P2C-006/ | cargo test -p fnx-conformance --test phase2c_packet_readiness_gate; cargo test -p fnx-conformance --test e2e_script_pack_gate | readwrite.readiness.gate_result; readwrite.e2e.replay_bundle | stop on any strict/hardened parity or security gate mismatch |


## Structured Logging + Verification Entry Points
| stage | harness | structured log hook | replay metadata fields | failure forensics artifact |
|---|---|---|---|---|
| unit | unit::fnx-p2c-006::contract | readwrite.unit.contract_asserted | packet_id; io_path; strict_mode; fixture_id | artifacts/conformance/latest/structured_logs.jsonl |
| property | property::fnx-p2c-006::invariants | readwrite.property.invariant_checkpoint | seed; graph_fingerprint; mode_policy; invariant_id | artifacts/conformance/latest/structured_log_emitter_normalization_report.json |
| differential | differential::fnx-p2c-006::fixtures | readwrite.diff.oracle_comparison | fixture_id; oracle_ref; io_signature; mismatch_count | artifacts/phase2c/FNX-P2C-006/parity_report.json |
| e2e | e2e::fnx-p2c-006::golden_journey | readwrite.e2e.replay_emitted | scenario_id; thread_id; trace_id; forensics_bundle | artifacts/conformance/latest/telemetry_dependent_unblock_matrix_v1.json |
