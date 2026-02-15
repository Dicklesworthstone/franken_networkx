# CGSE Legacy Tie-Break and Ordering Ledger

- artifact id: `cgse-legacy-tiebreak-ordering-ledger-v1`
- generated at (utc): `2026-02-15T04:44:37Z`
- baseline comparator: `legacy_networkx_code/networkx/networkx (repository checkout in current workspace)`

## Scope
Source-anchored tie-break and ordering behavior ledger for legacy NetworkX surfaces used by FrankenNetworkX CGSE policy compilation.

## Rule Index
| rule id | family | title | tie-break policy | ordering policy |
|---|---|---|---|---|
| CGSE-R01 | graph_core_mutation | MultiGraph auto-key allocation tie-break | first-unused-integer key scan | stable for fixed keydict state; gaps may be skipped after deletions |
| CGSE-R02 | graph_core_mutation | Keyless multiedge removal ordering | remove newest edge first when key=None | LIFO across multiedges between same endpoints |
| CGSE-R03 | graph_core_mutation | Directed-to-undirected attribute conflict ordering | preserve encounter-order attr selection | directed edge traversal order determines conflict winner |
| CGSE-R04 | view_semantics | Core view iteration order and union ambiguity | prefer direct dict-order surfaces; treat set-union surfaces as ambiguity hotspots | deterministic for pure dict proxies; ambiguous for set-union composites |
| CGSE-R05 | dispatch_routing | Backend-priority environment normalization | sorted-key application for unknown priority categories | stable env-variable fold order after normalization |
| CGSE-R06 | dispatch_routing | Dispatch try-order grouping and no-guess rule | grouped-priority try-order with no implicit alphabetical fallback for ambiguous group3 | group1 -> group2 -> group3 -> group4 -> group5 |
| CGSE-R07 | conversion_contracts | to_networkx_graph conversion precedence | fixed probe-order precedence | first successful conversion branch wins |
| CGSE-R08 | shortest_path_algorithms | Dijkstra fringe tie-break and predecessor selection | distance then insertion counter then predecessor-list first element | equal-weight predecessors tracked in encounter order |
| CGSE-R09 | shortest_path_algorithms | Bidirectional Dijkstra queue ordering | alternating direction + monotonic fringe counter | first discovered best meet-node wins unless shorter path found |
| CGSE-R10 | readwrite_serialization | Edgelist emission ordering | graph-edge iteration order | output row order follows edge iterator traversal |
| CGSE-R11 | readwrite_serialization | Edgelist parse sequencing and coercion | first-seen line order for duplicate/same-endpoint edges | edge insertion order matches parsed line order |
| CGSE-R12 | generator_semantics | Classic generator ordering contracts | input-iterable order and documented directed orientation | generator edge emission follows pairwise traversal |
| CGSE-R13 | runtime_config | Config validation ordering and unknown-backend reporting | deterministic sorted error-report ordering | stable validation message ordering across runs |
| CGSE-R14 | oracle_test_surface | Legacy oracle acceptance of equal-cost predecessor ordering | accept multiple equivalent predecessor orderings where legacy oracle permits | maintain compatibility allowlist for equal-cost ambiguity |

## Source Anchors
### CGSE-R01 - MultiGraph auto-key allocation tie-break
- `legacy_networkx_code/networkx/networkx/classes/multigraph.py:413-440` | symbols: `MultiGraph.new_edge_key` | behavior: New key starts at len(keydict) then increments until an unused key is found.
- ambiguity tags:
  - `CGSE-AMB-001` selected=`preserve first-unused scan exactly` - Auto-key sequence may contain gaps after remove/reinsert cycles.
- planned hooks:
  - `unit` `CGSE-UT-R01` -> `legacy_networkx_code/networkx/networkx/classes/tests/test_multigraph.py:320-362` (Edge-key assignment semantics and multigraph constructor ingestion remain parity-safe.)
  - `property` `CGSE-PROP-BASE` -> `crates/fnx-conformance/tests/phase2c_packet_readiness_gate.rs:51-187` (Phase2C readiness gate preserves deterministic + fail-closed invariants.)
  - `differential` `CGSE-DIFF-R01` -> `crates/fnx-conformance/fixtures/graph_core_mutation_hardened.json:1-200` (Graph mutation fixture bundle must preserve key behavior under strict/hardened paths.)
  - `e2e` `CGSE-E2E-BASE` -> `scripts/run_phase2c_readiness_e2e.sh:1-120` (End-to-end execution must keep replay metadata + deterministic ordering artifacts.)

