# Legacy Anchor Map

## Legacy Scope
- packet id: `FNX-P2C-001`
- subsystem: Graph core semantics (`Graph`, `DiGraph`, `MultiGraph`, `MultiDiGraph`)
- legacy module paths:
  - `legacy_networkx_code/networkx/networkx/classes/graph.py`
  - `legacy_networkx_code/networkx/networkx/classes/digraph.py`
  - `legacy_networkx_code/networkx/networkx/classes/multigraph.py`
  - `legacy_networkx_code/networkx/networkx/classes/multidigraph.py`
- extraction timestamp (utc): `2026-02-15T04:27:00Z`

## Contract Row Aliases (from `artifacts/phase2c/FNX-P2C-001/contract_table.md`)
- `IC-1`: Input Contract / `packet operations`
- `IC-2`: Input Contract / `compatibility mode`
- `OC-1`: Output Contract / `algorithm-state result`
- `OC-2`: Output Contract / `evidence artifacts`
- `EC-1`: Error Contract / `unknown incompatible feature -> fail-closed`
- `EC-2`: Error Contract / `malformed input strict -> fail-closed`
- `EC-3`: Error Contract / `malformed input hardened -> bounded defensive recovery + audit`
- `SD-1`: Strict-Hardened Divergence / strict exact behavior
- `HD-1`: Strict-Hardened Divergence / hardened bounded defensive handling
- `DC-1`: Determinism Commitments / tie-break policy
- `DC-2`: Determinism Commitments / ordering policy

## Anchor Index
| anchor id | source anchor | symbols | extracted behavior claim | confidence |
|---|---|---|---|---|
| `A01` | `legacy_networkx_code/networkx/networkx/classes/graph.py:22-45,348-391` | `_CachedPropertyResetterAdj`, `Graph.__init__` | Graph initialization always creates `_node` + `_adj`, then optionally loads incoming data via `convert.to_networkx_graph`; setting graph internals invalidates cached adjacency views. | high |
| `A02` | `legacy_networkx_code/networkx/networkx/classes/graph.py:534-660` | `Graph.add_node`, `Graph.add_nodes_from` | Nodes reject `None`; repeated adds update attribute dicts in-place; tuple form in `add_nodes_from` overrides common kwargs; cache is always cleared after mutation. | high |
| `A03` | `legacy_networkx_code/networkx/networkx/classes/graph.py:661-753` | `Graph.remove_node`, `Graph.remove_nodes_from` | `remove_node` raises on missing node; `remove_nodes_from` silently ignores missing nodes; removal deletes incident edges via explicit neighbor iteration. | high |
| `A04` | `legacy_networkx_code/networkx/networkx/classes/graph.py:916-1184` | `Graph.add_edge`, `Graph.add_edges_from`, `Graph.remove_edge`, `Graph.remove_edges_from` | Edge adds auto-materialize missing endpoint nodes; duplicate edges in simple graphs update one shared datadict; `remove_edge` raises on missing edge while `remove_edges_from` silently ignores misses. | high |
| `A05` | `legacy_networkx_code/networkx/networkx/classes/graph.py:1186-1301,1591-1734,2012-2055` | `Graph.update`, `Graph.copy`, `Graph.to_directed`, `Graph.nbunch_iter` | `update` accepts graph-like or edge/node collections and raises only when both inputs are absent; copy semantics are explicit (independent shallow for `copy`, deep for `to_directed` non-view). | high |
| `A06` | `legacy_networkx_code/networkx/networkx/classes/digraph.py:35-57,59-85,343-447` | `_CachedPropertyResetterAdj`, `_CachedPropertyResetterPred`, `DiGraph.__init__`, `DiGraph.adj/succ/pred` | Directed graphs maintain paired `_succ` and `_pred` maps; descriptor resets invalidate cached directed views when backing maps are replaced. | high |
| `A07` | `legacy_networkx_code/networkx/networkx/classes/digraph.py:449-895` | `DiGraph.add_node(s)`, `DiGraph.remove_node(s)`, `DiGraph.add_edge(s)`, `DiGraph.remove_edge(s)` | Directed mutations mirror Graph error asymmetry (single remove raises, bulk remove silently ignores misses) while maintaining consistent predecessor/successor mirror updates. | high |
| `A08` | `legacy_networkx_code/networkx/networkx/classes/digraph.py:1264-1362` | `DiGraph.to_undirected`, `DiGraph.reverse` | `to_undirected(reciprocal=True)` filters by reciprocal edges; when opposite directed edges carry different attrs, resulting undirected edge attrs are order-dependent and documented as arbitrary; `reverse(copy=False)` returns a view. | high |
| `A09` | `legacy_networkx_code/networkx/networkx/classes/multigraph.py:320-383,413-440,442-633` | `MultiGraph.__init__`, `MultiGraph.new_edge_key`, `MultiGraph.add_edge(s)` | Multigraph dict ingestion has tri-state `multigraph_input` behavior; default key allocation uses first unused integer, but may skip gaps after deletions; add-path supports 2/3/4 tuple edge forms with key-data disambiguation. | high |
| `A10` | `legacy_networkx_code/networkx/networkx/classes/multigraph.py:635-760` | `MultiGraph.remove_edge`, `MultiGraph.remove_edges_from` | `remove_edge(key=None)` removes the most recently inserted key via `popitem()`; `remove_edges_from` silently ignores absent edges and supports mixed tuple arities. | high |
| `A11` | `legacy_networkx_code/networkx/networkx/classes/multigraph.py:1034-1183` | `MultiGraph.copy`, `MultiGraph.to_directed` | Multigraph copy is independent-shallow for attrs; directed conversion deep-copies graph/node/edge attrs and preserves explicit edge keys. | high |
| `A12` | `legacy_networkx_code/networkx/networkx/classes/multidigraph.py:311-374,427-523,525-599` | `MultiDiGraph.__init__`, `MultiDiGraph.add_edge`, `MultiDiGraph.remove_edge` | MultiDiGraph combines directed predecessor/successor contracts with multiedge key semantics; missing edge/key raises on single remove while keyless removal is insertion-order LIFO (`popitem`). | high |
| `A13` | `legacy_networkx_code/networkx/networkx/classes/multidigraph.py:879-976` | `MultiDiGraph.to_undirected`, `MultiDiGraph.reverse` | Directed multigraph undirect conversion has reciprocal filtering and documented arbitrary attr choice for opposite-direction conflicts; reverse supports copy and view modes. | high |

