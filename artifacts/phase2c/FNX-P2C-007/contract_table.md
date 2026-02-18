# Contract Table

## Input Contract
| row id | API/behavior | preconditions | strict policy | hardened policy | legacy anchor regions | required validations |
|---|---|---|---|---|---|---|
| P2C007-IC-1 | complete_graph node-container and create_using contract | n resolves through nodes_or_number and create_using resolves to a valid graph constructor or instance | preserve complete_graph edge cardinality/orientation semantics exactly for Graph and DiGraph | same observable graph-output contract; bounded diagnostic metadata allowed without shape drift | P2C007-R1; P2C007-R3 | networkx/generators/tests/test_classic.py:147-182; generated/generators_complete_strict.json |
| P2C007-IC-2 | cycle_graph cyclic pairwise emission and directed orientation contract | node ordering is fixed by input iterable/range and create_using is explicit | preserve pairwise(cyclic=True) closure ordering and directed edge orientation exactly | same output ordering and direction contract with deterministic diagnostics only | P2C007-R2 | networkx/generators/tests/test_classic.py:212-235; generated/generators_cycle_strict.json |
| P2C007-IC-3 | path_graph iterable-order contract including duplicate-label behavior | input iterable order is explicit and add-node/edge semantics are deterministic | preserve path edge emission in iterable order with legacy duplicate-label outcomes | same path topology contract with deterministic diagnostics only | P2C007-R4 | networkx/generators/tests/test_classic.py:409-444; generated/generators_path_strict.json |
| P2C007-IC-4 | empty_graph graph-constructor and graph-instance clearing contract | create_using is None, a graph type, or graph-like instance exposing adj | preserve constructor/instance dispatch and node insertion semantics exactly | same constructor dispatch semantics; invalid graph-type inputs still fail closed | P2C007-R3 | networkx/generators/tests/test_classic.py:268-335; networkx/generators/classic.py:667-680 |

## Output Contract
| row id | output behavior | postconditions | strict policy | hardened policy | legacy anchor regions | required validations |
|---|---|---|---|---|---|---|
| P2C007-OC-1 | complete_graph topology and edge-count parity | node set and edge cardinality match legacy Graph/DiGraph observable behavior | zero mismatch budget for complete graph topology and orientation | identical output contract; diagnostics are out-of-band and deterministic | P2C007-R1 | networkx/generators/tests/test_classic.py:147-182; generated/generators_complete_strict.json |
| P2C007-OC-2 | cycle_graph edge ordering and closure parity | cycle closure and edge sequence remain deterministic under identical inputs | preserve canonical cycle closure order with zero mismatch budget | same closure/order contract; no topology-changing repair | P2C007-R2 | networkx/generators/tests/test_classic.py:212-235; generated/generators_cycle_strict.json |
| P2C007-OC-3 | path_graph ordered edge emission parity | path edges follow iterable order and directed orientation semantics exactly | preserve ordered path construction with zero output drift tolerance | same ordered-path output contract; deterministic diagnostics only | P2C007-R4 | networkx/generators/tests/test_classic.py:409-444; generated/generators_path_strict.json |
| P2C007-OC-4 | empty_graph class selection and zero-edge guarantees | returned graph class and node count match create_using/default contract | preserve class dispatch and zero-edge postcondition exactly | same output contract; invalid constructor pathways remain fail-closed | P2C007-R3 | networkx/generators/tests/test_classic.py:268-335; networkx/generators/classic.py:667-680 |

## Error Contract
| row id | trigger | strict behavior | hardened behavior | allowlisted divergence category | legacy anchor regions | required validations |
|---|---|---|---|---|---|---|
| P2C007-EC-1 | empty_graph receives create_using value without graph constructor/instance semantics | raise deterministic TypeError and fail closed | same fail-closed TypeError envelope with deterministic audit metadata only | bounded_diagnostic_enrichment | P2C007-R3 | networkx/generators/classic.py:671-673; networkx/generators/tests/test_classic.py:271-273 |
| P2C007-EC-2 | unknown incompatible generator feature/metadata path enters packet boundary | fail closed with deterministic incompatibility envelope | fail closed by default; diagnostics may annotate allowlisted context only | none | P2C007-R1; P2C007-R2; P2C007-R3; P2C007-R4 | artifacts/phase2c/FNX-P2C-007/parity_gate.yaml; adversarial::fnx-p2c-007::malformed_inputs |