### CGSE-R02 - Keyless multiedge removal ordering
- `legacy_networkx_code/networkx/networkx/classes/multigraph.py:635-700` | symbols: `MultiGraph.remove_edge` | behavior: Docs and implementation specify reverse insertion-order deletion for key=None.
- `legacy_networkx_code/networkx/networkx/classes/multidigraph.py:525-587` | symbols: `MultiDiGraph.remove_edge` | behavior: Directed multigraph path mirrors keyless LIFO removal semantics.
- ambiguity tags:
  - `CGSE-AMB-002` selected=`enforce insertion-order LIFO behavior` - Behavior depends on dict insertion-order guarantees backing popitem().
- planned hooks:
  - `unit` `CGSE-UT-R02A` -> `legacy_networkx_code/networkx/networkx/classes/tests/test_multigraph.py:363-406` (Keyed and keyless remove_edge branches remain behavior-compatible.)
  - `unit` `CGSE-UT-R02B` -> `legacy_networkx_code/networkx/networkx/classes/tests/test_multidigraph.py:329-392` (MultiDiGraph keyless removal and silent bulk-removal behavior remain parity-safe.)
  - `property` `CGSE-PROP-BASE` -> `crates/fnx-conformance/tests/phase2c_packet_readiness_gate.rs:51-187` (Phase2C readiness gate preserves deterministic + fail-closed invariants.)
  - `differential` `CGSE-DIFF-R02` -> `crates/fnx-conformance/fixtures/graph_core_mutation_hardened.json:1-200` (Differential fixture validates multiedge mutation behavior under hardened mode.)
  - `e2e` `CGSE-E2E-BASE` -> `scripts/run_phase2c_readiness_e2e.sh:1-120` (End-to-end execution must keep replay metadata + deterministic ordering artifacts.)

### CGSE-R03 - Directed-to-undirected attribute conflict ordering
- `legacy_networkx_code/networkx/networkx/classes/digraph.py:1264-1295` | symbols: `DiGraph.to_undirected` | behavior: Docs explicitly call attr choice arbitrary and encounter-order dependent.
- `legacy_networkx_code/networkx/networkx/classes/multidigraph.py:879-897` | symbols: `MultiDiGraph.to_undirected` | behavior: MultiDiGraph path carries same arbitrary-choice warning for conflicting attrs.
- ambiguity tags:
  - `CGSE-AMB-003` selected=`preserve encounter-order semantics` - Legacy contract marks conflict resolution as arbitrary.
- planned hooks:
  - `unit` `CGSE-UT-R03A` -> `legacy_networkx_code/networkx/networkx/classes/tests/test_digraph.py:101-123` (Reciprocal to_undirected behavior and reverse view interactions remain compatible.)
  - `unit` `CGSE-UT-R03B` -> `legacy_networkx_code/networkx/networkx/classes/tests/test_multidigraph.py:223-244` (Multidigraph reciprocal filtering and attribute conflict surfaces remain compatible.)
  - `property` `CGSE-PROP-BASE` -> `crates/fnx-conformance/tests/phase2c_packet_readiness_gate.rs:51-187` (Phase2C readiness gate preserves deterministic + fail-closed invariants.)
  - `differential` `CGSE-DIFF-R03` -> `crates/fnx-conformance/fixtures/graph_core_shortest_path_strict.json:1-220` (Strict fixture corpus catches drift in graph transformation semantics that affect algorithm output.)
  - `e2e` `CGSE-E2E-BASE` -> `scripts/run_phase2c_readiness_e2e.sh:1-120` (End-to-end execution must keep replay metadata + deterministic ordering artifacts.)

### CGSE-R04 - Core view iteration order and union ambiguity
- `legacy_networkx_code/networkx/networkx/classes/coreviews.py:23-53` | symbols: `AtlasView.__iter__` | behavior: AtlasView iteration returns iter(self._atlas), inheriting dict insertion order.
- `legacy_networkx_code/networkx/networkx/classes/coreviews.py:137-143` | symbols: `UnionAtlas.__iter__` | behavior: UnionAtlas iterates set(self._succ.keys()) | set(self._pred.keys()), exposing set-order ambiguity.
- ambiguity tags:
  - `CGSE-AMB-004` selected=`document and preserve legacy ambiguity` - UnionAtlas key iteration uses set union and may vary by hash-seed/process state.
