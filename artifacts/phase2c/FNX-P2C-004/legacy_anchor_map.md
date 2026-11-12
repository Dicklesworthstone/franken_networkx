# Legacy Anchor Map

## Legacy Scope
- packet id: FNX-P2C-004
- subsystem: Conversion and relabel contracts
- legacy module paths: networkx/convert.py, networkx/relabel.py, networkx/tests/test_convert.py, networkx/tests/test_relabel.py
- legacy symbols: to_networkx_graph, from_dict_of_lists, to_dict_of_dicts, from_dict_of_dicts, from_edgelist, relabel_nodes, convert_node_labels_to_integers

## Anchor Map
- region: P2C004-R1
  - pathway: normal
  - source anchors: networkx/convert.py:34-108; networkx/convert.py:173-183
  - symbols: to_networkx_graph, from_edgelist
  - behavior note: Conversion dispatch follows stable precedence (existing NetworkX graph, dict forms, edge-list forms, then optional integrations) before final edge-list collection fallback.
  - compatibility policy: strict mode preserves dispatch precedence and observable output shape exactly
  - downstream contract rows: Input Contract: packet operations; Output Contract: algorithm/state result; Determinism Commitments: stable traversal and output ordering
  - planned oracle tests: networkx/tests/test_convert.py:19-44; networkx/tests/test_convert.py:71-101; networkx/tests/test_convert.py:212-230
- region: P2C004-R2
  - pathway: edge
  - source anchors: networkx/convert.py:213-250; networkx/convert.py:253-370; networkx/convert.py:374-457
  - symbols: from_dict_of_lists, to_dict_of_dicts, from_dict_of_dicts
  - behavior note: Dict conversion pathways preserve NetworkX-observable multigraph and undirected de-duplication semantics, including edge-data overwrite rules for explicit edge_data values.
  - compatibility policy: retain legacy multigraph_input branch behavior and dict/list data-loss semantics
  - downstream contract rows: Input Contract: compatibility mode; Conversion/Readwrite Contract: scoped parity; Strict/Hardened Divergence: strict no repair heuristics
  - planned oracle tests: networkx/tests/test_convert.py:102-133; networkx/tests/test_convert.py:134-210; networkx/tests/test_convert.py:292-315
- region: P2C004-R3
  - pathway: adversarial
  - source anchors: networkx/convert.py:90-107; networkx/convert.py:123-171; networkx/convert.py:177-183
  - symbols: to_networkx_graph
  - behavior note: Unknown inputs, malformed dict forms, and invalid edge-list containers must fail closed via explicit TypeError/NetworkXError paths with no silent coercion in strict mode.
  - compatibility policy: strict fail-closed on unknown incompatible feature; hardened bounded recovery with audit
  - downstream contract rows: Error Contract: malformed input affecting compatibility; Error Contract: unknown incompatible feature; Strict/Hardened Divergence: hardened bounded recovery only when allowlisted
  - planned oracle tests: networkx/tests/test_convert.py:45-69; networkx/tests/test_convert.py:318-321
- region: P2C004-R4
  - pathway: relabel-determinism
  - source anchors: networkx/relabel.py:9-157; networkx/relabel.py:227-285
  - symbols: relabel_nodes, convert_node_labels_to_integers
  - behavior note: Relabel copy/in-place branches preserve API contract while order-sensitive behavior follows explicit topological or insertion-driven mapping strategy.
  - compatibility policy: preserve legacy ordering semantics for copy=True and documented copy=False caveats
  - downstream contract rows: Output Contract: algorithm/state result; Determinism Commitments: stable traversal and output ordering; Input Contract: packet operations
  - planned oracle tests: networkx/tests/test_relabel.py:9-90; networkx/tests/test_relabel.py:188-207; networkx/tests/test_relabel.py:319-349
- region: P2C004-R5
  - pathway: adversarial-relabel-collision
  - source anchors: networkx/relabel.py:130-190; networkx/relabel.py:193-223
  - symbols: relabel_nodes, _relabel_inplace, _relabel_copy
  - behavior note: Overlapping mappings, circular relabel cycles, and multigraph key collisions trigger deterministic key remapping or explicit NetworkXUnfeasible failures.
  - compatibility policy: enforce deterministic collision handling; reject unresolved cycles in copy=False
  - downstream contract rows: Error Contract: malformed input affecting compatibility; Output Contract: algorithm/state result; Determinism Commitments: stable traversal and output ordering
  - planned oracle tests: networkx/tests/test_relabel.py:208-317; networkx/tests/test_relabel.py:296-310

## Behavior Notes
- deterministic constraints: Input-form dispatch precedence remains deterministic across graph, dict, and edge-list ingestion; Relabel copy/in-place ordering policy and multigraph key collision behavior remain deterministic by mode
- compatibility-sensitive edge cases: input precedence drift; relabel contract divergence; multigraph key collision drift
- ambiguity resolution:
- legacy ambiguity: mixed-type attribute coercion on ingest
  - policy decision: strict fail-closed, hardened bounded coercion with audit
  - rationale: preserves strict parity while allowing bounded resilience in hardened mode
- legacy ambiguity: partial in-place relabel ordering under overlapping key spaces
  - policy decision: preserve legacy copy=False behavior with explicit deterministic audit note rather than forcing copy=True normalization
  - rationale: matches observable NetworkX semantics while keeping strict behavior-isomorphism

## Extraction Ledger Crosswalk
| region id | pathway | downstream contract rows | planned oracle tests |
|---|---|---|---|
| P2C004-R1 | normal | Input Contract: packet operations; Output Contract: algorithm/state result; Determinism Commitments: stable traversal and output ordering | networkx/tests/test_convert.py:19-44; networkx/tests/test_convert.py:71-101; networkx/tests/test_convert.py:212-230 |
| P2C004-R2 | edge | Input Contract: compatibility mode; Conversion/Readwrite Contract: scoped parity; Strict/Hardened Divergence: strict no repair heuristics | networkx/tests/test_convert.py:102-133; networkx/tests/test_convert.py:134-210; networkx/tests/test_convert.py:292-315 |
| P2C004-R3 | adversarial | Error Contract: malformed input affecting compatibility; Error Contract: unknown incompatible feature; Strict/Hardened Divergence: hardened bounded recovery only when allowlisted | networkx/tests/test_convert.py:45-69; networkx/tests/test_convert.py:318-321 |
| P2C004-R4 | relabel-determinism | Output Contract: algorithm/state result; Determinism Commitments: stable traversal and output ordering; Input Contract: packet operations | networkx/tests/test_relabel.py:9-90; networkx/tests/test_relabel.py:188-207; networkx/tests/test_relabel.py:319-349 |
| P2C004-R5 | adversarial-relabel-collision | Error Contract: malformed input affecting compatibility; Output Contract: algorithm/state result; Determinism Commitments: stable traversal and output ordering | networkx/tests/test_relabel.py:208-317; networkx/tests/test_relabel.py:296-310 |

## Compatibility Risk
- risk level: critical
- rationale: conversion matrix gate is required to guard compatibility-sensitive behavior.