## Behavior Notes

### Normal Pathway Behaviors
- Graph classes auto-create endpoint nodes during edge insertion (`A04`, `A07`, `A09`, `A12`).
- Bulk mutation APIs accept iterable edge tuples with strict arity checks (`A04`, `A07`, `A09`).
- Directed classes keep `_succ` and `_pred` mirrors consistent after every mutation (`A06`, `A07`, `A12`).
- Copy and conversion APIs distinguish view vs copy mode and shallow vs deep attribute copy behavior (`A05`, `A08`, `A11`, `A13`).

### Edge Case Behaviors
- Duplicate simple-graph edge insertion updates existing edge datadict (does not create parallel edge) (`A04`).
- `Graph.update` treats graph-like objects specially (`nodes`/`edges` attributes) and merges graph attrs (`A05`).
- `MultiGraph`/`MultiDiGraph` default edge keys are generated by `new_edge_key` and are not guaranteed contiguous after removals (`A09`).
- Bulk removals silently ignore missing edges/nodes, unlike singular removals (`A03`, `A04`, `A07`, `A10`).

### Adversarial or Malformed Input Behaviors
- Any add-node/add-edge path with node `None` raises `ValueError` (`A02`, `A04`, `A07`, `A09`, `A12`).
- Edge tuple arity violations raise `NetworkXError` (or `TypeError` when non-iterable tuples are malformed in multigraph edge forms) (`A04`, `A07`, `A09`).
- `multigraph_input=True` on non-conforming dict-of-dict-of-dict-of-dict raises `NetworkXError` during constructor conversion (`A09`, `A12`).
- `Graph.update()` with neither `edges` nor `nodes` raises `NetworkXError` (`A05`).

### Ambiguous or Undefined Legacy Behaviors (Tagged + Policy)
- `AMB-01` attr merge order ambiguity in directed-to-undirected conversion:
  - anchors: `A08`, `A13`
  - legacy note: attr selection is explicitly described as arbitrary when both directions exist with conflicting data.
  - compatibility policy: strict mode preserves encounter-order semantics exactly; hardened mode may emit deterministic audit metadata but must not change selected payload unless allowlisted.
- `AMB-02` multiedge removal order when `key=None`:
  - anchors: `A10`, `A12`
  - legacy mechanism: `popitem()` implies LIFO-by-insertion for modern dicts.
  - compatibility policy: strict mode enforces insertion-order LIFO; hardened mode identical (no divergence allowed).
- `AMB-03` iteration-order dependence in edge/node traversal:
  - anchors: `A01`, `A04`, `A06`, `A09`
  - legacy behavior depends on Python dict insertion order.
  - compatibility policy: strict mode follows insertion order exactly; hardened mode may validate order invariants and fail-closed on detected drift.
- `AMB-04` self-mutation while iterating:
  - anchors: `A02`, `A04`, `A07`, `A09`
  - legacy docs warn of runtime errors when iterables mutate underlying dicts during iteration.
  - compatibility policy: strict mode surfaces native runtime failure; hardened mode may preflight-snapshot iterable only when allowlisted and logged.