- planned hooks:
  - `unit` `CGSE-UT-R04` -> `legacy_networkx_code/networkx/networkx/classes/tests/test_coreviews.py:26-81` (AtlasView/AdjacencyView iteration parity and view semantics must remain stable.)
  - `property` `CGSE-PROP-BASE` -> `crates/fnx-conformance/tests/phase2c_packet_readiness_gate.rs:51-187` (Phase2C readiness gate preserves deterministic + fail-closed invariants.)
  - `differential` `CGSE-DIFF-R04` -> `crates/fnx-conformance/fixtures/generated/view_neighbors_strict.json:1-220` (View neighbor-order fixture validates deterministic strict-mode view behavior.)
  - `e2e` `CGSE-E2E-BASE` -> `scripts/run_phase2c_readiness_e2e.sh:1-120` (End-to-end execution must keep replay metadata + deterministic ordering artifacts.)

### CGSE-R05 - Backend-priority environment normalization
- `legacy_networkx_code/networkx/networkx/utils/backends.py:164-183` | symbols: `_set_configs_from_environment` | behavior: Priority suffixes are processed with sorted(priorities) for deterministic assignment order.
- ambiguity tags:
  - `CGSE-AMB-005` selected=`preserve legacy precedence exactly` - Conflicting priority sources (NETWORKX_BACKEND_PRIORITY vs suffix variants) can shadow values.
- planned hooks:
  - `unit` `CGSE-UT-R05` -> `legacy_networkx_code/networkx/networkx/utils/tests/test_backends.py:217-218` (Configured backend-priority contexts drive dispatch behavior deterministically.)
  - `property` `CGSE-PROP-BASE` -> `crates/fnx-conformance/tests/phase2c_packet_readiness_gate.rs:51-187` (Phase2C readiness gate preserves deterministic + fail-closed invariants.)
  - `differential` `CGSE-DIFF-R05` -> `crates/fnx-conformance/fixtures/generated/dispatch_route_strict.json:1-220` (Dispatch route fixture confirms route-selection behavior and fail-closed outcomes.)
  - `e2e` `CGSE-E2E-BASE` -> `scripts/run_phase2c_readiness_e2e.sh:1-120` (End-to-end execution must keep replay metadata + deterministic ordering artifacts.)

### CGSE-R06 - Dispatch try-order grouping and no-guess rule
- `legacy_networkx_code/networkx/networkx/utils/backends.py:848-930` | symbols: `_dispatchable._call_if_any_backends_installed` | behavior: Group1..5 ordering and explicit refusal to guess when len(group3)>1 are hard-coded.
- ambiguity tags:
  - `CGSE-AMB-006` selected=`fail/skip conversions rather than guess` - Multiple unspecified backend inputs create unresolved tie in group3.
- planned hooks:
  - `unit` `CGSE-UT-R06` -> `legacy_networkx_code/networkx/networkx/utils/tests/test_backends.py:136-158` (Mixing backend graphs should follow configured routing behavior and conversion boundaries.)
  - `property` `CGSE-PROP-BASE` -> `crates/fnx-conformance/tests/phase2c_packet_readiness_gate.rs:51-187` (Phase2C readiness gate preserves deterministic + fail-closed invariants.)
  - `differential` `CGSE-DIFF-R06` -> `crates/fnx-conformance/fixtures/generated/dispatch_route_strict.json:1-220` (Dispatch differential fixture captures routing + fallback outputs.)
  - `e2e` `CGSE-E2E-BASE` -> `scripts/run_phase2c_readiness_e2e.sh:1-120` (End-to-end execution must keep replay metadata + deterministic ordering artifacts.)

### CGSE-R07 - to_networkx_graph conversion precedence
- `legacy_networkx_code/networkx/networkx/convert.py:34-122` | symbols: `to_networkx_graph` | behavior: Control flow enforces deterministic conversion precedence with fallback chain and mode-sensitive dict handling.
- ambiguity tags:
  - `CGSE-AMB-007` selected=`preserve dict-of-dicts attempt before dict-of-lists` - Dict inputs may satisfy multiple representations (dict-of-dicts vs dict-of-lists).
