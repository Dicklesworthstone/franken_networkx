# SCORECARD — weighted-variant algorithms: comprehensive domination + the one residual

- Agent: `BlackThrush` · 2026-06-21 · MEASURED (gnm 300/1500, random int weights 1..20)

## Domination (nx/fnx, >1 = fnx wins)
floyd_warshall 50.4x · betweenness(w) 14.6x · eigenvector(w) 13.5x · all_pairs_dijkstra(w) 4.07x ·
closeness(w) 3.99x · bellman_ford all_pairs 2.94x · mst kruskal 1.66x · mst prim 1.41x ·
astar 1.05x · single_source_dijkstra(w) 0.99x (parity, sub-ms) · harmonic(w) 0.97x (parity, 208ms)

## The one residual: pagerank(weighted) — depends on WHERE the weights live
- CLEAN (weights set at construction via add_edges_from(data) -> live in the Rust `inner`): **3.16x WIN**
- DIRTY (weights Python-set post-construction `G[u][v]['weight']=w` -> live in the mirror): **0.89x**
Byte-exact in both (1e-9 vs nx).

## Root cause (profiled)
pagerank's weighted path calls `_sync_rust_edge_attrs(G, edge_only=True)` -> the native
`_fnx_sync_edge_attrs_to_inner` (0.65ms for 1500 edges = ~0.43us/edge, a PyO3 per-edge read of the
mirror's Python attr dicts) so the native COO sees the weights. It runs on EVERY weighted-native
call (no synced-revision short-circuit), and gates ALL weighted native exporters (pagerank,
to_numpy_array, to_scipy...) on dirty graphs. CLEAN graphs already have weights in `inner` -> the
sync is a no-op -> they win.

## Why not fixed here
The clean correct fix is native + risky: either (a) revision-gate the sync (skip when the mirror
hasn't changed since the last sync — needs a reliable dirty/revision invariant across EVERY edge-
attr mutation, or stale-inner -> wrong results), or (b) have the COO builder read the mirror
directly. Both are fnx-classes/binding native changes with correctness surface that outweighs the
moderate value (the clean path already wins 3.16x; only post-construction-mutated weights pay it).
Characterized precisely for a focused native pass.