## Extraction Ledger (Behavior Region -> Contract Rows -> Oracle Tests)
| region id | behavior region | source anchors | contract rows | planned oracle tests | notes |
|---|---|---|---|---|---|
| `R01` | Graph init and cache invalidation | `A01` | `IC-1`, `DC-2`, `OC-1` | `legacy_networkx_code/networkx/networkx/classes/tests/test_graph.py:620-636` | Cache-reset descriptors are core to view coherency expectations. |
| `R02` | Node add/update and None rejection | `A02` | `IC-1`, `EC-2`, `SD-1` | `legacy_networkx_code/networkx/networkx/classes/tests/test_graph.py:637-683` | Attribute override precedence (tuple attrs over kwargs) must match exactly. |
| `R03` | Node removals (raise vs silent) | `A03` | `IC-1`, `EC-2`, `EC-3`, `SD-1`, `HD-1` | `legacy_networkx_code/networkx/networkx/classes/tests/test_graph.py:684-698` | Single remove raises; bulk remove silent ignore is compatibility-critical. |
| `R04` | Simple graph edge add/remove semantics | `A04` | `IC-1`, `EC-2`, `EC-3`, `DC-2` | `legacy_networkx_code/networkx/networkx/classes/tests/test_graph.py:699-747` | Shared datadict aliasing for undirected endpoints is observable. |
| `R05` | Graph update/copy/conversion behavior | `A05` | `IC-1`, `OC-1`, `EC-2`, `DC-2` | `legacy_networkx_code/networkx/networkx/classes/tests/test_graph.py:783-853`; `legacy_networkx_code/networkx/networkx/classes/tests/test_graph.py:264-350`; `legacy_networkx_code/networkx/networkx/classes/tests/test_graph.py:500-563` | Includes error on empty update and shallow/deep copy distinctions. |
| `R06` | Directed predecessor/successor invariants | `A06`, `A07` | `IC-1`, `DC-2`, `OC-1` | `legacy_networkx_code/networkx/networkx/classes/tests/test_digraph.py:135-145`; `legacy_networkx_code/networkx/networkx/classes/tests/test_digraph.py:236-279` | `_succ`/`_pred` mirror integrity is a strict invariant. |
| `R07` | Directed undirect/reverse conversion | `A08` | `IC-1`, `DC-1`, `SD-1`, `HD-1` | `legacy_networkx_code/networkx/networkx/classes/tests/test_digraph.py:101-123` | Reciprocal filter and reverse view mutability constraints are required. |
| `R08` | Multigraph constructor/input parsing and key policy | `A09` | `IC-1`, `EC-1`, `EC-2`, `DC-1`, `DC-2` | `legacy_networkx_code/networkx/networkx/classes/tests/test_multigraph.py:203-275`; `legacy_networkx_code/networkx/networkx/classes/tests/test_multigraph.py:320-362` | Dict topology disambiguation and key assignment rules drive parity. |
| `R09` | Multigraph remove semantics and LIFO keyless removal | `A10` | `IC-1`, `DC-1`, `EC-2`, `EC-3` | `legacy_networkx_code/networkx/networkx/classes/tests/test_multigraph.py:363-406` | `popitem()` behavior is a tie-break surface; do not normalize away. |
| `R10` | Multidigraph directed multiedge mutation semantics | `A12` | `IC-1`, `DC-1`, `DC-2`, `EC-2`, `EC-3` | `legacy_networkx_code/networkx/networkx/classes/tests/test_multidigraph.py:277-393` | Must preserve key-aware directed predecessor/successor updates. |
| `R11` | Multidigraph undirect/reverse ambiguous attr merge | `A13` | `IC-1`, `DC-1`, `SD-1`, `HD-1` | `legacy_networkx_code/networkx/networkx/classes/tests/test_multidigraph.py:223-244` | Conflict attr selection remains intentionally legacy-compatible. |

## Oracle Coverage Cross-Check
- fixture manifest references packet fixtures:
  - `graph_core_mutation_hardened.json`
  - `graph_core_shortest_path_strict.json`
- legacy class test anchors used for planned packet-001 differential expansion:
  - `legacy_networkx_code/networkx/networkx/classes/tests/test_graph.py`
  - `legacy_networkx_code/networkx/networkx/classes/tests/test_digraph.py`
  - `legacy_networkx_code/networkx/networkx/classes/tests/test_multigraph.py`
  - `legacy_networkx_code/networkx/networkx/classes/tests/test_multidigraph.py`

## Compatibility Risk
- risk level: `critical`
- rationale:
  - Core graph mutation semantics are foundational for all downstream algorithm parity.
  - Tie-break/output ordering depends on dict insertion semantics plus multiedge key policy.
  - Directed-undirected conversion includes documented arbitrary attr choice; any normalization can change observable behavior.
- mitigation:
  - enforce strict parity checks on `R01..R11` behaviors before packet promotion.
  - keep hardened-mode deviations explicitly allowlisted and audit-logged only.
