# Legacy Anchor Map

## Legacy Scope
- packet id: FNX-P2C-006
- subsystem: Read/write edgelist and json graph
- legacy module paths: networkx/readwrite/edgelist.py, networkx/readwrite/json_graph/
- legacy symbols: generate_edgelist, write_edgelist, parse_edgelist, read_edgelist

## Anchor Map
- region: P2C006-R1
  - pathway: normal
  - source anchors: networkx/readwrite/edgelist.py:43-123; networkx/readwrite/edgelist.py:126-174; networkx/readwrite/edgelist.py:300-385
  - symbols: generate_edgelist, write_edgelist, read_edgelist
  - behavior note: Edge-list generation/write/read pathways preserve deterministic line emission, encoding, and round-trip reconstruction for scoped graph classes.
  - compatibility policy: strict mode preserves edgelist round-trip semantics and output ordering exactly
  - downstream contract rows: Input Contract: packet operations; Output Contract: algorithm/state result; Determinism Commitments: stable traversal and output ordering
  - planned oracle tests: networkx/readwrite/tests/test_edgelist.py:80-107; networkx/readwrite/tests/test_edgelist.py:187-220; networkx/readwrite/tests/test_edgelist.py:251-302
- region: P2C006-R2
  - pathway: edge
  - source anchors: networkx/readwrite/edgelist.py:176-297; networkx/readwrite/edgelist.py:388-489
  - symbols: parse_edgelist, write_weighted_edgelist, read_weighted_edgelist
  - behavior note: Parser tokenization, delimiter/comment handling, and typed edge-data conversion preserve legacy coercion/skip behavior for no-data, dict-data, and weighted tuple modes.
  - compatibility policy: retain legacy parse semantics across delimiter, nodetype, and weighted-data pathways
  - downstream contract rows: Input Contract: compatibility mode; Strict/Hardened Divergence: strict no repair heuristics; Error Contract: malformed input affecting compatibility
  - planned oracle tests: networkx/readwrite/tests/test_edgelist.py:86-90; networkx/readwrite/tests/test_edgelist.py:117-173; networkx/readwrite/tests/test_edgelist.py:304-318
- region: P2C006-R3
  - pathway: adversarial
  - source anchors: networkx/readwrite/edgelist.py:243-252; networkx/readwrite/edgelist.py:256-295; networkx/readwrite/tests/test_edgelist.py:142-173
  - symbols: parse_edgelist
  - behavior note: Malformed node/data conversions and mismatched data-key lengths fail closed with stable TypeError/IndexError envelopes while short or comment-only lines are ignored deterministically.
  - compatibility policy: strict fail-closed on malformed parse payloads; hardened bounded recovery only when allowlisted
  - downstream contract rows: Error Contract: malformed input affecting compatibility; Error Contract: unknown incompatible feature; Strict/Hardened Divergence: hardened bounded recovery only when allowlisted
  - planned oracle tests: networkx/readwrite/tests/test_edgelist.py:142-165; networkx/readwrite/tests/test_edgelist.py:167-173; networkx/readwrite/tests/test_edgelist.py:304-318
- region: P2C006-R4
  - pathway: json-roundtrip
  - source anchors: networkx/readwrite/json_graph/adjacency.py:8-81; networkx/readwrite/json_graph/adjacency.py:84-156; networkx/readwrite/json_graph/node_link.py:26-140; networkx/readwrite/json_graph/node_link.py:143-261
  - symbols: adjacency_data, adjacency_graph, node_link_data, node_link_graph, _to_tuple
  - behavior note: Adjacency and node-link serializers preserve directed/multigraph flags, node/edge attrs, tuple-node restoration, and deterministic JSON graph round-trip reconstruction.
  - compatibility policy: preserve legacy json_graph schema and reconstruction semantics across adjacency/node-link modes
  - downstream contract rows: Output Contract: algorithm/state result; Determinism Commitments: stable traversal and output ordering; Input Contract: packet operations
  - planned oracle tests: networkx/readwrite/json_graph/tests/test_adjacency.py:12-75; networkx/readwrite/json_graph/tests/test_node_link.py:10-50; networkx/readwrite/json_graph/tests/test_node_link.py:52-109
