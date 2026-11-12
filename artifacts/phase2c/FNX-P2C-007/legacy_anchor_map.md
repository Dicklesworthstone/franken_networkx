# Legacy Anchor Map

## Legacy Scope
- packet id: FNX-P2C-007
- subsystem: Generator first wave
- legacy module paths: networkx/generators/
- legacy symbols: path_graph, cycle_graph, complete_graph, empty_graph

## Anchor Map
- region: P2C007-R1
  - pathway: normal
  - source anchors: networkx/generators/classic.py:316-359; networkx/generators/tests/test_classic.py:147-182
  - symbols: complete_graph
  - behavior note: complete_graph materializes all pairwise edges deterministically, with undirected using combinations and directed using permutations; duplicate labels in node containers preserve legacy self-loop/backward-compatible behavior.
  - compatibility policy: strict mode preserves complete_graph edge cardinality and directed/undirected orientation exactly, including duplicate-node container effects
  - downstream contract rows: Input Contract: packet operations; Output Contract: algorithm/state result; Determinism Commitments: stable traversal and output ordering
  - planned oracle tests: networkx/generators/tests/test_classic.py:147-170; networkx/generators/tests/test_classic.py:171-182
- region: P2C007-R2
  - pathway: normal
  - source anchors: networkx/generators/classic.py:478-505; networkx/generators/tests/test_classic.py:212-235
  - symbols: cycle_graph
  - behavior note: cycle_graph emits pairwise cyclic edges in deterministic sequence and preserves directed orientation for DiGraph constructors.
  - compatibility policy: preserve cycle closure ordering and directed edge direction to avoid output-order drift
  - downstream contract rows: Input Contract: packet operations; Output Contract: algorithm/state result; Determinism Commitments: stable traversal and output ordering
  - planned oracle tests: networkx/generators/tests/test_classic.py:212-220; networkx/generators/tests/test_classic.py:222-235
- region: P2C007-R3
  - pathway: edge
  - source anchors: networkx/generators/classic.py:586-680; networkx/generators/tests/test_classic.py:268-335
  - symbols: empty_graph
  - behavior note: empty_graph deterministically constructs or clears graph instances, preserves requested graph class, and fails closed when create_using is not a valid graph constructor or instance.
  - compatibility policy: strict and hardened modes both preserve create_using semantics and TypeError envelopes for invalid graph-type inputs
  - downstream contract rows: Input Contract: compatibility mode; Error Contract: malformed input affecting compatibility; Error Contract: unknown incompatible feature
  - planned oracle tests: networkx/generators/tests/test_classic.py:268-305; networkx/generators/tests/test_classic.py:307-335
- region: P2C007-R4
  - pathway: normal
  - source anchors: networkx/generators/classic.py:788-809; networkx/generators/tests/test_classic.py:409-444
  - symbols: path_graph
  - behavior note: path_graph preserves iterable order in path construction and deterministic edge emission, including duplicate-node input behavior in both directed and undirected constructors.
  - compatibility policy: preserve ordered-path construction semantics and duplicate-node handling exactly
  - downstream contract rows: Input Contract: packet operations; Output Contract: algorithm/state result; Determinism Commitments: stable traversal and output ordering
  - planned oracle tests: networkx/generators/tests/test_classic.py:409-427; networkx/generators/tests/test_classic.py:428-444

## Behavior Notes
- deterministic constraints: Generated node and edge ordering is deterministic; Seeded random generation remains deterministic across runs
- compatibility-sensitive edge cases: seed interpretation drift; edge emission order drift
- ambiguity resolution:
- legacy ambiguity: large-cycle edge emission ordering
  - policy decision: canonical cycle closure order
  - rationale: prevents output-order drift across environments

## Extraction Ledger Crosswalk
| region id | pathway | downstream contract rows | planned oracle tests |
|---|---|---|---|
| P2C007-R1 | normal | Input Contract: packet operations; Output Contract: algorithm/state result; Determinism Commitments: stable traversal and output ordering | networkx/generators/tests/test_classic.py:147-170; networkx/generators/tests/test_classic.py:171-182 |
| P2C007-R2 | normal | Input Contract: packet operations; Output Contract: algorithm/state result; Determinism Commitments: stable traversal and output ordering | networkx/generators/tests/test_classic.py:212-220; networkx/generators/tests/test_classic.py:222-235 |
| P2C007-R3 | edge | Input Contract: compatibility mode; Error Contract: malformed input affecting compatibility; Error Contract: unknown incompatible feature | networkx/generators/tests/test_classic.py:268-305; networkx/generators/tests/test_classic.py:307-335 |
| P2C007-R4 | normal | Input Contract: packet operations; Output Contract: algorithm/state result; Determinism Commitments: stable traversal and output ordering | networkx/generators/tests/test_classic.py:409-427; networkx/generators/tests/test_classic.py:428-444 |

## Compatibility Risk
- risk level: high
- rationale: generator determinism gate is required to guard compatibility-sensitive behavior.