## Strict/Hardened Divergence
- strict: preserve generator topology/order contracts with zero mismatch budget and fail closed on invalid create_using or unknown incompatible pathways
- hardened: no topology/output drift allowed; divergence limited to bounded_diagnostic_enrichment metadata with deterministic replay evidence
- unknown incompatible generator features or metadata paths fail closed unless explicitly allowlisted with deterministic audit evidence

## Determinism Commitments
| row id | commitment | tie-break rule | legacy anchor regions | required validations |
|---|---|---|---|---|
| P2C007-DC-1 | complete_graph edge materialization is deterministic | undirected uses combinations; directed uses permutations over stable node order | P2C007-R1 | networkx/generators/classic.py:354-358; networkx/generators/tests/test_classic.py:147-182 |
| P2C007-DC-2 | cycle_graph closure ordering is deterministic | pairwise(cyclic=True) preserves input node sequence and single closure edge | P2C007-R2 | networkx/generators/classic.py:503-505; networkx/generators/tests/test_classic.py:212-235 |
| P2C007-DC-3 | path_graph edge emission is deterministic under iterable input | pairwise preserves iterable order and directed orientation | P2C007-R4 | networkx/generators/classic.py:806-809; networkx/generators/tests/test_classic.py:409-444 |
| P2C007-DC-4 | empty_graph node insertion order and class dispatch are deterministic | create_using dispatch order is None -> type -> graph instance with clear() | P2C007-R3 | networkx/generators/classic.py:667-680; networkx/generators/tests/test_classic.py:268-335 |

### Machine-Checkable Invariant Matrix
| invariant id | precondition | postcondition | preservation obligation | legacy anchor regions | required validations |
|---|---|---|---|---|---|
| P2C007-IV-1 | generator family complete/cycle/path is invoked with scoped create_using | output topology, edge orientation, and node identity match legacy-observable contract | strict mode forbids any repair that changes generated edge set, order, or directedness | P2C007-R1; P2C007-R2; P2C007-R4 | generated/generators_complete_strict.json; generated/generators_cycle_strict.json; generated/generators_path_strict.json; differential::fnx-p2c-007::fixtures |
| P2C007-IV-2 | empty_graph receives constructor/instance create_using pathways | result graph class and node-set cardinality remain deterministic with zero edges | both modes preserve create_using dispatch behavior and fail closed on invalid graph-type inputs | P2C007-R3 | networkx/generators/tests/test_classic.py:268-335; unit::fnx-p2c-007::contract |
| P2C007-IV-3 | hardened mode emits diagnostics under adversarial or malformed generator requests | diagnostics remain deterministic and do not alter returned graph topology | hardened divergence is bounded to allowlisted diagnostic metadata and remains replay-auditable | P2C007-R1; P2C007-R2; P2C007-R3; P2C007-R4 | adversarial::fnx-p2c-007::malformed_inputs; e2e::fnx-p2c-007::golden_journey |


## Rust Module Boundary Skeleton
| boundary id | crate | module path | public seam | internal ownership | legacy compatibility surface | threat boundary refs | compile-check proof | parallel contributor scope |
|---|---|---|---|---|---|---|---|---|
| P2C007-MB-1 | fnx-generators | crates/fnx-generators/src/lib.rs | pub fn complete_graph | complete_graph node-container normalization, deterministic edge materialization for Graph/DiGraph constructors, and duplicate-node compatibility handling | networkx.generators.classic.complete_graph | P2C007-CB-2; P2C007-CB-3; P2C007-CB-4 | cargo test -p fnx-generators -- --nocapture | complete_graph semantics and determinism probes only |
| P2C007-MB-2 | fnx-generators | crates/fnx-generators/src/lib.rs | pub fn cycle_graph / pub fn path_graph | pairwise cyclic closure and iterable-order path emission semantics, including directed orientation and duplicate-label behavior parity | networkx.generators.classic.cycle_graph / networkx.generators.classic.path_graph | P2C007-CB-2; P2C007-CB-3; P2C007-CB-4 | cargo check -p fnx-generators --all-targets | cycle/path ordering and closure semantics only |
| P2C007-MB-3 | fnx-generators | crates/fnx-generators/src/lib.rs | pub fn empty_graph | create_using dispatch ordering, graph-instance clear-before-populate invariants, and TypeError fail-closed envelopes for invalid graph-type inputs | networkx.generators.classic.empty_graph | P2C007-CB-1; P2C007-CB-5 | cargo test -p fnx-generators empty_graph -- --nocapture | empty_graph constructor/instance boundary only |
| P2C007-MB-4 | fnx-runtime | crates/fnx-runtime/src/lib.rs | pub struct CgsePolicyEngine | strict/hardened policy-row enforcement, allowlisted hardened deviation controls, and deterministic decision evidence emission for generator packet boundaries | strict/hardened compatibility envelope for generator classic family | P2C007-CB-1; P2C007-CB-3; P2C007-CB-5 | cargo check -p fnx-runtime --all-targets | generator policy routing and evidence terms only |


