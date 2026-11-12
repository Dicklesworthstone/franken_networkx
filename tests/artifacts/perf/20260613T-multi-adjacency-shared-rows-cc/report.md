# Multi adjacency() shared rows — 9x/7x → 2.1x vs nx (~4x/3x self-speedup)

Bead: br-r37-c1-adjshare (Multi leg)
Agent: cc
Date: 2026-06-13

## Problem

`list(G.adjacency())` for MultiGraph/MultiDiGraph was 9x / 7x slower than nx
(126µs / 94µs vs ~15µs at 1000 nodes / 3000 edges). Both serve the nested
`{node:{nbr:{key:edge_dict}}}` snapshot from the (nodes_seq,edges_seq)-keyed
`dict_of_dicts_cache` (`adjacency_dict_cached`), but ended in
`copy_dict_of_dicts_cache` — a per-call `row.copy()` per node (O(V+E)). nx's
`adjacency()` hands out the live `_adj[node]` rows (so two calls give the SAME
row object, `r1[u] is r2[u]`); the copy diverged from that.

This is the exact same lever already shipped for Graph/DiGraph (e6b768d24); this
applies it to the two Multi types via the `share_dict_of_dicts_cache` helper.

## Fix (ONE lever)

- `PyMultiGraph::adjacency_dict_cached` (lib.rs) and
  `PyMultiDiGraph::adjacency_dict_cached` (digraph.rs): final
  `copy_dict_of_dicts_cache` → `share_dict_of_dicts_cache` (assemble outer with
  shared rows, no per-row copy). The cache rebuild (correct nested rows, live
  leaf edge dicts) is unchanged; `to_dict_of_dicts` uses a separate view path,
  so sharing adjacency rows is safe.

Faster AND more nx-correct (`r1[u] is r2[u]` now matches nx).

## Proof

- 8-seed × {MultiGraph, MultiDiGraph} parity sweep (mixed int/str/tuple keys,
  parallel edges via repeated add_edge, weighted): nested
  `[(n, {nbr: dict(keyed)})]` == nx — **0 mismatches**.
- Leaf identity `d[u][v][k] is G[u][v][k]` holds (live edge dicts).
- Cache invalidation: `add_edge` after a cached `adjacency()` is reflected on the
  next call (nodes_seq/edges_seq bump → rebuild).
- Golden sha256 of nested adjacency (300 nodes / 800 edges):
  `06d437ee14fb8e27add73b0730f0337a6c4907f465b0d0e4b7f68d67749cb45a`.
- Full python suite: only the known pre-existing failures remain.

## Timing (1000 nodes, 3000 edges, min-of-8×30)

| op                              | before | after  | nx     | after vs nx | self-speedup |
|---------------------------------|--------|--------|--------|-------------|--------------|
| MultiGraph `list(G.adjacency())`   | 126µs | 30.5µs | 14.4µs | 2.12x | ~4.1x |
| MultiDiGraph `list(G.adjacency())` | 94µs  | 31.0µs | 14.9µs | 2.08x | ~3.0x |

All four graph types now serve `adjacency()` from a shared-row cache at ~2.1x of
nx. Residual ~2x is the O(V) outer-dict assembly per call (cacheable to O(1)
warm). Next adjacency-view target: `list(G.adj.items())`/`dict(G.adj)` for Multi
(~5-6x, ~800µs — the MultiAdjacencyView row materialization).

## Note

The remote build worker reused a stale `.rlib` across `rch exec` invocations
(worker swing) — clean+build had to be run in ONE `rch exec -- sh -c "cargo
clean -p fnx-python && maturin build ..."` so both ran on the same worker. A
stale `.so` silently served old code (probe via a temporary `eprintln` and
`r1[u] is r2[u]` confirmed liveness before trusting any benchmark).
