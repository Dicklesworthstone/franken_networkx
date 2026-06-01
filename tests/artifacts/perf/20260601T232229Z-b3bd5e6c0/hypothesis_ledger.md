# Hypothesis Ledger — betweenness_centrality (N=1500, M=6000)

Each candidate explanation for where the ~1025 ms/call goes, marked `supports` / `rejects`
with evidence. Total per-call ≈ 1025 ms; BFS phase 946 ms (93%), accum 29 ms (3%), alloc 19 ms (2%).

- **String→index adjacency resolution dominates (`neighbors_iter` + `get_node_index` per edge)** :
  **SUPPORTS** — `lookup_sweep` microbench isolates exactly these two ops over the full edge set =
  0.43-0.52 ms/sweep; Brandes runs 1500 sweeps → ~640-780 ms = ~62-76% of total. Consistent with
  BFS phase = 93% (the rest of BFS is queue/distance/sigma/predecessor bookkeeping).

- **Per-source `predecessors = vec![Vec::new(); n]` (n² Vec headers) is a major cost** :
  **REJECTS** — `alloc_phase_ms` (which brackets all four per-source vec allocations) is only
  19-22 ms (~2%). Allocation is not the bottleneck; the string lookups are.

- **Dependency-accumulation back-sweep is a hotspot** :
  **REJECTS** — `accum_phase_ms` = 29 ms (~3%).

- **Per-source reallocation of `sigma`/`distance`/`stack` (no reuse across sources) is major** :
  **REJECTS** — folded into the 2% alloc phase; reusing buffers would save <2%.

- **pagerank / connected_components / dijkstra are hotspots at this scale** :
  **REJECTS** — 1.2 ms / 0.08 ms / 0.006 ms per call respectively; negligible vs betweenness/closeness.

- **closeness_centrality shares the same root-cause hotspot** :
  **SUPPORTS** — 826-841 ms/call, same `in_neighbors_iter(name)` + index-resolve BFS-per-source
  structure (lib.rs ~2238). One fix (integer-indexed adjacency) addresses both.

## Conclusion

One structural lever — **precompute an integer-indexed adjacency (CSR / `Vec<Vec<usize>>`) per
call and iterate `usize` neighbor indices in the inner loop** — addresses the ~76% lookup share
shared by `betweenness_centrality`, `closeness_centrality`, and `harmonic_centrality`. Allocation
and accumulation micro-tuning would yield <5% and should be deprioritized. Hand off to
extreme-software-optimization (score Impact × Confidence / Effort) via the filed perf beads.
