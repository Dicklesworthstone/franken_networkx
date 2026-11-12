# br-r37-c1-0ek49 (part 1) — G.copy() adjacency row order = nx rebuild-walk order

Date: 2026-06-05 · Agent: cc (BlackThrush)

## Bug
nx `Graph.copy()` rebuilds via `add_edges_from((u, v, d) for u in _adj
for v in _adj[u])`: an unordered pair enters BOTH endpoint rows at its
first u-major touch, so copies REORDER undirected adjacency rows —
`adj[5] = [28, 7, 5]`, not the source's `[7, 28, 5]` — and directed
copies fill PRED rows in walk order (`pred[7] = [5, 9]` vs edge-order
`[9, 5]`). fnx's bulk `inner.clone()` (br-r37-c1-copyclone) preserved
source rows verbatim. Uniform keys affected; blast radius = every
`.copy()`, `subgraph().copy()` downstream iteration order.

## Fix (one lever)
`Graph::reorder_rows_for_nx_copy_walk` (fnx-classes/lib.rs): row u =
neighbors at smaller node position sorted by their touch time
`(pos(v), index of u within row v)`, then remaining neighbors
(self-loops included) in original row order; integer `adj_indices`
mirror rebuilt to match. `DiGraph::reorder_pred_rows_for_nx_copy_walk`:
each pred row fully sorted by `(pos(u), index of v within succ[u])`.
Called from PyGraph::copy / PyDiGraph::copy on the fresh clone — keeps
the bulk-clone perf win, only permutes row order. MultiGraph /
MultiDiGraph `_native_copy` already rebuild in walk-compatible order
(probed clean).

## Proof
- Pinned probes: 4-class copy rows+edges, directed pred walk order,
  copy-of-copy fixed point — all match nx.
- 300-trial random mutate-then-copy sweep: 0 divergences (rows, pred
  rows, edges() order).
- 14 new tests in test_copy_row_order_parity.py.
- Full pytest: see full_pytest.stdout (failure set vs HEAD compared).

## Residual (kept open on the bead)
- deepcopy must PRESERVE source structure verbatim (wrapper
  `_graph_deepcopy` rebuild-walks instead; all four classes).
- subgraph-view row iteration: nx `FilterAtlas.__iter__` switches to
  keep-SET iteration order when `2*len(keep) < len(row)` (CPython set
  hash order) — metamorphic seed 1157 reproduces via
  `subgraph([1,3]).copy()` on a 5-node row.