## Dependency-Aware Implementation Sequence
| checkpoint id | order | depends on | objective | modules touched | verification entrypoints | structured logging hooks | risk checkpoint |
|---|---|---|---|---|---|---|---|
| P2C007-SEQ-1 | 1 | none | Lock compile-checkable generator module seams and packet-boundary ownership before behavior changes. | crates/fnx-generators/src/lib.rs; crates/fnx-runtime/src/lib.rs | unit::fnx-p2c-007::boundary_shape; cargo check -p fnx-generators | generators.boundary.complete_graph_ready; generators.boundary.cycle_path_ready; generators.boundary.empty_graph_ready | fail if crate seam ownership or threat-boundary mapping is ambiguous |
| P2C007-SEQ-2 | 2 | P2C007-SEQ-1 | Implement strict complete/cycle/path deterministic ordering and directedness parity with zero mismatch budget. | crates/fnx-generators/src/lib.rs | networkx/generators/tests/test_classic.py:147-235; differential::fnx-p2c-007::fixtures | generators.strict.edge_order_signature; generators.strict.cycle_closure_signature | halt if strict mode edge-order or directedness signature drifts |
| P2C007-SEQ-3 | 3 | P2C007-SEQ-1; P2C007-SEQ-2 | Finalize empty_graph create_using dispatch, instance-clear invariants, and fail-closed TypeError envelopes. | crates/fnx-generators/src/lib.rs | networkx/generators/tests/test_classic.py:268-335; adversarial::fnx-p2c-007::malformed_inputs | generators.empty_graph.create_using_dispatch; generators.empty_graph.fail_closed_type_error | fail on any create_using pathway that mutates state without clear-before-populate |
| P2C007-SEQ-4 | 4 | P2C007-SEQ-2; P2C007-SEQ-3 | Apply hardened allowlisted policy-row controls and deterministic diagnostic envelopes for generator threat classes. | crates/fnx-runtime/src/lib.rs; crates/fnx-generators/src/lib.rs | adversarial::fnx-p2c-007::ordering_drift; adversarial::fnx-p2c-007::large_n_budget_blowup | generators.hardened.allowlisted_category; generators.hardened.audit_envelope_emitted | fail on any non-allowlisted hardened deviation category |
| P2C007-SEQ-5 | 5 | P2C007-SEQ-4 | Run packet readiness/e2e/perf gates and publish replay-auditable evidence artifacts for handoff to packet test implementation beads. | crates/fnx-conformance/tests/phase2c_packet_readiness_gate.rs; scripts/run_phase2c_readiness_e2e.sh; artifacts/phase2c/FNX-P2C-007/ | cargo test -p fnx-conformance --test phase2c_packet_readiness_gate; cargo test -p fnx-conformance --test e2e_script_pack_gate | generators.readiness.gate_result; generators.e2e.replay_bundle | stop on any strict/hardened parity, security, or budget gate mismatch |


## Structured Logging + Verification Entry Points
| stage | harness | structured log hook | replay metadata fields | failure forensics artifact |
|---|---|---|---|---|
| unit | unit::fnx-p2c-007::contract | generators.unit.contract_asserted | packet_id; generator_name; strict_mode; fixture_id | artifacts/conformance/latest/structured_logs.jsonl |
| property | property::fnx-p2c-007::invariants | generators.property.invariant_checkpoint | seed; graph_fingerprint; mode_policy; invariant_id | artifacts/conformance/latest/structured_log_emitter_normalization_report.json |
| differential | differential::fnx-p2c-007::fixtures | generators.diff.oracle_comparison | fixture_id; oracle_ref; edge_order_signature; mismatch_count | artifacts/phase2c/FNX-P2C-007/parity_report.json |
| e2e | e2e::fnx-p2c-007::golden_journey | generators.e2e.replay_emitted | scenario_id; thread_id; trace_id; forensics_bundle | artifacts/conformance/latest/telemetry_dependent_unblock_matrix_v1.json |
