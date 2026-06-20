# Negative-Evidence Ledger — MultiDiGraph copy()/subgraph clean re-measure (br-r37-c1-yl606)

- Agent: `BlackThrush` · 2026-06-20
- Method: ISOLATED git worktree at origin/main `e127904e0` + PYTHONPATH import
  (the main checkout's shared install was contaminated by a peer's uncommitted
  WIP — see [[reference_warm_sweep_false_losses_2026]] on contamination/noise).
  Zero touch to the shared site-packages; warm min-of-15, 6 warmup.

## Clean measurements (origin/main, uncontaminated)

| MultiDiGraph method | no-attr | with-attr |
| --- | ---: | ---: |
| `copy()` | 0.57x | 0.46x |
| `reverse()` | 0.96x | 1.05x |
| `to_undirected()` | 1.23x | 0.95x |
| `subgraph().copy()` | 0.87x | (≈copy) |

Note: the contaminated main-checkout measurement earlier this session reported
`subgraph().copy()` at 0.65-0.74x — OVERSTATED by peer-WIP/host noise. Clean
isolated value is 0.87x. Always measure in an isolated worktree when the shared
install is dirty.

## Red herrings RULED OUT (so future work doesn't chase them)

1. **NOT a double-build.** `fnx.MultiDiGraph.subgraph(nodes)` returns a cheap
   FROZEN VIEW (0.11ms, raises on mutation) exactly like nx — not an eager graph.
   So `subgraph().copy()` = view + one copy, same as nx. The loss is purely the
   copy materialization, identical root cause to plain `copy()`.
2. **NOT the pred-row reorder.** `reorder_pred_rows_for_nx_copy_walk` is a small
   fraction; a transpose rewrite of it was already measured neutral for copy.

## Confirmed root cause (single lever)

`MultiDiGraph`/`MultiGraph` store adjacency as fully String-keyed nested IndexMaps
for BOTH successors AND predecessors, PLUS the edge map — so `clone_with_fresh_policy`
deep-clones the edge set 3x over in String space. The ONLY real lever is the
integer-CSR migration of the multigraph adjacency (the scale of DiGraph's
br-r37-c1-d58s8), which clones integer Vecs instead of String IndexMaps. Simple
Graph/DiGraph copy already WINS 3.8-13x precisely because they are integer-CSR.

No code shipped: every sub-migration lever (pred-clone elimination, reorder
transpose) is clone-dominated and measures neutral. Reserved for a focused
integer-CSR migration effort.