- planned hooks:
  - `unit` `CGSE-UT-R07` -> `legacy_networkx_code/networkx/networkx/tests/test_convert.py:21-31` (Convert tests validate dict/list/graph conversion precedence contracts.)
  - `property` `CGSE-PROP-BASE` -> `crates/fnx-conformance/tests/phase2c_packet_readiness_gate.rs:51-187` (Phase2C readiness gate preserves deterministic + fail-closed invariants.)
  - `differential` `CGSE-DIFF-R07` -> `crates/fnx-conformance/fixtures/generated/convert_edge_list_strict.json:1-220` (Conversion fixture ensures strict conversion semantics remain parity-safe.)
  - `e2e` `CGSE-E2E-BASE` -> `scripts/run_phase2c_readiness_e2e.sh:1-120` (End-to-end execution must keep replay metadata + deterministic ordering artifacts.)

### CGSE-R08 - Dijkstra fringe tie-break and predecessor selection
- `legacy_networkx_code/networkx/networkx/algorithms/shortest_paths/weighted.py:837-903` | symbols: `_dijkstra_multisource` | behavior: Heap uses (distance, next(count), node); path reconstruction selects pred_dict[v][0].
- ambiguity tags:
  - `CGSE-AMB-008` selected=`preserve predecessor encounter order` - Equal-cost predecessor lists may contain multiple valid orderings.
- planned hooks:
  - `unit` `CGSE-UT-R08` -> `legacy_networkx_code/networkx/networkx/algorithms/shortest_paths/tests/test_weighted.py:271-286` (Predecessor and distance tests allow documented equal-cost ordering variants.)
  - `property` `CGSE-PROP-BASE` -> `crates/fnx-conformance/tests/phase2c_packet_readiness_gate.rs:51-187` (Phase2C readiness gate preserves deterministic + fail-closed invariants.)
  - `differential` `CGSE-DIFF-R08` -> `crates/fnx-conformance/fixtures/graph_core_shortest_path_strict.json:1-220` (Shortest-path fixture validates deterministic path outputs under strict mode.)
  - `e2e` `CGSE-E2E-BASE` -> `scripts/run_phase2c_readiness_e2e.sh:1-120` (End-to-end execution must keep replay metadata + deterministic ordering artifacts.)

### CGSE-R09 - Bidirectional Dijkstra queue ordering
- `legacy_networkx_code/networkx/networkx/algorithms/shortest_paths/weighted.py:2398-2453` | symbols: `bidirectional_dijkstra` | behavior: Forward/backward fringes use (distance, next(count), node) and alternate expansion direction.
- planned hooks:
  - `unit` `CGSE-UT-R09` -> `legacy_networkx_code/networkx/networkx/algorithms/shortest_paths/tests/test_weighted.py:165-182` (Bidirectional shortest-path tests verify distance/path parity for representative graph families.)
  - `property` `CGSE-PROP-BASE` -> `crates/fnx-conformance/tests/phase2c_packet_readiness_gate.rs:51-187` (Phase2C readiness gate preserves deterministic + fail-closed invariants.)
  - `differential` `CGSE-DIFF-R09` -> `crates/fnx-conformance/fixtures/graph_core_shortest_path_strict.json:1-220` (Bidirectional behavior contributes to strict shortest-path fixture parity.)
  - `e2e` `CGSE-E2E-BASE` -> `scripts/run_phase2c_readiness_e2e.sh:1-120` (End-to-end execution must keep replay metadata + deterministic ordering artifacts.)

### CGSE-R10 - Edgelist emission ordering
- `legacy_networkx_code/networkx/networkx/readwrite/edgelist.py:43-123` | symbols: `generate_edgelist` | behavior: Emission loops directly over G.edges(data=...), inheriting graph iteration order.
- ambiguity tags:
  - `CGSE-AMB-009` selected=`preserve native dict order in strict mode` - Stringified dict payload order depends on underlying dict key order.
- planned hooks:
  - `unit` `CGSE-UT-R10` -> `legacy_networkx_code/networkx/networkx/readwrite/tests/test_edgelist.py:187-217` (write_edgelist variants validate no-data/data/key-filter serialization behavior.)
  - `property` `CGSE-PROP-BASE` -> `crates/fnx-conformance/tests/phase2c_packet_readiness_gate.rs:51-187` (Phase2C readiness gate preserves deterministic + fail-closed invariants.)
  - `differential` `CGSE-DIFF-R10` -> `crates/fnx-conformance/fixtures/generated/readwrite_roundtrip_strict.json:1-220` (Read/write strict roundtrip fixture checks serialized edge-order stability.)
  - `e2e` `CGSE-E2E-BASE` -> `scripts/run_phase2c_readiness_e2e.sh:1-120` (End-to-end execution must keep replay metadata + deterministic ordering artifacts.)

