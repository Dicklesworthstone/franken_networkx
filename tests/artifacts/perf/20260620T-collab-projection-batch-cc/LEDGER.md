# Perf lever (code-only, bench deferred) — collaboration_weighted_projected_graph directed batch (br-r37-c1-collabbatch)

- Agent: `BlackThrush` · 2026-06-20 · File: `python/franken_networkx/bipartite.py`
- DISK-LOW turn: code-only, no build/bench. Parity verified with existing install.

`collaboration_weighted_projected_graph` takes a snapshot fast path
(`_weighted_projection_inprocess`) for undirected simple Graph B, but BAILS for a
DIRECTED bipartite B (type(B) is not Graph). The directed fallback then rebuilt the
projection via a per-node `add_node` + per-edge `add_edge` PyO3 round-trip (the
construction tax). Collect the (node, attrs) and (u, v, weight-dict) tuples and
commit via add_nodes_from / add_edges_from in one bulk pass each — identical
node/edge order and weights, only the construction is batched.

## Parity (existing install, no build)

500 random DIRECTED bipartite graphs (edges both directions, node attrs, graph
attrs): 0 mismatches vs networkx (node order, edge order, weights to 1e-12, node
attrs, graph attrs). Undirected fast path unaffected (sanity-checked).

## Perf

BENCH DEFERRED (disk-low). Expected win consistent with the construction-tax batch
lever ([[reference_batch_add_edges_from_construction]]): the per-edge add_edge loop
is the proven 2x+ tax on graph-building Python wrappers. Measure when disk recovers.
