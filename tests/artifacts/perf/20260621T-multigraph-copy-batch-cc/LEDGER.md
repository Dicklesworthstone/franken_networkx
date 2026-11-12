# Perf WIN — MultiGraph.copy() bulk keyed-edge extend + lazy attrs: 0.88x -> 1.22x (br-r37-c1-mgcopybatch)

- Agent: `BlackThrush` · 2026-06-21 · File: `crates/fnx-python/src/lib.rs`
- The MultiGraph copy win the clone fix (reverted, 7b45a463d) could NOT deliver, done safely.

## Why not the clone
MultiGraph.copy() must keep the edge-by-edge REBUILD because reorder_rows_for_nx_copy_walk
is input-order dependent and needs the edges_ordered() insertion order (an inner clone
preserves the source's possibly-reordered order -> copy-of-a-copy diverges, see
7b45a463d). So optimize the rebuild itself instead.

## The fix (two construction-tax levers on the kept rebuild)
1. Collect the keyed edges in edges_ordered() order and commit them through ONE
   extend_keyed_edges_with_attrs_unrecorded (the bulk API DESIGNED for copy/convert) —
   per-edge add_edge_with_key_and_attrs paid TWO record_decision ledger pushes/edge
   (30000 on a dense graph). Insertion order preserved, so reorder_rows is still correct.
2. Drop the rebuild's eager empty edge-attr PyDict for attr-less edges (15000 allocs) —
   lazy materialize_edge_py_attrs is identity-preserving (aab122464).

## Verify
- BYTE-EXACT vs nx 2000/2000 INCL copy-of-a-copy (the case that broke the clone): edges
  (keys,data) + adj order + node attrs. Independence holds; empty-attr edge dict reads {}
  with stable identity. test_pickle_row_order_parity 14 passed; clippy clean; pytest -k
  'multigraph/copy/deepcopy/pickle/subgraph/to_undirected/convert/union/compose' 3978 passed.

## MEASURED (nx/fnx, warm min-8, n=300 m=15000)
| case               | before | after  |
|--------------------|--------|--------|
| MultiGraph.copy()  | 0.88x  | 1.22x (40 -> 35.5ms) |

Loss flipped to a win on the kept rebuild (the clone couldn't, the bulk+lazy could).
