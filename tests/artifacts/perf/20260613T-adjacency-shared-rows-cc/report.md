# Graph/DiGraph adjacency() shared rows — 7x → 2.16x vs nx (4.7x self-speedup)

Bead: br-r37-c1-adjshare
Agent: cc
Date: 2026-06-13

## Problem

`list(G.adjacency())` was ~7x slower than nx for Graph and DiGraph (140µs vs
20µs at 1000 nodes / 3000 edges). It routed through
`to_dict_of_dicts_undirected`, which serves the nested
`{node: {nbr: live_edge_dict}}` snapshot from the (nodes_seq, edges_seq)-keyed
cache but **copies every row dict per call** (`copy_dict_of_dicts_cache` →
`row.copy()` per node). That O(V + E) per-call copy exists for
`to_dict_of_dicts`'s isolation contract (callers mutate the result), but
`adjacency()` does NOT need it: nx's `adjacency()` is `iter(self._adj.items())`,
handing out the LIVE row objects — so two `adjacency()` calls yield the SAME row
object (`r1[u] is r2[u]`). fnx's copy path returned a fresh row each call,
diverging from nx on that identity.

## Fix (ONE lever: drop the per-row copy for adjacency)

- New `share_dict_of_dicts_cache` (readwrite.rs): assembles the outer dict with
  `set_item(node, row)` (clone_ref, no copy) — O(V), the same shape nx pays.
- New `adjacency_dict_shared` pyfunction: runs the SAME fast integer-CSR cache
  rebuild as `to_dict_of_dicts` (`rebuild_dict_of_dicts_cache` /
  `rebuild_dict_of_dicts_digraph_cache`) then shares rows. Returns None for
  non-exact graph types (caller falls back).
- `Graph.adjacency()` / `DiGraph.adjacency()` route to it.
  `to_dict_of_dicts` keeps `copy_dict_of_dicts_cache` (isolation unchanged).

This is both faster AND more nx-correct (now `r1[u] is r2[u]` == nx).

## Proof

- 8-seed × {Graph, DiGraph} parity sweep (mixed int/str/tuple keys, weighted
  edges): `[(n, dict(d)) for n, d in G.adjacency()]` == nx — **0 mismatches**.
- Leaf identity `d[u][v] is G[u][v]` holds (live edge dicts).
- Row sharing `r1[u] is r2[u]` now True == nx (was False).
- `to_dict_of_dicts` still returns live-leaf isolated rows (unchanged).
- Golden sha256 of `adjacency()` structure (300 nodes / 800 edges):
  `f3a1dc491e45004b84dfe8bd7d7eef6482477f5d14ab9cf5b6e681371be1751d`.
- Full python suite: only the known pre-existing failures remain.

## Timing (1000 nodes, 3000 edges, min-of-8×30)

| op                         | before | after  | nx     | after vs nx | self-speedup |
|----------------------------|--------|--------|--------|-------------|--------------|
| Graph `list(G.adjacency())`   | 140µs | 29.9µs | 13.8µs | 2.16x | 4.7x |
| DiGraph `list(G.adjacency())` | 140µs | 30.8µs | 14.7µs | 2.10x | 4.5x |

Residual ~2x is the O(V) outer-dict assembly (V set_items) per call — a future
lever could cache the assembled outer dict for O(1) warm. Multi adjacency()
(separate uncached builder) remains; and `list(G.adj.items())`/`dict(G.adj)`
for Multi (~5-6x) is the next adjacency-view target.
