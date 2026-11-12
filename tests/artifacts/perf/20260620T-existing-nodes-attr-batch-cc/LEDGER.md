# Perf win — existing-nodes attributed edge index batch (br-r37-c1-dodattrbatch)

- Agent: `BlackThrush` · 2026-06-20 · isolated worktree at origin/main `69c6f1fd1`
- Files: `crates/fnx-classes/src/lib.rs` + `crates/fnx-python/src/lib.rs`
  (+ a clarifying comment in `__init__.py`; all unreserved)

## Root cause

The FRESH attributed-edge fast batch (`try_add_fresh_exact_int_attr_edge_batch`)
gates on `node_count == 0`. Any helper that does `add_nodes_from(...)` BEFORE
`add_edges_from(attr)` — generators, from_dict_of_*, much user code — defeats it
and falls to the ~4x-slower String-keyed general attributed batch. Clean-measured:
attributed `add_edges_from` on a FRESH graph is 1.83x nx, but on a graph-with-nodes
was ~0.5x.

## Lever

Added the attributed sibling of the plain existing-nodes index batch:
- `Graph::extend_existing_index_edges_with_attrs_unrecorded` (fnx-classes) — bulk
  insert by integer index with attrs; duplicates MERGE last-wins like add_edge.
- `collect_existing_exact_int_attr_edge_indices` + `try_add_existing_exact_int_attr_edge_index_batch`
  (fnx-python), wired into `try_add_attr_edge_batch` after the fresh path.
Attrs stay LAZY in the inner AttrMap (no eager py mirror), matching the fresh path.

## Win vs NetworkX 3.6.1 (clean worktree, warm min-of-20)

| add_edges_from-after-contiguous-int-nodes (attr), 1500n/3000e | before | after |
| --- | ---: | ---: |
| | ~0.5x | **2.05x** (1.48ms -> 0.73ms) |

## Parity

1500 random Graphs across fresh / pre-added (in-order AND shuffled) nodes /
empty-attr / duplicate edges (merge): 0 mismatches (node order, edges+data, adj
row order). pytest -k 'add_edge or from_dict or convert or construct': 958 passed
(lone failure is the pre-existing fnx.Graph RCM test — confirmed failing on the
pre-change .so).

## Scope note

Fires only when node labels equal their indices (contiguous-int prefix in order).
A graph from `to_dict_of_dicts` of a NON-0..n-ordered source still falls back to
the String-keyed batch (from_dict_of_dicts keeps its symmetric-reverse dedup,
0.74x). A general int-LABEL (not index) attr batch would extend this further.