### CGSE-R11 - Edgelist parse sequencing and coercion
- `legacy_networkx_code/networkx/networkx/readwrite/edgelist.py:249-296` | symbols: `parse_edgelist` | behavior: Line splitting, coercion, and add_edge happen in stream order; conversion errors are fail-fast.
- planned hooks:
  - `unit` `CGSE-UT-R11` -> `legacy_networkx_code/networkx/networkx/readwrite/tests/test_edgelist.py:117-170` (parse_edgelist variants validate typed coercion, delimiter, and malformed input handling.)
  - `property` `CGSE-PROP-BASE` -> `crates/fnx-conformance/tests/phase2c_packet_readiness_gate.rs:51-187` (Phase2C readiness gate preserves deterministic + fail-closed invariants.)
  - `differential` `CGSE-DIFF-R11` -> `crates/fnx-conformance/fixtures/generated/readwrite_json_roundtrip_strict.json:1-220` (JSON/edgelist roundtrip fixture captures parse + serialization sequencing invariants.)
  - `e2e` `CGSE-E2E-BASE` -> `scripts/run_phase2c_readiness_e2e.sh:1-120` (End-to-end execution must keep replay metadata + deterministic ordering artifacts.)

### CGSE-R12 - Classic generator ordering contracts
- `legacy_networkx_code/networkx/networkx/generators/classic.py:478-505` | symbols: `cycle_graph` | behavior: Directed cycle orientation is documented as increasing order and built via pairwise(nodes, cyclic=True).
- `legacy_networkx_code/networkx/networkx/generators/classic.py:788-808` | symbols: `path_graph` | behavior: Path edges are built in the iterable order provided by caller.
- ambiguity tags:
  - `CGSE-AMB-010` selected=`preserve legacy duplicate-node behavior` - Duplicate nodes in iterable input are accepted and can create surprising structures.
- planned hooks:
  - `unit` `CGSE-UT-R12` -> `legacy_networkx_code/networkx/networkx/generators/tests/test_classic.py:212-232` (cycle_graph directed ordering and duplicate iterable behavior remain covered.)
  - `unit` `CGSE-UT-R12B` -> `legacy_networkx_code/networkx/networkx/generators/tests/test_classic.py:409-442` (path_graph iterable-order semantics remain parity-safe.)
  - `property` `CGSE-PROP-BASE` -> `crates/fnx-conformance/tests/phase2c_packet_readiness_gate.rs:51-187` (Phase2C readiness gate preserves deterministic + fail-closed invariants.)
  - `differential` `CGSE-DIFF-R12` -> `crates/fnx-conformance/fixtures/generated/generators_cycle_strict.json:1-220` (Generator cycle fixture validates deterministic construction order.)
  - `e2e` `CGSE-E2E-BASE` -> `scripts/run_phase2c_readiness_e2e.sh:1-120` (End-to-end execution must keep replay metadata + deterministic ordering artifacts.)

### CGSE-R13 - Config validation ordering and unknown-backend reporting
- `legacy_networkx_code/networkx/networkx/utils/configs.py:252-270` | symbols: `BackendPriorities._on_setattr` | behavior: Unknown backend list is rendered via sorted(missing), stabilizing diagnostics.
- `legacy_networkx_code/networkx/networkx/utils/configs.py:366-381` | symbols: `NetworkXConfig._on_setattr` | behavior: Backends config validation also sorts missing backend names before raising.
- planned hooks:
  - `unit` `CGSE-UT-R13` -> `legacy_networkx_code/networkx/networkx/utils/tests/test_config.py:120-169` (Config tests assert backend-priority typing and unknown-backend error behavior.)
  - `property` `CGSE-PROP-BASE` -> `crates/fnx-conformance/tests/phase2c_packet_readiness_gate.rs:51-187` (Phase2C readiness gate preserves deterministic + fail-closed invariants.)
  - `differential` `CGSE-DIFF-R13` -> `crates/fnx-conformance/fixtures/generated/runtime_config_optional_strict.json:1-220` (Runtime optional-config fixture validates strict-mode config resolution paths.)
  - `e2e` `CGSE-E2E-BASE` -> `scripts/run_phase2c_readiness_e2e.sh:1-120` (End-to-end execution must keep replay metadata + deterministic ordering artifacts.)

