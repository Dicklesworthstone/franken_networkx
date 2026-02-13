# PHASE2C_EXTRACTION_PACKET.md — FrankenNetworkX

Date: 2026-02-13

Purpose: convert Phase-2 analysis into direct implementation tickets with concrete legacy anchors, target crates, and oracle tests.

## 1. Ticket Packets

| Ticket ID | Subsystem | Legacy anchors (classes/functions) | Target crates | Oracle tests |
|---|---|---|---|---|
| `FNX-P2C-001` | Graph core semantics | `Graph` + `_CachedPropertyResetter*` in `classes/graph.py`; `DiGraph` in `classes/digraph.py`; `MultiGraph`/`MultiDiGraph` in `multigraph.py`/`multidigraph.py` | `fnx-classes` | `networkx/classes/tests/test_graph.py`, `test_digraph.py`, `test_multigraph.py` |
| `FNX-P2C-002` | View layer semantics | `AtlasView`, `AdjacencyView`, `Filter*` classes in `classes/coreviews.py`; `generic_graph_view`, `subgraph_view`, `reverse_view` in `graphviews.py` | `fnx-views` | `networkx/classes/tests/test_coreviews.py`, `test_graphviews.py` |
| `FNX-P2C-003` | Dispatchable backend routing | `_dispatchable` class, `_get_cache_key`, cache helpers in `utils/backends.py` | `fnx-dispatch`, `fnx-runtime` | `networkx/classes/tests/dispatch_interface.py` |
| `FNX-P2C-004` | Conversion and relabel contracts | `to_networkx_graph`, `from_dict_of_lists`, `to_dict_of_dicts`, `from_dict_of_dicts`, `from_edgelist` in `convert.py` | `fnx-convert` | `networkx/tests/test_convert.py` |
| `FNX-P2C-005` | Shortest-path first-wave algorithms | `_weight_function`, `dijkstra_path*`, `multi_source_dijkstra*`, `bellman_ford*`, `bidirectional_dijkstra`, `johnson` in `algorithms/shortest_paths/weighted.py` | `fnx-algorithms` | `networkx/algorithms/shortest_paths/tests/test_weighted.py` |
| `FNX-P2C-006` | Read/write edgelist contract | `generate_edgelist`, `write_edgelist`, `parse_edgelist`, `read_edgelist`, weighted variants in `readwrite/edgelist.py` | `fnx-readwrite` | `networkx/readwrite/tests/test_edgelist.py` |
| `FNX-P2C-007` | Generator first wave | deterministic/random generator behaviors in `generators/*` (scoped family) | `fnx-generators` | `networkx/generators/tests/*` |
| `FNX-P2C-008` | Runtime config and optional deps | backend/env/config and lazy import semantics in `utils/configs.py`, `lazy_imports.py` | `fnx-runtime` | utils/runtime behavior tests |
| `FNX-P2C-009` | Conformance harness corpus wiring | fixture normalization and comparison schema | `fnx-conformance` | cross-family differential suites |

## 2. Packet Definition Template

For each ticket above, deliver all artifacts in the same PR:

1. `legacy_anchor_map.md`: path + line anchors + extracted behavior.
2. `contract_table.md`: input/output/error + graph/view/dispatch semantics.
3. `fixture_manifest.json`: oracle mapping and fixture IDs.
4. `parity_gate.yaml`: strict + hardened pass criteria.
5. `risk_note.md`: boundary risks and mitigations.

## 3. Strict/Hardened Expectations per Packet

- Strict mode: exact scoped NetworkX-observable behavior.
- Hardened mode: same outward contract with bounded defensive checks for malformed inputs and backend ambiguity.
- Unknown incompatible format/backend route: fail-closed.

## 4. Immediate Execution Order

1. `FNX-P2C-001`
2. `FNX-P2C-002`
3. `FNX-P2C-003`
4. `FNX-P2C-004`
5. `FNX-P2C-005`
6. `FNX-P2C-006`
7. `FNX-P2C-007`
8. `FNX-P2C-008`
9. `FNX-P2C-009`

## 5. Done Criteria (Phase-2C)

- All 9 packets have extracted anchor maps and contract tables.
- At least one runnable fixture family exists per packet in `fnx-conformance`.
- Packet-level parity report schema is produced for every packet.
- RaptorQ sidecars are generated for fixture bundles and parity reports.

## 6. Per-Ticket Extraction Schema (Mandatory Fields)

Every `FNX-P2C-*` packet MUST include:
1. `packet_id`
2. `legacy_paths`
3. `legacy_symbols`
4. `graph_mutation_contract`
5. `view_cache_contract`
6. `dispatch_backend_contract`
7. `conversion_readwrite_contract`
8. `error_contract`
9. `strict_mode_policy`
10. `hardened_mode_policy`
11. `excluded_scope`
12. `oracle_tests`
13. `performance_sentinels`
14. `compatibility_risks`
15. `raptorq_artifacts`

Missing fields => packet state `NOT READY`.

## 7. Risk Tiering and Gate Escalation

| Ticket | Risk tier | Why | Extra gate |
|---|---|---|---|
| `FNX-P2C-001` | Critical | core graph semantics define all higher layers | mutation invariant replay |
| `FNX-P2C-002` | High | views/cache reset semantics are subtle | view coherence witness gate |
| `FNX-P2C-003` | High | backend dispatch ambiguity can cause drift | dispatch route lock |
| `FNX-P2C-004` | Critical | conversion precedence is compatibility-sensitive | conversion matrix gate |
| `FNX-P2C-005` | Critical | shortest-path correctness is high-value user surface | path witness suite |
| `FNX-P2C-006` | High | read/write format drift breaks interoperability | parser adversarial gate |

Critical tickets must pass strict drift `0`.

## 8. Packet Artifact Topology (Normative)

Directory template:
- `artifacts/phase2c/FNX-P2C-00X/legacy_anchor_map.md`
- `artifacts/phase2c/FNX-P2C-00X/contract_table.md`
- `artifacts/phase2c/FNX-P2C-00X/fixture_manifest.json`
- `artifacts/phase2c/FNX-P2C-00X/parity_gate.yaml`
- `artifacts/phase2c/FNX-P2C-00X/risk_note.md`
- `artifacts/phase2c/FNX-P2C-00X/parity_report.json`
- `artifacts/phase2c/FNX-P2C-00X/parity_report.raptorq.json`
- `artifacts/phase2c/FNX-P2C-00X/parity_report.decode_proof.json`

## 9. Optimization and Isomorphism Proof Hooks

Optimization allowed only after strict parity baseline.

Required proof block:
- graph mutation semantics preserved
- view/cache coherence preserved
- conversion/readwrite semantics preserved
- fixture checksum verification pass/fail

## 10. Packet Readiness Rubric

Packet is `READY_FOR_IMPL` only when:
1. extraction schema complete,
2. fixture manifest includes happy/edge/adversarial paths,
3. strict/hardened gates are machine-checkable,
4. risk note includes compatibility + security mitigations,
5. parity report has RaptorQ sidecar + decode proof.