- region: P2C006-R5
  - pathway: json-adversarial
  - source anchors: networkx/readwrite/json_graph/adjacency.py:59-63; networkx/readwrite/json_graph/node_link.py:123-127; networkx/readwrite/json_graph/tests/test_adjacency.py:74-78; networkx/readwrite/json_graph/tests/test_node_link.py:10-14
  - symbols: adjacency_data, node_link_data
  - behavior note: Attribute-key collisions for id/source/target/key fields are rejected deterministically with explicit NetworkXError envelopes to avoid ambiguous JSON payload schemas.
  - compatibility policy: fail-closed default for ambiguous json_graph attribute naming contracts
  - downstream contract rows: Error Contract: malformed input affecting compatibility; Error Contract: unknown incompatible feature; Input Contract: compatibility mode
  - planned oracle tests: networkx/readwrite/json_graph/tests/test_adjacency.py:74-78; networkx/readwrite/json_graph/tests/test_node_link.py:10-14; networkx/readwrite/json_graph/tests/test_node_link.py:72-77

## Behavior Notes
- deterministic constraints: Round-trip serialization remains deterministic; Malformed line handling is deterministic by mode policy
- compatibility-sensitive edge cases: parser ambiguity; serialization round-trip drift
- ambiguity resolution:
- legacy ambiguity: malformed token tolerance in edgelist parsing
  - policy decision: strict reject; hardened bounded recovery with warnings
  - rationale: strict keeps parity; hardened remains API-compatible and auditable

## Extraction Ledger Crosswalk
| region id | pathway | downstream contract rows | planned oracle tests |
|---|---|---|---|
| P2C006-R1 | normal | Input Contract: packet operations; Output Contract: algorithm/state result; Determinism Commitments: stable traversal and output ordering | networkx/readwrite/tests/test_edgelist.py:80-107; networkx/readwrite/tests/test_edgelist.py:187-220; networkx/readwrite/tests/test_edgelist.py:251-302 |
| P2C006-R2 | edge | Input Contract: compatibility mode; Strict/Hardened Divergence: strict no repair heuristics; Error Contract: malformed input affecting compatibility | networkx/readwrite/tests/test_edgelist.py:86-90; networkx/readwrite/tests/test_edgelist.py:117-173; networkx/readwrite/tests/test_edgelist.py:304-318 |
| P2C006-R3 | adversarial | Error Contract: malformed input affecting compatibility; Error Contract: unknown incompatible feature; Strict/Hardened Divergence: hardened bounded recovery only when allowlisted | networkx/readwrite/tests/test_edgelist.py:142-165; networkx/readwrite/tests/test_edgelist.py:167-173; networkx/readwrite/tests/test_edgelist.py:304-318 |
| P2C006-R4 | json-roundtrip | Output Contract: algorithm/state result; Determinism Commitments: stable traversal and output ordering; Input Contract: packet operations | networkx/readwrite/json_graph/tests/test_adjacency.py:12-75; networkx/readwrite/json_graph/tests/test_node_link.py:10-50; networkx/readwrite/json_graph/tests/test_node_link.py:52-109 |
| P2C006-R5 | json-adversarial | Error Contract: malformed input affecting compatibility; Error Contract: unknown incompatible feature; Input Contract: compatibility mode | networkx/readwrite/json_graph/tests/test_adjacency.py:74-78; networkx/readwrite/json_graph/tests/test_node_link.py:10-14; networkx/readwrite/json_graph/tests/test_node_link.py:72-77 |

## Compatibility Risk
- risk level: high
- rationale: parser adversarial gate is required to guard compatibility-sensitive behavior.