### CGSE-R14 - Legacy oracle acceptance of equal-cost predecessor ordering
- `legacy_networkx_code/networkx/networkx/algorithms/shortest_paths/tests/test_weighted.py:271-286` | symbols: `test_dijkstra_predecessor2` | behavior: Oracle test permits pred[2] in [[1, 3], [3, 1]], confirming intentional ambiguity envelope.
- ambiguity tags:
  - `CGSE-AMB-011` selected=`allow documented permutation set` - Equal-cost predecessor ordering is intentionally non-unique in oracle contract.
- planned hooks:
  - `unit` `CGSE-UT-R14` -> `legacy_networkx_code/networkx/networkx/algorithms/shortest_paths/tests/test_weighted.py:271-286` (Oracle test itself encodes allowed predecessor-order permutations.)
  - `property` `CGSE-PROP-BASE` -> `crates/fnx-conformance/tests/phase2c_packet_readiness_gate.rs:51-187` (Phase2C readiness gate preserves deterministic + fail-closed invariants.)
  - `differential` `CGSE-DIFF-R14` -> `crates/fnx-conformance/fixtures/generated/conformance_harness_strict.json:1-220` (Harness fixture tracks expected outputs and ambiguity-tolerant comparison semantics.)
  - `e2e` `CGSE-E2E-BASE` -> `scripts/run_phase2c_readiness_e2e.sh:1-120` (End-to-end execution must keep replay metadata + deterministic ordering artifacts.)

## Ambiguity Register
| ambiguity id | rule id | family | selected policy | risk note |
|---|---|---|---|---|
| CGSE-AMB-001 | CGSE-R01 | graph_core_mutation | preserve first-unused scan exactly | Reindexing keys would alter observable MultiGraph edge-key contracts. |
| CGSE-AMB-002 | CGSE-R02 | graph_core_mutation | enforce insertion-order LIFO behavior | Changing keyless removal order mutates user-visible edge deletion outcomes. |
| CGSE-AMB-003 | CGSE-R03 | graph_core_mutation | preserve encounter-order semantics | Canonicalization would intentionally diverge from legacy observable payload selection. |
| CGSE-AMB-004 | CGSE-R04 | view_semantics | document and preserve legacy ambiguity | Imposing sorted iteration in strict mode would alter observable legacy traversal order. |
| CGSE-AMB-005 | CGSE-R05 | dispatch_routing | preserve legacy precedence exactly | Merging would change backend dispatch routing expectations. |
| CGSE-AMB-006 | CGSE-R06 | dispatch_routing | fail/skip conversions rather than guess | Guessing a backend can silently alter output/backend type semantics. |
| CGSE-AMB-007 | CGSE-R07 | conversion_contracts | preserve dict-of-dicts attempt before dict-of-lists | Changing precedence can alter graph type/edge payload interpretation. |
| CGSE-AMB-008 | CGSE-R08 | shortest_path_algorithms | preserve predecessor encounter order | Sorting predecessors changes returned path for equal-cost alternatives. |
| CGSE-AMB-009 | CGSE-R10 | readwrite_serialization | preserve native dict order in strict mode | Forced key sorting alters textual output parity for write_edgelist snapshots. |
| CGSE-AMB-010 | CGSE-R12 | generator_semantics | preserve legacy duplicate-node behavior | Deduplication changes graph topology for user-supplied repeated nodes. |
| CGSE-AMB-011 | CGSE-R14 | oracle_test_surface | allow documented permutation set | Over-canonicalization risks false negative drift findings in differential conformance. |

## Evidence References
- profile baseline: `artifacts/perf/phase2c/perf_baseline_matrix_v1.json`
- profile hotspot: `artifacts/perf/phase2c/hotspot_one_lever_backlog_v1.json`
- profile delta: `artifacts/perf/phase2c/perf_regression_gate_report_v1.json`
- isomorphism proof: `artifacts/proofs/ISOMORPHISM_PROOF_FNX_P2C_001_V1.md`
- isomorphism proof: `artifacts/proofs/ISOMORPHISM_PROOF_FNX_P2C_005_V1.md`
- isomorphism proof: `artifacts/proofs/ISOMORPHISM_PROOF_NEIGHBOR_ITER_BFS_V2.md`
- structured logging evidence: `artifacts/conformance/latest/structured_logs.json`
- structured logging evidence: `artifacts/conformance/latest/structured_logs.jsonl`
- structured logging evidence: `artifacts/conformance/latest/telemetry_dependent_unblock_matrix_v1.json`
