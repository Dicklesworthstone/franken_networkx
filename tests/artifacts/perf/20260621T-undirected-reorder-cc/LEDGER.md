# Perf WIN (Rust) — undirected copy-walk row reorder O(E*degree) -> O(E) (br-r37-c1-predrebuild)

- Agent: `BlackThrush` · 2026-06-21 · File: `crates/fnx-classes/src/lib.rs`
- Full build (maturin release). Sibling of the directed pred-reorder fix (a953b8e62).

## The quadratic
`reorder_rows_for_nx_copy_walk` (undirected Graph, called inside copy-shaped
constructors: Graph.copy() etc.) rebuilt each adjacency row in nx's copy-walk order.
For each node pu, each EARLY neighbor v (pos(v)<pu) did a LINEAR SEARCH
`adj_indices[v].position(|w| w==pu)` to find pu's index within v's row -> O(E*degree),
QUADRATIC. It eroded dense Graph.copy() wins as density climbed (complete-graph copy:
9.53x @400 -> 5.91x @800; fnx time growing super-linearly 7.79 -> 52.79ms).

## The fix
Build each pu's early list directly: walk adj in (v, adj-index) order and append v to
early[pu] when pu>v. Distinct undirected neighbours make pos(v) the lead key and the
adj-index the tiebreak, so the walk reproduces the exact (pos(v), index-of-pu-in-adj[v])
ordering. Late neighbours (v>=pu) keep adj[pu] row order. O(E), no search, no sort.

## Verify
- BYTE-EXACT: fnx.copy().adj == the OLD reorder algorithm recomputed in Python on the
  SAME graph, 3003/3003 (gnm sparse..dense + complete graphs). (A naive fnx-vs-nx copy
  test shows mismatches but those are a PRE-EXISTING gnm_random_graph source adjacency-
  order divergence, not the copy — confirmed: orig fnx G.adj != orig nx GN.adj.)
- conformance: pytest -k 'copy or subgraph or relabel or reverse' 3644 passed, 154 skip.
  clippy fnx-classes clean.

## MEASURED (nx/fnx, >1 = fnx WINS) — dense Graph.copy()
| case                          | before | after  |
|-------------------------------|--------|--------|
| complete_graph(400).copy()    | 9.53x  | 15.63x |
| complete_graph(800).copy()    | 5.91x  | 56.13x (52.79 -> 5.46ms, ~10x) |

The win was being eroded by the quadratic at high density; the O(E) rebuild restores
flat scaling (56x at n=800 instead of a shrinking-toward-loss 5.91x). Byte-exact,
conformance green, no regression on sparse (stays a win). Kept.
