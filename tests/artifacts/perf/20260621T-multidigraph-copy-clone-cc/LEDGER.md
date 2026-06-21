# Perf WIN (RADICAL) — MultiDiGraph.copy() rebuild -> inner clone: 0.61x -> 1.86x (br-r37-c1-mdgcopyclone)

- Agent: `BlackThrush` · 2026-06-21 · File: `crates/fnx-python/src/digraph.rs`

## The gap
MultiDiGraph `_native_copy` (backs G.copy()) REBUILT the graph edge-by-edge via
add_edge_with_key_and_attrs — on a dense graph that is ~15000 String-keyed succ+pred
IndexMap inserts + per-edge py_dict_to_attr_map. 0.61x vs nx (40ms vs 22ms, n=300 m=15000).

## The fix
The rebuild walked edges_ordered() (edge INSERTION order) then reordered PRED. An inner
clone (`clone_with_fresh_policy`) is ALREADY in that insertion order (succ rows are never
reordered — only pred), so `inner.clone() + reorder_pred_rows_for_nx_copy_walk()` is
FIELD-IDENTICAL to the rebuild, just bulk. The Python mirrors (node_key_map, succ_py_keys,
node/edge_py_attrs, edge_py_keys, graph_attrs) are cloned with the SAME field choices the
rebuild made: pred_py_keys re-derived (empty), graph_attrs a FRESH dict (G.copy semantics),
edge_dirty_keys clean. Also drops the rebuild's eager empty edge-attr PyDicts (lazy
materialize is identity-preserving, aab122464).

## Verify (correctness-critical — copy() is used everywhere)
- BYTE-EXACT vs nx 2000/2000 (nodes + edges(keys,data) + succ adj order + PRED adj order +
  graph attrs + node attrs; attributed & bare, with self-loops & parallel edges).
- INDEPENDENCE: mutating copy's edge/graph/node attrs does NOT touch the source.
- edge attr dict IDENTITY stable (C[u][v][k] is C[u][v][k]).
- clippy clean; pytest -k 'multidigraph/copy/deepcopy/pickle/subgraph/reverse/to_*' 3075 passed.

## MEASURED (nx/fnx, warm min-8, n=300 m=15000)
| case                  | before | after  |
|-----------------------|--------|--------|
| MultiDiGraph.copy()   | 0.61x (40.4ms) | 1.86x (13.7ms) |

Substrate loss flipped to a ~3x win WITHOUT the int-CSR migration. FOLLOW-UP: same
rebuild->clone applies to MultiGraph.copy() (0.80x, lib.rs _native_copy, undirected
reorder_rows variant).
