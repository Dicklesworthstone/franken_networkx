# Contract Table

## Input Contract
| row id | API/behavior | preconditions | strict policy | hardened policy | legacy anchor regions | required validations |
|---|---|---|---|---|---|---|
| P2C004-IC-1 | to_networkx_graph input-form dispatch precedence | input candidate may satisfy multiple adapters (graph/dict/collection); legacy branch evaluation order is fixed | evaluate conversion branches in legacy order and fail closed when branch validation fails | preserve branch order; allow only bounded diagnostic enrichment before fail-closed exit | P2C004-R1; P2C004-R3 | networkx/tests/test_convert.py:19-44; networkx/tests/test_convert.py:45-69; networkx/tests/test_convert.py:318-321 |
| P2C004-IC-2 | dict-of-lists/dicts conversion and multigraph_input semantics | dict payload shape, create_using graph kind, and multigraph_input flag are explicit | preserve undirected seen-edge dedupe and edge_data overwrite semantics exactly | same defaults; bounded attribute coercion allowed only under allowlisted audited paths | P2C004-R2; P2C004-R3 | networkx/tests/test_convert.py:102-133; networkx/tests/test_convert.py:134-210; networkx/tests/test_convert.py:292-315 |
| P2C004-IC-3 | relabel mapping and copy-mode semantics | mapping is callable/mapping and copy flag is explicit | copy=False follows topological/insertion ordering semantics; unresolved cycles fail closed | same ordering semantics; diagnostics may be enriched but no implicit copy-mode rewrite | P2C004-R4; P2C004-R5 | networkx/tests/test_relabel.py:91-140; networkx/tests/test_relabel.py:188-207; networkx/tests/test_relabel.py:312-349 |

## Output Contract
| row id | output behavior | postconditions | strict policy | hardened policy | legacy anchor regions | required validations |
|---|---|---|---|---|---|---|
| P2C004-OC-1 | conversion output graph class and edge payload shape | node/edge membership and edge-data projection match legacy semantics for selected branch | zero mismatch budget for conversion output drift | same output contract unless bounded attribute-coercion category is allowlisted and audited | P2C004-R1; P2C004-R2 | networkx/tests/test_convert.py:102-133; networkx/tests/test_convert.py:134-210 |
| P2C004-OC-2 | relabel output ordering and attribute preservation | node/edge attributes remain preserved and ordering semantics follow copy/order mode contract | no hidden reordering beyond documented legacy behavior | same output contract with deterministic audit envelopes for allowlisted deviations | P2C004-R4; P2C004-R5 | networkx/tests/test_relabel.py:91-140; networkx/tests/test_relabel.py:319-349 |
| P2C004-OC-3 | convert_node_labels_to_integers label_attribute mapping | integer label assignment and optional reverse-label attribute mapping are deterministic | ordering selector fully determines label mapping | same mapping contract; only bounded diagnostics are allowlisted | P2C004-R4 | networkx/tests/test_relabel.py:9-90 |

## Error Contract
| row id | trigger | strict behavior | hardened behavior | allowlisted divergence category | legacy anchor regions | required validations |
|---|---|---|---|---|---|---|
| P2C004-EC-1 | unknown or malformed to_networkx_graph input type | raise NetworkXError/TypeError per legacy branch semantics (fail-closed) | same fail-closed default; attach deterministic diagnostics only | bounded_diagnostic_enrichment | P2C004-R3 | networkx/tests/test_convert.py:45-69; networkx/tests/test_convert.py:318-321 |
| P2C004-EC-2 | relabel copy=False circular overlap without topological ordering | raise NetworkXUnfeasible and preserve source graph state | same exception path; no implicit copy=True fallback | none | P2C004-R5 | networkx/tests/test_relabel.py:312-317 |
| P2C004-EC-3 | multigraph relabel key collision during merge | deterministically re-key to lowest available non-negative integer when collisions occur | same deterministic re-key; bounded collision diagnostics are allowlisted | deterministic_tie_break_normalization | P2C004-R5 | networkx/tests/test_relabel.py:230-295; networkx/tests/test_relabel.py:296-310 |
| P2C004-EC-4 | incompatible conversion metadata payload in strict mode | raise fail-closed conversion error and emit no repaired output | quarantine unsupported metadata then fail closed if parity proof is absent | quarantine_of_unsupported_metadata | P2C004-R2; P2C004-R3 | networkx/tests/test_convert.py:134-210; networkx/tests/test_convert.py:45-69 |

## Strict/Hardened Divergence
- strict: fail-closed on unknown incompatible input/metadata paths with zero mismatch budget for conversion and relabel outputs
- hardened: divergence allowed only in allowlisted categories with deterministic audit evidence and explicit compatibility boundary traces
- unknown incompatible feature/metadata paths fail closed unless an allowlisted category + deterministic audit evidence is present

## Determinism Commitments
| row id | commitment | tie-break rule | legacy anchor regions | required validations |
|---|---|---|---|---|
| P2C004-DC-1 | input-form branch selection is deterministic | legacy branch order is fixed: graph -> dict_of_dicts -> dict_of_lists -> edge-list -> adapters | P2C004-R1 | networkx/tests/test_convert.py:19-44; networkx/tests/test_convert.py:45-69 |
| P2C004-DC-2 | dict conversion undirected dedupe is deterministic | first-seen orientation wins via explicit seen-set suppression | P2C004-R2 | networkx/tests/test_convert.py:134-210 |
| P2C004-DC-3 | relabel ordering is deterministic per copy/order mode | copy=False uses topological/insertion order rules; convert_node_labels_to_integers honors declared ordering selector | P2C004-R4; P2C004-R5 | networkx/tests/test_relabel.py:188-207; networkx/tests/test_relabel.py:319-349 |

### Machine-Checkable Invariant Matrix
| invariant id | precondition | postcondition | preservation obligation | legacy anchor regions | required validations |
|---|---|---|---|---|---|
| P2C004-IV-1 | create_using/multigraph_input are explicit with syntactically valid payloads | result graph preserves legacy-observable node/edge set and attribute projection | strict mode forbids silent coercion that changes observable contract | P2C004-R1; P2C004-R2; P2C004-R3 | unit::fnx-p2c-004::contract; differential::fnx-p2c-004::fixtures |
| P2C004-IV-2 | relabel mapping may overlap and merge endpoints | all intended edges are retained with deterministic key strategy and ordering semantics | copy=False cycle conflicts must fail closed with NetworkXUnfeasible | P2C004-R4; P2C004-R5 | networkx/tests/test_relabel.py:208-317; property::fnx-p2c-004::invariants |
| P2C004-IV-3 | strict/hardened mode and allowlist category are fixed for execution | strict and hardened outputs remain isomorphic unless explicit allowlisted divergence exists | unknown incompatible features/metadata paths fail closed with replayable evidence | P2C004-R3; P2C004-R4; P2C004-R5 | adversarial::fnx-p2c-004::malformed_inputs; e2e::fnx-p2c-004::golden_journey |
